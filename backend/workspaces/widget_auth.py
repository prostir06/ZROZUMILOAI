"""Authentication and permissions for widget tokens."""
from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission

from .models import WidgetToken, hash_widget_token


class WidgetTokenAuthentication(BaseAuthentication):
    """Authenticate embed requests using Authorization: Widget-Token <token>."""

    keyword = 'Widget-Token'

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith(f'{self.keyword} '):
            return None

        key = auth_header[len(self.keyword) + 1:].strip()
        if not key:
            return None

        try:
            widget_token = WidgetToken.objects.select_related('workspace').get(
                token_hash=hash_widget_token(key),
            )
        except WidgetToken.DoesNotExist as exc:
            raise AuthenticationFailed('Невірний widget token') from exc

        if not widget_token.is_active:
            raise AuthenticationFailed('Widget token деактивовано')

        return AnonymousUser(), widget_token


class WidgetTokenPermission(BasePermission):
    """Allow access only with a valid widget token."""

    def has_permission(self, request, view):
        return (
            isinstance(getattr(request, 'auth', None), WidgetToken)
            and request.auth.is_active
        )
