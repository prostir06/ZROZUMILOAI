"""Unit-тести pgvector RAG-пошуку та HnswIndex."""
from unittest.mock import MagicMock, patch

from django.contrib.postgres.indexes import GinIndex
from django.db import connection, migrations, models
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase, TestCase, override_settings
from pgvector.django import HnswIndex

from workspaces.models import DocumentChunk, _document_chunk_indexes
from workspaces.rag.vector_search import search_with_pgvector, uses_pgvector


class DocumentChunkIndexTests(SimpleTestCase):
    """Тести декларації індексів DocumentChunk та SQLite-сумісності."""

    def test_document_chunk_indexes_on_sqlite(self):
        indexes = _document_chunk_indexes(engine='django.db.backends.sqlite3')
        self.assertEqual(len(indexes), 1)
        self.assertEqual(indexes[0].fields, ['workspace'])
        self.assertFalse(any(isinstance(idx, HnswIndex) for idx in indexes))
        self.assertFalse(any(isinstance(idx, GinIndex) for idx in indexes))

    def test_document_chunk_indexes_on_postgresql(self):
        indexes = _document_chunk_indexes(engine='django.db.backends.postgresql')
        self.assertEqual(len(indexes), 3)
        self.assertEqual(indexes[0].fields, ['workspace'])

        hnsw_idx = indexes[1]
        self.assertIsInstance(hnsw_idx, HnswIndex)
        self.assertEqual(hnsw_idx.name, 'chunk_embedding_hnsw_idx')
        self.assertEqual(hnsw_idx.fields, ['embedding'])
        self.assertEqual(hnsw_idx.m, 16)
        self.assertEqual(hnsw_idx.ef_construction, 64)
        self.assertEqual(hnsw_idx.opclasses, ['vector_cosine_ops'])

        gin_idx = indexes[2]
        self.assertIsInstance(gin_idx, GinIndex)
        self.assertEqual(gin_idx.name, 'chunk_content_fts_gin_idx')

    def test_active_environment_model_indexes_compat(self):
        """В активному тестовому середовищі (SQLite) індекси не повинні містити HnswIndex."""
        if 'sqlite' in connection.vendor:
            for idx in DocumentChunk._meta.indexes:
                self.assertNotIsInstance(
                    idx,
                    HnswIndex,
                    'HnswIndex не повинен бути присутнім у Meta.indexes на SQLite',
                )
            workspace_indexes = [
                idx for idx in DocumentChunk._meta.indexes
                if 'workspace' in idx.fields
            ]
            self.assertTrue(len(workspace_indexes) >= 1)


class DocumentChunkMigrationTests(TestCase):
    """Тести виконання міграцій на тестовій БД (SQLite) та логіки міграції 0013."""

    def test_migration_0013_declared_and_loads(self):
        loader = MigrationLoader(connection)
        self.assertIn(
            ('workspaces', '0013_documentchunk_hnsw_index'),
            loader.disk_migrations,
            'Міграція 0013 повинна існувати на диску',
        )
        migration = loader.disk_migrations[('workspaces', '0013_documentchunk_hnsw_index')]
        self.assertIn(('workspaces', '0012_workspace_embed_branding'), migration.dependencies)

        # Перевіряємо state_operations
        sep_op = migration.operations[0]
        self.assertIsInstance(sep_op, migrations.SeparateDatabaseAndState)
        add_index_op = sep_op.state_operations[0]
        self.assertIsInstance(add_index_op, migrations.AddIndex)
        self.assertEqual(add_index_op.model_name, 'documentchunk')
        self.assertEqual(add_index_op.index.name, 'chunk_embedding_hnsw_idx')
        self.assertEqual(add_index_op.index.m, 16)
        self.assertEqual(add_index_op.index.ef_construction, 64)
        self.assertEqual(add_index_op.index.opclasses, ['vector_cosine_ops'])

    def test_migration_0013_sqlite_no_op(self):
        import importlib
        mod = importlib.import_module('workspaces.migrations.0013_documentchunk_hnsw_index')

        mock_editor = MagicMock()
        mock_editor.connection.vendor = 'sqlite'

        mod.create_hnsw_index(None, mock_editor)
        mock_editor.execute.assert_not_called()

        mod.drop_hnsw_index(None, mock_editor)
        mock_editor.execute.assert_not_called()

    def test_migration_0013_postgresql_execution(self):
        import importlib
        mod = importlib.import_module('workspaces.migrations.0013_documentchunk_hnsw_index')

        mock_editor = MagicMock()
        mock_editor.connection.vendor = 'postgresql'

        mod.create_hnsw_index(None, mock_editor)
        executed_sqls = [call.args[0] for call in mock_editor.execute.call_args_list]
        self.assertTrue(any('chunk_embedding_hnsw_idx' in sql for sql in executed_sqls))
        self.assertTrue(any('vector_cosine_ops' in sql for sql in executed_sqls))
        self.assertTrue(any('m = 16' in sql for sql in executed_sqls))

        mock_editor.reset_mock()
        mod.drop_hnsw_index(None, mock_editor)
        rollback_sqls = [call.args[0] for call in mock_editor.execute.call_args_list]
        self.assertTrue(any('DROP INDEX IF EXISTS chunk_embedding_hnsw_idx' in sql for sql in rollback_sqls))

    def test_migration_0015_fts_gin_index_declared_and_executes(self):
        import importlib
        loader = MigrationLoader(connection)
        self.assertIn(
            ('workspaces', '0015_documentchunk_fts_gin_index'),
            loader.disk_migrations,
            'Міграція 0015 повинна існувати на диску',
        )
        migration = loader.disk_migrations[('workspaces', '0015_documentchunk_fts_gin_index')]
        self.assertIn(('workspaces', '0014_remove_gemini'), migration.dependencies)

        sep_op = migration.operations[0]
        self.assertIsInstance(sep_op, migrations.SeparateDatabaseAndState)
        add_index_op = sep_op.state_operations[0]
        self.assertIsInstance(add_index_op, migrations.AddIndex)
        self.assertEqual(add_index_op.model_name, 'documentchunk')
        self.assertIsInstance(add_index_op.index, GinIndex)
        self.assertEqual(add_index_op.index.name, 'chunk_content_fts_gin_idx')

        mod = importlib.import_module('workspaces.migrations.0015_documentchunk_fts_gin_index')

        sqlite_editor = MagicMock()
        sqlite_editor.connection.vendor = 'sqlite'
        mod.create_fts_gin_index(None, sqlite_editor)
        sqlite_editor.execute.assert_not_called()
        mod.drop_fts_gin_index(None, sqlite_editor)
        sqlite_editor.execute.assert_not_called()

        pg_editor = MagicMock()
        pg_editor.connection.vendor = 'postgresql'
        mod.create_fts_gin_index(None, pg_editor)
        executed_sqls = [call.args[0] for call in pg_editor.execute.call_args_list]
        self.assertTrue(any('CREATE INDEX IF NOT EXISTS chunk_content_fts_gin_idx' in sql for sql in executed_sqls))
        self.assertTrue(any("to_tsvector('simple', content)" in sql for sql in executed_sqls))

        pg_editor.reset_mock()
        mod.drop_fts_gin_index(None, pg_editor)
        rollback_sqls = [call.args[0] for call in pg_editor.execute.call_args_list]
        self.assertTrue(any('DROP INDEX IF EXISTS chunk_content_fts_gin_idx' in sql for sql in rollback_sqls))


class PgvectorSearchTests(SimpleTestCase):
    @override_settings(DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3'}})
    def test_uses_pgvector_false_on_sqlite(self):
        self.assertFalse(uses_pgvector())

    @patch('workspaces.rag.vector_search.DocumentChunk')
    def test_search_with_pgvector_returns_scored_results(self, mock_chunk_model):
        chunk = MagicMock()
        chunk.content = 'FAQ текст'
        chunk.distance = 0.2
        chunk.document.original_filename = 'faq.md'

        queryset = MagicMock()
        queryset.annotate.return_value = queryset
        queryset.order_by.return_value = queryset
        queryset.select_related.return_value = queryset
        queryset.__getitem__.return_value = [chunk]
        mock_chunk_model.objects.filter.return_value = queryset

        results = search_with_pgvector(workspace=MagicMock(), query_vector=[0.1] * 768, top_k=3)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['content'], 'FAQ текст')
        self.assertAlmostEqual(results[0]['score'], 0.8)
