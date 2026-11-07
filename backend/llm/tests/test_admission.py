import logging
from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from llm.admission import (
    ADMISSION_KEY,
    OllamaBusy,
    acquire_ollama_slot,
    release_ollama_slot,
)


class FakeRedis:
    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def eval(self, script, numkeys, key, token):
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0


class AdmissionTests(SimpleTestCase):
    def test_second_acquire_is_busy_and_wrong_token_does_not_release(self):
        client = FakeRedis()
        token = acquire_ollama_slot(client=client)
        self.assertTrue(token)
        with self.assertRaises(OllamaBusy):
            acquire_ollama_slot(client=client)
        release_ollama_slot('other-token', client=client)
        self.assertIn(ADMISSION_KEY, client.store)
        release_ollama_slot(token, client=client)
        self.assertNotIn(ADMISSION_KEY, client.store)

    def test_redis_error_fails_open_with_warning(self):
        client = MagicMock()
        client.set.side_effect = ConnectionError('redis down')
        with override_settings(REDIS_URL='redis://localhost:6379/0'):
            with self.assertLogs('llm.admission', level=logging.WARNING):
                token = acquire_ollama_slot(client=client)
        self.assertIsNone(token)

    @override_settings(REDIS_URL='')
    def test_missing_redis_url_fails_open_without_client(self):
        token = acquire_ollama_slot(client=None)
        self.assertIsNone(token)
