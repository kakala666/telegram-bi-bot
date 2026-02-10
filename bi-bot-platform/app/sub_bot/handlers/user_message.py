import logging

from aiogram import Bot, Router
from aiogram.types import Message

from app.dto import SubBotDTO
from app.services.forwarder import ForwarderService
from app.sub_bot.filters import IsOwnerFilter

logger = logging.getLogger(__name__)

router = Router(name="sub_user_message")


@router.message(IsOwnerFilter(is_owner=False))
async def handle_user_message(
    message: Message,
    bot: Bot,
    sub_bot: SubBotDTO,
    forwarder: ForwarderService,
) -> None:
    """终端用户发送消息 -> 转发给Bot主人

    此handler仅处理非主人的消息。
    主人消息由 owner_reply handler 处理。
    路由逻辑在 dispatcher 层通过 filter 区分。
    """
    result = await forwarder.forward_to_owner(bot, sub_bot, message)
    if not result.success:
        logger.debug(
            "转发失败 sub_bot_id=%s user_id=%s error=%s",
            sub_bot.id,
            message.from_user.id,
            result.error,
        )
