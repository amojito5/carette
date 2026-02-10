# 📊 Récapitulatifs Mensuels RSE

## 🎯 Objectif

Après un mois d'emails hebdomadaires, générer des rapports détaillés :
- **Par employé** : trajets, km, moyens de transport, CO2
- **Par entreprise** : agrégation de tous les employés avec statistiques

---

## 🏢 Configuration Initiale

### 1️⃣ Créer une Entreprise

```bash
curl -X POST http://localhost:9000/api/v2/companies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TechCorp SARL",
    "siren": "123456789",
    "contact_email": "rh@techcorp.fr",
    "contact_name": "Marie Dupont",
    "address": "42 Avenue de la République, 75011 Paris"
  }'

# Réponse :
{
  "success": true,
  "company_id": 1,
  "message": "Entreprise créée avec succès"
}
```

### 2️⃣ Assigner des Employés à l'Entreprise

```bash
# Assigner employee1@techcorp.fr
curl -X POST http://localhost:9000/api/v2/companies/1/employees \
  -H "Content-Type: application/json" \
  -d '{"user_email": "employee1@techcorp.fr"}'

# Assigner employee2@techcorp.fr
curl -X POST http://localhost:9000/api/v2/companies/1/employees \
  -H "Content-Type: application/json" \
  -d '{"user_email": "employee2@techcorp.fr"}'
```

---

## 📈 Récapitulatif Mensuel par Employé

### Endpoint
```
GET /api/v2/rse/monthly-recap/user/{user_id}?year=2026&month=1
```

### Exemple de Requête

```bash
# Récap de janvier 2026 pour l'utilisateur ID 5
curl "http://localhost:9000/api/v2/rse/monthly-recap/user/5?year=2026&month=1"

# Récap du mois dernier (par défaut)
curl "http://localhost:9000/api/v2/rse/monthly-recap/user/5"
```

### Exemple de Réponse

```json
{
  "user": {
    "id": 5,
    "name": "Jean Martin",
    "email": "jean.martin@techcorp.fr",
    "company": "TechCorp SARL"
  },
  "period": {
    "year": 2026,
    "month": 1,
    "start": "2026-01-01",
    "end": "2026-01-31"
  },
  "summary": {
    "total_co2_kg": 48.6,
    "total_distance_km": 300.0,
    "total_working_days": 20,
    "weeks_count": 4,
    "weeks_confirmed": 4
  },
  "transport_breakdown": {
    "transports_commun": {
      "trips": 12,
      "distance_km": 180.0,
      "co2_kg": 10.8
    },
    "velo": {
      "trips": 6,
      "distance_km": 90.0,
      "co2_kg": 0.0
    },
    "voiture_solo": {
      "trips": 2,
      "distance_km": 30.0,
      "co2_kg": 6.6
    },
    "teletravail": {
      "trips": 10,
      "distance_km": 0.0,
      "co2_kg": 0.0
    }
  },
  "weeks": [
    {
      "start": "2026-01-06",
      "end": "2026-01-10",
      "co2_kg": 12.2,
      "distance_km": 75.0,
      "confirmed": true
    },
    {
      "start": "2026-01-13",
      "end": "2026-01-17",
      "co2_kg": 13.1,
      "distance_km": 75.0,
      "confirmed": true
    },
    {
      "start": "2026-01-20",
      "end": "2026-01-24",
      "co2_kg": 11.8,
      "distance_km": 75.0,
      "confirmed": true
    },
    {
      "start": "2026-01-27",
      "end": "2026-01-31",
      "co2_kg": 11.5,
      "distance_km": 75.0,
      "confirmed": true
    }
  ]
}
```

### Données Disponibles

✅ **Par employé :**
- CO2 total du mois (kg)
- Distance totale parcourue (km)
- Nombre de jours travaillés
- Répartition par mode de transport :
  - Nombre de trajets
  - Distance par mode
  - CO2 par mode
- Détail semaine par semaine

---

## 🏢 Récapitulatif Mensuel par Entreprise

### Endpoint
```
GET /api/v2/rse/monthly-recap/company/{company_id}?year=2026&month=1
```

### Exemple de Requête

```bash
# Récap de janvier 2026 pour l'entreprise ID 1
curl "http://localhost:9000/api/v2/rse/monthly-recap/company/1?year=2026&month=1"

# Récap du mois dernier (par défaut)
curl "http://localhost:9000/api/v2/rse/monthly-recap/company/1"
```

### Exemple de Réponse

```json
{
  "company": {
    "id": 1,
    "name": "TechCorp SARL",
    "contact": "Marie Dupont"
  },
  "period": {
    "year": 2026,
    "month": 1,
    "start": "2026-01-01",
    "end": "2026-01-31"
  },
  "summary": {
    "total_employees": 25,
    "active_employees": 23,
    "total_co2_kg": 1247.8,
    "total_distance_km": 7500.0,
    "total_weeks": 92,
    "confirmed_weeks": 87,
    "avg_co2_per_employee": 54.25
  },
  "transport_breakdown": {
    "voiture_solo": {
      "trips": 45,
      "distance_km": 675.0,
      "co2_kg": 148.5,
      "percentage": 11.9
    },
    "transports_commun": {
      "trips": 234,
      "distance_km": 3510.0,
      "co2_kg": 210.6,
      "percentage": 16.9
    },
    "covoiturage": {
      "trips": 78,
      "distance_km": 1170.0,
      "co2_kg": 128.7,
      "percentage": 10.3
    },
    "velo": {
      "trips": 156,
      "distance_km": 2340.0,
      "co2_kg": 0.0,
      "percentage": 0.0
    },
    "train": {
      "trips": 12,
      "distance_km": 180.0,
      "co2_kg": 1.08,
      "percentage": 0.09
    },
    "teletravail": {
      "trips": 267,
      "distance_km": 0.0,
      "co2_kg": 0.0,
      "percentage": 0.0
    },
    "marche": {
      "trips": 34,
      "distance_km": 510.0,
      "co2_kg": 0.0,
      "percentage": 0.0
    }
  },
  "top_employees": [
    {
      "id": 12,
      "name": "Pierre Dubois",
      "email": "pierre.dubois@techcorp.fr",
      "co2_kg": 88.2,
      "distance_km": 400.0,
      "weeks": 4
    },
    {
      "id": 7,
      "name": "Sophie Leroux",
      "email": "sophie.leroux@techcorp.fr",
      "co2_kg": 72.6,
      "distance_km": 330.0,
      "weeks": 4
    },
    {
      "id": 5,
      "name": "Jean Martin",
      "email": "jean.martin@techcorp.fr",
      "co2_kg": 48.6,
      "distance_km": 300.0,
      "weeks": 4
    }
  ]
}
```

### Données Disponibles

✅ **Par entreprise :**
- Nombre total d'employés
- Nombre d'employés actifs ce mois
- CO2 total de l'entreprise (kg)
- Distance totale parcourue (km)
- Moyenne CO2 par employé
- Répartition par mode de transport :
  - Nombre de trajets
  - Distance par mode
  - CO2 par mode
  - **Pourcentage du CO2 total**
- **Top 10 des employés** (classement CO2)

---

## 📊 Cas d'Usage

### 1️⃣ Rapport Mensuel RH

```bash
# Récupérer le récap de l'entreprise
curl "http://localhost:9000/api/v2/rse/monthly-recap/company/1?year=2026&month=1" | jq

# Analyser :
# - Quelle est la part du vélo/transports en commun ?
# - Qui sont les plus gros émetteurs ?
# - Combien d'employés ont confirmé leurs trajets ?
```

### 2️⃣ Bilan Carbone Annuel

```bash
# Récupérer les 12 mois de l'année
for month in {1..12}; do
  curl "http://localhost:9000/api/v2/rse/monthly-recap/company/1?year=2026&month=$month" \
    | jq '.summary.total_co2_kg' >> co2_2026.txt
done

# Calculer le total annuel
awk '{sum+=$1} END {print "Total CO2 2026:", sum, "kg"}' co2_2026.txt
```

### 3️⃣ Comparaison Mois par Mois

```sql
-- Requête SQL directe pour comparer les mois
SELECT 
    YEAR(wd.week_start) as year,
    MONTH(wd.week_start) as month,
    COUNT(DISTINCT wd.user_id) as active_users,
    SUM(CASE WHEN wd.confirmed = 1 THEN wd.total_co2 ELSE 0 END) as total_co2,
    ROUND(AVG(CASE WHEN wd.confirmed = 1 THEN wd.total_co2 ELSE NULL END), 2) as avg_co2_per_week
FROM rse_weekly_data wd
JOIN rse_users u ON wd.user_id = u.id
WHERE u.company_id = 1
GROUP BY YEAR(wd.week_start), MONTH(wd.week_start)
ORDER BY year, month;
```

### 4️⃣ Dashboard de Suivi

```javascript
// Récupérer les données pour un dashboard
async function loadCompanyDashboard(companyId, year, month) {
  const response = await fetch(
    `/api/v2/rse/monthly-recap/company/${companyId}?year=${year}&month=${month}`
  );
  const data = await response.json();
  
  // Afficher :
  // - CO2 total : data.summary.total_co2_kg
  // - Graphique camembert : data.transport_breakdown
  // - Top employés : data.top_employees
  // - Évolution par semaine
}
```

---

## 🗄️ Structure des Données en Base

### Tables Impliquées

```sql
-- Entreprises
companies
├── id
├── name
├── siren
└── contact_email

-- Employés (avec lien entreprise)
rse_users
├── id
├── company_id  ← NOUVEAU (lien vers companies)
├── name
├── email
└── distance_km

-- Semaines (données hebdomadaires)
rse_weekly_data
├── id
├── user_id
├── week_start
├── week_end
├── total_co2    ← Agrégé ici
├── total_distance
└── confirmed

-- Jours (détails quotidiens)
rse_daily_transports
├── weekly_data_id
├── date
├── transport_aller
├── transport_retour
├── co2_aller    ← Détail par trajet
├── co2_retour
├── distance_aller
└── distance_retour
```

### Exemple de Requête Personnalisée

```sql
-- Récap mensuel manuel pour vérifier
SELECT 
    u.name,
    u.email,
    COUNT(DISTINCT wd.id) as weeks,
    SUM(CASE WHEN wd.confirmed = 1 THEN wd.total_co2 ELSE 0 END) as co2_kg,
    SUM(CASE WHEN wd.confirmed = 1 THEN wd.total_distance ELSE 0 END) as distance_km
FROM rse_users u
JOIN rse_weekly_data wd ON u.id = wd.user_id
WHERE u.company_id = 1
AND wd.week_start >= '2026-01-01'
AND wd.week_end <= '2026-01-31'
GROUP BY u.id, u.name, u.email
ORDER BY co2_kg DESC;
```

---

## 📧 Export CSV pour Excel

```python
# Script Python pour exporter en CSV
import requests
import csv
from datetime import datetime

company_id = 1
year = 2026
month = 1

# Récupérer les données
response = requests.get(f'http://localhost:9000/api/v2/rse/monthly-recap/company/{company_id}?year={year}&month={month}')
data = response.json()

# Export CSV
with open(f'recap_{company_id}_{year}_{month}.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    
    # En-tête
    writer.writerow(['Entreprise', data['company']['name']])
    writer.writerow(['Période', f"{year}-{month:02d}"])
    writer.writerow([])
    writer.writerow(['Résumé'])
    writer.writerow(['Total CO2 (kg)', data['summary']['total_co2_kg']])
    writer.writerow(['Total Distance (km)', data['summary']['total_distance_km']])
    writer.writerow(['Employés actifs', data['summary']['active_employees']])
    writer.writerow([])
    
    # Top employés
    writer.writerow(['Top Employés'])
    writer.writerow(['Nom', 'Email', 'CO2 (kg)', 'Distance (km)', 'Semaines'])
    for emp in data['top_employees']:
        writer.writerow([emp['name'], emp['email'], emp['co2_kg'], emp['distance_km'], emp['weeks']])
    
    writer.writerow([])
    
    # Répartition transports
    writer.writerow(['Répartition par Mode de Transport'])
    writer.writerow(['Mode', 'Trajets', 'Distance (km)', 'CO2 (kg)', '%'])
    for mode, stats in data['transport_breakdown'].items():
        writer.writerow([mode, stats['trips'], stats['distance_km'], stats['co2_kg'], stats['percentage']])

print(f"✅ Export créé : recap_{company_id}_{year}_{month}.csv")
```

---

## 🎯 Réponse à Votre Question

### ✅ Oui, après un mois vous aurez :

#### **Par Employé :**
- ✅ Total CO2 émis (kg)
- ✅ Total distance parcourue (km)
- ✅ Nombre de jours travaillés
- ✅ Répartition exacte par mode de transport (combien de fois vélo, bus, voiture, etc.)
- ✅ Détail semaine par semaine
- ✅ Pourcentage de confirmation

#### **Par Entreprise :**
- ✅ CO2 total de tous les employés
- ✅ Distance totale parcourue
- ✅ Moyenne CO2 par employé
- ✅ Répartition des modes de transport (avec pourcentages)
- ✅ Top 10 des employés (classement CO2)
- ✅ Taux de participation (combien ont confirmé)

### 📊 Formats d'Export Disponibles :
- ✅ JSON (via API)
- ✅ CSV (script Python ci-dessus)
- ✅ SQL direct (pour analyses custom)
- ✅ PDF (à créer avec une librairie comme ReportLab)

---

## 🚀 Prochaines Étapes

1. **Redémarrer le serveur** pour créer la table `companies`
2. **Créer vos entreprises** via `/api/v2/companies`
3. **Assigner les employés** via `/api/v2/companies/{id}/employees`
4. **Attendre 1 mois** d'emails hebdomadaires
5. **Générer les récaps** via les endpoints `/monthly-recap/`

🎉 **Vous aurez un système complet de reporting RSE !**
