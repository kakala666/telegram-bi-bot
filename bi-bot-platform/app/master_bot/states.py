"""主Bot FSM 状态定义"""

from aiogram.fsm.state import State, StatesGroup


class RegisterStates(StatesGroup):
    waiting_token = State()
    confirming_register = State()


class WelcomeStates(StatesGroup):
    waiting_welcome = State()


class BroadcastStates(StatesGroup):
    selecting_bot = State()
    waiting_content = State()
    confirming_broadcast = State()


class BlockStates(StatesGroup):
    waiting_user_id = State()


class AdStates(StatesGroup):
    waiting_ad_name = State()
    waiting_ad_text = State()
    waiting_ad_button = State()
    waiting_ad_priority = State()
    confirming_ad = State()
    editing_ad_text = State()
    editing_ad_priority = State()
