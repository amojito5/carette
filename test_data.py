#!/usr/bin/env python3
import sys
import os
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, 'backend')
import sql

company_id = 1

with sql.db_cursor() as cur:
    # Voir TOUS les utilisateurs (toutes companies)
    cur.execute("SELECT id, name, email, company_id, active FROM rse_users ORDER BY id")
    all_users = cur.fetchall()
    print(f"📋 TOUS les utilisateurs en base: {len(all_users)}")
    for u in all_users:
        status = "✓" if u['active'] else "✗"
        print(f"   {status} ID:{u['id']} - {u['name']} ({u['email']}) - Company:{u['company_id']}")
    
    print("\n" + "="*60)
    
    # Voir les utilisateurs de la company 2
    cur.execute("SELECT id, name FROM rse_users WHERE company_id = %s AND active = 1", (company_id,))
    users = cur.fetchall()
    print(f"\n✅ Employés de la company {company_id}: {len(users)}")
    for u in users:
        print(f"   - {u['name']} (ID: {u['id']})")
    
    if users:
        user_ids = [u['id'] for u in users]
        placeholders = ','.join(['%s'] * len(user_ids))
        
        cur.execute(f"SELECT id, week_start, week_end, total_co2, confirmed FROM rse_weekly_data WHERE user_id IN ({placeholders}) ORDER BY week_start", user_ids)
        weeks = cur.fetchall()
        print(f"\n✅ Semaines trouvées: {len(weeks)}")
        for w in weeks:
            status = "✓" if w['confirmed'] else "✗"
            print(f"   {status} {w['week_start']} → {w['week_end']} : {w['total_co2']} kg CO2")
        
        if weeks:
            weekly_ids = [w['id'] for w in weeks]
            placeholders2 = ','.join(['%s'] * len(weekly_ids))
            cur.execute(f"SELECT COUNT(*) as cnt FROM rse_daily_transports WHERE weekly_data_id IN ({placeholders2})", weekly_ids)
            days = cur.fetchone()
            print(f"\n✅ Jours de transport trouvés: {days['cnt']}")
