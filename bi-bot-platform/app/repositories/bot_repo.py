from __future__ import annotations

import math

from sqlalchemy import delete, func, select, update

from app.database.models import SubBot
from app.dto import PaginatedResult, SubBotDTO
from app.repositories.base import BaseRepository


class BotRepo(BaseRepository):
    """sub_bots 表操作"""

    @staticmethod
    def _to_dto(row: SubBot) -> SubBotDTO:
        return SubBotDTO(
            id=row.id,
            bot_id=row.bot_id,
            bot_username=row.bot_username,
            owner_id=row.owner_id,
            owner_username=row.owner_username,
            status=row.status,
            welcome_message=row.welcome_message,
            user_count=row.user_count,
            message_count=row.message_count,
            created_at=row.created_at,
        )

    async def create(
        self,
        bot_token_encrypted: str,
        bot_id: int,
        bot_username: str,
        owner_id: int,
        owner_username: str | None,
    ) -> SubBotDTO:
        """创建子Bot记录"""
        async with self._session_factory() as session:
            bot = SubBot(
                bot_token_encrypted=bot_token_encrypted,
                bot_id=bot_id,
                bot_username=bot_username,
                owner_id=owner_id,
                owner_username=owner_username,
            )
            session.add(bot)
            await session.commit()
            await session.refresh(bot)
            return self._to_dto(bot)

    async def get_by_id(self, id: int) -> SubBotDTO | None:
        """按主键查询"""
        async with self._session_factory() as session:
            result = await session.get(SubBot, id)
            return self._to_dto(result) if result else None

    async def get_by_bot_id(self, bot_id: int) -> SubBotDTO | None:
        """按 Telegram bot_id 查询"""
        async with self._session_factory() as session:
            stmt = select(SubBot).where(SubBot.bot_id == bot_id)
            result = await session.scalar(stmt)
            return self._to_dto(result) if result else None

    async def get_by_owner(self, owner_id: int) -> list[SubBotDTO]:
        """查询某用户的所有Bot"""
        async with self._session_factory() as session:
            stmt = select(SubBot).where(SubBot.owner_id == owner_id)
            result = await session.scalars(stmt)
            return [self._to_dto(row) for row in result.all()]

    async def get_all_active(self) -> list[SubBotDTO]:
        """查询所有 status='active' 的Bot（启动恢复用）"""
        async with self._session_factory() as session:
            stmt = select(SubBot).where(SubBot.status == "active")
            result = await session.scalars(stmt)
            return [self._to_dto(row) for row in result.all()]

    async def get_all_paginated(
        self, page: int, page_size: int = 10
    ) -> PaginatedResult:
        """分页查询所有Bot（管理员用）"""
        async with self._session_factory() as session:
            total_stmt = select(func.count()).select_from(SubBot)
            total = await session.scalar(total_stmt) or 0

            total_pages = max(1, math.ceil(total / page_size))
            offset = (page - 1) * page_size

            stmt = (
                select(SubBot)
                .order_by(SubBot.id.desc())
                .offset(offset)
                .limit(page_size)
            )
            result = await session.scalars(stmt)
            items = [self._to_dto(row) for row in result.all()]

            return PaginatedResult(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1,
            )

    async def get_encrypted_token(self, id: int) -> str | None:
        """获取加密的Token（仅BotRegistry恢复时使用）"""
        async with self._session_factory() as session:
            stmt = select(SubBot.bot_token_encrypted).where(SubBot.id == id)
            return await session.scalar(stmt)

    async def count_by_owner(self, owner_id: int) -> int:
        """统计某用户的Bot数量"""
        async with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(SubBot)
                .where(SubBot.owner_id == owner_id)
            )
            return await session.scalar(stmt) or 0

    async def count_all(self) -> dict[str, int]:
        """统计所有Bot数量，按状态分组

        Returns:
            {"active": 38, "stopped": 5, "error": 2, "total": 45}
        """
        async with self._session_factory() as session:
            stmt = (
                select(SubBot.status, func.count())
                .group_by(SubBot.status)
            )
            result = await session.execute(stmt)
            counts: dict[str, int] = {}
            total = 0
            for status, count in result.all():
                counts[status] = count
                total += count
            counts["total"] = total
            return counts

    async def update_status(self, id: int, status: str) -> None:
        """更新Bot状态"""
        async with self._session_factory() as session:
            stmt = (
                update(SubBot)
                .where(SubBot.id == id)
                .values(status=status, updated_at=func.now())
            )
            await session.execute(stmt)
            await session.commit()

    async def update_welcome(self, id: int, welcome_message: str | None) -> None:
        """更新欢迎语"""
        async with self._session_factory() as session:
            stmt = (
                update(SubBot)
                .where(SubBot.id == id)
                .values(welcome_message=welcome_message, updated_at=func.now())
            )
            await session.execute(stmt)
            await session.commit()

    async def increment_user_count(self, id: int, delta: int = 1) -> None:
        """递增用户计数"""
        async with self._session_factory() as session:
            stmt = (
                update(SubBot)
                .where(SubBot.id == id)
                .values(
                    user_count=SubBot.user_count + delta,
                    updated_at=func.now(),
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def increment_message_count(self, id: int, delta: int = 1) -> None:
        """递增消息计数"""
        async with self._session_factory() as session:
            stmt = (
                update(SubBot)
                .where(SubBot.id == id)
                .values(
                    message_count=SubBot.message_count + delta,
                    updated_at=func.now(),
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def delete(self, id: int) -> None:
        """删除Bot记录"""
        async with self._session_factory() as session:
            stmt = delete(SubBot).where(SubBot.id == id)
            await session.execute(stmt)
            await session.commit()

    async def exists_by_bot_id(self, bot_id: int) -> bool:
        """检查 bot_id 是否已注册"""
        async with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(SubBot)
                .where(SubBot.bot_id == bot_id)
            )
            count = await session.scalar(stmt) or 0
            return count > 0
