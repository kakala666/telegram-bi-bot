"""Phase 2: 错误处理升级测试 (TDD RED 阶段)。

验证 ErrorHandlerMiddleware 的升级：
1. 不吞掉 SkipHandler 信号（aiogram 内部用于跳过 handler 的异常）
2. 错误日志包含追踪字段（bot_id、sub_bot_id、from_user_id）
3. sub_dp.errors() 返回 False（不静默吞异常）

这些测试在当前代码上必须 FAIL。
"""

from __future__ import annotations

import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.dto import SubBotDTO
from app.sub_bot.middleware.error_handler import ErrorHandlerMiddleware


def _make_sub_bot_dto(owner_id: int = 999) -> SubBotDTO:
    return SubBotDTO(
        id=1,
        bot_id=100,
        bot_username="test_bot",
        owner_id=owner_id,
        owner_username="owner",
        status="active",
        welcome_message=None,
        user_count=0,
        message_count=0,
        created_at=datetime.utcnow(),
    )


class TestErrorHandlerSkipHandler:
    """验证 ErrorHandlerMiddleware 不吞掉 SkipHandler 信号。

    aiogram 使用 SkipHandler 异常在中间件/handler 链中跳过当前 handler，
    让事件继续传播到下一个 handler。如果 ErrorHandlerMiddleware
    捕获了所有 Exception（包括 SkipHandler），就会阻止事件传播。

    当前 ErrorHandlerMiddleware 使用 `except Exception:` 捕获所有异常，
    SkipHandler 继承自 Exception，因此会被错误地吞掉。
    """

    @pytest.mark.asyncio
    async def test_error_handler_does_not_swallow_skip_handler(self):
        """ErrorHandlerMiddleware 不应吞掉 SkipHandler 信号。

        当前状态（error_handler.py）：
            try:
                return await handler(event, data)
            except Exception:  # 捕获所有异常，包括 SkipHandler
                logger.exception(...)
                return None

        期望状态：
            try:
                return await handler(event, data)
            except SkipHandler:
                raise  # 放行 SkipHandler
            except Exception:
                logger.exception(...)
                return None
        """
        from aiogram.dispatcher.event.bases import SkipHandler

        mw = ErrorHandlerMiddleware()
        event = MagicMock()
        handler = AsyncMock(side_effect=SkipHandler("skip this handler"))

        with pytest.raises(SkipHandler):
            await mw(handler, event, {})


class TestErrorHandlerLogging:
    """验证 ErrorHandlerMiddleware 错误日志包含追踪字段。

    当前状态：日志仅包含 "子Bot handler 未捕获异常"，
    没有 bot_id、sub_bot_id、from_user_id 等上下文信息，
    难以定位问题来源。

    期望状态：日志包含 bot_id、sub_bot_id、from_user_id 等追踪字段。
    """

    @pytest.mark.asyncio
    async def test_error_handler_logs_with_request_context(self, caplog):
        """错误日志应包含追踪字段（bot_id、sub_bot_id、from_user_id）。

        当异常发生时，日志应包含足够的上下文信息来追踪问题来源。
        """
        mw = ErrorHandlerMiddleware()

        sub_bot = _make_sub_bot_dto(owner_id=999)
        mock_bot = MagicMock()
        mock_bot.id = 100

        event = MagicMock()
        event.from_user = MagicMock()
        event.from_user.id = 555

        handler = AsyncMock(side_effect=ValueError("test error"))

        data = {
            "bot": mock_bot,
            "sub_bot": sub_bot,
        }

        with caplog.at_level(logging.ERROR):
            await mw(handler, event, data)

        log_text = caplog.text

        # 验证日志包含追踪字段
        assert "bot_id" in log_text or "100" in log_text, (
            f"错误日志应包含 bot_id 信息，当前日志: {log_text}"
        )
        assert "sub_bot_id" in log_text or str(sub_bot.id) in log_text, (
            f"错误日志应包含 sub_bot_id 信息，当前日志: {log_text}"
        )
        assert "from_user_id" in log_text or "555" in log_text, (
            f"错误日志应包含 from_user_id 信息，当前日志: {log_text}"
        )


class TestSubDpErrorHandler:
    """验证 sub_dp.errors() 返回 False。

    当 on_sub_dp_error 返回 True 时，aiogram 认为异常已处理，
    不再传播。返回 False 让上层感知异常。
    """

    @pytest.mark.asyncio
    async def test_sub_dp_error_handler_returns_false(self):
        """sub_dp.errors() handler 应返回 False。

        验证实际调用返回值为 False（不仅检查源码，还要验证运行时行为）。
        """
        from unittest.mock import MagicMock

        from aiogram.types import ErrorEvent

        from app.sub_bot.dispatcher import on_sub_dp_error

        # 构造 ErrorEvent mock
        error_event = MagicMock(spec=ErrorEvent)
        error_event.exception = ValueError("test error")

        result = await on_sub_dp_error(error_event)

        assert result is False, (
            f"on_sub_dp_error 应返回 False，当前返回 {result!r}。"
            "返回 True 会静默吞掉所有异常。"
        )
