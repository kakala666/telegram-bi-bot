"""广播消息 Handler - 重定向到子Bot操作"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.master_bot.keyboards.inline import (
    broadcast_progress_keyboard,
)
from app.repositories.bot_repo import BotRepo
from app.services.broadcast import BroadcastService

logger = logging.getLogger(__name__)

router = Router(name="broadcast")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot_repo: BotRepo) -> None:
    """广播命令入口 - 重定向到子Bot"""
    user_id = message.from_user.id
    bots = await bot_repo.get_by_owner(user_id)

    if not bots:
        await message.answer("你还没有注册任何Bot，请先使用 /start 注册一个Bot")
        return

    bot_list = "\n".join(f"- @{b.bot_username}" for b in bots)
    await message.answer(
        f"广播功能已迁移到子Bot中操作。\n\n"
        f"请在对应的子Bot中使用 /broadcast 命令发起广播：\n{bot_list}"
    )


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
