from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import Message

from app.dto import BotUserDTO, ForwardResult, SubBotDTO
from app.repositories.bot_repo import BotRepo
from app.repositories.message_map_repo import MessageMapRepo
from app.repositories.user_repo import UserRepo

if TYPE_CHECKING:
    from app.services.ad_injector import AdInjectorService

logger = logging.getLogger(__name__)

SEPARATOR = "━━━━━━━━━━━━━━━"


class ForwarderService:
    """双向消息转发核心服务"""

    def __init__(
        self,
        user_repo: UserRepo,
        msg_map_repo: MessageMapRepo,
        bot_repo: BotRepo,
        ad_injector: AdInjectorService,
    ) -> None:
        self._user_repo = user_repo
        self._msg_map_repo = msg_map_repo
        self._bot_repo = bot_repo
        self._ad_injector = ad_injector

    async def forward_to_owner(
        self,
        bot: Bot,
        sub_bot: SubBotDTO,
        message: Message,
    ) -> ForwardResult:
        """将终端用户的消息转发给Bot主人"""
        user = message.from_user
        bot_user, is_new = await self._user_repo.get_or_create(
            sub_bot_id=sub_bot.id,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        if is_new:
            await self._bot_repo.increment_user_count(sub_bot.id)

        if bot_user.is_blocked:
            await bot.send_message(chat_id=user.id, text="你已被限制使用此Bot")
            return ForwardResult(success=False, forwarded_msg_id=None, error="blocked")

        await self._user_repo.update_last_active(sub_bot.id, user.id)

        header = self._build_user_header(bot_user)

        try:
            sent = await self._send_to_owner(bot, sub_bot.owner_id, message, header)
        except TelegramForbiddenError:
            logger.error("Bot主人屏蔽了Bot sub_bot_id=%s", sub_bot.id)
            await self._bot_repo.update_status(sub_bot.id, "error")
            return ForwardResult(success=False, forwarded_msg_id=None, error="owner_blocked")
        except Exception as exc:
            logger.error("转发消息失败: %s", exc)
            return ForwardResult(success=False, forwarded_msg_id=None, error=str(exc))

        await self._msg_map_repo.create(
            sub_bot_id=sub_bot.id,
            user_id=user.id,
            user_msg_id=message.message_id,
            forwarded_msg_id=sent.message_id,
            direction="in",
        )
        await self._bot_repo.increment_message_count(sub_bot.id)

        return ForwardResult(
            success=True,
            forwarded_msg_id=sent.message_id,
            error=None,
        )

    async def reply_to_user(
        self,
        bot: Bot,
        sub_bot: SubBotDTO,
        message: Message,
    ) -> ForwardResult:
        """将Bot主人的回复发送给终端用户"""
        reply = message.reply_to_message
        if reply is None:
            await self.handle_no_reply(bot, sub_bot, message)
            return ForwardResult(success=False, forwarded_msg_id=None, error="no_reply")

        mapping = await self._msg_map_repo.get_by_forwarded_msg(
            sub_bot_id=sub_bot.id,
            forwarded_msg_id=reply.message_id,
        )
        if mapping is None:
            await bot.send_message(
                chat_id=sub_bot.owner_id,
                text="找不到该消息的原始用户，可能消息记录已过期。",
            )
            return ForwardResult(success=False, forwarded_msg_id=None, error="no_mapping")

        target_user_id, _ = mapping

        ad_result = await self._ad_injector.inject(
            text=message.text or message.caption,
            sub_bot_id=sub_bot.id,
        )

        try:
            sent = await self._send_to_user(
                bot, target_user_id, message, ad_result,
            )
        except TelegramForbiddenError:
            await self._user_repo.update_banned_by_telegram(
                sub_bot.id, target_user_id, is_banned=True,
            )
            await bot.send_message(
                chat_id=sub_bot.owner_id,
                text="发送失败，该用户已屏蔽Bot",
                reply_to_message_id=message.message_id,
            )
            return ForwardResult(success=False, forwarded_msg_id=None, error="user_blocked")
        except Exception as exc:
            logger.error("回复用户失败: %s", exc)
            await bot.send_message(
                chat_id=sub_bot.owner_id,
                text=f"发送失败: {exc}",
                reply_to_message_id=message.message_id,
            )
            return ForwardResult(success=False, forwarded_msg_id=None, error=str(exc))

        await self._msg_map_repo.create(
            sub_bot_id=sub_bot.id,
            user_id=target_user_id,
            user_msg_id=sent.message_id,
            forwarded_msg_id=message.message_id,
            direction="out",
        )
        await self._bot_repo.increment_message_count(sub_bot.id)

        bot_user = await self._user_repo.get_by_sub_bot_and_user(
            sub_bot.id, target_user_id,
        )
        display = bot_user.display_name if bot_user else str(target_user_id)
        await bot.send_message(
            chat_id=sub_bot.owner_id,
            text=f"✓ 消息已发送给 {display}",
            reply_to_message_id=message.message_id,
        )

        return ForwardResult(
            success=True,
            forwarded_msg_id=sent.message_id,
            error=None,
        )

    async def handle_no_reply(
        self,
        bot: Bot,
        sub_bot: SubBotDTO,
        message: Message,
    ) -> None:
        """Bot主人直接发消息（未回复任何消息）时的处理"""
        await bot.send_message(
            chat_id=sub_bot.owner_id,
            text=(
                "请回复一条转发的消息来回复用户。\n"
                "如需广播，请使用主Bot的 /broadcast 命令。"
            ),
        )

    def _build_user_header(self, user: BotUserDTO) -> str:
        """构建用户信息头"""
        header = f"👤 {user.display_name}"
        if user.username:
            header += f" (@{user.username})"
        header += f" [ID:{user.user_id}]"
        return header

    async def _send_to_owner(
        self,
        bot: Bot,
        owner_id: int,
        message: Message,
        header: str,
    ) -> Message:
        """根据消息类型转发给Bot主人，返回发送的消息。"""
        if message.text:
            return await bot.send_message(
                chat_id=owner_id,
                text=f"{header}\n{SEPARATOR}\n{message.text}",
            )

        caption = f"{header}\n{SEPARATOR}\n{message.caption or ''}"

        if message.photo:
            return await bot.send_photo(
                chat_id=owner_id,
                photo=message.photo[-1].file_id,
                caption=caption,
            )
        if message.video:
            return await bot.send_video(
                chat_id=owner_id,
                video=message.video.file_id,
                caption=caption,
            )
        if message.document:
            return await bot.send_document(
                chat_id=owner_id,
                document=message.document.file_id,
                caption=caption,
            )
        if message.audio:
            return await bot.send_audio(
                chat_id=owner_id,
                audio=message.audio.file_id,
                caption=caption,
            )
        if message.voice:
            return await bot.send_voice(
                chat_id=owner_id,
                voice=message.voice.file_id,
                caption=header,
            )

        if message.sticker:
            await bot.send_message(chat_id=owner_id, text=header)
            return await bot.send_sticker(
                chat_id=owner_id,
                sticker=message.sticker.file_id,
            )

        # video_note, location, contact 等：先发header再copy
        await bot.send_message(chat_id=owner_id, text=header)
        return await bot.copy_message(
            chat_id=owner_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )

    async def _send_to_user(
        self,
        bot: Bot,
        user_id: int,
        message: Message,
        ad_result: object,
    ) -> Message:
        """根据消息类型发送给终端用户（含广告注入），返回发送的消息。"""
        ad_text = ad_result.text if ad_result else None
        ad_keyboard = ad_result.keyboard if ad_result else None

        if message.text:
            text = ad_text if ad_text else message.text
            return await bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=ad_keyboard,
            )

        if message.photo:
            return await bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=ad_text or message.caption,
                reply_markup=ad_keyboard,
            )

        if message.video:
            return await bot.send_video(
                chat_id=user_id,
                video=message.video.file_id,
                caption=ad_text or message.caption,
                reply_markup=ad_keyboard,
            )

        if message.document:
            return await bot.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=ad_text or message.caption,
                reply_markup=ad_keyboard,
            )

        if message.audio:
            return await bot.send_audio(
                chat_id=user_id,
                audio=message.audio.file_id,
                caption=ad_text or message.caption,
                reply_markup=ad_keyboard,
            )

        # voice, sticker, video_note, location, contact 等：
        # 先 copy 原始消息，再单独发送广告
        sent = await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )

        if ad_text and ad_text != (message.text or message.caption or ""):
            await bot.send_message(
                chat_id=user_id,
                text=ad_text,
                reply_markup=ad_keyboard,
            )

        return sent
