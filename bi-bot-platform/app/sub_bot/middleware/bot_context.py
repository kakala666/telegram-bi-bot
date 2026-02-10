from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject

from app.repositories.bot_repo import BotRepo

logger = logging.getLogger(__name__)


class BotContextMiddleware(BaseMiddleware):
    """根据 bot.id 查询数据库，将 SubBotDTO 注入到 handler 参数中。

    如果 bot_id 不在数据库中或状态不是 active，则跳过处理。
    """

    def __init__(self, bot_repo: BotRepo) -> None:
        self._bot_repo = bot_repo

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        bot: Bot = data["bot"]
        bot_id = bot.id

        sub_bot = await self._bot_repo.get_by_bot_id(bot_id)

        if sub_bot is None:
            logger.warning("收到未知 bot_id=%s 的消息，忽略", bot_id)
            return None

        if sub_bot.status != "active":
            logger.debug("bot_id=%s 状态为 %s，忽略", bot_id, sub_bot.status)
            return None

        data["sub_bot"] = sub_bot

        return await handler(event, data)
