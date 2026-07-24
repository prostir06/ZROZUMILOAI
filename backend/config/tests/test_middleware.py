"""
Unit-тести RequestIdMiddleware та RequestIdFilter (PEP 8).

Перевіряють генерацію / прокидання X-Request-ID і поле request_id у логах.
"""
import logging

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from config.middleware import (
    RequestIdFilter,
    RequestIdMiddleware,
    get_request_id,
)


class RequestIdMiddlewareTests(SimpleTestCase):
    """Тести HTTP middleware для кореляції запитів."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_generates_request_id_when_header_missing(self):
        """Без X-Request-ID middleware генерує UUID і віддає його у відповіді."""
        def view(request):
            self.assertTrue(getattr(request, 'request_id', ''))
            return HttpResponse('ok')

        middleware = RequestIdMiddleware(view)
        request = self.factory.get('/api/health/')
        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn('X-Request-ID', response)
        self.assertTrue(response['X-Request-ID'])

    def test_reuses_incoming_request_id(self):
        """Вхідний X-Request-ID прокидається у відповідь без змін."""
        def view(request):
            return HttpResponse('ok')

        middleware = RequestIdMiddleware(view)
        request = self.factory.get(
            '/api/health/',
            HTTP_X_REQUEST_ID='client-corr-123',
        )
        response = middleware(request)

        self.assertEqual(response['X-Request-ID'], 'client-corr-123')
        self.assertEqual(request.request_id, 'client-corr-123')

    def test_clears_context_after_request(self):
        """Наступний запит починається з чистого контексту, потім новий id."""
        def view(request):
            return HttpResponse('ok')

        middleware = RequestIdMiddleware(view)
        request = self.factory.get('/api/health/', HTTP_X_REQUEST_ID='tmp')
        middleware(request)
        # Після запиту id лишається для post-middleware logging Django.
        self.assertEqual(get_request_id(), 'tmp')

        request2 = self.factory.get('/api/health/')
        middleware(request2)
        self.assertNotEqual(get_request_id(), 'tmp')
        self.assertNotEqual(get_request_id(), '-')

    def test_preserves_context_on_view_exception(self):
        """При винятку request_id зберігається для логування BaseHandler."""
        def view(request):
            raise RuntimeError('boom')

        middleware = RequestIdMiddleware(view)
        request = self.factory.get('/api/health/', HTTP_X_REQUEST_ID='err-id')
        with self.assertRaises(RuntimeError):
            middleware(request)
        self.assertEqual(get_request_id(), 'err-id')


class RequestIdFilterTests(SimpleTestCase):
    """Тести logging.Filter для request_id."""

    def test_filter_adds_request_id_attribute(self):
        """Filter завжди додає request_id у LogRecord."""
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg='hello',
            args=(),
            exc_info=None,
        )
        filt = RequestIdFilter()
        self.assertTrue(filt.filter(record))
        self.assertTrue(hasattr(record, 'request_id'))


class RequestIdIntegrationTests(TestCase):
    """Інтеграція middleware у Django test client."""

    def test_api_response_includes_request_id_header(self):
        """Будь-який HTTP-відповідь містить X-Request-ID."""
        response = self.client.get('/api/auth/config/')
        self.assertIn('X-Request-ID', response)
        self.assertTrue(response['X-Request-ID'])
