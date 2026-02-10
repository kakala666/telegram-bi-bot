"""结构化日志配置"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings


def setup_logging(
    settings: Settings | None = None,
    log_level: str = "INFO",
    log_file: str | None = None,
) -> None:
    """配置结构化日志。

    Args:
        settings: 应用配置对象（优先使用）
        log_level: 日志级别（settings 为 None 时使用）
        log_file: 日志文件路径（settings 为 None 时使用）
    """
    if settings is not None:
        log_level = settings.LOG_LEVEL
        log_file = settings.LOG_FILE

    level = getattr(logging, log_level.upper(), logging.INFO)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
        force=True,
    )

    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
