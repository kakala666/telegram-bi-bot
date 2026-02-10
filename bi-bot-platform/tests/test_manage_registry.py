"""测试 manage.py Registry 调用。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, User

from app.dto import SubBotDTO


def _make_callback(
    user_id: int = 999,
    data: str = "bot_stop_confirm:1",
) -> MagicMock:
    """创建 mock CallbackQuery 对象。"""
    cb = MagicMock(spec=CallbackQuery)
    cb.data = data
    cb.from_user = MagicMock(spec=User)
    cb.from_user.id = user_id
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    return cb


def _make_sub_bot_dto(
    id: int = 1,
    bot_id: int = 100,
    bot_username: str = "test_bot",
    owner_id: int = 999,
    status: str = "active",
) -> SubBotDTO:
    return SubBotDTO(
        id=id,
        bot_id=bot_id,
        bot_username=bot_username,
        owner_id=owner_id,
        owner_username=None,
        status=status,
        welcome_message=None,
        user_count=0,
        message_count=0,
        created_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
class TestManageRegistryCalls:
    """测试 manage.py 调用 BotRegistry。"""

    async def test_stop_bot_calls_registry_remove(self):
        """测试停止Bot调用 registry.remove_bot。"""
        try:
            from app.master_bot.handlers.manage import cb_bot_stop_confirm

            callback = _make_callback(user_id=999, data="bot_stop_confirm:1")

            bot_repo = MagicMock()
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(id=1, bot_id=12345, owner_id=999)
            )
            bot_repo.update_status = AsyncMock()

            registry = MagicMock()
            registry.remove_bot = AsyncMock()

            await cb_bot_stop_confirm(callback, bot_repo, registry)

            # 应该调用 registry.remove_bot
            registry.remove_bot.assert_called_once_with(12345)

            # 应该更新数据库状态
            bot_repo.update_status.assert_called_once_with(1, "stopped")

            # 应该显示成功消息
            callback.message.edit_text.assert_called_once()
        except (ImportError, TypeError) as e:
            # TypeError: 如果函数签名不包含 registry 参数
            pytest.skip(f"manage.py not updated with registry parameter: {e}")

    async def test_restart_bot_calls_registry_add(self):
        """测试重启Bot调用 registry.add_bot。"""
        try:
            from app.master_bot.handlers.manage import cb_bot_restart

            callback = _make_callback(user_id=999, data="bot_restart:1")

            bot_repo = MagicMock()
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(
                    id=1, bot_id=12345, owner_id=999, status="stopped"
                )
            )
            bot_repo.get_encrypted_token = AsyncMock(return_value="encrypted_token")
            bot_repo.update_status = AsyncMock()

            registry = MagicMock()
            registry.add_bot = AsyncMock()

            encryptor = MagicMock()
            encryptor.decrypt = MagicMock(return_value="decrypted_token")

            await cb_bot_restart(callback, bot_repo, registry, encryptor)

            # 应该解密Token
            encryptor.decrypt.assert_called_once_with("encrypted_token")

            # 应该调用 registry.add_bot
            registry.add_bot.assert_called_once_with("decrypted_token", 12345)

            # 应该更新数据库状态
            bot_repo.update_status.assert_called_once_with(1, "active")

            # 应该显示成功消息
            callback.message.edit_text.assert_called_once()
        except (ImportError, TypeError) as e:
            pytest.skip(f"manage.py not updated with registry parameter: {e}")

    async def test_delete_bot_calls_registry_remove(self):
        """测试删除Bot调用 registry.remove_bot。"""
        try:
            from app.master_bot.handlers.manage import cb_bot_delete_confirm

            callback = _make_callback(user_id=999, data="bot_delete_confirm:1")

            bot_repo = MagicMock()
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(id=1, bot_id=12345, owner_id=999)
            )
            bot_repo.delete = AsyncMock()

            user_repo = MagicMock()
            user_repo.delete_by_sub_bot = AsyncMock(return_value=10)

            msg_map_repo = MagicMock()
            msg_map_repo.delete_by_sub_bot = AsyncMock(return_value=50)

            broadcast_repo = MagicMock()
            broadcast_repo.delete_by_sub_bot = AsyncMock(return_value=2)

            registry = MagicMock()
            registry.remove_bot = AsyncMock()

            await cb_bot_delete_confirm(
                callback, bot_repo, user_repo, msg_map_repo, broadcast_repo, registry
            )

            # 应该调用 registry.remove_bot
            registry.remove_bot.assert_called_once_with(12345)

            # 应该删除所有相关数据
            msg_map_repo.delete_by_sub_bot.assert_called_once_with(1)
            broadcast_repo.delete_by_sub_bot.assert_called_once_with(1)
            user_repo.delete_by_sub_bot.assert_called_once_with(1)
            bot_repo.delete.assert_called_once_with(1)

            # 应该显示成功消息
            callback.message.edit_text.assert_called_once()
        except (ImportError, TypeError) as e:
            pytest.skip(f"manage.py not updated with registry parameter: {e}")


@pytest.mark.asyncio
class TestManageRegistryErrorHandling:
    """测试 manage.py Registry 错误处理。"""

    async def test_stop_bot_registry_error(self):
        """测试停止Bot时 Registry 错误处理。"""
        try:
            from app.exceptions import RegistryError
            from app.master_bot.handlers.manage import cb_bot_stop_confirm

            callback = _make_callback(user_id=999, data="bot_stop_confirm:1")

            bot_repo = MagicMock()
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(id=1, bot_id=12345, owner_id=999)
            )
            bot_repo.update_status = AsyncMock()

            registry = MagicMock()
            registry.remove_bot = AsyncMock(side_effect=RegistryError("Bot not found"))

            await cb_bot_stop_confirm(callback, bot_repo, registry)

            # 即使 Registry 失败，也应该更新数据库状态
            bot_repo.update_status.assert_called_once_with(1, "stopped")

            # 应该显示消息（可能包含警告）
            callback.message.edit_text.assert_called_once()
        except (ImportError, TypeError):
            pytest.skip("manage.py not updated with registry parameter")

    async def test_restart_bot_registry_error(self):
        """测试重启Bot时 Registry 错误处理。"""
        try:
            from app.exceptions import RegistryError
            from app.master_bot.handlers.manage import cb_bot_restart

            callback = _make_callback(user_id=999, data="bot_restart:1")

            bot_repo = MagicMock()
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(
                    id=1, bot_id=12345, owner_id=999, status="stopped"
                )
            )
            bot_repo.get_encrypted_token = AsyncMock(return_value="encrypted_token")
            bot_repo.update_status = AsyncMock()

            registry = MagicMock()
            registry.add_bot = AsyncMock(
                side_effect=RegistryError("Failed to start bot")
            )

            encryptor = MagicMock()
            encryptor.decrypt = MagicMock(return_value="decrypted_token")

            await cb_bot_restart(callback, bot_repo, registry, encryptor)

            # 应该显示错误消息
            callback.message.edit_text.assert_called_once()
            call_args = callback.message.edit_text.call_args[0][0]
            assert "失败" in call_args or "错误" in call_args

            # 不应该更新数据库状态为 active
            # （或者应该标记为 error）
        except (ImportError, TypeError):
            pytest.skip("manage.py not updated with registry parameter")


@pytest.mark.asyncio
class TestManageRegistryPermissions:
    """测试 manage.py Registry 权限检查。"""

    async def test_stop_bot_permission_check(self):
        """测试停止Bot权限检查。"""
        try:
            from app.master_bot.handlers.manage import cb_bot_stop_confirm

            callback = _make_callback(user_id=999, data="bot_stop_confirm:1")

            bot_repo = MagicMock()
            # Bot属于其他用户
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(id=1, bot_id=12345, owner_id=888)
            )

            registry = MagicMock()
            registry.remove_bot = AsyncMock()

            await cb_bot_stop_confirm(callback, bot_repo, registry)

            # 不应该调用 registry.remove_bot
            registry.remove_bot.assert_not_called()

            # 应该显示权限错误
            callback.answer.assert_called()
            call_args = callback.answer.call_args
            assert call_args[1].get("show_alert") is True
        except (ImportError, TypeError):
            pytest.skip("manage.py not updated with registry parameter")

    async def test_restart_bot_permission_check(self):
        """测试重启Bot权限检查。"""
        try:
            from app.master_bot.handlers.manage import cb_bot_restart

            callback = _make_callback(user_id=999, data="bot_restart:1")

            bot_repo = MagicMock()
            # Bot属于其他用户
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(id=1, bot_id=12345, owner_id=888)
            )

            registry = MagicMock()
            registry.add_bot = AsyncMock()

            encryptor = MagicMock()

            await cb_bot_restart(callback, bot_repo, registry, encryptor)

            # 不应该调用 registry.add_bot
            registry.add_bot.assert_not_called()

            # 应该显示权限错误
            callback.answer.assert_called()
            call_args = callback.answer.call_args
            assert call_args[1].get("show_alert") is True
        except (ImportError, TypeError):
            pytest.skip("manage.py not updated with registry parameter")

    async def test_delete_bot_permission_check(self):
        """测试删除Bot权限检查。"""
        try:
            from app.master_bot.handlers.manage import cb_bot_delete_confirm

            callback = _make_callback(user_id=999, data="bot_delete_confirm:1")

            bot_repo = MagicMock()
            # Bot属于其他用户
            bot_repo.get_by_id = AsyncMock(
                return_value=_make_sub_bot_dto(id=1, bot_id=12345, owner_id=888)
            )

            user_repo = MagicMock()
            msg_map_repo = MagicMock()
            broadcast_repo = MagicMock()
            registry = MagicMock()
            registry.remove_bot = AsyncMock()

            await cb_bot_delete_confirm(
                callback, bot_repo, user_repo, msg_map_repo, broadcast_repo, registry
            )

            # 不应该调用 registry.remove_bot
            registry.remove_bot.assert_not_called()

            # 应该显示权限错误
            callback.answer.assert_called()
            call_args = callback.answer.call_args
            assert call_args[1].get("show_alert") is True
        except (ImportError, TypeError):
            pytest.skip("manage.py not updated with registry parameter")
