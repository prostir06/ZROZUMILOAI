"""API-тести Chats Info (workspace chat logs)."""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from chats.models import WorkspaceChatLog
from workspaces.models import Workspace

User = get_user_model()


class WorkspaceChatLogApiTests(APITestCase):
    """Тести admin API для Chats Info."""

    def setUp(self):
        """Admin, звичайний user та тестові логи."""
        self.admin = User.objects.create_user(
            username='admin',
            password='pass',
            is_staff=True,
        )
        self.user = User.objects.create_user(username='user', password='pass')
        self.workspace = Workspace.objects.create(
            name='support',
            model_names=['llama3'],
        )
        self.log = WorkspaceChatLog.objects.create(
            sent_by='student',
            workspace=self.workspace,
            prompt='Допоможіть',
            response='З радістю',
        )
        self.list_url = reverse('workspace_chat_logs')
        self.export_url = reverse('workspace_chat_logs_export')
        self.clear_url = reverse('workspace_chat_logs_clear')
        self.detail_url = reverse(
            'workspace_chat_log_detail',
            kwargs={'log_id': self.log.pk},
        )

    def test_list_requires_admin(self):
        """Звичайний користувач не бачить логи."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_lists_logs(self):
        """Admin отримує список записів."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['prompt'], 'Допоможіть')

    def test_admin_deletes_log(self):
        """Admin видаляє один запис."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(WorkspaceChatLog.objects.filter(pk=self.log.pk).exists())

    def test_delete_missing_log_returns_404(self):
        """Видалення неіснуючого запису → 404."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('workspace_chat_log_detail', kwargs={'log_id': 99999})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_clears_logs(self):
        """Admin очищає всі записи."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(self.clear_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(WorkspaceChatLog.objects.count(), 0)

    def test_export_csv(self):
        """Експорт CSV через export_format (не format — конфлікт DRF)."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'{self.export_url}?export_format=csv')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/csv', response['Content-Type'])
        content = response.content.decode('utf-8')
        self.assertIn('sent_by', content)
        self.assertIn('student', content)

    def test_export_json_default(self):
        """Експорт JSON за замовчуванням."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.export_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('application/json', response['Content-Type'])

    def test_drf_format_param_causes_not_found(self):
        """
        DRF резервує query «format» — без export_format можливий 404.
        """
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'{self.export_url}?format=csv')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
