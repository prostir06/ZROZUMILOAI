"""Експорт записів Chats Info у CSV, JSON, JSONL та Alpaca."""
import csv
import io
import json
import logging

from django.http import HttpResponse
from django.utils import timezone

logger = logging.getLogger(__name__)

# Допустимі формати (не використовуємо query-параметр «format» — конфлікт з DRF).
SUPPORTED_EXPORT_FORMATS = frozenset({
    'csv',
    'json',
    'jsonl',
    'alpaca',
    'json_alpaca',
    'json-alpaca',
})

EXPORT_FIELDNAMES = ('id', 'sent_by', 'workspace', 'prompt', 'response', 'sent_at')


def _get_query_param(request, key):
    """Отримати query-параметр (DRF Request або Django HttpRequest)."""
    if hasattr(request, 'query_params'):
        return request.query_params.get(key)
    return request.GET.get(key)


def parse_export_format(request):
    """
    Отримати формат експорту з query-параметрів запиту.

    Параметри: export_format або type. За замовчуванням — json.
    """
    raw_value = (
        _get_query_param(request, 'export_format')
        or _get_query_param(request, 'type')
        or 'json'
    )
    return str(raw_value).strip().lower() or 'json'


def serialize_log_row(log):
    """
    Перетворити модель WorkspaceChatLog у словник для експорту.

    Безпечно обробляє відсутній workspace.
    """
    workspace_name = ''
    try:
        workspace_name = log.workspace.name if log.workspace_id else ''
    except AttributeError:
        workspace_name = ''

    return {
        'id': log.id,
        'sent_by': log.sent_by,
        'workspace': workspace_name,
        'prompt': log.prompt,
        'response': log.response,
        'sent_at': log.created_at.isoformat() if log.created_at else '',
    }


def serialize_logs(logs):
    """Серіалізувати queryset або список логів."""
    return [serialize_log_row(log) for log in logs]


def build_export_timestamp(logs):
    """Ім'я файлу: timestamp останнього запису або «empty»."""
    try:
        first_log = logs.first() if hasattr(logs, 'first') else None
        if first_log and first_log.created_at:
            return first_log.created_at.strftime('%Y%m%d_%H%M%S')
    except (AttributeError, TypeError) as exc:
        logger.warning('Не вдалося сформувати timestamp експорту: %s', exc)
    return 'empty'


def build_export_filename(export_format, timestamp):
    """Побудувати ім'я файлу для Content-Disposition."""
    if export_format in ('alpaca', 'json_alpaca', 'json-alpaca'):
        return f'workspace_chats_{timestamp}.alpaca.json'
    if export_format == 'jsonl':
        return f'workspace_chats_{timestamp}.jsonl'
    if export_format == 'csv':
        return f'workspace_chats_{timestamp}.csv'
    return f'workspace_chats_{timestamp}.json'


def rows_to_alpaca(rows):
    """Конвертувати рядки логів у формат Alpaca (instruction/input/output)."""
    return [
        {
            'instruction': row['prompt'],
            'input': '',
            'output': row['response'],
        }
        for row in rows
    ]


def build_export_response(rows, export_format, timestamp=None):
    """
    Побудувати HttpResponse з файлом експорту.

    :raises ValueError: якщо формат не підтримується або помилка серіалізації
    """
    export_format = (export_format or 'json').lower()
    timestamp = timestamp or timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = build_export_filename(export_format, timestamp)

    try:
        if export_format == 'csv':
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
            payload = buffer.getvalue()
            content_type = 'text/csv; charset=utf-8'
        elif export_format == 'jsonl':
            payload = '\n'.join(
                json.dumps(row, ensure_ascii=False) for row in rows
            )
            content_type = 'application/x-ndjson; charset=utf-8'
        elif export_format in ('alpaca', 'json_alpaca', 'json-alpaca'):
            payload = json.dumps(
                rows_to_alpaca(rows),
                ensure_ascii=False,
                indent=2,
            )
            content_type = 'application/json; charset=utf-8'
        else:
            payload = json.dumps(rows, ensure_ascii=False, indent=2)
            content_type = 'application/json; charset=utf-8'
    except (TypeError, ValueError, csv.Error) as exc:
        logger.error('Помилка формування експорту (%s): %s', export_format, exc)
        raise ValueError('Не вдалося сформувати файл експорту') from exc

    response = HttpResponse(payload, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
