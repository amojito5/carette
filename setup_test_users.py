#!/usr/bin/env python3
"""
Script de création rapide de 2 utilisateurs de test avec leurs habitudes
"""
import sys
import os
from dotenv import load_dotenv

# Charger .env
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import sql

def setup_test_users():
    """
    Crée une entreprise et 2 employés avec leurs habitudes de transport
    """
    print("🚀 Création des utilisateurs de test\n")
    print("=" * 60)
    
    with sql.db_cursor() as cur:
        # 1. Créer la company
        print("\n1️⃣  Création de l'entreprise...")
        cur.execute("""
            INSERT INTO companies (name, email, email_domain, created_at) 
            VALUES ('Ma Société Test', 'contact@test.com', 'test.com', NOW())
            ON DUPLICATE KEY UPDATE name = name
        """)
        
        cur.execute("SELECT id FROM companies WHERE email_domain = 'test.com'")
        company = cur.fetchone()
        company_id = company['id']
        print(f"   ✅ Entreprise créée (ID: {company_id})")
        
        # 2. Créer les 2 employés
        print("\n2️⃣  Création des employés...")
        
        users_data = [
            ('Alice Dupont', 'alice@test.com', 25.0),
            ('Bob Martin', 'bob@test.com', 30.0)
        ]
        
        user_ids = []
        
        for name, email, distance in users_data:
            cur.execute("""
                INSERT INTO rse_users (name, email, company_id, distance_km, active, created_at)
                VALUES (%s, %s, %s, %s, 1, NOW())
                ON DUPLICATE KEY UPDATE active = 1
            """, (name, email, company_id, distance))
            
            cur.execute("SELECT id FROM rse_users WHERE email = %s", (email,))
            user = cur.fetchone()
            user_ids.append(user['id'])
            print(f"   ✅ {name} ({email}) - {distance} km - ID: {user['id']}")
        
        # 3. Créer les habitudes de transport
        print("\n3️⃣  Création des habitudes de transport...")
        
        habits_data = [
            {
                'user_id': user_ids[0],
                'name': 'Alice',
                'monday': 'voiture_solo',
                'tuesday': 'voiture_solo',
                'wednesday': 'transports_commun',
                'thursday': 'covoiturage',
                'friday': 'teletravail'
            },
            {
                'user_id': user_ids[1],
                'name': 'Bob',
                'monday': 'transports_commun',
                'tuesday': 'transports_commun',
                'wednesday': 'transports_commun',
                'thursday': 'transports_commun',
                'friday': 'velo'
            }
        ]
        
        for habit in habits_data:
            # Supprimer l'ancien si existe
            cur.execute("DELETE FROM rse_user_habits WHERE user_id = %s", (habit['user_id'],))
            
            # Créer le nouveau
            cur.execute("""
                INSERT INTO rse_user_habits 
                (user_id, monday, tuesday, wednesday, thursday, friday, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (
                habit['user_id'],
                habit['monday'],
                habit['tuesday'],
                habit['wednesday'],
                habit['thursday'],
                habit['friday']
            ))
            
            print(f"   ✅ {habit['name']}:")
            print(f"      Lun: {habit['monday']}")
            print(f"      Mar: {habit['tuesday']}")
            print(f"      Mer: {habit['wednesday']}")
            print(f"      Jeu: {habit['thursday']}")
            print(f"      Ven: {habit['friday']}")
        
        print("\n" + "=" * 60)
        print("\n✨ Données de test créées avec succès!")
        print("\n📊 Récapitulatif:")
        print(f"   • Entreprise: Ma Société Test (ID: {company_id})")
        print(f"   • Employés: 2 (Alice et Bob)")
        print(f"   • Habitudes: configurées pour les 2 employés")
        print("\n🚀 Vous pouvez maintenant lancer:")
        print("   python3 simulate_4_weeks.py")

if __name__ == '__main__':
    setup_test_users()
