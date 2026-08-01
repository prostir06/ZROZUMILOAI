"""Unit-тести Reciprocal Rank Fusion (PEP 8)."""
from django.test import SimpleTestCase

from workspaces.rag.fusion import reciprocal_rank_fusion


class ReciprocalRankFusionEdgeTests(SimpleTestCase):
    """Граничні випадки RRF після винесення в окремий модуль."""

    def test_invalid_top_k_returns_empty(self):
        self.assertEqual(
            reciprocal_rank_fusion(
                [[{'document_name': 'A', 'content': 'x', 'score': 1}]],
                top_k='bad',
            ),
            [],
        )

    def test_skips_non_dict_items(self):
        merged = reciprocal_rank_fusion(
            [[
                'broken',
                {'document_name': 'A', 'content': 'ok', 'score': 0.9},
            ]],
            top_k=3,
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['document_name'], 'A')

    def test_bad_score_becomes_zero(self):
        merged = reciprocal_rank_fusion(
            [[{'document_name': 'A', 'content': 'x', 'score': 'nope'}]],
            top_k=1,
        )
        self.assertEqual(merged[0]['score'], 0.0)
        self.assertIn('rrf_score', merged[0])
