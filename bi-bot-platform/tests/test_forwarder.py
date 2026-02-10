"""测试 ForwarderService。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from app.dto import AdInjectionResult, BotUserDTO, ForwardResult, SubBotDTO
from app.repositories.bot_repo import BotRepo
from app.repositories.message_map_repo import MessageMapRepo
from app.repositories.user_repo import UserRepo
from app.services.ad_injector import AdInjectorService
from app.services.forwarder import ForwarderService


def _make_sub_bot_dto(
    id: int = 1,
    bot_id: int = 100,
    owner_id: int = 999,
) -> SubBotDTO:
    return SubBotDTO(
        id=id,
        bot_id=bot_id,
        bot_username="test_bot",
        owner_id=owner_id,
        owner_username=None,
        status="active",
        welcome_message=None,
        user_count=0,
        message_count=0,
        created_at=datetime.utcnow(),
    )


def _make_bot_user_dto(
    user_id: int = 555,
    username: str | None = "alice",
    display_name: str = "Alice Smith",
    is_blocked: bool = False,
) -> BotUserDTO:
    return BotUserDTO(
        id=1,
        sub_bot_id=1,
        user_id=user_id,
        username=username,
        display_name=display_name,
        is_blocked=is_blocked,
        is_banned_by_telegram=False,
        first_seen=datetime.utcnow(),
        last_active=datetime.utcnow(),
    )


def _make_message(
    user_id: int = 555,
    username: str = "alice",
    text: str = "Hello",
    message_id: int = 10,
    reply_to: MagicMock | None = None,
) -> MagicMock:
    """创建 mock Message 对象。"""
    msg = MagicMock()
    msg.message_id = message_id
    msg.text = text
    msg.caption = None
    msg.photo = None
    msg.video = None
    msg.document = None
    msg.audio = None
    msg.voice = None
    msg.sticker = None
    msg.chat = MagicMock()
    msg.chat.id = user_id
    msg.reply_to_message = reply_to

    from_user = MagicMock()
    from_user.id = user_id
    from_user.username = username
    from_user.first_name = "Alice"
    from_user.last_name = "Smith"
    msg.from_user = from_user

    return msg


class TestBuildUserHeader:
    """ForwarderService._build_user_header 测试。"""

    def test_header_with_username(self):
        """测试有 username 时的格式。"""
        user_repo = MagicMock()
        msg_map_repo = MagicMock()
        bot_repo = MagicMock()
        ad_injector = MagicMock()
        svc = ForwarderService(user_repo, msg_map_repo, bot_repo, ad_injector)

        user = _make_bot_user_dto(user_id=555, username="alice", display_name="Alice Smith")
        header = svc._build_user_header(user)

        assert "Alice Smith" in header
        assert "@alice" in header
        assert "ID:555" in header

    def test_header_without_username(self):
        """测试无 username 时的格式。"""
        svc = ForwarderService(MagicMock(), MagicMock(), MagicMock(), MagicMock())

        user = _make_bot_user_dto(user_id=666, username=None, display_name="Bob")
        header = svc._build_user_header(user)

        assert "Bob" in header
        assert "@" not in header
        assert "ID:666" in header


@pytest.mark.asyncio
class TestForwardToOwnerBlocked:
    """forward_to_owner 封禁用户被拒绝。"""

    async def test_blocked_user_rejected(self):
        """测试封禁用户消息被拒绝。"""
        blocked_user = _make_bot_user_dto(is_blocked=True)

        user_repo = MagicMock()
        user_repo.get_or_create = AsyncMock(return_value=(blocked_user, False))
        user_repo.update_last_active = AsyncMock()

        bot_repo = MagicMock()
        bot_repo.increment_user_count = AsyncMock()
        bot_repo.increment_message_count = AsyncMock()

        msg_map_repo = MagicMock()
        ad_injector = MagicMock()

        svc = ForwarderService(user_repo, msg_map_repo, bot_repo, ad_injector)

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        sub_bot = _make_sub_bot_dto()
        message = _make_message()

        result = await svc.forward_to_owner(mock_bot, sub_bot, message)

        assert result.success is False
        assert result.error == "blocked"
        mock_bot.send_message.assert_called_once()


@pytest.mark.asyncio
class TestReplyToUserNoMapping:
    """reply_to_user 找不到映射时返回错误。"""

    async def test_no_reply_message(self):
        """测试主人未回复任何消息时返回 no_reply。"""
        svc = ForwarderService(MagicMock(), MagicMock(), MagicMock(), MagicMock())

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        sub_bot = _make_sub_bot_dto()
        message = _make_message(reply_to=None)

        result = await svc.reply_to_user(mock_bot, sub_bot, message)

        assert result.success is False
        assert result.error == "no_reply"

    async def test_no_mapping_found(self):
        """测试找不到消息映射时返回 no_mapping。"""
        msg_map_repo = MagicMock()
        msg_map_repo.get_by_forwarded_msg = AsyncMock(return_value=None)

        svc = ForwarderService(MagicMock(), msg_map_repo, MagicMock(), MagicMock())

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        sub_bot = _make_sub_bot_dto()
        reply_msg = MagicMock()
        reply_msg.message_id = 50
        message = _make_message(reply_to=reply_msg)

        result = await svc.reply_to_user(mock_bot, sub_bot, message)

        assert result.success is False
        assert result.error == "no_mapping"
        mock_bot.send_message.assert_called_once()


@pytest.mark.asyncio
class TestForwardToOwnerSuccess:
    """forward_to_owner 成功场景。"""

    async def test_new_user_increments_count(self):
        """测试新用户时递增用户计数。"""
        normal_user = _make_bot_user_dto(is_blocked=False)

        user_repo = MagicMock()
        user_repo.get_or_create = AsyncMock(return_value=(normal_user, True))
        user_repo.update_last_active = AsyncMock()

        bot_repo = MagicMock()
        bot_repo.increment_user_count = AsyncMock()
        bot_repo.increment_message_count = AsyncMock()

        msg_map_repo = MagicMock()
        msg_map_repo.create = AsyncMock()

        ad_injector = MagicMock()

        svc = ForwarderService(user_repo, msg_map_repo, bot_repo, ad_injector)

        sent_msg = MagicMock()
        sent_msg.message_id = 100

        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=sent_msg)

        sub_bot = _make_sub_bot_dto()
        message = _make_message()

        result = await svc.forward_to_owner(mock_bot, sub_bot, message)

        assert result.success is True
        assert result.forwarded_msg_id == 100
        bot_repo.increment_user_count.assert_called_once_with(sub_bot.id)
        bot_repo.increment_message_count.assert_called_once_with(sub_bot.id)
        msg_map_repo.create.assert_called_once()
