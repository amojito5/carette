# 📧 État du système de notifications email

## ✅ Ce qui fonctionne MAINTENANT

### 1. **Système de tokens** (100% opérationnel)
- ✅ Génération de magic links sécurisés (HMAC-SHA256)
- ✅ Validation avec expiration (7 jours)
- ✅ Actions supportées: accept, refuse, cancel

### 2. **Templates d'emails** (100% terminés)
- ✅ 12 templates HTML + texte brut
- ✅ Design élégant avec gradients
- ✅ Boutons d'action magic links
- ✅ Support images de cartes inline

### 3. **Module d'envoi SMTP** (nouveau ✨)
- ✅ `email_sender.py` créé
- ✅ Support HTML + texte + images
- ✅ Mode dev (logs sans envoi si pas de SMTP_PASSWORD)
- ✅ Envoi batch pour plusieurs destinataires

### 4. **Endpoints avec envoi d'emails** (intégré ✨)

#### ✅ `/api/reservation/accept` - Accepter une demande
**Quand:** Le conducteur clique sur [Accepter] dans son email

**Emails envoyés automatiquement:**
1. **Au passager:** Réservation confirmée
   - Template: `email_reservation_confirmed_to_passenger()`
   - Contenu: RDV, conducteur, bouton [Annuler]
   
2. **Au conducteur:** Itinéraire mis à jour
   - Template: `email_driver_route_updated()`
   - Contenu: Liste complète des passagers, carte, boutons actions

**Ce qui manque:**
- ⚠️ Emails aux **autres passagers** (si horaire change) → nécessite recalcul itinéraire OSRM

#### ✅ `/api/reservation/refuse` - Refuser une demande
**Quand:** Le conducteur clique sur [Refuser] dans son email

**Emails envoyés automatiquement:**
1. **Au passager:** Demande refusée
   - Template: `email_reservation_refused()`
   - Contenu: Message empathique, suggestions

#### ✅ `/api/reservation/cancel` - Annuler (passager)
**Quand:** Le passager clique sur [Annuler] dans son email

**Validations:**
- ✅ Bloque si <24h avant le départ
- ✅ Libère la place
- ✅ Met à jour le statut

**Emails envoyés automatiquement:**
1. **Au passager:** Annulation confirmée
   - Template: `email_cancellation_confirmed_passenger()`
   
2. **Au conducteur:** Itinéraire mis à jour
   - Template: `email_driver_route_updated()`
   - Liste des passagers restants

**Ce qui manque:**
- ⚠️ Emails aux **autres passagers** (si horaire change) → nécessite recalcul itinéraire OSRM

---

## ⚠️ Ce qui manque encore

### 1. **Envoi initial de la demande** (pas encore fait)
📍 **Dans:** `/api/v2/reservations` POST

Actuellement, quand un passager fait une demande via le widget, **aucun email n'est envoyé**.

**À ajouter:**
```python
# Après création de la réservation en DB
from email_templates import email_new_reservation_request, email_request_sent_to_passenger
from email_sender import send_email
from token_manager import generate_accept_link, generate_refuse_link

# 1. Email au conducteur
accept_url = generate_accept_link(reservation_id, driver_email, BASE_URL)
refuse_url = generate_refuse_link(reservation_id, driver_email, BASE_URL)

subject, html, text = email_new_reservation_request(
    driver_email=driver_email,
    driver_name=driver_name,
    passenger_name=passenger_name,
    passenger_email=passenger_email,
    passenger_phone=passenger_phone,
    pickup_address=pickup_address,
    offer=offer_data,
    map_image_path=map_path,  # Carte générée
    accept_url=accept_url,
    refuse_url=refuse_url
)
send_email(driver_email, subject, html, text, map_image_path=map_path)

# 2. Email au passager (confirmation envoi)
subject2, html2, text2 = email_request_sent_to_passenger(
    passenger_email=passenger_email,
    passenger_name=passenger_name,
    driver_name=driver_name,
    offer=offer_data
)
send_email(passenger_email, subject2, html2, text2)
```

### 2. **Recalcul d'itinéraire** (pas encore fait)
📍 **Fichier à créer:** `route_recalculator.py`

**Pourquoi:** Quand un passager est ajouté/retiré, il faut:
- Recalculer l'itinéraire avec OSRM
- Déterminer les nouveaux waypoints (ordre des pickups)
- Calculer les nouvelles heures de pickup pour chaque passager
- Détecter quels passagers voient leur horaire changer

**Workflow:**
```python
def recalculate_route_after_change(offer_id, all_passengers):
    """
    Recalcule l'itinéraire et retourne les passagers affectés
    
    Returns:
        {
            'route': {...},  # Nouvelle géométrie
            'passengers_updated': [
                {
                    'passenger_id': 123,
                    'old_pickup_time': '14:30',
                    'new_pickup_time': '14:45',
                    'time_changed': True
                },
                ...
            ]
        }
    """
    # 1. Extraire les coordonnées de tous les pickups
    # 2. Appeler OSRM pour optimiser l'ordre
    # 3. Calculer les durées cumulées
    # 4. Comparer avec les anciens horaires
    # 5. Retourner la liste des changements
```

**Ensuite envoyer les emails aux passagers affectés:**
```python
for p in passengers_with_time_change:
    subject, html, text = email_passenger_route_updated(
        passenger_email=p['email'],
        passenger_name=p['name'],
        new_pickup_time=p['new_pickup_time'],
        old_pickup_time=p['old_pickup_time'],
        ...
    )
    send_email(p['email'], subject, html, text)
```

### 3. **Endpoints supplémentaires** (pas encore fait)

#### `/api/reservation/remove` - Conducteur retire un passager
```python
@app.route('/api/reservation/remove', methods=['GET'])
def remove_passenger_by_driver():
    # Vérifier token conducteur
    # Supprimer le passager
    # Envoyer email au passager retiré
    # Envoyer email au conducteur (itinéraire MAJ)
    # Envoyer emails aux autres passagers si horaire change
```

#### `/api/offer/cancel` - Conducteur annule l'offre entière
```python
@app.route('/api/offer/cancel', methods=['GET'])
def cancel_entire_offer():
    # Vérifier token conducteur
    # Vérifier délai 24h
    # Annuler l'offre
    # Envoyer email à TOUS les passagers confirmés
    # Template: email_offer_cancelled_by_driver()
```

#### `/api/offer/<id>/reservations` - Voir les réservations
```python
@app.route('/api/offer/<int:offer_id>/reservations', methods=['GET'])
def view_reservations():
    # Afficher page HTML avec liste des réservations
    # Boutons pour accepter/refuser les pending
    # Boutons pour retirer les confirmed
```

### 4. **Tâches automatiques (cron jobs)** (pas encore fait)
📍 **Fichier à créer:** `cron_jobs.py`

#### Job 1: Expirer les demandes après 24h
```python
def expire_pending_reservations():
    """
    Tourne toutes les heures
    Marque status='expired' pour les pending >24h
    Envoie email au passager: email_request_expired()
    """
    # SELECT * FROM carpool_reservations 
    # WHERE status='pending' AND created_at < NOW() - INTERVAL 24 HOUR
    
    for reservation in expired:
        # UPDATE status = 'expired'
        # send_email(passenger, email_request_expired())
```

**Setup crontab:**
```bash
0 * * * * cd /home/ubuntu/projects/carette/backend && python3 cron_jobs.py expire
```

#### Job 2: Rappels J-1
```python
def send_24h_reminders():
    """
    Tourne tous les jours à 10h
    Envoie rappels pour les trajets demain
    """
    # SELECT * FROM carpool_offers 
    # WHERE datetime BETWEEN NOW() + INTERVAL 23 HOUR AND NOW() + INTERVAL 25 HOUR
    
    for offer in tomorrow_offers:
        # Email au conducteur
        send_email(driver, email_reminder_24h(role='driver', ...))
        
        # Email à chaque passager confirmé
        for passenger in confirmed_passengers:
            send_email(passenger, email_reminder_24h(role='passenger', ...))
```

**Setup crontab:**
```bash
0 10 * * * cd /home/ubuntu/projects/carette/backend && python3 cron_jobs.py reminders
```

### 5. **Configuration SMTP** (pas encore fait)
📍 **Fichier:** `.env`

Créer un fichier `.env` à la racine :
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@carette.com
SMTP_PASSWORD=votre_mot_de_passe_app
FROM_EMAIL=Carette Covoiturage <noreply@carette.com>
SECRET_KEY=changez-moi-en-production-clé-très-longue-et-aléatoire
BASE_URL=https://votre-domaine.com
```

**Pour Gmail:**
1. Activer "Validation en 2 étapes"
2. Générer un "Mot de passe d'application"
3. Utiliser ce mot de passe dans SMTP_PASSWORD

**Modifier `token_manager.py`:**
```python
import os
SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-dev-key')
```

---

## 📊 Matrice de couverture des notifications

| Événement | Email conducteur | Email passager | Emails autres pass. | Status |
|-----------|------------------|----------------|---------------------|--------|
| **Demande initiale** | ✅ New request (accept/refuse) | ✅ Confirmation envoi | - | ⚠️ **PAS INTÉGRÉ** |
| **Accept** | ✅ Route updated | ✅ Confirmed | ⚠️ Route updated si horaire change | **50% fait** |
| **Refuse** | - | ✅ Refused | - | ✅ **COMPLET** |
| **Cancel passager** | ✅ Route updated | ✅ Cancel confirmed | ⚠️ Route updated si horaire change | **50% fait** |
| **Cancel conducteur** | - | ✅ Offer cancelled | ✅ Offer cancelled | ❌ **PAS FAIT** |
| **Timeout 24h** | - | ✅ Request expired | - | ❌ **PAS FAIT (cron)** |
| **Rappel J-1** | ✅ Reminder | ✅ Reminder | ✅ Reminder | ❌ **PAS FAIT (cron)** |
| **Conducteur retire** | ✅ Route updated | ✅ Removed | ⚠️ Route updated si horaire | ❌ **PAS FAIT** |

**Légende:**
- ✅ = Template existe ET envoi intégré
- ⚠️ = Template existe mais pas intégré (manque recalcul route)
- ❌ = Pas encore fait

---

## 🎯 Plan d'action pour compléter

### Phase 1: Flux de base fonctionnel (1-2h)
1. ✅ Intégrer envoi emails dans `/api/v2/reservations` POST
2. ✅ Tester le flux: Demande → Accept → Refuse
3. ✅ Configurer SMTP (Gmail ou autre)

### Phase 2: Recalcul d'itinéraire (2-3h)
1. ❌ Créer `route_recalculator.py`
2. ❌ Intégrer OSRM pour waypoints optimisés
3. ❌ Calculer les heures de pickup
4. ❌ Envoyer emails aux passagers affectés

### Phase 3: Endpoints manquants (1-2h)
1. ❌ `/api/reservation/remove`
2. ❌ `/api/offer/cancel`
3. ❌ `/api/offer/<id>/reservations` (page HTML)

### Phase 4: Cron jobs (1h)
1. ❌ Créer `cron_jobs.py`
2. ❌ Job expiration 24h
3. ❌ Job rappels J-1
4. ❌ Setup crontab

### Phase 5: Production (30min)
1. ❌ Déplacer SECRET_KEY dans .env
2. ❌ Tester emails réels
3. ❌ Monitoring logs

---

## 🚀 Pour tester maintenant

### Mode dev (sans SMTP)
Les emails sont loggés dans la console :
```bash
cd /home/ubuntu/projects/carette/backend
python3 api.py

# Dans les logs tu verras:
# 📧 [DEV MODE] Email à driver@example.com: 🔔 Nouvelle demande de réservation
```

### Avec SMTP (production)
```bash
export SMTP_PASSWORD="votre_mot_de_passe_app"
python3 api.py

# Les emails seront vraiment envoyés
```

### Tester un magic link
```python
from token_manager import generate_accept_link

url = generate_accept_link(
    reservation_id=123,
    user_email="driver@example.com",
    base_url="http://localhost:5000"
)
print(url)
# http://localhost:5000/api/reservation/accept?token=eyJhY3Rpb24...

# Ouvre ce lien dans le navigateur → accepte la réservation
# → emails envoyés automatiquement
```

---

## ✅ Résumé

### Ce qui marche MAINTENANT:
- ✅ Système de tokens magic links
- ✅ Tous les templates d'emails
- ✅ Module SMTP d'envoi
- ✅ Emails lors de: Accept, Refuse, Cancel passager
- ✅ Validation règles 24h

### Ce qui manque:
- ⚠️ Envoi initial demande (dans `/api/v2/reservations`)
- ⚠️ Recalcul itinéraire + emails passagers affectés
- ❌ Endpoints: remove, cancel offer, view reservations
- ❌ Cron jobs: expiration + rappels
- ❌ Config production (.env)

**Estimation:** Encore **6-8h** de dev pour avoir le système 100% complet.
