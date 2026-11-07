"""Витяг тексту з файлів документів workspace."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.txt', '.md', '.markdown', '.pdf', '.docx', '.html', '.htm'}
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
    elif suffix == '.docx':
        text = _extract_docx(path)
    elif suffix in {'.html', '.htm'}:
        text = _extract_html(path)
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

    reader = None
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
    finally:
        if reader is not None:
            try:
                stream = getattr(reader, 'stream', None)
                if stream is not None:
                    stream.close()
            except Exception as exc:
                logger.debug('Error closing PDF reader stream: %s', exc)


def _extract_docx(path):
    """Витягнути текст із DOCX через python-docx."""
    try:
        import docx
    except ImportError as exc:
        raise ValueError('DOCX не підтримується: встановіть python-docx') from exc

    try:
        doc = docx.Document(str(path))
    except Exception as exc:
        logger.error('DOCX loading failed for %s: %s', path, exc)
        raise ValueError(f'Не вдалося прочитати DOCX: {exc}') from exc

    parts = []
    for p in doc.paragraphs:
        try:
            p_text = p.text.strip()
            if p_text:
                parts.append(p_text)
        except Exception as exc:
            logger.warning('Failed to extract paragraph from %s: %s', path, exc)

    for table in doc.tables:
        try:
            for row in table.rows:
                try:
                    cells = [cell.text.strip() for cell in row.cells]
                    if any(cells):
                        parts.append(' | '.join(cells))
                except Exception as exc:
                    logger.warning('Failed to extract row from table in %s: %s', path, exc)
        except Exception as exc:
            logger.warning('Failed to extract table from %s: %s', path, exc)

    return '\n\n'.join(parts)


def _extract_html(path):
    """Витягнути текст із HTML через BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ValueError('HTML не підтримується: встановіть beautifulsoup4') from exc

    try:
        raw_text = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            raw_text = path.read_text(encoding='cp1251')
        except Exception as exc:
            logger.error('HTML read failed for %s: %s', path, exc)
            raise ValueError(f'Не вдалося прочитати HTML: {exc}') from exc
    except OSError as exc:
        logger.error('Cannot read HTML file %s: %s', path, exc)
        raise ValueError(f'Не вдалося прочитати файл: {exc}') from exc

    try:
        soup = BeautifulSoup(raw_text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
            tag.decompose()
        extracted = soup.get_text(separator='\n')
    except Exception as exc:
        logger.error('HTML parsing failed for %s: %s', path, exc)
        raise ValueError(f'Не вдалося розібрати HTML: {exc}') from exc

    lines = [line.strip() for line in extracted.splitlines()]
    collapsed = []
    prev_empty = False
    for line in lines:
        if line:
            collapsed.append(line)
            prev_empty = False
        elif not prev_empty:
            collapsed.append('')
            prev_empty = True

    return '\n'.join(collapsed).strip()
