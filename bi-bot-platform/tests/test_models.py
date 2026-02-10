"""测试 ORM 模型。"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.models import AdConfig, BotUser, BroadcastTask, MessageMap, SubBot


@pytest.mark.asyncio
class TestSubBotModel:
    """SubBot 模型测试。"""

    async def test_create_sub_bot(self, session_factory):
        """测试创建 SubBot 记录。"""
        async with session_factory() as session:
            bot = SubBot(
                bot_token_encrypted="encrypted_token_123",
                bot_id=123456789,
                bot_username="test_bot",
                owner_id=111222333,
                owner_username="owner_user",
                status="active",
            )
            session.add(bot)
            await session.commit()
            await session.refresh(bot)

            assert bot.id is not None
            assert bot.bot_id == 123456789
            assert bot.bot_username == "test_bot"
            assert bot.owner_id == 111222333
            assert bot.status == "active"

    async def test_default_values(self, session_factory):
        """测试字段默认值。"""
        async with session_factory() as session:
            bot = SubBot(
                bot_token_encrypted="enc_tok",
                bot_id=999,
                bot_username="bot99",
                owner_id=111,
            )
            session.add(bot)
            await session.commit()
            await session.refresh(bot)

            assert bot.status == "active"
            assert bot.user_count == 0
            assert bot.message_count == 0
            assert bot.welcome_message is None
            assert bot.created_at is not None
            assert bot.updated_at is not None

    async def test_unique_bot_id(self, session_factory):
        """测试 bot_id 唯一约束。"""
        async with session_factory() as session:
            bot1 = SubBot(
                bot_token_encrypted="tok1",
                bot_id=12345,
                bot_username="bot_a",
                owner_id=111,
            )
            session.add(bot1)
            await session.commit()

        async with session_factory() as session:
            bot2 = SubBot(
                bot_token_encrypted="tok2",
                bot_id=12345,
                bot_username="bot_b",
                owner_id=222,
            )
            session.add(bot2)
            with pytest.raises(IntegrityError):
                await session.commit()


@pytest.mark.asyncio
class TestBotUserModel:
    """BotUser 模型测试。"""

    async def test_create_bot_user(self, session_factory):
        """测试创建 BotUser 记录。"""
        async with session_factory() as session:
            bot = SubBot(
                bot_token_encrypted="tok",
                bot_id=100,
                bot_username="b",
                owner_id=1,
            )
            session.add(bot)
            await session.commit()
            await session.refresh(bot)

            user = BotUser(
                sub_bot_id=bot.id,
                user_id=555,
                username="testuser",
                first_name="Test",
                last_name="User",
                display_name="Test User",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            assert user.id is not None
            assert user.user_id == 555
            assert user.display_name == "Test User"

    async def test_bot_user_default_values(self, session_factory):
        """测试 BotUser 默认值。"""
        async with session_factory() as session:
            bot = SubBot(
                bot_token_encrypted="tok",
                bot_id=200,
                bot_username="b2",
                owner_id=1,
            )
            session.add(bot)
            await session.commit()
            await session.refresh(bot)

            user = BotUser(
                sub_bot_id=bot.id,
                user_id=666,
                display_name="User 666",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            assert user.is_blocked is False
            assert user.is_banned_by_telegram is False
            assert user.first_seen is not None
            assert user.last_active is not None

    async def test_unique_sub_bot_user(self, session_factory):
        """测试 (sub_bot_id, user_id) 唯一约束。"""
        async with session_factory() as session:
            bot = SubBot(
                bot_token_encrypted="tok",
                bot_id=300,
                bot_username="b3",
                owner_id=1,
            )
            session.add(bot)
            await session.commit()
            await session.refresh(bot)

            u1 = BotUser(sub_bot_id=bot.id, user_id=777, display_name="A")
            session.add(u1)
            await session.commit()

        async with session_factory() as session:
            u2 = BotUser(sub_bot_id=bot.id, user_id=777, display_name="B")
            session.add(u2)
            with pytest.raises(IntegrityError):
                await session.commit()


@pytest.mark.asyncio
class TestMessageMapModel:
    """MessageMap 模型测试。"""

    async def test_create_message_map(self, session_factory):
        """测试创建 MessageMap 记录。"""
        async with session_factory() as session:
            bot = SubBot(
                bot_token_encrypted="tok",
                bot_id=400,
                bot_username="b4",
                owner_id=1,
            )
            session.add(bot)
            await session.commit()
            await session.refresh(bot)

            mm = MessageMap(
                sub_bot_id=bot.id,
                user_id=888,
                user_msg_id=10,
                forwarded_msg_id=20,
                direction="in",
            )
            session.add(mm)
            await session.commit()
            await session.refresh(mm)

            assert mm.id is not None
            assert mm.direction == "in"
            assert mm.created_at is not None


@pytest.mark.asyncio
class TestAdConfigModel:
    """AdConfig 模型测试。"""

    async def test_create_ad_config(self, session_factory):
        """测试创建 AdConfig 记录。"""
        async with session_factory() as session:
            ad = AdConfig(
                name="Test Ad",
                ad_text="Buy now!",
                target_type="global",
                priority=10,
            )
            session.add(ad)
            await session.commit()
            await session.refresh(ad)

            assert ad.id is not None
            assert ad.name == "Test Ad"
            assert ad.is_active is True
            assert ad.impression_count == 0

    async def test_ad_config_default_values(self, session_factory):
        """测试 AdConfig 默认值。"""
        async with session_factory() as session:
            ad = AdConfig(
                name="Default Ad",
                ad_text="text",
                target_type="global",
            )
            session.add(ad)
            await session.commit()
            await session.refresh(ad)

            assert ad.is_active is True
            assert ad.priority == 0
            assert ad.impression_count == 0
            assert ad.target_bot_id is None


@pytest.mark.asyncio
class TestBroadcastTaskModel:
    """BroadcastTask 模型测试。"""

    async def test_create_broadcast_task(self, session_factory):
        """测试创建 BroadcastTask 记录。"""
        async with session_factory() as session:
            bot = SubBot(
                bot_token_encrypted="tok",
                bot_id=500,
                bot_username="b5",
                owner_id=1,
            )
            session.add(bot)
            await session.commit()
            await session.refresh(bot)

            task = BroadcastTask(
                sub_bot_id=bot.id,
                owner_id=1,
                content_type="text",
                content_text="Hello everyone!",
                total_count=100,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            assert task.id is not None
            assert task.status == "pending"
            assert task.sent_count == 0
            assert task.failed_count == 0
            assert task.completed_at is None