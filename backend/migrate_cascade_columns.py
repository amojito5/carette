#!/usr/bin/env python3
"""
Migration: Ajouter les colonnes du système cascade
Exécuté automatiquement au démarrage de l'application
"""

import sql

def migrate_cascade_columns():
    """Ajoute les colonnes cascade si elles n'existent pas déjà"""
    print("🔄 Vérification des colonnes cascade...")
    
    with sql.db_cursor(root=True) as cur:
        cur.execute(f"USE `{sql.DB_NAME}`")
        
        # Colonnes à ajouter à carpool_offers
        offers_columns = [
            ('current_route_geometry', 'JSON DEFAULT NULL', 'Route actuelle avec détours'),
            ('current_departure_time', 'DATETIME DEFAULT NULL', 'Heure ajustée'),
            ('time_budget_used', 'INT DEFAULT 0', 'Temps utilisé (minutes)'),
            ('original_departure_time', 'DATETIME DEFAULT NULL', 'Heure originale')
        ]
        
        for col_name, col_def, comment in offers_columns:
            try:
                cur.execute(f"SHOW COLUMNS FROM carpool_offers LIKE '{col_name}'")
                if not cur.fetchone():
                    print(f"  ➕ Ajout colonne carpool_offers.{col_name}")
                    cur.execute(f"ALTER TABLE carpool_offers ADD COLUMN {col_name} {col_def} COMMENT '{comment}'")
                else:
                    print(f"  ✓ carpool_offers.{col_name} existe déjà")
            except Exception as e:
                print(f"  ⚠️ Erreur pour {col_name}: {e}")
        
        # Colonnes à ajouter à carpool_reservations
        reservations_columns = [
            ('pickup_order', 'INT DEFAULT 0', 'Ordre de passage'),
            ('pickup_time', 'DATETIME DEFAULT NULL', 'Heure de prise en charge'),
            ('pickup_coords', 'JSON DEFAULT NULL', 'Coordonnées [lon, lat]'),
            ('pickup_address', 'VARCHAR(500) DEFAULT NULL', 'Adresse du point'),
            ('route_segment_geometry', 'JSON DEFAULT NULL', 'Segment de détour')
        ]
        
        for col_name, col_def, comment in reservations_columns:
            try:
                cur.execute(f"SHOW COLUMNS FROM carpool_reservations LIKE '{col_name}'")
                if not cur.fetchone():
                    print(f"  ➕ Ajout colonne carpool_reservations.{col_name}")
                    cur.execute(f"ALTER TABLE carpool_reservations ADD COLUMN {col_name} {col_def} COMMENT '{comment}'")
                else:
                    print(f"  ✓ carpool_reservations.{col_name} existe déjà")
            except Exception as e:
                print(f"  ⚠️ Erreur pour {col_name}: {e}")
    
    print("✅ Migration des colonnes cascade terminée")

if __name__ == "__main__":
    migrate_cascade_columns()
