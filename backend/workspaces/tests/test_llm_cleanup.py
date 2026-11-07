from django.test import TestCase

from workspaces.llm_cleanup import rewrite_llm_fields
from workspaces.models import Workspace


class RewriteLlmFieldsTests(TestCase):
    def test_gemini_provider_and_model_names_become_ollama(self):
        provider, names = rewrite_llm_fields(
            'gemini',
            ['gemini-2.0-flash', 'llama3.2:latest', 'gemini-1.5-flash:001'],
        )
        self.assertEqual(provider, 'ollama')
        self.assertEqual(names, ['llama3.2:latest'])

    def test_ollama_names_stay(self):
        provider, names = rewrite_llm_fields('ollama', ['llama3.2'])
        self.assertEqual(provider, 'ollama')
        self.assertEqual(names, ['llama3.2'])

    def test_model_has_no_gemini_api_key(self):
        field_names = {field.name for field in Workspace._meta.fields}
        self.assertNotIn('gemini_api_key', field_names)
        self.assertNotIn('gemini', Workspace.LLMProvider.values)
