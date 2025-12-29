#!/usr/bin/env python3
"""
Script de test du système email complet
Teste tous les templates et l'envoi SMTP
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_sender import send_email
from email_templates import (
    email_new_reservation_request,
    email_request_sent_to_passenger,
    email_reservation_confirmed_to_passenger,
    email_driver_route_updated,
    email_passenger_route_updated,
    email_reservation_refused,
    email_cancellation_confirmed_passenger,
    email_offer_cancelled_by_driver,
    email_request_expired,
    email_reminder_24h
)

# Email de test (CHANGEZ-MOI)
TEST_EMAIL = "votre-email@example.com"
BASE_URL = "http://localhost:5000"


def test_new_reservation_request():
    """Test: Nouvelle demande au conducteur"""
    print("\n1️⃣  Test: Nouvelle demande au conducteur")
    
    subject, html, text = email_new_reservation_request(
        driver_email=TEST_EMAIL,
        driver_name="Jean Dupont",
        passenger_name="Marie Martin",
        passenger_email="marie@example.com",
        passenger_phone="+33 6 12 34 56 78",
        meeting_address="123 Rue de la Paix, Lyon",
        offer={
            'departure': 'Lyon',
            'destination': 'Paris',
            'datetime': 'Mercredi 15 janvier 2026 à 14:30',
            'seats': 4
        },
        trip_type='outbound',
        detour_minutes=5,
        accept_url=f"{BASE_URL}/api/reservation/accept?token=TEST_TOKEN",
        refuse_url=f"{BASE_URL}/api/reservation/refuse?token=TEST_TOKEN",
        base_url=BASE_URL
    )
    
    result = send_email(TEST_EMAIL, subject, html, text)
    print(f"   {'✅' if result else '❌'} Sujet: {subject}")
    return result


def test_request_sent_passenger():
    """Test: Confirmation envoi au passager"""
    print("\n2️⃣  Test: Confirmation envoi au passager")
    
    subject, html, text = email_request_sent_to_passenger(
        passenger_email=TEST_EMAIL,
        passenger_name="Marie Martin",
        driver_name="Jean Dupont",
        offer={
            'departure': 'Lyon',
            'destination': 'Paris',
            'datetime': 'Mercredi 15 janvier 2026 à 14:30'
        }
    )
    
    result = send_email(TEST_EMAIL, subject, html, text)
    print(f"   {'✅' if result else '❌'} Sujet: {subject}")
    return result


def test_reservation_confirmed():
    """Test: Réservation confirmée"""
    print("\n3️⃣  Test: Réservation confirmée (passager)")
    
    subject, html, text = email_reservation_confirmed_to_passenger(
        passenger_email=TEST_EMAIL,
        passenger_name="Marie Martin",
        driver_name="Jean Dupont",
        driver_phone="+33 6 98 76 54 32",
        driver_email_contact="jean.dupont@example.com",
        offer={
            'departure': 'Lyon',
            'destination': 'Paris',
            'datetime': 'Mercredi 15 janvier 2026 à 14:30'
        },
        meeting_address="123 Rue de la Paix, Lyon",
        price="Gratuit",
        cancel_url=f"{BASE_URL}/api/reservation/cancel?token=TEST_TOKEN"
    )
    
    result = send_email(TEST_EMAIL, subject, html, text)
    print(f"   {'✅' if result else '❌'} Sujet: {subject}")
    return result


def test_driver_route_updated():
    """Test: Itinéraire mis à jour (conducteur)"""
    print("\n4️⃣  Test: Itinéraire mis à jour (conducteur)")
    
    subject, html, text = email_driver_route_updated(
        driver_email=TEST_EMAIL,
        driver_name="Jean Dupont",
        offer={
            'departure': 'Lyon',
            'destination': 'Paris',
            'datetime': 'Mercredi 15 janvier 2026 à 14:30',
            'seats': 4
        },
        all_passengers=[
            {
                'name': 'Marie Martin',
                'phone': '+33 6 12 34 56 78',
                'pickup_time': '14:15',
                'pickup_address': '123 Rue de la Paix, Lyon',
                'remove_url': f"{BASE_URL}/api/reservation/remove?token=TEST1"
            },
            {
                'name': 'Pierre Durand',
                'phone': '+33 6 11 22 33 44',
                'pickup_time': '14:45',
                'pickup_address': '456 Avenue des Champs, Lyon',
                'remove_url': f"{BASE_URL}/api/reservation/remove?token=TEST2"
            }
        ],
        seats_available=2,
        reason="Nouveau passager ajouté : Marie Martin",
        view_reservations_url=f"{BASE_URL}/api/offer/123/reservations",
        cancel_offer_url=f"{BASE_URL}/api/offer/cancel?token=TEST",
        base_url=BASE_URL
    )
    
    result = send_email(TEST_EMAIL, subject, html, text)
    print(f"   {'✅' if result else '❌'} Sujet: {subject}")
    return result


def test_passenger_route_updated():
    """Test: Horaire modifié (passager)"""
    print("\n5️⃣  Test: Horaire modifié (passager existant)")
    
    subject, html, text = email_passenger_route_updated(
        passenger_email=TEST_EMAIL,
        passenger_name="Pierre Durand",
        new_pickup_time="14:50",
        old_pickup_time="14:45",
        pickup_address="456 Avenue des Champs, Lyon",
        driver_name="Jean Dupont",
        driver_phone="+33 6 98 76 54 32",
        reason="Un nouveau passager a été ajouté",
        cancel_url=f"{BASE_URL}/api/reservation/cancel?token=TEST",
        base_url=BASE_URL
    )
    
    result = send_email(TEST_EMAIL, subject, html, text)
    print(f"   {'✅' if result else '❌'} Sujet: {subject}")
    return result


def test_reservation_refused():
    """Test: Demande refusée"""
    print("\n6️⃣  Test: Demande refusée")
    
    subject, html, text = email_reservation_refused(
        passenger_email=TEST_EMAIL,
        passenger_name="Marie Martin",
        driver_name="Jean Dupont",
        offer={
            'departure': 'Lyon',
            'destination': 'Paris',
            'datetime': 'Mercredi 15 janvier 2026 à 14:30'
        }
    )
    
    result = send_email(TEST_EMAIL, subject, html, text)
    print(f"   {'✅' if result else '❌'} Sujet: {subject}")
    return result


def test_cancellation_confirmed():
    """Test: Annulation confirmée (passager)"""
    print("\n7️⃣  Test: Annulation confirmée (passager)")
    
    subject, html, text = email_cancellation_confirmed_passenger(
        passenger_email=TEST_EMAIL,
        passenger_name="Marie Martin",
        offer={
            'departure': 'Lyon',
            'destination': 'Paris',
            'datetime': 'Mercredi 15 janvier 2026 à 14:30'
        }
    )
    
    result = send_email(TEST_EMAIL, subject, html, text)
    print(f"   {'✅' if result else '❌'} Sujet: {subject}")
    return result


def test_offer_cancelled():
    """Test: Offre annulée par conducteur"""
    print("\n8️⃣  Test: Offre annulée par conducteur")
    
    subject, html, text = email_offer_cancelled_by_driver(
        passenger_email=TEST_EMAIL,
        passenger_name="Marie Martin",
        driver_name="Jean Dupont",
        offer={
            'departure': 'Lyon',
            'destination': 'Paris',
            'datetime': 'Mercredi 15 janvier 2026 à 14:30'
        }
    )
    
    result = send_email(TEST_EMAIL, subject, html, text)
    print(f"   {'✅' if result else '❌'} Sujet: {subject}")
    return result


def test_request_expired():
    """Test: Demande expirée (timeout 24h)"""
    print("\n9️⃣  Test: Demande expirée (timeout 24h)")
    
    subject, html, text = email_request_expired(
        passenger_email=TEST_EMAIL,
        passenger_name="Marie Martin",
        driver_name="Jean Dupont",
        offer={
            'departure': 'Lyon',
            'destination': 'Paris',
            'datetime': 'Mercredi 15 janvier 2026 à 14:30'
        }
    )
    
    result = send_email(TEST_EMAIL, subject, html, text)
    print(f"   {'✅' if result else '❌'} Sujet: {subject}")
    return result


def test_reminder_driver():
    """Test: Rappel J-1 (conducteur)"""
    print("\n🔟 Test: Rappel J-1 (conducteur)")
    
    subject, html, text = email_reminder_24h(
        recipient_email=TEST_EMAIL,
        recipient_name="Jean Dupont",
        role='driver',
        offer={
            'departure': 'Lyon',
            'destination': 'Paris',
            'datetime': 'Mercredi 15 janvier 2026 à 14:30',
            'seats': 4
        },
        passengers=[
            {
                'name': 'Marie Martin',
                'phone': '+33 6 12 34 56 78',
                'pickup_time': '14:15',
                'pickup_address': '123 Rue de la Paix, Lyon'
            },
            {
                'name': 'Pierre Durand',
                'phone': '+33 6 11 22 33 44',
                'pickup_time': '14:45',
                'pickup_address': '456 Avenue des Champs, Lyon'
            }
        ],
        view_reservations_url=f"{BASE_URL}/api/offer/123/reservations"
    )
    
    result = send_email(TEST_EMAIL, subject, html, text)
    print(f"   {'✅' if result else '❌'} Sujet: {subject}")
    return result


def test_reminder_passenger():
    """Test: Rappel J-1 (passager)"""
    print("\n1️⃣1️⃣  Test: Rappel J-1 (passager)")
    
    subject, html, text = email_reminder_24h(
        recipient_email=TEST_EMAIL,
        recipient_name="Marie Martin",
        role='passenger',
        offer={
            'departure': 'Lyon',
            'destination': 'Paris',
            'datetime': 'Mercredi 15 janvier 2026 à 14:30'
        },
        pickup_time="14:15",
        pickup_address="123 Rue de la Paix, Lyon",
        driver_name="Jean Dupont",
        driver_phone="+33 6 98 76 54 32"
    )
    
    result = send_email(TEST_EMAIL, subject, html, text)
    print(f"   {'✅' if result else '❌'} Sujet: {subject}")
    return result


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test du système email')
    parser.add_argument('--email', type=str, help='Email de test (défaut: voir code)')
    parser.add_argument('--test', type=str, choices=[
        'all', 'request', 'confirmed', 'updated', 'refused',
        'cancelled', 'expired', 'reminder'
    ], default='all', help='Test spécifique à exécuter')
    
    args = parser.parse_args()
    
    if args.email:
        TEST_EMAIL = args.email
    
    print(f"\n📧 Tests d'envoi d'emails")
    print(f"📍 Destination: {TEST_EMAIL}")
    print(f"🔗 BASE_URL: {BASE_URL}")
    print("=" * 60)
    
    results = []
    
    if args.test in ['all', 'request']:
        results.append(test_new_reservation_request())
        results.append(test_request_sent_passenger())
    
    if args.test in ['all', 'confirmed']:
        results.append(test_reservation_confirmed())
    
    if args.test in ['all', 'updated']:
        results.append(test_driver_route_updated())
        results.append(test_passenger_route_updated())
    
    if args.test in ['all', 'refused']:
        results.append(test_reservation_refused())
    
    if args.test in ['all', 'cancelled']:
        results.append(test_cancellation_confirmed())
        results.append(test_offer_cancelled())
    
    if args.test in ['all', 'expired']:
        results.append(test_request_expired())
    
    if args.test in ['all', 'reminder']:
        results.append(test_reminder_driver())
        results.append(test_reminder_passenger())
    
    print("\n" + "=" * 60)
    success = sum(results)
    total = len(results)
    print(f"\n📊 Résultats: {success}/{total} emails envoyés avec succès")
    
    if success == 0:
        print("\n⚠️  Mode DEV détecté (pas de SMTP_PASSWORD configuré)")
        print("   Les emails sont loggés mais pas envoyés.")
        print("   Pour tester l'envoi réel, configurez .env avec SMTP_PASSWORD")
    elif success == total:
        print("\n✅ Tous les templates fonctionnent !")
        print(f"   Vérifiez votre boîte email: {TEST_EMAIL}")
    else:
        print("\n⚠️  Certains emails ont échoué, vérifiez les logs")
    
    print("")
