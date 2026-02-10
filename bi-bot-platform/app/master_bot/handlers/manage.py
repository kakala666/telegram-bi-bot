"""/mybot 命令 - Bot管理面板"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.master_bot.keyboards.inline import (
    STATUS_LABELS,
    back_home_keyboard,
    bot_list_keyboard,
    bot_manage_keyboard,
    broadcast_cancel_keyboard,
    confirm_delete_keyboard,
    confirm_stop_keyboard,
    no_bot_keyboard,
    user_list_keyboard,
    welcome_keyboard,
)
from app.master_bot.states import BroadcastStates, WelcomeStates
from app.repositories.bot_repo import BotRepo
from app.repositories.broadcast_repo import BroadcastRepo
from app.repositories.message_map_repo import MessageMapRepo
from app.repositories.user_repo import UserRepo
from app.services.token_encryptor import TokenEncryptor
from app.sub_bot.registry import BotRegistry

logger = logging.getLogger(__name__)

router = Router(name="manage")


def _format_bot_list(bots: list) -> str:
    lines = ["你的Bot列表：\n"]
    for i, bot in enumerate(bots, 1):
        label = STATUS_LABELS.get(bot.status, bot.status)
        lines.append(
            f"{i}. @{bot.bot_username} - {label}\n"
            f"   用户数: {bot.user_count:,} | 消息数: {bot.message_count:,}"
        )
    return "\n".join(lines)


def _format_bot_detail(bot) -> str:
    label = STATUS_LABELS.get(bot.status, bot.status)
    created = bot.created_at.strftime("%Y-%m-%d")
    return (
        f"@{bot.bot_username} 管理面板\n\n"
        f"状态: {label}\n"
        f"用户数: {bot.user_count:,}\n"
        f"总消息数: {bot.message_count:,}\n"
        f"注册时间: {created}"
    )


# ── /mybot 命令 ──────────────────────────────────────────────


@router.message(Command("mybot"))
async def cmd_mybot(message: Message, bot_repo: BotRepo) -> None:
    user_id = message.from_user.id
    bots = await bot_repo.get_by_owner(user_id)
    if not bots:
        await message.answer("你还没有注册任何Bot", reply_markup=no_bot_keyboard())
        return
    await message.answer(_format_bot_list(bots), reply_markup=bot_list_keyboard(bots))


# ── Bot列表回调（mybot_list）──────────────────────────────────


@router.callback_query(lambda c: c.data == "mybot_list")
async def cb_mybot_list(callback: CallbackQuery, bot_repo: BotRepo) -> None:
    user_id = callback.from_user.id
    bots = await bot_repo.get_by_owner(user_id)
    if not bots:
        await callback.message.edit_text(
            "你还没有注册任何Bot", reply_markup=no_bot_keyboard()
        )
    else:
        await callback.message.edit_text(
            _format_bot_list(bots), reply_markup=bot_list_keyboard(bots)
        )
    await callback.answer()


# ── 单Bot管理面板（bot_manage:{id}）─────────────────────────


@router.callback_query(lambda c: c.data and c.data.startswith("bot_manage:"))
async def cb_bot_manage(callback: CallbackQuery, bot_repo: BotRepo) -> None:
    bot_id = int(callback.data.split(":")[1])
    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != callback.from_user.id:
        await callback.answer("Bot不存在或无权限", show_alert=True)
        return
    await callback.message.edit_text(
        _format_bot_detail(bot),
        reply_markup=bot_manage_keyboard(bot.id, bot.status),
    )
    await callback.answer()


# ── 停止Bot（bot_stop:{id}）──────────────────────────────────


@router.callback_query(lambda c: c.data and c.data.startswith("bot_stop:"))
async def cb_bot_stop(callback: CallbackQuery, bot_repo: BotRepo) -> None:
    bot_id = int(callback.data.split(":")[1])
    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != callback.from_user.id:
        await callback.answer("Bot不存在或无权限", show_alert=True)
        return
    await callback.message.edit_text(
        f"确定要停止 @{bot.bot_username} 吗？\n\n"
        "停止后，用户发给Bot的消息将不会被转发。\n"
        "你可以随时重新启动。",
        reply_markup=confirm_stop_keyboard(bot.id),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("bot_stop_confirm:"))
async def cb_bot_stop_confirm(
    callback: CallbackQuery, bot_repo: BotRepo, registry: BotRegistry
) -> None:
    bot_id = int(callback.data.split(":")[1])
    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != callback.from_user.id:
        await callback.answer("Bot不存在或无权限", show_alert=True)
        return
    # 调用 registry.remove_bot 停止Bot（即使失败也继续更新数据库）
    try:
        await registry.remove_bot(bot.bot_id)
    except Exception as e:
        logger.warning("Registry停止Bot失败: %s", e)
    await bot_repo.update_status(bot.id, "stopped")
    await callback.message.edit_text(
        f"Bot @{bot.bot_username} 已停止",
        reply_markup=back_home_keyboard(),
    )
    await callback.answer()


# ── 重启Bot（bot_restart:{id}）───────────────────────────────


@router.callback_query(lambda c: c.data and c.data.startswith("bot_restart:"))
async def cb_bot_restart(
    callback: CallbackQuery, bot_repo: BotRepo, registry: BotRegistry, encryptor: TokenEncryptor
) -> None:
    bot_id = int(callback.data.split(":")[1])
    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != callback.from_user.id:
        await callback.answer("Bot不存在或无权限", show_alert=True)
        return

    # 获取加密的Token并解密
    encrypted_token = await bot_repo.get_encrypted_token(bot.id)
    if not encrypted_token:
        await callback.message.edit_text(
            f"Bot @{bot.bot_username} 启动失败：无法获取Token",
            reply_markup=bot_manage_keyboard(bot.id, bot.status),
        )
        await callback.answer()
        return

    try:
        token = encryptor.decrypt(encrypted_token)
        # 调用 registry.add_bot 启动Bot
        await registry.add_bot(token, bot.bot_id)
        await bot_repo.update_status(bot.id, "active")
        await callback.message.edit_text(
            f"Bot @{bot.bot_username} 已启动",
            reply_markup=bot_manage_keyboard(bot.id, "active"),
        )
    except Exception as e:
        logger.error("重启Bot失败: %s", e)
        await callback.message.edit_text(
            f"Bot @{bot.bot_username} 启动失败，请稍后重试",
            reply_markup=bot_manage_keyboard(bot.id, bot.status),
        )
    await callback.answer()


# ── 删除Bot（bot_delete:{id}）────────────────────────────────


@router.callback_query(lambda c: c.data and c.data.startswith("bot_delete:") and "confirm" not in c.data)
async def cb_bot_delete(callback: CallbackQuery, bot_repo: BotRepo) -> None:
    bot_id = int(callback.data.split(":")[1])
    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != callback.from_user.id:
        await callback.answer("Bot不存在或无权限", show_alert=True)
        return
    await callback.message.edit_text(
        f"确定要删除 @{bot.bot_username} 吗？\n\n"
        "删除后：\n"
        "- Bot将停止运行\n"
        "- 所有用户数据将被清除\n"
        "- 所有消息记录将被清除\n"
        "- 此操作不可撤销",
        reply_markup=confirm_delete_keyboard(bot.id),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("bot_delete_confirm:"))
async def cb_bot_delete_confirm(
    callback: CallbackQuery,
    bot_repo: BotRepo,
    user_repo: UserRepo,
    msg_map_repo: MessageMapRepo,
    broadcast_repo: BroadcastRepo,
    registry: BotRegistry,
) -> None:
    bot_id = int(callback.data.split(":")[1])
    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != callback.from_user.id:
        await callback.answer("Bot不存在或无权限", show_alert=True)
        return
    username = bot.bot_username
    # 调用 registry.remove_bot 停止Bot
    await registry.remove_bot(bot.bot_id)
    await msg_map_repo.delete_by_sub_bot(bot.id)
    await broadcast_repo.delete_by_sub_bot(bot.id)
    await user_repo.delete_by_sub_bot(bot.id)
    await bot_repo.delete(bot.id)
    await callback.message.edit_text(
        f"Bot @{username} 已删除",
        reply_markup=back_home_keyboard(),
    )
    await callback.answer()


# ── 设置欢迎语（bot_welcome:{id}）────────────────────────────


@router.callback_query(
    lambda c: c.data and c.data.startswith("bot_welcome:") and "default" not in c.data
)
async def cb_bot_welcome(
    callback: CallbackQuery, state: FSMContext, bot_repo: BotRepo
) -> None:
    bot_id = int(callback.data.split(":")[1])
    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != callback.from_user.id:
        await callback.answer("Bot不存在或无权限", show_alert=True)
        return
    current = bot.welcome_message or "（未设置，使用默认欢迎语）"
    await state.set_state(WelcomeStates.waiting_welcome)
    await state.update_data(welcome_bot_id=bot.id)
    await callback.message.edit_text(
        "请发送新的欢迎语\n\n"
        "当用户首次使用你的Bot（发送/start）时，\n"
        "会看到这条欢迎语。\n\n"
        f"当前欢迎语:\n\"{current}\"\n\n"
        "支持 HTML 格式（<b>粗体</b>等）",
        reply_markup=welcome_keyboard(bot.id),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("bot_welcome_default:"))
async def cb_bot_welcome_default(
    callback: CallbackQuery, state: FSMContext, bot_repo: BotRepo
) -> None:
    bot_id = int(callback.data.split(":")[1])
    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != callback.from_user.id:
        await callback.answer("Bot不存在或无权限", show_alert=True)
        return
    await bot_repo.update_welcome(bot.id, None)
    await state.clear()
    await callback.message.edit_text(
        "欢迎语已重置为默认",
        reply_markup=bot_manage_keyboard(bot.id, bot.status),
    )
    await callback.answer()


@router.message(WelcomeStates.waiting_welcome)
async def on_welcome_text(
    message: Message, state: FSMContext, bot_repo: BotRepo
) -> None:
    data = await state.get_data()
    bot_id = data.get("welcome_bot_id")
    if not bot_id:
        await state.clear()
        return
    text = message.text or ""
    if len(text) > 4096:
        await message.answer("欢迎语不能超过4096个字符，请重新发送")
        return
    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != message.from_user.id:
        await state.clear()
        return
    await bot_repo.update_welcome(bot.id, text)
    await state.clear()
    await message.answer(
        "欢迎语已更新",
        reply_markup=bot_manage_keyboard(bot.id, bot.status),
    )


# ── 查看用户列表（bot_users:{id}:{page}）────────────────────


@router.callback_query(lambda c: c.data and c.data.startswith("bot_users:"))
async def cb_bot_users(
    callback: CallbackQuery, bot_repo: BotRepo, user_repo: UserRepo
) -> None:
    parts = callback.data.split(":")
    bot_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 1

    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != callback.from_user.id:
        await callback.answer("Bot不存在或无权限", show_alert=True)
        return

    result = await user_repo.get_users_paginated(bot.id, page, page_size=10)

    if not result.items:
        await callback.message.edit_text(
            f"@{bot.bot_username} 还没有用户",
            reply_markup=bot_manage_keyboard(bot.id, bot.status),
        )
        await callback.answer()
        return

    lines = [f"@{bot.bot_username} 的用户列表 (共{result.total}人)\n"]
    for i, user in enumerate(result.items, (page - 1) * 10 + 1):
        status = "已封禁" if user.is_blocked else "活跃"
        name = user.display_name
        if user.username:
            name += f" (@{user.username})"
        else:
            name += f" (ID:{user.user_id})"
        last = user.last_active.strftime("%Y-%m-%d %H:%M")
        lines.append(f"{i}. {name} - {status}\n   最后活跃: {last}")

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=user_list_keyboard(bot.id, page, result.total_pages),
    )
    await callback.answer()


# ── 广播消息入口（bot_broadcast:{id}）────────────────────────


@router.callback_query(lambda c: c.data and c.data.startswith("bot_broadcast:"))
async def cb_bot_broadcast(
    callback: CallbackQuery, bot_repo: BotRepo, user_repo: UserRepo, state: FSMContext
) -> None:
    """管理面板广播入口 - 进入广播FSM流程"""
    bot_id = int(callback.data.split(":")[1])
    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != callback.from_user.id:
        await callback.answer("Bot不存在或无权限", show_alert=True)
        return

    active_count = await user_repo.count_active(bot.id)

    await state.update_data(broadcast_bot_id=bot.id)
    await state.set_state(BroadcastStates.waiting_content)

    await callback.message.edit_text(
        f"准备向 @{bot.bot_username} 的 {active_count} 个活跃用户广播消息\n\n"
        "请发送要广播的内容\n\n"
        "支持的内容类型:\n"
        "- 文字消息\n"
        "- 图片（可带文字说明）\n"
        "- 视频（可带文字说明）\n"
        "- 文件\n"
        "- 音频",
        reply_markup=broadcast_cancel_keyboard(),
    )
    await callback.answer()


# ── noop 回调（分页页码按钮）─────────────────────────────────


@router.callback_query(lambda c: c.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()
