# Дизайн інтеграції Телеграм-ботів із Workspaces

**Date:** 2026-11-12  
**Status:** Approved for Spec Review  
**Scope:** Backend (`workspaces`, `entrypoint.sh`), Docker Compose (`docker-compose.yml`, `docker-compose.prod.yml`), Frontend (`AdminLayout.jsx`, `App.jsx`, `TelegramBotsPage.jsx`, `WorkspacesPage.jsx`, `WorkspaceModal.jsx`, `useWorkspacesAdmin.js`, `api/workspaces.js`)

---

## 1. Мета та огляд

Додати повноцінну систему керування Телеграм-ботами в адміністративну панель ZROZUMILOAI:
1. Окремий розділ адмін-панелі **«Телеграм-бот»** (`/admin/telegram-bots`) для створення, налаштування, перевірки токенів, увімкнення/вимкнення та видалення ботів.
2. Інтеграція з розділом **«Workspaces»** (`/admin/workspaces`): можливість привʼязувати та відвʼязувати Телеграм-боти безпосередньо у формі створення/редагування Workspace, а також бачити привʼязані боти у списку Workspaces.
3. Фоновий сервіс Long Polling (`python manage.py run_telegram_bots`), який динамічно підхоплює активні боти з БД без перезапуску контейнерів та обслуговує діалоги користувачів через існуючий RAG + Meilisearch + Ollama пайплайн (`run_chat`), включно з привітанням `/start`, швидкими кнопками FAQ, памʼяттю діалогу (`/reset`) та оцінками відповідей (`👍`, `👎`, `До людини`) з автоматичним потраплянням у **Knowledge Gaps** та **Chats Info**.

---

## 2. Моделі даних та безпека (`backend/workspaces/models.py`)

### 2.1. `TelegramBot`
- `name` (`CharField(max_length=150)`) — назва бота в панелі адміністратора.
- `encrypted_token` (`TextField`) — токен від `@BotFather`, зашифрований через `workspaces.crypto.encrypt_secret()` (`enc:v1:...`). Відкритий токен ніколи не повертається в API; методи моделі надають `get_token()`, `set_token(raw)` та властивість `token_masked` (формат `123456:***abcd` або `***abcd`).
- `bot_username` (`CharField(max_length=150, blank=True, default='')`) — `@username` бота з Telegram `getMe` (без `@`).
- `workspace` (`ForeignKey(Workspace, null=True, blank=True, on_delete=models.SET_NULL, related_name='telegram_bots')`) — воркспейс, до якого привʼязаний бот. Один бот у конкретний момент часу привʼязаний щонайбільше до одного Workspace; один Workspace може мати декілька підключених ботів.
- `is_active` (`BooleanField(default=True)`).
- `last_update_id` (`BigIntegerField(default=0)`) — останній оброблений `update_id` Telegram `getUpdates`.
- `last_poll_at` (`DateTimeField(null=True, blank=True)`) — час останнього успішного циклу опитування.
- `last_error` (`TextField(blank=True, default='')`) — текст останньої помилки Telegram API (порожній при успіху).
- `created_at` (`DateTimeField(auto_now_add=True)`), `updated_at` (`DateTimeField(auto_now=True)`).

### 2.2. `TelegramChatSession`
- `bot` (`ForeignKey(TelegramBot, on_delete=models.CASCADE, related_name='sessions')`).
- `telegram_chat_id` (`BigIntegerField`) — ID чату користувача в Telegram.
- `telegram_username` (`CharField(max_length=150, blank=True, default='')`) — username/імʼя співрозмовника для довідки.
- `messages` (`JSONField(default=list, blank=True)`) — масив останніх повідомлень діалогу (`[{"role": "user"|"assistant", "content": "..."}]`, максимум 12 повідомлень).
- `updated_at` (`DateTimeField(auto_now=True)`).
- `Meta`: `constraints = [UniqueConstraint(fields=['bot', 'telegram_chat_id'], name='uniq_telegram_bot_chat_session')]`.

---

## 3. REST API (`backend/workspaces/`)

Усі ендпоінти керування ботами доступні лише адміністраторам (`IsAuthenticated`, `IsAdminUser` — аналогічно до `WorkspaceViewSet`).

### 3.1. Керування Телеграм-ботами (`/api/telegram-bots/`)
- `GET /api/telegram-bots/` — повертає список ботів:
  `id`, `name`, `bot_username`, `token_masked`, `has_token`, `workspace` (`id`), `workspace_name`, `is_active`, `last_poll_at`, `last_error`, `created_at`, `updated_at`.
- `POST /api/telegram-bots/` — створює бота (`name`, `token`, опційно `workspace`, `is_active`). Шифрує `token` через `encrypt_secret`. Виконує спробу виклику `getMe` (таймаут 5 с): якщо Telegram повертає `ok: true`, зберігає `bot_username` та очищує `last_error`; якщо мережа/токен недоступні при створенні — записує діагностику в `last_error` (або повертає 400 при явному `401 Unauthorized` від Telegram).
- `PATCH /api/telegram-bots/<id>/` — оновлює поля (`name`, опційно новий `token`, `workspace`, `is_active`). Якщо `token` порожній або не переданий у `PATCH` — існуючий токен зберігається без змін.
- `DELETE /api/telegram-bots/<id>/` — видаляє бота.
- `POST /api/telegram-bots/<id>/verify/` — виконує перевірку токена через Telegram `getMe`, оновлює `bot_username` і `last_error`, повертає оновлений обʼєкт бота (або HTTP 400 зі змістом помилки при невалідному токені).

### 3.2. Розширення `/api/workspaces/` (`WorkspaceSerializer`)
- Поле читання `telegram_bots`: список привʼязаних ботів `[{"id": ..., "name": ..., "bot_username": ..., "is_active": ...}]`.
- Поле запису `telegram_bot_ids` (`ListField(child=IntegerField(), write_only=True, required=False)`):
  - При `create` / `update` Workspace синхронізує привʼязку: боти зі списку `telegram_bot_ids` отримують `workspace = instance`, а боти, які раніше належали цьому `instance`, але відсутні у списку — відвʼязуються (`workspace = None`).

---

## 4. Telegram Bot API клієнт та фоновий поллер (`backend/workspaces/telegram/`)

Модульна структура в `backend/workspaces/telegram/`:
- `client.py` — тонкий HTTP-клієнт до `https://api.telegram.org/bot<token>/<method>` на базі `requests`:
  - `get_me(token, timeout=5)`
  - `get_updates(token, offset=None, timeout=20)`
  - `send_message(token, chat_id, text, reply_markup=None, timeout=10)` (автоматично розбиває довгі тексти на частини по ≤4000 символів; кнопки `reply_markup` прикріплює до останньої частини)
  - `send_chat_action(token, chat_id, action='typing', timeout=5)`
  - `answer_callback_query(token, callback_query_id, text='', timeout=5)`
  - `edit_message_reply_markup(token, chat_id, message_id, reply_markup=None, timeout=5)`
- `handlers.py` — обробка одного `update` від Telegram:
  - **Команди `/start` та `/reset` (або `/clear`):**
    - Очищують `session.messages = []`.
    - Надсилають текст `workspace.embed_greeting` (або `f"Вітаю! Я помічник воркспейсу «{workspace.name}». Поставте своє запитання."`).
    - Якщо `workspace.embed_faq_questions` містить питання (до 10 шт.) — додають інлайн-клавіатуру `inline_keyboard`, де кожна кнопка має `callback_data: f"faq:{idx}"`.
  - **Текстове повідомлення або клік на кнопку `faq:<idx>`:**
    - Якщо бот не має привʼязаного Workspace або у Workspace не обрано модель (`workspace.model_names`) — надсилає ввічливе повідомлення про те, що бот ще налаштовується адміністратором.
    - Відправляє `send_chat_action('typing')`.
    - Формує історію `messages = [*session.messages[-12:], {'role': 'user', 'content': prompt}]`.
    - Викликає `run_chat(model=workspace.model_names[0], messages=messages, stream=False, workspace=workspace, user=None, prompt=prompt)`.
    - Якщо `run_chat` повернув 200 OK:
      - Витягує текст відповіді (`extract_response_from_ollama_payload(response.data)`) та `log_id = response.data.get('log_id')`.
      - Оновлює `session.messages` (до 12 останніх реплік) і зберігає сесію.
      - Якщо є `log_id`, додає під відповіддю інлайн-кнопки:
        - `👍 Корисно` (`fb:<log_id>:up`)
        - `👎 Не допомогло` (`fb:<log_id>:down`)
        - `🙋 До людини` (`fb:<log_id>:handoff`)
      - Надсилає відповідь у Telegram.
    - Якщо `run_chat` повернув 429 (`ollama_busy`) або 503 — надсилає користувачу повідомлення `response.data.get('error')` без падіння поллера.
  - **Клік на кнопку оцінки `fb:<log_id>:<action>`:**
    - Знаходить `WorkspaceChatLog(pk=log_id, workspace=bot.workspace)`.
    - Для `up` / `down` застосовує `apply_feedback_fields(log, {'feedback': action})`, для `handoff` — `apply_feedback_fields(log, {'needs_handoff': True})`, і викликає `save_log_feedback(log)`.
    - Викликає `answer_callback_query` («Дякуємо за відгук!» / «Запит передано фахівцю!») та прибирає кнопки під повідомленням (`edit_message_reply_markup(..., reply_markup={'inline_keyboard': []})`).
- `poller.py` та management-команда `backend/workspaces/management/commands/run_telegram_bots.py`:
  - Головний цикл менеджера кожні 5 секунд читає `TelegramBot.objects.filter(is_active=True, workspace__isnull=False).select_related('workspace')`.
  - Для кожного активного бота підтримує окремий daemon-потік, а якщо бот деактивований, видалений або змінив токен — сигналізує потоку зупинитися (`stop_event`).
  - Перед `getUpdates` потік оновлює Redis-лок `telegram:poll_lock:<bot_id>` (TTL 60 с, `SET NX` / продовження своїм токеном), щоб унеможливити `409 Conflict` при паралельному запуску. Якщо Redis не налаштований (`REDIS_URL` порожній) — працює в режимі fail-open.

---

## 5. Docker Compose та `entrypoint.sh`

- У `backend/entrypoint.sh` додається підтримка `APP_ROLE=poller` (поряд із `worker` — виконує ідемпотентний `migrate --noinput` і передану команду).
- У `docker-compose.yml` та `docker-compose.prod.yml` додається сервіс `telegram_poller`:
  - `build: ./backend`
  - `command: python manage.py run_telegram_bots`
  - `APP_ROLE: poller`
  - Ті самі змінні БД, Redis, Ollama та `FIELD_ENCRYPTION_KEY`, що й у `worker`.

---

## 6. Фронтенд (`frontend/src/`)

1. **API клієнт (`frontend/src/api/telegramBots.js`):**
   - `getTelegramBots()`, `createTelegramBot(data)`, `updateTelegramBot(id, data)`, `deleteTelegramBot(id)`, `verifyTelegramBot(id)`.
2. **Розділ «Телеграм-бот» (`frontend/src/pages/TelegramBotsPage.jsx`):**
   - Маршрут `/admin/telegram-bots` у `App.jsx` та посилання `{ to: '/admin/telegram-bots', label: 'Телеграм-бот' }` у `AdminLayout.jsx`.
   - Таблиця ботів: Назва, `@username`, Маска токена, Привʼязаний Workspace, Статус (`Активний` / `Вимкнений` + індикатор останнього опитування чи помилки), Дії (`Перевірити`, `Редагувати`, `Видалити`).
   - Форма створення / редагування бота (Назва, Токен `@BotFather`, випадаючий список Workspace або «Не привʼязано», чекбокс «Активний»).
3. **Інтеграція у `WorkspacesPage.jsx`, `WorkspaceModal.jsx` та `useWorkspacesAdmin.js`:**
   - У таблиці `WorkspacesPage.jsx` додається колонка **«Телеграм-боти»** (відображає назви або `@username` підключених ботів).
   - У `useWorkspacesAdmin.js` паралельно завантажується список `telegramBots` (`getTelegramBots()`), а у стані форми `form` підтримується масив `telegram_bot_ids` та хендлер `toggleTelegramBotId(botId)`.
   - У `WorkspaceModal.jsx` додається група чекбоксів **«Телеграм-боти»** (поруч із «Користувачі» та «Модель»), де можна відмітити потрібні боти з розділу «Телеграм-бот» (якщо бот зараз привʼязаний до іншого воркспейсу — біля нього виводиться підказка `(зараз у: <Назва>)`).

---

## 7. Критерії успіху та тестування

- Unit-тести бекенду покривають:
  - Шифрування та маскування токена `TelegramBot`.
  - CRUD та `verify` API `/api/telegram-bots/` і привʼязку `telegram_bot_ids` через `/api/workspaces/`.
  - Обробку `/start`, `/reset`, текстових повідомлень, кнопок `faq:<idx>` та `fb:<log_id>:up|down|handoff` (з перевіркою збереження `WorkspaceChatLog` і сесії `TelegramChatSession`).
- Unit-тести фронтенду (Vitest) покривають `TelegramBotsPage` та вибір `telegram_bot_ids` у `useWorkspacesAdmin` / `WorkspaceModal`.
- `ruff check .`, `eslint --max-warnings=0`, усі тести бекенду та фронтенду проходять з кодом `0`.
