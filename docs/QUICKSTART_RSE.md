# 🚀 Démarrage Rapide - Système RSE Hebdomadaire

## Installation Automatique

### 1️⃣ Démarrer le serveur (crée les tables automatiquement)
```bash
cd /home/ubuntu/projects/carette
python3 backend/api.py
```

**Au démarrage, vous verrez :**
```
🔄 Initialisation des tables carpool...
  ✅ Table carpool_offers créée/vérifiée
  ✅ Table carpool_reservations créée/vérifiée
  ...
✅ Initialisation des tables carpool terminée
🔄 Initialisation des tables RSE...
  ✅ Table rse_users créée/vérifiée
  ✅ Table rse_weekly_data créée/vérifiée
  ✅ Table rse_daily_transports créée/vérifiée
  ✅ Table rse_emission_factors créée/vérifiée
  ➕ Facteurs d'émission ADEME insérés (8 modes de transport)
✅ Initialisation des tables RSE terminée
✅ Tables carpool initialisées
✅ Tables RSE initialisées
```

> **Les tables sont créées automatiquement au premier démarrage !** Pas besoin de script séparé.

---

### 2️⃣ Créer un utilisateur de test
```bash
python3 create_test_user.py "Arnaud Mojito" "arnaud@mojito.co" 25
```

**Résultat attendu:**
```
✅ Utilisateur créé:
   ID: 1
   Nom: Arnaud Mojito
   Email: arnaud@mojito.co
   Distance: 25.0 km
```

---

### 3️⃣ Envoyer un email de test

**Dans un autre terminal (le serveur doit tourner) :**
```bash
curl -X POST http://localhost:9000/api/v2/rse/send-weekly-recap \
  -H "Content-Type: application/json" \
  -d '{"test_email": "arnaud@mojito.co"}'
```

**Résultat attendu:**
```json
{
  "success": true,
  "message": "1 email(s) envoyé(s)",
  "week": "2026-01-13 → 2026-01-17"
}
```

---

### 4️⃣ Récupérer le token et tester

#### Option A: Depuis la DB
```sql
SELECT magic_token FROM rse_weekly_data WHERE user_id = 1 ORDER BY id DESC LIMIT 1;
```

Copier le token, puis:
```bash
firefox "http://localhost:9000/rse-edit-week.html?token=<VOTRE_TOKEN>"
```

#### Option B: Générer un email HTML
```bash
python3 test_weekly_email.py "arnaud@mojito.co" "2026-01-17"
firefox test_weekly_email.html
# Cliquer sur "Modifier mes trajets" dans l'email
```

---

## 🧪 Tester le Cycle Complet

### Scénario: Modifier et valider

1. **Ouvrir la page de modification** (avec le token de l'étape 5)

2. **Modifier les transports**
   - Lundi: Changer aller et retour en "Vélo" 🚴
   - Observer le CO2 diminuer en temps réel

3. **Cliquer sur "✅ Valider mes trajets"**
   - Page de confirmation s'affiche

4. **Vérifier en DB:**
```sql
-- Voir si confirmé
SELECT confirmed, confirmed_at, total_co2 
FROM rse_weekly_data 
WHERE user_id = 1 
ORDER BY id DESC LIMIT 1;

-- Voir les trajets modifiés
SELECT date, day_name, transport_aller, transport_retour, co2_aller, co2_retour
FROM rse_daily_transports
WHERE weekly_data_id = 1
ORDER BY date;
```

---

## 📊 Vérifications Post-Installation

> **Note :** Les tables sont créées automatiquement au démarrage du serveur.

### Vérifier les tables
```sql
SHOW TABLES LIKE 'rse_%';
```
**Attendu:** 4 tables

### Vérifier les facteurs d'émission
```sql
SELECT transport_code, transport_name, co2_per_km 
FROM rse_emission_factors 
ORDER BY display_order;
```
**Attendu:** 8 lignes (voiture_solo, transports_commun, covoiturage, vélo, train, télétravail, marche, absent)

### Vérifier l'utilisateur de test
```sql
SELECT id, name, email, distance_km, active 
FROM rse_users;
```

---

## 🔄 Réinitialiser pour un Nouveau Test

```sql
-- Supprimer les données de test (garde les tables et facteurs)
TRUNCATE TABLE rse_daily_transports;
TRUNCATE TABLE rse_weekly_data;
DELETE FROM rse_users WHERE id = 1;
```

Puis refaire à partir de l'étape 2.

---

## 🎯 Points de Validation

- [ ] Tables créées sans erreur
- [ ] Utilisateur créé (visible en DB)
- [ ] Email envoyé (retour API success: true)
- [ ] Email_sent = 1 en DB
- [ ] Token généré et présent en DB
- [ ] Page de modification charge les données (appel GET /api/v2/rse/weekly-data/<token>)
- [ ] Modification des transports met à jour le CO2 affiché
- [ ] Validation sauvegarde en DB (appel PUT)
- [ ] Confirmed = 1 après validation
- [ ] Page de confirmation s'affiche

---

## ❌ Dépannage

### "Table already exists"
✅ Normal si vous relancez `init_rse_weekly_tables.py` - les tables utilisent `CREATE TABLE IF NOT EXISTS`

### "Token invalide"
- Vérifiez que le token dans l'URL correspond bien à celui en DB
- Le token est sensible à la casse

### "Impossible de charger les données"
- Vérifiez que le serveur Flask est démarré
- Vérifiez l'URL: doit être `/api/v2/rse/weekly-data/<token>` (pas de `?token=`)

### CO2 reste à 0
- Vérifiez que `rse_emission_factors` contient les 8 facteurs
- Vérifiez que `distance_km` n'est pas NULL dans `rse_users`

---

## 📞 Support

Logs Flask pour débugger:
```bash
# Démarrer avec logs verbeux
python3 backend/api.py
# Observer les logs lors de chaque appel API
```

Logs SQL:
```python
# Dans backend/sql.py, activer les logs:
logging.basicConfig(level=logging.DEBUG)
```

---

**Documentation complète:** [WEEKLY_RSE_RECAP.md](./WEEKLY_RSE_RECAP.md)  
**Flux de données:** [RSE_DATA_FLOW.md](./RSE_DATA_FLOW.md)
