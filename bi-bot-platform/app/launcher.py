"""应用入口 - 初始化所有依赖并启动 Bot polling"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import Settings
from app.database.engine import create_engine, create_session_factory
from app.database.models import Base
from app.master_bot.dispatcher import master_dp, master_router
from app.repositories.ad_repo import AdRepo
from app.repositories.bot_repo import BotRepo
from app.repositories.broadcast_repo import BroadcastRepo
from app.repositories.message_map_repo import MessageMapRepo
from app.repositories.user_repo import UserRepo
from app.services.ad_injector import AdInjectorService
from app.services.broadcast import BroadcastService
from app.services.cleanup import CleanupService
from app.services.forwarder import ForwarderService
from app.services.token_encryptor import TokenEncryptor
from app.services.token_validator import TokenValidatorService
from app.sub_bot.dispatcher import sub_dp
from app.sub_bot.registry import BotRegistry

logger = logging.getLogger(__name__)


async def main() -> None:
    """主入口函数"""
    # 1. 加载配置
    settings = Settings()

    # 2. 初始化数据库引擎
    engine = create_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)

    # 3. 创建所有 Repository
    bot_repo = BotRepo(session_factory)
    user_repo = UserRepo(session_factory)
    msg_map_repo = MessageMapRepo(session_factory)
    ad_repo = AdRepo(session_factory)
    broadcast_repo = BroadcastRepo(session_factory)

    # 4. 创建 TokenEncryptor
    encryptor = TokenEncryptor(settings.TOKEN_ENCRYPTION_KEY)

    # 5. 创建 Service 层
    token_validator = TokenValidatorService(bot_repo, encryptor)
    ad_injector = AdInjectorService(ad_repo)
    forwarder = ForwarderService(user_repo, msg_map_repo, bot_repo, ad_injector)

    # 6. 创建 BotRegistry
    registry = BotRegistry(sub_dp, bot_repo, encryptor)

    # 7. 创建 BroadcastService（依赖 registry）
    broadcast_svc = BroadcastService(broadcast_repo, user_repo, registry)

    # 8. 创建 CleanupService
    cleanup_svc = CleanupService(msg_map_repo, broadcast_repo, settings)

    # 9. 注入依赖到 master_dp workflow_data
    master_dp.workflow_data.update({
        "bot_repo": bot_repo,
        "user_repo": user_repo,
        "msg_map_repo": msg_map_repo,
        "ad_repo": ad_repo,
        "broadcast_repo": broadcast_repo,
        "token_validator": token_validator,
        "encryptor": encryptor,
        "settings": settings,
        "registry": registry,
        "broadcast_svc": broadcast_svc,
        "ad_injector": ad_injector,
        "forwarder": forwarder,
        "cleanup_svc": cleanup_svc,
    })

    sub_dp.workflow_data.update({
        "user_repo": user_repo,
        "bot_repo": bot_repo,
        "forwarder": forwarder,
    })

    # 10. 创建 Master Bot 实例
    master_bot = Bot(token=settings.MASTER_BOT_TOKEN)

    # 11. 恢复所有活跃子Bot
    logger.info("恢复所有活跃子Bot...")
    recovery_result = await registry.recover_all()
    logger.info("恢复完成: %s", recovery_result)

    # 12. 启动 Master Bot polling
    logger.info("Starting master bot polling...")
    try:
        await master_dp.start_polling(master_bot)
    finally:
        # 13. 清理资源
        logger.info("Shutting down...")
        await registry.shutdown()
        await engine.dispose()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
