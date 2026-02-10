"""测试 BotRegistry。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import RegistryError
from app.sub_bot.registry import BotRegistry


def _make_mock_dispatcher() -> MagicMock:
    """创建 mock Dispatcher。"""
    dp = MagicMock()
    dp.start_polling = AsyncMock()
    return dp


def _make_mock_bot_repo() -> MagicMock:
    """创建 mock BotRepo。"""
    repo = MagicMock()
    repo.get_all_active = AsyncMock(return_value=[])
    repo.get_encrypted_token = AsyncMock(return_value=None)
    repo.update_status = AsyncMock()
    return repo


def _make_mock_encryptor() -> MagicMock:
    """创建 mock TokenEncryptor。"""
    enc = MagicMock()
    enc.decrypt = MagicMock(return_value="decrypted_token")
    return enc


def _make_mock_get_me(bot_id: int = 12345, username: str = "test_bot"):
    """创建 mock Bot.get_me 返回值。"""
    me = MagicMock()
    me.id = bot_id
    me.username = username
    return me


@pytest.mark.asyncio
class TestBotRegistryAddBot:
    """BotRegistry.add_bot 测试。"""

    async def test_add_bot_success(self):
        """测试成功添加 Bot。"""
        dp = _make_mock_dispatcher()
        bot_repo = _make_mock_bot_repo()
        enc = _make_mock_encryptor()
        registry = BotRegistry(dp, bot_repo, enc)

        with patch("app.sub_bot.registry.Bot") as MockBot:
            mock_bot = MagicMock()
            mock_bot.get_me = AsyncMock(return_value=_make_mock_get_me(12345))
            mock_bot.session = MagicMock()
            mock_bot.session.close = AsyncMock()
            MockBot.return_value = mock_bot

            await registry.add_bot("token123", 12345)

        assert registry.is_running(12345) is True
        assert registry.count_running() == 1
        assert registry.get_bot(12345) is mock_bot

    async def test_add_bot_id_mismatch_raises(self):
        """测试 bot_id 不匹配时抛出 RegistryError。"""
        dp = _make_mock_dispatcher()
        registry = BotRegistry(dp, _make_mock_bot_repo(), _make_mock_encryptor())

        with patch("app.sub_bot.registry.Bot") as MockBot:
            mock_bot = MagicMock()
            mock_bot.get_me = AsyncMock(return_value=_make_mock_get_me(99999))
            mock_bot.session = MagicMock()
            mock_bot.session.close = AsyncMock()
            MockBot.return_value = mock_bot

            with pytest.raises(RegistryError, match="不匹配"):
                await registry.add_bot("token123", 12345)

    async def test_add_bot_api_failure_raises(self):
        """测试 API 调用失败时抛出 RegistryError。"""
        dp = _make_mock_dispatcher()
        registry = BotRegistry(dp, _make_mock_bot_repo(), _make_mock_encryptor())

        with patch("app.sub_bot.registry.Bot") as MockBot:
            mock_bot = MagicMock()
            mock_bot.get_me = AsyncMock(side_effect=Exception("Network error"))
            mock_bot.session = MagicMock()
            mock_bot.session.close = AsyncMock()
            MockBot.return_value = mock_bot

            with pytest.raises(RegistryError, match="创建Bot实例失败"):
                await registry.add_bot("token123", 12345)


@pytest.mark.asyncio
class TestBotRegistryRemoveBot:
    """BotRegistry.remove_bot 测试。"""

    async def test_remove_existing_bot(self):
        """测试移除已存在的 Bot。"""
        dp = _make_mock_dispatcher()
        registry = BotRegistry(dp, _make_mock_bot_repo(), _make_mock_encryptor())

        mock_bot = MagicMock()
        mock_bot.session = MagicMock()
        mock_bot.session.close = AsyncMock()
        registry._bots[12345] = mock_bot

        await registry.remove_bot(12345)

        assert registry.is_running(12345) is False
        assert registry.count_running() == 0
        mock_bot.session.close.assert_called_once()

    async def test_remove_nonexistent_bot(self):
        """测试移除不存在的 Bot（不报错）。"""
        dp = _make_mock_dispatcher()
        registry = BotRegistry(dp, _make_mock_bot_repo(), _make_mock_encryptor())

        await registry.remove_bot(99999)

        assert registry.count_running() == 0


@pytest.mark.asyncio
class TestBotRegistryGetBot:
    """BotRegistry.get_bot 测试。"""

    async def test_get_existing_bot(self):
        """测试获取已存在的 Bot 实例。"""
        registry = BotRegistry(
            _make_mock_dispatcher(), _make_mock_bot_repo(), _make_mock_encryptor()
        )
        mock_bot = MagicMock()
        registry._bots[12345] = mock_bot

        assert registry.get_bot(12345) is mock_bot

    async def test_get_nonexistent_bot(self):
        """测试获取不存在的 Bot 返回 None。"""
        registry = BotRegistry(
            _make_mock_dispatcher(), _make_mock_bot_repo(), _make_mock_encryptor()
        )

        assert registry.get_bot(99999) is None


@pytest.mark.asyncio
class TestBotRegistryState:
    """BotRegistry 状态查询方法测试。"""

    async def test_is_running(self):
        """测试 is_running。"""
        registry = BotRegistry(
            _make_mock_dispatcher(), _make_mock_bot_repo(), _make_mock_encryptor()
        )
        registry._bots[111] = MagicMock()

        assert registry.is_running(111) is True
        assert registry.is_running(222) is False

    async def test_count_running(self):
        """测试 count_running。"""
        registry = BotRegistry(
            _make_mock_dispatcher(), _make_mock_bot_repo(), _make_mock_encryptor()
        )
        registry._bots[111] = MagicMock()
        registry._bots[222] = MagicMock()

        assert registry.count_running() == 2

    async def test_get_all_bot_ids(self):
        """测试 get_all_bot_ids。"""
        registry = BotRegistry(
            _make_mock_dispatcher(), _make_mock_bot_repo(), _make_mock_encryptor()
        )
        registry._bots[111] = MagicMock()
        registry._bots[222] = MagicMock()

        ids = registry.get_all_bot_ids()
        assert set(ids) == {111, 222}


@pytest.mark.asyncio
class TestBotRegistryShutdown:
    """BotRegistry.shutdown 测试。"""

    async def test_shutdown_closes_all(self):
        """测试 shutdown 关闭所有 Bot。"""
        registry = BotRegistry(
            _make_mock_dispatcher(), _make_mock_bot_repo(), _make_mock_encryptor()
        )

        bot1 = MagicMock()
        bot1.session = MagicMock()
        bot1.session.close = AsyncMock()
        bot2 = MagicMock()
        bot2.session = MagicMock()
        bot2.session.close = AsyncMock()

        registry._bots[111] = bot1
        registry._bots[222] = bot2

        await registry.shutdown()

        assert registry.count_running() == 0
        bot1.session.close.assert_called_once()
        bot2.session.close.assert_called_once()
