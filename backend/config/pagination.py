"""Опційна limit/offset пагінація для спискових ендпоінтів."""
from rest_framework.pagination import LimitOffsetPagination


class OptionalLimitOffsetPagination(LimitOffsetPagination):
    """
    Повертає весь список як масив за замовчуванням, або {count, results, ...},
    якщо клієнт явно передав ?limit=.
    """

    default_limit = None
    max_limit = 200
