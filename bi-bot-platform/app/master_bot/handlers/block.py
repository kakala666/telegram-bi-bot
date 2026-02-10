"""/block 命令 - 封禁/解封用户"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.master_bot.keyboards.inline import (
    back_home_keyboard,
    block_select_keyboard,
    cancel_keyboard,
    unblock_confirm_keyboard,
)
from app.master_bot.states import BlockStates
from app.repositories.bot_repo import BotRepo
from app.repositories.user_repo import UserRepo

logger = logging.getLogger(__name__)

router = Router(name="block")


async def _handle_block_user(
    owner_id: int,
    target_user_id: int,
    bot_repo: BotRepo,
    user_repo: UserRepo,
) -> tuple[str, object | None]:
    """查找用户并返回 (文本, 键盘或None)"""
    records = await user_repo.find_user_across_bots(owner_id, target_user_id)
    if not records:
        return "未找到该用户", back_home_keyboard()

    if len(records) == 1:
        record = records[0]
        bot = await bot_repo.get_by_id(record.sub_bot_id)
        bot_username = bot.bot_username if bot else "Unknown"
        if record.is_blocked:
            return (
                f"用户 {record.display_name} (ID:{record.user_id}) "
                f"当前状态: 已封禁",
                unblock_confirm_keyboard(record.sub_bot_id, record.user_id),
            )
        await user_repo.update_blocked(record.sub_bot_id, record.user_id, True)
        return (
            f"已封禁用户 {record.display_name} "
            f"(ID:{record.user_id}) - @{bot_username}",
            back_home_keyboard(),
        )

    # 多个Bot中都有该用户
    bots_map: dict[int, str] = {}
    for r in records:
        bot = await bot_repo.get_by_id(r.sub_bot_id)
        bots_map[r.sub_bot_id] = bot.bot_username if bot else "Unknown"

    first = records[0]
    return (
        f"用户 {first.display_name} (ID:{first.user_id}) 存在于多个Bot中：",
        block_select_keyboard(records, bots_map, target_user_id),
    )


# ── /block 命令 ──────────────────────────────────────────────


@router.message(Command("block"))
async def cmd_block(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    bot_repo: BotRepo,
    user_repo: UserRepo,
) -> None:
    args = command.args
    if args and args.strip().isdigit():
        target_user_id = int(args.strip())
        text, keyboard = await _handle_block_user(
            message.from_user.id, target_user_id, bot_repo, user_repo
        )
        await message.answer(text, reply_markup=keyboard)
        return

    await state.set_state(BlockStates.waiting_user_id)
    await message.answer(
        "请发送要封禁的用户ID\n\n"
        "你可以在转发的消息头部找到用户ID\n"
        "格式: 纯数字，如 123456789",
        reply_markup=cancel_keyboard(),
    )


@router.message(BlockStates.waiting_user_id)
async def on_block_user_id(
    message: Message,
    state: FSMContext,
    bot_repo: BotRepo,
    user_repo: UserRepo,
) -> None:
    text = (message.text or "").strip()
    if not text.isdigit() or len(text) > 15:
        await message.answer("请输入有效的用户ID（纯数字）")
        return

    target_user_id = int(text)
    await state.clear()
    reply_text, keyboard = await _handle_block_user(
        message.from_user.id, target_user_id, bot_repo, user_repo
    )
    await message.answer(reply_text, reply_markup=keyboard)


# ── 封禁/解封切换回调（blk_toggle:{sub_bot_id}:{user_id}）───


@router.callback_query(lambda c: c.data and c.data.startswith("blk_toggle:"))
async def cb_blk_toggle(
    callback: CallbackQuery, bot_repo: BotRepo, user_repo: UserRepo
) -> None:
    parts = callback.data.split(":")
    sub_bot_id = int(parts[1])
    target_user_id = int(parts[2])

    bot = await bot_repo.get_by_id(sub_bot_id)
    if not bot or bot.owner_id != callback.from_user.id:
        await callback.answer("无权限", show_alert=True)
        return

    user = await user_repo.get_by_sub_bot_and_user(sub_bot_id, target_user_id)
    if not user:
        await callback.answer("用户不存在", show_alert=True)
        return

    new_blocked = not user.is_blocked
    await user_repo.update_blocked(sub_bot_id, target_user_id, new_blocked)
    action = "已封禁" if new_blocked else "已解封"
    await callback.message.edit_text(
        f"{action}用户 {user.display_name} (ID:{user.user_id}) - @{bot.bot_username}",
        reply_markup=back_home_keyboard(),
    )
    await callback.answer()


# ── 全部封禁/解封回调（blk_all:{user_id}:{action}）──────────


@router.callback_query(lambda c: c.data and c.data.startswith("blk_all:"))
async def cb_blk_all(
    callback: CallbackQuery, bot_repo: BotRepo, user_repo: UserRepo
) -> None:
    parts = callback.data.split(":")
    target_user_id = int(parts[1])
    action = parts[2]  # "block" or "unblock"

    is_blocked = action == "block"
    records = await user_repo.find_user_across_bots(
        callback.from_user.id, target_user_id
    )
    if not records:
        await callback.answer("未找到用户", show_alert=True)
        return

    count = 0
    for record in records:
        bot = await bot_repo.get_by_id(record.sub_bot_id)
        if bot and bot.owner_id == callback.from_user.id:
            await user_repo.update_blocked(record.sub_bot_id, target_user_id, is_blocked)
            count += 1

    label = "封禁" if is_blocked else "解封"
    await callback.message.edit_text(
        f"已在 {count} 个Bot中{label}用户 (ID:{target_user_id})",
        reply_markup=back_home_keyboard(),
    )
    await callback.answer()
