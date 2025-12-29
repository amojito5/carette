# 🚗 Carette v2 - Workflow Simplifié Email + WhatsApp

## 🎯 Ce Qu'on a Implémenté

### ✅ Backend Complet
- **Nouveau schéma BDD** (sans user_id, juste email + téléphone)
- **API REST simplifiée** v2 avec 4 endpoints principaux
- **Système d'emails automatisés** avec templates HTML
- **Boutons WhatsApp** cliquables dans les emails
- **Simulation de paiement** (popup 1€) en attendant Stripe

### ✅ Frontend Widget
- **Interface complète** avec 2 onglets (Publier/Rechercher)
- **Formulaires simples** (juste email + téléphone)
- **Modal de réservation** avec simulation paiement
- **Design moderne** et responsive

---

## 📁 Fichiers Créés

```
backend/
  schema_v2.py          # Schéma BDD simplifié
  sql_v2.py             # Module SQL v2
  emails.py             # Templates emails + WhatsApp
  api_v2.py             # API Flask simplifiée

frontend/
  widget-v2.html        # Widget complet avec simulation paiement

.env.example.v2         # Configuration exemple
start_v2.sh             # Script de démarrage
```

---

## 🚀 Démarrage Rapide

### 1. Configuration initiale

```bash
# Copier la configuration
cp .env.example.v2 .env

# Générer des secrets
python3 backend/generate_secrets.py

# Éditer .env et configurer SMTP
nano .env
```

**SMTP Configuration (Gmail exemple) :**
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre_email@gmail.com
SMTP_PASSWORD=votre_mot_de_passe_app  # Pas votre mot de passe Gmail !
FROM_EMAIL=noreply@carette.app
```

> 💡 **Gmail** : Créez un "Mot de passe d'application" dans votre compte Google  
> Allez dans : Compte Google → Sécurité → Validation en deux étapes → Mots de passe des applications

### 2. Installation et lancement

```bash
# Rendre le script exécutable
chmod +x start_v2.sh

# Installer et initialiser
./start_v2.sh

# Lancer le serveur API
python3 backend/api_v2.py
```

### 3. Tester le widget

Ouvrez `frontend/widget-v2.html` dans votre navigateur.

---

## 🔄 Workflow Complet

### Scénario : Jean publie un trajet, Marie réserve

#### 1️⃣ **Jean publie son trajet**
- Remplit le formulaire (email, téléphone, trajet)
- Clique "Publier mon trajet"
- ✅ Trajet enregistré en BDD

#### 2️⃣ **Marie recherche et réserve**
- Recherche Paris → Lyon
- Clique "Réserver" sur le trajet de Jean
- Remplit ses coordonnées (email, téléphone)
- **Simulation paiement 1€** (popup violette)
- Clique "Payer 1,00€ (SIMULÉ)"

#### 3️⃣ **Emails automatiques**
📧 **Jean reçoit :**
```
Sujet : Nouvelle demande : Marie → Paris

┌─────────────────────────────────┐
│ Nouvelle demande de réservation │
│                                 │
│ Marie souhaite réserver une     │
│ place dans votre trajet :       │
│                                 │
│ 📍 Départ : Paris               │
│ 🎯 Destination : Lyon           │
│ 📅 Date : 16/12/2025 10:00      │
│                                 │
│ Coordonnées du passager :       │
│ 📧 marie@example.com            │
│ 📱 06 12 34 56 78               │
│                                 │
│ [ 💬 Contacter sur WhatsApp ]   │ ← Bouton cliquable !
│                                 │
│ [ ✅ Accepter ] [ ❌ Refuser ]  │
└─────────────────────────────────┘
```

📧 **Marie reçoit :**
```
Sujet : Demande envoyée - En attente

Votre demande a bien été envoyée
au conducteur. Vous recevrez une
confirmation dès qu'il acceptera.

💳 Paiement : 1,00€ (simulé)
```

#### 4️⃣ **Jean accepte (clic sur bouton email)**
Clique sur "✅ Accepter" dans l'email
→ Ouverture d'une page de confirmation
→ Réservation = "confirmed" en BDD

#### 5️⃣ **Emails de confirmation**
📧 **Marie reçoit :**
```
Sujet : Confirmé : Trajet Paris → Lyon

✅ Réservation confirmée !

Jean a accepté votre demande.

Coordonnées du conducteur :
📧 jean@example.com
📱 06 98 76 54 32

[ 💬 Contacter sur WhatsApp ]

💰 Rappel : 1€ payé (simulé)
Le prix du trajet se règle avec le
conducteur (espèces, Lydia, etc.)
```

📧 **Jean reçoit :**
```
(Notification interne - optionnel)
Votre réservation a été confirmée.
Marie a reçu vos coordonnées.
```

---

## 🛠️ API Endpoints

### `POST /api/v2/offers`
Publier une offre de covoiturage

**Requête :**
```json
{
  "driver_email": "jean@example.com",
  "driver_phone": "0698765432",
  "driver_name": "Jean Dupont",
  "departure": "Paris, France",
  "destination": "Lyon, France",
  "datetime": "2025-12-16 10:00:00",
  "seats_available": 3,
  "event_name": "Concert Metallica"
}
```

**Réponse :**
```json
{
  "success": true,
  "offer_id": 42,
  "message": "Offre publiée avec succès"
}
```

### `GET /api/v2/offers`
Rechercher des offres

**Paramètres :**
- `departure` (optionnel) : Ville de départ
- `destination` (optionnel) : Ville d'arrivée
- `date` (optionnel) : Date au format YYYY-MM-DD
- `event_id` (optionnel) : ID de l'événement

**Exemple :**
```
GET /api/v2/offers?departure=Paris&destination=Lyon&date=2025-12-16
```

**Réponse :**
```json
{
  "success": true,
  "count": 2,
  "offers": [
    {
      "id": 42,
      "driver_name": "Jean Dupont",
      "departure": "Paris, France",
      "destination": "Lyon, France",
      "datetime": "2025-12-16 10:00:00",
      "seats_available": 3,
      "event_name": "Concert Metallica"
    }
  ]
}
```

### `POST /api/v2/reservations`
Créer une réservation (avec paiement simulé)

**Requête :**
```json
{
  "offer_id": 42,
  "passenger_email": "marie@example.com",
  "passenger_phone": "0612345678",
  "passenger_name": "Marie Martin",
  "passengers_count": 1
}
```

**Réponse :**
```json
{
  "success": true,
  "reservation_id": 12,
  "message": "Réservation créée - Emails envoyés",
  "payment_simulated": true
}
```

### `GET /api/v2/confirm/<token>`
Accepter ou refuser une réservation (lien dans email)

**Exemple :**
```
GET /api/v2/confirm/abc123...
```

**Réponse :** Page HTML de confirmation

---

## 🎨 Widget Intégration

Pour intégrer le widget sur un site externe :

```html
<!DOCTYPE html>
<html>
<head>
    <title>Mon Site</title>
</head>
<body>
    <h1>Covoiturage pour notre événement</h1>
    
    <!-- Iframe du widget -->
    <iframe 
        src="http://localhost:8080/frontend/widget-v2.html"
        width="100%"
        height="800px"
        frameborder="0"
        style="border-radius: 12px;">
    </iframe>
</body>
</html>
```

---

## 📧 Configuration Email

### Gmail (Développement)

1. Activez la validation en 2 étapes sur votre compte Google
2. Allez dans "Mots de passe des applications"
3. Générez un mot de passe pour "Autre (nom personnalisé)"
4. Utilisez ce mot de passe dans `.env`

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre_email@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx  # Mot de passe d'application
```

### SendGrid (Production recommandée)

1. Créez un compte sur sendgrid.com
2. Générez une API Key
3. Configuration :

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.votre_api_key_ici
FROM_EMAIL=noreply@votre-domaine.com
```

### Mailgun (Alternative)

```env
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@votre-domaine.mailgun.org
SMTP_PASSWORD=votre_password_mailgun
```

---

## 🔐 Sécurité

- ✅ Validation des emails avec regex
- ✅ Sanitization des inputs (XSS)
- ✅ Tokens sécurisés pour confirmation (32 bytes)
- ✅ Expiration des liens (7 jours)
- ✅ Rate limiting (10 offres/heure, 5 réservations/heure)
- ✅ CORS configuré
- ✅ Pas de secrets dans le code

---

## 🧪 Tests Manuels

### Test 1 : Publier un trajet
1. Ouvrir `widget-v2.html`
2. Onglet "Publier un trajet"
3. Remplir le formulaire
4. Vérifier email reçu (ou logs si SMTP non configuré)

### Test 2 : Rechercher et réserver
1. Onglet "Rechercher"
2. Laisser vide ou filtrer
3. Cliquer "Réserver"
4. Remplir coordonnées
5. Cliquer "Payer" dans la popup
6. Vérifier emails (conducteur + passager)

### Test 3 : Accepter une réservation
1. Ouvrir l'email du conducteur
2. Cliquer sur "✅ Accepter"
3. Vérifier page de confirmation
4. Vérifier email de confirmation au passager

---

## 💡 Prochaines Étapes

### Phase 1 : Tests et Ajustements (Maintenant)
- [ ] Tester le workflow complet
- [ ] Ajuster les templates d'emails
- [ ] Améliorer les messages d'erreur
- [ ] Tester WhatsApp avec vrais numéros

### Phase 2 : Stripe Réel (Quand validé)
- [ ] Créer compte Stripe
- [ ] Intégrer Stripe Checkout
- [ ] Remplacer la popup par vraie redirection
- [ ] Webhooks pour confirmation automatique

### Phase 3 : Production
- [ ] Acheter domaine
- [ ] Configurer SendGrid
- [ ] Déployer sur serveur
- [ ] SSL/HTTPS
- [ ] Monitoring

---

## 🐛 Debug

### Emails non envoyés
```bash
# Vérifier les logs
tail -f logs/carette.log

# Tester la connexion SMTP manuellement
python3 -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('votre_email', 'votre_password')
print('✅ Connexion SMTP OK')
"
```

### Base de données
```bash
# Se connecter à MySQL
mysql -u carette_user -p carette_db

# Voir les offres
SELECT * FROM carpool_offers_v2;

# Voir les réservations
SELECT * FROM carpool_reservations_v2;

# Voir les tokens
SELECT * FROM confirmation_tokens;
```

### API
```bash
# Tester l'API
curl http://localhost:5000/api/v2/health

# Voir les offres
curl http://localhost:5000/api/v2/offers
```

---

## 📞 Support

Si vous rencontrez un problème :
1. Vérifiez les logs : `tail -f logs/carette.log`
2. Testez la connexion BDD : `python3 backend/sql_v2.py`
3. Vérifiez `.env` : toutes les variables sont remplies ?
4. Relancez : `python3 backend/api_v2.py`

---

**Bon covoiturage ! 🚗💨**
