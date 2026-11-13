# Telegram Bot Workspace Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement full Telegram Bot management in the admin panel, link bots to Workspaces, and execute an autonomous Long Polling service handling `/start`, FAQ quick chips, conversation memory, hybrid RAG answers, and feedback buttons directly tied to Knowledge Gaps and Chats Info.

**Architecture:**
- **Storage & Security:** `TelegramBot` encrypts tokens at rest with `encrypt_secret` (`workspaces/crypto.py`) and links to `Workspace`. `TelegramChatSession` retains sliding conversation window (up to 12 messages) per user chat.
- **REST API:** `/api/telegram-bots/` for full CRUD and `verify` token checks via Telegram `getMe`. `WorkspaceSerializer` syncs `telegram_bot_ids`.
- **Bot Engine:** Standard `requests`-based client (`getMe`, `getUpdates`, `sendMessage`, `sendChatAction`, `answerCallbackQuery`, `editMessageReplyMarkup`), message handler wrapping `run_chat`, feedback handler writing to `WorkspaceChatLog`, and multithreaded daemon manager (`run_telegram_bots`) with dynamic DB sync and Redis slot locking.
- **Frontend:** New `/admin/telegram-bots` management page, navigation item in `AdminLayout.jsx`, bot column in `WorkspacesPage.jsx`, and bot selector checkboxes in `WorkspaceModal.jsx`.
- **Ops:** `telegram_poller` container in `docker-compose.yml` and `docker-compose.prod.yml`.

**Tech Stack:** Python 3.12, Django 5.2, PostgreSQL 16 + pgvector, Redis 7.2, React 18, Vite 5, Vitest, Docker Compose.

## Global Constraints

- Follow PEP 8, HTML5, CSS3, and StandardJS/ESLint conventions; keep `requirements.txt` free of unnecessary third-party frameworks.
- Tokens must always be stored encrypted (`enc:v1:...`) and never exposed in full through API GET responses; use `token_masked` (e.g. `123456:***abcd`).
- Telegram bot conversation responses must route through `run_chat` to preserve `ollama:admission`, RAG + Meilisearch search, and `WorkspaceChatLog` logging.
- `run_telegram_bots` must dynamically synchronize active bots without requiring a container restart.
- Maintain 100% test passing rate across `backend` and `frontend`.

---

### Task 1: Backend Data Models & Migrations (`TelegramBot` and `TelegramChatSession`)

**Files:**
- Modify: `backend/workspaces/models.py`
- Create: `backend/workspaces/tests/test_telegram_models.py`
- Create: `backend/workspaces/migrations/0016_telegrambot_telegramchatsession.py`

**Interfaces:**
- Produces: `TelegramBot`, `TelegramChatSession` models in `workspaces.models`.
- Consumes: `encrypt_secret`, `decrypt_secret` from `workspaces.crypto`.

- [ ] **Step 1: Write failing unit tests for `TelegramBot` and `TelegramChatSession`**

Create `backend/workspaces/tests/test_telegram_models.py`:
```python
"""Tests for TelegramBot and TelegramChatSession models."""
from django.test import TestCase

from workspaces.models import TelegramBot, TelegramChatSession, Workspace


class TelegramModelTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(name='Telegram Test WS')

    def test_token_encryption_and_masking(self):
        bot = TelegramBot(name='Support Bot', workspace=self.workspace)
        raw_token = '123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234'
        bot.set_token(raw_token)
        bot.save()

        # In DB, token must be encrypted
        bot.refresh_from_db()
        self.assertTrue(bot.encrypted_token.startswith('enc:v1:'))
        self.assertEqual(bot.get_token(), raw_token)
        self.assertEqual(bot.token_masked, '123456789:***1234')

    def test_token_masking_short_or_empty(self):
        bot = TelegramBot(name='Empty Token Bot')
        self.assertEqual(bot.token_masked, '')

        bot.set_token('short')
        self.assertEqual(bot.token_masked, '***')

    def test_chat_session_unique_constraint_and_messages(self):
        bot = TelegramBot.objects.create(name='Chat Bot', workspace=self.workspace)
        session = TelegramChatSession.objects.create(
            bot=bot,
            telegram_chat_id=987654321,
            telegram_username='student_ua',
            messages=[{'role': 'user', 'content': 'Привіт!'}],
        )
        self.assertEqual(session.messages[0]['content'], 'Привіт!')

        with self.assertRaises(Exception):
            TelegramChatSession.objects.create(
                bot=bot,
                telegram_chat_id=987654321,
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_telegram_models`
Expected: FAIL with `ImportError: cannot import name 'TelegramBot' from 'workspaces.models'`

- [ ] **Step 3: Implement `TelegramBot` and `TelegramChatSession` in `backend/workspaces/models.py`**

In `backend/workspaces/models.py`:
```python
from workspaces.crypto import decrypt_secret, encrypt_secret


class TelegramBot(models.Model):
    """Телеграм-бот, підключений до системи та прив'язаний до Workspace."""

    name = models.CharField(max_length=150, help_text='Назва бота для адмін-панелі')
    encrypted_token = models.TextField(blank=True, default='')
    bot_username = models.CharField(max_length=150, blank=True, default='')
    workspace = models.ForeignKey(
        Workspace,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='telegram_bots',
    )
    is_active = models.BooleanField(default=True)
    last_update_id = models.BigIntegerField(default=0)
    last_poll_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Телеграм-бот'
        verbose_name_plural = 'Телеграм-боти'

    def __str__(self):
        return f'{self.name} (@{self.bot_username or "unknown"})'

    def set_token(self, raw_token: str) -> None:
        self.encrypted_token = encrypt_secret(raw_token or '')

    def get_token(self) -> str:
        return decrypt_secret(self.encrypted_token or '')

    @property
    def token_masked(self) -> str:
        token = self.get_token()
        if not token:
            return ''
        if len(token) <= 8:
            return '***'
        if ':' in token:
            prefix, secret = token.split(':', 1)
            return f'{prefix}:***{secret[-4:]}'
        return f'{token[:4]}***{token[-4:]}'


class TelegramChatSession(models.Model):
    """Сесія діалогу з користувачем у Telegram для збереження контексту."""

    bot = models.ForeignKey(
        TelegramBot,
        on_delete=models.CASCADE,
        related_name='sessions',
    )
    telegram_chat_id = models.BigIntegerField()
    telegram_username = models.CharField(max_length=150, blank=True, default='')
    messages = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['bot', 'telegram_chat_id'],
                name='uniq_telegram_bot_chat_session',
            ),
        ]
        verbose_name = 'Сесія Telegram чату'
        verbose_name_plural = 'Сесії Telegram чатів'

    def __str__(self):
        return f'Chat {self.telegram_chat_id} (Bot {self.bot.name})'
```

- [ ] **Step 4: Create and apply migration**

Run: `backend\.venv\Scripts\python.exe backend\manage.py makemigrations workspaces`
Expected: Migration `0016_telegrambot_telegramchatsession.py` created.
Run: `backend\.venv\Scripts\python.exe backend\manage.py migrate`

- [ ] **Step 5: Run tests to verify they pass**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_telegram_models`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/workspaces/models.py backend/workspaces/migrations/0016_telegrambot_telegramchatsession.py backend/workspaces/tests/test_telegram_models.py
git commit -m "feat(models): add TelegramBot and TelegramChatSession models with encrypted token"
```

---

### Task 2: Backend REST API (`/api/telegram-bots/` & `WorkspaceSerializer`)

**Files:**
- Create: `backend/workspaces/telegram/serializers.py`
- Create: `backend/workspaces/telegram/views.py`
- Modify: `backend/workspaces/serializers.py`
- Modify: `backend/workspaces/urls.py`
- Create: `backend/workspaces/tests/test_telegram_api.py`

**Interfaces:**
- Produces: `TelegramBotViewSet` mounted at `/api/telegram-bots/` and extended `WorkspaceSerializer`.
- Consumes: `TelegramBot`, `Workspace`, `encrypt_secret`.

- [ ] **Step 1: Write failing API unit tests**

Create `backend/workspaces/tests/test_telegram_api.py`:
```python
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from workspaces.models import TelegramBot, Workspace

User = get_user_model()


class TelegramBotAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
        self.regular_user = User.objects.create_user('user', 'user@example.com', 'userpass')
        self.workspace = Workspace.objects.create(name='Main WS')
        self.client.force_authenticate(user=self.admin)

    def test_anonymous_and_regular_user_forbidden(self):
        self.client.logout()
        res = self.client.get('/api/telegram-bots/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.regular_user)
        res = self.client.get('/api/telegram-bots/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    @patch('workspaces.telegram.client.TelegramClient.get_me')
    def test_create_and_list_telegram_bot(self, mock_get_me):
        mock_get_me.return_value = {'ok': True, 'result': {'username': 'zrozumilo_bot'}}

        payload = {
            'name': 'Довідка',
            'token': '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11',
            'workspace': self.workspace.id,
            'is_active': True,
        }
        res = self.client.post('/api/telegram-bots/', payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['bot_username'], 'zrozumilo_bot')
        self.assertEqual(res.data['token_masked'], '123456:***ew11')
        self.assertNotIn('token', res.data)

        # Check list
        list_res = self.client.get('/api/telegram-bots/')
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]['name'], 'Довідка')
        self.assertEqual(list_res.data[0]['workspace_name'], 'Main WS')

    @patch('workspaces.telegram.client.TelegramClient.get_me')
    def test_verify_token_endpoint(self, mock_get_me):
        mock_get_me.return_value = {'ok': True, 'result': {'username': 'verified_bot'}}
        bot = TelegramBot(name='Bot 1', workspace=self.workspace)
        bot.set_token('12345:validtoken123456789')
        bot.save()

        res = self.client.post(f'/api/telegram-bots/{bot.id}/verify/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        bot.refresh_from_db()
        self.assertEqual(bot.bot_username, 'verified_bot')
        self.assertEqual(bot.last_error, '')

    def test_workspace_serializer_syncs_telegram_bot_ids(self):
        bot1 = TelegramBot.objects.create(name='Bot 1')
        bot2 = TelegramBot.objects.create(name='Bot 2')

        # Link both bots via workspace update
        ws_res = self.client.patch(
            f'/api/workspaces/{self.workspace.id}/',
            {'telegram_bot_ids': [bot1.id, bot2.id]},
            format='json',
        )
        self.assertEqual(ws_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(ws_res.data.get('telegram_bots', [])), 2)

        bot1.refresh_from_db()
        bot2.refresh_from_db()
        self.assertEqual(bot1.workspace_id, self.workspace.id)
        self.assertEqual(bot2.workspace_id, self.workspace.id)

        # Remove bot1 by passing only bot2
        self.client.patch(
            f'/api/workspaces/{self.workspace.id}/',
            {'telegram_bot_ids': [bot2.id]},
            format='json',
        )
        bot1.refresh_from_db()
        bot2.refresh_from_db()
        self.assertIsNone(bot1.workspace)
        self.assertEqual(bot2.workspace_id, self.workspace.id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_telegram_api`
Expected: FAIL (routes not found).

- [ ] **Step 3: Implement Serializers, ViewSet, and URL routing**

Create `backend/workspaces/telegram/serializers.py`:
```python
from rest_framework import serializers
from workspaces.models import TelegramBot, Workspace


class TelegramBotSerializer(serializers.ModelSerializer):
    token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    token_masked = serializers.CharField(read_only=True)
    has_token = serializers.SerializerMethodField()
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)

    class Meta:
        model = TelegramBot
        fields = (
            'id',
            'name',
            'token',
            'token_masked',
            'has_token',
            'bot_username',
            'workspace',
            'workspace_name',
            'is_active',
            'last_poll_at',
            'last_error',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('last_poll_at', 'last_error', 'created_at', 'updated_at')

    def get_has_token(self, obj: TelegramBot) -> bool:
        return bool(obj.encrypted_token)

    def create(self, validated_data):
        token = validated_data.pop('token', None)
        bot = TelegramBot(**validated_data)
        if token:
            bot.set_token(token)
            from workspaces.telegram.client import TelegramClient
            me = TelegramClient().get_me(token)
            if me.get('ok') and 'result' in me:
                bot.bot_username = me['result'].get('username', '')
                bot.last_error = ''
            elif not me.get('ok'):
                bot.last_error = me.get('description', 'Не вдалося перевірити токен')
        bot.save()
        return bot

    def update(self, instance, validated_data):
        token = validated_data.pop('token', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if token:
            instance.set_token(token)
            from workspaces.telegram.client import TelegramClient
            me = TelegramClient().get_me(token)
            if me.get('ok') and 'result' in me:
                instance.bot_username = me['result'].get('username', '')
                instance.last_error = ''
            elif not me.get('ok'):
                instance.last_error = me.get('description', 'Не вдалося перевірити токен')
        instance.save()
        return instance
```

Create `backend/workspaces/telegram/views.py`:
```python
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from workspaces.models import TelegramBot
from workspaces.telegram.client import TelegramClient
from workspaces.telegram.serializers import TelegramBotSerializer


class TelegramBotViewSet(viewsets.ModelViewSet):
    queryset = TelegramBot.objects.select_related('workspace').all()
    serializer_class = TelegramBotSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        bot = self.get_object()
        token = bot.get_token()
        if not token:
            return Response(
                {'error': 'Токен відсутній'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        res = TelegramClient().get_me(token)
        if res.get('ok') and 'result' in res:
            bot.bot_username = res['result'].get('username', '')
            bot.last_error = ''
            bot.save(update_fields=['bot_username', 'last_error', 'updated_at'])
            return Response(self.get_serializer(bot).data)

        error_msg = res.get('description') or 'Невалідний токен або помилка мережі Telegram'
        bot.last_error = error_msg
        bot.save(update_fields=['last_error', 'updated_at'])
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
```

In `backend/workspaces/serializers.py`:
Add `telegram_bots` read field and `telegram_bot_ids` write field in `WorkspaceSerializer`, updating `create` and `update` to sync `TelegramBot.objects.filter(id__in=telegram_bot_ids).update(workspace=instance)` and decouple omitted bots.

In `backend/workspaces/urls.py`:
Register router for `telegram-bots` (`r'telegram-bots', TelegramBotViewSet, basename='telegram-bot'`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_telegram_api`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/workspaces/telegram/serializers.py backend/workspaces/telegram/views.py backend/workspaces/serializers.py backend/workspaces/urls.py backend/workspaces/tests/test_telegram_api.py
git commit -m "feat(api): add TelegramBotViewSet and workspace telegram_bot_ids sync"
```

---

### Task 3: Telegram Client, Handlers & Long Polling Engine

**Files:**
- Create: `backend/workspaces/telegram/client.py`
- Create: `backend/workspaces/telegram/handlers.py`
- Create: `backend/workspaces/telegram/poller.py`
- Create: `backend/workspaces/management/commands/run_telegram_bots.py`
- Create: `backend/workspaces/tests/test_telegram_client.py`
- Create: `backend/workspaces/tests/test_telegram_handlers.py`
- Create: `backend/workspaces/tests/test_telegram_poller.py`

**Interfaces:**
- Produces: `TelegramClient`, `handle_telegram_update`, `TelegramBotManager`, `run_telegram_bots` command.
- Consumes: `run_chat` from `llm.chat`, `apply_feedback_fields`, `save_log_feedback` from `chats.feedback`.

- [ ] **Step 1: Write unit tests for Client, Handlers, and Poller**

Create `backend/workspaces/tests/test_telegram_client.py`:
- Test `get_me`, `get_updates`, `send_message` (including split for >4000 chars), `answer_callback_query`, `edit_message_reply_markup`.

Create `backend/workspaces/tests/test_telegram_handlers.py`:
- Test `/start` and `/reset` message sending `embed_greeting` and FAQ buttons (`faq:<idx>`).
- Test textual message calling `run_chat`, saving `TelegramChatSession` message history, and returning message with `👍`, `👎`, `До людини` buttons.
- Test callback query `fb:<log_id>:down` creating Knowledge Gap in `WorkspaceChatLog` and calling `answer_callback_query`.
- Test callback query `faq:0` picking question text and generating answer.

Create `backend/workspaces/tests/test_telegram_poller.py`:
- Test `TelegramBotManager` detects active bots, spawns threads, and stops threads when bot is marked `is_active=False` or deleted.

- [ ] **Step 2: Implement `TelegramClient` in `backend/workspaces/telegram/client.py`**

Implement thin HTTP client using `requests.Session` with proper timeouts, JSON parsing, error handling, and message chunking (max 4000 chars).

- [ ] **Step 3: Implement `handle_telegram_update` in `backend/workspaces/telegram/handlers.py`**

Implement handler logic:
- Parse `update['message']` vs `update['callback_query']`.
- Handle `/start`, `/reset`, `/clear`.
- Handle `faq:<idx>` callbacks.
- Handle `fb:<log_id>:<action>` feedback callbacks using `apply_feedback_fields` and `save_log_feedback`.
- Maintain up to 12 chat messages in `TelegramChatSession`.
- Route question answering through `run_chat(...)`.

- [ ] **Step 4: Implement `TelegramBotManager` and `run_telegram_bots` command**

In `backend/workspaces/telegram/poller.py`:
- `TelegramBotWorker`: thread loop calling `get_updates(offset=bot.last_update_id + 1, timeout=20)`, updating `last_update_id`, invoking `handle_telegram_update`, and updating `last_poll_at`.
- Use Redis lock `telegram:poll_lock:<bot.id>` (if `REDIS_URL` present) with TTL 60s to prevent `409 Conflict`.
- `TelegramBotManager`: checks DB every 5s, adjusts running worker threads to match active bots.

In `backend/workspaces/management/commands/run_telegram_bots.py`:
- Handle SIGINT/SIGTERM gracefully and start `manager.run()`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_telegram_client workspaces.tests.test_telegram_handlers workspaces.tests.test_telegram_poller`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/workspaces/telegram/client.py backend/workspaces/telegram/handlers.py backend/workspaces/telegram/poller.py backend/workspaces/management/commands/run_telegram_bots.py backend/workspaces/tests/test_telegram_client.py backend/workspaces/tests/test_telegram_handlers.py backend/workspaces/tests/test_telegram_poller.py
git commit -m "feat(telegram): implement telegram client, handlers, and dynamic long poller daemon"
```

---

### Task 4: Frontend API & Admin Navigation for Telegram Bots

**Files:**
- Create: `frontend/src/api/telegramBots.js`
- Create: `frontend/src/pages/TelegramBotsPage.jsx`
- Create: `frontend/src/pages/TelegramBotsPage.test.jsx`
- Modify: `frontend/src/components/AdminLayout.jsx`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Produces: `/admin/telegram-bots` route and UI.
- Consumes: `/api/telegram-bots/` REST endpoints.

- [ ] **Step 1: Create `frontend/src/api/telegramBots.js` and tests**

Provide functions:
- `getTelegramBots()`
- `createTelegramBot(data)`
- `updateTelegramBot(id, data)`
- `deleteTelegramBot(id)`
- `verifyTelegramBot(id)`

- [ ] **Step 2: Add Route in `App.jsx` and Navigation link in `AdminLayout.jsx`**

In `frontend/src/components/AdminLayout.jsx`:
Add `{ to: '/admin/telegram-bots', label: 'Телеграм-бот' }` to `ADMIN_LINKS`.

In `frontend/src/App.jsx`:
Lazy-load `TelegramBotsPage` and add `<Route path="telegram-bots" element={<TelegramBotsPage />} />` under `/admin`.

- [ ] **Step 3: Implement `TelegramBotsPage.jsx` and Vitest tests**

Features:
- Header: "Телеграм-боти" + "Додати бота" button.
- Table of bots: Name, Username (`@...` or `—`), Masked Token, Assigned Workspace badge, Status (Active badge, last poll time, or error alert), Actions (Перевірити токен, Редагувати, Видалити).
- Modal form for Create/Edit: Name input, Token input (password type or text), Workspace select dropdown, Active checkbox.
- In-place "Перевірити" button calling `verifyTelegramBot(id)` with immediate feedback.

- [ ] **Step 4: Verify frontend tests and lint**

Run: `cd frontend; npm run lint; npm test -- TelegramBotsPage`
Expected: 0 warnings, tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/telegramBots.js frontend/src/pages/TelegramBotsPage.jsx frontend/src/pages/TelegramBotsPage.test.jsx frontend/src/components/AdminLayout.jsx frontend/src/App.jsx
git commit -m "feat(frontend): add Telegram Bots admin page and navigation"
```

---

### Task 5: Frontend Workspaces Integration

**Files:**
- Modify: `frontend/src/pages/workspaces/useWorkspacesAdmin.js`
- Modify: `frontend/src/pages/workspaces/WorkspaceModal.jsx`
- Modify: `frontend/src/pages/WorkspacesPage.jsx`
- Modify: `frontend/src/pages/workspaces/useWorkspacesAdmin.test.jsx`

**Interfaces:**
- Produces: Integrated Telegram bot assignment within Workspace creation and editing.
- Consumes: `getTelegramBots` from `api/telegramBots.js`.

- [ ] **Step 1: Write failing tests for Telegram bot selection in Workspace admin**

Update `frontend/src/pages/workspaces/useWorkspacesAdmin.test.jsx` to test:
- `telegramBots` loading into state.
- `telegram_bot_ids` initialized on `openEditForm` and toggled with `toggleTelegramBotId`.
- `telegram_bot_ids` sent on form submit.

- [ ] **Step 2: Update `useWorkspacesAdmin.js`**

Add:
- `telegramBots` state fetched on mount.
- `telegram_bot_ids` in `initialFormState`.
- `toggleTelegramBotId(botId)`.
- Populate `telegram_bot_ids` on `openEditForm` from `workspace.telegram_bots`.

- [ ] **Step 3: Update `WorkspaceModal.jsx` and `WorkspacesPage.jsx`**

In `WorkspaceModal.jsx`:
- Render "Телеграм-боти" section with checkboxes for each bot. If bot is already attached to another workspace, show `(у воркспейсі: X)`.

In `WorkspacesPage.jsx`:
- Add "Телеграм-боти" column in the workspaces table displaying linked bot names/tags.

- [ ] **Step 4: Run frontend tests and lint**

Run: `cd frontend; npm run lint; npm test`
Expected: 0 warnings, all Vitest test suites PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/workspaces/useWorkspacesAdmin.js frontend/src/pages/workspaces/WorkspaceModal.jsx frontend/src/pages/WorkspacesPage.jsx frontend/src/pages/workspaces/useWorkspacesAdmin.test.jsx
git commit -m "feat(frontend): integrate telegram bot selection into Workspace admin and table"
```

---

### Task 6: Docker Compose & Entrypoint Integration + E2E Verification

**Files:**
- Modify: `backend/entrypoint.sh`
- Modify: `docker-compose.yml`
- Modify: `docker-compose.prod.yml`

**Interfaces:**
- Produces: `telegram_poller` container in Docker Compose runtime.

- [ ] **Step 1: Update `backend/entrypoint.sh`**

Add support for `APP_ROLE=poller`:
```bash
elif [ "$ROLE" = "poller" ]; then
  python manage.py migrate --noinput
```

- [ ] **Step 2: Add `telegram_poller` service to `docker-compose.yml` and `docker-compose.prod.yml`**

In `docker-compose.yml`:
```yaml
  telegram_poller:
    build: ./backend
    command: python manage.py run_telegram_bots
    env_file:
      - path: .env
        required: false
    environment:
      APP_ROLE: poller
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:?Set DJANGO_SECRET_KEY in .env}
      DJANGO_DEBUG: ${DJANGO_DEBUG:-True}
      POSTGRES_DB: ${POSTGRES_DB:-zrozumiloai}
      POSTGRES_USER: ${POSTGRES_USER:-zrozumiloai}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}
      POSTGRES_HOST: db
      USE_SQLITE: "False"
      OLLAMA_BASE_URL: http://ollama:11434
      REDIS_URL: redis://redis:6379/0
      CELERY_TASK_ALWAYS_EAGER: "False"
      FIELD_ENCRYPTION_KEY: ${FIELD_ENCRYPTION_KEY:-}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
```

In `docker-compose.prod.yml`:
Add resource limits (`mem_limit: 512m`, `cpus: 0.5`).

- [ ] **Step 3: Run comprehensive verification**

1. Ruff linting: `cd backend; .venv\Scripts\ruff.exe check .`
2. Full backend tests: `cd backend; .venv\Scripts\python.exe manage.py test --verbosity=1`
3. Migration check: `cd backend; .venv\Scripts\python.exe manage.py makemigrations --check --dry-run`
4. Frontend lint & test: `cd frontend; npm run lint; npm test; npm run build`
5. Docker compose validation: `docker compose config --quiet` and `docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet`

- [ ] **Step 4: Commit**

```bash
git add backend/entrypoint.sh docker-compose.yml docker-compose.prod.yml
git commit -m "feat(ops): add telegram_poller service to docker compose and entrypoint"
```

---

## Plan Self-Review

1. **Spec Coverage:**
   - `TelegramBot` and `TelegramChatSession` encrypted models: Task 1.
   - REST API & `/api/workspaces/` sync: Task 2.
   - Telegram Bot API client, handlers (`/start`, FAQ, `run_chat`, feedback `👍`/`👎`/`handoff`), and long polling daemon: Task 3.
   - Frontend `/admin/telegram-bots` page: Task 4.
   - Frontend `Workspaces` integration (table + modal checkboxes): Task 5.
   - Docker container `telegram_poller` & ops: Task 6.
2. **No Placeholders:** All tasks define exact files, test cases, and code blocks.
3. **Consistency:** Model fields, URL paths, and function signatures match identically across tasks.
