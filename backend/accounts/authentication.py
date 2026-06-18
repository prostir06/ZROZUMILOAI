"""Authentication via API key header."""
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import hash_api_key

User = get_user_model()


class ApiKeyAuthentication(BaseAuthentication):
    """Authenticate requests using Authorization: Api-Key <key>."""

    keyword = 'Api-Key'

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith(f'{self.keyword} '):
            return None

        key = auth_header[len(self.keyword) + 1:].strip()
        if not key:
            return None

        from .models import ApiKey

        try:
            api_key = ApiKey.objects.select_related('user').get(
                key_hash=hash_api_key(key),
            )
        except ApiKey.DoesNotExist as exc:
            raise AuthenticationFailed('Невірний API ключ') from exc

        if not api_key.user.is_active:
            raise AuthenticationFailed('Обліковий запис деактивовано')

        return api_key.user, api_key
