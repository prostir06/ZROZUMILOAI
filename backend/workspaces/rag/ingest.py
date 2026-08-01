"""Індексація документів workspace (chunking + embeddings)."""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings
from django.db import transaction

from ollama_proxy.services import OllamaService

from ..models import DocumentChunk, WorkspaceDocument
from .chunker import split_text_into_chunks
from .text_extractor import extract_text_from_file

logger = logging.getLogger(__name__)


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
