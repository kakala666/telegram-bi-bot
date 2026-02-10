from __future__ import annotations

from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    """应用全局配置，从 .env 文件和环境变量加载"""

    # --- 主机器人 ---
    MASTER_BOT_TOKEN: str
    ADMIN_USER_IDS: Annotated[list[int], NoDecode]

    # --- 数据库 ---
    DATABASE_URL: str = "sqlite+aiosqlite:///data/bot.db"

    # --- 安全 ---
    TOKEN_ENCRYPTION_KEY: str

    # --- 广告 ---
    DEFAULT_AD_TEXT: str = "Powered by @YourPlatformBot"
    DEFAULT_AD_URL: str = ""

    # --- 广播 ---
    BROADCAST_RATE_LIMIT: int = 20

    # --- 子Bot ---
    MAX_BOTS_PER_USER: int = 3
    MESSAGE_MAP_RETENTION_DAYS: int = 30

    # --- 日志 ---
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/bot.log"

    @field_validator("ADMIN_USER_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: object) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, list):
            return [int(x) for x in v]
        return [int(v)]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }
