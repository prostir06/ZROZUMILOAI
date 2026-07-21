"""Сервіс індексації та пошуку документів workspace (RAG)."""
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Sum

from ollama_proxy.services import OllamaService

from ..models import DocumentChunk, Workspace, WorkspaceDocument
from .chunker import split_text_into_chunks
from .python_search import search_with_python
from .text_extractor import extract_text_from_file
from .text_utils import strip_html, truncate_text
from .vector_search import search_with_pgvector, uses_pgvector

logger = logging.getLogger(__name__)

# Reciprocal Rank Fusion константа (стандартне k=60).
RRF_K = 60


def ingest_workspace_document(document):
    """
    Проіндексувати документ: витяг тексту, chunking, embeddings.

    Embeddings поза atomic (паралельний пул); bulk_create у короткій транзакції.
    """
    document.status = WorkspaceDocument.Status.PROCESSING
    document.error_message = ''
    document.save(update_fields=['status', 'error_message', 'updated_at'])

    try:
        if not document.file or not document.file.path:
            raise ValueError('Файл документа не знайдено')

        text = extract_text_from_file(document.file.path)
        chunk_texts = split_text_into_chunks(
            text,
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        )
        if not chunk_texts:
            raise ValueError('Не вдалося створити фрагменти тексту')

        ollama = OllamaService()
        embed_model = settings.RAG_EMBED_MODEL
        embeddings = _embed_texts_parallel(ollama, embed_model, chunk_texts)

        prepared_chunks = [
            DocumentChunk(
                document=document,
                workspace=document.workspace,
                chunk_index=index,
                content=chunk_text,
                embedding=embedding,
            )
            for index, (chunk_text, embedding) in enumerate(
                zip(chunk_texts, embeddings),
            )
        ]

        with transaction.atomic():
            DocumentChunk.objects.filter(document=document).delete()
            DocumentChunk.objects.bulk_create(prepared_chunks)
            document.status = WorkspaceDocument.Status.READY
            document.chunk_count = len(prepared_chunks)
            document.error_message = ''
            document.save(update_fields=[
                'status', 'chunk_count', 'error_message', 'updated_at',
            ])

    except Exception as exc:
        logger.exception('Document ingest failed for %s', document.pk)
        try:
            document.status = WorkspaceDocument.Status.FAILED
            document.error_message = str(exc)[:2000]
            document.chunk_count = 0
            document.save(update_fields=[
                'status', 'error_message', 'chunk_count', 'updated_at',
            ])
            DocumentChunk.objects.filter(document=document).delete()
        except Exception as cleanup_exc:
            logger.error(
                'Failed to mark document %s as failed: %s',
                document.pk,
                cleanup_exc,
            )
        raise


def _embed_texts_parallel(ollama, embed_model, texts):
    """Паралельні embeddings з обмеженою конкуренцією."""
    workers = max(1, min(
        getattr(settings, 'RAG_EMBED_CONCURRENCY', 4),
        len(texts),
    ))
    results = [None] * len(texts)

    def _one(index_text):
        index, text = index_text
        return index, ollama.embed(embed_model, text)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(_one, (index, text))
            for index, text in enumerate(texts)
        ]
        for future in as_completed(futures):
            index, embedding = future.result()
            results[index] = embedding

    return results


def reciprocal_rank_fusion(result_lists, top_k, k=RRF_K):
    """
    Об'єднати кілька ранжованих списків через Reciprocal Rank Fusion.

    Кожен елемент — dict з content/score/document_name.
    Ключ дедуплікації: (document_name, content[:120]) — щоб один фрагмент
    з internal і Meili не дублювався, навіть якщо сирі score на різних шкалах.
    """
    scores = {}
    payloads = {}

    for results in result_lists:
        for rank, item in enumerate(results or [], start=1):
            key = (
                item.get('document_name', ''),
                (item.get('content') or '')[:120],
            )
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in payloads:
                payloads[key] = dict(item)

    merged = []
    for key, rrf_score in scores.items():
        entry = payloads[key]
        entry = dict(entry)
        entry['score'] = rrf_score
        merged.append(entry)

    merged.sort(key=lambda item: item.get('score', 0), reverse=True)
    return merged[:top_k]


def search_workspace_context(workspace, query, top_k=None, course_id=None):
    """
    Зібрати контекст з локального RAG та/або Meilisearch Open edX.

    Hybrid: RRF замість сирого змішування різних шкал score.
    """
    if not workspace or not query or not query.strip():
        return []

    top_k = top_k or settings.RAG_TOP_K
    source = workspace.search_source or Workspace.SearchSource.INTERNAL
    use_internal = source in (
        Workspace.SearchSource.INTERNAL,
        Workspace.SearchSource.HYBRID,
    )
    use_meili = source in (
        Workspace.SearchSource.MEILISEARCH,
        Workspace.SearchSource.HYBRID,
    )

    if use_internal and use_meili:
        internal, meili = _search_hybrid_lists(workspace, query, top_k, course_id)
        return reciprocal_rank_fusion([internal, meili], top_k=top_k)

    chunks = []
    if use_internal:
        chunks.extend(search_workspace_documents(workspace, query, top_k=top_k))
    if use_meili:
        from .meilisearch_search import search_openedx_meilisearch

        chunks.extend(
            search_openedx_meilisearch(
                workspace,
                query,
                top_k=top_k,
                course_id=course_id,
            ),
        )

    if not chunks:
        return []

    chunks.sort(key=lambda item: item.get('score', 0), reverse=True)
    return chunks[:top_k]


def _search_hybrid_lists(workspace, query, top_k, course_id):
    """Паралельно отримати списки internal + Meili (для RRF)."""
    from .meilisearch_search import search_openedx_meilisearch

    internal = []
    meili = []

    def _internal():
        return search_workspace_documents(workspace, query, top_k=top_k)

    def _meili():
        return search_openedx_meilisearch(
            workspace,
            query,
            top_k=top_k,
            course_id=course_id,
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_int = executor.submit(_internal)
            fut_meili = executor.submit(_meili)
            try:
                internal = fut_int.result() or []
            except Exception as exc:
                logger.error('Hybrid internal search failed: %s', exc)
            try:
                meili = fut_meili.result() or []
            except Exception as exc:
                logger.error('Hybrid meilisearch failed: %s', exc)
    except Exception as exc:
        logger.error('Hybrid parallel search failed: %s', exc)
        try:
            internal = search_workspace_documents(workspace, query, top_k=top_k)
        except Exception:
            internal = []

    return internal, meili


def search_workspace_documents(workspace, query, top_k=None):
    """Знайти найрелевантніші фрагменти документів workspace."""
    if not settings.RAG_ENABLED or not workspace or not query or not query.strip():
        return []

    top_k = top_k or settings.RAG_TOP_K

    try:
        ollama = OllamaService()
        query_vector = ollama.embed(settings.RAG_EMBED_MODEL, query.strip())
    except Exception as exc:
        logger.error('RAG query embedding failed: %s', exc)
        return []

    try:
        if uses_pgvector():
            return search_with_pgvector(workspace, query_vector, top_k)
        return search_with_python(workspace, query_vector, top_k)
    except Exception as exc:
        logger.error('RAG search failed: %s', exc)
        return []


def format_rag_context(chunks):
    """Сформувати блок контексту для system prompt."""
    if not chunks:
        return ''

    min_score = getattr(settings, 'RAG_MIN_SCORE', 0.25)
    best = max((c.get('score') or 0) for c in chunks)

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
            score = round(float(chunk.get('score') or 0), 4)
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


def workspace_rag_stats(workspace):
    """Агрегована статистика RAG для адмінки."""
    docs = workspace.documents.all()
    by_status = {
        row['status']: row['count']
        for row in docs.values('status').annotate(count=Count('id'))
    }
    chunk_total = docs.aggregate(total=Sum('chunk_count'))['total'] or 0
    return {
        'documents_total': docs.count(),
        'documents_ready': by_status.get(WorkspaceDocument.Status.READY, 0),
        'documents_processing': by_status.get(
            WorkspaceDocument.Status.PROCESSING, 0,
        ),
        'documents_failed': by_status.get(WorkspaceDocument.Status.FAILED, 0),
        'chunks_total': chunk_total,
    }


def extract_last_user_message(messages):
    """Отримати текст останнього user-повідомлення з історії чату."""
    if not isinstance(messages, list):
        return None

    for message in reversed(messages):
        if (
            isinstance(message, dict)
            and message.get('role') == 'user'
            and isinstance(message.get('content'), str)
        ):
            text = message['content'].strip()
            if text:
                return text
    return None


def sanitize_filename(filename):
    """Безпечне ім'я файлу без шляхів."""
    name = Path(filename).name if filename else 'document'
    name = re.sub(r'[^\w.\- ]', '_', name, flags=re.UNICODE)
    return name[:200] or 'document'
