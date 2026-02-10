"""测试 UserRepo。"""

from __future__ import annotations

import pytest

from app.repositories.bot_repo import BotRepo
from app.repositories.user_repo import UserRepo


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
class TestUserRepoGetOrCreate:
    """UserRepo.get_or_create 测试。"""

    async def test_get_or_create_new_user(self, user_repo: UserRepo, bot_repo: BotRepo):
        """测试创建新用户。"""
        sub_bot_id = await _create_bot(bot_repo, 1000001)

        dto, is_new = await user_repo.get_or_create(
            sub_bot_id=sub_bot_id,
            user_id=111,
            username="alice",
            first_name="Alice",
            last_name="Smith",
        )

        assert is_new is True
        assert dto.user_id == 111
        assert dto.username == "alice"
        assert dto.is_blocked is False

    async def test_get_or_create_existing_user(self, user_repo: UserRepo, bot_repo: BotRepo):
        """测试获取已存在的用户。"""
        sub_bot_id = await _create_bot(bot_repo, 1000002)

        dto1, is_new1 = await user_repo.get_or_create(
            sub_bot_id=sub_bot_id,
            user_id=222,
            username="bob",
            first_name="Bob",
            last_name=None,
        )
        assert is_new1 is True

        dto2, is_new2 = await user_repo.get_or_create(
            sub_bot_id=sub_bot_id,
            user_id=222,
            username="bob_updated",
            first_name="Bobby",
            last_name=None,
        )
        assert is_new2 is False
        assert dto2.id == dto1.id


@pytest.mark.asyncio
class TestUserRepoGetActiveUsers:
    """UserRepo.get_active_users 测试。"""

    async def test_get_active_users_excludes_blocked(
        self, user_repo: UserRepo, bot_repo: BotRepo
    ):
        """测试排除封禁用户。"""
        sub_bot_id = await _create_bot(bot_repo, 1100001)

        await user_repo.get_or_create(sub_bot_id, 10, "u1", "U1", None)
        await user_repo.get_or_create(sub_bot_id, 20, "u2", "U2", None)
        await user_repo.get_or_create(sub_bot_id, 30, "u3", "U3", None)

        await user_repo.update_blocked(sub_bot_id, 20, True)

        active = await user_repo.get_active_users(sub_bot_id)

        user_ids = [u.user_id for u in active]
        assert 10 in user_ids
        assert 30 in user_ids
        assert 20 not in user_ids

    async def test_get_active_users_excludes_banned(
        self, user_repo: UserRepo, bot_repo: BotRepo
    ):
        """测试排除被 Telegram 屏蔽的用户。"""
        sub_bot_id = await _create_bot(bot_repo, 1100002)

        await user_repo.get_or_create(sub_bot_id, 40, "u4", "U4", None)
        await user_repo.get_or_create(sub_bot_id, 50, "u5", "U5", None)

        await user_repo.update_banned_by_telegram(sub_bot_id, 50, True)

        active = await user_repo.get_active_users(sub_bot_id)

        user_ids = [u.user_id for u in active]
        assert 40 in user_ids
        assert 50 not in user_ids


@pytest.mark.asyncio
class TestUserRepoUpdateBlocked:
    """UserRepo.update_blocked 测试。"""

    async def test_update_blocked(self, user_repo: UserRepo, bot_repo: BotRepo):
        """测试更新封禁状态。"""
        sub_bot_id = await _create_bot(bot_repo, 1200001)
        dto, _ = await user_repo.get_or_create(sub_bot_id, 60, "u6", "U6", None)
        assert dto.is_blocked is False

        await user_repo.update_blocked(sub_bot_id, 60, True)

        active = await user_repo.get_active_users(sub_bot_id)
        assert all(u.user_id != 60 for u in active)


@pytest.mark.asyncio
class TestUserRepoUpdateBannedByTelegram:
    """UserRepo.update_banned_by_telegram 测试。"""

    async def test_update_banned_by_telegram(
        self, user_repo: UserRepo, bot_repo: BotRepo
    ):
        """测试更新 Telegram 屏蔽状态。"""
        sub_bot_id = await _create_bot(bot_repo, 1300001)
        await user_repo.get_or_create(sub_bot_id, 70, "u7", "U7", None)

        await user_repo.update_banned_by_telegram(sub_bot_id, 70, True)

        active = await user_repo.get_active_users(sub_bot_id)
        assert all(u.user_id != 70 for u in active)


@pytest.mark.asyncio
class TestUserRepoGetUsersPaginated:
    """UserRepo.get_users_paginated 测试。"""

    async def test_get_users_paginated(self, user_repo: UserRepo, bot_repo: BotRepo):
        """测试分页查询用户。"""
        sub_bot_id = await _create_bot(bot_repo, 1400001)

        for i in range(15):
            await user_repo.get_or_create(sub_bot_id, 1000 + i, f"u{i}", f"U{i}", None)

        page1 = await user_repo.get_users_paginated(sub_bot_id, page=1, page_size=10)

        assert len(page1.items) == 10
        assert page1.total == 15
        assert page1.has_next is True
        assert page1.has_prev is False

        page2 = await user_repo.get_users_paginated(sub_bot_id, page=2, page_size=10)

        assert len(page2.items) == 5
        assert page2.has_next is False
        assert page2.has_prev is True


@pytest.mark.asyncio
class TestUserRepoDeleteBySubBot:
    """UserRepo.delete_by_sub_bot 测试。"""

    async def test_delete_by_sub_bot(self, user_repo: UserRepo, bot_repo: BotRepo):
        """测试删除某Bot的所有用户。"""
        sub_bot_id = await _create_bot(bot_repo, 1500001)

        await user_repo.get_or_create(sub_bot_id, 80, "u8", "U8", None)
        await user_repo.get_or_create(sub_bot_id, 81, "u9", "U9", None)

        deleted = await user_repo.delete_by_sub_bot(sub_bot_id)

        assert deleted == 2

        active = await user_repo.get_active_users(sub_bot_id)
        assert len(active) == 0
