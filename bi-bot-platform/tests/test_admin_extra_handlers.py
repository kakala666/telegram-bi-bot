"""测试管理员额外 Handler 和管理面板广播入口。

缺失的回调 Handler:
5. adm_force_delete - 管理员强制删除Bot
6. adm_bot_users - 管理员查看Bot用户列表
7. bot_broadcast - 管理面板广播入口
"""

from __future__ import annotations

import inspect

import pytest


class TestAdmForceDeleteHandler:
    """验证 adm_force_delete 回调 Handler 存在且功能正确。

    在管理员Bot详情页点击"强制删除"按钮时，
    callback_data 为 adm_force_delete:{bot_id}。
    键盘已定义此按钮（admin.py _bot_detail_keyboard），
    但 admin.py 中缺少对应 handler。
    """

    def test_adm_force_delete_handler_registered(self):
        """admin.py router 应注册处理 adm_force_delete: 前缀的回调。"""
        from app.master_bot.handlers import admin as admin_module

        handler_names = [
            name for name, _ in inspect.getmembers(
                admin_module, inspect.iscoroutinefunction
            )
        ]

        has_force_delete = any(
            "force_delete" in name
            for name in handler_names
        )

        assert has_force_delete, (
            "admin.py 中缺少处理 'adm_force_delete:{bot_id}' 回调的 handler。"
            "键盘 _bot_detail_keyboard 已定义'强制删除'按钮，但无对应处理函数。"
            f"当前 handler 函数: {handler_names}"
        )

    def test_adm_force_delete_cleans_up_related_data(self):
        """强制删除应清理关联数据（用户、消息映射、广播记录）。

        根据设计文档，删除Bot时需要：
        1. 调用 registry.remove_bot 停止Bot
        2. 删除 message_maps 中该Bot的记录
        3. 删除 bot_users 中该Bot的记录
        4. 删除 broadcast_tasks 中该Bot的记录
        5. 删除 sub_bots 记录
        """
        from app.master_bot.handlers import admin as admin_module

        # 查找 force_delete handler
        force_delete_func = None
        for name, func in inspect.getmembers(
            admin_module, inspect.iscoroutinefunction
        ):
            if "force_delete" in name:
                force_delete_func = func
                break

        assert force_delete_func is not None, (
            "未找到 force_delete handler 函数"
        )

        # 检查函数签名是否包含必要的 repo 依赖
        sig = inspect.signature(force_delete_func)
        param_names = list(sig.parameters.keys())

        # 强制删除需要这些 repo 来清理关联数据
        required_deps = ["user_repo", "msg_map_repo", "broadcast_repo", "bot_repo"]
        for dep in required_deps:
            assert dep in param_names, (
                f"adm_force_delete handler 缺少依赖参数 '{dep}'。"
                f"强制删除需要清理关联数据。当前参数: {param_names}"
            )


class TestAdmBotUsersHandler:
    """验证 adm_bot_users 回调 Handler 存在。

    在管理员Bot详情页点击"查看用户"按钮时，
    callback_data 为 adm_bot_users:{bot_id}。
    键盘已定义此按钮（admin.py _bot_detail_keyboard），
    但 admin.py 中缺少对应 handler。
    """

    def test_adm_bot_users_handler_registered(self):
        """admin.py router 应注册处理 adm_bot_users: 前缀的回调。"""
        from app.master_bot.handlers import admin as admin_module

        handler_names = [
            name for name, _ in inspect.getmembers(
                admin_module, inspect.iscoroutinefunction
            )
        ]

        has_bot_users = any(
            "bot_users" in name
            for name in handler_names
        )

        assert has_bot_users, (
            "admin.py 中缺少处理 'adm_bot_users:{bot_id}' 回调的 handler。"
            "键盘 _bot_detail_keyboard 已定义'查看用户'按钮，但无对应处理函数。"
            f"当前 handler 函数: {handler_names}"
        )

    def test_adm_bot_users_handler_has_user_repo_dependency(self):
        """adm_bot_users handler 应依赖 user_repo 来查询用户列表。"""
        from app.master_bot.handlers import admin as admin_module

        bot_users_func = None
        for name, func in inspect.getmembers(
            admin_module, inspect.iscoroutinefunction
        ):
            if "bot_users" in name:
                bot_users_func = func
                break

        assert bot_users_func is not None, "未找到 bot_users handler"

        sig = inspect.signature(bot_users_func)
        param_names = list(sig.parameters.keys())

        assert "user_repo" in param_names, (
            f"adm_bot_users handler 缺少 user_repo 依赖。"
            f"当前参数: {param_names}"
        )


class TestBotBroadcastHandler:
    """验证 bot_broadcast 回调 Handler 存在。

    在Bot管理面板点击"广播消息"按钮时，
    callback_data 为 bot_broadcast:{bot_id}。
    键盘已定义此按钮（inline.py bot_manage_keyboard），
    但没有对应的 handler 处理此回调。

    应在 broadcast.py 或 manage.py 中注册处理此回调，
    进入广播 FSM 流程。
    """

    def test_bot_broadcast_handler_registered_in_any_module(self):
        """某个 handler 模块应注册处理 bot_broadcast: 前缀的回调。"""
        from app.master_bot.handlers import broadcast as broadcast_module
        from app.master_bot.handlers import manage as manage_module

        all_handler_names = []

        for module in [broadcast_module, manage_module]:
            for name, _ in inspect.getmembers(module, inspect.iscoroutinefunction):
                all_handler_names.append(f"{module.__name__}.{name}")

        has_bot_broadcast = any(
            "bot_broadcast" in name
            for name in all_handler_names
        )

        assert has_bot_broadcast, (
            "缺少处理 'bot_broadcast:{bot_id}' 回调的 handler。"
            "键盘 bot_manage_keyboard 已定义'广播消息'按钮，但无对应处理函数。"
            "应在 broadcast.py 或 manage.py 中注册。"
            f"已检查的 handler: {all_handler_names}"
        )

    def test_bot_broadcast_keyboard_button_exists(self):
        """bot_manage_keyboard 应包含广播消息按钮。"""
        from app.master_bot.keyboards.inline import bot_manage_keyboard

        kb = bot_manage_keyboard(bot_id=1, status="active")
        all_callbacks = []
        for row in kb.inline_keyboard:
            for btn in row:
                all_callbacks.append(btn.callback_data)

        has_broadcast_button = any(
            cb and cb.startswith("bot_broadcast:")
            for cb in all_callbacks
        )

        assert has_broadcast_button, (
            "bot_manage_keyboard 应包含 bot_broadcast:{bot_id} 回调的按钮。"
            f"当前回调: {all_callbacks}"
        )

    def test_bot_broadcast_enters_broadcast_fsm(self):
        """bot_broadcast handler 应设置 FSM 状态进入广播流程。

        点击管理面板的"广播消息"按钮后，应：
        1. 将 bot_id 保存到 FSM state data
        2. 进入 BroadcastStates.waiting_content 状态
        """
        from app.master_bot.handlers import broadcast as broadcast_module
        from app.master_bot.handlers import manage as manage_module

        bot_broadcast_func = None
        for module in [broadcast_module, manage_module]:
            for name, func in inspect.getmembers(module, inspect.iscoroutinefunction):
                if "bot_broadcast" in name:
                    bot_broadcast_func = func
                    break
            if bot_broadcast_func:
                break

        assert bot_broadcast_func is not None, (
            "未找到 bot_broadcast handler 函数"
        )

        # 检查函数签名包含 state 参数（用于 FSM）
        sig = inspect.signature(bot_broadcast_func)
        param_names = list(sig.parameters.keys())

        assert "state" in param_names, (
            f"bot_broadcast handler 缺少 state 参数（FSMContext），"
            f"无法进入广播 FSM 流程。当前参数: {param_names}"
        )
