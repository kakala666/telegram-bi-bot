from aiogram import Dispatcher, Router

from app.sub_bot.handlers import owner_reply, start, user_message

sub_router = Router(name="sub_bot")
sub_router.include_router(start.router)
sub_router.include_router(owner_reply.router)
sub_router.include_router(user_message.router)

sub_dp = Dispatcher()
sub_dp.include_router(sub_router)
