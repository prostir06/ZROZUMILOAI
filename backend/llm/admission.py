"""Один одночасний чат на інстанс Ollama."""
import logging
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


def acquire_ollama_slot(client=None):
    """Повернути токен власника, None для fail-open, або кинути OllamaBusy."""
    if client is None and not (getattr(settings, 'REDIS_URL', '') or '').strip():
        return None
    redis_client = client
    try:
        if redis_client is None:
            from django_redis import get_redis_connection
            redis_client = get_redis_connection('default')
        token = uuid.uuid4().hex
        ttl = int(getattr(settings, 'OLLAMA_ADMISSION_TTL_SECONDS', 180))
        written = redis_client.set(ADMISSION_KEY, token, nx=True, ex=ttl)
    except Exception as exc:
        logger.warning('Ollama admission unavailable, failing open: %s', exc)
        return None
    if not written:
        raise OllamaBusy()
    return token


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
        logger.warning('Ollama admission release failed: %s', exc)
