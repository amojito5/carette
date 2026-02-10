#!/usr/bin/env python3
"""
Script de debug pour visualiser les emails générés avec suggestions de covoiturage.
"""

import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from email_templates import email_weekly_rse_recap
import sql

def generate_sample_email_for_user(user_id: int, week_end_date_str: str = None):
    """Génère un email d'exemple pour visualisation."""
    
    if week_end_date_str:
        week_end = datetime.strptime(week_end_date_str, '%Y-%m-%d')
    else:
        today = datetime.now()
        days_since_friday = (today.weekday() - 4) % 7
        week_end = today - timedelta(days=days_since_friday)
    
    week_start = week_end - timedelta(days=4)
    
    with sql.db_cursor() as cur:
        # Récupérer l'utilisateur
        cur.execute("SELECT id, name, email, distance_km, company_id FROM rse_users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        
        if not user:
            print(f"❌ Utilisateur {user_id} non trouvé")
            return
        
        print(f"\n📧 Email pour: {user['name']} ({user['email']})")
        print(f"   Entreprise ID: {user['company_id']}")
        print("=" * 80)
        
        # Récupérer les données de la semaine
        cur.execute("""
            SELECT id FROM rse_weekly_data 
            WHERE user_id = %s AND week_start = %s
        """, (user_id, week_start.strftime('%Y-%m-%d')))
        
        weekly = cur.fetchone()
        if not weekly:
            print("⚠️  Aucune donnée de semaine trouvée")
            return
        
        weekly_data_id = weekly['id']
        
        # Récupérer les jours
        cur.execute("""
            SELECT date, day_name, transport_mode, co2_total
            FROM rse_daily_transports
            WHERE weekly_data_id = %s
            ORDER BY date
        """, (weekly_data_id,))
        
        days_data = cur.fetchall()
        
        # Construire week_data
        week_data = {
            'week_start': week_start.strftime('%Y-%m-%d'),
            'week_end': week_end.strftime('%Y-%m-%d'),
            'days': [],
            'total_co2': 0.0,
            'total_distance': float(user['distance_km'] or 30.0) * 10
        }
        
        for day in days_data:
            week_data['days'].append({
                'date': day['date'].strftime('%Y-%m-%d'),
                'day_name': day['day_name'],
                'transport_mode': day['transport_mode']
            })
            week_data['total_co2'] += float(day['co2_total'] or 0)
        
        # Chercher une suggestion de covoiturage
        from carpool_matching import get_carpool_suggestions_for_user
        
        carpool_suggestion = None
        try:
            if user['company_id']:
                suggestions = get_carpool_suggestions_for_user(user_id, user['company_id'], cur, max_detour_minutes=20)
                if suggestions:
                    carpool_suggestion = suggestions[0]
                    print(f"\n🚗 Suggestion trouvée:")
                    print(f"   Role: {carpool_suggestion['role']}")
                    print(f"   Match: {carpool_suggestion['match_name']}")
                    print(f"   Détour: {carpool_suggestion['detour_minutes']} min")
                    print(f"   Jours: {', '.join(carpool_suggestion['common_days'])}")
                    print(f"   CO₂ économisé: {carpool_suggestion['co2_saved_week']:.1f} kg/semaine")
        except Exception as e:
            print(f"⚠️  Erreur calcul covoiturage: {e}")
        
        # Générer l'email
        subject, html_body, text_body = email_weekly_rse_recap(
            user['name'],
            user['email'],
            week_data,
            'DEBUG_TOKEN_123456',
            'http://51.178.30.246:9000',
            carpool_suggestion=carpool_suggestion
        )
        
        print(f"\n📌 Sujet: {subject}")
        print("\n" + "=" * 80)
        print("TEXTE BRUT:")
        print("=" * 80)
        print(text_body)
        
        print("\n" + "=" * 80)
        print("HTML (aperçu - section covoiturage):")
        print("=" * 80)
        
        # Extraire la section covoiturage
        if "<!-- Section Covoiturage -->" in html_body:
            start = html_body.find("<!-- Section Covoiturage -->")
            end = html_body.find("<!-- Boutons d'action -->")
            if start >= 0 and end >= 0:
                section = html_body[start:end]
                print(section[:1000])
                print("...")
                print(section[-500:])
            else:
                print("[Section covoiturage trouvée mais extraction échouée]")
        else:
            print("[Pas de section covoiturage]")
        
        # Sauvegarder en fichier
        filename = f'/tmp/email_debug_{user_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
        with open(filename, 'w') as f:
            f.write(html_body)
        print(f"\n✅ Email complet sauvegardé: {filename}")


if __name__ == "__main__":
    print("🔍 Debug Email Viewer - Suggestions Covoiturage RSE\n")
    
    week_end = "2025-02-14"
    
    # Lister les utilisateurs
    with sql.db_cursor() as cur:
        cur.execute("SELECT id, name, email FROM rse_users WHERE active = 1 ORDER BY id")
        users = cur.fetchall()
        
        print(f"📋 {len(users)} utilisateurs trouvés:\n")
        for u in users:
            print(f"  ID {u['id']}: {u['name']} ({u['email']})")
        
        print("\n" + "=" * 80)
        
        # Générer les emails
        for u in users:
            try:
                generate_sample_email_for_user(u['id'], week_end)
            except Exception as e:
                print(f"\n❌ Erreur pour {u['name']}: {e}")
                import traceback
                traceback.print_exc()
