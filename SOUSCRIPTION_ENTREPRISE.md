# 🔐 Système de Souscription Entreprise

## 🎯 Vue d'Ensemble

Système complet de gestion des entreprises avec **3 méthodes d'inscription** pour les employés :

1. **Code Entreprise** (recommandé) - Ex: `TECH2026`
2. **Clé d'Accès API** - Pour intégrations tierces
3. **Domaine Email** - Auto-détection (@techcorp.fr)

---

## 🏢 Création d'une Entreprise

### Endpoint
```
POST /api/v2/companies
```

### Exemple de Requête

```bash
curl -X POST http://localhost:9000/api/v2/companies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TechCorp SARL",
    "email_domain": "techcorp.fr",
    "siren": "123456789",
    "contact_email": "rh@techcorp.fr",
    "contact_name": "Marie Dupont",
    "address": "42 Avenue de la République, 75011 Paris"
  }'
```

### Réponse

```json
{
  "success": true,
  "company_id": 1,
  "company_code": "TECH2026",
  "access_key": "vO7xK3_p9Lm2Nq8hR5jT1wY6iU4zX0cA3bD9eF2gH8kL5mN7pQ1sT4vW6xY0zA3",
  "message": "Entreprise créée avec succès",
  "instructions": "Partagez le code 'TECH2026' avec vos employés pour qu'ils s'inscrivent."
}
```

### ⚠️ IMPORTANT : Sauvegarder les Clés

**À communiquer à l'entreprise :**
- ✅ **company_code** : `TECH2026` → À partager avec les employés
- ✅ **access_key** : `vO7xK3...` → Pour les intégrations API (garder secret)

---

## 👤 Inscription Employé

### Méthode 1 : Via le Widget avec Code Entreprise ⭐ RECOMMANDÉ

#### 1.1 L'employé ouvre le widget

```bash
firefox http://localhost:9000/demo.html
```

#### 1.2 Il remplit le formulaire RSE

- **Nom** : Jean Martin
- **Email** : jean.martin@techcorp.fr
- **Téléphone** : 06 01 02 03 04
- **🏢 Code Entreprise** : `TECH2026`  ← NOUVEAU CHAMP
- **Départ/Destination** : ...
- **Transports** : ...

#### 1.3 Soumission automatique

L'API vérifie le code `TECH2026` en base et assigne automatiquement l'employé à TechCorp.

**Logs backend :**
```
🏢 Entreprise trouvée via code 'TECH2026': TechCorp SARL
✨ Nouvel utilisateur RSE créé: jean.martin@techcorp.fr (ID: 5, Company: 1)
```

### Méthode 2 : Auto-Détection par Domaine Email

#### 2.1 Configuration requise

L'entreprise doit avoir configuré `email_domain` lors de la création :

```json
{
  "name": "TechCorp SARL",
  "email_domain": "techcorp.fr"  ← Important !
}
```

#### 2.2 Fonctionnement automatique

Si l'employé saisit `jean.martin@techcorp.fr` et **ne fournit pas de code**, l'API :
1. Extrait le domaine : `techcorp.fr`
2. Cherche une entreprise avec `email_domain = 'techcorp.fr'`
3. Assigne automatiquement l'employé

**Logs backend :**
```
🏢 Entreprise auto-détectée via domaine 'techcorp.fr': TechCorp SARL
✨ Nouvel utilisateur RSE créé: jean.martin@techcorp.fr (ID: 5, Company: 1)
```

### Méthode 3 : Assignation Manuelle (API)

#### 3.1 L'employé s'inscrit sans code

Il remplit le widget normalement → `company_id = NULL`

#### 3.2 L'admin l'assigne manuellement

```bash
curl -X POST http://localhost:9000/api/v2/companies/1/employees \
  -H "Content-Type: application/json" \
  -d '{"user_email": "jean.martin@techcorp.fr"}'
```

**Réponse :**
```json
{
  "success": true,
  "message": "Employé Jean Martin assigné à l'entreprise"
}
```

---

## 🔍 Ordre de Priorité

Lorsqu'un employé soumet le formulaire :

```
1. Code entreprise fourni ?
   ├─ OUI → Chercher company_code en DB
   │   ├─ Trouvé → Assigner
   │   └─ Pas trouvé → Continuer (warning log)
   └─ NON → Passer à l'étape 2

2. Domaine email configuré ?
   ├─ Extraire domaine de l'email
   ├─ Chercher email_domain en DB
   │   ├─ Trouvé → Assigner
   │   └─ Pas trouvé → company_id = NULL
   └─ FIN

3. company_id = NULL (assignation manuelle ultérieure)
```

---

## 📊 Structure des Tables

### Table `companies`

```sql
CREATE TABLE companies (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  
  -- Clés d'inscription
  company_code VARCHAR(20) UNIQUE,     -- Ex: TECH2026 (généré auto)
  access_key VARCHAR(64) UNIQUE,       -- Ex: vO7xK3... (généré auto)
  email_domain VARCHAR(255),           -- Ex: techcorp.fr (manuel)
  
  -- Infos entreprise
  siren VARCHAR(9),
  contact_email VARCHAR(255),
  contact_name VARCHAR(255),
  address TEXT,
  active BOOLEAN DEFAULT TRUE,
  
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### Génération Automatique des Clés

#### Company Code
- **Format** : 4 lettres + année
- **Exemple** : TechCorp SARL → `TECH2026`
- **Collision** : Si existe déjà → `TECH20261`, `TECH20262`, etc.

#### Access Key
- **Format** : Token URL-safe de 48 bytes → ~64 caractères
- **Exemple** : `vO7xK3_p9Lm2Nq8hR5jT1wY6iU4zX0cA3bD9eF2gH8kL5mN7pQ1sT4vW6xY0zA3`
- **Utilisation** : API, webhooks, intégrations

---

## 🎨 Interface Widget

### Avant (sans code entreprise)
```
┌─────────────────────────────────┐
│ 👤 Vos Informations             │
├─────────────────────────────────┤
│ Nom : [____________]            │
│ Email : [____________]          │
│ Téléphone : [____________]      │
└─────────────────────────────────┘
```

### Après (avec code entreprise)
```
┌─────────────────────────────────┐
│ 👤 Vos Informations             │
├─────────────────────────────────┤
│ Nom : [____________]            │
│ Email : [____________]          │
│ Téléphone : [____________]      │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ 🏢 Code Entreprise (optionnel)  │
├─────────────────────────────────┤
│ [TECH2026________]              │
│ 💡 Si votre entreprise vous a  │
│    fourni un code, saisissez-le │
│    ici pour être automatiquement│
│    rattaché.                    │
└─────────────────────────────────┘
```

---

## 🔐 Sécurité

### Validation du Code

```sql
SELECT id, name, email_domain 
FROM companies 
WHERE company_code = 'TECH2026' 
AND active = 1
```

**Protections :**
- ✅ Code doit exister
- ✅ Entreprise doit être active
- ✅ (Optionnel) Vérifier que email correspond au domaine

### Logs de Sécurité

```python
# Code valide
logger.info(f"🏢 Entreprise trouvée via code 'TECH2026': TechCorp SARL")

# Code invalide
logger.warning(f"⚠️ Code entreprise 'FAKE999' invalide ou inactif")

# Email ne correspond pas au domaine
logger.warning(f"⚠️ Email john@gmail.com ne correspond pas au domaine techcorp.fr")
```

---

## 📧 Communication avec l'Entreprise

### Email de Bienvenue (suggéré)

```
Objet: Bienvenue sur Carette RSE !

Bonjour Marie,

Votre entreprise TechCorp SARL est maintenant inscrite sur Carette RSE.

🔑 INFORMATIONS D'INSCRIPTION

Pour que vos employés rejoignent votre espace RSE, 
communiquez-leur ce code :

  ┌──────────────────┐
  │   TECH2026       │
  └──────────────────┘

📋 INSTRUCTIONS POUR VOS EMPLOYÉS

1. Accéder au widget : https://carette.fr/rse
2. Remplir le formulaire
3. Saisir le code TECH2026 dans le champ "Code Entreprise"
4. Valider

Vos employés seront automatiquement rattachés à TechCorp SARL.

🔐 CLÉ API (À CONSERVER)

Pour des intégrations personnalisées :
vO7xK3_p9Lm2Nq8hR5jT1wY6iU4zX0cA3bD9eF2gH8kL5mN7pQ1sT4vW6xY0zA3

📊 TABLEAU DE BORD

Accédez à vos statistiques :
https://carette.fr/dashboard/1

Cordialement,
L'équipe Carette
```

---

## 🧪 Scénarios de Test

### Test 1 : Inscription avec Code Valide

```bash
# 1. Créer l'entreprise
curl -X POST http://localhost:9000/api/v2/companies \
  -H "Content-Type: application/json" \
  -d '{"name": "TechCorp", "email_domain": "techcorp.fr"}'

# Réponse : {"company_code": "TECH2026", ...}

# 2. Widget : remplir avec code TECH2026
# → Vérifier en DB
mysql -u root -pCarette2025! carette -e "
SELECT u.name, u.email, u.company_id, c.name as company_name 
FROM rse_users u 
JOIN companies c ON u.company_id = c.id 
WHERE u.email='jean@techcorp.fr';
"

# Résultat attendu : company_id=1, company_name='TechCorp'
```

### Test 2 : Auto-Détection par Domaine

```bash
# Widget : remplir SANS code, email = jean@techcorp.fr
# → Vérifier auto-assignation
mysql -u root -pCarette2025! carette -e "
SELECT u.email, u.company_id, c.name 
FROM rse_users u 
JOIN companies c ON u.company_id = c.id 
WHERE u.email='jean@techcorp.fr';
"

# Résultat attendu : Auto-assigné via domaine
```

### Test 3 : Code Invalide

```bash
# Widget : code = FAKE999
# → Vérifier logs
grep "Code entreprise" logs/api.log | tail -1

# Résultat attendu : "⚠️ Code entreprise 'FAKE999' invalide"
# company_id reste NULL
```

### Test 4 : Email ne correspond pas au Domaine

```bash
# Entreprise : email_domain = "techcorp.fr"
# Employé : email = "jean@gmail.com", code = TECH2026

# → Vérifier warning log
grep "ne correspond pas au domaine" logs/api.log | tail -1

# Note : L'assignation se fait quand même (warning seulement)
```

---

## 🚀 Workflow de Production

### 1️⃣ Onboarding Entreprise (RH/Admin)

```bash
# L'admin Carette crée l'entreprise
curl -X POST https://api.carette.fr/api/v2/companies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TechCorp SARL",
    "email_domain": "techcorp.fr",
    "contact_email": "rh@techcorp.fr",
    "contact_name": "Marie Dupont",
    "siren": "123456789"
  }'

# Réponse sauvegardée :
# company_id: 1
# company_code: TECH2026
# access_key: vO7xK3...
```

### 2️⃣ Communication au RH

Email ou appel avec :
- ✅ Code entreprise : `TECH2026`
- ✅ URL widget : `https://carette.fr/rse`
- ✅ Instructions pour employés
- ✅ (Optionnel) Clé API pour intégrations

### 3️⃣ Diffusion Interne (RH → Employés)

Email interne de l'entreprise :
```
Objet: [Action requise] Inscription au bilan carbone TechCorp

Chers collègues,

Dans le cadre de notre démarche RSE, merci de remplir 
votre bilan carbone hebdomadaire.

🌱 Inscrivez-vous ici : https://carette.fr/rse

⚠️ Important : Utilisez le code TECH2026 lors de l'inscription.

Cordialement,
RH
```

### 4️⃣ Inscription Employés

Chaque employé :
1. Ouvre https://carette.fr/rse
2. Remplit ses infos
3. Saisit `TECH2026` dans "Code Entreprise"
4. Valide

→ Automatiquement rattaché à TechCorp

### 5️⃣ Suivi (Admin Carette)

```bash
# Vérifier combien d'employés inscrits
curl "https://api.carette.fr/api/v2/rse/monthly-recap/company/1" | jq '.summary.total_employees'
```

---

## 🔄 Cas d'Usage Avancés

### Cas 1 : Multi-Entreprises (Groupe)

```bash
# Groupe avec 3 filiales
curl -X POST http://localhost:9000/api/v2/companies \
  -d '{"name": "TechCorp HQ", "email_domain": "techcorp.fr"}'
# Code: TECH2026

curl -X POST http://localhost:9000/api/v2/companies \
  -d '{"name": "TechCorp Marseille", "email_domain": "techcorp-marseille.fr"}'
# Code: TECH20261

curl -X POST http://localhost:9000/api/v2/companies \
  -d '{"name": "TechCorp Lyon", "email_domain": "techcorp-lyon.fr"}'
# Code: TECH20262

# Chaque filiale a son propre code + domaine
```

### Cas 2 : Intégration SIRH

```bash
# Script SIRH qui ajoute automatiquement les nouveaux employés
ACCESS_KEY="vO7xK3_p9Lm2Nq8hR5jT1wY6iU4zX0cA3bD9eF2gH8kL5mN7pQ1sT4vW6xY0zA3"

curl -X POST https://api.carette.fr/api/v2/companies/1/employees \
  -H "Authorization: Bearer $ACCESS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_email": "nouveau.employe@techcorp.fr"}'
```

### Cas 3 : Migration Employés Existants

```bash
# Assigner en masse via script
for email in $(cat employees.txt); do
  curl -X POST http://localhost:9000/api/v2/companies/1/employees \
    -H "Content-Type: application/json" \
    -d "{\"user_email\": \"$email\"}"
done
```

---

## ✅ Checklist de Déploiement

- [ ] Redémarrer serveur (créer colonnes `company_code`, `access_key`, `email_domain`)
- [ ] Créer entreprises de test
- [ ] Vérifier génération automatique des codes
- [ ] Tester widget avec code entreprise
- [ ] Tester auto-détection par domaine
- [ ] Tester code invalide (warning log)
- [ ] Vérifier récaps mensuels (filtrage par company_id)
- [ ] Préparer emails templates pour RH
- [ ] Documentation utilisateur final

---

## 🎉 Résumé

**3 Méthodes d'Inscription :**
1. **Code Entreprise** (TECH2026) - Simple, recommandé
2. **Domaine Email** (techcorp.fr) - Automatique, transparent
3. **API Manuelle** - Pour cas spéciaux

**Avantages :**
- ✅ Simple pour les employés (juste un code)
- ✅ Sécurisé (codes uniques)
- ✅ Flexible (3 méthodes)
- ✅ Scalable (automatisation possible)
- ✅ Traçable (logs complets)

**Workflow RH :**
1. Admin Carette crée entreprise → `TECH2026`
2. RH communique le code aux employés
3. Employés s'inscrivent avec le code
4. Auto-assignation instantanée
5. Récaps mensuels par entreprise

🚀 **Prêt pour la production !**
