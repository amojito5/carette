# 📧 Templates d'emails - Documentation

## 📁 Fichier : `email_templates.py`

**Taille :** 1738 lignes  
**Templates :** 12 fonctions complètes  
**Format :** HTML + Texte brut pour chaque email

## 🎯 Liste des templates

### 1. `email_new_reservation_request()`
**Trigger :** Passager demande une réservation  
**Destinataire :** Conducteur  
**Contenu :**
- Header gradient violet
- Détails du passager (nom, email, téléphone)
- Info du trajet demandé
- Carte statique du trajet
- **Boutons d'action :** [Accepter] [Refuser]
- Warning : Répondre dans les 24h sinon expiration

### 2. `email_request_sent_to_passenger()`
**Trigger :** Passager vient de faire une demande  
**Destinataire :** Passager  
**Contenu :**
- Header gradient vert
- Confirmation que la demande est envoyée
- Info : Le conducteur a 24h pour répondre
- Détails du trajet et du conducteur

### 3. `email_reservation_refused()`
**Trigger :** Conducteur refuse la demande  
**Destinataire :** Passager  
**Contenu :**
- Header gradient rouge
- Message empathique avec emoji triste
- Explication du refus
- Encouragement à chercher d'autres trajets

### 4. `email_driver_route_updated()`
**Trigger :** Après acceptation ou annulation d'un passager  
**Destinataire :** Conducteur  
**Contenu :**
- Header gradient violet
- Raison de la mise à jour
- Info du trajet
- **Carte statique avec nouvel itinéraire**
- **Liste complète des passagers** avec numéros emoji (1️⃣ 2️⃣ 3️⃣...)
- Chaque passager : nom, horaire pickup, adresse, téléphone
- Bouton [Retirer] pour chaque passager
- Places restantes
- Bouton [Voir les demandes en attente]
- Lien pour annuler l'offre

### 5. `email_passenger_route_updated()`
**Trigger :** Quand l'horaire de pickup d'un passager change  
**Destinataire :** Passagers existants affectés  
**Contenu :**
- Header gradient orange
- Raison du changement (nouveau passager ajouté/retiré)
- **Box changement d'horaire** avec ancien barré → nouveau
- Nouveau RDV : heure et adresse
- Carte statique
- Info conducteur avec bouton WhatsApp
- Bouton [Annuler ma réservation]
- Warning : Possible jusqu'à 24h avant

### 6. `email_cancellation_confirmed_passenger()`
**Trigger :** Passager annule sa réservation  
**Destinataire :** Passager  
**Contenu :**
- Header gradient vert
- Confirmation d'annulation
- Détails du trajet annulé
- Info : Conducteur et autres passagers prévenus

### 7. `email_offer_cancelled_by_driver()`
**Trigger :** Conducteur annule l'offre entière  
**Destinataire :** Tous les passagers confirmés  
**Contenu :**
- Header gradient rouge
- Message d'excuse
- Détails du trajet annulé (box rouge)
- Message empathique
- Suggestion de chercher d'autres trajets

### 8. `email_request_expired()`
**Trigger :** 24h passées sans réponse du conducteur  
**Destinataire :** Passager  
**Contenu :**
- Header gradient gris
- Notification d'expiration
- Détails du trajet
- Explication (conducteur n'a pas consulté emails)
- Box bleue : Suggestion de refaire une demande

### 9. `email_reminder_24h(role='driver')`
**Trigger :** Cron job J-1 avant le départ  
**Destinataire :** Conducteur  
**Contenu :**
- Header gradient violet
- "Demain c'est le grand départ !"
- Détails du trajet
- **Liste complète des passagers** avec infos pickup
- Warning orange : Dernier moment pour annuler
- Bouton [Voir les détails]

### 10. `email_reminder_24h(role='passenger')`
**Trigger :** Cron job J-1 avant le départ  
**Destinataire :** Chaque passager  
**Contenu :**
- Header gradient vert
- "Demain c'est le grand jour !"
- **Box RDV** : Heure et adresse de pickup
- Détails du trajet
- Info conducteur avec bouton WhatsApp
- Warning orange : Trop tard pour annuler

### 11. `email_card_template()`
**Usage :** Template de base réutilisable  
**Contenu :**
- Structure HTML générique
- Style inline pour emails
- Gradient header personnalisable

### 12. `email_offer_published()`
**Trigger :** Conducteur publie une offre  
**Destinataire :** Conducteur  
**Contenu :**
- Confirmation de publication
- Détails de l'offre

### 13. `email_reservation_confirmed_to_passenger()`
**Trigger :** Conducteur accepte la demande  
**Destinataire :** Passager  
**Contenu :**
- Confirmation de réservation
- Détails du RDV
- Info conducteur
- Bouton [Annuler]

## 🎨 Design System

### Couleurs
- **Violet principal** : `#8b5cf6` → `#7c3aed` (gradient)
- **Vert succès** : `#10b981` → `#059669`
- **Rouge erreur** : `#ef4444` → `#dc2626`
- **Orange warning** : `#f59e0b` → `#d97706`
- **Gris neutre** : `#6b7280` → `#4b5563`
- **Accent trajet** : `#c47cff` (violet widget)
- **WhatsApp** : `#25d366`

### Structure HTML
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
    <div style="max-width:600px;margin:40px auto;background:white;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.1);overflow:hidden;">
        
        <!-- Header avec gradient -->
        <div style="background:linear-gradient(135deg, #COLOR1 0%, #COLOR2 100%);padding:32px;text-align:center;">
            <div style="font-size:48px;margin-bottom:12px;">EMOJI</div>
            <h1 style="color:white;margin:0;font-size:28px;font-weight:700;">TITRE</h1>
        </div>
        
        <!-- Body -->
        <div style="padding:32px;">
            <!-- Contenu -->
        </div>
        
        <!-- Footer -->
        <div style="text-align:center;padding:20px;background:#f8f9fa;">
            <p style="margin:0;font-size:13px;color:#999;">Carette Covoiturage</p>
        </div>
    </div>
</body>
</html>
```

### Boutons d'action
```html
<a href="{url}" style="display:inline-block;padding:14px 28px;background:#10b981;color:white;text-decoration:none;border-radius:8px;font-weight:600;font-size:14px;">
    ✓ Accepter
</a>
```

### Cartes d'information
```html
<div style="background:#f8f9fa;padding:20px;border-radius:12px;margin-bottom:24px;border-left:4px solid #c47cff;">
    <!-- Contenu -->
</div>
```

### Warning boxes
```html
<div style="background:#fef3c7;border:2px solid #f59e0b;padding:20px;border-radius:12px;">
    <p style="margin:0;color:#78350f;font-size:15px;font-weight:700;">⚠️ Message</p>
</div>
```

## 📦 Format de retour

Chaque fonction retourne un tuple :
```python
return (subject, html_body, text_body)
```

- **subject** : Ligne de sujet de l'email
- **html_body** : Version HTML complète
- **text_body** : Version texte brut (fallback)

## 🔗 Magic Links

Les templates utilisent des magic links pour les actions :
- Format : `{base_url}/api/reservation/accept?token={TOKEN}`
- Tokens HMAC-SHA256 avec expiration 7 jours
- Stateless (pas de session nécessaire)

## 🌍 Images de carte

Les emails peuvent inclure des cartes statiques :
```html
<img src="cid:map_image" alt="Carte du trajet" style="width:100%;max-width:600px;border-radius:12px;" />
```

Le fichier image doit être attaché à l'email avec le CID `map_image`.

## 📱 Responsive Design

- Max-width: 600px pour compatibilité mobile
- Inline styles (requis par clients email)
- Font-family: `-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif`
- Padding adaptatif

## ✅ Compatibilité

- ✅ Gmail
- ✅ Outlook
- ✅ Apple Mail
- ✅ Clients mobiles
- ✅ Mode sombre (contraste suffisant)

## 🚀 Utilisation

```python
from email_templates import email_new_reservation_request, email_request_sent_to_passenger

# Générer l'email au conducteur
subject, html, text = email_new_reservation_request(
    driver_email="driver@example.com",
    driver_name="Jean Dupont",
    passenger_name="Marie Martin",
    passenger_email="marie@example.com",
    passenger_phone="+33 6 12 34 56 78",
    pickup_address="123 Rue de Paris, Lyon",
    offer={
        'departure': 'Lyon',
        'destination': 'Paris',
        'datetime': 'Mercredi 15 janvier 2025 à 14h30',
        'seats': 3
    },
    map_image_path="maps/abc123.png",
    accept_url="https://carette.com/api/reservation/accept?token=xxx",
    refuse_url="https://carette.com/api/reservation/refuse?token=xxx"
)

# Envoyer l'email (utiliser votre service SMTP)
send_email(driver_email, subject, html, text, attachments=[map_image_path])
```

## 📝 Notes importantes

- **Toujours envoyer HTML + texte** : Certains clients email n'affichent pas le HTML
- **Images inline** : Utiliser `cid:` pour les images embarquées
- **Emojis** : Testés sur tous les clients, bien supportés
- **Snapshots** : Chaque email est un snapshot complet (pas de dépendance externe)
- **Pas de JavaScript** : Interdit dans les emails
- **Pas de CSS externe** : Tout doit être inline

## 🔄 Workflow complet

```
1. Passager demande
   └─> email_new_reservation_request() → Conducteur
   └─> email_request_sent_to_passenger() → Passager

2a. Conducteur ACCEPTE
   └─> email_reservation_confirmed_to_passenger() → Passager
   └─> email_driver_route_updated() → Conducteur (avec carte + liste)
   └─> email_passenger_route_updated() → Autres passagers (si horaires changent)

2b. Conducteur REFUSE
   └─> email_reservation_refused() → Passager

3. Passager ANNULE (si >24h)
   └─> email_cancellation_confirmed_passenger() → Passager
   └─> email_driver_route_updated() → Conducteur
   └─> email_passenger_route_updated() → Autres passagers

4. Conducteur ANNULE offre
   └─> email_offer_cancelled_by_driver() → Tous les passagers

5. TIMEOUT 24h
   └─> email_request_expired() → Passager

6. RAPPEL J-1
   └─> email_reminder_24h(role='driver') → Conducteur
   └─> email_reminder_24h(role='passenger') → Chaque passager
```

## 🎯 Prochaines étapes

1. Intégrer l'envoi dans `/api/v2/reservations`
2. Créer `cron_jobs.py` pour expiration + rappels
3. Tester l'affichage sur différents clients email
4. Configurer SMTP en production
5. Ajouter tracking d'ouverture (optionnel)
