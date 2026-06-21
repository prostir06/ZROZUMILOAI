"""Rate limiting for auth endpoints."""
from rest_framework.throttling import ScopedRateThrottle


class ClientIPScopedRateThrottle(ScopedRateThrottle):
    """Scoped rate limit keyed by client IP (supports reverse proxy headers)."""

    def get_ident(self, request):
        if request.user and request.user.is_authenticated:
            return str(request.user.pk)

        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()

        real_ip = request.META.get('HTTP_X_REAL_IP')
        if real_ip:
            return real_ip.strip()

        return super().get_ident(request)
