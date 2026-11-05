"""
HTTP middleware для кореляції запитів у логах.

Додає/прокидає X-Request-ID і робить його доступним у logging.Filter.

Примітка: Django логує 4xx/5xx у BaseHandler ПІСЛЯ повернення з middleware,
тому request_id скидається лише на початку наступного запиту (не в finally).
"""
import json
import logging
import threading
import uuid
from datetime import datetime, timezone

# Thread-local сховище request_id для поточного запиту.
_request_context = threading.local()


def get_request_id():
    """Повернути request_id поточного потоку або '-' поза HTTP-запитом."""
    return getattr(_request_context, 'request_id', '-')


def set_request_id(request_id):
    """Встановити request_id (HTTP middleware або Celery worker)."""
    _request_context.request_id = (request_id or '-').strip() or '-'


class RequestIdFilter(logging.Filter):
    """Додає поле request_id у LogRecord для форматера."""

    def filter(self, record):
        record.request_id = get_request_id()
        return True


class JsonLogFormatter(logging.Formatter):
    """Структуровані JSON-логи з request_id (без сторонніх залежностей)."""

    def format(self, record):
        payload = {
            'ts': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', '-'),
        }
        if record.exc_info:
            payload['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class RequestIdMiddleware:
    """
    Middleware: читає X-Request-ID з клієнта або генерує UUID4.

    Відповідь завжди містить заголовок X-Request-ID.
    """

    HEADER = 'HTTP_X_REQUEST_ID'
    RESPONSE_HEADER = 'X-Request-ID'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Скидаємо попередній контекст потоку перед новим запитом.
        _request_context.request_id = '-'

        try:
            incoming = (request.META.get(self.HEADER) or '').strip()
            request_id = incoming or str(uuid.uuid4())
        except Exception:
            request_id = str(uuid.uuid4())

        _request_context.request_id = request_id
        request.request_id = request_id

        try:
            response = self.get_response(request)
        except Exception:
            # Залишаємо request_id для логування винятку в BaseHandler.
            raise

        try:
            response[self.RESPONSE_HEADER] = request_id
        except Exception:
            # Деякі streaming-відповіді можуть не підтримувати __setitem__.
            pass

        return response
