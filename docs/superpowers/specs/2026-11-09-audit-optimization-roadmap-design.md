# Технічний аудит, оптимізація продуктивності та дорожня карта розвитку ZROZUMILOAI

**Дата:** 2026-11-09  
**Статус:** На рев'ю  
**Поточний цикл реалізації:** Етап 1 (Продуктивність Бекенду, БД та RAG/Ollama Concurrency) + Етап 2 (Ops, Healthcheck та Backups).  
**Наступні цикли (Беклог дорожньої карти):** Етап 3 (Модульна декомпозиція коду) та Етап 4 (Розвиток продукту та Knowledge Gaps).

---

## 1. Контекст та результати технічного аудиту

Проєкт **ZROZUMILOAI** працює як односерверне рішення (VPS ≥16 GB RAM) із локальним інстансом **Ollama**, PostgreSQL (`pgvector`), Redis, Celery, Django 5 (DRF) та React 18 + вбудованим iframe-віджетом для Open edX.

Під час глибокого аудиту кодової бази виявлено такі вузькі місця та точки оптимізації:

1. **Конкурентність RAG Embeddings та Ingest із живим чатом у Ollama:**
   - У продакшені `PROD_OLLAMA_MAX_QUEUE=1` та `OLLAMA_NUM_PARALLEL=1`.
   - Живий чат (`run_chat`) і аналіз таблиці (`WorkspaceChatLogAnalysisView`) використовують Redis-слот `ollama:admission`, проте генерація векторів запиту (`cached_query_embedding`) та фонова індексація документів (`_embed_texts_parallel` до 4 потоків одночасно) викликають Ollama напряму поза слотом.
   - Крім того, `OllamaService.embed()` використовує застарілий поодинокий ендпоінт `POST /api/embeddings` замість батчевого `POST /api/embed`.
2. **Відсутність GIN-індексу для PostgreSQL Full-Text Search:**
   - Модель `DocumentChunk` має `HnswIndex` для векторів і B-tree індекс для `workspace`, але не має `GinIndex` для повнотекстового пошуку. Запит `SearchRank(SearchVector('content', config='simple'), ...)` у `search_with_fulltext()` виконує послідовне сканування чанків.
3. **Надлишкові SQL-запити в аналітиці та споживання RAM при експорті:**
   - `get_workspace_analytics()` виконує 5 окремих `.count()` запитів до `WorkspaceChatLog` замість одного `.aggregate()`.
   - `build_table_digest()` у `table_analysis.py` виконує 4 окремих `.count()` запити замість одного `.aggregate()`.
   - Експорт логів (`build_analytics_csv`, `serialize_logs`) вивантажує весь queryset у пам'ять без `.iterator(chunk_size=500)`.
   - Тести RAG-індексації залишають десятки тестових файлів у `backend/media/workspace_documents/1/` через відсутність ізоляції `MEDIA_ROOT`.
4. **Операційна видимість (`/api/health/`) та автоматизація бекапів:**
   - `GET /api/health/` перевіряє лише PostgreSQL і кеш, залишаючи статус `ok`, навіть коли контейнер `ollama` недоступний.
   - `docs/ops/vps-runbook.md` описує застарілу процедуру відновлення з `.sql` замість `.tar.gz` із медіафайлами.
   - `scripts/backup-cron.sh` видаляє локальні архіви старіші за 14 днів без вбудованого хука для off-box копіювання.

---

## 2. Архітектура Етапу 1: Координація Ollama, Батчінг Embeddings та Оптимізація БД

### 2.1. Батчевий клієнт `OllamaService.embed_batch` (`backend/ollama_proxy/services.py`)

- Додається метод `embed_batch(self, model, texts)`:
  - Якщо `texts` порожній — повертає `[]`.
  - Виконує `POST /api/embed` із JSON-тілом `{'model': normalize_model_name(model), 'input': list(texts)}` та таймаутом `180` с.
  - Парсить `embeddings = data.get('embeddings')`. Якщо відповідь валідна (`isinstance(embeddings, list)` і `len(embeddings) == len(texts)`), повертає список векторів.
  - Якщо старіша версія Ollama повернула `404` на `/api/embed`, виконує безпечний fallback на послідовні виклики `/api/embeddings`.
- Метод `embed(self, model, text)` делегує виклик `self.embed_batch(model, [text])[0]`, зберігаючи зворотну сумісність.

### 2.2. Слот допуску з очікуванням (`backend/llm/admission.py`)

- Функція `acquire_ollama_slot(wait_seconds=None, poll_interval=0.15)` розширюється параметром очікування:
  - Якщо `wait_seconds is None`, використовується `settings.OLLAMA_CHAT_SLOT_WAIT_SECONDS` (за замовчуванням `2.5` с; у unit-тестах за замовчуванням `0.0` або конфігуроване значення).
  - Якщо перша спроба `SET ollama:admission <token> NX EX <ttl>` повернула `False`, а `wait_seconds > 0`, функція повторює спробу кожні `poll_interval` секунд до дедлайну `monotonic() + wait_seconds`.
  - Якщо слот звільнився (наприклад, завершився короткий батч embeddings тривалістю ~0.5 с), запит чату отримує слот без помилки `429`. Якщо дедлайн вичерпано — піднімається `OllamaBusy`.
  - Як і раніше, при помилці Redis (`RedisError`) функція логує `warning` і повертає `None` (fail-open).

### 2.3. Поступливий батчевий Ingest (`backend/workspaces/rag/ingest.py`)

- Замість паралельного `ThreadPoolExecutor` функція `_embed_texts_batched(ollama, embed_model, texts)` ділить список чанків на пачки розміром `settings.RAG_EMBED_BATCH_SIZE` (за замовчуванням `16`).
- Для кожної пачки:
  1. Захоплює слот `token = acquire_ollama_slot(wait_seconds=settings.OLLAMA_INGEST_SLOT_WAIT_SECONDS)` (за замовчуванням `60.0` с).
  2. У блоці `try ... finally` викликає `ollama.embed_batch(embed_model, batch)` і звільняє слот `release_ollama_slot(token)`.
  3. Якщо між пачками є ще чанки, робить коротку паузу `time.sleep(settings.RAG_EMBED_BATCH_PAUSE_SECONDS)` (`0.05` с), дозволяючи запитам живого чату перехопити слот.

### 2.4. Координація Query Embedding (`backend/workspaces/rag/search_context.py`)

- У `cached_query_embedding(workspace_id, query)` при промаху кешу виклик `ollama.embed(embed_model, query)` обгортається у `acquire_ollama_slot(wait_seconds=settings.OLLAMA_CHAT_SLOT_WAIT_SECONDS)` / `release_ollama_slot(token)`.
- Якщо піднімається `OllamaBusy`, `cached_query_embedding` повертає `None`, а `search_workspace_documents` продовжує роботу через повнотекстовий пошук PostgreSQL FTS без падіння чату.

### 2.5. PostgreSQL GIN-індекс FTS та оптимізація SQL/RAM (`workspaces`, `chats`)

1. **GIN-індекс для `DocumentChunk` (`backend/workspaces/models.py` та міграція):**
   - У `_document_chunk_indexes()` для PostgreSQL додається `GinIndex(SearchVector('content', config='simple'), name='chunk_content_fts_gin_idx')`.
   - У `search_with_fulltext()` (`backend/workspaces/rag/text_search.py`) запит для PostgreSQL використовує `.annotate(search=search_vector, rank=SearchRank(search_vector, search_query)).filter(search=search_query, rank__gt=0.0)`, що активує індексний пошук у PostgreSQL.
2. **Консолідація SQL-агрегацій (`backend/chats/analytics_service.py`, `backend/chats/table_analysis.py`):**
   - У `get_workspace_analytics()` 5 окремих `.count()` замінюються одним `qs.aggregate(...)` з умовними `Count('id', filter=Q(...))` та `Count('sent_by', distinct=True)`.
   - У `build_table_digest()` 4 окремих `.count()` замінюються одним `logs.aggregate(...)`.
3. **Потоковий ітератор при експорті та чистка тестових медіа:**
   - У `build_analytics_csv()` та `serialize_logs()` вибірка читається через `.iterator(chunk_size=500)`.
   - Тести, що створюють `WorkspaceDocument` з файлами, використовують тимчасову директорію `MEDIA_ROOT`, а накопичені тестові файли з `backend/media/workspace_documents/` очищуються.

---

## 3. Архітектура Етапу 2: Healthcheck Ollama, Off-box Backups та Runbook

### 3.1. Розширений `GET /api/health/` (`backend/config/health.py`)

- Додається метод `_check_ollama()`, який читає ключ `health:ollama` з кешу (TTL `10` с). При промаху кешу викликає `OllamaService().health()` (таймаут `2` с) і кешує результат (`'ok'` або `'error'`).
- JSON-відповідь `/api/health/` тепер містить:
  ```json
  {
    "status": "ok",
    "database": "ok",
    "cache": "ok",
    "ollama": "ok"
  }
  ```
- Якщо `ollama != 'ok'`, поле `status` стає `'degraded'`.
- HTTP-статус:
  - За замовчуванням повертає `200`, якщо `database == 'ok'` (щоб внутрішній Docker healthcheck не вбивав контейнер `backend`, коли `ollama` перезапускається).
  - Якщо передано query-параметр `?strict=1` (або `true`/`yes`) і `status != 'ok'`, повертає HTTP `503` для зовнішніх систем моніторингу (UptimeRobot тощо).

### 3.2. Off-box хук у `scripts/backup-cron.sh` та оновлення `docs/ops/vps-runbook.md`

- У `scripts/backup-cron.sh` додається підтримка змінної середовища `BACKUP_OFFBOX_CMD`:
  - Якщо `BACKUP_OFFBOX_CMD` задана (наприклад, `rclone copy ./backup remote:zrozumiloai-backups`), скрипт виконує її відразу після `create_backup`.
  - Локальне видалення старих файлів (`find ./backup ... -delete`) виконується лише тоді, коли створення архіву (та `BACKUP_OFFBOX_CMD`, якщо заданий) завершилися успішно (`set -euo pipefail`).
- У `docs/ops/vps-runbook.md`:
  - Оновлюється розділ **Health** (опис поля `ollama` та параметра `/api/health/?strict=1`).
  - Оновлюється розділ **Backup / Restore drill** (використання `.tar.gz` архівів замість `.sql`, налаштування `BACKUP_OFFBOX_CMD`).
  - У таблиці **Incidents** уточнюється різниця між rate-limit `429` (`detail`) та зайнятим слотом `429` (`code: "ollama_busy"`).

---

## 4. Дорожня карта наступних циклів (Етапи 3 та 4 — Беклог)

Ці етапи зафіксовані для послідовного виконання після завершення поточного циклу:

### Етап 3: Модульна декомпозиція коду (Codebase Refactoring)
1. **Декомпозиція `backend/backups/services.py` (~590 рядків):**
   - Розділити на пакет `backend/backups/engine/`: `archive.py` (робота з `tar.gz` та `manifest.json`), `postgres.py` (`pg_dump` / `psql`), `sqlite.py` (SQLite backup API), залишивши в `services.py` фасад `BackupService`.
2. **Декомпозиція фронтенд-монолітів:**
   - Винести стан і обробники `frontend/src/pages/WorkspacesPage.jsx` (~585 рядків) у хук `useWorkspacesAdmin.js` та підкомпоненти форми/таблиці.
   - Розділити `frontend/src/embed/embed-app.js` (~650 рядків) на `embed-state.js`, `embed-api.js` та `embed-dom.js`.
   - Розбити `frontend/src/styles/index.css` (~1100 рядків) на тематичні модулі (`base.css`, `layout.css`, `forms.css`, `tables.css`, `components.css`).

### Етап 4: Розвиток продукту (Product Evolution)
1. **Життєвий цикл Knowledge Gaps:**
   - Додати в `WorkspaceChatLog` поля `is_resolved = models.BooleanField(default=False)` та `resolved_at = models.DateTimeField(null=True, blank=True)`.
   - Додати ендпоінт `PATCH /api/workspaces/<id>/analytics/gaps/<log_id>/resolve/` та кнопку «Вирішено» в `KnowledgeGapsTable.jsx`.
2. **Розширена аналітика та фільтри експорту:**
   - Додати фільтрацію за `workspace` та датою безпосередньо на сторінці `Chats Info` (`WorkspaceChatsPage.jsx`).

---

## 5. Критерії готовності поточного циклу (Етапи 1 + 2)

1. `OllamaService.embed_batch()` відправляє батч-запити на `/api/embed` і має fallback на `/api/embeddings`.
2. Фонова індексація (`ingest_workspace_document`) обробляє чанки пачками по `RAG_EMBED_BATCH_SIZE=16` через слот `ollama:admission`, не блокуючи назавжди живий чат.
3. У PostgreSQL міграцією створено GIN-індекс `chunk_content_fts_gin_idx`, який використовується у `search_with_fulltext()`.
4. `get_workspace_analytics()` та `build_table_digest()` виконують по 1 агрегаційному SQL-запиту замість 5 і 4 відповідно.
5. `GET /api/health/` повертає поле `ollama` (`ok`/`error`), ставить `status: "degraded"` при недоступності Ollama і віддає `503` при `?strict=1`.
6. Тести не залишають сміття в `backend/media/`, усі unit-тести бекенду та фронтенду проходять успішно.
