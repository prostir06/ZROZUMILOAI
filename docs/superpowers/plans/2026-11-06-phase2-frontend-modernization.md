# Phase 2: Frontend Refactoring, UX & Markdown Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Декомпонувати монолітний `ChatPage.jsx` (~730 рядків) на сфокусовані компоненти та хуки, впровадити безпечний рендеринг Markdown із підсвічуванням коду та копіюванням, і модулізувати стилі відповідно до стандартів HTML5, CSS3 та StandardJS.

**Architecture:** Виділення рендерингу форматування у `MarkdownMessage`, логіки SSE-стрімінгу та автоскролу у кастомні хуки `useChatStream` та `useChatScroll`, розбиття сторінки чату на атомарні компоненти (`ChatMessage`, `ChatInput`, `ModelSelector`, `SourceCitations`) та винесення стилів розмітки у `markdown.css`.

**Tech Stack:** React 18, Vite 5, `markdown-to-jsx`, Vitest, StandardJS/ESLint.

## Global Constraints

- **Стандарти коду**: Суворе дотримання ESLint (StandardJS правил проєкту), PEP 8 у бекенді, семантичний HTML5, валідний CSS3.
- **Обробка помилок**: Закрити прогалини `try/catch`, логувати помилки через `console.error` із контекстом, не ковтати винятки тихо.
- **Коментарі**: Короткі та лаконічні коментарі лише там, де поведінка неочевидна (наприклад, логика RAF буферизації або автоскролу).
- **Zero Regression**: Зберегти 100% сумісність з існуючими роутами (`/chat/:chatId`, `/workspace/:workspaceId`), обмеженнями доступу non-admin до воркспейсів та бекенд SSE форматом.
- **Тестування**: Vitest unit-тести для нових компонентів та утиліт.

---

### Task 1: MarkdownMessage Component with Code Copy & Safe Links

**Files:**
- Create: `frontend/src/components/chat/MarkdownMessage.jsx`
- Create: `frontend/src/styles/markdown.css`
- Test: `frontend/src/components/chat/MarkdownMessage.test.jsx`

**Interfaces:**
- Consumes: `content: string`, `isStreaming?: boolean`
- Produces: `<MarkdownMessage content={text} />` — рендерить Markdown (списки, таблиці, заголовки, блоки коду з підсвічуванням та кнопкою копіювання, безпечні зовнішні посилання).

- [ ] **Step 1: Write failing unit test for MarkdownMessage**

```jsx
// In frontend/src/components/chat/MarkdownMessage.test.jsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { MarkdownMessage } from './MarkdownMessage';

describe('MarkdownMessage', () => {
  it('renders formatted text and links with target blank and safe rel', () => {
    const markdown = 'Hello **bold** [example](https://example.com)';
    const { container } = render(<MarkdownMessage content={markdown} />);
    
    expect(container.querySelector('strong')).toHaveTextContent('bold');
    const link = container.querySelector('a');
    expect(link).toHaveAttribute('href', 'https://example.com');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders fenced code block with language and copy button', () => {
    const codeMarkdown = '```python\nprint("hello")\n```';
    const { container } = render(<MarkdownMessage content={codeMarkdown} />);
    
    expect(container.querySelector('pre')).toBeInTheDocument();
    expect(container.querySelector('code')).toHaveTextContent('print("hello")');
    expect(screen.getByRole('button', { name: /копіювати/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/MarkdownMessage.test.jsx`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement MarkdownMessage and markdown.css**

1. Створити `frontend/src/components/chat/MarkdownMessage.jsx`:
   - Використати `markdown-to-jsx`.
   - Оголосити кастомний рендерер для `a`: додавати `target="_blank" rel="noopener noreferrer"`.
   - Оголосити кастомний рендерер для `pre`: обгортка `code-block` із шапкою (назва мови, кнопка копіювання з візуальною зміною стану на «Скопійовано!» на 2 секунди через `navigator.clipboard.writeText`).
   - Захист від падінь при некоректному тексті (`try/catch` з fallback до звичайного тексту).
2. Створити `frontend/src/styles/markdown.css` із класами для таблиць, списків, цитат і блоків коду.
3. Підключити `markdown.css` у `main.jsx` або `MarkdownMessage.jsx`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/chat/MarkdownMessage.test.jsx`
Expected: PASS

- [ ] **Step 5: Run linter and commit**

```bash
cd frontend && npm run lint
git add frontend/src/components/chat/MarkdownMessage.jsx frontend/src/styles/markdown.css frontend/src/components/chat/MarkdownMessage.test.jsx frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add MarkdownMessage component with code copy and safe link rendering"
```

---

### Task 2: Custom Chat Hooks (useChatScroll and useChatStream)

**Files:**
- Create: `frontend/src/hooks/useChatScroll.js`
- Create: `frontend/src/hooks/useChatStream.js`
- Test: `frontend/src/hooks/useChatScroll.test.js`

**Interfaces:**
- `useChatScroll(messagesContainerRef, messagesEndRef)`: повертає `{ isAtBottomRef, showScrollButton, scrollToBottom, handleScroll }`.
- `useChatStream({ onChunk, onSources, onMeta, onError, onDone })`: повертає `{ streaming, startStream, abortStream }`.

- [ ] **Step 1: Write unit test for useChatScroll logic**

```javascript
// In frontend/src/hooks/useChatScroll.test.js
import { describe, it, expect } from 'vitest';
import { isNearBottom } from './useChatScroll';

describe('useChatScroll helpers', () => {
  it('detects near bottom within threshold', () => {
    // scrollHeight=1000, scrollTop=750, clientHeight=200 => distance = 50 <= threshold 80
    expect(isNearBottom({ scrollHeight: 1000, scrollTop: 750, clientHeight: 200 }, 80)).toBe(true);
    // distance = 150 > threshold 80
    expect(isNearBottom({ scrollHeight: 1000, scrollTop: 650, clientHeight: 200 }, 80)).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/useChatScroll.test.js`
Expected: FAIL

- [ ] **Step 3: Implement useChatScroll and useChatStream**

1. `useChatScroll.js`:
   - Експортувати чисту функцію `isNearBottom(el, threshold = 80)`.
   - Хук `useChatScroll`: відстежує `onScroll` через `requestAnimationFrame`, оновлює стан `showScrollButton`, підтримує плавний скрол `scrollToBottom`.
2. `useChatStream.js`:
   - Інкапсулює `AbortController`, накопичення токенів у черзі, оновлення через `requestAnimationFrame` (запобігає зависанню UI при частому стрімінгу).
   - Обробляє події `data: {"sources":[...]}`, звичайні чанки Ollama/Gemini, та фінальний `data: {"log_id":...}`.
   - Забезпечує коректне очищення при розмонтуванні компонента (abort active stream).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/hooks/useChatScroll.test.js`
Expected: PASS

- [ ] **Step 5: Run linter and commit**

```bash
cd frontend && npm run lint
git add frontend/src/hooks/
git commit -m "feat(frontend): add useChatScroll and useChatStream custom hooks"
```

---

### Task 3: Atomic Chat Components (SourceCitations, ChatMessage, ChatInput, ModelSelector)

**Files:**
- Create: `frontend/src/components/chat/SourceCitations.jsx`
- Create: `frontend/src/components/chat/ChatMessage.jsx`
- Create: `frontend/src/components/chat/ChatInput.jsx`
- Create: `frontend/src/components/chat/ModelSelector.jsx`
- Test: `frontend/src/components/chat/SourceCitations.test.jsx`

**Interfaces:**
- `SourceCitations`: `{ sources: Array<{ content, score, document_name }> }` — рендерить бейджі з відсотком релевантності та назвою документа.
- `ChatMessage`: `{ message, onFeedback, isStreaming }` — аватарка, MarkdownMessage, кнопки оцінки 👍/👎, цитати.
- `ChatInput`: `{ input, setInput, onSubmit, onStop, streaming, disabled }` — авторозширення textarea, клавіші Enter/Shift+Enter.
- `ModelSelector`: `{ models, selectedModel, onSelectModel, workspaces, selectedWorkspaceId, onSelectWorkspace, isAdmin }`.

- [ ] **Step 1: Write unit test for SourceCitations**

```jsx
// In frontend/src/components/chat/SourceCitations.test.jsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { SourceCitations } from './SourceCitations';

describe('SourceCitations', () => {
  it('renders citation badges with document name and score', () => {
    const sources = [
      { document_name: 'syllabus.pdf', score: 0.85, content: 'Course intro' },
    ];
    render(<SourceCitations sources={sources} />);
    expect(screen.getByText(/syllabus\.pdf/i)).toBeInTheDocument();
    expect(screen.getByText(/85%/i)).toBeInTheDocument();
  });

  it('renders nothing when sources empty', () => {
    const { container } = render(<SourceCitations sources={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/SourceCitations.test.jsx`
Expected: FAIL

- [ ] **Step 3: Implement components**

1. `SourceCitations.jsx`: бейджі джерел із розгортанням фрагмента тексту за кліком.
2. `ChatMessage.jsx`: картка повідомлення користувача чи асистента, підтримка MarkdownMessage, відображення джерел, кнопки зворотної оцінки.
3. `ChatInput.jsx`: textarea з автоматичною корекцією висоти (max 200px), гарячими клавішами та кнопкою зупинки стріму.
4. `ModelSelector.jsx`: селектор моделі та воркспейсу з чіткими лейблами та провайдерськими бейджами.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/chat/SourceCitations.test.jsx`
Expected: PASS

- [ ] **Step 5: Run linter and commit**

```bash
cd frontend && npm run lint
git add frontend/src/components/chat/
git commit -m "feat(frontend): create modular chat components (citations, message, input, selector)"
```

---

### Task 4: Refactor ChatPage.jsx to Composed Architecture

**Files:**
- Modify: `frontend/src/pages/ChatPage.jsx`
- Test: Existing vitest tests + manual route verification

**Interfaces:**
- Consumes: `useParams`, `useNavigate`, `useAuth`, `useChats`, `useWorkspaces`, `useChatScroll`, `useChatStream`.
- Coordinates data fetching, state management, and renders `<ModelSelector />`, `<ChatMessage />`, `<ChatInput />`.

- [ ] **Step 1: Refactor ChatPage.jsx to use new subcomponents and hooks**

1. Замінити інлайнову логіку стрімінгу на `useChatStream`.
2. Замінити інлайновий скролінг на `useChatScroll`.
3. Замінити ручний рендеринг повідомлень на `<ChatMessage />`.
4. Замінити селектор моделей на `<ModelSelector />`.
5. Замінити textarea та кнопки на `<ChatInput />`.
6. Зменшити розмір файлу з ~730 рядків до ~180 рядків чистого координаційного коду.

- [ ] **Step 2: Run all frontend tests and linter**

Run: `cd frontend && npm test -- --run && npm run lint`
Expected: ALL PASS

- [ ] **Step 3: Run frontend production build to verify bundle**

Run: `cd frontend && npm run build`
Expected: Build succeeds without errors.

- [ ] **Step 4: Commit changes**

```bash
git add frontend/src/pages/ChatPage.jsx
git commit -m "refactor(frontend): decompose ChatPage into modular components and custom hooks"
```

---

### Task 5: CSS Modularization and Clean Up

**Files:**
- Create: `frontend/src/styles/chat.css`
- Modify: `frontend/src/styles/index.css`
- Modify: `frontend/src/main.jsx`

**Interfaces:**
- Структурована система стилів: базові стилі + `chat.css` + `markdown.css`.

- [ ] **Step 1: Extract chat-specific CSS rules from index.css into chat.css**

Винести всі класи `.chat-*`, `.message-*`, `.citation-*`, `.chat-input-*` у `src/styles/chat.css`.

- [ ] **Step 2: Import chat.css and markdown.css in main.jsx**

Підключити модульні таблиці стилів у `main.jsx`.

- [ ] **Step 3: Run frontend tests, lint and build**

Run: `cd frontend && npm test -- --run && npm run lint && npm run build`
Expected: ALL PASS with pristine output.

- [ ] **Step 4: Commit changes**

```bash
git add frontend/src/styles/ frontend/src/main.jsx
git commit -m "style(frontend): modularize chat styles into dedicated stylesheet"
```
