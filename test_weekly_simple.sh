#!/bin/bash
# Script wrapper pour charger .env avant d'exécuter le test Python

# Charger les variables d'environnement
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Exécuter le script Python
python3 test_send_weekly_recap.py "$@"
