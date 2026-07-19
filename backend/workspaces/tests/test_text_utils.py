"""Unit-тести text_utils для Meilisearch."""
from django.test import SimpleTestCase

from workspaces.rag.text_utils import strip_html, truncate_text


class TextUtilsTests(SimpleTestCase):
    def test_strip_html(self):
        self.assertEqual(
            strip_html('<p>Текст <b>жирний</b></p>'),
            'Текст жирний',
        )

    def test_truncate_text(self):
        self.assertEqual(truncate_text('abcdef', 4), 'abc…')
