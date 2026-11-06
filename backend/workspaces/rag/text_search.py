"""Повнотекстовий пошук RAG: PostgreSQL SearchVector або SQLite fallback."""
import logging
import re

from django.conf import settings
from django.db import connection
from django.db.models import Q

from ..models import DocumentChunk, WorkspaceDocument

logger = logging.getLogger(__name__)


def search_with_fulltext(workspace, query, top_k=None):
    """
    Повнотекстовий пошук у фрагментах документів workspace.

    :param workspace: екземпляр Workspace
    :param query: пошуковий рядок
    :param top_k: максимальна кількість результатів
    :return: список dict з content, score, document_name, id, chunk_index
    """
    try:
        if not workspace or not query or not str(query).strip():
            return []

        top_k = top_k or getattr(settings, 'RAG_TOP_K', 5)
        try:
            top_k = int(top_k)
        except (TypeError, ValueError):
            top_k = 5
        if top_k <= 0:
            return []

        query_str = str(query).strip()

        if connection.vendor == 'postgresql':
            from django.contrib.postgres.search import (
                SearchQuery,
                SearchRank,
                SearchVector,
            )

            search_query = SearchQuery(query_str, config='simple')
            search_vector = SearchVector('content', config='simple')
            chunks = (
                DocumentChunk.objects.filter(
                    workspace=workspace,
                    document__status=WorkspaceDocument.Status.READY,
                )
                .annotate(rank=SearchRank(search_vector, search_query))
                .filter(rank__gt=0.0)
                .order_by('-rank')
                .select_related('document')[:top_k]
            )

            results = []
            for chunk in chunks:
                try:
                    rank_val = float(chunk.rank)
                    score = min(1.0, max(0.0, rank_val))
                    results.append({
                        'content': chunk.content,
                        'score': score,
                        'document_name': (
                            chunk.document.original_filename
                            if chunk.document
                            else ''
                        ),
                        'id': chunk.pk,
                        'chunk_index': chunk.chunk_index,
                    })
                except (TypeError, ValueError) as exc:
                    logger.warning('Skip fulltext chunk %s: %s', chunk.pk, exc)
            return results

        # SQLite / non-PostgreSQL fallback
        raw_tokens = list(dict.fromkeys(re.findall(r'\w+', query_str)))
        if not raw_tokens:
            return []

        tokens = [t.lower() for t in raw_tokens]

        q_filter = Q()
        for raw_token in raw_tokens:
            variants = {
                raw_token,
                raw_token.lower(),
                raw_token.upper(),
                raw_token.title(),
            }
            for variant in variants:
                q_filter |= Q(content__icontains=variant)

        chunks = (
            DocumentChunk.objects.filter(
                workspace=workspace,
                document__status=WorkspaceDocument.Status.READY,
            )
            .filter(q_filter)
            .select_related('document')
        )

        total_tokens = len(tokens)
        scored = []
        for chunk in chunks:
            content_lower = (chunk.content or '').lower()
            matched_count = sum(1 for token in tokens if token in content_lower)
            if matched_count <= 0:
                continue
            score = min(1.0, max(0.0, matched_count / total_tokens))
            scored.append({
                'content': chunk.content,
                'score': score,
                'document_name': (
                    chunk.document.original_filename
                    if chunk.document
                    else ''
                ),
                'id': chunk.pk,
                'chunk_index': chunk.chunk_index,
            })

        scored.sort(key=lambda item: item['score'], reverse=True)
        return scored[:top_k]

    except Exception as exc:
        logger.error('Fulltext search failed: %s', exc)
        return []
