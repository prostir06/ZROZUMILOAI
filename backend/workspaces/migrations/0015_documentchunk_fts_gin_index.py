"""Add PostgreSQL GIN functional index for full-text search on DocumentChunk.content."""
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import migrations


def create_fts_gin_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute("""
        CREATE INDEX IF NOT EXISTS chunk_content_fts_gin_idx
        ON workspaces_documentchunk
        USING gin (to_tsvector('simple', content));
    """)


def drop_fts_gin_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('DROP INDEX IF EXISTS chunk_content_fts_gin_idx;')


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0014_remove_gemini'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name='documentchunk',
                    index=GinIndex(
                        SearchVector('content', config='simple'),
                        name='chunk_content_fts_gin_idx',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    create_fts_gin_index,
                    drop_fts_gin_index,
                ),
            ],
        ),
    ]
