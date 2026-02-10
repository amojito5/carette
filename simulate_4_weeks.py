#!/usr/bin/env python3
"""
Script de simulation : 4 semaines d'emails de validation RSE
Envoie les emails de demande de validation hebdomadaire pour 4 vendredis consécutifs
"""
import sys
import os
from datetime import datetime, timedelta

# Ajouter le dossier backend au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import requests
import json

BASE_URL = 'http://localhost:9000'

def simulate_4_weeks():
    """
    Simule l'envoi d'emails hebdomadaires pour les 4 derniers vendredis
    """
    print("🚀 Simulation de 4 semaines d'emails RSE\n")
    print("=" * 60)
    
    # Calculer les 4 derniers vendredis
    today = datetime.now()
    # Trouver le dernier vendredi
    days_since_friday = (today.weekday() - 4) % 7
    last_friday = today - timedelta(days=days_since_friday)
    
    weeks = []
    for i in range(4):
        friday = last_friday - timedelta(weeks=i)
        weeks.insert(0, friday)  # Insérer au début pour avoir l'ordre chronologique
    
    print(f"\n📅 Dates des 4 vendredis:")
    for i, friday in enumerate(weeks, 1):
        print(f"   Semaine {i}: {friday.strftime('%d/%m/%Y')}")
    
    print("\n" + "=" * 60)
    
    # Pour chaque semaine
    for i, friday in enumerate(weeks, 1):
        week_end_date = friday.strftime('%Y-%m-%d')
        
        print(f"\n📧 SEMAINE {i} - Vendredi {friday.strftime('%d/%m/%Y')}")
        print("-" * 60)
        
        # Appel API pour envoyer les emails de cette semaine
        try:
            response = requests.post(
                f'{BASE_URL}/api/v2/rse/send-weekly-recap',
                json={'week_end_date': week_end_date},
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Emails envoyés: {result.get('sent_count', 0)}")
                if 'details' in result:
                    for detail in result['details']:
                        status = "✅" if detail.get('success') else "❌"
                        print(f"   {status} {detail.get('email')}")
                        if detail.get('magic_link'):
                            print(f"      🔗 {detail['magic_link'][:80]}...")
            else:
                print(f"❌ Erreur API: {response.status_code}")
                print(f"   {response.text}")
                
        except Exception as e:
            print(f"❌ Erreur: {str(e)}")
    
    print("\n" + "=" * 60)
    print("\n✨ Simulation terminée!")
    print("\n📊 Prochaines étapes:")
    print("   1. Vérifiez vos emails (boîte de réception)")
    print("   2. Cliquez sur les magic links pour valider/modifier")
    print("   3. Consultez le dashboard pour voir les stats mensuelles")
    print(f"\n🔗 Dashboard: {BASE_URL}/dashboard-company.html")

if __name__ == '__main__':
    simulate_4_weeks()
