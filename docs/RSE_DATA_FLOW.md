# 🔄 Flux de Données - Système RSE Hebdomadaire

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INITIALISATION (1× par utilisateur)               │
└─────────────────────────────────────────────────────────────────────┘

  POST /api/v2/rse/users
        ↓
  ┌─────────────┐
  │ rse_users   │  ← Création utilisateur
  └─────────────┘
        id = 1
        name = "Arnaud"
        email = "arnaud@mojito.co"
        distance_km = 25


┌─────────────────────────────────────────────────────────────────────┐
│                  ENVOI HEBDOMADAIRE (Vendredis 16h)                  │
└─────────────────────────────────────────────────────────────────────┘

  POST /api/v2/rse/send-weekly-recap
  {test_email: "arnaud@mojito.co", week_end_date: "2026-01-17"}
        ↓
  ┌──────────────────┐
  │ Génération token │  token = "abc123xyz..."
  └──────────────────┘
        ↓
  ┌───────────────────┐
  │ rse_weekly_data   │  ← Création semaine
  └───────────────────┘
        id = 1
        user_id = 1
        week_start = 2026-01-13 (Lundi)
        week_end = 2026-01-17 (Vendredi)
        magic_token = "abc123xyz..."
        email_sent = 0
        confirmed = 0
        ↓
  ┌────────────────────────┐
  │ rse_daily_transports   │  ← Création 5 jours
  └────────────────────────┘
        weekly_data_id = 1, date = 2026-01-13, transport_aller/retour = voiture_solo
        weekly_data_id = 1, date = 2026-01-14, transport_aller/retour = voiture_solo
        ... (3 autres jours)
        ↓
  ┌──────────────────┐
  │ Envoi email      │  📧 email_weekly_rse_recap()
  └──────────────────┘
        Contenu:
        - Grille 5 jours avec icônes
        - Bilan CO2
        - Bouton "Confirmer" → /api/v2/rse/weekly-confirm?token=abc123
        - Bouton "Modifier"  → /rse-edit-week.html?token=abc123
        ↓
  UPDATE rse_weekly_data SET email_sent = 1


┌─────────────────────────────────────────────────────────────────────┐
│                   SCÉNARIO 1: Confirmation Directe                   │
└─────────────────────────────────────────────────────────────────────┘

  Utilisateur clique "✅ Confirmer mes trajets" dans l'email
        ↓
  GET /api/v2/rse/weekly-confirm?token=abc123
        ↓
  UPDATE rse_weekly_data 
  SET confirmed = 1, confirmed_at = NOW()
  WHERE magic_token = 'abc123'
        ↓
  Affichage page HTML:
  ┌─────────────────┐
  │       ✓         │
  │ Trajets validés │
  └─────────────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                    SCÉNARIO 2: Modification + Validation             │
└─────────────────────────────────────────────────────────────────────┘

  Utilisateur clique "✏️ Modifier mes trajets" dans l'email
        ↓
  GET /rse-edit-week.html?token=abc123
        ↓ (chargement page)
  GET /api/v2/rse/weekly-data/abc123
        ↓
  Retourne JSON:
  {
    week_start: "2026-01-13",
    days: [
      {date: "2026-01-13", transport_modes: {aller: "voiture_solo", retour: "voiture_solo"}},
      ...
    ]
  }
        ↓
  Affichage interface:
  ┌────────────────────────────────┐
  │  Lundi 13/01                   │
  │  Aller:  🚗 🚌 🚗👥 🚴 ...     │
  │  Retour: 🚗 🚌 🚗👥 🚴 ...     │
  ├────────────────────────────────┤
  │  CO2: 19.5 kg                  │
  └────────────────────────────────┘
        ↓ (utilisateur modifie)
  Sélectionne vélo pour lundi aller/retour
  CO2 recalculé en temps réel: 6.3 kg
        ↓
  Clique "✅ Valider mes trajets"
        ↓
  PUT /api/v2/rse/weekly-data/abc123
  {
    days: [
      {date: "2026-01-13", transport_modes: {aller: "velo", retour: "velo"}},
      {date: "2026-01-14", transport_modes: {aller: "voiture_solo", retour: "covoiturage"}},
      ...
    ]
  }
        ↓
  Pour chaque jour:
    Récupère facteur depuis rse_emission_factors
    co2_aller = facteur_velo (0.000) × 25 km = 0 kg
    co2_retour = facteur_velo (0.000) × 25 km = 0 kg
        ↓
  UPDATE rse_daily_transports
  SET transport_aller = 'velo',
      transport_retour = 'velo',
      co2_aller = 0,
      co2_retour = 0
  WHERE weekly_data_id = 1 AND date = '2026-01-13'
        ↓ (pour les 5 jours)
  total_co2 = SUM(co2_aller + co2_retour) = 6.3 kg
        ↓
  UPDATE rse_weekly_data
  SET total_co2 = 6.3
  WHERE id = 1
        ↓
  Redirection →
  GET /api/v2/rse/weekly-confirm?token=abc123
        ↓
  UPDATE rse_weekly_data
  SET confirmed = 1, confirmed_at = NOW()
  WHERE magic_token = 'abc123'
        ↓
  Page confirmation ✓


┌─────────────────────────────────────────────────────────────────────┐
│                    ÉTATS FINAUX EN BASE DE DONNÉES                   │
└─────────────────────────────────────────────────────────────────────┘

rse_weekly_data:
  id  user_id  week_start   total_co2  confirmed  email_sent  confirmed_at
  1   1        2026-01-13   6.3        1          1           2026-01-17 18:23:15

rse_daily_transports:
  id  weekly_data_id  date         transport_aller  transport_retour  co2_aller  co2_retour
  1   1               2026-01-13   velo            velo              0.000      0.000
  2   1               2026-01-14   voiture_solo    covoiturage       5.500      1.375
  3   1               2026-01-15   transports_commun transports_commun 1.250    1.250
  4   1               2026-01-16   teletravail     teletravail       0.000      0.000
  5   1               2026-01-17   velo            velo              0.000      0.000


┌─────────────────────────────────────────────────────────────────────┐
│                         CRON JOB (Production)                        │
└─────────────────────────────────────────────────────────────────────┘

Tous les vendredis à 16h:

  0 16 * * 5  cd /path/to/carette && python3 send_weekly_recaps.py

send_weekly_recaps.py:
  import requests
  requests.post('http://localhost:9000/api/v2/rse/send-weekly-recap')
  
  → Envoie à TOUS les utilisateurs actifs
  → Crée automatiquement les semaines manquantes
  → Log des succès/échecs
```

---

## 🔢 Calculs CO2

### Facteurs d'émission (ADEME)
```
voiture_solo:       0.220 kg/km
transports_commun:  0.050 kg/km
covoiturage:        0.055 kg/km
velo:               0.000 kg/km
train:              0.025 kg/km
teletravail:        0.000 kg/km
marche:             0.000 kg/km
absent:             0.000 kg/km
```

### Exemple de calcul
```
Distance domicile-travail: 25 km

Lundi:
  Aller voiture_solo:  0.220 × 25 = 5.5 kg
  Retour voiture_solo: 0.220 × 25 = 5.5 kg
  Total jour: 11.0 kg

Mardi:
  Aller covoiturage:   0.055 × 25 = 1.375 kg
  Retour covoiturage:  0.055 × 25 = 1.375 kg
  Total jour: 2.75 kg

... (3 autres jours)

Total semaine: 19.5 kg CO2
Total mensuel (4 semaines): 78 kg
Total annuel (47 semaines): 916.5 kg ≈ 0.92 tonne
```
