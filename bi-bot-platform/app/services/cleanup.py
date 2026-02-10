"""清理服务 - 定期清理过期数据"""

from __future__ import annotations

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
