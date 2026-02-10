"""测试 BotRepo。"""

from __future__ import annotations

import pytest

from app.repositories.bot_repo import BotRepo


@pytest.mark.asyncio
class TestBotRepoCreate:
    """BotRepo.create 测试。"""

    async def test_create_returns_dto(self, bot_repo: BotRepo):
        """测试 create 返回 SubBotDTO。"""
        dto = await bot_repo.create(
            bot_token_encrypted="enc_tok_1",
            bot_id=100001,
            bot_username="test_bot_1",
            owner_id=999,
            owner_username="owner1",
        )

        assert dto.bot_id == 100001
        assert dto.bot_username == "test_bot_1"
        assert dto.owner_id == 999
        assert dto.owner_username == "owner1"
        assert dto.status == "active"
        assert dto.user_count == 0
        assert dto.message_count == 0


@pytest.mark.asyncio
class TestBotRepoGetById:
    """BotRepo.get_by_id 测试。"""

    async def test_get_by_id_found(self, bot_repo: BotRepo):
        """测试按主键查询存在的记录。"""
        created = await bot_repo.create(
            bot_token_encrypted="tok",
            bot_id=200001,
            bot_username="bot_a",
            owner_id=1,
            owner_username=None,
        )

        result = await bot_repo.get_by_id(created.id)

        assert result is not None
        assert result.id == created.id
        assert result.bot_id == 200001

    async def test_get_by_id_not_found(self, bot_repo: BotRepo):
        """测试按主键查询不存在的记录。"""
        result = await bot_repo.get_by_id(99999)
        assert result is None


@pytest.mark.asyncio
class TestBotRepoGetByBotId:
    """BotRepo.get_by_bot_id 测试。"""

    async def test_get_by_bot_id_found(self, bot_repo: BotRepo):
        """测试按 Telegram bot_id 查询。"""
        await bot_repo.create(
            bot_token_encrypted="tok",
            bot_id=300001,
            bot_username="bot_b",
            owner_id=1,
            owner_username=None,
        )

        result = await bot_repo.get_by_bot_id(300001)

        assert result is not None
        assert result.bot_id == 300001

    async def test_get_by_bot_id_not_found(self, bot_repo: BotRepo):
        """测试按 bot_id 查询不存在的记录。"""
        result = await bot_repo.get_by_bot_id(99999)
        assert result is None


@pytest.mark.asyncio
class TestBotRepoGetByOwner:
    """BotRepo.get_by_owner 测试。"""

    async def test_get_by_owner_multiple(self, bot_repo: BotRepo):
        """测试查询某用户的所有Bot。"""
        owner_id = 5000
        await bot_repo.create("t1", 400001, "b1", owner_id, None)
        await bot_repo.create("t2", 400002, "b2", owner_id, None)
        await bot_repo.create("t3", 400003, "b3", 9999, None)

        result = await bot_repo.get_by_owner(owner_id)

        assert len(result) == 2
        assert all(dto.owner_id == owner_id for dto in result)

    async def test_get_by_owner_empty(self, bot_repo: BotRepo):
        """测试查询无Bot的用户。"""
        result = await bot_repo.get_by_owner(88888)
        assert result == []


@pytest.mark.asyncio
class TestBotRepoGetAllActive:
    """BotRepo.get_all_active 测试。"""

    async def test_get_all_active(self, bot_repo: BotRepo):
        """测试查询所有活跃Bot。"""
        b1 = await bot_repo.create("t1", 500001, "b1", 1, None)
        b2 = await bot_repo.create("t2", 500002, "b2", 1, None)
        b3 = await bot_repo.create("t3", 500003, "b3", 1, None)
        await bot_repo.update_status(b3.id, "stopped")

        result = await bot_repo.get_all_active()

        bot_ids = [dto.bot_id for dto in result]
        assert 500001 in bot_ids
        assert 500002 in bot_ids
        assert 500003 not in bot_ids


@pytest.mark.asyncio
class TestBotRepoCountByOwner:
    """BotRepo.count_by_owner 测试。"""

    async def test_count_by_owner(self, bot_repo: BotRepo):
        """测试统计某用户的Bot数量。"""
        owner_id = 6000
        await bot_repo.create("t1", 600001, "b1", owner_id, None)
        await bot_repo.create("t2", 600002, "b2", owner_id, None)

        count = await bot_repo.count_by_owner(owner_id)

        assert count == 2

    async def test_count_by_owner_zero(self, bot_repo: BotRepo):
        """测试无Bot用户的计数。"""
        count = await bot_repo.count_by_owner(77777)
        assert count == 0


@pytest.mark.asyncio
class TestBotRepoCountAll:
    """BotRepo.count_all 测试。"""

    async def test_count_all(self, bot_repo: BotRepo):
        """测试按状态分组统计。"""
        await bot_repo.create("t1", 700001, "b1", 1, None)
        b2 = await bot_repo.create("t2", 700002, "b2", 1, None)
        await bot_repo.update_status(b2.id, "stopped")

        counts = await bot_repo.count_all()

        assert counts["total"] == 2
        assert counts.get("active", 0) == 1
        assert counts.get("stopped", 0) == 1


@pytest.mark.asyncio
class TestBotRepoUpdateStatus:
    """BotRepo.update_status 测试。"""

    async def test_update_status(self, bot_repo: BotRepo):
        """测试更新Bot状态。"""
        created = await bot_repo.create("tok", 800001, "b1", 1, None)

        await bot_repo.update_status(created.id, "stopped")

        result = await bot_repo.get_by_id(created.id)
        assert result is not None
        assert result.status == "stopped"


@pytest.mark.asyncio
class TestBotRepoUpdateWelcome:
    """BotRepo.update_welcome 测试。"""

    async def test_update_welcome(self, bot_repo: BotRepo):
        """测试更新欢迎语。"""
        created = await bot_repo.create("tok", 810001, "b1", 1, None)

        await bot_repo.update_welcome(created.id, "Welcome!")

        result = await bot_repo.get_by_id(created.id)
        assert result is not None
        assert result.welcome_message == "Welcome!"

    async def test_update_welcome_to_none(self, bot_repo: BotRepo):
        """测试清除欢迎语。"""
        created = await bot_repo.create("tok", 810002, "b2", 1, None)
        await bot_repo.update_welcome(created.id, "Hello")
        await bot_repo.update_welcome(created.id, None)

        result = await bot_repo.get_by_id(created.id)
        assert result is not None
        assert result.welcome_message is None


@pytest.mark.asyncio
class TestBotRepoIncrementCounts:
    """BotRepo increment 方法测试。"""

    async def test_increment_user_count(self, bot_repo: BotRepo):
        """测试递增用户计数。"""
        created = await bot_repo.create("tok", 820001, "b1", 1, None)
        assert created.user_count == 0

        await bot_repo.increment_user_count(created.id)

        result = await bot_repo.get_by_id(created.id)
        assert result is not None
        assert result.user_count == 1

    async def test_increment_user_count_delta(self, bot_repo: BotRepo):
        """测试递增用户计数（指定增量）。"""
        created = await bot_repo.create("tok", 820002, "b2", 1, None)

        await bot_repo.increment_user_count(created.id, delta=5)

        result = await bot_repo.get_by_id(created.id)
        assert result is not None
        assert result.user_count == 5

    async def test_increment_message_count(self, bot_repo: BotRepo):
        """测试递增消息计数。"""
        created = await bot_repo.create("tok", 820003, "b3", 1, None)

        await bot_repo.increment_message_count(created.id)
        await bot_repo.increment_message_count(created.id)

        result = await bot_repo.get_by_id(created.id)
        assert result is not None
        assert result.message_count == 2


@pytest.mark.asyncio
class TestBotRepoDelete:
    """BotRepo.delete 测试。"""

    async def test_delete(self, bot_repo: BotRepo):
        """测试删除Bot记录。"""
        created = await bot_repo.create("tok", 830001, "b1", 1, None)

        await bot_repo.delete(created.id)

        result = await bot_repo.get_by_id(created.id)
        assert result is None


@pytest.mark.asyncio
class TestBotRepoExistsByBotId:
    """BotRepo.exists_by_bot_id 测试。"""

    async def test_exists_by_bot_id_true(self, bot_repo: BotRepo):
        """测试 bot_id 已注册。"""
        await bot_repo.create("tok", 840001, "b1", 1, None)

        assert await bot_repo.exists_by_bot_id(840001) is True

    async def test_exists_by_bot_id_false(self, bot_repo: BotRepo):
        """测试 bot_id 未注册。"""
        assert await bot_repo.exists_by_bot_id(99999) is False
