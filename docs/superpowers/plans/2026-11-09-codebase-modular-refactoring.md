# Codebase Modular Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompose monolithic code files into modular, focused components across backend backups, frontend workspace management, embed chat widget, and global CSS stylesheets without altering external runtime behavior or public APIs.

**Architecture:** 
1. `backend/backups/services.py` (~590 lines) is refactored into a `backend/backups/engine/` package (`archive.py`, `postgres.py`, `sqlite.py`) while retaining the full public interface and test backward compatibility of `BackupService` in `services.py`.
2. `frontend/src/pages/WorkspacesPage.jsx` (~585 lines) delegates workspace CRUD state and actions to a custom hook `useWorkspacesAdmin.js` and splits modal editing into `WorkspaceModal.jsx`.
3. `frontend/src/embed/embed-app.js` (~650 lines) is modularized into `embed-state.js` (state management & config parsing), `embed-api.js` (network requests & streaming), and `embed-dom.js` (rendering helpers & UI listeners).
4. `frontend/src/styles/index.css` (~1100 lines) is partitioned into cohesive thematic modules (`base.css`, `layout.css`, `forms.css`, `tables.css`, `components.css`) imported via `index.css`.

**Tech Stack:** Python 3.12+, Django 5, DRF, Pytest, React 18, Vite, Vitest, StandardJS/ESLint, CSS3.

## Global Constraints

- 100% backward compatibility for all existing public methods and behavior of `BackupService` and Django management commands (`create_backup`, `restore_backup`).
- PEP 8 compliance for all Python code; preserve existing comments, docstrings, and Ukrainian user-facing strings.
- StandardJS/ESLint and React Hook rules compliance; zero lint errors (`npm run lint`).
- All existing tests in backend (`manage.py test`, `pytest backend/backups/tests/`) and frontend (`npm test`) must pass with zero regressions.

---

### Task 1: Decompose `backend/backups/services.py` into Engine Submodules

**Files:**
- Create: `backend/backups/engine/__init__.py`
- Create: `backend/backups/engine/archive.py`
- Create: `backend/backups/engine/postgres.py`
- Create: `backend/backups/engine/sqlite.py`
- Modify: `backend/backups/services.py:1-591`
- Test: `backend/backups/tests/test_services.py`
- Test: `backend/backups/tests/test_commands.py`

**Interfaces:**
- Produces:
  - `backend.backups.engine.archive`:
    - `pack_archive(backup_dir, db_dump_path, dump_arcname, include_media=True) -> Path`
    - `read_manifest(filepath) -> dict | None`
    - `resolve_safe_path(backup_dir, filename) -> Path`
    - `unpack_media_member(tar, member, media_root) -> None`
    - `restore_archive(backup_dir, backup_path, engine_type, restore_dump_fn) -> dict`
  - `backend.backups.engine.postgres`:
    - `dump_postgresql(target_filepath, db_config) -> None`
    - `restore_postgresql(filepath, db_config) -> None`
    - `run_psql(db_config, *extra_args) -> None`
    - `quote_pg_ident(ident) -> str`
  - `backend.backups.engine.sqlite`:
    - `dump_sqlite(target_filepath, db_config) -> None`
    - `restore_sqlite(filepath, db_config) -> None`
  - `BackupService` in `backend.backups.services` retains all existing public and helper methods (`create_backup`, `restore_backup`, `list_backups`, `get_backup_path`, `delete_backup`, `find_latest_backup`, `restore_latest_backup`, and delegation helpers like `_pack_archive`, `_read_manifest`, `_dump_postgresql`, `_dump_sqlite`, `_restore_postgresql`, `_restore_sqlite`, etc.) so all unit tests continue to pass untouched.

- [ ] **Step 1: Write a unit test verifying engine submodule imports and BackupService facade delegation**

In `backend/backups/tests/test_services.py`:
```python
    def test_engine_submodules_exist_and_facade_delegates(self):
        """Перевірити, що engine-модулі експортують функції та BackupService їх викликає."""
        from backups.engine import archive, postgres, sqlite

        self.assertTrue(callable(archive.pack_archive))
        self.assertTrue(callable(archive.read_manifest))
        self.assertTrue(callable(postgres.dump_postgresql))
        self.assertTrue(callable(postgres.restore_postgresql))
        self.assertTrue(callable(sqlite.dump_sqlite))
        self.assertTrue(callable(sqlite.restore_sqlite))
```

- [ ] **Step 2: Run pytest to verify the new test fails**

Run:
```powershell
backend\.venv\Scripts\python.exe -m pytest backend\backups\tests\test_services.py -k test_engine_submodules
```
Expected: FAIL (`ModuleNotFoundError: No module named 'backups.engine'`).

- [ ] **Step 3: Implement `backend/backups/engine/` modules and refactor `BackupService`**

1. Create `backend/backups/engine/__init__.py`.
2. Extract archive handling and manifest manipulation to `backend/backups/engine/archive.py`.
3. Extract `pg_dump` and `psql` restore logic to `backend/backups/engine/postgres.py`.
4. Extract `sqlite3.backup` logic to `backend/backups/engine/sqlite.py`.
5. In `backend/backups/services.py`, import functions from `backups.engine` and delegate class methods to them while preserving method signatures and docstrings.

- [ ] **Step 4: Run the full backups test suite**

Run:
```powershell
backend\.venv\Scripts\python.exe -m pytest backend\backups\tests\ -v
```
Expected: All 45+ tests pass with zero failures.

- [ ] **Step 5: Commit**

```powershell
git add backend/backups/engine/ backend/backups/services.py backend/backups/tests/test_services.py
git commit -m "refactor(backups): decompose BackupService into engine submodules"
```

---

### Task 2: Decompose `WorkspacesPage.jsx` into Custom Hook and Subcomponents

**Files:**
- Create: `frontend/src/pages/workspaces/useWorkspacesAdmin.js`
- Create: `frontend/src/pages/workspaces/WorkspaceModal.jsx`
- Modify: `frontend/src/pages/WorkspacesPage.jsx:1-585`
- Test: `frontend/src/pages/WorkspacesPage.test.jsx` (or run `npm test`)

**Interfaces:**
- Produces:
  - `useWorkspacesAdmin()`: hook encapsulating workspaces, users, models list fetching, form state (`form`, `setForm`, `formMode`, `editingId`), document uploading, and CRUD operations (`handleSave`, `handleDelete`, `openCreate`, `openEdit`, `closeForm`).
  - `WorkspaceModal`: modal dialog containing the workspace editing form with system prompt, temperature, provider models, and embedded sections (`MeilisearchSection`, `WidgetTokensSection`, `DocumentsRagSection`, `AnalyticsSection`).
  - `WorkspacesPage`: clean, high-level page component displaying page title, header actions, and workspace table/cards.

- [ ] **Step 1: Create unit test for `useWorkspacesAdmin` hook or component render test**

Create `frontend/src/pages/workspaces/useWorkspacesAdmin.test.jsx` testing data loading and initial state of `useWorkspacesAdmin`.

- [ ] **Step 2: Run Vitest to verify the test fails**

Run:
```powershell
npm --prefix frontend test -- useWorkspacesAdmin.test.jsx --run
```
Expected: FAIL (`Cannot find module './useWorkspacesAdmin'`).

- [ ] **Step 3: Implement `useWorkspacesAdmin.js`, `WorkspaceModal.jsx`, and refactor `WorkspacesPage.jsx`**

1. Move state management and async handlers from `WorkspacesPage.jsx` into `frontend/src/pages/workspaces/useWorkspacesAdmin.js`.
2. Extract the workspace modal form markup and logic into `frontend/src/pages/workspaces/WorkspaceModal.jsx`.
3. Simplify `frontend/src/pages/WorkspacesPage.jsx` so it uses `useWorkspacesAdmin()` and renders the table and `WorkspaceModal`.

- [ ] **Step 4: Run frontend tests and linter**

Run:
```powershell
npm --prefix frontend test -- --run
npm --prefix frontend run lint
```
Expected: PASS, zero errors.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/pages/workspaces/useWorkspacesAdmin.js frontend/src/pages/workspaces/WorkspaceModal.jsx frontend/src/pages/workspaces/useWorkspacesAdmin.test.jsx frontend/src/pages/WorkspacesPage.jsx
git commit -m "refactor(frontend): decompose WorkspacesPage with useWorkspacesAdmin hook and WorkspaceModal"
```

---

### Task 3: Decompose `frontend/src/embed/embed-app.js` into State, API, and DOM Modules

**Files:**
- Create: `frontend/src/embed/embed-state.js`
- Create: `frontend/src/embed/embed-api.js`
- Create: `frontend/src/embed/embed-dom.js`
- Modify: `frontend/src/embed/embed-app.js:1-650`
- Test: `frontend/src/embed/embed-modules.test.js`

**Interfaces:**
- Produces:
  - `embed-state.js`: manages embedded chat state (messages list, active session, conversation ID, workspace config, theme settings, greeting/FAQ questions).
  - `embed-api.js`: handles API interactions (`fetchWorkspaceConfig`, `sendChatMessageStream`, `sendFeedback`).
  - `embed-dom.js`: DOM helpers, message bubble rendering (assistant icon, user bubbles, feedback buttons, markdown rendering), and event listeners.
  - `embed-app.js`: lightweight entrypoint orchestrating initialization, state subscriptions, and user input events.

- [ ] **Step 1: Write unit tests for `embed-state.js` and `embed-api.js` in `embed-modules.test.js`**

Verify state transitions, message appending, and error formatting in `frontend/src/embed/embed-modules.test.js`.

- [ ] **Step 2: Run Vitest to verify tests fail**

Run:
```powershell
npm --prefix frontend test -- embed-modules.test.js --run
```
Expected: FAIL (`Cannot find module './embed-state.js'`).

- [ ] **Step 3: Implement `embed-state.js`, `embed-api.js`, `embed-dom.js`, and refactor `embed-app.js`**

1. Create `embed-state.js` exporting state store and state accessor functions.
2. Create `embed-api.js` exporting API fetch functions.
3. Create `embed-dom.js` exporting DOM rendering utilities.
4. Update `embed-app.js` to coordinate between modules.

- [ ] **Step 4: Run frontend tests, build, and linter**

Run:
```powershell
npm --prefix frontend test -- --run
npm --prefix frontend run lint
npm --prefix frontend run build
```
Expected: All tests pass, build succeeds (embed widget bundled without issues), and linter is clean.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/embed/embed-state.js frontend/src/embed/embed-api.js frontend/src/embed/embed-dom.js frontend/src/embed/embed-modules.test.js frontend/src/embed/embed-app.js
git commit -m "refactor(embed): split embed-app.js into state, api, and dom modules"
```

---

### Task 4: Modularize Global Stylesheet (`index.css`)

**Files:**
- Create: `frontend/src/styles/base.css`
- Create: `frontend/src/styles/layout.css`
- Create: `frontend/src/styles/forms.css`
- Create: `frontend/src/styles/tables.css`
- Create: `frontend/src/styles/components.css`
- Modify: `frontend/src/styles/index.css:1-1100`

**Interfaces:**
- Produces:
  - `frontend/src/styles/base.css`: CSS custom properties (`:root`), CSS reset, body background gradients, typography rules.
  - `frontend/src/styles/layout.css`: Sidebar, app container, navbar, header, layout grid utilities.
  - `frontend/src/styles/forms.css`: Input fields, textareas, select dropdowns, buttons (`.btn`, `.btn-primary`, `.btn-ghost`), toggles/switches.
  - `frontend/src/styles/tables.css`: Data tables, table rows/cells, pagination, status pills and badges.
  - `frontend/src/styles/components.css`: Modals, cards, empty states, spinners, alert callouts.
  - `frontend/src/styles/index.css`: Clean entrypoint importing the 5 thematic modules via `@import './base.css';` etc.

- [ ] **Step 1: Verify CSS modules file structure and import hierarchy**

Create the 5 CSS files and verify they partition all selectors from `index.css` without orphan selectors or missing variables.

- [ ] **Step 2: Update `frontend/src/styles/index.css` to import all submodules**

```css
@import './base.css';
@import './layout.css';
@import './forms.css';
@import './tables.css';
@import './components.css';
```

- [ ] **Step 3: Run frontend build and test suite**

Run:
```powershell
npm --prefix frontend run build
npm --prefix frontend test -- --run
npm --prefix frontend run lint
```
Expected: Vite build succeeds, styles bundle properly into `dist/assets/`, tests pass.

- [ ] **Step 4: Commit**

```powershell
git add frontend/src/styles/base.css frontend/src/styles/layout.css frontend/src/styles/forms.css frontend/src/styles/tables.css frontend/src/styles/components.css frontend/src/styles/index.css
git commit -m "refactor(styles): split index.css into thematic stylesheets"
```

---

### Step 5: Final Full-Stack Verification

- Run backend test suite:
  ```powershell
  backend\.venv\Scripts\python.exe backend\manage.py test workspaces accounts chats llm ollama_proxy config
  backend\.venv\Scripts\python.exe -m pytest backend\backups\tests\ -q
  ```
- Run frontend test suite, lint, and production build:
  ```powershell
  npm --prefix frontend test -- --run
  npm --prefix frontend run lint
  npm --prefix frontend run build
  ```
