from aiogram import Dispatcher, Router

from app.master_bot.handlers import block, callbacks, manage, register, start

master_router = Router(name="master")
master_router.include_router(start.router)
master_router.include_router(register.router)
master_router.include_router(manage.router)
master_router.include_router(block.router)
master_router.include_router(callbacks.router)

master_dp = Dispatcher()
master_dp.include_router(master_router)
