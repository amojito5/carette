#!/bin/bash

# Script de démarrage avec adaptateur API
# Permet d'utiliser le widget existant avec le workflow email/WhatsApp

set -e

echo "🚗 Carette - Démarrage avec Adaptateur"
echo "======================================"
echo ""

# Vérifier .env
if [ ! -f ".env" ]; then
    echo "⚠️  Fichier .env manquant"
    echo ""
    echo "Voulez-vous initialiser la configuration ? (o/N)"
    read -n 1 -r
    echo
    if [[ $REPLY =~ ^[Oo]$ ]]; then
        ./start_v2.sh
        exit 0
    else
        echo "❌ Configuration requise. Lancez : ./start_v2.sh"
        exit 1
    fi
fi

# Charger les variables
export $(cat .env | grep -v '^#' | xargs)

# Activer venv
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Environnement virtuel activé"
else
    echo "⚠️  Pas d'environnement virtuel. Création..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r backend/requirements.txt
fi

# Vérifier que la BDD v2 existe
echo "🔧 Vérification base de données..."
python3 -c "
from backend.sql_v2 import db_cursor
try:
    with db_cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM carpool_offers_v2')
        print('  ✓ Base de données v2 prête')
except:
    print('  ⚠️  Base de données v2 non initialisée')
    print('     Lancement de l\'initialisation...')
    import backend.sql_v2 as sql_v2
    sql_v2.init_simplified_db()
" || {
    echo "  Initialisation BDD..."
    python3 backend/sql_v2.py
}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 DÉMARRAGE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Mode : Adaptateur (Widget existant + Workflow email)"
echo ""
echo "✅ API adaptée : http://localhost:5000"
echo "✅ Widget : demo.html (ou votre page)"
echo ""

# Démarrer l'API adaptée
echo "Démarrage de l'API adaptateur..."
python3 backend/api_adapter.py
