#!/usr/bin/env python3
"""
Tâches automatiques (cron jobs) pour le système de covoiturage
- Expirer les demandes après 24h sans réponse
- Envoyer les rappels J-1 avant les trajets
"""
import sys
import os
from datetime import datetime, timedelta
import logging

# Setup path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sql
from email_sender import send_email, send_email_batch
from email_templates import email_request_expired, email_reminder_24h

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def expire_pending_reservations():
    """
    Expire les demandes de réservation en attente depuis plus de 24h
    Envoie un email au passager pour l'informer
    
    À lancer toutes les heures:
    0 * * * * cd /home/ubuntu/projects/carette/backend && python3 cron_jobs.py expire
    """
    logger.info("🕐 Démarrage job: Expiration des demandes pending >24h")
    
    try:
        with sql.db_cursor() as cur:
            # Trouver les réservations pending créées il y a plus de 24h
            cur.execute("""
                SELECT r.id, r.passenger_email, r.passenger_name,
                       o.driver_name, o.departure, o.destination, o.datetime
                FROM carpool_reservations r
                JOIN carpool_offers o ON r.offer_id = o.id
                WHERE r.status = 'pending'
                  AND r.created_at < NOW() - INTERVAL 24 HOUR
            """)
            
            expired_reservations = cur.fetchall()
            
            if not expired_reservations:
                logger.info("✅ Aucune demande à expirer")
                return
            
            logger.info(f"⏰ {len(expired_reservations)} demande(s) à expirer")
            
            # Marquer comme expired et envoyer emails
            for res in expired_reservations:
                reservation_id = res['id']
                
                # Update status
                cur.execute("""
                    UPDATE carpool_reservations
                    SET status = 'expired', updated_at = NOW()
                    WHERE id = %s
                """, (reservation_id,))
                
                # Libérer les places
                cur.execute("""
                    UPDATE carpool_offers o
                    JOIN carpool_reservations r ON r.offer_id = o.id
                    SET o.seats_available = o.seats_available + r.passengers
                    WHERE r.id = %s
                """, (reservation_id,))
                
                # Envoyer email au passager
                try:
                    subject, html, text = email_request_expired(
                        passenger_email=res['passenger_email'],
                        passenger_name=res['passenger_name'],
                        driver_name=res['driver_name'],
                        offer={
                            'departure': res['departure'],
                            'destination': res['destination'],
                            'datetime': str(res['datetime'])
                        }
                    )
                    send_email(res['passenger_email'], subject, html, text)
                    logger.info(f"  ✅ Email expiration envoyé à {res['passenger_email']}")
                except Exception as e:
                    logger.error(f"  ❌ Erreur email pour réservation {reservation_id}: {e}")
            
            logger.info(f"✅ {len(expired_reservations)} demande(s) expirée(s)")
            
    except Exception as e:
        logger.error(f"❌ Erreur job expiration: {e}", exc_info=True)


def send_24h_reminders():
    """
    Envoie les rappels J-1 pour les trajets de demain
    - Email au conducteur avec liste des passagers
    - Email à chaque passager avec infos de RDV
    
    À lancer tous les jours à 10h:
    0 10 * * * cd /home/ubuntu/projects/carette/backend && python3 cron_jobs.py reminders
    """
    logger.info("🔔 Démarrage job: Rappels J-1")
    
    try:
        with sql.db_cursor() as cur:
            # Trouver les offres qui ont lieu entre 23h et 25h à partir de maintenant
            # (window de 2h pour tolérer les variations d'exécution du cron)
            cur.execute("""
                SELECT o.id, o.driver_email, o.driver_name, o.driver_phone,
                       o.departure, o.destination, o.datetime, o.seats
                FROM carpool_offers o
                WHERE o.datetime BETWEEN NOW() + INTERVAL 23 HOUR 
                                     AND NOW() + INTERVAL 25 HOUR
                  AND o.status = 'active'
            """)
            
            tomorrow_offers = cur.fetchall()
            
            if not tomorrow_offers:
                logger.info("✅ Aucun trajet demain")
                return
            
            logger.info(f"📅 {len(tomorrow_offers)} trajet(s) demain")
            
            for offer in tomorrow_offers:
                offer_id = offer['id']
                
                # Récupérer les passagers confirmés
                cur.execute("""
                    SELECT id, passenger_email, passenger_name, passenger_phone,
                           pickup_address, pickup_time
                    FROM carpool_reservations
                    WHERE offer_id = %s AND status = 'confirmed'
                    ORDER BY pickup_time
                """, (offer_id,))
                
                passengers = cur.fetchall()
                
                if not passengers:
                    logger.info(f"  ⚠️  Offre {offer_id}: Aucun passager confirmé, skip")
                    continue
                
                logger.info(f"  📧 Offre {offer_id}: {len(passengers)} passager(s)")
                
                # 1. Email au CONDUCTEUR
                try:
                    passengers_data = []
                    for p in passengers:
                        passengers_data.append({
                            'name': p['passenger_name'],
                            'phone': p['passenger_phone'] or '',
                            'pickup_time': str(p['pickup_time']) if p['pickup_time'] else 'À définir',
                            'pickup_address': p['pickup_address'] or ''
                        })
                    
                    subject_drv, html_drv, text_drv = email_reminder_24h(
                        recipient_email=offer['driver_email'],
                        recipient_name=offer['driver_name'],
                        role='driver',
                        offer={
                            'departure': offer['departure'],
                            'destination': offer['destination'],
                            'datetime': str(offer['datetime']),
                            'seats': offer['seats']
                        },
                        passengers=passengers_data,
                        view_reservations_url=f"#"  # TODO: URL admin
                    )
                    
                    send_email(offer['driver_email'], subject_drv, html_drv, text_drv)
                    logger.info(f"    ✅ Rappel envoyé au conducteur: {offer['driver_email']}")
                    
                except Exception as e:
                    logger.error(f"    ❌ Erreur email conducteur offre {offer_id}: {e}")
                
                # 2. Email à CHAQUE PASSAGER
                for p in passengers:
                    try:
                        subject_pass, html_pass, text_pass = email_reminder_24h(
                            recipient_email=p['passenger_email'],
                            recipient_name=p['passenger_name'],
                            role='passenger',
                            offer={
                                'departure': offer['departure'],
                                'destination': offer['destination'],
                                'datetime': str(offer['datetime'])
                            },
                            pickup_time=str(p['pickup_time']) if p['pickup_time'] else 'À définir',
                            pickup_address=p['pickup_address'] or offer['departure'],
                            driver_name=offer['driver_name'],
                            driver_phone=offer['driver_phone'] or ''
                        )
                        
                        send_email(p['passenger_email'], subject_pass, html_pass, text_pass)
                        logger.info(f"    ✅ Rappel envoyé au passager: {p['passenger_email']}")
                        
                    except Exception as e:
                        logger.error(f"    ❌ Erreur email passager {p['passenger_email']}: {e}")
            
            logger.info(f"✅ Rappels envoyés pour {len(tomorrow_offers)} trajet(s)")
            
    except Exception as e:
        logger.error(f"❌ Erreur job rappels: {e}", exc_info=True)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Cron jobs covoiturage')
    parser.add_argument('job', choices=['expire', 'reminders', 'all'], 
                       help='Job à exécuter')
    
    args = parser.parse_args()
    
    if args.job == 'expire':
        expire_pending_reservations()
    elif args.job == 'reminders':
        send_24h_reminders()
    elif args.job == 'all':
        expire_pending_reservations()
        send_24h_reminders()
    
    logger.info("✅ Jobs terminés")
