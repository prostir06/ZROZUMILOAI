"""
Unit and integration tests for workspace analytics service and API.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from chats.analytics_service import build_analytics_csv, get_workspace_analytics
from chats.export_service import serialize_logs
from chats.models import WorkspaceChatLog
from chats.table_analysis import build_table_digest
from workspaces.models import Workspace

User = get_user_model()


class WorkspaceAnalyticsServiceTests(APITestCase):
    """Тести обчислення метрик аналітики робочого простору."""

    def setUp(self):
        self.workspace = Workspace.objects.create(name='Physics 101')
        self.now = timezone.now()

    def test_empty_workspace_returns_zeroes(self):
        """Для порожнього простору метрики дорівнюють 0 без ділення на нуль."""
        analytics = get_workspace_analytics(self.workspace, date_range='all')
        self.assertEqual(analytics['total_queries'], 0)
        self.assertEqual(analytics['unique_users'], 0)
        self.assertEqual(analytics['handoff_count'], 0)
        self.assertEqual(analytics['handoff_rate'], 0.0)
        self.assertEqual(analytics['feedback_up'], 0)
        self.assertEqual(analytics['feedback_down'], 0)
        self.assertEqual(analytics['csat_score'], 0.0)
        self.assertEqual(analytics['knowledge_gaps'], [])
        self.assertEqual(analytics['timeline'], [])

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

    def test_metrics_calculation(self):
        """Обчислення KPI (запити, передачі, CSAT)."""
        # User 1: up feedback
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_1',
            prompt='Що таке квант?',
            response='Квант - це неподільна порція...',
            feedback='up',
            needs_handoff=False,
        )
        # User 1: down feedback
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_1',
            prompt='Чому небо синє?',
            response='Не знаю',
            feedback='down',
            needs_handoff=False,
        )
        # User 2: needs handoff
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_2',
            prompt='З\'єднайте з викладачем',
            response='Звертаюсь до викладача...',
            feedback='',
            needs_handoff=True,
        )
        # User 3: unrated
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_3',
            prompt='Формула сили?',
            response='F = ma',
            feedback='',
            needs_handoff=False,
        )

        analytics = get_workspace_analytics(self.workspace, date_range='all')
        self.assertEqual(analytics['total_queries'], 4)
        self.assertEqual(analytics['unique_users'], 3)
        self.assertEqual(analytics['handoff_count'], 1)
        # 1 / 4 * 100 = 25.0%
        self.assertEqual(analytics['handoff_rate'], 25.0)
        self.assertEqual(analytics['feedback_up'], 1)
        self.assertEqual(analytics['feedback_down'], 1)
        # 1 / 2 * 100 = 50.0%
        self.assertEqual(analytics['csat_score'], 50.0)

    def test_knowledge_gaps_extraction(self):
        """Knowledge Gaps мають причину low_confidence або negative_feedback."""
        long_response = 'A' * 200
        log_handoff = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_1',
            prompt='Складна задача',
            response=long_response,
            needs_handoff=True,
            feedback='',
        )
        log_negative = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_2',
            prompt='Погана відповідь',
            response='Коротка відповідь',
            needs_handoff=False,
            feedback='down',
        )
        # Нормальний запит — не повинен потрапити в gaps
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_3',
            prompt='Гарна відповідь',
            response='Все супер',
            needs_handoff=False,
            feedback='up',
        )

        analytics = get_workspace_analytics(self.workspace, date_range='all')
        gaps = analytics['knowledge_gaps']
        self.assertEqual(len(gaps), 2)

        gap_handoff = next(g for g in gaps if g['id'] == log_handoff.id)
        self.assertEqual(gap_handoff['reason'], 'low_confidence')
        self.assertEqual(gap_handoff['needs_handoff'], True)
        self.assertEqual(len(gap_handoff['response_snippet']), 160)

        gap_negative = next(g for g in gaps if g['id'] == log_negative.id)
        self.assertEqual(gap_negative['reason'], 'negative_feedback')
        self.assertEqual(gap_negative['feedback'], 'down')

    def test_date_range_filtering(self):
        """Фільтрація за діапазонами today, 7d, 30d, all."""
        # Log today
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student',
            prompt='Сьогодні',
        )
        # Log 5 days ago
        log_5d = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student',
            prompt='5 днів тому',
        )
        WorkspaceChatLog.objects.filter(pk=log_5d.pk).update(
            created_at=self.now - timedelta(days=5),
        )
        # Log 20 days ago
        log_20d = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student',
            prompt='20 днів тому',
        )
        WorkspaceChatLog.objects.filter(pk=log_20d.pk).update(
            created_at=self.now - timedelta(days=20),
        )
        # Log 45 days ago
        log_45d = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student',
            prompt='45 днів тому',
        )
        WorkspaceChatLog.objects.filter(pk=log_45d.pk).update(
            created_at=self.now - timedelta(days=45),
        )

        today_data = get_workspace_analytics(
            self.workspace,
            date_range='today',
        )
        self.assertEqual(today_data['total_queries'], 1)

        d7_data = get_workspace_analytics(
            self.workspace,
            date_range='7d',
        )
        self.assertEqual(d7_data['total_queries'], 2)

        d30_data = get_workspace_analytics(
            self.workspace,
            date_range='30d',
        )
        self.assertEqual(d30_data['total_queries'], 3)

        all_data = get_workspace_analytics(
            self.workspace,
            date_range='all',
        )
        self.assertEqual(all_data['total_queries'], 4)

    def test_timeline_day_groupings(self):
        """Агрегація за днями в таймлайн."""
        # Day 1: 2 queries, 1 handoff
        l1 = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_1',
            prompt='Запит 1',
            needs_handoff=True,
        )
        l2 = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_2',
            prompt='Запит 2',
            needs_handoff=False,
        )
        day1 = self.now - timedelta(days=2)
        WorkspaceChatLog.objects.filter(
            pk__in=[l1.pk, l2.pk],
        ).update(created_at=day1)

        # Day 2: 1 query, 0 handoffs
        l3 = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_1',
            prompt='Запит 3',
            needs_handoff=False,
        )
        day2 = self.now - timedelta(days=1)
        WorkspaceChatLog.objects.filter(pk=l3.pk).update(created_at=day2)

        analytics = get_workspace_analytics(self.workspace, date_range='7d')
        timeline = analytics['timeline']
        self.assertEqual(len(timeline), 2)
        self.assertEqual(
            timeline[0]['date'],
            timezone.localtime(day1).strftime('%Y-%m-%d'),
        )
        self.assertEqual(timeline[0]['total_queries'], 2)
        self.assertEqual(timeline[0]['handoffs'], 1)
        self.assertEqual(
            timeline[1]['date'],
            timezone.localtime(day2).strftime('%Y-%m-%d'),
        )
        self.assertEqual(timeline[1]['total_queries'], 1)
        self.assertEqual(timeline[1]['handoffs'], 0)

    def test_get_workspace_analytics_uses_single_aggregate_for_kpis(self):
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='u1',
            prompt='Q1',
            response='A1',
            needs_handoff=True,
            feedback='down',
        )
        # 1 aggregate query + 1 gaps query + 1 timeline query = 3 queries total
        with self.assertNumQueries(3):
            data = get_workspace_analytics(self.workspace, date_range='30d')
        self.assertEqual(data['total_queries'], 1)
        self.assertEqual(data['handoff_count'], 1)

    def test_build_table_digest_uses_single_aggregate_for_totals(self):
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='u1',
            prompt='Q1',
            response='A1',
            needs_handoff=True,
            feedback='up',
        )
        qs = WorkspaceChatLog.objects.filter(workspace=self.workspace)
        # 1 aggregate query + 1 workspace_rows query + 1 sample query = 3 queries total
        with self.assertNumQueries(3):
            digest = build_table_digest(qs)
        self.assertEqual(digest['total'], 1)
        self.assertEqual(digest['handoff'], 1)
        self.assertEqual(digest['feedback_up'], 1)
        self.assertEqual(digest['feedback_down'], 0)

    def test_build_analytics_csv_and_serialize_logs_use_iterator(self):
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='u1',
            prompt='Q1',
            response='A1',
            needs_handoff=False,
            feedback='up',
        )
        csv_text = build_analytics_csv(self.workspace, date_range='30d')
        self.assertIn('Q1', csv_text)
        qs = WorkspaceChatLog.objects.filter(workspace=self.workspace)
        rows = serialize_logs(qs)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['prompt'], 'Q1')


    def test_knowledge_gaps_includes_resolution_fields(self):
        """Елементи knowledge_gaps містять is_resolved та resolved_at."""
        log1 = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            prompt='Нерозв\'язане питання',
            response='Не знаю',
            needs_handoff=True,
            is_resolved=False,
        )
        resolved_time = timezone.now()
        log2 = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            prompt='Вирішене питання',
            response='Тепер знаю',
            feedback='down',
            is_resolved=True,
            resolved_at=resolved_time,
        )

        analytics = get_workspace_analytics(self.workspace, date_range='all')
        gaps = analytics['knowledge_gaps']
        self.assertEqual(len(gaps), 2)
        gap1 = next(g for g in gaps if g['id'] == log1.id)
        gap2 = next(g for g in gaps if g['id'] == log2.id)

        self.assertFalse(gap1['is_resolved'])
        self.assertIsNone(gap1['resolved_at'])

        self.assertTrue(gap2['is_resolved'])
        self.assertEqual(gap2['resolved_at'], resolved_time.isoformat())

    def test_filter_analytics_by_resolved_status(self):
        """Параметр resolved фільтрує knowledge_gaps."""
        log_open = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            prompt='Відкрите',
            needs_handoff=True,
            is_resolved=False,
        )
        log_resolved = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            prompt='Вирішене',
            needs_handoff=True,
            is_resolved=True,
            resolved_at=timezone.now(),
        )

        open_analytics = get_workspace_analytics(self.workspace, date_range='all', resolved=False)
        open_ids = [g['id'] for g in open_analytics['knowledge_gaps']]
        self.assertIn(log_open.id, open_ids)
        self.assertNotIn(log_resolved.id, open_ids)

        resolved_analytics = get_workspace_analytics(self.workspace, date_range='all', resolved=True)
        resolved_ids = [g['id'] for g in resolved_analytics['knowledge_gaps']]
        self.assertNotIn(log_open.id, resolved_ids)
        self.assertIn(log_resolved.id, resolved_ids)


class WorkspaceAnalyticsApiTests(APITestCase):
    """Тести HTTP API endpoint аналітики робочого простору."""

    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher',
            password='password123',
        )
        self.outsider = User.objects.create_user(
            username='outsider',
            password='password123',
        )
        self.admin = User.objects.create_superuser(
            username='admin',
            password='password123',
            email='admin@example.com',
        )
        self.workspace = Workspace.objects.create(name='Math 202')
        self.workspace.users.add(self.teacher)

        self.url = reverse(
            'workspace_analytics',
            kwargs={'workspace_id': self.workspace.id},
        )

    def test_unauthenticated_forbidden(self):
        """Неавтентифікований користувач отримує 401."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unassigned_user_forbidden(self):
        """Користувач, не призначений до простору, отримує 403."""
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assigned_teacher_allowed(self):
        """Призначений викладач отримує 200 та структуру аналітики."""
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_1',
            prompt='Тестовий запит',
            response='Відповідь',
        )
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_queries'], 1)
        self.assertIn('timeline', response.data)
        self.assertIn('knowledge_gaps', response.data)
        self.assertIn('csat_score', response.data)

    def test_superuser_allowed(self):
        """Суперюзер отримує 200 навіть якщо не призначений до простору."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_range_query_parameter(self):
        """Параметр range передається сервісу та повертається в структурі."""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(f'{self.url}?range=7d')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['range'], '7d')

    def test_nonexistent_workspace_returns_404(self):
        """Неіснуючий простір повертає 404."""
        self.client.force_authenticate(user=self.admin)
        invalid_url = reverse(
            'workspace_analytics',
            kwargs={'workspace_id': 999999},
        )
        response = self.client.get(invalid_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class WorkspaceKnowledgeGapResolveApiTests(APITestCase):
    """Тести endpoint позначення прогалини знань як вирішеної."""

    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher',
            password='password123',
        )
        self.outsider = User.objects.create_user(
            username='outsider',
            password='password123',
        )
        self.admin = User.objects.create_superuser(
            username='admin',
            password='password123',
            email='admin@example.com',
        )
        self.workspace = Workspace.objects.create(name='Physics 101')
        self.workspace.users.add(self.teacher)

        self.other_workspace = Workspace.objects.create(name='Chemistry 101')

        self.log = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            prompt='Складне питання',
            response='Не маю відповіді',
            needs_handoff=True,
            is_resolved=False,
        )

        self.resolve_url = reverse(
            'workspace_gap_resolve',
            kwargs={'workspace_id': self.workspace.id, 'log_id': self.log.id},
        )

    def test_unauthenticated_returns_401(self):
        """Неавтентифікований запит повертає 401."""
        response = self.client.patch(self.resolve_url, {'resolved': True})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_outsider_forbidden_403(self):
        """Користувач без доступу до простору отримує 403."""
        self.client.force_authenticate(user=self.outsider)
        response = self.client.patch(self.resolve_url, {'resolved': True})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_resolves_gap_successfully(self):
        """Призначений викладач може позначити прогалину як вирішену."""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.patch(self.resolve_url, {'resolved': True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.log.id)
        self.assertTrue(response.data['is_resolved'])
        self.assertIsNotNone(response.data['resolved_at'])

        self.log.refresh_from_db()
        self.assertTrue(self.log.is_resolved)
        self.assertIsNotNone(self.log.resolved_at)

    def test_teacher_resolves_gap_default_true(self):
        """За замовчуванням без тіла або порожнє тіло resolved=True."""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.patch(self.resolve_url, {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_resolved'])

    def test_staff_resolves_gap_successfully(self):
        """Staff/superuser може позначити прогалину."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(self.resolve_url, {'resolved': True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_resolved'])

    def test_reopen_resolved_gap(self):
        """Повторне відкриття прогалини (resolved=False) скидає is_resolved та resolved_at."""
        self.log.is_resolved = True
        self.log.resolved_at = timezone.now()
        self.log.save()

        self.client.force_authenticate(user=self.teacher)
        response = self.client.patch(self.resolve_url, {'resolved': False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_resolved'])
        self.assertIsNone(response.data['resolved_at'])

        self.log.refresh_from_db()
        self.assertFalse(self.log.is_resolved)
        self.assertIsNone(self.log.resolved_at)

    def test_resolve_gap_from_different_workspace_returns_404(self):
        """Запит з ID чужого простору повертає 404."""
        self.client.force_authenticate(user=self.admin)
        wrong_url = reverse(
            'workspace_gap_resolve',
            kwargs={'workspace_id': self.other_workspace.id, 'log_id': self.log.id},
        )
        response = self.client.patch(wrong_url, {'resolved': True})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_gap_returns_404(self):
        """Неіснуючий лог повертає 404."""
        self.client.force_authenticate(user=self.teacher)
        missing_url = reverse(
            'workspace_gap_resolve',
            kwargs={'workspace_id': self.workspace.id, 'log_id': 999999},
        )
        response = self.client.patch(missing_url, {'resolved': True})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

