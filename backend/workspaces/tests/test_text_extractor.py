"""Unit-тести для екстракції тексту з документів (txt, md, pdf, docx, html)."""
import tempfile
from pathlib import Path

import docx
from django.test import SimpleTestCase

from workspaces.rag.text_extractor import ALLOWED_EXTENSIONS, extract_text_from_file


class TextExtractorExpansionTests(SimpleTestCase):
    def test_allowed_extensions_includes_new_formats(self):
        expected_extensions = {'.txt', '.md', '.markdown', '.pdf', '.docx', '.html', '.htm'}
        self.assertTrue(expected_extensions.issubset(ALLOWED_EXTENSIONS))

    def test_extract_docx_with_paragraphs_and_tables(self):
        doc = docx.Document()
        doc.add_heading('Документ про проєкт', level=1)
        doc.add_paragraph('Це перший параграф з описом системи.')
        doc.add_paragraph('Другий параграф із додатковою інформацією.')

        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = 'Критерій'
        table.cell(0, 1).text = 'Значення'
        table.cell(1, 0).text = 'Швидкість'
        table.cell(1, 1).text = 'Висока'

        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            doc.save(str(tmp_path))
            extracted = extract_text_from_file(tmp_path)

            self.assertIn('Документ про проєкт', extracted)
            self.assertIn('Це перший параграф з описом системи.', extracted)
            self.assertIn('Другий параграф із додатковою інформацією.', extracted)
            self.assertIn('Критерій', extracted)
            self.assertIn('Значення', extracted)
            self.assertIn('Швидкість', extracted)
            self.assertIn('Висока', extracted)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_extract_html_strips_scripts_styles_and_navigation(self):
        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Тестова сторінка</title>
    <style>body { font-size: 14px; color: #333; }</style>
    <script>console.log("secret script execution");</script>
</head>
<body>
    <header>
        <nav><a href="/home">Головна навігація</a></nav>
    </header>
    <main>
        <h1>Інформаційна стаття</h1>
        <p>Основний зміст публікації.</p>
        <ul>
            <li>Перший пункт</li>
            <li>Другий пункт</li>
        </ul>
    </main>
    <noscript>Потрібен JavaScript</noscript>
    <footer>Нижній колонтитул &copy; 2026</footer>
</body>
</html>"""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.html', delete=False, encoding='utf-8'
        ) as tmp:
            tmp.write(html_content)
            tmp_path = Path(tmp.name)

        try:
            extracted = extract_text_from_file(tmp_path)

            self.assertIn('Інформаційна стаття', extracted)
            self.assertIn('Основний зміст публікації.', extracted)
            self.assertIn('Перший пункт', extracted)
            self.assertIn('Другий пункт', extracted)

            self.assertNotIn('console.log', extracted)
            self.assertNotIn('font-size', extracted)
            self.assertNotIn('Головна навігація', extracted)
            self.assertNotIn('Потрібен JavaScript', extracted)
            self.assertNotIn('Нижній колонтитул', extracted)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_extract_htm_format(self):
        html_content = "<html><body><h2>Короткий огляд</h2><p>Текст у файлі htm.</p></body></html>"
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.htm', delete=False, encoding='utf-8'
        ) as tmp:
            tmp.write(html_content)
            tmp_path = Path(tmp.name)

        try:
            extracted = extract_text_from_file(tmp_path)
            self.assertIn('Короткий огляд', extracted)
            self.assertIn('Текст у файлі htm.', extracted)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_extract_html_cp1251_fallback(self):
        html_cp1251 = "<html><body><p>Український текст у кодуванні Windows-1251</p></body></html>"
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.html', delete=False) as tmp:
            tmp.write(html_cp1251.encode('cp1251'))
            tmp_path = Path(tmp.name)

        try:
            extracted = extract_text_from_file(tmp_path)
            self.assertIn('Український текст у кодуванні Windows-1251', extracted)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_extract_corrupted_docx_raises_value_error(self):
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp.write(b"NOT A REAL DOCX ARCHIVE DATA")
            tmp_path = Path(tmp.name)

        try:
            with self.assertRaises(ValueError):
                extract_text_from_file(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_extract_empty_docx_raises_value_error(self):
        doc = docx.Document()
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            doc.save(str(tmp_path))
            with self.assertRaises(ValueError) as ctx:
                extract_text_from_file(tmp_path)
            self.assertIn('не містить тексту', str(ctx.exception))
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_extract_empty_html_raises_value_error(self):
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.html', delete=False, encoding='utf-8'
        ) as tmp:
            tmp.write("<html><head><script>alert(1);</script></head><body></body></html>")
            tmp_path = Path(tmp.name)

        try:
            with self.assertRaises(ValueError) as ctx:
                extract_text_from_file(tmp_path)
            self.assertIn('не містить тексту', str(ctx.exception))
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_extract_nonexistent_file_raises_value_error(self):
        nonexistent = Path(tempfile.gettempdir()) / 'does_not_exist_12345.docx'
        with self.assertRaises(ValueError):
            extract_text_from_file(nonexistent)
