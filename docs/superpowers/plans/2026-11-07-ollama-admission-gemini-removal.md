# Local Ollama Admission and Gemini Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Прибрати Gemini повністю і поставити один слот Ollama, щоб другий паралельний чат одразу отримував `429` / `ollama_busy`, не викликаючи модель.

**Architecture:** Міграція переводить workspace на `ollama` і видаляє `gemini_api_key`. Фабрика завжди повертає `OllamaProvider`. `run_chat` перед `provider.chat` бере Redis-ключ `ollama:admission` (`SET NX EX 180`) і відпускає його своїм токеном. Зайнятий слот — JSON `429`, не SSE і не Gemini.

**Tech Stack:** Python 3.12, Django 5, DRF, django-redis, React 18, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-07-ollama-admission-gemini-removal-design.md`

## Global Constraints

- Порядок: спочатку Gemini (завдання 1–7), потім слот (завдання 8–10).
- Чат і embeddings лише через Ollama. Meilisearch лишається пошуком курсів.
- Адмін як і раніше може pull будь-якої моделі Ollama.
- Ingest і embeddings слот не беруть.
- Текст зайнятості дослівно: `Модель зайнята. Спробуйте ще раз за хвилину.`
- Код відповіді: `ollama_busy`. Статус `429`. Заголовок `Retry-After: 60`. Автоповтору немає.
- Ключ Redis: `ollama:admission`. TTL `180`. Ліміт цього циклу — рівно один власник (`OLLAMA_ADMISSION_LIMIT=1`), не лічильник.
- Порожній `REDIS_URL` (локальний file cache) — слот не береться і warning немає. Помилка `SET`, коли `REDIS_URL` задано — warning і чат без слота.
- Єдині дозволені згадки `gemini` після циклу: історичні міграції `0007` і `0008`, каталог `docs/superpowers/`, і порівняння збереженого `presetId === 'gemini'` у `frontend/src/themes/presets.js`. Видима назва теми «Google Gemini» зникає.
- Повідомлення студенту з `code === 'ollama_busy'` без префікса `Помилка:`.

---

### Task 1: Прибрати Gemini зі схеми workspace

**Files:**
- Create: `backend/workspaces/llm_cleanup.py`
- Create: `backend/workspaces/migrations/0014_remove_gemini.py`
- Create: `backend/workspaces/tests/test_llm_cleanup.py`
- Modify: `backend/workspaces/models.py`

**Interfaces:**
- Consumes: рядки `llm_provider`, список `model_names`
- Produces: `rewrite_llm_fields(provider: str, model_names: list) -> tuple[str, list]`. Імена, чия база входить у `gemini-2.0-flash`, `gemini-2.5-flash-lite`, `gemini-1.5-flash`, відкидаються. `provider == 'gemini'` стає `'ollama'`.

- [ ] **Step 1: Write the failing test**

```python
from django.test import TestCase

from workspaces.llm_cleanup import rewrite_llm_fields
from workspaces.models import Workspace


class RewriteLlmFieldsTests(TestCase):
    def test_gemini_provider_and_model_names_become_ollama(self):
        provider, names = rewrite_llm_fields(
            'gemini',
            ['gemini-2.0-flash', 'llama3.2:latest', 'gemini-1.5-flash:001'],
        )
        self.assertEqual(provider, 'ollama')
        self.assertEqual(names, ['llama3.2:latest'])

    def test_ollama_names_stay(self):
        provider, names = rewrite_llm_fields('ollama', ['llama3.2'])
        self.assertEqual(provider, 'ollama')
        self.assertEqual(names, ['llama3.2'])

    def test_model_has_no_gemini_api_key(self):
        field_names = {field.name for field in Workspace._meta.fields}
        self.assertNotIn('gemini_api_key', field_names)
        self.assertNotIn('gemini', Workspace.LLMProvider.values)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/workspaces/tests/test_llm_cleanup.py -v`

Expected: FAIL with `ModuleNotFoundError: workspaces.llm_cleanup`

- [ ] **Step 3: Write minimal implementation**

`backend/workspaces/llm_cleanup.py`:

```python
GEMINI_MODEL_BASES = frozenset({
    'gemini-2.0-flash',
    'gemini-2.5-flash-lite',
    'gemini-1.5-flash',
})


def rewrite_llm_fields(provider, model_names):
    """Повернути (provider, model_names) без Gemini."""
    cleaned = []
    for name in model_names or []:
        base = str(name).split(':', 1)[0].strip()
        if base not in GEMINI_MODEL_BASES:
            cleaned.append(name)
    if provider == 'gemini':
        provider = 'ollama'
    return provider or 'ollama', cleaned
```

У `Workspace.LLMProvider` лишити тільки `OLLAMA = 'ollama', 'Ollama'`. Видалити поле `gemini_api_key`.

`backend/workspaces/migrations/0014_remove_gemini.py`:

```python
from django.db import migrations, models

from workspaces.llm_cleanup import rewrite_llm_fields


def forwards(apps, schema_editor):
    Workspace = apps.get_model('workspaces', 'Workspace')
    for workspace in Workspace.objects.all().iterator():
        provider, names = rewrite_llm_fields(
            workspace.llm_provider,
            workspace.model_names,
        )
        if provider != workspace.llm_provider or list(names) != list(workspace.model_names or []):
            workspace.llm_provider = provider
            workspace.model_names = names
            workspace.save(update_fields=['llm_provider', 'model_names'])


class Migration(migrations.Migration):
    dependencies = [
        ('workspaces', '0013_documentchunk_hnsw_index'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='workspace',
            name='gemini_api_key',
        ),
        migrations.AlterField(
            model_name='workspace',
            name='llm_provider',
            field=models.CharField(
                choices=[('ollama', 'Ollama')],
                default='ollama',
                max_length=20,
            ),
        ),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/workspaces/tests/test_llm_cleanup.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/workspaces/llm_cleanup.py backend/workspaces/migrations/0014_remove_gemini.py backend/workspaces/tests/test_llm_cleanup.py backend/workspaces/models.py
git commit -m "feat(workspaces): drop Gemini provider and API key from workspace schema"
```

---

### Task 2: Відхиляти Gemini у серіалізаторі workspace

**Files:**
- Modify: `backend/workspaces/serializers.py`
- Modify: `backend/workspaces/tests/test_serializers.py`

**Interfaces:**
- Consumes: `Workspace.LLMProvider` лише `ollama`
- Produces: `WorkspaceSerializer` без полів `gemini_api_key` і `gemini_api_key_set`. Тіло з `llm_provider=gemini` або з ключем `gemini_api_key` (навіть порожнім) — невалідне. Відсутній `llm_provider` лишається валідним.

- [ ] **Step 1: Replace Gemini serializer tests**

Видалити `test_gemini_requires_api_key_with_model`, `test_gemini_accepts_workspace_key`, `test_gemini_rejects_non_gemini_model` і `GEMINI_*` з `@override_settings`. Додати:

```python
def test_rejects_gemini_provider(self):
    serializer = WorkspaceSerializer(data={
        'name': 'Local',
        'llm_provider': 'gemini',
        'model_names': ['llama3.2'],
    })
    self.assertFalse(serializer.is_valid())
    self.assertIn('llm_provider', serializer.errors)

def test_rejects_gemini_api_key_even_when_blank(self):
    serializer = WorkspaceSerializer(data={
        'name': 'Local',
        'model_names': ['llama3.2'],
        'gemini_api_key': '',
    })
    self.assertFalse(serializer.is_valid())
    self.assertIn('gemini_api_key', serializer.errors)

def test_ollama_workspace_without_provider_is_valid(self):
    serializer = WorkspaceSerializer(data={
        'name': 'Local',
        'model_names': ['llama3.2'],
    })
    self.assertTrue(serializer.is_valid(), serializer.errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/workspaces/tests/test_serializers.py -k "rejects_gemini or ollama_workspace_without_provider" -v`

Expected: FAIL (`gemini_api_key` ще приймається або `llm_provider=gemini` валідний)

- [ ] **Step 3: Write minimal implementation**

Прибрати поля `gemini_api_key`, `gemini_api_key_set`, метод `get_gemini_api_key_set`, `_apply_gemini_api_key` і всі гілки `GEMINI` у `validate`, `create`, `update`.

На початку `validate`:

```python
def validate(self, attrs):
    initial = getattr(self, 'initial_data', {}) or {}
    if 'gemini_api_key' in initial:
        raise serializers.ValidationError({
            'gemini_api_key': 'Gemini більше не підтримується',
        })
    llm_provider = attrs.get(
        'llm_provider',
        getattr(self.instance, 'llm_provider', Workspace.LLMProvider.OLLAMA),
    )
    if llm_provider != Workspace.LLMProvider.OLLAMA:
        raise serializers.ValidationError({
            'llm_provider': 'Підтримується лише Ollama',
        })
    # далі лишається наявна валідація Meilisearch
```

`validate_llm_provider` лишає перевірку проти `LLM_PROVIDER_CHOICES` (там уже лише `ollama`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/workspaces/tests/test_serializers.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/workspaces/serializers.py backend/workspaces/tests/test_serializers.py
git commit -m "fix(workspaces): reject Gemini provider and API key on workspace write"
```

---

### Task 3: Фабрика лише Ollama

**Files:**
- Modify: `backend/llm/factory.py`
- Modify: `backend/llm/tests/test_factory.py`
- Delete: `backend/llm/gemini_provider.py`
- Delete: `backend/llm/tests/test_gemini_provider.py`

**Interfaces:**
- Consumes: `OllamaProvider`
- Produces: `resolve_provider(workspace=None, model_name='') -> OllamaProvider`. `list_all_models() -> {'models': list}` лише з Ollama. Функцій `is_gemini_model` і `list_gemini_models` немає.

- [ ] **Step 1: Replace factory tests**

```python
from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from llm.factory import list_all_models, resolve_provider
from llm.ollama_provider import OllamaProvider


class ListAllModelsTests(SimpleTestCase):
    @patch('llm.factory.OllamaProvider')
    def test_includes_only_ollama_models(self, mock_provider_cls):
        mock_provider_cls.return_value.list_models.return_value = {
            'models': [{'name': 'llama3', 'size': 100}],
        }
        data = list_all_models()
        names = [model['name'] for model in data['models']]
        self.assertEqual(names, ['llama3'])
        self.assertEqual(data['models'][0]['provider'], 'ollama')

    @patch('llm.factory.OllamaProvider')
    def test_ollama_failure_returns_empty_list(self, mock_provider_cls):
        mock_provider_cls.return_value.list_models.side_effect = (
            requests.RequestException('down')
        )
        data = list_all_models()
        self.assertEqual(data['models'], [])


class ResolveProviderTests(SimpleTestCase):
    def test_gemini_model_name_still_uses_ollama(self):
        provider = resolve_provider(model_name='gemini-2.0-flash')
        self.assertIsInstance(provider, OllamaProvider)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/llm/tests/test_factory.py -v`

Expected: FAIL (`ImportError` або в списку ще є `gemini-2.0-flash`)

- [ ] **Step 3: Write minimal implementation**

Замінити `backend/llm/factory.py` на:

```python
"""Фабрика LLM-провайдерів. Єдиний провайдер — Ollama."""
import logging

import requests

from .ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


def resolve_provider(workspace=None, model_name=''):
    """Завжди повернути Ollama. Аргументи лишаються для викликів run_chat."""
    del workspace, model_name
    return OllamaProvider()


def list_all_models():
    """Зібрати моделі Ollama."""
    models = []
    try:
        data = OllamaProvider().list_models()
        for model in data.get('models', []):
            entry = dict(model)
            entry['provider'] = OllamaProvider.provider_id
            models.append(entry)
    except requests.RequestException as exc:
        logger.warning('Не вдалося отримати моделі Ollama: %s', exc)
    return {'models': models}
```

Видалити `backend/llm/gemini_provider.py` і `backend/llm/tests/test_gemini_provider.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/llm/tests/test_factory.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/llm/factory.py backend/llm/tests/test_factory.py backend/llm/gemini_provider.py backend/llm/tests/test_gemini_provider.py
git commit -m "feat(llm): resolve every chat through Ollama only"
```

---

### Task 4: Прибрати fallback з чату

**Files:**
- Modify: `backend/llm/chat.py`
- Modify: `backend/llm/tests/test_chat.py`
- Modify: `backend/workspaces/services.py`
- Modify: `backend/workspaces/tests/test_services.py`
- Delete: `backend/llm/tests/test_chat_fallback.py`

**Interfaces:**
- Consumes: `resolve_provider` з завдання 3
- Produces: `run_chat` без `get_fallback_provider`. Помилка Ollama — `503` і поле `error`. Функції `get_gemini_api_key` немає.

- [ ] **Step 1: Write the failing test and delete fallback tests**

У `test_non_stream_provider_error` замінити очікуваний текст на `Ollama недоступний` і той самий рядок у `side_effect`. Видалити файл `backend/llm/tests/test_chat_fallback.py`. Видалити з `test_services.py` імпорт `get_gemini_api_key` і три тести `test_get_gemini_api_key_*`.

Додати в `RunChatTests`:

```python
@patch('llm.chat.resolve_provider')
@patch('llm.chat.prepare_chat_messages')
def test_provider_error_does_not_call_a_second_provider(self, mock_prepare, mock_resolve):
    mock_prepare.return_value = ([{'role': 'user', 'content': 'Hi'}], [])
    provider = MagicMock()
    provider.chat.side_effect = LLMProviderError('Ollama недоступний')
    mock_resolve.return_value = provider

    response = run_chat(
        model='llama3',
        messages=[{'role': 'user', 'content': 'Hi'}],
        stream=False,
        workspace=self.workspace,
        user=self.user,
        prompt='Hi',
    )

    self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
    self.assertEqual(response.data['error'], 'Ollama недоступний')
    self.assertNotIn('provider_fallback', response.data)
    provider.chat.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/llm/tests/test_chat.py::RunChatTests::test_provider_error_does_not_call_a_second_provider -v`

Expected: FAIL під час імпорту `llm.chat` з `ModuleNotFoundError: No module named 'llm.gemini_provider'`

- [ ] **Step 3: Write minimal implementation**

Видалити з `chat.py` імпорт `GeminiProvider` і функцію `get_fallback_provider`. Видалити `get_gemini_api_key` з `workspaces/services.py`.

У стрімі прибрати `fallback_used`, `active_model` і гілку fallback. `except (LLMProviderError, requests.RequestException)` одразу логірує warning і робить `yield _provider_error_response(exc, stream=True)`, потім `return`. З фінального `meta` прибрати `provider_fallback`.

У non-stream `except` одразу `return _provider_error_response(exc, stream=False)`. Не викликати другого провайдера. Не додавати `provider_fallback` у JSON.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/llm/tests/test_chat.py backend/workspaces/tests/test_services.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/llm/chat.py backend/llm/tests/test_chat.py backend/llm/tests/test_chat_fallback.py backend/workspaces/services.py backend/workspaces/tests/test_services.py
git commit -m "fix(llm): return 503 when Ollama fails instead of calling Gemini"
```

---

### Task 5: Прибрати Gemini з конфігурації і health

**Files:**
- Modify: `backend/config/settings.py`
- Modify: `backend/ollama_proxy/views.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `backend/llm/__init__.py`
- Modify: `backend/llm/base.py`
- Modify: `backend/llm/ollama_provider.py`
- Modify: `backend/workspaces/rag/search_context.py`

**Interfaces:**
- Consumes: `OllamaProvider.health()`
- Produces: `GET` health провайдера без ключа `gemini`. У settings немає `GEMINI_API_KEY` і `GEMINI_MODEL_NAMES`.

- [ ] **Step 1: Write the failing test**

Додати в `backend/llm/tests/test_factory.py` не треба. Створити `backend/ollama_proxy/tests/test_health.py`:

```python
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()


class OllamaHealthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='health_user', password='pass')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('ollama_proxy.views.OllamaProvider')
    def test_health_has_no_gemini(self, mock_provider_cls):
        mock_provider_cls.return_value.health.return_value = True
        mock_provider_cls.return_value.base_url = 'http://ollama:11434'
        response = self.client.get(reverse('ollama_health'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('gemini', response.data)
        self.assertTrue(response.data['ollama']['connected'])
```

URL name уже є: `ollama_health` у `backend/ollama_proxy/urls.py`. Новий path не додавати.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/ollama_proxy/tests/test_health.py -v`

Expected: FAIL (`gemini` є у відповіді або `ImportError` на `GeminiProvider`)

- [ ] **Step 3: Write minimal implementation**

У `OllamaHealthView.get` прибрати `GeminiProvider`. Відповідь:

```python
ollama = OllamaProvider()
ollama_ok = ollama.health()
return Response({
    'connected': ollama_ok,
    'base_url': ollama.base_url,
    'ollama': {
        'connected': ollama_ok,
        'base_url': ollama.base_url,
    },
})
```

Видалити з `settings.py` блок `GEMINI_API_KEY` і `GEMINI_MODEL_NAMES`. Видалити ті самі змінні з `.env.example` і з сервісів `backend` та `worker` у `docker-compose.yml`.

Замінити згадки Gemini у docstring:

- `backend/llm/__init__.py`: `"""Абстракція LLM-провайдера Ollama."""`
- `backend/llm/base.py`: `"""Спільний контракт провайдера чату."""`
- `backend/llm/ollama_provider.py`: прибрати «чи Gemini» з коментаря
- `backend/workspaces/rag/search_context.py`: коментар замінити на `Embeddings завжди йдуть через Ollama.`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/ollama_proxy/tests/test_health.py backend/llm/tests/test_factory.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/config/settings.py backend/ollama_proxy/views.py backend/ollama_proxy/tests/test_health.py .env.example docker-compose.yml backend/llm/__init__.py backend/llm/base.py backend/llm/ollama_provider.py backend/workspaces/rag/search_context.py
git commit -m "chore(config): remove Gemini settings and health payload"
```

---

### Task 6: Прибрати Gemini з панелі

**Files:**
- Modify: `frontend/src/pages/WorkspacesPage.jsx`
- Modify: `frontend/src/themes/presets.js`
- Modify: `frontend/src/themes/presets.test.js`

**Interfaces:**
- Consumes: список моделей Ollama (`model.provider === 'ollama'` або без provider)
- Produces: форма workspace не має селекта провайдера і поля ключа Gemini. У payload немає `llm_provider` і `gemini_api_key`. Тема з колишнім id `gemini` має id `blue`, видима назва не містить Gemini. `presetId` `gemini` і `openai` резолвляться в `THEME_PRESETS.blue`.

- [ ] **Step 1: Write the failing test**

У `presets.test.js` замінити тест `мапить legacy openai на gemini`:

```javascript
it('мапить збережені presetId openai і gemini на blue', () => {
  const fromOpenAI = resolveThemeVars({ type: 'preset', presetId: 'openai' });
  const fromGemini = resolveThemeVars({ type: 'preset', presetId: 'gemini' });
  expect(fromOpenAI['--color-primary']).toBe(THEME_PRESETS.blue.vars['--color-primary']);
  expect(fromGemini['--color-primary']).toBe(THEME_PRESETS.blue.vars['--color-primary']);
  expect(THEME_PRESETS.blue.name).not.toMatch(/gemini/i);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/themes/presets.test.js`

Working directory: `frontend`

Expected: FAIL (`THEME_PRESETS.blue` is undefined)

- [ ] **Step 3: Write minimal implementation**

У `presets.js` перейменувати ключ пресета `gemini` на `blue`. `name` поставити `Синій`. У `resolveThemeVars` замінити fallback:

```javascript
const legacyBlue = state.presetId === 'openai' || state.presetId === 'gemini';
const preset = THEME_PRESETS[state.presetId]
  || (legacyBlue ? THEME_PRESETS.blue : undefined)
  || THEME_PRESETS[DEFAULT_PRESET_ID];
```

У `WorkspacesPage.jsx`:

- Прибрати з initial form і `openEditForm` поля `llm_provider`, `gemini_api_key`, `gemini_api_key_set`.
- Видалити `handleProviderChange`.
- Не класти в payload `llm_provider` і `gemini_api_key`.
- Видалити блок `<label>LLM провайдер</label>` разом із умовою `form.llm_provider === 'gemini'`.
- Список моделей фільтрувати так: `(model.provider || 'ollama') === 'ollama'`.
- Порожній список: текст `Немає встановлених моделей Ollama`.
- Прибрати колонку «Провайдер» з `<th>` і відповідну `<td>`.

`ChatPage.jsx` і `ModelSelector.jsx` рядка Gemini не містять. Не рефакторити їх у цьому завданні.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/themes/presets.test.js`

Working directory: `frontend`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/WorkspacesPage.jsx frontend/src/themes/presets.js frontend/src/themes/presets.test.js
git commit -m "feat(frontend): remove Gemini provider from workspace form"
```

---

### Task 7: Оновити README і перевірити, що Gemini не лишився

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: немає
- Produces: README описує лише Ollama для чату й embeddings. Рядки `GEMINI_API_KEY` і fallback Ollama → Gemini відсутні.

- [ ] **Step 1: Write the failing check**

Цей крок — пошук, не новий тест-раннер. Запустити з кореня репозиторія:

```powershell
rg -n -i "gemini" -g "!docs/superpowers/**" -g "!backend/workspaces/migrations/0007_workspace_llm_provider.py" -g "!backend/workspaces/migrations/0008_workspace_gemini_api_key.py" -g "!frontend/src/themes/presets.js"
```

Expected: є збіги в `README.md` і, якщо завдання 1–6 неповні, у коді.

- [ ] **Step 2: Update README**

Замінити перший абзац можливостей: чат через Ollama, без Google Gemini і без fallback. У швидкому старті прибрати `GEMINI_API_KEY` зі списку секретів. Прибрати речення, що embeddings ідуть через Ollama навіть для Gemini. У структурі `llm/` написати `Провайдер Ollama`. Інші збіги з кроку 1 у README прибрати або переписати так, щоб слова Gemini не було.

- [ ] **Step 3: Re-run the search**

Та сама команда `rg`.

Expected: збігів немає. Дозволений збіг лише всередині `frontend/src/themes/presets.js` на порівняння `presetId === 'gemini'`, і він виключений глобом.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: describe Ollama as the only chat provider"
```

---

### Task 8: Слот допуску Ollama

**Files:**
- Create: `backend/llm/admission.py`
- Create: `backend/llm/tests/test_admission.py`
- Modify: `backend/config/settings.py`

**Interfaces:**
- Consumes: Redis-клієнт із методами `set(key, value, nx=True, ex=180)` і `eval(script, 1, key, token)`. `set` повертає правдиве значення, якщо ключ записано, і `None`, якщо `NX` не пройшов.
- Produces:
  - `OllamaBusy(Exception)`
  - `OLLAMA_BUSY_MESSAGE = 'Модель зайнята. Спробуйте ще раз за хвилину.'`
  - `OLLAMA_BUSY_CODE = 'ollama_busy'`
  - `RETRY_AFTER_SECONDS = '60'`
  - `acquire_ollama_slot(client=None) -> str | None` — токен, якщо слот взято; `None`, якщо fail-open; виняток `OllamaBusy`, якщо слот зайнятий
  - `release_ollama_slot(token, client=None) -> None` — `token is None` нічого не робить; чужий токен ключ не знімає

- [ ] **Step 1: Write the failing test**

```python
import logging
from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from llm.admission import (
    ADMISSION_KEY,
    OllamaBusy,
    acquire_ollama_slot,
    release_ollama_slot,
)


class FakeRedis:
    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def eval(self, script, numkeys, key, token):
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0


class AdmissionTests(SimpleTestCase):
    def test_second_acquire_is_busy_and_wrong_token_does_not_release(self):
        client = FakeRedis()
        token = acquire_ollama_slot(client=client)
        self.assertTrue(token)
        with self.assertRaises(OllamaBusy):
            acquire_ollama_slot(client=client)
        release_ollama_slot('other-token', client=client)
        self.assertIn(ADMISSION_KEY, client.store)
        release_ollama_slot(token, client=client)
        self.assertNotIn(ADMISSION_KEY, client.store)

    def test_redis_error_fails_open_with_warning(self):
        client = MagicMock()
        client.set.side_effect = ConnectionError('redis down')
        with override_settings(REDIS_URL='redis://localhost:6379/0'):
            with self.assertLogs('llm.admission', level=logging.WARNING):
                token = acquire_ollama_slot(client=client)
        self.assertIsNone(token)

    @override_settings(REDIS_URL='')
    def test_missing_redis_url_fails_open_without_client(self):
        token = acquire_ollama_slot(client=None)
        self.assertIsNone(token)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/llm/tests/test_admission.py -v`

Expected: FAIL with `ModuleNotFoundError: llm.admission`

- [ ] **Step 3: Write minimal implementation**

У `settings.py` після `OLLAMA_BASE_URL`:

```python
OLLAMA_ADMISSION_LIMIT = 1
OLLAMA_ADMISSION_TTL_SECONDS = int(os.getenv('OLLAMA_ADMISSION_TTL_SECONDS', '180'))
```

`backend/llm/admission.py`:

```python
"""Один одночасний чат на інстанс Ollama."""
import logging
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)

ADMISSION_KEY = 'ollama:admission'
OLLAMA_BUSY_MESSAGE = 'Модель зайнята. Спробуйте ще раз за хвилину.'
OLLAMA_BUSY_CODE = 'ollama_busy'
RETRY_AFTER_SECONDS = '60'
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


class OllamaBusy(Exception):
    """Слот генерації вже зайнятий."""


def acquire_ollama_slot(client=None):
    """Повернути токен власника, None для fail-open, або кинути OllamaBusy."""
    if client is None and not (getattr(settings, 'REDIS_URL', '') or '').strip():
        return None
    redis_client = client
    try:
        if redis_client is None:
            from django_redis import get_redis_connection
            redis_client = get_redis_connection('default')
        token = uuid.uuid4().hex
        ttl = int(getattr(settings, 'OLLAMA_ADMISSION_TTL_SECONDS', 180))
        written = redis_client.set(ADMISSION_KEY, token, nx=True, ex=ttl)
    except Exception as exc:
        logger.warning('Ollama admission unavailable, failing open: %s', exc)
        return None
    if not written:
        raise OllamaBusy()
    return token


def release_ollama_slot(token, client=None):
    """Зняти слот лише своїм токеном."""
    if not token:
        return
    try:
        redis_client = client
        if redis_client is None:
            from django_redis import get_redis_connection
            redis_client = get_redis_connection('default')
        redis_client.eval(_RELEASE_LUA, 1, ADMISSION_KEY, token)
    except Exception as exc:
        logger.warning('Ollama admission release failed: %s', exc)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/llm/tests/test_admission.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/llm/admission.py backend/llm/tests/test_admission.py backend/config/settings.py
git commit -m "feat(llm): add a single Redis admission slot for Ollama chat"
```

---

### Task 9: Повернути 429 з run_chat і не дати віджету з’їсти його

**Files:**
- Modify: `backend/llm/chat.py`
- Modify: `backend/llm/tests/test_chat.py`
- Modify: `backend/workspaces/tests/test_roadmap_regressions.py`

**Interfaces:**
- Consumes: `acquire_ollama_slot`, `release_ollama_slot`, `OllamaBusy`, `OLLAMA_BUSY_MESSAGE`, `OLLAMA_BUSY_CODE`, `RETRY_AFTER_SECONDS`
- Produces: якщо `acquire_ollama_slot` кидає `OllamaBusy`, `run_chat` повертає DRF `Response` зі статусом 429, тілом `{'error': OLLAMA_BUSY_MESSAGE, 'code': 'ollama_busy'}` і заголовком `Retry-After: 60`. Ollama не викликається. Після успіху і після винятку провайдера слот звільняється переданим токеном. Стрім при зайнятому слоті не є `StreamingHttpResponse`.

- [ ] **Step 1: Write the failing test**

У `backend/llm/tests/test_chat.py`:

```python
from llm.admission import OllamaBusy

@patch('llm.chat.release_ollama_slot')
@patch('llm.chat.acquire_ollama_slot', side_effect=OllamaBusy())
@patch('llm.chat.resolve_provider')
@patch('llm.chat.prepare_chat_messages')
def test_busy_slot_returns_json_429_without_calling_ollama(
    self, mock_prepare, mock_resolve, mock_acquire, mock_release,
):
    mock_prepare.return_value = ([{'role': 'user', 'content': 'Hi'}], [])
    provider = MagicMock()
    mock_resolve.return_value = provider

    response = run_chat(
        model='llama3',
        messages=[{'role': 'user', 'content': 'Hi'}],
        stream=True,
        workspace=self.workspace,
        user=self.user,
        prompt='Hi',
    )

    self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
    self.assertEqual(response.data['code'], 'ollama_busy')
    self.assertEqual(
        response.data['error'],
        'Модель зайнята. Спробуйте ще раз за хвилину.',
    )
    self.assertEqual(response['Retry-After'], '60')
    provider.chat.assert_not_called()
    mock_release.assert_not_called()


@patch('llm.chat.release_ollama_slot')
@patch('llm.chat.acquire_ollama_slot', return_value='token-1')
@patch('llm.chat.resolve_provider')
@patch('llm.chat.prepare_chat_messages')
def test_provider_error_releases_slot(
    self, mock_prepare, mock_resolve, mock_acquire, mock_release,
):
    mock_prepare.return_value = ([{'role': 'user', 'content': 'Hi'}], [])
    provider = MagicMock()
    provider.chat.side_effect = LLMProviderError('Ollama недоступний')
    mock_resolve.return_value = provider

    response = run_chat(
        model='llama3',
        messages=[{'role': 'user', 'content': 'Hi'}],
        stream=False,
        workspace=self.workspace,
        user=self.user,
        prompt='Hi',
    )

    self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
    mock_release.assert_called_once_with('token-1')
```

Нагору `test_roadmap_regressions.py` додати `from llm.admission import OllamaBusy`. У `WidgetCourseScopeTests` додати:

```python
@patch('llm.chat.acquire_ollama_slot', side_effect=OllamaBusy())
@patch('llm.chat.prepare_chat_messages', return_value=([{'role': 'user', 'content': 'Hi'}], []))
@patch('llm.chat.resolve_provider')
def test_widget_busy_is_429_not_generic_503(self, mock_resolve, mock_prepare, mock_acquire):
    response = self.client.post(
        self.url,
        {
            'messages': [{'role': 'user', 'content': 'Hi'}],
            'stream': True,
        },
        format='json',
        HTTP_AUTHORIZATION=f'Widget-Token {self.raw}',
    )
    self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
    self.assertEqual(response.data['code'], 'ollama_busy')
```

Панельний ендпоінт покривається тим самим `run_chat`: і `ChatView`, і `WidgetChatView` повертають його `Response` без обгортки успішної відповіді. Окремий тест панелі не додавати.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/llm/tests/test_chat.py::RunChatTests::test_busy_slot_returns_json_429_without_calling_ollama backend/workspaces/tests/test_roadmap_regressions.py::WidgetCourseScopeTests::test_widget_busy_is_429_not_generic_503 -v`

Expected: FAIL зі збором тестів: `AttributeError: <module 'llm.chat'> does not have the attribute 'acquire_ollama_slot'`

- [ ] **Step 3: Write minimal implementation**

У `chat.py`:

```python
from .admission import (
    OLLAMA_BUSY_CODE,
    OLLAMA_BUSY_MESSAGE,
    RETRY_AFTER_SECONDS,
    OllamaBusy,
    acquire_ollama_slot,
    release_ollama_slot,
)


def _ollama_busy_response():
    response = Response(
        {'error': OLLAMA_BUSY_MESSAGE, 'code': OLLAMA_BUSY_CODE},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )
    response['Retry-After'] = RETRY_AFTER_SECONDS
    return response
```

Після `resolve_provider` і до гілки `if stream`:

```python
try:
    slot_token = acquire_ollama_slot()
except OllamaBusy:
    logger.warning(
        'Ollama busy (workspace=%s)',
        getattr(workspace, 'pk', None),
    )
    return _ollama_busy_response()
```

Non-stream: обгорнути виклик `provider.chat` у `try/finally` з `release_ollama_slot(slot_token)`.

Stream: у `finally` генератора, поруч із `response.close()`, викликати `release_ollama_slot(slot_token)`. Не звільняти токен у зовнішній функції після `return StreamingHttpResponse`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/llm/tests/test_chat.py backend/llm/tests/test_admission.py backend/workspaces/tests/test_roadmap_regressions.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/llm/chat.py backend/llm/tests/test_chat.py backend/workspaces/tests/test_roadmap_regressions.py
git commit -m "feat(llm): reject a second chat with ollama_busy before calling Ollama"
```

---

### Task 10: Показати «зайнято» без префікса і зменшити чергу Ollama

**Files:**
- Create: `frontend/src/utils/chatError.js`
- Create: `frontend/src/utils/chatError.test.js`
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/pages/ChatPage.jsx`
- Modify: `frontend/src/embed/embed-app.js`
- Modify: `docker-compose.prod.yml`

**Interfaces:**
- Consumes: об'єкт помилки `{ message: string, code?: string }`
- Produces: `formatChatError(err) -> string`. Для `code === 'ollama_busy'` повертає `err.message` без префікса. Інакше `` `Помилка: ${err.message || 'Помилка чату'}` ``. `chatStream` у `client.js` і `embed-app.js` ставить `err.code` з JSON `code`.

- [ ] **Step 1: Write the failing test**

```javascript
import { describe, expect, it } from 'vitest';
import { formatChatError } from './chatError';

describe('formatChatError', () => {
  it('показує ollama_busy без префікса Помилка', () => {
    expect(formatChatError({
      code: 'ollama_busy',
      message: 'Модель зайнята. Спробуйте ще раз за хвилину.',
    })).toBe('Модель зайнята. Спробуйте ще раз за хвилину.');
  });

  it('інші помилки лишає з префіксом', () => {
    expect(formatChatError({ message: 'немає мережі' })).toBe('Помилка: немає мережі');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/utils/chatError.test.js`

Working directory: `frontend`

Expected: FAIL with cannot find module `./chatError`

- [ ] **Step 3: Write minimal implementation**

`frontend/src/utils/chatError.js`:

```javascript
export function formatChatError(err) {
  if (err?.code === 'ollama_busy') {
    return err.message || 'Модель зайнята. Спробуйте ще раз за хвилину.';
  }
  return `Помилка: ${err?.message || 'Помилка чату'}`;
}
```

У `client.js` у гілці `if (!response.ok)` всередині `chatStream`:

```javascript
let message = 'Chat stream failed';
let code = '';
try {
  const error = await response.json();
  message = error.error || message;
  code = error.code || '';
} catch {
  /* ignore */
}
const err = new Error(message);
err.code = code;
throw err;
```

У `ChatPage.jsx` `onError`: замість шаблона з префіксом викликати `formatChatError(err)`.

У `embed-app.js` у `chatStream`, коли `!response.ok`:

```javascript
const error = await safeJson(response);
const err = new Error(error.error || error.detail || 'Помилка чату');
err.code = error.code || '';
throw err;
```

У `catch` відправки повідомлення і в гілці `chunk.error` підставляти текст через `formatChatError`. Для `chunk.error` це рядок, не об'єкт: лишити префікс `Помилка:` лише якщо це не код зайнятості. Зайнятість приходить до стріму як HTTP 429, тож гілка `chunk.error` лишається `Помилка: ${chunk.error}`. Змінити лише `catch (err)`, де текст зараз `` `Помилка: ${err.message}` ``, на `formatChatError(err)`.

У `docker-compose.prod.yml` замінити:

```yaml
OLLAMA_MAX_QUEUE: ${PROD_OLLAMA_MAX_QUEUE:-1}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/utils/chatError.test.js`

Working directory: `frontend`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/chatError.js frontend/src/utils/chatError.test.js frontend/src/api/client.js frontend/src/pages/ChatPage.jsx frontend/src/embed/embed-app.js docker-compose.prod.yml
git commit -m "feat(frontend): show ollama busy without an error prefix"
```

---

## Self-review

- Spec §2 слот, TTL, fail-open, `MAX_QUEUE=1`: завдання 8 і 10.
- Spec §3 контракт 429 і віджет: завдання 9 і 10.
- Spec §4 міграція, 400, фабрика, видалення провайдера, README: завдання 1–7.
- Spec §5 тести слота: завдання 8–10. Soak і гонка ingest не входять.
- Spec §6 беклог: свідомо без завдань.
- Spec §7 порядок Gemini, потім слот: номери завдань.

## Out of scope

- Автоматична off-box копія бекапів, правка runbook `.sql` проти `.tar.gz`, health Ollama, розрізання великих файлів.
- Слот для ingest/embeddings.
- Обмеження pull великих ваг Ollama.
