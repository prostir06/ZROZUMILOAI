"""Fallback RAG-пошук через Python (SQLite / без pgvector)."""
import logging

from ..models import DocumentChunk, WorkspaceDocument
from .similarity import cosine_similarity

logger = logging.getLogger(__name__)


def search_with_python(workspace, query_vector, top_k):
    """
    Лінійний пошук косинусної схожості в Python.

    :return: список dict з content, score, document_name
    """
    try:
        chunks = DocumentChunk.objects.filter(
            workspace=workspace,
            document__status=WorkspaceDocument.Status.READY,
        ).select_related('document')
    except Exception as exc:
        logger.error('Python RAG search query failed: %s', exc)
        return []

    if not chunks.exists():
        return []

    scored = []
    for chunk in chunks.iterator():
        embedding = chunk.embedding
        if embedding is None or isinstance(embedding, str):
            continue

        try:
            score = cosine_similarity(query_vector, embedding)
        except Exception as exc:
            logger.warning('Skip chunk %s: %s', chunk.pk, exc)
            continue

        if score > 0:
            scored.append({
                'content': chunk.content,
                'score': score,
                'document_name': chunk.document.original_filename,
            })

    scored.sort(key=lambda item: item['score'], reverse=True)
    return scored[:top_k]
