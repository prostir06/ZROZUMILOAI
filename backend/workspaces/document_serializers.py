"""Serializers for workspace documents."""
from rest_framework import serializers

from .models import WorkspaceDocument


class WorkspaceDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceDocument
        fields = (
            'id',
            'original_filename',
            'file_size',
            'status',
            'error_message',
            'chunk_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class WorkspaceDocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, uploaded_file):
        from django.conf import settings

        max_size = settings.RAG_MAX_FILE_SIZE
        if uploaded_file.size > max_size:
            raise serializers.ValidationError(
                f'Файл занадто великий (макс. {max_size // (1024 * 1024)} МБ)',
            )

        from workspaces.rag.text_extractor import ALLOWED_EXTENSIONS

        name = uploaded_file.name or ''
        suffix = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
        if f'.{suffix}' not in ALLOWED_EXTENSIONS:
            allowed = ', '.join(sorted(ALLOWED_EXTENSIONS))
            raise serializers.ValidationError(
                f'Непідтримуваний тип файлу. Дозволено: {allowed}',
            )

        return uploaded_file
