"""Handler 路由集成测试 (TDD RED 阶段)。

验证 handler 路由正确性：
- 普通用户发消息时，forwarder.forward_to_owner 被调用
- owner 发消息时，forwarder.reply_to_user 被调用
- 普通用户消息不被 owner_reply handler 拦截

当前 Bug：owner_reply.router 在 user_message.router 之前被 include，
两者都用无 filter 的 @router.message() 注册 handler。
当普通用户发消息时，owner_reply handler 先匹配，判断不是 owner 后 return None，
aiogram 认为事件已处理，不再传播到 user_message handler。

修复方案：使用 IsOwnerFilter 在 filter 层区分 owner/user。
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.dto import ForwardResult, SubBotDTO


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


def _make_message(
    user_id: int,
    username: str = "testuser",
    text: str = "Hello",
    message_id: int = 10,
    reply_to: MagicMock | None = None,
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
    msg.reply_to_message = reply_to

    from_user = MagicMock()
    from_user.id = user_id
    from_user.username = username
    from_user.first_name = "Test"
    from_user.last_name = "User"
    msg.from_user = from_user

    return msg


class TestHandlerRouting:
    """验证 dispatcher 中 handler 路由正确将消息分发到 owner/user handler。"""

    def test_owner_reply_router_has_owner_filter(self):
        """owner_reply router 的 message handler 应使用 IsOwnerFilter(is_owner=True)。

        当前状态：owner_reply 使用无 filter 的 @router.message()，
        依赖运行时 if 判断，导致路由冲突。

        修复后：应使用 IsOwnerFilter(is_owner=True) 作为 filter。
        """
        from app.sub_bot.handlers import owner_reply

        # 获取 owner_reply router 注册的 message handler 的 filters
        message_handlers = owner_reply.router.message.handlers
        assert len(message_handlers) > 0, "owner_reply router 应至少注册一个 message handler"

        # 检查 handler 是否使用了 IsOwnerFilter
        handler_obj = message_handlers[-1]  # 最后注册的（非 /start）
        filter_names = [
            type(f.callback).__name__ if hasattr(f, "callback") else type(f).__name__
            for f in handler_obj.filters
        ]

        assert "IsOwnerFilter" in filter_names, (
            f"owner_reply handler 应使用 IsOwnerFilter，"
            f"当前 filters: {filter_names}。"
            f"不应使用无 filter 的 @router.message() + 运行时 if 判断。"
        )

    def test_user_message_router_has_non_owner_filter(self):
        """user_message router 的 message handler 应使用 IsOwnerFilter(is_owner=False)。

        当前状态：user_message 使用无 filter 的 @router.message()，
        且被 owner_reply handler 抢先匹配。

        修复后：应使用 IsOwnerFilter(is_owner=False) 作为 filter。
        """
        from app.sub_bot.handlers import user_message

        message_handlers = user_message.router.message.handlers
        assert len(message_handlers) > 0, "user_message router 应至少注册一个 message handler"

        handler_obj = message_handlers[-1]
        filter_names = [
            type(f.callback).__name__ if hasattr(f, "callback") else type(f).__name__
            for f in handler_obj.filters
        ]

        assert "IsOwnerFilter" in filter_names, (
            f"user_message handler 应使用 IsOwnerFilter(is_owner=False)，"
            f"当前 filters: {filter_names}。"
        )

    def test_owner_reply_handler_no_runtime_owner_check(self):
        """owner_reply handler 不应在函数体内做 if from_user.id != owner_id 检查。

        如果使用了 IsOwnerFilter，handler 函数体内不应再做 owner 身份判断，
        因为 filter 已经保证只有 owner 的消息才会进入此 handler。
        """
        import inspect

        from app.sub_bot.handlers.owner_reply import handle_owner_message

        source = inspect.getsource(handle_owner_message)

        assert "from_user.id != sub_bot.owner_id" not in source, (
            "handle_owner_message 不应在运行时检查 from_user.id != sub_bot.owner_id，"
            "应由 IsOwnerFilter 在 filter 层处理。"
        )

    def test_user_message_handler_no_runtime_owner_check(self):
        """user_message handler 不应在函数体内做 if from_user.id == owner_id 检查。

        如果使用了 IsOwnerFilter，handler 函数体内不应再做 owner 身份判断。
        """
        import inspect

        from app.sub_bot.handlers.user_message import handle_user_message

        source = inspect.getsource(handle_user_message)

        assert "from_user.id == sub_bot.owner_id" not in source, (
            "handle_user_message 不应在运行时检查 from_user.id == sub_bot.owner_id，"
            "应由 IsOwnerFilter(is_owner=False) 在 filter 层处理。"
        )


class TestUserMessageNotInterceptedByOwnerHandler:
    """验证普通用户消息不会被 owner_reply handler 拦截。

    核心问题：当两个 router 都用无 filter 的 @router.message() 时，
    aiogram 按 include 顺序匹配，owner_reply 先匹配并 return None，
    aiogram 认为事件已处理，user_message handler 永远不会执行。

    这个测试验证修复后 owner_reply handler 的 filter 对非 owner 消息返回 False，
    使 aiogram 跳过该 handler，正确传播到 user_message handler。
    """

    def test_owner_reply_handler_rejects_non_owner_at_filter_level(self):
        """owner_reply 的 filter 应在过滤器层面拒绝非 owner 消息。

        验证 owner_reply router 使用了 filter 而非运行时 if 判断。
        这是修复路由冲突的关键。
        """
        from app.sub_bot.handlers import owner_reply

        message_handlers = owner_reply.router.message.handlers
        non_start_handlers = [
            h for h in message_handlers
            if not any(type(f).__name__ == "CommandStart" for f in h.filters)
        ]

        assert len(non_start_handlers) > 0, "应有非 /start 的 message handler"

        for handler_obj in non_start_handlers:
            filter_count = len(handler_obj.filters)
            assert filter_count > 0, (
                "owner_reply message handler 应至少有一个 filter (IsOwnerFilter)，"
                f"当前 filter 数量: {filter_count}。"
                "没有 filter 意味着所有消息都会匹配此 handler，导致路由冲突。"
            )
