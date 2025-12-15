"""
Fix de la contrainte d'unicité sur carpool_reservations.
La contrainte actuelle empêche plusieurs passagers de réserver le même trajet.
"""

import sys

import sql as sql

def fix_reservation_constraint():
    print("🔧 Correction de la contrainte d'unicité sur carpool_reservations...")
    
    with sql.db_cursor() as cur:
        # 1. Vérifier si la contrainte existe
        cur.execute("""
            SELECT CONSTRAINT_NAME 
            FROM information_schema.TABLE_CONSTRAINTS 
            WHERE TABLE_SCHEMA = 'carette_db' 
            AND TABLE_NAME = 'carpool_reservations' 
            AND CONSTRAINT_TYPE = 'UNIQUE'
        """)
        constraints = cur.fetchall()
        
        print(f"📋 Contraintes actuelles: {[c[0] for c in constraints]}")
        
        # 2. Supprimer la mauvaise contrainte si elle existe
        for constraint in constraints:
            constraint_name = constraint[0]
            if constraint_name == 'uniq_reservation':
                print(f"🗑️ Suppression de la contrainte problématique: {constraint_name}")
                try:
                    cur.execute(f"ALTER TABLE carpool_reservations DROP INDEX {constraint_name}")
                    print(f"  ✅ Contrainte {constraint_name} supprimée")
                except Exception as e:
                    print(f"  ⚠️ Erreur lors de la suppression: {e}")
        
        # 3. Créer la bonne contrainte : un utilisateur ne peut avoir qu'une réservation par (offer_id, trip_type)
        # Mais plusieurs utilisateurs peuvent réserver le même (offer_id, trip_type)
        try:
            cur.execute("""
                ALTER TABLE carpool_reservations 
                ADD CONSTRAINT uniq_user_offer_trip 
                UNIQUE (offer_id, passenger_user_id, trip_type)
            """)
            print("✅ Nouvelle contrainte créée: UNIQUE(offer_id, passenger_user_id, trip_type)")
        except Exception as e:
            if 'Duplicate key name' in str(e):
                print("ℹ️ La contrainte uniq_user_offer_trip existe déjà")
            else:
                print(f"⚠️ Erreur lors de la création de la contrainte: {e}")
    
    print("✅ Correction terminée!")

if __name__ == "__main__":
    fix_reservation_constraint()
