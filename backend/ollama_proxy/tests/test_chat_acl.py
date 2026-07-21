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
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
