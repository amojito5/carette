#!/bin/bash

# ============================================
# CARETTE v2 - Script de Démarrage Rapide
# ============================================

set -e

echo "🚗 Carette v2 - Initialisation"
echo "================================"

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé"
    exit 1
fi

echo "✅ Python 3 détecté"

# Vérifier MySQL
if ! command -v mysql &> /dev/null; then
    echo "⚠️  MySQL n'est pas installé ou pas dans le PATH"
    echo "   Installation requise : sudo apt install mysql-server"
    exit 1
fi

echo "✅ MySQL détecté"

# Créer l'environnement virtuel si nécessaire
if [ ! -d "venv" ]; then
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv venv
fi

# Activer l'environnement virtuel
source venv/bin/activate

# Installer les dépendances
echo "📦 Installation des dépendances..."
pip install -q -r backend/requirements.txt

# Vérifier .env
if [ ! -f ".env" ]; then
    echo "⚠️  Fichier .env manquant"
    echo ""
    echo "INSTRUCTIONS :"
    echo "1. Copiez .env.example.v2 vers .env"
    echo "2. Générez des secrets : python3 backend/generate_secrets.py"
    echo "3. Éditez .env et configurez vos paramètres"
    echo ""
    read -p "Voulez-vous créer .env maintenant ? (o/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Oo]$ ]]; then
        cp .env.example.v2 .env
        echo "✅ .env créé - Générer les secrets..."
        python3 backend/generate_secrets.py
        echo ""
        echo "⚠️  IMPORTANT : Éditez .env et configurez vos paramètres SMTP avant de continuer"
        echo "   Tapez : nano .env"
        exit 0
    else
        exit 1
    fi
fi

echo "✅ Fichier .env détecté"

# Charger les variables d'environnement
export $(cat .env | grep -v '^#' | xargs)

# Initialiser la base de données
echo "🔧 Initialisation de la base de données..."
python3 backend/sql_v2.py

echo ""
echo "✅ TOUT EST PRÊT !"
echo ""
echo "Pour démarrer le serveur :"
echo "  python3 backend/api_v2.py"
echo ""
echo "Pour tester le widget :"
echo "  Ouvrez frontend/widget-v2.html dans votre navigateur"
echo ""
echo "📧 N'oubliez pas de configurer vos paramètres SMTP dans .env"
echo ""
