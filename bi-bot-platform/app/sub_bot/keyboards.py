"""子Bot 内联键盘构建函数"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def broadcast_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="取消", callback_data="broadcast_cancel")],
    ])


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="确认发送", callback_data="broadcast_confirm"),
            InlineKeyboardButton(text="取消", callback_data="broadcast_cancel"),
        ],
    ])


def broadcast_progress_keyboard(task_id: int, show_cancel: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="刷新进度", callback_data=f"broadcast_progress:{task_id}")],
    ]
    if show_cancel:
        rows.append([
            InlineKeyboardButton(text="取消广播", callback_data=f"broadcast_cancel_task:{task_id}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
