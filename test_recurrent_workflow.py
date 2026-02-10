#!/usr/bin/env python3
"""
Script de test automatisé pour le workflow de covoiturage récurrent.
Crée une offre, fait des réservations, et accepte automatiquement.
"""

import requests
import json
import time
import subprocess
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:9000"
COMPANY_ID = 1  # Decathlon

def log(emoji, message):
    """Affiche un message avec timestamp"""
    print(f"{datetime.now().strftime('%H:%M:%S')} {emoji} {message}")


def geocode_address(address):
    """Géocode une adresse via l'API du serveur"""
    response = requests.get(f"{BASE_URL}/api/geocode/search?q={address}&limit=1")
    if response.status_code == 200:
        data = response.json()
        if data and 'features' in data and len(data['features']) > 0:
            feature = data['features'][0]
            return [feature['lon'], feature['lat']]
    return None

def get_osrm_route(start_coords, end_coords):
    """Calcule une route via OSRM"""
    url = f"http://router.project-osrm.org/route/v1/driving/{start_coords[0]},{start_coords[1]};{end_coords[0]},{end_coords[1]}?overview=full&geometries=geojson"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get('routes'):
            route = data['routes'][0]
            return {
                'distance': route['distance'],
                'duration': route['duration'],
                'geometry': route['geometry']
            }
    return None

def create_recurrent_offer():
    """Crée une offre récurrente Croisilles → Arras"""
    log("🚗", "Création de l'offre récurrente...")
    
    departure_coords = [2.87941, 50.19995]
    destination_coords = [2.756428, 50.290623]
    
    # Calculer les routes via OSRM
    log("🗺️", "Calcul des routes OSRM...")
    route_outbound = get_osrm_route(departure_coords, destination_coords)
    route_return = get_osrm_route(destination_coords, departure_coords)
    
    if not route_outbound or not route_return:
        log("❌", "Erreur lors du calcul des routes OSRM")
        return None
    
    log("✅", f"Route aller: {route_outbound['duration']/60:.1f} min, {route_outbound['distance']/1000:.1f} km")
    log("✅", f"Route retour: {route_return['duration']/60:.1f} min, {route_return['distance']/1000:.1f} km")
    
    payload = {
        "company_id": COMPANY_ID,
        "site_name": "Arras",
        "site_address": "Zone des bonnettes, 62000 Arras",
        "site_coords": [2.756428, 50.290623],
        "driver_name": "Conducteur Test",
        "driver_email": "amaurytruffier@hotmail.fr",
        "driver_phone": "0612345678",
        "departure": "Place de l'Eglise 62128 Croisilles",
        "departure_coords": departure_coords,
        "destination": "Zone des bonnettes, 62000 Arras",
        "destination_coords": destination_coords,
        "time_outbound": "08:00",
        "time_return": "18:00",
        "monday": True,
        "tuesday": True,
        "wednesday": True,
        "thursday": True,
        "friday": True,
        "saturday": False,
        "sunday": False,
        "seats": 4,
        "max_detour_time": 15,
        "color_outbound": "#7c3aed",
        "color_return": "#f97316",
        "route_outbound": route_outbound,
        "route_return": route_return
    }
    
    response = requests.post(f"{BASE_URL}/api/v2/offers/recurrent", json=payload)
    
    if response.status_code == 201:
        offer_id = response.json()['offer_id']
        log("✅", f"Offre créée : ID={offer_id}")
        return offer_id
    else:
        log("❌", f"Erreur création offre : {response.status_code} - {response.text}")
        return None

def create_reservation(offer_id, passenger_name, passenger_email, pickup_address, pickup_coords, days):
    """Crée une réservation pour un passager"""
    log("📝", f"Réservation pour {passenger_name}...")
    
    payload = {
        "offer_id": offer_id,
        "passenger_name": passenger_name,
        "passenger_email": passenger_email,
        "passenger_phone": "0687654321",
        "pickup_address": pickup_address,
        "pickup_coords": pickup_coords,
        "days_requested": days
    }
    
    response = requests.post(f"{BASE_URL}/api/v2/reservations/recurrent", json=payload)
    
    if response.status_code == 201:
        reservation_id = response.json()['reservation_id']
        token = response.json()['confirmation_token']
        log("✅", f"Réservation créée : ID={reservation_id}")
        return reservation_id, token
    else:
        log("❌", f"Erreur réservation : {response.status_code} - {response.text}")
        return None, None

def accept_reservation(reservation_id, token):
    """Accepte automatiquement une réservation"""
    log("👍", f"Acceptation réservation {reservation_id}...")
    
    response = requests.get(f"{BASE_URL}/api/v2/reservations/recurrent/{reservation_id}/accept?token={token}")
    
    if response.status_code == 200:
        log("✅", f"Réservation {reservation_id} acceptée !")
        return True
    else:
        log("❌", f"Erreur acceptation : {response.status_code} - {response.text}")
        return False

def main():
    """Workflow complet de test"""
    print("\n" + "="*60)
    log("🚀", "DÉMARRAGE DU TEST AUTOMATISÉ")
    print("="*60 + "\n")
    
    # 0. Nettoyer la base
    time.sleep(1)
    
    # 1. Créer l'offre
    offer_id = create_recurrent_offer()
    if not offer_id:
        return
    
    time.sleep(1)
    
    # 2. Réservation Hénin-sur-Cojeul (géocoder l'adresse pour avoir les vraies coordonnées)
    log("📍", "Passager 1 : Premier Hénin (Hénin-sur-Cojeul)")
    henin_address = "12 Rue Rene Edouard 62128 Hénin-sur-Cojeul"
    henin_coords = geocode_address(henin_address)
    if not henin_coords:
        log("❌", "Impossible de géocoder l'adresse de Hénin")
        return
    
    log("🗺️", f"Coordonnées Hénin : {henin_coords}")
    
    res1_id, token1 = create_reservation(
        offer_id=offer_id,
        passenger_name="Premier Hénin",
        passenger_email="henin@test.fr",
        pickup_address=henin_address,
        pickup_coords=henin_coords,
        days=["monday", "tuesday", "wednesday", "thursday", "friday"]
    )
    
    if not res1_id:
        return
    
    time.sleep(1)
    
    # 3. Accepter réservation 1
    if not accept_reservation(res1_id, token1):
        return
    
    time.sleep(1)
    
    # 4. Réservation Saint-Léger (géocoder l'adresse)
    log("📍", "Passager 2 : Deuxieme Saint Léger (Saint-Léger)")
    stleger_address = "1 Rue de Vaulx 62128 Saint-Léger"
    stleger_coords = geocode_address(stleger_address)
    if not stleger_coords:
        log("❌", "Impossible de géocoder l'adresse de Saint-Léger")
        return
    
    log("🗺️", f"Coordonnées Saint-Léger : {stleger_coords}")
    
    res2_id, token2 = create_reservation(
        offer_id=offer_id,
        passenger_name="Deuxieme Saint Léger",
        passenger_email="saintleger@test.fr",
        pickup_address=stleger_address,
        pickup_coords=stleger_coords,
        days=["monday", "wednesday", "friday"]
    )
    
    if not res2_id:
        return
    
    time.sleep(1)
    
    # 5. Accepter réservation 2
    if not accept_reservation(res2_id, token2):
        return
    
    print("\n" + "="*60)
    log("🎉", "TEST TERMINÉ AVEC SUCCÈS !")
    print("="*60 + "\n")
    
    log("📧", f"Vérifiez les emails générés dans les logs du serveur")
    log("ℹ️", f"Offre ID : {offer_id}")
    log("ℹ️", f"Réservation 1 : {res1_id} (Hénin)")
    log("ℹ️", f"Réservation 2 : {res2_id} (Saint-Léger)")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("⚠️", "Test interrompu par l'utilisateur")
    except Exception as e:
        log("❌", f"Erreur : {e}")
        import traceback
        traceback.print_exc()
