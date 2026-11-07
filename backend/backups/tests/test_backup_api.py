"""API-тести backups: list ACL і path traversal на download."""
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class BackupApiAclTests(APITestCase):
    """Backups лише для admin."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_bak',
            password='pass',
            is_staff=True,
        )
        self.user = User.objects.create_user(username='user_bak', password='pass')
        self.list_url = reverse('backup_list_create')

    def test_list_requires_admin(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_lists_backups(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('backups', response.data)

    def test_download_path_traversal_rejected(self):
        self.client.force_authenticate(user=self.admin)
        # URL converter не приймає «/»; перевіряємо encoded traversal.
        response = self.client.get('/api/backups/..%2Fsecrets.sql/download/')
        self.assertIn(
            response.status_code,
            (status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST),
        )

    def test_download_missing_file_404(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse(
            'backup_download',
            kwargs={'filename': 'missing_backup.sql'},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_value_error_returns_400(self):
        """ValueError на get_backup_path повертає 400 Bad Request."""
        from unittest.mock import patch
        self.client.force_authenticate(user=self.admin)
        url = reverse(
            'backup_download',
            kwargs={'filename': 'bad_backup.sql'},
        )
        with patch(
            'backups.views.BackupService.get_backup_path',
            side_effect=ValueError('Path traversal forbidden'),
        ):
            response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_delete_value_error_returns_400(self):
        """ValueError на delete_backup повертає 400 Bad Request."""
        from unittest.mock import patch
        self.client.force_authenticate(user=self.admin)
        url = reverse(
            'backup_delete',
            kwargs={'filename': 'bad_backup.sql'},
        )
        with patch(
            'backups.views.BackupService.delete_backup',
            side_effect=ValueError('Path traversal forbidden'),
        ):
            response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_delete_os_error_returns_500(self):
        """OSError на delete_backup повертає 500 та логується."""
        from unittest.mock import patch
        self.client.force_authenticate(user=self.admin)
        url = reverse(
            'backup_delete',
            kwargs={'filename': 'test.sql'},
        )
        with patch(
            'backups.views.BackupService.delete_backup',
            side_effect=OSError('Permission denied'),
        ):
            response = self.client.delete(url)
        self.assertEqual(
            response.status_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
