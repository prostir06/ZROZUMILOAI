"""Форматування RAG-контексту та sources для API."""
from django.conf import settings

from .text_utils import strip_html, truncate_text


def chunk_relevance_score(chunk):
    """Оригінальний score для порогів (не RRF)."""
    raw = chunk.get('relevance_score', chunk.get('score', 0))
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def format_rag_context(chunks):
    """Сформувати блок контексту для system prompt."""
    if not chunks:
        return ''

    min_score = getattr(settings, 'RAG_MIN_SCORE', 0.25)
    best = max(chunk_relevance_score(c) for c in chunks)

    lines = [
        'Використовуй наведені нижче фрагменти документів workspace для відповіді. '
        'Якщо відповіді немає в контексті — чесно скажи про це.',
    ]
    if best < min_score:
        lines.append(
            'Увага: релевантність знайденого контексту низька. '
            'Якщо не впевнений — запропонуй звернутися до підтримки.',
        )
    lines.extend(['', '--- Контекст з документів ---'])

    for index, chunk in enumerate(chunks, start=1):
        source = chunk['document_name']
        content = truncate_text(
            strip_html(chunk.get('content', '')),
            settings.MEILISEARCH_MAX_CHUNK_CHARS,
        )
        lines.append(f'[{index}] ({source}):')
        lines.append(content)
        lines.append('')

    lines.append('--- Кінець контексту ---')
    return '\n'.join(lines)


def sources_from_chunks(chunks):
    """Компактний список джерел для API/UI citations."""
    sources = []
    seen = set()
    for chunk in chunks or []:
        name = chunk.get('document_name') or 'Документ'
        key = (name, (chunk.get('content') or '')[:80])
        if key in seen:
            continue
        seen.add(key)
        try:
            score = round(chunk_relevance_score(chunk), 4)
        except (TypeError, ValueError):
            score = 0.0
        sources.append({
            'document_name': name,
            'score': score,
            'excerpt': truncate_text(
                strip_html(chunk.get('content', '')),
                180,
            ),
        })
    return sources
