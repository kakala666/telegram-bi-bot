"""子Bot全局错误处理中间件"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """捕获子Bot handler中的未处理异常，防止整个系统崩溃。"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except SkipHandler:
            raise
        except Exception:
            bot = data.get("bot")
            sub_bot = data.get("sub_bot")
            from_user = getattr(event, "from_user", None)

            bot_id = getattr(bot, "id", None) if bot else None
            sub_bot_id = getattr(sub_bot, "id", None) if sub_bot else None
            from_user_id = getattr(from_user, "id", None) if from_user else None

            logger.exception(
                "子Bot handler 未捕获异常 bot_id=%s sub_bot_id=%s from_user_id=%s",
                bot_id, sub_bot_id, from_user_id,
            )
            return None
