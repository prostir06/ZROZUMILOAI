"""Регресійні тести roadmap: Meili timeout, widget course scope, chat limits."""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.test import APITestCase

from chats.serializers import ChatSerializer
from workspaces.models import WidgetToken, Workspace
from workspaces.rag.meilisearch_search import search_openedx_meilisearch

User = get_user_model()


class MeilisearchTimeoutTests(SimpleTestCase):
    @override_settings(MEILISEARCH_TIMEOUT_MS=5000, RAG_TOP_K=3)
    @patch('workspaces.rag.meilisearch_search.meilisearch.Client')
    def test_client_timeout_is_seconds(self, mock_client_cls):
        """MEILISEARCH_TIMEOUT_MS конвертується в секунди для SDK."""
        workspace = Workspace(
            search_source=Workspace.SearchSource.MEILISEARCH,
            meilisearch_url='https://meilisearch.example.com',
            meilisearch_api_key='key',
            meilisearch_index_prefix='tutor_',
            meilisearch_indexes=['course_info'],
        )
        mock_index = MagicMock()
        mock_index.search.return_value = {'hits': []}
        mock_client = MagicMock()
        mock_client.index.return_value = mock_index
        mock_client_cls.return_value = mock_client

        search_openedx_meilisearch(workspace, 'query', top_k=1)

        mock_client_cls.assert_called_once()
        kwargs = mock_client_cls.call_args.kwargs
        self.assertEqual(kwargs.get('timeout'), 5.0)


class WidgetCourseScopeTests(APITestCase):
    def setUp(self):
        self.workspace = Workspace.objects.create(
            name='Course WS',
            model_names=['llama3'],
            meilisearch_course_id='',
        )
        self.raw, self.token = WidgetToken.create_for_workspace(
            self.workspace,
            label='locked',
            openedx_course_id='course-v1:ORG+LOCKED+1',
        )
        self.url = reverse('widget_chat')

    @patch('workspaces.widget_views.run_chat')
    def test_client_cannot_override_token_course_id(self, mock_run_chat):
        """Якщо token має course id — клієнтський openedx_course_id ігнорується."""
        mock_run_chat.return_value = Response(
            {'message': {'content': 'ok'}},
            status=status.HTTP_200_OK,
        )

        response = self.client.post(
            self.url,
            {
                'model': 'llama3',
                'messages': [{'role': 'user', 'content': 'Hi'}],
                'stream': False,
                'openedx_course_id': 'course-v1:ORG+HACKED+1',
            },
            format='json',
            HTTP_AUTHORIZATION=f'Widget-Token {self.raw}',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        kwargs = mock_run_chat.call_args.kwargs
        self.assertEqual(kwargs['meilisearch_course_id'], 'course-v1:ORG+LOCKED+1')

    @patch('workspaces.widget_views.run_chat')
    def test_client_may_set_course_when_unlocked(self, mock_run_chat):
        """Без course на token/workspace клієнт може передати openedx_course_id."""
        self.token.openedx_course_id = ''
        self.token.save(update_fields=['openedx_course_id'])
        mock_run_chat.return_value = Response(
            {'message': {'content': 'ok'}},
            status=status.HTTP_200_OK,
        )

        response = self.client.post(
            self.url,
            {
                'model': 'llama3',
                'messages': [{'role': 'user', 'content': 'Hi'}],
                'stream': False,
                'openedx_course_id': 'course-v1:ORG+FREE+1',
            },
            format='json',
            HTTP_AUTHORIZATION=f'Widget-Token {self.raw}',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        kwargs = mock_run_chat.call_args.kwargs
        self.assertEqual(kwargs['meilisearch_course_id'], 'course-v1:ORG+FREE+1')


class ChatSerializerLimitsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='limits', password='pass')
        self.workspace = Workspace.objects.create(
            name='Limits WS',
            model_names=['llama3'],
        )
        self.workspace.users.add(self.user)
        self.factory = RequestFactory()

    def _serializer(self, data):
        request = self.factory.post('/')
        request.user = self.user
        return ChatSerializer(data=data, context={'request': request})

    @override_settings(CHAT_MAX_MESSAGES=2)
    def test_rejects_too_many_messages(self):
        serializer = self._serializer({
            'title': 'Test',
            'model': 'llama3',
            'workspace': self.workspace.pk,
            'messages': [
                {'role': 'user', 'content': 'a'},
                {'role': 'assistant', 'content': 'b'},
                {'role': 'user', 'content': 'c'},
            ],
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('messages', serializer.errors)

    @override_settings(CHAT_MAX_MESSAGE_CHARS=5)
    def test_rejects_oversized_message(self):
        serializer = self._serializer({
            'title': 'Test',
            'model': 'llama3',
            'workspace': self.workspace.pk,
            'messages': [{'role': 'user', 'content': 'too-long'}],
        })
        self.assertFalse(serializer.is_valid())
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)
