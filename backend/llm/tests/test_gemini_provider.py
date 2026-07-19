"""Unit-тести для Gemini LLM провайдера."""
import json
from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from llm.base import LLMProviderError
from llm.gemini_provider import (
    GeminiProvider,
    GeminiStreamResponse,
    gemini_text_from_payload,
    split_messages_for_gemini,
    to_ollama_chunk,
    to_ollama_response,
)
from llm.factory import is_gemini_model, resolve_provider
from workspaces.models import Workspace


@override_settings(
    GEMINI_API_KEY='test-key',
    GEMINI_MODEL_NAMES=['gemini-2.0-flash', 'gemini-2.5-flash-lite'],
)
class GeminiProviderTests(SimpleTestCase):
    """Тести клієнта Gemini API."""

    def test_split_messages_for_gemini(self):
        """System, user та assistant мапляться коректно."""
        system, contents = split_messages_for_gemini([
            {'role': 'system', 'content': 'Be helpful'},
            {'role': 'user', 'content': 'Hi'},
            {'role': 'assistant', 'content': 'Hello'},
        ])
        self.assertEqual(system, 'Be helpful')
        self.assertEqual(len(contents), 2)
        self.assertEqual(contents[0]['role'], 'user')
        self.assertEqual(contents[1]['role'], 'model')

    def test_to_ollama_response_format(self):
        """Повна відповідь у форматі Ollama."""
        payload = to_ollama_response('Answer')
        self.assertEqual(payload['message']['content'], 'Answer')
        self.assertTrue(payload['done'])

    def test_to_ollama_chunk_format(self):
        """SSE-чанк у форматі Ollama."""
        raw = to_ollama_chunk('part')
        data = json.loads(raw)
        self.assertEqual(data['message']['content'], 'part')

    def test_gemini_text_from_payload(self):
        """Витяг тексту з відповіді Gemini."""
        text = gemini_text_from_payload({
            'candidates': [{
                'content': {'parts': [{'text': 'Hello'}]},
            }],
        })
        self.assertEqual(text, 'Hello')

    def test_list_models_uses_settings(self):
        """list_models повертає моделі з налаштувань."""
        provider = GeminiProvider()
        data = provider.list_models()
        names = [model['name'] for model in data['models']]
        self.assertIn('gemini-2.0-flash', names)
        self.assertEqual(data['models'][0]['provider'], 'gemini')

    def test_chat_non_stream_normalizes_response(self):
        """Нестрімінговий чат повертає Ollama-подібний JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'candidates': [{
                'content': {'parts': [{'text': 'Gemini reply'}]},
            }],
        }
        session = MagicMock()
        session.post.return_value = mock_response

        provider = GeminiProvider(session=session)
        result = provider.chat(
            'gemini-2.0-flash',
            [{'role': 'user', 'content': 'Hi'}],
            stream=False,
        )

        self.assertEqual(result['message']['content'], 'Gemini reply')
        session.post.assert_called_once()

    def test_stream_response_yields_ollama_chunks(self):
        """GeminiStreamResponse нормалізує SSE у формат Ollama."""
        payload = json.dumps({
            'candidates': [{
                'content': {'parts': [{'text': 'chunk'}]},
            }],
        })
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [f'data: {payload}'.encode('utf-8')]

        stream = GeminiStreamResponse(mock_response)
        lines = list(stream.iter_lines())

        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0].decode('utf-8'))
        self.assertEqual(data['message']['content'], 'chunk')

    def test_health_without_api_key(self):
        """health() повертає False без ключа."""
        provider = GeminiProvider(api_key='')
        self.assertFalse(provider.health())

    def test_chat_http_error_raises_provider_error(self):
        """HTTP 4xx від Gemini → LLMProviderError."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': {'message': 'Invalid API key'},
        }
        session = MagicMock()
        session.post.return_value = mock_response
        provider = GeminiProvider(session=session)

        with self.assertRaises(LLMProviderError) as ctx:
            provider.chat('gemini-2.0-flash', [{'role': 'user', 'content': 'Hi'}])

        self.assertIn('Invalid API key', str(ctx.exception))

    def test_chat_invalid_json_raises_provider_error(self):
        """Некоректний JSON у відповіді → LLMProviderError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError('bad json')
        session = MagicMock()
        session.post.return_value = mock_response
        provider = GeminiProvider(session=session)

        with self.assertRaises(LLMProviderError) as ctx:
            provider.chat('gemini-2.0-flash', [{'role': 'user', 'content': 'Hi'}])

        self.assertIn('JSON', str(ctx.exception))

    def test_empty_messages_raises(self):
        """Лише system-повідомлення без user → помилка."""
        provider = GeminiProvider()

        with self.assertRaises(LLMProviderError) as ctx:
            provider.chat(
                'gemini-2.0-flash',
                [{'role': 'system', 'content': 'Only system'}],
            )

        self.assertIn('порожніми', str(ctx.exception).lower())

    def test_invalid_temperature_raises(self):
        """Некоректна temperature → LLMProviderError."""
        provider = GeminiProvider()

        with self.assertRaises(LLMProviderError) as ctx:
            provider._build_payload(
                [{'role': 'user', 'content': 'Hi'}],
                options={'temperature': 'hot'},
            )

        self.assertIn('temperature', str(ctx.exception).lower())


@override_settings(GEMINI_MODEL_NAMES=['gemini-2.0-flash'])
class LLMFactoryTests(SimpleTestCase):
    """Тести фабрики провайдерів."""

    def test_is_gemini_model(self):
        """Розпізнавання імен Gemini моделей."""
        self.assertTrue(is_gemini_model('gemini-2.0-flash'))
        self.assertFalse(is_gemini_model('llama3'))

    def test_resolve_provider_from_workspace(self):
        """Workspace визначає провайдера."""
        workspace = Workspace(llm_provider=Workspace.LLMProvider.GEMINI)
        provider = resolve_provider(workspace=workspace)
        self.assertEqual(provider.provider_id, 'gemini')

        workspace.llm_provider = Workspace.LLMProvider.OLLAMA
        provider = resolve_provider(workspace=workspace)
        self.assertEqual(provider.provider_id, 'ollama')

    def test_resolve_provider_uses_workspace_gemini_key(self):
        """Ключ Gemini береться з workspace."""
        workspace = Workspace(
            llm_provider=Workspace.LLMProvider.GEMINI,
            gemini_api_key='workspace-key',
        )
        provider = resolve_provider(workspace=workspace)
        self.assertEqual(provider.api_key, 'workspace-key')

    def test_resolve_provider_from_model_name(self):
        """Без workspace модель визначає провайдера."""
        provider = resolve_provider(model_name='gemini-2.0-flash')
        self.assertEqual(provider.provider_id, 'gemini')

        provider = resolve_provider(model_name='llama3')
        self.assertEqual(provider.provider_id, 'ollama')
