from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.master_bot.keyboards.inline import back_home_keyboard, home_keyboard

router = Router(name="start")

WELCOME_TEXT = (
    "欢迎使用双向机器人托管平台!\n"
    "\n"
    "本平台可以将你的 Telegram Bot 变成一个双向消息转发机器人：\n"
    "\n"
    "- 用户给你的Bot发消息，你会收到通知\n"
    "- 你回复消息，用户也能收到回复\n"
    "\n"
    "请选择操作："
)

HELP_TEXT = (
    "<b>使用帮助</b>\n"
    "\n"
    "1. <b>如何注册Bot？</b>\n"
    "   - 在 @BotFather 创建一个Bot\n"
    "   - 复制 Bot Token\n"
    "   - 发送 /register 并粘贴Token\n"
    "\n"
    "2. <b>如何使用双向机器人？</b>\n"
    "   - 注册成功后，你的Bot自动开始工作\n"
    "   - 用户给Bot发消息，你会在这里收到\n"
    "   - 直接回复转发的消息即可回复用户\n"
    "\n"
    "3. <b>可用命令</b>\n"
    "   /register - 注册新Bot\n"
    "   /mybot    - 管理我的Bot\n"
    "   /broadcast - 群发消息\n"
    "   /block    - 封禁用户\n"
    "\n"
    "4. <b>管理员命令</b>\n"
    "   /admin   - 管理面板\n"
    "   /ad      - 广告管理"
)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=home_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=back_home_keyboard())
