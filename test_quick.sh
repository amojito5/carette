#!/bin/bash

# Quick Test Script - Carette v2
# Lance tout automatiquement pour tester

echo "🚗 Carette v2 - Test Rapide"
echo "============================"
echo ""

# Vérifier si .env existe
if [ ! -f ".env" ]; then
    echo "❌ Fichier .env manquant"
    echo ""
    echo "Lancez d'abord : ./start_v2.sh"
    exit 1
fi

# Charger les variables
export $(cat .env | grep -v '^#' | xargs)

# Activer venv si existe
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Lancer l'API en arrière-plan
echo "🚀 Démarrage de l'API..."
python3 backend/api_v2.py > logs/api.log 2>&1 &
API_PID=$!
echo "   API démarrée (PID: $API_PID)"

# Attendre que l'API soit prête
echo "⏳ Attente du démarrage..."
sleep 3

# Vérifier la santé de l'API
HEALTH=$(curl -s http://localhost:5000/api/v2/health 2>/dev/null)
if [[ $HEALTH == *"healthy"* ]]; then
    echo "✅ API opérationnelle !"
else
    echo "⚠️  API ne répond pas (vérifiez logs/api.log)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 TEST EN COURS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1️⃣  Ouvrez : frontend/widget-v2.html"
echo ""
echo "2️⃣  Testez le workflow :"
echo "   • Publier un trajet"
echo "   • Rechercher"
echo "   • Réserver (popup paiement 1€)"
echo ""
echo "3️⃣  Logs API : tail -f logs/api.log"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Pour arrêter l'API : kill $API_PID"
echo ""

# Garder le script actif
echo "Appuyez sur Ctrl+C pour arrêter tout..."
trap "echo ''; echo '🛑 Arrêt de l'API...'; kill $API_PID 2>/dev/null; echo '✅ Arrêté'; exit 0" INT

wait $API_PID
