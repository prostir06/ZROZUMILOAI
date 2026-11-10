# CI/CD Hardening Design (Варіант А)

**Date:** 2026-11-10  
**Status:** Approved for Spec Review  
**Scope:** `.github/workflows/ci.yml`, `backend/pyproject.toml`, `backend/requirements-dev.txt`, `frontend/package.json`

---

## 1. Мета та контекст

Базовий CI (`.github/workflows/ci.yml`) наразі містить SQLite-тести, мінімальний 3-файловий smoke-тест на PostgreSQL, ESLint + Vitest + build для фронтенду та синтаксичну перевірку `docker compose config`.  

Мета цього етапу — перевести CI на рівень надійного production-ready пайплайна, який автоматично блокує:
- порушення стандартів стилю Python (PEP 8) та імпортів;
- забуті міграції моделей Django;
- регресії у PostgreSQL (`pgvector`, FTS GIN, транзакції) та Redis-механізмах (`admission.py`, кеш);
- попередження ESLint у React-коді;
- поломки збірки Docker-образів та інтеграції Caddy + Gunicorn + Postgres + Redis.

---

## 2. Архітектура змін

### 2.1. Python-лінтер та dev-залежності (`backend/`)
- **`backend/pyproject.toml`** — єдина конфігурація інструмента **`ruff`**:
  - `target-version = "py312"`
  - `line-length = 120`
  - `exclude = ["**/migrations/*", ".venv", "staticfiles", "media"]`
  - `[tool.ruff.lint]`: `select = ["E", "W", "F", "I", "B"]`
  - `[tool.ruff.lint.isort]`: `known-first-party = ["accounts", "backups", "chats", "config", "llm", "ollama_proxy", "workspaces"]`
- **`backend/requirements-dev.txt`** — фіксує dev/CI-залежності окремо від продакшен-образу (`requirements.txt`):
  - `ruff>=0.8,<1.0`
  - `pytest>=8.0,<10.0`
  - `pytest-django>=4.9,<5.0`
- **Виправлення наявного коду:** усі попередження `ruff check .` у `backend/` мають бути усунуті в рамках реалізації, щоб CI одразу проходив із кодом виходу `0`.

### 2.2. Job `backend` (SQLite + Lint)
У `.github/workflows/ci.yml`:
1. Встановлюються залежності (`requirements.lock` / `requirements.txt`) та dev-інструменти (`pip install -r requirements-dev.txt`).
2. Запускається `ruff check .` (перевірка PEP 8, невикористаних імпортів, порядку імпортів, bugbear-патернів).
3. Виконується ліцензійна перевірка (`piplicenses --fail-on=...`).
4. Виконується `python manage.py makemigrations --check --dry-run` (перевірка відсутності незбережених міграцій).
5. Виконуються тести на SQLite (`python manage.py test --verbosity=1`) для підтвердження сумісності локального режиму розробки.

### 2.3. Job `backend-postgres` (PostgreSQL 16 + pgvector + Redis)
У `.github/workflows/ci.yml`:
1. Сервіси job:
   - `postgres`: `pgvector/pgvector:pg16` (з healthcheck `pg_isready`)
   - `redis`: `redis:7.2.7-alpine` (порт `6379:6379`, з healthcheck `redis-cli ping`)
2. Змінні середовища:
   - `USE_SQLITE: 'False'`
   - `REDIS_URL: 'redis://127.0.0.1:6379/0'`
   - `CELERY_TASK_ALWAYS_EAGER: 'True'`
3. Кроки:
   - `python manage.py migrate --noinput`
   - Повний запуск тестів: `python manage.py test --verbosity=1` (охоплює pgvector, HNSW, GIN FTS, RRF, RAG, chats analytics/resolution, crypto, backups, admission locks у Redis, healthcheck).

### 2.4. Job `frontend` (ESLint Strict + License + Test + Build)
У `frontend/package.json` та `.github/workflows/ci.yml`:
- У `frontend/package.json` скрипт `"lint"` оновлюється до `"eslint src --ext js,jsx --max-warnings=0"`, щоб сувора перевірка діяла однаково локально і в CI.
- Залишаються `npm ci`, `license-checker`, `npm run lint`, `npm test` (`vitest run`), `npm run build`.

### 2.5. Job `compose` (Validation + Docker Build + Live Smoke)
У `.github/workflows/ci.yml`:
1. Підготовка `.env` з `.env.example` та валідація конфігів:
   - `docker compose config --quiet`
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet`
2. Налаштування Docker Buildx (`docker/setup-buildx-action@v3`) з GHA-кешем для прискорення збірки.
3. Збірка образів: `docker compose build backend worker frontend`.
4. Послідовний запуск runtime-стеку без важкого образу `ollama`:
   - `docker compose up -d --wait db redis`
   - `docker compose up -d --no-deps --wait backend`
   - `docker compose up -d --no-deps --wait frontend`
5. Smoke-перевірка HTTP через `curl`:
   - перевірка `http://127.0.0.1/api/health/` — HTTP `200`, JSON містить `"database": "ok"` та `"cache": "ok"` (`ollama` у цьому режимі буде `"unavailable"`, тому `/api/health/` без `?strict=1` коректно повертає HTTP `200` зі `"status": "degraded"`).
   - перевірка `http://127.0.0.1/` — HTTP `200`, HTML SPA.
6. Прибирання ресурсів:
   - Друк логів при помилці (`if: failure()`): `docker compose logs --tail=50`
   - Повне очищення (`if: always()`): `docker compose down -v`

---

## 3. Критерії успіху
- Локальний запуск `ruff check .` у `backend/` завершується з кодом `0`.
- Локальний запуск `python manage.py makemigrations --check --dry-run` завершується з кодом `0`.
- Локальний запуск `npm run lint -- --max-warnings=0`, `npm test`, `npm run build` у `frontend/` завершується з кодом `0`.
- Локальні тести `backend` проходять без регресій.
- `.github/workflows/ci.yml` валідний за YAML/Actions-схемою та містить усі 4 посилені jobs (`backend`, `backend-postgres`, `frontend`, `compose`).
