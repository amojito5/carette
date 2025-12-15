# Carette 🚗

**Widget de covoiturage autonome et intégrable partout**

Carette est un système complet de covoiturage conçu pour être facilement intégré sur n'importe quel site web (événements, concerts, matchs sportifs, festivals, etc.).

## 🎯 Fonctionnalités

### Pour les utilisateurs
- **Interface tout-en-un** : Rechercher ou proposer un covoiturage depuis un seul widget
- **Calcul intelligent** : Itinéraires optimisés avec OSRM, alternatives de routes
- **Zones de détour** : Affichage visuel des zones accessibles pour les passagers
- **Aller-retour** : Gestion complète des trajets bidirectionnels
- **Timeline interactive** : Visualisation des horaires de passage à chaque point
- **Carte interactive** : MapLibre GL JS pour explorer les trajets

### Pour les intégrateurs
- **Embed simple** : Un seul `<script>` tag pour intégrer
- **Personnalisable** : Couleurs, thème clair/sombre, police
- **Métadonnées événement** : Pré-remplissage automatique via attributs HTML
- **API REST complète** : Backend Flask documenté
- **Base de données légère** : MySQL avec migrations automatiques

## 🚀 Installation rapide

### 1. Backend (Python/Flask)

```bash
cd backend

# Installer les dépendances
pip install -r requirements.txt

# Configurer la base de données (optionnel, variables d'environnement)
export CARETTE_DB_NAME=carette_db
export CARETTE_DB_USER=carette_user
export CARETTE_DB_PASSWORD=VotreMotDePasse

# Initialiser la base
python sql.py

# Lancer le serveur
python api.py
# → API disponible sur http://localhost:5001
```

### 2. Frontend (Web Component)

```html
<!-- Intégration minimale -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Covoiturage - Mon Événement</title>
</head>
<body>
    <!-- Le widget -->
    <carpool-offer-widget 
        color-outbound="#c47cff" 
        color-return="#ff9c3f"
        theme="light"
        event-id="concert-2025"
        event-name="Festival Rock 2025"
        event-location="Stade Municipal"
        event-date="2025-07-15"
        event-time="20:00"
    ></carpool-offer-widget>

    <!-- Script du widget -->
    <script type="module" src="/frontend/carpool-widget.js"></script>
</body>
</html>
```

## 📋 Prérequis

- **Backend** : Python 3.8+, MySQL 5.7+
- **Frontend** : Navigateur moderne (ES6 modules, Custom Elements)
- **Externe** : OSRM public (ou instance self-hosted pour production)

## 🔧 Configuration

### Variables d'environnement (backend)

```bash
# Base de données
CARETTE_DB_NAME=carette_db
CARETTE_DB_HOST=localhost
CARETTE_DB_USER=carette_user
CARETTE_DB_PASSWORD=VotreMotDePasse
CARETTE_DB_ROOT_PASSWORD=RootPassword

# API (optionnel)
CARETTE_API_PORT=5001
CARETTE_DEBUG=False
```

### Attributs HTML du widget

| Attribut | Description | Défaut |
|----------|-------------|--------|
| `color-outbound` | Couleur du trajet aller | `#7c3aed` |
| `color-return` | Couleur du trajet retour | `#f97316` |
| `detour-color` | Couleur des détours | `#fbbf24` |
| `theme` | Thème UI (`light` ou `dark`) | `light` |
| `font-family` | Police CSS | `Sofia Sans, system` |
| `event-id` | ID unique de l'événement | `""` |
| `event-name` | Nom affiché | `""` |
| `event-location` | Lieu/stade | `""` |
| `event-date` | Date ISO (`YYYY-MM-DD`) | `""` |
| `event-time` | Heure (`HH:MM`) | `""` |
| `page-url` | URL de référence | `window.location` |

## 📡 API Endpoints

### Offres

- `POST /api/carpool` - Créer une offre
- `GET /api/carpool` - Liste des offres (filtres : `event_id`, `user_id`, etc.)
- `GET /api/carpool/<id>` - Détails d'une offre avec réservations
- `DELETE /api/carpool/<id>` - Supprimer (par le créateur)

### Réservations

- `POST /api/carpool/reserve` - Réserver une place
- `GET /api/carpool/reservations?user_id=X` - Mes réservations
- `DELETE /api/carpool/reservations/<id>` - Annuler

### Utilitaires

- `POST /api/carpool/calculate-route` - Calcul d'itinéraire OSRM
- `GET /api/carpool/search` - Recherche spatiale d'offres compatibles

Voir [API.md](docs/API.md) pour la documentation complète.

## 🏗️ Architecture

```
carette/
├── frontend/
│   └── carpool-widget.js       # Web Component autonome (13k lignes)
├── backend/
│   ├── api.py                  # Flask API (endpoints carpool)
│   ├── sql.py                  # Gestion MySQL simplifiée
│   ├── route_buffer.py         # Zones géographiques (Shapely)
│   ├── temporal_buffer.py      # Zones temporelles (OSRM)
│   ├── init_carpool_tables.py  # Migrations auto
│   └── requirements.txt
├── static/                     # Assets statiques (avatars, etc.)
├── docs/                       # Documentation détaillée
└── README.md
```

## 💰 Potentiel Business

### Modèle B2B (recommandé)
- **Licence marque blanche** : Intégration pour organisateurs d'événements
- **Dashboard analytics** : Taux de remplissage, CO₂ évité, KPIs
- **Tarification** : Par événement ou forfait annuel (clubs, festivals)
- **Upsell** : Notifications push, matching IA, gamification, partenariats mobilité

### Partenariats
- **Billetteries** : Injection "post-achat" (offre de covoit après achat de ticket)
- **Stades/salles** : Réduction parking pour covoitureurs
- **Assureurs/carburantiers** : Affiliation, sponsoring

## ⚠️ Points d'attention (Production)

### Performance
- [ ] **Cache OSRM** : Redis pour éviter requêtes répétées (clé par waypoints)
- [ ] **OSRM self-hosted** : Instance dédiée pour haute disponibilité
- [ ] **Rate limiting** : Protection anti-abus sur endpoints publics

### Sécurité
- [ ] **Secrets** : Déplacer tokens/mots de passe en variables d'environnement
- [ ] **HTTPS** : Obligatoire en production
- [ ] **CORS** : Restreindre origins autorisées
- [ ] **Auth** : JWT ou OAuth pour API sensibles

### Scalabilité
- [ ] **Refactor frontend** : Découper widget monolithique en modules
- [ ] **Tests** : Unitaires (Jest) et E2E (Playwright)
- [ ] **Monitoring** : Sentry pour erreurs, métriques latence OSRM/DB
- [ ] **Migrations DB** : Alembic ou scripts versionnés (éviter import-time)

### RGPD
- [ ] **Consentement** : Géolocalisation, cookies
- [ ] **DPA** : Accord de traitement des données
- [ ] **Purge** : Suppression auto des vieux trajets (90j)

## 📦 Roadmap

- [ ] Build CDN (Rollup/esbuild) pour embed sans dépendances
- [ ] Mode "no-map" pour performances sur mobile
- [ ] Deep links / QR codes pour billets physiques
- [ ] Email/SMS notifications (Twilio/SendGrid)
- [ ] Admin panel pour organisateurs
- [ ] Matching intelligent (ML sur compatibilités)

## 📄 Licence

Propriétaire - Tous droits réservés (2025)

Pour toute question commerciale : contact@carette.app

---

**Made with ❤️ for seamless event carpooling**
