# P0 Ops Risks Remediation Design

**Date:** 2026-11-13  
**Status:** approved for planning  
**Scope:** document three production P0 risks and the target remediation; implementation follows a separate plan.

## Goal

Close the three sharpest production risks found in the Nov 13 audit:

1. Backup format contract drift (`.tar.gz` vs `.sql.gz` docs/scripts)
2. Redis fail-open under load for Ollama admission and Telegram poll locks
3. Health/monitoring semantics when Ollama is down

Deliverables of this cycle of design:

- This spec (risks + target state + acceptance)
- Implementation plan: `docs/superpowers/plans/2026-11-13-p0-ops-risks-remediation.md`

## Out of scope

- Off-box backup copy automation (rsync/S3)
- Encrypted backups
- CI restore-drill for real `.tar.gz`
- Telegram webhook mode
- Meilisearch admin test button
- Splitting large frontend modules
- Changing `OLLAMA_ADMISSION_LIMIT` semantics beyond fail-closed behavior
- Making Compose restart backend when Ollama is down

## Locked decisions

| Topic | Decision |
| --- | --- |
| Redis outage when `REDIS_URL` is set | Fail-closed: chat/widget → HTTP 503; Telegram poll iteration skips (no second poller) |
| Empty `REDIS_URL` (local without Redis) | Unchanged: no admission slot / no poll lock required |
| Backup format | Source of truth is `.tar.gz` (DB + media). Fix cron, prune, and runbook to match |
| Health | Compose health stays non-strict `/api/health/`. External monitoring uses `/api/health/?strict=1` |

## Risk 1 — Backup format mismatch

### Current state

- Create path writes `backup_*.tar.gz` with DB dump + `media/` + `manifest.json` (`backend/backups/engine/archive.py`, `backend/backups/services.py`).
- Allowed extensions include `.sql`, `.sqlite3`, `.db`, `.tar.gz` — not `.sql.gz` as a first-class restore format.
- `docs/ops/vps-runbook.md` still describes restore from `.sql.gz` / legacy SQL alongside `.tar.gz`.
- `scripts/backup-cron.sh` prune still matches `*.sql.gz`.

### Why it matters

An operator following the runbook can place or expect a `.sql.gz` that the app does not restore as the primary archive. Prune/docs diverge from what create actually produces, so the only good copy may be misunderstood or left undocumented.

### Target state

- Cron scripts create and document `.tar.gz` only as the supported backup artifact.
- Prune primarily targets `*.tar.gz`. Legacy `*.sql` / `*.sqlite3` / `*.db` may still be pruned for one cleanup pass so old junk disappears; `.sql.gz` is not recommended and is removed from runbook restore steps.
- Runbook restore steps: put newest `.tar.gz` in `./backup/`, set `FORCE_DB_RESTORE=1`, restart backend, then set it back to `0`.
- No change to archive packing logic unless a bug is found while aligning docs/scripts.

### Acceptance

- Runbook has no recommended `.sql.gz` restore path.
- Cron comments/prune patterns agree with `.tar.gz` as the primary format.
- A reviewer can restore from docs alone without meeting an unsupported extension.

## Risk 2 — Redis fail-open for admission and Telegram locks

### Current state

- `backend/llm/admission.py`: when `REDIS_URL` is set and Redis/SET fails, acquire logs a warning and **returns `None` (fail-open)**, so chat proceeds without a slot.
- `backend/workspaces/telegram/poller.py`: when Redis is missing/errors, `_acquire_or_renew_lock` **returns `True` (fail-open)**, so multiple workers can long-poll the same bot.

### Why it matters

On a loaded VPS, Redis outage currently removes the only guard that keeps Ollama at one chat and Telegram at one poller. That recreates queue pile-ups and duplicate updates — the failure modes the admission/Telegram work was meant to prevent.

### Target state

| Condition | Chat / widget / `run_chat` | Telegram poller |
| --- | --- | --- |
| Empty `REDIS_URL` | No slot (local OK) | No lock required (local OK) |
| `REDIS_URL` set, Redis OK, slot busy | Existing `429` / `ollama_busy` | Skip iteration if lock held by another worker |
| `REDIS_URL` set, Redis/SET/eval error | **HTTP 503**, log with `exc_info` | **Do not fail open** — skip iteration / do not poll |

Notes:

- Fail-closed chat response is **503**, not `ollama_busy` 429 (429 means “someone holds the slot”; 503 means “admission infrastructure unavailable”).
- Existing unit tests that assert fail-open must be updated to fail-closed when `REDIS_URL` is set.
- Empty-`REDIS_URL` tests stay fail-open / skip-lock.

### Acceptance

- With `REDIS_URL` set and mocked Redis connection/SET failure: chat API returns 503; admission does not return `None` as success.
- Telegram worker with Redis error skips poll iteration instead of returning “lock acquired”.
- Local empty `REDIS_URL` path still works without Redis.

## Risk 3 — Health / Ollama monitoring semantics

### Current state

- `backend/config/health.py` already returns `ollama` in the payload and supports `?strict=1` → HTTP 503 when Ollama (or other checked components) is degraded.
- Default `/api/health/` stays HTTP 200 while DB is up, even if Ollama is `error` / payload `status: degraded` — intentional so Compose does not restart backend during Ollama restarts.
- Compose backend healthcheck uses non-strict `/api/health/`; `depends_on` ollama is `service_started`, not `service_healthy`.

### Why it matters

If uptime checks hit the non-strict URL, Ollama downtime looks green. Operators need an explicit contract in the runbook.

### Target state

- **No Compose behavior change:** non-strict healthcheck and `service_started` for Ollama remain.
- Runbook documents: container liveness = `/api/health/`; alerting / uptime = `/api/health/?strict=1`.
- Tests (or extend existing ones) lock the contract: non-strict can be 200 with `ollama: error` and `status: degraded`; strict returns 503 in that case.

### Acceptance

- Runbook states both URLs and their purpose.
- Automated test covers non-strict vs strict Ollama-down behavior.

## Implementation order

1. Backup cron + runbook alignment to `.tar.gz`
2. Redis fail-closed for admission + Telegram poller (+ tests)
3. Health/runbook contract + tests for `strict=1`

## Testing strategy

- Unit: admission Redis error → not fail-open when URL set; poller Redis error → skip
- Unit/API: health non-strict vs strict
- Docs review: runbook restore and monitoring sections
- Manual smoke after implement: `docker compose` health 200; `curl '/api/health/?strict=1'` when Ollama stopped → 503

## Success criteria

The three P0 risks are either removed or have an explicit, tested operator contract. No scope creep into P1/P2 backlog items listed in the Nov 13 audit.
