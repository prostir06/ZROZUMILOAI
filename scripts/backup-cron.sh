#!/usr/bin/env bash
# Daily DB backup via Django management command (RPO target: 24h).
# Install (Linux VPS, from repo root):
#   chmod +x scripts/backup-cron.sh
#   crontab -e
#   15 2 * * * cd /opt/zrozumiloai && ./scripts/backup-cron.sh >> /var/log/zrozumiloai-backup.log 2>&1
#
# After success: copy ./backup/*.tar.gz (or newest file) off-box (rsync/S3).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"

echo "[$(date -Iseconds)] backup start"
FILENAME="$("${COMPOSE[@]}" exec -T backend python manage.py create_backup)"
echo "[$(date -Iseconds)] created: ${FILENAME}"

if [ -n "${BACKUP_OFFBOX_CMD:-}" ]; then
  echo "[backup-cron] $(date -Iseconds) Running BACKUP_OFFBOX_CMD..."
  sh -c "${BACKUP_OFFBOX_CMD}"
fi

# Prune local files older than KEEP_DAYS (off-box copies are the source of truth).
if [[ -d ./backup ]]; then
  find ./backup -type f \( -name '*.tar.gz' -o -name '*.sql.gz' -o -name '*.sql' -o -name '*.sqlite3' -o -name '*.db' \) -mtime "+${KEEP_DAYS}" -print -delete || true
fi

echo "[$(date -Iseconds)] backup done"
