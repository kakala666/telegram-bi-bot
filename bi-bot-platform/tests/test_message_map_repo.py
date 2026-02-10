"""测试 MessageMapRepo。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.repositories.bot_repo import BotRepo
from app.repositories.message_map_repo import MessageMapRepo


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
class TestMessageMapRepoCreate:
    """MessageMapRepo.create 测试。"""

    async def test_create(
        self, message_map_repo: MessageMapRepo, bot_repo: BotRepo
    ):
        """测试创建消息映射。"""
        sub_bot_id = await _create_bot(bot_repo, 2000001)

        await message_map_repo.create(
            sub_bot_id=sub_bot_id,
            user_id=100,
            user_msg_id=10,
            forwarded_msg_id=20,
            direction="in",
        )

        result = await message_map_repo.get_by_forwarded_msg(sub_bot_id, 20)
        assert result is not None
        user_id, user_msg_id = result
        assert user_id == 100
        assert user_msg_id == 10


@pytest.mark.asyncio
class TestMessageMapRepoGetByForwardedMsg:
    """MessageMapRepo.get_by_forwarded_msg 测试。"""

    async def test_get_by_forwarded_msg_not_found(
        self, message_map_repo: MessageMapRepo, bot_repo: BotRepo
    ):
        """测试查询不存在的映射。"""
        sub_bot_id = await _create_bot(bot_repo, 2100001)

        result = await message_map_repo.get_by_forwarded_msg(sub_bot_id, 99999)
        assert result is None


@pytest.mark.asyncio
class TestMessageMapRepoCleanupExpired:
    """MessageMapRepo.cleanup_expired 测试。"""

    async def test_cleanup_expired(
        self, message_map_repo: MessageMapRepo, bot_repo: BotRepo, session_factory
    ):
        """测试清理过期映射记录。"""
        from sqlalchemy import update

        from app.database.models import MessageMap

        sub_bot_id = await _create_bot(bot_repo, 2200001)

        await message_map_repo.create(sub_bot_id, 100, 1, 101, "in")
        await message_map_repo.create(sub_bot_id, 100, 2, 102, "in")

        old_time = datetime.now(timezone.utc) - timedelta(days=31)
        async with session_factory() as session:
            stmt = (
                update(MessageMap)
                .where(MessageMap.forwarded_msg_id == 101)
                .values(created_at=old_time)
            )
            await session.execute(stmt)
            await session.commit()

        deleted = await message_map_repo.cleanup_expired(retention_days=30)

        assert deleted == 1

        result = await message_map_repo.get_by_forwarded_msg(sub_bot_id, 102)
        assert result is not None


@pytest.mark.asyncio
class TestMessageMapRepoDeleteBySubBot:
    """MessageMapRepo.delete_by_sub_bot 测试。"""

    async def test_delete_by_sub_bot(
        self, message_map_repo: MessageMapRepo, bot_repo: BotRepo
    ):
        """测试删除某Bot的所有映射。"""
        sub_bot_id = await _create_bot(bot_repo, 2300001)

        await message_map_repo.create(sub_bot_id, 100, 1, 201, "in")
        await message_map_repo.create(sub_bot_id, 100, 2, 202, "in")

        deleted = await message_map_repo.delete_by_sub_bot(sub_bot_id)

        assert deleted == 2
