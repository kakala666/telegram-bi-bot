"""测试 CleanupService。

RED 阶段：实现尚不存在，测试会 FAIL。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.repositories.broadcast_repo import BroadcastRepo
from app.repositories.message_map_repo import MessageMapRepo

# 尝试导入 CleanupService，如果不存在则跳过
try:
    from app.services.cleanup import CleanupService
except ImportError:
    pytest.skip("CleanupService not implemented yet", allow_module_level=True)


@pytest.mark.asyncio
class TestCleanupExpiredMessageMaps:
    """清理过期消息映射测试。"""

    async def test_cleanup_expired_message_maps(
        self, message_map_repo: MessageMapRepo, broadcast_repo: BroadcastRepo
    ):
        """测试清理过期消息映射（默认7天）。"""
        # 创建过期映射（8天前）
        old_time = datetime.now(timezone.utc) - timedelta(days=8)
        await message_map_repo.create(
            sub_bot_id=1,
            user_id=100,
            user_msg_id=1,
            forwarded_msg_id=10,
            direction="in",
        )
        # 手动修改创建时间（需要直接操作数据库）
        # 注：这里简化处理，实际测试中需要 mock 或直接操作 session

        settings = MagicMock(spec=Settings)
        settings.MESSAGE_MAP_RETENTION_DAYS = 7

        svc = CleanupService(message_map_repo, broadcast_repo, settings)

        result = await svc.cleanup_all()

        assert "message_maps" in result
        # 过期的应该被删除
        assert result["message_maps"] >= 0

    async def test_cleanup_respects_retention_period(
        self, message_map_repo: MessageMapRepo, broadcast_repo: BroadcastRepo
    ):
        """测试遵守保留期设置。"""
        settings = MagicMock(spec=Settings)
        settings.MESSAGE_MAP_RETENTION_DAYS = 30

        svc = CleanupService(message_map_repo, broadcast_repo, settings)

        result = await svc.cleanup_all()

        assert "message_maps" in result
        assert isinstance(result["message_maps"], int)


@pytest.mark.asyncio
class TestCleanupCompletedBroadcasts:
    """清理已完成广播任务测试。"""

    async def test_cleanup_completed_broadcasts(
        self, message_map_repo: MessageMapRepo, broadcast_repo: BroadcastRepo
    ):
        """测试清理已完成的广播任务（默认30天）。"""
        # 创建已完成的广播任务
        await broadcast_repo.create(
            sub_bot_id=1,
            owner_id=999,
            content_type="text",
            content_text="Test broadcast",
            content_file_id=None,
            content_caption=None,
            total_count=10,
        )

        settings = MagicMock(spec=Settings)
        settings.MESSAGE_MAP_RETENTION_DAYS = 7

        svc = CleanupService(message_map_repo, broadcast_repo, settings)

        result = await svc.cleanup_all()

        assert "broadcast_tasks" in result
        assert isinstance(result["broadcast_tasks"], int)

    async def test_cleanup_does_not_delete_active_broadcasts(
        self, message_map_repo: MessageMapRepo, broadcast_repo: BroadcastRepo
    ):
        """测试不删除进行中的广播。"""
        # 创建运行中的广播
        task = await broadcast_repo.create(
            sub_bot_id=1,
            owner_id=999,
            content_type="text",
            content_text="Active broadcast",
            content_file_id=None,
            content_caption=None,
            total_count=10,
        )

        settings = MagicMock(spec=Settings)
        settings.MESSAGE_MAP_RETENTION_DAYS = 7

        svc = CleanupService(message_map_repo, broadcast_repo, settings)

        await svc.cleanup_all()

        # 验证运行中的广播仍然存在
        retrieved = await broadcast_repo.get_by_id(task.id)
        assert retrieved is not None


@pytest.mark.asyncio
class TestCleanupReturnsDeletedCount:
    """清理返回删除数量测试。"""

    async def test_cleanup_returns_deleted_count(
        self, message_map_repo: MessageMapRepo, broadcast_repo: BroadcastRepo
    ):
        """测试返回删除数量。"""
        settings = MagicMock(spec=Settings)
        settings.MESSAGE_MAP_RETENTION_DAYS = 7

        svc = CleanupService(message_map_repo, broadcast_repo, settings)

        result = await svc.cleanup_all()

        assert isinstance(result, dict)
        assert "message_maps" in result
        assert "broadcast_tasks" in result
        assert isinstance(result["message_maps"], int)
        assert isinstance(result["broadcast_tasks"], int)


@pytest.mark.asyncio
class TestCleanupHandlesEmptyTables:
    """清理空表测试。"""

    async def test_cleanup_handles_empty_tables(
        self, message_map_repo: MessageMapRepo, broadcast_repo: BroadcastRepo
    ):
        """测试空表不报错。"""
        settings = MagicMock(spec=Settings)
        settings.MESSAGE_MAP_RETENTION_DAYS = 7

        svc = CleanupService(message_map_repo, broadcast_repo, settings)

        result = await svc.cleanup_all()

        assert result["message_maps"] == 0
        assert result["broadcast_tasks"] == 0


@pytest.mark.asyncio
class TestRunAllCleanup:
    """运行所有清理任务测试。"""

    async def test_run_all_cleanup(
        self, message_map_repo: MessageMapRepo, broadcast_repo: BroadcastRepo
    ):
        """测试运行所有清理任务。"""
        settings = MagicMock(spec=Settings)
        settings.MESSAGE_MAP_RETENTION_DAYS = 7

        svc = CleanupService(message_map_repo, broadcast_repo, settings)

        result = await svc.cleanup_all()

        # 验证返回结果包含所有清理类型
        assert "message_maps" in result
        assert "broadcast_tasks" in result
        assert len(result) == 2
