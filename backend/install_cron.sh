#!/bin/bash
# Script pour installer les cron jobs automatiques

BACKEND_DIR="/home/ubuntu/projects/carette/backend"
PYTHON_BIN="/usr/bin/python3"

echo "📅 Installation des cron jobs Carette..."

# Créer le fichier de crontab temporaire
CRON_FILE="/tmp/carette_cron"

# Récupérer les crons existants (sans les lignes Carette)
crontab -l 2>/dev/null | grep -v "carette/backend/cron_jobs.py" > $CRON_FILE

# Ajouter les nouveaux crons
cat >> $CRON_FILE << EOF

# ========== Carette Covoiturage - Cron Jobs ==========

# Expirer les demandes pending >24h (toutes les heures)
0 * * * * cd $BACKEND_DIR && $PYTHON_BIN cron_jobs.py expire >> /var/log/carette_cron.log 2>&1

# Envoyer rappels J-1 (tous les jours à 10h)
0 10 * * * cd $BACKEND_DIR && $PYTHON_BIN cron_jobs.py reminders >> /var/log/carette_cron.log 2>&1

# ========== Carette RSE - Cron Jobs ==========

# Envoyer récap RSE hebdomadaire (tous les vendredis à 16h)
0 16 * * 5 cd $BACKEND_DIR && $PYTHON_BIN cron_jobs.py send-weekly-rse >> /var/log/carette_cron.log 2>&1

# Auto-confirmer les semaines RSE non confirmées >7 jours (tous les jours à 2h)
0 2 * * * cd $BACKEND_DIR && $PYTHON_BIN cron_jobs.py auto-confirm-rse >> /var/log/carette_cron.log 2>&1

# ======================================================

EOF

# Installer le nouveau crontab
crontab $CRON_FILE
rm $CRON_FILE

echo "✅ Cron jobs installés:"
echo ""
crontab -l | grep -A 15 "Carette"
echo ""
echo "📝 Logs disponibles dans: /var/log/carette_cron.log"
echo ""
echo "Pour tester manuellement:"
echo "  cd $BACKEND_DIR"
echo "  python3 cron_jobs.py expire           # Expirer demandes >24h"
echo "  python3 cron_jobs.py reminders        # Envoyer rappels J-1"
echo "  python3 cron_jobs.py send-weekly-rse  # Envoyer récaps RSE hebdo"
echo "  python3 cron_jobs.py auto-confirm-rse # Auto-confirmer semaines RSE >7j"
echo "  python3 cron_jobs.py all              # Exécuter tous les jobs"
