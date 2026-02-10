# ✅ Test du Workflow RSE Complet

## 📋 Checklist de Vérification

### ✅ 1. Base de Données
- [x] Table `rse_users` (infos utilisateur)
- [x] Table `rse_user_habits` (habitudes par défaut) 
- [x] Table `rse_weekly_data` (données hebdomadaires)
- [x] Table `rse_daily_transports` (transports quotidiens)
- [x] Clés étrangères et indexes

### ✅ 2. API Endpoints
- [x] `POST /api/v2/rse/submit` - Première déclaration + sauvegarde habitudes
- [x] `POST /api/v2/rse/send-weekly-recap` - Email vendredi (utilise habitudes)
- [x] `GET /api/v2/rse/weekly-confirm` - Bouton confirmer
- [x] `GET /api/v2/rse/weekly-absent` - Bouton absent/congés
- [x] `GET /api/v2/rse/weekly-data/<token>` - Récupérer données
- [x] `PUT /api/v2/rse/weekly-data/<token>` - Modifier + option save_as_habits

### ✅ 3. Workflow Submit (Widget)
**Localisation:** `backend/api.py` lignes 2161-2410
- [x] Création/mise à jour utilisateur dans `rse_users`
- [x] Sauvegarde dans `rse_weekly_data` (semaine courante)
- [x] Sauvegarde dans `rse_daily_transports` (7 jours)
- [x] **Sauvegarde dans `rse_user_habits`** (lignes 2303-2363)
  - Mapping des transport_modes → codes transport
  - INSERT ou UPDATE selon existence
  - Logs de confirmation

### ✅ 4. Workflow Vendredi (Email automatique)
**Localisation:** `backend/api.py` lignes 5117-5330
- [x] Récupération des utilisateurs actifs
- [x] **Vérification habitudes configurées** (ligne 5193-5203)
  - Si pas d'habitudes → skip utilisateur (warning log)
- [x] **Duplication depuis habitudes** (lignes 5220-5267)
  - Récupération monday_aller/retour → friday_aller/retour
  - Calcul CO2 avec facteurs d'émission
  - Création rse_daily_transports basée sur habitudes
- [x] Email envoyé avec 3 boutons

### ✅ 5. Email avec 3 Boutons
**Localisation:** `backend/email_templates.py` lignes 3289-3572
- [x] Bouton VERT "✅ Confirmer" → `/api/v2/rse/weekly-confirm`
- [x] Bouton GRIS "✏️ Modifier" → `/rse-edit-week.html?token=...`
- [x] Bouton JAUNE "🏖️ Congés" → `/api/v2/rse/weekly-absent`
- [x] Affichage récapitulatif semaine
- [x] Total CO2 calculé

### ✅ 6. Magic Link - Modification
**Localisation:** `rse-edit-week.html` + `backend/api.py` lignes 5604-5760
- [x] Page de modification jour par jour
- [x] **Checkbox "Sauvegarder comme habitudes"** (ligne 276)
  - Label explicite
  - Style visuel (fond jaune)
- [x] JavaScript récupère checkbox (ligne 493)
- [x] **Envoi paramètre `save_as_habits`** (ligne 504)
- [x] **Backend UPDATE/INSERT rse_user_habits** (lignes 5698-5745)
  - Seulement si save_as_habits=true
  - Mise à jour des 5 jours (lundi-vendredi)
  - Logs de confirmation

### ✅ 7. Facteurs d'Émission
**Calcul CO2 présent dans:**
- `send_weekly_recap` (lignes 5230-5243) - Hardcodé
- `update_weekly_data` (lignes 5637-5644) - Depuis DB rse_emission_factors

**Codes transport:**
- `voiture_solo` - 0.220 kg CO2/km
- `transports_commun` - 0.060 kg CO2/km
- `covoiturage` - 0.110 kg CO2/km
- `velo` - 0.0 kg CO2/km
- `train` - 0.006 kg CO2/km
- `teletravail` - 0.0 kg CO2/km
- `marche` - 0.0 kg CO2/km
- `ne_travaille_pas` - 0.0 kg CO2/km

---

## 🧪 Scénario de Test Complet

### Test 1: Première Déclaration
```bash
# 1. Submit via widget
curl -X POST http://localhost:9000/api/v2/rse/submit \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "Test User",
    "user_email": "test@example.com",
    "departure": "Paris 10eme",
    "destination": "La Defense",
    "distance_km": 15,
    "transport_modes": {
      "monday": 1,
      "tuesday": 1,
      "wednesday": 3,
      "thursday": 1,
      "friday": 5
    },
    "co2_emissions": {
      "monday": 1.8,
      "tuesday": 1.8,
      "wednesday": 0,
      "thursday": 1.8,
      "friday": 0
    },
    "total_co2": 5.4
  }'

# Vérifier en DB
mysql -u root -p carette -e "
  SELECT * FROM rse_users WHERE email='test@example.com';
  SELECT * FROM rse_user_habits WHERE user_id=(SELECT id FROM rse_users WHERE email='test@example.com');
  SELECT * FROM rse_weekly_data WHERE user_id=(SELECT id FROM rse_users WHERE email='test@example.com');
"
```

**Résultat attendu:**
- ✅ Entrée dans `rse_users`
- ✅ Entrée dans `rse_user_habits` avec:
  - monday_aller='transports_commun', monday_retour='transports_commun'
  - wednesday_aller='velo', wednesday_retour='velo'
  - friday_aller='teletravail', friday_retour='teletravail'
- ✅ Entrée dans `rse_weekly_data` pour semaine courante
- ✅ 7 entrées dans `rse_daily_transports`

### Test 2: Email Vendredi (Duplication Habitudes)
```bash
# Supprimer la semaine courante pour tester la duplication
mysql -u root -p carette -e "
  DELETE FROM rse_weekly_data 
  WHERE user_id=(SELECT id FROM rse_users WHERE email='test@example.com') 
  AND week_start >= CURDATE() - INTERVAL 7 DAY;
"

# Envoyer le recap
curl -X POST http://localhost:9000/api/v2/rse/send-weekly-recap \
  -H "Content-Type: application/json" \
  -d '{"test_email": "test@example.com"}'

# Vérifier en DB
mysql -u root -p carette -e "
  SELECT date, day_name, transport_aller, transport_retour, co2_aller, co2_retour
  FROM rse_daily_transports 
  WHERE weekly_data_id=(
    SELECT id FROM rse_weekly_data 
    WHERE user_id=(SELECT id FROM rse_users WHERE email='test@example.com')
    ORDER BY created_at DESC LIMIT 1
  );
"
```

**Résultat attendu:**
- ✅ Nouvelle semaine créée dans `rse_weekly_data`
- ✅ 5 jours créés avec transports = habitudes
- ✅ Lundi: transports_commun/transports_commun
- ✅ Mercredi: velo/velo
- ✅ Vendredi: teletravail/teletravail
- ✅ CO2 calculé automatiquement

### Test 3: Modification + Sauvegarde Habitudes
```bash
# 1. Récupérer le token
TOKEN=$(mysql -u root -p carette -N -e "
  SELECT magic_token FROM rse_weekly_data 
  WHERE user_id=(SELECT id FROM rse_users WHERE email='test@example.com')
  ORDER BY created_at DESC LIMIT 1;
")

# 2. Ouvrir le magic link
http://localhost:9000/rse-edit-week.html?token=$TOKEN

# 3. Modifier les transports (via UI)
# - Cocher la case "Sauvegarder comme habitudes"
# - Changer mercredi en "covoiturage"
# - Valider

# 4. Vérifier que les habitudes ont changé
mysql -u root -p carette -e "
  SELECT wednesday_aller, wednesday_retour 
  FROM rse_user_habits 
  WHERE user_id=(SELECT id FROM rse_users WHERE email='test@example.com');
"
```

**Résultat attendu:**
- ✅ `wednesday_aller` = 'covoiturage'
- ✅ `wednesday_retour` = 'covoiturage'
- ✅ La semaine suivante utilisera ces nouvelles habitudes

### Test 4: Bouton Absent/Congés
```bash
# Cliquer sur le bouton "Congés" dans l'email
curl "http://localhost:9000/api/v2/rse/weekly-absent?token=$TOKEN"

# Vérifier en DB
mysql -u root -p carette -e "
  SELECT transport_aller, transport_retour, co2_aller, co2_retour
  FROM rse_daily_transports 
  WHERE weekly_data_id=(SELECT id FROM rse_weekly_data WHERE magic_token='$TOKEN');
  
  SELECT total_co2, confirmed FROM rse_weekly_data WHERE magic_token='$TOKEN';
"
```

**Résultat attendu:**
- ✅ Tous les jours passent à `ne_travaille_pas`
- ✅ Tous les CO2 = 0
- ✅ `confirmed` = 1
- ✅ Page jaune avec emoji 🏖️

---

## 🎯 Points de Vigilance

### ⚠️ 1. Première Semaine vs Semaines Suivantes
- Première fois: Widget crée semaine + habitudes
- Semaines suivantes: Email duplique habitudes automatiquement

### ⚠️ 2. Modification sans Sauvegarde Habitudes
- Par défaut: checkbox NON cochée
- Modification = juste cette semaine
- Semaine suivante = habitudes précédentes (inchangées)

### ⚠️ 3. Modification AVEC Sauvegarde Habitudes
- Checkbox cochée = nouvelles habitudes
- Semaines futures utiliseront ces nouveaux transports

### ⚠️ 4. Utilisateurs sans Habitudes
- Si pas d'entrée dans `rse_user_habits` → pas d'email vendredi
- Warning log: "⚠️ {email} n'a pas d'habitudes configurées"
- Solution: utilisateur doit passer par widget une fois

---

## 📊 Résumé du Flux de Données

```
┌─────────────────────────────────────────────────────────────┐
│ 1️⃣  PREMIÈRE DÉCLARATION (Widget)                           │
├─────────────────────────────────────────────────────────────┤
│ Input: transport_modes (indices 0-7) par jour               │
│ ↓                                                            │
│ backend/api.py:submit_rse_data (L2161-2410)                 │
│ ↓                                                            │
│ ✅ INSERT/UPDATE rse_users                                  │
│ ✅ INSERT/UPDATE rse_user_habits ← HABITUDES SAUVEGARDÉES   │
│ ✅ INSERT rse_weekly_data (semaine courante)                │
│ ✅ INSERT rse_daily_transports (7 jours)                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 2️⃣  EMAIL VENDREDI (Automatique)                            │
├─────────────────────────────────────────────────────────────┤
│ Trigger: Cron tous les vendredis                            │
│ ↓                                                            │
│ backend/api.py:send_weekly_recap (L5117-5330)               │
│ ↓                                                            │
│ SELECT * FROM rse_users WHERE active=1                      │
│ ↓                                                            │
│ Pour chaque user:                                           │
│   Si rse_weekly_data existe → utiliser données existantes   │
│   Sinon:                                                    │
│     ✅ SELECT * FROM rse_user_habits ← LIT HABITUDES        │
│     ✅ INSERT rse_weekly_data (nouvelle semaine)            │
│     ✅ INSERT rse_daily_transports (5 jours depuis habits)  │
│ ↓                                                            │
│ ✅ Envoi email avec 3 boutons                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 3️⃣  MODIFICATION (Magic Link)                               │
├─────────────────────────────────────────────────────────────┤
│ rse-edit-week.html + backend/api.py:update_weekly_data      │
│ ↓                                                            │
│ Input: days[] + save_as_habits (boolean)                    │
│ ↓                                                            │
│ ✅ UPDATE rse_daily_transports (nouveaux transports)        │
│ ✅ UPDATE rse_weekly_data (total_co2 recalculé)             │
│ ↓                                                            │
│ Si save_as_habits = true:                                   │
│   ✅ UPDATE rse_user_habits ← NOUVELLES HABITUDES           │
│ ↓                                                            │
│ ✅ Redirect vers weekly-confirm                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 4️⃣  BOUTON ABSENT (Magic Link)                              │
├─────────────────────────────────────────────────────────────┤
│ backend/api.py:mark_weekly_absent (L5443-5540)              │
│ ↓                                                            │
│ ✅ UPDATE rse_daily_transports SET transport='ne_travaille' │
│ ✅ UPDATE rse_weekly_data SET total_co2=0, confirmed=1      │
│ ↓                                                            │
│ ✅ Page jaune "Congés enregistrés 🏖️"                      │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ Statut Global

| Composant | Statut | Fichier | Lignes |
|-----------|--------|---------|--------|
| Table rse_user_habits | ✅ OK | init_carpool_tables.py | 448-470 |
| Submit → Save habits | ✅ OK | api.py | 2303-2363 |
| Vendredi → Use habits | ✅ OK | api.py | 5193-5267 |
| Magic link checkbox | ✅ OK | rse-edit-week.html | 276 |
| Update → Save habits | ✅ OK | api.py | 5698-5745 |
| Email 3 boutons | ✅ OK | email_templates.py | 3501-3520 |
| Endpoint absent | ✅ OK | api.py | 5443-5540 |

**🎉 WORKFLOW COMPLET ET FONCTIONNEL**
