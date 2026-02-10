"""测试 AdRepo。"""

from __future__ import annotations

import pytest

from app.repositories.ad_repo import AdRepo
from app.repositories.bot_repo import BotRepo


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
class TestAdRepoCreate:
    """AdRepo.create 测试。"""

    async def test_create(self, ad_repo: AdRepo):
        """测试创建广告。"""
        dto = await ad_repo.create(
            name="Test Ad",
            ad_text="Buy now!",
            ad_url="https://example.com",
            button_text="Click",
            button_url="https://example.com",
            target_type="global",
            target_bot_id=None,
            priority=10,
        )

        assert dto.name == "Test Ad"
        assert dto.ad_text == "Buy now!"
        assert dto.is_active is True
        assert dto.priority == 10
        assert dto.impression_count == 0


@pytest.mark.asyncio
class TestAdRepoGetAll:
    """AdRepo.get_all 测试。"""

    async def test_get_all(self, ad_repo: AdRepo):
        """测试查询所有广告。"""
        await ad_repo.create("Ad1", "text1", None, None, None, "global", None, 0)
        await ad_repo.create("Ad2", "text2", None, None, None, "global", None, 5)

        result = await ad_repo.get_all()

        assert len(result) == 2


@pytest.mark.asyncio
class TestAdRepoGetActiveForBot:
    """AdRepo.get_active_for_bot 测试。"""

    async def test_specific_ad_priority_over_global(
        self, ad_repo: AdRepo, bot_repo: BotRepo
    ):
        """测试专属广告优先于全局广告。"""
        sub_bot_id = await _create_bot(bot_repo, 3000001)

        await ad_repo.create(
            "Global Ad", "global text", None, None, None,
            "global", None, 100,
        )
        await ad_repo.create(
            "Specific Ad", "specific text", None, None, None,
            "specific", sub_bot_id, 1,
        )

        result = await ad_repo.get_active_for_bot(sub_bot_id)

        assert result is not None
        assert result.name == "Specific Ad"
        assert result.target_type == "specific"

    async def test_global_ad_when_no_specific(self, ad_repo: AdRepo, bot_repo: BotRepo):
        """测试无专属广告时返回全局广告。"""
        sub_bot_id = await _create_bot(bot_repo, 3000002)

        await ad_repo.create(
            "Global Ad", "global text", None, None, None,
            "global", None, 10,
        )

        result = await ad_repo.get_active_for_bot(sub_bot_id)

        assert result is not None
        assert result.target_type == "global"

    async def test_no_active_ad(self, ad_repo: AdRepo, bot_repo: BotRepo):
        """测试无活跃广告时返回 None。"""
        sub_bot_id = await _create_bot(bot_repo, 3000003)

        result = await ad_repo.get_active_for_bot(sub_bot_id)

        assert result is None

    async def test_highest_priority_selected(self, ad_repo: AdRepo):
        """测试按优先级选择最高的广告。"""
        await ad_repo.create("Low", "low", None, None, None, "global", None, 1)
        await ad_repo.create("High", "high", None, None, None, "global", None, 99)
        await ad_repo.create("Mid", "mid", None, None, None, "global", None, 50)

        result = await ad_repo.get_active_for_bot(99999)

        assert result is not None
        assert result.name == "High"


@pytest.mark.asyncio
class TestAdRepoIncrementImpression:
    """AdRepo.increment_impression 测试。"""

    async def test_increment_impression(self, ad_repo: AdRepo):
        """测试递增展示计数。"""
        dto = await ad_repo.create("Ad", "text", None, None, None, "global", None, 0)
        assert dto.impression_count == 0

        await ad_repo.increment_impression(dto.id)
        await ad_repo.increment_impression(dto.id)

        result = await ad_repo.get_by_id(dto.id)
        assert result is not None
        assert result.impression_count == 2


@pytest.mark.asyncio
class TestAdRepoUpdate:
    """AdRepo.update 测试。"""

    async def test_update_partial_fields(self, ad_repo: AdRepo):
        """测试部分字段更新。"""
        dto = await ad_repo.create(
            "Original", "original text", None, None, None, "global", None, 0
        )

        await ad_repo.update(dto.id, name="Updated", priority=50)

        result = await ad_repo.get_by_id(dto.id)
        assert result is not None
        assert result.name == "Updated"
        assert result.priority == 50
        assert result.ad_text == "original text"

    async def test_update_is_active(self, ad_repo: AdRepo):
        """测试停用广告。"""
        dto = await ad_repo.create(
            "Active Ad", "text", None, None, None, "global", None, 0
        )

        await ad_repo.update(dto.id, is_active=False)

        result = await ad_repo.get_by_id(dto.id)
        assert result is not None
        assert result.is_active is False
