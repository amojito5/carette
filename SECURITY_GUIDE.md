# 🔒 Guide de Sécurité - Carette

**Mise à jour**: 15 décembre 2025  
**Important**: Ce guide doit être suivi AVANT tout déploiement en production.

---

## ⚡ Configuration Rapide (Production)

### 1. Générer les secrets

```bash
# Générer automatiquement tous les secrets nécessaires
python3 generate_secrets.py

# OU manuellement:
python3 -c "import secrets; print('CARETTE_SECRET_KEY=' + secrets.token_hex(32))"
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))"
```

### 2. Créer le fichier `.env`

```bash
# Copier le template
cp .env.example .env

# Éditer avec vos valeurs (générez de VRAIS secrets !)
nano .env
```

**Exemple de `.env` sécurisé:**

```bash
# Base de données
CARETTE_DB_NAME=carette_db
CARETTE_DB_HOST=localhost
CARETTE_DB_USER=carette_user
CARETTE_DB_PASSWORD=VotreMdpSuperSecurise123!@#
CARETTE_DB_ROOT_PASSWORD=RootMdpEncorePlusSecurise456!@#

# Sécurité (générez avec generate_secrets.py)
CARETTE_SECRET_KEY=a1b2c3d4e5f6...votre_cle_hex_64_chars
JWT_SECRET_KEY=f6e5d4c3b2a1...autre_cle_hex_64_chars

# API externes (optionnel)
ORS_API_KEY=votre_cle_openrouteservice

# Configuration
CARETTE_DEBUG=False
CARETTE_API_PORT=5001
CARETTE_ALLOWED_ORIGINS=https://votre-domaine.com,https://www.votre-domaine.com

# Rate limiting (Redis recommandé)
REDIS_URL=redis://localhost:6379/0
```

### 3. Vérifier que `.env` est ignoré par Git

```bash
# Vérifier
git status

# Si .env apparaît, l'ajouter à .gitignore
echo ".env" >> .gitignore

# Si déjà commité par erreur, le retirer:
git rm --cached .env
git commit -m "Remove .env from version control"
```

### 4. Installer les dépendances de sécurité

```bash
cd backend
pip install -r requirements.txt

# Vérifier les vulnérabilités
pip install safety
safety check
```

### 5. Configurer Redis (recommandé pour production)

```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# macOS
brew install redis
brew services start redis

# Vérifier
redis-cli ping  # Doit répondre "PONG"
```

---

## ✅ Checklist de Sécurité

Avant le déploiement, vérifiez:

- [ ] `.env` créé avec des secrets uniques et forts
- [ ] `.env` dans `.gitignore`
- [ ] `CARETTE_DEBUG=False` en production
- [ ] `CARETTE_ALLOWED_ORIGINS` configuré avec vos domaines réels
- [ ] Mots de passe BDD changés (pas les valeurs par défaut)
- [ ] Redis installé et configuré
- [ ] Dépendances à jour (`pip install -U -r requirements.txt`)
- [ ] Aucune clé API dans le frontend
- [ ] HTTPS activé (Let's Encrypt, Cloudflare, etc.)
- [ ] Firewall configuré (ports 80/443 ouverts, 5001/9000 fermés au public)

---

## 🔐 Bonnes Pratiques

### Gestion des Secrets

1. **Ne JAMAIS commiter de secrets dans Git**
   - Utilisez `.env` pour les variables sensibles
   - Ajoutez `.env` dans `.gitignore`
   - Utilisez `.env.example` comme template (sans valeurs réelles)

2. **Rotation des secrets**
   - Changez les secrets régulièrement (tous les 3-6 mois)
   - Changez immédiatement si compromis
   - Générez avec `generate_secrets.py`

3. **Stockage sécurisé**
   - En production: AWS Secrets Manager, HashiCorp Vault, etc.
   - Permissions fichier `.env`: `chmod 600 .env`
   - Ne pas partager par email/chat

### Base de Données

1. **Mots de passe forts**
   - Minimum 20 caractères
   - Mélange lettres, chiffres, symboles
   - Générés aléatoirement

2. **Privilèges minimaux**
   ```sql
   -- L'utilisateur app ne doit pas être root
   GRANT SELECT, INSERT, UPDATE, DELETE ON carette_db.* TO 'carette_user'@'localhost';
   REVOKE ALL PRIVILEGES ON *.* FROM 'carette_user'@'localhost';
   ```

3. **Sauvegardes régulières**
   ```bash
   # Sauvegarde quotidienne
   mysqldump -u root -p carette_db > backup_$(date +%Y%m%d).sql
   ```

### Rate Limiting

1. **Redis en production**
   - Plus fiable que le stockage mémoire
   - Partage entre workers Gunicorn
   - Configuration dans `.env`: `REDIS_URL=redis://localhost:6379/0`

2. **Ajuster les limites**
   ```python
   # Dans api.py, ajuster selon vos besoins:
   default_limits=["200 per day", "50 per hour"]
   ```

### CORS

1. **Origines spécifiques uniquement**
   ```bash
   # .env - JAMAIS de wildcard '*' avec credentials
   CARETTE_ALLOWED_ORIGINS=https://example.com,https://www.example.com
   ```

2. **Pas de credentials avec wildcard**
   - Ne JAMAIS utiliser `origins: "*"` avec `supports_credentials=True`

### HTTPS

1. **Obligatoire en production**
   ```bash
   # Let's Encrypt (gratuit)
   sudo certbot --nginx -d votre-domaine.com
   ```

2. **Redirection HTTP -> HTTPS**
   ```nginx
   # Nginx
   server {
       listen 80;
       server_name votre-domaine.com;
       return 301 https://$server_name$request_uri;
   }
   ```

---

## 🚀 Déploiement Sécurisé

### Avec Gunicorn (recommandé)

```bash
# Créer un utilisateur dédié
sudo adduser --system --group carette

# Copier les fichiers
sudo cp -r /path/to/carette /opt/carette
sudo chown -R carette:carette /opt/carette

# Créer .env sécurisé
sudo -u carette nano /opt/carette/.env
sudo chmod 600 /opt/carette/.env

# Service systemd
sudo nano /etc/systemd/system/carette.service
```

**`/etc/systemd/system/carette.service`:**

```ini
[Unit]
Description=Carette Carpool API
After=network.target redis.service mysql.service

[Service]
Type=notify
User=carette
Group=carette
WorkingDirectory=/opt/carette
Environment="PATH=/opt/carette/venv/bin"
ExecStart=/opt/carette/venv/bin/gunicorn \
    --workers 4 \
    --bind 127.0.0.1:9000 \
    --timeout 120 \
    --access-logfile /var/log/carette/access.log \
    --error-logfile /var/log/carette/error.log \
    serve:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Démarrer
sudo systemctl daemon-reload
sudo systemctl start carette
sudo systemctl enable carette
sudo systemctl status carette
```

### Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl http2;
    server_name api.votre-domaine.com;

    ssl_certificate /etc/letsencrypt/live/votre-domaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/votre-domaine.com/privkey.pem;

    # Sécurité headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 🛡️ Monitoring & Logging

### Logging Centralisé

```python
# backend/api.py - Configuration logging production
import logging
from logging.handlers import RotatingFileHandler

if not app.debug:
    handler = RotatingFileHandler(
        '/var/log/carette/app.log',
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
```

### Alertes de Sécurité

Surveillez:
- Tentatives de connexion BDD échouées
- Rate limiting dépassé
- Erreurs 500 répétées
- Tentatives d'accès à des fichiers sensibles

---

## 📊 Audit de Sécurité Régulier

```bash
# Vérifier vulnérabilités Python
pip install safety bandit
safety check -r backend/requirements.txt
bandit -r backend/

# Scanner de ports
nmap votre-serveur.com

# Logs suspects
sudo grep "error\|warning\|failed" /var/log/carette/*.log

# Tester HTTPS
curl -I https://votre-domaine.com
```

---

## 🆘 En Cas de Compromission

1. **Isoler immédiatement**
   ```bash
   sudo systemctl stop carette
   sudo ufw deny 9000
   ```

2. **Changer tous les secrets**
   ```bash
   python3 generate_secrets.py > new_secrets.txt
   # Copier dans .env
   ```

3. **Changer mots de passe BDD**
   ```sql
   ALTER USER 'carette_user'@'localhost' IDENTIFIED BY 'nouveau_mdp';
   ALTER USER 'root'@'localhost' IDENTIFIED BY 'nouveau_mdp_root';
   FLUSH PRIVILEGES;
   ```

4. **Analyser les logs**
   ```bash
   grep -r "suspicious" /var/log/carette/
   ```

5. **Mettre à jour dépendances**
   ```bash
   pip install -U -r requirements.txt
   ```

---

## 📚 Ressources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security](https://flask.palletsprojects.com/en/latest/security/)
- [MySQL Security](https://dev.mysql.com/doc/refman/8.0/en/security.html)
- [Let's Encrypt](https://letsencrypt.org/)

---

**Besoin d'aide?** Consultez `SECURITY_AUDIT.md` pour l'audit complet des vulnérabilités corrigées.
