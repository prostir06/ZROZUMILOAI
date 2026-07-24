#!/bin/bash
set -e

ROLE="${APP_ROLE:-web}"

# Спільна ініціалізація БД лише для web; worker пропускає collectstatic/ensure_admin.
if [ "$ROLE" = "web" ]; then
  if [ "${FORCE_DB_RESTORE:-0}" = "1" ]; then
    echo "FORCE_DB_RESTORE=1 — перевірка теки backup..."
    python manage.py restore_backup
  fi
  python manage.py migrate --noinput
  python manage.py ensure_admin
  python manage.py collectstatic --noinput
elif [ "$ROLE" = "worker" ]; then
  # Легкий migrate (ідемпотентний), без collectstatic/admin — уникаємо гонки з web.
  python manage.py migrate --noinput
else
  echo "Unknown APP_ROLE=$ROLE (expected web|worker)" >&2
  exit 1
fi

# Якщо передано команду (напр. celery worker) — виконуємо її.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

if [ "$ROLE" != "web" ]; then
  echo "APP_ROLE=$ROLE потребує command (напр. celery ...)" >&2
  exit 1
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
