# 🎯 DÉMARRAGE RAPIDE - Carette v2

## ✅ CE QUI EST PRÊT

Vous avez maintenant un **workflow complet** :
- ✅ Backend API simplifié (email + téléphone uniquement)
- ✅ Système d'emails automatisés avec templates HTML
- ✅ Boutons WhatsApp cliquables dans les emails
- ✅ Widget frontend avec simulation paiement 1€
- ✅ Confirmation par liens magiques (accept/reject)

## 🚀 LANCEMENT EN 3 MINUTES

### 1️⃣ Configuration (première fois seulement)

```bash
cd /home/ubuntu/projects/carette

# Copier la configuration
cp .env.example.v2 .env

# Générer des secrets
python3 backend/generate_secrets.py

# Éditer .env et configurer vos paramètres SMTP
nano .env
```

**Configuration SMTP minimale dans `.env` :**
```env
# Gmail (pour tester)
SMTP_USER=votre_email@gmail.com
SMTP_PASSWORD=votre_mot_de_passe_app  # Généré dans Google

# Ou laissez vide pour voir les emails dans les logs
```

### 2️⃣ Installation et initialisation

```bash
# Tout installer et créer la base
./start_v2.sh
```

### 3️⃣ Démarrer le serveur

```bash
# Terminal 1 : API Backend
python3 backend/api_v2.py

# Terminal 2 : Serveur web pour le widget (optionnel)
python3 -m http.server 8080
```

### 4️⃣ Tester !

Ouvrez dans votre navigateur :
```
http://localhost:8080/frontend/widget-v2.html
```

---

## 🧪 SCÉNARIO DE TEST

### Test Complet du Workflow

1. **Publier un trajet**
   - Onglet "Publier un trajet"
   - Email : `conducteur@test.com`
   - Téléphone : `0698765432`
   - Paris → Lyon, demain 10h00
   - ✅ "Trajet publié !"

2. **Rechercher**
   - Onglet "Rechercher"
   - Laisser vide ou chercher "Paris"
   - Voir le trajet s'afficher
   - Cliquer "Réserver"

3. **Réserver avec simulation paiement**
   - Email : `passager@test.com`
   - Téléphone : `0612345678`
   - Cliquer "Continuer vers le paiement"
   - **Popup violette "1,00€"** s'affiche
   - Cliquer "Payer (SIMULÉ)"
   - ✅ "Réservation confirmée !"

4. **Vérifier les emails**
   - Le conducteur reçoit : "Nouvelle demande de Marie"
   - Boutons "Accepter" / "Refuser"
   - Bouton WhatsApp pour contacter
   - Le passager reçoit : "Demande envoyée - En attente"

5. **Accepter la réservation**
   - Cliquez sur le bouton "✅ Accepter" dans l'email
   - Page de confirmation s'affiche
   - Le passager reçoit : "Confirmé !" avec coordonnées du conducteur

---

## 📧 SI SMTP N'EST PAS CONFIGURÉ

Pas de panique ! Les emails ne seront pas envoyés MAIS :
- Le workflow fonctionne quand même
- Vous verrez des messages dans les logs :
  ```
  ⚠️ Email NON envoyé (SMTP non configuré): passager@test.com
  ```
- La BDD est mise à jour correctement
- Vous pouvez tester la confirmation directement :
  ```
  # Récupérer un token depuis la BDD
  mysql -u carette_user -p carette_db
  SELECT token FROM confirmation_tokens LIMIT 1;
  
  # Tester dans le navigateur
  http://localhost:5000/api/v2/confirm/LE_TOKEN_ICI
  ```

---

## 🎨 PERSONNALISATION

### Changer les couleurs du widget
Éditez `frontend/widget-v2.html`, ligne ~30 :
```css
.btn {
    background-color: #4CAF50;  /* Votre couleur */
}
```

### Modifier les emails
Éditez `backend/emails.py`, fonction `email_template_base()` ligne ~100

### Ajouter des champs
1. Modifiez le schéma BDD dans `backend/schema_v2.py`
2. Ajoutez le champ dans le formulaire `frontend/widget-v2.html`
3. Ajoutez la validation dans `backend/api_v2.py`

---

## 🔧 DÉPANNAGE

### "Erreur : CARETTE_DB_PASSWORD non définie"
→ Vous n'avez pas créé le fichier `.env`
```bash
cp .env.example.v2 .env
python3 backend/generate_secrets.py
nano .env  # Éditez les paramètres
```

### "Erreur de connexion à la BDD"
→ MySQL n'est pas démarré
```bash
sudo systemctl start mysql
```

### "Module 'flask' introuvable"
→ Activez l'environnement virtuel
```bash
source venv/bin/activate
pip install -r backend/requirements.txt
```

### "Port 5000 déjà utilisé"
→ Un autre serveur tourne
```bash
# Trouver et tuer le processus
lsof -ti:5000 | xargs kill -9

# Ou changez le port dans api_v2.py (dernière ligne)
app.run(host='0.0.0.0', port=5001, debug=True)
```

---

## 💡 PROCHAINE ÉTAPE : STRIPE RÉEL

Quand vous serez prêt à ajouter le vrai paiement Stripe (1€) :

1. Créez un compte sur stripe.com
2. Récupérez vos clés API (test puis production)
3. Remplacez la fonction `simulatePayment()` dans le widget par :
   ```javascript
   // Rediriger vers Stripe Checkout
   const response = await fetch(`${API_BASE}/create-checkout-session`, {
       method: 'POST',
       body: JSON.stringify(data)
   });
   const { url } = await response.json();
   window.location.href = url;  // Redirection Stripe
   ```
4. Ajoutez l'endpoint dans `api_v2.py` pour créer la session Stripe

Je vous aide à le faire quand vous voulez !

---

## ✨ CE QUE VOUS AVEZ MAINTENANT

```
┌─────────────────────────────────────────┐
│  WORKFLOW COMPLET FONCTIONNEL           │
├─────────────────────────────────────────┤
│                                         │
│  1. Widget simple (email + téléphone)   │
│  2. Publication de trajets              │
│  3. Recherche de trajets                │
│  4. Réservation avec popup 1€           │
│  5. Emails automatiques                 │
│  6. Boutons WhatsApp                    │
│  7. Confirmation par liens magiques     │
│                                         │
│  🎯 PRÊT À TESTER IMMÉDIATEMENT !      │
└─────────────────────────────────────────┘
```

**Lancez `./start_v2.sh` et c'est parti ! 🚀**
