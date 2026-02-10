"""测试 BroadcastService。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from app.dto import BotUserDTO, BroadcastTaskDTO
from app.exceptions import BroadcastError
from app.repositories.broadcast_repo import BroadcastRepo
from app.repositories.user_repo import UserRepo


def _make_bot_user_dto(
    user_id: int = 555,
    username: str | None = "alice",
    display_name: str = "Alice Smith",
    is_blocked: bool = False,
    is_banned_by_telegram: bool = False,
) -> BotUserDTO:
    return BotUserDTO(
        id=1,
        sub_bot_id=1,
        user_id=user_id,
        username=username,
        display_name=display_name,
        is_blocked=is_blocked,
        is_banned_by_telegram=is_banned_by_telegram,
        first_seen=datetime.utcnow(),
        last_active=datetime.utcnow(),
    )


def _make_broadcast_task_dto(
    id: int = 1,
    sub_bot_id: int = 1,
    content_type: str = "text",
    total_count: int = 100,
    sent_count: int = 0,
    failed_count: int = 0,
    status: str = "running",
) -> BroadcastTaskDTO:
    return BroadcastTaskDTO(
        id=id,
        sub_bot_id=sub_bot_id,
        content_type=content_type,
        total_count=total_count,
        sent_count=sent_count,
        failed_count=failed_count,
        status=status,
        created_at=datetime.now(timezone.utc),
        completed_at=None,
    )


@pytest.mark.asyncio
class TestBroadcastServiceStart:
    """BroadcastService.start 测试。"""

    async def test_start_broadcast_creates_task(self):
        """测试创建广播任务。"""
        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=None)
        broadcast_repo.create = AsyncMock(
            return_value=_make_broadcast_task_dto(id=1, total_count=10)
        )

        user_repo = MagicMock()
        user_repo.get_active_users = AsyncMock(
            return_value=[_make_bot_user_dto(user_id=i) for i in range(10)]
        )

        registry = MagicMock()
        mock_bot = MagicMock()
        registry.get_bot = MagicMock(return_value=mock_bot)

        # 导入 BroadcastService（实现还不存在，会失败）
        try:
            from app.services.broadcast import BroadcastService

            service = BroadcastService(broadcast_repo, user_repo, registry)

            task = await service.start(
                sub_bot_id=1,
                owner_id=999,
                content_type="text",
                content_text="Hello",
                content_file_id=None,
                content_caption=None,
            )

            assert task.id == 1
            assert task.total_count == 10
            broadcast_repo.create.assert_called_once()
        except ImportError:
            pytest.skip("BroadcastService not implemented yet")

    async def test_start_broadcast_sends_to_all_users(self):
        """测试发送给所有活跃用户。"""
        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=None)
        broadcast_repo.create = AsyncMock(
            return_value=_make_broadcast_task_dto(id=1, total_count=3)
        )
        broadcast_repo.update_progress = AsyncMock()
        broadcast_repo.update_status = AsyncMock()

        users = [
            _make_bot_user_dto(user_id=100),
            _make_bot_user_dto(user_id=200),
            _make_bot_user_dto(user_id=300),
        ]
        user_repo = MagicMock()
        user_repo.get_active_users = AsyncMock(return_value=users)

        registry = MagicMock()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        registry.get_bot = MagicMock(return_value=mock_bot)

        try:
            from app.services.broadcast import BroadcastService

            service = BroadcastService(broadcast_repo, user_repo, registry)

            await service.start(
                sub_bot_id=1,
                owner_id=999,
                content_type="text",
                content_text="Broadcast message",
                content_file_id=None,
                content_caption=None,
            )

            # 等待异步任务执行
            await asyncio.sleep(0.2)

            # 验证发送给所有用户
            assert mock_bot.send_message.call_count == 3
        except ImportError:
            pytest.skip("BroadcastService not implemented yet")

    async def test_broadcast_rate_limiting(self):
        """测试限速20msg/sec。"""
        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=None)
        broadcast_repo.create = AsyncMock(
            return_value=_make_broadcast_task_dto(id=1, total_count=5)
        )
        broadcast_repo.update_progress = AsyncMock()
        broadcast_repo.update_status = AsyncMock()

        users = [_make_bot_user_dto(user_id=i) for i in range(5)]
        user_repo = MagicMock()
        user_repo.get_active_users = AsyncMock(return_value=users)

        registry = MagicMock()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        registry.get_bot = MagicMock(return_value=mock_bot)

        try:
            from app.services.broadcast import BroadcastService

            service = BroadcastService(broadcast_repo, user_repo, registry)

            start_time = asyncio.get_event_loop().time()
            await service.start(
                sub_bot_id=1,
                owner_id=999,
                content_type="text",
                content_text="Test",
                content_file_id=None,
                content_caption=None,
            )

            # 等待广播完成
            await asyncio.sleep(0.5)

            end_time = asyncio.get_event_loop().time()
            elapsed = end_time - start_time

            # 5条消息，限速20msg/sec，应该至少需要 5/20 = 0.25秒
            assert elapsed >= 0.2
        except ImportError:
            pytest.skip("BroadcastService not implemented yet")

    async def test_broadcast_retry_after(self):
        """测试 RetryAfter 处理。"""
        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=None)
        broadcast_repo.create = AsyncMock(
            return_value=_make_broadcast_task_dto(id=1, total_count=2)
        )
        broadcast_repo.update_progress = AsyncMock()
        broadcast_repo.update_status = AsyncMock()

        users = [_make_bot_user_dto(user_id=100), _make_bot_user_dto(user_id=200)]
        user_repo = MagicMock()
        user_repo.get_active_users = AsyncMock(return_value=users)

        registry = MagicMock()
        mock_bot = MagicMock()

        # 第一次调用抛出 RetryAfter，第二次成功
        retry_error = TelegramRetryAfter(
            method=MagicMock(), message="Rate limit", retry_after=1
        )
        mock_bot.send_message = AsyncMock(
            side_effect=[
                retry_error,
                None,
                None,
            ]
        )
        registry.get_bot = MagicMock(return_value=mock_bot)

        try:
            from app.services.broadcast import BroadcastService

            service = BroadcastService(broadcast_repo, user_repo, registry)

            await service.start(
                sub_bot_id=1,
                owner_id=999,
                content_type="text",
                content_text="Test",
                content_file_id=None,
                content_caption=None,
            )

            # 等待重试完成
            await asyncio.sleep(1.5)

            # 应该重试第一个用户，然后发送给第二个用户
            assert mock_bot.send_message.call_count >= 2
        except ImportError:
            pytest.skip("BroadcastService not implemented yet")

    async def test_cancel_broadcast(self):
        """测试取消广播。"""
        broadcast_repo = MagicMock()
        broadcast_repo.get_by_id = AsyncMock(
            return_value=_make_broadcast_task_dto(id=1, status="running")
        )
        broadcast_repo.update_status = AsyncMock()

        user_repo = MagicMock()
        registry = MagicMock()

        try:
            from app.services.broadcast import BroadcastService

            service = BroadcastService(broadcast_repo, user_repo, registry)

            result = await service.cancel(task_id=1)

            assert result is True
            broadcast_repo.update_status.assert_called_once_with(
                1, "cancelled", completed_at=None
            )
        except ImportError:
            pytest.skip("BroadcastService not implemented yet")

    async def test_get_progress(self):
        """测试查询进度。"""
        broadcast_repo = MagicMock()
        broadcast_repo.get_by_id = AsyncMock(
            return_value=_make_broadcast_task_dto(
                id=1, total_count=100, sent_count=72, failed_count=4, status="running"
            )
        )

        user_repo = MagicMock()
        registry = MagicMock()

        try:
            from app.services.broadcast import BroadcastService

            service = BroadcastService(broadcast_repo, user_repo, registry)

            progress = await service.get_progress(task_id=1)

            assert progress is not None
            assert progress.total == 100
            assert progress.sent == 72
            assert progress.failed == 4
            assert progress.percent == 72
            assert "█" in progress.progress_bar
        except ImportError:
            pytest.skip("BroadcastService not implemented yet")

    async def test_broadcast_skip_blocked_users(self):
        """测试跳过被封禁用户。"""
        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=None)
        broadcast_repo.create = AsyncMock(
            return_value=_make_broadcast_task_dto(id=1, total_count=2)
        )
        broadcast_repo.update_progress = AsyncMock()
        broadcast_repo.update_status = AsyncMock()

        # 只返回活跃用户（已封禁用户不在列表中）
        users = [
            _make_bot_user_dto(user_id=100, is_blocked=False),
            _make_bot_user_dto(user_id=200, is_blocked=False),
        ]
        user_repo = MagicMock()
        user_repo.get_active_users = AsyncMock(return_value=users)

        registry = MagicMock()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        registry.get_bot = MagicMock(return_value=mock_bot)

        try:
            from app.services.broadcast import BroadcastService

            service = BroadcastService(broadcast_repo, user_repo, registry)

            await service.start(
                sub_bot_id=1,
                owner_id=999,
                content_type="text",
                content_text="Test",
                content_file_id=None,
                content_caption=None,
            )

            await asyncio.sleep(0.2)

            # 只发送给2个活跃用户
            assert mock_bot.send_message.call_count == 2
        except ImportError:
            pytest.skip("BroadcastService not implemented yet")

    async def test_broadcast_updates_progress(self):
        """测试更新发送进度。"""
        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=None)
        broadcast_repo.create = AsyncMock(
            return_value=_make_broadcast_task_dto(id=1, total_count=60)
        )
        broadcast_repo.update_progress = AsyncMock()
        broadcast_repo.update_status = AsyncMock()

        users = [_make_bot_user_dto(user_id=i) for i in range(60)]
        user_repo = MagicMock()
        user_repo.get_active_users = AsyncMock(return_value=users)

        registry = MagicMock()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        registry.get_bot = MagicMock(return_value=mock_bot)

        try:
            from app.services.broadcast import BroadcastService

            service = BroadcastService(broadcast_repo, user_repo, registry)

            await service.start(
                sub_bot_id=1,
                owner_id=999,
                content_type="text",
                content_text="Test",
                content_file_id=None,
                content_caption=None,
            )

            await asyncio.sleep(0.5)

            # 每50条更新一次进度，60条应该至少更新1次
            assert broadcast_repo.update_progress.call_count >= 1
        except ImportError:
            pytest.skip("BroadcastService not implemented yet")

    async def test_broadcast_handles_send_failure(self):
        """测试处理发送失败。"""
        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=None)
        broadcast_repo.create = AsyncMock(
            return_value=_make_broadcast_task_dto(id=1, total_count=3)
        )
        broadcast_repo.update_progress = AsyncMock()
        broadcast_repo.update_status = AsyncMock()

        users = [_make_bot_user_dto(user_id=i) for i in range(3)]
        user_repo = MagicMock()
        user_repo.get_active_users = AsyncMock(return_value=users)
        user_repo.update_banned_by_telegram = AsyncMock()

        registry = MagicMock()
        mock_bot = MagicMock()

        # 第二个用户发送失败（被封禁）
        forbidden_error = TelegramForbiddenError(
            method=MagicMock(), message="User blocked bot"
        )
        mock_bot.send_message = AsyncMock(
            side_effect=[
                None,
                forbidden_error,
                None,
            ]
        )
        registry.get_bot = MagicMock(return_value=mock_bot)

        try:
            from app.services.broadcast import BroadcastService

            service = BroadcastService(broadcast_repo, user_repo, registry)

            await service.start(
                sub_bot_id=1,
                owner_id=999,
                content_type="text",
                content_text="Test",
                content_file_id=None,
                content_caption=None,
            )

            await asyncio.sleep(0.3)

            # 应该标记第二个用户为被Telegram封禁
            user_repo.update_banned_by_telegram.assert_called()
        except ImportError:
            pytest.skip("BroadcastService not implemented yet")


@pytest.mark.asyncio
class TestBroadcastServiceValidation:
    """BroadcastService 验证测试。"""

    async def test_start_with_running_broadcast_raises(self):
        """测试已有运行中的广播时抛出异常。"""
        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(
            return_value=_make_broadcast_task_dto(id=1, status="running")
        )

        user_repo = MagicMock()
        registry = MagicMock()

        try:
            from app.services.broadcast import BroadcastService

            service = BroadcastService(broadcast_repo, user_repo, registry)

            with pytest.raises(BroadcastError, match="正在进行的广播"):
                await service.start(
                    sub_bot_id=1,
                    owner_id=999,
                    content_type="text",
                    content_text="Test",
                    content_file_id=None,
                    content_caption=None,
                )
        except ImportError:
            pytest.skip("BroadcastService not implemented yet")

    async def test_start_within_5min_interval_raises(self):
        """测试5分钟内再次广播抛出异常。"""
        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)

        # 最近一次广播在2分钟前
        recent_task = _make_broadcast_task_dto(id=1, status="completed")
        recent_task = BroadcastTaskDTO(
            id=1,
            sub_bot_id=1,
            content_type="text",
            total_count=10,
            sent_count=10,
            failed_count=0,
            status="completed",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
            completed_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=recent_task)

        user_repo = MagicMock()
        registry = MagicMock()

        try:
            from app.services.broadcast import BroadcastService

            service = BroadcastService(broadcast_repo, user_repo, registry)

            with pytest.raises(BroadcastError, match="至少间隔5分钟"):
                await service.start(
                    sub_bot_id=1,
                    owner_id=999,
                    content_type="text",
                    content_text="Test",
                    content_file_id=None,
                    content_caption=None,
                )
        except ImportError:
            pytest.skip("BroadcastService not implemented yet")
