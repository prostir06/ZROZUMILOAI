# Audit Optimization & Ops Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate Ollama queue contention between RAG embeddings/ingest and live chat via batch `/api/embed` and yielding slot admission, add PostgreSQL GIN FTS indexing, consolidate N+1 analytics SQL queries, isolate test media files, and expose Ollama status in `/api/health/` with updated ops scripts and runbook.

**Architecture:** `OllamaService` gains `embed_batch(model, texts)` using `POST /api/embed` (with 404 fallback to `/api/embeddings`). `acquire_ollama_slot(wait_seconds=...)` supports bounded polling so live chats wait briefly for finishing embed batches, while `ingest_workspace_document` embeds chunks in batches of 16 holding the admission slot per batch and yielding between batches. PostgreSQL full-text search gets a functional `GinIndex` (`to_tsvector('simple', content)`), analytics services replace multiple `.count()` calls with single `.aggregate()` queries, and `GET /api/health/` reports cached Ollama status (`200` by default, `503` with `?strict=1`).

**Tech Stack:** Python 3.12+, Django 5, Django REST Framework, PostgreSQL 16 (`pgvector` + GIN FTS), Redis 7.2, Celery, Bash.

## Global Constraints

- Only Ollama is used as the LLM/embedding provider (no cloud providers).
- PEP 8 compliance for all Python code; Ukrainian docstrings and user-facing error messages where established.
- All migrations must be safe on both PostgreSQL (production/CI) and SQLite (local tests) via `SeparateDatabaseAndState` / `connection.vendor` checks.
- `GET /api/health/` must return HTTP `200` when PostgreSQL is healthy even if Ollama is unreachable, unless `?strict=1` (`true`/`yes`) is passed, in which case any degraded component returns HTTP `503`.
- Tests creating `WorkspaceDocument` files must use a temporary `MEDIA_ROOT` and never leave files in `backend/media/`.

---

### Task 1: Batch Embeddings (`OllamaService.embed_batch`) and Admission Slot Waiting (`acquire_ollama_slot`)

**Files:**
- Modify: `backend/config/settings.py:192-198,284-289`
- Modify: `backend/llm/admission.py:1-66`
- Modify: `backend/ollama_proxy/services.py:117-131`
- Test: `backend/llm/tests/test_admission.py`
- Test: `backend/ollama_proxy/tests/test_services.py`

**Interfaces:**
- Produces:
  - `acquire_ollama_slot(client=None, wait_seconds=None, poll_interval=0.05) -> str | None` in `llm.admission`
  - `OllamaService.embed_batch(model: str, texts: list[str]) -> list[list[float]]` in `ollama_proxy.services`
  - Settings: `OLLAMA_CHAT_SLOT_WAIT_SECONDS` (`0.0` default in settings so unit tests stay instant, configurable via env), `OLLAMA_INGEST_SLOT_WAIT_SECONDS` (`60.0`), `RAG_EMBED_BATCH_SIZE` (`16`), `RAG_EMBED_BATCH_PAUSE_SECONDS` (`0.05`).

- [ ] **Step 1: Write the failing unit tests for `acquire_ollama_slot(wait_seconds=...)` and `OllamaService.embed_batch`**

Add wait tests in `backend/llm/tests/test_admission.py`:

```python
    def test_acquire_waits_until_slot_is_released(self):
        client = FakeRedis()
        calls = {'count': 0}
        orig_set = client.set

        def releasing_set(key, value, nx=False, ex=None):
            calls['count'] += 1
            if calls['count'] == 2:
                client.store.pop(ADMISSION_KEY, None)
            return orig_set(key, value, nx=nx, ex=ex)

        client.set = releasing_set
        first = orig_set(ADMISSION_KEY, 'holder', nx=True, ex=180)
        self.assertTrue(first)

        token = acquire_ollama_slot(
            client=client,
            wait_seconds=0.2,
            poll_interval=0.01,
        )
        self.assertTrue(token)
        self.assertEqual(calls['count'], 2)
```

Add `embed_batch` tests in `backend/ollama_proxy/tests/test_services.py`:

```python
    @patch.object(requests.Session, 'request')
    def test_embed_batch_posts_to_api_embed(self, mock_request):
        """embed_batch викликає POST /api/embed і повертає список векторів."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'embeddings': [[0.1, 0.2], [0.3, 0.4]],
        }
        mock_request.return_value = mock_response

        service = OllamaService()
        vectors = service.embed_batch('nomic-embed-text', ['перший', 'другий'])

        self.assertEqual(vectors, [[0.1, 0.2], [0.3, 0.4]])
        mock_request.assert_called_once_with(
            'POST',
            'http://ollama:11434/api/embed',
            timeout=180,
            json={'model': 'nomic-embed-text', 'input': ['перший', 'другий']},
        )

    @patch.object(requests.Session, 'request')
    def test_embed_batch_falls_back_to_legacy_embeddings_on_404(self, mock_request):
        """При HTTP 404 на /api/embed виконується fallback на /api/embeddings."""
        not_found = MagicMock()
        not_found.status_code = 404

        legacy_ok = MagicMock()
        legacy_ok.status_code = 200
        legacy_ok.json.return_value = {'embedding': [0.5, 0.6]}

        mock_request.side_effect = [not_found, legacy_ok]

        service = OllamaService()
        vectors = service.embed_batch('nomic-embed-text', ['текст'])

        self.assertEqual(vectors, [[0.5, 0.6]])
        self.assertEqual(mock_request.call_count, 2)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```powershell
backend\.venv\Scripts\python.exe backend\manage.py test llm.tests.test_admission ollama_proxy.tests.test_services
```
Expected: FAIL (`TypeError: acquire_ollama_slot() got an unexpected keyword argument 'wait_seconds'` and `AttributeError: 'OllamaService' object has no attribute 'embed_batch'`).

- [ ] **Step 3: Implement settings, `acquire_ollama_slot` waiting, and `OllamaService.embed_batch`**

In `backend/config/settings.py`:
```python
OLLAMA_ADMISSION_LIMIT = 1
OLLAMA_ADMISSION_TTL_SECONDS = int(os.getenv('OLLAMA_ADMISSION_TTL_SECONDS', '180'))
OLLAMA_CHAT_SLOT_WAIT_SECONDS = float(os.getenv('OLLAMA_CHAT_SLOT_WAIT_SECONDS', '0.0'))
OLLAMA_INGEST_SLOT_WAIT_SECONDS = float(os.getenv('OLLAMA_INGEST_SLOT_WAIT_SECONDS', '60.0'))
```
And under `RAG_EMBED_CONCURRENCY`:
```python
RAG_EMBED_BATCH_SIZE = int(os.getenv('RAG_EMBED_BATCH_SIZE', '16'))
RAG_EMBED_BATCH_PAUSE_SECONDS = float(os.getenv('RAG_EMBED_BATCH_PAUSE_SECONDS', '0.05'))
```

In `backend/llm/admission.py`:
```python
import time
import uuid


def acquire_ollama_slot(client=None, wait_seconds=None, poll_interval=0.05):
    """Повернути токен власника, None для fail-open, або кинути OllamaBusy."""
    if client is None and not (getattr(settings, 'REDIS_URL', '') or '').strip():
        return None
    if wait_seconds is None:
        wait_seconds = float(
            getattr(settings, 'OLLAMA_CHAT_SLOT_WAIT_SECONDS', 0.0) or 0.0
        )
    wait_seconds = max(0.0, float(wait_seconds))
    poll_interval = max(0.005, float(poll_interval))
    deadline = time.monotonic() + wait_seconds
    redis_client = client
    token = uuid.uuid4().hex
    ttl = int(getattr(settings, 'OLLAMA_ADMISSION_TTL_SECONDS', 180))

    while True:
        try:
            if redis_client is None:
                from django_redis import get_redis_connection
                redis_client = get_redis_connection('default')
            written = redis_client.set(ADMISSION_KEY, token, nx=True, ex=ttl)
        except Exception as exc:
            logger.warning(
                'Ollama admission unavailable, failing open: %s',
                exc,
                exc_info=True,
            )
            return None
        if written:
            return token
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OllamaBusy()
        time.sleep(min(poll_interval, remaining))
```

In `backend/ollama_proxy/services.py`:
```python
    def _embed_single_legacy(self, model, text):
        """Отримати один embedding через legacy /api/embeddings."""
        model = normalize_model_name(model)
        response = self._request(
            'POST',
            '/api/embeddings',
            json={'model': model, 'prompt': text},
            timeout=120,
        )
        raise_for_ollama_status(response)
        data = self.parse_json(response)
        embedding = data.get('embedding')
        if not isinstance(embedding, list) or not embedding:
            raise requests.RequestException('Ollama не повернув embedding')
        return embedding

    def embed_batch(self, model, texts):
        """Отримати список embedding-векторів пачкою через /api/embed."""
        if not texts:
            return []
        model = normalize_model_name(model)
        items = [str(item) for item in texts]
        response = self._request(
            'POST',
            '/api/embed',
            json={'model': model, 'input': items},
            timeout=180,
        )
        if response.status_code == 404:
            return [self._embed_single_legacy(model, item) for item in items]
        raise_for_ollama_status(response)
        data = self.parse_json(response)
        embeddings = data.get('embeddings')
        if (
            not isinstance(embeddings, list)
            or len(embeddings) != len(items)
            or any(not isinstance(vec, list) or not vec for vec in embeddings)
        ):
            raise requests.RequestException('Ollama не повернув коректні embeddings')
        return embeddings

    def embed(self, model, text):
        """Отримати embedding-вектор для одного тексту."""
        return self.embed_batch(model, [text])[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```powershell
backend\.venv\Scripts\python.exe backend\manage.py test llm.tests.test_admission ollama_proxy.tests.test_services
```
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/config/settings.py backend/llm/admission.py backend/llm/tests/test_admission.py backend/ollama_proxy/services.py backend/ollama_proxy/tests/test_services.py
git commit -m "feat(ollama): add batch embed_batch client and bounded wait to admission slot"
```

---

### Task 2: Yielding Batch Ingest and Slot-Guarded Query Embedding

**Files:**
- Modify: `backend/workspaces/rag/ingest.py:1-107`
- Modify: `backend/workspaces/rag/search_context.py:131-159`
- Modify: `backend/workspaces/tests/test_ingest_service.py`
- Modify: `backend/workspaces/tests/test_rag_service.py`
- Modify: `backend/workspaces/tests/test_document_api.py`

**Interfaces:**
- Consumes: `OllamaService.embed_batch`, `acquire_ollama_slot`, `release_ollama_slot`, `OllamaBusy`.
- Produces: `_embed_texts_batched(ollama, embed_model, texts)` in `workspaces.rag.ingest`; slot-aware `cached_query_embedding` in `workspaces.rag.search_context`; isolated `MEDIA_ROOT` in `test_document_api.py` and cleanup of leftover files in `backend/media/workspace_documents/`.

- [ ] **Step 1: Write failing tests for batch ingest with admission slot and slot-guarded query embedding**

In `backend/workspaces/tests/test_ingest_service.py`, add a test verifying batching and slot acquire/release per batch:

```python
    @override_settings(
        RAG_EMBED_BATCH_SIZE=2,
        RAG_EMBED_BATCH_PAUSE_SECONDS=0.0,
        OLLAMA_INGEST_SLOT_WAIT_SECONDS=5.0,
    )
    @patch('workspaces.rag.ingest.release_ollama_slot')
    @patch('workspaces.rag.ingest.acquire_ollama_slot', side_effect=['tok1', 'tok2'])
    @patch('workspaces.rag.ingest.OllamaService')
    @patch(
        'workspaces.rag.ingest.split_text_into_chunks',
        return_value=['c1', 'c2', 'c3'],
    )
    @patch(
        'workspaces.rag.ingest.extract_text_from_file',
        return_value='text',
    )
    def test_ingest_batches_chunks_and_acquires_slot_per_batch(
        self,
        _extract,
        _split,
        mock_ollama_cls,
        mock_acquire,
        mock_release,
    ):
        mock_ollama = mock_ollama_cls.return_value
        mock_ollama.embed_batch.side_effect = [
            [[0.1, 0.2], [0.3, 0.4]],
            [[0.5, 0.6]],
        ]

        ingest_workspace_document(self.document)

        self.document.refresh_from_db()
        self.assertEqual(self.document.status, WorkspaceDocument.Status.READY)
        self.assertEqual(self.document.chunk_count, 3)
        self.assertEqual(mock_ollama.embed_batch.call_count, 2)
        self.assertEqual(mock_acquire.call_count, 2)
        self.assertEqual(
            [c.args[0] for c in mock_release.call_args_list],
            ['tok1', 'tok2'],
        )
```

In `backend/workspaces/tests/test_rag_service.py`, add a test verifying that `cached_query_embedding` returns `None` gracefully when `acquire_ollama_slot` raises `OllamaBusy`:

```python
    @patch('workspaces.rag.search_context.acquire_ollama_slot', side_effect=OllamaBusy())
    @patch('workspaces.rag.search_context.OllamaService')
    def test_cached_query_embedding_returns_none_when_ollama_busy(
        self,
        mock_ollama_cls,
        _mock_acquire,
    ):
        from django.core.cache import cache
        from workspaces.rag.search_context import cached_query_embedding

        cache.clear()
        result = cached_query_embedding(workspace_id=1, query='зайнятий запит')
        self.assertIsNone(result)
        mock_ollama_cls.return_value.embed.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_ingest_service workspaces.tests.test_rag_service
```
Expected: FAIL (`workspaces.rag.ingest` does not have `acquire_ollama_slot` or `embed_batch` integration yet).

- [ ] **Step 3: Implement `_embed_texts_batched`, slot-guarded `cached_query_embedding`, and temporary `MEDIA_ROOT` in `test_document_api.py`**

Update `backend/workspaces/rag/ingest.py`:
```python
"""Індексація документів workspace (chunking + embeddings)."""
import logging
import time

from django.conf import settings
from django.db import transaction

from llm.admission import acquire_ollama_slot, release_ollama_slot
from ollama_proxy.services import OllamaService

from ..models import DocumentChunk, WorkspaceDocument
from .chunker import split_text_into_chunks
from .text_extractor import extract_text_from_file

logger = logging.getLogger(__name__)


def ingest_workspace_document(document):
    """
    Проіндексувати документ: витяг тексту, chunking, батчеві embeddings.

    Embeddings виконуються пачками через слот допуску Ollama поза atomic;
    bulk_create виконується у короткій транзакції.
    """
    document.status = WorkspaceDocument.Status.PROCESSING
    document.error_message = ''
    document.save(update_fields=['status', 'error_message', 'updated_at'])

    try:
        if not document.file or not document.file.path:
            raise ValueError('Файл документа не знайдено')

        text = extract_text_from_file(document.file.path)
        chunk_texts = split_text_into_chunks(
            text,
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        )
        if not chunk_texts:
            raise ValueError('Не вдалося створити фрагменти тексту')

        ollama = OllamaService()
        embed_model = settings.RAG_EMBED_MODEL
        embeddings = _embed_texts_batched(ollama, embed_model, chunk_texts)

        prepared_chunks = [
            DocumentChunk(
                document=document,
                workspace=document.workspace,
                chunk_index=index,
                content=chunk_text,
                embedding=embedding,
            )
            for index, (chunk_text, embedding) in enumerate(
                zip(chunk_texts, embeddings),
            )
        ]

        with transaction.atomic():
            DocumentChunk.objects.filter(document=document).delete()
            DocumentChunk.objects.bulk_create(prepared_chunks)
            document.status = WorkspaceDocument.Status.READY
            document.chunk_count = len(prepared_chunks)
            document.error_message = ''
            document.save(update_fields=[
                'status', 'chunk_count', 'error_message', 'updated_at',
            ])

    except Exception as exc:
        logger.exception('Document ingest failed for %s', document.pk)
        try:
            document.status = WorkspaceDocument.Status.FAILED
            document.error_message = str(exc)[:2000]
            document.chunk_count = 0
            document.save(update_fields=[
                'status', 'error_message', 'chunk_count', 'updated_at',
            ])
            DocumentChunk.objects.filter(document=document).delete()
        except Exception as cleanup_exc:
            logger.error(
                'Failed to mark document %s as failed: %s',
                document.pk,
                cleanup_exc,
            )
        raise


def _embed_single_batch(ollama, embed_model, batch):
    """Отримати embeddings для однієї пачки з підтримкою embed_batch або fallback."""
    if hasattr(ollama, 'embed_batch'):
        batch_result = ollama.embed_batch(embed_model, batch)
        if isinstance(batch_result, list) and len(batch_result) == len(batch):
            return batch_result
    return [ollama.embed(embed_model, text) for text in batch]


def _embed_texts_batched(ollama, embed_model, texts):
    """Послідовні батчі embeddings з поступливим захопленням слота Ollama."""
    batch_size = max(1, int(getattr(settings, 'RAG_EMBED_BATCH_SIZE', 16)))
    wait_seconds = float(
        getattr(settings, 'OLLAMA_INGEST_SLOT_WAIT_SECONDS', 60.0)
    )
    pause_seconds = max(
        0.0,
        float(getattr(settings, 'RAG_EMBED_BATCH_PAUSE_SECONDS', 0.05)),
    )
    results = []
    total = len(texts)

    for start in range(0, total, batch_size):
        batch = texts[start:start + batch_size]
        slot_token = acquire_ollama_slot(wait_seconds=wait_seconds)
        try:
            batch_vectors = _embed_single_batch(ollama, embed_model, batch)
            results.extend(batch_vectors)
        finally:
            release_ollama_slot(slot_token)

        if pause_seconds > 0 and start + batch_size < total:
            time.sleep(pause_seconds)

    return results
```

Update `cached_query_embedding` in `backend/workspaces/rag/search_context.py`:
```python
from llm.admission import OllamaBusy, acquire_ollama_slot, release_ollama_slot
```
And inside `cached_query_embedding`:
```python
    wait_seconds = float(
        getattr(settings, 'OLLAMA_CHAT_SLOT_WAIT_SECONDS', 0.0) or 0.0
    )
    try:
        slot_token = acquire_ollama_slot(wait_seconds=wait_seconds)
    except OllamaBusy:
        logger.warning(
            'Skipping query embedding because Ollama slot is busy (workspace=%s)',
            ws_key,
        )
        return None

    try:
        ollama = OllamaService()
        vector = ollama.embed(embed_model, query)
    finally:
        release_ollama_slot(slot_token)

    try:
        cache.set(cache_key, vector, timeout=ttl)
    except Exception as exc:
        logger.warning('Failed to cache query embedding: %s', exc)
    return vector
```

In `backend/workspaces/tests/test_document_api.py`, add `tempfile.TemporaryDirectory` override on `WorkspaceDocumentApiTests` so uploaded test files are cleaned up automatically, and remove leftover files from `backend/media/workspace_documents/`.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```powershell
backend\.venv\Scripts\python.exe backend\manage.py test workspaces
```
Expected: PASS, and `backend/media/workspace_documents` contains no stray test files.

- [ ] **Step 5: Commit**

```powershell
git add backend/workspaces/rag/ingest.py backend/workspaces/rag/search_context.py backend/workspaces/tests/test_ingest_service.py backend/workspaces/tests/test_rag_service.py backend/workspaces/tests/test_document_api.py
git commit -m "feat(rag): batch document embeddings with yielding Ollama slot and isolate test media"
```

---

### Task 3: PostgreSQL GIN Index for Full-Text Search & SQL/Memory Optimization in Analytics

**Files:**
- Modify: `backend/workspaces/models.py:160-185`
- Create: `backend/workspaces/migrations/0015_documentchunk_fts_gin_index.py`
- Modify: `backend/workspaces/rag/text_search.py:37-56`
- Modify: `backend/chats/analytics_service.py:44-64,132-150`
- Modify: `backend/chats/table_analysis.py:50-64`
- Modify: `backend/chats/export_service.py:68-71`
- Test: `backend/workspaces/tests/test_pgvector.py`
- Test: `backend/chats/tests/test_analytics.py`

**Interfaces:**
- Produces:
  - `chunk_content_fts_gin_idx` (`GinIndex(SearchVector('content', config='simple'))`) on `DocumentChunk`
  - Migration `0015_documentchunk_fts_gin_index`
  - Single-query `.aggregate()` in `get_workspace_analytics` and `build_table_digest`
  - `.iterator(chunk_size=500)` in `build_analytics_csv` and `serialize_logs`

- [ ] **Step 1: Write failing tests for PostgreSQL GIN index and single-query analytics aggregation**

In `backend/workspaces/tests/test_pgvector.py`:
- Update `test_document_chunk_indexes_on_postgresql` to assert `len(indexes) == 3` and that `indexes[2]` is a `GinIndex` named `'chunk_content_fts_gin_idx'`.
- Add `test_migration_0015_fts_gin_index_declared_and_executes` testing SQLite no-op and PostgreSQL `CREATE INDEX IF NOT EXISTS chunk_content_fts_gin_idx`.

In `backend/chats/tests/test_analytics.py`, add a test verifying query count in `get_workspace_analytics`:
```python
    def test_get_workspace_analytics_uses_single_aggregate_for_kpis(self):
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='u1',
            prompt='Q1',
            response='A1',
            needs_handoff=True,
            feedback='down',
        )
        # 1 aggregate query + 1 gaps query + 1 timeline query = 3 queries total
        with self.assertNumQueries(3):
            data = get_workspace_analytics(self.workspace, date_range='30d')
        self.assertEqual(data['total_queries'], 1)
        self.assertEqual(data['handoff_count'], 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_pgvector chats.tests.test_analytics
```
Expected: FAIL (`len(indexes)` is 2 instead of 3, and `assertNumQueries(3)` fails because 7 queries are executed).

- [ ] **Step 3: Implement `GinIndex`, migration `0015`, FTS filter, `.aggregate()` consolidation, and `.iterator()`**

In `backend/workspaces/models.py`:
```python
    from django.contrib.postgres.indexes import GinIndex
    from django.contrib.postgres.search import SearchVector
    from pgvector.django import HnswIndex

    indexes.append(
        HnswIndex(
            name='chunk_embedding_hnsw_idx',
            fields=['embedding'],
            m=16,
            ef_construction=64,
            opclasses=['vector_cosine_ops'],
        ),
    )
    indexes.append(
        GinIndex(
            SearchVector('content', config='simple'),
            name='chunk_content_fts_gin_idx',
        ),
    )
    return indexes
```

Create `backend/workspaces/migrations/0015_documentchunk_fts_gin_index.py`:
```python
"""Add PostgreSQL GIN functional index for full-text search on DocumentChunk.content."""
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import migrations


def create_fts_gin_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute("""
        CREATE INDEX IF NOT EXISTS chunk_content_fts_gin_idx
        ON workspaces_documentchunk
        USING gin (to_tsvector('simple', content));
    """)


def drop_fts_gin_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('DROP INDEX IF EXISTS chunk_content_fts_gin_idx;')


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0014_remove_gemini'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name='documentchunk',
                    index=GinIndex(
                        SearchVector('content', config='simple'),
                        name='chunk_content_fts_gin_idx',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    create_fts_gin_index,
                    drop_fts_gin_index,
                ),
            ],
        ),
    ]
```

In `backend/workspaces/rag/text_search.py` (PostgreSQL branch):
```python
            search_query = SearchQuery(query_str, config='simple')
            search_vector = SearchVector('content', config='simple')
            chunks = (
                DocumentChunk.objects.filter(
                    workspace=workspace,
                    document__status=WorkspaceDocument.Status.READY,
                )
                .annotate(
                    search=search_vector,
                    rank=SearchRank(search_vector, search_query),
                )
                .filter(search=search_query, rank__gt=0.0)
                .order_by('-rank')
                .select_related('document')[:top_k]
            )
```

In `backend/chats/analytics_service.py`:
Replace the 5 separate `.count()` calls with:
```python
    totals = qs.aggregate(
        total_queries=Count('id'),
        unique_users=Count('sent_by', distinct=True),
        handoff_count=Count('id', filter=Q(needs_handoff=True)),
        feedback_up=Count('id', filter=Q(feedback='up')),
        feedback_down=Count('id', filter=Q(feedback='down')),
    )
    total_queries = totals['total_queries'] or 0
    unique_users = totals['unique_users'] or 0
    handoff_count = totals['handoff_count'] or 0
    feedback_up = totals['feedback_up'] or 0
    feedback_down = totals['feedback_down'] or 0
```
And in `build_analytics_csv`, iterate with `for log in qs.iterator(chunk_size=500):`.

In `backend/chats/table_analysis.py`:
Replace the 4 `.count()` calls in `build_table_digest(logs)` with:
```python
    totals = logs.aggregate(
        total=Count('id'),
        handoff=Count('id', filter=Q(needs_handoff=True)),
        feedback_up=Count('id', filter=Q(feedback='up')),
        feedback_down=Count('id', filter=Q(feedback='down')),
    )
    total = totals['total'] or 0
    handoff = totals['handoff'] or 0
    feedback_up = totals['feedback_up'] or 0
    feedback_down = totals['feedback_down'] or 0
```
(importing `Q` from `django.db.models`).

In `backend/chats/export_service.py`:
```python
def serialize_logs(logs):
    """Серіалізувати queryset або список логів з мінімальним споживанням RAM."""
    iterable = (
        logs.iterator(chunk_size=500)
        if hasattr(logs, 'iterator')
        else logs
    )
    return [serialize_log_row(log) for log in iterable]
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```powershell
backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_pgvector workspaces.tests.test_hybrid_search chats.tests.test_analytics chats.tests.test_services
```
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/workspaces/models.py backend/workspaces/migrations/0015_documentchunk_fts_gin_index.py backend/workspaces/rag/text_search.py backend/workspaces/tests/test_pgvector.py backend/chats/analytics_service.py backend/chats/table_analysis.py backend/chats/export_service.py backend/chats/tests/test_analytics.py
git commit -m "perf(db): add PostgreSQL FTS GIN index and consolidate analytics SQL aggregations"
```

---

### Task 4: Ollama Status in `/api/health/`, Off-box Backup Hook, and Runbook Update

**Files:**
- Modify: `backend/config/health.py:1-65`
- Modify: `backend/config/tests/test_health.py:1-27`
- Modify: `scripts/backup-cron.sh:1-26`
- Modify: `.env.example`
- Modify: `docs/ops/vps-runbook.md`

**Interfaces:**
- Produces:
  - `GET /api/health/` returning `{"status": "ok"|"degraded", "database": "ok"|"error", "cache": "ok"|"miss"|"error", "ollama": "ok"|"error"}` with HTTP `200` when DB is ok, or HTTP `503` when `?strict=1` and `status != "ok"`.
  - `BACKUP_OFFBOX_CMD` support in `scripts/backup-cron.sh` and `.env.example`.

- [ ] **Step 1: Write failing tests for Ollama check and `?strict=1` in `backend/config/tests/test_health.py`**

Update `backend/config/tests/test_health.py`:
```python
"""Unit-тести /api/health/."""
from unittest.mock import patch

from django.core.cache import cache
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    """Health має відповідати без auth і відображати стан БД, кешу та Ollama."""

    def setUp(self):
        cache.clear()

    @patch('config.health.OllamaService')
    def test_health_ok_when_database_and_ollama_available(self, mock_ollama_cls):
        mock_ollama_cls.return_value.health.return_value = True
        response = self.client.get(reverse('api_health'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['database'], 'ok')
        self.assertEqual(data['ollama'], 'ok')
        self.assertIn(data.get('cache'), ('ok', 'miss', 'error', 'unknown'))

    @patch('config.health.OllamaService')
    def test_health_degraded_200_by_default_and_503_with_strict_when_ollama_down(
        self,
        mock_ollama_cls,
    ):
        mock_ollama_cls.return_value.health.return_value = False

        res_default = self.client.get(reverse('api_health'))
        self.assertEqual(res_default.status_code, 200)
        self.assertEqual(res_default.json()['status'], 'degraded')
        self.assertEqual(res_default.json()['ollama'], 'error')

        res_strict = self.client.get(f"{reverse('api_health')}?strict=1")
        self.assertEqual(res_strict.status_code, 503)
        self.assertEqual(res_strict.json()['status'], 'degraded')
        self.assertEqual(res_strict.json()['ollama'], 'error')

    @patch('config.health.OllamaService')
    @patch('config.health.connection')
    def test_health_degraded_when_database_fails(
        self,
        mock_connection,
        mock_ollama_cls,
    ):
        mock_ollama_cls.return_value.health.return_value = True
        mock_connection.ensure_connection.side_effect = DatabaseError('down')
        response = self.client.get(reverse('api_health'))
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data['status'], 'degraded')
        self.assertEqual(data['database'], 'error')
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
backend\.venv\Scripts\python.exe backend\manage.py test config.tests.test_health
```
Expected: FAIL (`KeyError: 'ollama'`).

- [ ] **Step 3: Implement Ollama status in `backend/config/health.py`, update `scripts/backup-cron.sh`, `.env.example`, and `docs/ops/vps-runbook.md`**

In `backend/config/health.py`:
```python
"""
Публічний healthcheck для Docker / reverse-proxy.

Повертає JSON без автентифікації. Не повинен кидати необроблені
винятки — інакше healthcheck Compose/Kubernetes вважатиме контейнер мертвим.
"""
import logging

from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views import View

from ollama_proxy.services import OllamaService

logger = logging.getLogger(__name__)

OLLAMA_HEALTH_CACHE_KEY = 'health:ollama_status'
OLLAMA_HEALTH_CACHE_TTL = 10


def _check_ollama_status():
    """Перевірити доступність Ollama з коротким кешем (10 с)."""
    try:
        cached = cache.get(OLLAMA_HEALTH_CACHE_KEY)
        if cached in ('ok', 'error'):
            return cached
    except Exception as exc:  # noqa: BLE001
        logger.debug('Health Ollama cache read failed: %s', exc)

    status_val = 'error'
    try:
        if OllamaService().health():
            status_val = 'ok'
    except Exception as exc:  # noqa: BLE001
        logger.warning('Health Ollama check failed: %s', exc)

    try:
        cache.set(OLLAMA_HEALTH_CACHE_KEY, status_val, timeout=OLLAMA_HEALTH_CACHE_TTL)
    except Exception as exc:  # noqa: BLE001
        logger.debug('Health Ollama cache write failed: %s', exc)

    return status_val


class HealthView(View):
    """
    GET /api/health/

    Перевіряє підключення до БД, кешу та Ollama.
    За замовчуванням повертає HTTP 200, поки жива БД (щоб Docker не рестартував
    backend під час рестарту Ollama). З параметром ?strict=1 повертає 503,
    якщо будь-який компонент (зокрема Ollama) у стані degraded.
    """

    def get(self, request):
        """Зібрати статус залежностей у JSON-відповідь."""
        payload = {
            'status': 'ok',
            'database': 'ok',
            'cache': 'unknown',
            'ollama': 'unknown',
        }
        http_status = 200
        strict = str(request.GET.get('strict', '')).strip().lower() in (
            '1', 'true', 'yes',
        )

        try:
            connection.ensure_connection()
        except DatabaseError as exc:
            logger.warning('Health DB check failed: %s', exc)
            payload['status'] = 'degraded'
            payload['database'] = 'error'
            http_status = 503
        except Exception as exc:  # noqa: BLE001
            logger.exception('Unexpected health DB error: %s', exc)
            payload['status'] = 'degraded'
            payload['database'] = 'error'
            http_status = 503

        try:
            cache.set('healthcheck', '1', timeout=5)
            cached = cache.get('healthcheck')
            payload['cache'] = 'ok' if cached == '1' else 'miss'
        except Exception as exc:  # noqa: BLE001
            logger.warning('Health cache check failed: %s', exc)
            payload['cache'] = 'error'

        ollama_status = _check_ollama_status()
        payload['ollama'] = ollama_status
        if ollama_status != 'ok':
            payload['status'] = 'degraded'
            if strict:
                http_status = 503

        try:
            return JsonResponse(payload, status=http_status)
        except Exception as exc:  # noqa: BLE001
            logger.exception('Health JsonResponse failed: %s', exc)
            return JsonResponse(
                {
                    'status': 'error',
                    'database': 'unknown',
                    'cache': 'unknown',
                    'ollama': 'unknown',
                },
                status=503,
            )
```

In `scripts/backup-cron.sh`:
Add optional `BACKUP_OFFBOX_CMD` execution after `create_backup` before pruning local files.
Update `.env.example` with commented `BACKUP_OFFBOX_CMD=` and new RAG/Ollama batch settings.
Update `docs/ops/vps-runbook.md` to document `/api/health/?strict=1`, `.tar.gz` archives in restore drills, `BACKUP_OFFBOX_CMD`, and `429 ollama_busy`.

- [ ] **Step 4: Run full verification suite**

Run:
```powershell
backend\.venv\Scripts\python.exe backend\manage.py test workspaces accounts chats llm ollama_proxy config
backend\.venv\Scripts\python.exe -m pytest backend\backups\tests\ -q
npm --prefix frontend test -- --run
npm --prefix frontend run lint
```
Expected: All tests pass with zero warnings/errors.

- [ ] **Step 5: Commit**

```powershell
git add backend/config/health.py backend/config/tests/test_health.py scripts/backup-cron.sh .env.example docs/ops/vps-runbook.md
git commit -m "feat(ops): add Ollama healthcheck status, off-box backup hook, and update VPS runbook"
```
