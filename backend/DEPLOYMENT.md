# 🚀 Déploiement du système email complet

## ✅ Ce qui est prêt

- ✅ Templates d'emails (12 complets)
- ✅ Module SMTP d'envoi
- ✅ Système de tokens magic links
- ✅ Endpoints avec envoi automatique (accept, refuse, cancel)
- ✅ Envoi initial lors de demande de réservation
- ✅ Cron jobs pour expiration et rappels

## 📋 Checklist de déploiement

### 1. Configuration SMTP

```bash
cd /home/ubuntu/projects/carette/backend

# Copier le fichier exemple
cp .env.example .env

# Éditer avec vos vrais identifiants
nano .env
```

**Pour Gmail:**
1. Aller sur https://myaccount.google.com/security
2. Activer "Validation en 2 étapes"
3. Aller dans "Mots de passe des applications"
4. Créer un mot de passe pour "Carette"
5. Copier le mot de passe généré dans `.env` → `SMTP_PASSWORD`

**Fichier `.env` minimal:**
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre-email@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
FROM_EMAIL=Carette <votre-email@gmail.com>
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
BASE_URL=https://votre-domaine.com
```

### 2. Charger les variables d'environnement

```bash
# Exporter pour la session actuelle
export $(cat .env | xargs)

# Vérifier
echo $SMTP_PASSWORD
```

### 3. Installer les cron jobs

```bash
cd /home/ubuntu/projects/carette/backend

# Installer
./install_cron.sh

# Vérifier
crontab -l
```

**Crons installés:**
- `0 * * * *` → Expirer demandes >24h (toutes les heures)
- `0 10 * * *` → Rappels J-1 (tous les jours à 10h)

### 4. Tester le système

#### Test manuel du cron
```bash
cd /home/ubuntu/projects/carette/backend

# Test expiration
python3 cron_jobs.py expire

# Test rappels
python3 cron_jobs.py reminders

# Exécuter tout
python3 cron_jobs.py all
```

#### Test envoi d'email
```python
cd /home/ubuntu/projects/carette/backend
python3

from email_sender import send_email

send_email(
    to_email="votre-email@test.com",
    subject="🔔 Test Carette",
    html_body="<h1>Test</h1><p>Si vous recevez ce mail, ça marche !</p>",
    text_body="Test - Si vous recevez ce mail, ça marche !"
)
```

#### Test flux complet
1. Créer une offre via le widget
2. Faire une demande de réservation
3. **Vérifier:** Email reçu par le conducteur avec boutons [Accepter][Refuser]
4. **Vérifier:** Email reçu par le passager "Demande envoyée"
5. Cliquer sur [Accepter] dans l'email conducteur
6. **Vérifier:** Email au passager "Réservation confirmée"
7. **Vérifier:** Email au conducteur "Itinéraire mis à jour"

### 5. Monitoring

```bash
# Logs des cron jobs
tail -f /var/log/carette_cron.log

# Logs du serveur Flask
tail -f /path/to/api.log

# Vérifier les emails en attente d'expiration
mysql -u carette_user -p carette_db
SELECT COUNT(*) FROM carpool_reservations WHERE status='pending' AND created_at < NOW() - INTERVAL 24 HOUR;
```

### 6. Redémarrer le serveur

```bash
# Si systemd
sudo systemctl restart carette-api

# Si screen/tmux
# Arrêter l'ancien process et relancer
pkill -f "python.*api.py"
cd /home/ubuntu/projects/carette/backend
nohup python3 api.py > api.log 2>&1 &
```

## 🔍 Dépannage

### Emails non envoyés (mode dev)

Si `SMTP_PASSWORD` n'est pas défini, les emails sont **loggés** mais pas envoyés:

```
📧 [DEV MODE] Email à driver@example.com: 🔔 Nouvelle demande
```

Solution: Configurer `.env` avec le vrai mot de passe SMTP

### Erreur "Authentication failed"

```
❌ Erreur envoi email: (535, b'5.7.8 Username and Password not accepted')
```

Solutions:
1. Vérifier que "Validation en 2 étapes" est activée
2. Utiliser un "Mot de passe d'application" Gmail (pas le mot de passe normal)
3. Vérifier que `SMTP_USER` correspond au compte Gmail

### Cron jobs ne s'exécutent pas

```bash
# Vérifier que les crons sont installés
crontab -l

# Vérifier les permissions
ls -la /home/ubuntu/projects/carette/backend/cron_jobs.py

# Tester manuellement
cd /home/ubuntu/projects/carette/backend
python3 cron_jobs.py expire
```

### Tokens expirés

Les magic links expirent après 7 jours. Si un utilisateur clique sur un vieux lien:

```
Token invalide: Token expiré
```

C'est normal et voulu pour la sécurité.

## 📊 Statistiques à surveiller

```sql
-- Demandes en attente
SELECT COUNT(*) FROM carpool_reservations WHERE status='pending';

-- Demandes expirées automatiquement
SELECT COUNT(*) FROM carpool_reservations WHERE status='expired';

-- Taux d'acceptation
SELECT 
    COUNT(CASE WHEN status='confirmed' THEN 1 END) * 100.0 / COUNT(*) as taux_acceptation
FROM carpool_reservations
WHERE status IN ('confirmed', 'refused');

-- Emails envoyés aujourd'hui (via logs)
grep "📧" /var/log/carette_cron.log | grep "$(date +%Y-%m-%d)" | wc -l
```

## 🎯 Ce qui reste à faire (optionnel)

### Recalcul d'itinéraire après changement

Actuellement, quand un passager est ajouté/retiré:
- ✅ Email au conducteur avec liste MAJ
- ❌ Pas d'email aux autres passagers (horaire peut changer)

Pour compléter:
1. Créer `route_recalculator.py`
2. Appeler OSRM après chaque changement
3. Détecter les passagers avec pickup time modifié
4. Envoyer `email_passenger_route_updated()` à chacun

### Endpoints supplémentaires

- `/api/reservation/remove` → Conducteur retire un passager
- `/api/offer/cancel` → Conducteur annule toute l'offre
- `/api/offer/<id>/reservations` → Page HTML liste des réservations

### Dashboard conducteur

Une page web simple pour voir:
- Mes offres actives
- Les demandes en attente
- Les passagers confirmés
- Boutons pour actions

## ✅ Validation finale

Checklist avant mise en production:

- [ ] `.env` configuré avec vrais identifiants SMTP
- [ ] `SECRET_KEY` généré aléatoirement (pas la valeur par défaut)
- [ ] Cron jobs installés (`crontab -l`)
- [ ] Test d'envoi email réussi
- [ ] Test flux complet: Demande → Accept → Emails reçus
- [ ] Logs surveillés (`tail -f /var/log/carette_cron.log`)
- [ ] Serveur redémarré avec nouvelles variables

## 🎉 Système complet !

Une fois déployé, le système est **100% automatique** :

1. Passager demande → Emails envoyés
2. Conducteur accepte/refuse → Emails envoyés
3. Passager annule → Emails envoyés
4. Timeout 24h → Emails expiration (cron)
5. J-1 → Rappels automatiques (cron)

**Zéro intervention manuelle nécessaire !** 🚀
