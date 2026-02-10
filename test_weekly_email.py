#!/usr/bin/env python3
"""
Script de test pour l'envoi du récapitulatif hebdomadaire RSE
Usage: python test_weekly_email.py [email]
"""
import sys
from datetime import datetime, timedelta

# Ajouter le dossier backend au path
sys.path.insert(0, 'backend')

from email_templates import email_weekly_rse_recap

def generate_test_data(week_end_date_str=None):
    """Génère des données de test pour une semaine"""
    
    # Calculer la semaine
    if week_end_date_str:
        week_end = datetime.strptime(week_end_date_str, '%Y-%m-%d')
    else:
        # Par défaut: vendredi dernier
        today = datetime.now()
        days_since_friday = (today.weekday() - 4) % 7
        week_end = today - timedelta(days=days_since_friday)
    
    week_start = week_end - timedelta(days=4)
    
    # Données simulées
    week_data = {
        'week_start': week_start.strftime('%Y-%m-%d'),
        'week_end': week_end.strftime('%Y-%m-%d'),
        'days': [],
        'total_co2': 0.0,
        'total_distance': 150.0  # 30 km x 5 jours AR
    }
    
    # 5 jours avec différents modes de transport
    day_names = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi']
    example_transports = [
        {'aller': 'voiture_solo', 'retour': 'voiture_solo'},      # 30*2*0.220 = 13.2 kg
        {'aller': 'covoiturage', 'retour': 'covoiturage'},         # 30*2*0.055 = 3.3 kg
        {'aller': 'transports_commun', 'retour': 'transports_commun'}, # 30*2*0.050 = 3.0 kg
        {'aller': 'teletravail', 'retour': 'teletravail'},         # 0 kg
        {'aller': 'velo', 'retour': 'velo'}                        # 0 kg
    ]
    
    co2_factors = {
        'voiture_solo': 0.220,
        'transports_commun': 0.050,
        'covoiturage': 0.055,
        'velo': 0.000,
        'train': 0.025,
        'teletravail': 0.000,
        'marche': 0.000,
        'absent': 0.000
    }
    
    total_co2 = 0.0
    distance_per_trip = 30.0
    
    for i in range(5):
        day_date = week_start + timedelta(days=i)
        transports = example_transports[i]
        
        # Calcul CO2
        co2_aller = co2_factors.get(transports['aller'], 0) * distance_per_trip
        co2_retour = co2_factors.get(transports['retour'], 0) * distance_per_trip
        total_co2 += co2_aller + co2_retour
        
        week_data['days'].append({
            'date': day_date.strftime('%Y-%m-%d'),
            'day_name': day_names[i],
            'transport_modes': transports
        })
    
    week_data['total_co2'] = total_co2
    
    return week_data


def main():
    """Génère et affiche l'email de test"""
    
    # Email de test (peut être passé en argument)
    test_email = sys.argv[1] if len(sys.argv) > 1 else "test@example.com"
    test_name = "Utilisateur Test"
    
    # Date de fin de semaine (optionnelle)
    week_end = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Générer les données de test
    week_data = generate_test_data(week_end)
    
    # Magic link de test
    magic_token = "test_token_abc123xyz456"
    
    print("=" * 60)
    print("📧 GÉNÉRATION EMAIL RÉCAPITULATIF HEBDOMADAIRE")
    print("=" * 60)
    print(f"Destinataire: {test_name} <{test_email}>")
    print(f"Période: {week_data['week_start']} → {week_data['week_end']}")
    print(f"Distance totale: {week_data['total_distance']:.1f} km")
    print(f"CO₂ total: {week_data['total_co2']:.1f} kg")
    print("-" * 60)
    
    # Générer l'email
    subject, html_body, text_body = email_weekly_rse_recap(
        test_name,
        test_email,
        week_data,
        magic_token,
        "http://localhost:9000"
    )
    
    print(f"\n📌 SUJET:")
    print(subject)
    
    print(f"\n📄 VERSION TEXTE:")
    print(text_body)
    
    print(f"\n🌐 VERSION HTML:")
    print(f"Taille: {len(html_body)} caractères")
    
    # Sauvegarder le HTML dans un fichier pour prévisualisation
    output_file = "test_weekly_email.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_body)
    
    print(f"\n✅ Email HTML sauvegardé dans: {output_file}")
    print(f"   Ouvrez ce fichier dans un navigateur pour prévisualiser l'email")
    
    print("\n" + "=" * 60)
    print("🔗 LIENS DANS L'EMAIL:")
    print("-" * 60)
    print(f"Confirmer: http://localhost:9000/api/v2/rse/weekly-confirm?token={magic_token}")
    print(f"Modifier:  http://localhost:9000/rse-edit-week.html?token={magic_token}")
    print("=" * 60)


if __name__ == '__main__':
    main()
