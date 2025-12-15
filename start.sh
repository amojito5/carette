#!/bin/bash
# Script de démarrage du serveur Carette (production)

echo "🚗 Démarrage du serveur Carette..."

# Vérifier que les dépendances sont installées
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installation des dépendances..."
    cd /home/ubuntu/projects/carette/backend
    pip install -r requirements.txt
fi

# Initialiser la DB si nécessaire
cd /home/ubuntu/projects/carette
if ! python3 -c "import backend.sql as sql; sql.db_cursor()" 2>/dev/null; then
    echo "🗄️ Initialisation de la base de données..."
    python3 backend/sql.py
fi

# Lancer le serveur avec Gunicorn
echo "🚀 Lancement sur http://0.0.0.0:9000"
echo "   Widget: http://Votre_IP:9000/frontend/carpool-widget.js"
echo "   Démo:   http://Votre_IP:9000/demo.html"
echo "   API:    http://Votre_IP:9000/api/carpool"
echo ""

cd /home/ubuntu/projects/carette
gunicorn -w 2 -b 0.0.0.0:9000 serve:app --access-logfile - --error-logfile -
