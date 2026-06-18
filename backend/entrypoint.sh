#!/bin/bash
set -e

if [ "${FORCE_DB_RESTORE:-0}" = "1" ]; then
  echo "FORCE_DB_RESTORE=1 — перевірка теки backup..."
  python manage.py restore_backup
fi

python manage.py migrate --noinput
python manage.py ensure_admin
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 3 \
  --timeout 300
