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

    def test_release_failure_is_logged_and_not_raised(self):
        client = MagicMock()
        client.eval.side_effect = ConnectionError('redis down')
        with self.assertLogs('llm.admission', level=logging.WARNING) as logs:
            release_ollama_slot('token-1', client=client)
        self.assertIn('redis down', logs.output[0])

    @override_settings(REDIS_URL='')
    def test_missing_redis_url_fails_open_without_client(self):
        token = acquire_ollama_slot(client=None)
        self.assertIsNone(token)

    def test_acquire_waits_until_slot_is_released(self):
        client = FakeRedis()
        calls = {'count': 0}
        orig_set = client.set

        def releasing_set(key, value, nx=False, ex=None):
            calls['count'] += 1
            if calls['count'] == 2:
                client.store.pop(ADMISSION_KEY, None)
            return orig_set(key, value, nx=nx, ex=ex)

        client.set = releasing_set
        first = orig_set(ADMISSION_KEY, 'holder', nx=True, ex=180)
        self.assertTrue(first)

        token = acquire_ollama_slot(
            client=client,
            wait_seconds=0.2,
            poll_interval=0.01,
        )
        self.assertTrue(token)
        self.assertEqual(calls['count'], 2)
