"""
Unit and integration tests for workspace analytics CSV export service and API.
"""
import csv
import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from chats.analytics_service import build_analytics_csv
from chats.models import WorkspaceChatLog
from workspaces.models import Workspace

User = get_user_model()


class AnalyticsCsvExportServiceTests(APITestCase):
    """Тести генерації CSV-звіту аналітики робочого простору."""

    def setUp(self):
        self.workspace = Workspace.objects.create(name='Physics 101')
        self.now = timezone.now()

    def test_csv_starts_with_utf8_bom(self):
        """CSV повинен починатися з UTF-8 BOM для сумісності з Excel."""
        csv_text = build_analytics_csv(self.workspace, date_range='all')
        self.assertTrue(csv_text.startswith('\ufeff'))

    def test_csv_headers(self):
        """Перевірка обов'язкових колонок згідно з вимогами аудиту."""
        csv_text = build_analytics_csv(self.workspace, date_range='all')
        reader = csv.reader(io.StringIO(csv_text.lstrip('\ufeff')))
        header = next(reader)
        expected = [
            'ID',
            'Дата/Час',
            'Користувач',
            'Питання',
            'Скорочена відповідь',
            'Handoff',
            'Оцінка',
        ]
        self.assertEqual(header, expected)

    def test_empty_workspace_returns_header_only(self):
        """Порожній воркспейс містить лише заголовок."""
        csv_text = build_analytics_csv(self.workspace, date_range='all')
        reader = list(csv.reader(io.StringIO(csv_text.lstrip('\ufeff'))))
        self.assertEqual(len(reader), 1)

    def test_row_contents_and_formatting(self):
        """Форматування даних: Handoff (Так/Ні), Оцінка (👍/👎/—), скорочення тексту."""
        long_response = 'А' * 300
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_1',
            prompt='Що таке фотон?',
            response=long_response,
            needs_handoff=True,
            feedback='up',
        )
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_2',
            prompt='Чому трава зелена?',
            response='Хлорофіл...',
            needs_handoff=False,
            feedback='down',
        )
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_3',
            prompt='Як здати лабу?',
            response='Зверніться до методички.',
            needs_handoff=False,
            feedback='',
        )

        csv_text = build_analytics_csv(self.workspace, date_range='all')
        reader = list(csv.reader(io.StringIO(csv_text.lstrip('\ufeff'))))
        rows = reader[1:]  # skip header

        self.assertEqual(len(rows), 3)

        # Перевіряємо перший рядок (order by -created_at, student_3 створений останнім)
        row_student3 = next(r for r in rows if r[2] == 'student_3')
        self.assertEqual(row_student3[3], 'Як здати лабу?')
        self.assertEqual(row_student3[4], 'Зверніться до методички.')
        self.assertEqual(row_student3[5], 'Ні')
        self.assertEqual(row_student3[6], '—')

        row_student2 = next(r for r in rows if r[2] == 'student_2')
        self.assertEqual(row_student2[5], 'Ні')
        self.assertEqual(row_student2[6], '👎')

        row_student1 = next(r for r in rows if r[2] == 'student_1')
        self.assertEqual(row_student1[5], 'Так')
        self.assertEqual(row_student1[6], '👍')
        # Скорочена відповідь обрізана до 200 символів
        self.assertLessEqual(len(row_student1[4]), 200)

    def test_date_range_filtering_csv(self):
        """Фільтрація записів у CSV за періодами."""
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_today',
            prompt='Сьогоднішній запит',
        )
        l_5d = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_5d',
            prompt='5 днів тому',
        )
        WorkspaceChatLog.objects.filter(pk=l_5d.pk).update(
            created_at=self.now - timedelta(days=5),
        )
        l_20d = WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_20d',
            prompt='20 днів тому',
        )
        WorkspaceChatLog.objects.filter(pk=l_20d.pk).update(
            created_at=self.now - timedelta(days=20),
        )

        csv_today = build_analytics_csv(self.workspace, date_range='today')
        rows_today = list(csv.reader(io.StringIO(csv_today.lstrip('\ufeff'))))[1:]
        self.assertEqual(len(rows_today), 1)

        csv_7d = build_analytics_csv(self.workspace, date_range='7d')
        rows_7d = list(csv.reader(io.StringIO(csv_7d.lstrip('\ufeff'))))[1:]
        self.assertEqual(len(rows_7d), 2)

        csv_30d = build_analytics_csv(self.workspace, date_range='30d')
        rows_30d = list(csv.reader(io.StringIO(csv_30d.lstrip('\ufeff'))))[1:]
        self.assertEqual(len(rows_30d), 3)


class AnalyticsCsvExportApiTests(APITestCase):
    """Тести HTTP API endpoint експорту CSV аналітики."""

    def setUp(self):
        self.teacher = User.objects.create_user(
            username='export_teacher',
            password='password123',
        )
        self.outsider = User.objects.create_user(
            username='export_outsider',
            password='password123',
        )
        self.admin = User.objects.create_superuser(
            username='export_admin',
            password='password123',
            email='admin@example.com',
        )
        self.workspace = Workspace.objects.create(name='Physics 101')
        self.workspace.users.add(self.teacher)

        self.url = reverse(
            'workspace_analytics_export',
            kwargs={'workspace_id': self.workspace.id},
        )

    def test_unauthenticated_returns_401(self):
        """Неавтентифікований запит повертає 401."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unassigned_user_returns_403(self):
        """Користувач без доступу до воркспейсу отримує 403."""
        self.client.force_authenticate(user=self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assigned_teacher_can_export_csv(self):
        """Призначений викладач отримує CSV з правильними заголовками."""
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            sent_by='student_1',
            prompt='Тестове питання',
            response='Тестова відповідь',
        )
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment; filename=', response['Content-Disposition'])
        self.assertIn(
            'analytics_physics-101_30d.csv',
            response['Content-Disposition'],
        )

        content = response.content.decode('utf-8')
        self.assertTrue(content.startswith('\ufeff'))
        self.assertIn('Тестове питання', content)

    def test_superuser_can_export_csv(self):
        """Суперюзер має доступ до експорту будь-якого воркспейсу."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

    def test_date_range_parameter_and_filename(self):
        """Параметр range впливає на назву файлу та фільтрацію."""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(f'{self.url}?range=7d')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            'analytics_physics-101_7d.csv',
            response['Content-Disposition'],
        )

    def test_nonexistent_workspace_returns_404(self):
        """Неіснуючий воркспейс повертає 404."""
        self.client.force_authenticate(user=self.admin)
        invalid_url = reverse(
            'workspace_analytics_export',
            kwargs={'workspace_id': 999999},
        )
        response = self.client.get(invalid_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
