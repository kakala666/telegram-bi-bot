from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram.types import InlineKeyboardMarkup


@dataclass(frozen=True)
class BotInfo:
    """Token验证后返回的Bot信息"""

    bot_id: int
    username: str
    first_name: str


@dataclass(frozen=True)
class SubBotDTO:
    """子Bot信息（传递给Handler层）"""

    id: int
    bot_id: int
    bot_username: str
    owner_id: int
    owner_username: str | None
    status: str
    welcome_message: str | None
    user_count: int
    message_count: int
    created_at: datetime


@dataclass(frozen=True)
class BotUserDTO:
    """终端用户信息"""

    id: int
    sub_bot_id: int
    user_id: int
    username: str | None
    display_name: str
    is_blocked: bool
    is_banned_by_telegram: bool
    first_seen: datetime
    last_active: datetime


@dataclass(frozen=True)
class AdDTO:
    """广告信息"""

    id: int
    name: str
    ad_text: str
    ad_url: str | None
    button_text: str | None
    button_url: str | None
    is_active: bool
    target_type: str
    target_bot_id: int | None
    priority: int
    impression_count: int


@dataclass(frozen=True)
class BroadcastTaskDTO:
    """广播任务信息"""

    id: int
    sub_bot_id: int
    content_type: str
    total_count: int
    sent_count: int
    failed_count: int
    status: str
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class AdInjectionResult:
    """广告注入结果"""

    text: str
    keyboard: InlineKeyboardMarkup | None


@dataclass(frozen=True)
class ForwardResult:
    """转发结果"""

    success: bool
    forwarded_msg_id: int | None
    error: str | None


@dataclass(frozen=True)
class BroadcastProgress:
    """广播进度"""

    task_id: int
    total: int
    sent: int
    failed: int
    status: str
    percent: int
    progress_bar: str


@dataclass(frozen=True)
class PaginatedResult:
    """分页结果"""

    items: list
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
