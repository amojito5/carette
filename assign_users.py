#!/usr/bin/env python3
import sys, os
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, 'backend')
import sql

with sql.db_cursor() as cur:
    # Assigner les utilisateurs 1 et 2 à la company 1
    cur.execute("UPDATE rse_users SET company_id = 1 WHERE id IN (1, 2)")
    print(f"✅ Utilisateurs 1 et 2 assignés à la company 1 (Decathlon - Code: 87XWMF9R)")
    
    # Vérifier
    cur.execute("SELECT id, name, email, company_id FROM rse_users WHERE id IN (1, 2)")
    users = cur.fetchall()
    for u in users:
        print(f"   - {u['name']} → Company {u['company_id']}")
