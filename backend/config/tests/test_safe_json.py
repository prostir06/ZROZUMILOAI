"""Unit-тести safe_response_json."""
import json
from unittest.mock import MagicMock

import requests
from django.test import SimpleTestCase

from config.http_utils import safe_response_json


class SafeResponseJsonTests(SimpleTestCase):
    def test_parses_valid_json(self):
        response = MagicMock()
        response.json.return_value = {'ok': True}
        self.assertEqual(safe_response_json(response, 'Test'), {'ok': True})

    def test_raises_on_invalid_json(self):
        response = MagicMock()
        response.json.side_effect = json.JSONDecodeError('err', 'doc', 0)

        with self.assertRaises(requests.RequestException):
            safe_response_json(response, 'Ollama')
