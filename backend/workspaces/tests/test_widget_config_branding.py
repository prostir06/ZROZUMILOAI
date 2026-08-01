"""Unit-тести branding полів widget config (greeting / FAQ)."""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from workspaces.models import WidgetToken, Workspace


class WidgetConfigBrandingTests(APITestCase):
    """GET /api/widget/config/ повертає greeting і faq_questions."""

    def setUp(self):
        self.workspace = Workspace.objects.create(
            name='Brand WS',
            model_names=['llama3'],
            embed_greeting='Вітаю з курсу!',
            embed_faq_questions=['Питання 1', 'Питання 2'],
        )
        self.raw, _token = WidgetToken.create_for_workspace(
            self.workspace,
            label='brand',
        )

    def test_config_includes_greeting_and_faq(self):
        response = self.client.get(
            reverse('widget_config'),
            HTTP_AUTHORIZATION=f'Widget-Token {self.raw}',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['greeting'], 'Вітаю з курсу!')
        self.assertEqual(response.data['faq_questions'], ['Питання 1', 'Питання 2'])

    def test_default_greeting_when_empty(self):
        self.workspace.embed_greeting = ''
        self.workspace.embed_faq_questions = []
        self.workspace.save(
            update_fields=['embed_greeting', 'embed_faq_questions'],
        )
        response = self.client.get(
            reverse('widget_config'),
            HTTP_AUTHORIZATION=f'Widget-Token {self.raw}',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.workspace.name, response.data['greeting'])
        self.assertEqual(response.data['faq_questions'], [])
