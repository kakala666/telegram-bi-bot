"""测试广告编辑相关的缺失 Handler。

缺失的回调 Handler:
1. ad_edit_text - 编辑广告内容
2. ad_edit_priority - 编辑广告优先级
3. 添加广告优先级设置步骤（当前硬编码 priority=0）
4. 添加广告确认页"重新编辑"按钮
"""

from __future__ import annotations

import inspect

import pytest

from app.master_bot.states import AdStates


class TestAdEditTextHandler:
    """验证 ad_edit_text 回调 Handler 存在且功能正确。

    在广告详情页点击"修改内容"按钮时，callback_data 为 ad_edit_text:{ad_id}。
    键盘已定义此按钮（inline.py ad_detail_keyboard），但 ad.py 中缺少对应 handler。
    """

    def test_ad_edit_text_handler_registered(self):
        """ad.py router 应注册处理 ad_edit_text: 前缀的回调。"""
        from app.master_bot.handlers.ad import router

        callback_handlers = []
        for observer in router.callback_query.handlers:
            callback_handlers.append(observer)

        # 检查是否有处理 ad_edit_text 的 handler
        found = False
        for handler in callback_handlers:
            # 尝试用模拟的 callback_data 检查 filter
            try:
                callback_data = "ad_edit_text:1"
                # handler 的 filter 通常是 lambda
                if hasattr(handler, "filters"):
                    for f in handler.filters:
                        if hasattr(f, "callback"):
                            mock_cb = type("CB", (), {"data": callback_data})()
                            try:
                                if f.callback(mock_cb):
                                    found = True
                            except Exception:
                                pass
            except Exception:
                pass

        # 更直接的方式：检查模块中是否有处理 ad_edit_text 的函数
        from app.master_bot.handlers import ad as ad_module

        handler_names = [
            name for name, _ in inspect.getmembers(ad_module, inspect.iscoroutinefunction)
        ]
        has_edit_text_handler = any(
            "edit_text" in name or "ad_edit_text" in name
            for name in handler_names
        )

        assert found or has_edit_text_handler, (
            "ad.py 中缺少处理 'ad_edit_text:{ad_id}' 回调的 handler。"
            "键盘 ad_detail_keyboard 已定义此按钮，但无对应处理函数。"
            f"当前 handler 函数: {handler_names}"
        )

    def test_ad_edit_text_enters_fsm_state(self):
        """点击修改内容后应进入 FSM 等待新广告文本的状态。"""
        # AdStates 应包含编辑广告文本的状态
        states = [s for s in dir(AdStates) if not s.startswith("_")]

        has_edit_state = any(
            "edit" in s.lower() and "text" in s.lower()
            for s in states
        )

        # 也可以复用 waiting_ad_text 状态
        has_waiting_text = "waiting_ad_text" in states

        assert has_edit_state or has_waiting_text, (
            "AdStates 应包含编辑广告文本的 FSM 状态，"
            "或复用 waiting_ad_text 状态。"
            f"当前状态: {states}"
        )


class TestAdEditPriorityHandler:
    """验证 ad_edit_priority 回调 Handler 存在且功能正确。

    在广告详情页点击"修改优先级"按钮时，callback_data 为 ad_edit_priority:{ad_id}。
    键盘已定义此按钮（inline.py ad_detail_keyboard），但 ad.py 中缺少对应 handler。
    """

    def test_ad_edit_priority_handler_registered(self):
        """ad.py router 应注册处理 ad_edit_priority: 前缀的回调。"""
        from app.master_bot.handlers import ad as ad_module

        handler_names = [
            name for name, _ in inspect.getmembers(ad_module, inspect.iscoroutinefunction)
        ]
        has_edit_priority_handler = any(
            "edit_priority" in name or "priority" in name
            for name in handler_names
        )

        assert has_edit_priority_handler, (
            "ad.py 中缺少处理 'ad_edit_priority:{ad_id}' 回调的 handler。"
            "键盘 ad_detail_keyboard 已定义此按钮，但无对应处理函数。"
            f"当前 handler 函数: {handler_names}"
        )

    def test_ad_edit_priority_fsm_state_exists(self):
        """AdStates 应包含编辑优先级的 FSM 状态。"""
        states = [s for s in dir(AdStates) if not s.startswith("_")]

        has_priority_state = any(
            "priority" in s.lower()
            for s in states
        )

        assert has_priority_state, (
            "AdStates 应包含编辑广告优先级的 FSM 状态（如 waiting_ad_priority 或 editing_priority）。"
            f"当前状态: {states}"
        )


class TestAdPrioritySettingStep:
    """验证添加广告流程中包含优先级设置步骤。

    当前 ad.py 的 cb_ad_confirm 中硬编码 priority=0，
    应在确认前增加一个步骤让管理员设置优先级。
    """

    def test_ad_confirm_does_not_hardcode_priority_zero(self):
        """cb_ad_confirm 不应硬编码 priority=0。

        应从 FSM state data 中读取用户设置的优先级值。
        """
        from app.master_bot.handlers.ad import cb_ad_confirm

        source = inspect.getsource(cb_ad_confirm)

        # 检查是否从 state data 中读取 priority
        reads_priority_from_data = (
            "data.get(\"priority\"" in source
            or "data.get('priority'" in source
            or "data[\"priority\"]" in source
            or "data['priority']" in source
        )

        # 检查是否硬编码 priority=0
        hardcoded_zero = "priority=0" in source

        assert reads_priority_from_data or not hardcoded_zero, (
            "cb_ad_confirm 硬编码 priority=0，应从 FSM state data 中读取用户设置的优先级。"
            "需要在添加广告流程中增加优先级设置步骤。"
        )

    def test_ad_fsm_has_priority_step(self):
        """添加广告的 FSM 流程应包含优先级设置步骤。

        在选择范围之后、确认之前，应有一个步骤让管理员输入优先级。
        """
        states = [s for s in dir(AdStates) if not s.startswith("_")]

        has_priority_state = any(
            "priority" in s.lower()
            for s in states
        )

        assert has_priority_state, (
            "AdStates 应包含优先级设置步骤的 FSM 状态（如 waiting_ad_priority）。"
            f"当前状态: {states}"
        )


class TestAdConfirmReEditButton:
    """验证广告确认页包含"重新编辑"按钮。

    根据设计文档 06-广告系统设计.md 步骤5，确认页应有：
    [确认添加]  [重新编辑]  [取消]
    当前 ad_confirm_keyboard 只有 [确认添加] 和 [取消]。
    """

    def test_ad_confirm_keyboard_has_reedit_button(self):
        """ad_confirm_keyboard 应包含"重新编辑"按钮。"""
        from app.master_bot.keyboards.inline import ad_confirm_keyboard

        kb = ad_confirm_keyboard()
        all_buttons = []
        for row in kb.inline_keyboard:
            for btn in row:
                all_buttons.append(btn)

        button_texts = [btn.text for btn in all_buttons]
        button_callbacks = [btn.callback_data for btn in all_buttons]

        has_reedit = any(
            "重新编辑" in text or "reedit" in (cb or "").lower() or "re_edit" in (cb or "").lower()
            for text, cb in zip(button_texts, button_callbacks)
        )

        assert has_reedit, (
            "ad_confirm_keyboard 缺少'重新编辑'按钮。"
            "根据设计文档，确认页应有 [确认添加] [重新编辑] [取消] 三个按钮。"
            f"当前按钮: {button_texts}"
        )

    def test_ad_reedit_handler_exists(self):
        """应存在处理"重新编辑"回调的 handler。"""
        from app.master_bot.handlers import ad as ad_module

        handler_names = [
            name for name, _ in inspect.getmembers(ad_module, inspect.iscoroutinefunction)
        ]

        has_reedit_handler = any(
            "reedit" in name.lower() or "re_edit" in name.lower()
            for name in handler_names
        )

        assert has_reedit_handler, (
            "ad.py 中缺少处理'重新编辑'回调的 handler。"
            f"当前 handler 函数: {handler_names}"
        )
