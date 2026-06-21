"""Розбиття тексту на фрагменти для RAG."""
import re


def split_text_into_chunks(text, chunk_size=800, chunk_overlap=100):
    """
    Розбити текст на перекривні фрагменти.

    Намагається різати по абзацах або реченнях, якщо можливо.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks = []
    start = 0
    text_len = len(cleaned)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            split_at = _find_split_point(cleaned, start, end)
            if split_at > start:
                end = split_at

        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= text_len:
            break

        start = max(end - chunk_overlap, start + 1)

    return chunks


def _find_split_point(text, start, end):
    """Знайти природну точку розрізу в межах [start, end)."""
    window = text[start:end]
    for pattern in (r'\n\n', r'\n', r'[.!?]\s+'):
        matches = list(re.finditer(pattern, window))
        if matches:
            return start + matches[-1].end()
    return end
