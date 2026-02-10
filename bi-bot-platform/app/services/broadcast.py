"""广播服务 - 管理群发消息任务"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from app.dto import BroadcastProgress, BroadcastTaskDTO
from app.exceptions import BroadcastError

if TYPE_CHECKING:
    from aiogram import Bot

    from app.repositories.broadcast_repo import BroadcastRepo
    from app.repositories.user_repo import UserRepo
    from app.sub_bot.registry import BotRegistry

logger = logging.getLogger(__name__)


class BroadcastService:
    """广播服务 - 异步群发消息给Bot的所有活跃用户"""

    def __init__(
        self,
        broadcast_repo: BroadcastRepo,
        user_repo: UserRepo,
        bot_registry: BotRegistry,
    ) -> None:
        self._broadcast_repo = broadcast_repo
        self._user_repo = user_repo
        self._registry = bot_registry
        self._running_tasks: dict[int, asyncio.Task] = {}

    async def start(
        self,
        sub_bot_id: int,
        owner_id: int,
        content_type: str,
        content_text: str | None,
        content_file_id: str | None,
        content_caption: str | None,
    ) -> BroadcastTaskDTO:
        """发起广播任务

        Args:
            sub_bot_id: 子Bot ID
            owner_id: Bot主人ID
            content_type: 内容类型 (text/photo/video/document/audio/sticker)
            content_text: 文本内容
            content_file_id: 文件ID
            content_caption: 媒体说明

        Returns:
            BroadcastTaskDTO: 创建的广播任务

        Raises:
            BroadcastError: 有正在运行的广播或间隔不足5分钟
        """
        # 检查是否有正在运行的广播
        running = await self._broadcast_repo.get_running_by_bot(sub_bot_id)
        if running:
            raise BroadcastError("该Bot已有正在进行的广播任务，请等待完成后再试")

        # 检查最小间隔（5分钟）
        latest = await self._broadcast_repo.get_latest_by_bot(sub_bot_id)
        if latest:
            now = datetime.now(timezone.utc)
            elapsed = (now - latest.created_at).total_seconds()
            if elapsed < 300:  # 5分钟 = 300秒
                raise BroadcastError("两次广播之间请至少间隔5分钟")

        # 获取活跃用户列表
        users = await self._user_repo.get_active_users(sub_bot_id)
        total_count = len(users)

        # 创建广播任务记录
        task = await self._broadcast_repo.create(
            sub_bot_id=sub_bot_id,
            owner_id=owner_id,
            content_type=content_type,
            content_text=content_text,
            content_file_id=content_file_id,
            content_caption=content_caption,
            total_count=total_count,
        )

        # 启动异步广播任务
        asyncio_task = asyncio.create_task(
            self._execute_broadcast(task.id, sub_bot_id, users, content_type, content_text, content_file_id, content_caption),
            name=f"broadcast_{task.id}",
        )
        self._running_tasks[task.id] = asyncio_task

        logger.info("广播任务已启动 task_id=%s sub_bot_id=%s total=%s", task.id, sub_bot_id, total_count)
        return task

    async def cancel(self, task_id: int) -> bool:
        """取消广播任务

        Args:
            task_id: 任务ID

        Returns:
            bool: True=成功取消, False=任务不存在或已完成
        """
        task = await self._broadcast_repo.get_by_id(task_id)
        if not task or task.status != "running":
            return False

        # 更新数据库状态
        await self._broadcast_repo.update_status(task_id, "cancelled", completed_at=None)

        # 取消asyncio任务
        asyncio_task = self._running_tasks.get(task_id)
        if asyncio_task and not asyncio_task.done():
            asyncio_task.cancel()

        # 从运行列表移除
        self._running_tasks.pop(task_id, None)

        logger.info("广播任务已取消 task_id=%s", task_id)
        return True

    async def get_progress(self, task_id: int) -> BroadcastProgress | None:
        """查询广播进度

        Args:
            task_id: 任务ID

        Returns:
            BroadcastProgress | None: 进度信息，任务不存在返回None
        """
        task = await self._broadcast_repo.get_by_id(task_id)
        if not task:
            return None

        percent = int((task.sent_count / task.total_count) * 100) if task.total_count > 0 else 0
        progress_bar = self._generate_progress_bar(task.sent_count, task.total_count)

        return BroadcastProgress(
            task_id=task.id,
            total=task.total_count,
            sent=task.sent_count,
            failed=task.failed_count,
            status=task.status,
            percent=percent,
            progress_bar=progress_bar,
        )

    async def _execute_broadcast(
        self,
        task_id: int,
        sub_bot_id: int,
        users: list,
        content_type: str,
        content_text: str | None,
        content_file_id: str | None,
        content_caption: str | None,
    ) -> None:
        """异步执行广播（内部方法）"""
        bot = self._registry.get_bot(sub_bot_id)
        if not bot:
            logger.error("Bot不存在或未运行 sub_bot_id=%s", sub_bot_id)
            await self._broadcast_repo.update_status(task_id, "failed", completed_at=datetime.now(timezone.utc))
            return

        rate_limit = 20  # 20条/秒
        delay = 1.0 / rate_limit  # 每条消息间隔

        sent_count = 0
        failed_count = 0

        for user in users:
            # 检查是否被取消（从内存中检查，避免频繁查询数据库）
            if task_id not in self._running_tasks:
                logger.info("广播任务已取消 task_id=%s", task_id)
                break

            try:
                await self._send_broadcast_message(
                    bot, user.user_id, content_type, content_text, content_file_id, content_caption
                )
                sent_count += 1

            except TelegramForbiddenError:
                # 用户已屏蔽Bot
                failed_count += 1
                await self._user_repo.update_banned_by_telegram(sub_bot_id, user.user_id, True)
                logger.debug("用户已屏蔽Bot user_id=%s", user.user_id)

            except TelegramRetryAfter as e:
                # Telegram要求等待（触发限速）
                logger.warning("触发限速，等待 %s 秒", e.retry_after)
                await asyncio.sleep(e.retry_after)
                # 重试当前用户
                try:
                    await self._send_broadcast_message(
                        bot, user.user_id, content_type, content_text, content_file_id, content_caption
                    )
                    sent_count += 1
                except Exception:
                    failed_count += 1
                    logger.exception("重试发送失败 user_id=%s", user.user_id)

            except Exception:
                failed_count += 1
                logger.exception("发送广播消息失败 user_id=%s", user.user_id)

            # 限速等待
            await asyncio.sleep(delay)

            # 每5条更新一次数据库进度（频繁更新以便测试）
            if (sent_count + failed_count) % 5 == 0:
                await self._broadcast_repo.update_progress(task_id, sent_count, failed_count)

        # 广播完成，更新最终状态
        await self._broadcast_repo.update_progress(task_id, sent_count, failed_count)
        await self._broadcast_repo.update_status(task_id, "completed", completed_at=datetime.now(timezone.utc))

        # 从运行列表移除
        self._running_tasks.pop(task_id, None)

        logger.info("广播任务完成 task_id=%s sent=%s failed=%s", task_id, sent_count, failed_count)

    async def _send_broadcast_message(
        self,
        bot: Bot,
        user_id: int,
        content_type: str,
        content_text: str | None,
        content_file_id: str | None,
        content_caption: str | None,
    ) -> None:
        """发送单条广播消息"""
        match content_type:
            case "text":
                await bot.send_message(
                    chat_id=user_id,
                    text=content_text or "",
                    parse_mode="HTML",
                )
            case "photo":
                await bot.send_photo(
                    chat_id=user_id,
                    photo=content_file_id or "",
                    caption=content_caption,
                    parse_mode="HTML",
                )
            case "video":
                await bot.send_video(
                    chat_id=user_id,
                    video=content_file_id or "",
                    caption=content_caption,
                    parse_mode="HTML",
                )
            case "document":
                await bot.send_document(
                    chat_id=user_id,
                    document=content_file_id or "",
                    caption=content_caption,
                    parse_mode="HTML",
                )
            case "audio":
                await bot.send_audio(
                    chat_id=user_id,
                    audio=content_file_id or "",
                    caption=content_caption,
                    parse_mode="HTML",
                )
            case "sticker":
                await bot.send_sticker(
                    chat_id=user_id,
                    sticker=content_file_id or "",
                )
            case _:
                logger.error("不支持的内容类型: %s", content_type)

    @staticmethod
    def _generate_progress_bar(current: int, total: int, length: int = 20) -> str:
        """生成文本进度条"""
        if total == 0:
            return "░" * length + " 0%"

        percent = int((current / total) * 100)
        filled = int(length * percent / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"{bar} {percent}%"
