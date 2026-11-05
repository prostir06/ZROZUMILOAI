"""API ACL для ChatView та feedback."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient

from chats.models import WorkspaceChatLog
from workspaces.models import Workspace

User = get_user_model()


class ChatViewAclTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner_chat', password='pass')
        self.stranger = User.objects.create_user(username='stranger_chat', password='pass')
        self.workspace = Workspace.objects.create(
            name='Chat WS',
            model_names=['llama3'],
        )
        self.workspace.users.add(self.owner)
        self.client = APIClient()

    @patch('ollama_proxy.views.run_chat')
    def test_owner_can_chat(self, mock_run):
        mock_run.return_value = Response({'message': {'content': 'ok'}})

        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            '/api/ollama/chat/',
            {
                'model': 'llama3',
                'messages': [{'role': 'user', 'content': 'Hi'}],
                'stream': False,
                'workspace_id': self.workspace.pk,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        self.assertEqual(kwargs.get('model'), 'llama3')
        self.assertEqual(kwargs.get('workspace'), self.workspace)
        self.assertEqual(kwargs.get('user'), self.owner)
        self.assertFalse(kwargs.get('stream'))

    def test_chat_requires_auth(self):
        response = self.client.post(
            '/api/ollama/chat/',
            {
                'model': 'llama3',
                'messages': [{'role': 'user', 'content': 'Hi'}],
                'workspace_id': self.workspace.pk,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_chat_rejects_oversized_model_name(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            '/api/ollama/chat/',
            {
                'model': 'x' * 201,
                'messages': [{'role': 'user', 'content': 'Hi'}],
                'workspace_id': self.workspace.pk,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_model_pull_forbidden_for_non_admin(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            '/api/ollama/models/pull/',
            {'name': 'llama3'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_stranger_denied_workspace(self):
        self.client.force_authenticate(user=self.stranger)
        response = self.client.post(
            '/api/ollama/chat/',
            {
                'model': 'llama3',
                'messages': [{'role': 'user', 'content': 'Hi'}],
                'stream': False,
                'workspace_id': self.workspace.pk,
            },
            format='json',
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST),
        )

    @patch('ollama_proxy.views.run_chat')
    def test_workspace_course_id_locks_client_override(self, mock_run):
        """meilisearch_course_id workspace блокує openedx_course_id з клієнта."""
        mock_run.return_value = Response({'message': {'content': 'ok'}})
        self.workspace.meilisearch_course_id = 'course-v1:ORG+LOCKED+2024'
        self.workspace.save(update_fields=['meilisearch_course_id'])

        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            '/api/ollama/chat/',
            {
                'model': 'llama3',
                'messages': [{'role': 'user', 'content': 'Hi'}],
                'stream': False,
                'workspace_id': self.workspace.pk,
                'openedx_course_id': 'course-v1:OTHER+ANY+2024',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        _, kwargs = mock_run.call_args
        self.assertEqual(
            kwargs.get('meilisearch_course_id'),
            'course-v1:ORG+LOCKED+2024',
        )


class ChatFeedbackApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fb_user', password='pass')
        self.other = User.objects.create_user(username='fb_other', password='pass')
        self.workspace = Workspace.objects.create(name='FB WS', model_names=['llama3'])
        self.log = WorkspaceChatLog.objects.create(
            user=self.user,
            sent_by='fb_user',
            workspace=self.workspace,
            prompt='q',
            response='a',
        )
        self.client = APIClient()

    def test_owner_can_submit_feedback(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f'/api/chats/logs/{self.log.pk}/feedback/',
            {'feedback': 'up'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.log.refresh_from_db()
        self.assertEqual(self.log.feedback, 'up')

    def test_other_user_forbidden(self):
        self.client.force_authenticate(user=self.other)
        response = self.client.post(
            f'/api/chats/logs/{self.log.pk}/feedback/',
            {'feedback': 'down'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
