"""Account services."""
from django.db import IntegrityError

from .models import ApiKey


def ensure_api_key(user):
    """Create API key for user if missing; return raw key or None."""
    if ApiKey.objects.filter(user=user).exists():
        return None
    try:
        raw_key, _ = ApiKey.create_for_user(user)
        return raw_key
    except IntegrityError:
        # Паралельний create виграв гонку — ключ уже є.
        return None


def create_api_key(user):
    """Always create a new API key for user."""
    raw_key, _ = ApiKey.create_for_user(user)
    return raw_key
