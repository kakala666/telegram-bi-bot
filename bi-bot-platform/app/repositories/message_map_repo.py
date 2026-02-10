from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, func, select

from app.database.models import MessageMap
from app.repositories.base import BaseRepository


class MessageMapRepo(BaseRepository):
    """message_maps 表操作"""

    async def create(
        self,
        sub_bot_id: int,
        user_id: int,
        user_msg_id: int,
        forwarded_msg_id: int,
        direction: str = "in",
    ) -> None:
        """创建消息映射记录"""
        async with self._session_factory() as session:
            mapping = MessageMap(
                sub_bot_id=sub_bot_id,
                user_id=user_id,
                user_msg_id=user_msg_id,
                forwarded_msg_id=forwarded_msg_id,
                direction=direction,
            )
            session.add(mapping)
            await session.commit()

    async def get_by_forwarded_msg(
        self, sub_bot_id: int, forwarded_msg_id: int
    ) -> tuple[int, int] | None:
        """根据转发消息ID查找原始用户

        Returns:
            (user_id, user_msg_id) 或 None
        """
        async with self._session_factory() as session:
            stmt = select(
                MessageMap.user_id, MessageMap.user_msg_id
            ).where(
                and_(
                    MessageMap.sub_bot_id == sub_bot_id,
                    MessageMap.forwarded_msg_id == forwarded_msg_id,
                )
            )
            result = await session.execute(stmt)
            row = result.first()
            if row is None:
                return None
            return (row[0], row[1])

    async def cleanup_expired(self, retention_days: int) -> int:
        """清理过期映射记录，返回删除数量"""
        async with self._session_factory() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            stmt = delete(MessageMap).where(MessageMap.created_at < cutoff)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0

    async def delete_by_sub_bot(self, sub_bot_id: int) -> int:
        """删除某Bot的所有映射记录，返回删除数量"""
        async with self._session_factory() as session:
            stmt = delete(MessageMap).where(
                MessageMap.sub_bot_id == sub_bot_id
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0

    async def count_all(self) -> int:
        """统计总映射记录数（管理员系统状态用）"""
        async with self._session_factory() as session:
            stmt = select(func.count()).select_from(MessageMap)
            return await session.scalar(stmt) or 0
