import logging

from aiogram import Bot, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.dto import SubBotDTO
from app.repositories.bot_repo import BotRepo
from app.repositories.user_repo import UserRepo

logger = logging.getLogger(__name__)

router = Router(name="sub_start")

DEFAULT_WELCOME = "欢迎！请直接发送消息，我们会尽快回复。"


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    bot: Bot,
    sub_bot: SubBotDTO,
    user_repo: UserRepo,
    bot_repo: BotRepo,
) -> None:
    """终端用户 /start 欢迎流程"""
    user = message.from_user

    bot_user, is_new = await user_repo.get_or_create(
        sub_bot_id=sub_bot.id,
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    if is_new:
        await bot_repo.increment_user_count(sub_bot.id)
    else:
        await user_repo.update_last_active(sub_bot.id, user.id)

    if bot_user.is_blocked:
        await message.answer("你已被限制使用此Bot")
        return

    welcome = sub_bot.welcome_message or DEFAULT_WELCOME
    await message.answer(welcome)
