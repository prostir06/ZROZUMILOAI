"""
Unit-тести WidgetFeedbackView та course-scope ACL (JSON API).

PEP 8: імпорти згруповані, довгі рядки розбиті, docstrings українською.
"""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from chats.models import WorkspaceChatLog
from workspaces.models import WidgetToken, Workspace


class WidgetFeedbackApiTests(APITestCase):
    """Feedback 👍/👎 через Widget-Token."""

    def setUp(self):
        self.workspace = Workspace.objects.create(
            name='Feedback WS',
            model_names=['llama3'],
        )
        self.other = Workspace.objects.create(
            name='Other WS',
            model_names=['llama3'],
        )
        self.raw, self.token = WidgetToken.create_for_workspace(
            self.workspace,
            label='embed',
        )
        self.log = WorkspaceChatLog.objects.create(
            sent_by='widget',
            workspace=self.workspace,
            prompt='Питання',
            response='Відповідь',
        )
        self.other_log = WorkspaceChatLog.objects.create(
            sent_by='widget',
            workspace=self.other,
            prompt='Чуже',
            response='Чуже',
        )
        self.url = reverse(
            'widget_chat_log_feedback',
            kwargs={'log_id': self.log.pk},
        )

    def _auth(self):
        return {'HTTP_AUTHORIZATION': f'Widget-Token {self.raw}'}

    def test_feedback_up_returns_json(self):
        """Успішний feedback повертає JSON із оновленим полем."""
        response = self.client.post(
            self.url,
            {'feedback': 'up'},
            format='json',
            **self._auth(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['feedback'], 'up')
        self.log.refresh_from_db()
        self.assertEqual(self.log.feedback, 'up')

    def test_invalid_feedback_returns_400_json(self):
        """Невалідний feedback → 400 з JSON error."""
        response = self.client.post(
            self.url,
            {'feedback': 'maybe'},
            format='json',
            **self._auth(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_foreign_workspace_log_forbidden(self):
        """Лог іншого workspace → 403."""
        url = reverse(
            'widget_chat_log_feedback',
            kwargs={'log_id': self.other_log.pk},
        )
        response = self.client.post(
            url,
            {'feedback': 'down'},
            format='json',
            **self._auth(),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_log_returns_404(self):
        """Неіснуючий log_id → 404 JSON."""
        url = reverse(
            'widget_chat_log_feedback',
            kwargs={'log_id': 999999},
        )
        response = self.client.post(
            url,
            {'feedback': 'up'},
            format='json',
            **self._auth(),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_rejected(self):
        """Без Widget-Token → 401/403."""
        response = self.client.post(
            self.url,
            {'feedback': 'up'},
            format='json',
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class WidgetConfigJsonTests(APITestCase):
    """Конфіг віджета завжди JSON."""

    def setUp(self):
        self.workspace = Workspace.objects.create(
            name='Cfg WS',
            model_names=['llama3'],
            meilisearch_course_id='course-v1:ORG+WS+1',
        )
        self.raw, _token = WidgetToken.create_for_workspace(
            self.workspace,
            label='cfg',
            openedx_course_id='course-v1:ORG+TOKEN+1',
        )

    def test_config_prefers_token_course_id(self):
        """openedx_course_id у JSON береться з token, потім workspace."""
        response = self.client.get(
            reverse('widget_config'),
            HTTP_AUTHORIZATION=f'Widget-Token {self.raw}',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['openedx_course_id'],
            'course-v1:ORG+TOKEN+1',
        )
