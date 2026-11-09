"""Один одночасний чат на інстанс Ollama."""
import logging
import time
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)

ADMISSION_KEY = 'ollama:admission'
OLLAMA_BUSY_MESSAGE = 'Модель зайнята. Спробуйте ще раз за хвилину.'
OLLAMA_BUSY_CODE = 'ollama_busy'
RETRY_AFTER_SECONDS = '60'
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


class OllamaBusy(Exception):
    """Слот генерації вже зайнятий."""


def acquire_ollama_slot(client=None, wait_seconds=None, poll_interval=0.05):
    """Повернути токен власника, None для fail-open, або кинути OllamaBusy."""
    if client is None and not (getattr(settings, 'REDIS_URL', '') or '').strip():
        return None
    if wait_seconds is None:
        wait_seconds = float(
            getattr(settings, 'OLLAMA_CHAT_SLOT_WAIT_SECONDS', 0.0) or 0.0
        )
    wait_seconds = max(0.0, float(wait_seconds))
    poll_interval = max(0.005, float(poll_interval))
    deadline = time.monotonic() + wait_seconds
    redis_client = client
    token = uuid.uuid4().hex
    ttl = int(getattr(settings, 'OLLAMA_ADMISSION_TTL_SECONDS', 180))

    while True:
        try:
            if redis_client is None:
                from django_redis import get_redis_connection
                redis_client = get_redis_connection('default')
            written = redis_client.set(ADMISSION_KEY, token, nx=True, ex=ttl)
        except Exception as exc:
            # Без Redis чат лишається доступним; слот тоді ніхто не тримає.
            logger.warning(
                'Ollama admission unavailable, failing open: %s',
                exc,
                exc_info=True,
            )
            return None
        if written:
            return token
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise OllamaBusy()
        time.sleep(min(poll_interval, remaining))


def release_ollama_slot(token, client=None):
    """Зняти слот лише своїм токеном."""
    if not token:
        return
    try:
        redis_client = client
        if redis_client is None:
            from django_redis import get_redis_connection
            redis_client = get_redis_connection('default')
        redis_client.eval(_RELEASE_LUA, 1, ADMISSION_KEY, token)
    except Exception as exc:
        # Ключ зникне по TTL, навіть якщо eval не пройшов.
        logger.warning(
            'Ollama admission release failed: %s',
            exc,
            exc_info=True,
        )
