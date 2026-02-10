import re

import logging

from aiogram import Bot

from app.dto import BotInfo
from app.exceptions import (
    TokenDuplicateError,
    TokenFormatError,
    TokenInvalidError,
    TokenLimitError,
)
from app.repositories.bot_repo import BotRepo
from app.services.token_encryptor import TokenEncryptor

logger = logging.getLogger(__name__)

TOKEN_PATTERN = re.compile(r"^\d{8,10}:[A-Za-z0-9_-]{35}$")


class TokenValidatorService:
    """Token 验证与加密服务"""

    def __init__(self, bot_repo: BotRepo, encryptor: TokenEncryptor) -> None:
        self._bot_repo = bot_repo
        self._encryptor = encryptor

    def validate_format(self, token: str) -> bool:
        """校验Token格式"""
        return bool(TOKEN_PATTERN.match(token.strip()))

    async def validate_api(self, token: str) -> BotInfo:
        """调用 Telegram API 验证Token

        Raises:
            TokenInvalidError: Token无效
        """
        temp_bot = Bot(token=token)
        try:
            me = await temp_bot.get_me()
            return BotInfo(
                bot_id=me.id,
                username=me.username or "",
                first_name=me.first_name,
            )
        except Exception as exc:
            raise TokenInvalidError(f"Token无效: {exc}") from exc
        finally:
            await temp_bot.session.close()

    async def check_duplicate(self, bot_id: int) -> bool:
        """检查 bot_id 是否已注册

        Returns:
            True=已存在, False=未注册
        """
        return await self._bot_repo.exists_by_bot_id(bot_id)

    async def check_owner_limit(self, owner_id: int, max_bots: int) -> None:
        """检查用户是否超出注册数量限制

        Raises:
            TokenLimitError: 超出限制
        """
        count = await self._bot_repo.count_by_owner(owner_id)
        if count >= max_bots:
            raise TokenLimitError(f"你最多只能注册 {max_bots} 个Bot")

    async def full_validate(
        self,
        token: str,
        owner_id: int,
        max_bots: int,
    ) -> BotInfo:
        """完整验证流程：格式 → 数量限制 → API → 重复检查

        Raises:
            TokenFormatError: 格式错误
            TokenLimitError: 超出限制
            TokenInvalidError: API验证失败
            TokenDuplicateError: 已被注册
        """
        if not self.validate_format(token):
            raise TokenFormatError("Token格式不正确，请检查后重新发送")

        await self.check_owner_limit(owner_id, max_bots)

        bot_info = await self.validate_api(token)

        if await self.check_duplicate(bot_info.bot_id):
            existing = await self._bot_repo.get_by_bot_id(bot_info.bot_id)
            if existing and existing.owner_id == owner_id:
                raise TokenDuplicateError(
                    f"这是你已注册的Bot @{existing.bot_username}"
                )
            raise TokenDuplicateError("该Bot已被其他用户注册")

        return bot_info

    def encrypt_token(self, token: str) -> str:
        """加密Token用于存储"""
        return self._encryptor.encrypt(token)

    def decrypt_token(self, encrypted: str) -> str:
        """解密Token用于创建Bot实例"""
        return self._encryptor.decrypt(encrypted)
