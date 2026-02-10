from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.exceptions import RegistryError
from app.repositories.bot_repo import BotRepo
from app.services.token_encryptor import TokenEncryptor

logger = logging.getLogger(__name__)


class BotRegistry:
    """子Bot生命周期管理器。

    管理所有子Bot实例的创建、销毁和 polling。
    所有子Bot共享同一个 Dispatcher (sub_dp)。
    """

    def __init__(
        self,
        sub_dp: Dispatcher,
        bot_repo: BotRepo,
        encryptor: TokenEncryptor,
    ) -> None:
        self._dp = sub_dp
        self._bot_repo = bot_repo
        self._encryptor = encryptor
        self._bots: dict[int, Bot] = {}
        self._polling_task: asyncio.Task[None] | None = None

    async def add_bot(self, token: str, bot_id: int) -> None:
        """添加并启动一个子Bot。

        Raises:
            RegistryError: Bot创建或polling失败
        """
        try:
            bot = Bot(token=token)
            me = await bot.get_me()
            if me.id != bot_id:
                await bot.session.close()
                raise RegistryError(f"bot_id 不匹配: 期望 {bot_id}, 实际 {me.id}")
        except RegistryError:
            raise
        except Exception as exc:
            raise RegistryError(f"创建Bot实例失败: {exc}") from exc

        self._bots[bot_id] = bot
        logger.info("已添加子Bot bot_id=%s", bot_id)
        await self.restart_polling()

    async def remove_bot(self, bot_id: int) -> None:
        """停止并移除一个子Bot。"""
        bot = self._bots.pop(bot_id, None)
        if bot is None:
            return
        try:
            await bot.session.close()
        except Exception:
            logger.exception("关闭Bot session失败 bot_id=%s", bot_id)
        logger.info("已移除子Bot bot_id=%s", bot_id)
        if self._bots:
            await self.restart_polling()
        else:
            await self._cancel_polling()

    def get_bot(self, bot_id: int) -> Bot | None:
        """获取Bot实例"""
        return self._bots.get(bot_id)

    def get_all_bot_ids(self) -> list[int]:
        """获取所有运行中的Bot ID列表"""
        return list(self._bots.keys())

    def is_running(self, bot_id: int) -> bool:
        """检查某Bot是否正在运行"""
        return bot_id in self._bots

    def count_running(self) -> int:
        """获取运行中的Bot数量"""
        return len(self._bots)

    async def recover_all(self) -> dict[str, int]:
        """启动时恢复所有活跃Bot。

        Returns:
            {"recovered": 成功数, "failed": 失败数}
        """
        active_bots = await self._bot_repo.get_all_active()
        recovered = 0
        failed = 0

        for sub_bot in active_bots:
            encrypted_token = await self._bot_repo.get_encrypted_token(sub_bot.id)
            if not encrypted_token:
                logger.error("Bot id=%s 无加密Token，标记为error", sub_bot.id)
                await self._bot_repo.update_status(sub_bot.id, "error")
                failed += 1
                continue

            try:
                token = self._encryptor.decrypt(encrypted_token)
                bot = Bot(token=token)
                me = await bot.get_me()
                self._bots[me.id] = bot
                recovered += 1
                logger.info("恢复子Bot @%s (bot_id=%s)", me.username, me.id)
            except Exception as exc:
                logger.error("恢复Bot id=%s 失败: %s", sub_bot.id, exc)
                await self._bot_repo.update_status(sub_bot.id, "error")
                failed += 1

        if self._bots:
            await self.restart_polling()

        result = {"recovered": recovered, "failed": failed}
        logger.info("Bot恢复完成: %s", result)
        return result

    async def restart_polling(self) -> None:
        """重启 polling（add/remove后调用）。

        取消当前 polling task，如果有Bot则创建新的。
        """
        await self._cancel_polling()

        if not self._bots:
            return

        bots = list(self._bots.values())
        self._polling_task = asyncio.create_task(
            self._run_polling(bots),
            name="sub_bot_polling",
        )
        logger.info("已启动子Bot polling，共 %d 个Bot", len(bots))

    async def shutdown(self) -> None:
        """关闭所有Bot（程序退出时调用）。"""
        await self._cancel_polling()

        for bot_id, bot in self._bots.items():
            try:
                await bot.session.close()
            except Exception:
                logger.exception("关闭Bot session失败 bot_id=%s", bot_id)

        self._bots.clear()
        logger.info("所有子Bot已关闭")

    async def _cancel_polling(self) -> None:
        """取消当前 polling task。"""
        if self._polling_task is not None and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None

    async def _run_polling(self, bots: list[Bot]) -> None:
        """运行 polling（内部方法）。"""
        try:
            await self._dp.start_polling(*bots)
        except asyncio.CancelledError:
            logger.info("子Bot polling 已取消")
        except Exception:
            logger.exception("子Bot polling 异常退出")
