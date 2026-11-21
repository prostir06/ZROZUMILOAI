"""
Healthcheck та observability endpoints для Docker, reverse-proxy і адмін-панелі.

Публічний GET /api/health/ не вимагає автентифікації та не повинен кидати
необроблені винятки. Деталі компонентів і Prometheus-метрики закриті IsAdminUser.
"""
import logging

from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.views import View
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from ollama_proxy.services import OllamaService

from .observability import (
    OLLAMA_HEALTH_CACHE_KEY,
    OLLAMA_HEALTH_CACHE_TTL,
    check_cache_status,
    check_database_status,
    check_ollama_status,
    collect_system_health_details,
    render_prometheus_metrics,
)

logger = logging.getLogger(__name__)

__all__ = [
    'OLLAMA_HEALTH_CACHE_KEY',
    'OLLAMA_HEALTH_CACHE_TTL',
    'HealthView',
    'HealthDetailsView',
    'HealthMetricsView',
]


def _check_ollama_status():
    """Зворотна сумісність із тестами, що мокають config.health.OllamaService."""
    return check_ollama_status(
        service_cls=OllamaService,
        cache_backend=cache,
    )


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
        db_status = check_database_status(db_connection=connection)
        cache_status = check_cache_status(cache_backend=cache)
        ollama_status = _check_ollama_status()

        payload = {
            'status': 'ok',
            'database': db_status,
            'cache': cache_status,
            'ollama': ollama_status,
        }
        http_status = 200
        strict = str(request.GET.get('strict', '')).strip().lower() in (
            '1', 'true', 'yes',
        )

        if db_status != 'ok':
            payload['status'] = 'degraded'
            http_status = 503

        if ollama_status != 'ok':
            payload['status'] = 'degraded'
            if strict:
                http_status = 503

        try:
            return JsonResponse(payload, status=http_status)
        except Exception as exc:
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


class HealthDetailsView(APIView):
    """GET /api/health/details/ — розширений стан системи для адмін-дашборду."""

    permission_classes = (IsAdminUser,)

    def get(self, request):
        """Повернути деталізований стан БД, Redis, Ollama, Celery, Poller і RAG."""
        details = collect_system_health_details(
            service_cls=OllamaService,
            db_connection=connection,
            cache_backend=cache,
        )
        strict = str(request.query_params.get('strict', '')).strip().lower() in (
            '1', 'true', 'yes',
        )
        http_status = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if strict and details['status'] != 'ok'
            else status.HTTP_200_OK
        )
        return Response(details, status=http_status)


class HealthMetricsView(APIView):
    """GET /api/health/metrics/ — Prometheus text exposition для адміна."""

    permission_classes = (IsAdminUser,)

    def get(self, request):
        """Віддати поточні метрики сервісів у форматі Prometheus."""
        body = render_prometheus_metrics(
            service_cls=OllamaService,
            db_connection=connection,
            cache_backend=cache,
        )
        return HttpResponse(
            body,
            content_type='text/plain; version=0.0.4; charset=utf-8',
        )
