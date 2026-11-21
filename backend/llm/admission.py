"""Один одночасний чат на інстанс Ollama."""
import logging
import math
import time
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)

ADMISSION_KEY = 'ollama:admission'
OLLAMA_BUSY_MESSAGE = 'Модель зайнята. Спробуйте ще раз за хвилину.'
OLLAMA_BUSY_CODE = 'ollama_busy'
RETRY_AFTER_SECONDS = '60'
# Атомарне звільнення: видаляємо ключ лише за збігу токена, щоб не зняти чужий слот після TTL.
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


class OllamaBusy(Exception):
    """Слот генерації вже зайнятий."""


class AdmissionUnavailable(Exception):
    """Інфраструктура допуску недоступна (Redis не відповідає при заданому REDIS_URL)."""


def _safe_non_negative_float(value, default=0.0):
    """Перетворити значення у невід'ємний скінченний float або повернути default."""
    if value is None or isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed) or parsed < 0.0:
        return default
    return parsed


def _safe_positive_int(value, default=180):
    """Перетворити значення у ціле >= 1 (для Redis EX), інакше default."""
    if value is None or isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, parsed)


def _slot_keys(limit=1):
    """Повернути список Redis-ключів слотів допуску для заданого ліміту."""
    count = max(1, int(limit or 1))
    if count == 1:
        return [ADMISSION_KEY]
    return [ADMISSION_KEY, *(f'{ADMISSION_KEY}:{idx}' for idx in range(2, count + 1))]


def acquire_ollama_slot(client=None, wait_seconds=None, poll_interval=0.05):
    """Повернути токен власника, None для fail-open, або кинути OllamaBusy / AdmissionUnavailable."""
    is_redis_configured = bool((getattr(settings, 'REDIS_URL', '') or '').strip())
    if client is None and not is_redis_configured:
        # Локальна розробка без Redis: дозволяємо запит напряму (fail-open).
        return None
    raw_wait = (
        getattr(settings, 'OLLAMA_CHAT_SLOT_WAIT_SECONDS', 0.0)
        if wait_seconds is None
        else wait_seconds
    )
    wait_seconds = _safe_non_negative_float(raw_wait, default=0.0)
    poll_interval = max(0.005, _safe_non_negative_float(poll_interval, default=0.05))
    deadline = time.monotonic() + wait_seconds
    redis_client = client
    token = uuid.uuid4().hex
    ttl = _safe_positive_int(getattr(settings, 'OLLAMA_ADMISSION_TTL_SECONDS', 180), default=180)
    limit = _safe_positive_int(getattr(settings, 'OLLAMA_ADMISSION_LIMIT', 1), default=1)
    slot_keys = _slot_keys(limit)

    while True:
        try:
            if redis_client is None:
                from django_redis import get_redis_connection
                redis_client = get_redis_connection('default')
            for slot_key in slot_keys:
                if redis_client.set(slot_key, token, nx=True, ex=ttl):
                    return token if slot_key == ADMISSION_KEY else f'{slot_key}|{token}'
        except Exception as exc:
            if is_redis_configured:
                # Із заданим REDIS_URL працюємо fail-closed, щоб не перевантажити Ollama без черги.
                logger.error(
                    'Ollama admission unavailable, failing closed: %s',
                    exc,
                    exc_info=True,
                )
                raise AdmissionUnavailable(str(exc)) from exc
            logger.warning(
                'Ollama admission unavailable without REDIS_URL, failing open: %s',
                exc,
                exc_info=True,
            )
            return None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OllamaBusy()
        time.sleep(min(poll_interval, remaining))


def release_ollama_slot(token, client=None):
    """Зняти слот лише своїм токеном."""
    if not token:
        return
    if '|' in str(token):
        slot_key, raw_token = str(token).split('|', 1)
    else:
        slot_key, raw_token = ADMISSION_KEY, token
    try:
        redis_client = client
        if redis_client is None:
            from django_redis import get_redis_connection
            redis_client = get_redis_connection('default')
        redis_client.eval(_RELEASE_LUA, 1, slot_key, raw_token)
    except Exception as exc:
        # Ключ зникне по TTL, навіть якщо eval не пройшов.
        logger.warning(
            'Ollama admission release failed: %s',
            exc,
            exc_info=True,
        )
