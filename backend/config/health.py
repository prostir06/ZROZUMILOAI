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

from ollama_proxy.services import OllamaService

logger = logging.getLogger(__name__)

OLLAMA_HEALTH_CACHE_KEY = 'health:ollama_status'
OLLAMA_HEALTH_CACHE_TTL = 10


def _check_ollama_status():
    """Перевірити доступність Ollama з коротким кешем (10 с)."""
    try:
        cached = cache.get(OLLAMA_HEALTH_CACHE_KEY)
        if cached in ('ok', 'error'):
            return cached
    except Exception as exc:  # noqa: BLE001
        logger.debug('Health Ollama cache read failed: %s', exc)

    status_val = 'error'
    try:
        if OllamaService().health():
            status_val = 'ok'
    except Exception as exc:  # noqa: BLE001
        logger.warning('Health Ollama check failed: %s', exc)

    try:
        cache.set(OLLAMA_HEALTH_CACHE_KEY, status_val, timeout=OLLAMA_HEALTH_CACHE_TTL)
    except Exception as exc:  # noqa: BLE001
        logger.debug('Health Ollama cache write failed: %s', exc)

    return status_val


class HealthView(View):
    """
    GET /api/health/

    Перевіряє підключення до БД, кешу та Ollama.
    За замовчуванням повертає HTTP 200, поки жива БД (щоб Docker не рестартував
    backend під час рестарту Ollama). З параметром ?strict=1 повертає 503,
    якщо будь-який компонент (зокрема Ollama) у стані degraded.
    """

    def get(self, request):
        """Зібрати статус залежностей у JSON-відповідь."""
        payload = {
            'status': 'ok',
            'database': 'ok',
            'cache': 'unknown',
            'ollama': 'unknown',
        }
        http_status = 200
        strict = str(request.GET.get('strict', '')).strip().lower() in (
            '1', 'true', 'yes',
        )

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

        ollama_status = _check_ollama_status()
        payload['ollama'] = ollama_status
        if ollama_status != 'ok':
            payload['status'] = 'degraded'
            if strict:
                http_status = 503

        try:
            return JsonResponse(payload, status=http_status)
        except Exception as exc:  # noqa: BLE001
            logger.exception('Health JsonResponse failed: %s', exc)
            return JsonResponse(
                {
                    'status': 'error',
                    'database': 'unknown',
                    'cache': 'unknown',
                    'ollama': 'unknown',
                },
                status=503,
            )

