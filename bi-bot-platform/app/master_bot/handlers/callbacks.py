"""统一的 callback_query 路由分发

根据 callback_data 前缀路由到对应 handler。
大部分回调已在各自的 handler 模块中通过 router 注册，
此模块处理通用导航回调（nav_home, nav_help, nav_cancel 等）。
"""

from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.master_bot.keyboards.inline import back_home_keyboard, home_keyboard

router = Router(name="callbacks")

HELP_TEXT = (
    "使用帮助\n\n"
    "1. 如何注册Bot？\n"
    "   - 在 @BotFather 创建一个Bot\n"
    "   - 复制 Bot Token\n"
    "   - 发送 /register 并粘贴Token\n\n"
    "2. 如何使用双向机器人？\n"
    "   - 注册成功后，你的Bot自动开始工作\n"
    "   - 用户给Bot发消息，你会在这里收到\n"
    "   - 直接回复转发的消息即可回复用户\n\n"
    "3. 可用命令\n"
    "   /register - 注册新Bot\n"
    "   /mybot    - 管理我的Bot\n"
    "   /broadcast - 群发消息\n"
    "   /block    - 封禁用户"
)

WELCOME_TEXT = (
    "欢迎使用双向机器人托管平台!\n\n"
    "本平台可以将你的 Telegram Bot 变成一个\n"
    "双向消息转发机器人：\n\n"
    "- 用户给你的Bot发消息，你会收到通知\n"
    "- 你回复消息，用户也能收到回复\n\n"
    "请选择操作："
)


@router.callback_query(lambda c: c.data == "nav_home")
async def cb_nav_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=home_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data == "nav_help")
async def cb_nav_help(callback: CallbackQuery) -> None:
    await callback.message.edit_text(HELP_TEXT, reply_markup=back_home_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data == "nav_cancel")
async def cb_nav_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("操作已取消", reply_markup=home_keyboard())
    await callback.answer()
