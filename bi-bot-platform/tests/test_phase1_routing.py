"""Phase 1: 路由重排与回归验证测试 (TDD RED 阶段)。

验证中间件从 inner middleware 改为 outer middleware 的正确性：

核心问题：
当前 dispatcher.py 使用 .middleware()（inner middleware）注册中间件，
aiogram 3.x 中 inner middleware 在 Filter 之后执行。
IsOwnerFilter 依赖 sub_bot 参数（由 BotContextMiddleware 注入），
但 Filter 运行时 BotContextMiddleware 尚未执行 → sub_bot 不存在 → TypeError。

正确架构：
    ErrorHandlerMiddleware (outer, 外层)
      -> BotContextMiddleware (outer, 内层，注入 sub_bot)
        -> Filter (IsOwnerFilter，此时 sub_bot 可用)
          -> inner middleware（如有）
            -> handler

这些测试在当前代码上必须 FAIL，因为当前代码使用 inner middleware。
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.dto import ForwardResult, SubBotDTO
from app.sub_bot.middleware.bot_context import BotContextMiddleware
from app.sub_bot.middleware.error_handler import ErrorHandlerMiddleware


# ── 公共 fixtures ──────────────────────────────────────────


def _make_sub_bot_dto(owner_id: int = 999, status: str = "active") -> SubBotDTO:
    return SubBotDTO(
        id=1,
        bot_id=100,
        bot_username="test_bot",
        owner_id=owner_id,
        owner_username="owner",
        status=status,
        welcome_message=None,
        user_count=0,
        message_count=0,
        created_at=datetime.utcnow(),
    )


def _make_message(
    user_id: int,
    username: str = "testuser",
    text: str = "Hello",
    message_id: int = 10,
) -> MagicMock:
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
    msg.reply_to_message = None

    from_user = MagicMock()
    from_user.id = user_id
    from_user.username = username
    from_user.first_name = "Test"
    from_user.last_name = "User"
    msg.from_user = from_user

    return msg


# ══════════════════════════════════════════════════════════════
# 中间件注册方式测试
# ══════════════════════════════════════════════════════════════


class TestMiddlewareRegistrationType:
    """验证中间件通过 outer_middleware() 注册，而非 inner middleware()。

    aiogram 3.x 执行顺序：
        outer middleware -> Filter -> inner middleware -> handler

    BotContextMiddleware 必须在 Filter 之前执行才能注入 sub_bot，
    因此必须注册为 outer middleware。
    """

    def test_bot_context_is_outer_middleware(self):
        """BotContextMiddleware 应通过 outer_middleware() 注册，不是 inner middleware。

        当前状态（dispatcher.py）：
            sub_router.message.middleware(_bot_context_mw)  # inner middleware

        期望状态：
            sub_router.message.outer_middleware(_bot_context_mw)  # outer middleware
        """
        from app.sub_bot.dispatcher import sub_router

        outer_mw_types = [type(mw) for mw in sub_router.message.outer_middleware]
        inner_mw_types = [type(mw) for mw in sub_router.message.middleware]

        assert BotContextMiddleware in outer_mw_types, (
            f"BotContextMiddleware 应注册为 outer middleware，"
            f"当前 outer: {[t.__name__ for t in outer_mw_types]}，"
            f"inner: {[t.__name__ for t in inner_mw_types]}。"
            f"inner middleware 在 Filter 之后执行，无法为 IsOwnerFilter 注入 sub_bot。"
        )

    def test_error_handler_is_outer_middleware(self):
        """ErrorHandlerMiddleware 应通过 outer_middleware() 注册。

        ErrorHandlerMiddleware 需要在 BotContextMiddleware 外层（更早执行），
        才能捕获 BotContextMiddleware 的异常。两者都应为 outer middleware。
        """
        from app.sub_bot.dispatcher import sub_router

        outer_mw_types = [type(mw) for mw in sub_router.message.outer_middleware]
        inner_mw_types = [type(mw) for mw in sub_router.message.middleware]

        assert ErrorHandlerMiddleware in outer_mw_types, (
            f"ErrorHandlerMiddleware 应注册为 outer middleware，"
            f"当前 outer: {[t.__name__ for t in outer_mw_types]}，"
            f"inner: {[t.__name__ for t in inner_mw_types]}。"
        )

    def test_error_handler_wraps_bot_context(self):
        """ErrorHandlerMiddleware 应在 BotContextMiddleware 外层。

        outer middleware 中，先注册的在外层（洋葱模型）。
        ErrorHandlerMiddleware 应先注册，才能捕获 BotContextMiddleware 的异常。
        """
        from app.sub_bot.dispatcher import sub_router

        outer_mw_types = [type(mw) for mw in sub_router.message.outer_middleware]

        if ErrorHandlerMiddleware not in outer_mw_types:
            pytest.fail(
                "ErrorHandlerMiddleware 未注册为 outer middleware，"
                "无法检验层级顺序（前置测试应先 fail）"
            )
        if BotContextMiddleware not in outer_mw_types:
            pytest.fail(
                "BotContextMiddleware 未注册为 outer middleware，"
                "无法检验层级顺序（前置测试应先 fail）"
            )

        error_idx = outer_mw_types.index(ErrorHandlerMiddleware)
        context_idx = outer_mw_types.index(BotContextMiddleware)

        assert error_idx < context_idx, (
            f"ErrorHandlerMiddleware (index={error_idx}) 应在 "
            f"BotContextMiddleware (index={context_idx}) 之前注册（外层），"
            "先注册的 outer middleware 在外层执行。"
        )

    def test_no_inner_middlewares_for_message(self):
        """message 不应有 inner middleware（所有中间件都在 outer 层）。

        当前状态：两个中间件都注册为 inner middleware。
        修复后：inner middleware 列表应为空。
        """
        from app.sub_bot.dispatcher import sub_router

        inner_middlewares = list(sub_router.message.middleware)

        assert len(inner_middlewares) == 0, (
            f"message 不应有 inner middleware，"
            f"当前 inner: {[type(mw).__name__ for mw in inner_middlewares]}。"
            f"所有中间件应迁移到 outer middleware 层。"
        )

    def test_callback_query_has_both_outer_middlewares(self):
        """callback_query 也应注册两个 outer middleware。

        callback_query 和 message 使用相同的中间件链。
        """
        from app.sub_bot.dispatcher import sub_router

        outer_mw_types = [
            type(mw) for mw in sub_router.callback_query.outer_middleware
        ]

        assert ErrorHandlerMiddleware in outer_mw_types, (
            f"callback_query 缺少 outer ErrorHandlerMiddleware，"
            f"当前 outer: {[t.__name__ for t in outer_mw_types]}"
        )
        assert BotContextMiddleware in outer_mw_types, (
            f"callback_query 缺少 outer BotContextMiddleware，"
            f"当前 outer: {[t.__name__ for t in outer_mw_types]}"
        )


# ══════════════════════════════════════════════════════════════
# Filter 与中间件集成测试
# ══════════════════════════════════════════════════════════════


class TestFilterMiddlewareIntegration:
    """验证 IsOwnerFilter 在 Filter 阶段能获取到 sub_bot。

    核心验证：outer middleware 在 Filter 之前注入 sub_bot，
    使 IsOwnerFilter 不会因缺少 sub_bot 而抛 TypeError。
    """

    @pytest.mark.asyncio
    async def test_filter_receives_sub_bot_from_outer_middleware(self):
        """IsOwnerFilter 在 Filter 阶段能通过 data 获取到 sub_bot。

        模拟完整调用链：outer middleware 注入 sub_bot -> Filter 使用 sub_bot。
        如果中间件是 inner middleware，Filter 在中间件之前执行，sub_bot 不存在。

        此测试验证端到端行为：BotContextMiddleware 作为 outer middleware
        将 sub_bot 注入 data 后，IsOwnerFilter 能正常工作。
        """
        from app.sub_bot.filters import IsOwnerFilter

        sub_bot = _make_sub_bot_dto(owner_id=999)
        bot_repo = AsyncMock()
        bot_repo.get_by_bot_id = AsyncMock(return_value=sub_bot)

        mock_bot = MagicMock()
        mock_bot.id = 100

        message = _make_message(user_id=999)

        # 模拟 outer middleware 注入 sub_bot 的行为
        bot_context_mw = BotContextMiddleware()

        captured_data = {}

        async def fake_handler(event, data):
            captured_data.update(data)
            return None

        data = {"bot": mock_bot, "bot_repo": bot_repo}
        await bot_context_mw(fake_handler, message, data)

        # 验证 sub_bot 被注入到 data 中
        assert "sub_bot" in captured_data, (
            "BotContextMiddleware 应将 sub_bot 注入到 data 中"
        )

        # 验证 IsOwnerFilter 能使用注入的 sub_bot
        filt = IsOwnerFilter(is_owner=True)
        result = await filt(message, sub_bot=captured_data["sub_bot"])
        assert result is True, (
            "IsOwnerFilter 应能使用 outer middleware 注入的 sub_bot"
        )

        # 关键验证：当前代码中中间件注册为 inner，
        # 意味着真实运行时 Filter 先于中间件执行，sub_bot 不在 data 中。
        # 验证 dispatcher 中确实注册为 outer middleware。
        from app.sub_bot.dispatcher import sub_router

        outer_mw_types = [type(mw) for mw in sub_router.message.outer_middleware]
        assert BotContextMiddleware in outer_mw_types, (
            "BotContextMiddleware 必须注册为 outer middleware，"
            "否则 Filter 阶段 sub_bot 不可用，IsOwnerFilter 会抛 TypeError"
        )


# ══════════════════════════════════════════════════════════════
# 回归验证矩阵
# ══════════════════════════════════════════════════════════════


class TestRegressionMatrix:
    """端到端回归验证：验证 owner/user 路由分流在 outer middleware 架构下正常工作。

    这些测试直接调用 handler 函数（绕过 dispatcher），验证业务逻辑正确性。
    同时验证 dispatcher 中间件注册方式正确（outer 而非 inner）。
    """

    @pytest.mark.asyncio
    async def test_scenario_a_user_message_triggers_forward(self):
        """场景 A: 普通用户发消息 -> forward_to_owner 被调用。"""
        from app.sub_bot.handlers.user_message import handle_user_message

        sub_bot = _make_sub_bot_dto(owner_id=999)
        message = _make_message(user_id=555, username="normal_user")
        mock_bot = MagicMock()
        forwarder = AsyncMock()
        forwarder.forward_to_owner = AsyncMock(
            return_value=ForwardResult(success=True, forwarded_msg_id=42, error=None)
        )

        await handle_user_message(
            message=message,
            bot=mock_bot,
            sub_bot=sub_bot,
            forwarder=forwarder,
        )

        forwarder.forward_to_owner.assert_called_once_with(mock_bot, sub_bot, message)

    @pytest.mark.asyncio
    async def test_scenario_b_owner_message_triggers_reply(self):
        """场景 B: 主人发消息 -> reply_to_user 被调用。"""
        from app.sub_bot.handlers.owner_reply import handle_owner_message

        sub_bot = _make_sub_bot_dto(owner_id=999)
        message = _make_message(user_id=999, username="owner")
        mock_bot = MagicMock()
        forwarder = AsyncMock()
        forwarder.reply_to_user = AsyncMock(
            return_value=ForwardResult(success=True, forwarded_msg_id=43, error=None)
        )

        await handle_owner_message(
            message=message,
            bot=mock_bot,
            sub_bot=sub_bot,
            forwarder=forwarder,
        )

        forwarder.reply_to_user.assert_called_once_with(mock_bot, sub_bot, message)

    @pytest.mark.asyncio
    async def test_scenario_c_unknown_bot_short_circuits(self):
        """场景 C: 未知 bot -> 中间件短路，handler 不执行。"""
        bot_repo = AsyncMock()
        bot_repo.get_by_bot_id = AsyncMock(return_value=None)

        mock_bot = MagicMock()
        mock_bot.id = 999

        mw = BotContextMiddleware()
        handler = AsyncMock()
        message = _make_message(user_id=555)

        result = await mw(handler, message, {"bot": mock_bot, "bot_repo": bot_repo})

        assert result is None, "未知 bot 应返回 None（短路）"
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_scenario_c_inactive_bot_short_circuits(self):
        """场景 C: 停用 bot -> 中间件短路，handler 不执行。"""
        sub_bot = _make_sub_bot_dto(owner_id=999, status="inactive")
        bot_repo = AsyncMock()
        bot_repo.get_by_bot_id = AsyncMock(return_value=sub_bot)

        mock_bot = MagicMock()
        mock_bot.id = 100

        mw = BotContextMiddleware()
        handler = AsyncMock()
        message = _make_message(user_id=555)

        result = await mw(handler, message, {"bot": mock_bot, "bot_repo": bot_repo})

        assert result is None, "停用 bot 应返回 None（短路）"
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_scenario_d_missing_bot_repo_no_type_error(self):
        """场景 D: 中间件依赖缺失 -> 不抛出 TypeError，优雅处理。

        如果 bot_repo 不可用，BotContextMiddleware 应优雅处理，
        而不是抛出 TypeError 或 AttributeError。
        """
        mock_bot = MagicMock()
        mock_bot.id = 100

        mw = BotContextMiddleware()
        handler = AsyncMock()
        message = _make_message(user_id=555)

        # data 中没有 bot_repo
        try:
            result = await mw(handler, message, {"bot": mock_bot})
        except TypeError:
            pytest.fail(
                "BotContextMiddleware 在 bot_repo 缺失时不应抛出 TypeError，"
                "应优雅处理（跳过或透传）"
            )
        except AttributeError:
            pytest.fail(
                "BotContextMiddleware 在 bot_repo 缺失时不应抛出 AttributeError"
            )

        # handler 应仍被调用（透传）
        handler.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "sequence",
        [
            [(555, False), (999, True), (555, False), (999, True)],
            [(999, True), (555, False), (999, True), (555, False)],
            [(555, False), (555, False), (999, True), (999, True)],
        ],
        ids=["user-owner-user-owner", "owner-user-owner-user", "user-user-owner-owner"],
    )
    async def test_scenario_e_alternating_owner_user_no_crosstalk(self, sequence):
        """场景 E: owner/user 交替发消息，分流不串线。

        验证 IsOwnerFilter 在连续不同身份的消息下，每次都正确判断。
        """
        from app.sub_bot.filters import IsOwnerFilter

        sub_bot = _make_sub_bot_dto(owner_id=999)
        owner_filter = IsOwnerFilter(is_owner=True)

        for user_id, expected_is_owner in sequence:
            message = _make_message(user_id=user_id)
            result = await owner_filter(message, sub_bot=sub_bot)
            assert result is expected_is_owner, (
                f"user_id={user_id} 应{'匹配' if expected_is_owner else '不匹配'} "
                f"owner_id={sub_bot.owner_id}，但 IsOwnerFilter 返回 {result}"
            )
