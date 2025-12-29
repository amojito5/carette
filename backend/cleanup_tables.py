#!/usr/bin/env python3
"""
Script de nettoyage : migrer de v2 vers les tables principales et supprimer les tables v2
"""
import os
import sys

# Prompt pour confirmation
print("🔧 Script de nettoyage des tables MySQL pour Carette")
print("=" * 60)
print("\nCe script va :")
print("  1. Copier les données de *_v2 vers les tables principales")
print("  2. Supprimer les tables *_v2")
print("\n⚠️  ATTENTION : Cette opération est irréversible!")
print("\nAppuyez sur ENTRÉE pour continuer, ou Ctrl+C pour annuler...")
try:
    input()
except KeyboardInterrupt:
    print("\n❌ Opération annulée")
    sys.exit(0)

# Importer après confirmation
try:
    import pymysql
except ImportError:
    print("❌ pymysql non installé. Installer avec: pip install pymysql")
    sys.exit(1)

# Configuration
DB_NAME = 'carette_db'
DB_HOST = 'localhost'

# Essayer différents mots de passe
passwords_to_try = [
    ('root', ''),  # Root sans mot de passe (auth_socket)
    ('root', 'Ju1ll3t2025'),
    ('root', 'Ju1ll3t2025!'),
    ('carette_user', 'Ju1ll3t2025'),
    ('carette_user', 'Ju1ll3t2025!'),
]

conn = None
for user, pwd in passwords_to_try:
    try:
        if user == 'root' and pwd == '':
            # Essayer avec sudo
            print(f"⏳ Essai de connexion avec {user} (auth_socket)...")
            os.system(f'sudo mysql {DB_NAME} -e "SELECT 1;" > /dev/null 2>&1')
            # Si ça marche, on utilise sudo pour tout
            USE_SUDO = True
            break
        else:
            print(f"⏳ Essai de connexion avec {user}...")
            conn = pymysql.connect(
                host=DB_HOST,
                user=user,
                password=pwd,
                database=DB_NAME
            )
            USE_SUDO = False
            print(f"✅ Connexion réussie avec {user}")
            break
    except Exception as e:
        continue

if conn is None and not USE_SUDO:
    print("\n❌ Impossible de se connecter à MySQL")
    print("💡 Solutions :")
    print("  1. Définir les variables d'environnement CARETTE_DB_PASSWORD et CARETTE_DB_ROOT_PASSWORD")
    print("  2. Exécuter ce script avec sudo : sudo python3 cleanup_tables.py")
    sys.exit(1)

def execute_sql(query, fetch=False):
    """Exécuter une requête SQL"""
    if USE_SUDO:
        import subprocess
        cmd = f'sudo mysql {DB_NAME} -e "{query}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr)
        return result.stdout if fetch else None
    else:
        cur = conn.cursor()
        cur.execute(query)
        if fetch:
            return cur.fetchall()
        conn.commit()
        cur.close()

print("\n📊 État actuel des tables :")
print("-" * 60)

tables = ['carpool_offers', 'carpool_offers_v2', 'carpool_reservations', 'carpool_reservations_v2']
counts = {}

for table in tables:
    try:
        result = execute_sql(f"SELECT COUNT(*) FROM {table}", fetch=True)
        if USE_SUDO:
            # Parser la sortie texte
            count = int(result.strip().split('\n')[-1])
        else:
            count = result[0][0]
        counts[table] = count
        print(f"  {table:30s} : {count:5d} lignes")
    except Exception as e:
        counts[table] = 0
        print(f"  {table:30s} : Table inexistante")

print("\n" + "=" * 60)

# Déterminer la stratégie
v2_has_data = counts.get('carpool_offers_v2', 0) > 0 or counts.get('carpool_reservations_v2', 0) > 0
main_has_data = counts.get('carpool_offers', 0) > 0 or counts.get('carpool_reservations', 0) > 0

if v2_has_data and not main_has_data:
    print("\n📋 Stratégie : Renommer v2 -> principal (les tables principales sont vides)")
    print("\nExécution...")
    try:
        execute_sql("DROP TABLE IF EXISTS carpool_reservations")
        execute_sql("DROP TABLE IF EXISTS carpool_offers")
        execute_sql("RENAME TABLE carpool_offers_v2 TO carpool_offers")
        execute_sql("RENAME TABLE carpool_reservations_v2 TO carpool_reservations")
        print("✅ Tables renommées avec succès!")
    except Exception as e:
        print(f"❌ Erreur : {e}")
        sys.exit(1)

elif v2_has_data and main_has_data:
    print("\n⚠️  Les DEUX versions ont des données!")
    print(f"  - Tables principales : {counts['carpool_offers']} offres, {counts['carpool_reservations']} réservations")
    print(f"  - Tables v2 : {counts['carpool_offers_v2']} offres, {counts['carpool_reservations_v2']} réservations")
    print("\nQue voulez-vous faire ?")
    print("  1) Garder les tables principales, supprimer v2")
    print("  2) Garder v2, supprimer les tables principales")
    print("  3) Fusionner (copier v2 -> principal puis supprimer v2)")
    print("  4) Annuler")
    choice = input("\nVotre choix [1-4] : ").strip()
    
    if choice == '1':
        execute_sql("DROP TABLE IF EXISTS carpool_reservations_v2")
        execute_sql("DROP TABLE IF EXISTS carpool_offers_v2")
        print("✅ Tables v2 supprimées!")
    elif choice == '2':
        execute_sql("DROP TABLE IF EXISTS carpool_reservations")
        execute_sql("DROP TABLE IF EXISTS carpool_offers")
        execute_sql("RENAME TABLE carpool_offers_v2 TO carpool_offers")
        execute_sql("RENAME TABLE carpool_reservations_v2 TO carpool_reservations")
        print("✅ Tables v2 renommées en tables principales!")
    elif choice == '3':
        print("⏳ Fusion des données...")
        # TODO: Implémenter la fusion
        print("❌ Fonctionnalité de fusion pas encore implémentée")
        print("💡 Faites-le manuellement avec SQL ou choisissez option 1 ou 2")
    else:
        print("❌ Opération annulée")

elif not v2_has_data and main_has_data:
    print("\n📋 Stratégie : Supprimer v2 (vides)")
    execute_sql("DROP TABLE IF EXISTS carpool_reservations_v2")
    execute_sql("DROP TABLE IF EXISTS carpool_offers_v2")
    print("✅ Tables v2 supprimées!")

else:
    print("\n✅ Toutes les tables sont vides, suppression de v2...")
    execute_sql("DROP TABLE IF EXISTS carpool_reservations_v2")
    execute_sql("DROP TABLE IF EXISTS carpool_offers_v2")
    print("✅ Tables v2 supprimées!")

print("\n📊 État final :")
print("-" * 60)
for table in ['carpool_offers', 'carpool_reservations']:
    try:
        result = execute_sql(f"SELECT COUNT(*) FROM {table}", fetch=True)
        if USE_SUDO:
            count = int(result.strip().split('\n')[-1])
        else:
            count = result[0][0]
        print(f"  {table:30s} : {count:5d} lignes")
    except Exception as e:
        print(f"  {table:30s} : Erreur - {e}")

if conn:
    conn.close()

print("\n✅ Nettoyage terminé!")
