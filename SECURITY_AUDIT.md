# 🔒 Audit de Sécurité - Carette

**Date**: 15 décembre 2025  
**Projet**: Carette - Widget de covoiturage  
**Auditeur**: Analyse de sécurité complète

---

## 📋 Résumé Exécutif

### Niveau de Risque Global: **🔴 CRITIQUE**

Le projet présente plusieurs **vulnérabilités critiques** qui doivent être corrigées immédiatement avant tout déploiement en production. Les principales préoccupations concernent :
- Mots de passe en clair dans le code source
- Injections SQL potentielles
- Exposition de clés API publiques
- Configuration CORS permissive
- Absence de validation complète des entrées utilisateur

---

## 🚨 Vulnérabilités Critiques

### 1. **Mots de passe hardcodés** (CRITIQUE)

**Fichier**: `backend/sql.py` (lignes 13-14)

```python
DB_PASSWORD = os.getenv('CARETTE_DB_PASSWORD', 'Carette2025!')
DB_ROOT_PASSWORD = os.getenv('CARETTE_DB_ROOT_PASSWORD', 'Root#2025')
```

**Risque**: 
- Mots de passe faibles exposés dans le code source
- Si le dépôt est public ou accessible, accès direct à la base de données
- Les mots de passe par défaut sont prévisibles

**Recommandations**:
```python
# ✅ CORRECTION
DB_PASSWORD = os.getenv('CARETTE_DB_PASSWORD')
DB_ROOT_PASSWORD = os.getenv('CARETTE_DB_ROOT_PASSWORD')

if not DB_PASSWORD or not DB_ROOT_PASSWORD:
    raise ValueError("Variables d'environnement DB_PASSWORD et DB_ROOT_PASSWORD requises")
```

**Actions**:
- ❌ Ne JAMAIS commiter de mots de passe
- ✅ Utiliser uniquement des variables d'environnement
- ✅ Ajouter `.env` dans `.gitignore`
- ✅ Créer un `.env.example` avec des valeurs vides
- ✅ Utiliser un gestionnaire de secrets (AWS Secrets Manager, HashiCorp Vault, etc.)

---

### 2. **SECRET_KEY faible** (CRITIQUE)

**Fichier**: `backend/api.py` (ligne 33)

```python
app.config['SECRET_KEY'] = os.getenv('CARETTE_SECRET_KEY', 'dev-secret-change-me')
```

**Risque**:
- La clé secrète par défaut est prévisible
- Permet de forger des sessions/tokens
- Compromission totale de l'authentification si utilisée

**Recommandations**:
```python
# ✅ CORRECTION
SECRET_KEY = os.getenv('CARETTE_SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("CARETTE_SECRET_KEY doit être définie en production")
app.config['SECRET_KEY'] = SECRET_KEY

# Génération d'une clé forte (à faire une fois):
# python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

### 3. **Injections SQL potentielles** (CRITIQUE)

**Fichier**: `backend/api.py` (ligne 200)

```python
cur.execute(
    f"INSERT INTO carpool_offers ({columns}) VALUES ({placeholders})",
    list(offer_data.values())
)
```

**Risque**:
- Construction dynamique de requêtes SQL
- Les noms de colonnes ne sont pas échappés
- Potentiel d'injection SQL si les clés du dictionnaire sont contrôlées par l'utilisateur

**Recommandations**:
```python
# ✅ CORRECTION - Whitelist des colonnes autorisées
ALLOWED_COLUMNS = {
    'user_id', 'departure', 'destination', 'datetime', 'seats',
    'comment', 'details', 'accept_passengers_on_route', 
    # ... liste complète
}

# Filtrer uniquement les colonnes autorisées
safe_data = {k: v for k, v in offer_data.items() if k in ALLOWED_COLUMNS}
columns = ', '.join(safe_data.keys())
placeholders = ', '.join(['%s'] * len(safe_data))

cur.execute(
    f"INSERT INTO carpool_offers ({columns}) VALUES ({placeholders})",
    list(safe_data.values())
)
```

---

### 4. **Clés API exposées** (ÉLEVÉ)

**Fichier**: `frontend/carpool-widget.js` (ligne 14)

```javascript
this.ORS_API_KEY = '5b3ce3597851110001cf6248a0e1e0f65f684a2fa52e0a6e5b4f3e88';
```

**Risque**:
- Clé API OpenRouteService exposée côté client
- Visible par tous les utilisateurs (code source du navigateur)
- Peut être extraite et utilisée de manière abusive
- Quota de l'API peut être épuisé par des acteurs malveillants

**Recommandations**:
```javascript
// ✅ CORRECTION - Proxy via le backend
// Frontend: appeler votre API
const route = await fetch('/api/routing/calculate', {
    method: 'POST',
    body: JSON.stringify({ waypoints })
});

// Backend: proxy vers OpenRouteService
@app.route('/api/routing/calculate', methods=['POST'])
@limiter.limit("30 per minute")
def proxy_routing():
    data = request.json
    ors_key = os.getenv('ORS_API_KEY')  # Stockée côté serveur
    # Appel à l'API avec la clé serveur
    ...
```

---

### 5. **CORS permissif** (MOYEN)

**Fichier**: `backend/api.py` (lignes 36-37)

```python
allowed_origins = os.getenv('CARETTE_ALLOWED_ORIGINS', 'https://lemur-lensois.fr').split(',')
CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)
```

**Risque**:
- Configuration par défaut avec un seul domaine
- Si mal configuré en production (wildcard `*`), exposition CSRF

**Recommandations**:
```python
# ✅ CORRECTION - Configuration stricte
allowed_origins = os.getenv('CARETTE_ALLOWED_ORIGINS', '').split(',')
if not allowed_origins or allowed_origins == ['']:
    raise ValueError("CARETTE_ALLOWED_ORIGINS doit être configuré")

# Jamais de wildcard '*' avec credentials=True
CORS(app, 
     resources={r"/api/*": {
         "origins": allowed_origins,
         "methods": ["GET", "POST", "DELETE"],
         "allow_headers": ["Content-Type"]
     }}, 
     supports_credentials=True)
```

---

## ⚠️ Vulnérabilités Moyennes

### 6. **Rate Limiting en mémoire** (MOYEN)

**Fichier**: `backend/api.py` (ligne 40)

```python
limiter = Limiter(app=app, key_func=get_remote_address, 
                  default_limits=["200 per day", "50 per hour"], 
                  storage_uri="memory://")
```

**Risque**:
- Le stockage en mémoire ne persiste pas entre les redémarrages
- Ne fonctionne pas avec plusieurs workers (Gunicorn, etc.)
- Les limites peuvent être contournées

**Recommandations**:
```python
# ✅ CORRECTION - Utiliser Redis
# pip install redis
storage_uri = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
limiter = Limiter(
    app=app, 
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=storage_uri
)
```

---

### 7. **Validation d'entrée incomplète** (MOYEN)

**Fichier**: `backend/api.py` (diverses lignes)

**Problèmes identifiés**:
- Validation basique de la longueur des champs (ligne 176)
- Pas de validation du format des coordonnées GPS
- Pas de sanitisation des champs texte (HTML/JavaScript)
- Pas de validation des dates (format, plage)

**Recommandations**:
```python
# ✅ CORRECTION - Validation stricte
from datetime import datetime
import re
import bleach

def validate_coordinates(lon, lat):
    try:
        lon_f = float(lon)
        lat_f = float(lat)
        if not (-180 <= lon_f <= 180 and -90 <= lat_f <= 90):
            raise ValueError("Coordonnées hors limites")
        return lon_f, lat_f
    except (ValueError, TypeError):
        raise ValueError("Coordonnées invalides")

def sanitize_text(text, max_length=1000):
    if not text:
        return ""
    # Enlever HTML/JavaScript dangereux
    clean = bleach.clean(str(text), tags=[], strip=True)
    return clean[:max_length]

def validate_datetime(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str)
        # Vérifier que la date n'est pas trop ancienne/future
        now = datetime.now()
        if dt < now - timedelta(days=1) or dt > now + timedelta(days=365):
            raise ValueError("Date hors de la plage autorisée")
        return dt
    except (ValueError, TypeError):
        raise ValueError("Format de date invalide")
```

---

### 8. **Gestion des erreurs exposée** (FAIBLE-MOYEN)

**Fichier**: `backend/api.py` (multiples endpoints)

```python
except Exception as e:
    print(f"❌ Error creating offer: {e}")
    return jsonify({"error": str(e)}), 500
```

**Risque**:
- Messages d'erreur détaillés exposés aux utilisateurs
- Peuvent révéler des informations sur la structure de la base de données
- Stack traces en mode debug

**Recommandations**:
```python
# ✅ CORRECTION
import logging
logger = logging.getLogger(__name__)

try:
    # ... code
except ValueError as e:
    # Erreurs attendues - message pour l'utilisateur
    logger.warning(f"Validation error: {e}")
    return jsonify({"error": str(e)}), 400
except Exception as e:
    # Erreurs inattendues - log détaillé, message générique
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return jsonify({"error": "Une erreur est survenue"}), 500
```

---

### 9. **Pas d'authentification sur les endpoints critiques** (CRITIQUE)

**Fichiers**: Tous les endpoints de `backend/api.py`

**Risque**:
- Aucun système d'authentification/autorisation
- N'importe qui peut créer/supprimer des offres
- Le `user_id` est fourni par le client (facilement falsifiable)
- Pas de vérification JWT/OAuth

**Recommandations**:
```python
# ✅ CORRECTION - Ajouter JWT
# pip install flask-jwt-extended

from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity

jwt = JWTManager(app)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')

@app.route('/api/carpool', methods=['POST'])
@jwt_required()  # Requiert un token valide
@limiter.limit("10 per minute")
def create_offer():
    user_id = get_jwt_identity()  # ID depuis le token, pas le body
    # ... reste du code
```

---

### 10. **Exposition de fichiers sensibles** (MOYEN)

**Fichier**: `serve.py`

```python
@backend_app.route('/')
@backend_app.route('/demo.html')
def demo():
    return send_from_directory(BASE_DIR, 'demo.html')
```

**Risque**:
- Le serveur expose tous les fichiers du répertoire via les routes `/static/`, `/docs/`, etc.
- Possible accès à des fichiers non prévus (.env, .git, etc.)

**Recommandations**:
```python
# ✅ CORRECTION
import os
from werkzeug.security import safe_join

@backend_app.route('/static/<path:filename>')
def static_files(filename):
    # Bloquer les fichiers sensibles
    if filename.startswith('.') or '..' in filename:
        abort(404)
    
    safe_path = safe_join(os.path.join(BASE_DIR, 'static'), filename)
    if not safe_path or not os.path.exists(safe_path):
        abort(404)
    
    return send_from_directory(os.path.join(BASE_DIR, 'static'), filename)
```

---

## 🔍 Vulnérabilités Faibles

### 11. **Mode Debug activé** (FAIBLE)

**Fichier**: `backend/api.py`

```python
app.debug = os.getenv('CARETTE_DEBUG', 'False').lower() == 'true'
```

**Risque**:
- Si activé en production, expose les stack traces
- Peut révéler des informations sensibles

**Recommandations**:
- ✅ Toujours désactiver en production
- ✅ Utiliser un logger approprié

---

### 12. **Logs avec informations sensibles** (FAIBLE)

```python
print(f"❌ Error creating offer: {e}")
```

**Recommandations**:
- ✅ Utiliser le module `logging` avec niveaux appropriés
- ✅ Ne jamais logger de mots de passe, tokens, données sensibles

---

## 📊 Tableau Récapitulatif

| # | Vulnérabilité | Niveau | Fichier | Impact |
|---|---------------|--------|---------|--------|
| 1 | Mots de passe hardcodés | 🔴 Critique | `sql.py` | Accès BDD |
| 2 | SECRET_KEY faible | 🔴 Critique | `api.py` | Compromission sessions |
| 3 | Injections SQL | 🔴 Critique | `api.py` | Exfiltration données |
| 4 | Clés API exposées | 🟠 Élevé | `carpool-widget.js` | Abus quota API |
| 5 | CORS permissif | 🟡 Moyen | `api.py` | CSRF potentiel |
| 6 | Rate Limiting mémoire | 🟡 Moyen | `api.py` | DoS |
| 7 | Validation entrée | 🟡 Moyen | `api.py` | XSS, injection |
| 8 | Gestion erreurs | 🟡 Moyen | `api.py` | Info leak |
| 9 | Pas d'auth | 🔴 Critique | `api.py` | Abus complet |
| 10 | Fichiers exposés | 🟡 Moyen | `serve.py` | Info leak |
| 11 | Mode debug | 🟢 Faible | `api.py` | Stack traces |
| 12 | Logs sensibles | 🟢 Faible | `api.py` | Info leak |

---

## ✅ Plan d'Action Recommandé

### Phase 1: Corrections Urgentes (Avant tout déploiement)

1. **Supprimer tous les secrets hardcodés**
   - Créer `.env` et `.env.example`
   - Migrer vers variables d'environnement
   - Ajouter validation des variables requises

2. **Implémenter l'authentification**
   - JWT ou OAuth2
   - Vérification du `user_id` côté serveur
   - Protection des endpoints critiques

3. **Corriger les injections SQL**
   - Whitelist des colonnes
   - Validation stricte des inputs
   - Utiliser ORM (SQLAlchemy) si possible

### Phase 2: Améliorations Sécurité (Court terme)

4. **Sécuriser les clés API**
   - Proxy backend pour OpenRouteService
   - Ne jamais exposer de clés côté client

5. **Améliorer la validation**
   - Utiliser une bibliothèque (Marshmallow, Pydantic)
   - Sanitiser tous les inputs utilisateur
   - Valider formats et plages

6. **Renforcer le Rate Limiting**
   - Migrer vers Redis
   - Limites par utilisateur authentifié

### Phase 3: Bonnes Pratiques (Moyen terme)

7. **Audit de sécurité automatisé**
   - Intégrer Bandit, Safety dans CI/CD
   - Scans de dépendances (Dependabot)

8. **Logging et Monitoring**
   - Centraliser les logs (ELK, Datadog)
   - Alertes sur événements suspects
   - Ne pas logger de données sensibles

9. **Tests de sécurité**
   - Tests d'injection SQL
   - Tests CSRF
   - Fuzzing des endpoints

---

## 🛡️ Bonnes Pratiques Générales

### Dépendances

```bash
# Vérifier les vulnérabilités connues
pip install safety
safety check -r backend/requirements.txt

# Mettre à jour régulièrement
pip list --outdated
```

### Variables d'environnement

Créer `.env.example`:
```bash
# Base de données
CARETTE_DB_NAME=carette_db
CARETTE_DB_HOST=localhost
CARETTE_DB_USER=carette_user
CARETTE_DB_PASSWORD=
CARETTE_DB_ROOT_PASSWORD=

# Sécurité
CARETTE_SECRET_KEY=
JWT_SECRET_KEY=

# API externes
ORS_API_KEY=

# Configuration
CARETTE_DEBUG=False
CARETTE_ALLOWED_ORIGINS=https://example.com
REDIS_URL=redis://localhost:6379/0
```

### Fichiers à ajouter à `.gitignore`

```
.env
*.pyc
__pycache__/
*.log
.venv/
venv/
.DS_Store
```

---

## 📚 Ressources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/2.3.x/security/)
- [Python Security Guide](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)

---

## 📞 Contact

Pour toute question sur cet audit, contactez l'équipe de sécurité.

**Note**: Ce rapport doit être traité comme **CONFIDENTIEL** et ne doit pas être partagé publiquement.
