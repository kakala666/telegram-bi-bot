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


# ===== 广告管理键盘 =====


def ad_list_keyboard(ads: list, admin_panel: bool = False) -> InlineKeyboardMarkup:
    """广告列表键盘"""
    rows: list[list[InlineKeyboardButton]] = []
    for ad in ads:
        status = "启用" if ad.is_active else "停用"
        scope = "全局" if ad.target_type == "global" else f"Bot#{ad.target_bot_id}"
        rows.append([
            InlineKeyboardButton(
                text=f"[{status}] \"{ad.name}\" ({scope})",
                callback_data=f"ad_detail:{ad.id}",
            ),
        ])
    rows.append([
        InlineKeyboardButton(text="添加广告", callback_data="ad_add"),
    ])
    back_cb = "adm_panel" if admin_panel else "nav_home"
    rows.append([
        InlineKeyboardButton(text="返回管理面板", callback_data=back_cb),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ad_detail_keyboard(ad_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """广告详情键盘"""
    toggle_text = "停用" if is_active else "启用"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=toggle_text, callback_data=f"ad_toggle:{ad_id}"),
            InlineKeyboardButton(text="修改内容", callback_data=f"ad_edit_text:{ad_id}"),
        ],
        [
            InlineKeyboardButton(text="修改优先级", callback_data=f"ad_edit_priority:{ad_id}"),
            InlineKeyboardButton(text="删除广告", callback_data=f"ad_delete:{ad_id}"),
        ],
        [
            InlineKeyboardButton(text="返回列表", callback_data="ad_list"),
        ],
    ])


def ad_button_choice_keyboard() -> InlineKeyboardMarkup:
    """是否添加广告按钮"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="添加按钮", callback_data="ad_add_button"),
            InlineKeyboardButton(text="跳过，无按钮", callback_data="ad_skip_button"),
        ],
    ])


def ad_scope_keyboard() -> InlineKeyboardMarkup:
    """广告范围选择"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="全局 - 所有Bot展示", callback_data="ad_scope_global")],
        [InlineKeyboardButton(text="指定Bot - 仅特定Bot展示", callback_data="ad_scope_specific")],
        [InlineKeyboardButton(text="取消", callback_data="ad_cancel")],
    ])


def ad_confirm_keyboard() -> InlineKeyboardMarkup:
    """广告确认键盘"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="确认添加", callback_data="ad_confirm"),
            InlineKeyboardButton(text="取消", callback_data="ad_cancel"),
        ],
    ])


def ad_delete_confirm_keyboard(ad_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="确认删除", callback_data=f"ad_delete_confirm:{ad_id}"),
            InlineKeyboardButton(text="取消", callback_data=f"ad_detail:{ad_id}"),
        ],
    ])


# ===== 广播相关键盘 =====


def broadcast_bot_select_keyboard(bots: list[SubBotDTO]) -> InlineKeyboardMarkup:
    """广播Bot选择键盘"""
    rows: list[list[InlineKeyboardButton]] = []
    for bot in bots:
        rows.append([
            InlineKeyboardButton(
                text=f"@{bot.bot_username} - {bot.user_count}个用户",
                callback_data=f"broadcast_select:{bot.id}",
            ),
        ])
    rows.append([
        InlineKeyboardButton(text="取消", callback_data="broadcast_cancel"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_cancel_keyboard() -> InlineKeyboardMarkup:
    """广播取消键盘"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="取消", callback_data="broadcast_cancel")],
    ])


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    """广播确认键盘"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="确认发送", callback_data="broadcast_confirm"),
            InlineKeyboardButton(text="取消", callback_data="broadcast_cancel"),
        ],
    ])


def broadcast_progress_keyboard(task_id: int, show_cancel: bool = False) -> InlineKeyboardMarkup:
    """广播进度查询键盘"""
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="刷新进度", callback_data=f"broadcast_progress:{task_id}")],
    ]
    if show_cancel:
        rows.append([
            InlineKeyboardButton(text="取消广播", callback_data=f"broadcast_cancel_task:{task_id}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
