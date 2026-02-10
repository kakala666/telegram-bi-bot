import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.exceptions import (
    RegistryError,
    TokenDuplicateError,
    TokenFormatError,
    TokenInvalidError,
    TokenLimitError,
)
from app.master_bot.keyboards.inline import (
    cancel_keyboard,
    confirm_register_keyboard,
    home_keyboard,
    register_fail_keyboard,
    register_success_keyboard,
)
from app.repositories.bot_repo import BotRepo
from app.services.token_validator import TokenValidatorService

logger = logging.getLogger(__name__)

router = Router(name="register")


class RegisterStates(StatesGroup):
    waiting_token = State()
    confirming_register = State()


PROMPT_TOKEN_TEXT = (
    "请发送你的 Bot Token\n"
    "\n"
    "你可以从 @BotFather 获取Token：\n"
    "1. 打开 @BotFather\n"
    "2. 发送 /mybots\n"
    "3. 选择你的Bot\n"
    "4. 点击 \"API Token\"\n"
    "5. 复制Token并发送给我\n"
    "\n"
    "Token格式: 123456:ABC-DEF1234ghIkl-zyx"
)


@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext) -> None:
    """进入Token注册流程"""
    await state.set_state(RegisterStates.waiting_token)
    await message.answer(PROMPT_TOKEN_TEXT, reply_markup=cancel_keyboard())


@router.callback_query(lambda c: c.data == "reg_start")
async def cb_register_start(callback: CallbackQuery, state: FSMContext) -> None:
    """从主菜单按钮进入注册流程"""
    await state.set_state(RegisterStates.waiting_token)
    await callback.message.edit_text(PROMPT_TOKEN_TEXT, reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(RegisterStates.waiting_token)
async def on_token_received(
    message: Message,
    state: FSMContext,
    token_validator: TokenValidatorService,
    settings: Settings,
) -> None:
    """收到Token文本，执行完整验证"""
    token = message.text.strip() if message.text else ""

    try:
        bot_info = await token_validator.full_validate(
            token=token,
            owner_id=message.from_user.id,
            max_bots=settings.MAX_BOTS_PER_USER,
        )
    except TokenFormatError:
        await message.answer(
            "Token格式不正确，请重新发送",
            reply_markup=cancel_keyboard(),
        )
        return
    except TokenLimitError as exc:
        await message.answer(str(exc))
        await state.clear()
        return
    except TokenInvalidError:
        await message.answer(
            "Token无效，请检查后重新发送",
            reply_markup=cancel_keyboard(),
        )
        return
    except TokenDuplicateError as exc:
        await message.answer(str(exc))
        await state.clear()
        return

    await state.update_data(
        token=token,
        bot_id=bot_info.bot_id,
        bot_username=bot_info.username,
        bot_first_name=bot_info.first_name,
    )
    await state.set_state(RegisterStates.confirming_register)

    confirm_text = (
        "检测到Bot信息：\n"
        "\n"
        f"名称: {bot_info.first_name}\n"
        f"用户名: @{bot_info.username}\n"
        f"ID: {bot_info.bot_id}\n"
        "\n"
        "确认将此Bot注册为双向机器人吗？"
    )
    await message.answer(confirm_text, reply_markup=confirm_register_keyboard())


@router.callback_query(lambda c: c.data == "reg_confirm")
async def cb_register_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    token_validator: TokenValidatorService,
    bot_repo: BotRepo,
    registry: object,
) -> None:
    """用户确认注册"""
    data = await state.get_data()
    token = data.get("token", "")
    bot_id = data.get("bot_id", 0)
    bot_username = data.get("bot_username", "")

    encrypted = token_validator.encrypt_token(token)
    owner = callback.from_user

    sub_bot_dto = await bot_repo.create(
        bot_token_encrypted=encrypted,
        bot_id=bot_id,
        bot_username=bot_username,
        owner_id=owner.id,
        owner_username=owner.username,
    )

    try:
        await registry.add_bot(token, bot_id)
    except (RegistryError, Exception) as exc:
        logger.error("Bot启动失败 bot_id=%s: %s", bot_id, exc)
        await bot_repo.update_status(sub_bot_dto.id, "error")
        fail_text = (
            "注册已保存，但Bot启动失败。\n"
            f"错误: {exc}\n"
            "\n"
            "Bot已标记为\"错误\"状态，你可以稍后\n"
            "在 /mybot 中重新启动。"
        )
        await callback.message.edit_text(fail_text, reply_markup=register_fail_keyboard())
        await state.clear()
        await callback.answer()
        return

    success_text = (
        "注册成功!\n"
        "\n"
        f"你的Bot @{bot_username} 已开始工作\n"
        "\n"
        f"现在任何人给 @{bot_username} 发消息，\n"
        "你都会在这里收到通知。\n"
        "直接回复消息即可回复对方。"
    )
    await callback.message.edit_text(
        success_text,
        reply_markup=register_success_keyboard(sub_bot_dto.id),
    )
    await state.clear()
    await callback.answer()


@router.callback_query(lambda c: c.data == "reg_cancel")
async def cb_register_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """取消注册流程"""
    await state.clear()
    await callback.message.edit_text("已取消注册", reply_markup=home_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data == "nav_cancel")
async def cb_nav_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """通用取消（清除FSM状态并返回主菜单）"""
    await state.clear()
    await callback.message.edit_text("操作已取消", reply_markup=home_keyboard())
    await callback.answer()
