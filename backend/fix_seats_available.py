"""
Migration rapide : Initialiser seats_available pour les offres existantes
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sql

def fix_seats_available():
    print("🔧 Initialisation de seats_available pour les offres existantes...")
    
    with sql.db_cursor() as cur:
        # Mettre à jour les offres où seats_available est NULL
        cur.execute("""
            UPDATE carpool_offers
            SET seats_available = seats
            WHERE seats_available IS NULL
        """)
        
        affected = cur.rowcount
        print(f"✅ {affected} offres mises à jour")

if __name__ == '__main__':
    fix_seats_available()
