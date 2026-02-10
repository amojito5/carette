#!/usr/bin/env bash
# Reset specific Carette tables quickly for testing
# Usage:
#   ./reset_tables.sh [DB_NAME]
# Defaults:
#   DB_NAME = carette_db
# Auth options:
#   - If sudo works for MySQL, uses it automatically
#   - Else, set MYSQL_USER env and it will prompt for password
#   - Else, it tries direct `mysql` and falls back to prompting for user

set -euo pipefail

DB_NAME="${1:-carette_db}"
TABLES=(
  confirmation_tokens
  carpool_reservations_recurrent
  carpool_offers_recurrent
  company_sites
  companies
)

# Build SQL
SQL="SET FOREIGN_KEY_CHECKS=0;"
for t in "${TABLES[@]}"; do
  SQL+=" DROP TABLE IF EXISTS \`${t}\`;"
done
SQL+=" SET FOREIGN_KEY_CHECKS=1;"

echo "⚠️  This will drop tables in database: ${DB_NAME}"
echo "   Tables: ${TABLES[*]}"
read -r -p "Proceed? [y/N] " CONFIRM
CONFIRM=${CONFIRM:-N}
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo "❌ Aborted"
  exit 0
fi

run_with_sudo() {
  sudo mysql "$DB_NAME" -e "$SQL"
}

run_with_user() {
  local user="$1"
  echo "Enter password for MySQL user '$user' (prompted by mysql):"
  mysql -u "$user" -p "$DB_NAME" -e "$SQL"
}

run_direct() {
  mysql "$DB_NAME" -e "$SQL"
}

# Try sudo first
if command -v sudo >/dev/null 2>&1; then
  if sudo -n true >/dev/null 2>&1; then
    if sudo mysql "$DB_NAME" -e "SELECT 1;" >/dev/null 2>&1; then
      echo "⏳ Using sudo mysql..."
      run_with_sudo
      echo "✅ Done via sudo"
      exit 0
    fi
  fi
fi

# If MYSQL_USER is set, use it
if [[ -n "${MYSQL_USER:-}" ]]; then
  echo "⏳ Using mysql as user '${MYSQL_USER}'..."
  run_with_user "$MYSQL_USER"
  echo "✅ Done via mysql (-u ${MYSQL_USER})"
  exit 0
fi

# Try direct mysql (auth_socket or default login)
if mysql "$DB_NAME" -e "SELECT 1;" >/dev/null 2>&1; then
  echo "⏳ Using direct mysql..."
  run_direct
  echo "✅ Done via direct mysql"
  exit 0
fi

# Prompt for user if all else fails
read -r -p "MySQL user: " MYSQL_USER
if [[ -z "$MYSQL_USER" ]]; then
  echo "❌ No user provided"
  exit 1
fi
run_with_user "$MYSQL_USER"
echo "✅ Done via mysql (-u ${MYSQL_USER})"
