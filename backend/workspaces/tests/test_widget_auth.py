"""Unit-тести widget token authentication."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory, APITestCase

from workspaces.models import WidgetToken, Workspace
from workspaces.widget_auth import WidgetTokenAuthentication

User = get_user_model()


class WidgetTokenAuthTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.workspace = Workspace.objects.create(
            name='Widget WS',
            model_names=['llama3'],
        )
        self.raw, self.token = WidgetToken.create_for_workspace(
            self.workspace,
            label='test',
        )
        self.auth = WidgetTokenAuthentication()

    def test_valid_token(self):
        request = self.factory.get(
            '/api/widget/config/',
            HTTP_AUTHORIZATION=f'Widget-Token {self.raw}',
        )
        user, auth = self.auth.authenticate(request)
        self.assertTrue(user.is_anonymous)
        self.assertEqual(auth.pk, self.token.pk)

    def test_invalid_token(self):
        request = self.factory.get(
            '/api/widget/config/',
            HTTP_AUTHORIZATION='Widget-Token wt_invalid',
        )
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_inactive_token(self):
        self.token.is_active = False
        self.token.save(update_fields=['is_active'])
        request = self.factory.get(
            '/api/widget/config/',
            HTTP_AUTHORIZATION=f'Widget-Token {self.raw}',
        )
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)


class WidgetTokenDeleteApiTests(APITestCase):
    """Тести видалення widget token через API та обробки помилок."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_wt',
            password='pass',
            is_staff=True,
        )
        self.workspace = Workspace.objects.create(
            name='WT Delete WS',
            model_names=['llama3'],
        )
        _raw, self.token = WidgetToken.create_for_workspace(
            self.workspace,
            label='to-delete',
        )
        self.url = reverse(
            'workspace_widget_token_delete',
            kwargs={
                'workspace_id': self.workspace.pk,
                'token_id': self.token.pk,
            },
        )

    def test_delete_success(self):
        """Успішне видалення повертає 200."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted'], self.token.pk)
        self.assertFalse(WidgetToken.objects.filter(pk=self.token.pk).exists())

    def test_delete_database_error_returns_500(self):
        """DatabaseError при видаленні токена повертає 500 та логується."""
        from unittest.mock import patch

        from django.db import DatabaseError

        self.client.force_authenticate(user=self.admin)
        with patch.object(
            WidgetToken,
            'delete',
            side_effect=DatabaseError('DB locked'),
        ):
            response = self.client.delete(self.url)
        self.assertEqual(
            response.status_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        self.assertIn('error', response.data)
