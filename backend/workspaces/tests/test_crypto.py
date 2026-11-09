"""Unit-тести шифрування секретів workspace."""
from django.test import SimpleTestCase, override_settings

from workspaces.crypto import decrypt_secret, encrypt_secret


@override_settings(SECRET_KEY='test-secret-key-for-fernet', FIELD_ENCRYPTION_KEY='')
class WorkspaceCryptoTests(SimpleTestCase):
    """Fernet round-trip та legacy plaintext."""

    def test_encrypt_decrypt_roundtrip(self):
        cipher = encrypt_secret('my-api-key')
        self.assertTrue(cipher.startswith('enc:v1:'))
        self.assertEqual(decrypt_secret(cipher), 'my-api-key')

    def test_empty_stays_empty(self):
        self.assertEqual(encrypt_secret(''), '')
        self.assertEqual(decrypt_secret(''), '')

    def test_legacy_plaintext_passthrough(self):
        self.assertEqual(decrypt_secret('plain-legacy'), 'plain-legacy')

    def test_double_encrypt_noop(self):
        first = encrypt_secret('abc')
        second = encrypt_secret(first)
        self.assertEqual(first, second)

    def test_decrypt_invalid_token_logs_with_exc_info_and_returns_empty(self):
        """Невалідний зашифрований токен логується з деталями та повертає порожній рядок."""
        from unittest.mock import patch
        with patch('workspaces.crypto.logger.error') as mock_log:
            result = decrypt_secret('enc:v1:invalid-token-payload')
            self.assertEqual(result, '')
            mock_log.assert_called_once()
            self.assertIn('decrypt_secret failed', mock_log.call_args[0][0])
            self.assertTrue(mock_log.call_args[1].get('exc_info'))
