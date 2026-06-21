# ZROZUMILOAI — Панель керування персональним помічником

Веб-панель для керування AI-помічником на базі Ollama з React frontend та Django backend.

## Можливості

- Чат з AI-помічником (streaming) через Ollama API
- Workspaces — ізоляція моделей, system prompt і temperature для груп користувачів
- **RAG** — завантаження документів (TXT, MD, PDF) у workspace; релевантний контекст автоматично додається в чат
- Збережені чати на сервері (історія діалогів)
- Перегляд моделей (з фільтрацією за workspace); завантаження та видалення — лише для адміністратора
- Реєстрація та авторизація (JWT + API-ключі)
- Адмін-панель: користувачі, workspaces, моделі, резервні копії БД
- Налаштування зовнішнього вигляду (теми)
- Адаптивний інтерфейс (мобільні, планшети, десктоп)
- Docker Compose з Ollama, PostgreSQL, Django та Caddy

## Структура

```
ZROZUMILOAI/
├── backend/          # Django REST API
│   ├── accounts/     # Авторизація, користувачі, API-ключі
│   ├── chats/        # Збережені діалоги
│   ├── workspaces/   # Workspaces та доступ до моделей
│   ├── ollama_proxy/ # Проксі до Ollama
│   └── backups/      # Резервні копії БД
├── frontend/         # React (Vite)
├── backup/           # Файли backup (.sql / .sqlite3)
├── scripts/          # ensure_admin.sh / .ps1
├── docker-compose.yml
└── .env.example
```

## Швидкий старт (Docker)

```bash
cp .env.example .env
docker compose up --build -d
```

Після запуску:
- Frontend: http://localhost
- Backend API: http://localhost:8000/api/
- Ollama: http://localhost:11434

Адміністратор створюється автоматично з `.env` при першому запуску (`DJANGO_ADMIN_USERNAME`, `DJANGO_ADMIN_PASSWORD`).

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
python manage.py migrate
..\scripts\ensure_admin.ps1
python manage.py runserver
```

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

### Чати

| Метод | URL | Доступ | Опис |
|-------|-----|--------|------|
| GET/POST | `/api/chats/` | auth | Список / створення чатів |
| GET/PATCH/DELETE | `/api/chats/<id>/` | auth | Перегляд / оновлення / видалення |

### Workspaces

| Метод | URL | Доступ | Опис |
|-------|-----|--------|------|
| GET | `/api/workspaces/my/` | auth | Workspaces поточного користувача |
| GET/POST | `/api/workspaces/` | admin | Список / створення |
| GET/PATCH/DELETE | `/api/workspaces/<id>/` | admin | Перегляд / редагування / видалення |
| GET/POST | `/api/workspaces/<id>/documents/` | admin | Список / завантаження документів (RAG) |
| DELETE | `/api/workspaces/<id>/documents/<doc_id>/` | admin | Видалити документ |

### RAG (документи workspace)

1. Адмін завантажує `.txt`, `.md` або `.pdf` у workspace (адмінка → Workspaces → редагування).
2. Backend індексує текст: chunking + embeddings через Ollama (`RAG_EMBED_MODEL`, за замовчуванням `nomic-embed-text`).
3. Вектори зберігаються в **PostgreSQL + pgvector** (HNSW-індекс, cosine-пошук).
4. При кожному повідомленні в чаті (в т.ч. widget) у system prompt додаються найрелевантніші фрагменти.

Docker використовує образ `pgvector/pgvector:pg16`. Локально з `USE_SQLITE=True` пошук працює через Python fallback (без pgvector).

Змінні середовища: `RAG_ENABLED`, `RAG_EMBED_MODEL`, `RAG_EMBED_DIMENSIONS`, `RAG_TOP_K`, `RAG_CHUNK_SIZE`, `RAG_MAX_FILE_SIZE` (див. `.env.example`).

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

Резервні копії зберігаються в теці `backup/` (PostgreSQL — `.sql`, SQLite — `.sqlite3`).

Для відновлення БД при старті встановіть `FORCE_DB_RESTORE=1` у `.env` — Docker entrypoint відновить найновіший backup перед `migrate`.

## Технології

- **Frontend:** React 18, React Router, Vite, CSS3
- **Backend:** Django 5, DRF, SimpleJWT
- **Інфра:** Docker, PostgreSQL, Ollama, Caddy

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
tutor themes create zrozumilo
tutor themes enable zrozumilo
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

MIT
