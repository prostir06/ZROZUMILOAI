#!/bin/bash
# Локальний скрипт: завантажує .env, відновлює БД (за потреби) і створює адміна.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_DIR}/.env"
BACKEND_DIR="${PROJECT_DIR}/backend"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

cd "$BACKEND_DIR"

if [ -d ".venv" ]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
fi

if [ "${FORCE_DB_RESTORE:-0}" = "1" ]; then
  echo "FORCE_DB_RESTORE=1 — перевірка теки backup..."
  python manage.py restore_backup
fi

python manage.py migrate --noinput
python manage.py ensure_admin
