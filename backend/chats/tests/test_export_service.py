"""Unit-тести експорту Chats Info."""
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from chats.export_service import (
    build_export_filename,
    build_export_response,
    build_export_timestamp,
    parse_export_format,
    rows_to_alpaca,
    serialize_log_row,
    serialize_logs,
)
from chats.models import WorkspaceChatLog
from workspaces.models import Workspace


class ParseExportFormatTests(TestCase):
    """Тести парсингу формату експорту."""

    def setUp(self):
        """RequestFactory для mock-запитів."""
        self.factory = RequestFactory()

    def test_default_is_json(self):
        """Без параметрів — json."""
        request = self.factory.get('/api/chats/logs/export/')
        self.assertEqual(parse_export_format(request), 'json')

    def test_export_format_param(self):
        """Параметр export_format."""
        request = self.factory.get('/api/chats/logs/export/?export_format=csv')
        self.assertEqual(parse_export_format(request), 'csv')

    def test_type_param_fallback(self):
        """Альтернативний параметр type."""
        request = self.factory.get('/api/chats/logs/export/?type=jsonl')
        self.assertEqual(parse_export_format(request), 'jsonl')


class SerializeLogRowTests(TestCase):
    """Тести серіалізації одного запису."""

    def setUp(self):
        """Тестовий log."""
        self.workspace = Workspace.objects.create(
            name='zrozumilo',
            model_names=['llama3'],
        )
        self.log = WorkspaceChatLog.objects.create(
            sent_by='tester',
            workspace=self.workspace,
            prompt='Питання',
            response='Відповідь',
        )

    def test_serialize_log_row(self):
        """Коректні поля у словнику."""
        row = serialize_log_row(self.log)
        self.assertEqual(row['sent_by'], 'tester')
        self.assertEqual(row['workspace'], 'zrozumilo')
        self.assertEqual(row['prompt'], 'Питання')
        self.assertIn('sent_at', row)


class BuildExportResponseTests(TestCase):
    """Тести формування HTTP-відповіді експорту."""

    def setUp(self):
        """Приклад даних для експорту."""
        self.rows = [{
            'id': 1,
            'sent_by': 'u',
            'workspace': 'ws',
            'prompt': 'q',
            'response': 'a',
            'sent_at': '2026-06-21T12:00:00',
        }]

    def test_csv_export(self):
        """CSV містить заголовок і дані."""
        response = build_export_response(self.rows, 'csv', timestamp='test')
        self.assertIsInstance(response, HttpResponse)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('id,sent_by', response.content.decode('utf-8'))

    def test_json_export(self):
        """JSON — масив об'єктів."""
        response = build_export_response(self.rows, 'json', timestamp='test')
        self.assertIn('application/json', response['Content-Type'])
        self.assertIn('"prompt": "q"', response.content.decode('utf-8'))

    def test_jsonl_export(self):
        """JSONL — один JSON на рядок."""
        response = build_export_response(self.rows, 'jsonl', timestamp='test')
        self.assertIn('ndjson', response['Content-Type'])
        lines = response.content.decode('utf-8').strip().split('\n')
        self.assertEqual(len(lines), 1)

    def test_alpaca_export(self):
        """Alpaca — instruction/input/output."""
        alpaca = rows_to_alpaca(self.rows)
        self.assertEqual(alpaca[0]['instruction'], 'q')
        self.assertEqual(alpaca[0]['output'], 'a')
        response = build_export_response(self.rows, 'alpaca', timestamp='test')
        self.assertIn('.alpaca.json', response['Content-Disposition'])

    def test_build_export_filename(self):
        """Імена файлів для різних форматів."""
        self.assertTrue(build_export_filename('csv', 't').endswith('.csv'))
        self.assertTrue(build_export_filename('jsonl', 't').endswith('.jsonl'))
        self.assertIn('alpaca', build_export_filename('alpaca', 't'))

    def test_build_export_timestamp_from_queryset(self):
        """Timestamp має формат YYYYMMDD_HHMMSS."""
        workspace = Workspace.objects.create(name='ws', model_names=['m'])
        WorkspaceChatLog.objects.create(
            sent_by='u',
            workspace=workspace,
            prompt='p',
        )
        logs = WorkspaceChatLog.objects.order_by('-created_at')
        ts = build_export_timestamp(logs)
        self.assertRegex(ts, r'^\d{8}_\d{6}$')

    def test_serialize_logs_list(self):
        """serialize_logs для списку моделей."""
        workspace = Workspace.objects.create(name='ws2', model_names=['m'])
        log = WorkspaceChatLog.objects.create(
            sent_by='x',
            workspace=workspace,
            prompt='p',
        )
        rows = serialize_logs([log])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['sent_by'], 'x')
