"""Unit-тести widget token authentication."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

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
