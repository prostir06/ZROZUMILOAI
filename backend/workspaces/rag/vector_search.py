"""Векторний пошук RAG через pgvector (PostgreSQL)."""
import logging

from django.conf import settings
from django.db import connection, DatabaseError

from pgvector.django import CosineDistance

from ..models import DocumentChunk, WorkspaceDocument

logger = logging.getLogger(__name__)


def uses_pgvector():
    """Чи доступний pgvector (PostgreSQL, не SQLite)."""
    if connection.vendor != 'postgresql':
        return False
    engine = settings.DATABASES['default']['ENGINE']
    return 'sqlite' not in engine


def search_with_pgvector(workspace, query_vector, top_k):
    """
    Пошук найближчих фрагментів через pgvector (cosine distance).

    :return: список dict з content, score, document_name
    """
    try:
        chunks = (
            DocumentChunk.objects.filter(
                workspace=workspace,
                document__status=WorkspaceDocument.Status.READY,
                embedding__isnull=False,
            )
            .annotate(distance=CosineDistance('embedding', query_vector))
            .order_by('distance')
            .select_related('document')[:top_k]
        )
    except DatabaseError as exc:
        logger.error('pgvector RAG search failed: %s', exc)
        return []

    results = []
    for chunk in chunks:
        try:
            distance = float(chunk.distance)
            score = max(0.0, 1.0 - distance)
            results.append({
                'content': chunk.content,
                'score': score,
                'document_name': chunk.document.original_filename,
            })
        except (TypeError, ValueError) as exc:
            logger.warning('Skip pgvector chunk %s: %s', chunk.pk, exc)

    return results
