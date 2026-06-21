"""Косинусна схожість для векторного пошуку (fallback без pgvector)."""
import logging
import math

logger = logging.getLogger(__name__)


def cosine_similarity(vector_a, vector_b):
    """
    Обчислити косинусну схожість двох векторів.

    Повертає 0.0 при некоректних або порожніх векторах.
    """
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0

    try:
        dot = sum(float(a) * float(b) for a, b in zip(vector_a, vector_b))
        norm_a = math.sqrt(sum(float(a) * float(a) for a in vector_a))
        norm_b = math.sqrt(sum(float(b) * float(b) for b in vector_b))
    except (TypeError, ValueError) as exc:
        logger.warning('Invalid embedding values for similarity: %s', exc)
        return 0.0

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)
