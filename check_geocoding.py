#!/usr/bin/env python3
"""Test du géocodage automatique"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from dotenv import load_dotenv
load_dotenv()

import sql

# Test quelques adresses
test_addresses = [
    "15 Rue de la Paix, 75002 Paris",
    "10 Avenue des Champs-Élysées, 75008 Paris",
    "1 Place de la Concorde, 75008 Paris"
]

with sql.db_cursor() as cur:
    # Créer la table
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
    
    print("✅ Table geocoding_cache créée\n")
    
    # Afficher les données existantes
    cur.execute("SELECT address, latitude, longitude FROM geocoding_cache")
    existing = cur.fetchall()
    
    if existing:
        print(f"📍 {len(existing)} adresses déjà géocodées:\n")
        for row in existing:
            print(f"   {row['address']}")
            print(f"   → {row['latitude']}, {row['longitude']}\n")
    else:
        print("ℹ️  Aucune adresse géocodée pour l'instant\n")
        print("💡 Le géocodage se fera automatiquement quand les utilisateurs")
        print("   rempliront le widget RSE avec leur adresse domicile.")
