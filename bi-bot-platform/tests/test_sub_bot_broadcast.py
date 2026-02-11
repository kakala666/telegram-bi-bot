"""测试子Bot广播重构 - RED阶段。

验证广播功能从 master_bot 迁移到 sub_bot 后的行为：
- 主人在子Bot中直接操作广播（/broadcast 命令 + FSM 流程）
- master_bot 中的 /broadcast 改为重定向提示
- 管理页广播按钮改为重定向提示
- BroadcastService.start() 接受 bot 参数直接使用
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, PhotoSize, User

from app.dto import BroadcastProgress, BroadcastTaskDTO, SubBotDTO
from app.exceptions import BroadcastError


# ── 工厂函数 ────────────────────────────────────────────────────

def _make_message(
    user_id: int = 999,
    text: str = "/broadcast",
    message_id: int = 1,
) -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.message_id = message_id
    msg.text = text
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = user_id
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    # 默认无媒体
    msg.photo = None
    msg.video = None
    msg.document = None
    msg.audio = None
    msg.sticker = None
    msg.caption = None
    return msg


def _make_callback(
    user_id: int = 999,
    data: str = "broadcast_confirm",
    message_id: int = 1,
) -> MagicMock:
    cb = MagicMock(spec=CallbackQuery)
    cb.data = data
    cb.from_user = MagicMock(spec=User)
    cb.from_user.id = user_id
    cb.message = _make_message(user_id=user_id, message_id=message_id)
    cb.answer = AsyncMock()
    return cb


def _make_sub_bot_dto(
    id: int = 1,
    bot_id: int = 100,
    bot_username: str = "test_bot",
    owner_id: int = 999,
    user_count: int = 50,
) -> SubBotDTO:
    return SubBotDTO(
        id=id,
        bot_id=bot_id,
        bot_username=bot_username,
        owner_id=owner_id,
        owner_username=None,
        status="active",
        welcome_message=None,
        user_count=user_count,
        message_count=0,
        created_at=datetime.utcnow(),
    )


def _make_broadcast_task_dto(
    id: int = 1,
    sub_bot_id: int = 1,
    total_count: int = 50,
    status: str = "running",
) -> BroadcastTaskDTO:
    return BroadcastTaskDTO(
        id=id,
        sub_bot_id=sub_bot_id,
        content_type="text",
        total_count=total_count,
        sent_count=0,
        failed_count=0,
        status=status,
        created_at=datetime.utcnow(),
        completed_at=None,
    )


def _make_broadcast_progress(
    task_id: int = 1,
    total: int = 100,
    sent: int = 50,
    failed: int = 2,
    status: str = "running",
) -> BroadcastProgress:
    percent = int((sent / total) * 100) if total > 0 else 0
    filled = int(20 * percent / 100)
    progress_bar = "█" * filled + "░" * (20 - filled) + f" {percent}%"
    return BroadcastProgress(
        task_id=task_id,
        total=total,
        sent=sent,
        failed=failed,
        status=status,
        percent=percent,
        progress_bar=progress_bar,
    )


def _make_fsm_context(**initial_data) -> MagicMock:
    """创建 mock FSMContext，支持 get_data/update_data/set_state/clear。"""
    state = MagicMock(spec=FSMContext)
    data = dict(initial_data)
    state.get_data = AsyncMock(return_value=data)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state


# ── 测试：子Bot广播handler ──────────────────────────────────────


@pytest.mark.asyncio
class TestSubBotBroadcastCommand:
    """测试子Bot中 /broadcast 命令入口。"""

    async def test_broadcast_command_owner_only(self) -> None:
        """主人在子Bot发送 /broadcast，应进入广播FSM流程。

        前提：IsOwnerFilter(is_owner=True) 已通过。
        handler 应回复广播提示并设置 FSM 状态为 waiting_content。
        """
        from app.sub_bot.handlers.broadcast import cmd_broadcast

        message = _make_message(user_id=999, text="/broadcast")
        sub_bot = _make_sub_bot_dto(id=1, owner_id=999)
        state = _make_fsm_context()
        bot = MagicMock(spec=Bot)

        await cmd_broadcast(message, bot, sub_bot, state)

        # 应该回复广播提示
        message.answer.assert_called_once()
        call_text = message.answer.call_args[0][0]
        assert "广播" in call_text or "broadcast" in call_text.lower()

        # FSM 应进入 waiting_content
        state.set_state.assert_called_once()

    async def test_broadcast_command_non_owner_rejected(self) -> None:
        """非主人发送 /broadcast，由于 IsOwnerFilter 的作用不触发handler。

        验证 IsOwnerFilter(is_owner=True) 对非主人返回 False。
        """
        from app.sub_bot.filters import IsOwnerFilter

        filt = IsOwnerFilter(is_owner=True)
        message = _make_message(user_id=888)
        sub_bot = _make_sub_bot_dto(owner_id=999)

        result = await filt(message, sub_bot)
        assert result is False


@pytest.mark.asyncio
class TestSubBotBroadcastContent:
    """测试子Bot广播内容输入阶段。"""

    async def test_broadcast_waiting_content_text(self) -> None:
        """主人发送文字内容，FSM 进入确认状态，内容正确保存。"""
        from app.sub_bot.handlers.broadcast import on_broadcast_content

        message = _make_message(user_id=999, text="新年快乐！祝大家万事如意")
        sub_bot = _make_sub_bot_dto(id=1, owner_id=999)
        state = _make_fsm_context(broadcast_bot_id=1)
        bot = MagicMock(spec=Bot)
        user_repo = MagicMock()
        user_repo.count_active = AsyncMock(return_value=42)

        await on_broadcast_content(message, bot, sub_bot, state, user_repo)

        # FSM 应进入 confirming 状态
        state.set_state.assert_called_once()

        # 应保存内容到 FSM data
        state.update_data.assert_called()
        update_call = state.update_data.call_args
        saved_data = update_call[0][0] if update_call[0] else update_call[1]
        assert saved_data.get("content_type") == "text"
        assert saved_data.get("content_text") == "新年快乐！祝大家万事如意"

        # 应回复预览消息
        message.answer.assert_called_once()

    async def test_broadcast_waiting_content_photo(self) -> None:
        """主人发送图片，file_id 正确保存到 FSM data。"""
        from app.sub_bot.handlers.broadcast import on_broadcast_content

        message = _make_message(user_id=999, text=None)
        photo = MagicMock(spec=PhotoSize)
        photo.file_id = "sub_bot_photo_file_id_abc123"
        message.photo = [photo]
        message.caption = "图片广播说明"

        sub_bot = _make_sub_bot_dto(id=1, owner_id=999)
        state = _make_fsm_context(broadcast_bot_id=1)
        bot = MagicMock(spec=Bot)
        user_repo = MagicMock()
        user_repo.count_active = AsyncMock(return_value=42)

        await on_broadcast_content(message, bot, sub_bot, state, user_repo)

        # 应保存图片 file_id
        state.update_data.assert_called()
        update_call = state.update_data.call_args
        saved_data = update_call[0][0] if update_call[0] else update_call[1]
        assert saved_data.get("content_type") == "photo"
        assert saved_data.get("content_file_id") == "sub_bot_photo_file_id_abc123"
        assert saved_data.get("content_caption") == "图片广播说明"


@pytest.mark.asyncio
class TestSubBotBroadcastConfirm:
    """测试子Bot广播确认发送。"""

    async def test_broadcast_confirm_starts_task(self) -> None:
        """确认发送后调用 BroadcastService.start()，验证传入了 bot 实例。"""
        from app.sub_bot.handlers.broadcast import cb_broadcast_confirm

        callback = _make_callback(user_id=999, data="broadcast_confirm")
        sub_bot = _make_sub_bot_dto(id=1, owner_id=999)
        state = _make_fsm_context(
            broadcast_bot_id=1,
            content_type="text",
            content_text="测试广播",
            content_file_id=None,
            content_caption=None,
        )
        bot = MagicMock(spec=Bot)

        broadcast_svc = MagicMock()
        broadcast_svc.start = AsyncMock(
            return_value=_make_broadcast_task_dto(id=1, total_count=50)
        )

        await cb_broadcast_confirm(callback, bot, sub_bot, state, broadcast_svc)

        # BroadcastService.start() 应被调用
        broadcast_svc.start.assert_called_once()

        # 调用时应传入 bot 参数（子Bot实例）
        call_kwargs = broadcast_svc.start.call_args[1]
        assert "bot" in call_kwargs, "BroadcastService.start() 应接受 bot 参数"
        assert call_kwargs["bot"] is bot

        # FSM 应被清除
        state.clear.assert_called_once()

        # 应编辑消息显示广播已开始
        callback.message.edit_text.assert_called_once()

    async def test_broadcast_service_start_with_bot_param(self) -> None:
        """BroadcastService.start() 接受 bot: Bot 参数，直接使用该 bot 执行发送。

        验证 start() 签名包含 bot 参数，且 _execute_broadcast 使用传入的 bot。
        """
        from app.services.broadcast import BroadcastService

        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=None)
        broadcast_repo.create = AsyncMock(
            return_value=_make_broadcast_task_dto(id=1, total_count=1)
        )

        user_repo = MagicMock()
        user_repo.get_active_users = AsyncMock(return_value=[])

        registry = MagicMock()
        bot_repo = MagicMock()

        svc = BroadcastService(broadcast_repo, user_repo, registry, bot_repo=bot_repo)

        bot_instance = MagicMock(spec=Bot)

        # start() 应接受 bot 参数
        task = await svc.start(
            sub_bot_id=1,
            owner_id=999,
            content_type="text",
            content_text="Hello",
            content_file_id=None,
            content_caption=None,
            bot=bot_instance,
        )

        assert task is not None
        assert task.id == 1


@pytest.mark.asyncio
class TestSubBotBroadcastCancel:
    """测试子Bot广播取消。"""

    async def test_broadcast_cancel(self) -> None:
        """取消操作正确清理 FSM 状态。"""
        from app.sub_bot.handlers.broadcast import cb_broadcast_cancel

        callback = _make_callback(user_id=999, data="broadcast_cancel")
        state = _make_fsm_context()

        await cb_broadcast_cancel(callback, state)

        # FSM 应被清除
        state.clear.assert_called_once()

        # 应回复取消消息
        callback.message.edit_text.assert_called_once()
        call_text = callback.message.edit_text.call_args[0][0]
        assert "取消" in call_text


@pytest.mark.asyncio
class TestSubBotBroadcastProgress:
    """测试子Bot广播进度查询。"""

    async def test_broadcast_progress_query(self) -> None:
        """查询进度返回正确进度信息。"""
        from app.sub_bot.handlers.broadcast import cb_broadcast_progress

        callback = _make_callback(user_id=999, data="broadcast_progress:1")

        broadcast_svc = MagicMock()
        broadcast_svc.get_progress = AsyncMock(
            return_value=_make_broadcast_progress(
                task_id=1, total=100, sent=72, failed=4, status="running"
            )
        )

        await cb_broadcast_progress(callback, broadcast_svc)

        broadcast_svc.get_progress.assert_called_once_with(task_id=1)

        callback.message.edit_text.assert_called_once()
        call_text = callback.message.edit_text.call_args[0][0]
        assert "72" in call_text or "进度" in call_text
        assert "█" in call_text


# ── 测试：master_bot 重定向 ─────────────────────────────────────


@pytest.mark.asyncio
class TestMasterBotBroadcastRedirect:
    """测试 master_bot 广播功能重定向到子Bot。"""

    async def test_master_broadcast_redirect(self) -> None:
        """master_bot /broadcast 命令应返回提示文字引导去子Bot操作。"""
        from app.master_bot.handlers.broadcast import cmd_broadcast

        message = _make_message(user_id=999, text="/broadcast")
        bot_repo = MagicMock()
        bot_repo.get_by_owner = AsyncMock(
            return_value=[_make_sub_bot_dto(owner_id=999)]
        )

        await cmd_broadcast(message, bot_repo)

        message.answer.assert_called_once()
        call_text = message.answer.call_args[0][0]
        # 重构后应引导用户去子Bot操作
        assert "子Bot" in call_text or "直接" in call_text or "bot" in call_text.lower()

    async def test_manage_broadcast_button_redirect(self) -> None:
        """管理页广播按钮点击后应返回提示文字引导去子Bot操作。"""
        from app.master_bot.handlers.manage import cb_bot_broadcast

        callback = _make_callback(user_id=999, data="bot_broadcast:1")
        bot_repo = MagicMock()
        bot_repo.get_by_id = AsyncMock(
            return_value=_make_sub_bot_dto(id=1, owner_id=999)
        )
        user_repo = MagicMock()
        user_repo.count_active = AsyncMock(return_value=50)
        state = _make_fsm_context()

        await cb_bot_broadcast(callback, bot_repo, user_repo, state)

        # 重构后应引导用户去子Bot操作，而非直接进入FSM
        called_text = ""
        if callback.message.edit_text.called:
            called_text = callback.message.edit_text.call_args[0][0]
        elif callback.answer.called and callback.answer.call_args[0]:
            called_text = callback.answer.call_args[0][0]

        assert "子Bot" in called_text or "直接" in called_text or "/broadcast" in called_text


# ── 测试：Router 注册顺序 ──────────────────────────────────────


@pytest.mark.asyncio
class TestSubBotBroadcastRouterOrder:
    """测试 broadcast router 在 sub_bot dispatcher 中的注册顺序。"""

    async def test_sub_bot_broadcast_router_order(self) -> None:
        """broadcast router 应在 owner_reply router 之前注册。

        这样 /broadcast 命令优先匹配广播handler，
        而不是被 owner_reply 的 IsOwnerFilter(is_owner=True) catch-all 吞掉。
        """
        from app.sub_bot.dispatcher import sub_router

        router_names = [r.name for r in sub_router.sub_routers]

        assert "sub_broadcast" in router_names, (
            "sub_broadcast router 未注册到 sub_router"
        )
        assert "sub_owner_reply" in router_names, (
            "sub_owner_reply router 未注册到 sub_router"
        )

        broadcast_idx = router_names.index("sub_broadcast")
        owner_reply_idx = router_names.index("sub_owner_reply")

        assert broadcast_idx < owner_reply_idx, (
            f"sub_broadcast (index={broadcast_idx}) 应在 "
            f"sub_owner_reply (index={owner_reply_idx}) 之前注册"
        )
