# 🔐 Système de Magic Links - État d'avancement

## ✅ Terminé

### 1. Système de tokens sécurisés
- ✅ `token_manager.py` créé
- ✅ Génération de tokens HMAC-SHA256
- ✅ Vérification avec expiration
- ✅ Fonctions helper pour chaque type de lien
- ✅ Tests passés

### 2. Endpoints API
- ✅ `api_magic_links.py` créé
- ✅ `/api/reservation/accept` - Accepter une réservation
- ✅ `/api/reservation/refuse` - Refuser une réservation  
- ✅ `/api/reservation/cancel` - Passager annule
- ✅ Pages HTML de confirmation élégantes
- ✅ Validation des délais (< 24h bloqué)
- ✅ Intégration dans `api.py`

### 3. Templates HTML
- ✅ Page de succès (gradient violet)
- ✅ Page d'erreur (gradient rouge)
- ✅ Page d'erreur avec contact conducteur

### 4. Templates d'emails ✅ **TERMINÉ**
Fichier `email_templates.py` - 1738 lignes - 12 templates complets :

- ✅ `email_new_reservation_request()` - Conducteur reçoit demande avec [Accept][Refuse]
- ✅ `email_request_sent_to_passenger()` - Confirmation envoi au passager
- ✅ `email_reservation_refused()` - Demande refusée
- ✅ `email_driver_route_updated()` - Itinéraire mis à jour (conducteur + carte + liste passagers)
- ✅ `email_passenger_route_updated()` - Horaire modifié (passagers existants)
- ✅ `email_cancellation_confirmed_passenger()` - Confirmation annulation passager
- ✅ `email_offer_cancelled_by_driver()` - Offre annulée par conducteur
- ✅ `email_request_expired()` - Timeout 24h dépassé
- ✅ `email_reminder_24h()` - Rappel J-1 (conducteur + passagers)
- ✅ `email_card_template()` - Template de base
- ✅ `email_offer_published()` - Offre publiée
- ✅ `email_reservation_confirmed_to_passenger()` - Réservation confirmée

**Design des templates :**
- Headers avec gradient backgrounds (violet/vert/rouge/orange selon contexte)
- Boutons d'action avec magic links
- Responsive design
- Inline styles pour compatibilité email
- Versions HTML + texte brut
- Emojis pour UX sympathique
- Cartes d'information stylisées
- WhatsApp buttons

## 🚧 À faire

### 5. Calcul d'itinéraire
- [ ] `route_recalculator.py` - Recalculer route après changement passager
- [ ] Intégration OSRM pour nouveaux waypoints
- [ ] Mise à jour times de pickup pour chaque passager

### 6. Endpoints supplémentaires
- [ ] `/api/reservation/remove` - Conducteur retire un passager
- [ ] `/api/offer/cancel` - Annuler offre entière
- [ ] `/api/offer/<id>/reservations` - Voir toutes les réservations

### 7. Intégration dans le flux
- [ ] Modifier `/api/v2/reservations` POST pour envoyer les emails
- [ ] Appeler `email_new_reservation_request()` au conducteur
- [ ] Appeler `email_request_sent_to_passenger()` au passager

### 8. Tâches automatisées (cron jobs)
- [ ] `cron_jobs.py` - Script pour tâches planifiées
- [ ] Job : Expirer demandes après 24h (marquer status='expired')
- [ ] Job : Envoyer rappels J-1 à conducteur + passagers
- [ ] Setup crontab sur le serveur

### 9. Configuration production
- [ ] Déplacer SECRET_KEY dans `.env`
- [ ] Ajouter variable `BASE_URL` dans `.env`
- [ ] Configurer SMTP pour envoi emails
- [ ] Tester en production

### 10. Tests
- [ ] Test flux complet : demande → accept → emails route update
- [ ] Test expiration 24h
- [ ] Test refus
- [ ] Test annulation passager
- [ ] Test annulation conducteur
- [ ] Test rappels J-1

## 📋 Matrice des notifications email

| Événement | Destinataire(s) | Template | Magic Links |
|-----------|----------------|----------|-------------|
| Passager demande | Conducteur | `email_new_reservation_request()` | [Accept] [Refuse] |
| Passager demande | Passager | `email_request_sent_to_passenger()` | - |
| Conducteur accepte | Passager | `email_reservation_confirmed_to_passenger()` | [Cancel] |
| Conducteur accepte | Conducteur | `email_driver_route_updated()` | [Remove passenger] [Cancel offer] |
| Conducteur accepte | Autres passagers | `email_passenger_route_updated()` | [Cancel] |
| Conducteur refuse | Passager | `email_reservation_refused()` | - |
| Passager annule | Passager | `email_cancellation_confirmed_passenger()` | - |
| Passager annule | Conducteur | `email_driver_route_updated()` | - |
| Passager annule | Autres passagers | `email_passenger_route_updated()` | [Cancel] |
| Conducteur annule offre | Tous passagers | `email_offer_cancelled_by_driver()` | - |
| Timeout 24h | Passager | `email_request_expired()` | - |
| J-1 avant départ | Conducteur | `email_reminder_24h(role='driver')` | - |
| J-1 avant départ | Chaque passager | `email_reminder_24h(role='passenger')` | - |

## 🔑 Format des tokens

```
Format: base64(payload).signature

Payload:
{
  "action": "accept_reservation",
  "resource_id": 123,
  "email": "user@example.com",
  "exp": 1735689600
}

Expiration: 7 jours (604800 secondes)
Secret: "carette-secret-key-change-me-in-production-2025"
```

## 📝 Notes importantes

- **Règle 24h** : Passagers ne peuvent pas annuler <24h avant départ
- **Règle 24h** : Conducteurs ne peuvent pas annuler offre <24h avant départ
- **Timeout demandes** : Les demandes expirent automatiquement après 24h sans réponse
- **Stateless** : Les magic links sont stateless, aucune session nécessaire
- **Snapshots** : Chaque email contient un snapshot complet de l'état actuel
- **Pas de spam** : Maximum 1 email par action réelle (pas de ping-pong)
- **UX email-only** : Pas besoin d'app, tout via email

## 🎨 Couleurs du design

- Violet principal: `#8b5cf6` → `#7c3aed` (gradient header succès/info)
- Vert succès: `#10b981` → `#059669`
- Rouge erreur: `#ef4444` → `#dc2626`
- Orange warning: `#f59e0b` → `#d97706`
- Gris neutre: `#6b7280` → `#4b5563`
- Accent trajet: `#c47cff` (violet widget)
- WhatsApp: `#25d366`

