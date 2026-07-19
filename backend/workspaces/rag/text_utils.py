"""Утиліти для очищення тексту з Open edX / Meilisearch."""
import re

_HTML_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')


def strip_html(text):
    """Прибрати HTML-теги та нормалізувати пробіли."""
    if not text:
        return ''
    cleaned = _HTML_TAG_RE.sub(' ', str(text))
    return _WS_RE.sub(' ', cleaned).strip()


def truncate_text(text, max_chars):
    """Обрізати текст з позначкою, якщо він занадто довгий."""
    if not text or max_chars <= 0:
        return ''
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + '…'
