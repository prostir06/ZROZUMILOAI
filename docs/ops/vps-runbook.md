# VPS Runbook (Compose + Caddy)

Мінімум хоста: **16 GB RAM**, 4+ vCPU (llama3.2 + panel + Postgres/Redis на одному боксі).  
Design: [docs/superpowers/specs/2026-11-05-vps-prod-readiness-design.md](../superpowers/specs/2026-11-05-vps-prod-readiness-design.md).

## First deploy

1. Скопіюйте `.env.example` → `.env` і задайте:
   - `DJANGO_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`
   - `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `DJANGO_ADMIN_PASSWORD`
   - `CADDY_SITE_ADDRESS=your.domain` (DNS A/AAAA на VPS)
   - `DJANGO_ALLOWED_HOSTS=your.domain,backend`
   - `CORS_ALLOWED_ORIGINS=https://your.domain` (+ LMS origins для віджета)
2. Запуск:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

3. Моделі:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec ollama ollama pull llama3.2
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec ollama ollama pull nomic-embed-text
```

4. Перевірте TLS (Caddy) і логін адміна.

**Remote Ollama (пізніше):** у `.env` задайте `OLLAMA_BASE_URL=http://gpu-host:11434` і за потреби вимкніть локальний сервіс `ollama` (scale 0 / окремий compose без ollama).

## Health

| Check | Як |
|-------|-----|
| App | `curl -fsS https://your.domain/api/health/` → 200 |
| Containers | `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps` |
| Ollama (auth) | `GET /api/ollama/health/` з JWT / API key |
| External uptime | HTTP GET `/api/health/` і `/` кожні 1–5 хв (UptimeRobot тощо) |

Логи: JSON з `request_id` при `DJANGO_LOG_FORMAT=json` (prod default).

**Не** ставте Prometheus/Grafana на цей самий VPS у цій ітерації.

## Backup (RPO 24h)

Створення:

```bash
./scripts/backup-cron.sh
# або:
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python manage.py create_backup
```

Cron (приклад):

```cron
15 2 * * * cd /opt/zrozumiloai && ./scripts/backup-cron.sh >> /var/log/zrozumiloai-backup.log 2>&1
```

Після кожного backup — **скопіюйте** `./backup/` off-box (rsync/object storage). Локальний prune: `BACKUP_KEEP_DAYS` (default 14).

### Restore drill (раз на квартал)

1. Зупиніть write-навантаження / візьміть maintenance window.
2. Покладіть потрібний `.sql` у `./backup/` (найновіший підхопить `find_latest_backup`).
3. Відновлення через entrypoint:

```bash
FORCE_DB_RESTORE=1 docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend
```

Або вручну: `docker compose … exec backend python manage.py restore_backup` (потрібен `FORCE_DB_RESTORE=1` у env контейнера).

4. Перевірте health, логін, один widget chat, один документ у RAG.
5. Зніміть `FORCE_DB_RESTORE` назад на `0`.

## Incidents

| Симптом | Дія |
|---------|-----|
| OOM / хост swap | Знизьте `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MEM_LIMIT`; не робіть model pull / mass reindex |
| Redis down | Chat/сесії можуть деградувати; перевірте пароль і `redis` health |
| Ingest FAILED | Повтор у UI / Celery; перевірте worker + Ollama embed model |
| 429 на chat | Очікувано: DRF `WIDGET_CHAT_RATE` / `USER_CHAT_RATE` (prod ~30/min) |
| TLS fail | DNS, `CADDY_SITE_ADDRESS`, порти 80/443 |

Під тиском спочатку вимкніть: pull великих моделей → масовий reindex → зайвий parallel Ollama.

## Rollback

1. Попередні image tags / `docker compose … up -d` зі старим build.
2. За потреби restore з останнього off-box backup (див. drill).
3. Перевірка health + smoke chat.

## Manual soak (після деплою)

- N=5–10 паралельних widget chat (короткі промпти) — без 5xx / OOM.
- Один upload PDF + ingest → READY.
- `docker stats` — Ollama у межах `mem_limit`.
