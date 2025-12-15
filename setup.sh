#!/bin/bash
# Script de démarrage rapide Carette

set -e

echo "🚗 Carette - Démarrage rapide"
echo "=============================="
echo ""

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé. Veuillez l'installer : https://python.org"
    exit 1
fi

echo "✓ Python détecté : $(python3 --version)"

# Vérifier MySQL
if ! command -v mysql &> /dev/null; then
    echo "⚠️  MySQL n'est pas détecté. Assurez-vous qu'il est installé et en cours d'exécution."
    echo "   Ubuntu/Debian : sudo apt install mysql-server"
    echo "   macOS : brew install mysql"
    read -p "   Continuer quand même ? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "📦 Installation des dépendances Python..."
cd backend
python3 -m pip install -r requirements.txt --quiet

echo ""
echo "🗄️  Initialisation de la base de données..."
python3 sql.py

echo ""
echo "✅ Configuration terminée !"
echo ""
echo "🚀 Pour démarrer l'API :"
echo "   cd backend && python3 api.py"
echo ""
echo "🌐 Pour tester le widget :"
echo "   Ouvrez demo.html dans votre navigateur"
echo "   ou lancez : python3 -m http.server 8000"
echo "   puis visitez http://localhost:8000/demo.html"
echo ""
echo "📚 Documentation complète : docs/INTEGRATION.md"
echo ""
