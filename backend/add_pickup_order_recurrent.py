#!/usr/bin/env python3
"""
Migration: Ajouter pickup_order à carpool_reservations_recurrent
"""

import os
import sys
from pathlib import Path

# Ajouter le répertoire backend au path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Charger les variables d'environnement depuis .env
env_file = backend_dir.parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

import sql

def add_pickup_order_column():
    """Ajoute la colonne pickup_order si elle n'existe pas déjà"""
    print("🔄 Ajout de pickup_order à carpool_reservations_recurrent...")
    
    with sql.db_cursor(root=True) as cur:
        cur.execute(f"USE `{sql.DB_NAME}`")
        
        try:
            cur.execute("SHOW COLUMNS FROM carpool_reservations_recurrent LIKE 'pickup_order'")
            if not cur.fetchone():
                print("  ➕ Ajout colonne pickup_order")
                cur.execute("""
                    ALTER TABLE carpool_reservations_recurrent 
                    ADD COLUMN pickup_order INT DEFAULT 0 COMMENT 'Ordre chronologique de passage'
                """)
                print("  ✅ Colonne pickup_order ajoutée")
            else:
                print("  ✓ Colonne pickup_order existe déjà")
        except Exception as e:
            print(f"  ⚠️ Erreur: {e}")
    
    print("✅ Migration terminée")

if __name__ == "__main__":
    add_pickup_order_column()
