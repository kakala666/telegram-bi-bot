"""测试3个严重运行时Bug的修复。

Bug 1: BotContextMiddleware 未注册到 sub_dp
Bug 2: admin handler 参数名 message_map_repo 与 launcher 注入的 msg_map_repo 不匹配
Bug 3: BroadcastService._execute_broadcast 用 sub_bot_id 查找Bot实例，但BotRegistry用的是 bot_id
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.dto import BotUserDTO, BroadcastTaskDTO, SubBotDTO


# ── Bug 1: BotContextMiddleware 未注册到 sub_dp ──────────────────


class TestBug1BotContextMiddlewareRegistration:
    """验证 launcher 启动后 sub_dp 已注册 BotContextMiddleware。

    Bug: 中间件已编写(app/sub_bot/middleware/bot_context.py)但从未在
    launcher.py 或 sub_bot/dispatcher.py 中注册到 sub_dp。
    """

    def test_sub_dp_has_bot_context_middleware_registered(self):
        """sub_dp 的 message handler 中间件链应包含 BotContextMiddleware。

        检查 sub_dp 或 sub_router 的 middleware（inner 或 outer）列表中
        是否包含 BotContextMiddleware 实例。
        """
        from app.sub_bot.dispatcher import sub_dp, sub_router
        from app.sub_bot.middleware.bot_context import BotContextMiddleware

        # 收集 sub_dp 和 sub_router 上所有已注册的中间件类型（inner + outer）
        all_middleware_types: list[type] = []

        # 检查 dispatcher 级别的中间件
        for mw in sub_dp.message.middleware:
            all_middleware_types.append(type(mw))
        for mw in sub_dp.message.outer_middleware:
            all_middleware_types.append(type(mw))
        for mw in sub_dp.callback_query.middleware:
            all_middleware_types.append(type(mw))
        for mw in sub_dp.callback_query.outer_middleware:
            all_middleware_types.append(type(mw))

        # 检查 router 级别的中间件
        for mw in sub_router.message.middleware:
            all_middleware_types.append(type(mw))
        for mw in sub_router.message.outer_middleware:
            all_middleware_types.append(type(mw))
        for mw in sub_router.callback_query.middleware:
            all_middleware_types.append(type(mw))
        for mw in sub_router.callback_query.outer_middleware:
            all_middleware_types.append(type(mw))

        assert BotContextMiddleware in all_middleware_types, (
            "BotContextMiddleware 未注册到 sub_dp 或 sub_router。"
            "需要在 sub_bot/dispatcher.py 或 launcher.py 中调用 "
            "sub_dp.message.outer_middleware(BotContextMiddleware(bot_repo)) 或类似注册。"
        )

    def test_bot_context_middleware_registered_for_message_updates(self):
        """BotContextMiddleware 至少应注册在 message 类型的 update 上。

        因为子Bot的核心功能是处理用户消息，中间件必须拦截 message 事件。
        """
        from app.sub_bot.dispatcher import sub_dp, sub_router
        from app.sub_bot.middleware.bot_context import BotContextMiddleware

        message_middleware_types = [
            type(mw) for mw in sub_dp.message.middleware
        ] + [
            type(mw) for mw in sub_dp.message.outer_middleware
        ] + [
            type(mw) for mw in sub_router.message.middleware
        ] + [
            type(mw) for mw in sub_router.message.outer_middleware
        ]

        assert BotContextMiddleware in message_middleware_types, (
            "BotContextMiddleware 未注册到 message 事件的中间件链。"
        )


# ── Bug 2: admin handler 参数名不匹配 ────────────────────────────
# PLACEHOLDER_BUG2


class TestBug2AdminHandlerParameterMismatch:
    """验证 admin handler 参数名与 launcher workflow_data key 一致。

    Bug: admin.py 中 admin_command 函数使用参数名 message_map_repo，
    但 launcher.py 注入的 workflow_data key 是 msg_map_repo。
    aiogram 按参数名匹配注入，名称不一致会导致注入失败。
    """

    def test_admin_command_uses_msg_map_repo_parameter(self):
        """admin_command handler 的参数名应为 msg_map_repo（与 launcher 一致）。"""
        from app.master_bot.handlers.admin import admin_command

        sig = inspect.signature(admin_command)
        param_names = list(sig.parameters.keys())

        # launcher.py 注入的 key 是 "msg_map_repo"
        assert "msg_map_repo" in param_names, (
            f"admin_command 参数名应包含 'msg_map_repo'（与 launcher workflow_data 一致），"
            f"当前参数列表: {param_names}"
        )
        assert "message_map_repo" not in param_names, (
            "admin_command 不应使用 'message_map_repo'，launcher 注入的 key 是 'msg_map_repo'"
        )

    def test_admin_panel_callback_uses_msg_map_repo_parameter(self):
        """admin_panel_callback handler 的参数名应为 msg_map_repo。"""
        from app.master_bot.handlers.admin import admin_panel_callback

        sig = inspect.signature(admin_panel_callback)
        param_names = list(sig.parameters.keys())

        assert "msg_map_repo" in param_names, (
            f"admin_panel_callback 参数名应包含 'msg_map_repo'，"
            f"当前参数列表: {param_names}"
        )
        assert "message_map_repo" not in param_names, (
            "admin_panel_callback 不应使用 'message_map_repo'"
        )

    def test_admin_view_statistics_uses_msg_map_repo_parameter(self):
        """admin_view_statistics handler 的参数名应为 msg_map_repo。"""
        from app.master_bot.handlers.admin import admin_view_statistics

        sig = inspect.signature(admin_view_statistics)
        param_names = list(sig.parameters.keys())

        assert "msg_map_repo" in param_names, (
            f"admin_view_statistics 参数名应包含 'msg_map_repo'，"
            f"当前参数列表: {param_names}"
        )
        assert "message_map_repo" not in param_names, (
            "admin_view_statistics 不应使用 'message_map_repo'"
        )

    def test_all_admin_handlers_match_launcher_workflow_keys(self):
        """所有 admin handler 中引用 MessageMapRepo 的参数名都应与 launcher 一致。"""
        from app.master_bot.handlers import admin

        # launcher.py 中 master_dp.workflow_data 的 key 集合
        launcher_keys = {
            "bot_repo", "user_repo", "msg_map_repo", "ad_repo",
            "broadcast_repo", "token_validator", "encryptor", "settings",
            "registry", "broadcast_svc", "ad_injector", "forwarder",
            "cleanup_svc",
        }

        # 检查 admin 模块中所有 async 函数的参数
        for name, func in inspect.getmembers(admin, inspect.iscoroutinefunction):
            sig = inspect.signature(func)
            for param_name in sig.parameters:
                if param_name in ("self", "message", "callback", "state"):
                    continue
                # 如果参数名看起来像 repo/service 依赖，应在 launcher_keys 中
                if param_name.endswith("_repo") or param_name in (
                    "settings", "registry", "broadcast_svc", "ad_injector",
                    "forwarder", "token_validator", "encryptor", "cleanup_svc",
                ):
                    assert param_name in launcher_keys, (
                        f"admin.{name} 的参数 '{param_name}' 不在 launcher workflow_data 中。"
                        f"launcher 可用的 key: {launcher_keys}"
                    )


# ── Bug 3: BroadcastService 用 sub_bot_id 查找Bot实例 ────────────


@pytest.mark.asyncio
class TestBug3BroadcastBotLookup:
    """验证广播时能正确通过 bot_id（Telegram ID）找到对应的Bot实例。

    Bug: BroadcastService._execute_broadcast 调用
    self._registry.get_bot(sub_bot_id) 传入的是数据库主键 sub_bot_id，
    但 BotRegistry._bots 字典的 key 是 Telegram bot_id。
    两者不同，导致 get_bot 返回 None，广播无法执行。

    修复方案：需要先通过 bot_repo 查询 sub_bot_id 对应的 bot_id，
    再用 bot_id 去 registry 获取 Bot 实例。
    或者在 _execute_broadcast 中接收 bot_id 参数。
    """

    async def test_execute_broadcast_finds_bot_by_telegram_bot_id(self):
        """广播执行时应使用 Telegram bot_id 而非数据库主键 sub_bot_id 查找Bot。

        场景：sub_bot_id=1（数据库主键），bot_id=9999999（Telegram ID）
        BotRegistry._bots = {9999999: <Bot>}
        调用 get_bot(1) 会返回 None（错误）
        调用 get_bot(9999999) 才能返回正确的 Bot 实例
        """
        from app.services.broadcast import BroadcastService

        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=None)
        broadcast_repo.create = AsyncMock(
            return_value=BroadcastTaskDTO(
                id=1, sub_bot_id=1, content_type="text",
                total_count=1, sent_count=0, failed_count=0,
                status="running",
                created_at=datetime.now(timezone.utc),
                completed_at=None,
            )
        )
        broadcast_repo.update_progress = AsyncMock()
        broadcast_repo.update_status = AsyncMock()

        user_repo = MagicMock()
        user = BotUserDTO(
            id=1, sub_bot_id=1, user_id=555,
            username="alice", display_name="Alice",
            is_blocked=False, is_banned_by_telegram=False,
            first_seen=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc),
        )
        user_repo.get_active_users = AsyncMock(return_value=[user])

        # 模拟 BotRegistry：bot_id=9999999 是 Telegram ID
        registry = MagicMock()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        # get_bot 只在传入 9999999 时返回 bot，传入 1 时返回 None
        def get_bot_side_effect(bid):
            if bid == 9999999:
                return mock_bot
            return None

        registry.get_bot = MagicMock(side_effect=get_bot_side_effect)

        # 提供 bot_repo 以便 BroadcastService 解析 sub_bot_id -> bot_id
        bot_repo = MagicMock()
        bot_repo.get_by_id = AsyncMock(
            return_value=SubBotDTO(
                id=1, bot_id=9999999, bot_username="test_bot",
                owner_id=999, owner_username="owner",
                status="active", welcome_message=None,
                user_count=1, message_count=0,
                created_at=datetime.now(timezone.utc),
            )
        )

        service = BroadcastService(broadcast_repo, user_repo, registry, bot_repo=bot_repo)

        # 发起广播（sub_bot_id=1）
        await service.start(
            sub_bot_id=1,
            owner_id=999,
            content_type="text",
            content_text="Hello broadcast",
            content_file_id=None,
            content_caption=None,
        )

        # 等待异步任务执行
        await asyncio.sleep(0.3)

        # 验证：广播应该成功发送消息（即 get_bot 被传入了正确的 bot_id）
        # 如果 Bug 未修复，get_bot(1) 返回 None，send_message 不会被调用
        assert mock_bot.send_message.call_count == 1, (
            "广播未能发送消息。可能是因为 _execute_broadcast 使用 sub_bot_id(数据库主键) "
            "而非 bot_id(Telegram ID) 查找 Bot 实例。"
        )

    async def test_broadcast_service_resolves_bot_id_from_sub_bot_id(self):
        """BroadcastService 应能将 sub_bot_id 解析为 Telegram bot_id。

        验证 _execute_broadcast 内部逻辑：
        1. 接收 sub_bot_id（数据库主键）
        2. 查询数据库获取对应的 bot_id（Telegram ID）
        3. 用 bot_id 调用 registry.get_bot()
        """
        from app.services.broadcast import BroadcastService

        # 检查 _execute_broadcast 的源码或参数
        # 确保它不是直接把 sub_bot_id 传给 registry.get_bot
        source = inspect.getsource(BroadcastService._execute_broadcast)

        # 如果源码中直接调用 self._registry.get_bot(sub_bot_id)
        # 那就是 Bug 未修复
        # 修复后应该使用 bot_id 或通过 bot_repo 查询
        has_bot_id_lookup = (
            "bot_repo" in source
            or "bot_id" in source
            or "get_by_id" in source
        )

        # 不应该直接把 sub_bot_id 传给 get_bot
        direct_sub_bot_id_usage = "get_bot(sub_bot_id)" in source

        assert not direct_sub_bot_id_usage or has_bot_id_lookup, (
            "_execute_broadcast 直接使用 sub_bot_id 调用 registry.get_bot()，"
            "但 BotRegistry 的 key 是 Telegram bot_id，不是数据库主键 sub_bot_id。"
            "需要先查询数据库获取 bot_id，再调用 registry.get_bot(bot_id)。"
        )
