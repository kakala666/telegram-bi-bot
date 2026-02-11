"""广播消息 Handler - /broadcast 命令和FSM流程"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.exceptions import BroadcastError
from app.master_bot.keyboards.inline import (
    broadcast_bot_select_keyboard,
    broadcast_cancel_keyboard,
    broadcast_confirm_keyboard,
    broadcast_progress_keyboard,
    no_bot_keyboard,
)
from app.master_bot.states import BroadcastStates
from app.repositories.bot_repo import BotRepo
from app.repositories.user_repo import UserRepo
from app.services.broadcast import BroadcastService

logger = logging.getLogger(__name__)

router = Router(name="broadcast")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot_repo: BotRepo, state: FSMContext | None = None) -> None:
    """广播命令入口 - 列出用户的Bot供选择"""
    user_id = message.from_user.id
    bots = await bot_repo.get_by_owner(user_id)

    if not bots:
        await message.answer(
            "你还没有注册任何Bot\n\n"
            "请先使用 /start 注册一个Bot",
            reply_markup=no_bot_keyboard(),
        )
        return

    if len(bots) == 1:
        # 只有一个Bot，直接进入内容输入
        bot = bots[0]
        await message.answer(
            f"准备向 Bot @{bot.bot_username} 的用户广播消息\n\n"
            "请发送要广播的内容\n\n"
            "支持的内容类型:\n"
            "- 文字消息\n"
            "- 图片（可带文字说明）\n"
            "- 视频（可带文字说明）\n"
            "- 文件\n"
            "- 音频",
            reply_markup=broadcast_cancel_keyboard(),
        )
        # 保存Bot ID到FSM
        if state:
            await state.update_data(broadcast_bot_id=bot.id)
            await state.set_state(BroadcastStates.waiting_content)
    else:
        # 多个Bot，显示选择列表
        await message.answer(
            "请选择要广播的Bot:",
            reply_markup=broadcast_bot_select_keyboard(bots),
        )


@router.callback_query(lambda c: c.data and c.data.startswith("broadcast_select:"))
async def cb_broadcast_select(
    callback: CallbackQuery,
    state: FSMContext,
    bot_repo: BotRepo,
    user_repo: UserRepo,
) -> None:
    """选择Bot回调 - 进入输入广播内容状态"""
    bot_id = int(callback.data.split(":")[1])
    bot = await bot_repo.get_by_id(bot_id)

    if not bot:
        await callback.answer("Bot不存在", show_alert=True)
        return

    # 权限检查
    if bot.owner_id != callback.from_user.id:
        await callback.answer("你没有权限操作此Bot", show_alert=True)
        return

    # 获取活跃用户数
    active_count = await user_repo.count_active(bot_id)

    await state.update_data(broadcast_bot_id=bot_id)
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


@router.message(BroadcastStates.waiting_content)
async def on_broadcast_content(
    message: Message,
    state: FSMContext,
    bot_repo: BotRepo,
    user_repo: UserRepo,
) -> None:
    """接收广播内容 - 显示预览和确认按钮"""
    data = await state.get_data()
    bot_id = data.get("broadcast_bot_id")

    if not bot_id:
        await message.answer("会话已过期，请重新开始")
        await state.clear()
        return

    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != message.from_user.id:
        await message.answer("Bot不存在或无权限")
        await state.clear()
        return

    # 解析消息类型和内容
    content_type = "text"
    content_text = None
    content_file_id = None
    content_caption = None

    if message.text:
        content_type = "text"
        content_text = message.text
    elif message.photo:
        content_type = "photo"
        content_file_id = message.photo[-1].file_id
        content_caption = message.caption
    elif message.video:
        content_type = "video"
        content_file_id = message.video.file_id
        content_caption = message.caption
    elif message.document:
        content_type = "document"
        content_file_id = message.document.file_id
        content_caption = message.caption
    elif message.audio:
        content_type = "audio"
        content_file_id = message.audio.file_id
        content_caption = message.caption
    elif message.sticker:
        content_type = "sticker"
        content_file_id = message.sticker.file_id
    else:
        await message.answer("不支持的消息类型，请重新发送")
        return

    # 保存内容到FSM
    await state.update_data({
        "content_type": content_type,
        "content_text": content_text,
        "content_file_id": content_file_id,
        "content_caption": content_caption,
    })
    await state.set_state(BroadcastStates.confirming_broadcast)

    # 获取活跃用户数
    active_count = await user_repo.count_active(bot_id)

    # 显示预览
    type_labels = {
        "text": "文字",
        "photo": "图片",
        "video": "视频",
        "document": "文件",
        "audio": "音频",
        "sticker": "贴纸",
    }
    type_label = type_labels.get(content_type, content_type)

    preview_text = (
        f"广播预览\n\n"
        f"类型: {type_label}\n"
        f"将发送给 @{bot.bot_username} 的 {active_count} 个用户\n\n"
    )

    if content_text:
        preview_text += f"内容:\n{content_text[:200]}{'...' if len(content_text) > 200 else ''}"
    elif content_caption:
        preview_text += f"说明:\n{content_caption[:200]}{'...' if len(content_caption) > 200 else ''}"

    await message.answer(
        preview_text,
        reply_markup=broadcast_confirm_keyboard(),
    )


@router.callback_query(lambda c: c.data == "broadcast_confirm")
async def cb_broadcast_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    bot_repo: BotRepo,
    broadcast_svc: BroadcastService,
) -> None:
    """确认发送 - 调用BroadcastService.start"""
    data = await state.get_data()
    bot_id = data.get("broadcast_bot_id")

    if not bot_id:
        await callback.answer("会话已过期", show_alert=True)
        await state.clear()
        return

    bot = await bot_repo.get_by_id(bot_id)
    if not bot or bot.owner_id != callback.from_user.id:
        await callback.answer("Bot不存在或无权限", show_alert=True)
        await state.clear()
        return

    try:
        task = await broadcast_svc.start(
            sub_bot_id=bot_id,
            owner_id=callback.from_user.id,
            content_type=data.get("content_type", "text"),
            content_text=data.get("content_text"),
            content_file_id=data.get("content_file_id"),
            content_caption=data.get("content_caption"),
        )

        await state.clear()

        await callback.message.edit_text(
            f"广播已开始!\n\n"
            f"Bot: @{bot.bot_username}\n"
            f"目标用户: {task.total_count}\n"
            f"状态: 发送中...\n\n"
            f"任务ID: {task.id}",
            reply_markup=broadcast_progress_keyboard(task.id),
        )
        await callback.answer()

    except BroadcastError as e:
        await callback.message.edit_text(
            f"广播失败\n\n"
            f"错误: {e}",
            reply_markup=broadcast_cancel_keyboard(),
        )
        await callback.answer()
    except Exception:
        logger.exception("广播启动时发生未预期的错误")
        await callback.message.edit_text(
            "广播失败\n\n系统内部错误，请稍后重试",
            reply_markup=broadcast_cancel_keyboard(),
        )
        await callback.answer()


@router.callback_query(lambda c: c.data == "broadcast_cancel")
async def cb_broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """取消操作 - 清理FSM状态"""
    await state.clear()
    await callback.message.edit_text(
        "已取消广播操作",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("broadcast_progress:"))
async def cb_broadcast_progress(
    callback: CallbackQuery,
    broadcast_svc: BroadcastService,
) -> None:
    """查询进度回调 - 显示发送进度"""
    task_id = int(callback.data.split(":")[1])
    progress = await broadcast_svc.get_progress(task_id=task_id)

    if not progress:
        await callback.answer("任务不存在", show_alert=True)
        return

    status_labels = {
        "running": "发送中",
        "completed": "已完成",
        "cancelled": "已取消",
        "failed": "失败",
    }
    status_label = status_labels.get(progress.status, progress.status)

    text = (
        f"广播进度\n\n"
        f"{progress.progress_bar}\n\n"
        f"状态: {status_label}\n"
        f"已发送: {progress.sent} / {progress.total}\n"
        f"失败: {progress.failed}\n"
    )

    if progress.status == "running":
        text += f"\n剩余: {progress.total - progress.sent - progress.failed}"
        kb = broadcast_progress_keyboard(task_id, show_cancel=True)
    else:
        kb = None

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("broadcast_cancel_task:"))
async def cb_broadcast_cancel_task(
    callback: CallbackQuery,
    broadcast_svc: BroadcastService,
) -> None:
    """取消正在运行的广播"""
    task_id = int(callback.data.split(":")[1])
    success = await broadcast_svc.cancel(task_id=task_id)

    if success:
        await callback.message.edit_text(
            f"广播已取消\n\n"
            f"任务ID: {task_id}",
        )
        await callback.answer("已取消广播")
    else:
        await callback.answer("任务不存在或已完成", show_alert=True)
