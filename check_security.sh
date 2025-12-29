#!/bin/bash
# Script de vérification de sécurité pour Carette

echo "🔒 Vérification de la Configuration de Sécurité Carette"
echo "========================================================"
echo ""

ERRORS=0

# Vérifier que .env existe
if [ ! -f .env ]; then
    echo "❌ Fichier .env manquant"
    echo "   → Exécutez: cp .env.example .env"
    echo "   → Puis éditez .env avec vos secrets (utilisez generate_secrets.py)"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Fichier .env trouvé"
    
    # Vérifier les variables critiques
    source .env
    
    if [ -z "$CARETTE_DB_PASSWORD" ]; then
        echo "❌ CARETTE_DB_PASSWORD non défini dans .env"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ CARETTE_DB_PASSWORD défini"
    fi
    
    if [ -z "$CARETTE_DB_ROOT_PASSWORD" ]; then
        echo "❌ CARETTE_DB_ROOT_PASSWORD non défini dans .env"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ CARETTE_DB_ROOT_PASSWORD défini"
    fi
    
    if [ -z "$CARETTE_SECRET_KEY" ]; then
        echo "❌ CARETTE_SECRET_KEY non défini dans .env"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ CARETTE_SECRET_KEY défini"
    fi
    
    if [ -z "$CARETTE_ALLOWED_ORIGINS" ]; then
        echo "⚠️  CARETTE_ALLOWED_ORIGINS non défini (utilisera localhost)"
    else
        echo "✅ CARETTE_ALLOWED_ORIGINS défini: $CARETTE_ALLOWED_ORIGINS"
    fi
    
    if [ "$CARETTE_DEBUG" = "True" ]; then
        echo "⚠️  CARETTE_DEBUG=True (désactiver en production)"
    else
        echo "✅ CARETTE_DEBUG=False"
    fi
fi

echo ""

# Vérifier .gitignore
if grep -q "^\.env$" .gitignore 2>/dev/null; then
    echo "✅ .env dans .gitignore"
else
    echo "❌ .env n'est pas dans .gitignore"
    echo "   → Ajoutez-le: echo '.env' >> .gitignore"
    ERRORS=$((ERRORS + 1))
fi

# Vérifier que .env n'est pas tracké
if git ls-files --error-unmatch .env 2>/dev/null; then
    echo "❌ .env est tracké par Git !"
    echo "   → Exécutez: git rm --cached .env"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ .env non tracké par Git"
fi

echo ""

# Vérifier dépendances Python
if python3 -c "import flask, flask_cors, flask_limiter, pymysql, dotenv, bleach, redis" 2>/dev/null; then
    echo "✅ Toutes les dépendances Python installées"
else
    echo "❌ Dépendances Python manquantes"
    echo "   → Exécutez: pip install -r backend/requirements.txt"
    ERRORS=$((ERRORS + 1))
fi

# Vérifier Redis (optionnel)
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &>/dev/null; then
        echo "✅ Redis installé et en cours d'exécution"
    else
        echo "⚠️  Redis installé mais pas démarré"
        echo "   → Ubuntu: sudo systemctl start redis"
        echo "   → macOS: brew services start redis"
    fi
else
    echo "⚠️  Redis non installé (recommandé pour production)"
    echo "   → Ubuntu: sudo apt install redis-server"
    echo "   → macOS: brew install redis"
fi

echo ""
echo "========================================================"

if [ $ERRORS -eq 0 ]; then
    echo "✅ Configuration sécurisée !"
    echo ""
    echo "Vous pouvez maintenant:"
    echo "  1. Initialiser la BDD: python3 backend/sql.py"
    echo "  2. Lancer le serveur: python3 serve.py"
    exit 0
else
    echo "❌ $ERRORS erreur(s) trouvée(s)"
    echo ""
    echo "Corrigez les erreurs ci-dessus avant de continuer"
    echo "📖 Consultez SECURITY_GUIDE.md pour plus d'aide"
    exit 1
fi
