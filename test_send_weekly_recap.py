#!/usr/bin/env python3
"""
Script complet pour tester l'envoi du récapitulatif hebdomadaire RSE
1. Vérifie/crée l'utilisateur
2. Envoie le récap pour une semaine spécifique
3. Affiche les données créées en DB
"""
import sys
import os
from pathlib import Path

# IMPORTANT: Charger les variables d'environnement AVANT d'importer sql
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Maintenant on peut importer les modules qui dépendent des variables d'env
sys.path.insert(0, 'backend')
import sql

# Autres imports
import requests
from datetime import datetime, timedelta

def ensure_user_exists(name, email, distance_km=30.0):
    """Crée l'utilisateur s'il n'existe pas"""
    with sql.db_cursor() as cur:
        cur.execute("SELECT id FROM rse_users WHERE email = %s", (email,))
        existing = cur.fetchone()
        
        if existing:
            print(f"✅ Utilisateur existant trouvé: {email} (ID: {existing['id']})")
            return existing['id']
        
        cur.execute("""
            INSERT INTO rse_users 
            (name, email, departure_address, destination_address, distance_km, active)
            VALUES (%s, %s, %s, %s, %s, 1)
        """, (name, email, "123 Rue de la Paix, Paris", "456 Avenue des Champs, Paris", distance_km))
        
        user_id = cur.lastrowid
        print(f"✨ Nouvel utilisateur créé: {email} (ID: {user_id})")
        return user_id


def send_weekly_recap(email, week_end_date=None):
    """Envoie le récap hebdomadaire"""
    payload = {"test_email": email}
    if week_end_date:
        payload["week_end_date"] = week_end_date
    
    print(f"\n📧 Envoi du récap hebdomadaire...")
    print(f"   Email: {email}")
    print(f"   Semaine se terminant le: {week_end_date or 'vendredi dernier'}")
    
    response = requests.post(
        'http://localhost:9000/api/v2/rse/send-weekly-recap',
        json=payload
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ {result['message']}")
        print(f"   Période: {result['week']}")
        return True
    else:
        print(f"❌ Erreur: {response.status_code}")
        print(f"   {response.text}")
        return False


def show_created_data(email):
    """Affiche les données créées en DB"""
    with sql.db_cursor() as cur:
        # Récupérer l'utilisateur
        cur.execute("SELECT id, name, email, distance_km FROM rse_users WHERE email = %s", (email,))
        user = cur.fetchone()
        
        if not user:
            print("❌ Utilisateur non trouvé")
            return
        
        user_id = user['id']
        
        # Récupérer la dernière semaine
        cur.execute("""
            SELECT id, week_start, week_end, magic_token, total_co2, 
                   email_sent, confirmed, created_at
            FROM rse_weekly_data 
            WHERE user_id = %s 
            ORDER BY id DESC LIMIT 1
        """, (user_id,))
        
        week = cur.fetchone()
        
        if not week:
            print("⚠️  Aucune donnée hebdomadaire trouvée")
            return
        
        print("\n" + "="*70)
        print("📊 DONNÉES CRÉÉES EN BASE DE DONNÉES")
        print("="*70)
        
        print(f"\n👤 Utilisateur:")
        print(f"   ID: {user['id']}")
        print(f"   Nom: {user['name']}")
        print(f"   Email: {user['email']}")
        print(f"   Distance: {user['distance_km']} km")
        
        print(f"\n📅 Semaine (ID: {week['id']}):")
        print(f"   Période: {week['week_start']} → {week['week_end']}")
        print(f"   Token: {week['magic_token'][:20]}...")
        print(f"   CO2 total: {week['total_co2']} kg")
        print(f"   Email envoyé: {'✅ Oui' if week['email_sent'] else '❌ Non'}")
        print(f"   Confirmé: {'✅ Oui' if week['confirmed'] else '❌ Non'}")
        print(f"   Créé le: {week['created_at']}")
        
        # Récupérer les trajets quotidiens
        cur.execute("""
            SELECT date, day_name, transport_aller, transport_retour, 
                   co2_aller, co2_retour, distance_aller, distance_retour
            FROM rse_daily_transports
            WHERE weekly_data_id = %s
            ORDER BY date
        """, (week['id'],))
        
        days = cur.fetchall()
        
        print(f"\n🗓️  Trajets quotidiens ({len(days)} jours):")
        print("   " + "-"*66)
        print(f"   {'Jour':<12} {'Date':<12} {'Aller':<20} {'Retour':<20}")
        print("   " + "-"*66)
        
        for day in days:
            print(f"   {day['day_name']:<12} {day['date'].strftime('%Y-%m-%d'):<12} "
                  f"{day['transport_aller']:<20} {day['transport_retour']:<20}")
        
        print("\n🔗 LIENS POUR TESTER:")
        print(f"   Modifier:  http://localhost:9000/rse-edit-week.html?token={week['magic_token']}")
        print(f"   Confirmer: http://localhost:9000/api/v2/rse/weekly-confirm?token={week['magic_token']}")
        print("="*70 + "\n")


def main():
    """Script principal"""
    # Paramètres
    if len(sys.argv) < 2:
        print("Usage: python3 test_send_weekly_recap.py <email> [week_end_date] [distance_km]")
        print("\nExemples:")
        print("  python3 test_send_weekly_recap.py arnaud@mojito.co")
        print("  python3 test_send_weekly_recap.py arnaud@mojito.co 2026-01-17")
        print("  python3 test_send_weekly_recap.py arnaud@mojito.co 2026-01-17 25")
        sys.exit(1)
    
    email = sys.argv[1]
    week_end_date = sys.argv[2] if len(sys.argv) > 2 else None
    distance_km = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0
    
    # Si pas de date fournie, calculer le vendredi dernier
    if not week_end_date:
        today = datetime.now()
        days_since_friday = (today.weekday() - 4) % 7
        friday = today - timedelta(days=days_since_friday)
        week_end_date = friday.strftime('%Y-%m-%d')
    
    print("="*70)
    print("🌱 TEST RÉCAPITULATIF HEBDOMADAIRE RSE")
    print("="*70)
    
    # 1. S'assurer que l'utilisateur existe
    user_id = ensure_user_exists("Arnaud Mojito", email, distance_km)
    
    # 2. Envoyer le récap
    success = send_weekly_recap(email, week_end_date)
    
    if success:
        # 3. Afficher les données créées
        show_created_data(email)
    else:
        print("\n⚠️  L'envoi a échoué. Le serveur est-il démarré ?")
        print("   Lancez: python3 backend/api.py")


if __name__ == '__main__':
    main()
