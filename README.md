# ZROZUMILOAI — Панель керування персональним помічником

Веб-панель для керування AI-помічником з React frontend та Django backend.
Підтримує **Ollama**, RAG по документах workspace та Open edX Meilisearch.

## Можливості

- Чат з AI-помічником (streaming) через Ollama
- Workspaces — ізоляція моделей, system prompt, temperature, LLM-провайдера
- **RAG** — завантаження документів (**TXT, MD, PDF, DOCX, HTML**); структурний chunking та індексація через Celery/Redis
- **Гібридний пошук (Hybrid Search)** — RRF (Reciprocal Rank Fusion) об'єднання векторного пошуку (pgvector HNSW) та повнотекстового пошуку PostgreSQL FTS
- **Аналітика та Knowledge Gaps** — дашборд запитів, відстеження прогалин у знаннях з чергою резолюції для викладачів, експорт у CSV/JSON
- **Chats Info та розмежування каналів (`Web`, `Telegram`, `Widget`)** — автоматичне тегування джерела повідомлень (`channel`: `web` | `telegram` | `widget`) та відправника (`username/email`, `@username (@bot_username)`, `Widget (<label|prefix>)`), кольорові бейджі в таблиці, фільтрація за джерелом, робочим простором, періодом (`today`, `7d`, `30d`), `needs_handoff`, `feedback` та `is_resolved`, AI-аналіз вибірки та експорт у CSV/JSON/JSONL/Alpaca
- **Feedback / handoff** — 👍/👎 на відповіді, ескалація при низькій релевантності RAG
- **Meilisearch / hybrid** — пошук у Open edX (Tutor) разом із локальним RAG (RRF)
- Збережені чати на сервері (історія діалогів)
- Embed-віджет для сторонніх сайтів (Widget-Token, course-scoped, кастомізація логотипу, заголовка та кольорів)
- **Telegram-боти** — Long Polling демон (`telegram_poller`), шифрування токенів у БД (`FIELD_ENCRYPTION_KEY`), перевірка токена через Telegram `getMe`, прив'язка ботів до робочих просторів, привітання та кнопки швидких FAQ із налаштувань workspace, ковзне вікно контексту сесії (12 останніх повідомлень) й inline-кнопки оцінки 👍/👎
- Перегляд моделей (фільтр за workspace); pull/delete — лише адміністратор
- Реєстрація та авторизація (JWT + API-ключі)
- Адмін-панель: користувачі, workspaces, Telegram-боти, Chats Info, аналітика, моделі, резервні копії БД
- Налаштування зовнішнього вигляду (теми)
- Адаптивний інтерфейс (мобільні, планшети, десктоп)
- Docker Compose: Ollama, PostgreSQL (pgvector), Redis, Celery worker, Django, `telegram_poller`, Caddy
- **Надійність та моніторинг (Ops)** — fail-closed Redis admission control (`HTTP 503` при недоступному Redis) та fail-closed Redis-блокування у `telegram_poller`, дуальні health-ендпоінти (`/api/health/` і `/api/health/?strict=1`), повні `.tar.gz`-бекапи (дамп БД + `media/` + `manifest.json`)
- CI: GitHub Actions (`ruff`, `eslint`, `manage.py test`, `npm test` / build, перевірка ліцензій)

## Структура

```
ZROZUMILOAI/
├── backend/          # Django REST API
│   ├── accounts/     # Авторизація, користувачі, API-ключі
│   ├── chats/        # Збережені діалоги + Chats Info (Web/Telegram/Widget) + аналітика
│   ├── workspaces/   # Workspaces, RAG, widget tokens, Telegram-боти (client/handlers/poller)
│   ├── llm/          # Провайдер Ollama та concurrency admission
│   ├── ollama_proxy/ # HTTP API чату / моделей
│   └── backups/      # Резервні копії БД та media (.tar.gz)
├── frontend/         # React (Vite) + embed widget
├── TeplateTutor/     # Тема Open edX + Tutor plugin
├── .github/          # CI workflows
├── LICENSE           # MIT
├── docker-compose.yml
└── .env.example
```

## Швидкий старт (Docker)

```bash
cp .env.example .env
docker compose up --build -d
```

Після запуску:
- Frontend / API через Caddy: http://localhost
- Ollama: лише `127.0.0.1:11434` (не публікується на всі інтерфейси)
- Redis + Celery worker — для черги ingest документів та координації слотів/блокувань
- `telegram_poller` — сервіс Long Polling для активних Telegram-ботів (стартує після переходу `backend` у стан `healthy`)
- Backend API слухає лише всередині Docker-мережі (`backend:8000`), не на хості

**Безпека перед GitHub / продакшеном:**
1. Скопіюйте `.env.example` → `.env` і задайте унікальні `DJANGO_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, паролі БД.
2. Не комітьте `.env`, реальні widget tokens, токени Telegram-ботів або backup з продакшен-даними. Якщо token потрапив у git — вилучіть його (revoke у Workspaces або оновіть у `@BotFather`) і створіть новий.
3. `docker-compose.yml` вимагає `DJANGO_SECRET_KEY` і `POSTGRES_PASSWORD` з `.env` (без слабких fallback). При `DJANGO_DEBUG=False` placeholder-секрети **відхиляються**.
4. Для продакшену використовуйте `docker compose -f docker-compose.yml -f docker-compose.prod.yml` (resource limits, жорсткіші concurrency defaults).
5. Конфіденційні ключі у БД (Meilisearch API keys та токени Telegram-ботів) шифруються at rest (`FIELD_ENCRYPTION_KEY`).

### Продакшен (один VPS)

- Мінімум: **16 GB RAM**, 4+ vCPU (Ollama + панель на одному хості).
- Overlay: `docker-compose.prod.yml` — `mem_limit`/`cpus`, `OLLAMA_NUM_PARALLEL=1`, Gunicorn/Celery caps, Redis password.
- Remote LLM пізніше: лише `OLLAMA_BASE_URL` у `.env`.
- Ops: [docs/ops/vps-runbook.md](docs/ops/vps-runbook.md) (deploy, backup cron, restore drill, overload).
- Observability: дуальний контракт health-check — `/api/health/` (внутрішня liveness-перевірка Docker, HTTP 200 поки жива БД) та `/api/health/?strict=1` (зовнішній моніторинг, HTTP 503 при деградації БД чи Ollama) + JSON logs (**без** Prometheus на цьому VPS).

Завантажте модель:

```bash
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama pull nomic-embed-text
```

Модель `nomic-embed-text` потрібна для RAG (embeddings документів).

Або через адмін-панель: http://localhost/admin/models

## Локальна розробка

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
set USE_SQLITE=True
set CELERY_TASK_ALWAYS_EAGER=True
python manage.py migrate
..\scripts\ensure_admin.ps1
python manage.py runserver
# Опційно (локальний Telegram Long Polling демон):
python manage.py run_telegram_bots
```

Локально без Redis ingest виконується синхронно (`CELERY_TASK_ALWAYS_EAGER=True` за замовчуванням, якщо `REDIS_URL` порожній).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173 (проксі на backend :8000)

### Ollama

Встановіть [Ollama](https://ollama.com/) та запустіть:

```bash
ollama serve
ollama pull llama3.2
```

## Ролі та доступ

| Дія | Користувач | Адміністратор (`is_staff`) |
|-----|:----------:|:--------------------------:|
| Чат з доступними моделями | ✓ | ✓ |
| Перегляд моделей (фільтр за workspace) | ✓ | ✓ (усі моделі) |
| Завантаження / видалення моделей | — | ✓ |
| Керування workspaces | — | ✓ |
| Керування Telegram-ботами | — | ✓ |
| Перегляд та експорт Chats Info | — | ✓ |
| Керування користувачами | — | ✓ |
| Резервні копії БД | — | ✓ |
| Зміна пароля / теми | ✓ | ✓ |

Звичайний користувач бачить лише моделі, призначені його workspace. Адміністратор має доступ до всіх моделей Ollama.

## API Endpoints

Авторизація: `Authorization: Bearer <JWT>` або `Authorization: Api-Key zai_...`

API-ключ генерується автоматично при реєстрації або створенні користувача адміном. Повний ключ показується один раз.

### Авторизація

| Метод | URL | Доступ | Опис |
|-------|-----|--------|------|
| POST | `/api/auth/register/` | публічний | Реєстрація |
| POST | `/api/auth/login/` | публічний | Вхід (JWT) |
| POST | `/api/auth/refresh/` | публічний | Оновлення access token |
| GET | `/api/auth/me/` | auth | Поточний користувач |
| POST | `/api/auth/me/change-password/` | auth | Зміна пароля |
| GET/POST | `/api/auth/users/` | admin | Список / створення користувачів |
| GET/PATCH/DELETE | `/api/auth/users/<id>/` | admin | Перегляд / редагування / видалення |

### Чати та Chats Info

| Метод | URL | Доступ | Опис |
|-------|-----|--------|------|
| GET/POST | `/api/chats/` | auth | Список / створення чатів |
| GET/PATCH/DELETE | `/api/chats/<id>/` | auth | Перегляд / оновлення / видалення |
| GET | `/api/chats/logs/` | admin | Логи обмінів (фільтри: `workspace_id`, `range=today\|7d\|30d`, `channel=web\|telegram\|widget`, `needs_handoff`, `feedback`, `is_resolved`) |
| GET | `/api/chats/logs/export/` | admin | Експорт логів (`export_format=csv\|json\|jsonl\|alpaca`, із тими ж фільтрами) |
| POST | `/api/chats/logs/analysis/` | admin | AI-аналіз поточної відфільтрованої таблиці чатів |
| DELETE | `/api/chats/logs/clear/` | admin | Очищення всіх логів Chats Info |
| PATCH/DELETE | `/api/chats/logs/<id>/` | admin | Оновлення feedback/handoff або видалення окремого запису логу |
| POST | `/api/chats/logs/<id>/feedback/` | auth | Оцінка відповіді (`up` / `down`, власник запису або admin; embed-віджет використовує Widget-Token API) |

**Розмежування каналів (`channel` / `sent_by`):**
- `web` — авторизовані користувачі веб-інтерфейсу (формат `sent_by`: `username` / `email`)
- `telegram` — користувачі Telegram-бота (формат `sent_by`: `@username \| first_name \| id:<chat_id> (@bot_username \| bot.name)`)
- `widget` — гості вбудованого вебвіджета (формат `sent_by`: `Widget (<label \| token_prefix>)` або `Widget guest`)

### Workspaces

| Метод | URL | Доступ | Опис |
|-------|-----|--------|------|
| GET | `/api/workspaces/my/` | auth | Workspaces поточного користувача |
| GET/POST | `/api/workspaces/` | admin | Список / створення (зокрема прив'язка `telegram_bot_ids`) |
| GET/PATCH/DELETE | `/api/workspaces/<id>/` | admin | Перегляд / редагування / видалення |
| GET/POST | `/api/workspaces/<id>/widget-tokens/` | admin | Список / створення токенів віджета |
| DELETE | `/api/workspaces/<id>/widget-tokens/<token_id>/` | admin | Видалення токена віджета |
| GET/POST | `/api/workspaces/<id>/documents/` | admin | Список / завантаження документів (RAG) |
| DELETE | `/api/workspaces/<id>/documents/<doc_id>/` | admin | Видалити документ |
| POST | `/api/workspaces/<id>/documents/<doc_id>/retry/` | admin | Повторна індексація документа |
| GET | `/api/workspaces/<id>/rag-stats/` | admin | Статистика RAG-індексу workspace |
| GET | `/api/workspaces/<id>/analytics/` | teacher/admin | Загальна статистика, тренди, популярні теми |
| GET | `/api/workspaces/<id>/analytics/export/` | teacher/admin | Експорт аналітики у CSV |
| PATCH | `/api/workspaces/<id>/analytics/gaps/<log_id>/resolve/` | teacher/admin | Позначення прогалини знань як опрацьованої |

### Telegram-боти

| Метод | URL | Доступ | Опис |
|-------|-----|--------|------|
| GET/POST | `/api/workspaces/telegram-bots/` | admin | Список / створення Telegram-бота (також доступно на `/api/telegram-bots/`) |
| GET/PATCH/DELETE | `/api/workspaces/telegram-bots/<id>/` | admin | Перегляд / оновлення / видалення бота |
| POST | `/api/workspaces/telegram-bots/<id>/verify/` | admin | Перевірка токена через Telegram Bot API (`getMe`) |

**Як працює `telegram_poller`:**
1. Отримує активних ботів, прив'язаних до workspace, і розшифровує токен (`FIELD_ENCRYPTION_KEY`).
2. За наявності `REDIS_URL` утримує розподілений Redis poll lock із fail-closed захистом, щоб уникнути дублювання polling-воркерів при збоях Redis або кількох репліках.
3. Обробляє команди `/start`, `/reset`, `/clear` (скидання історії сесії, привітання з `embed_greeting` + кнопки швидких FAQ з `embed_faq_questions`), текстові запити й `callback_query` (FAQ та 👍/👎 фідбек), передаючи контекст останніх 12 повідомлень (`TelegramChatSession`) і зберігаючи обміни в `WorkspaceChatLog` із `channel='telegram'`.
4. **Рекомендовані налаштування у `@BotFather`:** додати команди `start`, `reset`, `clear` через `/setcommands`, вимкнути inline-режим (`/setinline` → Disable), увімкнути Privacy Mode для груп (`/setprivacy` → Enable) та налаштувати `/setjoingroups` відповідно до політики доступу.

### RAG (документи workspace)

1. Адмін завантажує `.txt`, `.md`, `.pdf`, `.docx` або `.html` у workspace (адмінка → Workspaces → редагування).
2. Backend індексує текст: структурний chunking (із збереженням заголовків та метаданих) + embeddings через Ollama (`RAG_EMBED_MODEL`, за замовчуванням `nomic-embed-text`).
3. Вектори зберігаються в **PostgreSQL + pgvector** (HNSW-індекс, cosine-пошук), а текстові поля індексуються через GIN-індекс PostgreSQL FTS.
4. При кожному повідомленні в чаті (в т.ч. widget) виконується гібридний пошук (RRF) і у system prompt додаються найрелевантніші фрагменти.

**Важливо:** embeddings для RAG ідуть через **Ollama** (`nomic-embed-text`). Без запущеного Ollama ingest документів і RAG-контекст не працюватимуть.

Docker використовує образ `pgvector/pgvector:pg16`. Локально з `USE_SQLITE=True` пошук працює через Python fallback (без pgvector).

Змінні середовища: `RAG_ENABLED`, `RAG_EMBED_MODEL`, `RAG_EMBED_DIMENSIONS`, `RAG_TOP_K`, `RAG_CHUNK_SIZE`, `RAG_MAX_FILE_SIZE` (див. `.env.example`).

### Open edX Meilisearch (пошук курсів)

Workspace може брати контекст з **Meilisearch Tutor/Open edX** замість або разом із локальним RAG:

| `search_source` | Поведінка |
|-----------------|-----------|
| `internal` | Лише завантажені документи (RAG) |
| `meilisearch` | Лише індекси Open edX |
| `hybrid` | Обидва джерела, top-K за score |

Налаштування в адмінці: **Workspaces → Редагувати → Пошук Open edX**:

- **URL** — напр. `meilisearch.local.openedx.io` (схема `https://` додається автоматично)
- **API key** — tenant key з Tutor (`MEILISEARCH_API_KEY`)
- **Префікс індексів** — зазвичай `tutor_` (не повна назва індексу)
- **Індекси** — `course_info`, `courseware_content` (каталог і зміст курсів)
- **Course ID** — опційний фільтр `course-v1:ORG+COURSE+RUN`

Глобальний fallback у `.env`: `MEILISEARCH_URL`, `MEILISEARCH_API_KEY`, `MEILISEARCH_INDEX_PREFIX`.

Для віджета на сторінці курсу можна передати `openedx_course_id` у тілі POST `/api/widget/chat/` або в атрибуті віджета (див. demo).

### Ollama

| Метод | URL | Доступ | Опис |
|-------|-----|--------|------|
| GET | `/api/ollama/health/` | auth | Статус підключення до Ollama |
| GET | `/api/ollama/models/` | auth | Список моделей (фільтр за workspace) |
| POST | `/api/ollama/models/pull/` | admin | Завантажити модель (SSE) |
| DELETE | `/api/ollama/models/delete/` | admin | Видалити модель |
| POST | `/api/ollama/chat/` | auth | Чат з моделлю (streaming або JSON) |

Параметри `/api/ollama/chat/`: `model`, `messages`, `stream` (bool), `workspace_id` (опційно).

### Резервні копії

| Метод | URL | Доступ | Опис |
|-------|-----|--------|------|
| GET/POST | `/api/backups/` | admin | Список / створення backup |
| GET | `/api/backups/<file>/download/` | admin | Завантажити backup |
| DELETE | `/api/backups/<file>/` | admin | Видалити backup |

Резервні копії зберігаються в теці `backup/` у вигляді повного архіву `.tar.gz` (дамп БД PostgreSQL/SQLite + директорія `media/` + `manifest.json`; під час відновлення також зберігається зворотна сумісність із застарілими файлами `.sql` та `.sqlite3`).

Для відновлення БД при старті встановіть `FORCE_DB_RESTORE=1` у `.env` — Docker entrypoint відновить найновіший backup перед `migrate`.

## Технології

- **Frontend:** React 18, React Router, Vite, CSS3
- **Backend:** Django 5, DRF, SimpleJWT
- **Інфра:** Docker, PostgreSQL (pgvector), Redis 7.2 (BSD), Celery, Ollama, Caddy

## HTTPS (Caddy)

Локально frontend слухає `:80` (HTTP). Для продакшену в `.env` вкажіть домен:

```env
CADDY_SITE_ADDRESS=chat.example.com
DJANGO_ALLOWED_HOSTS=chat.example.com,backend
CORS_ALLOWED_ORIGINS=https://chat.example.com,https://your-wordpress-site.com
```

Caddy автоматично отримує сертифікат Let's Encrypt (порти 80 і 443 мають бути доступні з інтернету).

## Як додати віджет чату до Open edX

Віджет можна вбудувати в LMS Open edX (Tutor) так само, як на будь-який зовнішній сайт — через тег `<script>`. Token створюється в адмінці: **Workspaces → Редагувати → «Створити token»**.

### Підключення

**1. Кастомна тема Tutor**

```bash
THEME_DIR="$(tutor config printroot)/env/build/openedx/themes/zrozumilo"
mkdir -p "$THEME_DIR"
cp -r /path/to/ZROZUMILOAI/TeplateTutor/zrozumilo/lms "$THEME_DIR/"
cp /path/to/ZROZUMILOAI/TeplateTutor/zrozumilo/theme.conf "$THEME_DIR/"
tutor local do settheme zrozumilo
```

У темі додайте скрипт у базовий шаблон LMS (footer, перед `</body>`), наприклад `lms/templates/main.html`:

```html
<script
  src="https://chat.example.com/widget.js"
  data-widget-token="wt_ВАШ_TOKEN"
  data-title="Підтримка"
  data-color="#0D9E96"
></script>
```

Потім перезберіть образ:

```bash
tutor images build openedx
tutor local restart
```

**2. Tutor plugin (рекомендовано для продакшену)** — патч шаблонів LMS, CSP-винятки, token з env через `tutor config save`.

**3. Site Configuration** — у деяких версіях Open edX є поля для extra footer HTML; у новіших MFE-версіях зазвичай потрібна тема або plugin.

### Найпростіші варіанти (від простого до складного)

#### 1. Посилання «Підтримка» → окрема сторінка чату

**Найпростіше для Tutor.**

- У Open edX додаєте пункт меню або кнопку на `https://chat.example.com` (або embed-сторінку).
- Користувач переходить у чат у новій вкладці.
- **Без** CSP для `script-src` / `frame-src`, **без** Tutor plugin.

**Мінус:** не плаваюча кнопка в куті, а окремий перехід.

#### 2. Віджет `<script>` (розділ «Підключення» вище)

Плаваюча кнопка чату на сторінках LMS. Потрібні тема Tutor, HTTPS і CSP.

### Налаштування ZrozumiloAI

На продакшені не використовуйте `http://localhost`. У `.env`:

```env
CADDY_SITE_ADDRESS=chat.example.com
DJANGO_ALLOWED_HOSTS=chat.example.com,backend
CORS_ALLOWED_ORIGINS=https://learn.example.com
```

Додайте домен Open edX (`https://learn.example.com`) до `CORS_ALLOWED_ORIGINS`.

### Content Security Policy (CSP)

Open edX часто блокує зовнішні скрипти. У налаштуваннях LMS дозвольте домен віджета:

| Директива | Значення |
|-----------|----------|
| `script-src` | `https://chat.example.com` |
| `frame-src` | `https://chat.example.com` |
| `connect-src` | `https://chat.example.com` |

У Tutor це робиться через патч `production.py` або plugin.

### Важливо

- Скрипт має бути звичайним `<script src="...">` **без** `async` / `defer` (віджет використовує `document.currentScript`).
- Open edX працює по **HTTPS** — віджет теж має бути на HTTPS (див. розділ [HTTPS (Caddy)](#https-caddy)).
- Скрипт у LMS-шаблоні показує віджет на сторінках LMS; для **CMS (Studio)** потрібен окремий шаблон.
- `data-widget-token` видно в HTML — це нормально: token обмежений одним workspace.

### Опційні атрибути

```html
data-position="left"          <!-- або right (за замовчуванням) -->
data-z-index="999999"
data-api-url="https://chat.example.com/api"
data-embed-url="https://chat.example.com/embed.html"
```

### Локальний тест

Демо-сторінка: http://localhost/demo-embed.html. Для перевірки з Open edX потрібен staging з HTTPS і публічним доменом ZrozumiloAI.

## Ліцензія

Код проєкту — **MIT** (див. `LICENSE`). Атрибуція сторонніх компонентів (LGPL тощо) — у `NOTICE`.

**Моделі Ollama** (ваги) ліцензуються окремо від цього репозиторію:
- `llama3.2` — Meta Llama Community License (перевірте умови перед комерційним SaaS)
- `nomic-embed-text` — зазвичай Apache-2.0 (перевірте картку моделі в Ollama / на сайті автора)

У CI: `pip-licenses` і `license-checker` блокують GPL/AGPL у залежностях. Redis у Compose закріплено на **7.2.7-alpine** (BSD), не 7.4+/SSPL.
