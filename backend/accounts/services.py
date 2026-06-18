"""Account services."""
from .models import ApiKey


def ensure_api_key(user):
    """Create API key for user if missing; return raw key or None."""
    if hasattr(user, 'api_key'):
        return None
    raw_key, _ = ApiKey.create_for_user(user)
    return raw_key


def create_api_key(user):
    """Always create a new API key for user."""
    raw_key, _ = ApiKey.create_for_user(user)
    return raw_key
