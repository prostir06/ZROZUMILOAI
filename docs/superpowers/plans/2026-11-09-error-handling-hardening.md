# Error Handling Hardening & Unit Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate silent error loss across frontend and backend try/catch and try/except blocks, surface actionable error feedback to users, preserve diagnostics in logs, add focused unit tests, and maintain PEP 8 and StandardJS compliance with concise comments only where unobvious.

**Architecture:**
1. Frontend State & UI Error Propagation:
   - In `useWorkspacesAdmin.js`: surface errors when loading widget tokens, documents, or models via `setError`.
   - In `useWorkspaceChats.js` / `WorkspaceChatsPage.jsx`: surface errors when loading workspace options.
   - In `WorkspaceContext.jsx` and `ChatContext.jsx`: expose `error` in context state and log with contextual warnings.
   - In `UsersPage.jsx`: set user error when `navigator.clipboard.writeText` fails.
   - In `DashboardPage.jsx`: log errors in `fetchJsonSafe` instead of bare catch.
   - In `base.js`: add defensive try/catch to `getAuthConfig()` to prevent uncaught network exceptions.
2. Backend Diagnostics Hardening:
   - In `workspaces/document_views.py`: broaden file deletion exception handling to `Exception` with logging before database delete.
   - In `workspaces/crypto.py`: add `exc_info=True` to `decrypt_secret` failure logging for debugging corrupted tokens or key mismatches.
3. Unit Test Coverage:
   - Add frontend tests for `useWorkspacesAdmin`, `useWorkspaceChats`, `UsersPage`, and `base.js`.
   - Add backend tests for document deletion file error handling and crypto decryption failure logging.

**Tech Stack:** Python 3.12, Django 5, DRF, React 18, Vitest, StandardJS/ESLint.

## Global Constraints

- Preserve PEP 8 and StandardJS compliance; zero ESLint warnings or errors (`npm run lint`).
- Short, concise comments ONLY where behavior is unobvious; no redundant comments.
- All backend (`manage.py test`, `pytest`) and frontend (`npm test`) suites must pass.

---

### Task 1: Fix Silent Error Drops in Frontend Data Hooks and Contexts

**Files:**
- Modify: `frontend/src/api/base.js:89-95`
- Modify: `frontend/src/pages/workspaces/useWorkspacesAdmin.js:50-112`
- Modify: `frontend/src/pages/WorkspaceChatsPage.jsx:40-52`
- Modify: `frontend/src/context/WorkspaceContext.jsx:12-38`
- Modify: `frontend/src/context/ChatContext.jsx:12-38`
- Modify: `frontend/src/pages/DashboardPage.jsx:30-40`
- Modify: `frontend/src/pages/UsersPage.jsx:124-131`
- Test: `frontend/src/pages/workspaces/useWorkspacesAdmin.test.jsx`
- Test: `frontend/src/pages/WorkspaceChatsPage.test.jsx`
- Test: `frontend/src/api/base.test.js`

- [ ] **Step 1: Write failing unit tests for error surfaces**
- [ ] **Step 2: Implement error propagation in hooks, contexts, and pages**
- [ ] **Step 3: Run frontend tests and linter**
- [ ] **Step 4: Commit**

---

### Task 2: Backend Error Logging Hardening & Backend Unit Tests

**Files:**
- Modify: `backend/workspaces/document_views.py:121-130`
- Modify: `backend/workspaces/crypto.py:74-78`
- Test: `backend/workspaces/tests/test_document_api.py`
- Test: `backend/workspaces/tests/test_crypto.py`

- [ ] **Step 1: Write failing backend unit tests**
- [ ] **Step 2: Implement logging hardening in document views and crypto**
- [ ] **Step 3: Run backend test suite**
- [ ] **Step 4: Commit**

---

### Task 3: Full Stack Verification & Quality Gate

- [ ] **Step 1: Run full verification suite across all apps and frontend**
- [ ] **Step 2: Verify zero lint errors and clean test output**
