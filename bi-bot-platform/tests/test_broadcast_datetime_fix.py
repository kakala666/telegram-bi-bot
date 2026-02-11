"""测试广播 datetime 时区修复 - RED 阶段。

验证 BroadcastService 在 offset-naive datetime（SQLite 返回值）场景下
不会抛出 TypeError，以及 handler 层的异常兜底逻辑。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.dto import BotUserDTO, BroadcastTaskDTO, SubBotDTO
from app.exceptions import BroadcastError
from app.services.broadcast import BroadcastService


# ── 工厂函数 ──────────────────────────────────────────────────────


def _make_task_dto(
    *,
    id: int = 1,
    sub_bot_id: int = 1,
    content_type: str = "text",
    total_count: int = 5,
    sent_count: int = 0,
    failed_count: int = 0,
    status: str = "completed",
    created_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> BroadcastTaskDTO:
    return BroadcastTaskDTO(
        id=id,
        sub_bot_id=sub_bot_id,
        content_type=content_type,
        total_count=total_count,
        sent_count=sent_count,
        failed_count=failed_count,
        status=status,
        created_at=created_at or datetime.utcnow(),
        completed_at=completed_at,
    )


def _make_bot_user(user_id: int = 100) -> BotUserDTO:
    return BotUserDTO(
        id=1,
        sub_bot_id=1,
        user_id=user_id,
        username="test_user",
        display_name="Test User",
        is_blocked=False,
        is_banned_by_telegram=False,
        first_seen=datetime.utcnow(),
        last_active=datetime.utcnow(),
    )


def _build_service(
    *,
    broadcast_repo: MagicMock | None = None,
    user_repo: MagicMock | None = None,
    registry: MagicMock | None = None,
    bot_repo: MagicMock | None = None,
) -> BroadcastService:
    if broadcast_repo is None:
        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=None)
        broadcast_repo.create = AsyncMock(
            return_value=_make_task_dto(status="running")
        )
        broadcast_repo.update_progress = AsyncMock()
        broadcast_repo.update_status = AsyncMock()

    if user_repo is None:
        user_repo = MagicMock()
        user_repo.get_active_users = AsyncMock(
            return_value=[_make_bot_user(user_id=i) for i in range(3)]
        )

    if registry is None:
        registry = MagicMock()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        registry.get_bot = MagicMock(return_value=mock_bot)

    return BroadcastService(broadcast_repo, user_repo, registry, bot_repo)


# ── 测试用例 ──────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestBroadcastDatetimeFix:
    """广播服务 datetime 时区兼容性测试。"""

    async def test_start_with_naive_datetime(self) -> None:
        """offset-naive 的 created_at 不应导致 TypeError。

        SQLite 返回的 datetime 是 offset-naive 的。
        BroadcastService.start() 中用 datetime.now(timezone.utc) 做减法
        会抛出 TypeError: can't subtract offset-naive and offset-aware datetimes。
        修复后应该正常通过。
        """
        # 10 分钟前的 naive datetime —— 模拟 SQLite 返回值
        naive_created_at = datetime.utcnow() - timedelta(minutes=10)

        latest_task = _make_task_dto(created_at=naive_created_at)

        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=latest_task)
        broadcast_repo.create = AsyncMock(
            return_value=_make_task_dto(status="running")
        )
        broadcast_repo.update_progress = AsyncMock()
        broadcast_repo.update_status = AsyncMock()

        service = _build_service(broadcast_repo=broadcast_repo)

        # 不应抛出 TypeError
        task = await service.start(
            sub_bot_id=1,
            owner_id=999,
            content_type="text",
            content_text="Hello",
            content_file_id=None,
            content_caption=None,
        )

        assert task is not None
        assert task.status == "running"

    async def test_start_first_broadcast_no_history(self) -> None:
        """首次广播（无历史记录）应正常创建任务。"""
        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=None)
        broadcast_repo.create = AsyncMock(
            return_value=_make_task_dto(status="running", total_count=3)
        )
        broadcast_repo.update_progress = AsyncMock()
        broadcast_repo.update_status = AsyncMock()

        service = _build_service(broadcast_repo=broadcast_repo)

        task = await service.start(
            sub_bot_id=1,
            owner_id=999,
            content_type="text",
            content_text="First broadcast",
            content_file_id=None,
            content_caption=None,
        )

        assert task is not None
        assert task.total_count == 3
        broadcast_repo.create.assert_called_once()

    async def test_start_interval_sufficient(self) -> None:
        """created_at 为 6 分钟前（naive），应通过 5 分钟间隔检查。"""
        naive_created_at = datetime.utcnow() - timedelta(minutes=6)
        latest_task = _make_task_dto(created_at=naive_created_at)

        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=latest_task)
        broadcast_repo.create = AsyncMock(
            return_value=_make_task_dto(status="running")
        )
        broadcast_repo.update_progress = AsyncMock()
        broadcast_repo.update_status = AsyncMock()

        service = _build_service(broadcast_repo=broadcast_repo)

        # 不应抛出异常
        task = await service.start(
            sub_bot_id=1,
            owner_id=999,
            content_type="text",
            content_text="OK",
            content_file_id=None,
            content_caption=None,
        )

        assert task is not None

    async def test_start_interval_insufficient(self) -> None:
        """created_at 为 2 分钟前（naive），应抛出 BroadcastError。"""
        naive_created_at = datetime.utcnow() - timedelta(minutes=2)
        latest_task = _make_task_dto(created_at=naive_created_at)

        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=latest_task)

        service = _build_service(broadcast_repo=broadcast_repo)

        # 当前代码会因 naive vs aware 比较抛出 TypeError 而不是 BroadcastError
        # 修复后应抛出 BroadcastError
        with pytest.raises(BroadcastError, match="至少间隔5分钟"):
            await service.start(
                sub_bot_id=1,
                owner_id=999,
                content_type="text",
                content_text="Too soon",
                content_file_id=None,
                content_caption=None,
            )

    async def test_handler_exception_fallback(self) -> None:
        """cb_broadcast_confirm 应兜底 TypeError，不让异常逃逸。

        当前 handler 只捕获 BroadcastError，TypeError 会逃逸。
        修复后应捕获更广泛的异常并返回友好错误消息。
        """
        from aiogram import Bot

        from app.dto import SubBotDTO
        from app.sub_bot.handlers.broadcast import cb_broadcast_confirm

        # 构造 mock callback
        callback = MagicMock()
        callback.from_user = MagicMock()
        callback.from_user.id = 999
        callback.data = "broadcast_confirm"
        callback.message = MagicMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        # 构造 mock state
        state = MagicMock()
        state.get_data = AsyncMock(return_value={
            "broadcast_bot_id": 1,
            "content_type": "text",
            "content_text": "Hello",
            "content_file_id": None,
            "content_caption": None,
        })
        state.clear = AsyncMock()

        # 构造 mock sub_bot
        sub_bot = SubBotDTO(
            id=1,
            bot_id=12345,
            bot_username="test_bot",
            owner_id=999,
            owner_username="owner",
            status="active",
            welcome_message=None,
            user_count=10,
            message_count=100,
            created_at=datetime.utcnow(),
        )

        bot = MagicMock(spec=Bot)

        # broadcast_svc.start() 抛出 TypeError（模拟 datetime bug）
        broadcast_svc = MagicMock()
        broadcast_svc.start = AsyncMock(
            side_effect=TypeError(
                "can't subtract offset-naive and offset-aware datetimes"
            )
        )

        # 调用 handler —— 不应让 TypeError 逃逸
        try:
            await cb_broadcast_confirm(
                callback=callback,
                bot=bot,
                sub_bot=sub_bot,
                state=state,
                broadcast_svc=broadcast_svc,
            )
            # 如果没有抛异常，验证返回了错误消息
            callback.message.edit_text.assert_called_once()
            call_args = callback.message.edit_text.call_args
            assert "失败" in call_args[0][0] or "错误" in call_args[0][0]
        except TypeError:
            pytest.fail(
                "TypeError escaped from cb_broadcast_confirm - "
                "handler should catch non-BroadcastError exceptions too"
            )

    async def test_cleanup_expired_naive_datetime(self) -> None:
        """cleanup_expired 内部使用 aware datetime 与 SQLite naive 值兼容。

        BroadcastRepo.cleanup_expired 用 datetime.now(timezone.utc)
        生成 cutoff，但 SQLite 存储的 created_at 是 naive datetime。
        在 Python 层面比较时会报 TypeError。
        此测试验证实际的 repo 层面在 SQLite 环境下能正常工作。
        """
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        from app.database.models import Base, BroadcastTask
        from app.repositories.broadcast_repo import BroadcastRepo

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        repo = BroadcastRepo(factory)

        # 插入一条 8 天前的记录
        async with factory() as session:
            old_task = BroadcastTask(
                sub_bot_id=1,
                owner_id=999,
                content_type="text",
                content_text="Old broadcast",
                total_count=10,
                sent_count=10,
                failed_count=0,
                status="completed",
                created_at=datetime.utcnow() - timedelta(days=8),
                completed_at=datetime.utcnow() - timedelta(days=8),
            )
            session.add(old_task)
            await session.commit()

        # cleanup_expired 使用 datetime.now(timezone.utc) 做比较
        # 在 SQLite 中，比较发生在 SQL 层面（字符串比较），不会触发 Python TypeError
        # 但我们仍需验证结果正确
        deleted_count = await repo.cleanup_expired(retention_days=7)
        assert deleted_count == 1

        await engine.dispose()

    async def test_completed_at_is_naive(self) -> None:
        """_execute_broadcast 完成时写入的 completed_at 应与 SQLite 兼容。

        当前代码用 datetime.now(timezone.utc)（offset-aware）写入 completed_at，
        但 SQLite 不支持时区信息，后续读取时会变成 naive datetime。
        确保写入的值在 SQLite 往返后仍可正确比较。
        """
        broadcast_repo = MagicMock()
        broadcast_repo.get_running_by_bot = AsyncMock(return_value=None)
        broadcast_repo.get_latest_by_bot = AsyncMock(return_value=None)
        broadcast_repo.create = AsyncMock(
            return_value=_make_task_dto(id=42, status="running", total_count=1)
        )
        broadcast_repo.update_progress = AsyncMock()
        broadcast_repo.update_status = AsyncMock()

        user_repo = MagicMock()
        user_repo.get_active_users = AsyncMock(
            return_value=[_make_bot_user(user_id=100)]
        )

        registry = MagicMock()
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        registry.get_bot = MagicMock(return_value=mock_bot)

        bot_repo = MagicMock()
        bot_repo.get_by_id = AsyncMock(return_value=None)

        service = BroadcastService(broadcast_repo, user_repo, registry, bot_repo)

        await service.start(
            sub_bot_id=1,
            owner_id=999,
            content_type="text",
            content_text="Done",
            content_file_id=None,
            content_caption=None,
        )

        # 等待异步广播任务完成
        await asyncio.sleep(0.3)

        # 验证 update_status 被调用时传入了 completed_at
        broadcast_repo.update_status.assert_called()
        call_args = broadcast_repo.update_status.call_args

        # completed_at 参数
        completed_at = call_args.kwargs.get("completed_at") or call_args[1].get("completed_at")
        if completed_at is None and len(call_args[0]) >= 3:
            completed_at = call_args[0][2]

        assert completed_at is not None, "completed_at should be provided"

        # 验证写入的 completed_at 是 naive datetime（与 SQLite 兼容）
        # 当前代码用 datetime.now(timezone.utc) 生成 aware datetime
        # 修复后应使用 datetime.utcnow()（naive）或在写入前 strip tzinfo
        assert completed_at.tzinfo is None, (
            f"completed_at should be offset-naive for SQLite compatibility, "
            f"got tzinfo={completed_at.tzinfo}"
        )
