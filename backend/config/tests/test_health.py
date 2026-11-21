"""Unit-тести /api/health/, /api/health/details/ та /api/health/metrics/."""
import time
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from chats.models import WorkspaceChatLog
from workspaces.models import TelegramBot, Workspace, WorkspaceDocument
from workspaces.telegram.poller import TELEGRAM_POLLER_HEARTBEAT_CACHE_KEY

User = get_user_model()


class HealthEndpointTests(TestCase):
    """Health має відповідати без auth і відображати стан БД, кешу та Ollama."""

    def setUp(self):
        cache.clear()

    @patch('config.health.OllamaService')
    def test_health_ok_when_database_and_ollama_available(self, mock_ollama_cls):
        mock_ollama_cls.return_value.health.return_value = True
        response = self.client.get(reverse('api_health'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['database'], 'ok')
        self.assertEqual(data['ollama'], 'ok')
        self.assertIn(data.get('cache'), ('ok', 'miss', 'error', 'unknown'))

        res_strict = self.client.get(f"{reverse('api_health')}?strict=1")
        self.assertEqual(res_strict.status_code, 200)
        self.assertEqual(res_strict.json()['status'], 'ok')

    @patch('config.health.OllamaService')
    def test_health_degraded_200_by_default_and_503_with_strict_when_ollama_down(
        self,
        mock_ollama_cls,
    ):
        mock_ollama_cls.return_value.health.return_value = False

        res_default = self.client.get(reverse('api_health'))
        self.assertEqual(res_default.status_code, 200)
        self.assertEqual(res_default.json()['status'], 'degraded')
        self.assertEqual(res_default.json()['ollama'], 'error')

        res_strict = self.client.get(f"{reverse('api_health')}?strict=1")
        self.assertEqual(res_strict.status_code, 503)
        self.assertEqual(res_strict.json()['status'], 'degraded')
        self.assertEqual(res_strict.json()['ollama'], 'error')

    @patch('config.health.OllamaService')
    def test_health_degraded_when_ollama_raises_exception(
        self,
        mock_ollama_cls,
    ):
        mock_ollama_cls.return_value.health.side_effect = ConnectionError('Ollama unreachable')

        res_default = self.client.get(reverse('api_health'))
        self.assertEqual(res_default.status_code, 200)
        self.assertEqual(res_default.json()['status'], 'degraded')
        self.assertEqual(res_default.json()['ollama'], 'error')

        cache.clear()
        res_strict = self.client.get(f"{reverse('api_health')}?strict=1")
        self.assertEqual(res_strict.status_code, 503)
        self.assertEqual(res_strict.json()['status'], 'degraded')
        self.assertEqual(res_strict.json()['ollama'], 'error')

    @patch('config.health.OllamaService')
    @patch('config.health.connection')
    def test_health_degraded_when_database_fails(
        self,
        mock_connection,
        mock_ollama_cls,
    ):
        mock_ollama_cls.return_value.health.return_value = True
        mock_connection.ensure_connection.side_effect = DatabaseError('down')

        # Non-strict must return HTTP 503
        response = self.client.get(reverse('api_health'))
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data['status'], 'degraded')
        self.assertEqual(data['database'], 'error')

        # Strict must also return HTTP 503
        res_strict = self.client.get(f"{reverse('api_health')}?strict=1")
        self.assertEqual(res_strict.status_code, 503)
        data_strict = res_strict.json()
        self.assertEqual(data_strict['status'], 'degraded')
        self.assertEqual(data_strict['database'], 'error')

    @patch('config.health.OllamaService')
    def test_check_ollama_status_caches_result_for_subsequent_calls(
        self,
        mock_ollama_cls,
    ):
        mock_ollama_cls.return_value.health.return_value = True

        res1 = self.client.get(reverse('api_health'))
        res2 = self.client.get(reverse('api_health'))

        self.assertEqual(res1.json()['ollama'], 'ok')
        self.assertEqual(res2.json()['ollama'], 'ok')
        self.assertEqual(mock_ollama_cls.return_value.health.call_count, 1)


class HealthDetailsAndMetricsTests(TestCase):
    """Тести адмін-ендпоінтів /api/health/details/ та /api/health/metrics/."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='regular_obs', password='pass')
        self.admin = User.objects.create_superuser(
            username='admin_obs',
            email='admin_obs@example.com',
            password='pass',
        )
        self.api_client = APIClient()
        self.workspace = Workspace.objects.create(name='Obs Course')

    def test_details_and_metrics_require_admin(self):
        for url_name in ('api_health_details', 'api_health_metrics'):
            url = reverse(url_name)
            self.api_client.force_authenticate(user=None)
            self.assertEqual(self.api_client.get(url).status_code, 401)

            self.api_client.force_authenticate(user=self.user)
            self.assertEqual(self.api_client.get(url).status_code, 403)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('config.health.OllamaService')
    def test_details_returns_component_aggregates_and_healthy_poller(
        self,
        mock_ollama_cls,
    ):
        mock_ollama_cls.return_value.health.return_value = True
        cache.set(TELEGRAM_POLLER_HEARTBEAT_CACHE_KEY, time.time(), timeout=60)

        WorkspaceDocument.objects.create(
            workspace=self.workspace,
            original_filename='ready.pdf',
            status=WorkspaceDocument.Status.READY,
        )
        WorkspaceDocument.objects.create(
            workspace=self.workspace,
            original_filename='proc.pdf',
            status=WorkspaceDocument.Status.PROCESSING,
        )
        WorkspaceDocument.objects.create(
            workspace=self.workspace,
            original_filename='fail.pdf',
            status=WorkspaceDocument.Status.FAILED,
        )

        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.get(reverse('api_health_details'))
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['database'], 'ok')
        self.assertEqual(data['ollama'], 'ok')
        self.assertEqual(data['celery'], {'status': 'eager', 'workers': 0})
        self.assertEqual(data['telegram_poller']['status'], 'ok')
        self.assertEqual(
            data['rag'],
            {
                'total_documents': 3,
                'processing': 1,
                'ready': 1,
                'failed': 1,
            },
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch('config.observability.celery_app')
    @patch('config.health.OllamaService')
    def test_details_checks_celery_ping_and_marks_degraded_with_strict_503(
        self,
        mock_ollama_cls,
        mock_celery_app,
    ):
        mock_ollama_cls.return_value.health.return_value = True
        mock_celery_app.control = MagicMock()
        mock_celery_app.control.ping.return_value = [{'worker@1': {'ok': 'pong'}}]

        self.api_client.force_authenticate(user=self.admin)
        ok_resp = self.api_client.get(reverse('api_health_details'))
        self.assertEqual(ok_resp.status_code, 200)
        self.assertEqual(ok_resp.json()['celery'], {'status': 'ok', 'workers': 1})

        # Коли кеш очищено, немає воркерів і є активний бот без heartbeat -> degraded
        cache.clear()
        mock_celery_app.control.ping.return_value = []
        TelegramBot.objects.create(
            name='Bot Obs',
            workspace=self.workspace,
            is_active=True,
            last_error='Network timeout',
        )

        degraded_resp = self.api_client.get(
            f"{reverse('api_health_details')}?strict=1",
        )
        self.assertEqual(degraded_resp.status_code, 503)
        payload = degraded_resp.json()
        self.assertEqual(payload['status'], 'degraded')
        self.assertEqual(payload['celery'], {'status': 'error', 'workers': 0})
        self.assertEqual(payload['telegram_poller']['status'], 'offline')
        self.assertEqual(payload['telegram_poller']['active_bots'], 1)
        self.assertEqual(payload['telegram_poller']['bots_with_errors'], 1)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('config.health.OllamaService')
    def test_prometheus_metrics_endpoint_outputs_gauges(self, mock_ollama_cls):
        mock_ollama_cls.return_value.health.return_value = True
        WorkspaceChatLog.objects.create(
            workspace=self.workspace,
            channel=WorkspaceChatLog.Channel.TELEGRAM,
            prompt='Q',
            response='A',
            needs_handoff=True,
        )

        self.api_client.force_authenticate(user=self.admin)
        response = self.api_client.get(reverse('api_health_metrics'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/plain', response['Content-Type'])

        text = response.content.decode('utf-8')
        self.assertIn('zrozumiloai_component_up{component="database"} 1', text)
        self.assertIn('zrozumiloai_rag_documents_total{status="failed"} 0', text)
        self.assertIn('zrozumiloai_chat_logs_total{channel="telegram"} 1', text)
        self.assertIn('zrozumiloai_chat_logs_handoff_total 1', text)

