"""Workspace models."""
import hashlib
import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def generate_widget_token_value():
    """Generate a new widget token string."""
    return f'wt_{secrets.token_urlsafe(32)}'


def hash_widget_token(key):
    """Return SHA-256 hash of the widget token."""
    return hashlib.sha256(key.encode()).hexdigest()


class Workspace(models.Model):
    """Named workspace with assigned models and users."""

    class SearchSource(models.TextChoices):
        INTERNAL = 'internal', 'Локальні документи (RAG)'
        MEILISEARCH = 'meilisearch', 'Open edX Meilisearch'
        HYBRID = 'hybrid', 'RAG + Meilisearch'

    class LLMProvider(models.TextChoices):
        OLLAMA = 'ollama', 'Ollama'
        GEMINI = 'gemini', 'Google Gemini'

    name = models.CharField(max_length=200, unique=True)
    system_prompt = models.TextField(blank=True, default='')
    temperature = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0.0), MaxValueValidator(2.0)],
    )
    model_names = models.JSONField(default=list, blank=True)
    llm_provider = models.CharField(
        max_length=20,
        choices=LLMProvider.choices,
        default=LLMProvider.OLLAMA,
    )
    gemini_api_key = models.CharField(max_length=255, blank=True, default='')
    search_source = models.CharField(
        max_length=20,
        choices=SearchSource.choices,
        default=SearchSource.INTERNAL,
    )
    meilisearch_url = models.URLField(blank=True, default='')
    meilisearch_api_key = models.CharField(max_length=255, blank=True, default='')
    meilisearch_index_prefix = models.CharField(
        max_length=100,
        blank=True,
        default='tutor_',
    )
    meilisearch_indexes = models.JSONField(
        default=list,
        blank=True,
        help_text='Суфікси індексів (course_info) або повні UID (tutor_course_info)',
    )
    meilisearch_course_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Фільтр course-v1:... для courseware_content',
    )
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='workspaces',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)
        verbose_name = 'Workspace'
        verbose_name_plural = 'Workspaces'

    def __str__(self):
        return self.name


def workspace_document_upload_to(instance, filename):
    """Шлях збереження файлу документа workspace."""
    from workspaces.rag.service import sanitize_filename
    safe_name = sanitize_filename(filename)
    return f'workspace_documents/{instance.workspace_id}/{safe_name}'


class WorkspaceDocument(models.Model):
    """Завантажений документ для RAG у workspace."""

    class Status(models.TextChoices):
        PROCESSING = 'processing', 'Обробка'
        READY = 'ready', 'Готовий'
        FAILED = 'failed', 'Помилка'

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=workspace_document_upload_to)
    file_size = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PROCESSING,
    )
    error_message = models.TextField(blank=True, default='')
    chunk_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Документ workspace'
        verbose_name_plural = 'Документи workspace'

    def __str__(self):
        return f'{self.original_filename} ({self.workspace.name})'


def _embedding_field():
    """VectorField для PostgreSQL + pgvector, JSONField для SQLite."""
    from django.conf import settings as django_settings

    engine = django_settings.DATABASES['default']['ENGINE']
    if 'sqlite' in engine:
        return models.JSONField(default=list)

    from pgvector.django import VectorField

    return VectorField(
        dimensions=django_settings.RAG_EMBED_DIMENSIONS,
        null=True,
        blank=True,
    )


class DocumentChunk(models.Model):
    """Фрагмент документа з embedding для векторного пошуку."""

    document = models.ForeignKey(
        WorkspaceDocument,
        on_delete=models.CASCADE,
        related_name='chunks',
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='document_chunks',
    )
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    embedding = _embedding_field()

    class Meta:
        ordering = ('document', 'chunk_index')
        indexes = [
            models.Index(fields=['workspace']),
        ]
        verbose_name = 'Фрагмент документа'
        verbose_name_plural = 'Фрагменти документів'

    def __str__(self):
        return f'{self.document.original_filename} #{self.chunk_index}'


class WidgetToken(models.Model):
    """Public embed token scoped to a single workspace."""

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='widget_tokens',
    )
    label = models.CharField(max_length=100, blank=True, default='')
    token_prefix = models.CharField(max_length=12)
    token_hash = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Widget token'
        verbose_name_plural = 'Widget tokens'

    def __str__(self):
        label = self.label or self.token_prefix
        return f'{label} ({self.workspace.name})'

    @classmethod
    def create_for_workspace(cls, workspace, label=''):
        """Create token and return the raw value (shown once)."""
        raw_token = generate_widget_token_value()
        instance = cls.objects.create(
            workspace=workspace,
            label=label.strip(),
            token_prefix=raw_token[:12],
            token_hash=hash_widget_token(raw_token),
        )
        return raw_token, instance

    def mark_used(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])
