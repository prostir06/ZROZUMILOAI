"""Тести Reciprocal Rank Fusion і sources."""
from django.test import SimpleTestCase, override_settings

from workspaces.rag.service import (
    format_rag_context,
    reciprocal_rank_fusion,
    sources_from_chunks,
)


class ReciprocalRankFusionTests(SimpleTestCase):
    def test_merges_and_ranks_by_rrf(self):
        internal = [
            {'document_name': 'A', 'content': 'alpha text', 'score': 0.99},
            {'document_name': 'B', 'content': 'beta text', 'score': 0.5},
        ]
        meili = [
            {'document_name': 'B', 'content': 'beta text', 'score': 12.0},
            {'document_name': 'C', 'content': 'gamma text', 'score': 11.0},
        ]
        merged = reciprocal_rank_fusion([internal, meili], top_k=3)
        names = [item['document_name'] for item in merged]
        self.assertEqual(names[0], 'B')
        self.assertIn('A', names)
        self.assertIn('C', names)

    def test_top_k_limit(self):
        lists = [
            [
                {'document_name': f'D{i}', 'content': f'c{i}', 'score': 1.0}
                for i in range(5)
            ],
        ]
        merged = reciprocal_rank_fusion(lists, top_k=2)
        self.assertEqual(len(merged), 2)

    def test_empty_lists(self):
        self.assertEqual(reciprocal_rank_fusion([[], None], top_k=3), [])


class SourcesFromChunksTests(SimpleTestCase):
    def test_dedupes_and_truncates(self):
        chunks = [
            {'document_name': 'FAQ', 'content': 'hello world', 'score': 0.8},
            {'document_name': 'FAQ', 'content': 'hello world', 'score': 0.7},
            {'document_name': 'Guide', 'content': 'other', 'score': 0.6},
        ]
        sources = sources_from_chunks(chunks)
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]['document_name'], 'FAQ')
        self.assertIn('excerpt', sources[0])

    def test_handles_none_and_bad_score(self):
        self.assertEqual(sources_from_chunks(None), [])
        sources = sources_from_chunks([
            {'document_name': 'X', 'content': 'c', 'score': 'bad'},
        ])
        self.assertEqual(sources[0]['score'], 0.0)


class FormatRagContextTests(SimpleTestCase):
    @override_settings(RAG_MIN_SCORE=0.5, MEILISEARCH_MAX_CHUNK_CHARS=200)
    def test_low_score_adds_escalation_hint(self):
        text = format_rag_context([
            {'document_name': 'FAQ', 'content': 'мало релевантне', 'score': 0.1},
        ])
        self.assertIn('підтримки', text.lower())
        self.assertIn('FAQ', text)
