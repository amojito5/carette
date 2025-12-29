#!/usr/bin/env python3
"""
Migration : Séparer detour_time en detour_time_outbound et detour_time_return
Pour gérer correctement les détours indépendants pour aller et retour
"""

import sys
import pymysql
from sql import get_db_connection

def migrate_detour_columns():
    """Ajouter detour_time_outbound et detour_time_return, migrer les données"""
    
    print("🔧 Migration : Séparation des détours aller/retour")
    print("=" * 60)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Vérifier si les colonnes existent déjà
        cur.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'carpool_reservations' 
            AND COLUMN_NAME IN ('detour_time_outbound', 'detour_time_return')
        """)
        existing = [row[0] for row in cur.fetchall()]
        
        if 'detour_time_outbound' in existing and 'detour_time_return' in existing:
            print("✅ Les colonnes existent déjà, migration ignorée")
            return
        
        # 2. Ajouter les nouvelles colonnes
        print("\n📝 Ajout des colonnes detour_time_outbound et detour_time_return...")
        
        if 'detour_time_outbound' not in existing:
            cur.execute("""
                ALTER TABLE carpool_reservations 
                ADD COLUMN detour_time_outbound INT DEFAULT NULL 
                AFTER detour_time
            """)
            print("  ✓ Colonne detour_time_outbound ajoutée")
        
        if 'detour_time_return' not in existing:
            cur.execute("""
                ALTER TABLE carpool_reservations 
                ADD COLUMN detour_time_return INT DEFAULT NULL 
                AFTER detour_time_outbound
            """)
            print("  ✓ Colonne detour_time_return ajoutée")
        
        # 3. Migrer les données existantes
        print("\n📦 Migration des données...")
        cur.execute("""
            SELECT id, trip_type, detour_time 
            FROM carpool_reservations 
            WHERE detour_time IS NOT NULL
        """)
        reservations = cur.fetchall()
        
        migrated = 0
        for res_id, trip_type, detour_time in reservations:
            if trip_type == 'outbound':
                cur.execute("""
                    UPDATE carpool_reservations 
                    SET detour_time_outbound = %s, detour_time_return = NULL
                    WHERE id = %s
                """, (detour_time, res_id))
                migrated += 1
            elif trip_type == 'return':
                cur.execute("""
                    UPDATE carpool_reservations 
                    SET detour_time_outbound = NULL, detour_time_return = %s
                    WHERE id = %s
                """, (detour_time, res_id))
                migrated += 1
            elif trip_type == 'both':
                # Pour 'both', on suppose que detour_time actuel = aller
                # Le retour devra être recalculé
                cur.execute("""
                    UPDATE carpool_reservations 
                    SET detour_time_outbound = %s, detour_time_return = %s
                    WHERE id = %s
                """, (detour_time, detour_time, res_id))  # Dupliquer pour l'instant
                migrated += 1
        
        print(f"  ✓ {migrated} réservations migrées")
        
        # 4. Optionnel : Supprimer l'ancienne colonne (commenté pour sécurité)
        # print("\n🗑️  Suppression de l'ancienne colonne detour_time...")
        # cur.execute("ALTER TABLE carpool_reservations DROP COLUMN detour_time")
        # print("  ✓ Colonne detour_time supprimée")
        
        conn.commit()
        print("\n✅ Migration terminée avec succès!")
        print("\n⚠️  Note: L'ancienne colonne 'detour_time' est conservée pour référence")
        print("    Vous pouvez la supprimer manuellement après vérification")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Erreur durant la migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    migrate_detour_columns()
