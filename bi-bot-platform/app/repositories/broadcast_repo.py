from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, delete, func, select, update

from app.database.models import BroadcastTask
from app.dto import BroadcastTaskDTO
from app.repositories.base import BaseRepository


class BroadcastRepo(BaseRepository):
    """broadcast_tasks 表操作"""

    @staticmethod
    def _to_dto(row: BroadcastTask) -> BroadcastTaskDTO:
        return BroadcastTaskDTO(
            id=row.id,
            sub_bot_id=row.sub_bot_id,
            content_type=row.content_type,
            total_count=row.total_count,
            sent_count=row.sent_count,
            failed_count=row.failed_count,
            status=row.status,
            created_at=row.created_at,
            completed_at=row.completed_at,
        )

    async def create(
        self,
        sub_bot_id: int,
        owner_id: int,
        content_type: str,
        content_text: str | None,
        content_file_id: str | None,
        content_caption: str | None,
        total_count: int,
    ) -> BroadcastTaskDTO:
        """创建广播任务"""
        async with self._session_factory() as session:
            task = BroadcastTask(
                sub_bot_id=sub_bot_id,
                owner_id=owner_id,
                content_type=content_type,
                content_text=content_text,
                content_file_id=content_file_id,
                content_caption=content_caption,
                total_count=total_count,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return self._to_dto(task)

    async def get_by_id(self, id: int) -> BroadcastTaskDTO | None:
        """按主键查询"""
        async with self._session_factory() as session:
            result = await session.get(BroadcastTask, id)
            return self._to_dto(result) if result else None

    async def get_running_by_bot(self, sub_bot_id: int) -> BroadcastTaskDTO | None:
        """查询某Bot正在运行的广播任务（status='running'）"""
        async with self._session_factory() as session:
            stmt = select(BroadcastTask).where(
                and_(
                    BroadcastTask.sub_bot_id == sub_bot_id,
                    BroadcastTask.status == "running",
                )
            )
            result = await session.scalar(stmt)
            return self._to_dto(result) if result else None

    async def get_latest_by_bot(self, sub_bot_id: int) -> BroadcastTaskDTO | None:
        """查询某Bot最近一次广播任务"""
        async with self._session_factory() as session:
            stmt = (
                select(BroadcastTask)
                .where(BroadcastTask.sub_bot_id == sub_bot_id)
                .order_by(BroadcastTask.created_at.desc())
                .limit(1)
            )
            result = await session.scalar(stmt)
            return self._to_dto(result) if result else None

    async def update_progress(
        self, id: int, sent_count: int, failed_count: int
    ) -> None:
        """更新广播进度"""
        async with self._session_factory() as session:
            stmt = (
                update(BroadcastTask)
                .where(BroadcastTask.id == id)
                .values(sent_count=sent_count, failed_count=failed_count)
            )
            await session.execute(stmt)
            await session.commit()

    async def update_status(
        self, id: int, status: str, completed_at: datetime | None = None
    ) -> None:
        """更新广播状态"""
        values: dict = {"status": status}
        if completed_at is not None:
            values["completed_at"] = completed_at

        async with self._session_factory() as session:
            stmt = (
                update(BroadcastTask)
                .where(BroadcastTask.id == id)
                .values(**values)
            )
            await session.execute(stmt)
            await session.commit()

    async def delete_by_sub_bot(self, sub_bot_id: int) -> int:
        """删除某Bot的所有广播记录"""
        async with self._session_factory() as session:
            stmt = delete(BroadcastTask).where(
                BroadcastTask.sub_bot_id == sub_bot_id
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0

    async def cleanup_expired(self, retention_days: int) -> int:
        """清理过期广播记录"""
        async with self._session_factory() as session:
            cutoff = datetime.utcnow() - timedelta(days=retention_days)
            stmt = delete(BroadcastTask).where(
                BroadcastTask.created_at < cutoff
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount or 0