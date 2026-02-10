from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.dto import SubBotDTO


class IsOwnerFilter(BaseFilter):
    def __init__(self, is_owner: bool = True) -> None:
        self.is_owner = is_owner

    async def __call__(self, message: Message, sub_bot: SubBotDTO) -> bool:
        result = message.from_user.id == sub_bot.owner_id
        return result if self.is_owner else not result
