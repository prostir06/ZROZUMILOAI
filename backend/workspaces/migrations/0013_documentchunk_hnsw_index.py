# Generated manually for DocumentChunk HnswIndex declaration.

from django.db import migrations
from pgvector.django import HnswIndex


def create_hnsw_index(apps, schema_editor):
    """Створити HNSW-індекс для PostgreSQL (і видалити застарілий дублікат 0005 якщо є)."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    # Drop legacy raw-SQL index from 0005 if present to prevent duplicate HNSW index
    schema_editor.execute(
        'DROP INDEX IF EXISTS workspaces_documentchunk_embedding_hnsw;'
    )
    schema_editor.execute("""
        CREATE INDEX IF NOT EXISTS chunk_embedding_hnsw_idx
        ON workspaces_documentchunk
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)


def drop_hnsw_index(apps, schema_editor):
    """Видалити HNSW-індекс при відкаті міграції."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute('DROP INDEX IF EXISTS chunk_embedding_hnsw_idx;')
    schema_editor.execute("""
        CREATE INDEX IF NOT EXISTS workspaces_documentchunk_embedding_hnsw
        ON workspaces_documentchunk
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0012_workspace_embed_branding'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name='documentchunk',
                    index=HnswIndex(
                        ef_construction=64,
                        fields=['embedding'],
                        m=16,
                        name='chunk_embedding_hnsw_idx',
                        opclasses=['vector_cosine_ops'],
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    create_hnsw_index,
                    drop_hnsw_index,
                ),
            ],
        ),
    ]
