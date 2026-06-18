"""Account models."""
import hashlib
import secrets

from django.conf import settings
from django.db import models


def generate_api_key_value():
    """Generate a new API key string."""
    return f'zai_{secrets.token_urlsafe(32)}'


def hash_api_key(key):
    """Return SHA-256 hash of the API key."""
    return hashlib.sha256(key.encode()).hexdigest()


class ApiKey(models.Model):
    """API key for programmatic access."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_key',
    )
    key_prefix = models.CharField(max_length=12)
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'API ключ'
        verbose_name_plural = 'API ключі'

    def __str__(self):
        return f'{self.key_prefix}... ({self.user.username})'

    @classmethod
    def create_for_user(cls, user):
        """Create a new API key and return the raw key (shown once)."""
        raw_key = generate_api_key_value()
        instance = cls.objects.create(
            user=user,
            key_prefix=raw_key[:12],
            key_hash=hash_api_key(raw_key),
        )
        return raw_key, instance
