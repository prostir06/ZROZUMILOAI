# P0 Ops Risks Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three production P0 risks identified in the audit: backup format contract drift (`.tar.gz`), Redis fail-closed behavior for Ollama admission and Telegram poll locks, and health/monitoring contract verification.

**Architecture:**
- **Storage & Ops:** Standardize `.tar.gz` (DB dump + `media/` + `manifest.json`) as the single supported backup artifact. Update `scripts/backup-cron.sh` and `docs/ops/vps-runbook.md` to remove legacy `.sql.gz` restore instructions.
- **Concurrency & Throttling:** When `REDIS_URL` is set, Redis outages switch from fail-open to fail-closed: `backend/llm/admission.py` raises `AdmissionUnavailable` triggering HTTP 503 in chat endpoints, and `backend/workspaces/telegram/poller.py` skips poll iterations to prevent concurrent poller conflict. When `REDIS_URL` is empty, local dev without Redis remains supported.
- **Monitoring:** Formally lock the contract in tests and runbooks: container liveness uses `/api/health/` (200 while DB is up), while external uptime monitors use `/api/health/?strict=1` (503 when Ollama is degraded).

**Tech Stack:** Python 3.12, Django 5.2, Redis 7.2, Bash, Docker Compose.

## Global Constraints

- Never store or recommend `.sql.gz` as a primary backup format; `.tar.gz` is the sole source of truth.
- When `REDIS_URL` is configured, Redis failures must fail closed (chat returns 503, Telegram skips poll); when `REDIS_URL` is empty, local behavior without Redis is preserved.
- Keep non-strict `/api/health/` returning 200 while DB is up so Docker Compose does not restart backend during Ollama model loading.
- Maintain 100% test passing rate across `backend` and `frontend`; zero Ruff and ESLint warnings.

---

### Task 1: Backup Format Contract Alignment (`.tar.gz`)

**Files:**
- Modify: `scripts/backup-cron.sh`
- Modify: `docs/ops/vps-runbook.md`

**Interfaces:**
- Produces: Consistent documentation and cron scripting for `.tar.gz` backups.
- Consumes: `backend/backups/engine/archive.py` (`backup_*.tar.gz`).

- [ ] **Step 1: Update `scripts/backup-cron.sh`**

Align comments and pruning in `scripts/backup-cron.sh`:
- Comment: Explicitly state that `create_backup` produces `.tar.gz` containing database dump, `media/`, and `manifest.json`.
- Prune: Prioritize `.tar.gz` files while retaining cleanup for legacy uncompressed or legacy formats.

- [ ] **Step 2: Update `docs/ops/vps-runbook.md`**

In `docs/ops/vps-runbook.md`:
- Under "Backup (RPO 24h)": Remove mentions of `.sql.gz` and `.sql`. Clarify that `create_backup` outputs a full `.tar.gz` archive.
- Under "Restore drill": Document that operators must place the newest `.tar.gz` into `./backup/`, set `FORCE_DB_RESTORE=1`, restart backend, and unset it back to `0`.

- [ ] **Step 3: Verify script syntax**

Run: `bash -n scripts/backup-cron.sh` (or syntax check in git bash/powershell).

- [ ] **Step 4: Commit**

```bash
git add scripts/backup-cron.sh docs/ops/vps-runbook.md
git commit -m "docs(ops): standardize backup format contract on .tar.gz in cron and runbook"
```

---

### Task 2: Redis Fail-Closed for Ollama Admission

**Files:**
- Modify: `backend/llm/admission.py`
- Modify: `backend/llm/chat.py`
- Modify: `backend/llm/tests/test_admission.py`
- Modify: `backend/chats/tests/test_chat_view.py`

**Interfaces:**
- Produces: `AdmissionUnavailable` exception in `backend.llm.admission`, HTTP 503 response in `backend.llm.chat.run_chat`.
- Consumes: `settings.REDIS_URL`, `get_redis_connection`.

- [ ] **Step 1: Write failing unit test in `backend/llm/tests/test_admission.py`**

Replace `test_redis_error_fails_open_with_warning` with `test_redis_error_raises_admission_unavailable_when_redis_url_set`:
```python
    def test_redis_error_raises_admission_unavailable_when_redis_url_set(self):
        client = MagicMock()
        client.set.side_effect = ConnectionError('redis down')
        with override_settings(REDIS_URL='redis://localhost:6379/0'):
            with self.assertLogs('llm.admission', level=logging.ERROR):
                with self.assertRaises(AdmissionUnavailable):
                    acquire_ollama_slot(client=client)
```

Verify that empty `REDIS_URL` still succeeds without error:
```python
    @override_settings(REDIS_URL='')
    def test_missing_redis_url_fails_open_without_client(self):
        token = acquire_ollama_slot(client=None)
        self.assertIsNone(token)
```

- [ ] **Step 2: Run test to verify failure**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test llm.tests.test_admission`
Expected: FAIL (`AdmissionUnavailable` not found or not raised).

- [ ] **Step 3: Implement `AdmissionUnavailable` in `backend/llm/admission.py`**

In `backend/llm/admission.py`:
```python
class AdmissionUnavailable(Exception):
    """Інфраструктура допуску недоступна (Redis не відповідає при заданому REDIS_URL)."""
```

In `acquire_ollama_slot`:
```python
    is_redis_configured = bool((getattr(settings, 'REDIS_URL', '') or '').strip())
    if client is None and not is_redis_configured:
        return None
...
        except Exception as exc:
            if is_redis_configured:
                logger.error(
                    'Ollama admission unavailable, failing closed: %s',
                    exc,
                    exc_info=True,
                )
                raise AdmissionUnavailable(str(exc)) from exc
            logger.warning(
                'Ollama admission unavailable without REDIS_URL, failing open: %s',
                exc,
                exc_info=True,
            )
            return None
```

- [ ] **Step 4: Handle `AdmissionUnavailable` in `backend/llm/chat.py`**

In `backend/llm/chat.py`:
Import `AdmissionUnavailable`.
In `run_chat`:
```python
    try:
        slot_token = acquire_ollama_slot()
    except OllamaBusy:
        logger.warning(
            'Ollama busy (workspace=%s)',
            getattr(workspace, 'pk', None),
        )
        return _ollama_busy_response()
    except AdmissionUnavailable as exc:
        logger.error('Admission infrastructure unavailable: %s', exc)
        if stream:
            return _provider_error_response(
                'Сервіс тимчасово недоступний через збій черги запитів.',
                stream=True,
            )
        return Response(
            {'error': 'Сервіс тимчасово недоступний. Спробуйте пізніше.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
```

- [ ] **Step 5: Add integration test in `backend/chats/tests/test_chat_view.py`**

Test that when `acquire_ollama_slot` raises `AdmissionUnavailable`, `/api/chats/` (or widget chat) returns HTTP 503 with error message.

- [ ] **Step 6: Run tests and linter**

Run:
`backend\.venv\Scripts\python.exe backend\manage.py test llm.tests chats.tests`
`backend\.venv\Scripts\ruff.exe check backend/`
Expected: PASS, 0 lint errors.

- [ ] **Step 7: Commit**

```bash
git add backend/llm/admission.py backend/llm/chat.py backend/llm/tests/test_admission.py backend/chats/tests/
git commit -m "fix(llm): fail-closed with HTTP 503 on Redis error during admission when REDIS_URL is configured"
```

---

### Task 3: Redis Fail-Closed for Telegram Poll Lock

**Files:**
- Modify: `backend/workspaces/telegram/poller.py`
- Modify: `backend/workspaces/tests/test_telegram_poller.py`

**Interfaces:**
- Produces: Fail-closed lock acquisition in `TelegramBotWorker._acquire_or_renew_lock`.
- Consumes: `settings.REDIS_URL`, `get_redis_connection`.

- [ ] **Step 1: Write failing tests in `backend/workspaces/tests/test_telegram_poller.py`**

Add tests:
1. `test_worker_skips_polling_when_redis_fails_and_redis_url_set`:
   With `REDIS_URL='redis://localhost:6379/0'`, mock Redis connection raising `ConnectionError`. Verify `_acquire_or_renew_lock()` returns `False`, and `worker.step()` does NOT call `client.get_updates`.
2. `test_worker_polls_when_redis_url_empty`:
   With `REDIS_URL=''`, verify `_acquire_or_renew_lock()` returns `True`, allowing local execution without Redis.

- [ ] **Step 2: Run test to verify failure**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_telegram_poller`
Expected: FAIL (currently returns `True` on error).

- [ ] **Step 3: Implement fail-closed in `backend/workspaces/telegram/poller.py`**

In `TelegramBotWorker._acquire_or_renew_lock`:
```python
    def _acquire_or_renew_lock(self) -> bool:
        redis_url = (getattr(settings, "REDIS_URL", "") or "").strip()
        if not redis_url:
            # Local dev without Redis: proceed without distributed lock
            return True

        redis_client = _get_redis_client()
        if redis_client is None:
            logger.error(
                "Redis client unavailable for bot %s while REDIS_URL is set (failing closed)",
                self.bot_id,
            )
            return False

        key = f"telegram:poll_lock:{self.bot_id}"
        try:
            res = redis_client.eval(_RENEW_OR_ACQUIRE_LUA, 1, key, self.lock_token, 60)
            return bool(res)
        except Exception as exc:
            logger.error(
                "Redis error acquiring poll lock for bot %s while REDIS_URL is set (failing closed): %s",
                self.bot_id,
                exc,
                exc_info=True,
            )
            return False
```

- [ ] **Step 4: Run tests and linter**

Run:
`backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_telegram_poller`
`backend\.venv\Scripts\ruff.exe check backend/`
Expected: PASS, 0 lint errors.

- [ ] **Step 5: Commit**

```bash
git add backend/workspaces/telegram/poller.py backend/workspaces/tests/test_telegram_poller.py
git commit -m "fix(telegram): fail-closed poll lock on Redis error when REDIS_URL is set"
```

---

### Task 4: Health Monitoring Contract & Verification

**Files:**
- Modify: `docs/ops/vps-runbook.md`
- Modify: `backend/config/tests/test_health.py`

**Interfaces:**
- Produces: Documented and verified dual-health contract (`/api/health/` non-strict vs `/api/health/?strict=1` strict).

- [ ] **Step 1: Review & extend `backend/config/tests/test_health.py`**

Ensure tests explicitly assert:
1. When Ollama is degraded (`status_val == 'error'`):
   - Non-strict `GET /api/health/` returns HTTP 200 with `status: "degraded"` and `ollama: "error"`.
   - Strict `GET /api/health/?strict=1` returns HTTP 503 with `status: "degraded"` and `ollama: "error"`.
2. When DB fails:
   - Both non-strict and strict return HTTP 503 with `database: "error"`.

- [ ] **Step 2: Update `docs/ops/vps-runbook.md`**

In `docs/ops/vps-runbook.md` under "Health":
- Clarify the explicit contract:
  - `/api/health/` (Docker Compose / internal load balancer): HTTP 200 while database is alive; prevents unnecessary container restarts during heavy Ollama load or model reloads.
  - `/api/health/?strict=1` (External alerting / UptimeRobot / BetterUptime): HTTP 503 as soon as any subsystem (including Ollama) degrades, triggering operational alerts.

- [ ] **Step 3: Run comprehensive verification**

1. `backend\.venv\Scripts\ruff.exe check backend/`
2. `backend\.venv\Scripts\python.exe backend\manage.py test`
3. `npm --prefix frontend run lint`
4. `npm --prefix frontend test`

- [ ] **Step 4: Commit**

```bash
git add docs/ops/vps-runbook.md backend/config/tests/test_health.py
git commit -m "docs(health): solidify dual-health monitoring contract in runbook and unit tests"
```

---

## Plan Self-Review

1. **Spec Coverage:**
   - Risk 1 (Backup format contract drift): Task 1.
   - Risk 2 (Redis fail-closed for admission and Telegram poller): Task 2 & Task 3.
   - Risk 3 (Health/monitoring semantics when Ollama is down): Task 4.
2. **No Placeholders:** All tasks define exact files, test cases, and code blocks.
3. **Consistency:** Exception names, HTTP status codes, and environment variables match identically across tasks.
