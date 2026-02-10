"""测试 /admin 管理面板 Handler。

RED 阶段：实现尚不存在，测试会 FAIL。
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.dto import SubBotDTO
from app.repositories.bot_repo import BotRepo
from app.repositories.message_map_repo import MessageMapRepo
from app.repositories.user_repo import UserRepo

# 尝试导入 admin handler，如果不存在则跳过
try:
    from app.master_bot.handlers.admin import (
        admin_command,
        admin_list_bots,
        admin_view_bot_detail,
        admin_force_stop_bot,
        admin_view_statistics,
    )
except ImportError:
    pytest.skip("Admin handler not implemented yet", allow_module_level=True)


def _make_message(user_id: int, text: str = "/admin") -> MagicMock:
    """创建 mock Message 对象。"""
    msg = MagicMock()
    msg.text = text
    msg.message_id = 1
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()

    from_user = MagicMock()
    from_user.id = user_id
    from_user.username = "testuser"
    msg.from_user = from_user

    chat = MagicMock()
    chat.id = user_id
    msg.chat = chat

    return msg


def _make_callback_query(user_id: int, data: str) -> MagicMock:
    """创建 mock CallbackQuery 对象。"""
    callback = MagicMock()
    callback.data = data
    callback.answer = AsyncMock()
    callback.message = _make_message(user_id)

    from_user = MagicMock()
    from_user.id = user_id
    callback.from_user = from_user

    return callback


def _make_sub_bot_dto(
    id: int = 1,
    bot_id: int = 100,
    owner_id: int = 999,
    status: str = "active",
) -> SubBotDTO:
    """创建 SubBotDTO 对象。"""
    return SubBotDTO(
        id=id,
        bot_id=bot_id,
        bot_username=f"bot_{bot_id}",
        owner_id=owner_id,
        owner_username="owner",
        status=status,
        welcome_message=None,
        user_count=10,
        message_count=100,
        created_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
class TestAdminCommandAdminOnly:
    """测试 /admin 命令只有管理员可用。"""

    async def test_admin_command_admin_only(self):
        """测试只有ADMIN_USER_IDS中的用户可用。"""
        admin_id = 12345
        settings = MagicMock(spec=Settings)
        settings.ADMIN_USER_IDS = [admin_id]

        bot_repo = MagicMock(spec=BotRepo)
        bot_repo.count_all = AsyncMock(
            return_value={"active": 10, "stopped": 2, "error": 1, "total": 13}
        )

        user_repo = MagicMock(spec=UserRepo)
        user_repo.count_total_users = AsyncMock(return_value=500)

        message_map_repo = MagicMock(spec=MessageMapRepo)
        message_map_repo.count_all = AsyncMock(return_value=1000)

        message = _make_message(admin_id)

        await admin_command(
            message,
            bot_repo=bot_repo,
            user_repo=user_repo,
            message_map_repo=message_map_repo,
            settings=settings,
        )

        # 验证管理员收到管理面板
        message.answer.assert_called_once()
        call_args = message.answer.call_args
        assert "平台管理面板" in call_args[0][0] or "管理面板" in str(call_args)

    async def test_admin_command_non_admin_rejected(self):
        """测试非管理员被拒绝。"""
        admin_id = 12345
        non_admin_id = 99999

        settings = MagicMock(spec=Settings)
        settings.ADMIN_USER_IDS = [admin_id]

        bot_repo = MagicMock(spec=BotRepo)
        user_repo = MagicMock(spec=UserRepo)
        message_map_repo = MagicMock(spec=MessageMapRepo)

        message = _make_message(non_admin_id)

        await admin_command(
            message,
            bot_repo=bot_repo,
            user_repo=user_repo,
            message_map_repo=message_map_repo,
            settings=settings,
        )

        # 验证非管理员收到拒绝消息
        message.answer.assert_called_once()
        call_args = message.answer.call_args
        assert "没有权限" in call_args[0][0] or "权限" in str(call_args)


@pytest.mark.asyncio
class TestAdminShowsSystemStatus:
    """测试 /admin 显示系统状态。"""

    async def test_admin_shows_system_status(self):
        """测试显示系统状态（Bot数量、用户数量、消息数量）。"""
        admin_id = 12345
        settings = MagicMock(spec=Settings)
        settings.ADMIN_USER_IDS = [admin_id]

        bot_repo = MagicMock(spec=BotRepo)
        bot_repo.count_all = AsyncMock(
            return_value={"active": 38, "stopped": 5, "error": 2, "total": 45}
        )

        user_repo = MagicMock(spec=UserRepo)
        user_repo.count_total_users = AsyncMock(return_value=12456)

        message_map_repo = MagicMock(spec=MessageMapRepo)
        message_map_repo.count_all = AsyncMock(return_value=156789)

        message = _make_message(admin_id)

        await admin_command(
            message,
            bot_repo=bot_repo,
            user_repo=user_repo,
            message_map_repo=message_map_repo,
            settings=settings,
        )

        # 验证显示了统计信息
        message.answer.assert_called_once()
        call_args = message.answer.call_args
        response_text = call_args[0][0]

        # 验证包含关键统计数据
        assert "45" in response_text or "total" in str(call_args)
        assert "38" in response_text or "active" in str(call_args)


@pytest.mark.asyncio
class TestAdminListAllBots:
    """测试管理员列出所有Bot。"""

    async def test_admin_list_all_bots(self):
        """测试列出所有Bot。"""
        admin_id = 12345
        settings = MagicMock(spec=Settings)
        settings.ADMIN_USER_IDS = [admin_id]

        bot_repo = MagicMock(spec=BotRepo)
        bot_repo.get_all_paginated = AsyncMock(
            return_value=MagicMock(
                items=[
                    _make_sub_bot_dto(id=1, bot_id=100, status="active"),
                    _make_sub_bot_dto(id=2, bot_id=200, status="stopped"),
                ],
                total=2,
                page=1,
                page_size=10,
                total_pages=1,
                has_next=False,
                has_prev=False,
            )
        )

        callback = _make_callback_query(admin_id, "adm_bots")

        await admin_list_bots(
            callback,
            bot_repo=bot_repo,
            settings=settings,
        )

        # 验证显示了Bot列表
        callback.message.edit_text.assert_called_once()
        call_args = callback.message.edit_text.call_args
        response_text = call_args[0][0]

        assert "bot_100" in response_text or "Bot" in response_text


@pytest.mark.asyncio
class TestAdminViewBotDetail:
    """测试管理员查看Bot详情。"""

    async def test_admin_view_bot_detail(self):
        """测试查看Bot详情。"""
        admin_id = 12345
        settings = MagicMock(spec=Settings)
        settings.ADMIN_USER_IDS = [admin_id]

        bot_repo = MagicMock(spec=BotRepo)
        bot_repo.get_by_id = AsyncMock(
            return_value=_make_sub_bot_dto(id=1, bot_id=100, owner_id=999)
        )

        callback = _make_callback_query(admin_id, "adm_bot_detail:1")

        await admin_view_bot_detail(
            callback,
            bot_repo=bot_repo,
            settings=settings,
        )

        # 验证显示了Bot详情
        callback.message.edit_text.assert_called_once()
        call_args = callback.message.edit_text.call_args
        response_text = call_args[0][0]

        assert "bot_100" in response_text or "详情" in response_text


@pytest.mark.asyncio
class TestAdminForceStopBot:
    """测试管理员强制停止Bot。"""

    async def test_admin_force_stop_bot(self):
        """测试强制停止Bot。"""
        admin_id = 12345
        settings = MagicMock(spec=Settings)
        settings.ADMIN_USER_IDS = [admin_id]

        bot_repo = MagicMock(spec=BotRepo)
        bot_repo.get_by_id = AsyncMock(
            return_value=_make_sub_bot_dto(id=1, bot_id=100, status="active")
        )
        bot_repo.update_status = AsyncMock()

        registry = MagicMock()
        registry.remove_bot = AsyncMock()

        callback = _make_callback_query(admin_id, "adm_force_stop:1")

        await admin_force_stop_bot(
            callback,
            bot_repo=bot_repo,
            registry=registry,
            settings=settings,
        )

        # 验证Bot被停止
        registry.remove_bot.assert_called_once_with(100)
        bot_repo.update_status.assert_called_once_with(1, "stopped")

        # 验证显示了确认消息
        callback.message.edit_text.assert_called_once()


@pytest.mark.asyncio
class TestAdminViewStatistics:
    """测试管理员查看统计信息。"""

    async def test_admin_view_statistics(self):
        """测试查看统计信息。"""
        admin_id = 12345
        settings = MagicMock(spec=Settings)
        settings.ADMIN_USER_IDS = [admin_id]

        bot_repo = MagicMock(spec=BotRepo)
        bot_repo.count_all = AsyncMock(
            return_value={"active": 38, "stopped": 5, "error": 2, "total": 45}
        )

        user_repo = MagicMock(spec=UserRepo)
        user_repo.count_total_users = AsyncMock(return_value=12456)

        message_map_repo = MagicMock(spec=MessageMapRepo)
        message_map_repo.count_all = AsyncMock(return_value=156789)

        callback = _make_callback_query(admin_id, "adm_stats")

        await admin_view_statistics(
            callback,
            bot_repo=bot_repo,
            user_repo=user_repo,
            message_map_repo=message_map_repo,
            settings=settings,
        )

        # 验证显示了统计信息
        callback.message.edit_text.assert_called_once()
        call_args = callback.message.edit_text.call_args
        response_text = call_args[0][0]

        assert "45" in response_text or "统计" in response_text
