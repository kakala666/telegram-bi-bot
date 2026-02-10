from __future__ import annotations

import math
from datetime import datetime

from sqlalchemy import and_, delete, func, select, update

from app.database.models import BotUser, SubBot
from app.dto import BotUserDTO, PaginatedResult
from app.repositories.base import BaseRepository


class UserRepo(BaseRepository):
    """bot_users 表操作"""

    @staticmethod
    def _to_dto(row: BotUser) -> BotUserDTO:
        return BotUserDTO(
            id=row.id,
            sub_bot_id=row.sub_bot_id,
            user_id=row.user_id,
            username=row.username,
            display_name=row.display_name,
            is_blocked=row.is_blocked,
            is_banned_by_telegram=row.is_banned_by_telegram,
            first_seen=row.first_seen,
            last_active=row.last_active,
        )

    @staticmethod
    def _build_display_name(
        first_name: str | None, last_name: str | None
    ) -> str:
        parts = [p for p in (first_name, last_name) if p]
        return " ".join(parts) if parts else "Unknown"

    async def get_or_create(
        self,
        sub_bot_id: int,
        user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> tuple[BotUserDTO, bool]:
        """获取或创建用户记录

        Returns:
            (用户DTO, 是否新创建)
        """
        async with self._session_factory() as session:
            stmt = select(BotUser).where(
                and_(
                    BotUser.sub_bot_id == sub_bot_id,
                    BotUser.user_id == user_id,
                )
            )
            existing = await session.scalar(stmt)
            if existing:
                return self._to_dto(existing), False

            display_name = self._build_display_name(first_name, last_name)
            user = BotUser(
                sub_bot_id=sub_bot_id,
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                display_name=display_name,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return self._to_dto(user), True

    async def get_by_sub_bot_and_user(
        self, sub_bot_id: int, user_id: int
    ) -> BotUserDTO | None:
        """查询特定Bot下的特定用户"""
        async with self._session_factory() as session:
            stmt = select(BotUser).where(
                and_(
                    BotUser.sub_bot_id == sub_bot_id,
                    BotUser.user_id == user_id,
                )
            )
            result = await session.scalar(stmt)
            return self._to_dto(result) if result else None

    async def get_active_users(self, sub_bot_id: int) -> list[BotUserDTO]:
        """获取某Bot的所有活跃用户（未封禁 + 未被Telegram屏蔽）"""
        async with self._session_factory() as session:
            stmt = select(BotUser).where(
                and_(
                    BotUser.sub_bot_id == sub_bot_id,
                    BotUser.is_blocked == False,  # noqa: E712
                    BotUser.is_banned_by_telegram == False,  # noqa: E712
                )
            )
            result = await session.scalars(stmt)
            return [self._to_dto(row) for row in result.all()]

    async def get_users_paginated(
        self, sub_bot_id: int, page: int, page_size: int = 10
    ) -> PaginatedResult:
        """分页查询某Bot的用户列表"""
        async with self._session_factory() as session:
            total_stmt = (
                select(func.count())
                .select_from(BotUser)
                .where(BotUser.sub_bot_id == sub_bot_id)
            )
            total = await session.scalar(total_stmt) or 0

            total_pages = max(1, math.ceil(total / page_size))
            offset = (page - 1) * page_size

            stmt = (
                select(BotUser)
                .where(BotUser.sub_bot_id == sub_bot_id)
                .order_by(BotUser.last_active.desc())
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

    async def count_active(self, sub_bot_id: int) -> int:
        """统计某Bot的活跃用户数"""
        async with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(BotUser)
                .where(
                    and_(
                        BotUser.sub_bot_id == sub_bot_id,
                        BotUser.is_blocked == False,  # noqa: E712
                        BotUser.is_banned_by_telegram == False,  # noqa: E712
                    )
                )
            )
            return await session.scalar(stmt) or 0

    async def update_blocked(
        self, sub_bot_id: int, user_id: int, is_blocked: bool
    ) -> None:
        """更新封禁状态"""
        async with self._session_factory() as session:
            stmt = (
                update(BotUser)
                .where(
                    and_(
                        BotUser.sub_bot_id == sub_bot_id,
                        BotUser.user_id == user_id,
                    )
                )
                .values(is_blocked=is_blocked)
            )
            await session.execute(stmt)
            await session.commit()

    async def update_banned_by_telegram(
        self, sub_bot_id: int, user_id: int, is_banned: bool
    ) -> None:
        """更新Telegram屏蔽状态（发送失败时标记）"""
        async with self._session_factory() as session:
            stmt = (
                update(BotUser)
                .where(
                    and_(
                        BotUser.sub_bot_id == sub_bot_id,
                        BotUser.user_id == user_id,
                    )
                )
                .values(is_banned_by_telegram=is_banned)
            )
            await session.execute(stmt)
            await session.commit()

    async def update_last_active(
        self, sub_bot_id: int, user_id: int
    ) -> None:
        """更新最后活跃时间"""
        async with self._session_factory() as session:
            stmt = (
                update(BotUser)
                .where(
                    and_(
                        BotUser.sub_bot_id == sub_bot_id,
                        BotUser.user_id == user_id,
                    )
                )
                .values(last_active=func.now())
            )
            await session.execute(stmt)
            await session.commit()

    async def find_user_across_bots(
        self, owner_id: int, target_user_id: int
    ) -> list[BotUserDTO]:
        """在某主人的所有Bot中查找指定用户（/block命令用）

        需要 JOIN sub_bots 表按 owner_id 过滤
        """
        async with self._session_factory() as session:
            stmt = (
                select(BotUser)
                .join(SubBot, BotUser.sub_bot_id == SubBot.id)
                .where(
                    and_(
                        SubBot.owner_id == owner_id,
                        BotUser.user_id == target_user_id,
                    )
                )
            )
            result = await session.scalars(stmt)
            return [self._to_dto(row) for row in result.all()]

    async def delete_by_sub_bot(self, sub_bot_id: int) -> int:
        """删除某Bot的所有用户记录，返回删除数量"""
        async with self._session_factory() as session:
            stmt = (
                delete(BotUser)
                .where(BotUser.sub_bot_id == sub_bot_id)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0

    async def count_total_users(self) -> int:
        """统计平台总用户数（管理员统计用）"""
        async with self._session_factory() as session:
            stmt = select(func.count()).select_from(BotUser)
            return await session.scalar(stmt) or 0