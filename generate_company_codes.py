#!/usr/bin/env python3
"""
Génère des company_code pour les companies existantes qui n'en ont pas
"""
import sys
import os
import secrets
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, 'backend')
import sql

def generate_company_codes():
    with sql.db_cursor() as cur:
        # Trouver les companies sans code
        cur.execute("SELECT id, name, email_domain FROM companies WHERE company_code IS NULL OR company_code = ''")
        companies = cur.fetchall()
        
        print(f"🔑 Génération de codes pour {len(companies)} entreprise(s)\n")
        
        for company in companies:
            # Générer un code unique de 8 caractères
            code = secrets.token_urlsafe(6).replace('-', '').replace('_', '').upper()[:8]
            
            # Vérifier l'unicité
            while True:
                cur.execute("SELECT id FROM companies WHERE company_code = %s", (code,))
                if not cur.fetchone():
                    break
                code = secrets.token_urlsafe(6).replace('-', '').replace('_', '').upper()[:8]
            
            # Mettre à jour
            cur.execute("UPDATE companies SET company_code = %s WHERE id = %s", (code, company['id']))
            
            print(f"✅ {company['name']}")
            print(f"   Code: {code}")
            print(f"   Email: {company['email_domain']}\n")
        
        print("="*60)
        print("\n📋 Récapitulatif complet :\n")
        
        cur.execute("SELECT id, name, company_code, email_domain FROM companies ORDER BY id")
        all_companies = cur.fetchall()
        
        for c in all_companies:
            print(f"ID: {c['id']} | Code: {c['company_code']} | {c['name']} ({c['email_domain']})")

if __name__ == '__main__':
    generate_company_codes()
