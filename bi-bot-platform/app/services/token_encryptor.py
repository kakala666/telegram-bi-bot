from cryptography.fernet import Fernet


class TokenEncryptor:
    """Token 加密/解密工具，使用 Fernet 对称加密"""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> str:
        """加密，返回密文字符串"""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """解密，返回明文字符串

        Raises:
            cryptography.fernet.InvalidToken: 密钥不匹配或数据损坏
        """
        return self._fernet.decrypt(ciphertext.encode()).decode()
