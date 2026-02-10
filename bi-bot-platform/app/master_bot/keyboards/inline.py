"""主Bot 内联键盘构建函数"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.dto import BotUserDTO, SubBotDTO


STATUS_LABELS: dict[str, str] = {
    "active": "运行中",
    "stopped": "已停止",
    "error": "错误",
    "token_invalid": "Token无效",
}


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="注册新Bot", callback_data="reg_start"),
            InlineKeyboardButton(text="我的Bot", callback_data="mybot_list"),
        ],
        [
            InlineKeyboardButton(text="帮助说明", callback_data="nav_help"),
        ],
    ])


def back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="返回主菜单", callback_data="nav_home")],
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="取消", callback_data="nav_cancel")],
    ])


def bot_list_keyboard(bots: list[SubBotDTO]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for bot in bots:
        label = STATUS_LABELS.get(bot.status, bot.status)
        rows.append([
            InlineKeyboardButton(
                text=f"管理 @{bot.bot_username} ({label})",
                callback_data=f"bot_manage:{bot.id}",
            ),
        ])
    rows.append([
        InlineKeyboardButton(text="注册新Bot", callback_data="reg_start"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def no_bot_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="注册新Bot", callback_data="reg_start"),
            InlineKeyboardButton(text="返回主菜单", callback_data="nav_home"),
        ],
    ])


def bot_manage_keyboard(bot_id: int, status: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if status == "active":
        rows.append([
            InlineKeyboardButton(text="停止Bot", callback_data=f"bot_stop:{bot_id}"),
            InlineKeyboardButton(text="重启Bot", callback_data=f"bot_restart:{bot_id}"),
        ])
    else:
        rows.append([
            InlineKeyboardButton(text="启动Bot", callback_data=f"bot_restart:{bot_id}"),
        ])
    rows.append([
        InlineKeyboardButton(text="设置欢迎语", callback_data=f"bot_welcome:{bot_id}"),
        InlineKeyboardButton(text="查看用户列表", callback_data=f"bot_users:{bot_id}:1"),
    ])
    rows.append([
        InlineKeyboardButton(text="广播消息", callback_data=f"bot_broadcast:{bot_id}"),
        InlineKeyboardButton(text="删除Bot", callback_data=f"bot_delete:{bot_id}"),
    ])
    rows.append([
        InlineKeyboardButton(text="返回列表", callback_data="mybot_list"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_register_keyboard() -> InlineKeyboardMarkup:
    """Token验证通过后的确认注册键盘"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="确认注册", callback_data="reg_confirm"),
            InlineKeyboardButton(text="取消", callback_data="reg_cancel"),
        ],
    ])


def register_success_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    """注册成功后的键盘"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="管理此Bot", callback_data=f"bot_manage:{bot_id}"),
            InlineKeyboardButton(text="返回主菜单", callback_data="nav_home"),
        ],
    ])


def register_fail_keyboard() -> InlineKeyboardMarkup:
    """注册失败（启动失败）后的键盘"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="我的Bot", callback_data="mybot_list"),
            InlineKeyboardButton(text="返回主菜单", callback_data="nav_home"),
        ],
    ])


def confirm_stop_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="确认停止", callback_data=f"bot_stop_confirm:{bot_id}"),
            InlineKeyboardButton(text="取消", callback_data=f"bot_manage:{bot_id}"),
        ],
    ])


def confirm_delete_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="确认删除", callback_data=f"bot_delete_confirm:{bot_id}"),
            InlineKeyboardButton(text="取消", callback_data=f"bot_manage:{bot_id}"),
        ],
    ])


def user_list_keyboard(
    bot_id: int,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """用户列表分页键盘"""
    nav_buttons: list[InlineKeyboardButton] = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(text="上一页", callback_data=f"bot_users:{bot_id}:{page - 1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"第{page}/{total_pages}页", callback_data="noop")
    )
    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(text="下一页", callback_data=f"bot_users:{bot_id}:{page + 1}")
        )
    return InlineKeyboardMarkup(inline_keyboard=[
        nav_buttons,
        [InlineKeyboardButton(text="返回管理面板", callback_data=f"bot_manage:{bot_id}")],
    ])


def welcome_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="使用默认欢迎语", callback_data=f"bot_welcome_default:{bot_id}"
            ),
            InlineKeyboardButton(text="取消", callback_data=f"bot_manage:{bot_id}"),
        ],
    ])


def block_select_keyboard(
    user_records: list[BotUserDTO],
    bots_map: dict[int, str],
    target_user_id: int,
) -> InlineKeyboardMarkup:
    """多Bot封禁选择键盘"""
    rows: list[list[InlineKeyboardButton]] = []
    for record in user_records:
        bot_username = bots_map.get(record.sub_bot_id, "Unknown")
        action = "解封" if record.is_blocked else "封禁"
        rows.append([
            InlineKeyboardButton(
                text=f"{action}于 @{bot_username}",
                callback_data=f"blk_toggle:{record.sub_bot_id}:{target_user_id}",
            ),
        ])
    if not any(r.is_blocked for r in user_records):
        rows.append([
            InlineKeyboardButton(
                text="全部封禁", callback_data=f"blk_all:{target_user_id}:block"
            ),
        ])
    elif all(r.is_blocked for r in user_records):
        rows.append([
            InlineKeyboardButton(
                text="全部解封", callback_data=f"blk_all:{target_user_id}:unblock"
            ),
        ])
    rows.append([InlineKeyboardButton(text="取消", callback_data="nav_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def unblock_confirm_keyboard(sub_bot_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="解除封禁",
                callback_data=f"blk_toggle:{sub_bot_id}:{user_id}",
            ),
            InlineKeyboardButton(text="取消", callback_data="nav_cancel"),
        ],
    ])
