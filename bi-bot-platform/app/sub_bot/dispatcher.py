import logging

from aiogram import Dispatcher, Router
from aiogram.types import ErrorEvent

from app.sub_bot.handlers import broadcast, owner_reply, start, user_message
from app.sub_bot.middleware.bot_context import BotContextMiddleware
from app.sub_bot.middleware.error_handler import ErrorHandlerMiddleware

logger = logging.getLogger(__name__)

sub_router = Router(name="sub_bot")
sub_router.include_router(start.router)
sub_router.include_router(broadcast.router)
sub_router.include_router(owner_reply.router)
sub_router.include_router(user_message.router)

# 注册中间件（bot_repo 在运行时通过 workflow_data 注入）
# 洋葱模型：先注册的在外层，ErrorHandler 应在外层才能捕获 BotContext 异常
_error_handler_mw = ErrorHandlerMiddleware()
_bot_context_mw = BotContextMiddleware()

sub_router.message.outer_middleware(_error_handler_mw)
sub_router.message.outer_middleware(_bot_context_mw)

sub_router.callback_query.outer_middleware(_error_handler_mw)
sub_router.callback_query.outer_middleware(_bot_context_mw)

sub_dp = Dispatcher()
sub_dp.include_router(sub_router)


@sub_dp.errors()
async def on_sub_dp_error(event: ErrorEvent) -> bool:
    """全局错误处理：捕获子Bot未处理异常"""
    logger.exception("子Bot dispatcher 未捕获异常: %s", event.exception)
    return False
