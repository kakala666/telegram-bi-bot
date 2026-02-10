"""测试 TokenEncryptor 加密/解密。"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.services.token_encryptor import TokenEncryptor


class TestTokenEncryptor:
    """TokenEncryptor 测试。"""

    def test_encrypt_decrypt_roundtrip(self, token_encryptor):
        """测试加密后能正确解密（往返测试）。"""
        plaintext = "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ_abc"

        encrypted = token_encryptor.encrypt(plaintext)
        decrypted = token_encryptor.decrypt(encrypted)

        assert decrypted == plaintext
        assert encrypted != plaintext

    def test_different_key_cannot_decrypt(self, fernet_key):
        """测试不同密钥无法解密。"""
        encryptor1 = TokenEncryptor(fernet_key)
        other_key = Fernet.generate_key().decode()
        encryptor2 = TokenEncryptor(other_key)

        encrypted = encryptor1.encrypt("secret-token")

        with pytest.raises(InvalidToken):
            encryptor2.decrypt(encrypted)

    def test_empty_string(self, token_encryptor):
        """测试空字符串处理。"""
        encrypted = token_encryptor.encrypt("")
        decrypted = token_encryptor.decrypt(encrypted)

        assert decrypted == ""

    def test_encrypt_produces_different_ciphertext(self, token_encryptor):
        """测试同一明文多次加密产生不同密文（Fernet 特性）。"""
        plaintext = "same-token"

        encrypted1 = token_encryptor.encrypt(plaintext)
        encrypted2 = token_encryptor.encrypt(plaintext)

        assert encrypted1 != encrypted2
        assert token_encryptor.decrypt(encrypted1) == plaintext
        assert token_encryptor.decrypt(encrypted2) == plaintext
