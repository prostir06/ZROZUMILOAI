"""Сервіс індексації та пошуку документів workspace (RAG)."""
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from django.conf import settings
from django.db import transaction

from ollama_proxy.services import OllamaService

from ..models import DocumentChunk, Workspace, WorkspaceDocument
from .chunker import split_text_into_chunks
from .python_search import search_with_python
from .text_extractor import extract_text_from_file
from .text_utils import strip_html, truncate_text
from .vector_search import search_with_pgvector, uses_pgvector

logger = logging.getLogger(__name__)


def ingest_workspace_document(document):
    """
    Проіндексувати документ: витяг тексту, chunking, embeddings.

    Важливо (P0):
    - HTTP-embeddings виконуються ПОЗА transaction.atomic
    - у БД пишемо короткою транзакцією через bulk_create
    - status: processing → ready | failed
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

        # Embeddings поза atomic — не тримаємо DB-transaction на час Ollama.
        ollama = OllamaService()
        embed_model = settings.RAG_EMBED_MODEL
        prepared_chunks = []
        for index, chunk_text in enumerate(chunk_texts):
            embedding = ollama.embed(embed_model, chunk_text)
            prepared_chunks.append(
                DocumentChunk(
                    document=document,
                    workspace=document.workspace,
                    chunk_index=index,
                    content=chunk_text,
                    embedding=embedding,
                ),
            )

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


def search_workspace_context(workspace, query, top_k=None, course_id=None):
    """
    Зібрати контекст з локального RAG та/або Meilisearch Open edX.

    Залежно від workspace.search_source:
    - internal — лише embeddings у DocumentChunk
    - meilisearch — лише індекси Open edX (Tutor)
    - hybrid — обидва джерела паралельно, сортування за score, top_k

    :return: список dict з content, score, document_name
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

    chunks = []

    # P1: hybrid — паралельний пошук, щоб не складати latency.
    if use_internal and use_meili:
        chunks.extend(
            _search_hybrid_parallel(workspace, query, top_k, course_id),
        )
    elif use_internal:
        chunks.extend(search_workspace_documents(workspace, query, top_k=top_k))
    elif use_meili:
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


def _search_hybrid_parallel(workspace, query, top_k, course_id):
    """Запустити internal + Meilisearch паралельно; ізолювати помилки джерел."""
    from .meilisearch_search import search_openedx_meilisearch

    results = []

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
            futures = {
                executor.submit(_internal): 'internal',
                executor.submit(_meili): 'meilisearch',
            }
            for future in as_completed(futures):
                label = futures[future]
                try:
                    results.extend(future.result() or [])
                except Exception as exc:
                    logger.error('Hybrid search source %s failed: %s', label, exc)
    except Exception as exc:
        logger.error('Hybrid parallel search failed: %s', exc)
        # Fallback: спробувати хоча б internal синхронно.
        try:
            results.extend(search_workspace_documents(workspace, query, top_k=top_k))
        except Exception:
            pass

    return results


def search_workspace_documents(workspace, query, top_k=None):
    """
    Знайти найрелевантніші фрагменти документів workspace.

    :return: список dict з content, score, document_name
    """
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

    lines = [
        'Використовуй наведені нижче фрагменти документів workspace для відповіді. '
        'Якщо відповіді немає в контексті — чесно скажи про це.',
        '',
        '--- Контекст з документів ---',
    ]

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
