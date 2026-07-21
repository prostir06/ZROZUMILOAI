#!/bin/bash
set -e

if [ "${FORCE_DB_RESTORE:-0}" = "1" ]; then
  echo "FORCE_DB_RESTORE=1 — перевірка теки backup..."
  python manage.py restore_backup
fi

python manage.py migrate --noinput
python manage.py ensure_admin
python manage.py collectstatic --noinput

# Якщо передано команду (напр. celery worker) — виконуємо її.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

WORKER_CLASS="${GUNICORN_WORKER_CLASS:-gevent}"
WORKERS="${GUNICORN_WORKERS:-4}"
TIMEOUT="${GUNICORN_TIMEOUT:-300}"

if [ "$WORKER_CLASS" = "gevent" ]; then
  exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --worker-class gevent \
    --workers "$WORKERS" \
    --worker-connections "${GUNICORN_WORKER_CONNECTIONS:-1000}" \
    --timeout "$TIMEOUT"
fi

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "$WORKERS" \
  --timeout "$TIMEOUT"
