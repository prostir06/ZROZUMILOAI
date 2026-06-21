"""Сервіс індексації та пошуку документів workspace (RAG)."""
import logging
import re
from pathlib import Path

from django.conf import settings
from django.db import transaction

from ollama_proxy.services import OllamaService

from ..models import DocumentChunk, WorkspaceDocument
from .chunker import split_text_into_chunks
from .python_search import search_with_python
from .text_extractor import extract_text_from_file
from .vector_search import search_with_pgvector, uses_pgvector

logger = logging.getLogger(__name__)


def ingest_workspace_document(document):
    """
    Проіндексувати документ: витяг тексту, chunking, embeddings.

    Оновлює status документа на ready або failed.
    """
    document.status = WorkspaceDocument.Status.PROCESSING
    document.error_message = ''
    document.save(update_fields=['status', 'error_message', 'updated_at'])

    try:
        if not document.file or not document.file.path:
            raise ValueError('Файл документа не знайдено')
        text = extract_text_from_file(document.file.path)
        chunks = split_text_into_chunks(
            text,
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        )

        if not chunks:
            raise ValueError('Не вдалося створити фрагменти тексту')

        ollama = OllamaService()
        embed_model = settings.RAG_EMBED_MODEL

        with transaction.atomic():
            DocumentChunk.objects.filter(document=document).delete()
            for index, chunk_text in enumerate(chunks):
                embedding = ollama.embed(embed_model, chunk_text)
                DocumentChunk.objects.create(
                    document=document,
                    workspace=document.workspace,
                    chunk_index=index,
                    content=chunk_text,
                    embedding=embedding,
                )

            document.status = WorkspaceDocument.Status.READY
            document.chunk_count = len(chunks)
            document.error_message = ''
            document.save(update_fields=[
                'status', 'chunk_count', 'error_message', 'updated_at',
            ])

    except Exception as exc:
        logger.exception('Document ingest failed for %s', document.pk)
        document.status = WorkspaceDocument.Status.FAILED
        document.error_message = str(exc)[:2000]
        document.chunk_count = 0
        document.save(update_fields=[
            'status', 'error_message', 'chunk_count', 'updated_at',
        ])
        DocumentChunk.objects.filter(document=document).delete()
        raise


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
        lines.append(f'[{index}] ({source}):')
        lines.append(chunk['content'])
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
