"""Unit-тести Meilisearch Open edX пошуку."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from workspaces.models import Workspace
from workspaces.rag.meilisearch_search import (
    build_course_filter,
    extract_openedx_hit_text,
    normalize_meilisearch_url,
    resolve_meilisearch_indexes,
    search_openedx_meilisearch,
)


class MeilisearchHelperTests(SimpleTestCase):
    def test_normalize_meilisearch_url_adds_https(self):
        self.assertEqual(
            normalize_meilisearch_url('meilisearch.example.com'),
            'https://meilisearch.example.com',
        )

    def test_normalize_meilisearch_url_local_openedx_uses_http(self):
        self.assertEqual(
            normalize_meilisearch_url('meilisearch.local.openedx.io'),
            'http://meilisearch.local.openedx.io',
        )

    def test_normalize_meilisearch_url_rewrites_local_https_to_http(self):
        self.assertEqual(
            normalize_meilisearch_url('https://meilisearch.local.openedx.io'),
            'http://meilisearch.local.openedx.io',
        )

    def test_resolve_indexes_with_prefix(self):
        workspace = Workspace(
            meilisearch_index_prefix='tutor_',
            meilisearch_indexes=['course_info', 'courseware_content'],
        )
        self.assertEqual(
            resolve_meilisearch_indexes(workspace),
            ['tutor_course_info', 'tutor_courseware_content'],
        )

    def test_resolve_indexes_full_uid(self):
        workspace = Workspace(
            meilisearch_index_prefix='tutor_',
            meilisearch_indexes=['tutor_course_info'],
        )
        self.assertEqual(
            resolve_meilisearch_indexes(workspace),
            ['tutor_course_info'],
        )

    @override_settings(MEILISEARCH_INDEX_PREFIX='tutor_')
    def test_resolve_default_indexes(self):
        workspace = Workspace(meilisearch_indexes=[])
        self.assertEqual(
            resolve_meilisearch_indexes(workspace),
            ['tutor_course_info', 'tutor_courseware_content'],
        )

    def test_extract_openedx_hit_text(self):
        hit = {
            'course': 'course-v1:ORG+COURSE+RUN',
            'content': {
                'display_name': 'Вступ',
                'overview': '<p>Опис <strong>курсу</strong></p>',
            },
        }
        text = extract_openedx_hit_text(hit)
        self.assertIn('Вступ', text)
        self.assertIn('Опис курсу', text)
        self.assertNotIn('<p>', text)

    def test_build_course_filter_for_courseware(self):
        self.assertEqual(
            build_course_filter('course-v1:X', 'tutor_courseware_content'),
            'course = "course-v1:X"',
        )


class MeilisearchSearchTests(SimpleTestCase):
    @patch('workspaces.rag.meilisearch_search.meilisearch.Client')
    def test_search_returns_ranked_chunks(self, mock_client_cls):
        workspace = Workspace(
            search_source=Workspace.SearchSource.MEILISEARCH,
            meilisearch_url='https://meilisearch.local.openedx.io',
            meilisearch_api_key='test-key',
            meilisearch_index_prefix='tutor_',
            meilisearch_indexes=['course_info'],
        )

        mock_index = MagicMock()
        mock_index.search.return_value = {
            'hits': [{
                'display_name': 'Demo Course',
                'content': {'overview': 'About demo'},
                '_rankingScore': 0.91,
                'course': 'course-v1:OpenedX+DemoX+DemoCourse',
            }],
        }
        mock_client = MagicMock()
        mock_client.index.return_value = mock_index
        mock_client_cls.return_value = mock_client

        results = search_openedx_meilisearch(workspace, 'demo course', top_k=2)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['document_name'], 'Demo Course')
        self.assertIn('About demo', results[0]['content'])
        mock_index.search.assert_called_once()

    def test_search_skipped_for_internal_source(self):
        workspace = Workspace(search_source=Workspace.SearchSource.INTERNAL)
        self.assertEqual(search_openedx_meilisearch(workspace, 'test'), [])
