"""运行时Bug回归测试。

Bug 1: 子Bot转发不工作
  - TypeError: cmd_start() missing 1 required positional argument: 'sub_bot'
  - BotContextMiddleware 需要正确从 workflow_data 获取 bot_repo
  - BotContextMiddleware 需要正确将 sub_bot 注入到 handler kwargs

Bug 2: 管理员没有广告配置入口
  - /help 文本中应提示管理员可用 /ad 命令
  - 管理面板应有广告管理按钮
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.dto import SubBotDTO
from app.sub_bot.middleware.bot_context import BotContextMiddleware
from app.sub_bot.middleware.error_handler import ErrorHandlerMiddleware


# ── Helpers ──────────────────────────────────────────────────────


def _make_sub_bot_dto(
    *,
    bot_id: int = 12345,
    status: str = "active",
    owner_id: int = 99999,
) -> SubBotDTO:
    """创建测试用 SubBotDTO。"""
    return SubBotDTO(
        id=1,
        bot_id=bot_id,
        bot_username="test_bot",
        owner_id=owner_id,
        owner_username="owner",
        status=status,
        welcome_message=None,
        user_count=0,
        message_count=0,
        created_at=datetime(2025, 1, 1),
    )

def _make_mock_bot(bot_id: int = 12345) -> MagicMock:
    """创建 mock aiogram Bot 对象。"""
    bot = MagicMock()
    bot.id = bot_id
    return bot


def _make_mock_bot_repo(sub_bot_dto: SubBotDTO | None = None) -> MagicMock:
    """创建 mock BotRepo，get_by_bot_id 返回指定 DTO。"""
    repo = MagicMock()
    repo.get_by_bot_id = AsyncMock(return_value=sub_bot_dto)
    return repo


# ══════════════════════════════════════════════════════════════════
# Bug 1: 子Bot转发不工作 - BotContextMiddleware 测试
# ══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestBotContextMiddlewareInjectsSubBot:
    """BotContextMiddleware 应将 sub_bot 注入到 handler data 中。"""

    async def test_bot_context_middleware_injects_sub_bot(self):
        """中间件查询到活跃Bot后，应将 sub_bot 写入 data dict。

        handler 收到的 data 中应包含 sub_bot 键。
        """
        sub_bot = _make_sub_bot_dto()
        bot_repo = _make_mock_bot_repo(sub_bot)
        mock_bot = _make_mock_bot(bot_id=12345)

        captured_data: dict = {}

        async def fake_handler(event, data):
            captured_data.update(data)
            return "ok"

        middleware = BotContextMiddleware()
        event = MagicMock()
        data = {"bot": mock_bot, "bot_repo": bot_repo}

        result = await middleware(fake_handler, event, data)

        assert result == "ok"
        assert "sub_bot" in captured_data, (
            "BotContextMiddleware 未将 sub_bot 注入到 handler data 中"
        )
        assert captured_data["sub_bot"] is sub_bot


@pytest.mark.asyncio
class TestBotContextMiddlewareGetsBotRepoFromWorkflowData:
    """BotContextMiddleware 应能从 data dict（即 workflow_data）获取 bot_repo。"""

    async def test_bot_context_middleware_gets_bot_repo_from_workflow_data(self):
        """当构造时未传入 bot_repo，中间件应从 data['bot_repo'] 获取。

        这模拟了 launcher.py 中 sub_dp.workflow_data 注入 bot_repo 的场景。
        """
        sub_bot = _make_sub_bot_dto()
        bot_repo = _make_mock_bot_repo(sub_bot)
        mock_bot = _make_mock_bot(bot_id=12345)

        captured_data: dict = {}

        async def fake_handler(event, data):
            captured_data.update(data)
            return "ok"

        # 构造时不传 bot_repo，模拟 dispatcher.py 中的用法
        middleware = BotContextMiddleware()
        event = MagicMock()

        # bot_repo 通过 workflow_data 注入到 data 中
        data = {"bot": mock_bot, "bot_repo": bot_repo}

        result = await middleware(fake_handler, event, data)

        assert result == "ok"
        bot_repo.get_by_bot_id.assert_called_once_with(12345)
        assert captured_data.get("sub_bot") is sub_bot

    async def test_middleware_without_bot_repo_still_calls_handler(self):
        """当 bot_repo 完全不可用时，中间件仍应调用 handler（但不注入 sub_bot）。

        这是当前的行为 - handler 被调用但没有 sub_bot，导致 TypeError。
        此测试验证这个有问题的行为确实存在。
        """
        mock_bot = _make_mock_bot()
        handler_called = False

        async def fake_handler(event, data):
            nonlocal handler_called
            handler_called = True
            # 模拟 handler 需要 sub_bot 参数
            if "sub_bot" not in data:
                raise TypeError("missing required argument: 'sub_bot'")
            return "ok"

        middleware = BotContextMiddleware()
        event = MagicMock()
        # 没有 bot_repo 在 data 中
        data = {"bot": mock_bot}

        # 当前行为：中间件跳过注入，handler 抛出 TypeError
        with pytest.raises(TypeError, match="sub_bot"):
            await middleware(fake_handler, event, data)

        assert handler_called is True


@pytest.mark.asyncio
class TestSubBotHandlerReceivesSubBotParam:
    """子Bot handler 应能通过 data dict 收到 sub_bot 参数。"""

    async def test_sub_bot_handler_receives_sub_bot_param(self):
        """模拟完整的中间件链：BotContextMiddleware -> handler。

        验证 handler 函数签名中的 sub_bot 参数能被正确填充。
        """
        sub_bot = _make_sub_bot_dto()
        bot_repo = _make_mock_bot_repo(sub_bot)
        mock_bot = _make_mock_bot(bot_id=12345)

        received_sub_bot = None

        async def fake_start_handler(event, data):
            nonlocal received_sub_bot
            # 模拟 aiogram 从 data 中提取 handler 参数
            received_sub_bot = data.get("sub_bot")
            if received_sub_bot is None:
                raise TypeError(
                    "cmd_start() missing 1 required positional argument: 'sub_bot'"
                )
            return "ok"

        middleware = BotContextMiddleware()
        event = MagicMock()
        data = {"bot": mock_bot, "bot_repo": bot_repo}

        result = await middleware(fake_start_handler, event, data)

        assert result == "ok"
        assert received_sub_bot is sub_bot
        assert received_sub_bot.bot_id == 12345
        assert received_sub_bot.status == "active"


@pytest.mark.asyncio
class TestErrorHandlerDoesNotSwallowMiddlewareErrors:
    """ErrorHandlerMiddleware 不应静默吞掉中间件链中的关键错误。"""

    async def test_error_handler_does_not_swallow_middleware_errors_silently(self):
        """当 handler 因缺少 sub_bot 抛出 TypeError 时，
        ErrorHandlerMiddleware 会捕获并静默返回 None。

        这导致用户发消息后完全没有响应，没有任何错误提示。
        此测试验证这个问题行为：错误被吞掉，用户无感知。

        期望修复后：中间件应该在 bot_repo 不可用时直接返回 None
        （不调用 handler），或者 ErrorHandlerMiddleware 应该给用户
        发送一个友好的错误提示。
        """
        handler_error = TypeError(
            "cmd_start() missing 1 required positional argument: 'sub_bot'"
        )

        async def failing_handler(event, data):
            raise handler_error

        error_mw = ErrorHandlerMiddleware()
        event = MagicMock()
        data = {}

        # 当前行为：ErrorHandlerMiddleware 捕获异常并返回 None
        result = await error_mw(failing_handler, event, data)

        # 验证错误被静默吞掉（返回 None 而不是重新抛出或通知用户）
        assert result is None, (
            "ErrorHandlerMiddleware 应该捕获异常（当前行为），"
            "但理想情况下应该通知用户而不是静默失败"
        )


# ══════════════════════════════════════════════════════════════════
# Bug 2: 管理员没有广告配置入口
# ══════════════════════════════════════════════════════════════════


class TestHelpTextMentionsAdCommand:
    """HELP_TEXT 应为管理员提示 /ad 命令。"""

    def test_help_text_mentions_ad_command_for_admin(self):
        """管理员应能从 /help 输出中得知 /ad 命令的存在。

        当前 HELP_TEXT 只列出了 /register, /mybot, /broadcast, /block，
        没有提到 /ad 或 /admin 命令。管理员无法发现广告管理功能。
        """
        from app.master_bot.handlers.start import HELP_TEXT

        # 检查 HELP_TEXT 中是否提到了广告相关命令
        has_ad_mention = "/ad" in HELP_TEXT or "广告" in HELP_TEXT
        has_admin_mention = "/admin" in HELP_TEXT or "管理面板" in HELP_TEXT

        assert has_ad_mention or has_admin_mention, (
            "HELP_TEXT 中未提及 /ad 或 /admin 命令，"
            "管理员无法发现广告管理和管理面板功能"
        )


class TestAdminPanelHasAdManagementButton:
    """管理面板应包含广告管理入口按钮。"""

    def test_admin_panel_has_ad_management_button(self):
        """管理面板键盘中应有 '广告管理' 按钮，callback_data 为 'ad_list'。"""
        from app.master_bot.handlers.admin import _admin_panel_keyboard

        keyboard = _admin_panel_keyboard()
        all_buttons = [
            btn
            for row in keyboard.inline_keyboard
            for btn in row
        ]

        button_texts = [btn.text for btn in all_buttons]
        button_callbacks = [btn.callback_data for btn in all_buttons]

        assert "广告管理" in button_texts, (
            "管理面板键盘中缺少 '广告管理' 按钮"
        )
        assert "ad_list" in button_callbacks, (
            "管理面板键盘中缺少 callback_data='ad_list' 的按钮"
        )
