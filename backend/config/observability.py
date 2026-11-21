"""
Системні колектори стану компонентів та Prometheus-метрик.
"""
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connection
from django.db.models import Count, Q

from chats.models import WorkspaceChatLog
from config.celery import app as celery_app
from ollama_proxy.services import OllamaService
from workspaces.models import TelegramBot, WorkspaceDocument
from workspaces.telegram.poller import TELEGRAM_POLLER_HEARTBEAT_CACHE_KEY

logger = logging.getLogger(__name__)

OLLAMA_HEALTH_CACHE_KEY = 'health:ollama_status'
OLLAMA_HEALTH_CACHE_TTL = 10

CELERY_HEALTH_CACHE_KEY = 'health:celery_status'
CELERY_HEALTH_CACHE_TTL = 15

POLLER_STALE_AFTER_SECONDS = 45.0


def check_database_status(db_connection=connection) -> str:
    """Перевірити доступність підключення до БД."""
    try:
        db_connection.ensure_connection()
        return 'ok'
    except DatabaseError as exc:
        logger.warning('Health DB check failed: %s', exc)
        return 'error'
    except Exception as exc:
        logger.exception('Unexpected health DB error: %s', exc)
        return 'error'


def check_cache_status(cache_backend=cache) -> str:
    """Перевірити запис та читання у Django cache (Redis / LocMem)."""
    try:
        cache_backend.set('healthcheck', '1', timeout=5)
        cached = cache_backend.get('healthcheck')
        return 'ok' if cached == '1' else 'miss'
    except Exception as exc:
        logger.warning('Health cache check failed: %s', exc)
        return 'error'


def check_ollama_status(
    service_cls=OllamaService,
    cache_backend=cache,
) -> str:
    """Перевірити доступність Ollama з коротким кешем (10 с)."""
    try:
        cached = cache_backend.get(OLLAMA_HEALTH_CACHE_KEY)
        if cached in ('ok', 'error'):
            return cached
    except Exception as exc:
        logger.debug('Health Ollama cache read failed: %s', exc)

    status_val = 'error'
    try:
        if service_cls().health():
            status_val = 'ok'
    except Exception as exc:
        logger.warning('Health Ollama check failed: %s', exc)

    try:
        cache_backend.set(
            OLLAMA_HEALTH_CACHE_KEY,
            status_val,
            timeout=OLLAMA_HEALTH_CACHE_TTL,
        )
    except Exception as exc:
        logger.debug('Health Ollama cache write failed: %s', exc)

    return status_val


def check_celery_status(
    celery=None,
    cache_backend=cache,
) -> dict:
    """Перевірити доступність Celery worker через control.ping з кешем (15 с)."""
    if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
        return {'status': 'eager', 'workers': 0}

    active_celery = celery_app if celery is None else celery

    try:
        cached = cache_backend.get(CELERY_HEALTH_CACHE_KEY)
        if isinstance(cached, dict) and cached.get('status') in ('ok', 'error'):
            return cached
    except Exception as exc:
        logger.debug('Health Celery cache read failed: %s', exc)

    result = {'status': 'error', 'workers': 0}
    try:
        responses = active_celery.control.ping(timeout=1.5) or []
        worker_count = len(responses)
        if worker_count > 0:
            result = {'status': 'ok', 'workers': worker_count}
    except Exception as exc:
        logger.warning('Health Celery ping failed: %s', exc)

    try:
        cache_backend.set(
            CELERY_HEALTH_CACHE_KEY,
            result,
            timeout=CELERY_HEALTH_CACHE_TTL,
        )
    except Exception as exc:
        logger.debug('Health Celery cache write failed: %s', exc)

    return result


def check_telegram_poller_status(
    cache_backend=cache,
    now_fn=time.time,
) -> dict:
    """Перевірити heartbeat telegram_poller у Redis та агрегати стану ботів."""
    poller_status = 'offline'
    age_sec = None
    try:
        raw_ts = cache_backend.get(TELEGRAM_POLLER_HEARTBEAT_CACHE_KEY)
        if raw_ts is not None:
            age_sec = round(max(0.0, float(now_fn()) - float(raw_ts)), 1)
            poller_status = 'ok' if age_sec <= POLLER_STALE_AFTER_SECONDS else 'stale'
    except (TypeError, ValueError) as exc:
        logger.debug('Invalid poller heartbeat timestamp in cache: %s', exc)
    except Exception as exc:
        logger.warning('Health Telegram poller cache read failed: %s', exc)

    active_bots = 0
    bots_with_errors = 0
    try:
        bot_stats = TelegramBot.objects.aggregate(
            active_bots=Count(
                'id',
                filter=Q(is_active=True, workspace__isnull=False),
            ),
            bots_with_errors=Count(
                'id',
                filter=Q(is_active=True) & ~Q(last_error=''),
            ),
        )
        active_bots = bot_stats['active_bots'] or 0
        bots_with_errors = bot_stats['bots_with_errors'] or 0
    except DatabaseError as exc:
        logger.warning('Health Telegram bot stats query failed: %s', exc)

    return {
        'status': poller_status,
        'last_heartbeat_age_sec': age_sec,
        'active_bots': active_bots,
        'bots_with_errors': bots_with_errors,
    }


def check_rag_documents_status() -> dict:
    """Агрегація статусів RAG-документів у базі знань."""
    try:
        stats = WorkspaceDocument.objects.aggregate(
            total_documents=Count('id'),
            processing=Count(
                'id',
                filter=Q(status=WorkspaceDocument.Status.PROCESSING),
            ),
            ready=Count(
                'id',
                filter=Q(status=WorkspaceDocument.Status.READY),
            ),
            failed=Count(
                'id',
                filter=Q(status=WorkspaceDocument.Status.FAILED),
            ),
        )
        return {
            'total_documents': stats['total_documents'] or 0,
            'processing': stats['processing'] or 0,
            'ready': stats['ready'] or 0,
            'failed': stats['failed'] or 0,
        }
    except DatabaseError as exc:
        logger.warning('Health RAG documents query failed: %s', exc)
        return {
            'total_documents': 0,
            'processing': 0,
            'ready': 0,
            'failed': 0,
        }


def collect_system_health_details(
    *,
    service_cls=OllamaService,
    db_connection=connection,
    cache_backend=cache,
    celery=None,
    now_fn=time.time,
) -> dict:
    """Зібрати розширену діагностику всіх сервісів для адмін-панелі."""
    database = check_database_status(db_connection=db_connection)
    cache_state = check_cache_status(cache_backend=cache_backend)
    ollama = check_ollama_status(
        service_cls=service_cls,
        cache_backend=cache_backend,
    )
    celery_info = check_celery_status(celery=celery, cache_backend=cache_backend)
    poller_info = check_telegram_poller_status(
        cache_backend=cache_backend,
        now_fn=now_fn,
    )
    rag_info = check_rag_documents_status()

    is_degraded = (
        database != 'ok'
        or ollama != 'ok'
        or celery_info['status'] == 'error'
        or (poller_info['active_bots'] > 0 and poller_info['status'] != 'ok')
    )

    return {
        'status': 'degraded' if is_degraded else 'ok',
        'database': database,
        'cache': cache_state,
        'ollama': ollama,
        'celery': celery_info,
        'telegram_poller': poller_info,
        'rag': rag_info,
    }


def render_prometheus_metrics(
    *,
    service_cls=OllamaService,
    db_connection=connection,
    cache_backend=cache,
    celery=None,
    now_fn=time.time,
) -> str:
    """Згенерувати метрики у текстовому форматі Prometheus exposition."""
    details = collect_system_health_details(
        service_cls=service_cls,
        db_connection=db_connection,
        cache_backend=cache_backend,
        celery=celery,
        now_fn=now_fn,
    )

    chat_stats = {'web': 0, 'telegram': 0, 'widget': 0, 'handoffs': 0}
    try:
        agg = WorkspaceChatLog.objects.aggregate(
            web=Count('id', filter=Q(channel=WorkspaceChatLog.Channel.WEB)),
            telegram=Count('id', filter=Q(channel=WorkspaceChatLog.Channel.TELEGRAM)),
            widget=Count('id', filter=Q(channel=WorkspaceChatLog.Channel.WIDGET)),
            handoffs=Count('id', filter=Q(needs_handoff=True)),
        )
        chat_stats = {
            'web': agg['web'] or 0,
            'telegram': agg['telegram'] or 0,
            'widget': agg['widget'] or 0,
            'handoffs': agg['handoffs'] or 0,
        }
    except DatabaseError as exc:
        logger.warning('Metrics chat log query failed: %s', exc)

    celery_up = 1 if details['celery']['status'] in ('ok', 'eager') else 0
    poller_up = 1 if details['telegram_poller']['status'] == 'ok' else 0

    lines = [
        '# HELP zrozumiloai_component_up Component health status (1 = up/healthy, 0 = down/degraded).',
        '# TYPE zrozumiloai_component_up gauge',
        f'zrozumiloai_component_up{{component="database"}} {1 if details["database"] == "ok" else 0}',
        f'zrozumiloai_component_up{{component="cache"}} {1 if details["cache"] == "ok" else 0}',
        f'zrozumiloai_component_up{{component="ollama"}} {1 if details["ollama"] == "ok" else 0}',
        f'zrozumiloai_component_up{{component="celery"}} {celery_up}',
        f'zrozumiloai_component_up{{component="telegram_poller"}} {poller_up}',
        '# HELP zrozumiloai_celery_workers Number of active Celery workers responding to ping.',
        '# TYPE zrozumiloai_celery_workers gauge',
        f'zrozumiloai_celery_workers {details["celery"]["workers"]}',
        '# HELP zrozumiloai_telegram_bots_active Number of active configured Telegram bots.',
        '# TYPE zrozumiloai_telegram_bots_active gauge',
        f'zrozumiloai_telegram_bots_active {details["telegram_poller"]["active_bots"]}',
        '# HELP zrozumiloai_telegram_bots_with_errors Number of active Telegram bots reporting errors.',
        '# TYPE zrozumiloai_telegram_bots_with_errors gauge',
        f'zrozumiloai_telegram_bots_with_errors {details["telegram_poller"]["bots_with_errors"]}',
        '# HELP zrozumiloai_rag_documents_total Total RAG documents grouped by status.',
        '# TYPE zrozumiloai_rag_documents_total gauge',
        f'zrozumiloai_rag_documents_total{{status="processing"}} {details["rag"]["processing"]}',
        f'zrozumiloai_rag_documents_total{{status="ready"}} {details["rag"]["ready"]}',
        f'zrozumiloai_rag_documents_total{{status="failed"}} {details["rag"]["failed"]}',
        '# HELP zrozumiloai_chat_logs_total Total recorded chat exchanges grouped by channel.',
        '# TYPE zrozumiloai_chat_logs_total gauge',
        f'zrozumiloai_chat_logs_total{{channel="web"}} {chat_stats["web"]}',
        f'zrozumiloai_chat_logs_total{{channel="telegram"}} {chat_stats["telegram"]}',
        f'zrozumiloai_chat_logs_total{{channel="widget"}} {chat_stats["widget"]}',
        '# HELP zrozumiloai_chat_logs_handoff_total Total chat logs marked for teacher handoff.',
        '# TYPE zrozumiloai_chat_logs_handoff_total gauge',
        f'zrozumiloai_chat_logs_handoff_total {chat_stats["handoffs"]}',
    ]
    return '\n'.join(lines) + '\n'
