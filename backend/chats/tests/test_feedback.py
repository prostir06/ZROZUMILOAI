"""
Unit-тести спільної логіки feedback / handoff (PEP 8).

Перевіряють валідацію payload і збереження без падіння на помилках БД.
"""
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from rest_framework import status

from chats.feedback import apply_feedback_fields, save_log_feedback


class ApplyFeedbackFieldsTests(SimpleTestCase):
    """Валідація тіла feedback без звернення до БД."""

    def setUp(self):
        self.log = MagicMock()
        self.log.feedback = ''
        self.log.needs_handoff = False

    def test_rejects_none_body(self):
        response = apply_feedback_fields(self.log, None)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accepts_up_feedback(self):
        error = apply_feedback_fields(self.log, {'feedback': 'up'})
        self.assertIsNone(error)
        self.assertEqual(self.log.feedback, 'up')

    def test_rejects_invalid_feedback(self):
        response = apply_feedback_fields(self.log, {'feedback': 'maybe'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_parses_needs_handoff_string_true(self):
        error = apply_feedback_fields(self.log, {'needs_handoff': 'true'})
        self.assertIsNone(error)
        self.assertTrue(self.log.needs_handoff)

    def test_parses_needs_handoff_string_false(self):
        self.log.needs_handoff = True
        error = apply_feedback_fields(self.log, {'needs_handoff': 'false'})
        self.assertIsNone(error)
        self.assertFalse(self.log.needs_handoff)

    def test_rejects_invalid_needs_handoff_string(self):
        response = apply_feedback_fields(self.log, {'needs_handoff': 'maybe'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class SaveLogFeedbackTests(SimpleTestCase):
    """Збереження feedback з обробкою помилок БД."""

    def test_save_success_returns_none(self):
        log = MagicMock()
        self.assertIsNone(save_log_feedback(log))
        log.save.assert_called_once_with(
            update_fields=['feedback', 'needs_handoff'],
        )

    def test_database_error_returns_500(self):
        from django.db import DatabaseError

        log = MagicMock()
        log.pk = 7
        log.save.side_effect = DatabaseError('disk full')
        response = save_log_feedback(log)
        self.assertEqual(
            response.status_code,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        self.assertIn('error', response.data)
