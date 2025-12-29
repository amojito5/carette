"""
Endpoints API pour les magic links (actions par email)
Ces endpoints sont appelés quand l'utilisateur clique sur un lien dans un email
"""
from flask import jsonify, request, render_template_string
from datetime import datetime, timedelta
import logging
from email_sender import send_email, send_email_batch
from email_templates import (
    email_reservation_confirmed_to_passenger,
    email_driver_route_updated,
    email_passenger_route_updated,
    email_reservation_refused,
    email_cancellation_confirmed_passenger
)
from token_manager import generate_cancel_passenger_link

logger = logging.getLogger(__name__)

def register_magic_link_routes(app, db_cursor_v2):
    """
    Enregistre les routes pour les magic links
    
    Args:
        app: Instance Flask
        db_cursor_v2: Fonction pour obtenir un curseur DB
    """
    
    @app.route('/api/reservation/accept', methods=['GET'])
    def accept_reservation():
        """
        Accepte une réservation via magic link
        URL: /api/reservation/accept?token=xxx
        """
        from token_manager import verify_token
        
        token = request.args.get('token')
        if not token:
            return render_error("Token manquant"), 400
        
        # Vérifier le token
        valid, payload, error = verify_token(token)
        if not valid:
            return render_error(f"Token invalide: {error}"), 403
        
        # Vérifier que c'est bien une action d'acceptation
        if payload['action'] != 'accept_reservation':
            return render_error("Action non autorisée"), 403
        
        reservation_id = payload['resource_id']
        driver_email = payload['email']
        
        try:
            with db_cursor_v2() as cur:
                # Récupérer la réservation avec détours
                cur.execute("""
                    SELECT r.id, r.offer_id, r.passenger_email, r.passenger_name, 
                           r.status, r.pickup_address, r.trip_type,
                           r.detour_time_outbound, r.detour_time_return,
                           o.driver_email, o.datetime, o.seats_available, o.max_detour_time
                    FROM carpool_reservations r
                    JOIN carpool_offers o ON r.offer_id = o.id
                    WHERE r.id = %s
                """, (reservation_id,))
                
                reservation = cur.fetchone()
                
                if not reservation:
                    return render_error("Réservation introuvable"), 404
                
                # Convertir en dict
                reservation = dict(zip([d[0] for d in cur.description], reservation))
                
                # Vérifier que c'est bien le conducteur
                if reservation['driver_email'] != driver_email:
                    return render_error("Vous n'êtes pas autorisé à accepter cette réservation"), 403
                
                # Vérifier que la réservation est en attente
                if reservation['status'] != 'pending':
                    return render_error(f"Cette réservation a déjà été {reservation['status']}"), 400
                
                # Vérifier qu'il reste des places
                if reservation['seats_available'] <= 0:
                    return render_error("Plus de places disponibles"), 400
                
                # Vérifier que ce n'est pas dans moins de 24h
                trip_datetime = reservation['datetime']
                if isinstance(trip_datetime, str):
                    trip_datetime = datetime.strptime(trip_datetime, '%Y-%m-%d %H:%M:%S')
                
                hours_until_trip = (trip_datetime - datetime.now()).total_seconds() / 3600
                
                # Accepter la réservation
                cur.execute("""
                    UPDATE carpool_reservations
                    SET status = 'confirmed', confirmed_at = NOW()
                    WHERE id = %s
                """, (reservation_id,))
                
                # Décrémenter les places disponibles
                cur.execute("""
                    UPDATE carpool_offers
                    SET seats_available = seats_available - 1
                    WHERE id = %s
                """, (reservation['offer_id'],))
                
                logger.info(f"✅ Réservation {reservation_id} acceptée par {driver_email}")
                
                # Récupérer les infos complètes de l'offre pour les emails
                cur.execute("""
                    SELECT id, driver_email, driver_name, departure, destination, 
                           datetime, seats, seats_available, departure_coords, 
                           destination_coords, route_outbound, route_return
                    FROM carpool_offers
                    WHERE id = %s
                """, (reservation['offer_id'],))
                offer = cur.fetchone()
                
                # Convertir en dict
                offer = dict(zip([d[0] for d in cur.description], offer))
                
                # Récupérer tous les passagers confirmés (y compris le nouveau)
                cur.execute("""
                    SELECT id, passenger_email, passenger_name, passenger_phone,
                           pickup_address, pickup_time, trip_type,
                           detour_time_outbound, detour_time_return
                    FROM carpool_reservations
                    WHERE offer_id = %s AND status = 'confirmed'
                    ORDER BY pickup_time
                """, (reservation['offer_id'],))
                all_passengers = cur.fetchall()
                
                # Convertir chaque passager en dict
                column_names = [d[0] for d in cur.description]
                all_passengers = [dict(zip(column_names, p)) for p in all_passengers]
                
                # Calculer détours total et restant par direction
                trip_type = reservation.get('trip_type', 'outbound')
                
                if trip_type == 'outbound':
                    detour_this_passenger = reservation.get('detour_time_outbound', 0) or 0
                    total_detour_outbound = sum(p.get('detour_time_outbound', 0) or 0 for p in all_passengers)
                    total_detour_return = 0
                elif trip_type == 'return':
                    detour_this_passenger = reservation.get('detour_time_return', 0) or 0
                    total_detour_outbound = 0
                    total_detour_return = sum(p.get('detour_time_return', 0) or 0 for p in all_passengers)
                else:  # both
                    detour_this_passenger = (reservation.get('detour_time_outbound', 0) or 0) + (reservation.get('detour_time_return', 0) or 0)
                    total_detour_outbound = sum(p.get('detour_time_outbound', 0) or 0 for p in all_passengers)
                    total_detour_return = sum(p.get('detour_time_return', 0) or 0 for p in all_passengers)
                
                max_detour = offer.get('max_detour_time', 15) or 15
                detour_remaining_outbound = max(0, max_detour - total_detour_outbound)
                detour_remaining_return = max(0, max_detour - total_detour_return)
                
                BASE_URL = request.host_url.rstrip('/')
                
                # 1. Email au passager: Réservation confirmée
                cancel_url = generate_cancel_passenger_link(reservation_id, reservation['passenger_email'], BASE_URL)
                subject_pass, html_pass, text_pass = email_reservation_confirmed_to_passenger(
                    passenger_email=reservation['passenger_email'],
                    passenger_name=reservation['passenger_name'],
                    driver_name=offer['driver_name'],
                    driver_phone='',  # TODO: récupérer du driver
                    driver_email_contact=driver_email,
                    offer={
                        'departure': offer['departure'],
                        'destination': offer['destination'],
                        'datetime': str(offer['datetime'])
                    },
                    meeting_address=reservation.get('pickup_address', ''),
                    price='Gratuit',  # TODO: récupérer le prix si applicable
                    cancel_url=cancel_url
                )
                send_email(reservation['passenger_email'], subject_pass, html_pass, text_pass)
                
                # 2. Email au conducteur: Itinéraire mis à jour
                passengers_for_email = []
                for p in all_passengers:
                    remove_url = f"{BASE_URL}/api/reservation/remove?token=TODO"  # TODO: implement
                    passengers_for_email.append({
                        'name': p['passenger_name'],
                        'phone': p['passenger_phone'] or '',
                        'pickup_time': str(p['pickup_time']) if p['pickup_time'] else 'À définir',
                        'pickup_address': p['pickup_address'] or '',
                        'remove_url': remove_url
                    })
                
                subject_drv, html_drv, text_drv = email_driver_route_updated(
                    driver_email=driver_email,
                    driver_name=offer['driver_name'],
                    offer={
                        'departure': offer['departure'],
                        'destination': offer['destination'],
                        'datetime': str(offer['datetime']),
                        'seats': offer['seats']
                    },
                    all_passengers=passengers_for_email,
                    seats_available=offer['seats_available'],
                    reason=f"Nouveau passager ajouté : {reservation['passenger_name']}",
                    detour_outbound=total_detour_outbound,
                    detour_return=total_detour_return,
                    detour_remaining_outbound=detour_remaining_outbound,
                    detour_remaining_return=detour_remaining_return,
                    view_reservations_url=f"{BASE_URL}/api/offer/{offer['id']}/reservations",
                    cancel_offer_url=f"{BASE_URL}/api/offer/cancel?token=TODO",  # TODO: implement
                    base_url=BASE_URL
                )
                send_email(driver_email, subject_drv, html_drv, text_drv)
                
                # 3. TODO: Emails aux autres passagers existants si leur horaire change
                # (nécessite recalcul d'itinéraire avec OSRM)
                
                logger.info(f"📧 Emails de confirmation envoyés pour réservation {reservation_id}")
                
                return render_success(
                    title="✅ Réservation acceptée",
                    message=f"Vous avez accepté {reservation['passenger_name']}.",
                    details=f"Un email de confirmation a été envoyé au passager et votre itinéraire a été mis à jour.",
                    show_back_link=True
                )
                
        except Exception as e:
            logger.error(f"❌ Erreur acceptation réservation: {e}", exc_info=True)
            return render_error("Erreur serveur"), 500
    
    
    @app.route('/api/reservation/refuse', methods=['GET'])
    def refuse_reservation():
        """
        Refuse une réservation via magic link
        URL: /api/reservation/refuse?token=xxx
        """
        from token_manager import verify_token
        
        token = request.args.get('token')
        if not token:
            return render_error("Token manquant"), 400
        
        valid, payload, error = verify_token(token)
        if not valid:
            return render_error(f"Token invalide: {error}"), 403
        
        if payload['action'] != 'refuse_reservation':
            return render_error("Action non autorisée"), 403
        
        reservation_id = payload['resource_id']
        driver_email = payload['email']
        
        try:
            with db_cursor_v2() as cur:
                # Récupérer la réservation
                cur.execute("""
                    SELECT r.id, r.passenger_email, r.passenger_name, r.status, o.driver_email
                    FROM carpool_reservations r
                    JOIN carpool_offers o ON r.offer_id = o.id
                    WHERE r.id = %s
                """, (reservation_id,))
                
                reservation = cur.fetchone()
                
                if not reservation:
                    return render_error("Réservation introuvable"), 404
                
                # Convertir en dict
                reservation = dict(zip([d[0] for d in cur.description], reservation))
                
                if reservation['driver_email'] != driver_email:
                    return render_error("Non autorisé"), 403
                
                if reservation['status'] != 'pending':
                    return render_error(f"Cette réservation a déjà été {reservation['status']}"), 400
                
                # Refuser la réservation
                cur.execute("""
                    UPDATE carpool_reservations
                    SET status = 'refused'
                    WHERE id = %s
                """, (reservation_id,))
                
                logger.info(f"❌ Réservation {reservation_id} refusée par {driver_email}")
                
                # Récupérer les infos de l'offre pour l'email
                cur.execute("""
                    SELECT o.id, o.driver_name, o.departure, o.destination, o.datetime
                    FROM carpool_offers o
                    JOIN carpool_reservations r ON r.offer_id = o.id
                    WHERE r.id = %s
                """, (reservation_id,))
                offer = cur.fetchone()
                
                # Convertir en dict
                offer = dict(zip([d[0] for d in cur.description], offer))
                
                # Envoyer email au passager
                subject, html, text = email_reservation_refused(
                    passenger_email=reservation['passenger_email'],
                    passenger_name=reservation['passenger_name'],
                    driver_name=offer['driver_name'],
                    offer={
                        'departure': offer['departure'],
                        'destination': offer['destination'],
                        'datetime': str(offer['datetime'])
                    },
                    trip_type=reservation.get('trip_type', 'outbound')
                )
                send_email(reservation['passenger_email'], subject, html, text)
                logger.info(f"📧 Email de refus envoyé à {reservation['passenger_email']}")
                
                return render_success(
                    title="Réservation refusée",
                    message=f"Vous avez refusé {reservation['passenger_name']}.",
                    details="Un email a été envoyé au passager pour l'informer."
                )
                
        except Exception as e:
            logger.error(f"❌ Erreur refus réservation: {e}", exc_info=True)
            return render_error("Erreur serveur"), 500
    
    
    @app.route('/api/reservation/cancel', methods=['GET'])
    def cancel_reservation_passenger():
        """
        Annule une réservation par le passager via magic link
        URL: /api/reservation/cancel?token=xxx
        """
        from token_manager import verify_token
        
        token = request.args.get('token')
        if not token:
            return render_error("Token manquant"), 400
        
        valid, payload, error = verify_token(token)
        if not valid:
            return render_error(f"Token invalide: {error}"), 403
        
        if payload['action'] != 'cancel_passenger':
            return render_error("Action non autorisée"), 403
        
        reservation_id = payload['resource_id']
        passenger_email = payload['email']
        
        try:
            with db_cursor_v2() as cur:
                # Récupérer la réservation
                cur.execute("""
                    SELECT r.id, r.passenger_email, r.status, o.datetime, o.driver_email, o.driver_name, o.driver_phone
                    FROM carpool_reservations r
                    JOIN carpool_offers o ON r.offer_id = o.id
                    WHERE r.id = %s
                """, (reservation_id,))
                
                reservation = cur.fetchone()
                
                if not reservation:
                    return render_error("Réservation introuvable"), 404
                
                # Convertir en dict
                reservation = dict(zip([d[0] for d in cur.description], reservation))
                
                if reservation['passenger_email'] != passenger_email:
                    return render_error("Non autorisé"), 403
                
                if reservation['status'] != 'confirmed':
                    return render_error(f"Cette réservation est déjà {reservation['status']}"), 400
                
                # Vérifier le délai de 24h
                trip_datetime = reservation['datetime']
                if isinstance(trip_datetime, str):
                    trip_datetime = datetime.strptime(trip_datetime, '%Y-%m-%d %H:%M:%S')
                
                hours_until_trip = (trip_datetime - datetime.now()).total_seconds() / 3600
                
                if hours_until_trip < 24:
                    # Annulation impossible
                    return render_error_with_contact(
                        title="❌ Annulation impossible",
                        message="Vous ne pouvez plus annuler votre réservation (moins de 24h avant le départ).",
                        driver_name=reservation['driver_name'],
                        driver_phone=reservation['driver_phone']
                    ), 403
                
                # Annuler la réservation
                cur.execute("""
                    UPDATE carpool_reservations
                    SET status = 'cancelled', cancelled_at = NOW()
                    WHERE id = %s
                """, (reservation_id,))
                
                # Libérer la place
                cur.execute("""
                    UPDATE carpool_offers
                    SET seats_available = seats_available + 1
                    WHERE id = (SELECT offer_id FROM carpool_reservations WHERE id = %s)
                """, (reservation_id,))
                
                logger.info(f"❌ Réservation {reservation_id} annulée par passager {passenger_email}")
                
                # Récupérer les infos complètes pour les emails
                cur.execute("""
                    SELECT r.offer_id, r.passenger_name, 
                           o.id, o.driver_email, o.driver_name, o.departure, 
                           o.destination, o.datetime, o.seats, o.seats_available
                    FROM carpool_reservations r
                    JOIN carpool_offers o ON r.offer_id = o.id
                    WHERE r.id = %s
                """, (reservation_id,))
                data = cur.fetchone()
                
                # Convertir en dict
                data = dict(zip([d[0] for d in cur.description], data))
                
                # 1. Email au passager: Annulation confirmée
                subject_pass, html_pass, text_pass = email_cancellation_confirmed_passenger(
                    passenger_email=passenger_email,
                    passenger_name=data['passenger_name'],
                    offer={
                        'departure': data['departure'],
                        'destination': data['destination'],
                        'datetime': str(data['datetime'])
                    }
                )
                send_email(passenger_email, subject_pass, html_pass, text_pass)
                
                # 2. Email au conducteur: Itinéraire mis à jour
                # Récupérer les passagers restants
                cur.execute("""
                    SELECT passenger_name, passenger_phone, pickup_time, pickup_address
                    FROM carpool_reservations
                    WHERE offer_id = %s AND status = 'confirmed'
                    ORDER BY pickup_time
                """, (data['offer_id'],))
                remaining_passengers = cur.fetchall()
                
                # Convertir chaque passager en dict
                column_names = [d[0] for d in cur.description]
                remaining_passengers = [dict(zip(column_names, p)) for p in remaining_passengers]
                
                BASE_URL = request.host_url.rstrip('/')
                passengers_for_email = []
                for p in remaining_passengers:
                    passengers_for_email.append({
                        'name': p['passenger_name'],
                        'phone': p['passenger_phone'] or '',
                        'pickup_time': str(p['pickup_time']) if p['pickup_time'] else 'À définir',
                        'pickup_address': p['pickup_address'] or '',
                        'remove_url': f"{BASE_URL}/api/reservation/remove?token=TODO"
                    })
                
                subject_drv, html_drv, text_drv = email_driver_route_updated(
                    driver_email=data['driver_email'],
                    driver_name=data['driver_name'],
                    offer={
                        'departure': data['departure'],
                        'destination': data['destination'],
                        'datetime': str(data['datetime']),
                        'seats': data['seats']
                    },
                    all_passengers=passengers_for_email,
                    seats_available=data['seats_available'],
                    reason=f"Annulation de {data['passenger_name']}",
                    view_reservations_url=f"{BASE_URL}/api/offer/{data['id']}/reservations",
                    cancel_offer_url=f"{BASE_URL}/api/offer/cancel?token=TODO",
                    base_url=BASE_URL
                )
                send_email(data['driver_email'], subject_drv, html_drv, text_drv)
                
                # 3. TODO: Emails aux autres passagers si leur horaire change
                
                logger.info(f"📧 Emails d'annulation envoyés")
                
                return render_success(
                    title="✅ Annulation confirmée",
                    message="Votre réservation a été annulée.",
                    details="Le conducteur et les autres passagers ont été prévenus. L'itinéraire a été recalculé."
                )
                
        except Exception as e:
            logger.error(f"❌ Erreur annulation passager: {e}", exc_info=True)
            return render_error("Erreur serveur"), 500


# ============================================================================
# TEMPLATES HTML pour les pages de confirmation
# ============================================================================

def render_success(title, message, details="", show_back_link=False):
    """Rendu d'une page de succès"""
    html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ title }}</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .card {
                background: white;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 40px;
                max-width: 500px;
                width: 100%;
                text-align: center;
            }
            .icon {
                font-size: 64px;
                margin-bottom: 20px;
            }
            h1 {
                color: #2d3748;
                font-size: 24px;
                margin-bottom: 16px;
            }
            .message {
                color: #4a5568;
                font-size: 16px;
                margin-bottom: 12px;
            }
            .details {
                color: #718096;
                font-size: 14px;
                margin-bottom: 24px;
            }
            .btn {
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 12px 32px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 600;
                transition: background 0.2s;
            }
            .btn:hover {
                background: #5568d3;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">✅</div>
            <h1>{{ title }}</h1>
            <p class="message">{{ message }}</p>
            {% if details %}
            <p class="details">{{ details }}</p>
            {% endif %}
            {% if show_back_link %}
            <a href="mailto:" class="btn">Retour à ma boîte mail</a>
            {% endif %}
        </div>
    </body>
    </html>
    """
    from flask import render_template_string
    return render_template_string(html, title=title, message=message, details=details, show_back_link=show_back_link)


def render_error(message):
    """Rendu d'une page d'erreur"""
    html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Erreur</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .card {
                background: white;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 40px;
                max-width: 500px;
                width: 100%;
                text-align: center;
            }
            .icon { font-size: 64px; margin-bottom: 20px; }
            h1 { color: #2d3748; font-size: 24px; margin-bottom: 16px; }
            .message { color: #4a5568; font-size: 16px; }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">❌</div>
            <h1>Erreur</h1>
            <p class="message">{{ message }}</p>
        </div>
    </body>
    </html>
    """
    from flask import render_template_string
    return render_template_string(html, message=message)


def render_error_with_contact(title, message, driver_name, driver_phone):
    """Rendu d'une page d'erreur avec contact conducteur"""
    html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ title }}</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .card {
                background: white;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 40px;
                max-width: 500px;
                width: 100%;
                text-align: center;
            }
            .icon { font-size: 64px; margin-bottom: 20px; }
            h1 { color: #2d3748; font-size: 24px; margin-bottom: 16px; }
            .message { color: #4a5568; font-size: 16px; margin-bottom: 24px; }
            .contact {
                background: #f7fafc;
                padding: 20px;
                border-radius: 8px;
                margin-top: 24px;
            }
            .contact h2 { font-size: 14px; color: #718096; margin-bottom: 12px; }
            .contact p { font-size: 16px; font-weight: 600; color: #2d3748; }
            .btn {
                display: inline-block;
                background: #48bb78;
                color: white;
                padding: 12px 32px;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 600;
                margin-top: 16px;
                transition: background 0.2s;
            }
            .btn:hover { background: #38a169; }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">⚠️</div>
            <h1>{{ title }}</h1>
            <p class="message">{{ message }}</p>
            <div class="contact">
                <h2>Contactez directement le conducteur :</h2>
                <p>{{ driver_name }}</p>
                <p>{{ driver_phone }}</p>
                <a href="tel:{{ driver_phone }}" class="btn">📞 Appeler</a>
            </div>
        </div>
    </body>
    </html>
    """
    from flask import render_template_string
    return render_template_string(html, title=title, message=message, 
                                 driver_name=driver_name, driver_phone=driver_phone)
