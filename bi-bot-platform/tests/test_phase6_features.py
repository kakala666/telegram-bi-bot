"""测试 Phase 6 缺失功能。

缺失功能:
1. logging_config.py - 结构化日志配置
2. CleanupService.start_periodic() - 定期清理
3. 默认广告首次创建 - launcher 启动时检查
4. sub_dp 全局错误处理中间件
5. 回调去重 - start.py 和 callbacks.py 重复注册 nav_home/nav_help
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest


# ── 1. logging_config.py 结构化日志配置 ──────────────────────────


class TestLoggingConfig:
    """验证 logging_config.py 模块存在且提供结构化日志配置。

    Phase 6 任务 6.7: 实现结构化日志。
    应提供 setup_logging() 函数，配置日志格式、级别、文件输出等。
    """

    def test_logging_config_module_exists(self):
        """app.logging_config 模块应存在。"""
        try:
            mod = importlib.import_module("app.logging_config")
            assert mod is not None
        except ImportError:
            pytest.fail(
                "app.logging_config 模块不存在。"
                "Phase 6 任务 6.7 要求实现结构化日志配置。"
            )

    def test_logging_config_has_setup_function(self):
        """logging_config 应提供 setup_logging 函数。"""
        try:
            mod = importlib.import_module("app.logging_config")
        except ImportError:
            pytest.fail("app.logging_config 模块不存在")

        assert hasattr(mod, "setup_logging"), (
            "app.logging_config 缺少 setup_logging 函数。"
            "应提供一个函数来配置日志格式、级别和输出。"
        )

    def test_setup_logging_accepts_settings(self):
        """setup_logging 应接受 Settings 或 log_level/log_file 参数。"""
        try:
            mod = importlib.import_module("app.logging_config")
        except ImportError:
            pytest.fail("app.logging_config 模块不存在")

        if not hasattr(mod, "setup_logging"):
            pytest.fail("缺少 setup_logging 函数")

        sig = inspect.signature(mod.setup_logging)
        param_names = list(sig.parameters.keys())

        # 应接受配置参数（Settings 对象或单独的 level/file 参数）
        accepts_config = (
            "settings" in param_names
            or "log_level" in param_names
            or "level" in param_names
            or len(param_names) > 0
        )

        assert accepts_config, (
            "setup_logging 应接受配置参数（如 settings, log_level, log_file）。"
            f"当前参数: {param_names}"
        )

    def test_launcher_calls_setup_logging(self):
        """launcher.py 应在启动时调用 setup_logging。"""
        from app import launcher

        source = inspect.getsource(launcher)

        has_logging_setup = (
            "setup_logging" in source
            or "logging_config" in source
        )

        assert has_logging_setup, (
            "launcher.py 未调用 setup_logging 或导入 logging_config。"
            "应在启动时配置结构化日志。"
        )


class TestCleanupServiceStartPeriodic:
    """验证 CleanupService.start_periodic() 方法存在且功能正确。

    Phase 6 任务 6.6: 实现消息映射定期清理。
    CleanupService 已有 cleanup_all()，但缺少 start_periodic() 方法。
    start_periodic() 应启动一个后台 asyncio.Task，定期调用 cleanup_all()。
    """

    def test_start_periodic_method_exists(self):
        """CleanupService 应有 start_periodic 方法。"""
        from app.services.cleanup import CleanupService

        assert hasattr(CleanupService, "start_periodic"), (
            "CleanupService 缺少 start_periodic 方法。"
            "应实现定期清理功能，作为 asyncio.Task 后台运行。"
        )

    def test_start_periodic_is_async(self):
        """start_periodic 应是异步方法。"""
        from app.services.cleanup import CleanupService

        if not hasattr(CleanupService, "start_periodic"):
            pytest.fail("CleanupService 缺少 start_periodic 方法")

        assert asyncio.iscoroutinefunction(CleanupService.start_periodic), (
            "start_periodic 应是 async 方法"
        )

    def test_start_periodic_accepts_interval(self):
        """start_periodic 应接受 interval_hours 参数。"""
        from app.services.cleanup import CleanupService

        if not hasattr(CleanupService, "start_periodic"):
            pytest.fail("CleanupService 缺少 start_periodic 方法")

        sig = inspect.signature(CleanupService.start_periodic)
        param_names = list(sig.parameters.keys())

        has_interval = any(
            "interval" in p
            for p in param_names
        )

        assert has_interval, (
            "start_periodic 应接受 interval_hours 参数来控制清理间隔。"
            f"当前参数: {param_names}"
        )

    def test_launcher_starts_periodic_cleanup(self):
        """launcher.py 应在启动时调用 cleanup_svc.start_periodic()。"""
        from app import launcher

        source = inspect.getsource(launcher)

        has_periodic_cleanup = (
            "start_periodic" in source
            or "cleanup_svc.start" in source
        )

        assert has_periodic_cleanup, (
            "launcher.py 未调用 cleanup_svc.start_periodic()。"
            "应在启动时启动定期清理任务。"
        )


# ── 3. 默认广告首次创建 ─────────────────────────────────────────


class TestDefaultAdCreation:
    """验证 launcher 启动时检查并创建默认广告。

    Phase 4 任务 4.8: 创建默认广告（首次启动时）。
    launcher.py 应在启动时检查是否存在广告，
    如果没有则创建一条默认广告。
    """

    def test_launcher_creates_default_ad_on_first_start(self):
        """launcher.py 应包含默认广告创建逻辑。"""
        from app import launcher

        source = inspect.getsource(launcher)

        has_default_ad_logic = (
            "default_ad" in source.lower()
            or "DEFAULT_AD" in source
            or ("ad_repo" in source and "create" in source)
            or "get_all" in source
        )

        assert has_default_ad_logic, (
            "launcher.py 未包含默认广告创建逻辑。"
            "Phase 4 任务 4.8 要求首次启动时创建默认广告。"
            "应检查 ad_repo.get_all() 是否为空，为空则创建默认广告。"
        )

    def test_settings_has_default_ad_config(self):
        """Settings 应包含默认广告配置。"""
        from app.config import Settings

        fields = Settings.model_fields

        has_default_ad_text = "DEFAULT_AD_TEXT" in fields
        has_default_ad_url = "DEFAULT_AD_URL" in fields

        assert has_default_ad_text, (
            "Settings 缺少 DEFAULT_AD_TEXT 配置项"
        )
        assert has_default_ad_url, (
            "Settings 缺少 DEFAULT_AD_URL 配置项"
        )


# ── 4. sub_dp 全局错误处理中间件 ─────────────────────────────────
class TestSubDpErrorHandlingMiddleware:
    """验证 sub_dp 注册了全局错误处理中间件。

    Phase 6 任务 6.9: 实现全局错误处理。
    子Bot的 Dispatcher 应注册错误处理中间件或 error handler，
    确保未捕获异常不会导致整个系统崩溃。
    """

    def test_sub_dp_has_error_handler_or_middleware(self):
        """sub_dp 应注册错误处理机制。

        可以是：
        1. sub_dp.errors 注册了 error handler
        2. sub_dp 或 sub_router 注册了错误处理中间件
        """
        from app.sub_bot.dispatcher import sub_dp, sub_router

        # 检查 error handlers
        has_error_handlers = len(sub_dp.errors.handlers) > 0

        # 检查中间件中是否有错误处理相关的
        middleware_types = []
        for mw in sub_dp.message.middleware:
            middleware_types.append(type(mw).__name__)
        for mw in sub_router.message.middleware:
            middleware_types.append(type(mw).__name__)

        has_error_middleware = any(
            "error" in name.lower()
            for name in middleware_types
        )

        assert has_error_handlers or has_error_middleware, (
            "sub_dp 未注册全局错误处理机制。"
            "Phase 6 任务 6.9 要求实现全局错误处理，"
            "确保未捕获异常不会导致整个系统崩溃。"
            f"当前 error handlers 数量: {len(sub_dp.errors.handlers)}, "
            f"中间件: {middleware_types}"
        )

    def test_sub_dp_error_handler_catches_exceptions(self):
        """sub_dp 的错误处理应能捕获一般异常。"""
        from app.sub_bot.dispatcher import sub_dp

        # 检查是否注册了 error handler
        if len(sub_dp.errors.handlers) == 0:
            pytest.fail(
                "sub_dp 未注册 error handler。"
                "应使用 @sub_dp.errors() 或 sub_router.errors() 注册。"
            )


# ── 5. 回调去重 ─────────────────────────────────────────────────


class TestCallbackDeduplication:
    """验证 start.py 和 callbacks.py 不重复注册 nav_home/nav_help 回调。

    Bug: start.py 和 callbacks.py 都注册了 nav_home 和 nav_help 回调，
    导致同一个回调被处理两次。应只在一个地方注册。
    """

    def test_nav_home_registered_only_once(self):
        """nav_home 回调应只在一个模块中注册。"""
        from app.master_bot.handlers import callbacks as cb_module
        from app.master_bot.handlers import start as start_module

        # 检查 start.py 中是否有 nav_home handler
        start_has_nav_home = False
        start_source = inspect.getsource(start_module)
        if 'nav_home' in start_source and 'callback_query' in start_source:
            # 更精确：检查是否有注册 nav_home 的回调装饰器
            start_has_nav_home = (
                '"nav_home"' in start_source
                and "@" in start_source
                and "callback_query" in start_source
            )

        # 检查 callbacks.py 中是否有 nav_home handler
        cb_has_nav_home = False
        cb_source = inspect.getsource(cb_module)
        if 'nav_home' in cb_source and 'callback_query' in cb_source:
            cb_has_nav_home = (
                '"nav_home"' in cb_source
                and "@" in cb_source
                and "callback_query" in cb_source
            )

        # 两个模块不应同时注册 nav_home
        assert not (start_has_nav_home and cb_has_nav_home), (
            "nav_home 回调在 start.py 和 callbacks.py 中重复注册。"
            "应只在一个模块中注册，建议保留 callbacks.py 中的版本。"
        )

    def test_nav_help_registered_only_once(self):
        """nav_help 回调应只在一个模块中注册。"""
        from app.master_bot.handlers import callbacks as cb_module
        from app.master_bot.handlers import start as start_module

        start_source = inspect.getsource(start_module)
        cb_source = inspect.getsource(cb_module)

        start_has_nav_help = (
            '"nav_help"' in start_source
            and "callback_query" in start_source
            and "@" in start_source
        )

        cb_has_nav_help = (
            '"nav_help"' in cb_source
            and "callback_query" in cb_source
            and "@" in cb_source
        )

        assert not (start_has_nav_help and cb_has_nav_help), (
            "nav_help 回调在 start.py 和 callbacks.py 中重复注册。"
            "应只在一个模块中注册，建议保留 callbacks.py 中的版本。"
        )

    def test_no_duplicate_callback_data_across_routers(self):
        """master_dp 中不应有重复的 callback_data 处理。

        检查 start.py 和 callbacks.py 的 router 是否有重叠的回调。
        """
        from app.master_bot.handlers.callbacks import router as cb_router
        from app.master_bot.handlers.start import router as start_router

        # 收集两个 router 中注册的回调 handler 数量
        start_cb_count = len(start_router.callback_query.handlers)
        cb_cb_count = len(cb_router.callback_query.handlers)

        # start.py 不应注册任何 callback_query handler
        # 所有通用导航回调应在 callbacks.py 中处理
        if start_cb_count > 0 and cb_cb_count > 0:
            # 如果两个 router 都有回调 handler，检查是否有重叠
            # start.py 的回调 handler 应该为 0（所有导航回调在 callbacks.py）
            assert start_cb_count == 0, (
                f"start.py router 注册了 {start_cb_count} 个 callback_query handler。"
                "通用导航回调（nav_home, nav_help）应只在 callbacks.py 中注册，"
                "避免重复处理。"
            )
