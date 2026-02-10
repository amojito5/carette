#!/usr/bin/env python3
"""Test rapide de l'API modifiée pour les données confirmées/non confirmées"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from dotenv import load_dotenv
load_dotenv()

import sql
from datetime import datetime

company_id = 1
first_day = datetime(2026, 1, 1)
last_day = datetime(2026, 1, 31)

with sql.db_cursor() as cur:
    # Récupérer les employés
    cur.execute("""
        SELECT id, name, email
        FROM rse_users
        WHERE company_id = %s AND active = 1
    """, (company_id,))
    
    employees = cur.fetchall()
    employee_ids = [e['id'] for e in employees]
    
    print(f"✅ {len(employees)} employés trouvés pour company {company_id}")
    print(f"   IDs: {employee_ids}\n")
    
    # Données agrégées
    placeholders = ','.join(['%s'] * len(employee_ids))
    
    cur.execute(f"""
        SELECT 
            COUNT(DISTINCT wd.user_id) as active_employees,
            COUNT(DISTINCT wd.id) as total_weeks,
            SUM(CASE WHEN wd.confirmed = 1 THEN 1 ELSE 0 END) as confirmed_weeks,
            SUM(CASE WHEN wd.confirmed = 1 THEN wd.total_co2 ELSE 0 END) as confirmed_co2,
            SUM(CASE WHEN wd.confirmed = 0 THEN wd.total_co2 ELSE 0 END) as unconfirmed_co2,
            SUM(wd.total_co2) as total_co2
        FROM rse_weekly_data wd
        WHERE wd.user_id IN ({placeholders})
        AND wd.week_start >= %s
        AND wd.week_end <= %s
    """, (*employee_ids, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
    
    agg = cur.fetchone()
    
    print(f"📊 RÉSUMÉ:")
    print(f"   Total semaines: {agg['total_weeks']}")
    print(f"   Semaines confirmées: {agg['confirmed_weeks']}")
    print(f"   CO2 confirmé: {agg['confirmed_co2']:.2f} kg")
    print(f"   CO2 non confirmé: {agg['unconfirmed_co2']:.2f} kg")
    print(f"   CO2 TOTAL: {agg['total_co2']:.2f} kg\n")
    
    # Stats par transport confirmé
    cur.execute(f"""
        SELECT 
            dt.transport_mode as transport,
            COUNT(*) as count,
            SUM(dt.co2_total) as co2
        FROM rse_daily_transports dt
        JOIN rse_weekly_data wd ON dt.weekly_data_id = wd.id
        WHERE wd.user_id IN ({placeholders})
        AND dt.date >= %s
        AND dt.date <= %s
        AND wd.confirmed = 1
        GROUP BY dt.transport_mode
    """, (*employee_ids, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
    
    transport_confirmed = cur.fetchall()
    
    print("🟢 TRANSPORTS CONFIRMÉS:")
    for t in transport_confirmed:
        print(f"   {t['transport']}: {t['count']} trajets, {t['co2']:.2f} kg CO2")
    
    # Stats par transport NON confirmé
    cur.execute(f"""
        SELECT 
            dt.transport_mode as transport,
            COUNT(*) as count,
            SUM(dt.co2_total) as co2
        FROM rse_daily_transports dt
        JOIN rse_weekly_data wd ON dt.weekly_data_id = wd.id
        WHERE wd.user_id IN ({placeholders})
        AND dt.date >= %s
        AND dt.date <= %s
        AND wd.confirmed = 0
        GROUP BY dt.transport_mode
    """, (*employee_ids, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
    
    transport_unconfirmed = cur.fetchall()
    
    print("\n⚪ TRANSPORTS NON CONFIRMÉS:")
    for t in transport_unconfirmed:
        print(f"   {t['transport']}: {t['count']} trajets, {t['co2']:.2f} kg CO2")
    
    # Stats par jour de la semaine
    cur.execute(f"""
        SELECT 
            DAYOFWEEK(dt.date) as day_num,
            SUM(CASE WHEN wd.confirmed = 1 THEN dt.co2_total ELSE 0 END) as confirmed_co2,
            SUM(CASE WHEN wd.confirmed = 0 THEN dt.co2_total ELSE 0 END) as unconfirmed_co2,
            COUNT(*) as trips
        FROM rse_daily_transports dt
        JOIN rse_weekly_data wd ON dt.weekly_data_id = wd.id
        WHERE wd.user_id IN ({placeholders})
        AND dt.date >= %s
        AND dt.date <= %s
        GROUP BY day_num
        ORDER BY day_num
    """, (*employee_ids, first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')))
    
    weekday_data = cur.fetchall()
    
    print("\n📅 ÉMISSIONS PAR JOUR DE LA SEMAINE:")
    day_names = {1: 'Dimanche', 2: 'Lundi', 3: 'Mardi', 4: 'Mercredi', 5: 'Jeudi', 6: 'Vendredi', 7: 'Samedi'}
    for row in weekday_data:
        day_name = day_names.get(row['day_num'], 'Inconnu')
        print(f"   {day_name}: {row['trips']} trajets | Confirmé: {row['confirmed_co2']:.2f} kg | Non confirmé: {row['unconfirmed_co2']:.2f} kg")
