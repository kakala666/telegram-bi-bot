"""中间件顺序测试 (TDD RED 阶段)。

验证中间件注册顺序和覆盖范围：
1. ErrorHandlerMiddleware 应在 BotContextMiddleware 外层（先注册）
2. callback_query 也应注册 ErrorHandlerMiddleware
3. sub_dp.errors() 不应返回 True 静默吞异常

当前 Bug：
- ErrorHandlerMiddleware 在 BotContextMiddleware 之后注册（内层），
  当 BotContextMiddleware 抛异常时无法被 ErrorHandlerMiddleware 捕获
- callback_query 没有注册 ErrorHandlerMiddleware
- sub_dp.errors() 返回 True 会阻止异常传播
"""

from __future__ import annotations

import inspect

import pytest

from app.sub_bot.middleware.bot_context import BotContextMiddleware
from app.sub_bot.middleware.error_handler import ErrorHandlerMiddleware


class TestMiddlewareOrder:
    """验证中间件注册顺序。

    aiogram 中间件执行顺序：先注册的在外层（洋葱模型）。
    ErrorHandlerMiddleware 应先注册，才能捕获 BotContextMiddleware 的异常。
    """

    def test_error_handler_registered_before_bot_context_for_message(self):
        """message 中间件中 ErrorHandlerMiddleware 应在 BotContextMiddleware 之前注册。

        aiogram 中间件按注册顺序构成洋葱模型：
        先注册的在外层。ErrorHandlerMiddleware 应在外层才能捕获内层异常。

        修复后应为：
            sub_router.message.outer_middleware(_error_handler_mw) # 先注册 = 外层
            sub_router.message.outer_middleware(_bot_context_mw)   # 后注册 = 内层
        """
        from app.sub_bot.dispatcher import sub_router

        middlewares = list(sub_router.message.outer_middleware)
        mw_types = [type(mw) for mw in middlewares]

        assert ErrorHandlerMiddleware in mw_types, (
            "ErrorHandlerMiddleware 未注册到 message 中间件链"
        )
        assert BotContextMiddleware in mw_types, (
            "BotContextMiddleware 未注册到 message 中间件链"
        )

        error_idx = mw_types.index(ErrorHandlerMiddleware)
        context_idx = mw_types.index(BotContextMiddleware)

        assert error_idx < context_idx, (
            f"ErrorHandlerMiddleware (index={error_idx}) 应在 "
            f"BotContextMiddleware (index={context_idx}) 之前注册（外层），"
            "当前顺序错误：ErrorHandlerMiddleware 在内层，无法捕获 BotContextMiddleware 异常。"
        )

    def test_callback_query_has_error_handler(self):
        """callback_query 也应注册 ErrorHandlerMiddleware。

        当前状态（dispatcher.py）：
            sub_router.callback_query.middleware(_bot_context_mw)  # 只注册了 BotContext
            # ErrorHandlerMiddleware 未注册到 callback_query  ← 缺失

        callback_query handler 抛异常时会直接崩溃。
        """
        from app.sub_bot.dispatcher import sub_router

        callback_mw_types = [type(mw) for mw in sub_router.callback_query.outer_middleware]

        assert ErrorHandlerMiddleware in callback_mw_types, (
            "ErrorHandlerMiddleware 未注册到 callback_query 中间件链。"
            f"当前 callback_query 中间件: {[t.__name__ for t in callback_mw_types]}。"
            "callback_query handler 抛异常时无法被捕获。"
        )

    def test_callback_query_error_handler_before_bot_context(self):
        """callback_query 中间件中 ErrorHandlerMiddleware 也应在外层。"""
        from app.sub_bot.dispatcher import sub_router

        callback_mw_types = [type(mw) for mw in sub_router.callback_query.outer_middleware]

        if ErrorHandlerMiddleware not in callback_mw_types:
            pytest.skip("ErrorHandlerMiddleware 未注册到 callback_query，前置测试会 fail")

        if BotContextMiddleware not in callback_mw_types:
            pytest.skip("BotContextMiddleware 未注册到 callback_query")

        error_idx = callback_mw_types.index(ErrorHandlerMiddleware)
        context_idx = callback_mw_types.index(BotContextMiddleware)

        assert error_idx < context_idx, (
            "callback_query 中 ErrorHandlerMiddleware 应在 BotContextMiddleware 之前注册"
        )


class TestErrorHandlerCatchesBotContextException:
    """验证 ErrorHandlerMiddleware 能捕获 BotContextMiddleware 抛出的异常。

    这是一个中间件集成测试：模拟 BotContextMiddleware 抛异常，
    验证 ErrorHandlerMiddleware 能捕获并处理，而不是让异常传播到顶层。
    """

    @pytest.mark.asyncio
    async def test_error_handler_catches_inner_middleware_exception(self):
        """ErrorHandlerMiddleware 应能捕获内层中间件（如 BotContextMiddleware）的异常。"""
        from unittest.mock import AsyncMock, MagicMock

        error_mw = ErrorHandlerMiddleware()
        event = MagicMock()

        # 模拟内层 handler（包含 BotContextMiddleware）抛异常
        inner_handler = AsyncMock(side_effect=Exception("BotContext DB error"))

        # ErrorHandlerMiddleware 应捕获异常并返回 None，而不是让异常传播
        result = await error_mw(inner_handler, event, {})

        assert result is None, (
            "ErrorHandlerMiddleware 应捕获异常并返回 None"
        )
        inner_handler.assert_called_once()


class TestSubDpErrorHandler:
    """验证 sub_dp.errors() 不应静默吞掉所有异常。

    当前状态：on_sub_dp_error 返回 True，这会告诉 aiogram
    "异常已处理"，阻止异常进一步传播。在某些情况下这可能
    导致异常被完全忽略，没有任何用户可见的反馈。
    """

    def test_sub_dp_error_handler_does_not_return_true(self):
        """sub_dp.errors() handler 不应返回 True（静默吞异常）。

        返回 True 表示异常已处理，aiogram 不再传播。
        这会导致所有异常被静默忽略。

        更合理的做法是返回 None 或 False，让异常能被上层感知。
        或者在 return True 之前做更细粒度的处理（如通知 owner）。
        """
        source = inspect.getsource(_get_error_handler_func())

        # 检查函数是否直接 return True
        lines = [line.strip() for line in source.split("\n")]
        has_unconditional_return_true = any(
            line == "return True" for line in lines
        )

        assert not has_unconditional_return_true, (
            "on_sub_dp_error 不应无条件 return True。"
            "这会静默吞掉所有异常。应返回 None/False 或做更细粒度处理。"
        )


def _get_error_handler_func():
    """获取 sub_dp.errors() 注册的 handler 函数。"""
    from app.sub_bot.dispatcher import on_sub_dp_error

    return on_sub_dp_error
