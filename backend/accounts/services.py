"""Account services."""
import logging

from django.db import IntegrityError

from .models import ApiKey

logger = logging.getLogger(__name__)


def ensure_api_key(user):
    """Create API key for user if missing; return raw key or None."""
    if ApiKey.objects.filter(user=user).exists():
        return None
    try:
        raw_key, _ = ApiKey.create_for_user(user)
        return raw_key
    except IntegrityError as exc:
        # Паралельний create виграв гонку — ключ уже є.
        logger.debug('Concurrent API key creation for user %s: %s', getattr(user, 'pk', None), exc)
        return None


def create_api_key(user):
    """Always create a new API key for user."""
    raw_key, _ = ApiKey.create_for_user(user)
    return raw_key
