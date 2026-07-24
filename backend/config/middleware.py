"""
HTTP middleware для кореляції запитів у логах.

Додає/прокидає X-Request-ID і робить його доступним у logging.Filter.

Примітка: Django логує 4xx/5xx у BaseHandler ПІСЛЯ повернення з middleware,
тому request_id скидається лише на початку наступного запиту (не в finally).
"""
from __future__ import annotations

import logging
import threading
import uuid

# Thread-local сховище request_id для поточного запиту.
_request_context = threading.local()


def get_request_id() -> str:
    """Повернути request_id поточного потоку або '-' поза HTTP-запитом."""
    return getattr(_request_context, 'request_id', '-')


class RequestIdFilter(logging.Filter):
    """Додає поле request_id у LogRecord для форматера."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


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
