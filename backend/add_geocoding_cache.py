#!/usr/bin/env python3
"""
Ajoute une table de cache pour le géocodage des adresses
et pré-géocode les adresses existantes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import sql
import requests
import time

def create_geocoding_cache_table():
    """Crée la table de cache de géocodage"""
    with sql.db_cursor() as cur:
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
        print("✅ Table geocoding_cache créée")

def geocode_address(address):
    """Géocode une adresse via Nominatim"""
    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'q': address,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'fr'  # Limiter à la France
            },
            headers={'User-Agent': 'Carette-RSE-Dashboard/1.0'},
            timeout=5
        )
        
        if response.status_code == 200:
            results = response.json()
            if results:
                return {
                    'lat': float(results[0]['lat']),
                    'lon': float(results[0]['lon'])
                }
    except Exception as e:
        print(f"❌ Erreur géocodage pour '{address}': {e}")
    
    return None

def geocode_all_addresses():
    """Géocode toutes les adresses uniques des employés"""
    with sql.db_cursor() as cur:
        # Récupérer toutes les adresses uniques
        cur.execute("""
            SELECT DISTINCT departure_address
            FROM rse_users
            WHERE departure_address IS NOT NULL
            AND departure_address != ''
            AND active = 1
        """)
        
        addresses = [row['departure_address'] for row in cur.fetchall()]
        
        print(f"📍 {len(addresses)} adresses à géocoder")
        
        for i, address in enumerate(addresses, 1):
            # Vérifier si déjà dans le cache
            cur.execute("SELECT latitude, longitude FROM geocoding_cache WHERE address = %s", (address,))
            cached = cur.fetchone()
            
            if cached and cached['latitude']:
                print(f"✓ [{i}/{len(addresses)}] {address} (déjà en cache)")
                continue
            
            # Géocoder
            print(f"🔍 [{i}/{len(addresses)}] Géocodage de: {address}")
            coords = geocode_address(address)
            
            if coords:
                cur.execute("""
                    INSERT INTO geocoding_cache (address, latitude, longitude)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        latitude = VALUES(latitude),
                        longitude = VALUES(longitude),
                        geocoded_at = CURRENT_TIMESTAMP
                """, (address, coords['lat'], coords['lon']))
                print(f"   ✅ Géocodé: {coords['lat']}, {coords['lon']}")
            else:
                print(f"   ⚠️  Échec du géocodage")
            
            # Respecter les limites de l'API (1 req/sec)
            if i < len(addresses):
                time.sleep(1.1)

if __name__ == '__main__':
    print("🗺️  Configuration du système de géocodage\n")
    create_geocoding_cache_table()
    print()
    
    response = input("Voulez-vous géocoder toutes les adresses maintenant? (o/n): ")
    if response.lower() == 'o':
        geocode_all_addresses()
        print("\n✅ Géocodage terminé!")
    else:
        print("⏭️  Géocodage ignoré. Utilisez ce script plus tard pour géocoder.")
