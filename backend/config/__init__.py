"""Load Celery app when Django starts (worker + beat share this)."""
from .celery import app as celery_app

__all__ = ('celery_app',)
