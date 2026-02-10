import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.master_bot.keyboards.inline import (
    ad_button_choice_keyboard,
    ad_confirm_keyboard,
    ad_delete_confirm_keyboard,
    ad_detail_keyboard,
    ad_list_keyboard,
    ad_scope_keyboard,
    cancel_keyboard,
)
from app.master_bot.states import AdStates
from app.repositories.ad_repo import AdRepo

logger = logging.getLogger(__name__)

router = Router(name="ad")

SEPARATOR = "━━━━━━━━━━━━━━━"


def _is_admin(user_id: int, settings: Settings) -> bool:
    return user_id in settings.ADMIN_USER_IDS


async def _show_ad_list(
    target: Message | CallbackQuery,
    ad_repo: AdRepo,
    edit: bool = False,
) -> None:
    """显示广告列表"""
    ads = await ad_repo.get_all()
    if not ads:
        text = "广告管理\n\n当前没有任何广告。"
    else:
        lines = ["广告管理\n\n当前广告列表:\n"]
        for i, ad in enumerate(ads, 1):
            status = "启用" if ad.is_active else "停用"
            scope = "全局" if ad.target_type == "global" else f"@Bot#{ad.target_bot_id}"
            lines.append(
                f"{i}. [{status}] \"{ad.name}\" ({scope})\n"
                f"   {ad.ad_text[:40]}{'...' if len(ad.ad_text) > 40 else ''}\n"
                f"   展示次数: {ad.impression_count:,}\n"
            )
        text = "\n".join(lines)

    kb = ad_list_keyboard(ads, admin_panel=True)
    if edit and isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb)
    elif isinstance(target, Message):
        await target.answer(text, reply_markup=kb)
    elif isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb)


@router.message(Command("ad"))
async def cmd_ad(message: Message, settings: Settings, ad_repo: AdRepo) -> None:
    if not _is_admin(message.from_user.id, settings):
        await message.answer("你没有权限使用此命令")
        return
    await _show_ad_list(message, ad_repo)


@router.callback_query(lambda c: c.data == "ad_list")
async def cb_ad_list(callback: CallbackQuery, ad_repo: AdRepo, settings: Settings) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return
    await _show_ad_list(callback, ad_repo, edit=True)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("ad_detail:"))
async def cb_ad_detail(callback: CallbackQuery, ad_repo: AdRepo, settings: Settings) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return
    ad_id = int(callback.data.split(":")[1])
    ad = await ad_repo.get_by_id(ad_id)
    if ad is None:
        await callback.answer("广告不存在", show_alert=True)
        return

    status = "启用" if ad.is_active else "停用"
    scope = "全局" if ad.target_type == "global" else f"指定Bot#{ad.target_bot_id}"
    text = (
        f"广告详情: \"{ad.name}\"\n\n"
        f"状态: {status}\n"
        f"范围: {scope}\n"
        f"优先级: {ad.priority}\n"
        f"展示次数: {ad.impression_count:,}\n\n"
        f"内容预览:\n{SEPARATOR}\n{ad.ad_text}\n{SEPARATOR}"
    )
    if ad.button_text:
        text += f"\n按钮: [{ad.button_text}]({ad.button_url})"

    await callback.message.edit_text(
        text, reply_markup=ad_detail_keyboard(ad.id, ad.is_active),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("ad_toggle:"))
async def cb_ad_toggle(callback: CallbackQuery, ad_repo: AdRepo, settings: Settings) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return
    ad_id = int(callback.data.split(":")[1])
    ad = await ad_repo.get_by_id(ad_id)
    if ad is None:
        await callback.answer("广告不存在", show_alert=True)
        return
    new_active = not ad.is_active
    await ad_repo.update(ad_id, is_active=new_active)
    status = "已启用" if new_active else "已停用"
    await callback.answer(f"广告{status}")
    # Refresh detail view
    updated = await ad_repo.get_by_id(ad_id)
    scope = "全局" if updated.target_type == "global" else f"指定Bot#{updated.target_bot_id}"
    text = (
        f"广告详情: \"{updated.name}\"\n\n"
        f"状态: {'启用' if updated.is_active else '停用'}\n"
        f"范围: {scope}\n"
        f"优先级: {updated.priority}\n"
        f"展示次数: {updated.impression_count:,}\n\n"
        f"内容预览:\n{SEPARATOR}\n{updated.ad_text}\n{SEPARATOR}"
    )
    await callback.message.edit_text(
        text, reply_markup=ad_detail_keyboard(updated.id, updated.is_active),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("ad_delete:"))
async def cb_ad_delete(callback: CallbackQuery, ad_repo: AdRepo, settings: Settings) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return
    ad_id = int(callback.data.split(":")[1])
    ad = await ad_repo.get_by_id(ad_id)
    if ad is None:
        await callback.answer("广告不存在", show_alert=True)
        return
    await callback.message.edit_text(
        f"确定要删除广告 \"{ad.name}\" 吗？\n此操作不可撤销。",
        reply_markup=ad_delete_confirm_keyboard(ad_id),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("ad_delete_confirm:"))
async def cb_ad_delete_confirm(callback: CallbackQuery, ad_repo: AdRepo, settings: Settings) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return
    ad_id = int(callback.data.split(":")[1])
    await ad_repo.delete(ad_id)
    await callback.answer("广告已删除")
    await _show_ad_list(callback, ad_repo, edit=True)


# ===== 添加广告 FSM 流程 =====


@router.callback_query(lambda c: c.data == "ad_add")
async def cb_ad_add(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return
    await state.set_state(AdStates.waiting_ad_name)
    await callback.message.edit_text(
        "请输入广告名称（管理用）\n\n例如: \"默认广告\"、\"春节活动\"",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(AdStates.waiting_ad_name)
async def on_ad_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("广告名称不能为空，请重新输入", reply_markup=cancel_keyboard())
        return
    await state.update_data(ad_name=name)
    await state.set_state(AdStates.waiting_ad_text)
    await message.answer(
        "请输入广告文本内容\n\n"
        "支持 HTML 格式:\n"
        "<b>粗体</b> <i>斜体</i> <a href=\"url\">链接</a>\n\n"
        "例如:\n"
        "📢 <b>Powered by</b> @PlatformBot",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdStates.waiting_ad_text)
async def on_ad_text(message: Message, state: FSMContext) -> None:
    ad_text = (message.text or "").strip()
    if not ad_text:
        await message.answer("广告文本不能为空，请重新输入", reply_markup=cancel_keyboard())
        return
    await state.update_data(ad_text=ad_text)
    await message.answer(
        "是否添加广告按钮？\n\n"
        "按钮会显示在广告文本下方，\n"
        "用户点击后跳转到指定链接。",
        reply_markup=ad_button_choice_keyboard(),
    )


@router.callback_query(lambda c: c.data == "ad_skip_button")
async def cb_ad_skip_button(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(button_text=None, button_url=None)
    await callback.message.edit_text(
        "请选择广告展示范围",
        reply_markup=ad_scope_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "ad_add_button")
async def cb_ad_add_button(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdStates.waiting_ad_button)
    await callback.message.edit_text(
        "请输入按钮文字和链接\n\n"
        "格式: 按钮文字 | 链接\n"
        "例如: 免费创建Bot | https://t.me/MyBot",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(AdStates.waiting_ad_button)
async def on_ad_button(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if "|" not in text:
        await message.answer(
            "格式错误，请使用: 按钮文字 | 链接",
            reply_markup=cancel_keyboard(),
        )
        return
    parts = text.split("|", 1)
    button_text = parts[0].strip()
    button_url = parts[1].strip()
    if not button_text or not button_url:
        await message.answer(
            "按钮文字和链接都不能为空，请重新输入",
            reply_markup=cancel_keyboard(),
        )
        return
    await state.update_data(button_text=button_text, button_url=button_url)
    await message.answer(
        "请选择广告展示范围",
        reply_markup=ad_scope_keyboard(),
    )


@router.callback_query(lambda c: c.data == "ad_scope_global")
async def cb_ad_scope_global(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(target_type="global", target_bot_id=None)
    await state.set_state(AdStates.waiting_ad_priority)
    await callback.message.edit_text(
        "请输入广告优先级（数字，越大越优先）\n\n"
        "例如: 0（默认）、10（高优先级）",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "ad_scope_specific")
async def cb_ad_scope_specific(
    callback: CallbackQuery, state: FSMContext,
) -> None:
    await callback.message.edit_text(
        "请输入目标Bot的数据库ID（数字）\n\n"
        "你可以在 /admin Bot管理中查看Bot ID",
        reply_markup=cancel_keyboard(),
    )
    await state.update_data(target_type="specific")
    await state.set_state(AdStates.confirming_ad)
    await callback.answer()


@router.message(AdStates.confirming_ad)
async def on_ad_target_bot_id(message: Message, state: FSMContext) -> None:
    """接收指定Bot ID（仅在 target_type=specific 且尚未设置 target_bot_id 时）"""
    data = await state.get_data()
    if data.get("target_type") != "specific" or data.get("target_bot_id") is not None:
        return

    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("请输入有效的数字ID", reply_markup=cancel_keyboard())
        return

    await state.update_data(target_bot_id=int(text))
    await state.set_state(AdStates.waiting_ad_priority)
    await message.answer(
        "请输入广告优先级（数字，越大越优先）\n\n"
        "例如: 0（默认）、10（高优先级）",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdStates.waiting_ad_priority)
async def on_ad_priority(message: Message, state: FSMContext) -> None:
    """接收广告优先级"""
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer("请输入有效的数字", reply_markup=cancel_keyboard())
        return
    await state.update_data(priority=int(text))
    await state.set_state(AdStates.confirming_ad)
    await _show_ad_preview_msg(message, state)


async def _show_ad_preview(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    scope = "全局" if data.get("target_type") == "global" else f"指定Bot#{data.get('target_bot_id')}"
    preview = (
        f"广告预览:\n\n"
        f"名称: {data.get('ad_name')}\n"
        f"范围: {scope}\n\n"
        f"{SEPARATOR}\n"
        f"{data.get('ad_text')}\n"
        f"{SEPARATOR}"
    )
    if data.get("button_text"):
        preview += f"\n按钮: [{data['button_text']}]"

    await callback.message.edit_text(preview, reply_markup=ad_confirm_keyboard())


async def _show_ad_preview_msg(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    scope = "全局" if data.get("target_type") == "global" else f"指定Bot#{data.get('target_bot_id')}"
    preview = (
        f"广告预览:\n\n"
        f"名称: {data.get('ad_name')}\n"
        f"范围: {scope}\n\n"
        f"{SEPARATOR}\n"
        f"{data.get('ad_text')}\n"
        f"{SEPARATOR}"
    )
    if data.get("button_text"):
        preview += f"\n按钮: [{data['button_text']}]"

    await message.answer(preview, reply_markup=ad_confirm_keyboard())


@router.callback_query(lambda c: c.data == "ad_confirm")
async def cb_ad_confirm(
    callback: CallbackQuery, state: FSMContext, ad_repo: AdRepo,
) -> None:
    data = await state.get_data()
    await ad_repo.create(
        name=data.get("ad_name", ""),
        ad_text=data.get("ad_text", ""),
        ad_url=None,
        button_text=data.get("button_text"),
        button_url=data.get("button_url"),
        target_type=data.get("target_type", "global"),
        target_bot_id=data.get("target_bot_id"),
        priority=data.get("priority", 0),
    )
    await state.clear()
    await callback.answer("广告已添加并启用")
    await _show_ad_list(callback, ad_repo, edit=True)


@router.callback_query(lambda c: c.data == "ad_cancel")
async def cb_ad_cancel(callback: CallbackQuery, state: FSMContext, ad_repo: AdRepo) -> None:
    await state.clear()
    await callback.answer("已取消")
    await _show_ad_list(callback, ad_repo, edit=True)


# ===== 重新编辑 =====


@router.callback_query(lambda c: c.data == "ad_re_edit")
async def cb_ad_re_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """重新编辑 - 回到输入广告名称步骤"""
    await state.set_state(AdStates.waiting_ad_name)
    await callback.message.edit_text(
        "请重新输入广告名称（管理用）\n\n例如: \"默认广告\"、\"春节活动\"",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


# ===== 编辑广告内容 =====


@router.callback_query(lambda c: c.data and c.data.startswith("ad_edit_text:"))
async def cb_ad_edit_text(callback: CallbackQuery, state: FSMContext, ad_repo: AdRepo, settings: Settings) -> None:
    """编辑广告内容 - 进入FSM等待新文本"""
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return
    ad_id = int(callback.data.split(":")[1])
    ad = await ad_repo.get_by_id(ad_id)
    if ad is None:
        await callback.answer("广告不存在", show_alert=True)
        return

    await state.set_state(AdStates.editing_ad_text)
    await state.update_data(editing_ad_id=ad_id)
    await callback.message.edit_text(
        f"正在编辑广告 \"{ad.name}\" 的内容\n\n"
        f"当前内容:\n{SEPARATOR}\n{ad.ad_text}\n{SEPARATOR}\n\n"
        "请发送新的广告文本:",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(AdStates.editing_ad_text)
async def on_edit_ad_text(message: Message, state: FSMContext, ad_repo: AdRepo) -> None:
    """接收编辑后的广告文本"""
    data = await state.get_data()
    ad_id = data.get("editing_ad_id")
    if not ad_id:
        await state.clear()
        return

    new_text = (message.text or "").strip()
    if not new_text:
        await message.answer("广告文本不能为空，请重新输入", reply_markup=cancel_keyboard())
        return

    await ad_repo.update(ad_id, ad_text=new_text)
    await state.clear()

    ad = await ad_repo.get_by_id(ad_id)
    if ad:
        await message.answer(
            f"广告 \"{ad.name}\" 内容已更新",
            reply_markup=ad_detail_keyboard(ad.id, ad.is_active),
        )
    else:
        await message.answer("广告内容已更新")


# ===== 编辑广告优先级 =====


@router.callback_query(lambda c: c.data and c.data.startswith("ad_edit_priority:"))
async def cb_ad_edit_priority(callback: CallbackQuery, state: FSMContext, ad_repo: AdRepo, settings: Settings) -> None:
    """编辑广告优先级 - 进入FSM等待新优先级"""
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("你没有权限", show_alert=True)
        return
    ad_id = int(callback.data.split(":")[1])
    ad = await ad_repo.get_by_id(ad_id)
    if ad is None:
        await callback.answer("广告不存在", show_alert=True)
        return

    await state.set_state(AdStates.editing_ad_priority)
    await state.update_data(editing_ad_id=ad_id)
    await callback.message.edit_text(
        f"正在编辑广告 \"{ad.name}\" 的优先级\n\n"
        f"当前优先级: {ad.priority}\n\n"
        "请输入新的优先级（数字，越大越优先）:",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(AdStates.editing_ad_priority)
async def on_edit_ad_priority(message: Message, state: FSMContext, ad_repo: AdRepo) -> None:
    """接收编辑后的广告优先级"""
    data = await state.get_data()
    ad_id = data.get("editing_ad_id")
    if not ad_id:
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer("请输入有效的数字", reply_markup=cancel_keyboard())
        return

    new_priority = int(text)
    await ad_repo.update(ad_id, priority=new_priority)
    await state.clear()

    ad = await ad_repo.get_by_id(ad_id)
    if ad:
        await message.answer(
            f"广告 \"{ad.name}\" 优先级已更新为 {new_priority}",
            reply_markup=ad_detail_keyboard(ad.id, ad.is_active),
        )
    else:
        await message.answer("广告优先级已更新")
