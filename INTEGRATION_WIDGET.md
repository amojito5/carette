# 🔄 Guide d'Adaptation - Widget Existant → Workflow Email/WhatsApp

## 📋 Ce Qui a Été Créé

### 1. **API Adapter** (`backend/api_adapter.py`)
- Convertit automatiquement `user_id` → `email + téléphone`
- Compatible avec vos endpoints actuels
- Ajoute le workflow email/WhatsApp automatiquement

### 2. **Payment Simulator** (`frontend/payment-simulator.js`)
- Popup de paiement 1€ simulé
- Prêt à intégrer dans votre widget
- Design moderne (violet/blanc)

---

## 🚀 Intégration Rapide (3 Étapes)

### Étape 1 : Charger le module de paiement

Ajoutez dans votre HTML qui charge le widget :

```html
<!-- Avant le widget -->
<script src="frontend/payment-simulator.js"></script>
<script src="frontend/carpool-widget.js"></script>
```

### Étape 2 : Modifier la réservation dans le widget

Dans `carpool-widget.js`, ligne ~13100 (fonction `reserveOffer`), **ajoutez la popup** :

```javascript
async reserveOffer(offer, tripType = 'outbound') {
  // NOUVEAU : Afficher popup paiement AVANT de réserver
  const paymentSimulator = new CarettePaymentSimulator();
  
  paymentSimulator.show({
    amount: '1,00 €',
    onConfirm: async () => {
      // Code existant de réservation ici
      try {
        const userId = (typeof window !== 'undefined' && window.userId) 
          ? String(window.userId) : null;
        
        if (!userId) { 
          alert('Veuillez vous connecter pour réserver.'); 
          return; 
        }
        
        // ... reste du code existant ...
        
        const res = await fetch('/api/carpool/reserve', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          credentials:'include',
          body:JSON.stringify(payload)
        });
        
        // ... reste du code existant ...
        
      } catch(e) {
        console.error(e);
        alert('Erreur lors de la réservation');
      }
    },
    onCancel: () => {
      console.log('Paiement annulé');
    }
  });
}
```

### Étape 3 : Lancer l'API adaptée

```bash
# Au lieu de :
python3 backend/api.py

# Lancez :
python3 backend/api_adapter.py
```

---

## 🎯 Ce Que Ça Change

### Avant
```
User → Réserver → BDD
```

### Après
```
User → Popup 1€ → Réserver → BDD + Emails automatiques
                                  ↓
                    Conducteur reçoit email avec boutons WhatsApp
                    Passager reçoit confirmation
```

---

## 📧 Workflow Email Automatique

Quand un passager réserve :

1. **Popup paiement 1€** (simulé)
2. **Email au conducteur** :
   - Notification de la demande
   - Coordonnées du passager
   - Bouton WhatsApp cliquable
   - Boutons Accepter/Refuser

3. **Email au passager** :
   - Confirmation demande envoyée
   - Infos du trajet
   - Mention paiement 1€ simulé

4. **Si accepté** :
   - Email au passager avec coordonnées conducteur
   - Bouton WhatsApp pour contact direct

---

## 🔧 Configuration SMTP (Optionnel)

Pour recevoir les vrais emails, éditez `.env` :

```env
SMTP_USER=votre_email@gmail.com
SMTP_PASSWORD=votre_mot_de_passe_app
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

**Si non configuré** : Les emails s'affichent dans les logs (parfait pour tester).

---

## 🎨 Personnalisation Popup Paiement

Dans `frontend/payment-simulator.js`, modifiez :

```javascript
// Changer les couleurs (ligne ~60)
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
// → Vos couleurs

// Changer le montant par défaut (ligne ~15)
amount = "1,00 €"
// → Votre montant
```

---

## 🧪 Test Rapide

1. **Démarrer l'API adaptée** :
   ```bash
   python3 backend/api_adapter.py
   ```

2. **Ouvrir votre widget** (demo.html ou autre)

3. **Publier un trajet** avec email comme user_id :
   ```javascript
   window.userId = 'conducteur@test.com';
   ```

4. **Réserver** :
   - La popup 1€ s'affiche
   - Cliquez "Payer (SIMULÉ)"
   - Vérifiez les logs pour voir les emails

---

## 🔄 Compatibilité Totale

L'adaptateur convertit automatiquement :

| V1 (Actuel) | V2 (Nouveau) |
|-------------|--------------|
| `user_id: 'email@test.com'` | `driver_email: 'email@test.com'`<br>`driver_phone: '0600000000'` |
| `POST /api/carpool` | `POST /api/v2/offers` |
| `GET /api/carpool` | `GET /api/v2/offers` |
| `POST /api/carpool/reserve` | `POST /api/v2/reservations` |

**Aucune modification du widget requise** (sauf ajout popup paiement).

---

## 📝 Checklist Complète

- [ ] Charger `payment-simulator.js` avant le widget
- [ ] Ajouter popup dans fonction `reserveOffer`
- [ ] Lancer `api_adapter.py` au lieu de `api.py`
- [ ] Tester avec `window.userId = 'test@email.com'`
- [ ] Vérifier logs pour voir les emails
- [ ] (Optionnel) Configurer SMTP pour vrais emails

---

## 💡 Prochaine Étape : Stripe Réel

Quand vous serez prêt, on remplacera :

```javascript
// Simulation
paymentSimulator.show({ ... })

// Par vraie redirection Stripe
const { url } = await fetch('/api/create-stripe-session', { ... });
window.location.href = url;
```

---

**Besoin d'aide ? Testez d'abord avec l'adaptateur et dites-moi ce qui bloque !** 🚀
