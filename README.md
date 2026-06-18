# ZROZUMILOAI — Панель керування персональним помічником

Веб-панель для керування AI-помічником на базі Ollama з React frontend та Django backend.

## Можливості

- Чат з AI-помічником (streaming) через Ollama API
- Workspaces — ізоляція моделей, system prompt і temperature для груп користувачів
- Збережені чати на сервері (історія діалогів)
- Перегляд моделей (з фільтрацією за workspace); завантаження та видалення — лише для адміністратора
- Реєстрація та авторизація (JWT + API-ключі)
- Адмін-панель: користувачі, workspaces, моделі, резервні копії БД
- Налаштування зовнішнього вигляду (теми)
- Адаптивний інтерфейс (мобільні, планшети, десктоп)
- Docker Compose з Ollama, PostgreSQL, Django та Nginx

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
```

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
- **Інфра:** Docker, PostgreSQL, Ollama, Nginx

## Ліцензія

MIT
