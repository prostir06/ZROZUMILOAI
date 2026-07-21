"""Rate limiting for auth and chat endpoints."""
from django.conf import settings
from rest_framework.throttling import ScopedRateThrottle


class ClientIPScopedRateThrottle(ScopedRateThrottle):
    """
    Scoped rate limit keyed by user pk або client IP.

    X-Forwarded-For / X-Real-IP враховуються лише коли TRUST_X_FORWARDED_FOR=True
    (типово за reverse-proxy у продакшені).
    """

    def get_ident(self, request):
        if request.user and request.user.is_authenticated:
            return str(request.user.pk)

        if getattr(settings, 'TRUST_X_FORWARDED_FOR', False):
            forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
            if forwarded:
                return forwarded.split(',')[0].strip()

            real_ip = request.META.get('HTTP_X_REAL_IP')
            if real_ip:
                return real_ip.strip()

        return super().get_ident(request)
