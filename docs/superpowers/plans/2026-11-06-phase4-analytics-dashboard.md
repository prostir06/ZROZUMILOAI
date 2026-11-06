# Phase 4: Teacher & Admin Analytics Dashboard & Knowledge Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Створити повнофункціональну систему аналітики та звітності для викладачів і адміністраторів: бекенд-агрегацію метрик (KPIs, CSAT, Handoff Rate), виявлення прогалин у навчальних матеріалах (Knowledge Gaps), вивантаження анонімізованих CSV-звітів, а також інтерактивні фронтенд-компоненти з картками показників та таблицею запитів для швидкого донавчання RAG.

**Architecture:** Сервісний шар агрегації `analytics_service.py` поверх моделі `WorkspaceChatLog`, REST API ендпоінти `GET /api/workspaces/<id>/analytics/` та `GET /api/workspaces/<id>/analytics/export/`, модульні фронтенд-компоненти `KpiCards` та `KnowledgeGapsTable`, інтегровані у `AnalyticsSection` воркспейсу та сторінку журналів чатів.

**Tech Stack:** Python 3.12/3.14, Django 5.x, Django REST Framework, React 18, Vite 5, Vitest, StandardJS/ESLint.

## Global Constraints

- **Стандарти коду:** Суворе дотримання PEP 8 у Python-файлах та StandardJS/ESLint у JS/JSX-файлах.
- **Обробка помилок:** Захищені запити, жодних порожніх `except: pass`; логування помилок із контекстом.
- **Безпека та конфіденційність:** Доступ до аналітики мають лише адміністратори або призначені користувачі конкретного воркспейсу. Експортні CSV анонімізують студентів (або використовують `sent_by` без витоку персональних паролів/токенів).
- **Zero Regression:** Не зламати існуючі ендпоінти журналів (`/api/chats/logs/`) та роботу воркспейсів.
- **Тестування:** Unit-тести на бекенді через `manage.py test` та фронтенді через `vitest`.

---

### Task 1: Backend Analytics Aggregation API & Services

**Files:**
- Create: `backend/chats/analytics_service.py`
- Create: `backend/chats/analytics_views.py`
- Modify: `backend/workspaces/urls.py`
- Create: `backend/chats/tests/test_analytics.py`

**Interfaces:**
- Consumes: `workspace: Workspace`, `date_range: str = '30d'` ('today', '7d', '30d', 'all')
- Produces: `get_workspace_analytics(workspace, date_range='30d') -> dict`:
  ```python
  {
      "total_queries": int,
      "unique_users": int,
      "handoff_count": int,
      "handoff_rate": float,  # % 0.0 - 100.0
      "csat_score": float,    # % 0.0 - 100.0 (up / (up + down))
      "feedback_up": int,
      "feedback_down": int,
      "timeline": [{"date": str, "count": int, "handoffs": int}],
      "knowledge_gaps": [
          {
              "id": int,
              "created_at": str,
              "prompt": str,
              "response_snippet": str,
              "needs_handoff": bool,
              "feedback": str,
              "reason": str,  # "low_confidence" | "negative_feedback"
          }
      ]
  }
  ```

- [ ] **Step 1: Write failing unit tests for analytics service and view**

```python
# In backend/chats/tests/test_analytics.py
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from workspaces.models import Workspace
from chats.models import WorkspaceChatLog
from chats.analytics_service import get_workspace_analytics

User = get_user_model()

class WorkspaceAnalyticsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='teacher', password='password123')
        self.workspace = Workspace.objects.create(name='Physics 101', slug='physics-101')
        self.workspace.users.add(self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        now = timezone.now()
        # Log 1: normal success with positive feedback
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            user=self.user,
            prompt='Що таке закон Ома?',
            response='Закон Ома встановлює зв\'язок між напругою, струмом і опором.',
            needs_handoff=False,
            feedback='up',
            created_at=now,
        )
        # Log 2: knowledge gap due to low confidence (needs_handoff=True)
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_1',
            prompt='Коли дедлайн лаби 3?',
            response='На жаль, у наданих документах немає цієї інформації.',
            needs_handoff=True,
            feedback='',
            created_at=now - timedelta(hours=2),
        )
        # Log 3: knowledge gap due to negative feedback
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_2',
            prompt='Як обчислити ентропію?',
            response='Неточна відповідь.',
            needs_handoff=False,
            feedback='down',
            created_at=now - timedelta(days=1),
        )

    def test_get_workspace_analytics_metrics(self):
        data = get_workspace_analytics(self.workspace, date_range='7d')
        self.assertEqual(data['total_queries'], 3)
        self.assertEqual(data['handoff_count'], 1)
        self.assertAlmostEqual(data['handoff_rate'], 33.3, places=1)
        self.assertEqual(data['feedback_up'], 1)
        self.assertEqual(data['feedback_down'], 1)
        self.assertEqual(data['csat_score'], 50.0)
        self.assertEqual(len(data['knowledge_gaps']), 2)

    def test_analytics_api_endpoint(self):
        response = self.client.get(f'/api/workspaces/{self.workspace.pk}/analytics/?range=7d')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_queries'], 3)
        self.assertIn('knowledge_gaps', response.data)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test chats.tests.test_analytics`
Expected: FAIL (module/endpoint does not exist)

- [ ] **Step 3: Implement analytics service and view**

1. Створити `backend/chats/analytics_service.py`:
   - `get_workspace_analytics(workspace, date_range='30d')`:
     - Фільтрація логів за часом:
       `now = timezone.now()`
       `today`: початок поточної доби
       `7d`: `now - timedelta(days=7)`
       `30d`: `now - timedelta(days=30)`
       `all`: без фільтра дати
     - Агрегація: `total_queries = qs.count()`, `handoff_count = qs.filter(needs_handoff=True).count()`.
     - `handoff_rate = round(handoff_count / total_queries * 100, 1)` при `total_queries > 0`.
     - CSAT: `up = qs.filter(feedback='up').count()`, `down = qs.filter(feedback='down').count()`.
     - `csat_score = round(up / (up + down) * 100, 1)` при `(up + down) > 0`.
     - `knowledge_gaps`: вибірка запитів з `Q(needs_handoff=True) | Q(feedback='down')`, перші 50 записів.
     - `timeline`: групування кількості запитів за днями.
2. Створити `backend/chats/analytics_views.py`:
   - `WorkspaceAnalyticsView(APIView)`:
     - `permission_classes = [IsAuthenticated]`
     - Перевірка доступу користувача до воркспейсу (якщо не суперюзер, перевірити `workspace.users.filter(pk=request.user.pk).exists()`).
     - Повернення результату `get_workspace_analytics`.
3. Додати URL у `backend/workspaces/urls.py`:
   - `path('<int:workspace_id>/analytics/', WorkspaceAnalyticsView.as_view(), name='workspace_analytics')`

- [ ] **Step 4: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test chats.tests.test_analytics`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add backend/chats/analytics_service.py backend/chats/analytics_views.py backend/workspaces/urls.py backend/chats/tests/test_analytics.py
git commit -m "feat(analytics): implement workspace analytics aggregation service and API endpoint"
```

---

### Task 2: Analytics CSV Export Service

**Files:**
- Modify: `backend/chats/analytics_service.py`
- Modify: `backend/chats/analytics_views.py`
- Modify: `backend/workspaces/urls.py`
- Create: `backend/chats/tests/test_analytics_export.py`

**Interfaces:**
- Consumes: `workspace: Workspace`, `date_range: str = '30d'`
- Produces: `generate_analytics_csv(workspace, date_range) -> str`
- Endpoint: `GET /api/workspaces/<id>/analytics/export/?range=30d`

- [ ] **Step 1: Write failing unit tests for analytics CSV export**

```python
# In backend/chats/tests/test_analytics_export.py
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from workspaces.models import Workspace
from chats.models import WorkspaceChatLog

User = get_user_model()

class AnalyticsExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin_user', password='password123', is_staff=True)
        self.workspace = Workspace.objects.create(name='Math 201', slug='math-201')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_10',
            prompt='Як обчислити інтеграл?',
            response='Використайте формулу інтегрування частинами.',
            needs_handoff=False,
            feedback='up',
        )

    def test_export_analytics_csv_endpoint(self):
        response = self.client.get(f'/api/workspaces/{self.workspace.pk}/analytics/export/?range=30d')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        content = response.content.decode('utf-8-sig')
        self.assertIn('ID,Дата,Користувач,Питання,Відповідь,Handoff,Оцінка', content)
        self.assertIn('Як обчислити інтеграл?', content)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test chats.tests.test_analytics_export`
Expected: FAIL (view/route not found)

- [ ] **Step 3: Implement CSV export in analytics_service.py and analytics_views.py**

1. У `backend/chats/analytics_service.py`:
   - Реалізувати функцію `build_analytics_csv_response(workspace, date_range)`:
     - Використовувати `csv.writer` з `utf-8-sig` (для коректного відкриття кирилиці в MS Excel).
     - Поля: ID, Дата/Час, Користувач (анонімізований `sent_by`), Питання, Скорочена відповідь (до 200 символів), Handoff (Так/Ні), Оцінка.
2. У `backend/chats/analytics_views.py`:
   - Додати `WorkspaceAnalyticsExportView(APIView)`.
   - Захист доступу за воркспейсом.
   - Повертати `HttpResponse` з заголовком `Content-Disposition: attachment; filename="analytics_{workspace_slug}_{range}.csv"`.
3. Зареєструвати в `backend/workspaces/urls.py`:
   - `path('<int:workspace_id>/analytics/export/', WorkspaceAnalyticsExportView.as_view(), name='workspace_analytics_export')`

- [ ] **Step 4: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe backend\manage.py test chats.tests.test_analytics_export`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add backend/chats/analytics_service.py backend/chats/analytics_views.py backend/workspaces/urls.py backend/chats/tests/test_analytics_export.py
git commit -m "feat(analytics): add CSV export endpoint for workspace analytics"
```

---

### Task 3: Frontend Analytics API Client & KPI Cards Component

**Files:**
- Modify: `frontend/src/api/client.js`
- Create: `frontend/src/components/analytics/KpiCards.jsx`
- Create: `frontend/src/components/analytics/KpiCards.test.jsx`
- Create: `frontend/src/styles/analytics.css`
- Modify: `frontend/src/main.jsx`

**Interfaces:**
- Consumes: `api.getWorkspaceAnalytics(workspaceId, { range })`
- Produces: `<KpiCards analytics={analyticsData} />`

- [ ] **Step 1: Write failing unit test for KpiCards component**

```jsx
// In frontend/src/components/analytics/KpiCards.test.jsx
import { describe, it, expect } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import { KpiCards } from './KpiCards';

describe('KpiCards', () => {
  it('renders all 4 primary KPIs correctly', () => {
    const data = {
      total_queries: 142,
      unique_users: 38,
      handoff_rate: 12.5,
      handoff_count: 18,
      csat_score: 91.2,
      feedback_up: 52,
      feedback_down: 5,
      knowledge_gaps: [{}, {}, {}],
    };
    const html = renderToString(<KpiCards analytics={data} />);
    expect(html).toContain('142');
    expect(html).toContain('91.2%');
    expect(html).toContain('12.5%');
    expect(html).toContain('3'); // 3 gaps
  });

  it('renders zero state safely without dividing by zero', () => {
    const emptyData = {
      total_queries: 0,
      unique_users: 0,
      handoff_rate: 0,
      handoff_count: 0,
      csat_score: 0,
      feedback_up: 0,
      feedback_down: 0,
      knowledge_gaps: [],
    };
    const html = renderToString(<KpiCards analytics={emptyData} />);
    expect(html).toContain('0');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- --run src/components/analytics/KpiCards.test.jsx`
Expected: FAIL

- [ ] **Step 3: Implement client methods, KpiCards, and analytics.css**

1. Оновити `frontend/src/api/client.js`:
   - `getWorkspaceAnalytics(workspaceId, { range = '30d' } = {})`: виклик `GET /api/workspaces/${workspaceId}/analytics/?range=${range}`.
   - `exportWorkspaceAnalyticsCsv(workspaceId, { range = '30d' } = {})`: повертає blob або скачує файл.
2. Створити `frontend/src/components/analytics/KpiCards.jsx`:
   - 4 картки метрик у сітці `kpi-grid`:
     1. Загальна кількість запитів (Total queries) + бейдж унікальних користувачів.
     2. Індекс корисності (CSAT %) + лічильники 👍 / 👎.
     3. Рівень ескалації (Handoff Rate %) + кількість ескалацій.
     4. Прогалини у знаннях (Knowledge Gaps) + статус готовності.
3. Створити `frontend/src/styles/analytics.css` з класами `.kpi-grid`, `.kpi-card`, `.kpi-card__value`, `.kpi-card__meta`.
4. Підключити `analytics.css` у `frontend/src/main.jsx`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend test -- --run src/components/analytics/KpiCards.test.jsx`
Expected: PASS

- [ ] **Step 5: Run linter and commit**

```bash
npm --prefix frontend run lint
git add frontend/src/api/client.js frontend/src/components/analytics/ frontend/src/styles/analytics.css frontend/src/main.jsx
git commit -m "feat(frontend): create KpiCards component and analytics API client"
```

---

### Task 4: Frontend Knowledge Gaps Queue & Workspace Analytics Tab

**Files:**
- Create: `frontend/src/components/analytics/KnowledgeGapsTable.jsx`
- Create: `frontend/src/components/analytics/KnowledgeGapsTable.test.jsx`
- Create: `frontend/src/pages/workspaces/AnalyticsSection.jsx`
- Modify: `frontend/src/pages/WorkspacesPage.jsx`
- Modify: `frontend/src/pages/WorkspaceChatsPage.jsx`

**Interfaces:**
- Consumes: `knowledge_gaps: list`, `onUploadClick: function`
- Produces: `<KnowledgeGapsTable gaps={knowledgeGaps} onResolve={handleResolveGap} />`
- Produces: `<AnalyticsSection workspaceId={id} onUploadMaterial={switchToUpload} />`

- [ ] **Step 1: Write failing unit test for KnowledgeGapsTable**

```jsx
// In frontend/src/components/analytics/KnowledgeGapsTable.test.jsx
import { describe, it, expect } from 'vitest';
import React from 'react';
import { renderToString } from 'react-dom/server';
import { KnowledgeGapsTable } from './KnowledgeGapsTable';

describe('KnowledgeGapsTable', () => {
  it('renders table of gaps with reason badges and prompt', () => {
    const gaps = [
      {
        id: 1,
        created_at: '2026-11-06T12:00:00Z',
        prompt: 'Коли дедлайн модульного контролю?',
        response_snippet: 'Інформація відсутня.',
        needs_handoff: true,
        feedback: '',
        reason: 'low_confidence',
      },
      {
        id: 2,
        created_at: '2026-11-06T13:00:00Z',
        prompt: 'Як обрахувати похибку?',
        response_snippet: 'Невірна формула.',
        needs_handoff: false,
        feedback: 'down',
        reason: 'negative_feedback',
      },
    ];
    const html = renderToString(<KnowledgeGapsTable gaps={gaps} onUploadClick={() => {}} />);
    expect(html).toContain('Коли дедлайн модульного контролю?');
    expect(html).toContain('Низька впевненість RAG');
    expect(html).toContain('Негативна оцінка');
    expect(html).toContain('Додати матеріал');
  });

  it('renders empty message when no gaps exist', () => {
    const html = renderToString(<KnowledgeGapsTable gaps={[]} onUploadClick={() => {}} />);
    expect(html).toContain('Прогалин не виявлено');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test -- --run src/components/analytics/KnowledgeGapsTable.test.jsx`
Expected: FAIL

- [ ] **Step 3: Implement KnowledgeGapsTable, AnalyticsSection, and integrate into WorkspacesPage and WorkspaceChatsPage**

1. Створити `frontend/src/components/analytics/KnowledgeGapsTable.jsx`:
   - Таблиця: Дата, Питання студента, Причина (бейджі), Фрагмент відповіді, Дія (кнопка «Додати матеріал у RAG»).
2. Створити `frontend/src/pages/workspaces/AnalyticsSection.jsx`:
   - Включає селектор діапазону (`7 днів`, `30 днів`, `Всі`), кнопку «Завантажити CSV», `<KpiCards />` та `<KnowledgeGapsTable />`.
   - Завантажує дані через `api.getWorkspaceAnalytics`.
3. Інтегрувати у `frontend/src/pages/WorkspacesPage.jsx`:
   - Відображати `<AnalyticsSection />` у режимі редагування воркспейсу поряд із `DocumentsRagSection`.
   - Клік на «Додати матеріал у RAG» скролить сторінку до секції завантаження документів або активує фокус інпуту файлів.
4. Додати кнопку швидкого переходу до аналітики у шапці `WorkspaceChatsPage.jsx`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend test -- --run`
Expected: PASS

- [ ] **Step 5: Run linter, build, and commit**

```bash
npm --prefix frontend run lint
npm --prefix frontend run build
git add frontend/
git commit -m "feat(frontend): implement KnowledgeGapsTable, AnalyticsSection and integrate workspace analytics"
```
