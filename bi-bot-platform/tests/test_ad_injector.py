"""测试 AdInjectorService。"""

from __future__ import annotations

import pytest
from aiogram.types import InlineKeyboardMarkup

from app.repositories.ad_repo import AdRepo
from app.repositories.bot_repo import BotRepo
from app.services.ad_injector import AdInjectorService


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
class TestAdInjectorInjectNoAd:
    """inject 无广告时返回原文本。"""

    async def test_no_active_ad_returns_original(self, ad_repo, bot_repo):
        """测试无活跃广告时返回原文本。"""
        sub_bot_id = await _create_bot(bot_repo, 5000001)
        svc = AdInjectorService(ad_repo)

        result = await svc.inject(text="Hello user", sub_bot_id=sub_bot_id)

        assert result.text == "Hello user"
        assert result.keyboard is None

    async def test_no_ad_with_none_text(self, ad_repo, bot_repo):
        """测试无广告且文本为 None 时返回空字符串。"""
        sub_bot_id = await _create_bot(bot_repo, 5000002)
        svc = AdInjectorService(ad_repo)

        result = await svc.inject(text=None, sub_bot_id=sub_bot_id)

        assert result.text == ""
        assert result.keyboard is None


@pytest.mark.asyncio
class TestAdInjectorInjectWithAd:
    """inject 有广告时正确拼接。"""

    async def test_text_ad_appended(self, ad_repo, bot_repo):
        """测试文本广告被追加到原文本末尾。"""
        sub_bot_id = await _create_bot(bot_repo, 5100001)
        await ad_repo.create(
            "Test Ad", "Buy now!", None, None, None,
            "specific", sub_bot_id, 10,
        )
        svc = AdInjectorService(ad_repo)

        result = await svc.inject(text="Hello user", sub_bot_id=sub_bot_id)

        assert "Hello user" in result.text
        assert "Buy now!" in result.text
        assert result.keyboard is None

    async def test_ad_url_appended_without_button(self, ad_repo, bot_repo):
        """测试有 ad_url 但无 button 时 URL 追加到文本。"""
        sub_bot_id = await _create_bot(bot_repo, 5100002)
        await ad_repo.create(
            "URL Ad", "Check this", "https://example.com", None, None,
            "specific", sub_bot_id, 10,
        )
        svc = AdInjectorService(ad_repo)

        result = await svc.inject(text="Hi", sub_bot_id=sub_bot_id)

        assert "https://example.com" in result.text
        assert result.keyboard is None

    async def test_none_text_with_ad(self, ad_repo, bot_repo):
        """测试原文本为 None 时只返回广告文本。"""
        sub_bot_id = await _create_bot(bot_repo, 5100003)
        await ad_repo.create(
            "Ad", "Ad text", None, None, None,
            "specific", sub_bot_id, 10,
        )
        svc = AdInjectorService(ad_repo)

        result = await svc.inject(text=None, sub_bot_id=sub_bot_id)

        assert "Ad text" in result.text

    async def test_impression_incremented(self, ad_repo, bot_repo):
        """测试展示计数递增。"""
        sub_bot_id = await _create_bot(bot_repo, 5100004)
        ad = await ad_repo.create(
            "Ad", "text", None, None, None,
            "specific", sub_bot_id, 10,
        )
        svc = AdInjectorService(ad_repo)

        await svc.inject(text="msg", sub_bot_id=sub_bot_id)
        await svc.inject(text="msg2", sub_bot_id=sub_bot_id)

        updated = await ad_repo.get_by_id(ad.id)
        assert updated is not None
        assert updated.impression_count == 2


@pytest.mark.asyncio
class TestAdInjectorButton:
    """按钮广告生成 InlineKeyboardMarkup。"""

    async def test_button_ad_creates_keyboard(self, ad_repo, bot_repo):
        """测试有 button_text 和 button_url 时生成键盘。"""
        sub_bot_id = await _create_bot(bot_repo, 5200001)
        await ad_repo.create(
            "Button Ad", "Click below", None,
            "Visit", "https://example.com",
            "specific", sub_bot_id, 10,
        )
        svc = AdInjectorService(ad_repo)

        result = await svc.inject(text="Hello", sub_bot_id=sub_bot_id)

        assert result.keyboard is not None
        assert isinstance(result.keyboard, InlineKeyboardMarkup)
        button = result.keyboard.inline_keyboard[0][0]
        assert button.text == "Visit"
        assert button.url == "https://example.com"

    async def test_button_ad_url_not_in_text(self, ad_repo, bot_repo):
        """测试有按钮时 ad_url 不追加到文本中。"""
        sub_bot_id = await _create_bot(bot_repo, 5200002)
        await ad_repo.create(
            "Button Ad", "Ad text", "https://hidden.com",
            "Click", "https://button.com",
            "specific", sub_bot_id, 10,
        )
        svc = AdInjectorService(ad_repo)

        result = await svc.inject(text="Hello", sub_bot_id=sub_bot_id)

        assert "https://hidden.com" not in result.text
        assert result.keyboard is not None


@pytest.mark.asyncio
class TestAdInjectorGetActiveAd:
    """AdInjectorService.get_active_ad 测试。"""

    async def test_get_active_ad_found(self, ad_repo, bot_repo):
        """测试获取活跃广告。"""
        sub_bot_id = await _create_bot(bot_repo, 5300001)
        await ad_repo.create(
            "Active", "text", None, None, None,
            "specific", sub_bot_id, 10,
        )
        svc = AdInjectorService(ad_repo)

        result = await svc.get_active_ad(sub_bot_id)

        assert result is not None
        assert result.name == "Active"

    async def test_get_active_ad_none(self, ad_repo, bot_repo):
        """测试无活跃广告时返回 None。"""
        sub_bot_id = await _create_bot(bot_repo, 5300002)
        svc = AdInjectorService(ad_repo)

        result = await svc.get_active_ad(sub_bot_id)

        assert result is None
