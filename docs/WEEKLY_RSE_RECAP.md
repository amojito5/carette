# 📊 Système de Récapitulatif Hebdomadaire RSE

## Vue d'ensemble

Système complet d'envoi automatique d'emails hebdomadaires permettant aux utilisateurs de valider ou modifier leurs trajets de la semaine, avec **persistance en base de données MySQL**.

**Envoi prévu :** Tous les vendredis à 16h

---

## 🗄️ Architecture Base de Données

### Tables créées

#### 1. `rse_users` - Utilisateurs du système RSE
```sql
- id (PK)
- name
- email (UNIQUE)
- departure_address
- destination_address
- distance_km (distance domicile-travail en km)
- active (pour désactiver sans supprimer)
- created_at, updated_at
```

#### 2. `rse_weekly_data` - Données hebdomadaires
```sql
- id (PK)
- user_id (FK → rse_users)
- week_start (DATE, lundi)
- week_end (DATE, vendredi)
- magic_token (token unique pour sécurité)
- total_co2 (calculé automatiquement)
- total_distance
- confirmed (validation utilisateur)
- confirmed_at
- email_sent (tracking envoi)
- email_sent_at
- created_at, updated_at

UNIQUE(user_id, week_start) -- 1 seule entrée par utilisateur par semaine
```

#### 3. `rse_daily_transports` - Trajets quotidiens
```sql
- id (PK)
- weekly_data_id (FK → rse_weekly_data)
- date (DATE)
- day_name (Lundi, Mardi, etc.)
- transport_aller
- transport_retour
- co2_aller (calculé)
- co2_retour (calculé)
- distance_aller
- distance_retour
- created_at, updated_at

UNIQUE(weekly_data_id, date) -- 1 seule entrée par jour
```

#### 4. `rse_emission_factors` - Référentiel des facteurs d'émission
```sql
- id (PK)
- transport_code (voiture_solo, covoiturage, etc.)
- transport_name
- icon (emoji)
- co2_per_km (facteur ADEME)
- color (pour UI)
- display_order
- active
```

---

## 🚀 Installation

### Les tables sont créées automatiquement

**Pas besoin de script séparé !** Les tables RSE sont créées automatiquement au démarrage du serveur Flask.

```bash
# Simplement démarrer le serveur
python3 backend/api.py
```

Au premier lancement, vous verrez :
```
🔄 Initialisation des tables RSE...
  ✅ Table rse_users créée/vérifiée
  ✅ Table rse_weekly_data créée/vérifiée
  ✅ Table rse_daily_transports créée/vérifiée
  ✅ Table rse_emission_factors créée/vérifiée
  ➕ Facteurs d'émission ADEME insérés
✅ Initialisation des tables RSE terminée
```

### Créer un utilisateur de test

```bash
python3 create_test_user.py "Arnaud Mojito" "arnaud@mojito.co" 25
```

---

## 📧 Fonctionnalités

### 1. Email Hebdomadaire

L'email contient :
- ✅ **Grille des 5 jours** (Lundi → Vendredi) avec icônes des transports utilisés
- 📊 **Bilan CO₂** de la semaine avec message d'encouragement adapté
- 🎯 **2 boutons d'action** :
  - **Confirmer mes trajets** : validation en 1 clic
  - **Modifier mes trajets** : accès à la page de modification

### 2. Page de Modification

Interface interactive permettant de :
- 📅 Voir la semaine complète avec tous les jours
- ✏️ Modifier les transports pour chaque trajet (aller/retour)
- 💚 Voir le CO₂ mis à jour en temps réel
- ✅ Valider les changements

### 3. Confirmation

Page de succès animée après validation.

---

## 🧪 Workflow de Test Complet

### 1. Initialiser la DB
```bash
python3 backend/init_rse_weekly_tables.py
```

### 2. Créer un utilisateur
```bash
python3 create_test_user.py "Arnaud Mojito" "arnaud@mojito.co" 25
```

### 3. Envoyer le récap hebdo (via API ou curl)
```bash
curl -X POST http://localhost:9000/api/v2/rse/send-weekly-recap \
  -H "Content-Type: application/json" \
  -d '{"test_email": "arnaud@mojito.co", "week_end_date": "2026-01-17"}'
```

**Ou via Python:**
```python
import requests
response = requests.post('http://localhost:9000/api/v2/rse/send-weekly-recap', json={
    'test_email': 'arnaud@mojito.co'
})
print(response.json())
```

### 4. Vérifier en DB
```sql
-- Voir les données créées
SELECT * FROM rse_weekly_data WHERE user_id = 1;
SELECT * FROM rse_daily_transports WHERE weekly_data_id = 1;
```

### 5. Tester la modification
```bash
# Ouvrir la page avec le token récupéré en DB
firefox "http://localhost:9000/rse-edit-week.html?token=<VOTRE_TOKEN>"
```

### 6. Vérifier la validation
```bash
# Cliquer sur "Confirmer mes trajets" dans l'email ou la page
# Puis vérifier en DB:
SELECT confirmed, confirmed_at FROM rse_weekly_data WHERE id = 1;
```

---

## 🧪 Test Manuel

### Générer un email de test

```bash
python3 test_weekly_email.py "votre.email@example.com" "2026-01-17"
```

Cela génère :
- Un fichier `test_weekly_email.html` pour visualiser le rendu
- Les liens de confirmation et modification dans la console

### Visualiser l'email

```bash
# Ouvrir dans le navigateur
firefox test_weekly_email.html
# ou
google-chrome test_weekly_email.html
```

### Tester la page de modification

```bash
# Ouvrir directement
firefox rse-edit-week.html?token=test_token_abc123xyz456
```

---

## 🔧 API Endpoints

### POST `/api/v2/rse/users`
Crée un nouvel utilisateur RSE.

**Body (JSON):**
```json
{
  "name": "Arnaud Mojito",
  "email": "arnaud@mojito.co",
  "departure_address": "123 Rue de la Paix, Paris",
  "destination_address": "456 Avenue des Champs, Paris",
  "distance_km": 25.0
}
```

**Réponse:**
```json
{
  "success": true,
  "user_id": 1,
  "message": "Utilisateur créé avec succès"
}
```

---

### POST `/api/v2/rse/send-weekly-recap`

Envoie le récapitulatif hebdomadaire. **Crée automatiquement** les entrées en DB si elles n'existent pas.

**Paramètres (JSON):**
```json
{
  "test_email": "test@example.com",    // Optionnel: pour test
  "week_end_date": "2026-01-17"        // Optionnel: défaut = dernier vendredi
}
```

**Ce qui se passe en DB:**
1. Récupère tous les `rse_users` actifs (ou filtré par `test_email`)
2. Pour chaque utilisateur:
   - Vérifie si une entrée `rse_weekly_data` existe pour la semaine
   - Si non: crée l'entrée + 5 jours dans `rse_daily_transports` (défaut: voiture_solo)
   - Si oui: charge les données existantes
3. Envoie l'email avec le magic token
4. Marque `email_sent = 1` et `email_sent_at = NOW()`

**Exemple:**
```bash
curl -X POST http://localhost:9000/api/v2/rse/send-weekly-recap \
  -H "Content-Type: application/json" \
  -d '{"test_email": "arnaud@mojito.co"}'
```

---

### GET `/api/v2/rse/weekly-data/<token>`

Récupère les données hebdomadaires pour un token. **Utilisé par rse-edit-week.html**.

**Réponse:**
```json
{
  "week_start": "2026-01-13",
  "week_end": "2026-01-17",
  "distance_km": 25.0,
  "confirmed": false,
  "user_name": "Arnaud Mojito",
  "days": [
    {
      "date": "2026-01-13",
      "day_name": "Lundi",
      "transport_modes": {
        "aller": "voiture_solo",
        "retour": "covoiturage"
      }
    }
    // ... 4 autres jours
  ]
}
```

---

### PUT `/api/v2/rse/weekly-data/<token>`

Met à jour les trajets hebdomadaires. **Recalcule automatiquement le CO2**.

**Body (JSON):**
```json
{
  "days": [
    {
      "date": "2026-01-13",
      "day_name": "Lundi",
      "transport_modes": {
        "aller": "velo",
        "retour": "velo"
      }
    }
    // ... 4 autres jours
  ]
}
```

**Ce qui se passe:**
1. Récupère les facteurs d'émission depuis `rse_emission_factors`
2. Pour chaque jour:
   - Calcule `co2_aller = facteur * distance_km`
   - Calcule `co2_retour = facteur * distance_km`
   - Update `rse_daily_transports`
3. Calcule `total_co2` de la semaine
4. Update `rse_weekly_data.total_co2`

**Réponse:**
```json
{
  "success": true,
  "total_co2": 12.5
}
```

---

### GET `/api/v2/rse/weekly-confirm?token=xxx`

Valide les trajets (lien depuis l'email). **Persiste en DB**.

**Ce qui se passe:**
```sql
UPDATE rse_weekly_data 
SET confirmed = 1, confirmed_at = NOW()
WHERE magic_token = ? AND confirmed = 0
```

**Retour:** Page HTML de confirmation animée.

---

## 🔧 API Endpoints

## 📊 Structure des Données

### Format `week_data`

```python
{
    'week_start': '2026-01-13',         # Lundi
    'week_end': '2026-01-17',           # Vendredi
    'total_co2': 19.5,                  # kg CO₂
    'total_distance': 150.0,            # km (aller-retour sur 5 jours)
    'days': [
        {
            'date': '2026-01-13',
            'day_name': 'Lundi',
            'transport_modes': {
                'aller': 'voiture_solo',
    ✅ FAIT
- [x] Créer tables SQL
- [x] Endpoint création utilisateur
- [x] Endpoint envoi récap avec création auto des données
- [x] Endpoint récupération données par token
- [x] Endpoint mise à jour trajets
- [x] Endpoint confirmation
- [x] Page HTML interactive avec chargement API
- [x] Calcul automatique CO2
- [x] Scripts de test

### 🔲 À FAIRE

#### Base de Données
- [ ] Migration pour copier les données depuis `rse/submit` existantes
- [ ] Index de performance sur les requêtes fréquentes
- [ ] Archivage des données anciennes (> 1 an)

#### Fonctionnalités
- [ ] Pré-remplissage semaine N à partir de semaine N-1 (habitudes)
- [ ] Statistiques mensuelles/annuelles par utilisateur
- [ ] Export CSV des données
- [ ] Tableau de bord admin (nombre validations, stats CO2, etc.)
- [ ] Email de relance si pas validé après 3 jours

#### Automatisation
- [ ] Cron job Python pour envoi automatique vendredis 16h
- [ ] Alternative: Celery Beat task
- [ ] Logs d'envoi centralisés
- [ ] Alerting si échec d'envoi

#### Email
- [ ] Test rendu sur Gmail, Outlook, Apple Mail, Thunderbird
- [ ] Version mobile optimisée (grille responsive)
- [ ] Lien de désinscription
- [ ] Préférences utilisateur (fréquence, langue)
---

## 🎨 Design

### Email
- **Couleurs:** Dégradé violet/indigo (#667eea → #764ba2)
- **Layout:** Grid responsive 5 colonnes pour desktop, empilé sur mobile
- **CO₂ Badge:** Couleur adaptative selon le niveau d'émissions
  - < 5 kg : 🟢 Vert (#10b981)
  - 5-15 kg : 🟠 Orange (#f59e0b)
  - > 15 kg : 🔴 Rouge (#ef4444)

### Page de Modification
- **Style:** Cards avec hover effects
- **Interactivité:** Sélection radio avec visual feedback
- **Responsive:** Grid adaptatif pour tous les écrans

---

## 🔐 Sécurité

- **Magic Links:** Token unique généré pour chaque utilisateur (`secrets.token_urlsafe(32)`)
- **Validation:** Token vérifié avant toute action
- **Expiration:** TODO - Ajouter expiration 7 jours après envoi

---

## 📝 TODO / Prochaines Étapes

### Base de Données
- [ ] Créer table `rse_users` (id, name, email, active, distance_km)
- [ ] Créer table `rse_weekly_data` (id, user_id, week_start, token, confirmed, created_at)
- [ ] Créer table `rse_daily_transports` (id, weekly_data_id, date, transport_aller, transport_retour)

### Fonctionnalités
- [ ] Récupération des vraies données depuis DB
- [ ] Sauvegarde des modifications depuis `rse-edit-week.html`
- [ ] Endpoint de récupération des données par token
- [ ] Tracking des validations (qui a confirmé, quand)
- [ ] Statistiques mensuelles/annuelles

### Automatisation
- [ ] Cron job Python pour envoi automatique vendredis 16h
- [ ] Alternative: Celery Beat task
- [ ] Logs d'envoi (succès/échecs)

### Email
- [ ] Test sur Gmail, Outlook, Apple Mail
- [ ] Version mobile optimisée
- [ ] Footer avec lien de désinscription

---

## 🚀 Mise en Production

### Configuration Cron

```bash
# Éditer crontab
crontab -e

# Ajouter la ligne (tous les vendredis à 16h)
0 16 * * 5 cd /path/to/carette && python3 send_weekly_recaps.py >> /var/log/carette/weekly_recaps.log 2>&1
```

### Script Production

Créer `send_weekly_recaps.py`:
```python
#!/usr/bin/env python3
import requests
import logging

logging.basicConfig(level=logging.INFO)

response = requests.post('http://localhost:9000/api/v2/rse/send-weekly-recap', json={})
logging.info(f"Status: {response.status_code}, Response: {response.json()}")
```

---

## 📧 Contact

Pour toute question : arnaud@mojito.co

---

**Version:** 1.0  
**Dernière mise à jour:** 18 janvier 2026
