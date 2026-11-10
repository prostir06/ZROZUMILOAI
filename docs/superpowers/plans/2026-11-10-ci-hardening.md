# CI/CD Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the GitHub Actions CI pipeline and codebase checks so PEP 8 linting, Django migration verification, the full 395-test suite on PostgreSQL + pgvector + Redis, strict ESLint, and live Docker Compose smoke verification run cleanly on every push and PR.

**Architecture:** Fix real PostgreSQL/Redis concurrency and dimension bugs uncovered during full-suite Postgres testing, add standalone `ruff` and dev dependencies (`backend/pyproject.toml`, `backend/requirements-dev.txt`), enforce `--max-warnings=0` in `frontend/package.json`, and upgrade `.github/workflows/ci.yml` with Buildx caching and live `/api/health/` verification.

**Tech Stack:** GitHub Actions, Ruff (`>=0.8,<1.0`), Django 5.2, PostgreSQL 16 + pgvector, Redis 7.2.7-alpine, ESLint 8, Vitest, Docker Compose v2.

## Global Constraints

- Follow PEP 8, HTML5, CSS3, and StandardJS/ESLint conventions; do not alter unrelated existing comments or docstrings.
- Keep `backend/requirements.txt` free of dev/lint tools (`ruff`, `pytest`); place dev tools in `backend/requirements-dev.txt`.
- Run `python manage.py makemigrations --check --dry-run` only with `USE_SQLITE='False'` (PostgreSQL mode) because `DocumentChunk` conditionally defines `VectorField`, `HnswIndex`, and `GinIndex`.
- Every task must finish with passing local verification before committing.

---

### Task 1: Fix Streaming Redis Slot Leak & Postgres Test Assumptions

**Files:**
- Modify: `backend/llm/chat.py:150-235`
- Test: `backend/llm/tests/test_chat.py`
- Modify: `backend/workspaces/tests/test_hybrid_search.py:72-89`
- Modify: `backend/workspaces/tests/test_ingest_service.py:35-38,114-118`
- Modify: `backend/backups/tests/test_services.py:385-390,414-418,499-518`

**Interfaces:**
- Consumes: `acquire_ollama_slot`, `release_ollama_slot` from `llm.admission`
- Produces: Guaranteed `release_ollama_slot(slot_token)` execution in `run_chat(..., stream=True)` even if `provider.chat()` raises before `iter_lines()`; Postgres-safe 768-dim vectors and SQLite `DATABASES` overrides in unit tests.

- [ ] **Step 1: Write failing regression test for streaming slot release on `provider.chat()` error**

In `backend/llm/tests/test_chat.py`, update `test_stream_provider_error_in_sse` or add `test_stream_provider_error_releases_slot`:

```python
    @patch('llm.chat.release_ollama_slot')
    @patch('llm.chat.acquire_ollama_slot', return_value='token-stream-err')
    @patch('llm.chat.resolve_provider')
    @patch('llm.chat.prepare_chat_messages')
    def test_stream_provider_error_releases_slot(
        self, mock_prepare, mock_resolve, _mock_acquire, mock_release,
    ):
        """Помилка provider.chat() у стрімі все одно звільняє Redis-слот."""
        mock_prepare.return_value = ([{'role': 'user', 'content': 'Hi'}], [])
        provider = MagicMock()
        provider.chat.side_effect = LLMProviderError('stream init fail')
        mock_resolve.return_value = provider

        response = run_chat(
            model='llama3',
            messages=[{'role': 'user', 'content': 'Hi'}],
            stream=True,
            workspace=self.workspace,
            user=self.user,
            prompt='Hi',
        )

        body = b''.join(response.streaming_content).decode('utf-8')
        self.assertIn('stream init fail', body)
        mock_release.assert_called_once_with('token-stream-err')
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test llm.tests.test_chat.RunChatTests.test_stream_provider_error_releases_slot`
Expected: FAIL with `AssertionError: Expected 'release_ollama_slot' to be called once. Called 0 times.`

- [ ] **Step 3: Fix `event_stream()` in `backend/llm/chat.py` so `finally` wraps the entire generator lifecycle**

In `backend/llm/chat.py`:

```python
    if stream:
        def event_stream():
            accumulated = []
            response = None

            try:
                if sources:
                    yield f'data: {json.dumps({"sources": sources})}\n\n'

                try:
                    response = provider.chat(
                        model,
                        prepared_messages,
                        stream=True,
                        options=options,
                    )
                except (LLMProviderError, requests.RequestException) as exc:
                    logger.warning(
                        'Streaming LLM error (workspace=%s, model=%s): %s',
                        getattr(workspace, 'pk', None),
                        model,
                        exc,
                        exc_info=True,
                    )
                    yield _provider_error_response(exc, stream=True)
                    return
                except Exception:
                    logger.exception('Unexpected streaming chat error')
                    yield _provider_error_response(
                        LLMProviderError('Внутрішня помилка чату'),
                        stream=True,
                    )
                    return

                try:
                    for line in response.iter_lines():
                        if not line:
                            continue
                        decoded = decode_stream_line(line)
                        if not decoded:
                            continue
                        yield f'data: {decoded}\n\n'
                        chunk_content = content_from_ollama_chunk(decoded)
                        if chunk_content:
                            accumulated.append(chunk_content)
                except (LLMProviderError, requests.RequestException) as exc:
                    logger.warning(
                        'Streaming LLM error (workspace=%s, model=%s): %s',
                        getattr(workspace, 'pk', None),
                        model,
                        exc,
                        exc_info=True,
                    )
                    yield _provider_error_response(exc, stream=True)
                except Exception:
                    logger.exception('Unexpected streaming chat error')
                    yield _provider_error_response(
                        LLMProviderError('Внутрішня помилка чату'),
                        stream=True,
                    )
                else:
                    log = log_workspace_chat_exchange(
                        workspace=workspace,
                        user=user,
                        prompt=log_prompt,
                        response=''.join(accumulated),
                        needs_handoff=needs_handoff,
                    )
                    meta = {'needs_handoff': needs_handoff}
                    if log:
                        meta['log_id'] = log.pk
                        yield f'data: {json.dumps(meta)}\n\n'
            finally:
                release_ollama_slot(slot_token)
                if response is not None and hasattr(response, 'close'):
                    try:
                        response.close()
                    except Exception as exc:
                        logger.warning(
                            'Error closing stream response: %s',
                            exc,
                            exc_info=True,
                        )

        return StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
        )
```

- [ ] **Step 4: Fix Postgres `VectorField(768)` and `NOT NULL` assumptions in RAG tests**

In `backend/workspaces/tests/test_hybrid_search.py` lines 72-89, add `embedding=[0.0] * 768` to each `DocumentChunk.objects.create(...)`:

```python
        dummy_vec = [0.0] * 768
        self.chunk_iso = DocumentChunk.objects.create(
            workspace=self.workspace,
            document=self.doc_ready,
            chunk_index=0,
            content='Сертифікація за міжнародним стандартом ISO-9001 гарантує якість.',
            embedding=dummy_vec,
        )
        self.chunk_dstu = DocumentChunk.objects.create(
            workspace=self.workspace,
            document=self.doc_ready,
            chunk_index=1,
            content='Національний стандарт ДСТУ 1.0 встановлює правила стандартизації.',
            embedding=dummy_vec,
        )
        self.chunk_failed = DocumentChunk.objects.create(
            workspace=self.workspace,
            document=self.doc_failed,
            chunk_index=0,
            content='Помилковий документ ISO-9001 не повинен знаходитися.',
            embedding=dummy_vec,
        )
```

In `backend/workspaces/tests/test_ingest_service.py`:
- Line 36: `mock_ollama_cls.return_value.embed.return_value = [0.1] * 768`
- Lines 114-117:
```python
        mock_ollama.embed_batch.side_effect = [
            [[0.1] * 768, [0.3] * 768],
            [[0.5] * 768],
        ]
```

- [ ] **Step 5: Fix SQLite engine assumptions in `backend/backups/tests/test_services.py`**

Wrap `test_restore_archive_path_traversal_prevention`, `test_restore_archive_rejects_symlinks`, and `test_find_latest_backup_filters_by_engine` with `DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(tmp_path / 'db.sqlite3')}}` inside `override_settings(...)` so they test SQLite behavior deterministically regardless of active CI database engine.

- [ ] **Step 6: Verify tests pass on both SQLite and live Docker PostgreSQL + Redis**

Run locally (SQLite): `backend\.venv\Scripts\python.exe backend\manage.py test llm.tests.test_chat workspaces.tests.test_hybrid_search workspaces.tests.test_ingest_service backups.tests.test_services`
Run in Docker (PostgreSQL + Redis): `docker compose exec -e CELERY_TASK_ALWAYS_EAGER=True backend python manage.py test --verbosity=1`
Expected: PASS (396+ tests, 0 failures, 0 errors).

- [ ] **Step 7: Commit**

```bash
git add backend/llm/chat.py backend/llm/tests/test_chat.py backend/workspaces/tests/test_hybrid_search.py backend/workspaces/tests/test_ingest_service.py backend/backups/tests/test_services.py
git commit -m "fix(tests): release streaming admission slot on init error and align Postgres tests"
```

---

### Task 2: Add Ruff Configuration, Dev Requirements, and Clean PEP 8 Lint

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/requirements-dev.txt`
- Modify: any `backend/**/*.py` files flagged by `ruff check .`

**Interfaces:**
- Produces: `backend/pyproject.toml` (`[tool.ruff]`) and `backend/requirements-dev.txt` consumed by CI and developers.

- [ ] **Step 1: Create `backend/pyproject.toml` and `backend/requirements-dev.txt`**

`backend/pyproject.toml`:
```toml
[tool.ruff]
target-version = "py312"
line-length = 120
exclude = [
    "**/migrations/*",
    ".venv",
    "staticfiles",
    "media",
]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B"]

[tool.ruff.lint.isort]
known-first-party = [
    "accounts",
    "backups",
    "chats",
    "config",
    "llm",
    "ollama_proxy",
    "workspaces",
]
```

`backend/requirements-dev.txt`:
```text
ruff>=0.8,<1.0
pytest>=8.0,<10.0
pytest-django>=4.9,<5.0
```

- [ ] **Step 2: Install dev requirements in `.venv` and run `ruff check .`**

Run:
`backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt`
`cd backend && .venv\Scripts\ruff.exe check .`

- [ ] **Step 3: Fix all reported Ruff lint findings across `backend/`**

Fix safe formatting/import/line-length issues reported by `ruff check .` (keeping all existing comments, docstrings, and behavior intact; re-run `ruff check .` until 0 errors).

- [ ] **Step 4: Run backend SQLite tests to ensure lint cleanups introduced zero regressions**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test --verbosity=1`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/requirements-dev.txt backend/
git commit -m "chore(backend): configure ruff linter and resolve PEP 8 lint findings"
```

---

### Task 3: Enforce Zero-Warning ESLint in Frontend

**Files:**
- Modify: `frontend/package.json:11`

- [ ] **Step 1: Update `"lint"` script in `frontend/package.json`**

Change line 11 from:
```json
    "lint": "eslint src --ext js,jsx",
```
to:
```json
    "lint": "eslint src --ext js,jsx --max-warnings=0",
```

- [ ] **Step 2: Verify lint, tests, and production build pass**

Run:
`cd frontend && npm run lint && npm test && npm run build`
Expected: Exit code 0 with 0 ESLint warnings/errors, all Vitest tests passing, clean Vite build.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json
git commit -m "chore(frontend): fail eslint on any warnings"
```

---

### Task 4: Upgrade `.github/workflows/ci.yml` (Ruff, Full Postgres+Redis Suite, Buildx & Live Smoke)

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `backend/pyproject.toml`, `backend/requirements-dev.txt`, `frontend/package.json`, `docker-compose.yml`, `docker-compose.prod.yml`.

- [ ] **Step 1: Update `.github/workflows/ci.yml`**

Update the 4 jobs in `.github/workflows/ci.yml`:
1. `backend`: install `requirements-dev.txt`, run `ruff check .` before license check & SQLite tests.
2. `backend-postgres`: add `redis:7.2.7-alpine` service (`6379:6379`), set `REDIS_URL: redis://127.0.0.1:6379/0`, run `python manage.py makemigrations --check --dry-run`, `python manage.py migrate --noinput`, and full `python manage.py test --verbosity=1`.
3. `frontend`: keep `npm ci`, license check, `npm run lint`, `npm test`, `npm run build`.
4. `compose`: keep YAML validations, add `docker/setup-buildx-action@v3`, build `backend worker frontend`, start `db redis`, start `--no-deps --wait backend`, start `--no-deps --wait frontend`, probe `http://127.0.0.1/api/health/` (verify HTTP 200, `"database": "ok"`, `"cache": "ok"`) and `http://127.0.0.1/` (HTTP 200), dump logs on failure, and `docker compose down -v` always.

- [ ] **Step 2: Verify compose build/smoke steps locally and check workflow syntax**

Run compose smoke sequence against Docker locally to verify exact flags (`--no-deps --wait` and curl assertions).

- [ ] **Step 3: Commit and push**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add ruff lint, full postgres+redis tests, migration check, and docker smoke test"
```

---

## Plan Self-Review

1. **Spec coverage:**
   - Python Ruff linter (`backend/pyproject.toml`, `backend/requirements-dev.txt`, CI step): covered in Task 2 & Task 4.
   - Migration check (`makemigrations --check --dry-run` on Postgres): covered in Task 4.
   - Full Postgres + Redis test suite + bugfixes uncovered during verification: covered in Task 1 & Task 4.
   - Frontend `--max-warnings=0`: covered in Task 3.
   - Docker Compose Buildx + live `/api/health/` + `/` smoke check: covered in Task 4.
2. **Placeholder scan:** No TBD, TODO, or abstract "fix as needed" items without concrete files/commands.
3. **Consistency:** `backend/pyproject.toml`, `backend/requirements-dev.txt`, `frontend/package.json`, `llm/chat.py` paths and commands match across all tasks and spec.
