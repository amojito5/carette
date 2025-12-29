# ✅ Checklist de Test - Workflow V2

## 🎯 Objectif
Vérifier que le workflow complet email + WhatsApp fonctionne correctement.

---

## 📝 Prérequis

- [ ] Backend lancé : `python3 backend/api.py`
- [ ] Frontend lancé : `python3 serve.py` ou `python3 -m http.server 8080`
- [ ] Base de données créée et accessible
- [ ] Tables v2 initialisées (log backend doit afficher "✅ Tables v2 initialisées")

---

## 🧪 Tests à Effectuer

### ✅ Test 1 : Création d'offre (Conducteur)

**Étapes :**
1. Ouvrir http://localhost:8080/demo.html
2. Onglet "Proposer"
3. Remplir :
   - Départ : `75001 Paris`
   - Destination : `69001 Lyon`
   - Date : `2025-12-31`
   - Heure : `18:00`
   - Passagers : `3`
   - **Nom** : `Jean Test`
   - **Email** : `jean.test@example.com`
   - **Téléphone** : `0612345678`
4. Cliquer "Rechercher" (étape intermédiaire)
5. Sélectionner un itinéraire
6. Cliquer "Publier mon offre"

**Résultat attendu :**
- ✅ Alert : "Votre proposition a été enregistrée..."
- ✅ Console backend : `✅ Offre v2 créée: {id} par jean.test@example.com`
- ✅ Pas d'erreur dans la console navigateur

**En cas d'échec :**
- Vérifier que les 3 champs (nom/email/téléphone) sont bien remplis
- Ouvrir la console navigateur (F12) pour voir les erreurs
- Vérifier le log backend pour l'erreur exacte

---

### ✅ Test 2 : Listing des offres

**Étapes :**
1. Onglet "Trouver"
2. Remplir :
   - Départ : `Paris`
   - Destination : `Lyon`
   - Passagers : `2`
3. Cliquer "Rechercher"

**Résultat attendu :**
- ✅ L'offre créée à l'étape 1 apparaît dans la liste
- ✅ Email/téléphone du conducteur sont masqués : `jea***@example.com`, `0612****`
- ✅ Détails visibles : Départ, Destination, Date, Places disponibles

**En cas d'échec :**
- Vérifier requête réseau dans l'onglet Network (F12)
- Vérifier que `/api/v2/offers` renvoie bien des données
- Regarder le log backend pour les erreurs SQL

---

### ✅ Test 3 : Popup de paiement

**Étapes :**
1. Sur une offre trouvée, cliquer "Réserver"

**Résultat attendu :**
- ✅ Popup "Paiement 1€" s'affiche immédiatement
- ✅ Design élégant (style iOS, fond semi-transparent)
- ✅ Bouton vert "Payer 1,00 €"
- ✅ Bouton "Annuler"

**En cas d'échec :**
- Vérifier console navigateur : erreur "CarettePaymentSimulator is not defined"
- Vérifier que `payment-simulator.js` est bien chargé dans `demo.html`
- Vérifier Network : `payment-simulator.js` doit être chargé (200 OK)

---

### ✅ Test 4 : Simulation paiement

**Étapes :**
1. Dans le popup, cliquer "Payer 1,00 €"

**Résultat attendu :**
- ✅ Animation de chargement (spinner + texte "Traitement...")
- ✅ Durée : ~2 secondes
- ✅ Popup se ferme automatiquement
- ✅ Prompts apparaissent pour saisir nom/email/téléphone

**En cas d'échec :**
- Console navigateur doit montrer l'erreur
- Vérifier que la promesse du simulateur se résout bien

---

### ✅ Test 5 : Saisie coordonnées passager

**Étapes :**
1. Après paiement, 3 prompts apparaissent :
   - Nom : `Marie Test`
   - Email : `marie.test@example.com`
   - Téléphone : `0687654321`

**Résultat attendu :**
- ✅ Les 3 prompts s'affichent successivement
- ✅ Si annulé ou vide → Alert d'erreur
- ✅ Email validé (format correct)

**En cas d'échec :**
- Prompts natifs du navigateur, pas de personnalisation possible
- Pour UX améliorée, créer une modal HTML personnalisée (TODO)

---

### ✅ Test 6 : Création de réservation

**Étapes :**
1. Après saisie des 3 champs, validation automatique

**Résultat attendu :**
- ✅ Alert : "Réservation confirmée ! Vous allez recevoir un email..."
- ✅ Console backend : 
  ```
  ✅ Réservation v2 créée: {id} pour offre {offer_id}
  📧 Email envoyé à jean.test@example.com (conducteur)
  📧 Email envoyé à marie.test@example.com (passager)
  ```
- ✅ Liste des offres mise à jour (places disponibles diminuées)

**En cas d'échec :**
- Vérifier console backend pour l'erreur SQL ou validation
- Vérifier que l'offre a encore des places disponibles
- Regarder la requête Network `/api/v2/reservations`

---

### ✅ Test 7 : Emails envoyés (logs)

**Étapes :**
1. Regarder les logs backend après création de réservation

**Résultat attendu (si SMTP non configuré) :**
```
📧 [EMAIL SIMULATION]
To: jean.test@example.com
Subject: Nouvelle réservation pour votre trajet Paris → Lyon
Body: 
  Bonjour Jean Test,
  
  Vous avez une nouvelle réservation !
  
  Passager : Marie Test
  Téléphone : 0687654321
  Trajet : Paris → Lyon
  Date : 2025-12-31 18:00
  Passagers : 2
  
  [Bouton WhatsApp]
```

**Résultat attendu (si SMTP configuré) :**
- ✅ 2 emails envoyés réellement
- ✅ Jean reçoit email avec bouton WhatsApp vers Marie
- ✅ Marie reçoit email avec bouton WhatsApp vers Jean

**En cas d'échec :**
- Si SMTP non configuré : normal, emails dans les logs uniquement
- Si SMTP configuré mais échec : vérifier `.env` et mot de passe app Gmail
- Regarder les logs d'erreur email

---

### ✅ Test 8 : Mise à jour des places

**Étapes :**
1. Retourner sur l'onglet "Trouver"
2. Refaire une recherche

**Résultat attendu :**
- ✅ L'offre affiche maintenant `1 place disponible` (au lieu de 3)
- ✅ Si on réserve à nouveau, le compteur diminue encore

**En cas d'échec :**
- Vérifier en BDD : `SELECT seats_available FROM carpool_offers_v2;`
- La colonne doit être décrémentée correctement

---

### ✅ Test 9 : Validation des places épuisées

**Étapes :**
1. Réserver la dernière place disponible
2. Essayer de réserver à nouveau

**Résultat attendu :**
- ✅ Alert : "Seulement 0 place(s) disponible(s)"
- ✅ Réservation refusée
- ✅ L'offre disparaît de la liste (filtre `seats_available > 0`)

**En cas d'échec :**
- Vérifier le endpoint GET `/api/v2/offers` filtre bien les offres

---

### ✅ Test 10 : Script de test automatisé

**Étapes :**
```bash
cd /home/ubuntu/projects/carette
./test_v2.sh
```

**Résultat attendu :**
```
🧪 TEST WORKFLOW V2 - CARETTE
✅ API accessible
✅ Offre créée avec succès (ID: X)
✅ Offres récupérées (1 trouvée(s))
✅ Réservation créée avec succès (ID: Y)
🎉 Tous les tests passés !
```

**En cas d'échec :**
- Regarder le message d'erreur du script
- Vérifier que l'API tourne bien sur le port 5001

---

## 🔍 Vérification Base de Données

```sql
-- Offres créées
SELECT id, driver_email, departure, destination, seats_available, created_at 
FROM carpool_offers_v2 
ORDER BY created_at DESC 
LIMIT 5;

-- Réservations créées
SELECT r.id, r.passenger_email, r.passengers_count, r.status, r.created_at,
       o.departure, o.destination
FROM carpool_reservations_v2 r
JOIN carpool_offers_v2 o ON r.offer_id = o.id
ORDER BY r.created_at DESC
LIMIT 5;

-- Statistiques
SELECT 
  (SELECT COUNT(*) FROM carpool_offers_v2) as total_offres,
  (SELECT COUNT(*) FROM carpool_reservations_v2) as total_reservations,
  (SELECT SUM(seats_available) FROM carpool_offers_v2 WHERE expires_at > NOW()) as places_disponibles;
```

---

## 🐛 Bugs Connus / TODO

- [ ] **UX Prompts** : Remplacer `prompt()` par modal HTML élégante
- [ ] **Email confirmation offre** : Envoyer email au conducteur après création offre
- [ ] **Stripe** : Intégrer vrai paiement (remplacer simulation)
- [ ] **Gestion réservations** : Page pour voir ses réservations via lien email
- [ ] **Confirmation token** : Implémenter validation par clic email
- [ ] **Analytics** : Tracker conversions et taux de réservation

---

## ✅ Critères de Validation Finale

Le workflow V2 est fonctionnel si :

1. ✅ Conducteur peut créer une offre sans compte (email/téléphone uniquement)
2. ✅ Offres apparaissent dans l'onglet "Trouver"
3. ✅ Popup paiement 1€ s'affiche lors de la réservation
4. ✅ Passager peut saisir ses coordonnées
5. ✅ Réservation créée en base de données
6. ✅ 2 emails envoyés (conducteur + passager) avec boutons WhatsApp
7. ✅ Places disponibles mises à jour correctement
8. ✅ Pas d'erreur dans les consoles navigateur/backend

---

**Date de création :** 2025-01-XX  
**Statut :** ✅ Workflow V2 implémenté et prêt à tester
