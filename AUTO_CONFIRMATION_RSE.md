# 🤷 Gestion des Semaines Non Validées

## ❓ Problème

**Que se passe-t-il si un employé oublie de cliquer sur les boutons de l'email vendredi ?**

### Scénario
1. Vendredi : Email envoyé avec données par défaut (basées sur habitudes)
2. Employé reçoit 3 boutons : ✅ Confirmer / ✏️ Modifier / 🏖️ Absent
3. Employé **ne fait rien** (oubli, vacances, flemme...)
4. ⚠️ La semaine reste `confirmed = 0` en base

### Conséquences
- ❌ Dans les récaps mensuels, on filtre sur `confirmed = 1`
- ❌ Les données non confirmées **ne sont pas comptabilisées**
- ❌ Sous-estimation des émissions CO2 réelles

---

## ✅ Solution Implémentée : Auto-Confirmation Automatique

### 🎯 Logique

**Si un employé ne répond pas dans les 7 jours, on considère que c'est une validation tacite.**

Les données par défaut (basées sur ses habitudes) sont automatiquement confirmées.

### 🔧 Fonctionnement

1. **Vendredi 10 janvier** : Email envoyé → `confirmed = 0`, `email_sent = 1`
2. **Lundi-Jeudi** : Employé peut encore cliquer sur les boutons
3. **Vendredi 17 janvier** (7 jours après) : **Auto-confirmation automatique**
   - Recalcul du CO2 depuis les trajets quotidiens
   - `confirmed = 1`, `confirmed_at = NOW()`
   - Log dans les fichiers

### 📅 Cron Job

```bash
# Ajouté dans cron_jobs.py
# S'exécute tous les jours à 2h du matin
0 2 * * * cd /home/ubuntu/projects/carette/backend && python3 cron_jobs.py auto-confirm-rse
```

---

## 🛠️ Endpoint API

### Auto-Confirmer Manuellement

```bash
POST /api/v2/rse/auto-confirm-old-weeks
```

**Exemple :**
```bash
curl -X POST http://localhost:9000/api/v2/rse/auto-confirm-old-weeks
```

**Réponse :**
```json
{
  "success": true,
  "message": "3 semaine(s) auto-confirmée(s)",
  "auto_confirmed": 3,
  "details": [
    {
      "user": "Jean Martin",
      "email": "jean.martin@example.com",
      "week_start": "2026-01-06"
    },
    {
      "user": "Sophie Leroux",
      "email": "sophie.leroux@example.com",
      "week_start": "2026-01-06"
    },
    {
      "user": "Pierre Dubois",
      "email": "pierre.dubois@example.com",
      "week_start": "2026-01-13"
    }
  ]
}
```

---

## 📊 Requête SQL de Vérification

```sql
-- Voir les semaines qui seront auto-confirmées
SELECT 
    u.name,
    u.email,
    wd.week_start,
    wd.week_end,
    wd.confirmed,
    DATEDIFF(NOW(), wd.week_end) as days_since_week_end
FROM rse_weekly_data wd
JOIN rse_users u ON wd.user_id = u.id
WHERE wd.confirmed = 0
AND wd.email_sent = 1
AND wd.week_end < NOW() - INTERVAL 7 DAY
ORDER BY wd.week_end DESC;
```

---

## 🔄 Workflow Complet

```
┌─────────────────────────────────────────────────────────┐
│ VENDREDI (J+0) - 10h00                                 │
├─────────────────────────────────────────────────────────┤
│ Email envoyé à tous les employés                        │
│ Données : basées sur habitudes (rse_user_habits)       │
│ État : confirmed = 0, email_sent = 1                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ LUNDI-JEUDI (J+3 à J+6)                                │
├─────────────────────────────────────────────────────────┤
│ Employé peut cliquer sur :                              │
│   ✅ Confirmer → confirmed = 1 immédiatement           │
│   ✏️ Modifier → ouvre magic link                       │
│   🏖️ Absent → tous les jours = ne_travaille_pas       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ VENDREDI SUIVANT (J+7) - 2h00 du matin                 │
├─────────────────────────────────────────────────────────┤
│ Cron job auto-confirm-rse s'exécute                     │
│                                                          │
│ Pour chaque semaine où :                                │
│   - confirmed = 0                                       │
│   - email_sent = 1                                      │
│   - week_end < NOW() - 7 jours                          │
│                                                          │
│ ✅ AUTO-CONFIRMATION :                                  │
│   1. Recalcul CO2 depuis rse_daily_transports          │
│   2. UPDATE confirmed = 1, confirmed_at = NOW()        │
│   3. Log : "Auto-confirmé semaine du ..."              │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ RÉSULTAT                                                │
├─────────────────────────────────────────────────────────┤
│ ✅ Toutes les semaines sont confirmées                 │
│ ✅ Aucune perte de données                             │
│ ✅ Récaps mensuels complets et fiables                 │
└─────────────────────────────────────────────────────────┘
```

---

## 💡 Avantages de cette Approche

### ✅ Avantages
1. **Aucune perte de données** - Même si l'employé oublie
2. **Données réalistes** - Basées sur les habitudes déclarées
3. **Automatique** - Pas d'intervention manuelle
4. **Délai raisonnable** - 7 jours pour réagir
5. **Récaps mensuels fiables** - Toutes les semaines comptabilisées

### ⚠️ Inconvénients (limités)
1. **Si changement exceptionnel non déclaré** - Ex: l'employé était en vélo toute la semaine mais n'a pas cliqué
   - Solution : Possibilité de modifier rétroactivement via magic link
2. **Données "moins précises"** que si validées manuellement
   - Mais : Mieux vaut une estimation basée sur habitudes que rien

---

## 📝 Alternatives Non Retenues

### ❌ Option 1 : Laisser vide (non confirmé = non comptabilisé)
**Problèmes :**
- Sous-estimation massive des émissions
- Données incomplètes dans les récaps
- Mauvaise expérience utilisateur (perte de données)

### ❌ Option 2 : Email de relance
**Problèmes :**
- Surcharge email (déjà un email/semaine)
- Coût d'envoi
- Peut être ignoré aussi

### ❌ Option 3 : Inclure les non-confirmées avec flag "estimé"
**Problèmes :**
- Complexité inutile
- Confusion dans les rapports
- Difficile à expliquer aux entreprises

---

## 🧪 Test Manuel

### 1️⃣ Créer une vieille semaine non confirmée

```sql
-- Créer une semaine du 1er janvier (il y a 24 jours)
INSERT INTO rse_weekly_data 
(user_id, week_start, week_end, magic_token, total_co2, confirmed, email_sent)
VALUES 
(1, '2026-01-06', '2026-01-10', 'test_token_123', 15.5, 0, 1);
```

### 2️⃣ Lancer l'auto-confirmation

```bash
curl -X POST http://localhost:9000/api/v2/rse/auto-confirm-old-weeks
```

### 3️⃣ Vérifier le résultat

```sql
SELECT * FROM rse_weekly_data WHERE magic_token = 'test_token_123';
-- Devrait montrer : confirmed = 1, confirmed_at = NOW()
```

---

## 📊 Impact sur les Récaps Mensuels

### Avant Auto-Confirmation
```json
{
  "summary": {
    "weeks_count": 4,
    "weeks_confirmed": 2,  // ⚠️ Seulement 2 sur 4
    "total_co2_kg": 48.6   // ⚠️ Sous-estimé
  }
}
```

### Après Auto-Confirmation
```json
{
  "summary": {
    "weeks_count": 4,
    "weeks_confirmed": 4,  // ✅ Toutes confirmées
    "total_co2_kg": 97.2   // ✅ Valeur réaliste
  }
}
```

---

## 🎯 Résumé

| Critère | Valeur |
|---------|--------|
| **Délai avant auto-confirmation** | 7 jours après `week_end` |
| **Données utilisées** | Habitudes par défaut (rse_user_habits) |
| **Recalcul CO2** | Oui, depuis rse_daily_transports |
| **Fréquence cron** | Tous les jours à 2h |
| **Endpoint API** | POST /api/v2/rse/auto-confirm-old-weeks |
| **Impact** | Aucune perte de données, récaps complets |

**✅ Recommandation : Activez cette fonctionnalité pour garantir des données complètes !**
