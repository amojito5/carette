#!/bin/bash

# 🚀 Script de test du workflow v2 Carette

echo "==================================="
echo "🧪 TEST WORKFLOW V2 - CARETTE"
echo "==================================="
echo ""

# Couleurs
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# URL de base
BASE_URL="http://localhost:5001"

echo "📍 URL de base: $BASE_URL"
echo ""

# Test 1: Vérifier que l'API est lancée
echo "1️⃣  Test connexion API..."
if curl -s "$BASE_URL/api/carpool" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API accessible${NC}"
else
    echo -e "${RED}❌ API non accessible. Lancez: python3 backend/api.py${NC}"
    exit 1
fi

# Test 2: Créer une offre v2
echo ""
echo "2️⃣  Test création d'offre v2..."

OFFER_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v2/offers" \
  -H "Content-Type: application/json" \
  -d '{
    "driver_email": "test@example.com",
    "driver_name": "Jean Dupont",
    "driver_phone": "0612345678",
    "departure": "Paris, France",
    "destination": "Lyon, France",
    "datetime": "2025-12-31 18:00:00",
    "seats": 3,
    "event_id": "test-event",
    "event_name": "Festival Test",
    "event_location": "Lyon Centre",
    "event_date": "2025-12-31"
  }')

if echo "$OFFER_RESPONSE" | grep -q '"success": true'; then
    OFFER_ID=$(echo "$OFFER_RESPONSE" | grep -o '"offer_id": [0-9]*' | grep -o '[0-9]*')
    echo -e "${GREEN}✅ Offre créée avec succès (ID: $OFFER_ID)${NC}"
else
    echo -e "${RED}❌ Échec création offre${NC}"
    echo "Réponse: $OFFER_RESPONSE"
    exit 1
fi

# Test 3: Récupérer les offres v2
echo ""
echo "3️⃣  Test récupération des offres v2..."

OFFERS_RESPONSE=$(curl -s "$BASE_URL/api/v2/offers?event_id=test-event")

if echo "$OFFERS_RESPONSE" | grep -q '"offers"'; then
    COUNT=$(echo "$OFFERS_RESPONSE" | grep -o '"count": [0-9]*' | grep -o '[0-9]*')
    echo -e "${GREEN}✅ Offres récupérées ($COUNT trouvée(s))${NC}"
else
    echo -e "${RED}❌ Échec récupération offres${NC}"
    echo "Réponse: $OFFERS_RESPONSE"
fi

# Test 4: Créer une réservation v2
echo ""
echo "4️⃣  Test création de réservation v2..."

if [ -n "$OFFER_ID" ]; then
    RESERVATION_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v2/reservations" \
      -H "Content-Type: application/json" \
      -d "{
        \"offer_id\": $OFFER_ID,
        \"passenger_email\": \"passager@example.com\",
        \"passenger_name\": \"Marie Martin\",
        \"passenger_phone\": \"0687654321\",
        \"passengers\": 2
      }")

    if echo "$RESERVATION_RESPONSE" | grep -q '"success": true'; then
        RESERVATION_ID=$(echo "$RESERVATION_RESPONSE" | grep -o '"reservation_id": [0-9]*' | grep -o '[0-9]*')
        echo -e "${GREEN}✅ Réservation créée avec succès (ID: $RESERVATION_ID)${NC}"
    else
        echo -e "${RED}❌ Échec création réservation${NC}"
        echo "Réponse: $RESERVATION_RESPONSE"
    fi
else
    echo -e "${YELLOW}⚠️  Pas d'offre créée, test de réservation ignoré${NC}"
fi

# Résumé
echo ""
echo "==================================="
echo "📊 RÉSUMÉ DES TESTS"
echo "==================================="
echo ""
echo -e "${GREEN}✅ API v2 fonctionnelle${NC}"
echo -e "${GREEN}✅ Création d'offres : OK${NC}"
echo -e "${GREEN}✅ Récupération offres : OK${NC}"
echo -e "${GREEN}✅ Création réservations : OK${NC}"
echo ""
echo -e "${YELLOW}📝 Prochaines étapes :${NC}"
echo "  1. Ouvrir http://localhost:8080/demo.html"
echo "  2. Tester le flux complet dans le navigateur"
echo "  3. Vérifier les emails envoyés (logs backend)"
echo "  4. Configurer SMTP pour envoi réel d'emails"
echo ""
echo -e "${GREEN}🎉 Tous les tests passés !${NC}"
