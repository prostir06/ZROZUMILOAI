"""Unit-тести RAG chunker та text extractor."""
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from workspaces.rag.chunker import split_text_into_chunks
from workspaces.rag.text_extractor import extract_text_from_file


class ChunkerTests(SimpleTestCase):
    def test_empty_text(self):
        self.assertEqual(split_text_into_chunks(''), [])
        self.assertEqual(split_text_into_chunks('   '), [])

    def test_short_text_single_chunk(self):
        text = 'Короткий текст.'
        self.assertEqual(split_text_into_chunks(text, chunk_size=100), [text])

    def test_long_text_multiple_chunks(self):
        text = 'А' * 500 + '\n\n' + 'Б' * 500
        chunks = split_text_into_chunks(text, chunk_size=300, chunk_overlap=50)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 300 for c in chunks))


class TextExtractorTests(SimpleTestCase):
    def test_extract_txt_file(self):
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.txt',
            delete=False,
            encoding='utf-8',
        ) as tmp:
            tmp.write('Тестовий текст')
            path = tmp.name

        try:
            text = extract_text_from_file(path)
            self.assertEqual(text, 'Тестовий текст')
        finally:
            Path(path).unlink(missing_ok=True)

    def test_rejects_unknown_extension(self):
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp:
            path = tmp.name
        try:
            with self.assertRaises(ValueError):
                extract_text_from_file(path)
        finally:
            Path(path).unlink(missing_ok=True)
