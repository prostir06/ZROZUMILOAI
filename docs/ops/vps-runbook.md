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

## Health & Monitoring Contract

Система має чіткий дуальний контракт для внутрішнього liveness check та зовнішнього моніторингу:

1. **`/api/health/` (Docker Compose / internal container liveness):**
   - **Контракт:** повертає **HTTP 200**, поки доступна база даних (`database: "ok"`). Якщо БД недоступна, повертає **HTTP 503** (`status: "degraded"`, `database: "error"`).
   - **Мета:** запобігти деструктивним каскадним перезапускам контейнера `backend` під час пікового навантаження на Ollama, завантаження великих моделей або рестарту самого контейнера `ollama`. Поки БД доступна, бекенд залишається живим і повертає контрольовані відповіді (наприклад, `503 ollama_busy` або кешовані дані).

2. **`/api/health/?strict=1` (External alerting / UptimeRobot / BetterUptime):**
   - **Контракт:** повертає **HTTP 200** тільки якщо всі підсистеми у статусі `ok`. Якщо будь-яка підсистема деградувала (зокрема `ollama: "error"` або `database: "error"`), повертає **HTTP 503** (`status: "degraded"`).
   - **Мета:** негайно тригерити сповіщення для чергових інженерів (SLA / Ops alert) про деградацію генерації відповідей чи ембедингів без перезапуску самого контейнера бекенда.
   - **Кешування:** статус Ollama кешується на 10 с (`OLLAMA_HEALTH_CACHE_TTL`), щоб регулярні проби моніторингу не створювали паразитне навантаження на Ollama.

| Check | Як | Очікувана поведінка |
|-------|-----|----------------------|
| App (Docker Compose liveness) | `curl -fsS https://your.domain/api/health/` | HTTP 200 (поки жива БД; стан може бути `degraded`, але без рестарту контейнера). HTTP 503 якщо впала БД. |
| Strict (External uptime monitor) | `curl -fsS "https://your.domain/api/health/?strict=1"` | HTTP 200 якщо всі сервіси `ok`; HTTP 503 як тільки будь-яка підсистема (`ollama`, `database`) деградує. |
| Containers | `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps` | Перегляд стану контейнерів. |
| Ollama (auth) | `GET /api/ollama/health/` з JWT / API key | Діагностика працездатності Ollama через проксі. |
| External uptime | HTTP GET `/api/health/?strict=1` і `/` кожні 1–5 хв | UptimeRobot / BetterUptime (alerting при HTTP != 200). |

Логи: JSON з `request_id` при `DJANGO_LOG_FORMAT=json` (prod default).

**Не** ставте Prometheus/Grafana на цей самий VPS у цій ітерації.

## Backup (RPO 24h)

Створення (повний архів `.tar.gz` з дампом БД, `media/` та `manifest.json`):

```bash
./scripts/backup-cron.sh
# або:
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python manage.py create_backup
```

Cron (приклад):

```cron
15 2 * * * cd /opt/zrozumiloai && ./scripts/backup-cron.sh >> /var/log/zrozumiloai-backup.log 2>&1
```

Після кожного backup — **скопіюйте** `./backup/` off-box (rsync/object storage). Можна автоматизувати через змінну середовища `BACKUP_OFFBOX_CMD` (виконується у `scripts/backup-cron.sh` одразу після `create_backup` і перед локальним ротуванням), наприклад:

```bash
export BACKUP_OFFBOX_CMD="rclone copy ./backup remote:zrozumiloai-backups"
```

Локальний prune: `BACKUP_KEEP_DAYS` (default 14).

### Restore drill (раз на квартал)

1. Зупиніть write-навантаження / візьміть maintenance window.
2. Покладіть найновіший архів `.tar.gz` у `./backup/` (найновіший архів `.tar.gz` підхопить `find_latest_backup`).
3. Встановіть `FORCE_DB_RESTORE=1` і перезапустіть backend для відновлення через entrypoint:

```bash
FORCE_DB_RESTORE=1 docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend
```

Або вручну: `docker compose … exec backend python manage.py restore_backup` (потрібен `FORCE_DB_RESTORE=1` у env контейнера).

4. Перевірте health (`/api/health/?strict=1`), логін, один widget chat, один документ у RAG.
5. Зніміть `FORCE_DB_RESTORE` назад на `0` (revert `FORCE_DB_RESTORE` back to `0`) і перезапустіть backend без прапорця відновлення, щоб запобігти випадковому повторному відновленню при наступних перезапусках:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend
```

## Incidents

| Симптом | Дія |
|---------|-----|
| OOM / хост swap | Знизьте `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MEM_LIMIT`; не робіть model pull / mass reindex |
| Redis down | Chat/сесії можуть деградувати; перевірте пароль і `redis` health |
| Ingest FAILED | Повтор у UI / Celery; перевірте worker + Ollama embed model та параметри батчингу (`RAG_EMBED_BATCH_SIZE`, `RAG_EMBED_BATCH_PAUSE_SECONDS`, `OLLAMA_INGEST_SLOT_WAIT_SECONDS`) |
| 429 на chat (`ollama_busy` або rate limit) | Якщо `"code": "ollama_busy"` (з заголовком `Retry-After`) — слот генерації Ollama зайнятий; налаштуйте `OLLAMA_CHAT_SLOT_WAIT_SECONDS` або зменшіть конкурентний ingest (`RAG_EMBED_BATCH_SIZE`, `RAG_EMBED_BATCH_PAUSE_SECONDS`). Інакше — DRF throttle `WIDGET_CHAT_RATE` / `USER_CHAT_RATE` (prod ~30/min) |
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
