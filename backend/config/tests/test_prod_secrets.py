"""
Unit-тести маркерів insecure DJANGO_SECRET_KEY (prod fail-fast).
"""
from django.test import SimpleTestCase


class ProdSecretsFailFastTests(SimpleTestCase):
    """Маркери дефолтних секретів, які блокують DEBUG=False."""

    def test_insecure_secret_markers_detected(self):
        """Дефолтні insecure-ключі розпізнаються маркерами з settings."""
        from config import settings as app_settings

        markers = app_settings._INSECURE_SECRET_MARKERS
        sample = 'django-insecure-change-me-in-production'
        self.assertTrue(any(marker in sample for marker in markers))
        self.assertTrue(
            any(marker in 'change-me-in-production' for marker in markers),
        )
        self.assertTrue(
            any(
                marker in 'zrozumiloai-docker-dev-secret-change-me'
                for marker in markers
            ),
        )
