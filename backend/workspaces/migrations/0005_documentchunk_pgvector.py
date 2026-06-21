"""Міграція embedding на pgvector (PostgreSQL)."""
from django.db import migrations
from pgvector.django import VectorExtension, VectorField


def convert_embedding_to_vector(apps, schema_editor):
    """Конвертувати JSONB embedding у vector(768) для PostgreSQL."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute("""
        ALTER TABLE workspaces_documentchunk
        ALTER COLUMN embedding TYPE vector(768)
        USING (
            CASE
                WHEN embedding IS NULL OR embedding::text IN ('[]', 'null')
                THEN NULL
                ELSE (embedding::text)::vector
            END
        );
    """)


def revert_embedding_to_json(apps, schema_editor):
    """Повернути vector назад у JSONB."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute("""
        ALTER TABLE workspaces_documentchunk
        ALTER COLUMN embedding TYPE jsonb
        USING (
            CASE
                WHEN embedding IS NULL THEN '[]'::jsonb
                ELSE to_jsonb(embedding::real[])
            END
        );
    """)


def create_hnsw_index(apps, schema_editor):
    """HNSW-індекс для швидкого cosine-пошуку."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute("""
        CREATE INDEX IF NOT EXISTS workspaces_documentchunk_embedding_hnsw
        ON workspaces_documentchunk
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)


def drop_hnsw_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute(
        'DROP INDEX IF EXISTS workspaces_documentchunk_embedding_hnsw;',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0004_workspacedocument_documentchunk'),
    ]

    operations = [
        VectorExtension(),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='documentchunk',
                    name='embedding',
                    field=VectorField(blank=True, dimensions=768, null=True),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    convert_embedding_to_vector,
                    revert_embedding_to_json,
                ),
                migrations.RunPython(create_hnsw_index, drop_hnsw_index),
            ],
        ),
    ]
