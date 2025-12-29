# 🔧 Guide de Modification - Widget Carpool Simplifié

## 🎯 Objectif

Modifier votre `carpool-widget.js` pour :
1. **Supprimer** la dépendance à `window.userId`
2. **Ajouter** des champs email + téléphone dans les formulaires
3. **Ajouter** popup paiement 1€ avant réservation
4. **Envoyer** emails automatiques avec WhatsApp

---

## 📝 Modifications à Faire

### 1. Charger le Module de Paiement

**Dans votre HTML** (demo.html ou autre) :

```html
<!-- AVANT -->
<script src="frontend/carpool-widget.js"></script>

<!-- APRÈS -->
<script src="frontend/payment-simulator.js"></script>
<script src="frontend/carpool-widget.js"></script>
```

---

### 2. Ajouter Champs Email/Téléphone dans le HTML du Widget

**Fichier : `frontend/carpool-widget.js`**

Cherchez la fonction `renderUI()` (ligne ~2100) et trouvez la section du formulaire "Proposer un trajet".

**AJOUTEZ** après les champs existants :

```javascript
// Dans renderUI(), après les champs from/to/date/time, ajoutez:

<div class="field-group">
  <label for="driver-email">📧 Votre email *</label>
  <input type="email" id="driver-email" placeholder="votre@email.com" required>
</div>

<div class="field-group">
  <label for="driver-phone">📱 Votre téléphone *</label>
  <input type="tel" id="driver-phone" placeholder="06 12 34 56 78" required>
</div>

<div class="field-group">
  <label for="driver-name">👤 Votre nom (optionnel)</label>
  <input type="text" id="driver-name" placeholder="Jean Dupont">
</div>
```

---

### 3. Modifier `submitCarpoolOffer` - Supprimer userId

**Fichier : `frontend/carpool-widget.js`**  
**Ligne : ~6500**

```javascript
// AVANT
async submitCarpoolOffer() {
  try {
    const userId = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
    if (!userId) {
      alert("Veuillez vous connecter pour proposer un covoiturage.");
      return;
    }
    
    // ... reste du code ...
    
    const payload = {
      user_id: userId,  // ❌ ANCIEN
      departure,
      destination,
      // ...
    };
    
// APRÈS
async submitCarpoolOffer() {
  try {
    // Récupérer email + téléphone du formulaire
    const driverEmail = this.shadowRoot.getElementById('driver-email')?.value?.trim();
    const driverPhone = this.shadowRoot.getElementById('driver-phone')?.value?.trim();
    const driverName = this.shadowRoot.getElementById('driver-name')?.value?.trim();
    
    if (!driverEmail || !driverPhone) {
      alert("Veuillez renseigner votre email et téléphone.");
      return;
    }
    
    // ... reste du code inchangé ...
    
    const payload = {
      driver_email: driverEmail,   // ✅ NOUVEAU
      driver_phone: driverPhone,   // ✅ NOUVEAU
      driver_name: driverName,     // ✅ NOUVEAU
      departure,
      destination,
      // ... reste identique
    };
    
    // Appeler l'API v2 au lieu de v1
    const res = await fetch('/api/v2/offers', {  // ✅ Nouveau endpoint
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
```

---

### 4. Ajouter Popup Paiement dans `reserveOffer`

**Fichier : `frontend/carpool-widget.js`**  
**Ligne : ~13100**

```javascript
// AVANT
async reserveOffer(offer, tripType = 'outbound') {
  try {
    const userId = (typeof window !== 'undefined' && window.userId) ? String(window.userId) : null;
    if (!userId) { 
      alert('Veuillez vous connecter pour réserver.'); 
      return; 
    }
    
    // ... code de réservation directement ...
  }
}

// APRÈS
async reserveOffer(offer, tripType = 'outbound') {
  // ✅ 1. Demander email/téléphone AVANT la popup
  const passengerEmail = prompt('Votre email :');
  if (!passengerEmail) return;
  
  const passengerPhone = prompt('Votre téléphone :');
  if (!passengerPhone) return;
  
  // ✅ 2. Afficher popup paiement 1€
  const paymentSimulator = new CarettePaymentSimulator();
  
  paymentSimulator.show({
    amount: '1,00 €',
    onConfirm: async () => {
      // ✅ 3. Code de réservation existant ICI
      try {
        const seatsEl = this.shadowRoot.getElementById('seats');
        const requestedSeats = seatsEl ? parseInt(seatsEl.value, 10) : 1;
        
        let detourTime = 0;
        let meetingPoint = null;
        let meetingAddress = null;
        let detourRoute = null;
        
        if (offer._detourInfo) {
          if (offer._detourInfo.additionalTime) {
            detourTime = Math.round(offer._detourInfo.additionalTime);
          }
          if (offer._detourInfo.meetingPoint) {
            meetingPoint = offer._detourInfo.meetingPoint;
          }
          if (offer._detourInfo.meetingAddress) {
            meetingAddress = offer._detourInfo.meetingAddress;
          }
          if (offer._detourInfo.detourRoute) {
            detourRoute = offer._detourInfo.detourRoute;
          }
        }
        
        const payload = { 
          offer_id: offer.id,
          passenger_email: passengerEmail,    // ✅ NOUVEAU
          passenger_phone: passengerPhone,    // ✅ NOUVEAU
          passenger_name: '',                 // ✅ NOUVEAU
          passengers_count: requestedSeats,   // ✅ Renommé
          detour_time: detourTime,
          meeting_point: meetingPoint,
          meeting_address: meetingAddress,
          detour_route: detourRoute,
          trip_type: tripType
        };
        
        // ✅ Appeler l'API v2
        const res = await fetch('/api/v2/reservations', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify(payload)
        });
        
        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          const errorMsg = errorData.error || 'Réservation échouée';
          throw new Error(errorMsg);
        }
        
        alert('✅ Réservation confirmée ! Vous allez recevoir un email.');
        this.closeReservationPopup();
        
        // Rafraîchir
        try { await this.fetchMyTrips(); } catch(_) {}
        try {
          if (this.searchCenterCoords) this.renderFindOffersFiltered(); 
          else this.renderFindOffers();
        } catch(_) {}
        
        const card = this.shadowRoot.querySelector(`.offer-card[data-offer-id="${offer.id}"]`);
        if (card) card.classList.add('selected');
        
      } catch(e) {
        console.error(e);
        const errorMsg = e.message || 'Désolé, la réservation n\'a pas pu être effectuée.';
        alert(errorMsg);
      }
    },
    onCancel: () => {
      console.log('Paiement annulé');
    }
  });
}
```

---

### 5. Modifier `fetchMyTrips` et `get_offers`

Ces fonctions utilisent `window.userId`. Vous avez 2 options :

**Option A : Stocker email localement**
```javascript
// Au début du widget (constructor)
this.userEmail = localStorage.getItem('carette_user_email');
this.userPhone = localStorage.getItem('carette_user_phone');

// Après soumission d'offre, sauvegarder
localStorage.setItem('carette_user_email', driverEmail);
localStorage.setItem('carette_user_phone', driverPhone);

// Dans fetchMyTrips
async fetchMyTrips() {
  if (!this.userEmail) return; // Pas connecté
  
  const [myOffers, myReservations] = await Promise.all([
    fetch(`/api/v2/offers/mine?email=${encodeURIComponent(this.userEmail)}`),
    fetch(`/api/v2/reservations/mine?email=${encodeURIComponent(this.userEmail)}`)
  ]);
  
  // ...
}
```

**Option B : Supprimer "Mes trajets"**
Si vous ne voulez pas de système de connexion du tout, retirez simplement la fonctionnalité "Mes trajets".

---

### 6. Modifier l'API Backend

**Fichier : `backend/api_v2.py`**

Ajoutez un endpoint pour récupérer "mes offres" :

```python
@app.route('/api/v2/offers/mine', methods=['GET'])
def get_my_offers():
    """Récupérer mes offres par email"""
    email = request.args.get('email', '')
    
    if not email:
        return jsonify([]), 200
    
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT id, driver_email, driver_phone, driver_name,
                       departure, destination, datetime, seats_available,
                       status, event_id, event_name, created_at
                FROM carpool_offers_v2
                WHERE driver_email = %s
                ORDER BY datetime DESC
                LIMIT 50
            """, (email,))
            
            rows = cur.fetchall()
            offers = [/* formater les résultats */]
            
            return jsonify(offers), 200
    except Exception as e:
        return jsonify([]), 200
```

---

## 🚀 Test Rapide

1. **Initialiser la BDD v2** :
   ```bash
   python3 backend/sql_v2.py
   ```

2. **Lancer l'API v2** :
   ```bash
   python3 backend/api_v2.py
   ```

3. **Ouvrir le widget** :
   ```bash
   firefox demo.html
   ```

4. **Tester le parcours** :
   - Publier un trajet (remplir email + téléphone)
   - Rechercher
   - Réserver → Popup 1€ s'affiche
   - Cliquer "Payer" → Vérifier les logs pour voir les emails

---

## 📧 Emails Envoyés Automatiquement

### Après réservation :

**Conducteur reçoit :**
```
Sujet : Nouvelle demande de réservation

Nouvelle demande : [Nom passager] → [Départ]

Coordonnées :
📧 passager@email.com
📱 06 12 34 56 78

[ 💬 Contacter sur WhatsApp ]

[ ✅ Accepter ]  [ ❌ Refuser ]
```

**Passager reçoit :**
```
Sujet : Demande envoyée - En attente

Votre demande a été envoyée au conducteur.
Vous recevrez une confirmation par email.

💳 Paiement : 1,00€ (simulé)
```

---

## 🔧 Résumé des Changements

| Fichier | Changement |
|---------|-----------|
| `demo.html` | Charger `payment-simulator.js` avant le widget |
| `carpool-widget.js` → `renderUI()` | Ajouter champs email/phone/name |
| `carpool-widget.js` → `submitCarpoolOffer()` | Utiliser email/phone au lieu de userId |
| `carpool-widget.js` → `reserveOffer()` | Ajouter popup paiement + demander email/phone |
| `backend/api_v2.py` | Ajouter endpoints `/offers/mine` et `/reservations/mine` |

---

## 💡 Prochaine Étape

Une fois que ça fonctionne en local, on pourra :
- Remplacer la simulation par vrai Stripe
- Configurer SMTP pour vrais emails
- Déployer en production

**Commencez par ces modifications et testez ! Si besoin, je peux faire les changements pour vous.** 🚀
