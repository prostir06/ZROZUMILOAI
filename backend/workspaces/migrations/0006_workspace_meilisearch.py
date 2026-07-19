"""Meilisearch (Open edX) settings on Workspace."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0005_documentchunk_pgvector'),
    ]

    operations = [
        migrations.AddField(
            model_name='workspace',
            name='search_source',
            field=models.CharField(
                choices=[
                    ('internal', 'Локальні документи (RAG)'),
                    ('meilisearch', 'Open edX Meilisearch'),
                    ('hybrid', 'RAG + Meilisearch'),
                ],
                default='internal',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='workspace',
            name='meilisearch_url',
            field=models.URLField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='workspace',
            name='meilisearch_api_key',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='workspace',
            name='meilisearch_index_prefix',
            field=models.CharField(blank=True, default='tutor_', max_length=100),
        ),
        migrations.AddField(
            model_name='workspace',
            name='meilisearch_indexes',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='workspace',
            name='meilisearch_course_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
