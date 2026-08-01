"""
Публічний healthcheck для Docker / reverse-proxy.

Повертає JSON без автентифікації. Не повинен кидати необроблені
винятки — інакше healthcheck Compose/Kubernetes вважатиме контейнер мертвим.
"""
import logging

from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views import View

logger = logging.getLogger(__name__)


class HealthView(View):
    """
    GET /api/health/

    Перевіряє підключення до БД. Кеш (Redis/локальний) — best-effort:
    помилка кешу не робить сервіс «мертвим», лише позначає degraded.
    """

    def get(self, request):
        """Зібрати статус залежностей у JSON-відповідь."""
        payload = {
            'status': 'ok',
            'database': 'ok',
            'cache': 'unknown',
        }
        http_status = 200

        # БД критична: без неї API не обслуговує запити.
        try:
            connection.ensure_connection()
        except DatabaseError as exc:
            logger.warning('Health DB check failed: %s', exc)
            payload['status'] = 'degraded'
            payload['database'] = 'error'
            http_status = 503
        except Exception as exc:  # noqa: BLE001 — health ніколи не повинен падати
            logger.exception('Unexpected health DB error: %s', exc)
            payload['status'] = 'degraded'
            payload['database'] = 'error'
            http_status = 503

        # Кеш опційний (FileBasedCache / LocMem також ок).
        try:
            cache.set('healthcheck', '1', timeout=5)
            cached = cache.get('healthcheck')
            payload['cache'] = 'ok' if cached == '1' else 'miss'
        except Exception as exc:  # noqa: BLE001
            logger.warning('Health cache check failed: %s', exc)
            payload['cache'] = 'error'
            # Не піднімаємо HTTP 503 лише через кеш — чат може працювати без Redis.

        try:
            return JsonResponse(payload, status=http_status)
        except Exception as exc:  # noqa: BLE001
            logger.exception('Health JsonResponse failed: %s', exc)
            return JsonResponse(
                {'status': 'error', 'database': 'unknown', 'cache': 'unknown'},
                status=503,
            )
