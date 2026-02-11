"""子Bot广播 Handler - /broadcast 命令和FSM流程"""

from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.dto import SubBotDTO
from app.exceptions import BroadcastError
from app.repositories.user_repo import UserRepo
from app.services.broadcast import BroadcastService
from app.sub_bot.filters import IsOwnerFilter
from app.sub_bot.keyboards import (
    broadcast_cancel_keyboard,
    broadcast_confirm_keyboard,
    broadcast_progress_keyboard,
)
from app.sub_bot.states import SubBotBroadcastStates

logger = logging.getLogger(__name__)

router = Router(name="sub_broadcast")


@router.message(Command("broadcast"), IsOwnerFilter(is_owner=True))
async def cmd_broadcast(
    message: Message,
    bot: Bot,
    sub_bot: SubBotDTO,
    state: FSMContext,
) -> None:
    """子Bot广播命令入口 - 直接进入内容输入"""
    await state.update_data(broadcast_bot_id=sub_bot.id)
    await state.set_state(SubBotBroadcastStates.waiting_content)

    await message.answer(
        f"准备向 @{sub_bot.bot_username} 的用户广播消息\n\n"
        "请发送要广播的内容\n\n"
        "支持的内容类型:\n"
        "- 文字消息\n"
        "- 图片（可带文字说明）\n"
        "- 视频（可带文字说明）\n"
        "- 文件\n"
        "- 音频",
        reply_markup=broadcast_cancel_keyboard(),
    )


@router.message(SubBotBroadcastStates.waiting_content)
async def on_broadcast_content(
    message: Message,
    bot: Bot,
    sub_bot: SubBotDTO,
    state: FSMContext,
    user_repo: UserRepo,
) -> None:
    """接收广播内容 - 显示预览和确认按钮"""
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

    await state.update_data({
        "content_type": content_type,
        "content_text": content_text,
        "content_file_id": content_file_id,
        "content_caption": content_caption,
    })
    await state.set_state(SubBotBroadcastStates.confirming_broadcast)

    active_count = await user_repo.count_active(sub_bot.id)

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
        f"将发送给 @{sub_bot.bot_username} 的 {active_count} 个用户\n\n"
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
    bot: Bot,
    sub_bot: SubBotDTO,
    state: FSMContext,
    broadcast_svc: BroadcastService,
) -> None:
    """确认发送 - 调用BroadcastService.start"""
    data = await state.get_data()

    try:
        task = await broadcast_svc.start(
            sub_bot_id=sub_bot.id,
            owner_id=callback.from_user.id,
            content_type=data.get("content_type", "text"),
            content_text=data.get("content_text"),
            content_file_id=data.get("content_file_id"),
            content_caption=data.get("content_caption"),
            bot=bot,
        )

        await state.clear()

        await callback.message.edit_text(
            f"广播已开始!\n\n"
            f"Bot: @{sub_bot.bot_username}\n"
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
    await callback.message.edit_text("已取消广播操作")
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
