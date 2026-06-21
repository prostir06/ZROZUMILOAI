"""Unit-тести cosine similarity."""
from django.test import SimpleTestCase

from workspaces.rag.similarity import cosine_similarity


class CosineSimilarityTests(SimpleTestCase):
    def test_identical_vectors(self):
        vector = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(vector, vector), 1.0)

    def test_orthogonal_vectors(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_empty_vectors(self):
        self.assertEqual(cosine_similarity([], [1]), 0.0)
        self.assertEqual(cosine_similarity([1], []), 0.0)

    def test_mismatched_length(self):
        self.assertEqual(cosine_similarity([1, 2], [1]), 0.0)

    def test_invalid_values_return_zero(self):
        self.assertEqual(cosine_similarity(['bad', 1], [1, 2]), 0.0)
