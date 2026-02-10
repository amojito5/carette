"""
Carette - Adaptateur API v1 → v2
Permet au widget existant de fonctionner avec le nouveau workflow email/WhatsApp
"""
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import os
import sys
from datetime import datetime
import json

# Import des modules v2
from api_v2 import app as app_v2
from sql_v2 import db_cursor
from emails import (
    email_new_reservation_to_driver,
    email_reservation_confirmed_to_passenger,
    email_payment_simulation,
    generate_confirmation_token
)

# Créer l'app adaptateur
app = Flask(__name__)
app.config.from_object(app_v2.config)

# Même CORS que v2
CORS(app, origins=os.getenv('ALLOWED_ORIGINS', 'http://localhost:8080').split(','))


# ============================================
# ADAPTATEURS - Conversion v1 ↔ v2
# ============================================

def user_id_to_email_phone(user_id):
    """
    Convertir un user_id (email simulé) en email + phone
    Format attendu : email@example.com ou email|phone
    """
    if '|' in user_id:
        email, phone = user_id.split('|', 1)
        return email, phone
    else:
        # Si juste email, générer un téléphone fictif
        return user_id, '0600000000'


def offer_v2_to_v1(offer_v2):
    """Convertir une offre v2 (email/phone) en format v1 (user_id)"""
    return {
        'id': offer_v2[0],
        'user_id': offer_v2[1],  # driver_email devient user_id
        'departure': offer_v2[4],
        'destination': offer_v2[5],
        'datetime': offer_v2[8].strftime('%Y-%m-%d %H:%M:%S') if offer_v2[8] else None,
        'seats': offer_v2[9],
        'seats_outbound': offer_v2[9],  # Même valeur pour compatibilité
        'seats_return': 0,
        'event_id': offer_v2[11],
        'event_name': offer_v2[12],
        'event_location': offer_v2[13],
        'event_date': offer_v2[14].strftime('%Y-%m-%d') if offer_v2[14] else None,
        'created_at': offer_v2[15].strftime('%Y-%m-%d %H:%M:%S') if offer_v2[15] else None,
        'status': offer_v2[10],
        # Champs supplémentaires pour compatibilité
        '_driver_phone': offer_v2[2],
        '_driver_name': offer_v2[3]
    }


# ============================================
# ENDPOINTS COMPATIBLES V1
# ============================================

@app.route('/api/carpool', methods=['POST'])
def create_offer_compat():
    """
    Endpoint compatible v1 : POST /api/carpool
    Convertit vers v2 : email + phone au lieu de user_id
    """
    data = request.json
    
    # Extraire email et téléphone depuis user_id
    user_id = data.get('user_id', '')
    driver_email, driver_phone = user_id_to_email_phone(user_id)
    
    # Préparer les données v2
    v2_data = {
        'driver_email': driver_email,
        'driver_phone': driver_phone,
        'driver_name': data.get('driver_name', ''),
        'departure': data.get('departure'),
        'destination': data.get('destination'),
        'datetime': data.get('datetime'),
        'seats_available': data.get('seats', 1),
        'event_id': data.get('event_id'),
        'event_name': data.get('event_name'),
        'event_location': data.get('event_location'),
        'event_date': data.get('event_date')
    }
    
    # Appeler l'API v2
    with app_v2.test_request_context('/api/v2/offers', method='POST', json=v2_data):
        from api_v2 import create_offer as create_offer_v2
        response = create_offer_v2()
        return response


@app.route('/api/carpool', methods=['GET'])
def get_offers_compat():
    """
    Endpoint compatible v1 : GET /api/carpool
    Récupère les offres v2 et les convertit au format v1
    """
    departure = request.args.get('departure', '')
    destination = request.args.get('destination', '')
    date = request.args.get('date')
    event_id = request.args.get('event_id')
    
    try:
        with db_cursor() as cur:
            query = """
                SELECT id, driver_email, driver_phone, driver_name,
                       departure, destination, departure_coords, destination_coords,
                       datetime, seats_available, status,
                       event_id, event_name, event_location, event_date,
                       created_at
                FROM carpool_offers_v2
                WHERE status = 'active'
                  AND datetime > NOW()
                  AND seats_available > 0
            """
            params = []
            
            if departure:
                query += " AND departure LIKE %s"
                params.append(f"%{departure}%")
            
            if destination:
                query += " AND destination LIKE %s"
                params.append(f"%{destination}%")
            
            if date:
                query += " AND DATE(datetime) = %s"
                params.append(date)
            
            if event_id:
                query += " AND event_id = %s"
                params.append(event_id)
            
            query += " ORDER BY datetime ASC LIMIT 50"
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            # Convertir au format v1
            offers = [offer_v2_to_v1(row) for row in rows]
            
            return jsonify(offers), 200
            
    except Exception as e:
        print(f"Erreur get_offers_compat: {e}")
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/carpool/reserve', methods=['POST'])
def reserve_offer_compat():
    """
    Endpoint compatible v1 : POST /api/carpool/reserve
    Avec workflow email/WhatsApp automatique
    """
    data = request.json
    
    offer_id = data.get('offer_id')
    user_id = data.get('user_id', '')
    passengers = data.get('passengers', 1)
    trip_type = data.get('trip_type', 'outbound')
    
    # Extraire email et téléphone
    passenger_email, passenger_phone = user_id_to_email_phone(user_id)
    
    try:
        # Récupérer l'offre
        with db_cursor() as cur:
            cur.execute("""
                SELECT id, driver_email, driver_name, driver_phone,
                       departure, destination, datetime, seats_available
                FROM carpool_offers_v2
                WHERE id = %s AND status = 'active' AND seats_available >= %s
            """, (offer_id, passengers))
            
            offer = cur.fetchone()
            if not offer:
                return jsonify({'error': 'Offre non disponible'}), 404
            
            # Vérifier doublon
            cur.execute("""
                SELECT id FROM carpool_reservations_v2
                WHERE offer_id = %s AND passenger_email = %s AND status != 'cancelled'
            """, (offer_id, passenger_email))
            
            if cur.fetchone():
                return jsonify({'error': 'Réservation déjà existante'}), 400
            
            # Créer la réservation avec simulation paiement
            cur.execute("""
                INSERT INTO carpool_reservations_v2
                (offer_id, passenger_email, passenger_name, passenger_phone, 
                 passengers_count, payment_status)
                VALUES (%s, %s, %s, %s, %s, 'simulated')
            """, (offer_id, passenger_email, '', passenger_phone, passengers))
            
            reservation_id = cur.lastrowid
            
            # Générer les tokens de confirmation
            accept_token = generate_confirmation_token()
            reject_token = generate_confirmation_token()
            expires_at = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            
            cur.execute("""
                INSERT INTO confirmation_tokens (token, reservation_id, action, expires_at)
                VALUES (%s, %s, 'accept', %s), (%s, %s, 'reject', %s)
            """, (accept_token, reservation_id, expires_at,
                  reject_token, reservation_id, expires_at))
        
        # Envoyer les emails
        from datetime import timedelta
        offer_details = {
            'departure': offer[4],
            'destination': offer[5],
            'datetime': offer[6].strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Email au conducteur
        email_new_reservation_to_driver(
            driver_email=offer[1],
            driver_name=offer[2] or 'Conducteur',
            passenger_name='Passager',
            passenger_email=passenger_email,
            passenger_phone=passenger_phone,
            offer_details=offer_details,
            accept_token=accept_token,
            reject_token=reject_token
        )
        
        # Email au passager
        email_payment_simulation(
            passenger_email=passenger_email,
            passenger_name='Passager',
            offer_details=offer_details
        )
        
        return jsonify({
            'success': True,
            'message': 'Réservation créée',
            'reservation_id': reservation_id
        }), 201
        
    except Exception as e:
        print(f"Erreur reserve_offer_compat: {e}")
        return jsonify({'error': 'Erreur serveur'}), 500


@app.route('/api/carpool/reservations', methods=['GET'])
def get_reservations_compat():
    """
    Endpoint compatible v1 : GET /api/carpool/reservations
    """
    user_id = request.args.get('user_id', '')
    passenger_email, _ = user_id_to_email_phone(user_id)
    
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT r.id, r.offer_id, r.passenger_email, r.status,
                       o.departure, o.destination, o.datetime
                FROM carpool_reservations_v2 r
                JOIN carpool_offers_v2 o ON r.offer_id = o.id
                WHERE r.passenger_email = %s
                ORDER BY o.datetime DESC
            """, (passenger_email,))
            
            rows = cur.fetchall()
            
            reservations = [{
                'id': row['id'],
                'offer_id': row['offer_id'],
                'user_id': row['passenger_email'],
                'status': row['status'],
                'departure': row['departure'],
                'destination': row['destination'],
                'datetime': row['datetime'].strftime('%Y-%m-%d %H:%M:%S') if row['datetime'] else None,
                'trip_type': 'outbound'  # Compatibilité
            } for row in rows]
            
            return jsonify(reservations), 200
            
    except Exception as e:
        print(f"Erreur get_reservations_compat: {e}")
        return jsonify([]), 200


@app.route('/api/carpool/mine', methods=['GET'])
def get_my_offers_compat():
    """
    Endpoint compatible v1 : GET /api/carpool/mine
    """
    user_id = request.args.get('user_id', '')
    driver_email, _ = user_id_to_email_phone(user_id)
    
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT id, driver_email, driver_phone, driver_name,
                       departure, destination, departure_coords, destination_coords,
                       datetime, seats_available, status,
                       event_id, event_name, event_location, event_date,
                       created_at
                FROM carpool_offers_v2
                WHERE driver_email = %s
                ORDER BY datetime DESC
            """, (driver_email,))
            
            rows = cur.fetchall()
            offers = [offer_v2_to_v1(row) for row in rows]
            
            return jsonify(offers), 200
            
    except Exception as e:
        print(f"Erreur get_my_offers_compat: {e}")
        return jsonify([]), 200


# ============================================
# PROXIES POUR ENDPOINTS NON MODIFIÉS
# ============================================

@app.route('/api/geocode/search', methods=['GET'])
def geocode_search():
    """Proxy vers l'ancien endpoint de géocodage"""
    # Rediriger vers l'API v1 existante (backend/api.py)
    # Ou implémenter ici si besoin
    query = request.args.get('q', '')
    limit = request.args.get('limit', 5)
    
    # Pour l'instant, retourner une réponse vide
    # À implémenter selon vos besoins
    return jsonify([]), 200


@app.route('/api/carpool/calculate-route', methods=['POST'])
def calculate_route():
    """Proxy vers l'ancien endpoint de calcul de route"""
    # Rediriger vers l'API v1 existante
    return jsonify({'routes': []}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
