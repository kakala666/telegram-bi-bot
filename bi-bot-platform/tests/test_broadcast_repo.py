"""测试 BroadcastRepo。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.repositories.bot_repo import BotRepo
from app.repositories.broadcast_repo import BroadcastRepo


async def _create_bot(bot_repo: BotRepo, bot_id: int) -> int:
    """辅助函数：创建一个 SubBot 并返回其 id。"""
    dto = await bot_repo.create(
        bot_token_encrypted=f"tok_{bot_id}",
        bot_id=bot_id,
        bot_username=f"bot_{bot_id}",
        owner_id=1,
        owner_username=None,
    )
    return dto.id


@pytest.mark.asyncio
class TestBroadcastRepoCreate:
    """BroadcastRepo.create 测试。"""

    async def test_create(self, broadcast_repo: BroadcastRepo, bot_repo: BotRepo):
        """测试创建广播任务。"""
        sub_bot_id = await _create_bot(bot_repo, 4000001)

        dto = await broadcast_repo.create(
            sub_bot_id=sub_bot_id,
            owner_id=1,
            content_type="text",
            content_text="Hello!",
            content_file_id=None,
            content_caption=None,
            total_count=50,
        )

        assert dto.sub_bot_id == sub_bot_id
        assert dto.content_type == "text"
        assert dto.total_count == 50
        assert dto.sent_count == 0
        assert dto.failed_count == 0
        assert dto.status == "pending"


@pytest.mark.asyncio
class TestBroadcastRepoGetById:
    """BroadcastRepo.get_by_id 测试。"""

    async def test_get_by_id_found(
        self, broadcast_repo: BroadcastRepo, bot_repo: BotRepo
    ):
        """测试按主键查询。"""
        sub_bot_id = await _create_bot(bot_repo, 4100001)
        created = await broadcast_repo.create(
            sub_bot_id, 1, "text", "msg", None, None, 10
        )

        result = await broadcast_repo.get_by_id(created.id)

        assert result is not None
        assert result.id == created.id

    async def test_get_by_id_not_found(self, broadcast_repo: BroadcastRepo):
        """测试查询不存在的记录。"""
        result = await broadcast_repo.get_by_id(99999)
        assert result is None


@pytest.mark.asyncio
class TestBroadcastRepoGetRunningByBot:
    """BroadcastRepo.get_running_by_bot 测试。"""

    async def test_get_running_by_bot(
        self, broadcast_repo: BroadcastRepo, bot_repo: BotRepo
    ):
        """测试查询正在运行的广播任务。"""
        sub_bot_id = await _create_bot(bot_repo, 4200001)
        task = await broadcast_repo.create(
            sub_bot_id, 1, "text", "msg", None, None, 10
        )
        await broadcast_repo.update_status(task.id, "running")

        result = await broadcast_repo.get_running_by_bot(sub_bot_id)

        assert result is not None
        assert result.status == "running"

    async def test_get_running_by_bot_none(
        self, broadcast_repo: BroadcastRepo, bot_repo: BotRepo
    ):
        """测试无运行中任务时返回 None。"""
        sub_bot_id = await _create_bot(bot_repo, 4200002)

        result = await broadcast_repo.get_running_by_bot(sub_bot_id)

        assert result is None


@pytest.mark.asyncio
class TestBroadcastRepoUpdateProgress:
    """BroadcastRepo.update_progress 测试。"""

    async def test_update_progress(
        self, broadcast_repo: BroadcastRepo, bot_repo: BotRepo
    ):
        """测试更新广播进度。"""
        sub_bot_id = await _create_bot(bot_repo, 4300001)
        task = await broadcast_repo.create(
            sub_bot_id, 1, "text", "msg", None, None, 100
        )

        await broadcast_repo.update_progress(task.id, sent_count=30, failed_count=5)

        result = await broadcast_repo.get_by_id(task.id)
        assert result is not None
        assert result.sent_count == 30
        assert result.failed_count == 5


@pytest.mark.asyncio
class TestBroadcastRepoUpdateStatus:
    """BroadcastRepo.update_status 测试。"""

    async def test_update_status(
        self, broadcast_repo: BroadcastRepo, bot_repo: BotRepo
    ):
        """测试更新广播状态。"""
        sub_bot_id = await _create_bot(bot_repo, 4400001)
        task = await broadcast_repo.create(
            sub_bot_id, 1, "text", "msg", None, None, 10
        )

        await broadcast_repo.update_status(task.id, "running")

        result = await broadcast_repo.get_by_id(task.id)
        assert result is not None
        assert result.status == "running"

    async def test_update_status_with_completed_at(
        self, broadcast_repo: BroadcastRepo, bot_repo: BotRepo
    ):
        """测试更新状态并设置完成时间。"""
        sub_bot_id = await _create_bot(bot_repo, 4400002)
        task = await broadcast_repo.create(
            sub_bot_id, 1, "text", "msg", None, None, 10
        )

        now = datetime.now(timezone.utc)
        await broadcast_repo.update_status(task.id, "completed", completed_at=now)

        result = await broadcast_repo.get_by_id(task.id)
        assert result is not None
        assert result.status == "completed"
        assert result.completed_at is not None
