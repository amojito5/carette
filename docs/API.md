# Carette API Documentation

Base URL: `http://localhost:5001/api`

## 🔐 Authentication

Actuellement : pas d'authentification (ajoutez JWT/OAuth en production)
Les endpoints utilisent `user_id` passé dans le body/query pour identifier l'utilisateur.

---

## 📍 Endpoints

### **Offres de covoiturage**

#### `POST /carpool`
Créer une nouvelle offre de covoiturage.

**Body:**
```json
{
  "user_id": "user123",
  "departure": "Paris, France",
  "destination": "Stade Bollaert, Lens",
  "datetime": "2025-07-15T18:00:00",
  "seats": 4,
  "seats_outbound": 3,
  "seats_return": 2,
  "comment": "Départ direct après le boulot",
  "accept_passengers_on_route": true,
  "max_detour_km": 5,
  "max_detour_time": 25,
  "route_outbound": {
    "geometry": { "type": "LineString", "coordinates": [[...]] },
    "distance": 180000,
    "duration": 7200
  },
  "route_return": { ... },
  "return_datetime": "2025-07-15T23:30:00",
  "event_id": "lens-psg-2025",
  "event_name": "Lens vs PSG",
  "event_location": "Stade Bollaert-Delelis",
  "event_date": "2025-07-15",
  "event_time": "20:00",
  "page_url": "https://example.com/match"
}
```

**Response:**
```json
{
  "success": true,
  "offer_id": 42
}
```

---

#### `GET /carpool`
Lister les offres avec filtres optionnels.

**Query params:**
- `event_id` (string) : Filtrer par événement
- `user_id` (string) : Offres d'un utilisateur
- `departure` (string) : Ville de départ
- `destination` (string) : Ville d'arrivée

**Response:**
```json
{
  "offers": [
    {
      "id": 42,
      "user_id": "user123",
      "departure": "Paris, France",
      "destination": "Lens",
      "datetime": "2025-07-15T18:00:00",
      "seats": 4,
      "seats_outbound": 3,
      "seats_return": 2,
      "route_outbound": { ... },
      "detour_zone_outbound": { "type": "Polygon", "coordinates": [...] },
      "created_at": "2025-06-01T10:30:00",
      ...
    }
  ]
}
```

---

#### `GET /carpool/<id>`
Détails d'une offre avec ses réservations.

**Response:**
```json
{
  "id": 42,
  "user_id": "user123",
  "departure": "Paris",
  "destination": "Lens",
  "datetime": "2025-07-15T18:00:00",
  "reservations": [
    {
      "id": 10,
      "passenger_user_id": "alice456",
      "passengers": 2,
      "trip_type": "outbound",
      "status": "confirmed",
      "meeting_point_coords": [2.3522, 48.8566],
      "meeting_point_address": "Place de la République, Paris",
      "created_at": "2025-06-05T14:20:00"
    }
  ],
  ...
}
```

---

#### `DELETE /carpool/<id>`
Supprimer une offre (seulement par son créateur).

**Body:**
```json
{
  "user_id": "user123"
}
```

**Response:**
```json
{
  "success": true
}
```

---

### **Réservations**

#### `POST /carpool/reserve`
Réserver une place sur une offre.

**Body:**
```json
{
  "offer_id": 42,
  "passenger_user_id": "alice456",
  "passengers": 2,
  "trip_type": "outbound",
  "meeting_point_coords": [2.3522, 48.8566],
  "meeting_point_address": "Place de la République, Paris",
  "detour_route": { "geometry": {...}, "distance": 2500, "duration": 420 }
}
```

**Response:**
```json
{
  "success": true,
  "reservation_id": 10
}
```

**Erreurs:**
- `409 Conflict` : Réservation déjà existante pour ce trajet (contrainte UNIQUE)

---

#### `GET /carpool/reservations`
Lister les réservations d'un utilisateur.

**Query params:**
- `user_id` (string, requis)

**Response:**
```json
{
  "reservations": [
    {
      "id": 10,
      "offer_id": 42,
      "passenger_user_id": "alice456",
      "passengers": 2,
      "trip_type": "outbound",
      "status": "pending",
      "departure": "Paris",
      "destination": "Lens",
      "datetime": "2025-07-15T18:00:00",
      "driver_user_id": "user123",
      ...
    }
  ]
}
```

---

### **Utilitaires**

#### `POST /carpool/calculate-route`
Calculer un itinéraire via OSRM avec alternatives.

**Body:**
```json
{
  "waypoints": [
    [2.3522, 48.8566],
    [2.8322, 50.4292]
  ],
  "alternatives": true
}
```

**Response:**
```json
{
  "route": {
    "geometry": { "type": "LineString", "coordinates": [...] },
    "distance": 180000,
    "duration": 7200,
    "realistic_duration": 7920
  },
  "alternatives": [
    { "geometry": {...}, "distance": 185000, "duration": 7500, ... }
  ]
}
```

---

#### `GET /carpool/search`
Recherche spatiale d'offres compatibles avec un trajet passager.

**Query params:**
- `start_lon`, `start_lat` (float, requis) : Point de départ
- `end_lon`, `end_lat` (float, requis) : Point d'arrivée
- `date` (ISO datetime) : Date du trajet
- `trip_type` (string) : `outbound` ou `return`

**Response:**
```json
{
  "offers": [
    {
      "id": 42,
      "departure": "Paris",
      "destination": "Lens",
      "datetime": "2025-07-15T18:00:00",
      "seats_outbound": 3,
      ...
    }
  ]
}
```

---

## 🧪 Exemples cURL

### Créer une offre
```bash
curl -X POST http://localhost:5001/api/carpool \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo123",
    "departure": "Paris",
    "destination": "Lens",
    "datetime": "2025-07-15T18:00:00",
    "seats": 4,
    "event_id": "match-lens-2025"
  }'
```

### Lister les offres d'un événement
```bash
curl "http://localhost:5001/api/carpool?event_id=match-lens-2025"
```

### Réserver une place
```bash
curl -X POST http://localhost:5001/api/carpool/reserve \
  -H "Content-Type: application/json" \
  -d '{
    "offer_id": 1,
    "passenger_user_id": "alice",
    "passengers": 2,
    "trip_type": "outbound"
  }'
```

---

## 📊 Codes de statut

- `200 OK` : Succès
- `201 Created` : Ressource créée
- `400 Bad Request` : Paramètres manquants/invalides
- `403 Forbidden` : Action non autorisée
- `404 Not Found` : Ressource inexistante
- `409 Conflict` : Contrainte d'unicité violée
- `500 Internal Server Error` : Erreur serveur

---

## 🔒 Sécurité (TODO Production)

- [ ] Authentification JWT/OAuth
- [ ] Rate limiting (par IP/user)
- [ ] HTTPS obligatoire
- [ ] Validation stricte des inputs
- [ ] CORS restreint aux domaines autorisés
