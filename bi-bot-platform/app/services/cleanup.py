"""清理服务 - 定期清理过期数据"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings
    from app.repositories.broadcast_repo import BroadcastRepo
    from app.repositories.message_map_repo import MessageMapRepo

logger = logging.getLogger(__name__)


class CleanupService:
    """定期清理服务 - 清理过期消息映射和已完成广播任务"""

    def __init__(
        self,
        msg_map_repo: MessageMapRepo,
        broadcast_repo: BroadcastRepo,
        settings: Settings,
    ) -> None:
        self._msg_map_repo = msg_map_repo
        self._broadcast_repo = broadcast_repo
        self._settings = settings
        self._task: asyncio.Task | None = None

    async def cleanup_all(self) -> dict[str, int]:
        """执行所有清理任务

        Returns:
            dict: {"message_maps": 删除数, "broadcast_tasks": 删除数}
        """
        retention_days = self._settings.MESSAGE_MAP_RETENTION_DAYS

        # 清理过期消息映射
        msg_deleted = await self._msg_map_repo.cleanup_expired(retention_days)
        logger.info("清理过期消息映射: %d 条", msg_deleted)

        # 清理已完成的广播任务（保留30天）
        broadcast_deleted = await self._broadcast_repo.cleanup_expired(retention_days=30)
        logger.info("清理已完成广播任务: %d 条", broadcast_deleted)

        return {
            "message_maps": msg_deleted,
            "broadcast_tasks": broadcast_deleted,
        }

    async def start_periodic(self, interval_hours: int = 24) -> None:
        """启动定期清理后台任务

        Args:
            interval_hours: 清理间隔（小时）
        """
        if self._task and not self._task.done():
            logger.warning("定期清理任务已在运行")
            return

        self._task = asyncio.create_task(
            self._periodic_loop(interval_hours),
            name="cleanup_periodic",
        )
        logger.info("定期清理任务已启动，间隔 %d 小时", interval_hours)

    async def stop(self) -> None:
        """停止定期清理任务"""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("定期清理任务已停止")

    async def _periodic_loop(self, interval_hours: int) -> None:
        """定期清理循环（内部方法）"""
        interval_seconds = interval_hours * 3600
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                result = await self.cleanup_all()
                logger.info("定期清理完成: %s", result)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("定期清理执行失败")
