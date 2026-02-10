import logging

from aiogram import Bot, Router
from aiogram.types import Message

from app.dto import SubBotDTO
from app.services.forwarder import ForwarderService

logger = logging.getLogger(__name__)

router = Router(name="sub_owner_reply")


@router.message()
async def handle_owner_message(
    message: Message,
    bot: Bot,
    sub_bot: SubBotDTO,
    forwarder: ForwarderService,
) -> None:
    """Bot主人发送消息 -> 回复给终端用户

    此handler仅处理主人的消息。
    路由逻辑在 dispatcher 层通过 filter 区分。
    """
    if message.from_user.id != sub_bot.owner_id:
        return

    result = await forwarder.reply_to_user(bot, sub_bot, message)
    if not result.success:
        logger.debug(
            "回复失败 sub_bot_id=%s error=%s",
            sub_bot.id,
            result.error,
        )
