"""/admin 命令 - 平台管理面板（仅管理员）"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import Settings
from app.repositories.bot_repo import BotRepo
from app.repositories.message_map_repo import MessageMapRepo
from app.repositories.user_repo import UserRepo
from app.sub_bot.registry import BotRegistry

logger = logging.getLogger(__name__)

router = Router(name="admin")


def _is_admin(user_id: int, settings: Settings) -> bool:
    """检查是否是管理员"""
    return user_id in settings.ADMIN_USER_IDS


def _admin_panel_keyboard() -> InlineKeyboardMarkup:
    """管理面板主键盘"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Bot管理", callback_data="adm_bots"),
            InlineKeyboardButton(text="查看统计", callback_data="adm_stats"),
        ],
        [
            InlineKeyboardButton(text="系统状态", callback_data="adm_system"),
        ],
        [
            InlineKeyboardButton(text="返回主菜单", callback_data="nav_home"),
        ],
    ])


def _bot_list_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Bot列表分页键盘"""
    nav_buttons: list[InlineKeyboardButton] = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(text="上一页", callback_data=f"adm_bots_page:{page - 1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"第{page}/{total_pages}页", callback_data="noop")
    )
    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(text="下一页", callback_data=f"adm_bots_page:{page + 1}")
        )
    return InlineKeyboardMarkup(inline_keyboard=[
        nav_buttons,
        [InlineKeyboardButton(text="返回管理面板", callback_data="adm_panel")],
    ])


def _bot_detail_keyboard(bot_id: int, status: str) -> InlineKeyboardMarkup:
    """Bot详情键盘"""
    rows: list[list[InlineKeyboardButton]] = []
    if status == "active":
        rows.append([
            InlineKeyboardButton(text="强制停止", callback_data=f"adm_force_stop:{bot_id}"),
        ])
    rows.append([
        InlineKeyboardButton(text="查看用户", callback_data=f"adm_bot_users:{bot_id}"),
        InlineKeyboardButton(text="强制删除", callback_data=f"adm_force_delete:{bot_id}"),
    ])
    rows.append([
        InlineKeyboardButton(text="返回列表", callback_data="adm_bots"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── /admin 命令 ──────────────────────────────────────────────


@router.message(Command("admin"))
async def admin_command(
    message: Message,
    bot_repo: BotRepo,
    user_repo: UserRepo,
    message_map_repo: MessageMapRepo,
    settings: Settings,
) -> None:
    """管理员面板入口"""
    if not _is_admin(message.from_user.id, settings):
        await message.answer("你没有权限使用此命令")
        return

    # 获取统计数据
    bot_counts = await bot_repo.count_all()
    total_users = await user_repo.count_total_users()
    total_maps = await message_map_repo.count_all()

    text = (
        "平台管理面板\n\n"
        "统计概览:\n"
        f"- 注册Bot总数: {bot_counts['total']}\n"
        f"- 运行中: {bot_counts['active']}\n"
        f"- 已停止: {bot_counts['stopped']}\n"
        f"- 错误: {bot_counts['error']}\n"
        f"- 总用户数: {total_users:,}\n"
        f"- 消息映射记录: {total_maps:,}"
    )

    await message.answer(text, reply_markup=_admin_panel_keyboard())


# ── 管理面板回调 ──────────────────────────────────────────────


@router.callback_query(lambda c: c.data == "adm_panel")
async def admin_panel_callback(
    callback: CallbackQuery,
    bot_repo: BotRepo,
    user_repo: UserRepo,
    message_map_repo: MessageMapRepo,
    settings: Settings,
) -> None:
    """返回管理面板"""
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return

    bot_counts = await bot_repo.count_all()
    total_users = await user_repo.count_total_users()
    total_maps = await message_map_repo.count_all()

    text = (
        "平台管理面板\n\n"
        "统计概览:\n"
        f"- 注册Bot总数: {bot_counts['total']}\n"
        f"- 运行中: {bot_counts['active']}\n"
        f"- 已停止: {bot_counts['stopped']}\n"
        f"- 错误: {bot_counts['error']}\n"
        f"- 总用户数: {total_users:,}\n"
        f"- 消息映射记录: {total_maps:,}"
    )

    await callback.message.edit_text(text, reply_markup=_admin_panel_keyboard())
    await callback.answer()


# ── Bot管理 ──────────────────────────────────────────────


@router.callback_query(lambda c: c.data and c.data.startswith("adm_bots"))
async def admin_list_bots(
    callback: CallbackQuery,
    bot_repo: BotRepo,
    settings: Settings,
) -> None:
    """列出所有Bot"""
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return

    # 解析页码
    page = 1
    if ":" in callback.data:
        page = int(callback.data.split(":")[1])

    result = await bot_repo.get_all_paginated(page, page_size=10)

    if not result.items:
        await callback.message.edit_text(
            "暂无Bot",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="返回管理面板", callback_data="adm_panel")],
            ]),
        )
        await callback.answer()
        return

    lines = [f"所有Bot列表 (共{result.total}个)\n"]
    for i, bot in enumerate(result.items, (page - 1) * 10 + 1):
        status_label = {"active": "运行中", "stopped": "已停止", "error": "错误"}.get(
            bot.status, bot.status
        )
        lines.append(
            f"{i}. @{bot.bot_username} - 主人: {bot.owner_username or bot.owner_id} - {status_label}\n"
            f"   用户:{bot.user_count} | 消息:{bot.message_count}"
        )

    # 添加Bot详情按钮
    keyboard_rows: list[list[InlineKeyboardButton]] = []
    for bot in result.items:
        keyboard_rows.append([
            InlineKeyboardButton(
                text=f"查看 @{bot.bot_username}",
                callback_data=f"adm_bot_detail:{bot.id}",
            ),
        ])

    # 分页按钮
    nav_buttons: list[InlineKeyboardButton] = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(text="上一页", callback_data=f"adm_bots:{page - 1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"第{page}/{result.total_pages}页", callback_data="noop")
    )
    if page < result.total_pages:
        nav_buttons.append(
            InlineKeyboardButton(text="下一页", callback_data=f"adm_bots:{page + 1}")
        )
    keyboard_rows.append(nav_buttons)
    keyboard_rows.append([
        InlineKeyboardButton(text="返回管理面板", callback_data="adm_panel"),
    ])

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
    )
    await callback.answer()


# ── Bot详情 ──────────────────────────────────────────────


@router.callback_query(lambda c: c.data and c.data.startswith("adm_bot_detail:"))
async def admin_view_bot_detail(
    callback: CallbackQuery,
    bot_repo: BotRepo,
    settings: Settings,
) -> None:
    """查看Bot详情"""
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return

    bot_id = int(callback.data.split(":")[1])
    bot = await bot_repo.get_by_id(bot_id)

    if not bot:
        await callback.answer("Bot不存在", show_alert=True)
        return

    status_label = {"active": "运行中", "stopped": "已停止", "error": "错误"}.get(
        bot.status, bot.status
    )
    created = bot.created_at.strftime("%Y-%m-%d")

    text = (
        f"@{bot.bot_username} 详情（管理员视角）\n\n"
        f"主人: {bot.owner_username or 'N/A'} (ID: {bot.owner_id})\n"
        f"状态: {status_label}\n"
        f"用户数: {bot.user_count}\n"
        f"消息数: {bot.message_count:,}\n"
        f"注册时间: {created}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=_bot_detail_keyboard(bot.id, bot.status),
    )
    await callback.answer()


# ── 强制停止Bot ──────────────────────────────────────────────


@router.callback_query(lambda c: c.data and c.data.startswith("adm_force_stop:"))
async def admin_force_stop_bot(
    callback: CallbackQuery,
    bot_repo: BotRepo,
    registry: BotRegistry,
    settings: Settings,
) -> None:
    """强制停止Bot"""
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return

    bot_id = int(callback.data.split(":")[1])
    bot = await bot_repo.get_by_id(bot_id)

    if not bot:
        await callback.answer("Bot不存在", show_alert=True)
        return

    # 调用 registry 停止Bot
    await registry.remove_bot(bot.bot_id)

    # 更新数据库状态
    await bot_repo.update_status(bot.id, "stopped")

    await callback.message.edit_text(
        f"Bot @{bot.bot_username} 已被强制停止",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="返回列表", callback_data="adm_bots")],
        ]),
    )
    await callback.answer()


# ── 查看统计信息 ──────────────────────────────────────────────


@router.callback_query(lambda c: c.data == "adm_stats")
async def admin_view_statistics(
    callback: CallbackQuery,
    bot_repo: BotRepo,
    user_repo: UserRepo,
    message_map_repo: MessageMapRepo,
    settings: Settings,
) -> None:
    """查看统计信息"""
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return

    bot_counts = await bot_repo.count_all()
    total_users = await user_repo.count_total_users()
    total_maps = await message_map_repo.count_all()

    text = (
        "平台统计信息\n\n"
        "Bot统计:\n"
        f"- 总数: {bot_counts['total']}\n"
        f"- 运行中: {bot_counts['active']}\n"
        f"- 已停止: {bot_counts['stopped']}\n"
        f"- 错误: {bot_counts['error']}\n\n"
        "用户统计:\n"
        f"- 总用户数: {total_users:,}\n\n"
        "消息统计:\n"
        f"- 消息映射记录: {total_maps:,}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="返回管理面板", callback_data="adm_panel")],
        ]),
    )
    await callback.answer()


# ── 系统状态 ──────────────────────────────────────────────


@router.callback_query(lambda c: c.data == "adm_system")
async def admin_view_system_status(
    callback: CallbackQuery,
    bot_repo: BotRepo,
    registry: BotRegistry,
    settings: Settings,
) -> None:
    """查看系统状态"""
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return

    bot_counts = await bot_repo.count_all()
    running_bots = registry.count_running()

    text = (
        "系统状态\n\n"
        f"活跃Bot数: {running_bots}\n"
        f"数据库Bot总数: {bot_counts['total']}\n"
        f"数据库: {settings.DATABASE_URL}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="返回管理面板", callback_data="adm_panel")],
        ]),
    )
    await callback.answer()
