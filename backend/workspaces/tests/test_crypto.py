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
