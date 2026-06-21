"""Витяг тексту з файлів документів workspace."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.txt', '.md', '.markdown', '.pdf'}
MAX_EXTRACTED_CHARS = 500_000


def extract_text_from_file(file_path):
    """
    Витягнути текст із файлу за розширенням.

    :raises ValueError: непідтримуваний тип або порожній вміст
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f'Непідтримуваний тип файлу. Дозволено: {", ".join(sorted(ALLOWED_EXTENSIONS))}',
        )

    if suffix == '.pdf':
        text = _extract_pdf(path)
    else:
        text = _extract_plain_text(path)

    text = text.strip()
    if not text:
        raise ValueError('Файл не містить тексту для індексації')

    if len(text) > MAX_EXTRACTED_CHARS:
        text = text[:MAX_EXTRACTED_CHARS]

    return text


def _extract_plain_text(path):
    """Прочитати UTF-8 текстовий файл."""
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('Файл має бути в кодуванні UTF-8') from exc
    except OSError as exc:
        logger.error('Cannot read file %s: %s', path, exc)
        raise ValueError(f'Не вдалося прочитати файл: {exc}') from exc


def _extract_pdf(path):
    """Витягнути текст з PDF через pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError('PDF не підтримується: встановіть pypdf') from exc

    try:
        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages:
            page_text = page.extract_text() or ''
            if page_text.strip():
                parts.append(page_text)
        return '\n\n'.join(parts)
    except Exception as exc:
        logger.error('PDF extraction failed: %s', exc)
        raise ValueError(f'Не вдалося прочитати PDF: {exc}') from exc
