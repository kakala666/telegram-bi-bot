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
from app.services.token_encryptor import TokenEncryptor
from app.services.token_validator import TokenValidatorService

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
    # TODO: AdInjectorService(ad_repo)
    # TODO: ForwarderService(user_repo, msg_map_repo, bot_repo, ad_injector)
    # TODO: BroadcastService(broadcast_repo, user_repo, registry)
    # TODO: CleanupService(msg_map_repo, broadcast_repo, settings)

    # 6. 创建 sub Dispatcher
    sub_dp = Dispatcher()

    # 7. 创建 BotRegistry
    # TODO: BotRegistry(sub_dp, bot_repo, encryptor)

    # 8. 注入依赖到 master_dp workflow_data
    master_dp.workflow_data.update({
        "bot_repo": bot_repo,
        "user_repo": user_repo,
        "msg_map_repo": msg_map_repo,
        "ad_repo": ad_repo,
        "broadcast_repo": broadcast_repo,
        "token_validator": token_validator,
        "encryptor": encryptor,
        "settings": settings,
        # TODO: 注入 BroadcastService, Registry 等
    })

    sub_dp.workflow_data.update({
        "user_repo": user_repo,
        "bot_repo": bot_repo,
        # TODO: 注入 ForwarderService
    })

    # 9. 创建 Master Bot 实例
    master_bot = Bot(token=settings.MASTER_BOT_TOKEN)

    # 10. 恢复所有活跃子Bot
    # TODO: await registry.recover_all()

    # 11. 启动 Master Bot polling
    logger.info("Starting master bot polling...")
    try:
        await master_dp.start_polling(master_bot)
    finally:
        # 12. 清理资源
        # TODO: await registry.shutdown()
        await engine.dispose()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
