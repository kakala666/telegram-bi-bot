"""测试 TokenValidatorService。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.dto import BotInfo
from app.exceptions import (
    TokenDuplicateError,
    TokenFormatError,
    TokenInvalidError,
    TokenLimitError,
)
from app.repositories.bot_repo import BotRepo
from app.services.token_encryptor import TokenEncryptor
from app.services.token_validator import TokenValidatorService


@pytest.mark.asyncio
class TestValidateFormat:
    """TokenValidatorService.validate_format 测试。"""

    def _make_service(self, bot_repo, token_encryptor):
        return TokenValidatorService(bot_repo, token_encryptor)

    def test_valid_format(self, bot_repo, token_encryptor):
        """测试正确格式的 Token。"""
        svc = self._make_service(bot_repo, token_encryptor)
        # 8-10 位数字 + : + 35 位字母数字下划线横线
        assert svc.validate_format("12345678:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi") is True

    def test_valid_format_10_digits(self, bot_repo, token_encryptor):
        """测试 10 位数字前缀。"""
        svc = self._make_service(bot_repo, token_encryptor)
        assert svc.validate_format("1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi") is True

    def test_invalid_format_short_digits(self, bot_repo, token_encryptor):
        """测试数字部分过短。"""
        svc = self._make_service(bot_repo, token_encryptor)
        assert svc.validate_format("1234567:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi") is False

    def test_invalid_format_no_colon(self, bot_repo, token_encryptor):
        """测试缺少冒号。"""
        svc = self._make_service(bot_repo, token_encryptor)
        assert svc.validate_format("12345678ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi") is False

    def test_invalid_format_short_suffix(self, bot_repo, token_encryptor):
        """测试后缀过短。"""
        svc = self._make_service(bot_repo, token_encryptor)
        assert svc.validate_format("12345678:SHORT") is False

    def test_invalid_format_empty(self, bot_repo, token_encryptor):
        """测试空字符串。"""
        svc = self._make_service(bot_repo, token_encryptor)
        assert svc.validate_format("") is False


@pytest.mark.asyncio
class TestCheckDuplicate:
    """TokenValidatorService.check_duplicate 测试。"""

    async def test_check_duplicate_exists(self, bot_repo, token_encryptor):
        """测试已注册的 bot_id。"""
        await bot_repo.create("tok", 99001, "b1", 1, None)
        svc = TokenValidatorService(bot_repo, token_encryptor)

        assert await svc.check_duplicate(99001) is True

    async def test_check_duplicate_not_exists(self, bot_repo, token_encryptor):
        """测试未注册的 bot_id。"""
        svc = TokenValidatorService(bot_repo, token_encryptor)

        assert await svc.check_duplicate(99999) is False


@pytest.mark.asyncio
class TestEncryptDecrypt:
    """TokenValidatorService encrypt/decrypt 往返测试。"""

    async def test_encrypt_decrypt_roundtrip(self, bot_repo, token_encryptor):
        """测试加密后能正确解密。"""
        svc = TokenValidatorService(bot_repo, token_encryptor)
        token = "12345678:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"

        encrypted = svc.encrypt_token(token)
        decrypted = svc.decrypt_token(encrypted)

        assert decrypted == token
        assert encrypted != token


@pytest.mark.asyncio
class TestCheckOwnerLimit:
    """TokenValidatorService.check_owner_limit 测试。"""

    async def test_under_limit(self, bot_repo, token_encryptor):
        """测试未超出限制。"""
        svc = TokenValidatorService(bot_repo, token_encryptor)
        await svc.check_owner_limit(owner_id=1, max_bots=3)

    async def test_at_limit_raises(self, bot_repo, token_encryptor):
        """测试达到限制时抛出异常。"""
        await bot_repo.create("t1", 88001, "b1", 1, None)
        await bot_repo.create("t2", 88002, "b2", 1, None)
        await bot_repo.create("t3", 88003, "b3", 1, None)
        svc = TokenValidatorService(bot_repo, token_encryptor)

        with pytest.raises(TokenLimitError):
            await svc.check_owner_limit(owner_id=1, max_bots=3)


VALID_TOKEN = "12345678:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"


def _mock_bot_get_me(bot_id: int = 12345678, username: str = "test_bot"):
    """创建 mock 的 Bot.get_me 返回值。"""
    me = MagicMock()
    me.id = bot_id
    me.username = username
    me.first_name = "TestBot"
    return me


@pytest.mark.asyncio
class TestFullValidate:
    """TokenValidatorService.full_validate 测试。"""

    async def test_format_error(self, bot_repo, token_encryptor):
        """测试格式错误时抛出 TokenFormatError。"""
        svc = TokenValidatorService(bot_repo, token_encryptor)

        with pytest.raises(TokenFormatError):
            await svc.full_validate("bad-token", owner_id=1, max_bots=3)

    async def test_limit_error(self, bot_repo, token_encryptor):
        """测试超出限制时抛出 TokenLimitError。"""
        await bot_repo.create("t1", 77001, "b1", 1, None)
        await bot_repo.create("t2", 77002, "b2", 1, None)
        await bot_repo.create("t3", 77003, "b3", 1, None)
        svc = TokenValidatorService(bot_repo, token_encryptor)

        with pytest.raises(TokenLimitError):
            await svc.full_validate(VALID_TOKEN, owner_id=1, max_bots=3)

    async def test_api_invalid_error(self, bot_repo, token_encryptor):
        """测试 API 验证失败时抛出 TokenInvalidError。"""
        svc = TokenValidatorService(bot_repo, token_encryptor)

        with patch("app.services.token_validator.Bot") as MockBot:
            mock_bot_instance = MagicMock()
            mock_bot_instance.get_me = AsyncMock(side_effect=Exception("Unauthorized"))
            mock_bot_instance.session = MagicMock()
            mock_bot_instance.session.close = AsyncMock()
            MockBot.return_value = mock_bot_instance

            with pytest.raises(TokenInvalidError):
                await svc.full_validate(VALID_TOKEN, owner_id=1, max_bots=3)

    async def test_duplicate_error_same_owner(self, bot_repo, token_encryptor):
        """测试同一用户重复注册时抛出 TokenDuplicateError。"""
        await bot_repo.create("t1", 12345678, "test_bot", 1, None)
        svc = TokenValidatorService(bot_repo, token_encryptor)

        with patch("app.services.token_validator.Bot") as MockBot:
            mock_bot_instance = MagicMock()
            mock_bot_instance.get_me = AsyncMock(
                return_value=_mock_bot_get_me(12345678, "test_bot")
            )
            mock_bot_instance.session = MagicMock()
            mock_bot_instance.session.close = AsyncMock()
            MockBot.return_value = mock_bot_instance

            with pytest.raises(TokenDuplicateError, match="你已注册"):
                await svc.full_validate(VALID_TOKEN, owner_id=1, max_bots=3)

    async def test_duplicate_error_other_owner(self, bot_repo, token_encryptor):
        """测试其他用户已注册时抛出 TokenDuplicateError。"""
        await bot_repo.create("t1", 12345678, "test_bot", 999, None)
        svc = TokenValidatorService(bot_repo, token_encryptor)

        with patch("app.services.token_validator.Bot") as MockBot:
            mock_bot_instance = MagicMock()
            mock_bot_instance.get_me = AsyncMock(
                return_value=_mock_bot_get_me(12345678, "test_bot")
            )
            mock_bot_instance.session = MagicMock()
            mock_bot_instance.session.close = AsyncMock()
            MockBot.return_value = mock_bot_instance

            with pytest.raises(TokenDuplicateError, match="其他用户"):
                await svc.full_validate(VALID_TOKEN, owner_id=1, max_bots=3)

    async def test_success(self, bot_repo, token_encryptor):
        """测试完整验证成功。"""
        svc = TokenValidatorService(bot_repo, token_encryptor)

        with patch("app.services.token_validator.Bot") as MockBot:
            mock_bot_instance = MagicMock()
            mock_bot_instance.get_me = AsyncMock(
                return_value=_mock_bot_get_me(12345678, "new_bot")
            )
            mock_bot_instance.session = MagicMock()
            mock_bot_instance.session.close = AsyncMock()
            MockBot.return_value = mock_bot_instance

            result = await svc.full_validate(VALID_TOKEN, owner_id=1, max_bots=3)

            assert isinstance(result, BotInfo)
            assert result.bot_id == 12345678
            assert result.username == "new_bot"
