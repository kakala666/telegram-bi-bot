"""测试 Settings 配置类。"""

from __future__ import annotations

import os

import pytest

from app.config import Settings


class TestSettings:
    """Settings 类测试。"""

    def test_load_from_env_vars(self, monkeypatch):
        """测试从环境变量加载必填字段。"""
        monkeypatch.setenv("MASTER_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
        monkeypatch.setenv("ADMIN_USER_IDS", "111,222")
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-key-value")

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )

        assert settings.MASTER_BOT_TOKEN == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert settings.TOKEN_ENCRYPTION_KEY == "test-key-value"

    def test_admin_user_ids_comma_separated(self, monkeypatch):
        """测试 ADMIN_USER_IDS 逗号分隔解析。"""
        monkeypatch.setenv("MASTER_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("ADMIN_USER_IDS", "111, 222, 333")
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "key")

        settings = Settings(_env_file=None)  # type: ignore[call-arg]

        assert settings.ADMIN_USER_IDS == [111, 222, 333]

    def test_admin_user_ids_single_value(self, monkeypatch):
        """测试 ADMIN_USER_IDS 单个值。"""
        monkeypatch.setenv("MASTER_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("ADMIN_USER_IDS", "999")
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "key")

        settings = Settings(_env_file=None)  # type: ignore[call-arg]

        assert settings.ADMIN_USER_IDS == [999]

    def test_default_values(self, monkeypatch):
        """测试默认值。"""
        monkeypatch.setenv("MASTER_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("ADMIN_USER_IDS", "111")
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "key")

        settings = Settings(_env_file=None)  # type: ignore[call-arg]

        assert settings.DATABASE_URL == "sqlite+aiosqlite:///data/bot.db"
        assert settings.DEFAULT_AD_TEXT == "Powered by @YourPlatformBot"
        assert settings.DEFAULT_AD_URL == ""
        assert settings.BROADCAST_RATE_LIMIT == 20
        assert settings.MAX_BOTS_PER_USER == 3
        assert settings.MESSAGE_MAP_RETENTION_DAYS == 30
        assert settings.LOG_LEVEL == "INFO"
        assert settings.LOG_FILE == "logs/bot.log"

    def test_override_defaults(self, monkeypatch):
        """测试覆盖默认值。"""
        monkeypatch.setenv("MASTER_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("ADMIN_USER_IDS", "111")
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "key")
        monkeypatch.setenv("MAX_BOTS_PER_USER", "10")
        monkeypatch.setenv("BROADCAST_RATE_LIMIT", "50")

        settings = Settings(_env_file=None)  # type: ignore[call-arg]

        assert settings.MAX_BOTS_PER_USER == 10
        assert settings.BROADCAST_RATE_LIMIT == 50
