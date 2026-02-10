#!/usr/bin/env python3
"""
Script pour créer un utilisateur RSE de test
"""
import sys
sys.path.insert(0, 'backend')
import sql

def create_test_user(name, email, distance_km=30.0):
    """Crée un utilisateur de test dans la table rse_users"""
    
    with sql.db_cursor() as cur:
        # Vérifier si l'utilisateur existe déjà
        cur.execute("SELECT id FROM rse_users WHERE email = %s", (email,))
        existing = cur.fetchone()
        
        if existing:
            print(f"⚠️  L'utilisateur {email} existe déjà (ID: {existing['id']})")
            return existing['id']
        
        # Créer l'utilisateur
        cur.execute("""
            INSERT INTO rse_users 
            (name, email, departure_address, destination_address, distance_km, active)
            VALUES (%s, %s, %s, %s, %s, 1)
        """, (
            name,
            email,
            "123 Rue de la Paix, Paris",
            "456 Avenue des Champs-Élysées, Paris",
            distance_km
        ))
        
        user_id = cur.lastrowid
        
        print(f"✅ Utilisateur créé:")
        print(f"   ID: {user_id}")
        print(f"   Nom: {name}")
        print(f"   Email: {email}")
        print(f"   Distance: {distance_km} km")
        
        return user_id


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 create_test_user.py <name> <email> [distance_km]")
        print("Exemple: python3 create_test_user.py 'Arnaud Mojito' 'arnaud@mojito.co' 25")
        sys.exit(1)
    
    name = sys.argv[1]
    email = sys.argv[2]
    distance = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0
    
    create_test_user(name, email, distance)
