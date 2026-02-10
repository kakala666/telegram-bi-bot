"""测试 /broadcast FSM Handler。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from app.dto import BroadcastProgress, BroadcastTaskDTO, SubBotDTO
from app.exceptions import BroadcastError
from app.master_bot.states import BroadcastStates


def _make_message(
    user_id: int = 999,
    text: str = "/broadcast",
    message_id: int = 1,
) -> MagicMock:
    """创建 mock Message 对象。"""
    msg = MagicMock(spec=Message)
    msg.message_id = message_id
    msg.text = text
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = user_id
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    return msg


def _make_callback(
    user_id: int = 999,
    data: str = "broadcast_select:1",
    message_id: int = 1,
) -> MagicMock:
    """创建 mock CallbackQuery 对象。"""
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
    sent_count: int = 0,
    failed_count: int = 0,
    status: str = "running",
) -> BroadcastTaskDTO:
    return BroadcastTaskDTO(
        id=id,
        sub_bot_id=sub_bot_id,
        content_type="text",
        total_count=total_count,
        sent_count=sent_count,
        failed_count=failed_count,
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


@pytest.mark.asyncio
class TestBroadcastCommandOwnerOnly:
    """测试 /broadcast 命令只有Bot主人可用。"""

    async def test_broadcast_command_owner_only(self):
        """测试只有Bot主人可以使用 /broadcast。"""
        try:
            from app.master_bot.handlers.broadcast import cmd_broadcast

            message = _make_message(user_id=999, text="/broadcast")
            bot_repo = MagicMock()
            bot_repo.get_by_owner = AsyncMock(
                return_value=[_make_sub_bot_dto(owner_id=999)]
            )

            await cmd_broadcast(message, bot_repo)

            # 应该显示Bot选择界面
            message.answer.assert_called_once()
            call_args = message.answer.call_args[0][0]
            assert "选择" in call_args or "Bot" in call_args
        except ImportError:
            pytest.skip("broadcast handler not implemented yet")

    async def test_broadcast_no_bots(self):
        """测试没有Bot时的提示。"""
        try:
            from app.master_bot.handlers.broadcast import cmd_broadcast

            message = _make_message(user_id=999, text="/broadcast")
            bot_repo = MagicMock()
            bot_repo.get_by_owner = AsyncMock(return_value=[])

            await cmd_broadcast(message, bot_repo)

            # 应该提示没有Bot
            message.answer.assert_called_once()
            call_args = message.answer.call_args[0][0]
            assert "没有" in call_args or "注册" in call_args
        except ImportError:
            pytest.skip("broadcast handler not implemented yet")


@pytest.mark.asyncio
class TestBroadcastSelectBot:
    """测试选择要广播的Bot。"""

    async def test_broadcast_select_bot(self):
        """测试选择Bot进入内容输入状态。"""
        try:
            from app.master_bot.handlers.broadcast import cb_broadcast_select

            callback = _make_callback(user_id=999, data="broadcast_select:1")
            state = MagicMock(spec=FSMContext)
            state.set_state = AsyncMock()
            state.update_data = AsyncMock()

            bot_repo = MagicMock()
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(id=1, owner_id=999, user_count=50)
            )

            user_repo = MagicMock()
            user_repo.count_active = AsyncMock(return_value=48)

            await cb_broadcast_select(callback, state, bot_repo, user_repo)

            # 应该设置FSM状态
            state.set_state.assert_called_once_with(BroadcastStates.waiting_content)
            state.update_data.assert_called_once()

            # 应该编辑消息显示输入提示
            callback.message.edit_text.assert_called_once()
            call_args = callback.message.edit_text.call_args[0][0]
            assert "48" in call_args or "活跃" in call_args
        except ImportError:
            pytest.skip("broadcast handler not implemented yet")

    async def test_broadcast_select_bot_permission_denied(self):
        """测试选择不属于自己的Bot被拒绝。"""
        try:
            from app.master_bot.handlers.broadcast import cb_broadcast_select

            callback = _make_callback(user_id=999, data="broadcast_select:1")
            state = MagicMock(spec=FSMContext)

            bot_repo = MagicMock()
            # Bot属于其他用户
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(id=1, owner_id=888)
            )

            user_repo = MagicMock()

            await cb_broadcast_select(callback, state, bot_repo, user_repo)

            # 应该显示权限错误
            callback.answer.assert_called()
            call_args = callback.answer.call_args
            assert call_args[1].get("show_alert") is True
        except ImportError:
            pytest.skip("broadcast handler not implemented yet")


@pytest.mark.asyncio
class TestBroadcastInputContent:
    """测试输入广播内容。"""

    async def test_broadcast_input_content(self):
        """测试输入广播内容进入确认状态。"""
        try:
            from app.master_bot.handlers.broadcast import on_broadcast_content

            message = _make_message(user_id=999, text="新年快乐！")
            state = MagicMock(spec=FSMContext)
            state.get_data = AsyncMock(return_value={"broadcast_bot_id": 1})
            state.set_state = AsyncMock()
            state.update_data = AsyncMock()

            bot_repo = MagicMock()
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(id=1, owner_id=999)
            )

            user_repo = MagicMock()
            user_repo.count_active = AsyncMock(return_value=50)

            await on_broadcast_content(message, state, bot_repo, user_repo)

            # 应该设置确认状态
            state.set_state.assert_called_once_with(BroadcastStates.confirming_broadcast)
            state.update_data.assert_called()

            # 应该显示预览
            message.answer.assert_called_once()
            call_args = message.answer.call_args[0][0]
            assert "预览" in call_args or "确认" in call_args
        except ImportError:
            pytest.skip("broadcast handler not implemented yet")

    async def test_broadcast_input_photo(self):
        """测试输入图片广播内容。"""
        try:
            from app.master_bot.handlers.broadcast import on_broadcast_content

            message = _make_message(user_id=999, text=None)
            message.photo = [MagicMock()]
            message.photo[-1].file_id = "photo_file_id_123"
            message.caption = "图片说明"

            state = MagicMock(spec=FSMContext)
            state.get_data = AsyncMock(return_value={"broadcast_bot_id": 1})
            state.set_state = AsyncMock()
            state.update_data = AsyncMock()

            bot_repo = MagicMock()
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(id=1, owner_id=999)
            )

            user_repo = MagicMock()
            user_repo.count_active = AsyncMock(return_value=50)

            await on_broadcast_content(message, state, bot_repo, user_repo)

            # 应该保存图片信息
            state.update_data.assert_called()
            call_args = state.update_data.call_args[0][0]
            assert call_args.get("content_type") == "photo"
            assert call_args.get("content_file_id") == "photo_file_id_123"
        except ImportError:
            pytest.skip("broadcast handler not implemented yet")


@pytest.mark.asyncio
class TestBroadcastConfirm:
    """测试确认发送广播。"""

    async def test_broadcast_confirm(self):
        """测试确认发送广播。"""
        try:
            from app.master_bot.handlers.broadcast import cb_broadcast_confirm

            callback = _make_callback(user_id=999, data="broadcast_confirm")
            state = MagicMock(spec=FSMContext)
            state.get_data = AsyncMock(
                return_value={
                    "broadcast_bot_id": 1,
                    "content_type": "text",
                    "content_text": "Hello",
                    "content_file_id": None,
                    "content_caption": None,
                }
            )
            state.clear = AsyncMock()

            bot_repo = MagicMock()
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(id=1, owner_id=999)
            )

            broadcast_svc = MagicMock()
            broadcast_svc.start = AsyncMock(
                return_value=_make_broadcast_task_dto(id=1, total_count=50)
            )

            await cb_broadcast_confirm(callback, state, bot_repo, broadcast_svc)

            # 应该启动广播
            broadcast_svc.start.assert_called_once()

            # 应该清除FSM状态
            state.clear.assert_called_once()

            # 应该显示广播开始消息
            callback.message.edit_text.assert_called_once()
            call_args = callback.message.edit_text.call_args[0][0]
            assert "已开始" in call_args or "发送中" in call_args
        except ImportError:
            pytest.skip("broadcast handler not implemented yet")

    async def test_broadcast_confirm_error(self):
        """测试确认发送时出错。"""
        try:
            from app.master_bot.handlers.broadcast import cb_broadcast_confirm

            callback = _make_callback(user_id=999, data="broadcast_confirm")
            state = MagicMock(spec=FSMContext)
            state.get_data = AsyncMock(
                return_value={
                    "broadcast_bot_id": 1,
                    "content_type": "text",
                    "content_text": "Hello",
                    "content_file_id": None,
                    "content_caption": None,
                }
            )

            bot_repo = MagicMock()
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(id=1, owner_id=999)
            )

            broadcast_svc = MagicMock()
            broadcast_svc.start = AsyncMock(
                side_effect=BroadcastError("该Bot已有正在进行的广播任务")
            )

            await cb_broadcast_confirm(callback, state, bot_repo, broadcast_svc)

            # 应该显示错误消息
            callback.message.edit_text.assert_called_once()
            call_args = callback.message.edit_text.call_args[0][0]
            assert "正在进行" in call_args or "错误" in call_args
        except ImportError:
            pytest.skip("broadcast handler not implemented yet")


@pytest.mark.asyncio
class TestBroadcastCancel:
    """测试取消广播操作。"""

    async def test_broadcast_cancel(self):
        """测试取消广播流程。"""
        try:
            from app.master_bot.handlers.broadcast import cb_broadcast_cancel

            callback = _make_callback(user_id=999, data="broadcast_cancel")
            state = MagicMock(spec=FSMContext)
            state.clear = AsyncMock()

            await cb_broadcast_cancel(callback, state)

            # 应该清除FSM状态
            state.clear.assert_called_once()

            # 应该显示取消消息
            callback.message.edit_text.assert_called_once()
            call_args = callback.message.edit_text.call_args[0][0]
            assert "取消" in call_args
        except ImportError:
            pytest.skip("broadcast handler not implemented yet")


@pytest.mark.asyncio
class TestBroadcastProgressCallback:
    """测试查询进度回调。"""

    async def test_broadcast_progress_callback(self):
        """测试查询广播进度。"""
        try:
            from app.master_bot.handlers.broadcast import cb_broadcast_progress

            callback = _make_callback(user_id=999, data="broadcast_progress:1")

            broadcast_svc = MagicMock()
            broadcast_svc.get_progress = AsyncMock(
                return_value=_make_broadcast_progress(
                    task_id=1, total=100, sent=72, failed=4, status="running"
                )
            )

            await cb_broadcast_progress(callback, broadcast_svc)

            # 应该查询进度
            broadcast_svc.get_progress.assert_called_once_with(task_id=1)

            # 应该编辑消息显示进度
            callback.message.edit_text.assert_called_once()
            call_args = callback.message.edit_text.call_args[0][0]
            assert "72" in call_args or "进度" in call_args
            assert "█" in call_args  # 进度条
        except ImportError:
            pytest.skip("broadcast handler not implemented yet")

    async def test_broadcast_progress_completed(self):
        """测试查询已完成的广播进度。"""
        try:
            from app.master_bot.handlers.broadcast import cb_broadcast_progress

            callback = _make_callback(user_id=999, data="broadcast_progress:1")

            broadcast_svc = MagicMock()
            broadcast_svc.get_progress = AsyncMock(
                return_value=_make_broadcast_progress(
                    task_id=1, total=100, sent=96, failed=4, status="completed"
                )
            )

            await cb_broadcast_progress(callback, broadcast_svc)

            # 应该显示完成状态
            callback.message.edit_text.assert_called_once()
            call_args = callback.message.edit_text.call_args[0][0]
            assert "完成" in call_args or "96" in call_args
        except ImportError:
            pytest.skip("broadcast handler not implemented yet")

    async def test_broadcast_cancel_running(self):
        """测试取消正在运行的广播。"""
        try:
            from app.master_bot.handlers.broadcast import cb_broadcast_cancel_task

            callback = _make_callback(user_id=999, data="broadcast_cancel_task:1")

            broadcast_svc = MagicMock()
            broadcast_svc.cancel = AsyncMock(return_value=True)

            await cb_broadcast_cancel_task(callback, broadcast_svc)

            # 应该取消广播
            broadcast_svc.cancel.assert_called_once_with(task_id=1)

            # 应该显示取消成功消息
            callback.message.edit_text.assert_called_once()
            call_args = callback.message.edit_text.call_args[0][0]
            assert "已取消" in call_args or "取消" in call_args
        except ImportError:
            pytest.skip("broadcast handler not implemented yet")
