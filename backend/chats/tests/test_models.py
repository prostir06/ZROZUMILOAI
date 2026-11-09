"""
Unit-тести моделей додатку chats.
"""
from django.test import SimpleTestCase

from chats.models import WorkspaceChatLog


class WorkspaceChatLogIndexesTests(SimpleTestCase):
    """Перевірка наявності композитних індексів для аналітики та черги handoff."""

    def test_workspace_chat_log_indexes_defined(self):
        index_fields = [list(idx.fields) for idx in WorkspaceChatLog._meta.indexes]
        self.assertIn(['workspace', 'created_at'], index_fields)
        self.assertIn(['workspace', 'needs_handoff'], index_fields)
        self.assertIn(['workspace', 'is_resolved'], index_fields)
