# 🚀 Workflow V2 - Email + WhatsApp (Sans comptes utilisateurs)

## ✅ Modifications Terminées

### 1. Frontend - Widget (`frontend/carpool-widget.js`)

#### **Ajout des champs email/téléphone/nom** (lignes ~3870-3895)
```javascript
<!-- Coordonnées conducteur (offre uniquement) -->
<div class="search-field offer-only">
  <input id="driver-name" type="text" placeholder="Votre nom complet" />
</div>
<div class="search-field offer-only">
  <input id="driver-email" type="email" placeholder="Votre email" />
</div>
<div class="search-field offer-only">
  <input id="driver-phone" type="tel" placeholder="Votre téléphone" />
</div>
```

#### **Modification `submitCarpoolOffer()`** (ligne ~6500)
**Avant :**
- Vérifiait `window.userId`
- Appelait `/api/carpool`

**Après :**
- Collecte email/nom/téléphone du conducteur
- Validation email
- Appelle `/api/v2/offers`
- Message de confirmation avec mention de l'email

#### **Modification `reserveOffer()`** (ligne ~13116)
**Avant :**
- Vérifiait `window.userId`
- Appelait `/api/carpool/reserve`

**Après :**
1. Affiche popup de paiement 1€ (`CarettePaymentSimulator`)
2. Si confirmé, collecte email/nom/téléphone du passager via `prompt()`
3. Appelle `/api/v2/reservations`
4. Message de confirmation avec mention de l'email WhatsApp

### 2. Backend - API (`backend/api.py`)

#### **Import des modules v2** (ligne ~34)
```python
try:
    from sql_v2 import db_cursor as db_cursor_v2
    from emails import (
        generate_confirmation_token,
        email_new_reservation_to_driver,
        email_reservation_confirmed_to_passenger,
        email_payment_simulation
    )
    V2_ENABLED = True
except ImportError as e:
    V2_ENABLED = False
```

#### **Nouveaux endpoints ajoutés :**

**POST `/api/v2/offers`** (ligne ~795)
- Crée une offre avec `driver_email`, `driver_phone`, `driver_name`
- Pas de `user_id`
- Rate limit: 10/heure
- Insère dans `carpool_offers_v2`
- TODO: Email de confirmation au conducteur

**GET `/api/v2/offers`** (ligne ~860)
- Liste les offres disponibles
- Masque email/téléphone (privacy)
- Filtres: `event_id`, `min_seats`
- Rate limit: 60/minute

**POST `/api/v2/reservations`** (ligne ~930)
- Crée une réservation avec `passenger_email`, `passenger_phone`, `passenger_name`
- Vérifie disponibilité de l'offre
- Décrément les places
- Génère token de confirmation
- **Envoie 2 emails automatiques :**
  - Conducteur → Bouton WhatsApp vers passager
  - Passager → Bouton WhatsApp vers conducteur

### 3. Popup de paiement (`frontend/payment-simulator.js`)

Classe `CarettePaymentSimulator` :
- Popup modal élégant (style iOS)
- Simulation paiement 1€
- Animation de chargement
- Prêt pour intégration Stripe

**Intégré dans `demo.html`** (ligne ~126) :
```html
<script src="./frontend/payment-simulator.js"></script>
```

### 4. Base de données v2 (`backend/sql_v2.py`)

Tables créées automatiquement au démarrage :

**`carpool_offers_v2`**
```sql
- driver_email (VARCHAR 255, INDEX)
- driver_name (VARCHAR 100)
- driver_phone (VARCHAR 20)
- departure, destination, datetime
- seats_available (INT)
- event_id, event_name, event_location, event_date
- details (JSON)
- expires_at (DATETIME)
```

**`carpool_reservations_v2`**
```sql
- passenger_email (VARCHAR 255, INDEX)
- passenger_name (VARCHAR 100)
- passenger_phone (VARCHAR 20)
- passengers_count (INT)
- status (ENUM: pending, confirmed, cancelled)
- confirmation_token (VARCHAR 64)
```

**`confirmation_tokens`**
```sql
- token (VARCHAR 64, UNIQUE)
- reservation_id (INT, FK)
- expires_at (DATETIME)
```

### 5. Système d'emails (`backend/emails.py`)

**Templates disponibles :**

1. **`email_new_reservation_to_driver()`**
   - Notifie le conducteur d'une nouvelle réservation
   - Bouton WhatsApp vers le passager
   - Détails du trajet

2. **`email_reservation_confirmed_to_passenger()`**
   - Confirme la réservation au passager
   - Bouton WhatsApp vers le conducteur
   - Détails du trajet

3. **`whatsapp_button()`**
   - Génère un bouton vert WhatsApp
   - Deep link : `https://wa.me/{phone}?text={message}`

4. **`generate_confirmation_token()`**
   - Token sécurisé 64 caractères

---

## 🔄 Parcours Utilisateur Complet

### **Conducteur - Proposer un trajet**

1. Ouvre le widget (onglet "Proposer")
2. Remplit :
   - Départ / Destination / Date / Heure
   - **Nom complet**
   - **Email**
   - **Téléphone**
3. Clique sur "Publier mon offre"
4. **Envoi à `/api/v2/offers`**
5. ✅ Message : "Vous allez recevoir un email pour chaque réservation"
6. (TODO) Reçoit email de confirmation d'offre publiée

### **Passager - Réserver un trajet**

1. Ouvre le widget (onglet "Trouver")
2. Recherche trajets disponibles
3. Clique sur "Réserver"
4. **Popup paiement 1€ s'affiche**
5. Simule le paiement → Confirmé
6. **Saisit ses coordonnées :**
   - Nom complet (prompt)
   - Email (prompt)
   - Téléphone (prompt)
7. **Envoi à `/api/v2/reservations`**
8. ✅ Message : "Vous allez recevoir un email avec le bouton WhatsApp"
9. **Reçoit email avec :**
   - Détails du trajet
   - Bouton WhatsApp vert → Contact direct avec conducteur

### **Conducteur - Notification**

1. Reçoit email automatique :
   - "Nouvelle réservation de [Nom du passager]"
   - Détails : Départ, Destination, Date
   - Nombre de passagers
   - **Bouton WhatsApp vert → Contact direct avec passager**

---

## 🧪 Comment Tester

### 1. Démarrer le backend
```bash
cd /home/ubuntu/projects/carette
python3 backend/api.py
```

Les tables v2 seront initialisées automatiquement.

### 2. Démarrer le frontend
```bash
python3 serve.py
# ou
python3 -m http.server 8080
```

### 3. Ouvrir le navigateur
```
http://localhost:8080/demo.html
```

### 4. Test du flux complet

**Créer une offre :**
1. Onglet "Proposer"
2. Remplir tous les champs + email/téléphone/nom
3. Publier
4. Vérifier console backend : `✅ Offre v2 créée: {id}`

**Réserver :**
1. Onglet "Trouver"
2. Rechercher (devrait afficher l'offre créée)
3. Cliquer "Réserver"
4. Popup 1€ → Simuler paiement
5. Remplir nom/email/téléphone
6. Vérifier console backend : `✅ Réservation v2 créée: {id}`
7. **Vérifier emails envoyés** (logs backend)

---

## 📧 Configuration Email (Production)

Dans `.env` :
```bash
# SMTP Gmail (exemple)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre-email@gmail.com
SMTP_PASSWORD=votre-mot-de-passe-app
SMTP_FROM=Carette <noreply@carette.app>
```

**Note :** Pour Gmail, créer un "App Password" dans les paramètres de sécurité.

---

## 💳 Intégration Stripe (Production)

Remplacer dans `frontend/payment-simulator.js` (ligne ~50) :

```javascript
// Simulation actuelle (ligne 50-60)
await new Promise(resolve => setTimeout(resolve, 2000));
return true;

// Remplacer par appel Stripe :
const stripe = Stripe('pk_live_...');
const {error, paymentIntent} = await stripe.confirmCardPayment(clientSecret, {
  payment_method: {
    card: cardElement,
    billing_details: {email: customerEmail}
  }
});
if (error) throw error;
return paymentIntent.status === 'succeeded';
```

---

## ✅ Checklist de Déploiement

- [x] Champs email/téléphone ajoutés au widget
- [x] `submitCarpoolOffer()` utilise API v2
- [x] `reserveOffer()` avec popup paiement + collecte email
- [x] Endpoints `/api/v2/offers` et `/api/v2/reservations` créés
- [x] Tables v2 auto-créées au démarrage
- [x] Emails automatiques avec boutons WhatsApp
- [x] Payment simulator intégré
- [ ] **TODO:** Configurer SMTP en production
- [ ] **TODO:** Intégrer Stripe pour paiement réel
- [ ] **TODO:** Tests E2E complets
- [ ] **TODO:** Email de confirmation d'offre (conducteur)

---

## 🔥 Prochaines Étapes

1. **Tester le flux complet en local**
2. **Configurer SMTP pour envoi d'emails réels**
3. **Créer un compte Stripe et intégrer paiement**
4. **Améliorer UX de saisie des coordonnées passager** (modal au lieu de prompt())
5. **Ajouter page de gestion des réservations** (via tokens par email)
6. **Analytics et métriques** (conversion, taux de réservation)

---

## 📝 Notes Techniques

- **Rétrocompatibilité :** L'ancien flux avec `user_id` reste fonctionnel (`/api/carpool`)
- **Sécurité :** Emails/téléphones masqués dans les listings publics
- **Rate limiting :** 10 offres/heure, 10 réservations/heure par IP
- **Expiration :** Offres expirent 7 jours après la date du trajet
- **Tokens :** Confirmation tokens de 64 caractères (SHA-256)

---

**Fait le :** 2025-01-XX  
**Par :** GitHub Copilot  
**Version :** 2.0.0 - Email + WhatsApp Workflow
