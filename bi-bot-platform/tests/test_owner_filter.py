"""IsOwnerFilter 单元测试 (TDD RED 阶段)。

测试 IsOwnerFilter 自定义 Filter：
- owner 发消息时返回 True
- 非 owner 发消息时返回 False

这些测试在 IsOwnerFilter 实现之前必须 FAIL。
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.dto import SubBotDTO


def _make_sub_bot_dto(owner_id: int = 999) -> SubBotDTO:
    return SubBotDTO(
        id=1,
        bot_id=100,
        bot_username="test_bot",
        owner_id=owner_id,
        owner_username="owner",
        status="active",
        welcome_message=None,
        user_count=0,
        message_count=0,
        created_at=datetime.utcnow(),
    )


def _make_message(user_id: int) -> MagicMock:
    msg = MagicMock()
    from_user = MagicMock()
    from_user.id = user_id
    msg.from_user = from_user
    return msg


class TestIsOwnerFilter:
    """IsOwnerFilter 应根据 message.from_user.id 是否等于 sub_bot.owner_id 返回结果。"""

    @pytest.mark.asyncio
    async def test_is_owner_filter_returns_true_for_owner(self):
        """owner 发消息时，IsOwnerFilter 应返回 True。"""
        from app.sub_bot.filters import IsOwnerFilter

        filt = IsOwnerFilter(is_owner=True)
        sub_bot = _make_sub_bot_dto(owner_id=999)
        message = _make_message(user_id=999)

        result = await filt(message, sub_bot=sub_bot)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_owner_filter_returns_false_for_non_owner(self):
        """非 owner 发消息时，IsOwnerFilter 应返回 False。"""
        from app.sub_bot.filters import IsOwnerFilter

        filt = IsOwnerFilter(is_owner=True)
        sub_bot = _make_sub_bot_dto(owner_id=999)
        message = _make_message(user_id=555)

        result = await filt(message, sub_bot=sub_bot)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_owner_filter_inverted_returns_true_for_non_owner(self):
        """IsOwnerFilter(is_owner=False) 时，非 owner 发消息应返回 True。"""
        from app.sub_bot.filters import IsOwnerFilter

        filt = IsOwnerFilter(is_owner=False)
        sub_bot = _make_sub_bot_dto(owner_id=999)
        message = _make_message(user_id=555)

        result = await filt(message, sub_bot=sub_bot)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_owner_filter_inverted_returns_false_for_owner(self):
        """IsOwnerFilter(is_owner=False) 时，owner 发消息应返回 False。"""
        from app.sub_bot.filters import IsOwnerFilter

        filt = IsOwnerFilter(is_owner=False)
        sub_bot = _make_sub_bot_dto(owner_id=999)
        message = _make_message(user_id=999)

        result = await filt(message, sub_bot=sub_bot)

        assert result is False
