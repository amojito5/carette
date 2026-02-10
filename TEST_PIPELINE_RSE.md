# 🧪 Guide de Test du Pipeline RSE Complet

## 🎯 Objectif
Tester le workflow complet de A à Z : Widget → Habitudes → Email Vendredi → 3 Boutons → Auto-Confirmation → Récaps Mensuels

---

## 📋 Checklist Rapide

- [ ] 1. Redémarrer le serveur (créer nouvelles tables)
- [ ] 2. Créer une entreprise
- [ ] 3. Soumettre via widget (créer habitudes)
- [ ] 4. Vérifier les habitudes en DB
- [ ] 5. Envoyer email vendredi
- [ ] 6. Tester bouton "Confirmer"
- [ ] 7. Tester bouton "Modifier" + checkbox habitudes
- [ ] 8. Tester bouton "Absent/Congés"
- [ ] 9. Tester auto-confirmation (7 jours)
- [ ] 10. Générer récap mensuel (user + company)

---

## 🚀 Étape 1 : Préparer l'Environnement

### 1.1 Redémarrer le serveur

```bash
cd /home/ubuntu/projects/carette

# Arrêter le serveur
pkill -f "python.*api.py"

# Redémarrer (crée les nouvelles tables)
nohup python3 backend/api.py > logs/api.log 2>&1 &

# Vérifier les logs
tail -f logs/api.log
# Attendre de voir "✅ Table rse_user_habits créée/vérifiée"
# Attendre de voir "✅ Table companies créée/vérifiée"
```

### 1.2 Vérifier les tables créées

```bash
mysql -u root -pCarette2025! carette -e "
SHOW TABLES LIKE 'rse%';
SHOW TABLES LIKE 'companies';
"
```

**Résultat attendu :**
```
rse_daily_transports
rse_emission_factors
rse_user_habits         ← NOUVEAU
rse_users
rse_weekly_data
companies               ← NOUVEAU
```

---

## 🏢 Étape 2 : Créer une Entreprise

```bash
# Créer l'entreprise "TechCorp"
curl -X POST http://localhost:9000/api/v2/companies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TechCorp SARL",
    "siren": "123456789",
    "contact_email": "rh@techcorp.fr",
    "contact_name": "Marie Dupont",
    "address": "42 Avenue de la République, 75011 Paris"
  }'
```

**Résultat attendu :**
```json
{
  "success": true,
  "company_id": 1,
  "message": "Entreprise créée avec succès"
}
```

**Note :** Gardez le `company_id` (ici : 1) pour la suite

---

## 👤 Étape 3 : Première Déclaration via Widget

### 3.1 Ouvrir le widget dans le navigateur

```bash
# Ouvrir dans le navigateur
firefox http://localhost:9000/demo.html &
# Ou
google-chrome http://localhost:9000/demo.html &
```

### 3.2 Remplir le formulaire RSE

**Mode RSE :**
1. Cliquer sur le bouton "Mode RSE" en haut
2. Remplir :
   - Nom : `Jean Martin`
   - Email : `jean.martin@techcorp.fr`
   - Téléphone : `0601020304`
   - Départ : `Paris 10eme`
   - Destination : `La Defense`
   - Distance : `15` km

3. Sélectionner les transports :
   - **Lundi** : 🚌 Transports en commun
   - **Mardi** : 🚌 Transports en commun
   - **Mercredi** : 🚴 Vélo
   - **Jeudi** : 🚌 Transports en commun
   - **Vendredi** : 🏠 Télétravail

4. Cliquer sur "Soumettre mon bilan carbone"

**Résultat attendu :**
- ✅ Message de confirmation
- ✅ Total CO2 affiché (~5.4 kg)

### 3.3 Vérifier en base de données

```bash
mysql -u root -pCarette2025! carette -e "
-- Utilisateur créé
SELECT id, name, email, distance_km, company_id FROM rse_users WHERE email='jean.martin@techcorp.fr';

-- Habitudes sauvegardées (NOUVEAU)
SELECT * FROM rse_user_habits WHERE user_id=(SELECT id FROM rse_users WHERE email='jean.martin@techcorp.fr');

-- Semaine courante créée
SELECT id, week_start, week_end, total_co2, confirmed FROM rse_weekly_data WHERE user_id=(SELECT id FROM rse_users WHERE email='jean.martin@techcorp.fr');

-- 7 jours créés
SELECT date, day_name, transport_aller, transport_retour, co2_aller, co2_retour FROM rse_daily_transports WHERE weekly_data_id=(SELECT id FROM rse_weekly_data WHERE user_id=(SELECT id FROM rse_users WHERE email='jean.martin@techcorp.fr') ORDER BY created_at DESC LIMIT 1);
"
```

**Résultat attendu pour `rse_user_habits` :**
```
monday_aller: transports_commun
monday_retour: transports_commun
tuesday_aller: transports_commun
tuesday_retour: transports_commun
wednesday_aller: velo
wednesday_retour: velo
thursday_aller: transports_commun
thursday_retour: transports_commun
friday_aller: teletravail
friday_retour: teletravail
```

---

## 🏢 Étape 4 : Assigner l'Employé à l'Entreprise

```bash
# Assigner Jean Martin à TechCorp (company_id=1)
curl -X POST http://localhost:9000/api/v2/companies/1/employees \
  -H "Content-Type: application/json" \
  -d '{"user_email": "jean.martin@techcorp.fr"}'
```

**Vérifier :**
```bash
mysql -u root -pCarette2025! carette -e "
SELECT u.id, u.name, u.email, u.company_id, c.name as company_name 
FROM rse_users u 
LEFT JOIN companies c ON u.company_id = c.id 
WHERE u.email='jean.martin@techcorp.fr';
"
```

**Résultat attendu :**
```
company_id: 1
company_name: TechCorp SARL
```

---

## 📧 Étape 5 : Envoyer l'Email Vendredi

### 5.1 Supprimer la semaine courante (pour tester la duplication depuis habitudes)

```bash
mysql -u root -pCarette2025! carette -e "
DELETE FROM rse_daily_transports WHERE weekly_data_id IN (
  SELECT id FROM rse_weekly_data WHERE user_id=(SELECT id FROM rse_users WHERE email='jean.martin@techcorp.fr')
);
DELETE FROM rse_weekly_data WHERE user_id=(SELECT id FROM rse_users WHERE email='jean.martin@techcorp.fr');
"
```

### 5.2 Envoyer l'email de récap

```bash
# Envoyer uniquement à Jean Martin (test)
curl -X POST http://localhost:9000/api/v2/rse/send-weekly-recap \
  -H "Content-Type: application/json" \
  -d '{"test_email": "jean.martin@techcorp.fr"}'
```

**Résultat attendu dans les logs :**
```
✨ Semaine créée depuis habitudes pour jean.martin@techcorp.fr
✅ Email envoyé à jean.martin@techcorp.fr
```

### 5.3 Vérifier en DB que la semaine a été créée depuis les habitudes

```bash
mysql -u root -pCarette2025! carette -e "
SELECT dt.date, dt.day_name, dt.transport_aller, dt.transport_retour, dt.co2_aller, dt.co2_retour
FROM rse_daily_transports dt
JOIN rse_weekly_data wd ON dt.weekly_data_id = wd.id
WHERE wd.user_id=(SELECT id FROM rse_users WHERE email='jean.martin@techcorp.fr')
ORDER BY dt.date;
"
```

**Résultat attendu :**
- Lundi : `transports_commun` / `transports_commun` (CO2 ≠ 0)
- Mardi : `transports_commun` / `transports_commun` (CO2 ≠ 0)
- Mercredi : `velo` / `velo` (CO2 = 0)
- Jeudi : `transports_commun` / `transports_commun` (CO2 ≠ 0)
- Vendredi : `teletravail` / `teletravail` (CO2 = 0)

### 5.4 Récupérer le magic link depuis l'email

**Option A : Logs du serveur**
```bash
grep "magic_link" logs/api.log | tail -1
```

**Option B : Base de données**
```bash
mysql -u root -pCarette2025! carette -e "
SELECT magic_token FROM rse_weekly_data 
WHERE user_id=(SELECT id FROM rse_users WHERE email='jean.martin@techcorp.fr') 
ORDER BY created_at DESC LIMIT 1;
"
```

Gardez ce token pour la suite (ex: `abc123def456...`)

---

## ✅ Étape 6 : Tester le Bouton "Confirmer"

```bash
# Remplacer TOKEN par le magic_token récupéré
TOKEN="abc123def456..."

# Cliquer sur "Confirmer"
curl "http://localhost:9000/api/v2/rse/weekly-confirm?token=$TOKEN"
```

**Résultat attendu :**
- Page verte avec ✅ "Trajets confirmés !"
- Affichage du CO2 total

**Vérifier en DB :**
```bash
mysql -u root -pCarette2025! carette -e "
SELECT confirmed, confirmed_at, total_co2 FROM rse_weekly_data WHERE magic_token='$TOKEN';
"
```

**Résultat :**
```
confirmed: 1
confirmed_at: 2026-01-25 14:23:45
total_co2: 5.4 (ou similaire)
```

---

## ✏️ Étape 7 : Tester le Bouton "Modifier" + Checkbox Habitudes

### 7.1 Réinitialiser la confirmation

```bash
mysql -u root -pCarette2025! carette -e "
UPDATE rse_weekly_data SET confirmed=0, confirmed_at=NULL WHERE magic_token='$TOKEN';
"
```

### 7.2 Ouvrir le magic link

```bash
firefox "http://localhost:9000/rse-edit-week.html?token=$TOKEN" &
# Ou
google-chrome "http://localhost:9000/rse-edit-week.html?token=$TOKEN" &
```

### 7.3 Modifier les transports

1. Changer **Mercredi** de 🚴 Vélo à 🚗👥 Covoiturage
2. **Cocher la case** "💾 Enregistrer comme mes nouvelles habitudes par défaut"
3. Cliquer sur "✅ Valider mes trajets"

**Résultat attendu :**
- Redirect vers page verte de confirmation
- Total CO2 a augmenté (covoiturage > vélo)

### 7.4 Vérifier que les HABITUDES ont changé

```bash
mysql -u root -pCarette2025! carette -e "
SELECT wednesday_aller, wednesday_retour 
FROM rse_user_habits 
WHERE user_id=(SELECT id FROM rse_users WHERE email='jean.martin@techcorp.fr');
"
```

**Résultat attendu :**
```
wednesday_aller: covoiturage
wednesday_retour: covoiturage
```

✅ **Test réussi !** Les futures semaines utiliseront covoiturage le mercredi.

---

## 🏖️ Étape 8 : Tester le Bouton "Absent/Congés"

### 8.1 Créer une nouvelle semaine

```bash
# Re-envoyer l'email pour avoir un nouveau token
curl -X POST http://localhost:9000/api/v2/rse/send-weekly-recap \
  -H "Content-Type: application/json" \
  -d '{"test_email": "jean.martin@techcorp.fr", "week_end_date": "2026-02-07"}'

# Récupérer le nouveau token
NEW_TOKEN=$(mysql -u root -pCarette2025! carette -N -e "
SELECT magic_token FROM rse_weekly_data 
WHERE user_id=(SELECT id FROM rse_users WHERE email='jean.martin@techcorp.fr') 
AND week_start='2026-02-03';
")

echo "Nouveau token: $NEW_TOKEN"
```

### 8.2 Cliquer sur "Absent/Congés"

```bash
curl "http://localhost:9000/api/v2/rse/weekly-absent?token=$NEW_TOKEN"
```

**Résultat attendu :**
- Page jaune avec 🏖️ "Congés enregistrés !"
- Message "Aucune émission CO₂ n'a été comptabilisée"

### 8.3 Vérifier en DB

```bash
mysql -u root -pCarette2025! carette -e "
SELECT transport_aller, transport_retour, co2_aller, co2_retour 
FROM rse_daily_transports 
WHERE weekly_data_id=(SELECT id FROM rse_weekly_data WHERE magic_token='$NEW_TOKEN');

SELECT confirmed, total_co2 FROM rse_weekly_data WHERE magic_token='$NEW_TOKEN';
"
```

**Résultat attendu :**
```
Tous les jours:
  transport_aller: ne_travaille_pas
  transport_retour: ne_travaille_pas
  co2_aller: 0
  co2_retour: 0

rse_weekly_data:
  confirmed: 1
  total_co2: 0
```

---

## ⏰ Étape 9 : Tester l'Auto-Confirmation (7 jours)

### 9.1 Créer une vieille semaine non confirmée (simulation)

```bash
mysql -u root -pCarette2025! carette -e "
-- Créer une semaine du 13 janvier (il y a 12 jours)
INSERT INTO rse_weekly_data 
(user_id, week_start, week_end, magic_token, total_co2, total_distance, confirmed, email_sent, created_at)
VALUES (
  (SELECT id FROM rse_users WHERE email='jean.martin@techcorp.fr'),
  '2026-01-13',
  '2026-01-17',
  'old_week_token_123',
  0,
  150,
  0,
  1,
  '2026-01-17 10:00:00'
);

-- Créer des trajets pour cette semaine
SET @old_weekly_id = LAST_INSERT_ID();

INSERT INTO rse_daily_transports (weekly_data_id, date, day_name, transport_aller, transport_retour, distance_aller, distance_retour, co2_aller, co2_retour)
VALUES
(@old_weekly_id, '2026-01-13', 'Lundi', 'transports_commun', 'transports_commun', 15, 15, 0.9, 0.9),
(@old_weekly_id, '2026-01-14', 'Mardi', 'transports_commun', 'transports_commun', 15, 15, 0.9, 0.9),
(@old_weekly_id, '2026-01-15', 'Mercredi', 'covoiturage', 'covoiturage', 15, 15, 1.65, 1.65),
(@old_weekly_id, '2026-01-16', 'Jeudi', 'transports_commun', 'transports_commun', 15, 15, 0.9, 0.9),
(@old_weekly_id, '2026-01-17', 'Vendredi', 'teletravail', 'teletravail', 0, 0, 0, 0);
"
```

### 9.2 Lancer l'auto-confirmation

```bash
# Via API
curl -X POST http://localhost:9000/api/v2/rse/auto-confirm-old-weeks

# Ou via cron job
cd /home/ubuntu/projects/carette/backend
python3 cron_jobs.py auto-confirm-rse
```

**Résultat attendu :**
```json
{
  "success": true,
  "message": "1 semaine(s) auto-confirmée(s)",
  "auto_confirmed": 1,
  "details": [
    {
      "user": "Jean Martin",
      "email": "jean.martin@techcorp.fr",
      "week_start": "2026-01-13"
    }
  ]
}
```

### 9.3 Vérifier en DB

```bash
mysql -u root -pCarette2025! carette -e "
SELECT confirmed, confirmed_at, total_co2 
FROM rse_weekly_data 
WHERE magic_token='old_week_token_123';
"
```

**Résultat attendu :**
```
confirmed: 1
confirmed_at: 2026-01-25 14:45:32
total_co2: 7.8 (0.9+0.9+1.65+1.65+0.9+0.9+0+0)
```

✅ **Auto-confirmation réussie !**

---

## 📊 Étape 10 : Générer les Récaps Mensuels

### 10.1 Récap par employé (Jean Martin)

```bash
# Récap de janvier 2026
JEAN_ID=$(mysql -u root -pCarette2025! carette -N -e "
SELECT id FROM rse_users WHERE email='jean.martin@techcorp.fr';
")

curl "http://localhost:9000/api/v2/rse/monthly-recap/user/$JEAN_ID?year=2026&month=1" | jq
```

**Résultat attendu :**
```json
{
  "user": {
    "id": 1,
    "name": "Jean Martin",
    "email": "jean.martin@techcorp.fr",
    "company": "TechCorp SARL"
  },
  "summary": {
    "total_co2_kg": 13.2,
    "total_distance_km": 300.0,
    "total_working_days": 10,
    "weeks_count": 2,
    "weeks_confirmed": 2
  },
  "transport_breakdown": {
    "transports_commun": { ... },
    "velo": { ... },
    "covoiturage": { ... },
    "teletravail": { ... }
  }
}
```

### 10.2 Récap par entreprise (TechCorp)

```bash
curl "http://localhost:9000/api/v2/rse/monthly-recap/company/1?year=2026&month=1" | jq
```

**Résultat attendu :**
```json
{
  "company": {
    "id": 1,
    "name": "TechCorp SARL",
    "contact": "Marie Dupont"
  },
  "summary": {
    "total_employees": 1,
    "active_employees": 1,
    "total_co2_kg": 13.2,
    "avg_co2_per_employee": 13.2
  },
  "transport_breakdown": { ... },
  "top_employees": [
    {
      "id": 1,
      "name": "Jean Martin",
      "co2_kg": 13.2
    }
  ]
}
```

---

## 🎯 Test Complet avec Plusieurs Employés

### Créer 3 employés avec profils différents

```bash
# Employé 1 : Écolo (vélo + transports)
curl -X POST http://localhost:9000/api/v2/rse/submit \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "Sophie Ecolo",
    "user_email": "sophie@techcorp.fr",
    "departure": "Paris 11eme",
    "destination": "Paris 8eme",
    "distance_km": 8,
    "transport_modes": {
      "monday": 3,
      "tuesday": 3,
      "wednesday": 1,
      "thursday": 3,
      "friday": 5
    },
    "co2_emissions": {
      "monday": 0,
      "tuesday": 0,
      "wednesday": 0.96,
      "thursday": 0,
      "friday": 0
    },
    "total_co2": 0.96
  }'

# Employé 2 : Voiture solo
curl -X POST http://localhost:9000/api/v2/rse/submit \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "Pierre Voiture",
    "user_email": "pierre@techcorp.fr",
    "departure": "Banlieue Sud",
    "destination": "La Defense",
    "distance_km": 25,
    "transport_modes": {
      "monday": 0,
      "tuesday": 0,
      "wednesday": 0,
      "thursday": 0,
      "friday": 5
    },
    "co2_emissions": {
      "monday": 11.0,
      "tuesday": 11.0,
      "wednesday": 11.0,
      "thursday": 11.0,
      "friday": 0
    },
    "total_co2": 44.0
  }'

# Employé 3 : Mix équilibré
curl -X POST http://localhost:9000/api/v2/rse/submit \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "Marie Mix",
    "user_email": "marie@techcorp.fr",
    "departure": "Paris 15eme",
    "destination": "La Defense",
    "distance_km": 12,
    "transport_modes": {
      "monday": 1,
      "tuesday": 2,
      "wednesday": 3,
      "thursday": 1,
      "friday": 5
    },
    "co2_emissions": {
      "monday": 1.44,
      "tuesday": 2.64,
      "wednesday": 0,
      "thursday": 1.44,
      "friday": 0
    },
    "total_co2": 5.52
  }'

# Assigner à l'entreprise
for email in sophie@techcorp.fr pierre@techcorp.fr marie@techcorp.fr; do
  curl -X POST http://localhost:9000/api/v2/companies/1/employees \
    -H "Content-Type: application/json" \
    -d "{\"user_email\": \"$email\"}"
done

# Envoyer les emails vendredi
curl -X POST http://localhost:9000/api/v2/rse/send-weekly-recap \
  -H "Content-Type: application/json" \
  -d '{}'

# Récap entreprise
curl "http://localhost:9000/api/v2/rse/monthly-recap/company/1?year=2026&month=1" | jq
```

**Résultat attendu :**
- 4 employés au total
- Top 3 : Pierre (voiture) > Marie (mix) > Sophie/Jean (écolos)
- Répartition transports visible

---

## ✅ Checklist de Validation Finale

| Test | Statut | Vérification |
|------|--------|--------------|
| Tables créées | ☐ | `rse_user_habits`, `companies` existent |
| Widget → Habitudes | ☐ | Données dans `rse_user_habits` |
| Email vendredi | ☐ | Semaine créée depuis habitudes |
| Bouton Confirmer | ☐ | `confirmed=1` en DB |
| Bouton Modifier | ☐ | Modifications sauvegardées |
| Checkbox habitudes | ☐ | `rse_user_habits` mis à jour |
| Bouton Absent | ☐ | Tous les jours = `ne_travaille_pas` |
| Auto-confirmation | ☐ | Vieilles semaines confirmées |
| Récap user | ☐ | JSON complet avec breakdown |
| Récap company | ☐ | Agrégation + top employés |

---

## 🐛 Dépannage

### Erreur : "Table doesn't exist"
```bash
# Relancer les migrations
cd /home/ubuntu/projects/carette
pkill -f "python.*api.py"
python3 backend/init_carpool_tables.py
nohup python3 backend/api.py > logs/api.log 2>&1 &
```

### Email non reçu
```bash
# Vérifier les logs SMTP
grep "SMTP" logs/api.log | tail -20

# Vérifier la config email
cat .env | grep EMAIL
```

### Magic link ne fonctionne pas
```bash
# Vérifier le token en DB
mysql -u root -pCarette2025! carette -e "
SELECT magic_token, week_start, confirmed FROM rse_weekly_data ORDER BY created_at DESC LIMIT 5;
"
```

### Récap vide
```bash
# Vérifier les semaines confirmées
mysql -u root -pCarette2025! carette -e "
SELECT u.name, wd.week_start, wd.confirmed, wd.total_co2 
FROM rse_weekly_data wd 
JOIN rse_users u ON wd.user_id = u.id 
WHERE wd.week_start >= '2026-01-01';
"
```

---

## 🎉 Résumé

Si tous les tests passent, vous avez un **pipeline RSE 100% fonctionnel** :

✅ Widget → Habitudes sauvegardées  
✅ Email vendredi → Duplication depuis habitudes  
✅ 3 boutons fonctionnels (Confirmer/Modifier/Absent)  
✅ Modification des habitudes via checkbox  
✅ Auto-confirmation après 7 jours  
✅ Récaps mensuels complets (user + company)  
✅ Gestion multi-entreprises

**🚀 Prêt pour la production !**
