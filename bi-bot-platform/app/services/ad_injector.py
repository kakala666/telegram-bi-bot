from __future__ import annotations

import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.dto import AdDTO, AdInjectionResult
from app.repositories.ad_repo import AdRepo

logger = logging.getLogger(__name__)

SEPARATOR = "\n\n━━━━━━━━━━━━━━━"


class AdInjectorService:
    """广告注入服务"""

    def __init__(self, ad_repo: AdRepo) -> None:
        self._ad_repo = ad_repo

    async def inject(
        self, text: str | None, sub_bot_id: int
    ) -> AdInjectionResult:
        """在文本末尾注入广告。

        Args:
            text: 原始文本（None表示纯媒体消息）
            sub_bot_id: 子Bot ID

        Returns:
            AdInjectionResult(text, keyboard)
        """
        ad = await self._ad_repo.get_next_ad(sub_bot_id)

        if ad is None:
            return AdInjectionResult(text=text or "", keyboard=None)

        ad_line = f"{SEPARATOR}\n{ad.ad_text}"

        if ad.ad_url and not ad.button_text:
            ad_line += f"\n{ad.ad_url}"

        ad_keyboard: InlineKeyboardMarkup | None = None
        if ad.button_text and ad.button_url:
            ad_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=ad.button_text, url=ad.button_url)]
            ])

        if text:
            return AdInjectionResult(
                text=f"{text}{ad_line}",
                keyboard=ad_keyboard,
            )

        return AdInjectionResult(
            text=ad_line.lstrip("\n"),
            keyboard=ad_keyboard,
        )

    async def get_active_ad(self, sub_bot_id: int) -> AdDTO | None:
        """获取某Bot当前应展示的广告（供外部查询用）"""
        return await self._ad_repo.get_active_for_bot(sub_bot_id)
