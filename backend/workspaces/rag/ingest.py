"""Індексація документів workspace (chunking + embeddings)."""
import logging
import time

from django.conf import settings
from django.db import transaction

from llm.admission import acquire_ollama_slot, release_ollama_slot
from ollama_proxy.services import OllamaService

from ..models import DocumentChunk, WorkspaceDocument
from .chunker import split_text_into_chunks
from .text_extractor import extract_text_from_file

logger = logging.getLogger(__name__)


def ingest_workspace_document(document):
    """
    Проіндексувати документ: витяг тексту, chunking, батчеві embeddings.

    Embeddings виконуються пачками через слот допуску Ollama поза atomic;
    bulk_create виконується у короткій транзакції.
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
        embeddings = _embed_texts_batched(ollama, embed_model, chunk_texts)

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


def _embed_single_batch(ollama, embed_model, batch):
    """Отримати embeddings для однієї пачки з підтримкою embed_batch або fallback."""
    if hasattr(ollama, 'embed_batch'):
        batch_result = ollama.embed_batch(embed_model, batch)
        if isinstance(batch_result, list) and len(batch_result) == len(batch):
            return batch_result
    return [ollama.embed(embed_model, text) for text in batch]


def _embed_texts_batched(ollama, embed_model, texts):
    """Послідовні батчі embeddings з поступливим захопленням слота Ollama."""
    batch_size = max(1, int(getattr(settings, 'RAG_EMBED_BATCH_SIZE', 16)))
    wait_seconds = float(
        getattr(settings, 'OLLAMA_INGEST_SLOT_WAIT_SECONDS', 60.0)
    )
    pause_seconds = max(
        0.0,
        float(getattr(settings, 'RAG_EMBED_BATCH_PAUSE_SECONDS', 0.05)),
    )
    results = []
    total = len(texts)

    for start in range(0, total, batch_size):
        batch = texts[start:start + batch_size]
        slot_token = acquire_ollama_slot(wait_seconds=wait_seconds)
        try:
            batch_vectors = _embed_single_batch(ollama, embed_model, batch)
            results.extend(batch_vectors)
        finally:
            release_ollama_slot(slot_token)

        if pause_seconds > 0 and start + batch_size < total:
            time.sleep(pause_seconds)

    return results
