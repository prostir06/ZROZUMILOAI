# Product Evolution: Knowledge Gaps Lifecycle & Advanced Chats Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full lifecycle for identified Knowledge Gaps (resolving/reopening gaps with timestamp audit in database and UI) and add workspace & date range filtering to Chats Info logs and data exports.

**Architecture:**
1. Database & Models: `WorkspaceChatLog` gains `is_resolved` (boolean, default False) and `resolved_at` (DateTimeField, nullable) with an index on `(workspace, is_resolved)`.
2. Backend API: 
   - `PATCH /api/workspaces/<workspace_id>/analytics/gaps/<log_id>/resolve/` toggles or sets the resolution state of a gap for authorized teachers and staff.
   - `get_workspace_analytics(workspace, date_range, resolved=None)` optionally filters knowledge gaps by resolution status.
   - `filtered_chat_logs(params)` in `backend/chats/log_views.py` supports `workspace_id`, `date_range` (today, 7d, 30d, all), and `is_resolved` filtering for both listing and export.
3. Frontend:
   - `KnowledgeGapsTable.jsx` adds a resolution badge ("Відкрито" / "Вирішено"), filter tab/toggle for unresolved vs all gaps, and a one-click resolve button.
   - `WorkspaceChatsPage.jsx` adds workspace dropdown filter and date range selector, passing these params to API and export downloads.

**Tech Stack:** Python 3.12+, Django 5, DRF, PostgreSQL / SQLite, React 18, Vitest, StandardJS/ESLint.

## Global Constraints

- Migrations must be safe on both PostgreSQL and SQLite.
- Ukrainian localization for all user-facing UI labels, statuses, and API error messages.
- PEP 8 compliance for Python; ESLint and React hooks compliance for JavaScript.
- All backend (`manage.py test`, `pytest`) and frontend (`npm test`, `npm run lint`) tests must pass with zero regressions.

---

### Task 1: Add `is_resolved` and `resolved_at` to `WorkspaceChatLog` and Migration

**Files:**
- Modify: `backend/chats/models.py:35-73`
- Create: `backend/chats/migrations/0003_workspacechatlog_resolution.py`
- Modify: `backend/chats/serializers.py`
- Test: `backend/chats/tests/test_models.py` (or `backend/chats/tests/test_analytics.py`)

**Interfaces:**
- Produces:
  - `WorkspaceChatLog.is_resolved: models.BooleanField(default=False)`
  - `WorkspaceChatLog.resolved_at: models.DateTimeField(null=True, blank=True)`
  - Index on `['workspace', 'is_resolved']`
  - Serializer field `is_resolved` and `resolved_at` in `WorkspaceChatLogSerializer`

- [ ] **Step 1: Write failing unit test for `is_resolved` and `resolved_at` fields**

In `backend/chats/tests/test_analytics.py`:
```python
    def test_workspace_chat_log_has_resolution_fields(self):
        log = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            prompt='Питання',
            response='Відповідь',
            needs_handoff=True,
            is_resolved=False,
        )
        self.assertFalse(log.is_resolved)
        self.assertIsNone(log.resolved_at)

        log.is_resolved = True
        log.resolved_at = timezone.now()
        log.save()
        log.refresh_from_db()
        self.assertTrue(log.is_resolved)
        self.assertIsNotNone(log.resolved_at)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
backend\.venv\Scripts\python.exe backend\manage.py test chats.tests.test_analytics -k test_workspace_chat_log_has_resolution_fields
```
Expected: FAIL (`TypeError: WorkspaceChatLog() got an unexpected keyword argument 'is_resolved'`).

- [ ] **Step 3: Update `backend/chats/models.py`, generate migration, and update `serializers.py`**

In `backend/chats/models.py`:
```python
    is_resolved = models.BooleanField(
        default=False,
        help_text='Чи опрацьовано цю прогалину викладачем/адміністратором',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
```
Add index `models.Index(fields=['workspace', 'is_resolved'])` to `Meta.indexes`.
Run `makemigrations` and ensure clean migration `0003_workspacechatlog_resolution.py`.
Add `is_resolved` and `resolved_at` to `WorkspaceChatLogSerializer.Meta.fields`.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```powershell
backend\.venv\Scripts\python.exe backend\manage.py test chats
```
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/chats/models.py backend/chats/migrations/0003_workspacechatlog_resolution.py backend/chats/serializers.py backend/chats/tests/test_analytics.py
git commit -m "feat(chats): add resolution tracking fields and migration to WorkspaceChatLog"
```

---

### Task 2: Backend API for Resolving Knowledge Gaps & Filtering Logs

**Files:**
- Modify: `backend/chats/analytics_service.py:70-95`
- Modify: `backend/chats/analytics_views.py:1-87`
- Modify: `backend/chats/log_views.py:34-47`
- Modify: `backend/workspaces/urls.py:55-65`
- Test: `backend/chats/tests/test_analytics.py`
- Test: `backend/chats/tests/test_log_views.py`

**Interfaces:**
- Produces:
  - `PATCH /api/workspaces/<workspace_id>/analytics/gaps/<log_id>/resolve/`: returns `{"id": log_id, "is_resolved": bool, "resolved_at": str | null}`
  - `get_workspace_analytics(workspace, date_range='30d', resolved=None)`: includes `is_resolved` and `resolved_at` in each item of `knowledge_gaps`.
  - `filtered_chat_logs(params)`: supports `workspace_id`, `range` (`today`, `7d`, `30d`), and `is_resolved` (`true`/`false`).

- [ ] **Step 1: Write failing tests for gap resolve endpoint and filtering**

In `backend/chats/tests/test_analytics.py`:
Test that `PATCH /api/workspaces/<id>/analytics/gaps/<log_id>/resolve/`:
1. Requires teacher or staff permission.
2. Updates `is_resolved=True` and sets `resolved_at`.
3. With `{"resolved": false}`, clears `is_resolved` and `resolved_at`.

In `backend/chats/tests/test_log_views.py`:
Test that `filtered_chat_logs` filters by `workspace_id` and `is_resolved`.

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
backend\.venv\Scripts\python.exe backend\manage.py test chats.tests.test_analytics chats.tests.test_log_views
```
Expected: FAIL.

- [ ] **Step 3: Implement `WorkspaceKnowledgeGapResolveView`, update `analytics_service.py`, and `filtered_chat_logs`**

1. In `backend/chats/analytics_views.py`, create `WorkspaceKnowledgeGapResolveView(APIView)`:
   - Verifies workspace access.
   - Retrieves `WorkspaceChatLog` matching `pk=log_id, workspace_id=workspace_id`.
   - Reads `resolved = request.data.get('resolved', True)`.
   - Updates `is_resolved` and `resolved_at` (now or None), saves `update_fields=['is_resolved', 'resolved_at']`.
   - Returns serialized status.
2. Register route in `backend/workspaces/urls.py`:
   `path('<int:workspace_id>/analytics/gaps/<int:log_id>/resolve/', WorkspaceKnowledgeGapResolveView.as_view(), name='workspace_gap_resolve')`
3. In `backend/chats/analytics_service.py`, add `is_resolved` and `resolved_at` to the returned `knowledge_gaps` dicts.
4. In `backend/chats/log_views.py`, add `workspace_id`, `is_resolved`, and date filtering to `filtered_chat_logs`.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```powershell
backend\.venv\Scripts\python.exe backend\manage.py test chats workspaces
```
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/chats/analytics_service.py backend/chats/analytics_views.py backend/chats/log_views.py backend/workspaces/urls.py backend/chats/tests/test_analytics.py backend/chats/tests/test_log_views.py
git commit -m "feat(analytics): add knowledge gap resolve endpoint and workspace/date log filters"
```

---

### Task 3: Frontend Knowledge Gaps Resolution UI & Filters

**Files:**
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/components/analytics/KnowledgeGapsTable.jsx`
- Modify: `frontend/src/pages/workspaces/AnalyticsSection.jsx`
- Test: `frontend/src/components/analytics/KnowledgeGapsTable.test.jsx`

**Interfaces:**
- Produces:
  - `api.resolveKnowledgeGap(workspaceId, logId, resolved = true)` in `client.js`
  - Interactive "Вирішено" / "Відкрити знову" button and status badge in `KnowledgeGapsTable.jsx`
  - Filter toggle in `KnowledgeGapsTable` or `AnalyticsSection` ("Всі" / "Лише відкриті" / "Лише вирішені")

- [ ] **Step 1: Write failing component test for `KnowledgeGapsTable` with resolve action**

In `frontend/src/components/analytics/KnowledgeGapsTable.test.jsx`:
- Test that resolution status is displayed ("Вирішено" / "Потребує уваги").
- Test clicking resolve button triggers `onResolveClick(gap)`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
npm --prefix frontend test -- KnowledgeGapsTable.test.jsx --run
```
Expected: FAIL.

- [ ] **Step 3: Implement client method and update `KnowledgeGapsTable.jsx` and `AnalyticsSection.jsx`**

1. In `frontend/src/api/client.js`:
   ```javascript
   resolveKnowledgeGap: (workspaceId, logId, resolved = true) =>
     request(`/workspaces/${workspaceId}/analytics/gaps/${logId}/resolve/`, {
       method: 'PATCH',
       body: JSON.stringify({ resolved }),
     }),
   ```
2. In `KnowledgeGapsTable.jsx`:
   - Add status column with badge (`gap.is_resolved ? 'Вирішено' : 'Потребує матеріалу'`).
   - Add action button (`gap.is_resolved ? '↩ Відкрити' : '✓ Вирішено'`) calling `onResolveClick(gap)`.
   - Add filter toggle above the table ("Лише актуальні" / "Всі").
3. In `AnalyticsSection.jsx`, handle `handleResolveGap` calling `api.resolveKnowledgeGap` and refreshing or updating local state optimistically.

- [ ] **Step 4: Run frontend tests and linter**

Run:
```powershell
npm --prefix frontend test -- --run
npm --prefix frontend run lint
```
Expected: PASS, 0 lint errors.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/api/client.js frontend/src/components/analytics/KnowledgeGapsTable.jsx frontend/src/pages/workspaces/AnalyticsSection.jsx frontend/src/components/analytics/KnowledgeGapsTable.test.jsx
git commit -m "feat(frontend): add knowledge gap resolution button, badges, and filters"
```

---

### Task 4: Advanced Workspace & Date Filters in `WorkspaceChatsPage.jsx`

**Files:**
- Modify: `frontend/src/pages/WorkspaceChatsPage.jsx`
- Modify: `frontend/src/pages/WorkspaceChatsPage.test.jsx` (or add test)

**Interfaces:**
- Produces:
  - Workspace selector dropdown in Chats Info filter bar (loaded via `api.getWorkspaces()`).
  - Date range selector (`today`, `7d`, `30d`, `all`).
  - Handoff, feedback, workspace, and date range query parameters sent to `api.getWorkspaceChatLogs` and export links.

- [ ] **Step 1: Write test for workspace and date filters in `WorkspaceChatsPage`**

Test that changing workspace dropdown or date range selector triggers `api.getWorkspaceChatLogs` with corresponding parameters.

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
npm --prefix frontend test -- WorkspaceChatsPage.test.jsx --run
```

- [ ] **Step 3: Implement filters in `WorkspaceChatsPage.jsx`**

1. Add state `selectedWorkspace` (`''` for all) and `dateRange` (`'all'`, `'today'`, `'7d'`, `'30d'`).
2. Fetch workspaces list on mount.
3. Pass `workspace_id` and `range` to `api.getWorkspaceChatLogs` and to export URL generators (`api.getWorkspaceChatLogsExportUrl(...)`).
4. Render filter dropdowns in the toolbar.

- [ ] **Step 4: Run full verification suite**

Run:
```powershell
npm --prefix frontend test -- --run
npm --prefix frontend run lint
npm --prefix frontend run build
backend\.venv\Scripts\python.exe backend\manage.py test workspaces accounts chats llm ollama_proxy config
```
Expected: All tests pass, build succeeds cleanly.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/pages/WorkspaceChatsPage.jsx frontend/src/pages/WorkspaceChatsPage.test.jsx
git commit -m "feat(frontend): add workspace and date range filters to Chats Info page"
```
