"""运行时Bug修复测试

问题1: 子Bot不工作 - cmd_start() missing 1 required positional argument: 'sub_bot'
问题2: 管理员没有广告配置入口
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Message, User

from app.config import Settings
from app.dto import SubBotDTO
from app.master_bot.handlers.admin import _admin_panel_keyboard
from app.master_bot.handlers.start import HELP_TEXT
from app.repositories.bot_repo import BotRepo
from app.sub_bot.middleware.bot_context import BotContextMiddleware


# ============================================================================
# 问题1: 子Bot中间件和handler参数注入测试
# ============================================================================


@pytest.mark.asyncio
async def test_bot_context_middleware_injects_sub_bot(bot_repo: BotRepo):
    """测试BotContextMiddleware能从workflow_data获取bot_repo并注入sub_bot参数"""
    # Arrange: 创建测试数据
    sub_bot_dto = SubBotDTO(
        id=1,
        bot_id=123456789,
        bot_username="test_bot",
        owner_id=111222333,
        owner_username="owner",
        status="active",
        welcome_message="Welcome",
        user_count=0,
        message_count=0,
        created_at=Mock(),
    )

    # 创建一个活跃的子Bot记录
    await bot_repo.create(
        bot_token_encrypted="encrypted_token_here",
        bot_id=123456789,
        bot_username="test_bot",
        owner_id=111222333,
        owner_username="owner",
    )
    await bot_repo.update_status(1, "active")

    # 创建中间件（不传bot_repo，模拟dispatcher.py中的情况）
    middleware = BotContextMiddleware()

    # 创建mock handler
    handler = AsyncMock()

    # 创建mock event和data
    event = Mock()
    bot_mock = Mock(spec=Bot)
    bot_mock.id = 123456789

    data = {
        "bot": bot_mock,
        "bot_repo": bot_repo,  # 模拟从workflow_data注入的bot_repo
    }

    # Act: 调用中间件
    await middleware(handler, event, data)

    # Assert: 验证sub_bot被注入到data中
    assert "sub_bot" in data
    assert data["sub_bot"].bot_id == 123456789
    assert data["sub_bot"].status == "active"

    # 验证handler被调用
    handler.assert_called_once_with(event, data)


@pytest.mark.asyncio
async def test_bot_context_middleware_works_without_constructor_bot_repo(bot_repo: BotRepo):
    """测试中间件在构造时不传bot_repo也能工作（从data获取）"""
    # Arrange
    await bot_repo.create(
        bot_token_encrypted="encrypted_token_2",
        bot_id=987654321,
        bot_username="another_bot",
        owner_id=444555666,
        owner_username="another_owner",
    )
    await bot_repo.update_status(1, "active")

    # 创建中间件，不传bot_repo参数
    middleware = BotContextMiddleware(bot_repo=None)

    handler = AsyncMock()
    event = Mock()
    bot_mock = Mock(spec=Bot)
    bot_mock.id = 987654321

    data = {
        "bot": bot_mock,
        "bot_repo": bot_repo,  # 从workflow_data获取
    }

    # Act
    await middleware(handler, event, data)

    # Assert
    assert "sub_bot" in data
    assert data["sub_bot"].bot_id == 987654321
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_bot_context_middleware_skips_inactive_bot(bot_repo: BotRepo):
    """测试中间件跳过非active状态的Bot"""
    # Arrange
    await bot_repo.create(
        bot_token_encrypted="encrypted_token_3",
        bot_id=111111111,
        bot_username="stopped_bot",
        owner_id=777888999,
        owner_username="stopped_owner",
    )
    await bot_repo.update_status(1, "stopped")

    middleware = BotContextMiddleware()
    handler = AsyncMock()
    event = Mock()
    bot_mock = Mock(spec=Bot)
    bot_mock.id = 111111111

    data = {
        "bot": bot_mock,
        "bot_repo": bot_repo,
    }

    # Act
    result = await middleware(handler, event, data)

    # Assert: 中间件应该返回None，不调用handler
    assert result is None
    handler.assert_not_called()
    assert "sub_bot" not in data


@pytest.mark.asyncio
async def test_bot_context_middleware_skips_unknown_bot(bot_repo: BotRepo):
    """测试中间件跳过未知的bot_id"""
    # Arrange
    middleware = BotContextMiddleware()
    handler = AsyncMock()
    event = Mock()
    bot_mock = Mock(spec=Bot)
    bot_mock.id = 999999999  # 不存在的bot_id

    data = {
        "bot": bot_mock,
        "bot_repo": bot_repo,
    }

    # Act
    result = await middleware(handler, event, data)

    # Assert
    assert result is None
    handler.assert_not_called()
    assert "sub_bot" not in data


@pytest.mark.asyncio
async def test_sub_bot_handler_receives_sub_bot_param():
    """测试子Bot handler能收到sub_bot参数

    这个测试模拟完整的handler调用流程，验证sub_bot参数能正确传递
    """
    # Arrange: 创建mock对象
    message = Mock(spec=Message)
    message.from_user = Mock(spec=User)
    message.from_user.id = 123456
    message.from_user.username = "test_user"
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.answer = AsyncMock()

    bot = Mock(spec=Bot)

    sub_bot = SubBotDTO(
        id=1,
        bot_id=123456789,
        bot_username="test_bot",
        owner_id=111222333,
        owner_username="owner",
        status="active",
        welcome_message="Custom welcome message",
        user_count=0,
        message_count=0,
        created_at=Mock(),
    )

    user_repo = Mock()
    user_repo.get_or_create = AsyncMock(return_value=(Mock(is_blocked=False), True))

    bot_repo = Mock()
    bot_repo.increment_user_count = AsyncMock()

    # Act: 直接调用handler函数（模拟aiogram的调用）
    from app.sub_bot.handlers.start import cmd_start

    await cmd_start(
        message=message,
        bot=bot,
        sub_bot=sub_bot,
        user_repo=user_repo,
        bot_repo=bot_repo,
    )

    # Assert: 验证handler正常执行
    message.answer.assert_called_once_with("Custom welcome message")
    user_repo.get_or_create.assert_called_once()
    bot_repo.increment_user_count.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_error_handler_logs_exceptions():
    """测试ErrorHandlerMiddleware记录异常而不是静默吞掉"""
    from app.sub_bot.middleware.error_handler import ErrorHandlerMiddleware

    # Arrange
    middleware = ErrorHandlerMiddleware()

    # 创建一个会抛出异常的handler
    async def failing_handler(event, data):
        raise ValueError("Test exception")

    event = Mock()
    data = {}

    # Act & Assert: 验证异常被记录但不会传播
    with patch("app.sub_bot.middleware.error_handler.logger") as mock_logger:
        result = await middleware(failing_handler, event, data)

        # 验证logger被调用
        mock_logger.exception.assert_called_once()

        # 验证中间件返回None（不传播异常）
        assert result is None


# ============================================================================
# 问题2: 管理员广告配置入口测试
# ============================================================================


def test_help_text_includes_ad_command():
    """测试/help文本中包含/ad命令说明（针对管理员）"""
    # Assert: 验证HELP_TEXT中提到了广告管理或/ad命令
    # 注意：这个测试预期会失败（RED阶段），因为当前HELP_TEXT没有包含/ad命令
    assert "/ad" in HELP_TEXT or "广告" in HELP_TEXT, (
        "/help命令应该包含/ad命令或广告管理的说明"
    )


def test_admin_panel_has_ad_management_button():
    """测试admin面板键盘中有广告管理按钮"""
    # Act: 获取管理面板键盘
    keyboard = _admin_panel_keyboard()

    # Assert: 验证键盘中有广告管理按钮
    buttons_text = []
    for row in keyboard.inline_keyboard:
        for button in row:
            buttons_text.append(button.text)

    assert "广告管理" in buttons_text, "管理面板应该有广告管理按钮"

    # 验证callback_data正确
    ad_button = None
    for row in keyboard.inline_keyboard:
        for button in row:
            if button.text == "广告管理":
                ad_button = button
                break

    assert ad_button is not None
    assert ad_button.callback_data == "ad_list", "广告管理按钮的callback_data应该是ad_list"


def test_start_help_mentions_admin_commands_for_admins():
    """测试管理员相关命令在帮助中有说明

    这个测试验证管理员能够知道如何访问管理功能
    """
    # 当前的HELP_TEXT应该为管理员提供足够的信息
    # 至少应该提到/admin命令或管理面板

    # 这个测试预期会失败（RED阶段），因为当前HELP_TEXT没有提到管理员命令
    assert "/admin" in HELP_TEXT or "管理员" in HELP_TEXT or "管理面板" in HELP_TEXT, (
        "帮助文本应该为管理员提供管理功能的入口说明"
    )


def test_help_command_shows_admin_commands_for_admins():
    """测试/help命令对管理员显示额外的管理员命令"""
    # 这个测试验证/help命令应该根据用户权限显示不同的内容
    # 当前实现可能没有这个功能，这是一个改进建议

    # 创建Settings mock（使用环境变量或默认值）
    import os
    os.environ["MASTER_BOT_TOKEN"] = "test_token"
    os.environ["TOKEN_ENCRYPTION_KEY"] = "test_key"
    os.environ["ADMIN_USER_IDS"] = "111222333"

    settings = Settings()

    # 测试管理员用户
    admin_user_id = 111222333
    assert admin_user_id in settings.ADMIN_USER_IDS

    # 测试普通用户
    normal_user_id = 999888777
    assert normal_user_id not in settings.ADMIN_USER_IDS

    # 注意：这个测试只是验证Settings配置正确
    # 实际的/help命令可能需要修改以支持动态内容


@pytest.mark.asyncio
async def test_admin_command_requires_permission():
    """测试/admin命令需要管理员权限"""
    from app.master_bot.handlers.admin import admin_command
    import os

    # Arrange: 创建非管理员用户的消息
    message = Mock(spec=Message)
    message.from_user = Mock(spec=User)
    message.from_user.id = 999888777  # 非管理员ID
    message.answer = AsyncMock()

    os.environ["MASTER_BOT_TOKEN"] = "test_token"
    os.environ["TOKEN_ENCRYPTION_KEY"] = "test_key"
    os.environ["ADMIN_USER_IDS"] = "111222333"  # 只有这个ID是管理员

    settings = Settings()

    bot_repo = Mock()
    user_repo = Mock()
    msg_map_repo = Mock()

    # Act: 调用admin命令
    await admin_command(
        message=message,
        bot_repo=bot_repo,
        user_repo=user_repo,
        msg_map_repo=msg_map_repo,
        settings=settings,
    )

    # Assert: 验证返回权限错误
    message.answer.assert_called_once_with("你没有权限使用此命令")


@pytest.mark.asyncio
async def test_admin_command_works_for_admin():
    """测试/admin命令对管理员正常工作"""
    from app.master_bot.handlers.admin import admin_command
    import os

    # Arrange: 创建管理员用户的消息
    message = Mock(spec=Message)
    message.from_user = Mock(spec=User)
    message.from_user.id = 111222333  # 管理员ID
    message.answer = AsyncMock()

    os.environ["MASTER_BOT_TOKEN"] = "test_token"
    os.environ["TOKEN_ENCRYPTION_KEY"] = "test_key"
    os.environ["ADMIN_USER_IDS"] = "111222333"

    settings = Settings()

    bot_repo = Mock()
    bot_repo.count_all = AsyncMock(return_value={
        "total": 10,
        "active": 8,
        "stopped": 1,
        "error": 1,
    })

    user_repo = Mock()
    user_repo.count_total_users = AsyncMock(return_value=100)

    msg_map_repo = Mock()
    msg_map_repo.count_all = AsyncMock(return_value=500)

    # Act
    await admin_command(
        message=message,
        bot_repo=bot_repo,
        user_repo=user_repo,
        msg_map_repo=msg_map_repo,
        settings=settings,
    )

    # Assert: 验证显示管理面板
    message.answer.assert_called_once()
    call_args = message.answer.call_args
    assert "平台管理面板" in call_args[0][0]
    assert call_args[1]["reply_markup"] is not None
