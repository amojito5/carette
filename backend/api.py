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
from temporal_buffer import create_temporal_buffer, calculate_detour_time_osrm
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
    logger.error(f"❌ Erreur initialisation tables: {e}")
    # Ne pas bloquer le démarrage si c'est juste un problème de colonnes existantes
    if "Duplicate column" not in str(e):
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
                offer = dict(zip([d[0] for d in cur.description], row))
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
            
            offer = dict(zip([d[0] for d in cur.description], row))
            
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
            
            if row[0] != user_id:
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
                res = dict(zip([d[0] for d in cur.description], row))
                for field_name in ['meeting_point_coords', 'detour_route', 'pickup_coords', 'route_segment_geometry']:
                    if res.get(json_field):
                        try:
                            res[json_field] = json.loads(res[json_field])
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
                    offer = dict(zip([d[0] for d in cur.description], row))
                    
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
                offer = dict(zip([d[0] for d in cur.description], row))
                
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
            total_offers = row[0] if row else 0
            
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
        
        # Routes (geometries)
        route_outbound = data.get('route_outbound')
        route_return = data.get('route_return')
        
        # Insérer dans la base de données
        with sql.db_cursor() as cur:
            cur.execute("""
                INSERT INTO carpool_offers_recurrent 
                (company_id, site_id, departure, destination, departure_coords, destination_coords,
                 recurrent_time, monday, tuesday, wednesday, thursday, friday, saturday, sunday,
                 seats, route_outbound, route_return, max_detour_time,
                 driver_email, driver_name, driver_phone, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')
            """, (
                company_id, site_id, departure, destination,
                json.dumps(departure_coords) if departure_coords else None,
                json.dumps(destination_coords) if destination_coords else None,
                time_outbound,
                days['monday'], days['tuesday'], days['wednesday'], days['thursday'],
                days['friday'], days['saturday'], days['sunday'],
                seats,
                json.dumps(route_outbound) if route_outbound else None,
                json.dumps(route_return) if route_return else None,
                max_detour_time,
                driver_email, driver_name, driver_phone
            ))
            
            offer_id = cur.lastrowid
        
        logger.info(f"Offre récurrente créée: ID={offer_id}, conducteur={driver_name}, company={company_id}, site={site_id}")
        
        # Récupérer les couleurs depuis le payload (définies par l'utilisateur dans le widget)
        color_outbound = data.get('color_outbound', '#7c3aed')
        color_return = data.get('color_return', '#f97316')
        
        # Normaliser les couleurs (retirer le canal alpha si présent)
        if color_outbound and len(color_outbound) == 9:  # #RRGGBBAA
            color_outbound = color_outbound[:7]  # #RRGGBB
        if color_return and len(color_return) == 9:
            color_return = color_return[:7]
        
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
                'offer_id': offer_id
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
        
        with sql.db_cursor() as cur:
            # Rechercher les offres actives pour ce site
            query = f"""
                SELECT 
                    id, company_id, site_id,
                    driver_name, driver_email, driver_phone,
                    departure, destination,
                    departure_coords, destination_coords,
                    recurrent_time,
                    monday, tuesday, wednesday, thursday, friday, saturday, sunday,
                    seats, max_detour_time,
                    route_outbound, route_return,
                    created_at, status
                FROM carpool_offers_recurrent
                WHERE site_id = %s 
                AND status = 'active'
                {day_clause}
                ORDER BY created_at DESC
                LIMIT 50
            """
            
            cur.execute(query, (site_id,))
            rows = cur.fetchall()
        
        # Colonnes dans l'ordre du SELECT
        columns = ['id', 'company_id', 'site_id', 'driver_name', 'driver_email', 'driver_phone',
                   'departure', 'destination', 'departure_coords', 'destination_coords',
                   'recurrent_time',
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
            route_outbound = json.loads(row_dict['route_outbound']) if row_dict['route_outbound'] else None
            route_return = json.loads(row_dict['route_return']) if row_dict['route_return'] else None
            
            # Vérifier si le point utilisateur est compatible (dans la zone de détour)
            max_detour_time = row_dict['max_detour_time'] or 25  # 25 min par défaut
            is_compatible = False
            compatible_direction = None
            detour_time = None
            
            # Vérifier l'aller (domicile → bureau)
            if route_outbound and len(route_outbound) >= 2:
                try:
                    start = route_outbound[0]  # Départ conducteur
                    end = route_outbound[-1]   # Arrivée (bureau)
                    
                    # Calculer le temps de détour si le conducteur passe prendre l'utilisateur
                    detour = calculate_detour_time_osrm(start, user_point, end)
                    
                    if detour is not None and detour <= max_detour_time:
                        is_compatible = True
                        compatible_direction = 'outbound'
                        detour_time = detour
                        logger.info(f"✅ Offre {row_dict['id']} compatible (aller): détour {detour:.1f} min")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur calcul détour aller pour offre {row_dict['id']}: {e}")
            
            # Vérifier le retour (bureau → domicile) si pas déjà compatible
            if not is_compatible and route_return and len(route_return) >= 2:
                try:
                    start = route_return[0]  # Départ bureau
                    end = route_return[-1]   # Arrivée domicile conducteur
                    
                    # Calculer le temps de détour
                    detour = calculate_detour_time_osrm(start, user_point, end)
                    
                    if detour is not None and detour <= max_detour_time:
                        is_compatible = True
                        compatible_direction = 'return'
                        detour_time = detour
                        logger.info(f"✅ Offre {row_dict['id']} compatible (retour): détour {detour:.1f} min")
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
                'days': active_days,
                'seats': row_dict['seats'],
                'max_detour_time': row_dict['max_detour_time'],
                'route_outbound': route_outbound,
                'route_return': route_return,
                'created_at': row_dict['created_at'].strftime('%Y-%m-%d %H:%M:%S') if row_dict['created_at'] else None,
                'compatible_direction': compatible_direction,
                'detour_time_minutes': round(detour_time, 1) if detour_time else None
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
            count = result[0] if result else 0
        
        return jsonify({'count': count}), 200
        
    except Exception as e:
        logger.error(f"Error in count_recurrent_offers: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erreur serveur'}), 500



