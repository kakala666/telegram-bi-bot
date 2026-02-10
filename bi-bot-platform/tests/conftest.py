"""测试公共 fixtures。

使用内存 SQLite 数据库，每个测试函数获得独立的数据库会话。
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base
from app.repositories.bot_repo import BotRepo
from app.repositories.user_repo import UserRepo
from app.repositories.message_map_repo import MessageMapRepo
from app.repositories.ad_repo import AdRepo
from app.repositories.broadcast_repo import BroadcastRepo
from app.services.token_encryptor import TokenEncryptor


@pytest_asyncio.fixture
async def engine():
    """创建内存 SQLite 异步引擎。"""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    """创建 async_sessionmaker fixture。"""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory


# ── Repository fixtures ──────────────────────────────────────────


@pytest.fixture
def bot_repo(session_factory) -> BotRepo:
    return BotRepo(session_factory)


@pytest.fixture
def user_repo(session_factory) -> UserRepo:
    return UserRepo(session_factory)


@pytest.fixture
def message_map_repo(session_factory) -> MessageMapRepo:
    return MessageMapRepo(session_factory)


@pytest.fixture
def ad_repo(session_factory) -> AdRepo:
    return AdRepo(session_factory)


@pytest.fixture
def broadcast_repo(session_factory) -> BroadcastRepo:
    return BroadcastRepo(session_factory)


# ── TokenEncryptor fixture ───────────────────────────────────────


@pytest.fixture
def fernet_key() -> str:
    """生成一个测试用 Fernet 密钥。"""
    return Fernet.generate_key().decode()


@pytest.fixture
def token_encryptor(fernet_key) -> TokenEncryptor:
    return TokenEncryptor(fernet_key)
