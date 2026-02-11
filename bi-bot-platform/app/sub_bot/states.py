from aiogram.fsm.state import State, StatesGroup


class SubBotBroadcastStates(StatesGroup):
    waiting_content = State()
    confirming_broadcast = State()
