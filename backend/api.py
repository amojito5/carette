"""
Carette - API backend autonome pour le widget de covoiturage
Extraction des endpoints carpool de l'API principale
"""
from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
import requests
from pymysql.err import IntegrityError
import math
import json
import sys
import os
import urllib.parse

# Charger variables d'environnement
load_dotenv()

# Configuration
BASE_URL = os.getenv('BASE_URL', 'http://localhost:9000')
STATIC_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Ajouter le dossier backend au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import des modules DB, buffer géographique et validation
import sql
import init_carpool_tables
from route_buffer import create_buffer_from_route, create_buffer_simple
from temporal_buffer import create_temporal_buffer, calculate_detour_time_osrm, haversine_distance
from validation import (
    validate_coordinates, sanitize_text, validate_datetime,
    validate_integer, validate_user_id, validate_email
)
# Import token manager pour les magic links
from token_manager import verify_token, generate_accept_link, generate_refuse_link, generate_cancel_passenger_link
# Import email system
from email_sender import send_email
from email_templates import (
    email_new_reservation_request,
    email_request_sent_to_passenger,
    email_reservation_confirmed_to_passenger
)
# Import modules v2 pour flux sans comptes
try:
    from sql import db_cursor as db_cursor_v2  # Utiliser sql au lieu de sql_v2
    from emails import (
        generate_confirmation_token,
        email_payment_simulation
    )
    V2_ENABLED = True
    logger.info("✅ API v2 (email/WhatsApp workflow) activée")
except ImportError as e:
    V2_ENABLED = False
    logger.warning(f"⚠️  API v2 non disponible: {e}")

app = Flask(__name__)

# Initialiser les tables carpool au démarrage (création automatique si inexistantes)
try:
    init_carpool_tables.init_carpool_tables()
    logger.info("✅ Tables carpool initialisées")
except Exception as e:
    logger.error(f"❌ Erreur initialisation tables carpool: {e}")
    # Ne pas bloquer le démarrage si c'est juste un problème de colonnes existantes
    if "Duplicate column" not in str(e):
        raise

# Initialiser les tables RSE au démarrage
try:
    init_carpool_tables.init_rse_weekly_tables()
    logger.info("✅ Tables RSE initialisées")
except Exception as e:
    logger.error(f"❌ Erreur initialisation tables RSE: {e}")
    # Ne pas bloquer le démarrage
    if "Duplicate column" not in str(e) and "already exists" not in str(e):
        raise

# SECRET_KEY obligatoire en production
SECRET_KEY = os.getenv('CARETTE_SECRET_KEY')
if not SECRET_KEY:
    if os.getenv('CARETTE_DEBUG', 'False').lower() == 'true':
        logger.warning("⚠️  CARETTE_SECRET_KEY non définie, utilisation d'une clé de développement")
        SECRET_KEY = 'dev-insecure-key-change-me-' + os.urandom(24).hex()
    else:
        logger.error("❌ CARETTE_SECRET_KEY doit être définie en production")
        sys.exit(1)

app.config['SECRET_KEY'] = SECRET_KEY
app.debug = os.getenv('CARETTE_DEBUG', 'False').lower() == 'true'

# CORS restrictif - Validation des origines
allowed_origins_str = os.getenv('CARETTE_ALLOWED_ORIGINS', '')
if not allowed_origins_str:
    if app.debug:
        logger.warning("⚠️  CARETTE_ALLOWED_ORIGINS non définie, autorisation localhost uniquement")
        allowed_origins = ['http://localhost:3000', 'http://localhost:8000', 'http://localhost:9000']
    else:
        logger.error("❌ CARETTE_ALLOWED_ORIGINS doit être définie en production")
        sys.exit(1)
else:
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',') if origin.strip()]

# Configuration CORS stricte
CORS(app, resources={
    r"/api/*": {
        "origins": allowed_origins,
        "methods": ["GET", "POST", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
}, supports_credentials=True)

# Route pour servir les fichiers statiques (images de cartes, etc.)
@app.route('/static/<path:filename>')
def serve_static(filename):
    """Sert les fichiers statiques (images de cartes, etc.)"""
    return send_from_directory(STATIC_FOLDER, filename)

# Route pour servir la page d'accueil
@app.route('/')
def serve_index():
    """Sert la page d'accueil"""
    root_folder = os.path.dirname(STATIC_FOLDER)
    return send_from_directory(root_folder, 'index.html')

# Route pour servir les fichiers HTML à la racine
@app.route('/<path:filename>')
def serve_html(filename):
    """Sert les fichiers HTML et autres à la racine du projet"""
    root_folder = os.path.dirname(STATIC_FOLDER)
    # Sécurité: bloquer l'accès aux fichiers sensibles
    if filename.startswith('.') or filename.startswith('backend/') or '__pycache__' in filename:
        return jsonify({'error': 'Access denied'}), 403
    try:
        return send_from_directory(root_folder, filename)
    except Exception:
        return jsonify({'error': 'File not found'}), 404

# Rate limiting avec Redis (ou mémoire en dev)
storage_uri = os.getenv('REDIS_URL', 'memory://')
if storage_uri == 'memory://' and not app.debug:
    logger.warning("⚠️  Rate limiting en mémoire (non recommandé en production). Utilisez Redis.")

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=storage_uri
)


def estimate_realistic_duration(distance_meters, route_data=None):
    """
    Estime une durée réaliste de trajet en tenant compte :
    - De la distance
    - Du type de route (autoroute, nationale, etc.)
    - Des conditions de circulation typiques
    """
    if not distance_meters or distance_meters <= 0:
        return 0
    
    # Vitesse moyenne de base : 50 km/h (circulation urbaine/mixte)
    base_speed_kmh = 50
    
    # Si on a des données de route OSRM, analyser pour ajuster
    if route_data and isinstance(route_data, dict):
        geometry = route_data.get('geometry', {})
        if isinstance(geometry, dict) and 'coordinates' in geometry:
            coords = geometry['coordinates']
            # Routes longues (>50km) : probablement autoroute, vitesse plus élevée
            if distance_meters > 50000:
                base_speed_kmh = 90
            # Routes moyennes (10-50km) : nationale/départementale
            elif distance_meters > 10000:
                base_speed_kmh = 70
    
    # Calcul durée en secondes
    distance_km = distance_meters / 1000
    duration_hours = distance_km / base_speed_kmh
    duration_seconds = duration_hours * 3600
    
    # Ajouter 10% de marge pour les imprévus (feux, ralentissements)
    duration_seconds *= 1.1
    
    return int(duration_seconds)


def calculate_osrm_route(waypoints, get_alternatives=False):
    """
    Calcule un itinéraire via OSRM avec support des alternatives
    
    Args:
        waypoints: Liste de [lon, lat] pour l'itinéraire
        get_alternatives: Si True, retourne jusqu'à 3 routes alternatives
    
    Returns:
        Dict avec route principale et alternatives si demandées
    """
    if not waypoints or len(waypoints) < 2:
        return {"error": "Au moins 2 points requis"}
    
    # Serveurs OSRM avec fallback
    servers = [
        'https://router.project-osrm.org',
        'https://routing.openstreetmap.de/routed-car',
        'http://router.project-osrm.org'
    ]
    
    # Construire URL avec coordonnées
    coords_str = ';'.join([f"{lon},{lat}" for lon, lat in waypoints])
    
    for server in servers:
        try:
            url = f"{server}/route/v1/driving/{coords_str}"
            params = {
                'overview': 'full',
                'geometries': 'geojson',
                'steps': 'true'
            }
            
            if get_alternatives:
                params['alternatives'] = 3
            
            resp = requests.get(url, params=params, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                
                if data.get('code') == 'Ok' and 'routes' in data:
                    routes = data['routes']
                    
                    result = {
                        'route': routes[0],
                        'alternatives': routes[1:] if get_alternatives and len(routes) > 1 else []
                    }
                    
                    # Ajouter durées réalistes estimées
                    for r in [result['route']] + result['alternatives']:
                        r['realistic_duration'] = estimate_realistic_duration(
                            r.get('distance', 0),
                            r
                        )
                    
                    return result
        
        except Exception as e:
            print(f"⚠️ OSRM {server} failed: {e}")
            continue
    
    return {"error": "Tous les serveurs OSRM ont échoué"}


def generate_static_map_url(route_coords, markers, width=600, height=400, title=""):
    """
    Génère une URL d'image statique de carte avec itinéraire et marqueurs
    Utilise MapBox Static Images API (ou alternative OSM)
    
    Args:
        route_coords: Liste de [lon, lat] pour tracer la route
        markers: Liste de dicts avec {coords: [lon,lat], color: 'violet'|'orange'|'blue', label: str}
        width: Largeur de l'image
        height: Hauteur de l'image
        title: Titre optionnel
    
    Returns:
        URL de l'image statique
    """
    # Utiliser geojson.io pour générer une image statique
    # Alternative : API MapBox si token disponible, sinon OSM StaticMap
    
    # Calculer le centre et le zoom basé sur les coordonnées
    if not route_coords:
        return None
    
    lons = [c[0] for c in route_coords]
    lats = [c[1] for c in route_coords]
    center_lon = (min(lons) + max(lons)) / 2
    center_lat = (min(lats) + max(lats)) / 2
    
    # Calculer le zoom approximatif
    lon_range = max(lons) - min(lons)
    lat_range = max(lats) - min(lats)
    max_range = max(lon_range, lat_range)
    
    if max_range > 1:
        zoom = 9
    elif max_range > 0.5:
        zoom = 10
    elif max_range > 0.1:
        zoom = 12
    else:
        zoom = 13
    
    # Construire l'URL pour OSM Static Maps (utiliser HTTP au lieu de HTTPS pour éviter les erreurs de certificat)
    # Alternative : utiliser staticmap.openstreetmap.de avec HTTP
    base_url = "http://staticmap.openstreetmap.de/staticmap.php"
    
    marker_params = []
    color_map = {'violet': 'purple', 'orange': 'orange', 'blue': 'blue', 'green': 'green'}
    
    for m in markers:
        lat, lon = m['coords'][1], m['coords'][0]
        color = color_map.get(m.get('color', 'blue'), 'blue')
        marker_params.append(f"{lat},{lon},{color}")
    
    params = {
        'center': f"{center_lat},{center_lon}",
        'zoom': zoom,
        'size': f"{width}x{height}",
        'maptype': 'mapnik'
    }
    
    if marker_params:
        params['markers'] = '|'.join(marker_params)
    
    import urllib.parse
    query_string = '&'.join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
    
    return f"{base_url}?{query_string}"


@app.route('/api/carpool/calculate-route', methods=['POST'])
@limiter.limit("30 per minute")
def calculate_route():
    """Calcule un itinéraire OSRM avec alternatives"""
    data = request.json
    waypoints = data.get('waypoints', [])
    get_alternatives = data.get('alternatives', False)
    
    if not waypoints or len(waypoints) < 2:
        return jsonify({"error": "Au moins 2 waypoints requis"}), 400
    
    result = calculate_osrm_route(waypoints, get_alternatives)
    
    if 'error' in result:
        return jsonify(result), 500
    
    # Transformer au format attendu par le widget: {routes: [...]}
    routes = [result['route']] + result.get('alternatives', [])
    return jsonify({'routes': routes})


@app.route("/api/carpool", methods=["POST"])
@limiter.limit("10 per minute")
def create_offer():
    """Créer une nouvelle offre de covoiturage"""
    data = request.json
    
    if not data:
        return jsonify({"error": "Données requises"}), 400
    
    # Validation stricte des entrées
    try:
        # User ID (requis)
        user_id = validate_user_id(data.get('user_id'))
        
        # Champs texte
        departure = sanitize_text(data.get('departure', ''), max_length=255)
        destination = sanitize_text(data.get('destination', ''), max_length=255)
        comment = sanitize_text(data.get('comment', ''), max_length=1000)
        
        if not departure or not destination:
            return jsonify({"error": "Départ et destination requis"}), 400
        
        # Dates
        datetime_val = validate_datetime(data.get('datetime'))
        return_datetime_val = None
        if data.get('return_datetime'):
            return_datetime_val = validate_datetime(data.get('return_datetime'))
        
        # Sièges
        seats = validate_integer(data.get('seats', 1), min_val=1, max_val=8, field_name="seats")
        seats_outbound = None
        seats_return = None
        if data.get('seats_outbound'):
            seats_outbound = validate_integer(data.get('seats_outbound'), min_val=1, max_val=8, field_name="seats_outbound")
        if data.get('seats_return'):
            seats_return = validate_integer(data.get('seats_return'), min_val=1, max_val=8, field_name="seats_return")
        
        # Détours
        max_detour_km = validate_integer(data.get('max_detour_km', 5), min_val=1, max_val=100, field_name="max_detour_km")
        max_detour_time = validate_integer(data.get('max_detour_time', 25), min_val=1, max_val=120, field_name="max_detour_time")
        
    except ValueError as e:
        logger.warning(f"Validation error in create_offer: {e}")
        return jsonify({"error": str(e)}), 400
    
    # Whitelist stricte des colonnes autorisées
    ALLOWED_COLUMNS = {
        'user_id', 'departure', 'destination', 'datetime', 'seats', 'seats_available', 'comment',
        'details', 'accept_passengers_on_route', 'seats_outbound', 'seats_return',
        'route_outbound', 'route_return', 'max_detour_km', 'max_detour_time',
        'detour_zone_outbound', 'detour_zone_return', 'return_datetime',
        'event_id', 'event_name', 'event_location', 'event_date', 'event_time',
        'referring_site', 'page_url'
    }
    
    try:
        with sql.db_cursor() as cur:
            # Préparer les données avec valeurs validées
            offer_data = {
                'user_id': user_id,
                'departure': departure,
                'destination': destination,
                'datetime': datetime_val.isoformat(),
                'seats': seats,
                'seats_available': seats,  # Initialiser avec le nombre total de places
                'comment': comment,
                'details': json.dumps(data.get('details', {})),
                'accept_passengers_on_route': bool(data.get('accept_passengers_on_route', True)),
                'seats_outbound': seats_outbound,
                'seats_return': seats_return,
                'route_outbound': json.dumps(data.get('route_outbound')) if data.get('route_outbound') else None,
                'route_return': json.dumps(data.get('route_return')) if data.get('route_return') else None,
                'max_detour_km': max_detour_km,
                'max_detour_time': max_detour_time,
                'return_datetime': return_datetime_val.isoformat() if return_datetime_val else None,
                'event_id': sanitize_text(data.get('event_id', ''), max_length=255),
                'event_name': sanitize_text(data.get('event_name', ''), max_length=255),
                'event_location': sanitize_text(data.get('event_location', ''), max_length=255),
                'event_date': data.get('event_date'),
                'event_time': sanitize_text(data.get('event_time', ''), max_length=50),
                'referring_site': sanitize_text(data.get('referring_site', ''), max_length=255),
                'page_url': sanitize_text(data.get('page_url', ''), max_length=500)
            }
            
            # Calculer les zones de détour si routes fournies
            if offer_data['route_outbound']:
                route_out = json.loads(offer_data['route_outbound'])
                if route_out and 'geometry' in route_out:
                    coords = route_out['geometry'].get('coordinates', [])
                    if coords:
                        buffer_geojson = create_buffer_simple(coords, offer_data['max_detour_km'])
                        offer_data['detour_zone_outbound'] = json.dumps(buffer_geojson) if buffer_geojson else None
            
            if offer_data['route_return']:
                route_ret = json.loads(offer_data['route_return'])
                if route_ret and 'geometry' in route_ret:
                    coords = route_ret['geometry'].get('coordinates', [])
                    if coords:
                        buffer_geojson = create_buffer_simple(coords, offer_data['max_detour_km'])
                        offer_data['detour_zone_return'] = json.dumps(buffer_geojson) if buffer_geojson else None
            
            # Filtrer avec whitelist avant insertion SQL
            safe_data = {k: v for k, v in offer_data.items() if k in ALLOWED_COLUMNS}
            columns = ', '.join(safe_data.keys())
            placeholders = ', '.join(['%s'] * len(safe_data))
            
            cur.execute(
                f"INSERT INTO carpool_offers ({columns}) VALUES ({placeholders})",
                list(safe_data.values())
            )
            
            offer_id = cur.lastrowid
            
        return jsonify({"success": True, "offer_id": offer_id}), 201
    
    except ValueError as e:
        # Erreurs de validation attendues
        logger.warning(f"Validation error in create_offer: {e}")
        return jsonify({"error": str(e)}), 400
    
    except Exception as e:
        # Erreurs inattendues - log détaillé, message générique
        logger.error(f"Unexpected error in create_offer: {e}", exc_info=True)
        return jsonify({"error": "Une erreur est survenue lors de la création de l'offre"}), 500


@app.route("/api/carpool", methods=["GET"])
@limiter.limit("30 per minute")
def get_offers():
    """Récupérer les offres de covoiturage avec filtres optionnels"""
    try:
        filters = {}
        for key in ['event_id', 'user_id', 'departure', 'destination']:
            val = request.args.get(key)
            if val:
                filters[key] = val
        
        with sql.db_cursor() as cur:
            where_clauses = []
            params = []
            
            for key, val in filters.items():
                where_clauses.append(f"{key} = %s")
                params.append(val)
            
            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            
            cur.execute(f"""
                SELECT * FROM carpool_offers 
                {where_sql}
                ORDER BY datetime DESC
                LIMIT 100
            """, params)
            
            offers = []
            for row in cur.fetchall():
                offer = dict(row)  # DictCursor already returns dicts
                # Décoder les champs JSON
                for field_name in ['details', 'route_outbound', 'route_return', 'detour_zone_outbound', 'detour_zone_return']:
                    if offer.get(field_name):
                        try:
                            offer[field_name] = json.loads(offer[field_name])
                        except:
                            pass
                offers.append(offer)
        
        return jsonify({"offers": offers})
    
    except Exception as e:
        logger.error(f"Error fetching offers: {e}", exc_info=True)
        return jsonify({"error": "Une erreur est survenue"}), 500


@app.route('/api/carpool/<int:offer_id>', methods=['GET'])
@limiter.limit("40 per minute")
def get_offer(offer_id):
    """Récupérer une offre spécifique avec ses réservations"""
    try:
        with sql.db_cursor() as cur:
            cur.execute("SELECT * FROM carpool_offers WHERE id = %s", (offer_id,))
            row = cur.fetchone()
            
            if not row:
                return jsonify({"error": "Offre non trouvée"}), 404
            
            offer = dict(row)  # DictCursor already returns dicts
            
            # Décoder JSON
            for field_name in ['details', 'route_outbound', 'route_return', 'detour_zone_outbound', 'detour_zone_return', 'current_route_geometry']:
                if offer.get(field_name):
                    try:
                        offer[field_name] = json.loads(offer[field_name])
                    except:
                        pass
            
            # Récupérer les réservations
            cur.execute("""
                SELECT * FROM carpool_reservations 
                WHERE offer_id = %s
                ORDER BY created_at ASC
            """, (offer_id,))
            
            reservations = []
            for res_row in cur.fetchall():
                res = dict(zip([d[0] for d in cur.description], res_row))
                for field_name in ['meeting_point_coords', 'detour_route', 'pickup_coords', 'route_segment_geometry']:
                    if res.get(field_name):
                        try:
                            res[field_name] = json.loads(res[field_name])
                        except:
                            pass
                reservations.append(res)
            
            offer['reservations'] = reservations
        
        return jsonify(offer)
    
    except Exception as e:
        logger.error(f"Error fetching offer {offer_id}: {e}", exc_info=True)
        return jsonify({"error": "Une erreur est survenue"}), 500


@app.route('/api/carpool/<int:offer_id>', methods=['DELETE'])
@limiter.limit("10 per minute")
def delete_offer(offer_id):
    """Supprimer une offre (seulement par son créateur)"""
    data = request.json
    
    if not data:
        return jsonify({"error": "user_id requis"}), 400
    
    try:
        user_id = validate_user_id(data.get('user_id'))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    
    try:
        with sql.db_cursor() as cur:
            # Vérifier propriété
            cur.execute("SELECT user_id FROM carpool_offers WHERE id = %s", (offer_id,))
            row = cur.fetchone()
            
            if not row:
                return jsonify({"error": "Offre non trouvée"}), 404
            
            if row['user_id'] != user_id:
                return jsonify({"error": "Non autorisé"}), 403
            
            # Suppression (cascade sur reservations)
            cur.execute("DELETE FROM carpool_offers WHERE id = %s", (offer_id,))
        
        return jsonify({"success": True})
    
    except ValueError as e:
        logger.warning(f"Validation error in delete_offer: {e}")
        return jsonify({"error": str(e)}), 400
    
    except Exception as e:
        logger.error(f"Unexpected error in delete_offer: {e}", exc_info=True)
        return jsonify({"error": "Une erreur est survenue"}), 500


@app.route('/api/carpool/reserve', methods=['POST'])
@limiter.limit("20 per minute")
def create_reservation():
    """Créer une réservation pour une offre"""
    data = request.json
    
    if not data:
        return jsonify({"error": "Données requises"}), 400
    
    # Validation inputs
    required = ['offer_id', 'passenger_user_id', 'trip_type']
    if not all(k in data for k in required):
        return jsonify({"error": f"Champs requis: {', '.join(required)}"}), 400
    
    try:
        offer_id = validate_integer(data['offer_id'], min_val=1, field_name="offer_id")
        passenger_user_id = validate_user_id(data['passenger_user_id'])
        
        trip_type = str(data['trip_type']).strip()
        if trip_type not in ['outbound', 'return', 'both']:
            raise ValueError("trip_type doit être 'outbound', 'return' ou 'both'")
        
        passengers = validate_integer(data.get('passengers', 1), min_val=1, max_val=8, field_name="passengers")
        
    except ValueError as e:
        logger.warning(f"Validation error in create_reservation: {e}")
        return jsonify({"error": str(e)}), 400
    
    try:
        with sql.db_cursor() as cur:
            # Vérifier que l'offre existe
            cur.execute("SELECT id FROM carpool_offers WHERE id = %s", (offer_id,))
            if not cur.fetchone():
                return jsonify({"error": "Offre non trouvée"}), 404
            
            # Préparer données réservation
            res_data = {
                'offer_id': offer_id,
                'passenger_user_id': passenger_user_id,
                'passengers': passengers,
                'trip_type': trip_type,
                'meeting_point_coords': json.dumps(data.get('meeting_point_coords')) if data.get('meeting_point_coords') else None,
                'meeting_point_address': sanitize_text(data.get('meeting_point_address', ''), max_length=500),
                'detour_route': json.dumps(data.get('detour_route')) if data.get('detour_route') else None,
                'status': data.get('status', 'pending')
            }
            
            columns = ', '.join(res_data.keys())
            placeholders = ', '.join(['%s'] * len(res_data))
            
            cur.execute(
                f"INSERT INTO carpool_reservations ({columns}) VALUES ({placeholders})",
                list(res_data.values())
            )
            
            reservation_id = cur.lastrowid
        
        return jsonify({"success": True, "reservation_id": reservation_id}), 201
    
    except IntegrityError as e:
        if 'uniq_user_offer_trip' in str(e):
            return jsonify({"error": "Vous avez déjà une réservation pour ce trajet"}), 409
        logger.error(f"Database integrity error in create_reservation: {e}")
        return jsonify({"error": "Erreur d'intégrité des données"}), 500
    
    except ValueError as e:
        logger.warning(f"Validation error in create_reservation: {e}")
        return jsonify({"error": str(e)}), 400
    
    except Exception as e:
        logger.error(f"Unexpected error in create_reservation: {e}", exc_info=True)
        return jsonify({"error": "Une erreur est survenue"}), 500


@app.route('/api/carpool/reservations', methods=['GET'])
def get_my_reservations():
    """Récupérer les réservations d'un utilisateur"""
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({"error": "user_id requis"}), 400
    
    try:
        user_id = validate_user_id(user_id)
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT r.*, o.departure, o.destination, o.datetime, o.user_id as driver_user_id
                FROM carpool_reservations r
                JOIN carpool_offers o ON r.offer_id = o.id
                WHERE r.passenger_user_id = %s
                ORDER BY o.datetime DESC
            """, (user_id,))
            
            reservations = []
            for row in cur.fetchall():
                res = dict(row)  # DictCursor already returns dicts
                for field_name in ['meeting_point_coords', 'detour_route', 'pickup_coords', 'route_segment_geometry']:
                    if res.get(field_name):
                        try:
                            res[field_name] = json.loads(res[field_name])
                        except:
                            pass
                reservations.append(res)
        
        return jsonify({"reservations": reservations})
    
    except ValueError as e:
        logger.warning(f"Validation error in get_my_reservations: {e}")
        return jsonify({"error": str(e)}), 400
    
    except Exception as e:
        logger.error(f"Error fetching reservations: {e}", exc_info=True)
        return jsonify({"error": "Une erreur est survenue"}), 500


@app.route('/api/carpool/search', methods=['GET'])
@limiter.limit("60 per minute")
def search_offers():
    """
    Recherche spatiale d'offres compatibles avec un trajet passager ou un point + rayon
    
    Deux modes:
    1. Recherche par trajet: start_lon, start_lat, end_lon, end_lat
    2. Recherche par rayon: lon, lat, radius
    """
    try:
        # Mode 1: Recherche par rayon (point + radius)
        if request.args.get('lon') and request.args.get('lat') and request.args.get('radius'):
            lon = float(request.args.get('lon'))
            lat = float(request.args.get('lat'))
            radius = float(request.args.get('radius'))
            
            # Validation
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                return jsonify({"error": "Coordonnées invalides"}), 400
            
            if radius <= 0 or radius > 200000:  # Max 200km
                return jsonify({"error": "Radius doit être entre 0 et 200000 mètres"}), 400
            
            # Chercher dans les deux tables (v1 et v2)
            offers = []
            
            # Fonction helper pour calculer la distance
            def haversine_distance(lon1, lat1, lon2, lat2):
                """Distance en mètres entre deux points"""
                import math
                R = 6371000  # Rayon de la Terre en mètres
                phi1 = math.radians(lat1)
                phi2 = math.radians(lat2)
                delta_phi = math.radians(lat2 - lat1)
                delta_lambda = math.radians(lon2 - lon1)
                
                a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                
                return R * c
            
            # Table v1
            with sql.db_cursor() as cur:
                cur.execute("""
                    SELECT * FROM carpool_offers
                    WHERE datetime >= NOW() - INTERVAL 2 DAY
                    ORDER BY datetime DESC
                    LIMIT 100
                """)
                
                for row in cur.fetchall():
                    offer = dict(row)  # DictCursor already returns dicts
                    
                    # Décoder les champs JSON
                    for field_name in ['details', 'route_outbound', 'route_return', 'detour_zone_outbound', 'detour_zone_return']:
                        if offer.get(field_name):
                            try:
                                offer[field_name] = json.loads(offer[field_name])
                            except Exception as e:
                                logging.error(f"Failed to parse {field_name}: {e}, value type: {type(offer.get(field_name))}")
                                # If it failed, ensure it's at least an empty dict
                                if field_name == "details" and isinstance(offer.get(field_name), str):
                                    offer[field_name] = {}
                    
                    # Filtrer par rayon : vérifier si le départ ou l'arrivée est dans le rayon
                    details = offer.get('details', {})
                    from_coords = details.get('fromCoords', [])
                    to_coords = details.get('toCoords', [])
                    
                    logger.debug(f"🔍 Offre {offer.get('id')}: fromCoords={from_coords}, toCoords={to_coords}, details keys={list(details.keys()) if isinstance(details, dict) else 'not a dict'}")
                    
                    in_radius = False
                    if len(from_coords) == 2:
                        dist = haversine_distance(lon, lat, from_coords[0], from_coords[1])
                        if dist <= radius:
                            in_radius = True
                    
                    if not in_radius and len(to_coords) == 2:
                        dist = haversine_distance(lon, lat, to_coords[0], to_coords[1])
                        if dist <= radius:
                            in_radius = True
                    
                    # Vérifier aussi les stops
                    if not in_radius:
                        stops = details.get('stops', [])
                        for stop in stops:
                            stop_coords = stop.get('coords', [])
                            if len(stop_coords) == 2:
                                dist = haversine_distance(lon, lat, stop_coords[0], stop_coords[1])
                                if dist <= radius:
                                    in_radius = True
                                    break
                    
                    if in_radius:
                        offers.append(offer)
                        logger.info(f"✅ Offre {offer.get('id')} ajoutée (in_radius=True)")
                    else:
                        logger.warning(f"❌ Offre {offer.get('id')} IGNORÉE (in_radius=False) - departure={offer.get('departure')}, destination={offer.get('destination')}")
            
            # Table v2 si disponible
            
            logger.info(f"🔍 Recherche par rayon: {len(offers)} offres trouvées autour de ({lon}, {lat}) rayon {radius}m")
            return jsonify(offers)
        
        # Mode 2: Recherche par trajet (ancienne logique)
        start_lon = request.args.get('start_lon', 0)
        start_lat = request.args.get('start_lat', 0)
        end_lon = request.args.get('end_lon', 0)
        end_lat = request.args.get('end_lat', 0)
        
        # Validation coordonnées
        start_lon, start_lat = validate_coordinates(start_lon, start_lat)
        end_lon, end_lat = validate_coordinates(end_lon, end_lat)
        
        date_str = request.args.get('date', '')
        trip_type = request.args.get('trip_type', 'outbound')
        
        if not all([start_lon, start_lat, end_lon, end_lat]):
            return jsonify({"error": "Coordonnées start/end requises"}), 400
        
        # Chercher offres du jour (±12h)
        with sql.db_cursor() as cur:
            date_filter = ""
            params = []
            
            if date_str:
                try:
                    target_date = datetime.fromisoformat(date_str)
                    date_min = target_date - timedelta(hours=12)
                    date_max = target_date + timedelta(hours=12)
                    date_filter = "AND datetime BETWEEN %s AND %s"
                    params = [date_min, date_max]
                except:
                    pass
            
            cur.execute(f"""
                SELECT * FROM carpool_offers
                WHERE accept_passengers_on_route = TRUE
                {date_filter}
                ORDER BY datetime ASC
                LIMIT 50
            """, params)
            
            matching_offers = []
            
            for row in cur.fetchall():
                offer = dict(row)  # DictCursor already returns dicts
                
                # Décoder zones de détour
                zone_field = 'detour_zone_outbound' if trip_type == 'outbound' else 'detour_zone_return'
                if offer.get(zone_field):
                    try:
                        zone = json.loads(offer[zone_field])
                        
                        # Vérifier si les points passager sont dans la zone
                        # (simplification: vérifier au moins un point)
                        # TODO: implémenter point_in_polygon proprement
                        
                        matching_offers.append(offer)
                    except:
                        pass
        
        return jsonify({"offers": matching_offers[:20]})  # Limiter à 20 résultats
    
    except ValueError as e:
        logger.warning(f"Validation error in search_offers: {e}")
        return jsonify({"error": str(e)}), 400
    
    except Exception as e:
        logger.error(f"Error searching offers: {e}", exc_info=True)
        return jsonify({"error": "Erreur serveur"}), 500


# ============================================
# ENDPOINTS API V2 - Sans comptes utilisateurs
# ============================================


@app.route('/api/carpool/count', methods=['GET'])
@limiter.limit("60 per minute")
def count_offers():
    """Retourne le nombre total d'offres disponibles (aller + retour)"""
    try:
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as total
                FROM carpool_offers
                WHERE datetime >= NOW() - INTERVAL 2 DAY
                  AND (seats_available IS NULL OR seats_available > 0)
            """)
            row = cur.fetchone()
            total_offers = row['total'] if row else 0
            
        return jsonify({'total_trips': total_offers})
    except Exception as e:
        logger.error(f"Error in count_offers: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/v2/offers', methods=['POST'])
@limiter.limit("10 per hour")
def create_offer_v2():
    """Créer une offre de covoiturage (workflow email/WhatsApp)"""
    if not V2_ENABLED:
        return jsonify({'error': 'API v2 non disponible'}), 503
    
    try:
        data = request.json
        
        # Validation
        driver_email = validate_email(data.get('driver_email'))
        driver_name = sanitize_text(data.get('driver_name', ''), max_length=100)
        driver_phone = sanitize_text(data.get('driver_phone', ''), max_length=20)
        
        departure = sanitize_text(data.get('departure'), max_length=255)
        destination = sanitize_text(data.get('destination'), max_length=255)
        
        # Parse datetime (sans validation stricte du passé car peut y avoir décalage horaire)
        datetime_str = data.get('datetime')
        if not datetime_str:
            return jsonify({'error': 'Date/heure requise'}), 400
        
        # Validation basique du format
        try:
            dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
            # Vérifier que la date n'est pas trop vieille (> 48h dans le passé)
            if dt < datetime.now() - timedelta(hours=48):
                return jsonify({'error': 'La date du trajet est trop ancienne (maximum 48h dans le passé)'}), 400
            # Garder datetime_str comme string pour l'insertion SQL
        except ValueError:
            return jsonify({'error': 'Format de date invalide (utilisez YYYY-MM-DD HH:MM:SS)'}), 400
        
        seats = validate_integer(data.get('seats', 1), min_val=1, max_val=8)
        
        if not all([driver_email, driver_phone, departure, destination, datetime_str]):
            return jsonify({'error': 'Champs obligatoires manquants'}), 400
        
        # Coordonnées (optionnel - extraire depuis details si présent)
        details = data.get('details', {})
        departure_coords = None
        destination_coords = None
        
        if details.get('fromCoords'):
            coords = details['fromCoords']
            departure_coords = json.dumps({'lat': coords[1], 'lon': coords[0]})
        
        if details.get('toCoords'):
            coords = details['toCoords']
            destination_coords = json.dumps({'lat': coords[1], 'lon': coords[0]})
        
        # Événement (optionnel)
        event_id = sanitize_text(data.get('event_id', ''), max_length=255)
        event_name = sanitize_text(data.get('event_name', ''), max_length=255)
        event_location = sanitize_text(data.get('event_location', ''), max_length=255)
        event_date = data.get('event_date')
        
        # Ajouter les routes au details pour les rendre disponibles côté frontend
        route_outbound = data.get('route_outbound')
        route_return = data.get('route_return')
        if route_outbound:
            details['route_outbound'] = route_outbound
        if route_return:
            details['route_return'] = route_return
        
        # Sérialiser details en JSON
        details_json = json.dumps(details) if details else None
        
        # Date d'expiration (7 jours après le trajet)
        expires_at = (datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S') + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        
        # Insertion BDD
        with db_cursor_v2() as cur:
            cur.execute("""
                INSERT INTO carpool_offers 
                (driver_email, driver_name, driver_phone, departure, destination, 
                 departure_coords, destination_coords, datetime, seats, seats_available, 
                 event_id, event_name, event_location, event_date, details, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                driver_email, driver_name, driver_phone, departure, destination,
                departure_coords, destination_coords, datetime_str, seats, seats,
                event_id, event_name, event_location, event_date, details_json, expires_at
            ))
            offer_id = cur.lastrowid
        
        logger.info(f"✅ Offre v2 créée: {offer_id} par {driver_email}")
        
        # Envoyer email de confirmation au conducteur
        try:
            from email_templates import email_offer_published
            from emails import send_email
            
            # Calculer l'heure de DÉPART (arrivée - durée du trajet)
            arrival_dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
            duration_seconds = details.get('durationSeconds', {}).get('outbound', 0)
            departure_dt = arrival_dt - timedelta(seconds=duration_seconds)
            departure_time_str = departure_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Extraire infos retour depuis details
            return_trip = details.get('returnTrip', {})
            return_enabled = return_trip.get('enabled', False)
            return_datetime_str = None
            return_arrival_time_str = None
            
            if return_enabled:
                return_date = return_trip.get('date', '')
                return_time = return_trip.get('time', '')
                if return_date and return_time:
                    # return_datetime est l'heure de DÉPART du retour
                    return_datetime_str = f"{return_date} {return_time}:00"
                    
                    # Calculer l'heure d'ARRIVÉE du retour
                    return_depart_dt = datetime.strptime(return_datetime_str, '%Y-%m-%d %H:%M:%S')
                    return_duration = details.get('durationSeconds', {}).get('return', 0)
                    return_arrival_dt = return_depart_dt + timedelta(seconds=return_duration)
                    return_arrival_time_str = return_arrival_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            seats_outbound = seats
            seats_return = return_trip.get('seats', seats) if return_enabled else 0
            
            # Prix (estimation si non fourni)
            price_val = None
            prices_out = details.get('prices', {}).get('out', [])
            if prices_out and len(prices_out) > 0:
                price_val = prices_out[0]
            else:
                # Calculer prix estimé
                distance_km = details.get('distanceMeters', {}).get('outbound', 0) / 1000
                if distance_km > 0:
                    price_val = round(distance_km * 0.10, 2)  # 10 centimes/km
            
            # Générer la carte avec les itinéraires
            map_image_path = None
            try:
                from map_generator import generate_map_image
                
                # Parser les coordonnées si elles sont en string JSON
                dep_coords = departure_coords
                dest_coords = destination_coords
                if isinstance(dep_coords, str):
                    dep_coords = json.loads(dep_coords)
                if isinstance(dest_coords, str):
                    dest_coords = json.loads(dest_coords)
                
                # Extraire les routes depuis le payload principal (pas details!)
                route_outbound = data.get('route_outbound') if data else None
                route_return = data.get('route_return') if data else None
                
                # Debug: vérifier ce qui est reçu
                logger.info(f"🔍 route_outbound présent: {route_outbound is not None}")
                if route_outbound:
                    logger.info(f"🔍 route_outbound keys: {route_outbound.keys() if isinstance(route_outbound, dict) else 'not a dict'}")
                    if isinstance(route_outbound, dict) and 'geometry' in route_outbound:
                        geom = route_outbound['geometry']
                        if isinstance(geom, dict) and 'coordinates' in geom:
                            logger.info(f"🔍 route_outbound coords count: {len(geom['coordinates'])}")
                
                # Récupérer les couleurs depuis le payload (depuis le widget)
                # Note: les couleurs peuvent avoir un canal alpha (8 caractères), on ne garde que RGB (6 caractères)
                color_outbound = data.get('color_outbound', '#7c3aed')
                color_return = data.get('color_return', '#f97316')
                
                # Normaliser les couleurs (retirer le canal alpha si présent)
                if color_outbound and len(color_outbound) == 9:  # #RRGGBBAA
                    color_outbound = color_outbound[:7]  # #RRGGBB
                if color_return and len(color_return) == 9:
                    color_return = color_return[:7]
                
                # Générer l'image
                map_image_path = generate_map_image(
                    dep_coords,
                    dest_coords,
                    route_outbound,
                    route_return,
                    width=700,
                    height=400,
                    color_outbound=color_outbound,
                    color_return=color_return
                )
                logger.info(f"🗺️ Carte générée: {map_image_path}")
            except Exception as e:
                logger.warning(f"⚠️ Échec génération carte: {e}")
                import traceback
                logger.warning(traceback.format_exc())
            
            offer_data = {
                'departure': departure,
                'destination': destination,
                'datetime': datetime_str,  # Heure d'ARRIVÉE
                'departure_time': departure_time_str,  # Heure de DÉPART
                'return_datetime': return_datetime_str,  # Heure de départ retour
                'return_arrival_time': return_arrival_time_str,  # Heure d'arrivée retour
                'seats': seats,
                'seats_outbound': seats_outbound,
                'seats_return': seats_return,
                'driver_phone': driver_phone,
                'price': price_val,
                'has_return': return_enabled,
                'departure_coords': departure_coords,
                'destination_coords': destination_coords,
                'map_image_path': map_image_path  # Chemin de l'image générée
            }
            
            subject, html_body, text_body = email_offer_published(
                driver_email=driver_email,
                driver_name=driver_name,
                offer=offer_data,
                base_url=BASE_URL
            )
            
            # Préparer les pièces jointes (image de carte inline)
            attachments = []
            if map_image_path:
                full_path = os.path.join('/home/ubuntu/projects/carette/static', map_image_path)
                if os.path.exists(full_path):
                    attachments.append({
                        'path': full_path,
                        'cid': 'map_image'  # Correspond au cid: dans le HTML
                    })
            
            send_email(driver_email, subject, html_body, text_body, attachments=attachments)
            logger.info(f"✅ Email de confirmation envoyé à {driver_email}")
        except Exception as e:
            logger.warning(f"⚠️ Échec envoi email confirmation: {e}")
            import traceback
            logger.warning(traceback.format_exc())
        
        return jsonify({
            'success': True,
            'offer_id': offer_id,
            'message': 'Offre créée avec succès. Vous recevrez un email pour chaque réservation.'
        }), 201
        
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating offer v2: {e}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/offers', methods=['GET'])
@limiter.limit("60 per minute")
def get_offers_v2():
    """Récupérer les offres de covoiturage disponibles"""
    if not V2_ENABLED:
        return jsonify({'error': 'API v2 non disponible'}), 503
    
    try:
        # Filtres optionnels
        event_id = request.args.get('event_id')
        min_seats = request.args.get('min_seats', type=int)
        
        # Query de base - offres non expirées
        query = """
            SELECT id, driver_email, driver_name, driver_phone,
                   departure, destination, departure_coords, destination_coords,
                   datetime, seats_available, 
                   event_id, event_name, event_location, event_date,
                   details, created_at
            FROM carpool_offers
            WHERE expires_at > NOW()
            AND seats_available > 0
        """
        params = []
        
        if event_id:
            query += " AND event_id = %s"
            params.append(event_id)
        
        if min_seats:
            query += " AND seats_available >= %s"
            params.append(min_seats)
        
        query += " ORDER BY datetime ASC LIMIT 100"
        
        with db_cursor_v2() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        
        offers = []
        for row in rows:
            # Masquer les données sensibles (téléphone/email complet)
            masked_email = row['driver_email'].split('@')[0][:3] + '***@' + row['driver_email'].split('@')[1]
            masked_phone = row['driver_phone'][:4] + '****' if row['driver_phone'] else None
            
            offers.append({
                'id': row['id'],
                'driver_name': row['driver_name'],
                'driver_email_masked': masked_email,
                'driver_phone_masked': masked_phone,
                'departure': row['departure'],
                'destination': row['destination'],
                'departure_coords': json.loads(row['departure_coords']) if row['departure_coords'] else None,
                'destination_coords': json.loads(row['destination_coords']) if row['destination_coords'] else None,
                'datetime': row['datetime'].strftime('%Y-%m-%d %H:%M:%S') if row['datetime'] else None,
                'seats_available': row['seats_available'],
                'event_id': row['event_id'],
                'event_name': row['event_name'],
                'event_location': row['event_location'],
                'event_date': row['event_date'].strftime('%Y-%m-%d') if row['event_date'] else None,
                'details': json.loads(row['details']) if row['details'] else {},
                'created_at': row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if row['created_at'] else None
            })
        
        return jsonify({'offers': offers, 'count': len(offers)}), 200
        
    except Exception as e:
        logger.error(f"Error fetching offers v2: {e}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/offers/search', methods=['GET'])
@limiter.limit("60 per minute")
def search_offers_v2():
    """
    Recherche spatiale d'offres v2 (ponctuel/événementiel).
    Paramètres: lon, lat, radius (mètres), event_id (optionnel)
    """
    try:
        lon = request.args.get('lon', type=float)
        lat = request.args.get('lat', type=float)
        radius = request.args.get('radius', type=float)
        event_id = request.args.get('event_id')

        if lon is None or lat is None or radius is None:
            return jsonify({'error': 'lon, lat, radius requis'}), 400

        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            return jsonify({'error': 'Coordonnées invalides'}), 400

        if radius <= 0 or radius > 200000:
            return jsonify({'error': 'Radius doit être entre 0 et 200000 mètres'}), 400

        import math

        def haversine_distance(lon1, lat1, lon2, lat2):
            R = 6371000
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            delta_phi = math.radians(lat2 - lat1)
            delta_lambda = math.radians(lon2 - lon1)
            a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        query = """
            SELECT * FROM carpool_offers
            WHERE datetime >= NOW() - INTERVAL 2 DAY
        """
        params = []

        if event_id:
            query += " AND event_id = %s"
            params.append(event_id)

        query += " ORDER BY datetime DESC LIMIT 100"

        offers = []
        with sql.db_cursor() as cur:
            cur.execute(query, params)
            for row in cur.fetchall():
                offer = dict(row)  # DictCursor already returns dicts

                # Décoder les champs JSON
                for field_name in ['details', 'route_outbound', 'route_return', 'detour_zone_outbound', 'detour_zone_return']:
                    if offer.get(field_name):
                        try:
                            offer[field_name] = json.loads(offer[field_name])
                        except Exception:
                            if field_name == 'details':
                                offer[field_name] = {}

                # Filtrer par rayon
                details = offer.get('details') or {}
                if isinstance(details, str):
                    try:
                        details = json.loads(details)
                    except Exception:
                        details = {}
                from_coords = details.get('fromCoords', [])
                to_coords = details.get('toCoords', [])

                in_radius = False
                if len(from_coords) == 2:
                    if haversine_distance(lon, lat, from_coords[0], from_coords[1]) <= radius:
                        in_radius = True

                if not in_radius and len(to_coords) == 2:
                    if haversine_distance(lon, lat, to_coords[0], to_coords[1]) <= radius:
                        in_radius = True

                # Vérifier aussi les stops
                if not in_radius:
                    for stop in details.get('stops', []):
                        stop_coords = stop.get('coords', [])
                        if len(stop_coords) == 2:
                            if haversine_distance(lon, lat, stop_coords[0], stop_coords[1]) <= radius:
                                in_radius = True
                                break

                # Vérifier les zones de détour (Shapely) si disponibles
                if not in_radius:
                    try:
                        from shapely.geometry import shape, Point
                        search_point = Point(lon, lat)
                        for zone_key in ['detour_zone_outbound', 'detour_zone_return']:
                            zone = offer.get(zone_key)
                            if zone and isinstance(zone, dict) and zone.get('type'):
                                poly = shape(zone)
                                if poly.contains(search_point):
                                    in_radius = True
                                    break
                    except Exception:
                        pass

                if in_radius:
                    # Masquer les informations sensibles
                    offer.pop('driver_phone', None)
                    # Sérialiser les dates
                    for key in ['datetime', 'created_at', 'updated_at', 'expires_at']:
                        if offer.get(key) and hasattr(offer[key], 'strftime'):
                            offer[key] = offer[key].strftime('%Y-%m-%dT%H:%M:%S')
                    for key in ['event_date']:
                        if offer.get(key) and hasattr(offer[key], 'strftime'):
                            offer[key] = offer[key].strftime('%Y-%m-%d')
                    offers.append(offer)

        logger.info(f"🔍 V2 search: {len(offers)} offres trouvées autour de ({lon}, {lat}) rayon {radius}m")
        return jsonify(offers)

    except Exception as e:
        logger.error(f"Error in search_offers_v2: {e}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/events/<event_id>/qrcode', methods=['GET'])
def get_event_qrcode(event_id):
    """Générer un QR code pour un événement (lien direct vers le widget)"""
    try:
        import io
        try:
            import qrcode
            has_qrcode = True
        except ImportError:
            has_qrcode = False

        base_url = os.getenv('CARETTE_BASE_URL', 'http://localhost:9000')
        event_url = f"{base_url}/event/{event_id}"

        if not has_qrcode:
            # Fallback: retourner l'URL en JSON si qrcode n'est pas installé
            return jsonify({
                'event_url': event_url,
                'message': 'Module qrcode non installé — installer avec: pip install qrcode[pil]'
            }), 200

        # Générer le QR code
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=8, border=2)
        qr.add_data(event_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#7c3aed", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        from flask import send_file
        return send_file(buf, mimetype='image/png', download_name=f'carette-{event_id}.png')

    except Exception as e:
        logger.error(f"Error generating QR code: {e}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/events/<event_id>/info', methods=['GET'])
def get_event_info(event_id):
    """Récupérer les infos d'un événement et ses offres de covoiturage"""
    try:
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT id, event_id, event_name, event_location, event_date, event_time,
                       COUNT(*) as offer_count,
                       SUM(seats_available) as total_seats
                FROM carpool_offers
                WHERE event_id = %s AND datetime >= NOW() - INTERVAL 2 DAY
                GROUP BY event_id
            """, (event_id,))
            row = cur.fetchone()

        if not row:
            return jsonify({
                'event_id': event_id,
                'offer_count': 0,
                'total_seats': 0,
                'message': 'Aucune offre pour cet événement'
            }), 200

        event_info = dict(zip([d[0] for d in cur.description], row)) if not isinstance(row, dict) else row
        # Sérialiser les dates
        for key in ['event_date']:
            if event_info.get(key) and hasattr(event_info[key], 'strftime'):
                event_info[key] = event_info[key].strftime('%Y-%m-%d')

        base_url = os.getenv('CARETTE_BASE_URL', 'http://localhost:9000')
        event_info['share_url'] = f"{base_url}/event/{event_id}"
        event_info['qrcode_url'] = f"{base_url}/api/v2/events/{event_id}/qrcode"

        return jsonify(event_info), 200

    except Exception as e:
        logger.error(f"Error fetching event info: {e}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/event/<event_id>')
def event_deep_link(event_id):
    """Page de deep link pour un événement — redirige vers le widget avec l'event pré-rempli"""
    try:
        # Récupérer les infos de l'événement
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT event_name, event_location, event_date, event_time
                FROM carpool_offers
                WHERE event_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (event_id,))
            row = cur.fetchone()

        event_name = row[0] if row else event_id
        event_location = row[1] if row else ''
        event_date = row[2].strftime('%Y-%m-%d') if row and row[2] and hasattr(row[2], 'strftime') else ''
        event_time = row[3] if row else ''

        # Compter les offres disponibles
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as cnt, COALESCE(SUM(seats_available), 0) as seats
                FROM carpool_offers
                WHERE event_id = %s AND datetime >= NOW() - INTERVAL 2 DAY
            """, (event_id,))
            stats = cur.fetchone()
            offer_count = stats[0] if stats else 0
            total_seats = stats[1] if stats else 0

        base_url = os.getenv('CARETTE_BASE_URL', 'http://localhost:9000')

        return f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Covoiturage - {event_name}</title>
            <meta property="og:title" content="Covoiturage pour {event_name}" />
            <meta property="og:description" content="{offer_count} covoiturages disponibles • {total_seats} places • {event_location}" />
            <meta property="og:type" content="website" />
            <meta property="og:url" content="{base_url}/event/{event_id}" />
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh; padding: 20px;
                }}
                .container {{ max-width: 800px; margin: 0 auto; }}
                .header {{
                    text-align: center; color: white; margin-bottom: 20px;
                }}
                .header h1 {{ font-size: 2em; margin-bottom: 8px; }}
                .header p {{ font-size: 1.1em; opacity: 0.9; }}
                .stats {{
                    display: flex; gap: 20px; justify-content: center; margin: 16px 0;
                }}
                .stat {{
                    background: rgba(255,255,255,0.15); backdrop-filter: blur(10px);
                    padding: 12px 24px; border-radius: 12px; text-align: center; color: white;
                }}
                .stat strong {{ display: block; font-size: 1.8em; }}
                .widget-container {{
                    background: white; border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden;
                }}
                .share-bar {{
                    text-align: center; margin-top: 20px; color: white;
                }}
                .share-bar a {{
                    display: inline-block; background: rgba(255,255,255,0.2);
                    color: white; padding: 10px 20px; border-radius: 8px;
                    text-decoration: none; margin: 0 8px; font-weight: 600;
                    transition: background 0.2s;
                }}
                .share-bar a:hover {{ background: rgba(255,255,255,0.35); }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚗 {event_name}</h1>
                    <p>📍 {event_location} {('• 📅 ' + event_date) if event_date else ''} {('• 🕐 ' + event_time) if event_time else ''}</p>
                    <div class="stats">
                        <div class="stat"><strong>{offer_count}</strong>covoiturage{'s' if offer_count > 1 else ''}</div>
                        <div class="stat"><strong>{total_seats}</strong>place{'s' if total_seats > 1 else ''} disponible{'s' if total_seats > 1 else ''}</div>
                    </div>
                </div>

                <div class="widget-container">
                    <carpool-offer-widget
                        theme="light"
                        event-id="{event_id}"
                        event-name="{event_name}"
                        event-location="{event_location}"
                        event-date="{event_date}"
                        event-time="{event_time}"
                        page-url="{base_url}/event/{event_id}"
                    ></carpool-offer-widget>
                </div>

                <div class="share-bar">
                    <a href="https://wa.me/?text=Covoiturage%20pour%20{urllib.parse.quote(event_name)}%20🚗%20{urllib.parse.quote(base_url + '/event/' + event_id)}" target="_blank">💬 Partager sur WhatsApp</a>
                    <a href="{base_url}/api/v2/events/{event_id}/qrcode" target="_blank" download>📱 QR Code</a>
                </div>
            </div>
            <script type="module" src="/frontend/carpool-widget.js"></script>
            <script src="/frontend/payment-simulator.js"></script>
        </body>
        </html>
        """

    except Exception as e:
        logger.error(f"Error in event deep link: {e}", exc_info=True)
        return "Erreur serveur", 500


@app.route('/api/v2/reservations', methods=['POST'])
@limiter.limit("10 per hour")
def create_reservation_v2():
    """Créer une demande de réservation (envoi email au conducteur pour validation)"""
    if not V2_ENABLED:
        return jsonify({'error': 'API v2 non disponible'}), 503
    
    try:
        data = request.json
        
        # Validation
        offer_id = validate_integer(data.get('offer_id'), min_val=1)
        passenger_email = validate_email(data.get('passenger_email'))
        passenger_name = sanitize_text(data.get('passenger_name', ''), max_length=100)
        passenger_phone = sanitize_text(data.get('passenger_phone', ''), max_length=20)
        passengers_count = validate_integer(data.get('passengers', 1), min_val=1, max_val=8)
        trip_type = data.get('trip_type', 'outbound')
        
        if trip_type not in ['outbound', 'return', 'both']:
            return jsonify({'error': 'trip_type invalide'}), 400
        
        if not all([offer_id, passenger_email, passenger_phone]):
            return jsonify({'error': 'Champs obligatoires manquants'}), 400
        
        # Récupérer les infos de détour si présentes
        detour_time = data.get('detour_time', 0)  # minutes
        meeting_point = data.get('meeting_point')  # {coords: {lat, lon}, address: "..."}
        meeting_address = data.get('meeting_address', '')
        detour_route = data.get('detour_route')  # geometry GeoJSON
        
        # Vérifier disponibilité de l'offre
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT id, driver_email, driver_name, driver_phone, 
                       departure, destination, datetime, seats_available,
                       event_name, event_location, event_date, details
                FROM carpool_offers
                WHERE id = %s
            """, (offer_id,))
            offer_row = cur.fetchone()
        
        if not offer_row:
            return jsonify({'error': 'Offre introuvable'}), 404
        
        offer = dict(zip([d[0] for d in cur.description], offer_row))
        
        # Décoder details JSON
        if offer.get('details') and isinstance(offer['details'], str):
            try:
                offer['details'] = json.loads(offer['details'])
            except:
                offer['details'] = {}
        
        # Vérifier disponibilité sièges
        seats_available = offer.get('seats_available', 0)
        if seats_available < passengers_count:
            return jsonify({'error': f"Seulement {seats_available} place(s) disponible(s)"}), 400
        
        # Générer token de confirmation unique
        confirmation_token = generate_confirmation_token()
        
        # Insérer réservation avec status='pending'
        with sql.db_cursor() as cur:
            # Déterminer quelle colonne de détour utiliser selon trip_type
            if trip_type == 'outbound':
                detour_cols = 'detour_time_outbound'
                detour_vals = (detour_time,)
            elif trip_type == 'return':
                detour_cols = 'detour_time_return'
                detour_vals = (detour_time,)
            else:  # both
                detour_cols = 'detour_time_outbound, detour_time_return'
                detour_vals = (detour_time, detour_time)  # TODO: calculer séparément
            
            cur.execute(f"""
                INSERT INTO carpool_reservations
                (offer_id, passenger_email, passenger_name, passenger_phone, 
                 passengers, trip_type, status, confirmation_token,
                 meeting_point_coords, meeting_point_address, detour_route, {detour_cols})
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s, {', '.join(['%s'] * len(detour_vals))})
            """, (
                offer_id, passenger_email, passenger_name, passenger_phone,
                passengers_count, trip_type, confirmation_token,
                json.dumps(meeting_point) if meeting_point else None,
                meeting_address or None,
                json.dumps(detour_route) if detour_route else None,
                *detour_vals
            ))
            reservation_id = cur.lastrowid
            
            # Décrémenter les places disponibles (réservation optimiste)
            cur.execute("""
                UPDATE carpool_offers
                SET seats_available = seats_available - %s
                WHERE id = %s
            """, (passengers_count, offer_id))
        
        logger.info(f"✅ Demande de réservation créée: {reservation_id} pour offre {offer_id} (status: pending, -{passengers_count} places)")
        
        # ========== ENVOI DES EMAILS ==========
        try:
            # Générer magic links pour le conducteur
            accept_url = generate_accept_link(reservation_id, offer['driver_email'], BASE_URL)
            refuse_url = generate_refuse_link(reservation_id, offer['driver_email'], BASE_URL)
            
            # Préparer les données de l'offre
            offer_data = {
                'departure': offer['departure'],
                'destination': offer['destination'],
                'datetime': offer['datetime'].strftime('%A %d %B %Y à %H:%M') if offer.get('datetime') else '',
                'seats': offer.get('seats', 0),
                'seats_available': offer.get('seats_available', 0)
            }
            
            # TODO: Générer carte statique du trajet
            # map_image_path = generate_map_for_reservation(offer, meeting_point)
            
            # 1. Email au CONDUCTEUR avec boutons [Accepter] [Refuser]
            subject_drv, html_drv, text_drv = email_new_reservation_request(
                driver_email=offer['driver_email'],
                driver_name=offer['driver_name'],
                passenger_name=passenger_name,
                passenger_email=passenger_email,
                passenger_phone=passenger_phone,
                meeting_address=meeting_address or offer['departure'],
                offer=offer_data,
                trip_type=trip_type,
                detour_minutes=detour_time,
                accept_url=accept_url,
                refuse_url=refuse_url,
                base_url=request.host_url.rstrip('/')
            )
            send_email(offer['driver_email'], subject_drv, html_drv, text_drv)
            logger.info(f"📧 Email demande envoyé au conducteur: {offer['driver_email']}")
            
            # 2. Email au PASSAGER avec confirmation d'envoi
            subject_pass, html_pass, text_pass = email_request_sent_to_passenger(
                passenger_email=passenger_email,
                passenger_name=passenger_name,
                driver_name=offer['driver_name'],
                offer=offer_data,
                trip_type=trip_type,
                meeting_address=meeting_address or ''
            )
            send_email(passenger_email, subject_pass, html_pass, text_pass)
            logger.info(f"📧 Email confirmation envoyé au passager: {passenger_email}")
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi emails: {e}", exc_info=True)
            # Ne pas bloquer la création de réservation même si email échoue
        
        return jsonify({
            'success': True,
            'reservation_id': reservation_id,
            'status': 'pending',
            'message': 'Demande envoyée au conducteur ! Vous recevrez un email dès qu\'il aura accepté.'
        }), 201
        
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating reservation v2: {e}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


# NOTE: Ces endpoints sont maintenant gérés par api_magic_links.py
# @app.route('/api/v2/reservations/accept/<token>', methods=['GET'])
def _old_accept_reservation(token):
    """Accepter une réservation (lien depuis email conducteur)"""
    if not V2_ENABLED:
        return jsonify({'error': 'API v2 non disponible'}), 503
    
    try:
        with sql.db_cursor() as cur:
            # Trouver la réservation par token
            cur.execute("""
                SELECT r.id, r.offer_id, r.passenger_email, r.passenger_name, r.passenger_phone,
                       r.meeting_point_address, r.detour_time, r.passengers,
                       o.driver_email, o.driver_name, o.driver_phone,
                       o.departure, o.destination, o.datetime
                FROM carpool_reservations r
                JOIN carpool_offers o ON r.offer_id = o.id
                WHERE r.confirmation_token = %s AND r.status = 'pending'
            """, (token,))
            
            reservation = cur.fetchone()
            
            if not reservation:
                return "<html><body><h2>❌ Lien invalide ou réservation déjà traitée</h2></body></html>", 404
            
            res_dict = dict(zip([d[0] for d in cur.description], reservation))
            
            # Mettre à jour le status
            cur.execute("""
                UPDATE carpool_reservations
                SET status = 'confirmed', confirmed_at = NOW()
                WHERE id = %s
            """, (res_dict['id'],))
            
            # Décrémenter les places disponibles
            cur.execute("""
                UPDATE carpool_offers
                SET seats_available = seats_available - %s
                WHERE id = %s
            """, (res_dict['passengers'], res_dict['offer_id']))
        
        logger.info(f"✅ Réservation {res_dict['id']} acceptée par conducteur")
        
        # Envoyer email au passager avec coordonnées du conducteur
        try:
            offer_details = {
                'departure': res_dict['departure'],
                'destination': res_dict['destination'],
                'datetime': res_dict['datetime'].strftime('%d/%m/%Y à %H:%M') if res_dict['datetime'] else '',
                'meeting_address': res_dict.get('meeting_point_address') or res_dict['departure']
            }
            
            email_reservation_confirmed_to_passenger(
                passenger_email=res_dict['passenger_email'],
                passenger_name=res_dict['passenger_name'],
                driver_name=res_dict['driver_name'],
                driver_email=res_dict['driver_email'],
                driver_phone=res_dict['driver_phone'],
                offer_details=offer_details
            )
        except Exception as e:
            logger.error(f"Failed to send confirmation email: {e}")
        
        return f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Réservation acceptée</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; background: #f5f5f5;">
            <div style="background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h1 style="color: #4CAF50; margin-bottom: 20px;">✅ Réservation acceptée !</h1>
                <p style="font-size: 16px; color: #333; line-height: 1.6;">
                    <strong>{res_dict['passenger_name']}</strong> va recevoir un email avec vos coordonnées 
                    pour vous contacter directement.
                </p>
                <p style="font-size: 14px; color: #666; margin-top: 20px;">
                    Vous pouvez fermer cette page.
                </p>
            </div>
        </body>
        </html>
        """
        
    except Exception as e:
        logger.error(f"Error accepting reservation: {e}", exc_info=True)
        return "<html><body><h2>❌ Erreur serveur</h2></body></html>", 500


# NOTE: Ces endpoints sont maintenant gérés par api_magic_links.py
# @app.route('/api/v2/reservations/reject/<token>', methods=['GET'])
def _old_reject_reservation(token):
    """Refuser une réservation (lien depuis email conducteur)"""
    if not V2_ENABLED:
        return jsonify({'error': 'API v2 non disponible'}), 503
    
    try:
        with sql.db_cursor() as cur:
            # Trouver la réservation par token
            cur.execute("""
                SELECT r.id, r.offer_id, r.passenger_email, r.passenger_name, r.passengers,
                       r.payment_intent_id, r.payment_status,
                       o.driver_name, o.departure, o.destination, o.datetime, o.seats_available
                FROM carpool_reservations r
                JOIN carpool_offers o ON r.offer_id = o.id
                WHERE r.confirmation_token = %s AND r.status = 'pending'
            """, (token,))
            
            reservation = cur.fetchone()
            
            if not reservation:
                return "<html><body><h2>❌ Lien invalide ou réservation déjà traitée</h2></body></html>", 404
            
            res_dict = dict(zip([d[0] for d in cur.description], reservation))
            
            # Mettre à jour le status
            cur.execute("""
                UPDATE carpool_reservations
                SET status = 'rejected', confirmed_at = NOW()
                WHERE id = %s
            """, (res_dict['id'],))
            
            # PAS de changement de places : la demande était 'pending', 
            # donc les places n'avaient jamais été décrémentées
            
            # TODO: Remboursement Stripe si payment_intent_id existe
            payment_intent_id = res_dict.get('payment_intent_id')
            if payment_intent_id:
                try:
                    # import stripe
                    # stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
                    # stripe.Refund.create(payment_intent=payment_intent_id)
                    logger.info(f"💰 Remboursement Stripe à faire pour: {payment_intent_id}")
                    
                    # Mettre à jour le statut de paiement
                    cur.execute("""
                        UPDATE carpool_reservations
                        SET payment_status = 'refunded'
                        WHERE id = %s
                    """, (res_dict['id'],))
                except Exception as e:
                    logger.error(f"Erreur remboursement Stripe: {e}")
        
        logger.info(f"❌ Réservation {res_dict['id']} refusée par conducteur")
        
        # Envoyer email au passager
        try:
            offer_details = {
                'departure': res_dict['departure'],
                'destination': res_dict['destination'],
                'datetime': res_dict['datetime'].strftime('%d/%m/%Y à %H:%M') if res_dict['datetime'] else ''
            }
            
            email_reservation_rejected_to_passenger(
                passenger_email=res_dict['passenger_email'],
                passenger_name=res_dict['passenger_name'],
                driver_name=res_dict['driver_name'],
                offer_details=offer_details
            )
        except Exception as e:
            logger.error(f"Failed to send rejection email: {e}")
        
        return f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Réservation refusée</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; background: #f5f5f5;">
            <div style="background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h2 style="color: #f44336; margin-bottom: 20px;">Réservation refusée</h2>
                <p style="font-size: 16px; color: #333; line-height: 1.6;">
                    <strong>{res_dict['passenger_name']}</strong> sera notifié par email.
                </p>
                <p style="font-size: 14px; color: #666; margin-top: 20px;">
                    Vous pouvez fermer cette page.
                </p>
            </div>
        </body>
        </html>
        """
        
    except Exception as e:
        logger.error(f"Error rejecting reservation: {e}", exc_info=True)
        return "<html><body><h2>❌ Erreur serveur</h2></body></html>", 500


# NOTE: Endpoint d'annulation (peut rester car différent de magic links)
@app.route('/api/v2/reservations/<int:reservation_id>/cancel', methods=['POST'])
@limiter.limit("10 per minute")
def cancel_reservation(reservation_id):
    """Annuler une réservation pending (par le passager)"""
    if not V2_ENABLED:
        return jsonify({'error': 'API v2 non disponible'}), 503
    
    try:
        data = request.get_json() or {}
        passenger_email = data.get('passenger_email')
        
        if not passenger_email:
            return jsonify({'error': 'Email passager requis'}), 400
        
        with sql.db_cursor() as cur:
            # Vérifier que la réservation existe et appartient au passager
            cur.execute("""
                SELECT r.id, r.offer_id, r.passengers, r.status, r.passenger_email
                FROM carpool_reservations r
                WHERE r.id = %s AND r.passenger_email = %s
            """, (reservation_id, passenger_email))
            
            reservation = cur.fetchone()
            
            if not reservation:
                return jsonify({'error': 'Réservation introuvable ou email incorrect'}), 404
            
            res_dict = dict(zip([d[0] for d in cur.description], reservation))
            
            # Seules les réservations confirmed peuvent être annulées par le passager
            # (les pending peuvent simplement expirer ou être refusées par le conducteur)
            if res_dict['status'] != 'confirmed':
                return jsonify({'error': f"Impossible d'annuler une réservation {res_dict['status']}. Seules les réservations confirmées peuvent être annulées."}), 400
            
            # Annuler la réservation
            cur.execute("""
                UPDATE carpool_reservations
                SET status = 'cancelled', confirmed_at = NOW()
                WHERE id = %s
            """, (reservation_id,))
            
            # Libérer les places (car elles avaient été prises lors de la confirmation)
            cur.execute("""
                UPDATE carpool_offers
                SET seats_available = seats_available + %s
                WHERE id = %s
            """, (res_dict['passengers'], res_dict['offer_id']))
        
        logger.info(f"🚫 Réservation {reservation_id} annulée par passager (+{res_dict['passengers']} places)")
        
        return jsonify({
            'success': True,
            'message': 'Réservation annulée avec succès'
        }), 200
        
    except Exception as e:
        logger.error(f"Error cancelling reservation: {e}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


def compute_base_price(distance_km, include_tolls=False):
    """
    Calcule le prix BlaBlaCar officiel (2024-2025):
    - 0,08 €/km pour les 400 premiers km
    - 0,06 €/km au-delà de 400 km
    - Minimum 2€
    - Arrondi au 0,50€ le plus proche
    - Majoration de 15% si péages inclus
    """
    if distance_km <= 400:
        price = distance_km * 0.08
    else:
        price = (400 * 0.08) + ((distance_km - 400) * 0.06)
    
    if include_tolls:
        price *= 1.15
    
    # Arrondi au 0,50€
    price = round(price * 2) / 2
    
    # Minimum 2€
    return max(2.0, price)


@app.route('/api/carpool/calculate-pickup', methods=['POST'])
@limiter.limit("60 per minute")
def calculate_pickup_times():
    """
    Calcule l'heure de pickup et le prix pour un point de recherche donné
    par rapport aux routes d'une offre.
    
    Body JSON:
    {
        "offer_id": 123,
        "search_point": [lon, lat],
        "trip_type": "outbound" ou "return"
    }
    
    Returns:
    {
        "pickup_time": "2025-12-20 15:30:00",
        "pickup_distance_km": 2.5,
        "segment_price": 8.5,
        "detour_time_minutes": 5
    }
    """
    try:
        data = request.json
        offer_id = data.get('offer_id')
        search_point = data.get('search_point')  # [lon, lat]
        trip_type = data.get('trip_type', 'outbound')
        
        if not offer_id or not search_point:
            return jsonify({'error': 'Missing offer_id or search_point'}), 400
        
        # Récupérer l'offre
        with sql.db_cursor() as cur:
            cur.execute("SELECT * FROM carpool_offers WHERE id = %s", (offer_id,))
            offer = cur.fetchone()
            
            if not offer:
                return jsonify({'error': 'Offer not found'}), 404
            
            offer_dict = dict(zip([d[0] for d in cur.description], offer))
        
        # Décoder la route selon le type de trajet
        route_field = 'route_outbound' if trip_type == 'outbound' else 'route_return'
        route_json = offer_dict.get(route_field)
        
        if not route_json:
            return jsonify({'error': f'No {trip_type} route available'}), 404
        
        route_data = json.loads(route_json) if isinstance(route_json, str) else route_json
        route_coords = route_data.get('geometry', {}).get('coordinates', [])
        
        if not route_coords or len(route_coords) < 2:
            return jsonify({'error': 'Invalid route data'}), 400
        
        # Point de départ et d'arrivée
        start_point = tuple(route_coords[0])
        end_point = tuple(route_coords[-1])
        search_tuple = tuple(search_point)
        
        # Calculer le temps de détour pour aller chercher le passager
        detour_time = calculate_detour_time_osrm(start_point, search_tuple, end_point)
        
        if detour_time is None:
            return jsonify({'error': 'Could not calculate route timing'}), 500
        
        # Calculer la route du point de pickup à la destination
        pickup_to_dest_url = f"https://router.project-osrm.org/route/v1/driving/{search_point[0]},{search_point[1]};{end_point[0]},{end_point[1]}?overview=false"
        
        try:
            resp = requests.get(pickup_to_dest_url, timeout=5)
            if resp.ok:
                route_info = resp.json()
                if route_info.get('code') == 'Ok' and route_info.get('routes'):
                    segment_distance_m = route_info['routes'][0]['distance']
                    segment_duration_s = route_info['routes'][0]['duration']
                    segment_distance_km = segment_distance_m / 1000
                else:
                    return jsonify({'error': 'Could not calculate segment route'}), 500
            else:
                return jsonify({'error': 'OSRM routing failed'}), 500
        except Exception as e:
            logger.error(f"Error calculating segment route: {e}")
            return jsonify({'error': 'Routing service error'}), 500
        
        # Calculer le prix du segment selon tarif BlaBlaCar
        # Vérifier si l'offre inclut les péages
        include_tolls = offer_dict.get('include_tolls', False) or offer_dict.get('includeTolls', False)
        segment_price = compute_base_price(segment_distance_km, include_tolls)
        
        # Calculer l'heure de pickup
        # Heure de départ de l'offre
        departure_time_str = offer_dict.get('datetime')
        if not departure_time_str:
            return jsonify({'error': 'No departure time in offer'}), 400
        
        departure_dt = datetime.strptime(str(departure_time_str), '%Y-%m-%d %H:%M:%S')
        
        # Temps pour aller du départ au point de pickup (approximation: detour_time / 2)
        # Plus précis: calculer la route start -> search_point
        start_to_pickup_url = f"https://router.project-osrm.org/route/v1/driving/{start_point[0]},{start_point[1]};{search_point[0]},{search_point[1]}?overview=false"
        
        try:
            resp = requests.get(start_to_pickup_url, timeout=5)
            if resp.ok:
                route_info = resp.json()
                if route_info.get('code') == 'Ok' and route_info.get('routes'):
                    time_to_pickup_s = route_info['routes'][0]['duration']
                    time_to_pickup_min = time_to_pickup_s / 60
                else:
                    # Fallback: utiliser detour_time / 2
                    time_to_pickup_min = detour_time / 2
            else:
                time_to_pickup_min = detour_time / 2
        except:
            time_to_pickup_min = detour_time / 2
        
        # Heure de pickup = heure de départ + temps pour arriver au pickup
        pickup_dt = departure_dt + timedelta(minutes=time_to_pickup_min)
        pickup_time_str = pickup_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'pickup_time': pickup_time_str,
            'pickup_distance_km': round(segment_distance_km, 1),
            'segment_price': segment_price,
            'detour_time_minutes': round(detour_time, 1)
        })
    
    except Exception as e:
        logger.error(f"Error in calculate_pickup_times: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# MAGIC LINKS - Enregistrer les routes pour les actions par email
# ============================================================================
from api_magic_links import register_magic_link_routes
register_magic_link_routes(app, db_cursor_v2)

if __name__ == '__main__':
    # Initialiser les tables au démarrage
    try:
        from init_carpool_tables import init_carpool_tables
        init_carpool_tables()
    except Exception as e:
        print(f"⚠️ Warning: Could not init tables: {e}")
    
    # Initialiser les tables v2 si activées
    if V2_ENABLED:
        try:
            # Les tables sont déjà initialisées par init_carpool_tables au démarrage
            print("✅ Tables v2 (maintenant tables principales) déjà initialisées")
        except Exception as e:
            print(f"⚠️ Warning: Could not init v2 tables: {e}")
    
    app.run(host='0.0.0.0', port=9000, debug=True)


# ============================================
# ENDPOINTS GEOCODAGE (Autocomplétion adresses)
# ============================================

@app.route('/api/geocode/search', methods=['GET'])
@limiter.limit("60 per minute")
def search_geocode():
    """Proxy pour recherche d'adresse (BAN puis Nominatim en fallback)"""
    from urllib.parse import quote as url_quote
    
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', '5')
    
    if not query:
        return jsonify({'error': 'paramètre q requis'}), 400
    
    # Validation de la limite
    try:
        limit_int = validate_integer(limit, min_val=1, max_val=20, field_name="limit")
        limit = str(limit_int)
    except ValueError:
        limit = '5'
    
    try:
        # API BAN (Base Adresse Nationale - France)
        ban_url = f"https://api-adresse.data.gouv.fr/search/?q={url_quote(query)}&limit={limit}"
        ban_resp = requests.get(ban_url, timeout=10)
        
        if ban_resp.status_code == 200:
            ban_data = ban_resp.json()
            if ban_data.get('features'):
                best_score = max((f.get('properties', {}).get('score', 0) for f in ban_data['features']), default=0)
                
                if best_score > 0.5:
                    # Formater résultats BAN
                    ban_features = []
                    for feature in ban_data['features']:
                        props = feature.get('properties', {})
                        coords = feature.get('geometry', {}).get('coordinates', [])
                        ban_features.append({
                            'label': props.get('label', ''),
                            'name': props.get('name', ''),
                            'postcode': props.get('postcode', ''),
                            'city': props.get('city', ''),
                            'context': props.get('context', ''),
                            'type': props.get('type', ''),
                            'score': props.get('score', 0),
                            'lon': coords[0] if len(coords) > 0 else None,
                            'lat': coords[1] if len(coords) > 1 else None
                        })
                    return jsonify({'features': ban_features, 'source': 'ban'})
        
        # Fallback Nominatim (couverture mondiale)
        nom_url = f"https://nominatim.openstreetmap.org/search?format=json&q={url_quote(query)}&limit={limit}&addressdetails=1"
        nom_headers = {'User-Agent': 'Carette-Carpool-Widget/1.0'}
        nom_resp = requests.get(nom_url, headers=nom_headers, timeout=10)
        
        if nom_resp.status_code == 200:
            nom_data = nom_resp.json()
            nom_features = []
            for item in nom_data:
                nom_features.append({
                    'label': item.get('display_name', ''),
                    'name': item.get('name', ''),
                    'type': item.get('type', ''),
                    'lon': float(item.get('lon', 0)),
                    'lat': float(item.get('lat', 0))
                })
            return jsonify({'features': nom_features, 'source': 'nominatim'})
        
        return jsonify({'features': [], 'source': 'none'})
        
    except Exception as e:
        logger.error(f"Error in search_geocode: {str(e)}")
        if app.debug:
            return jsonify({"error": str(e)}), 500
        else:
            return jsonify({"error": "Erreur serveur"}), 500


@app.route('/api/geocode/reverse', methods=['GET'])
@limiter.limit("60 per minute")
def reverse_geocode():
    """Géocodage inversé (coordonnées -> adresse)"""
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    
    if not lat or not lon:
        return jsonify({'error': 'lat et lon requis'}), 400
    
    try:
        # Validation des coordonnées
        lon, lat = validate_coordinates(lon, lat)
        
        # Nominatim reverse geocoding
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
        headers = {'User-Agent': 'Carette-Carpool-Widget/1.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            return jsonify(resp.json())
        else:
            return jsonify({'error': 'Géocodage inversé échoué'}), 500
    
    except ValueError as e:
        logger.warning(f"Validation error in reverse_geocode: {e}")
        return jsonify({"error": str(e)}), 400
            
    except Exception as e:
        logger.error(f"Error in reverse_geocode: {str(e)}", exc_info=True)
        if app.debug:
            return jsonify({"error": str(e)}), 500
        else:
            return jsonify({"error": "Erreur serveur"}), 500


@app.route('/api/v2/offers/recurrent', methods=['POST'])
@limiter.limit("10 per minute")
def create_recurrent_offer():
    """
    Créer une offre de covoiturage récurrente (B2B entre collègues)
    """
    try:
        data = request.get_json()
        logger.info(f"📦 Données reçues: company_id={data.get('company_id')}, site_name={data.get('site_name')}, site_address={data.get('site_address')}")
        
        # Validation des champs obligatoires
        driver_name = sanitize_text(data.get('driver_name', ''))
        driver_email = validate_email(data.get('driver_email', ''))
        driver_phone = sanitize_text(data.get('driver_phone', ''))
        
        if not driver_name or not driver_email or not driver_phone:
            return jsonify({'error': 'Coordonnées conducteur manquantes'}), 400
        
        # Adresses
        departure = sanitize_text(data.get('departure', ''))
        destination = sanitize_text(data.get('destination', ''))
        
        if not departure or not destination:
            return jsonify({'error': 'Adresses de départ et arrivée requises'}), 400
        
        # Récupérer company_id et site_id depuis le widget
        company_id = validate_integer(data.get('company_id'))
        site_id = data.get('site_id')  # Peut être None
        if site_id:
            site_id = validate_integer(site_id)
        
        # Informations du site (pour créer/vérifier le site)
        site_name = sanitize_text(data.get('site_name', ''))
        site_address = sanitize_text(data.get('site_address', ''))
        site_coords = data.get('site_coords')  # [lon, lat]
        
        if not company_id:
            return jsonify({'error': 'company_id requis pour le mode récurrent'}), 400
        
        # Vérifier si l'utilisateur a déjà une offre active
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT id FROM carpool_offers_recurrent 
                WHERE driver_email = %s AND status = 'active'
                LIMIT 1
            """, (driver_email,))
            
            existing_offer = cur.fetchone()
            
            if existing_offer:
                return jsonify({
                    'error': 'Vous avez déjà une offre de covoiturage active. Veuillez la désactiver avant d\'en créer une nouvelle.',
                    'existing_offer_id': existing_offer[0]
                }), 409
        
        # Si site_id n'est pas fourni mais qu'on a les infos du site, on le crée/récupère
        if not site_id and site_name and site_address:
            with sql.db_cursor() as cur:
                # Vérifier si le site existe déjà pour cette entreprise
                cur.execute("""
                    SELECT id FROM company_sites 
                    WHERE company_id = %s AND site_name = %s
                    LIMIT 1
                """, (company_id, site_name))
                
                existing_site = cur.fetchone()
                
                if existing_site:
                    site_id = existing_site[0]
                    logger.info(f"Site existant trouvé: {site_name} (ID={site_id})")
                else:
                    # Créer le nouveau site
                    cur.execute("""
                        INSERT INTO company_sites (company_id, site_name, site_address, site_coords)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        company_id, 
                        site_name, 
                        site_address,
                        json.dumps(site_coords) if site_coords else None
                    ))
                    site_id = cur.lastrowid
                    logger.info(f"Nouveau site créé: {site_name} (ID={site_id})")
        
        if not site_id:
            return jsonify({'error': 'Impossible de déterminer le site (site_id ou site_name/site_address requis)'}), 400
        
        # Coordonnées géographiques
        departure_coords = data.get('departure_coords')  # [lon, lat]
        destination_coords = data.get('destination_coords')
        
        if departure_coords:
            validate_coordinates(departure_coords[0], departure_coords[1])
        if destination_coords:
            validate_coordinates(destination_coords[0], destination_coords[1])
        
        # Jours de la semaine
        days = {
            'monday': bool(data.get('monday', False)),
            'tuesday': bool(data.get('tuesday', False)),
            'wednesday': bool(data.get('wednesday', False)),
            'thursday': bool(data.get('thursday', False)),
            'friday': bool(data.get('friday', False)),
            'saturday': bool(data.get('saturday', False)),
            'sunday': bool(data.get('sunday', False))
        }
        
        # Au moins un jour doit être sélectionné
        if not any(days.values()):
            return jsonify({'error': 'Au moins un jour de covoiturage doit être sélectionné'}), 400
        
        # Heures (en mode récurrent, on a une heure d'arrivée au travail et une heure de départ du travail)
        time_outbound = data.get('time_outbound', '')  # Heure d'arrivée souhaitée sur site
        time_return = data.get('time_return', '')  # Heure de départ depuis le site
        
        if not time_outbound or not time_return:
            return jsonify({'error': 'Heures aller et retour requises'}), 400
        
        # Places disponibles
        seats = validate_integer(data.get('seats', 4))
        if seats < 1 or seats > 8:
            return jsonify({'error': 'Nombre de places invalide (1-8)'}), 400
        
        # Budget détour
        max_detour_time = validate_integer(data.get('max_detour_time', 25))
        
        # Couleurs (définies par l'utilisateur dans le widget)
        color_outbound = data.get('color_outbound', '#7c3aed')
        color_return = data.get('color_return', '#f97316')
        
        # Normaliser les couleurs (retirer le canal alpha si présent)
        if color_outbound and len(color_outbound) == 9:  # #RRGGBBAA
            color_outbound = color_outbound[:7]  # #RRGGBB
        if color_return and len(color_return) == 9:
            color_return = color_return[:7]
        
        # Routes (geometries)
        route_outbound = data.get('route_outbound')
        route_return = data.get('route_return')
        
        # Insérer dans la base de données
        with sql.db_cursor() as cur:
            cur.execute("""
                INSERT INTO carpool_offers_recurrent 
                (company_id, site_id, departure, destination, departure_coords, destination_coords,
                 recurrent_time, time_return, monday, tuesday, wednesday, thursday, friday, saturday, sunday,
                 seats, route_outbound, route_return, max_detour_time, color_outbound, color_return,
                 driver_email, driver_name, driver_phone, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')
            """, (
                company_id, site_id, departure, destination,
                json.dumps(departure_coords) if departure_coords else None,
                json.dumps(destination_coords) if destination_coords else None,
                time_outbound,
                time_return,
                days['monday'], days['tuesday'], days['wednesday'], days['thursday'],
                days['friday'], days['saturday'], days['sunday'],
                seats,
                json.dumps(route_outbound) if route_outbound else None,
                json.dumps(route_return) if route_return else None,
                max_detour_time,
                color_outbound,
                color_return,
                driver_email, driver_name, driver_phone
            ))
            
            offer_id = cur.lastrowid
        
        logger.info(f"Offre récurrente créée: ID={offer_id}, conducteur={driver_name}, company={company_id}, site={site_id}")
        
        # Envoyer l'email de confirmation au conducteur
        try:
            from email_templates import email_recurrent_offer_published
            from emails import send_email
            
            # Préparer les données de l'offre pour le template
            offer_data = {
                'departure': departure,
                'destination': destination,
                'time_outbound': time_outbound,
                'time_return': time_return,
                'monday': data.get('monday', False),
                'tuesday': data.get('tuesday', False),
                'wednesday': data.get('wednesday', False),
                'thursday': data.get('thursday', False),
                'friday': data.get('friday', False),
                'saturday': data.get('saturday', False),
                'sunday': data.get('sunday', False),
                'seats': seats,
                'max_detour_time': max_detour_time,
                'departure_coords': departure_coords,
                'destination_coords': destination_coords,
                'route_outbound': route_outbound,
                'route_return': route_return,
                'color_outbound': color_outbound,
                'color_return': color_return,
                'offer_id': offer_id,
                'is_rse': data.get('is_rse', False),
                'transport_modes': data.get('transport_modes', {}),
                'distance_km': route_outbound.get('distance', 0) / 1000 if route_outbound else 0
            }
            
            subject, html_body, text_body = email_recurrent_offer_published(driver_email, driver_name, offer_data)
            
            # Pas de pièces jointes pour les offres récurrentes (juste le bouton Google Maps)
            send_email(driver_email, subject, html_body, text_body)
            logger.info(f"✅ Email de confirmation envoyé à {driver_email}")
        except Exception as e:
            logger.warning(f"⚠️ Échec envoi email confirmation: {e}")
            import traceback
            logger.warning(traceback.format_exc())
        
        return jsonify({
            'success': True,
            'offer_id': offer_id,
            'message': 'Offre de covoiturage récurrent créée avec succès'
        }), 201
        
    except ValueError as e:
        logger.warning(f"Validation error in create_recurrent_offer: {e}")
        return jsonify({'error': str(e)}), 400
    except IntegrityError as e:
        logger.error(f"Database integrity error: {e}")
        return jsonify({'error': 'Erreur d\'intégrité de la base de données'}), 409
    except Exception as e:
        logger.error(f"Error in create_recurrent_offer: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


def geocode_address_auto(address, cur):
    """
    Géocode automatiquement une adresse et stocke le résultat en cache
    
    Args:
        address: Adresse complète à géocoder
        cur: Curseur DB pour accès à geocoding_cache
    
    Returns:
        dict: {'lat': float, 'lon': float} ou None si échec
    """
    if not address or address.strip() == '':
        return None
    
    address = address.strip()
    
    # Vérifier d'abord dans le cache
    cur.execute("SELECT latitude, longitude FROM geocoding_cache WHERE address = %s", (address,))
    cached = cur.fetchone()
    
    if cached and cached['latitude']:
        return {
            'lat': float(cached['latitude']),
            'lon': float(cached['longitude'])
        }
    
    # Géocoder via Nominatim
    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'q': address,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'fr'
            },
            headers={'User-Agent': 'Carette-RSE-Dashboard/1.0'},
            timeout=3
        )
        
        if response.status_code == 200:
            results = response.json()
            if results:
                lat = float(results[0]['lat'])
                lon = float(results[0]['lon'])
                
                # Créer la table si elle n'existe pas
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS geocoding_cache (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        address VARCHAR(500) NOT NULL UNIQUE,
                        latitude DECIMAL(10, 8),
                        longitude DECIMAL(11, 8),
                        geocoded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_address (address)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                
                # Stocker en cache
                cur.execute("""
                    INSERT INTO geocoding_cache (address, latitude, longitude)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        latitude = VALUES(latitude),
                        longitude = VALUES(longitude),
                        geocoded_at = CURRENT_TIMESTAMP
                """, (address, lat, lon))
                
                logger.info(f"📍 Géocodé: {address} → {lat}, {lon}")
                return {'lat': lat, 'lon': lon}
    except Exception as e:
        logger.warning(f"⚠️ Échec géocodage pour '{address}': {e}")
    
    return None


@app.route('/api/v2/rse/submit', methods=['POST'])
@limiter.limit("10 per minute")
def submit_rse_data():
    """
    Enregistre les données RSE (bilan carbone) en base de données et envoie un email de confirmation
    """
    try:
        from datetime import datetime, timedelta
        import secrets
        
        data = request.json
        logger.info(f"📊 Soumission RSE reçue: {data}")
        
        # Validation des champs requis
        required_fields = ['user_name', 'user_email', 'departure', 'destination', 
                          'distance_km', 'transport_modes', 'co2_emissions', 'total_co2']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Champ manquant: {field}")
        
        # Extraire les données
        user_name = data['user_name']
        user_email = data['user_email']
        user_phone = data.get('user_phone', '')
        company_code = data.get('company_code', '')  # NOUVEAU : code entreprise
        departure = data['departure']
        destination = data['destination']
        distance_km = float(data['distance_km'])
        transport_modes = data['transport_modes']  # {monday: 0, tuesday: 1, ...}
        co2_emissions = data['co2_emissions']  # {monday: 13.2, tuesday: 3.0, ...}
        total_co2 = float(data['total_co2'])
        
        # Mapping des indices vers les codes transport
        transport_mapping = [
            'voiture_solo',      # 0: 🚗
            'transports_commun', # 1: 🚌
            'covoiturage',       # 2: 🚗👥
            'velo',              # 3: 🚴
            'train',             # 4: 🚆
            'teletravail',       # 5: 🏠
            'marche',            # 6: 🚶
            'ne_travaille_pas'   # 7: 🌴
        ]
        
        # Calculer la semaine en cours (lundi à vendredi)
        today = datetime.now()
        # Lundi de cette semaine
        days_since_monday = today.weekday()  # 0=lundi, 6=dimanche
        week_start = today - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=4)  # vendredi
        
        with sql.db_cursor() as cur:
            # Déterminer le company_id (auto-assignation)
            company_id = None
            
            # Option 1 : Code entreprise fourni
            if company_code:
                cur.execute("""
                    SELECT id, name, email_domain 
                    FROM companies 
                    WHERE company_code = %s AND active = 1
                """, (company_code,))
                company = cur.fetchone()
                
                if company:
                    company_id = company['id']
                    logger.info(f"🏢 Entreprise trouvée via code '{company_code}': {company['name']}")
                    
                    # Vérifier que l'email correspond au domaine (optionnel mais recommandé)
                    email_domain = company['email_domain']
                    if email_domain and not user_email.endswith(f"@{email_domain}"):
                        logger.warning(f"⚠️ Email {user_email} ne correspond pas au domaine {email_domain}")
                else:
                    logger.warning(f"⚠️ Code entreprise '{company_code}' invalide ou inactif")
            
            # Option 2 : Auto-détection via domaine email
            if not company_id:
                email_parts = user_email.split('@')
                if len(email_parts) == 2:
                    domain = email_parts[1]
                    cur.execute("""
                        SELECT id, name 
                        FROM companies 
                        WHERE email_domain = %s
                    """, (domain,))
                    company = cur.fetchone()
                    
                    if company:
                        company_id = company['id']
                        logger.info(f"🏢 Entreprise auto-détectée via domaine '{domain}': {company['name']}")
            
            # 1. Créer ou mettre à jour l'utilisateur RSE
            cur.execute("SELECT id, company_id FROM rse_users WHERE email = %s", (user_email,))
            existing_user = cur.fetchone()
            
            if existing_user:
                user_id = existing_user['id']
                # Géocoder l'adresse de départ automatiquement
                geocode_address_auto(departure, cur)
                
                # Mettre à jour les infos (et company_id si trouvé)
                if company_id and not existing_user['company_id']:
                    cur.execute("""
                        UPDATE rse_users 
                        SET name = %s, departure_address = %s, destination_address = %s, 
                            distance_km = %s, phone = %s, company_id = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (user_name, departure, destination, distance_km, user_phone, company_id, user_id))
                    logger.info(f"✏️ Utilisateur RSE mis à jour avec company_id={company_id}: {user_email}")
                else:
                    cur.execute("""
                        UPDATE rse_users 
                        SET name = %s, departure_address = %s, destination_address = %s, 
                            distance_km = %s, phone = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (user_name, departure, destination, distance_km, user_phone, user_id))
                    logger.info(f"✏️ Utilisateur RSE mis à jour: {user_email} (ID: {user_id})")
            else:
                # Géocoder l'adresse de départ automatiquement
                geocode_address_auto(departure, cur)
                
                cur.execute("""
                    INSERT INTO rse_users 
                    (name, email, phone, departure_address, destination_address, distance_km, company_id, active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                """, (user_name, user_email, user_phone, departure, destination, distance_km, company_id))
                user_id = cur.lastrowid
                logger.info(f"✨ Nouvel utilisateur RSE créé: {user_email} (ID: {user_id}, Company: {company_id})")
            
            # 2. Créer ou mettre à jour la semaine
            cur.execute("""
                SELECT id, magic_token 
                FROM rse_weekly_data 
                WHERE user_id = %s AND week_start = %s
            """, (user_id, week_start.strftime('%Y-%m-%d')))
            
            existing_week = cur.fetchone()
            is_update = False
            
            if existing_week:
                weekly_data_id = existing_week['id']
                magic_token = existing_week['magic_token']
                is_update = True
                # Mettre à jour le total CO2 et RÉINITIALISER la confirmation
                cur.execute("""
                    UPDATE rse_weekly_data 
                    SET total_co2 = %s, total_distance = %s, confirmed = 0, confirmed_at = NULL, updated_at = NOW()
                    WHERE id = %s
                """, (total_co2, distance_km * 10, weekly_data_id))  # 5 jours AR
                logger.info(f"✏️ Semaine RSE mise à jour (ID: {weekly_data_id}) - Confirmation réinitialisée")
            else:
                magic_token = secrets.token_urlsafe(32)
                cur.execute("""
                    INSERT INTO rse_weekly_data 
                    (user_id, week_start, week_end, magic_token, total_co2, total_distance)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    week_start.strftime('%Y-%m-%d'),
                    week_end.strftime('%Y-%m-%d'),
                    magic_token,
                    total_co2,
                    distance_km * 10
                ))
                weekly_data_id = cur.lastrowid
                logger.info(f"✨ Nouvelle semaine RSE créée (ID: {weekly_data_id})")
            
            # 3. Enregistrer les trajets quotidiens
            day_names = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
            day_keys = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            
            # Supprimer les trajets existants pour cette semaine
            cur.execute("DELETE FROM rse_daily_transports WHERE weekly_data_id = %s", (weekly_data_id,))
            
            # Créer les nouveaux trajets
            for i, day_key in enumerate(day_keys):
                day_date = week_start + timedelta(days=i)
                mode_index = transport_modes.get(day_key, 0)
                transport_code = transport_mapping[mode_index] if 0 <= mode_index < len(transport_mapping) else 'voiture_solo'
                co2_kg = float(co2_emissions.get(day_key, 0))
                
                cur.execute("""
                    INSERT INTO rse_daily_transports 
                    (weekly_data_id, date, day_name, transport_mode, co2_total, distance_total)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    weekly_data_id,
                    day_date.strftime('%Y-%m-%d'),
                    day_names[i],
                    transport_code,
                    co2_kg,
                    distance_km * 2  # Aller-retour
                ))
            
            logger.info(f"✅ {len(day_keys)} trajets quotidiens enregistrés")
            
            # 4. Sauvegarder les habitudes par défaut (pour les semaines futures)
            habits_data = {}
            day_keys_habits = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
            
            for day_key in day_keys_habits:
                mode_index = transport_modes.get(day_key, 0)
                transport_code = transport_mapping[mode_index] if 0 <= mode_index < len(transport_mapping) else 'voiture_solo'
                habits_data[day_key] = transport_code
            
            # Insérer ou mettre à jour les habitudes
            cur.execute("SELECT id FROM rse_user_habits WHERE user_id = %s", (user_id,))
            existing_habits = cur.fetchone()
            
            if existing_habits:
                cur.execute("""
                    UPDATE rse_user_habits
                    SET monday = %s, tuesday = %s, wednesday = %s, thursday = %s, friday = %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                """, (
                    habits_data['monday'], habits_data['tuesday'], habits_data['wednesday'],
                    habits_data['thursday'], habits_data['friday'],
                    user_id
                ))
                logger.info(f"✏️ Habitudes mises à jour pour user_id={user_id}")
            else:
                cur.execute("""
                    INSERT INTO rse_user_habits
                    (user_id, monday, tuesday, wednesday, thursday, friday)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    habits_data['monday'], habits_data['tuesday'], habits_data['wednesday'],
                    habits_data['thursday'], habits_data['friday']
                ))
                logger.info(f"✨ Habitudes créées pour user_id={user_id}")
        
        # Préparer les données pour l'email
        rse_data = {
            'departure': departure,
            'destination': destination,
            'distance_km': distance_km,
            'co2_emissions': co2_emissions,
            'transport_modes': transport_modes,
            'total_co2': total_co2,
            'has_carpool_offer': data.get('has_carpool_offer', False),
            'max_detour_time': data.get('max_detour_time', 10),
            'car_days': data.get('car_days', []),
            'is_update': is_update  # Nouveau flag
        }
        
        # Envoyer l'email de confirmation
        try:
            from email_templates import email_rse_confirmation
            from email_sender import send_email
            
            subject, html_body, text_body = email_rse_confirmation(user_name, user_email, rse_data)
            send_email(user_email, subject, html_body, text_body)
            logger.info(f"✅ Email RSE envoyé à {user_email}")
        except Exception as e:
            logger.warning(f"⚠️ Échec envoi email RSE: {e}")
            import traceback
            logger.warning(traceback.format_exc())
        
        return jsonify({
            'success': True,
            'message': 'Bilan carbone mis à jour avec succès' if is_update else 'Bilan carbone enregistré avec succès',
            'is_update': is_update,
            'user_id': user_id,
            'weekly_data_id': weekly_data_id
        }), 200
        
    except ValueError as e:
        logger.warning(f"Validation error in submit_rse_data: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error in submit_rse_data: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/offers/recurrent/<int:offer_id>/cancel', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def cancel_recurrent_offer(offer_id):
    """
    Désactiver une offre de covoiturage récurrente
    """
    try:
        with sql.db_cursor() as cur:
            # Vérifier que l'offre existe
            cur.execute("""
                SELECT id, driver_email, driver_name, status 
                FROM carpool_offers_recurrent 
                WHERE id = %s
            """, (offer_id,))
            
            offer = cur.fetchone()
            
            if not offer:
                return jsonify({'error': 'Offre non trouvée'}), 404
            
            offer_id_db, driver_email, driver_name, current_status = offer
            
            if current_status == 'cancelled':
                return jsonify({'error': 'Offre déjà désactivée'}), 400
            
            # Désactiver l'offre
            cur.execute("""
                UPDATE carpool_offers_recurrent 
                SET status = 'cancelled' 
                WHERE id = %s
            """, (offer_id,))
            
            logger.info(f"Offre récurrente désactivée: ID={offer_id}, conducteur={driver_name}")
            
            # Envoyer un email de confirmation
            try:
                from emails import send_email
                
                subject = f"🛑 Votre offre de covoiturage récurrent a été désactivée"
                html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
    <div style="max-width:600px;margin:40px auto;padding:20px;">
        <div style="background:#fff;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.12);padding:32px;text-align:center;">
            <div style="font-size:64px;margin-bottom:16px;">🛑</div>
            <h2 style="color:#ef4444;margin:0 0 16px;">Offre désactivée</h2>
            <p style="color:#666;font-size:15px;line-height:1.6;">
                Bonjour {driver_name},<br/><br/>
                Votre offre de covoiturage récurrent a bien été désactivée.<br/>
                Elle n'apparaîtra plus dans les recherches de vos collègues.
            </p>
            <div style="margin-top:32px;padding-top:24px;border-top:1px solid #e5e7eb;">
                <p style="font-size:13px;color:#999;">L'équipe Carette</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
                text_body = f"""
🛑 Offre désactivée

Bonjour {driver_name},

Votre offre de covoiturage récurrent a bien été désactivée.
Elle n'apparaîtra plus dans les recherches de vos collègues.

L'équipe Carette
"""
                send_email(driver_email, subject, html_body, text_body)
                logger.info(f"✅ Email de désactivation envoyé à {driver_email}")
            except Exception as e:
                logger.warning(f"⚠️ Échec envoi email désactivation: {e}")
        
        # Si c'est un GET (depuis l'email), retourner une page HTML
        if request.method == 'GET':
            return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Offre désactivée</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
    <div style="max-width:600px;margin:80px auto;padding:20px;">
        <div style="background:#fff;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.12);padding:48px;text-align:center;">
            <div style="font-size:80px;margin-bottom:24px;">✅</div>
            <h1 style="color:#10b981;margin:0 0 16px;font-size:28px;">Offre désactivée</h1>
            <p style="color:#666;font-size:16px;line-height:1.6;margin-bottom:32px;">
                Votre offre de covoiturage récurrent a bien été désactivée.<br/>
                Elle n'apparaîtra plus dans les recherches de vos collègues.
            </p>
            <div style="background:#f8f9fa;border-radius:8px;padding:20px;margin-bottom:24px;">
                <p style="color:#666;font-size:14px;margin:0;">
                    💡 Vous pouvez toujours créer une nouvelle offre quand vous le souhaitez !
                </p>
            </div>
            <div style="margin-top:32px;padding-top:24px;border-top:1px solid #e5e7eb;">
                <p style="font-size:13px;color:#999;margin:0;">L'équipe Carette 🚗</p>
            </div>
        </div>
    </div>
</body>
</html>
            """, 200
        
        # Si c'est un POST (API), retourner du JSON
        return jsonify({
            'success': True,
            'message': 'Offre désactivée avec succès'
        }), 200
        
    except Exception as e:
        logger.error(f"Error in cancel_recurrent_offer: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/offers/recurrent/search', methods=['POST'])
@limiter.limit("60 per minute")
def search_recurrent_offers():
    """Rechercher des offres de covoiturage récurrentes"""
    if not V2_ENABLED:
        return jsonify({'error': 'API v2 non disponible'}), 503
    
    try:
        data = request.get_json()

        # Paramètres requis
        site_id = data.get('site_id')
        departure_coords = data.get('departure_coords')  # [lon, lat]
        days = data.get('days', [])  # Liste des jours: ['monday', 'tuesday', ...] (optionnel)
        # search_radius_m n'est plus fourni par le passager; par défaut 2km
        search_radius_m = 2000.0  # mètres

        # Vérifier que le site_id est bien un entier strictement positif
        try:
            site_id_int = int(site_id)
            if site_id_int <= 0:
                return jsonify({'offers': []})
        except (TypeError, ValueError):
            return jsonify({'offers': []})

        # Vérifier que le site existe AVANT toute requête
        with sql.db_cursor() as cur:
            cur.execute("SELECT id FROM company_sites WHERE id = %s", (site_id_int,))
            site_row = cur.fetchone()
        if not site_row:
            return jsonify({'offers': []})

        if not departure_coords or len(departure_coords) != 2:
            return jsonify({'error': 'departure_coords requis (format: [lon, lat])'}), 400
        # Rayon fixe par défaut (2km) pour simplifier l'expérience passager
        try:
            search_radius_m = float(search_radius_m)
        except Exception:
            search_radius_m = 2000.0

        # Construire la clause WHERE pour les jours (optionnel)
        day_clause = ""
        if days and isinstance(days, list) and len(days) > 0:
            # On cherche les offres qui ont au moins un jour en commun avec la recherche
            day_conditions = []
            for day in days:
                if day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                    day_conditions.append(f"{day} = 1")
            
            if day_conditions:
                day_clause = " AND (" + " OR ".join(day_conditions) + ")"
        
        try:
            with sql.db_cursor() as cur:
                # Rechercher les offres actives pour ce site
                query = f"""
                    SELECT 
                        id, company_id, site_id,
                        driver_name, driver_email, driver_phone,
                        departure, destination,
                        departure_coords, destination_coords,
                        recurrent_time, time_return,
                        monday, tuesday, wednesday, thursday, friday, saturday, sunday,
                        seats, max_detour_time,
                        route_outbound, route_return,
                        created_at, status
                    FROM carpool_offers_recurrent
                    WHERE site_id = %s 
                    AND status = 'active'
                    {day_clause}
                    LIMIT 50
                """
                
                cur.execute(query, (site_id,))
                rows = cur.fetchall()
        except Exception as sql_error:
            logger.error(f"SQL error in recurrent search (site_id={site_id}): {sql_error}")
            return jsonify({'offers': [], 'count': 0}), 200
        
        # Colonnes dans l'ordre du SELECT
        columns = ['id', 'company_id', 'site_id', 'driver_name', 'driver_email', 'driver_phone',
                   'departure', 'destination', 'departure_coords', 'destination_coords',
                   'recurrent_time', 'time_return',
                   'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                   'seats', 'max_detour_time', 'route_outbound', 'route_return', 'created_at', 'status']
        
        # Point de recherche de l'utilisateur
        user_point = departure_coords  # [lon, lat]
        
        offers = []
        for row in rows:
            # Créer un dict depuis le tuple
            row_dict = dict(zip(columns, row))
            
            # Parser les coordonnées et routes
            dep_coords = json.loads(row_dict['departure_coords']) if row_dict['departure_coords'] else None
            dest_coords = json.loads(row_dict['destination_coords']) if row_dict['destination_coords'] else None
            route_outbound_raw = json.loads(row_dict['route_outbound']) if row_dict['route_outbound'] else None
            route_return_raw = json.loads(row_dict['route_return']) if row_dict['route_return'] else None
            
            # Extraire les coordonnées depuis la structure OSRM
            # Format: {legs: [{steps: [{geometry: {coordinates: [[lon, lat], ...]}}]}]}
            # ou {geometry: [[lon, lat], ...], waypoints: [...], duration: ...}
            def extract_coordinates(route):
                """Extrait les coordonnées d'une route OSRM"""
                if not route:
                    return None
                try:
                    # Si c'est déjà un tableau de coordonnées
                    if isinstance(route, list) and len(route) > 0 and isinstance(route[0], list):
                        return route
                    # Si c'est notre nouveau format {geometry: [...], waypoints: [...], duration: ...}
                    if isinstance(route, dict) and 'geometry' in route:
                        geom = route['geometry']
                        if isinstance(geom, list) and len(geom) > 0:
                            return geom
                    # Si c'est une structure OSRM complète
                    if isinstance(route, dict) and 'legs' in route:
                        coords = []
                        for leg in route['legs']:
                            for step in leg.get('steps', []):
                                geom = step.get('geometry', {})
                                step_coords = geom.get('coordinates', [])
                                coords.extend(step_coords)
                        return coords if coords else None
                except Exception as e:
                    logger.warning(f"Erreur extraction coordonnées route: {e}")
                return None
            
            route_outbound = extract_coordinates(route_outbound_raw)
            route_return = extract_coordinates(route_return_raw)

            # Normaliser les coords (floats) et fallback sur route si nécessaire
            try:
                if dep_coords and isinstance(dep_coords, (list, tuple)) and len(dep_coords) == 2:
                    dep_coords = [float(dep_coords[0]), float(dep_coords[1])]
                if dest_coords and isinstance(dest_coords, (list, tuple)) and len(dest_coords) == 2:
                    dest_coords = [float(dest_coords[0]), float(dest_coords[1])]
            except Exception:
                pass
            if (not dep_coords) and route_outbound and len(route_outbound) >= 1:
                try:
                    dep_coords = [float(route_outbound[0][0]), float(route_outbound[0][1])]
                except Exception:
                    dep_coords = None
            if (not dest_coords) and route_outbound and len(route_outbound) >= 1:
                try:
                    dest_coords = [float(route_outbound[-1][0]), float(route_outbound[-1][1])]
                except Exception:
                    dest_coords = None
            
            # Calculer le buffer de détour restant
            max_detour_time = row_dict['max_detour_time'] or 25  # 25 min par défaut (budget total)
            
            # Récupérer le détour déjà consommé par les passagers confirmés ET pending
            # Les pending "réservent" temporairement le budget
            with sql.db_cursor() as cur_inner:
                cur_inner.execute("""
                    SELECT COALESCE(SUM(detour_time_outbound), 0) as total_detour_out,
                           COALESCE(SUM(detour_time_return), 0) as total_detour_ret
                    FROM carpool_reservations_recurrent
                    WHERE offer_id = %s AND status IN ('confirmed', 'pending')
                """, (row_dict['id'],))
                detour_consumed = cur_inner.fetchone()
                consumed_outbound = float(detour_consumed['total_detour_out'] or 0)
                consumed_return = float(detour_consumed['total_detour_ret'] or 0)
            
            # Calculer le budget restant
            remaining_buffer_outbound = max_detour_time - consumed_outbound
            remaining_buffer_return = max_detour_time - consumed_return
            
            logger.info(f"📊 Offre {row_dict['id']}: Budget total={max_detour_time}min | "
                       f"Consommé aller={consumed_outbound:.1f}min, retour={consumed_return:.1f}min | "
                       f"Restant aller={remaining_buffer_outbound:.1f}min, retour={remaining_buffer_return:.1f}min")
            
            # Calculer le nombre maximum de passagers sur tous les jours de la semaine
            # pour décrémenter les places disponibles
            with sql.db_cursor() as cur_inner2:
                cur_inner2.execute("""
                    SELECT 
                        SUM(monday) as mon, SUM(tuesday) as tue, SUM(wednesday) as wed,
                        SUM(thursday) as thu, SUM(friday) as fri, SUM(saturday) as sat, SUM(sunday) as sun
                    FROM carpool_reservations_recurrent
                    WHERE offer_id = %s AND status IN ('confirmed', 'pending')
                """, (row_dict['id'],))
                day_counts = cur_inner2.fetchone()
                max_passengers_per_day = max(
                    int(day_counts[0] or 0), int(day_counts[1] or 0), int(day_counts[2] or 0),
                    int(day_counts[3] or 0), int(day_counts[4] or 0), int(day_counts[5] or 0),
                    int(day_counts[6] or 0)
                )
            
            # Calculer les places disponibles après réservations
            available_seats = max(0, row_dict['seats'] - max_passengers_per_day)
            
            logger.info(f"🪑 Offre {row_dict['id']}: {row_dict['seats']} places totales - {max_passengers_per_day} passagers max/jour = {available_seats} places disponibles")
            
            # 1) D'ABORD : vérifier s'il existe un point de rencontre à proximité (départ ou pickup existant)
            # Cela évite un détour supplémentaire si le passager peut rejoindre un point existant
            user_tuple = tuple(user_point)
            recommended_meeting_point = None
            search_radius_m = 2000.0  # 2km pour considérer qu'on peut rejoindre un point existant
            
            # Récupérer les pickups confirmés pour cette offre
            pickup_points = []
            try:
                with sql.db_cursor() as cur_inner2:
                    cur_inner2.execute(
                        """
                        SELECT meeting_point_coords, meeting_point_address
                        FROM carpool_reservations_recurrent
                        WHERE offer_id = %s AND status = 'confirmed'
                        """,
                        (row_dict['id'],)
                    )
                    for (mp_coords, mp_address) in cur_inner2.fetchall():
                        if mp_coords:
                            try:
                                coords = json.loads(mp_coords)
                                if isinstance(coords, (list, tuple)) and len(coords) == 2:
                                    pickup_points.append({'coords': tuple(coords), 'address': mp_address})
                            except Exception:
                                continue
            except Exception as e:
                logger.warning(f"⚠️ Erreur récupération pickups pour offre {row_dict['id']}: {e}")

            # Vérifier départ conducteur dans le rayon
            if dep_coords:
                try:
                    distance_to_dep = haversine_distance(tuple(dep_coords), user_tuple)
                    if distance_to_dep <= search_radius_m:
                        recommended_meeting_point = {'coords': tuple(dep_coords), 'address': row_dict['departure']}
                        logger.info(f"✅ Offre {row_dict['id']}: user dans rayon du départ (0 détour)")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur distance départ offre {row_dict['id']}: {e}")

            # Vérifier pickups existants dans le rayon
            if not recommended_meeting_point:
                for pp in pickup_points:
                    try:
                        if haversine_distance(pp['coords'], user_tuple) <= search_radius_m:
                            recommended_meeting_point = {'coords': pp['coords'], 'address': pp['address']}
                            logger.info(f"✅ Offre {row_dict['id']}: user dans rayon d'un pickup existant (0 détour)")
                            break
                    except Exception:
                        continue

            # Vérifier bureau dans le rayon (pour le retour)
            if not recommended_meeting_point and dest_coords:
                try:
                    if haversine_distance(tuple(dest_coords), user_tuple) <= search_radius_m:
                        recommended_meeting_point = {'coords': tuple(dest_coords), 'address': row_dict['destination']}
                        logger.info(f"✅ Offre {row_dict['id']}: user dans rayon du bureau (retour, 0 détour)")
                except Exception:
                    pass

            # Si un point de rencontre existe → compatible sans détour
            if recommended_meeting_point:
                is_compatible = True
                compatible_direction = 'outbound' if recommended_meeting_point['address'] != row_dict['destination'] else 'return'
                detour_time = 0.0
                logger.info(f"✅ Offre {row_dict['id']} compatible via point existant (détour=0)")
            else:
                # 2) SINON : calculer le détour pour un nouveau pickup
                # Si le buffer est déjà dépassé (< 0) des deux côtés, ignorer cette offre
                if remaining_buffer_outbound < 0 and remaining_buffer_return < 0:
                    logger.info(f"❌ Offre {row_dict['id']} ignorée: budget de détour épuisé")
                    continue
                
                is_compatible = False
                compatible_direction = None
                detour_time = None
                
                # Vérifier l'aller (domicile → bureau) avec le buffer RESTANT
                if remaining_buffer_outbound >= 0 and dep_coords and dest_coords:
                    try:
                        start = tuple(dep_coords)  # Départ conducteur
                        end = tuple(dest_coords)   # Arrivée (bureau)
                        
                        # Calculer le temps de détour via OSRM
                        logger.info(f"🔍 Calcul détour aller offre {row_dict['id']}: start={start}, via={user_tuple}, end={end}")
                        detour = calculate_detour_time_osrm(start, user_tuple, end)
                        
                        logger.info(f"📊 Résultat détour aller: {detour} min (buffer restant: {remaining_buffer_outbound:.1f} min)")
                        
                        if detour is not None and detour <= remaining_buffer_outbound:
                            is_compatible = True
                            compatible_direction = 'outbound'
                            detour_time = detour
                            logger.info(f"✅ Offre {row_dict['id']} compatible (aller): détour {detour:.1f} min ≤ buffer restant {remaining_buffer_outbound:.1f} min")
                        else:
                            logger.info(f"❌ Aller non compatible: détour={detour}, buffer restant={remaining_buffer_outbound:.1f}")
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur calcul détour aller pour offre {row_dict['id']}: {e}")
            
                # Vérifier le retour (bureau → domicile) si pas déjà compatible, avec le buffer RESTANT
                if not is_compatible and remaining_buffer_return >= 0 and dep_coords and dest_coords:
                    try:
                        start = tuple(dest_coords)  # Départ bureau
                        end = tuple(dep_coords)     # Arrivée domicile conducteur
                        
                        # Calculer le temps de détour via OSRM
                        logger.info(f"🔍 Calcul détour retour offre {row_dict['id']}: start={start}, via={user_tuple}, end={end}")
                        detour = calculate_detour_time_osrm(start, user_tuple, end)
                        
                        logger.info(f"📊 Résultat détour retour: {detour} min (buffer restant: {remaining_buffer_return:.1f} min)")
                        
                        if detour is not None and detour <= remaining_buffer_return:
                            is_compatible = True
                            compatible_direction = 'return'
                            detour_time = detour
                            logger.info(f"✅ Offre {row_dict['id']} compatible (retour): détour {detour:.1f} min ≤ buffer restant {remaining_buffer_return:.1f} min")
                        else:
                            logger.info(f"❌ Retour non compatible: détour={detour}, buffer restant={remaining_buffer_return:.1f}")
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur calcul détour retour pour offre {row_dict['id']}: {e}")
            
            # Ne garder que les offres compatibles
            if not is_compatible:
                logger.info(f"❌ Offre {row_dict['id']} ignorée: point utilisateur hors zone de détour")
                continue
            
            # Construire la liste des jours actifs
            active_days = []
            for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                if row_dict[day] == 1:
                    active_days.append(day)
            
            # Masquer les données sensibles
            masked_email = row_dict['driver_email'].split('@')[0][:3] + '***@' + row_dict['driver_email'].split('@')[1]
            masked_phone = row_dict['driver_phone'][:4] + '****' if row_dict['driver_phone'] else None
            
            # Calculer le budget restant pour affichage
            remaining_detour = remaining_buffer_outbound if compatible_direction == 'outbound' else remaining_buffer_return
            
            offers.append({
                'id': row_dict['id'],
                'driver_name': row_dict['driver_name'],
                'driver_email_masked': masked_email,
                'driver_phone_masked': masked_phone,
                'departure': row_dict['departure'],
                'destination': row_dict['destination'],
                'departure_coords': dep_coords,
                'destination_coords': dest_coords,
                'recurrent_time': str(row_dict['recurrent_time']) if row_dict['recurrent_time'] else None,
                'time_return': str(row_dict['time_return']) if row_dict.get('time_return') else None,
                'days': active_days,
                'seats': row_dict['seats'],
                'seats_available': available_seats,  # Places après déduction du max de passagers sur tous les jours
                'max_detour_time': row_dict['max_detour_time'],
                'remaining_detour_time': round(remaining_detour, 1),
                'route_outbound': route_outbound,
                'route_return': route_return,
                'created_at': row_dict['created_at'].strftime('%Y-%m-%d %H:%M:%S') if row_dict['created_at'] else None,
                'compatible_direction': compatible_direction,
                'detour_time_minutes': round(detour_time, 1) if detour_time is not None else None,
                'recommended_meeting_point': recommended_meeting_point  # Point existant à rejoindre (ou None si nouveau pickup)
            })
        
        return jsonify({
            'offers': offers,
            'count': len(offers)
        }), 200
        
    except Exception as e:
        logger.error(f"Error in search_recurrent_offers: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/offers/recurrent/count', methods=['GET'])
@limiter.limit("60 per minute")
def count_recurrent_offers():
    """Compter le nombre total d'offres récurrentes actives pour une entreprise"""
    if not V2_ENABLED:
        return jsonify({'error': 'API v2 non disponible'}), 503
    
    try:
        company_id = request.args.get('company_id', type=int)
        
        if not company_id:
            return jsonify({'error': 'company_id requis'}), 400
        
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as count
                FROM carpool_offers_recurrent
                WHERE company_id = %s 
                AND status = 'active'
            """, (company_id,))
            
            result = cur.fetchone()
            count = result['count'] if result else 0
        
        return jsonify({'count': count}), 200
        
    except Exception as e:
        logger.error(f"Error in count_recurrent_offers: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/sites/resolve', methods=['POST'])
@limiter.limit("60 per minute")
def resolve_company_sites():
    """
    Résout les sites d'une entreprise : crée les IDs auto pour les sites fournis
    Accepte une liste de sites avec {name, address} et retourne les mêmes avec leur ID
    """
    if not V2_ENABLED:
        return jsonify({'error': 'API v2 non disponible'}), 503
    
    try:
        data = request.get_json()
        company_id = data.get('company_id')
        sites_input = data.get('sites', [])  # [{name, address}, ...]
        
        if not company_id:
            return jsonify({'error': 'company_id requis'}), 400
        
        resolved_sites = []
        
        with sql.db_cursor() as cur:
            for site_input in sites_input:
                site_name = site_input.get('name', '').strip()
                site_address = site_input.get('address', '').strip()
                
                if not site_name or not site_address:
                    continue
                
                # Normaliser le nom pour la comparaison (minuscules, sans accents)
                import unicodedata
                normalized_name = unicodedata.normalize('NFKD', site_name.lower()).encode('ASCII', 'ignore').decode('ASCII')
                
                # Vérifier si le site existe déjà (recherche insensible à la casse)
                cur.execute("""
                    SELECT id, site_name, site_address, site_coords FROM company_sites
                    WHERE company_id = %s AND LOWER(site_name) = LOWER(%s)
                    LIMIT 1
                """, (company_id, site_name))
                
                existing = cur.fetchone()
                
                if existing:
                    site_id = existing[0]
                    # Utiliser le nom stocké en base (garde la casse originale)
                    stored_name = existing[1]
                    stored_address = existing[2]
                    site_coords = json.loads(existing[3]) if existing[3] else None
                    logger.info(f"Site existant: {stored_name} (ID={site_id})")
                    
                    # Mettre à jour l'adresse si elle a changé
                    if stored_address != site_address:
                        cur.execute("""
                            UPDATE company_sites 
                            SET site_address = %s
                            WHERE id = %s
                        """, (site_address, site_id))
                        logger.info(f"Adresse mise à jour pour site {stored_name}")
                    
                    resolved_sites.append({
                        'id': site_id,
                        'name': stored_name,  # Nom stocké en base
                        'address': site_address,  # Adresse mise à jour
                        'coords': site_coords
                    })
                else:
                    # Créer le site
                    cur.execute("""
                        INSERT INTO company_sites (company_id, site_name, site_address)
                        VALUES (%s, %s, %s)
                    """, (company_id, site_name, site_address))
                    
                    site_id = cur.lastrowid
                    site_coords = None
                    logger.info(f"Nouveau site créé: {site_name} (ID={site_id})")
                    
                    resolved_sites.append({
                        'id': site_id,
                        'name': site_name,
                        'address': site_address,
                        'coords': site_coords
                    })
        
        return jsonify({'sites': resolved_sites}), 200
        
    except Exception as e:
        logger.error(f"Error in resolve_company_sites: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/reservations/recurrent', methods=['POST'])
@limiter.limit("10 per minute")
def create_recurrent_reservation():
    """Créer une demande de réservation pour un covoiturage récurrent"""
    try:
        data = request.get_json()
        
        # Validation des données
        offer_id = data.get('offer_id')
        passenger_name = data.get('passenger_name', '').strip()
        passenger_email = data.get('passenger_email', '').strip()
        passenger_phone = data.get('passenger_phone', '').strip() or None
        days_requested = data.get('days_requested', [])
        pickup_coords = data.get('pickup_coords')  # [lon, lat]
        pickup_address = data.get('pickup_address', '').strip()
        
        if not offer_id:
            return jsonify({'error': 'offer_id requis'}), 400
        
        if not passenger_name:
            return jsonify({'error': 'Nom du passager requis'}), 400
        
        if not passenger_email or '@' not in passenger_email:
            return jsonify({'error': 'Email valide requis'}), 400
        
        if not pickup_coords or not isinstance(pickup_coords, list) or len(pickup_coords) != 2:
            return jsonify({'error': 'Coordonnées de prise en charge requises'}), 400
        
        if not days_requested or not isinstance(days_requested, list) or len(days_requested) == 0:
            return jsonify({'error': 'Au moins un jour doit être sélectionné'}), 400
        
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day in days_requested:
            if day not in valid_days:
                return jsonify({'error': f'Jour invalide: {day}'}), 400
        
        # Récupérer l'offre pour validation et pour l'email
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT id, company_id, driver_name, driver_email, driver_phone,
                       departure, destination, departure_coords, destination_coords, seats,
                       monday, tuesday, wednesday, thursday, friday, saturday, sunday,
                       route_outbound, route_return, recurrent_time, time_return,
                       max_detour_time, color_outbound, color_return
                FROM carpool_offers_recurrent
                WHERE id = %s AND status = 'active'
            """, (offer_id,))
            
            offer = cur.fetchone()
            
            if not offer:
                return jsonify({'error': 'Offre non trouvée ou inactive'}), 404
            
            offer_data = {
                'id': offer[0],
                'company_id': offer[1],
                'driver_name': offer[2],
                'driver_email': offer[3],
                'driver_phone': offer[4],
                'departure': offer[5],
                'destination': offer[6],
                'departure_coords': json.loads(offer[7]) if offer[7] else None,
                'destination_coords': json.loads(offer[8]) if offer[8] else None,
                'seats': offer[9],
                'days': {
                    'monday': bool(offer[10]),
                    'tuesday': bool(offer[11]),
                    'wednesday': bool(offer[12]),
                    'thursday': bool(offer[13]),
                    'friday': bool(offer[14]),
                    'saturday': bool(offer[15]),
                    'sunday': bool(offer[16])
                },
                'route_outbound': json.loads(offer[17]) if offer[17] else None,
                'route_return': json.loads(offer[18]) if offer[18] else None,
                'recurrent_time': offer[19],  # Heure d'arrivée au bureau
                'time_return': offer[20],  # Heure de départ du bureau
                'max_detour_time': offer[21] or 15,  # Temps de détour max en minutes
                'color_outbound': offer[22] or '#7c3aed',  # Couleur aller
                'color_return': offer[23] or '#f97316'  # Couleur retour
            }
            
            # Import nécessaire pour la conversion
            from datetime import datetime, timedelta
            
            # Convertir les timedelta en time pour compatibilité avec le template
            if isinstance(offer_data['recurrent_time'], timedelta):
                total_seconds = int(offer_data['recurrent_time'].total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                offer_data['recurrent_time'] = datetime.min.time().replace(hour=hours, minute=minutes)
            
            if isinstance(offer_data['time_return'], timedelta):
                total_seconds = int(offer_data['time_return'].total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                offer_data['time_return'] = datetime.min.time().replace(hour=hours, minute=minutes)
            
            # Vérifier que les jours demandés sont disponibles dans l'offre
            for day in days_requested:
                if not offer_data['days'][day]:
                    return jsonify({'error': f'Le jour {day} n\'est pas disponible pour cette offre'}), 400
            
            # Récupérer les passagers déjà confirmés pour cet offre (AVANT le calcul du détour)
            cur.execute("""
                SELECT passenger_name, meeting_point_address, meeting_point_coords,
                       detour_time_outbound, detour_time_return,
                       monday, tuesday, wednesday, thursday, friday, saturday, sunday,
                       pickup_time_outbound, dropoff_time_return,
                       computed_departure_time, computed_arrival_home_time
                FROM carpool_reservations_recurrent
                WHERE offer_id = %s AND status IN ('confirmed', 'pending')
                ORDER BY created_at ASC
            """, (offer_id,))
            existing_passengers = []
            for row in cur.fetchall():
                existing_passengers.append({
                    'passenger_name': row['passenger_name'],
                    'meeting_point_address': row['meeting_point_address'],
                    'meeting_point_coords': json.loads(row['meeting_point_coords']) if row['meeting_point_coords'] else None,
                    'detour_outbound': row['detour_time_outbound'] or 0,
                    'detour_return': row['detour_time_return'] or 0,
                    'days': {
                        'monday': row['monday'],
                        'tuesday': row['tuesday'],
                        'wednesday': row['wednesday'],
                        'thursday': row['thursday'],
                        'friday': row['friday'],
                        'saturday': row['saturday'],
                        'sunday': row['sunday']
                    },
                    'pickup_time_outbound': row['pickup_time_outbound'],
                    'dropoff_time_return': row['dropoff_time_return'],
                    'computed_departure_time': row['computed_departure_time'],
                    'computed_arrival_home_time': row['computed_arrival_home_time']
                })
            
            # Vérifier si ce pickup existe déjà pour les jours demandés
            # Normaliser l'adresse pour la comparaison
            pickup_addr_normalized = pickup_address.lower().strip()
            
            # Identifier les jours où ce pickup existe déjà
            days_with_existing_pickup = set()
            existing_pickup_data = None
            
            for passenger in existing_passengers:
                passenger_addr = passenger['meeting_point_address'].lower().strip()
                if passenger_addr == pickup_addr_normalized:
                    # Ce pickup existe déjà, noter les jours
                    for day in days_requested:
                        if passenger['days'].get(day, False):
                            days_with_existing_pickup.add(day)
                    # Garder les données du premier passager avec ce pickup
                    if existing_pickup_data is None:
                        existing_pickup_data = passenger
                    break
            
            # Jours nécessitant un recalcul = jours demandés - jours avec pickup existant
            days_needing_calculation = [day for day in days_requested if day not in days_with_existing_pickup]
            
            logger.info(f"📍 Pickup '{pickup_address}' - Jours existants: {days_with_existing_pickup}, Jours à calculer: {days_needing_calculation}")
            
            # Calculer le détour uniquement si nécessaire
            from temporal_buffer import calculate_detour_time_osrm
            
            detour_outbound = None
            detour_return = None
            pickup_time_outbound = None
            dropoff_time_return = None
            arrival_home_time = None
            
            if days_needing_calculation and offer_data['departure_coords'] and offer_data['destination_coords']:
                # Calculer le détour pour les nouveaux jours
                detour_outbound = calculate_detour_time_osrm(
                    offer_data['departure_coords'],
                    pickup_coords,
                    offer_data['destination_coords']
                )
                
                # Détour retour : destination → pickup passager → départ conducteur
                detour_return = calculate_detour_time_osrm(
                    offer_data['destination_coords'],
                    pickup_coords,
                    offer_data['departure_coords']
                )
                
                logger.info(f"📊 Détour calculé pour nouveaux jours - Aller: {detour_outbound} min, Retour: {detour_return} min")
            elif days_with_existing_pickup and existing_pickup_data:
                # Utiliser les données existantes
                detour_outbound = existing_pickup_data['detour_outbound']
                detour_return = existing_pickup_data['detour_return']
                pickup_time_outbound = existing_pickup_data['pickup_time_outbound']
                dropoff_time_return = existing_pickup_data['dropoff_time_return']
                arrival_home_time = existing_pickup_data['computed_arrival_home_time']
                logger.info(f"♻️ Réutilisation des données existantes - Pas de recalcul pour {days_with_existing_pickup}")
            
            # Calculer les horaires seulement si on a fait un nouveau calcul de détour
            if days_needing_calculation:
                # Calculer les horaires avec détour (même si détour = 0)
                if detour_outbound is not None and offer_data.get('recurrent_time'):
                    try:
                        import requests
                        # Temps pickup → bureau
                        osrm_url = f"https://router.project-osrm.org/route/v1/driving/{pickup_coords[0]},{pickup_coords[1]};{offer_data['destination_coords'][0]},{offer_data['destination_coords'][1]}?overview=false"
                        response = requests.get(osrm_url, timeout=5)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('routes'):
                                time_pickup_to_office = data['routes'][0]['duration'] / 60
                                arrival_office = datetime.combine(datetime.today(), offer_data['recurrent_time'])
                                pickup_datetime = arrival_office - timedelta(minutes=time_pickup_to_office)
                                pickup_time_outbound = pickup_datetime.time()
                                logger.info(f"✅ Heure de prise en charge (aller): {pickup_time_outbound}")
                            else:
                                logger.error(f"❌ Pas de route retournée par OSRM pour pickup: {osrm_url}")
                        else:
                            logger.error(f"❌ OSRM status {response.status_code} pour pickup")
                    except Exception as e:
                        logger.error(f"❌ Erreur calcul heure pickup: {e}", exc_info=True)
                
                if detour_return is not None and offer_data.get('time_return'):
                    try:
                        import requests
                        # Temps bureau → dropoff
                        osrm_url1 = f"https://router.project-osrm.org/route/v1/driving/{offer_data['destination_coords'][0]},{offer_data['destination_coords'][1]};{pickup_coords[0]},{pickup_coords[1]}?overview=false"
                        # Temps dropoff → home
                        osrm_url2 = f"https://router.project-osrm.org/route/v1/driving/{pickup_coords[0]},{pickup_coords[1]};{offer_data['departure_coords'][0]},{offer_data['departure_coords'][1]}?overview=false"
                        
                        response1 = requests.get(osrm_url1, timeout=5)
                        response2 = requests.get(osrm_url2, timeout=5)
                        
                        if response1.status_code == 200 and response2.status_code == 200:
                            data1 = response1.json()
                            data2 = response2.json()
                            if data1.get('routes') and data2.get('routes'):
                                time_office_to_dropoff = data1['routes'][0]['duration'] / 60
                                time_dropoff_to_home = data2['routes'][0]['duration'] / 60
                                
                                departure_office = datetime.combine(datetime.today(), offer_data['time_return'])
                                dropoff_datetime = departure_office + timedelta(minutes=time_office_to_dropoff)
                                dropoff_time_return = dropoff_datetime.time()
                                
                                arrival_datetime = dropoff_datetime + timedelta(minutes=time_dropoff_to_home)
                                arrival_home_time = arrival_datetime.time()
                                
                                logger.info(f"✅ Heure de dépôt (retour): {dropoff_time_return}, Arrivée: {arrival_home_time}")
                            else:
                                logger.error(f"❌ Pas de route retournée par OSRM pour dropoff")
                        else:
                            logger.error(f"❌ OSRM status {response1.status_code}/{response2.status_code} pour dropoff")
                    except Exception as e:
                        logger.error(f"❌ Erreur calcul heure dropoff: {e}", exc_info=True)
            
            # Pas besoin de générer des images statiques, on utilise des liens Google Maps
            
            # Générer un token de confirmation
            import secrets
            confirmation_token = secrets.token_urlsafe(32)
            
            # Convertir days_requested en colonnes booléennes
            days_dict = {day: False for day in valid_days}
            for day in days_requested:
                days_dict[day] = True
            
            # Créer la réservation en statut "pending"
            cur.execute("""
                INSERT INTO carpool_reservations_recurrent
                (offer_id, passenger_name, passenger_email, passenger_phone, passengers,
                 monday, tuesday, wednesday, thursday, friday, saturday, sunday,
                 meeting_point_coords, meeting_point_address,
                 detour_time_outbound, detour_time_return,
                 pickup_time_outbound, dropoff_time_return,
                 trip_type, status, confirmation_token)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                offer_id,
                passenger_name,
                passenger_email,
                passenger_phone,
                1,  # passengers (par défaut 1)
                days_dict['monday'],
                days_dict['tuesday'],
                days_dict['wednesday'],
                days_dict['thursday'],
                days_dict['friday'],
                days_dict['saturday'],
                days_dict['sunday'],
                json.dumps(pickup_coords),
                pickup_address,
                int(detour_outbound) if detour_outbound else None,
                int(detour_return) if detour_return else None,
                pickup_time_outbound,
                dropoff_time_return,
                'both',
                'pending',
                confirmation_token
            ))
            
            reservation_id = cur.lastrowid
            
            logger.info(f"✅ Réservation récurrente créée: ID={reservation_id}, passager={passenger_name}, offre={offer_id}")
        
        # Envoyer l'email au conducteur
        try:
            from emails import send_email
            from email_request_by_day import generate_request_email_by_day
            import requests
            
            # URL de base pour les actions
            base_url = request.host_url.rstrip('/')
            
            # Calculer la nouvelle heure de départ TOTALE (avec tous les détours)
            new_departure_time = None
            new_arrival_home_time = None
            
            # Calculer détour total (existants + nouveau)
            total_detour_outbound = detour_outbound  # Détour du nouveau passager
            total_detour_return = detour_return
            
            # Ajouter les détours des passagers existants
            for ep in existing_passengers:
                total_detour_outbound += ep.get('detour_time_outbound', 0) or 0
                total_detour_return += ep.get('detour_time_return', 0) or 0
            
            # Calculer le trajet direct
            if offer_data.get('departure_coords') and offer_data.get('destination_coords'):
                try:
                    departure_coords = offer_data['departure_coords']
                    destination_coords = offer_data['destination_coords']
                    
                    coord_str = f"{departure_coords[0]},{departure_coords[1]};{destination_coords[0]},{destination_coords[1]}"
                    osrm_url = f"https://router.project-osrm.org/route/v1/driving/{coord_str}?overview=false"
                    resp = requests.get(osrm_url, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get('routes'):
                            direct_duration_min = data['routes'][0]['duration'] / 60
                            
                            # Nouvelle heure de départ = heure arrivée bureau - trajet direct - détours totaux
                            arrival_time = offer_data['recurrent_time']
                            if isinstance(arrival_time, timedelta):
                                total_sec = int(arrival_time.total_seconds())
                                arrival_time = datetime.min.time().replace(hour=total_sec//3600, minute=(total_sec%3600)//60)
                            
                            arrival_dt = datetime.combine(datetime.today(), arrival_time)
                            new_departure_dt = arrival_dt - timedelta(minutes=direct_duration_min + total_detour_outbound)
                            new_departure_time = new_departure_dt.time()
                            
                            # Nouvelle heure d'arrivée domicile = heure départ bureau + trajet direct + détours totaux
                            departure_bureau_time = offer_data['time_return']
                            if isinstance(departure_bureau_time, timedelta):
                                total_sec = int(departure_bureau_time.total_seconds())
                                departure_bureau_time = datetime.min.time().replace(hour=total_sec//3600, minute=(total_sec%3600)//60)
                            
                            departure_bureau_dt = datetime.combine(datetime.today(), departure_bureau_time)
                            new_arrival_home_dt = departure_bureau_dt + timedelta(minutes=direct_duration_min + total_detour_return)
                            new_arrival_home_time = new_arrival_home_dt.time()
                            
                            logger.info(f"🕐 Heures finales calculées: Départ {new_departure_time}, Arrivée domicile {new_arrival_home_time} (détour total aller: {total_detour_outbound:.1f}min, retour: {total_detour_return:.1f}min)")
                except Exception as e:
                    logger.warning(f"Erreur calcul nouvelles heures: {e}")
            
            # Générer l'email détaillé par jour
            subject, html_body, text_body = generate_request_email_by_day(
                offer_data=offer_data,
                passenger_name=passenger_name,
                passenger_email=passenger_email,
                passenger_phone=passenger_phone,
                pickup_address=pickup_address,
                pickup_coords=pickup_coords,
                days_requested=days_requested,
                days_with_existing_pickup=days_with_existing_pickup,
                detour_outbound=total_detour_outbound,  # Détour TOTAL (existants + nouveau)
                detour_return=total_detour_return,
                pickup_time_outbound=pickup_time_outbound,
                dropoff_time_return=dropoff_time_return,
                existing_passengers=existing_passengers,
                arrival_home_time=new_arrival_home_time,  # Nouvelle heure arrivée domicile
                new_departure_time=new_departure_time,    # Nouvelle heure départ domicile
                reservation_id=reservation_id,
                confirmation_token=confirmation_token,
                base_url=base_url,
                email_type='request'
            )
            
            send_email(offer_data['driver_email'], subject, html_body, text_body)
            logger.info(f"📧 Email de demande envoyé à {offer_data['driver_email']}")
            
        except Exception as e:
            logger.error(f"⚠️ Erreur envoi email: {e}")
        
        # Envoyer un email de confirmation au passager
        try:
            from emails import send_email
            
            # Créer la liste des jours demandés en français
            day_names_fr = {
                'monday': 'Lundi',
                'tuesday': 'Mardi',
                'wednesday': 'Mercredi',
                'thursday': 'Jeudi',
                'friday': 'Vendredi',
                'saturday': 'Samedi',
                'sunday': 'Dimanche'
            }
            days_list = ', '.join([day_names_fr[day] for day in days_requested])
            
            subject_passenger = "🚗 Votre demande de covoiturage a bien été envoyée"
            
            html_body_passenger = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #7c3aed 0%, #f97316 100%); color: white; padding: 30px; text-align: center; border-radius: 12px 12px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">✅ Demande envoyée</h1>
                </div>
                
                <div style="background: #f8fafc; padding: 30px; border-radius: 0 0 12px 12px;">
                    <p style="font-size: 16px; color: #1e293b;">Bonjour <strong>{passenger_name}</strong>,</p>
                    
                    <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                        Votre demande de covoiturage a bien été envoyée à <strong>{offer_data['driver_name']}</strong>.
                    </p>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #7c3aed;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 13px;">📍 Trajet demandé</p>
                        <p style="margin: 0 0 5px 0; font-size: 15px; color: #1e293b;">
                            <strong>🏠 {offer_data['departure']}</strong>
                        </p>
                        <p style="margin: 0; font-size: 15px; color: #1e293b;">
                            <strong>🏢 {offer_data['destination']}</strong>
                        </p>
                    </div>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f97316;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 13px;">📅 Jours demandés</p>
                        <p style="margin: 0; font-size: 15px; color: #1e293b;">
                            <strong>{days_list}</strong>
                        </p>
                    </div>
                    
                    <div style="background: #dbeafe; border-left: 4px solid #3b82f6; padding: 16px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0; font-size: 14px; color: #1e40af; line-height: 1.6;">
                            ⏳ <strong>En attente de validation</strong><br>
                            Le conducteur va recevoir votre demande et vous recevrez un email dès qu'il aura pris une décision.
                        </p>
                    </div>
                    
                    <p style="font-size: 12px; color: #94a3b8; text-align: center; margin-top: 30px;">
                        Carette - Plateforme de covoiturage RSE
                    </p>
                </div>
            </div>
            """
            
            text_body_passenger = f"""
Demande de covoiturage envoyée

Bonjour {passenger_name},

Votre demande de covoiturage a bien été envoyée à {offer_data['driver_name']}.

Trajet :
🏠 {offer_data['departure']}
🏢 {offer_data['destination']}

Jours demandés : {days_list}

⏳ En attente de validation
Le conducteur va recevoir votre demande et vous recevrez un email dès qu'il aura pris une décision.

---
Carette - Plateforme de covoiturage RSE
            """
            
            send_email(passenger_email, subject_passenger, html_body_passenger, text_body_passenger)
            logger.info(f"📧 Email de confirmation envoyé à {passenger_email}")
            
        except Exception as e:
            logger.error(f"⚠️ Erreur envoi email confirmation passager: {e}")
        
        return jsonify({
            'success': True,
            'reservation_id': reservation_id,
            'confirmation_token': confirmation_token,
            'message': 'Demande envoyée au conducteur'
        }), 201
        
    except Exception as e:
        logger.error(f"Error in create_recurrent_reservation: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/reservations/recurrent/<int:reservation_id>/accept', methods=['GET'])
def accept_recurrent_reservation(reservation_id):
    """Accepter une demande de réservation récurrente (via lien email)"""
    try:
        token = request.args.get('token')
        
        if not token:
            return "Token manquant", 400
        
        with sql.db_cursor() as cur:
            # Récupérer la réservation avec toutes les données
            cur.execute("""
                SELECT r.id, r.offer_id, r.passenger_name, r.passenger_email, r.passenger_phone,
                       r.status, r.confirmation_token, r.meeting_point_address, r.meeting_point_coords,
                       r.detour_time_outbound, r.detour_time_return,
                       r.monday, r.tuesday, r.wednesday, r.thursday, r.friday, r.saturday, r.sunday
                FROM carpool_reservations_recurrent r
                WHERE r.id = %s
            """, (reservation_id,))
            
            reservation = cur.fetchone()
            
            if not reservation:
                return "Réservation non trouvée", 404
            
            if reservation['confirmation_token'] != token:
                return "Token invalide", 403
            
            if reservation['status'] != 'pending':
                return f"Réservation déjà {reservation['status']}", 400
            
            # Récupérer les données de l'offre
            cur.execute("""
                SELECT id, driver_name, driver_email, driver_phone,
                       departure, destination, departure_coords, destination_coords,
                       recurrent_time, time_return,
                       route_outbound, route_return, max_detour_time,
                       color_outbound, color_return,
                       monday, tuesday, wednesday, thursday, friday, saturday, sunday
                FROM carpool_offers_recurrent
                WHERE id = %s
            """, (reservation['offer_id'],))
            
            offer = cur.fetchone()
            
            if not offer:
                return "Offre non trouvée", 404
            
            # VALIDATION : Vérifier que le budget n'est pas dépassé avec cette acceptation
            max_detour_time = offer['max_detour_time'] or 25
            
            # Calculer le détour total si on accepte cette réservation
            cur.execute("""
                SELECT COALESCE(SUM(detour_time_outbound), 0) as total_out,
                       COALESCE(SUM(detour_time_return), 0) as total_ret
                FROM carpool_reservations_recurrent
                WHERE offer_id = %s AND status = 'confirmed'
            """, (reservation['offer_id'],))
            current_detours = cur.fetchone()
            current_out = float(current_detours['total_out'] or 0)
            current_ret = float(current_detours['total_ret'] or 0)
            
            new_detour_out = reservation['detour_time_outbound'] or 0
            new_detour_ret = reservation['detour_time_return'] or 0
            
            total_out_after = current_out + new_detour_out
            total_ret_after = current_ret + new_detour_ret
            
            # Si le budget est dépassé, refuser automatiquement
            if total_out_after > max_detour_time or total_ret_after > max_detour_time:
                cur.execute("""
                    UPDATE carpool_reservations_recurrent
                    SET status = 'rejected', confirmed_at = NOW()
                    WHERE id = %s
                """, (reservation_id,))
                
                logger.warning(f"⚠️ Réservation {reservation_id} refusée automatiquement: budget dépassé (aller: {total_out_after}/{max_detour_time}, retour: {total_ret_after}/{max_detour_time})")
                
                return f"""
                <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                    <div style="font-size: 64px; margin-bottom: 20px;">⚠️</div>
                    <h1 style="color: #f59e0b;">Budget de détour dépassé</h1>
                    <p style="font-size: 18px; color: #475569;">Cette demande ne peut plus être acceptée car le budget de détour du conducteur serait dépassé.</p>
                    <p style="font-size: 14px; color: #94a3b8;">Une autre demande a probablement été acceptée entre-temps.</p>
                </body></html>
                """, 409  # Conflict
            
            # Mettre à jour le statut
            cur.execute("""
                UPDATE carpool_reservations_recurrent
                SET status = 'confirmed', confirmed_at = NOW()
                WHERE id = %s
            """, (reservation_id,))
            
            logger.info(f"✅ Réservation {reservation_id} acceptée (budget: aller {total_out_after}/{max_detour_time}, retour {total_ret_after}/{max_detour_time})")
            
            # RECALCULER L'ITINÉRAIRE COMPLET avec TOUS les passagers confirmés (incluant celui-ci)
            import json
            from datetime import datetime, timedelta
            import requests
            
            # Récupérer TOUS les passagers confirmés (incluant celui qu'on vient d'accepter)
            # IMPORTANT : Trier par pickup_time_outbound pour ordre chronologique correct
            cur.execute("""
                SELECT id, meeting_point_coords, meeting_point_address, passenger_name, pickup_time_outbound
                FROM carpool_reservations_recurrent
                WHERE offer_id = %s AND status = 'confirmed'
                ORDER BY pickup_time_outbound ASC, id ASC
            """, (reservation[1],))
            
            all_confirmed_passengers = cur.fetchall()
            
            # Mettre à jour le pickup_order pour chaque passager selon l'ordre chronologique
            for index, passenger in enumerate(all_confirmed_passengers):
                cur.execute("""
                    UPDATE carpool_reservations_recurrent
                    SET pickup_order = %s
                    WHERE id = %s
                """, (index + 1, passenger[0]))  # passenger[0] = id
            
            logger.info(f"📋 {len(all_confirmed_passengers)} passager(s) triés par ordre chronologique")
            
            # Coordonnées de départ et destination
            departure_coords = json.loads(offer[6]) if offer[6] else None
            destination_coords = json.loads(offer[7]) if offer[7] else None
            
            # Horaires de base (SANS détour)
            base_recurrent_time = offer[8]   # Heure d'arrivée au bureau (recurrent_time)
            base_time_return = offer[9]      # Heure de départ du bureau (time_return)
            
            # Convertir en time si nécessaire (peut être timedelta, str ou déjà time)
            def ensure_time(value):
                if isinstance(value, timedelta):
                    total_seconds = int(value.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    return datetime.min.time().replace(hour=hours, minute=minutes)
                elif isinstance(value, str):
                    # Parser HH:MM
                    return datetime.strptime(value, '%H:%M').time()
                elif isinstance(value, datetime.time):
                    return value
                else:
                    return value
            
            base_recurrent_time = ensure_time(base_recurrent_time)
            base_time_return = ensure_time(base_time_return)
            
            # Calculer le trajet DIRECT domicile → bureau (sans passagers)
            base_duration_outbound = 0
            base_duration_return = 0
            
            if departure_coords and destination_coords:
                try:
                    osrm_url = f"https://router.project-osrm.org/route/v1/driving/{departure_coords[0]},{departure_coords[1]};{destination_coords[0]},{destination_coords[1]}?overview=false"
                    response = requests.get(osrm_url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('routes'):
                            base_duration_outbound = data['routes'][0]['duration'] / 60  # minutes
                            base_duration_return = base_duration_outbound  # même durée
                except Exception as e:
                    logger.warning(f"Erreur calcul trajet de base: {e}")
            
            # Calculer base_time_outbound (heure de départ domicile sans passagers)
            # = recurrent_time (heure arrivée bureau) - durée trajet de base
            base_time_outbound = (datetime.combine(datetime.today(), base_recurrent_time) - timedelta(minutes=base_duration_outbound)).time()
            
            # Construire l'itinéraire avec TOUS les passagers confirmés
            route_outbound = {'waypoints': [], 'duration': base_duration_outbound * 60}
            route_return = {'waypoints': [], 'duration': base_duration_return * 60}
            
            # Collecter toutes les coordonnées des passagers
            passenger_waypoints = []
            for passenger in all_confirmed_passengers:
                passenger_coords = json.loads(passenger[1]) if passenger[1] else None
                passenger_address = passenger[2]
                passenger_name = passenger[3]
                
                if passenger_coords:
                    passenger_waypoints.append({
                        'coords': passenger_coords,
                        'address': passenger_address,
                        'passenger_name': passenger_name
                    })
            
            # Calculer le trajet ALLER avec TOUS les passagers en une seule fois
            total_detour_outbound = 0
            total_detour_return = 0
            
            if passenger_waypoints and departure_coords and destination_coords:
                try:
                    # Construire l'URL OSRM avec tous les waypoints : domicile → pickup1 → pickup2 → ... → bureau
                    waypoint_coords = ';'.join([f"{wp['coords'][0]},{wp['coords'][1]}" for wp in passenger_waypoints])
                    osrm_url_aller = f"https://router.project-osrm.org/route/v1/driving/{departure_coords[0]},{departure_coords[1]};{waypoint_coords};{destination_coords[0]},{destination_coords[1]}?overview=full&geometries=geojson"
                    
                    response = requests.get(osrm_url_aller, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('routes'):
                            route_data = data['routes'][0]
                            duration_with_all = route_data['duration'] / 60
                            total_detour_outbound = duration_with_all - base_duration_outbound
                            route_outbound['duration'] = duration_with_all * 60
                            # Stocker la géométrie complète
                            route_outbound['geometry'] = route_data.get('geometry', {}).get('coordinates', [])
                            logger.info(f"📍 Trajet ALLER avec {len(passenger_waypoints)} passager(s): {duration_with_all:.1f}min (détour: +{total_detour_outbound:.1f}min)")
                except Exception as e:
                    logger.warning(f"Erreur calcul trajet aller complet: {e}")
                    # Fallback : utiliser la somme des détours individuels
                    total_detour_outbound = sum([wp.get('detour', 0) for wp in passenger_waypoints])
                
                try:
                    # Construire l'URL OSRM pour le RETOUR : bureau → dropoff1 → dropoff2 → ... → domicile
                    waypoint_coords = ';'.join([f"{wp['coords'][0]},{wp['coords'][1]}" for wp in passenger_waypoints])
                    osrm_url_retour = f"https://router.project-osrm.org/route/v1/driving/{destination_coords[0]},{destination_coords[1]};{waypoint_coords};{departure_coords[0]},{departure_coords[1]}?overview=full&geometries=geojson"
                    
                    response = requests.get(osrm_url_retour, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('routes'):
                            route_data = data['routes'][0]
                            duration_with_all = route_data['duration'] / 60
                            total_detour_return = duration_with_all - base_duration_return
                            route_return['duration'] = duration_with_all * 60
                            # Stocker la géométrie complète
                            route_return['geometry'] = route_data.get('geometry', {}).get('coordinates', [])
                            logger.info(f"📍 Trajet RETOUR avec {len(passenger_waypoints)} passager(s): {duration_with_all:.1f}min (détour: +{total_detour_return:.1f}min)")
                except Exception as e:
                    logger.warning(f"Erreur calcul trajet retour complet: {e}")
                    # Fallback : utiliser la somme des détours individuels
                    total_detour_return = sum([wp.get('detour', 0) for wp in passenger_waypoints])
            
            # Ajouter les waypoints à la route
            for wp in passenger_waypoints:
                route_outbound['waypoints'].append(wp)
                route_return['waypoints'].append(wp)
            
            # Mettre à jour les durées totales
            route_outbound['duration'] = (base_duration_outbound + total_detour_outbound) * 60
            route_return['duration'] = (base_duration_return + total_detour_return) * 60
            
            # NE PAS modifier recurrent_time et time_return dans la base - ce sont les horaires CONFIGURÉS
            # MAIS on calcule les heures de départ/arrivée domicile pour l'email
            # Départ domicile = heure configurée MOINS le détour (on part plus tôt)
            new_departure_from_home = (datetime.combine(datetime.today(), base_time_outbound) - timedelta(minutes=total_detour_outbound)).time()
            # Arrivée domicile = heure configurée PLUS le détour (on arrive plus tard)
            new_arrival_at_home = (datetime.combine(datetime.today(), base_time_return) + timedelta(minutes=base_duration_return + total_detour_return)).time()
            
            # Mettre à jour l'offre en base avec le nouvel itinéraire COMPLET (sans modifier les horaires configurés)
            cur.execute("""
                UPDATE carpool_offers_recurrent
                SET route_outbound = %s,
                    route_return = %s
                WHERE id = %s
            """, (
                json.dumps(route_outbound),
                json.dumps(route_return),
                reservation[1]  # offer_id
            ))
            
            logger.info(f"🔄 Offre {reservation[1]} mise à jour avec {len(all_confirmed_passengers)} passager(s) - Détour total aller: {total_detour_outbound:.1f}min, retour: {total_detour_return:.1f}min")
            
            # Envoyer email de confirmation au passager
            try:
                from emails import send_email
                
                subject = "✅ Votre demande de covoiturage a été acceptée !"
                
                html_body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; text-align: center; padding: 40px;">
                    <div style="font-size: 64px; margin-bottom: 20px;">✅</div>
                    <h1 style="color: #22c55e; margin-bottom: 20px;">Demande acceptée !</h1>
                    <p style="font-size: 16px; color: #475569;">
                        Bonne nouvelle ! Votre demande de covoiturage a été acceptée par {offer[1]}.
                    </p>
                </div>
                """
                
                send_email(reservation[3], subject, html_body, "✅ Votre demande de covoiturage a été acceptée !")
                
            except Exception as e:
                logger.error(f"⚠️ Erreur envoi email confirmation passager: {e}")
            
            # Envoyer email récapitulatif au conducteur avec l'état actualisé
            try:
                from emails import send_email
                import json
                from datetime import datetime, timedelta
                import requests
                
                # Récupérer TOUTES les réservations confirmées pour cette offre
                cur.execute("""
                    SELECT id, passenger_name, passenger_email, passenger_phone,
                           meeting_point_address, meeting_point_coords,
                           detour_time_outbound, detour_time_return,
                           monday, tuesday, wednesday, thursday, friday, saturday, sunday,
                           confirmation_token
                    FROM carpool_reservations_recurrent
                    WHERE offer_id = %s AND status = 'confirmed'
                """, (reservation[1],))
                
                confirmed_reservations = cur.fetchall()
                
                # Préparer les données de l'offre MISE À JOUR
                offer_data = {
                    'driver_name': offer[1],
                    'driver_email': offer[2],
                    'departure': offer[4],
                    'destination': offer[5],
                    'departure_coords': json.loads(offer[6]) if offer[6] else None,
                    'destination_coords': json.loads(offer[7]) if offer[7] else None,
                    'departure_time': new_departure_from_home,  # Départ plus tôt de chez soi
                    'arrival_time': base_recurrent_time,  # Arrivée au bureau (heure cible, reste fixe)
                    'return_departure_time': base_time_return,  # Départ du bureau (heure fixe)
                    'return_arrival_time': new_arrival_at_home,  # Arrivée chez soi (plus tard à cause du détour)
                    'color_outbound': offer[13] or '#7c3aed',
                    'color_return': offer[14] or '#f97316',
                    'monday': offer[15],
                    'tuesday': offer[16],
                    'wednesday': offer[17],
                    'thursday': offer[18],
                    'friday': offer[19],
                    'saturday': offer[20],
                    'sunday': offer[21]
                }
                
                # Préparer la liste des passagers pour le récap
                reservations_list = []
                for res in confirmed_reservations:
                    passenger_coords = json.loads(res[5]) if res[5] else None
                    
                    # Calculer heures de pickup/dropoff
                    pickup_time_outbound = None
                    dropoff_time_return = None
                    computed_departure_time = None
                    computed_arrival_home_time = None
                    
                    if passenger_coords and offer_data['departure_coords'] and offer_data['destination_coords']:
                        try:
                            # ALLER : Calculer EN ARRIÈRE depuis l'arrivée au bureau (comme dans le mail de demande)
                            # Temps pickup → bureau
                            osrm_url = f"https://router.project-osrm.org/route/v1/driving/{passenger_coords[0]},{passenger_coords[1]};{offer_data['destination_coords'][0]},{offer_data['destination_coords'][1]}?overview=false"
                            response = requests.get(osrm_url, timeout=5)
                            if response.status_code == 200:
                                data = response.json()
                                if data.get('routes'):
                                    time_pickup_to_office = data['routes'][0]['duration'] / 60
                                    arrival_office = datetime.combine(datetime.today(), offer_data['arrival_time'])  # Heure d'arrivée cible
                                    pickup_datetime = arrival_office - timedelta(minutes=time_pickup_to_office)
                                    pickup_time_outbound = pickup_datetime.time()
                                    
                                    # Calculer domicile → pickup pour obtenir l'heure de départ réelle
                                    osrm_home_pickup = f"https://router.project-osrm.org/route/v1/driving/{offer_data['departure_coords'][0]},{offer_data['departure_coords'][1]};{passenger_coords[0]},{passenger_coords[1]}?overview=false"
                                    resp_hp = requests.get(osrm_home_pickup, timeout=5)
                                    if resp_hp.status_code == 200:
                                        data_hp = resp_hp.json()
                                        if data_hp.get('routes'):
                                            home_to_pickup = data_hp['routes'][0]['duration'] / 60
                                            computed_departure_dt = pickup_datetime - timedelta(minutes=home_to_pickup)
                                            computed_departure_time = computed_departure_dt.time()
                        except Exception as e:
                            logger.warning(f"Erreur calcul pickup time: {e}")
                    
                    if passenger_coords and offer_data['departure_coords'] and offer_data['destination_coords']:
                        try:
                            # RETOUR : Calculer EN AVANT depuis le départ du bureau (comme dans le mail de demande)
                            # Temps bureau → dropoff
                            osrm_url1 = f"https://router.project-osrm.org/route/v1/driving/{offer_data['destination_coords'][0]},{offer_data['destination_coords'][1]};{passenger_coords[0]},{passenger_coords[1]}?overview=false"
                            response = requests.get(osrm_url1, timeout=5)
                            if response.status_code == 200:
                                data = response.json()
                                if data.get('routes'):
                                    time_office_to_dropoff = data['routes'][0]['duration'] / 60
                                    departure_office = datetime.combine(datetime.today(), offer_data['return_departure_time'])
                                    dropoff_datetime = departure_office + timedelta(minutes=time_office_to_dropoff)
                                    dropoff_time_return = dropoff_datetime.time()
                                    
                                    # Calculer dropoff → domicile pour obtenir l'heure d'arrivée réelle
                                    osrm_drop_home = f"https://router.project-osrm.org/route/v1/driving/{passenger_coords[0]},{passenger_coords[1]};{offer_data['departure_coords'][0]},{offer_data['departure_coords'][1]}?overview=false"
                                    resp_dh = requests.get(osrm_drop_home, timeout=5)
                                    if resp_dh.status_code == 200:
                                        data_dh = resp_dh.json()
                                        if data_dh.get('routes'):
                                            drop_to_home = data_dh['routes'][0]['duration'] / 60
                                            arrival_home_dt = dropoff_datetime + timedelta(minutes=drop_to_home)
                                            computed_arrival_home_time = arrival_home_dt.time()
                        except Exception as e:
                            logger.warning(f"Erreur calcul dropoff time: {e}")
                    
                    reservations_list.append({
                        'id': res[0],
                        'passenger_name': res[1],
                        'passenger_email': res[2],
                        'passenger_phone': res[3],
                        'meeting_point_address': res[4],
                        'pickup_time_outbound': pickup_time_outbound,
                        'dropoff_time_return': dropoff_time_return,
                        'computed_departure_time': computed_departure_time,
                        'computed_arrival_home_time': computed_arrival_home_time,
                        'confirmation_token': res[15],
                        'monday': res[8],
                        'tuesday': res[9],
                        'wednesday': res[10],
                        'thursday': res[11],
                        'friday': res[12],
                        'saturday': res[13],
                        'sunday': res[14]
                    })
                
                # Générer l'email récapitulatif
                from email_recap_covoiturage import generate_covoiturage_recap_email
                
                subject, html_body, text_body = generate_covoiturage_recap_email(
                    offer_data=offer_data,
                    reservations=reservations_list,
                    email_type='accepted'
                )
                
                send_email(offer_data['driver_email'], subject, html_body, text_body)
                logger.info(f"📧 Email récapitulatif envoyé au conducteur {offer_data['driver_email']}")
                
            except Exception as e:
                logger.error(f"⚠️ Erreur envoi email récapitulatif conducteur: {e}", exc_info=True)
        
        return """
        <html><body style="font-family: Arial; text-align: center; padding: 50px;">
            <div style="font-size: 64px; margin-bottom: 20px;">✅</div>
            <h1 style="color: #22c55e;">Demande acceptée !</h1>
            <p style="font-size: 18px; color: #475569;">La demande de covoiturage a été acceptée.</p>
        </body></html>
        """
        
    except Exception as e:
        logger.error(f"Error in accept_recurrent_reservation: {str(e)}", exc_info=True)
        return "Erreur serveur", 500


@app.route('/api/v2/reservations/recurrent/<int:reservation_id>/reject', methods=['GET'])
def reject_recurrent_reservation(reservation_id):
    """Refuser une demande de réservation récurrente (via lien email)"""
    try:
        token = request.args.get('token')
        
        if not token:
            return "Token manquant", 400
        
        with sql.db_cursor() as cur:
            # Récupérer la réservation avec toutes les données
            cur.execute("""
                SELECT r.id, r.offer_id, r.passenger_name, r.passenger_email, r.passenger_phone,
                       r.status, r.confirmation_token, r.meeting_point_address, r.meeting_point_coords,
                       r.detour_time_outbound, r.detour_time_return,
                       r.monday, r.tuesday, r.wednesday, r.thursday, r.friday, r.saturday, r.sunday
                FROM carpool_reservations_recurrent r
                WHERE r.id = %s
            """, (reservation_id,))
            
            reservation = cur.fetchone()
            
            if not reservation:
                return "Réservation non trouvée", 404
            
            if reservation[6] != token:
                return "Token invalide", 403
            
            if reservation[5] != 'pending':
                return f"Réservation déjà {reservation[5]}", 400
            
            # Récupérer les données de l'offre
            cur.execute("""
                SELECT id, driver_name, driver_email, driver_phone,
                       departure, destination, departure_coords, destination_coords,
                       recurrent_time, time_return,
                       route_outbound, route_return, max_detour_time,
                       color_outbound, color_return,
                       monday, tuesday, wednesday, thursday, friday, saturday, sunday
                FROM carpool_offers_recurrent
                WHERE id = %s
            """, (reservation[1],))
            
            offer = cur.fetchone()
            
            if not offer:
                return "Offre non trouvée", 404
            
            # Mettre à jour le statut
            cur.execute("""
                UPDATE carpool_reservations_recurrent
                SET status = 'rejected'
                WHERE id = %s
            """, (reservation_id,))
            
            logger.info(f"❌ Réservation {reservation_id} refusée")
            
            # Envoyer email simple au passager
            try:
                from emails import send_email
                
                subject = "Demande de covoiturage refusée"
                
                html_body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; text-align: center; padding: 40px;">
                    <div style="font-size: 64px; margin-bottom: 20px;">😔</div>
                    <h1 style="color: #ef4444; margin-bottom: 20px;">Demande refusée</h1>
                    <p style="font-size: 16px; color: #475569;">
                        Malheureusement, votre demande de covoiturage n'a pas été acceptée.
                    </p>
                </div>
                """
                
                send_email(reservation[3], subject, html_body, "Votre demande de covoiturage n'a pas été acceptée.")
                
            except Exception as e:
                logger.error(f"⚠️ Erreur envoi email refus passager: {e}")
            
            # Envoyer email détaillé au conducteur avec les détails
            try:
                from emails import send_email
                import json
                from datetime import datetime, timedelta
                
                # Reconstruire les données pour l'email
                offer_data = {
                    'driver_name': offer[1],
                    'driver_email': offer[2],
                    'departure': offer[4],
                    'destination': offer[5],
                    'departure_coords': json.loads(offer[6]) if offer[6] else None,
                    'destination_coords': json.loads(offer[7]) if offer[7] else None,
                    'recurrent_time': offer[8],
                    'time_return': offer[9],
                    'route_outbound': json.loads(offer[10]) if offer[10] else None,
                    'route_return': json.loads(offer[11]) if offer[11] else None,
                    'max_detour_time': offer[12] or 15,
                    'color_outbound': offer[13] or '#7c3aed',
                    'color_return': offer[14] or '#f97316',
                    'monday': offer[15],
                    'tuesday': offer[16],
                    'wednesday': offer[17],
                    'thursday': offer[18],
                    'friday': offer[19],
                    'saturday': offer[20],
                    'sunday': offer[21]
                }
                
                # Convertir les timedelta en time pour compatibilité avec le template
                if isinstance(offer_data['recurrent_time'], timedelta):
                    total_seconds = int(offer_data['recurrent_time'].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    offer_data['recurrent_time'] = datetime.min.time().replace(hour=hours, minute=minutes)
                
                if isinstance(offer_data['time_return'], timedelta):
                    total_seconds = int(offer_data['time_return'].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    offer_data['time_return'] = datetime.min.time().replace(hour=hours, minute=minutes)
                
                pickup_coords = json.loads(reservation[8]) if reservation[8] else None
                pickup_address = reservation[7]
                passenger_name = reservation[2]
                passenger_email = reservation[3]
                passenger_phone = reservation[4]
                detour_outbound = reservation[9]
                detour_return = reservation[10]
                
                # Jours demandés
                days_requested = []
                day_columns = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                for i, day in enumerate(day_columns):
                    if reservation[11 + i]:  # Index 11 à 17
                        days_requested.append(day)
                
                # Calculer les horaires de pickup/dropoff
                pickup_time_outbound = None
                dropoff_time_return = None
                arrival_home_time = None
                
                if pickup_coords and offer_data['destination_coords'] and offer_data['recurrent_time']:
                    try:
                        import requests
                        # Temps pickup → bureau
                        osrm_url = f"https://router.project-osrm.org/route/v1/driving/{pickup_coords[0]},{pickup_coords[1]};{offer_data['destination_coords'][0]},{offer_data['destination_coords'][1]}?overview=false"
                        response = requests.get(osrm_url, timeout=5)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('routes'):
                                time_pickup_to_office = data['routes'][0]['duration'] / 60
                                arrival_office = datetime.combine(datetime.today(), offer_data['recurrent_time'])
                                pickup_datetime = arrival_office - timedelta(minutes=time_pickup_to_office)
                                pickup_time_outbound = pickup_datetime.time()
                    except Exception as e:
                        logger.warning(f"Erreur calcul heure pickup: {e}")
                
                if pickup_coords and offer_data['departure_coords'] and offer_data['destination_coords'] and offer_data['time_return']:
                    try:
                        import requests
                        # Temps bureau → dropoff
                        osrm_url1 = f"https://router.project-osrm.org/route/v1/driving/{offer_data['destination_coords'][0]},{offer_data['destination_coords'][1]};{pickup_coords[0]},{pickup_coords[1]}?overview=false"
                        # Temps dropoff → home
                        osrm_url2 = f"https://router.project-osrm.org/route/v1/driving/{pickup_coords[0]},{pickup_coords[1]};{offer_data['departure_coords'][0]},{offer_data['departure_coords'][1]}?overview=false"
                        
                        response1 = requests.get(osrm_url1, timeout=5)
                        response2 = requests.get(osrm_url2, timeout=5)
                        
                        if response1.status_code == 200 and response2.status_code == 200:
                            data1 = response1.json()
                            data2 = response2.json()
                            if data1.get('routes') and data2.get('routes'):
                                time_office_to_dropoff = data1['routes'][0]['duration'] / 60
                                time_dropoff_to_home = data2['routes'][0]['duration'] / 60
                                
                                departure_office = datetime.combine(datetime.today(), offer_data['time_return'])
                                dropoff_datetime = departure_office + timedelta(minutes=time_office_to_dropoff)
                                dropoff_time_return = dropoff_datetime.time()
                                
                                arrival_datetime = dropoff_datetime + timedelta(minutes=time_dropoff_to_home)
                                arrival_home_time = arrival_datetime.time()
                    except Exception as e:
                        logger.warning(f"Erreur calcul heure dropoff: {e}")
                
                # Calculer la nouvelle heure de départ avec le détour
                new_departure_time = None
                if pickup_time_outbound and detour_outbound and offer_data.get('departure_coords'):
                    try:
                        departure_coords = offer_data['departure_coords']
                        today = datetime.now().date()
                        pickup_datetime = datetime.combine(today, pickup_time_outbound)
                        
                        coord_str = f"{departure_coords[0]},{departure_coords[1]};{pickup_coords[0]},{pickup_coords[1]}"
                        osrm_url = f"https://router.project-osrm.org/route/v1/driving/{coord_str}"
                        resp = requests.get(osrm_url, timeout=5)
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get('routes'):
                                home_to_pickup_duration = data['routes'][0]['duration'] / 60
                                new_departure_datetime = pickup_datetime - timedelta(minutes=home_to_pickup_duration)
                                new_departure_time = new_departure_datetime.time()
                    except Exception as e:
                        logger.warning(f"Erreur calcul nouveau départ: {e}")
                
                # Générer l'email détaillé pour le conducteur
                from email_request_by_day import generate_request_email_by_day
                
                subject, html_body, text_body = generate_request_email_by_day(
                    offer_data=offer_data,
                    passenger_name=passenger_name,
                    passenger_email=passenger_email,
                    passenger_phone=passenger_phone,
                    pickup_address=pickup_address,
                    pickup_coords=pickup_coords,
                    days_requested=days_requested,
                    detour_outbound=detour_outbound,
                    detour_return=detour_return,
                    pickup_time_outbound=pickup_time_outbound,
                    dropoff_time_return=dropoff_time_return,
                    arrival_home_time=arrival_home_time,
                    new_departure_time=new_departure_time,
                    reservation_id=None,  # Pas de boutons d'action
                    confirmation_token=None,
                    base_url=None,
                    email_type='rejected'  # Type d'email: refusé
                )
                
                send_email(offer_data['driver_email'], subject, html_body, text_body)
                logger.info(f"📧 Email de refus détaillé envoyé au conducteur {offer_data['driver_email']}")
                
            except Exception as e:
                logger.error(f"⚠️ Erreur envoi email refus conducteur: {e}", exc_info=True)
        
        return """
        <html><body style="font-family: Arial; text-align: center; padding: 50px;">
            <div style="font-size: 64px; margin-bottom: 20px;">✋</div>
            <h1 style="color: #ef4444;">Demande refusée</h1>
            <p style="font-size: 18px; color: #475569;">La demande de covoiturage a été refusée.</p>
        </body></html>
        """
        
    except Exception as e:
        logger.error(f"Error in reject_recurrent_reservation: {str(e)}", exc_info=True)
        return "Erreur serveur", 500


@app.route('/api/v2/reservations/recurrent/<int:reservation_id>/remove', methods=['GET'])
def remove_recurrent_passenger(reservation_id):
    """Retirer un passager confirmé (via lien email dans recap)"""
    try:
        token = request.args.get('token')
        
        if not token:
            return "Token manquant", 400
        
        with sql.db_cursor() as cur:
            # Récupérer la réservation
            cur.execute("""
                SELECT r.id, r.offer_id, r.passenger_name, r.passenger_email,
                       r.status, r.confirmation_token
                FROM carpool_reservations_recurrent r
                WHERE r.id = %s
            """, (reservation_id,))
            
            reservation = cur.fetchone()
            
            if not reservation:
                return "Réservation non trouvée", 404
            
            if reservation[5] != token:
                return "Token invalide", 403
            
            if reservation[4] != 'confirmed':
                return f"Cette réservation n'est pas confirmée (statut: {reservation[4]})", 400
            
            offer_id = reservation[1]
            passenger_name = reservation[2]
            passenger_email = reservation[3]
            
            # Marquer comme cancelled
            cur.execute("""
                UPDATE carpool_reservations_recurrent
                SET status = 'cancelled', confirmed_at = NOW()
                WHERE id = %s
            """, (reservation_id,))
            
            logger.info(f"🗑️ Passager {passenger_name} retiré de l'offre {offer_id}")
            
            # RECALCULER L'ITINÉRAIRE avec les passagers restants (exactement comme dans accept)
            import json
            from datetime import datetime, timedelta
            import requests
            
            # Récupérer les passagers RESTANTS confirmés
            cur.execute("""
                SELECT id, meeting_point_coords, meeting_point_address, passenger_name, pickup_time_outbound
                FROM carpool_reservations_recurrent
                WHERE offer_id = %s AND status = 'confirmed'
                ORDER BY pickup_time_outbound ASC, id ASC
            """, (offer_id,))
            
            remaining_passengers = cur.fetchall()
            
            # Mettre à jour le pickup_order pour les passagers restants
            for index, passenger in enumerate(remaining_passengers):
                cur.execute("""
                    UPDATE carpool_reservations_recurrent
                    SET pickup_order = %s
                    WHERE id = %s
                """, (index + 1, passenger[0]))
            
            logger.info(f"📋 {len(remaining_passengers)} passager(s) restant(s) après retrait")
            
            # Récupérer l'offre
            cur.execute("""
                SELECT id, driver_name, driver_email, driver_phone,
                       departure, destination, departure_coords, destination_coords,
                       recurrent_time, time_return,
                       route_outbound, route_return, max_detour_time,
                       color_outbound, color_return,
                       monday, tuesday, wednesday, thursday, friday, saturday, sunday
                FROM carpool_offers_recurrent
                WHERE id = %s
            """, (offer_id,))
            
            offer = cur.fetchone()
            
            if not offer:
                return "Offre non trouvée", 404
            
            # Recalculer les routes (même logique qu'accept_recurrent_reservation)
            departure_coords = json.loads(offer[6]) if offer[6] else None
            destination_coords = json.loads(offer[7]) if offer[7] else None
            
            base_recurrent_time = offer[8]
            base_time_return = offer[9]
            
            def ensure_time(value):
                if isinstance(value, timedelta):
                    total_seconds = int(value.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    return datetime.min.time().replace(hour=hours, minute=minutes)
                elif isinstance(value, str):
                    return datetime.strptime(value, '%H:%M').time()
                elif isinstance(value, datetime.time):
                    return value
                else:
                    return value
            
            base_recurrent_time = ensure_time(base_recurrent_time)
            base_time_return = ensure_time(base_time_return)
            
            # Calculer le trajet DIRECT
            base_duration_outbound = 0
            base_duration_return = 0
            
            if departure_coords and destination_coords:
                try:
                    osrm_url = f"https://router.project-osrm.org/route/v1/driving/{departure_coords[0]},{departure_coords[1]};{destination_coords[0]},{destination_coords[1]}?overview=false"
                    response = requests.get(osrm_url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('routes'):
                            base_duration_outbound = data['routes'][0]['duration'] / 60
                            base_duration_return = base_duration_outbound
                except Exception as e:
                    logger.warning(f"Erreur calcul trajet de base: {e}")
            
            base_time_outbound = (datetime.combine(datetime.today(), base_recurrent_time) - timedelta(minutes=base_duration_outbound)).time()
            
            route_outbound = {'waypoints': [], 'duration': base_duration_outbound * 60}
            route_return = {'waypoints': [], 'duration': base_duration_return * 60}
            
            # Collecter waypoints des passagers restants
            passenger_waypoints = []
            for passenger in remaining_passengers:
                passenger_coords = json.loads(passenger[1]) if passenger[1] else None
                if passenger_coords:
                    passenger_waypoints.append({
                        'coords': passenger_coords,
                        'address': passenger[2],
                        'passenger_name': passenger[3]
                    })
            
            total_detour_outbound = 0
            total_detour_return = 0
            
            if passenger_waypoints and departure_coords and destination_coords:
                try:
                    waypoint_coords = ';'.join([f"{wp['coords'][0]},{wp['coords'][1]}" for wp in passenger_waypoints])
                    osrm_url_aller = f"https://router.project-osrm.org/route/v1/driving/{departure_coords[0]},{departure_coords[1]};{waypoint_coords};{destination_coords[0]},{destination_coords[1]}?overview=full&geometries=geojson"
                    
                    response = requests.get(osrm_url_aller, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('routes'):
                            route_data = data['routes'][0]
                            duration_with_all = route_data['duration'] / 60
                            total_detour_outbound = duration_with_all - base_duration_outbound
                            route_outbound['duration'] = duration_with_all * 60
                            route_outbound['geometry'] = route_data.get('geometry', {}).get('coordinates', [])
                            logger.info(f"📍 Trajet ALLER avec {len(passenger_waypoints)} passager(s): {duration_with_all:.1f}min (détour: +{total_detour_outbound:.1f}min)")
                except Exception as e:
                    logger.warning(f"Erreur calcul trajet aller: {e}")
                
                try:
                    waypoint_coords = ';'.join([f"{wp['coords'][0]},{wp['coords'][1]}" for wp in passenger_waypoints])
                    osrm_url_retour = f"https://router.project-osrm.org/route/v1/driving/{destination_coords[0]},{destination_coords[1]};{waypoint_coords};{departure_coords[0]},{departure_coords[1]}?overview=full&geometries=geojson"
                    
                    response = requests.get(osrm_url_retour, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('routes'):
                            route_data = data['routes'][0]
                            duration_with_all = route_data['duration'] / 60
                            total_detour_return = duration_with_all - base_duration_return
                            route_return['duration'] = duration_with_all * 60
                            route_return['geometry'] = route_data.get('geometry', {}).get('coordinates', [])
                            logger.info(f"📍 Trajet RETOUR avec {len(passenger_waypoints)} passager(s): {duration_with_all:.1f}min (détour: +{total_detour_return:.1f}min)")
                except Exception as e:
                    logger.warning(f"Erreur calcul trajet retour: {e}")
            
            for wp in passenger_waypoints:
                route_outbound['waypoints'].append(wp)
                route_return['waypoints'].append(wp)
            
            route_outbound['duration'] = (base_duration_outbound + total_detour_outbound) * 60
            route_return['duration'] = (base_duration_return + total_detour_return) * 60
            
            new_departure_from_home = (datetime.combine(datetime.today(), base_time_outbound) - timedelta(minutes=total_detour_outbound)).time()
            new_arrival_at_home = (datetime.combine(datetime.today(), base_time_return) + timedelta(minutes=base_duration_return + total_detour_return)).time()
            
            # Mettre à jour l'offre
            cur.execute("""
                UPDATE carpool_offers_recurrent
                SET route_outbound = %s,
                    route_return = %s
                WHERE id = %s
            """, (
                json.dumps(route_outbound),
                json.dumps(route_return),
                offer_id
            ))
            
            logger.info(f"🔄 Offre {offer_id} mise à jour après retrait - Détour total aller: {total_detour_outbound:.1f}min, retour: {total_detour_return:.1f}min")
            
            # Envoyer email au passager retiré
            try:
                from emails import send_email
                
                subject = "Vous avez été retiré du covoiturage"
                
                html_body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; text-align: center; padding: 40px;">
                    <div style="font-size: 64px; margin-bottom: 20px;">👋</div>
                    <h1 style="color: #f59e0b; margin-bottom: 20px;">Retrait du covoiturage</h1>
                    <p style="font-size: 16px; color: #475569;">
                        Le conducteur {offer[1]} vous a retiré de son covoiturage.
                    </p>
                    <p style="font-size: 14px; color: #94a3b8;">
                        Trajet : {offer[4]} → {offer[5]}
                    </p>
                </div>
                """
                
                send_email(passenger_email, subject, html_body, "Vous avez été retiré du covoiturage.")
                
            except Exception as e:
                logger.error(f"⚠️ Erreur envoi email passager retiré: {e}")
            
            # Envoyer email récap ACTUALISÉ au conducteur
            try:
                from emails import send_email
                from email_recap_covoiturage import generate_covoiturage_recap_email
                
                # Récupérer toutes les réservations confirmées restantes
                cur.execute("""
                    SELECT id, passenger_name, passenger_email, passenger_phone,
                           meeting_point_address, meeting_point_coords,
                           detour_time_outbound, detour_time_return,
                           monday, tuesday, wednesday, thursday, friday, saturday, sunday,
                           pickup_time_outbound, dropoff_time_return,
                           computed_departure_time, computed_arrival_home_time,
                           confirmation_token
                    FROM carpool_reservations_recurrent
                    WHERE offer_id = %s AND status = 'confirmed'
                """, (offer_id,))
                
                confirmed_reservations = cur.fetchall()
                
                # Préparer les données de l'offre
                offer_data = {
                    'driver_name': offer[1],
                    'driver_email': offer[2],
                    'departure': offer[4],
                    'destination': offer[5],
                    'departure_coords': departure_coords,
                    'destination_coords': destination_coords,
                    'departure_time': new_departure_from_home,
                    'arrival_time': base_recurrent_time,
                    'return_departure_time': base_time_return,
                    'return_arrival_time': new_arrival_at_home,
                    'color_outbound': offer[13] or '#7c3aed',
                    'color_return': offer[14] or '#f97316',
                    'monday': offer[15],
                    'tuesday': offer[16],
                    'wednesday': offer[17],
                    'thursday': offer[18],
                    'friday': offer[19],
                    'saturday': offer[20],
                    'sunday': offer[21]
                }
                
                # Convertir les réservations en dict
                reservations_list = []
                for r in confirmed_reservations:
                    # Convertir pickup_time et dropoff_time de timedelta à time si nécessaire
                    pickup_time = r[15]
                    dropoff_time = r[16]
                    
                    if pickup_time and isinstance(pickup_time, timedelta):
                        total_seconds = int(pickup_time.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        pickup_time = datetime.min.time().replace(hour=hours, minute=minutes)
                    
                    if dropoff_time and isinstance(dropoff_time, timedelta):
                        total_seconds = int(dropoff_time.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        dropoff_time = datetime.min.time().replace(hour=hours, minute=minutes)
                    
                    reservations_list.append({
                        'id': r[0],
                        'passenger_name': r[1],
                        'passenger_email': r[2],
                        'passenger_phone': r[3],
                        'meeting_point_address': r[4],
                        'meeting_point_coords': r[5],
                        'detour_time_outbound': r[6],
                        'detour_time_return': r[7],
                        'monday': r[8],
                        'tuesday': r[9],
                        'wednesday': r[10],
                        'thursday': r[11],
                        'friday': r[12],
                        'saturday': r[13],
                        'sunday': r[14],
                        'pickup_time_outbound': pickup_time,
                        'dropoff_time_return': dropoff_time,
                        'computed_departure_time': r[17],
                        'computed_arrival_home_time': r[18],
                        'confirmation_token': r[19]
                    })
                
                BASE_URL = os.getenv('CARETTE_BASE_URL', 'http://localhost:9000')
                
                subject, html_body, text_body = generate_covoiturage_recap_email(
                    offer_data=offer_data,
                    reservations=reservations_list,
                    email_type='updated',
                    base_url=BASE_URL
                )
                
                send_email(offer_data['driver_email'], subject, html_body, text_body)
                logger.info(f"📧 Email récap ACTUALISÉ envoyé au conducteur après retrait de {passenger_name}")
                
            except Exception as e:
                logger.error(f"⚠️ Erreur envoi email récap actualisé: {e}", exc_info=True)
        
        return f"""
        <html><body style="font-family: Arial; text-align: center; padding: 50px;">
            <div style="font-size: 64px; margin-bottom: 20px;">✅</div>
            <h1 style="color: #22c55e;">Passager retiré</h1>
            <p style="font-size: 18px; color: #475569;">{passenger_name} a été retiré du covoiturage.</p>
            <p style="font-size: 14px; color: #94a3b8;">Un email récapitulatif actualisé vous a été envoyé.</p>
        </body></html>
        """
        
    except Exception as e:
        logger.error(f"Error in remove_recurrent_passenger: {str(e)}", exc_info=True)
        return "Erreur serveur", 500


# ================================
# API PONCTUEL - Réservations
# ================================

@app.route('/api/v2/reservations/ponctual', methods=['POST'])
@limiter.limit("10 per minute")
def create_ponctual_reservation():
    """Créer une demande de réservation pour un covoiturage ponctuel"""
    try:
        data = request.get_json()
        
        # Validation des données
        offer_id = data.get('offer_id')
        passenger_name = data.get('passenger_name', '').strip()
        passenger_email = data.get('passenger_email', '').strip()
        passenger_phone = data.get('passenger_phone', '').strip() or None
        date_requested = data.get('date')  # Format YYYY-MM-DD
        pickup_coords = data.get('pickup_coords')  # [lon, lat]
        pickup_address = data.get('pickup_address', '').strip()
        
        if not offer_id:
            return jsonify({'error': 'offer_id requis'}), 400
        
        if not passenger_name:
            return jsonify({'error': 'Nom du passager requis'}), 400
        
        if not passenger_email or '@' not in passenger_email:
            return jsonify({'error': 'Email valide requis'}), 400
        
        if not date_requested:
            return jsonify({'error': 'Date requise'}), 400
        
        # Valider le format de date
        from datetime import datetime
        try:
            date_obj = datetime.strptime(date_requested, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Format de date invalide (YYYY-MM-DD requis)'}), 400
        
        if not pickup_coords or not isinstance(pickup_coords, list) or len(pickup_coords) != 2:
            return jsonify({'error': 'Coordonnées de prise en charge requises'}), 400
        
        # Récupérer l'offre pour validation
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT id, company_id, driver_name, driver_email, driver_phone,
                       departure, destination, departure_coords, destination_coords, 
                       seats_available, event_date, event_time, max_detour_time
                FROM carpool_offers
                WHERE id = %s
            """, (offer_id,))
            
            offer = cur.fetchone()
            
            if not offer:
                return jsonify({'error': 'Offre non trouvée ou inactive'}), 404
            
            offer_data = {
                'id': offer[0],
                'company_id': offer[1],
                'driver_name': offer[2],
                'driver_email': offer[3],
                'driver_phone': offer[4],
                'departure': offer[5],
                'destination': offer[6],
                'departure_coords': json.loads(offer[7]) if offer[7] else None,
                'destination_coords': json.loads(offer[8]) if offer[8] else None,
                'seats_available': offer[9],
                'event_date': offer[10],
                'event_time': offer[11],
                'max_detour_time': offer[12] or 15
            }
            
            # Vérifier les places disponibles pour cette date
            cur.execute("""
                SELECT COUNT(*) as count FROM carpool_reservations_ponctual
                WHERE offer_id = %s AND date = %s AND status IN ('confirmed', 'pending')
            """, (offer_id, date_requested))
            
            current_reservations = cur.fetchone()['count']
            logger.info(f"🔍 Places: seats_available={offer_data['seats_available']}, current_reservations={current_reservations}")
            
            # Si seats_available est NULL, utiliser une valeur par défaut (par ex. 4 places)
            available_seats = offer_data['seats_available'] if offer_data['seats_available'] is not None else 4
            
            if current_reservations >= available_seats:
                return jsonify({'error': 'Plus de places disponibles pour cette date'}), 400
            
            # Générer un token de confirmation unique
            import secrets
            confirmation_token = secrets.token_urlsafe(32)
            
            # Créer la réservation en attente
            cur.execute("""
                INSERT INTO carpool_reservations_ponctual 
                (offer_id, passenger_name, passenger_email, passenger_phone, date,
                 meeting_point_coords, meeting_point_address, confirmation_token, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            """, (
                offer_id,
                passenger_name,
                passenger_email,
                passenger_phone,
                date_requested,
                json.dumps(pickup_coords),
                pickup_address,
                confirmation_token
            ))
            
            reservation_id = cur.lastrowid
            
        logger.info(f"✅ Réservation ponctuelle créée: ID {reservation_id} pour l'offre {offer_id}, date {date_requested}")
        
        # Envoyer l'email de demande au conducteur
        try:
            from emails import send_email
            import os
            
            base_url = os.getenv('CARETTE_BASE_URL', 'http://localhost:9000')
            
            # Formater la date en français
            months_fr = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 
                        'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
            days_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
            
            day_name = days_fr[date_obj.weekday()]
            date_formatted = f"{day_name} {date_obj.day} {months_fr[date_obj.month - 1]} {date_obj.year}"
            
            subject = f"🚗 Nouvelle demande de covoiturage pour le {date_formatted}"
            
            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #7c3aed 0%, #f97316 100%); color: white; padding: 30px; text-align: center; border-radius: 12px 12px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">📬 Nouvelle demande</h1>
                </div>
                
                <div style="background: #f8fafc; padding: 30px; border-radius: 0 0 12px 12px;">
                    <p style="font-size: 16px; color: #1e293b;">Bonjour <strong>{offer_data['driver_name']}</strong>,</p>
                    
                    <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                        <strong>{passenger_name}</strong> souhaite rejoindre votre covoiturage.
                    </p>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #7c3aed;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 13px;">📅 Date</p>
                        <p style="margin: 0; font-size: 18px; color: #1e293b;">
                            <strong>{date_formatted}</strong>
                        </p>
                    </div>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f97316;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 13px;">👤 Passager</p>
                        <p style="margin: 0 0 5px 0; font-size: 15px; color: #1e293b;">
                            <strong>{passenger_name}</strong>
                        </p>
                        <p style="margin: 0; font-size: 14px; color: #64748b;">
                            📧 {passenger_email}
                            {f"<br>📱 {passenger_phone}" if passenger_phone else ""}
                        </p>
                    </div>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #3b82f6;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 13px;">📍 Point de prise en charge</p>
                        <p style="margin: 0; font-size: 14px; color: #1e293b;">
                            {pickup_address}
                        </p>
                    </div>
                    
                    <div style="margin: 30px 0; text-align: center;">
                        <a href="{base_url}/api/v2/reservations/ponctual/{reservation_id}/accept?token={confirmation_token}" 
                           style="display: inline-block; background: #22c55e; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 0 10px; font-size: 16px;">
                            ✅ Accepter
                        </a>
                        <a href="{base_url}/api/v2/reservations/ponctual/{reservation_id}/reject?token={confirmation_token}" 
                           style="display: inline-block; background: #ef4444; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; margin: 0 10px; font-size: 16px;">
                            ❌ Refuser
                        </a>
                    </div>
                    
                    {f'''<div style="margin: 20px 0; text-align: center;">
                        <a href="https://wa.me/{passenger_phone.replace(" ", "").replace("+", "")}?text=Bonjour%20{passenger_name}%20!%20Je%20suis%20{offer_data["driver_name"]},%20votre%20conducteur%20pour%20le%20covoiturage%20du%20{date_formatted}." 
                           style="display: inline-block; background: #25D366; color: white; padding: 12px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 15px;">
                            💬 Contacter {passenger_name} sur WhatsApp
                        </a>
                    </div>''' if passenger_phone else ''}
                    
                    <p style="font-size: 12px; color: #94a3b8; text-align: center; margin-top: 30px;">
                        Carette - Plateforme de covoiturage RSE
                    </p>
                </div>
            </div>
            """
            
            text_body = f"""
Nouvelle demande de covoiturage

Bonjour {offer_data['driver_name']},

{passenger_name} souhaite rejoindre votre covoiturage.

📅 Date : {date_formatted}

👤 Passager :
{passenger_name}
📧 {passenger_email}
{"📱 " + passenger_phone if passenger_phone else ""}

📍 Point de prise en charge :
{pickup_address}

Pour accepter : {base_url}/api/v2/reservations/ponctual/{reservation_id}/accept?token={confirmation_token}
Pour refuser : {base_url}/api/v2/reservations/ponctual/{reservation_id}/reject?token={confirmation_token}

---
Carette - Plateforme de covoiturage RSE
            """
            
            send_email(offer_data['driver_email'], subject, html_body, text_body)
            logger.info(f"📧 Email de demande ponctuelle envoyé à {offer_data['driver_email']}")
            
        except Exception as e:
            logger.error(f"⚠️ Erreur envoi email: {e}")
        
        # Envoyer un email de confirmation au passager
        try:
            from emails import send_email
            
            subject_passenger = "🚗 Votre demande de covoiturage a bien été envoyée"
            
            html_body_passenger = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #7c3aed 0%, #f97316 100%); color: white; padding: 30px; text-align: center; border-radius: 12px 12px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">✅ Demande envoyée</h1>
                </div>
                
                <div style="background: #f8fafc; padding: 30px; border-radius: 0 0 12px 12px;">
                    <p style="font-size: 16px; color: #1e293b;">Bonjour <strong>{passenger_name}</strong>,</p>
                    
                    <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                        Votre demande de covoiturage a bien été envoyée à <strong>{offer_data['driver_name']}</strong>.
                    </p>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #7c3aed;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 13px;">📅 Date</p>
                        <p style="margin: 0; font-size: 18px; color: #1e293b;">
                            <strong>{date_formatted}</strong>
                        </p>
                    </div>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f97316;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 13px;">📍 Trajet</p>
                        <p style="margin: 0 0 5px 0; font-size: 15px; color: #1e293b;">
                            <strong>🏠 {offer_data['departure']}</strong>
                        </p>
                        <p style="margin: 0; font-size: 15px; color: #1e293b;">
                            <strong>🏢 {offer_data['destination']}</strong>
                        </p>
                    </div>
                    
                    <div style="background: #dbeafe; border-left: 4px solid #3b82f6; padding: 16px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0; font-size: 14px; color: #1e40af; line-height: 1.6;">
                            ⏳ <strong>En attente de validation</strong><br>
                            Le conducteur va recevoir votre demande et vous recevrez un email dès qu'il aura pris une décision.
                        </p>
                    </div>
                    
                    <p style="font-size: 12px; color: #94a3b8; text-align: center; margin-top: 30px;">
                        Carette - Plateforme de covoiturage RSE
                    </p>
                </div>
            </div>
            """
            
            text_body_passenger = f"""
Demande de covoiturage envoyée

Bonjour {passenger_name},

Votre demande de covoiturage a bien été envoyée à {offer_data['driver_name']}.

📅 Date : {date_formatted}

📍 Trajet :
🏠 {offer_data['departure']}
🏢 {offer_data['destination']}

⏳ En attente de validation
Le conducteur va recevoir votre demande et vous recevrez un email dès qu'il aura pris une décision.

---
Carette - Plateforme de covoiturage RSE
            """
            
            send_email(passenger_email, subject_passenger, html_body_passenger, text_body_passenger)
            logger.info(f"📧 Email de confirmation envoyé à {passenger_email}")
            
        except Exception as e:
            logger.error(f"⚠️ Erreur envoi email confirmation passager: {e}")
        
        return jsonify({
            'success': True,
            'reservation_id': reservation_id,
            'confirmation_token': confirmation_token,
            'message': 'Demande envoyée au conducteur'
        }), 201
        
    except Exception as e:
        logger.error(f"Error in create_ponctual_reservation: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/reservations/ponctual/<int:reservation_id>/accept', methods=['GET'])
def accept_ponctual_reservation(reservation_id):
    """Accepter une demande de réservation ponctuelle"""
    try:
        # Vérifier le token de sécurité
        token = request.args.get('token')
        if not token:
            return "Token manquant", 400
        
        with sql.db_cursor() as cur:
            # Récupérer la réservation avec le token
            cur.execute("""
                SELECT r.id, r.offer_id, r.passenger_name, r.passenger_email, r.date,
                       r.meeting_point_address, r.confirmation_token, r.status,
                       o.driver_name, o.driver_email, o.driver_phone,
                       o.departure, o.destination
                FROM carpool_reservations_ponctual r
                JOIN carpool_offers o ON r.offer_id = o.id
                WHERE r.id = %s
            """, (reservation_id,))
            
            reservation = cur.fetchone()
            
            if not reservation:
                return "Réservation non trouvée", 404
            
            res_id, offer_id, passenger_name, passenger_email, date_requested, \
                pickup_address, confirmation_token_db, status, \
                driver_name, driver_email, driver_phone, departure, destination = reservation
            
            # Vérifier le token
            if confirmation_token_db != token:
                return "Token invalide", 403
            
            # Vérifier que la réservation est encore en attente
            if status != 'pending':
                return f"Cette réservation a déjà été {status}.", 400
            
            # Mettre à jour le statut
            cur.execute("""
                UPDATE carpool_reservations_ponctual
                SET status = 'confirmed', confirmed_at = NOW()
                WHERE id = %s
            """, (reservation_id,))
            
            sql.db.commit()
        
        logger.info(f"✅ Réservation ponctuelle {reservation_id} acceptée")
        
        # Envoyer un email de confirmation au passager
        try:
            from emails import send_email
            from datetime import datetime
            
            # Formater la date
            date_obj = datetime.strptime(str(date_requested), '%Y-%m-%d').date()
            months_fr = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 
                        'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
            days_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
            
            day_name = days_fr[date_obj.weekday()]
            date_formatted = f"{day_name} {date_obj.day} {months_fr[date_obj.month - 1]} {date_obj.year}"
            
            subject = f"✅ Votre covoiturage du {date_formatted} est confirmé !"
            
            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #22c55e 0%, #10b981 100%); color: white; padding: 30px; text-align: center; border-radius: 12px 12px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">🎉 Covoiturage confirmé !</h1>
                </div>
                
                <div style="background: #f8fafc; padding: 30px; border-radius: 0 0 12px 12px;">
                    <p style="font-size: 16px; color: #1e293b;">Bonjour <strong>{passenger_name}</strong>,</p>
                    
                    <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                        Excellente nouvelle ! <strong>{driver_name}</strong> a accepté votre demande de covoiturage.
                    </p>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #22c55e;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 13px;">📅 Date</p>
                        <p style="margin: 0; font-size: 18px; color: #1e293b;">
                            <strong>{date_formatted}</strong>
                        </p>
                    </div>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #7c3aed;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 13px;">📍 Trajet</p>
                        <p style="margin: 0 0 5px 0; font-size: 15px; color: #1e293b;">
                            <strong>🏠 {departure}</strong>
                        </p>
                        <p style="margin: 0; font-size: 15px; color: #1e293b;">
                            <strong>🏢 {destination}</strong>
                        </p>
                    </div>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f97316;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 13px;">📍 Point de rencontre</p>
                        <p style="margin: 0; font-size: 14px; color: #1e293b;">
                            {pickup_address}
                        </p>
                    </div>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #3b82f6;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 13px;">🚗 Conducteur</p>
                        <p style="margin: 0 0 5px 0; font-size: 15px; color: #1e293b;">
                            <strong>{driver_name}</strong>
                        </p>
                        <p style="margin: 0; font-size: 14px; color: #64748b;">
                            📧 {driver_email}
                            {f"<br>📱 {driver_phone}" if driver_phone else ""}
                        </p>
                    </div>
                    
                    {f'''<div style="margin: 20px 0; text-align: center;">
                        <a href="https://wa.me/{driver_phone.replace(" ", "").replace("+", "")}?text=Bonjour%20{driver_name}%20!%20C%27est%20{passenger_name},%20votre%20passager%20pour%20le%20covoiturage%20du%20{date_formatted}.%20%F0%9F%9A%97" 
                           style="display: inline-block; background: #25D366; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px;">
                            💬 Contacter {driver_name} sur WhatsApp
                        </a>
                    </div>''' if driver_phone else ''}
                    
                    <div style="background: #dcfce7; border-left: 4px solid #22c55e; padding: 16px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0; font-size: 14px; color: #166534; line-height: 1.6;">
                            💡 <strong>Conseil</strong><br>
                            N'hésitez pas à contacter {driver_name} pour coordonner votre rendez-vous.
                        </p>
                    </div>
                    
                    <p style="font-size: 12px; color: #94a3b8; text-align: center; margin-top: 30px;">
                        Carette - Plateforme de covoiturage RSE
                    </p>
                </div>
            </div>
            """
            
            text_body = f"""
🎉 Covoiturage confirmé !

Bonjour {passenger_name},

Excellente nouvelle ! {driver_name} a accepté votre demande de covoiturage.

📅 Date : {date_formatted}

📍 Trajet :
🏠 {departure}
🏢 {destination}

📍 Point de rencontre :
{pickup_address}

🚗 Conducteur :
{driver_name}
📧 {driver_email}

💡 N'hésitez pas à contacter {driver_name} par email pour coordonner votre rendez-vous.

---
Carette - Plateforme de covoiturage RSE
            """
            
            send_email(passenger_email, subject, html_body, text_body)
            logger.info(f"📧 Email de confirmation envoyé à {passenger_email}")
            
        except Exception as e:
            logger.error(f"⚠️ Erreur envoi email confirmation: {e}")
        
        return f"""
        <html><body style="font-family: Arial; text-align: center; padding: 50px;">
            <div style="font-size: 64px; margin-bottom: 20px;">✅</div>
            <h1 style="color: #22c55e;">Réservation acceptée</h1>
            <p style="font-size: 18px; color: #475569;">Un email de confirmation a été envoyé à {passenger_name}.</p>
            <p style="font-size: 14px; color: #94a3b8;">Vous pouvez fermer cette fenêtre.</p>
        </body></html>
        """
        
    except Exception as e:
        logger.error(f"Error in accept_ponctual_reservation: {str(e)}", exc_info=True)
        return "Erreur serveur", 500


@app.route('/api/v2/reservations/ponctual/<int:reservation_id>/reject', methods=['GET'])
def reject_ponctual_reservation(reservation_id):
    """Refuser une demande de réservation ponctuelle"""
    try:
        # Vérifier le token de sécurité
        token = request.args.get('token')
        if not token:
            return "Token manquant", 400
        
        with sql.db_cursor() as cur:
            # Récupérer la réservation avec le token
            cur.execute("""
                SELECT r.id, r.passenger_name, r.passenger_email, r.date,
                       r.confirmation_token, r.status,
                       o.driver_name, o.departure, o.destination
                FROM carpool_reservations_ponctual r
                JOIN carpool_offers o ON r.offer_id = o.id
                WHERE r.id = %s
            """, (reservation_id,))
            
            reservation = cur.fetchone()
            
            if not reservation:
                return "Réservation non trouvée", 404
            
            res_id, passenger_name, passenger_email, date_requested, \
                confirmation_token_db, status, \
                driver_name, departure, destination = reservation
            
            # Vérifier le token
            if confirmation_token_db != token:
                return "Token invalide", 403
            
            # Vérifier que la réservation est encore en attente
            if status != 'pending':
                return f"Cette réservation a déjà été {status}.", 400
            
            # Mettre à jour le statut
            cur.execute("""
                UPDATE carpool_reservations_ponctual
                SET status = 'rejected'
                WHERE id = %s
            """, (reservation_id,))
            
            sql.db.commit()
        
        logger.info(f"❌ Réservation ponctuelle {reservation_id} refusée")
        
        # Envoyer un email au passager
        try:
            from emails import send_email
            from datetime import datetime
            
            # Formater la date
            date_obj = datetime.strptime(str(date_requested), '%Y-%m-%d').date()
            months_fr = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 
                        'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
            days_fr = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
            
            day_name = days_fr[date_obj.weekday()]
            date_formatted = f"{day_name} {date_obj.day} {months_fr[date_obj.month - 1]} {date_obj.year}"
            
            subject = f"Demande de covoiturage du {date_formatted}"
            
            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #64748b 0%, #475569 100%); color: white; padding: 30px; text-align: center; border-radius: 12px 12px 0 0;">
                    <h1 style="margin: 0; font-size: 24px;">Demande non acceptée</h1>
                </div>
                
                <div style="background: #f8fafc; padding: 30px; border-radius: 0 0 12px 12px;">
                    <p style="font-size: 16px; color: #1e293b;">Bonjour <strong>{passenger_name}</strong>,</p>
                    
                    <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                        Malheureusement, <strong>{driver_name}</strong> n'a pas pu accepter votre demande de covoiturage pour le {date_formatted}.
                    </p>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #7c3aed;">
                        <p style="margin: 0 0 10px 0; color: #64748b; font-size: 13px;">📍 Trajet</p>
                        <p style="margin: 0 0 5px 0; font-size: 15px; color: #1e293b;">
                            <strong>🏠 {departure}</strong>
                        </p>
                        <p style="margin: 0; font-size: 15px; color: #1e293b;">
                            <strong>🏢 {destination}</strong>
                        </p>
                    </div>
                    
                    <div style="background: #dbeafe; border-left: 4px solid #3b82f6; padding: 16px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0; font-size: 14px; color: #1e40af; line-height: 1.6;">
                            💡 <strong>Conseil</strong><br>
                            Consultez les autres offres disponibles sur la plateforme. Il y a peut-être d'autres conducteurs sur ce trajet !
                        </p>
                    </div>
                    
                    <p style="font-size: 12px; color: #94a3b8; text-align: center; margin-top: 30px;">
                        Carette - Plateforme de covoiturage RSE
                    </p>
                </div>
            </div>
            """
            
            text_body = f"""
Demande de covoiturage non acceptée

Bonjour {passenger_name},

Malheureusement, {driver_name} n'a pas pu accepter votre demande de covoiturage pour le {date_formatted}.

📍 Trajet :
🏠 {departure}
🏢 {destination}

💡 Consultez les autres offres disponibles sur la plateforme. Il y a peut-être d'autres conducteurs sur ce trajet !

---
Carette - Plateforme de covoiturage RSE
            """
            
            send_email(passenger_email, subject, html_body, text_body)
            logger.info(f"📧 Email de refus envoyé à {passenger_email}")
            
        except Exception as e:
            logger.error(f"⚠️ Erreur envoi email refus: {e}")
        
        return f"""
        <html><body style="font-family: Arial; text-align: center; padding: 50px;">
            <div style="font-size: 64px; margin-bottom: 20px;">✓</div>
            <h1 style="color: #64748b;">Réservation refusée</h1>
            <p style="font-size: 18px; color: #475569;">Un email a été envoyé à {passenger_name}.</p>
            <p style="font-size: 14px; color: #94a3b8;">Vous pouvez fermer cette fenêtre.</p>
        </body></html>
        """
        
    except Exception as e:
        logger.error(f"Error in reject_ponctual_reservation: {str(e)}", exc_info=True)
        return "Erreur serveur", 500


# ============================================================================
# ENDPOINTS RSE - RÉCAPITULATIF HEBDOMADAIRE
# ============================================================================

@app.route('/api/v2/rse/send-weekly-recap', methods=['POST'])
@limiter.limit("10 per hour")
def send_weekly_recap():
    """
    Envoie le récapitulatif hebdomadaire à tous les utilisateurs RSE (ou un seul pour test).
    Crée les entrées en DB pour la semaine si elles n'existent pas déjà.
    Inclut une suggestion de covoiturage si applicable.
    
    Paramètres optionnels:
        - test_email: pour envoyer uniquement à un email de test
        - week_end_date: date de fin de semaine (format YYYY-MM-DD), par défaut = vendredi dernier
    """
    try:
        from datetime import datetime, timedelta
        from email_templates import email_weekly_rse_recap
        from email_sender import send_email
        from carpool_matching import get_carpool_suggestions_for_user
        import secrets
        
        data = request.json or {}
        test_email = data.get('test_email')
        week_end_date_str = data.get('week_end_date')
        
        # Calculer la semaine (du lundi au vendredi)
        if week_end_date_str:
            week_end = datetime.strptime(week_end_date_str, '%Y-%m-%d')
        else:
            today = datetime.now()
            days_since_friday = (today.weekday() - 4) % 7
            week_end = today - timedelta(days=days_since_friday)
        
        week_start = week_end - timedelta(days=4)
        
        with sql.db_cursor() as cur:
            # Récupérer les utilisateurs actifs avec leur company_id
            if test_email:
                cur.execute("""
                    SELECT id, name, email, distance_km, company_id 
                    FROM rse_users 
                    WHERE email = %s AND active = 1
                """, (test_email,))
            else:
                cur.execute("""
                    SELECT id, name, email, distance_km, company_id 
                    FROM rse_users 
                    WHERE active = 1
                """)
            
            users = cur.fetchall()
            
            if not users:
                return jsonify({'error': 'Aucun utilisateur trouvé'}), 404
            
            sent_count = 0
            carpool_count = 0
            
            for user in users:
                user_id = user['id']
                user_name = user['name']
                user_email = user['email']
                distance_km = float(user['distance_km'] or 30.0)
                company_id = user['company_id']
                
                # Vérifier si une entrée existe déjà pour cette semaine
                cur.execute("""
                    SELECT id, magic_token, total_co2, total_distance
                    FROM rse_weekly_data 
                    WHERE user_id = %s AND week_start = %s
                """, (user_id, week_start.strftime('%Y-%m-%d')))
                
                existing = cur.fetchone()
                
                if not existing:
                    # Créer les données de la semaine basées sur les HABITUDES de l'utilisateur
                    magic_token = secrets.token_urlsafe(32)
                    
                    # Récupérer les habitudes par défaut
                    cur.execute("""
                        SELECT monday, tuesday, wednesday, thursday, friday
                        FROM rse_user_habits
                        WHERE user_id = %s
                    """, (user_id,))
                    
                    habits = cur.fetchone()
                    
                    if not habits:
                        # L'utilisateur n'a jamais déclaré ses habitudes via le widget
                        logger.warning(f"⚠️ {user_email} n'a pas d'habitudes de transport configurées - email non envoyé")
                        continue  # Passer à l'utilisateur suivant
                    
                    # Créer l'entrée hebdomadaire
                    cur.execute("""
                        INSERT INTO rse_weekly_data 
                        (user_id, week_start, week_end, magic_token, total_distance)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        user_id,
                        week_start.strftime('%Y-%m-%d'),
                        week_end.strftime('%Y-%m-%d'),
                        magic_token,
                        distance_km * 10  # 5 jours AR
                    ))
                    weekly_data_id = cur.lastrowid
                    
                    # Créer les 5 jours basés sur les HABITUDES
                    day_names = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
                    habit_keys = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
                    
                    # Calcul CO2 par mode de transport (kg CO2/km pour aller-retour)
                    co2_factors = {
                        'voiture_solo': 0.220,
                        'transports_commun': 0.060,
                        'covoiturage': 0.110,
                        'velo': 0.0,
                        'train': 0.006,
                        'teletravail': 0.0,
                        'marche': 0.0,
                        'ne_travaille_pas': 0.0
                    }
                    
                    for i in range(5):
                        day_date = week_start + timedelta(days=i)
                        transport_mode = habits[habit_keys[i]]
                        
                        # Calculer CO2 pour aller-retour (distance × 2)
                        co2_total = distance_km * 2 * co2_factors.get(transport_mode, 0.220)
                        
                        cur.execute("""
                            INSERT INTO rse_daily_transports 
                            (weekly_data_id, date, day_name, transport_mode, distance_total, co2_total)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            weekly_data_id,
                            day_date.strftime('%Y-%m-%d'),
                            day_names[i],
                            transport_mode,
                            distance_km * 2,
                            co2_total
                        ))
                    
                    logger.info(f"✨ Semaine créée depuis habitudes pour {user_email}")
                else:
                    weekly_data_id = existing['id']
                    magic_token = existing['magic_token']
                    logger.info(f"📦 Données existantes trouvées pour {user_email}")
                
                # Récupérer les données de la semaine
                cur.execute("""
                    SELECT date, day_name, transport_mode, co2_total
                    FROM rse_daily_transports
                    WHERE weekly_data_id = %s
                    ORDER BY date
                """, (weekly_data_id,))
                
                days_data = cur.fetchall()
                
                # Construire week_data pour l'email
                week_data = {
                    'week_start': week_start.strftime('%Y-%m-%d'),
                    'week_end': week_end.strftime('%Y-%m-%d'),
                    'days': [],
                    'total_co2': 0.0,
                    'total_distance': distance_km * 10
                }
                
                for day in days_data:
                    week_data['days'].append({
                        'date': day['date'].strftime('%Y-%m-%d'),
                        'day_name': day['day_name'],
                        'transport_mode': day['transport_mode']
                    })
                    week_data['total_co2'] += float(day['co2_total'] or 0)
                
                # Chercher une suggestion de covoiturage pour cet utilisateur
                carpool_suggestion = None
                try:
                    if company_id:
                        suggestions = get_carpool_suggestions_for_user(user_id, company_id, cur, max_detour_minutes=20)
                        if suggestions:
                            carpool_suggestion = suggestions[0]  # Prendre la meilleure
                            logger.info(f"🚗 Suggestion covoiturage pour {user_email}: {carpool_suggestion.get('match_name')}")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur calcul covoiturage pour {user_email}: {e}")
                
                # Envoyer l'email
                try:
                    subject, html_body, text_body = email_weekly_rse_recap(
                        user_name,
                        user_email,
                        week_data,
                        magic_token,
                        BASE_URL,
                        carpool_suggestion=carpool_suggestion
                    )
                    send_email(user_email, subject, html_body, text_body)
                    
                    # Marquer comme envoyé
                    cur.execute("""
                        UPDATE rse_weekly_data 
                        SET email_sent = 1, email_sent_at = NOW()
                        WHERE id = %s
                    """, (weekly_data_id,))
                    
                    sent_count += 1
                    if carpool_suggestion:
                        carpool_count += 1
                    logger.info(f"✅ Récap hebdo envoyé à {user_email}")
                    
                except Exception as e:
                    logger.error(f"❌ Échec envoi à {user_email}: {e}")
        
        return jsonify({
            'success': True,
            'message': f'{sent_count} email(s) envoyé(s) dont {carpool_count} avec suggestion covoiturage',
            'sent_count': sent_count,
            'carpool_suggestions_count': carpool_count,
            'week': f"{week_start.strftime('%Y-%m-%d')} → {week_end.strftime('%Y-%m-%d')}"
        }), 200
        
    except Exception as e:
        logger.error(f"Error in send_weekly_recap: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/rse/weekly-confirm', methods=['GET'])
def confirm_weekly_data():
    """
    Valide les trajets hebdomadaires depuis l'email (magic link).
    RECHARGE les données depuis les habitudes avant de confirmer.
    URL: /api/v2/rse/weekly-confirm?token=xxx
    """
    try:
        from datetime import datetime, timedelta
        
        token = request.args.get('token')
        if not token:
            return "Token manquant", 400
        
        with sql.db_cursor() as cur:
            # Vérifier le token et récupérer user_id + week_start
            cur.execute("""
                SELECT w.id, w.user_id, w.week_start, u.distance_km
                FROM rse_weekly_data w
                JOIN rse_users u ON w.user_id = u.id
                WHERE w.magic_token = %s
            """, (token,))
            
            week_info = cur.fetchone()
            
            if not week_info:
                return "Token invalide", 400
            
            weekly_data_id = week_info['id']
            user_id = week_info['user_id']
            week_start = week_info['week_start']
            distance_km = float(week_info['distance_km'] or 30.0)
            
            # Récupérer les HABITUDES de l'utilisateur
            cur.execute("""
                SELECT monday, tuesday, wednesday, thursday, friday
                FROM rse_user_habits
                WHERE user_id = %s
            """, (user_id,))
            
            habits = cur.fetchone()
            
            if not habits:
                return "Habitudes de transport non trouvées", 400
            
            # RECHARGER les transports depuis les habitudes
            habit_keys = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
            
            co2_factors = {
                'voiture_solo': 0.220,
                'transports_commun': 0.060,
                'covoiturage': 0.110,
                'velo': 0.0,
                'train': 0.006,
                'teletravail': 0.0,
                'marche': 0.0,
                'ne_travaille_pas': 0.0
            }
            
            total_co2 = 0.0
            
            for i in range(5):
                day_date = week_start + timedelta(days=i)
                transport_mode = habits[habit_keys[i]]
                
                # Calculer CO2 pour aller-retour (distance × 2)
                co2_total = distance_km * 2 * co2_factors.get(transport_mode, 0.220)
                total_co2 += co2_total
                
                # Mettre à jour le trajet quotidien
                cur.execute("""
                    UPDATE rse_daily_transports
                    SET transport_mode = %s, co2_total = %s, distance_total = %s
                    WHERE weekly_data_id = %s AND date = %s
                """, (
                    transport_mode, co2_total, distance_km * 2,
                    weekly_data_id, day_date
                ))
            
            # Marquer comme confirmé avec le CO2 recalculé
            cur.execute("""
                UPDATE rse_weekly_data 
                SET confirmed = 1, confirmed_at = NOW(), total_co2 = %s
                WHERE id = %s
            """, (total_co2, weekly_data_id))
            
            logger.info(f"✅ Validation hebdo confirmée (rechargé depuis habitudes): {total_co2:.1f} kg CO2")
        
        return f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Trajets validés ✓</title>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                    margin: 0; 
                    padding: 0; 
                    display: flex; 
                    align-items: center; 
                    justify-content: center; 
                    min-height: 100vh;">
            <div style="background: white; 
                        border-radius: 20px; 
                        padding: 48px; 
                        text-align: center; 
                        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                        max-width: 500px;
                        margin: 20px;">
                <div style="font-size: 80px; margin-bottom: 24px; animation: bounce 1s;">✓</div>
                <h1 style="color: #1f2937; font-size: 32px; margin: 0 0 16px 0; font-weight: 900;">
                    Trajets validés !
                </h1>
                <p style="font-size: 18px; color: #6b7280; margin: 0 0 32px 0; line-height: 1.6;">
                    Merci d'avoir confirmé vos déplacements de la semaine. 
                    Vos données ont été enregistrées avec succès.
                </p>
                <div style="background: #f0fdf4; 
                            border-radius: 12px; 
                            padding: 20px; 
                            border-left: 4px solid #10b981;">
                    <p style="margin: 0; font-size: 14px; color: #166534; line-height: 1.6;">
                        <strong>🌱 Continuez vos efforts !</strong><br>
                        Rendez-vous vendredi prochain pour le prochain récapitulatif.
                    </p>
                </div>
                <p style="font-size: 12px; color: #9ca3af; margin-top: 32px;">
                    Vous pouvez fermer cette fenêtre.
                </p>
            </div>
            <style>
                @keyframes bounce {{
                    0%, 100% {{ transform: translateY(0); }}
                    50% {{ transform: translateY(-20px); }}
                }}
            </style>
        </body>
        </html>
        """
        
    except Exception as e:
        logger.error(f"Error in confirm_weekly_data: {str(e)}", exc_info=True)
        return "Erreur serveur", 500


@app.route('/api/v2/rse/weekly-absent', methods=['GET'])
def mark_weekly_absent():
    """
    Marque toute la semaine comme absente/en congés (tous les trajets passent à 'ne_travaille_pas').
    URL: /api/v2/rse/weekly-absent?token=xxx
    """
    try:
        token = request.args.get('token')
        if not token:
            return "Token manquant", 400
        
        with sql.db_cursor() as cur:
            # Vérifier le token
            cur.execute("""
                SELECT wd.id, u.distance_km
                FROM rse_weekly_data wd
                JOIN rse_users u ON wd.user_id = u.id
                WHERE wd.magic_token = %s
            """, (token,))
            
            week_info = cur.fetchone()
            
            if not week_info:
                return "Token invalide", 400
            
            weekly_data_id = week_info['id']
            
            # Mettre tous les trajets à "ne_travaille_pas" avec CO2 = 0
            cur.execute("""
                UPDATE rse_daily_transports
                SET transport_mode = 'ne_travaille_pas',
                    co2_total = 0,
                    distance_total = 0
                WHERE weekly_data_id = %s
            """, (weekly_data_id,))
            
            # Mettre à jour le total CO2 et marquer comme confirmé
            cur.execute("""
                UPDATE rse_weekly_data 
                SET confirmed = 1, confirmed_at = NOW(), total_co2 = 0
                WHERE id = %s
            """, (weekly_data_id,))
            
            logger.info(f"🏖️ Semaine marquée comme absente/congés")
        
        return f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Congés enregistrés ✓</title>
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%); 
                    margin: 0; 
                    padding: 0; 
                    display: flex; 
                    align-items: center; 
                    justify-content: center; 
                    min-height: 100vh;">
            <div style="background: white; 
                        border-radius: 20px; 
                        padding: 48px; 
                        text-align: center; 
                        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                        max-width: 500px;
                        margin: 20px;">
                <div style="font-size: 80px; margin-bottom: 24px;">🏖️</div>
                <h1 style="color: #1f2937; font-size: 32px; margin: 0 0 16px 0; font-weight: 900;">
                    Congés enregistrés !
                </h1>
                <p style="font-size: 18px; color: #6b7280; margin: 0 0 32px 0; line-height: 1.6;">
                    Votre semaine a été marquée comme congés/absence.
                    Aucune émission CO₂ n'a été comptabilisée.
                </p>
                <div style="background: #fffbeb; 
                            border-radius: 12px; 
                            padding: 20px; 
                            border-left: 4px solid #fbbf24;">
                    <p style="margin: 0; font-size: 14px; color: #92400e; line-height: 1.6;">
                        <strong>😊 Bon repos !</strong><br>
                        Rendez-vous vendredi prochain pour la semaine suivante.
                    </p>
                </div>
                <p style="font-size: 12px; color: #9ca3af; margin-top: 32px;">
                    Vous pouvez fermer cette fenêtre.
                </p>
            </div>
        </body>
        </html>
        """
        
    except Exception as e:
        logger.error(f"Error in mark_weekly_absent: {str(e)}", exc_info=True)
        return "Erreur serveur", 500


@app.route('/api/v2/rse/weekly-data/<token>', methods=['GET'])
def get_weekly_data(token):
    """
    Récupère les données hebdomadaires pour un token donné.
    Utilisé par la page rse-edit-week.html pour charger les données.
    """
    try:
        with sql.db_cursor() as cur:
            # Récupérer les données de la semaine
            cur.execute("""
                SELECT wd.id, wd.week_start, wd.week_end, wd.total_co2, wd.total_distance,
                       wd.confirmed, u.name, u.email, u.distance_km
                FROM rse_weekly_data wd
                JOIN rse_users u ON wd.user_id = u.id
                WHERE wd.magic_token = %s
            """, (token,))
            
            week_info = cur.fetchone()
            
            if not week_info:
                return jsonify({'error': 'Token invalide'}), 404
            
            weekly_data_id = week_info['id']
            distance_km = float(week_info['distance_km'] or 30.0)
            
            # Récupérer les trajets quotidiens
            cur.execute("""
                SELECT date, day_name, transport_mode, co2_total, distance_total
                FROM rse_daily_transports
                WHERE weekly_data_id = %s
                ORDER BY date
            """, (weekly_data_id,))
            
            days_data = cur.fetchall()
            
            # Construire la réponse
            response = {
                'week_start': week_info['week_start'].strftime('%Y-%m-%d'),
                'week_end': week_info['week_end'].strftime('%Y-%m-%d'),
                'distance_km': distance_km,
                'confirmed': bool(week_info['confirmed']),
                'user_name': week_info['name'],
                'days': []
            }
            
            for day in days_data:
                response['days'].append({
                    'date': day['date'].strftime('%Y-%m-%d'),
                    'day_name': day['day_name'],
                    'transport_mode': day['transport_mode'],
                    'co2': float(day['co2_total'] or 0),
                    'distance': float(day['distance_total'] or 0)
                })
            
            return jsonify(response), 200
            
    except Exception as e:
        logger.error(f"Error in get_weekly_data: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/rse/weekly-data/<token>', methods=['PUT'])
@limiter.limit("20 per minute")
def update_weekly_data(token):
    """
    Met à jour les trajets hebdomadaires depuis la page de modification.
    Recalcule automatiquement les émissions CO2.
    Peut optionnellement mettre à jour les habitudes par défaut.
    """
    try:
        data = request.json
        
        if not data or 'days' not in data:
            return jsonify({'error': 'Données manquantes'}), 400
        
        save_as_habits = data.get('save_as_habits', False)  # Nouveau paramètre
        
        with sql.db_cursor() as cur:
            # Vérifier le token
            cur.execute("""
                SELECT wd.id, wd.user_id, u.distance_km
                FROM rse_weekly_data wd
                JOIN rse_users u ON wd.user_id = u.id
                WHERE wd.magic_token = %s
            """, (token,))
            
            week_info = cur.fetchone()
            
            if not week_info:
                return jsonify({'error': 'Token invalide'}), 404
            
            weekly_data_id = week_info['id']
            user_id = week_info['user_id']
            distance_km = float(week_info['distance_km'] or 30.0)
            
            # Récupérer les facteurs d'émission
            cur.execute("""
                SELECT transport_code, co2_per_km
                FROM rse_emission_factors
                WHERE active = 1
            """)
            
            emission_factors = {row['transport_code']: float(row['co2_per_km']) 
                               for row in cur.fetchall()}
            
            total_co2 = 0.0
            habits_update = {}  # Pour sauvegarder les habitudes si demandé
            
            # Mettre à jour chaque jour
            for i, day in enumerate(data['days']):
                date_str = day['date']
                transport_mode = day.get('transport_mode', 'voiture_solo')
                
                # Calculer CO2 pour aller-retour (distance × 2)
                co2_total = emission_factors.get(transport_mode, 0) * distance_km * 2
                total_co2 += co2_total
                
                # Préparer les habitudes si nécessaire (jours ouvrés uniquement)
                if save_as_habits and i < 5:  # Lundi à Vendredi
                    day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
                    day_key = day_names[i]
                    habits_update[day_key] = transport_mode
                
                # Mettre à jour en DB
                cur.execute("""
                    UPDATE rse_daily_transports
                    SET transport_mode = %s,
                        co2_total = %s,
                        distance_total = %s
                    WHERE weekly_data_id = %s AND date = %s
                """, (
                    transport_mode,
                    co2_total,
                    distance_km * 2,
                    weekly_data_id,
                    date_str
                ))
            
            # Mettre à jour le total CO2 de la semaine
            cur.execute("""
                UPDATE rse_weekly_data
                SET total_co2 = %s
                WHERE id = %s
            """, (total_co2, weekly_data_id))
            
            # Sauvegarder les nouvelles habitudes si demandé
            if save_as_habits and habits_update:
                cur.execute("SELECT id FROM rse_user_habits WHERE user_id = %s", (user_id,))
                existing_habits = cur.fetchone()
                
                if existing_habits:
                    cur.execute("""
                        UPDATE rse_user_habits
                        SET monday = %s, tuesday = %s, wednesday = %s, thursday = %s, friday = %s,
                            updated_at = NOW()
                        WHERE user_id = %s
                    """, (
                        habits_update.get('monday'),
                        habits_update.get('tuesday'),
                        habits_update.get('wednesday'),
                        habits_update.get('thursday'),
                        habits_update.get('friday'),
                        user_id
                    ))
                    logger.info(f"✅ Habitudes mises à jour pour user_id={user_id}")
                else:
                    cur.execute("""
                        INSERT INTO rse_user_habits
                        (user_id, monday, tuesday, wednesday, thursday, friday)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        user_id,
                        habits_update.get('monday'),
                        habits_update.get('tuesday'),
                        habits_update.get('wednesday'),
                        habits_update.get('thursday'),
                        habits_update.get('friday')
                    ))
                    logger.info(f"✨ Habitudes créées pour user_id={user_id}")
            
            logger.info(f"✅ Données hebdo mises à jour: {total_co2:.1f} kg CO2 (habitudes sauvegardées: {save_as_habits})")
            
            return jsonify({
                'success': True,
                'total_co2': round(total_co2, 1),
                'habits_saved': save_as_habits
            }), 200
            
    except Exception as e:
        logger.error(f"Error in update_weekly_data: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/rse/users', methods=['POST'])
@limiter.limit("10 per hour")
def create_rse_user():
    """
    Crée un nouvel utilisateur RSE.
    Utilisé pour l'inscription au système de récap hebdomadaire.
    """
    try:
        data = request.json
        
        required_fields = ['name', 'email']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Champ manquant: {field}'}), 400
        
        name = data['name']
        email = data['email']
        departure = data.get('departure_address', '')
        destination = data.get('destination_address', '')
        distance_km = float(data.get('distance_km', 30.0))
        
        with sql.db_cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO rse_users 
                    (name, email, departure_address, destination_address, distance_km, active)
                    VALUES (%s, %s, %s, %s, %s, 1)
                """, (name, email, departure, destination, distance_km))
                
                user_id = cur.lastrowid
                
                logger.info(f"✅ Nouvel utilisateur RSE créé: {email}")
                
                return jsonify({
                    'success': True,
                    'user_id': user_id,
                    'message': 'Utilisateur créé avec succès'
                }), 201
                
            except IntegrityError:
                return jsonify({'error': 'Cet email est déjà enregistré'}), 409
            
    except Exception as e:
        logger.error(f"Error in create_rse_user: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/rse/monthly-recap/user/<int:user_id>', methods=['GET'])
@limiter.limit("30 per minute")
def monthly_recap_user(user_id):
    """
    Récapitulatif mensuel pour un utilisateur spécifique.
    Paramètres: year, month (optionnels, par défaut = mois dernier)
    """
    try:
        from datetime import datetime, timedelta
        
        # Récupérer les paramètres
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        
        # Par défaut : mois dernier
        if not year or not month:
            today = datetime.now()
            first_day_this_month = today.replace(day=1)
            last_month = first_day_this_month - timedelta(days=1)
            year = last_month.year
            month = last_month.month
        
        # Calculer le premier et dernier jour du mois
        first_day = datetime(year, month, 1)
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)
        
        with sql.db_cursor() as cur:
            # Récupérer les infos utilisateur
            cur.execute("""
                SELECT u.name, u.email, u.distance_km, c.name as company_name
                FROM rse_users u
                LEFT JOIN companies c ON u.company_id = c.id
                WHERE u.id = %s
            """, (user_id,))
            
            user = cur.fetchone()
            
            if not user:
                return jsonify({'error': 'Utilisateur non trouvé'}), 404
            
            # Récupérer toutes les semaines confirmées du mois
            cur.execute("""
                SELECT wd.week_start, wd.week_end, wd.total_co2, wd.total_distance, wd.confirmed
                FROM rse_weekly_data wd
                WHERE wd.user_id = %s
                AND wd.week_start >= %s
                AND wd.week_end <= %s
                ORDER BY wd.week_start
            """, (user_id, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
            
            weeks = cur.fetchall()
            
            # Récupérer les détails quotidiens du mois
            cur.execute("""
                SELECT dt.date, dt.day_name, dt.transport_aller, dt.transport_retour,
                       dt.co2_aller, dt.co2_retour, dt.distance_aller, dt.distance_retour
                FROM rse_daily_transports dt
                JOIN rse_weekly_data wd ON dt.weekly_data_id = wd.id
                WHERE wd.user_id = %s
                AND dt.date >= %s
                AND dt.date <= %s
                ORDER BY dt.date
            """, (user_id, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
            
            days = cur.fetchall()
            
            # Calculer les statistiques
            total_co2 = sum(float(w['total_co2'] or 0) for w in weeks if w['confirmed'])
            total_distance = sum(float(w['total_distance'] or 0) for w in weeks if w['confirmed'])
            total_days = len([d for d in days if d['transport_aller'] != 'ne_travaille_pas'])
            
            # Statistiques par mode de transport
            transport_stats = {}
            for day in days:
                for direction in ['aller', 'retour']:
                    transport = day[f'transport_{direction}']
                    if transport not in transport_stats:
                        transport_stats[transport] = {
                            'count': 0,
                            'distance': 0.0,
                            'co2': 0.0
                        }
                    transport_stats[transport]['count'] += 1
                    transport_stats[transport]['distance'] += float(day[f'distance_{direction}'] or 0)
                    transport_stats[transport]['co2'] += float(day[f'co2_{direction}'] or 0)
            
            return jsonify({
                'user': {
                    'id': user_id,
                    'name': user['name'],
                    'email': user['email'],
                    'company': user['company_name']
                },
                'period': {
                    'year': year,
                    'month': month,
                    'start': first_day.strftime('%Y-%m-%d'),
                    'end': last_day.strftime('%Y-%m-%d')
                },
                'summary': {
                    'total_co2_kg': round(total_co2, 2),
                    'total_distance_km': round(total_distance, 2),
                    'total_working_days': total_days,
                    'weeks_count': len(weeks),
                    'weeks_confirmed': len([w for w in weeks if w['confirmed']])
                },
                'transport_breakdown': {
                    mode: {
                        'trips': stats['count'],
                        'distance_km': round(stats['distance'], 2),
                        'co2_kg': round(stats['co2'], 2)
                    }
                    for mode, stats in transport_stats.items()
                },
                'weeks': [
                    {
                        'start': w['week_start'].strftime('%Y-%m-%d'),
                        'end': w['week_end'].strftime('%Y-%m-%d'),
                        'co2_kg': round(float(w['total_co2'] or 0), 2),
                        'distance_km': round(float(w['total_distance'] or 0), 2),
                        'confirmed': bool(w['confirmed'])
                    }
                    for w in weeks
                ]
            }), 200
            
    except Exception as e:
        logger.error(f"Error in monthly_recap_user: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/rse/monthly-recap/company/<int:company_id>', methods=['GET'])
@limiter.limit("30 per minute")
def monthly_recap_company(company_id):
    """
    Récapitulatif mensuel pour une entreprise (agrégation de tous les employés).
    Paramètres: start_date, end_date (optionnels, par défaut = mois dernier)
    """
    try:
        from datetime import datetime, timedelta
        
        # Récupérer les paramètres de dates
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # Par défaut : mois dernier
        if not start_date_str or not end_date_str:
            today = datetime.now()
            first_day_this_month = today.replace(day=1)
            last_month = first_day_this_month - timedelta(days=1)
            year = last_month.year
            month = last_month.month
            
            # Calculer le premier et dernier jour du mois dernier
            first_day = datetime(year, month, 1)
            if month == 12:
                last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = datetime(year, month + 1, 1) - timedelta(days=1)
        else:
            # Utiliser les dates fournies
            first_day = datetime.strptime(start_date_str, '%Y-%m-%d')
            last_day = datetime.strptime(end_date_str, '%Y-%m-%d')
            year = first_day.year
            month = first_day.month
        
        with sql.db_cursor() as cur:
            # Récupérer les infos entreprise
            cur.execute("""
                SELECT name, email, email_domain
                FROM companies
                WHERE id = %s
            """, (company_id,))
            
            company = cur.fetchone()
            
            if not company:
                return jsonify({'error': 'Entreprise non trouvée'}), 404
            
            # Récupérer tous les employés de l'entreprise
            cur.execute("""
                SELECT id, name, email
                FROM rse_users
                WHERE company_id = %s AND active = 1
            """, (company_id,))
            
            employees = cur.fetchall()
            employee_ids = [e['id'] for e in employees]
            
            # Récupérer les sites de l'entreprise (même s'il n'y a pas d'employés)
            cur.execute("""
                SELECT site_name, site_address, site_coords
                FROM company_sites
                WHERE company_id = %s AND active = 1
            """, (company_id,))
            
            company_sites = cur.fetchall()
            
            # Parser les coordonnées JSON pour les sites et construire la liste
            sites_list = []
            for site in company_sites:
                coords = None
                if site['site_coords']:
                    try:
                        if isinstance(site['site_coords'], str):
                            coords = json.loads(site['site_coords'])
                        else:
                            coords = site['site_coords']
                        
                        # Vérifier que coords a bien lat/lng OU lat/lon (géocodage utilise 'lon')
                        if coords and 'lat' in coords:
                            lng = coords.get('lng') or coords.get('lon')  # Support des deux formats
                            if lng:
                                sites_list.append({
                                    'name': site['site_name'],
                                    'address': site['site_address'],
                                    'latitude': float(coords['lat']),
                                    'longitude': float(lng)
                                })
                    except Exception as e:
                        logger.error(f"Erreur parsing coords pour site {site['site_name']}: {e}")
            
            logger.info(f"🗺️ Sites trouvés pour entreprise {company_id}: {len(sites_list)}")
            
            # Si pas d'employés, retourner une structure vide mais valide avec les sites
            if not employee_ids:
                return jsonify({
                    'company': {
                        'id': company_id,
                        'name': company['name'],
                        'email': company['email']
                    },
                    'period': {
                        'year': year,
                        'month': month,
                        'start': first_day.strftime('%Y-%m-%d'),
                        'end': last_day.strftime('%Y-%m-%d')
                    },
                    'summary': {
                        'total_employees': 0,
                        'active_employees': 0,
                        'total_weeks': 0,
                        'confirmed_weeks': 0,
                        'total_co2_kg': 0,
                        'confirmed_co2_kg': 0,
                        'unconfirmed_co2_kg': 0,
                        'total_distance_km': 0,
                        'avg_co2_per_employee': 0
                    },
                    'transport_breakdown': {},
                    'weekday_breakdown': {},
                    'map_data': {
                        'company_sites': sites_list,
                        'employee_locations': []
                    },
                    'top_employees': [],
                    'message': 'Aucun employé inscrit pour le moment. Partagez votre code entreprise pour commencer !'
                }), 200
            
            # Récupérer les coordonnées géocodées des adresses domicile depuis le cache
            cur.execute("""
                SELECT DISTINCT 
                    gc.latitude,
                    gc.longitude,
                    gc.address
                FROM rse_users ru
                JOIN geocoding_cache gc ON ru.departure_address = gc.address
                WHERE ru.company_id = %s 
                AND ru.active = 1
                AND gc.latitude IS NOT NULL
                AND gc.longitude IS NOT NULL
            """, (company_id,))
            
            employee_locations = [
                {
                    'latitude': float(row['latitude']),
                    'longitude': float(row['longitude']),
                    'address': row['address']
                }
                for row in cur.fetchall()
            ]
            
            # Récupérer les données agrégées de la période
            placeholders = ','.join(['%s'] * len(employee_ids))
            
            cur.execute(f"""
                SELECT 
                    COUNT(DISTINCT wd.user_id) as active_employees,
                    COUNT(DISTINCT wd.id) as total_weeks,
                    SUM(CASE WHEN wd.confirmed = 1 THEN 1 ELSE 0 END) as confirmed_weeks,
                    SUM(CASE WHEN wd.confirmed = 1 THEN wd.total_co2 ELSE 0 END) as confirmed_co2,
                    SUM(CASE WHEN wd.confirmed = 0 THEN wd.total_co2 ELSE 0 END) as unconfirmed_co2,
                    SUM(CASE WHEN wd.confirmed = 1 THEN wd.total_distance ELSE 0 END) as confirmed_distance,
                    SUM(CASE WHEN wd.confirmed = 0 THEN wd.total_distance ELSE 0 END) as unconfirmed_distance,
                    SUM(wd.total_co2) as total_co2,
                    SUM(wd.total_distance) as total_distance
                FROM rse_weekly_data wd
                WHERE wd.user_id IN ({placeholders})
                AND wd.week_start >= %s
                AND wd.week_end <= %s
            """, (*employee_ids, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
            
            aggregates = cur.fetchone()
            
            # Statistiques par mode de transport (entreprise) - confirmées
            cur.execute(f"""
                SELECT 
                    dt.transport_mode as transport,
                    COUNT(*) as count,
                    SUM(dt.distance_total) as distance,
                    SUM(dt.co2_total) as co2
                FROM rse_daily_transports dt
                JOIN rse_weekly_data wd ON dt.weekly_data_id = wd.id
                WHERE wd.user_id IN ({placeholders})
                AND dt.date >= %s
                AND dt.date <= %s
                AND wd.confirmed = 1
                GROUP BY dt.transport_mode
            """, (*employee_ids, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
            
            transport_confirmed = cur.fetchall()
            
            # Statistiques par mode de transport (entreprise) - non confirmées
            cur.execute(f"""
                SELECT 
                    dt.transport_mode as transport,
                    COUNT(*) as count,
                    SUM(dt.distance_total) as distance,
                    SUM(dt.co2_total) as co2
                FROM rse_daily_transports dt
                JOIN rse_weekly_data wd ON dt.weekly_data_id = wd.id
                WHERE wd.user_id IN ({placeholders})
                AND dt.date >= %s
                AND dt.date <= %s
                AND wd.confirmed = 0
                GROUP BY dt.transport_mode
            """, (*employee_ids, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
            
            transport_unconfirmed = cur.fetchall()
            
            # Créer les stats par transport (confirmées)
            transport_stats_confirmed = {}
            for row in transport_confirmed:
                transport = row['transport']
                transport_stats_confirmed[transport] = {
                    'count': row['count'],
                    'distance': float(row['distance'] or 0),
                    'co2': float(row['co2'] or 0)
                }
            
            # Créer les stats par transport (non confirmées)
            transport_stats_unconfirmed = {}
            for row in transport_unconfirmed:
                transport = row['transport']
                transport_stats_unconfirmed[transport] = {
                    'count': row['count'],
                    'distance': float(row['distance'] or 0),
                    'co2': float(row['co2'] or 0)
                }
            
            # Récupérer TOUS les employés avec leurs stats (confirmées + non confirmées)
            cur.execute(f"""
                SELECT 
                    u.id,
                    u.name,
                    u.email,
                    SUM(wd.total_co2) as total_co2,
                    SUM(wd.total_distance) as total_distance,
                    SUM(CASE WHEN wd.confirmed = 1 THEN wd.total_co2 ELSE 0 END) as confirmed_co2,
                    SUM(CASE WHEN wd.confirmed = 1 THEN wd.total_distance ELSE 0 END) as confirmed_distance,
                    COUNT(DISTINCT wd.id) as weeks_count,
                    SUM(CASE WHEN wd.confirmed = 1 THEN 1 ELSE 0 END) as confirmed_weeks
                FROM rse_users u
                JOIN rse_weekly_data wd ON u.id = wd.user_id
                WHERE u.company_id = %s
                AND wd.week_start >= %s
                AND wd.week_end <= %s
                GROUP BY u.id, u.name, u.email
                ORDER BY total_co2 DESC
            """, (company_id, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
            
            top_employees = cur.fetchall()
            
            # Statistiques par jour de la semaine
            cur.execute(f"""
                SELECT 
                    DAYOFWEEK(dt.date) as day_num,
                    SUM(CASE WHEN wd.confirmed = 1 THEN dt.co2_total ELSE 0 END) as confirmed_co2,
                    SUM(CASE WHEN wd.confirmed = 0 THEN dt.co2_total ELSE 0 END) as unconfirmed_co2,
                    COUNT(*) as trips
                FROM rse_daily_transports dt
                JOIN rse_weekly_data wd ON dt.weekly_data_id = wd.id
                WHERE wd.user_id IN ({placeholders})
                AND dt.date >= %s
                AND dt.date <= %s
                GROUP BY day_num
                ORDER BY day_num
            """, (*employee_ids, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
            
            weekday_data = cur.fetchall()
            
            # Convertir en dict (1=Dimanche en MySQL, on veut Lundi=0)
            weekday_stats = {
                'monday': {'confirmed': 0, 'unconfirmed': 0, 'trips': 0},
                'tuesday': {'confirmed': 0, 'unconfirmed': 0, 'trips': 0},
                'wednesday': {'confirmed': 0, 'unconfirmed': 0, 'trips': 0},
                'thursday': {'confirmed': 0, 'unconfirmed': 0, 'trips': 0},
                'friday': {'confirmed': 0, 'unconfirmed': 0, 'trips': 0}
            }
            
            day_map = {2: 'monday', 3: 'tuesday', 4: 'wednesday', 5: 'thursday', 6: 'friday'}
            for row in weekday_data:
                day_name = day_map.get(row['day_num'])
                if day_name:
                    weekday_stats[day_name] = {
                        'confirmed': float(row['confirmed_co2'] or 0),
                        'unconfirmed': float(row['unconfirmed_co2'] or 0),
                        'trips': row['trips']
                    }
            
            # Tous les modes de transport (union des deux listes)
            all_modes = set(list(transport_stats_confirmed.keys()) + list(transport_stats_unconfirmed.keys()))
            
            return jsonify({
                'company': {
                    'id': company_id,
                    'name': company['name'],
                    'email': company['email']
                },
                'period': {
                    'year': year,
                    'month': month,
                    'start': first_day.strftime('%Y-%m-%d'),
                    'end': last_day.strftime('%Y-%m-%d')
                },
                'summary': {
                    'total_employees': len(employees),
                    'active_employees': aggregates['active_employees'],
                    'total_co2_kg': round(float(aggregates['total_co2'] or 0), 2),
                    'confirmed_co2_kg': round(float(aggregates['confirmed_co2'] or 0), 2),
                    'unconfirmed_co2_kg': round(float(aggregates['unconfirmed_co2'] or 0), 2),
                    'total_distance_km': round(float(aggregates['total_distance'] or 0), 2),
                    'confirmed_distance_km': round(float(aggregates['confirmed_distance'] or 0), 2),
                    'unconfirmed_distance_km': round(float(aggregates['unconfirmed_distance'] or 0), 2),
                    'total_weeks': aggregates['total_weeks'],
                    'confirmed_weeks': aggregates['confirmed_weeks'],
                    'avg_co2_per_employee': round(float(aggregates['total_co2'] or 0) / max(aggregates['active_employees'], 1), 2)
                },
                'transport_breakdown': {
                    mode: {
                        'confirmed': {
                            'trips': transport_stats_confirmed.get(mode, {}).get('count', 0),
                            'distance_km': round(transport_stats_confirmed.get(mode, {}).get('distance', 0), 2),
                            'co2_kg': round(transport_stats_confirmed.get(mode, {}).get('co2', 0), 2),
                        },
                        'unconfirmed': {
                            'trips': transport_stats_unconfirmed.get(mode, {}).get('count', 0),
                            'distance_km': round(transport_stats_unconfirmed.get(mode, {}).get('distance', 0), 2),
                            'co2_kg': round(transport_stats_unconfirmed.get(mode, {}).get('co2', 0), 2),
                        }
                    }
                    for mode in all_modes
                },
                'weekday_breakdown': {
                    day: {
                        'confirmed_co2_kg': round(stats['confirmed'], 2),
                        'unconfirmed_co2_kg': round(stats['unconfirmed'], 2),
                        'total_co2_kg': round(stats['confirmed'] + stats['unconfirmed'], 2),
                        'trips': stats['trips']
                    }
                    for day, stats in weekday_stats.items()
                },
                'map_data': {
                    'company_sites': sites_list,  # Utiliser la liste déjà parsée
                    'employee_locations': [
                        {
                            'latitude': loc['latitude'],
                            'longitude': loc['longitude'],
                            'address': loc['address']
                        }
                        for loc in employee_locations
                    ]
                },
                'top_employees': [
                    {
                        'id': e['id'],
                        'name': e['name'],
                        'email': e['email'],
                        'co2_kg': round(float(e['total_co2'] or 0), 2),
                        'distance_km': round(float(e['total_distance'] or 0), 2),
                        'confirmed_co2_kg': round(float(e['confirmed_co2'] or 0), 2),
                        'confirmed_distance_km': round(float(e['confirmed_distance'] or 0), 2),
                        'weeks': int(e['weeks_count']),
                        'confirmed_weeks': int(e['confirmed_weeks'] or 0),
                        'validation_rate': round((int(e['confirmed_weeks'] or 0) / int(e['weeks_count']) * 100) if e['weeks_count'] > 0 else 0, 1)
                    }
                    for e in top_employees
                ]
            }), 200
            
    except Exception as e:
        logger.error(f"Error in monthly_recap_company: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500

@app.route('/api/v2/companies', methods=['POST'])
@limiter.limit("10 per hour")
def create_company():
    """
    Crée une nouvelle entreprise avec génération automatique du code et de la clé d'accès.
    """
    try:
        import secrets
        import hashlib
        from datetime import datetime
        from werkzeug.security import generate_password_hash
        
        data = request.json
        
        required_fields = ['name']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Champ manquant: {field}'}), 400
        
        name = data['name']
        siren = data.get('siren')
        contact_email = data.get('contact_email')
        contact_name = data.get('contact_name')
        address = data.get('address')
        email_domain = data.get('email_domain')  # ex: "techcorp.fr"
        sites = data.get('sites', [])  # Liste des sites [{name, address}, ...]
        password = data.get('password')  # Mot de passe optionnel
        
        # Hasher le mot de passe si fourni
        password_hash = None
        if password and len(password) >= 8:
            password_hash = generate_password_hash(password)
        
        # Générer un code entreprise court (ex: TECH2026)
        # Format: 4 premières lettres + année
        prefix = ''.join(c for c in name.upper() if c.isalpha())[:4]
        year = datetime.now().year
        company_code = f"{prefix}{year}"
        
        # Si collision, ajouter un suffixe
        with sql.db_cursor() as cur:
            counter = 1
            original_code = company_code
            while True:
                cur.execute("SELECT id FROM companies WHERE company_code = %s", (company_code,))
                if not cur.fetchone():
                    break
                company_code = f"{original_code}{counter}"
                counter += 1
        
        # Générer une clé d'accès sécurisée (64 caractères)
        access_key = secrets.token_urlsafe(48)  # ~64 chars en base64
        
        # Générer magic link admin pour accès dashboard
        magic_token_admin = secrets.token_urlsafe(32)
        
        with sql.db_cursor() as cur:
            cur.execute("""
                INSERT INTO companies 
                (name, company_code, access_key, magic_token_admin, email_domain, siren, contact_email, contact_name, address, email, password_hash, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
            """, (name, company_code, access_key, magic_token_admin, email_domain, siren, contact_email, contact_name, address, contact_email, password_hash))
            
            company_id = cur.lastrowid
            
            # Créer les sites si fournis
            sites_created = 0
            if sites:
                for site in sites:
                    site_name = site.get('name', '').strip()
                    site_address = site.get('address', '').strip()
                    
                    if site_name and site_address:
                        # Géocoder l'adresse
                        coords = geocode_address_auto(site_address, cur)
                        
                        # Insérer le site
                        cur.execute("""
                            INSERT INTO company_sites 
                            (company_id, site_name, site_address, site_coords)
                            VALUES (%s, %s, %s, %s)
                        """, (company_id, site_name, site_address, json.dumps(coords) if coords else None))
                        sites_created += 1
                        logger.info(f"  📍 Site créé: {site_name} - {site_address}")
            
            logger.info(f"✅ Nouvelle entreprise créée: {name} (ID: {company_id}, Code: {company_code}, {sites_created} site(s))")
            
            # URL de base pour les liens
            base_url = request.host_url.rstrip('/')
            management_url = f"{base_url}/manage-employees-new.html?token={magic_token_admin}"
            dashboard_url = f"{base_url}/dashboard-company.html?company_id={company_id}&access_key={access_key}"
            
            # Envoyer email de confirmation avec les informations de connexion
            if contact_email:
                try:
                    from email_sender import send_email
                    
                    subject = f"🎉 Bienvenue sur Carette RSE - Code: {company_code}"
                    
                    html_body = f"""
                    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h1 style="color: #667eea; text-align: center;">🌱 Bienvenue sur Carette RSE</h1>
                        
                        <div style="background: #f8fafc; border-radius: 12px; padding: 24px; margin: 24px 0;">
                            <h2 style="color: #1e293b; margin-top: 0;">Votre compte a été créé avec succès !</h2>
                            
                            <p style="color: #475569; line-height: 1.6;">
                                Bonjour <strong>{contact_name}</strong>,
                            </p>
                            
                            <p style="color: #475569; line-height: 1.6;">
                                Votre entreprise <strong>{name}</strong> est maintenant inscrite sur Carette RSE.
                            </p>
                            
                            <div style="background: white; border: 2px solid #667eea; border-radius: 8px; padding: 16px; margin: 20px 0; text-align: center;">
                                <div style="font-size: 14px; color: #64748b; margin-bottom: 8px;">Votre code entreprise :</div>
                                <div style="font-size: 32px; font-weight: 900; color: #667eea; letter-spacing: 2px;">{company_code}</div>
                            </div>
                            
                            <p style="color: #475569; line-height: 1.6;">
                                <strong>Partagez ce code avec vos employés</strong> pour qu'ils puissent s'inscrire et commencer à suivre leurs trajets domicile-travail.
                            </p>
                        </div>
                        
                        <div style="margin: 24px 0;">
                            <h3 style="color: #1e293b;">🔗 Vos liens de gestion</h3>
                            
                            <a href="{dashboard_url}" 
                               style="display: block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; padding: 16px; border-radius: 10px; text-align: center; font-weight: 700; margin: 12px 0;">
                                📊 Accéder au Dashboard
                            </a>
                            
                            <a href="{management_url}" 
                               style="display: block; background: #10b981; color: white; text-decoration: none; padding: 16px; border-radius: 10px; text-align: center; font-weight: 700; margin: 12px 0;">
                                ⚙️ Gérer mes employés et sites
                            </a>
                            
                            <p style="color: #64748b; font-size: 13px; margin-top: 16px;">
                                💡 Conservez ces liens précieusement. Vous pourrez y accéder à tout moment.
                            </p>
                        </div>
                        
                        <div style="background: #f1f5f9; border-radius: 8px; padding: 16px; margin: 24px 0;">
                            <h3 style="color: #1e293b; margin-top: 0;">📋 Prochaines étapes</h3>
                            <ol style="color: #475569; line-height: 1.8;">
                                <li>Partagez le code <strong>{company_code}</strong> avec vos employés</li>
                                <li>Intégrez le widget RSE sur votre intranet (voir documentation)</li>
                                <li>Suivez les statistiques sur votre dashboard</li>
                            </ol>
                        </div>
                        
                        <div style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 32px; padding-top: 20px; border-top: 1px solid #e5e7eb;">
                            <strong>Carette</strong> - Plateforme RSE de mobilité durable<br>
                            Email envoyé automatiquement - Ne pas répondre
                        </div>
                    </div>
                    """
                    
                    text_body = f"""
Bienvenue sur Carette RSE

Votre compte a été créé avec succès !

Bonjour {contact_name},

Votre entreprise {name} est maintenant inscrite sur Carette RSE.

CODE ENTREPRISE: {company_code}

Partagez ce code avec vos employés pour qu'ils puissent s'inscrire.

LIENS DE GESTION:
- Dashboard: {dashboard_url}
- Gestion employés: {management_url}

Prochaines étapes:
1. Partagez le code {company_code} avec vos employés
2. Intégrez le widget RSE sur votre intranet
3. Suivez les statistiques sur votre dashboard

---
Carette - Plateforme RSE de mobilité durable
                    """
                    
                    send_email(contact_email, subject, html_body, text_body)
                    logger.info(f"📧 Email de bienvenue envoyé à {contact_email}")
                    
                except Exception as email_error:
                    logger.error(f"❌ Erreur envoi email bienvenue: {email_error}")
                    # Ne pas bloquer la création si l'email échoue
            
            return jsonify({
                'success': True,
                'company_id': company_id,
                'company_code': company_code,
                'access_key': access_key,
                'magic_token_admin': magic_token_admin,
                'management_url': management_url,
                'dashboard_url': dashboard_url,
                'sites_created': sites_created,
                'contact_email': contact_email,
                'message': 'Entreprise créée avec succès',
                'instructions': f"Partagez le code '{company_code}' avec vos employés pour qu'ils s'inscrivent."
            }), 201
            
    except Exception as e:
        logger.error(f"Error in create_company: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/companies/<int:company_id>/import-employees', methods=['POST'])
@limiter.limit("10 per hour")
def import_employees_csv(company_id):
    """
    Import d'employés via CSV.
    Format attendu: nom,email,adresse (avec header optionnel)
    Authentification via access_key en header ou query param
    """
    import csv
    import io
    
    try:
        # Vérifier l'authentification
        access_key = request.headers.get('X-Access-Key') or request.args.get('access_key')
        
        if not access_key:
            return jsonify({'error': 'Clé d\'accès manquante'}), 401
        
        with sql.db_cursor() as cur:
            # Vérifier que l'entreprise existe et que la clé est valide
            cur.execute("""
                SELECT id, name, company_code FROM companies 
                WHERE id = %s AND access_key = %s AND active = 1
            """, (company_id, access_key))
            
            company = cur.fetchone()
            if not company:
                return jsonify({'error': 'Entreprise non trouvée ou accès refusé'}), 404
            
            company_code = company['company_code']
            
            # Récupérer le fichier CSV
            if 'file' not in request.files:
                # Essayer le body raw comme CSV
                csv_data = request.get_data(as_text=True)
                if not csv_data:
                    return jsonify({'error': 'Aucun fichier CSV fourni'}), 400
            else:
                file = request.files['file']
                csv_data = file.read().decode('utf-8-sig')  # utf-8-sig pour gérer le BOM Excel
            
            # Parser le CSV
            reader = csv.reader(io.StringIO(csv_data), delimiter=';')
            rows = list(reader)
            
            # Détecter si première ligne est un header
            if rows and rows[0][0].lower() in ['nom', 'name', 'prenom', 'prénom']:
                rows = rows[1:]
            
            # Si le délimiteur ; ne marche pas, essayer ,
            if rows and len(rows[0]) == 1:
                reader = csv.reader(io.StringIO(csv_data), delimiter=',')
                rows = list(reader)
                if rows and rows[0][0].lower() in ['nom', 'name', 'prenom', 'prénom']:
                    rows = rows[1:]
            
            imported = []
            errors = []
            
            for i, row in enumerate(rows, 1):
                if len(row) < 2:
                    errors.append(f"Ligne {i}: format invalide (min: nom, email)")
                    continue
                
                # Parser les colonnes (flexible : 2 ou 3 colonnes)
                name = row[0].strip()
                email = row[1].strip().lower()
                address = row[2].strip() if len(row) > 2 else ''
                
                if not name or not email:
                    errors.append(f"Ligne {i}: nom ou email manquant")
                    continue
                
                if '@' not in email:
                    errors.append(f"Ligne {i}: email invalide '{email}'")
                    continue
                
                # Vérifier si l'employé existe déjà
                cur.execute("""
                    SELECT id FROM rse_users WHERE email = %s AND company_id = %s
                """, (email, company_id))
                
                existing = cur.fetchone()
                if existing:
                    errors.append(f"Ligne {i}: {email} déjà inscrit")
                    continue
                
                # Géocoder l'adresse si fournie
                address_coords = None
                if address:
                    try:
                        geo_result = geocode_address(address)
                        if geo_result:
                            address_coords = json.dumps(geo_result)
                    except:
                        pass  # Ignorer les erreurs de géocodage
                
                # Créer l'employé
                cur.execute("""
                    INSERT INTO rse_users (company_id, name, email, address, address_coords, active)
                    VALUES (%s, %s, %s, %s, %s, 1)
                """, (company_id, name, email, address, address_coords))
                
                imported.append({
                    'name': name,
                    'email': email,
                    'address': address or None,
                    'geocoded': address_coords is not None
                })
            
            logger.info(f"📥 Import CSV: {len(imported)} employés importés pour {company['name']}")
            
            return jsonify({
                'success': True,
                'company_id': company_id,
                'company_code': company_code,
                'imported_count': len(imported),
                'errors_count': len(errors),
                'imported': imported,
                'errors': errors[:20],  # Limiter les erreurs affichées
                'message': f"{len(imported)} employé(s) importé(s) avec succès"
            }), 200
            
    except Exception as e:
        logger.error(f"Error in import_employees_csv: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur lors de l\'import'}), 500


@app.route('/api/v2/companies/<int:company_id>/report-pdf', methods=['GET'])
@limiter.limit("10 per hour")
def generate_monthly_report_pdf(company_id):
    """
    Génère un rapport PDF mensuel avec les statistiques RSE.
    Params: month (YYYY-MM), access_key
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO
    
    try:
        access_key = request.args.get('access_key')
        month_param = request.args.get('month')  # Format YYYY-MM
        
        if not access_key:
            return jsonify({'error': 'Clé d\'accès manquante'}), 401
        
        # Déterminer la période
        if month_param:
            try:
                year, month = map(int, month_param.split('-'))
            except:
                return jsonify({'error': 'Format mois invalide (YYYY-MM)'}), 400
        else:
            # Mois précédent par défaut
            now = datetime.now()
            if now.month == 1:
                year, month = now.year - 1, 12
            else:
                year, month = now.year, now.month - 1
        
        # Premier et dernier jour du mois
        from calendar import monthrange
        first_day = datetime(year, month, 1)
        last_day = datetime(year, month, monthrange(year, month)[1])
        
        with sql.db_cursor() as cur:
            # Vérifier l'accès
            cur.execute("""
                SELECT id, name, company_code, contact_email, siren
                FROM companies WHERE id = %s AND access_key = %s AND active = 1
            """, (company_id, access_key))
            
            company = cur.fetchone()
            if not company:
                return jsonify({'error': 'Entreprise non trouvée'}), 404
            
            # Récupérer les stats
            cur.execute("""
                SELECT 
                    COUNT(DISTINCT u.id) as total_employees,
                    SUM(wd.total_co2) as total_co2,
                    SUM(wd.total_distance) as total_distance,
                    SUM(CASE WHEN wd.confirmed = 1 THEN wd.total_co2 ELSE 0 END) as confirmed_co2,
                    COUNT(DISTINCT wd.id) as total_weeks,
                    SUM(CASE WHEN wd.confirmed = 1 THEN 1 ELSE 0 END) as confirmed_weeks
                FROM rse_users u
                LEFT JOIN rse_weekly_data wd ON u.id = wd.user_id
                    AND wd.week_start >= %s AND wd.week_end <= %s
                WHERE u.company_id = %s AND u.active = 1
            """, (first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d'), company_id))
            
            stats = cur.fetchone()
            
            # Top 5 employés
            cur.execute("""
                SELECT u.name, SUM(wd.total_co2) as co2, SUM(wd.total_distance) as distance
                FROM rse_users u
                JOIN rse_weekly_data wd ON u.id = wd.user_id
                WHERE u.company_id = %s AND wd.week_start >= %s AND wd.week_end <= %s
                GROUP BY u.id, u.name
                ORDER BY co2 DESC
                LIMIT 5
            """, (company_id, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
            
            top_employees = cur.fetchall()
            
            # Répartition transports
            cur.execute("""
                SELECT dt.transport_mode, COUNT(*) as trips, SUM(dt.co2_total) as co2
                FROM rse_daily_transports dt
                JOIN rse_weekly_data wd ON dt.weekly_data_id = wd.id
                JOIN rse_users u ON wd.user_id = u.id
                WHERE u.company_id = %s AND wd.week_start >= %s AND wd.week_end <= %s
                GROUP BY dt.transport_mode
                ORDER BY co2 DESC
            """, (company_id, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
            
            transport_breakdown = cur.fetchall()
        
        # Générer le PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Couleurs
        primary = HexColor('#667eea')
        secondary = HexColor('#10b981')
        gray = HexColor('#64748b')
        dark = HexColor('#1e293b')
        
        # En-tête
        p.setFillColor(primary)
        p.rect(0, height - 3*cm, width, 3*cm, fill=True, stroke=False)
        
        p.setFillColor(HexColor('#ffffff'))
        p.setFont("Helvetica-Bold", 24)
        p.drawString(2*cm, height - 2*cm, "🌱 Rapport RSE Mobilité")
        
        p.setFont("Helvetica", 12)
        month_names = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                       'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        p.drawString(2*cm, height - 2.6*cm, f"{month_names[month-1]} {year} - {company['name']}")
        
        # Infos entreprise
        y = height - 4.5*cm
        p.setFillColor(dark)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(2*cm, y, "Informations entreprise")
        
        y -= 0.7*cm
        p.setFont("Helvetica", 10)
        p.setFillColor(gray)
        p.drawString(2*cm, y, f"Code: {company['company_code']}")
        if company.get('siren'):
            p.drawString(8*cm, y, f"SIREN: {company['siren']}")
        
        # Stats principales
        y -= 1.5*cm
        p.setFillColor(dark)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(2*cm, y, "Bilan du mois")
        
        y -= 1*cm
        
        # Boîtes stats
        box_width = 4*cm
        box_height = 2.5*cm
        boxes = [
            (f"{stats['total_employees'] or 0}", "Employés actifs", secondary),
            (f"{float(stats['total_co2'] or 0):.1f} kg", "CO₂ total", HexColor('#ef4444')),
            (f"{float(stats['total_distance'] or 0):.0f} km", "Distance totale", primary),
            (f"{int((stats['confirmed_weeks'] or 0) / max(stats['total_weeks'] or 1, 1) * 100)}%", "Taux validation", HexColor('#f59e0b'))
        ]
        
        x = 2*cm
        for value, label, color in boxes:
            p.setFillColor(color)
            p.roundRect(x, y - box_height, box_width, box_height, 5, fill=True, stroke=False)
            
            p.setFillColor(HexColor('#ffffff'))
            p.setFont("Helvetica-Bold", 18)
            p.drawCentredString(x + box_width/2, y - 1*cm, value)
            
            p.setFont("Helvetica", 9)
            p.drawCentredString(x + box_width/2, y - 1.8*cm, label)
            
            x += box_width + 0.5*cm
        
        # Top employés
        y -= 4*cm
        p.setFillColor(dark)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(2*cm, y, "Top 5 contributeurs CO₂")
        
        y -= 0.8*cm
        p.setFont("Helvetica", 10)
        for i, emp in enumerate(top_employees, 1):
            p.setFillColor(gray)
            p.drawString(2*cm, y, f"{i}. {emp['name']}")
            p.drawString(10*cm, y, f"{float(emp['co2']):.1f} kg CO₂")
            p.drawString(14*cm, y, f"{float(emp['distance']):.0f} km")
            y -= 0.5*cm
        
        # Répartition transports
        y -= 1*cm
        p.setFillColor(dark)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(2*cm, y, "Répartition par mode de transport")
        
        y -= 0.8*cm
        transport_labels = {
            'voiture_solo': '🚗 Voiture solo',
            'covoiturage': '🚕 Covoiturage',
            'transports_commun': '🚌 Transports',
            'velo': '🚴 Vélo',
            'marche': '🚶 Marche',
            'teletravail': '🏠 Télétravail',
            'train': '🚄 Train'
        }
        
        p.setFont("Helvetica", 10)
        for t in transport_breakdown:
            mode = t['transport_mode']
            label = transport_labels.get(mode, mode)
            p.setFillColor(gray)
            p.drawString(2*cm, y, label)
            p.drawString(8*cm, y, f"{t['trips']} trajets")
            p.drawString(12*cm, y, f"{float(t['co2']):.1f} kg CO₂")
            y -= 0.5*cm
        
        # Pied de page
        p.setFillColor(gray)
        p.setFont("Helvetica", 8)
        p.drawString(2*cm, 1.5*cm, f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
        p.drawString(width - 6*cm, 1.5*cm, "Carette - Mobilité durable")
        
        p.save()
        
        # Retourner le PDF
        buffer.seek(0)
        
        from flask import send_file
        filename = f"rapport_rse_{company['company_code']}_{year}-{month:02d}.pdf"
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Error in generate_monthly_report_pdf: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur génération PDF'}), 500


@app.route('/api/v2/companies/<int:company_id>/monthly-comparison', methods=['GET'])
@limiter.limit("30 per minute")
def get_monthly_comparison(company_id):
    """
    Retourne la comparaison entre le mois en cours et le mois précédent.
    """
    try:
        access_key = request.args.get('access_key')
        
        if not access_key:
            return jsonify({'error': 'Clé d\'accès manquante'}), 401
        
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT id, name FROM companies WHERE id = %s AND access_key = %s AND active = 1
            """, (company_id, access_key))
            
            if not cur.fetchone():
                return jsonify({'error': 'Accès refusé'}), 403
            
            # Calculer les périodes
            now = datetime.now()
            
            # Mois en cours
            current_start = datetime(now.year, now.month, 1)
            if now.month == 12:
                current_end = datetime(now.year + 1, 1, 1) - timedelta(days=1)
            else:
                current_end = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
            
            # Mois précédent
            if now.month == 1:
                prev_start = datetime(now.year - 1, 12, 1)
                prev_end = datetime(now.year, 1, 1) - timedelta(days=1)
            else:
                prev_start = datetime(now.year, now.month - 1, 1)
                prev_end = current_start - timedelta(days=1)
            
            def get_month_stats(start, end):
                cur.execute("""
                    SELECT 
                        COUNT(DISTINCT u.id) as employees,
                        COALESCE(SUM(wd.total_co2), 0) as co2,
                        COALESCE(SUM(wd.total_distance), 0) as distance,
                        COUNT(DISTINCT wd.id) as weeks,
                        SUM(CASE WHEN wd.confirmed = 1 THEN 1 ELSE 0 END) as confirmed
                    FROM rse_users u
                    LEFT JOIN rse_weekly_data wd ON u.id = wd.user_id
                        AND wd.week_start >= %s AND wd.week_end <= %s
                    WHERE u.company_id = %s AND u.active = 1
                """, (start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), company_id))
                return cur.fetchone()
            
            current = get_month_stats(current_start, current_end)
            previous = get_month_stats(prev_start, prev_end)
            
            # Calculer les variations
            def calc_variation(curr, prev):
                if prev == 0 or prev is None:
                    return None
                return round((float(curr or 0) - float(prev)) / float(prev) * 100, 1)
            
            month_names = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                          'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
            
            return jsonify({
                'current_month': {
                    'name': month_names[now.month - 1],
                    'year': now.year,
                    'co2_kg': float(current['co2'] or 0),
                    'distance_km': float(current['distance'] or 0),
                    'employees': current['employees'] or 0,
                    'weeks': current['weeks'] or 0,
                    'validation_rate': round((current['confirmed'] or 0) / max(current['weeks'] or 1, 1) * 100, 1)
                },
                'previous_month': {
                    'name': month_names[prev_start.month - 1],
                    'year': prev_start.year,
                    'co2_kg': float(previous['co2'] or 0),
                    'distance_km': float(previous['distance'] or 0),
                    'employees': previous['employees'] or 0,
                    'weeks': previous['weeks'] or 0,
                    'validation_rate': round((previous['confirmed'] or 0) / max(previous['weeks'] or 1, 1) * 100, 1)
                },
                'variations': {
                    'co2': calc_variation(current['co2'], previous['co2']),
                    'distance': calc_variation(current['distance'], previous['distance']),
                    'employees': calc_variation(current['employees'], previous['employees'])
                }
            }), 200
            
    except Exception as e:
        logger.error(f"Error in get_monthly_comparison: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/auth/verify-admin-token', methods=['GET'])
@limiter.limit("60 per minute")
def verify_admin_token():
    """
    Vérifie le magic token admin et retourne les infos entreprise
    """
    try:
        token = request.args.get('token')
        
        if not token:
            return jsonify({'error': 'Token manquant'}), 401
        
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT id, name, company_code, contact_email
                FROM companies 
                WHERE magic_token_admin = %s AND active = 1
            """, (token,))
            
            company = cur.fetchone()
            
            if not company:
                return jsonify({'error': 'Token invalide'}), 403
            
            return jsonify({
                'success': True,
                'company_id': company['id'],
                'company_name': company['name'],
                'company_code': company['company_code']
            }), 200
            
    except Exception as e:
        logger.error(f"Error in verify_admin_token: {str(e)}")
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def company_login():
    """
    Connexion entreprise par email + mot de passe.
    Retourne les clés d'accès au dashboard.
    """
    try:
        from werkzeug.security import check_password_hash
        
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email et mot de passe requis'}), 400
        
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT id, name, company_code, access_key, magic_token_admin, password_hash
                FROM companies 
                WHERE contact_email = %s AND active = 1
            """, (email,))
            
            company = cur.fetchone()
            
            if not company:
                return jsonify({'error': 'Email ou mot de passe incorrect'}), 401
            
            # Vérifier si l'entreprise a un mot de passe configuré
            if not company['password_hash']:
                return jsonify({
                    'error': 'Pas de mot de passe configuré',
                    'message': 'Utilisez le lien magic link envoyé par email, ou contactez le support pour réinitialiser votre mot de passe.'
                }), 401
            
            # Vérifier le mot de passe
            if not check_password_hash(company['password_hash'], password):
                return jsonify({'error': 'Email ou mot de passe incorrect'}), 401
            
            logger.info(f"✅ Connexion entreprise réussie: {company['name']} ({email})")
            
            # URL de base pour les liens
            base_url = request.host_url.rstrip('/')
            
            return jsonify({
                'success': True,
                'company_id': company['id'],
                'company_name': company['name'],
                'company_code': company['company_code'],
                'access_key': company['access_key'],
                'dashboard_url': f"{base_url}/dashboard-company.html?company_id={company['id']}&access_key={company['access_key']}",
                'management_url': f"{base_url}/manage-employees-new.html?token={company['magic_token_admin']}"
            }), 200
            
    except Exception as e:
        logger.error(f"Error in company_login: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/auth/send-magic-link', methods=['POST'])
@limiter.limit("3 per minute")
def send_company_magic_link():
    """
    Envoie un magic link de connexion par email à l'entreprise.
    """
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'error': 'Email requis'}), 400
        
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT id, name, company_code, access_key, magic_token_admin, contact_name
                FROM companies 
                WHERE contact_email = %s AND active = 1
            """, (email,))
            
            company = cur.fetchone()
            
            # Ne pas révéler si l'email existe ou non (sécurité)
            if company:
                base_url = request.host_url.rstrip('/')
                dashboard_url = f"{base_url}/dashboard-company.html?company_id={company['id']}&access_key={company['access_key']}"
                management_url = f"{base_url}/manage-employees-new.html?token={company['magic_token_admin']}"
                
                # Envoyer l'email
                try:
                    from email_sender import send_email
                    
                    subject = f"🔗 Votre lien de connexion Carette RSE"
                    
                    html_body = f"""
                    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h1 style="color: #667eea; text-align: center;">🌱 Connexion Carette RSE</h1>
                        
                        <div style="background: #f8fafc; border-radius: 12px; padding: 24px; margin: 24px 0;">
                            <p style="color: #475569; line-height: 1.6;">
                                Bonjour <strong>{company['contact_name'] or 'Admin'}</strong>,
                            </p>
                            
                            <p style="color: #475569; line-height: 1.6;">
                                Voici votre lien de connexion pour <strong>{company['name']}</strong> :
                            </p>
                            
                            <a href="{dashboard_url}" 
                               style="display: block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; padding: 16px; border-radius: 10px; text-align: center; font-weight: 700; margin: 20px 0;">
                                📊 Accéder au Dashboard
                            </a>
                            
                            <a href="{management_url}" 
                               style="display: block; background: #10b981; color: white; text-decoration: none; padding: 12px; border-radius: 8px; text-align: center; font-weight: 600; margin: 12px 0;">
                                ⚙️ Gérer mes employés
                            </a>
                        </div>
                        
                        <p style="color: #94a3b8; font-size: 12px; text-align: center;">
                            Ce lien est valable indéfiniment. Conservez-le précieusement.
                        </p>
                    </div>
                    """
                    
                    send_email(email, subject, html_body)
                    logger.info(f"📧 Magic link envoyé à {email} pour {company['name']}")
                    
                except Exception as e:
                    logger.error(f"Erreur envoi magic link: {e}")
            
            # Toujours retourner succès pour ne pas révéler si l'email existe
            return jsonify({
                'success': True,
                'message': 'Si un compte existe avec cet email, vous recevrez un lien de connexion.'
            }), 200
            
    except Exception as e:
        logger.error(f"Error in send_company_magic_link: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/companies/<int:company_id>/verify', methods=['GET'])
@limiter.limit("60 per minute")
def verify_company_access(company_id):
    """
    Vérifie que l'access_key fourni correspond à l'entreprise
    Header: X-Access-Key
    """
    try:
        access_key = request.headers.get('X-Access-Key')
        
        if not access_key:
            return jsonify({'error': 'Access key manquant'}), 401
        
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT id, name, company_code 
                FROM companies 
                WHERE id = %s AND access_key = %s AND active = 1
            """, (company_id, access_key))
            
            company = cur.fetchone()
            
            if not company:
                return jsonify({'error': 'Accès refusé'}), 403
            
            return jsonify({
                'success': True,
                'company_id': company['id'],
                'company_name': company['name'],
                'company_code': company['company_code']
            }), 200
            
    except Exception as e:
        logger.error(f"Error in verify_company_access: {str(e)}")
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/companies/verify-code', methods=['GET'])
@limiter.limit("60 per minute")
def verify_company_code():
    """
    Vérifie qu'un company_code existe et retourne les infos de l'entreprise
    Utilisé par le widget RSE pour valider le code au chargement
    
    Query param: code (ex: DECA2026)
    """
    try:
        company_code = request.args.get('code', '').strip().upper()
        
        if not company_code:
            return jsonify({'error': 'Code entreprise manquant'}), 400
        
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT id, name, company_code, email_domain
                FROM companies 
                WHERE company_code = %s AND active = 1
            """, (company_code,))
            
            company = cur.fetchone()
            
            if not company:
                return jsonify({
                    'error': f'Code entreprise "{company_code}" non trouvé',
                    'valid': False
                }), 404
            
            # Récupérer les sites de l'entreprise
            cur.execute("""
                SELECT id, site_name, site_address, site_coords
                FROM company_sites
                WHERE company_id = %s AND active = 1
                ORDER BY created_at ASC
            """, (company['id'],))
            
            sites = cur.fetchall()
            
            # Parser les coordonnées JSON
            for site in sites:
                if site['site_coords']:
                    site['site_coords'] = json.loads(site['site_coords']) if isinstance(site['site_coords'], str) else site['site_coords']
            
            logger.info(f"✅ Code entreprise validé: {company_code} → {company['name']} ({len(sites)} site(s))")
            
            return jsonify({
                'valid': True,
                'company_id': company['id'],
                'company_name': company['name'],
                'company_code': company['company_code'],
                'email_domain': company['email_domain'],
                'sites': sites
            }), 200
            
    except Exception as e:
        logger.error(f"Error in verify_company_code: {str(e)}")
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/companies/<int:company_id>/employees', methods=['POST'])
@limiter.limit("20 per hour")
def assign_employee_to_company(company_id):
    """
    Assigne un employé à une entreprise.
    Body: {"user_email": "employee@example.com"}
    """
    try:
        data = request.json
        user_email = data.get('user_email')
        
        if not user_email:
            return jsonify({'error': 'Email utilisateur manquant'}), 400
        
        with sql.db_cursor() as cur:
            # Vérifier que l'entreprise existe
            cur.execute("SELECT id FROM companies WHERE id = %s", (company_id,))
            if not cur.fetchone():
                return jsonify({'error': 'Entreprise non trouvée'}), 404
            
            # Vérifier que l'utilisateur existe
            cur.execute("SELECT id, name FROM rse_users WHERE email = %s", (user_email,))
            user = cur.fetchone()
            
            if not user:
                return jsonify({'error': 'Utilisateur non trouvé'}), 404
            
            # Assigner l'employé à l'entreprise
            cur.execute("""
                UPDATE rse_users 
                SET company_id = %s, updated_at = NOW()
                WHERE id = %s
            """, (company_id, user['id']))
            
            logger.info(f"✅ Employé {user['name']} assigné à company_id={company_id}")
            
            return jsonify({
                'success': True,
                'message': f"Employé {user['name']} assigné à l'entreprise"
            }), 200
            
    except Exception as e:
        logger.error(f"Error in assign_employee_to_company: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/rse/auto-confirm-old-weeks', methods=['POST'])
@limiter.limit("5 per hour")
def auto_confirm_old_weeks():
    """
    Auto-confirme les semaines non confirmées de plus de 7 jours.
    À appeler via cron tous les jours ou manuellement.
    
    Logique : Si un employé n'a pas cliqué sur les boutons de l'email,
    on considère que c'est une validation tacite après 7 jours.
    """
    try:
        from datetime import datetime, timedelta
        
        # Date limite : il y a 7 jours
        cutoff_date = datetime.now() - timedelta(days=7)
        
        with sql.db_cursor() as cur:
            # Récupérer les semaines non confirmées de plus de 7 jours
            cur.execute("""
                SELECT wd.id, wd.user_id, wd.week_start, wd.week_end, u.name, u.email
                FROM rse_weekly_data wd
                JOIN rse_users u ON wd.user_id = u.id
                WHERE wd.confirmed = 0
                AND wd.email_sent = 1
                AND wd.week_end < %s
            """, (cutoff_date.strftime('%Y-%m-%d'),))
            
            old_weeks = cur.fetchall()
            
            if not old_weeks:
                return jsonify({
                    'success': True,
                    'message': 'Aucune semaine à auto-confirmer',
                    'auto_confirmed': 0
                }), 200
            
            auto_confirmed_count = 0
            
            for week in old_weeks:
                weekly_data_id = week['id']
                user_name = week['name']
                user_email = week['email']
                week_start = week['week_start']
                
                # Recalculer le CO2 total depuis les trajets quotidiens
                cur.execute("""
                    SELECT SUM(co2_aller + co2_retour) as total_co2
                    FROM rse_daily_transports
                    WHERE weekly_data_id = %s
                """, (weekly_data_id,))
                
                result = cur.fetchone()
                total_co2 = float(result['total_co2'] or 0)
                
                # Auto-confirmer la semaine
                cur.execute("""
                    UPDATE rse_weekly_data
                    SET confirmed = 1, 
                        confirmed_at = NOW(),
                        total_co2 = %s
                    WHERE id = %s
                """, (total_co2, weekly_data_id))
                
                auto_confirmed_count += 1
                logger.info(f"✅ Auto-confirmé semaine {week_start} pour {user_name} ({user_email})")
            
            return jsonify({
                'success': True,
                'message': f'{auto_confirmed_count} semaine(s) auto-confirmée(s)',
                'auto_confirmed': auto_confirmed_count,
                'details': [
                    {
                        'user': w['name'],
                        'email': w['email'],
                        'week_start': w['week_start'].strftime('%Y-%m-%d')
                    }
                    for w in old_weeks
                ]
            }), 200
            
    except Exception as e:
        logger.error(f"Error in auto_confirm_old_weeks: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/rse/users/list', methods=['GET'])
@limiter.limit("30 per minute")
def list_all_rse_users():
    """
    Liste tous les utilisateurs RSE (actifs et inactifs) pour l'administration
    Filtre par company_id si fourni en paramètre
    """
    try:
        company_id = request.args.get('company_id', type=int)
        
        with sql.db_cursor() as cur:
            if company_id:
                cur.execute("""
                    SELECT 
                        u.id,
                        u.name,
                        u.email,
                        u.phone,
                        u.departure_address,
                        u.destination_address,
                        u.distance_km,
                        u.active,
                        u.company_id,
                        c.name as company_name,
                        u.created_at,
                        u.updated_at
                    FROM rse_users u
                    LEFT JOIN companies c ON u.company_id = c.id
                    WHERE u.company_id = %s
                    ORDER BY u.active DESC, u.updated_at DESC
                """, (company_id,))
            else:
                cur.execute("""
                    SELECT 
                        u.id,
                        u.name,
                        u.email,
                        u.phone,
                        u.departure_address,
                        u.destination_address,
                        u.distance_km,
                        u.active,
                        u.company_id,
                        c.name as company_name,
                        u.created_at,
                        u.updated_at
                    FROM rse_users u
                    LEFT JOIN companies c ON u.company_id = c.id
                    ORDER BY u.active DESC, u.updated_at DESC
                """)
            
            users = cur.fetchall()
            
            return jsonify({
                'success': True,
                'count': len(users),
                'users': [
                    {
                        'id': u['id'],
                        'name': u['name'],
                        'email': u['email'],
                        'phone': u['phone'],
                        'departure_address': u['departure_address'],
                        'destination_address': u['destination_address'],
                        'distance_km': float(u['distance_km']) if u['distance_km'] else 0,
                        'active': bool(u['active']),
                        'company_id': u['company_id'],
                        'company_name': u['company_name'],
                        'created_at': u['created_at'].strftime('%Y-%m-%d %H:%M') if u['created_at'] else None,
                        'updated_at': u['updated_at'].strftime('%Y-%m-%d %H:%M') if u['updated_at'] else None
                    }
                    for u in users
                ]
            }), 200
            
    except Exception as e:
        logger.error(f"Error in list_all_rse_users: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/rse/users/<int:user_id>/deactivate', methods=['POST'])
@limiter.limit("10 per minute")
def deactivate_rse_user(user_id):
    """
    Désactive un utilisateur RSE (ex: employé qui quitte l'entreprise)
    Les données historiques sont conservées mais l'utilisateur n'apparaît plus dans les stats
    """
    try:
        # Récupérer company_id depuis les paramètres pour validation
        company_id = request.args.get('company_id', type=int)
        
        with sql.db_cursor() as cur:
            # Vérifier que l'utilisateur existe ET appartient à l'entreprise
            if company_id:
                cur.execute("SELECT id, name, email, active, company_id FROM rse_users WHERE id = %s AND company_id = %s", (user_id, company_id))
            else:
                cur.execute("SELECT id, name, email, active, company_id FROM rse_users WHERE id = %s", (user_id,))
            
            user = cur.fetchone()
            
            if not user:
                return jsonify({'error': 'Utilisateur non trouvé ou accès refusé'}), 404
            
            # Désactiver l'utilisateur
            cur.execute("UPDATE rse_users SET active = 0, updated_at = NOW() WHERE id = %s", (user_id,))
            
            logger.info(f"👋 Utilisateur RSE désactivé: {user['email']} (ID: {user_id})")
            
            return jsonify({
                'success': True,
                'message': f"Utilisateur {user['name']} désactivé avec succès",
                'user_id': user_id,
                'email': user['email']
            }), 200
            
    except Exception as e:
        logger.error(f"Error in deactivate_rse_user: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/rse/users/<int:user_id>/reactivate', methods=['POST'])
@limiter.limit("10 per minute")
def reactivate_rse_user(user_id):
    """
    Réactive un utilisateur RSE précédemment désactivé
    """
    try:
        company_id = request.args.get('company_id', type=int)
        
        with sql.db_cursor() as cur:
            # Vérifier que l'utilisateur existe ET appartient à l'entreprise
            if company_id:
                cur.execute("SELECT id, name, email, active FROM rse_users WHERE id = %s AND company_id = %s", (user_id, company_id))
            else:
                cur.execute("SELECT id, name, email, active FROM rse_users WHERE id = %s", (user_id,))
            
            user = cur.fetchone()
            
            if not user:
                return jsonify({'error': 'Utilisateur non trouvé ou accès refusé'}), 404
            
            # Réactiver l'utilisateur
            cur.execute("UPDATE rse_users SET active = 1, updated_at = NOW() WHERE id = %s", (user_id,))
            
            logger.info(f"🔄 Utilisateur RSE réactivé: {user['email']} (ID: {user_id})")
            
            return jsonify({
                'success': True,
                'message': f"Utilisateur {user['name']} réactivé avec succès",
                'user_id': user_id,
                'email': user['email']
            }), 200
    except Exception as e:
        logger.error(f"❌ Erreur réactivation utilisateur {user_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/rse/users/unsubscribe', methods=['POST'])
def unsubscribe_rse_user():
    """
    Permet à un utilisateur de se désinscrire via le lien dans l'email
    Utilise le magic_link token pour authentifier la requête
    """
    try:
        data = request.json
        token = data.get('token')
        
        if not token:
            return jsonify({'error': 'Token manquant'}), 400
        
        with sql.db_cursor() as cur:
            # Vérifier le token et récupérer l'utilisateur
            # Le token est le même que pour les magic links (hash de user_id + email)
            cur.execute("""
                SELECT id, name, email, active 
                FROM rse_users 
                WHERE MD5(CONCAT(id, email, 'carette_magic_salt_2024')) = %s
            """, (token,))
            user = cur.fetchone()
            
            if not user:
                return jsonify({'error': 'Lien de désinscription invalide ou expiré'}), 404
            
            if not user['active']:
                return jsonify({
                    'success': True,
                    'message': 'Vous êtes déjà désinscrit',
                    'already_unsubscribed': True
                }), 200
            
            # Désactiver l'utilisateur
            cur.execute("UPDATE rse_users SET active = 0, updated_at = NOW() WHERE id = %s", (user['id'],))
            
            logger.info(f"👋 Utilisateur RSE désinscrit (self-service): {user['email']} (ID: {user['id']})")
            
            return jsonify({
                'success': True,
                'message': f"Vous avez été désinscrit avec succès",
                'user_id': user['id'],
                'email': user['email']
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Erreur désinscription utilisateur: {e}")
        return jsonify({'error': 'Erreur lors de la désinscription'}), 500


@app.route('/api/v2/rse/users/update-address', methods=['POST'])
def update_user_address():
    """
    Permet à un utilisateur de mettre à jour son adresse de domicile
    Utilise le magic_link token pour authentifier la requête
    L'historique (rse_weekly_data) reste intact
    """
    try:
        data = request.json
        token = data.get('token')
        new_address = data.get('address', '').strip()
        
        if not token:
            return jsonify({'error': 'Token manquant'}), 400
        
        if not new_address:
            return jsonify({'error': 'Adresse manquante'}), 400
        
        with sql.db_cursor() as cur:
            # Vérifier le token et récupérer l'utilisateur
            cur.execute("""
                SELECT id, name, email, departure_address, default_transport
                FROM rse_users 
                WHERE MD5(CONCAT(id, email, 'carette_magic_salt_2024')) = %s AND active = 1
            """, (token,))
            user = cur.fetchone()
            
            if not user:
                return jsonify({'error': 'Lien invalide ou compte inactif'}), 404
            
            old_address = user['departure_address']
            
            # Géocoder la nouvelle adresse
            coords = geocode_address_auto(new_address, cur)
            
            if not coords:
                return jsonify({'error': 'Impossible de géocoder cette adresse. Vérifiez la saisie.'}), 400
            
            # Mettre à jour l'adresse dans rse_users (n'affecte PAS l'historique)
            cur.execute("""
                UPDATE rse_users 
                SET departure_address = %s, updated_at = NOW()
                WHERE id = %s
            """, (new_address, user['id']))
            
            logger.info(f"🏠 Adresse mise à jour pour {user['email']}: {old_address} → {new_address}")
            
            return jsonify({
                'success': True,
                'message': 'Adresse mise à jour avec succès',
                'user_id': user['id'],
                'old_address': old_address,
                'new_address': new_address,
                'current_default_transport': user['default_transport'],
                'suggest_review': True  # Suggère de revoir les transports par défaut
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour adresse: {e}")
        return jsonify({'error': 'Erreur lors de la mise à jour'}), 500


@app.route('/api/v2/rse/users/update-transport', methods=['POST'])
def update_user_transport():
    """
    Permet à un utilisateur de mettre à jour ses moyens de transport par défaut
    """
    try:
        data = request.json
        token = data.get('token')
        transports = data.get('transports', {})  # {lundi: 'velo', mardi: 'voiture_solo', ...}
        
        if not token:
            return jsonify({'error': 'Token manquant'}), 400
        
        with sql.db_cursor() as cur:
            # Vérifier le token
            cur.execute("""
                SELECT id, name, email
                FROM rse_users 
                WHERE MD5(CONCAT(id, email, 'carette_magic_salt_2024')) = %s AND active = 1
            """, (token,))
            user = cur.fetchone()
            
            if not user:
                return jsonify({'error': 'Lien invalide ou compte inactif'}), 404
            
            # Mettre à jour le default_transport (JSON)
            cur.execute("""
                UPDATE rse_users 
                SET default_transport = %s, updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(transports), user['id']))
            
            logger.info(f"🚗 Transports par défaut mis à jour pour {user['email']}")
            
            return jsonify({
                'success': True,
                'message': 'Moyens de transport mis à jour avec succès',
                'user_id': user['id'],
                'transports': transports
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour transports: {e}")
        return jsonify({'error': 'Erreur lors de la mise à jour'}), 500


@app.route('/api/v2/rse/users/me', methods=['POST'])
def get_user_info():
    """
    Récupère les informations d'un utilisateur via son token
    """
    try:
        data = request.json
        token = data.get('token')
        
        if not token:
            return jsonify({'error': 'Token manquant'}), 400
        
        with sql.db_cursor() as cur:
            cur.execute("""
                SELECT id, name, email, departure, default_transport, active
                FROM rse_users 
                WHERE MD5(CONCAT(id, email, 'carette_magic_salt_2024')) = %s
            """, (token,))
            user = cur.fetchone()
            
            if not user:
                return jsonify({'error': 'Utilisateur non trouvé'}), 404
            
            return jsonify({
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'departure': user['departure'],
                'default_transport': user['default_transport'],
                'active': bool(user['active'])
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Erreur récupération infos utilisateur: {e}")
        return jsonify({'error': 'Erreur serveur'}), 500


# ========== GESTION DES SITES D'ENTREPRISE ==========

@app.route('/api/v2/companies/<int:company_id>/sites', methods=['GET'])
@limiter.limit("60 per minute")
def get_company_sites(company_id):
    """
    Récupère la liste des sites d'une entreprise
    """
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        
        with sql.db_cursor() as cur:
            if include_inactive:
                cur.execute("""
                    SELECT id, site_name, site_address, site_coords, active, created_at
                    FROM company_sites
                    WHERE company_id = %s
                    ORDER BY active DESC, created_at ASC
                """, (company_id,))
            else:
                cur.execute("""
                    SELECT id, site_name, site_address, site_coords, active, created_at
                    FROM company_sites
                    WHERE company_id = %s AND active = 1
                    ORDER BY created_at ASC
                """, (company_id,))
            
            sites = cur.fetchall()
            
            # Parser les coordonnées JSON
            for site in sites:
                if site['site_coords']:
                    site['site_coords'] = json.loads(site['site_coords']) if isinstance(site['site_coords'], str) else site['site_coords']
            
            return jsonify({
                'success': True,
                'sites': sites,
                'count': len(sites)
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Erreur récupération sites: {e}")
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/companies/<int:company_id>/sites', methods=['POST'])
@limiter.limit("10 per minute")
def add_company_site(company_id):
    """
    Ajoute un nouveau site à l'entreprise
    """
    try:
        data = request.json
        site_name = data.get('site_name', '').strip()
        site_address = data.get('site_address', '').strip()
        
        if not site_name or not site_address:
            return jsonify({'error': 'Nom et adresse requis'}), 400
        
        with sql.db_cursor() as cur:
            # Vérifier que l'entreprise existe
            cur.execute("SELECT id FROM companies WHERE id = %s", (company_id,))
            if not cur.fetchone():
                return jsonify({'error': 'Entreprise non trouvée'}), 404
            
            # Géocoder l'adresse
            coords = geocode_address_auto(site_address, cur)
            
            if not coords:
                return jsonify({'error': 'Impossible de géocoder cette adresse'}), 400
            
            # Insérer le site
            cur.execute("""
                INSERT INTO company_sites (company_id, site_name, site_address, site_coords)
                VALUES (%s, %s, %s, %s)
            """, (company_id, site_name, site_address, json.dumps(coords)))
            
            site_id = cur.lastrowid
            
            logger.info(f"📍 Site ajouté: {site_name} pour entreprise {company_id}")
            
            return jsonify({
                'success': True,
                'site_id': site_id,
                'site_name': site_name,
                'site_address': site_address,
                'coords': coords
            }), 201
            
    except Exception as e:
        logger.error(f"❌ Erreur ajout site: {e}")
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/companies/<int:company_id>/sites/<int:site_id>', methods=['PUT'])
@limiter.limit("10 per minute")
def update_company_site(company_id, site_id):
    """
    Modifie un site existant
    """
    try:
        data = request.json
        site_name = data.get('site_name', '').strip()
        site_address = data.get('site_address', '').strip()
        
        if not site_name or not site_address:
            return jsonify({'error': 'Nom et adresse requis'}), 400
        
        with sql.db_cursor() as cur:
            # Vérifier que le site existe et appartient à l'entreprise
            cur.execute("""
                SELECT id FROM company_sites 
                WHERE id = %s AND company_id = %s
            """, (site_id, company_id))
            
            if not cur.fetchone():
                return jsonify({'error': 'Site non trouvé'}), 404
            
            # Géocoder la nouvelle adresse
            coords = geocode_address_auto(site_address, cur)
            
            if not coords:
                return jsonify({'error': 'Impossible de géocoder cette adresse'}), 400
            
            # Mettre à jour
            cur.execute("""
                UPDATE company_sites 
                SET site_name = %s, site_address = %s, site_coords = %s
                WHERE id = %s AND company_id = %s
            """, (site_name, site_address, json.dumps(coords), site_id, company_id))
            
            logger.info(f"📍 Site modifié: {site_name} (ID: {site_id})")
            
            return jsonify({
                'success': True,
                'site_id': site_id,
                'site_name': site_name,
                'site_address': site_address,
                'coords': coords
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Erreur modification site: {e}")
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/companies/<int:company_id>/sites/<int:site_id>', methods=['DELETE'])
@limiter.limit("10 per minute")
def delete_company_site(company_id, site_id):
    """
    Désactive un site (soft delete)
    """
    try:
        with sql.db_cursor() as cur:
            # Vérifier que le site existe et appartient à l'entreprise
            cur.execute("""
                SELECT site_name, active FROM company_sites 
                WHERE id = %s AND company_id = %s
            """, (site_id, company_id))
            
            site = cur.fetchone()
            if not site:
                return jsonify({'error': 'Site non trouvé'}), 404
            
            # Désactiver (soft delete)
            cur.execute("""
                UPDATE company_sites 
                SET active = 0
                WHERE id = %s AND company_id = %s
            """, (site_id, company_id))
            
            logger.info(f"🔴 Site désactivé: {site['site_name']} (ID: {site_id})")
            
            return jsonify({
                'success': True,
                'message': f"Site {site['site_name']} désactivé"
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Erreur désactivation site: {e}")
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/v2/companies/<int:company_id>/sites/<int:site_id>/reactivate', methods=['POST'])
@limiter.limit("10 per minute")
def reactivate_company_site(company_id, site_id):
    """
    Réactive un site désactivé
    """
    try:
        with sql.db_cursor() as cur:
            # Vérifier que le site existe
            cur.execute("""
                SELECT site_name, active FROM company_sites 
                WHERE id = %s AND company_id = %s
            """, (site_id, company_id))
            
            site = cur.fetchone()
            if not site:
                return jsonify({'error': 'Site non trouvé'}), 404
            
            # Réactiver
            cur.execute("""
                UPDATE company_sites 
                SET active = 1
                WHERE id = %s AND company_id = %s
            """, (site_id, company_id))
            
            logger.info(f"🟢 Site réactivé: {site['site_name']} (ID: {site_id})")
            
            return jsonify({
                'success': True,
                'message': f"Site {site['site_name']} réactivé"
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Erreur réactivation site: {e}")
        return jsonify({'error': 'Erreur serveur'}), 500


# ========== SUPPRESSION UTILISATEUR (SOFT DELETE) ==========

@app.route('/api/v2/rse/users/<int:user_id>/delete', methods=['POST'])
@limiter.limit("10 per minute")
def delete_rse_user(user_id):
    """
    Supprime un utilisateur RSE (soft delete)
    L'historique (rse_weekly_data) reste en base
    L'utilisateur est marqué comme deleted et active=0
    """
    try:
        with sql.db_cursor() as cur:
            # Vérifier que l'utilisateur existe
            cur.execute("SELECT id, name, email, active FROM rse_users WHERE id = %s", (user_id,))
            user = cur.fetchone()
            
            if not user:
                return jsonify({'error': 'Utilisateur non trouvé'}), 404
            
            # Soft delete : marquer comme inactif
            # L'historique dans rse_weekly_data reste intact
            cur.execute("""
                UPDATE rse_users 
                SET active = 0, updated_at = NOW()
                WHERE id = %s
            """, (user_id,))
            
            logger.info(f"🗑️ Utilisateur RSE supprimé (soft): {user['email']} (ID: {user_id})")
            
            return jsonify({
                'success': True,
                'message': f"Utilisateur {user['name']} supprimé (historique conservé)",
                'user_id': user_id,
                'email': user['email']
            }), 200
            
    except Exception as e:
        logger.error(f"❌ Erreur suppression utilisateur {user_id}: {e}")
        return jsonify({'error': str(e)}), 500
