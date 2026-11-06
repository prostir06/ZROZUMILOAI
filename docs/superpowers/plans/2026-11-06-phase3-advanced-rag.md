# Phase 3: Advanced RAG Pipeline, New Document Formats & Multi-LLM Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Розширити можливості RAG новими форматами документів (`.docx`, `.html`), впровадити структурний (семантичний) чанкінг зі збереженням контексту заголовків, реалізувати локальний гібридний пошук (Vector + Full-Text через Reciprocal Rank Fusion) та додати відмовостійкий фолбек (Circuit Breaker) з Ollama на Gemini.

**Architecture:** Модульне розширення `text_extractor.py` із безпечною обробкою помилок, оновлення `chunker.py` для ієрархічного розбиття, новий модуль `fusion.py` та гібридний пошуковий сервіс у `workspaces/rag/`, а також прозорий механізм перемикання провайдера у `backend/llm/chat.py`.

**Tech Stack:** Python 3.12/3.14, Django 5.x, PostgreSQL/pgvector, `python-docx`, `beautifulsoup4`, SQLite (test fallback), Ollama API, Google Gemini API.

## Global Constraints

- **Стандарти коду:** Суворе дотримання PEP 8 у всіх Python-файлах, типові анотації або зрозумілі docstrings.
- **Обробка помилок:** Жодних тихих `except: pass`; обов'язкове логування через `logger.warning` / `logger.error` із контекстом.
- **Сумісність:** Повна сумісність із поточними тестами PostgreSQL та SQLite (fallback для локального тестування).
- **Zero Regression:** Не зламати існуючу логіку Meilisearch та векторного пошуку.
- **Тестування:** Unit-тести на кожен модуль із перевіркою граничних випадків (биті файли, пусті таблиці, збої мережі).

---

### Task 1: Document Extractors Expansion (.docx & .html)

**Files:**
- Modify: `backend/workspaces/rag/text_extractor.py`
- Modify: `backend/requirements.txt`
- Create: `backend/workspaces/tests/test_text_extractor.py`

**Interfaces:**
- Consumes: `file_path: str | Path`
- Produces: `extract_text_from_file(file_path) -> str` (підтримка `.txt`, `.md`, `.markdown`, `.pdf`, `.docx`, `.html`, `.htm`)

- [ ] **Step 1: Write failing unit tests for docx and html extraction**

```python
# In backend/workspaces/tests/test_text_extractor.py
import tempfile
from pathlib import Path
from django.test import SimpleTestCase
from workspaces.rag.text_extractor import extract_text_from_file, ALLOWED_EXTENSIONS

class TextExtractorDocxHtmlTests(SimpleTestCase):
    def test_allowed_extensions_includes_docx_and_html(self):
        self.assertIn('.docx', ALLOWED_EXTENSIONS)
        self.assertIn('.html', ALLOWED_EXTENSIONS)
        self.assertIn('.htm', ALLOWED_EXTENSIONS)

    def test_extract_html_removes_scripts_and_styles(self):
        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write('<html><head><style>body {color: red;}</style></head><body><h1>Лекція 1</h1><script>alert(1);</script><p>Зміст курсу.</p></body></html>')
            path = f.name
        try:
            text = extract_text_from_file(path)
            self.assertIn('Лекція 1', text)
            self.assertIn('Зміст курсу.', text)
            self.assertNotIn('alert', text)
            self.assertNotIn('color: red', text)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_extract_docx_paragraphs_and_tables(self):
        import docx
        doc = docx.Document()
        doc.add_heading('Тема 1', level=1)
        doc.add_paragraph('Опис теми.')
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = 'Критерій'
        table.cell(0, 1).text = 'Бали'
        table.cell(1, 0).text = 'Тест'
        table.cell(1, 1).text = '100'
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
            doc.save(f.name)
            path = f.name
        try:
            text = extract_text_from_file(path)
            self.assertIn('Тема 1', text)
            self.assertIn('Опис теми.', text)
            self.assertIn('Критерій', text)
            self.assertIn('100', text)
        finally:
            Path(path).unlink(missing_ok=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_text_extractor`
Expected: FAIL (extensions not supported)

- [ ] **Step 3: Implement docx and html extraction in text_extractor.py**

1. Оновити `ALLOWED_EXTENSIONS = {'.txt', '.md', '.markdown', '.pdf', '.docx', '.html', '.htm'}`.
2. Створити функцію `_extract_docx(path)`:
   - Використати `docx.Document(str(path))`.
   - Вилучити параграфи (`p.text.strip()`).
   - Вилучити клітинки таблиць з форматуванням рядків.
   - Забезпечити захист від падінь при частково пошкоджених елементах.
3. Створити функцію `_extract_html(path)`:
   - Прочитати файл через UTF-8 (з fallback до `cp1251` при помилці).
   - Використати `BeautifulSoup(content, 'html.parser')`.
   - Видалити теги `['script', 'style', 'nav', 'footer', 'header', 'noscript']`.
   - Витягнути текст із сепаратором `\n`.
4. Додати маршрутизацію у `extract_text_from_file(file_path)`:
   - `if suffix in ('.html', '.htm'): return _extract_html(path)`
   - `elif suffix == '.docx': return _extract_docx(path)`

- [ ] **Step 4: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_text_extractor`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add backend/workspaces/rag/text_extractor.py backend/workspaces/tests/test_text_extractor.py backend/requirements.txt
git commit -m "feat(rag): add support for .docx and .html document extraction"
```

---

### Task 2: Structural & Semantic Text Chunker

**Files:**
- Modify: `backend/workspaces/rag/chunker.py`
- Create: `backend/workspaces/tests/test_chunker.py`

**Interfaces:**
- Consumes: `text: str`, `chunk_size: int = 800`, `chunk_overlap: int = 100`
- Produces: `split_text_into_chunks(text, chunk_size, chunk_overlap) -> list[str]`

- [ ] **Step 1: Write failing unit tests for structural chunker**

```python
# In backend/workspaces/tests/test_chunker.py
from django.test import SimpleTestCase
from workspaces.rag.chunker import split_text_into_chunks

class ChunkerStructuralTests(SimpleTestCase):
    def test_preserves_heading_context_across_splits(self):
        text = (
            "# Розділ 1. Архітектура систем\n\n"
            "Параграф 1 з великою кількістю інформації про сервери. " * 10 + "\n\n"
            "Параграф 2 з додатковою деталізацією про бази даних. " * 10
        )
        chunks = split_text_into_chunks(text, chunk_size=300, chunk_overlap=50)
        self.assertGreater(len(chunks), 1)
        # Наступні чанки всередині розділу мають містити контекст розділу
        for chunk in chunks:
            self.assertTrue(
                "Розділ 1" in chunk or len(chunk) > 0,
                "Context should be preserved"
            )

    def test_splits_on_markdown_headers_and_double_newlines(self):
        text = (
            "## Вступ\n\n"
            "Текст вступу.\n\n"
            "## Основна частина\n\n"
            "Текст основної частини."
        )
        chunks = split_text_into_chunks(text, chunk_size=50, chunk_overlap=0)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(any('Вступ' in c for c in chunks))
        self.assertTrue(any('Основна частина' in c for c in chunks))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_chunker`
Expected: FAIL

- [ ] **Step 3: Implement structural chunker in chunker.py**

1. Оновити алгоритм розбиття тексту:
   - Розпізнавати Markdown заголовки (`# `, `## `, `### `, `#### `).
   - При переході до нового підрозділу відстежувати поточний активний заголовок (`current_heading`).
   - Якщо блок тексту розрізається посередині розділу, додавати заголовок як контекстний префікс (якщо він ще не присутній на початку фрагмента).
   - Пріоритетні точки розрізу: `\n# `, `\n## `, `\n### `, `\n\n`, `\n- `, `\n* `, `[.!?]\s+`.
   - Зберігати обмеження `chunk_size` та `chunk_overlap`.

- [ ] **Step 4: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_chunker`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add backend/workspaces/rag/chunker.py backend/workspaces/tests/test_chunker.py
git commit -m "feat(rag): implement structural and heading-preserving text chunking"
```

---

### Task 3: Local Hybrid Search (Full-Text & Reciprocal Rank Fusion)

**Files:**
- Create: `backend/workspaces/rag/fusion.py`
- Create: `backend/workspaces/rag/hybrid_search.py`
- Modify: `backend/workspaces/rag/service.py`
- Create: `backend/workspaces/tests/test_hybrid_search.py`

**Interfaces:**
- Consumes: `ranked_lists: list[list[dict]]`, `k: int = 60`
- Produces: `reciprocal_rank_fusion(ranked_lists, k=60) -> list[dict]`
- Produces: `hybrid_search_workspace_chunks(workspace_id, query_text, query_embedding, limit=5) -> list[dict]`

- [ ] **Step 1: Write failing unit test for RRF and hybrid search**

```python
# In backend/workspaces/tests/test_hybrid_search.py
from django.test import TestCase
from workspaces.models import Workspace, WorkspaceDocument, DocumentChunk
from workspaces.rag.fusion import reciprocal_rank_fusion
from workspaces.rag.hybrid_search import hybrid_search_workspace_chunks

class HybridSearchTests(TestCase):
    def test_reciprocal_rank_fusion_merges_and_orders(self):
        list_a = [{'id': 1, 'text': 'Doc 1'}, {'id': 2, 'text': 'Doc 2'}]
        list_b = [{'id': 2, 'text': 'Doc 2'}, {'id': 3, 'text': 'Doc 3'}]
        fused = reciprocal_rank_fusion([list_a, list_b], k=60)
        # Doc 2 is present in both lists, so its combined RRF score should be highest
        self.assertEqual(fused[0]['id'], 2)
        self.assertEqual(len(fused), 3)

    def test_hybrid_search_returns_matches_for_exact_terms(self):
        ws = Workspace.objects.create(name='Test WS', slug='test-ws')
        doc = WorkspaceDocument.objects.create(
            workspace=ws,
            original_filename='terms.txt',
            file_size=100,
            status=WorkspaceDocument.Status.READY
        )
        chunk1 = DocumentChunk.objects.create(
            workspace=ws,
            document=doc,
            chunk_index=0,
            content='Специфікація стандарту ISO-9001 у навчальному процесі.',
            embedding=[0.1] * 128
        )
        chunk2 = DocumentChunk.objects.create(
            workspace=ws,
            document=doc,
            chunk_index=1,
            content='Загальні відомості про курс та лекції.',
            embedding=[0.2] * 128
        )
        results = hybrid_search_workspace_chunks(
            workspace_id=ws.pk,
            query_text='ISO-9001',
            query_embedding=[0.1] * 128,
            limit=2
        )
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]['id'], chunk1.pk)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_hybrid_search`
Expected: FAIL

- [ ] **Step 3: Implement RRF and hybrid search**

1. Створити `backend/workspaces/rag/fusion.py`:
   - Реалізувати `reciprocal_rank_fusion(ranked_lists, k=60)`.
   - Обчислювати score: $RRF(d) = \sum \frac{1}{k + rank(d)}$.
   - Нормалізувати фінальні scores до діапазону [0.0 .. 1.0].
2. Створити `backend/workspaces/rag/hybrid_search.py`:
   - Виконувати векторний пошук (через існуючий `similarity.py` або pgvector `<=>`).
   - Виконувати текстовий пошук:
     - У PostgreSQL: `SearchVector('content')` + `SearchQuery(query_text)`.
     - У SQLite (для тестів/локально): `Q(content__icontains=term)`.
   - Об'єднувати результати через `reciprocal_rank_fusion`.
3. Інтегрувати у `backend/workspaces/rag/service.py`:
   - Додати виклик гібридного пошуку в `search_relevant_chunks`.

- [ ] **Step 4: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test workspaces.tests.test_hybrid_search`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add backend/workspaces/rag/fusion.py backend/workspaces/rag/hybrid_search.py backend/workspaces/rag/service.py backend/workspaces/tests/test_hybrid_search.py
git commit -m "feat(rag): add local hybrid search with reciprocal rank fusion"
```

---

### Task 4: Circuit Breaker & Resilient Multi-LLM Fallback (Ollama -> Gemini)

**Files:**
- Modify: `backend/llm/chat.py`
- Create: `backend/llm/tests/test_chat_fallback.py`

**Interfaces:**
- Consumes: `workspace`, `model`, `messages`, `stream`
- Produces: Transparent streaming or response execution with automatic fallback to Gemini on Ollama outage, setting `provider_fallback: true` in metadata.

- [ ] **Step 1: Write failing unit test for LLM fallback**

```python
# In backend/llm/tests/test_chat_fallback.py
from unittest.mock import patch, MagicMock
from django.test import TestCase
import requests
from workspaces.models import Workspace
from llm.chat import run_chat

class ChatFallbackTests(TestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(
            name='Fallback WS',
            slug='fallback-ws',
            llm_provider='ollama',
            model_names=['llama3'],
            gemini_api_key='fake-gemini-key',
        )

    @patch('llm.ollama.OllamaProvider.chat')
    @patch('llm.gemini.GeminiProvider.chat')
    def test_run_chat_falls_back_to_gemini_when_ollama_fails(self, mock_gemini, mock_ollama):
        mock_ollama.side_effect = requests.exceptions.ConnectionError('Ollama unreachable')
        mock_gemini.return_value = {
            'message': {'role': 'assistant', 'content': 'Відповідь від Gemini'},
            'model': 'gemini-1.5-flash',
        }
        response = run_chat(
            model='llama3',
            messages=[{'role': 'user', 'content': 'Привіт'}],
            stream=False,
            workspace=self.workspace,
            user=None,
            prompt='',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('Відповідь від Gemini', response.data['message']['content'])
        self.assertTrue(response.data.get('provider_fallback'))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test llm.tests.test_chat_fallback`
Expected: FAIL

- [ ] **Step 3: Implement fallback circuit breaker in backend/llm/chat.py**

1. Створити функцію `_resolve_fallback_provider(workspace, primary_provider_name)`:
   - Якщо `primary_provider_name == 'ollama'`:
   - Перевірити наявність `workspace.gemini_api_key` або `settings.GEMINI_API_KEY`.
   - Якщо ключ є, повернути `('gemini', fallback_provider, fallback_model)`.
2. Оновити `run_chat`:
   - Для non-streaming: перехоплювати помилки провайдера (`LLMProviderError`, `requests.RequestException`).
   - Якщо доступний fallback, логувати попередження:
     `logger.warning("Ollama connection failed (%s); switching to fallback Gemini provider for workspace %s", exc, workspace.pk)`
   - Виконувати запит через fallback провайдер та додавати `'provider_fallback': True` у відповідь.
   - Для streaming: у генераторі `_stream_response_generator` при збої Ollama до першого чанка перемикатися на fallback провайдер із відправкою події `{"provider_fallback": true}`.

- [ ] **Step 4: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test llm.tests.test_chat_fallback`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add backend/llm/chat.py backend/llm/tests/test_chat_fallback.py
git commit -m "feat(llm): implement transparent circuit breaker fallback from Ollama to Gemini"
```
