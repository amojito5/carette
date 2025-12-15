"""
Carette - API backend autonome pour le widget de covoiturage
Extraction des endpoints carpool de l'API principale
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import requests
from pymysql.err import IntegrityError
import json
import math
import sys
import os

# Ajouter le dossier backend au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import des modules DB et buffer géographique
import sql
from route_buffer import create_buffer_from_route, create_buffer_simple
from temporal_buffer import create_temporal_buffer

app = Flask(__name__)

# CORS pour permettre l'intégration cross-origin
CORS(
    app,
    resources={r"/api/*": {"origins": "*"}},
    supports_credentials=True
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
                params['alternatives'] = 'true'
                params['number'] = '3'
            
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
    
    return jsonify(result)


@app.route("/api/carpool", methods=["POST"])
def create_offer():
    """Créer une nouvelle offre de covoiturage"""
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({"error": "user_id requis"}), 400
    
    try:
        with sql.db_cursor() as cur:
            # Préparer les données
            offer_data = {
                'user_id': user_id,
                'departure': data.get('departure', ''),
                'destination': data.get('destination', ''),
                'datetime': data.get('datetime'),
                'seats': data.get('seats', 1),
                'comment': data.get('comment', ''),
                'details': json.dumps(data.get('details', {})),
                'accept_passengers_on_route': data.get('accept_passengers_on_route', True),
                'seats_outbound': data.get('seats_outbound'),
                'seats_return': data.get('seats_return'),
                'route_outbound': json.dumps(data.get('route_outbound')) if data.get('route_outbound') else None,
                'route_return': json.dumps(data.get('route_return')) if data.get('route_return') else None,
                'max_detour_km': data.get('max_detour_km', 5),
                'max_detour_time': data.get('max_detour_time', 25),
                'return_datetime': data.get('return_datetime'),
                'event_id': data.get('event_id', ''),
                'event_name': data.get('event_name', ''),
                'event_location': data.get('event_location', ''),
                'event_date': data.get('event_date'),
                'event_time': data.get('event_time', ''),
                'referring_site': data.get('referring_site', ''),
                'page_url': data.get('page_url', '')
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
            
            # Insertion
            columns = ', '.join(offer_data.keys())
            placeholders = ', '.join(['%s'] * len(offer_data))
            
            cur.execute(
                f"INSERT INTO carpool_offers ({columns}) VALUES ({placeholders})",
                list(offer_data.values())
            )
            
            offer_id = cur.lastrowid
            
        return jsonify({"success": True, "offer_id": offer_id}), 201
    
    except Exception as e:
        print(f"❌ Error creating offer: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/carpool", methods=["GET"])
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
                for json_field in ['details', 'route_outbound', 'route_return', 'detour_zone_outbound', 'detour_zone_return']:
                    if offer.get(json_field):
                        try:
                            offer[json_field] = json.loads(offer[json_field])
                        except:
                            pass
                offers.append(offer)
        
        return jsonify({"offers": offers})
    
    except Exception as e:
        print(f"❌ Error fetching offers: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/carpool/<int:offer_id>', methods=['GET'])
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
            for json_field in ['details', 'route_outbound', 'route_return', 'detour_zone_outbound', 'detour_zone_return', 'current_route_geometry']:
                if offer.get(json_field):
                    try:
                        offer[json_field] = json.loads(offer[json_field])
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
                for json_field in ['meeting_point_coords', 'detour_route', 'pickup_coords', 'route_segment_geometry']:
                    if res.get(json_field):
                        try:
                            res[json_field] = json.loads(res[json_field])
                        except:
                            pass
                reservations.append(res)
            
            offer['reservations'] = reservations
        
        return jsonify(offer)
    
    except Exception as e:
        print(f"❌ Error fetching offer: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/carpool/<int:offer_id>', methods=['DELETE'])
def delete_offer(offer_id):
    """Supprimer une offre (seulement par son créateur)"""
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({"error": "user_id requis"}), 400
    
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
    
    except Exception as e:
        print(f"❌ Error deleting offer: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/carpool/reserve', methods=['POST'])
def create_reservation():
    """Créer une réservation pour une offre"""
    data = request.json
    
    required = ['offer_id', 'passenger_user_id', 'trip_type']
    if not all(k in data for k in required):
        return jsonify({"error": f"Champs requis: {required}"}), 400
    
    try:
        with sql.db_cursor() as cur:
            # Vérifier que l'offre existe
            cur.execute("SELECT id FROM carpool_offers WHERE id = %s", (data['offer_id'],))
            if not cur.fetchone():
                return jsonify({"error": "Offre non trouvée"}), 404
            
            # Préparer données réservation
            res_data = {
                'offer_id': data['offer_id'],
                'passenger_user_id': data['passenger_user_id'],
                'passengers': data.get('passengers', 1),
                'trip_type': data['trip_type'],
                'meeting_point_coords': json.dumps(data.get('meeting_point_coords')) if data.get('meeting_point_coords') else None,
                'meeting_point_address': data.get('meeting_point_address', ''),
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
        return jsonify({"error": str(e)}), 500
    
    except Exception as e:
        print(f"❌ Error creating reservation: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/carpool/reservations', methods=['GET'])
def get_my_reservations():
    """Récupérer les réservations d'un utilisateur"""
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({"error": "user_id requis"}), 400
    
    try:
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
                for json_field in ['meeting_point_coords', 'detour_route', 'pickup_coords', 'route_segment_geometry']:
                    if res.get(json_field):
                        try:
                            res[json_field] = json.loads(res[json_field])
                        except:
                            pass
                reservations.append(res)
        
        return jsonify({"reservations": reservations})
    
    except Exception as e:
        print(f"❌ Error fetching reservations: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/carpool/search', methods=['GET'])
def search_offers():
    """
    Recherche spatiale d'offres compatibles avec un trajet passager
    Utilise les zones de détour et la géométrie des routes
    """
    try:
        # Paramètres de recherche
        start_lon = float(request.args.get('start_lon', 0))
        start_lat = float(request.args.get('start_lat', 0))
        end_lon = float(request.args.get('end_lon', 0))
        end_lat = float(request.args.get('end_lat', 0))
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
    
    except Exception as e:
        print(f"❌ Error searching offers: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Initialiser les tables au démarrage
    try:
        from init_carpool_tables import init_carpool_tables
        init_carpool_tables()
    except Exception as e:
        print(f"⚠️ Warning: Could not init tables: {e}")
    
    app.run(host='0.0.0.0', port=5001, debug=True)
