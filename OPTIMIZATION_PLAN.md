# План оптимізації ZROZUMILOAI

Статус: **виконано** (P0 → P1 → P2, 2026-07-19)

## P0 — критично ✅
1. ✅ Async ingest документів (`workspaces/rag/tasks.py` + `document_views.py`)
2. ✅ Embed поза `transaction.atomic` + `bulk_create` (`rag/service.py`)
3. ✅ Streaming UI без повного re-render (rAF у `ChatPage`, append у embed)
4. ✅ Менше `refreshChats` під час autosave
5. ✅ Безпека: Ollama `127.0.0.1:11434`, Fernet для workspace keys
6. ✅ `widget.js` — прибрано cache-bust `Date.now()`
7. ✅ Ліміти chat messages (`CHAT_MAX_*`)
8. ✅ Unit-тести (crypto, tasks, ingest, widget auth, limits, SSE)

## P1 ✅
1. ✅ `requests.Session` (Ollama / Gemini)
2. ✅ Паралельний hybrid search
3. ✅ Дедуп `validation_error_message`
4. ✅ Тести widget auth / ingest / crypto
5. ✅ Lazy-load admin routes
6. ✅ Memoize Context providers
7. ✅ Спільний SSE util + AbortController у чаті
8. ✅ Poll статусу documents у WorkspacesPage

## P2 ✅
1. ✅ README оновлено (Gemini, Meilisearch, llm/, async RAG)
2. ✅ Production `SECURE_*` при `DEBUG=False`
3. ✅ `.env.example` без секретів + `FIELD_ENCRYPTION_KEY`
4. ✅ A11y: `aria-label` на textarea чату
5. ✅ `OPTIMIZATION_PLAN.md`

## Перед push на GitHub
- [ ] Переконайтесь, що `.env` у `.gitignore`
- [ ] Немає реальних API keys / widget tokens у комітах
- [ ] `pip install -r backend/requirements.txt` (додано `cryptography`)
- [ ] `python manage.py test` / `npm test`
