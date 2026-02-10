"""测试广告等权轮询功能。

验证持久化游标轮询（方案C）的完整行为：
- AdRotationState 模型
- AdRepo 轮询方法（get_active_ads_for_pool / get_next_ad）
- AdInjectorService 集成轮询
- 事务一致性
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import AdConfig, Base
from app.repositories.ad_repo import AdRepo
from app.repositories.bot_repo import BotRepo
from app.services.ad_injector import AdInjectorService


# ── 辅助函数 ──────────────────────────────────────────────────────


async def _create_bot(bot_repo: BotRepo, bot_id: int) -> int:
    """辅助函数：创建一个 SubBot 并返回其 id。"""
    dto = await bot_repo.create(
        bot_token_encrypted=f"tok_{bot_id}",
        bot_id=bot_id,
        bot_username=f"bot_{bot_id}",
        owner_id=1,
        owner_username=None,
    )
    return dto.id


async def _create_ad(
    ad_repo: AdRepo,
    name: str,
    target_type: str = "global",
    target_bot_id: int | None = None,
    priority: int = 0,
    is_active: bool = True,
) -> int:
    """辅助函数：创建广告并返回 id。"""
    dto = await ad_repo.create(
        name=name,
        ad_text=f"Text for {name}",
        ad_url=None,
        button_text=None,
        button_url=None,
        target_type=target_type,
        target_bot_id=target_bot_id,
        priority=priority,
    )
    if not is_active:
        await ad_repo.update(dto.id, is_active=False)
    return dto.id


# ═══════════════════════════════════════════════════════════════════
# 1. AdRotationState 模型测试
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestAdRotationStateModel:
    """验证 AdRotationState ORM 模型存在且字段正确。"""

    async def test_rotation_state_model_exists(self, engine):
        """AdRotationState 模型类存在且有正确字段。"""
        from app.database.models import AdRotationState

        assert hasattr(AdRotationState, "__tablename__")
        assert AdRotationState.__tablename__ == "ad_rotation_state"

        # 验证必要字段
        mapper = inspect(AdRotationState)
        column_names = {col.key for col in mapper.columns}
        expected_columns = {
            "id", "scope_type", "scope_id", "cursor", "version", "updated_at"
        }
        assert expected_columns.issubset(column_names), (
            f"缺少字段: {expected_columns - column_names}"
        )

    async def test_rotation_state_unique_constraint(self, engine):
        """(scope_type, scope_id) 有唯一约束。"""
        from app.database.models import AdRotationState

        # 通过表元数据检查唯一约束
        table = AdRotationState.__table__
        unique_constraints = [
            c for c in table.constraints
            if hasattr(c, "columns")
            and {col.name for col in c.columns} >= {"scope_type", "scope_id"}
        ]
        unique_indexes = [
            idx for idx in table.indexes
            if idx.unique and {col.name for col in idx.columns} >= {"scope_type", "scope_id"}
        ]
        assert len(unique_constraints) > 0 or len(unique_indexes) > 0, (
            "(scope_type, scope_id) 应有唯一约束或唯一索引"
        )

    async def test_rotation_state_table_created(self, engine):
        """ad_rotation_state 表在 create_all 时被创建。"""
        from app.database.models import AdRotationState  # noqa: F401

        # 重建表结构（包含新模型）
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # 验证表存在
        async with engine.begin() as conn:
            table_names = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
        assert "ad_rotation_state" in table_names


# ═══════════════════════════════════════════════════════════════════
# 2. AdRepo 轮询方法测试
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGetActiveAdsForPool:
    """测试 AdRepo.get_active_ads_for_pool 方法。"""

    async def test_get_active_ads_for_pool_specific(
        self, ad_repo: AdRepo, bot_repo: BotRepo
    ):
        """获取 specific 池活跃广告列表，按 priority DESC, id ASC 排序。"""
        sub_bot_id = await _create_bot(bot_repo, 7000001)

        # 创建 3 条 specific 广告（不同优先级）
        id_low = await _create_ad(
            ad_repo, "Low", "specific", sub_bot_id, priority=1
        )
        id_high = await _create_ad(
            ad_repo, "High", "specific", sub_bot_id, priority=10
        )
        id_mid = await _create_ad(
            ad_repo, "Mid", "specific", sub_bot_id, priority=5
        )
        # 创建 1 条非活跃的，不应出现
        await _create_ad(
            ad_repo, "Inactive", "specific", sub_bot_id, priority=100, is_active=False
        )

        result = await ad_repo.get_active_ads_for_pool("specific", sub_bot_id)

        assert len(result) == 3
        # 排序验证: priority DESC, id ASC
        assert result[0].id == id_high  # priority=10
        assert result[1].id == id_mid   # priority=5
        assert result[2].id == id_low   # priority=1

    async def test_get_active_ads_for_pool_global(self, ad_repo: AdRepo):
        """获取 global 池活跃广告列表。"""
        id_a = await _create_ad(ad_repo, "Global A", "global", priority=5)
        id_b = await _create_ad(ad_repo, "Global B", "global", priority=10)

        result = await ad_repo.get_active_ads_for_pool("global", 0)

        assert len(result) == 2
        assert result[0].id == id_b  # priority=10 排在前
        assert result[1].id == id_a  # priority=5

    async def test_get_active_ads_for_pool_empty(self, ad_repo: AdRepo):
        """池为空返回空列表。"""
        result = await ad_repo.get_active_ads_for_pool("specific", 99999)

        assert result == []

    async def test_get_active_ads_for_pool_same_priority_sorted_by_id(
        self, ad_repo: AdRepo
    ):
        """相同优先级时按 id ASC 排序。"""
        id_first = await _create_ad(ad_repo, "First", "global", priority=5)
        id_second = await _create_ad(ad_repo, "Second", "global", priority=5)

        result = await ad_repo.get_active_ads_for_pool("global", 0)

        assert len(result) == 2
        assert result[0].id == id_first   # id 较小排在前
        assert result[1].id == id_second


@pytest.mark.asyncio
class TestGetNextAd:
    """测试 AdRepo.get_next_ad 轮询方法。"""

    async def test_get_next_ad_specific_priority(
        self, ad_repo: AdRepo, bot_repo: BotRepo
    ):
        """有 specific 广告时优先用 specific 池。"""
        sub_bot_id = await _create_bot(bot_repo, 7100001)

        await _create_ad(ad_repo, "Global", "global", priority=100)
        specific_id = await _create_ad(
            ad_repo, "Specific", "specific", sub_bot_id, priority=1
        )

        result = await ad_repo.get_next_ad(sub_bot_id)

        assert result is not None
        assert result.id == specific_id
        assert result.target_type == "specific"

    async def test_get_next_ad_fallback_to_global(
        self, ad_repo: AdRepo, bot_repo: BotRepo
    ):
        """无 specific 广告时回退到 global 池。"""
        sub_bot_id = await _create_bot(bot_repo, 7100002)

        global_id = await _create_ad(ad_repo, "Global", "global", priority=10)

        result = await ad_repo.get_next_ad(sub_bot_id)

        assert result is not None
        assert result.id == global_id
        assert result.target_type == "global"

    async def test_get_next_ad_round_robin(
        self, ad_repo: AdRepo, bot_repo: BotRepo
    ):
        """连续调用轮询返回不同广告。"""
        sub_bot_id = await _create_bot(bot_repo, 7100003)

        id_a = await _create_ad(
            ad_repo, "Ad A", "specific", sub_bot_id, priority=10
        )
        id_b = await _create_ad(
            ad_repo, "Ad B", "specific", sub_bot_id, priority=5
        )

        # 连续调用 3 次应轮询
        first = await ad_repo.get_next_ad(sub_bot_id)
        second = await ad_repo.get_next_ad(sub_bot_id)
        third = await ad_repo.get_next_ad(sub_bot_id)

        assert first is not None
        assert second is not None
        assert third is not None

        # 第 1 次和第 2 次应返回不同广告
        assert first.id != second.id
        # 第 3 次应回到第 1 个（环形）
        assert third.id == first.id

        # 验证返回的是池中的广告
        returned_ids = {first.id, second.id}
        assert returned_ids == {id_a, id_b}

    async def test_get_next_ad_cursor_persists(
        self, ad_repo: AdRepo, bot_repo: BotRepo, session_factory
    ):
        """cursor 持久化验证——值保存在数据库中。"""
        from app.database.models import AdRotationState

        sub_bot_id = await _create_bot(bot_repo, 7100004)

        await _create_ad(ad_repo, "Ad 1", "specific", sub_bot_id, priority=10)
        await _create_ad(ad_repo, "Ad 2", "specific", sub_bot_id, priority=5)

        # 调用一次轮询
        await ad_repo.get_next_ad(sub_bot_id)

        # 直接查数据库验证 cursor 已持久化
        async with session_factory() as session:
            stmt = select(AdRotationState).where(
                AdRotationState.scope_type == "specific",
                AdRotationState.scope_id == sub_bot_id,
            )
            state = await session.scalar(stmt)

        assert state is not None
        assert state.cursor >= 0

    async def test_get_next_ad_cursor_wraps_around(
        self, ad_repo: AdRepo, bot_repo: BotRepo
    ):
        """cursor 环形回绕：超出列表长度后从头开始。"""
        sub_bot_id = await _create_bot(bot_repo, 7100005)

        await _create_ad(ad_repo, "Only A", "specific", sub_bot_id, priority=10)
        await _create_ad(ad_repo, "Only B", "specific", sub_bot_id, priority=5)
        await _create_ad(ad_repo, "Only C", "specific", sub_bot_id, priority=1)

        # 调用 3 次（完整一轮）
        results_round1 = []
        for _ in range(3):
            r = await ad_repo.get_next_ad(sub_bot_id)
            assert r is not None
            results_round1.append(r.id)

        # 再调用 3 次（第二轮），应与第一轮完全相同
        results_round2 = []
        for _ in range(3):
            r = await ad_repo.get_next_ad(sub_bot_id)
            assert r is not None
            results_round2.append(r.id)

        assert results_round1 == results_round2

    async def test_get_next_ad_cursor_resets_on_invalid(
        self, ad_repo: AdRepo, bot_repo: BotRepo
    ):
        """广告被删除/停用后 cursor 自动重置，不会越界。"""
        sub_bot_id = await _create_bot(bot_repo, 7100006)

        id_a = await _create_ad(ad_repo, "Ad A", "specific", sub_bot_id, priority=10)
        id_b = await _create_ad(ad_repo, "Ad B", "specific", sub_bot_id, priority=5)
        id_c = await _create_ad(ad_repo, "Ad C", "specific", sub_bot_id, priority=1)

        # 推进 cursor 到 2（已过 A、B）
        await ad_repo.get_next_ad(sub_bot_id)  # cursor -> 1
        await ad_repo.get_next_ad(sub_bot_id)  # cursor -> 2

        # 删掉 A 和 B，只剩 C
        await ad_repo.delete(id_a)
        await ad_repo.delete(id_b)

        # cursor=2 但列表只有 1 条，应自动重置/取模
        result = await ad_repo.get_next_ad(sub_bot_id)

        assert result is not None
        assert result.id == id_c

    async def test_get_next_ad_no_active_ads(
        self, ad_repo: AdRepo, bot_repo: BotRepo
    ):
        """无活跃广告返回 None。"""
        sub_bot_id = await _create_bot(bot_repo, 7100007)

        result = await ad_repo.get_next_ad(sub_bot_id)

        assert result is None

    async def test_get_next_ad_single_ad_always_returns_same(
        self, ad_repo: AdRepo, bot_repo: BotRepo
    ):
        """只有一条广告时，每次都返回同一条。"""
        sub_bot_id = await _create_bot(bot_repo, 7100008)

        the_id = await _create_ad(
            ad_repo, "Solo", "specific", sub_bot_id, priority=1
        )

        for _ in range(5):
            result = await ad_repo.get_next_ad(sub_bot_id)
            assert result is not None
            assert result.id == the_id

    async def test_get_next_ad_global_round_robin(self, ad_repo: AdRepo):
        """global 池也支持轮询。"""
        id_g1 = await _create_ad(ad_repo, "G1", "global", priority=10)
        id_g2 = await _create_ad(ad_repo, "G2", "global", priority=5)

        # 用一个不存在 specific 广告的 bot_id 触发 global 回退
        first = await ad_repo.get_next_ad(88888)
        second = await ad_repo.get_next_ad(88888)

        assert first is not None
        assert second is not None
        assert first.id != second.id
        assert {first.id, second.id} == {id_g1, id_g2}


# ═══════════════════════════════════════════════════════════════════
# 3. AdInjectorService 集成测试
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestAdInjectorRoundRobin:
    """验证 AdInjectorService.inject() 使用轮询而非固定选取。"""

    async def test_inject_uses_round_robin(
        self, ad_repo: AdRepo, bot_repo: BotRepo
    ):
        """inject() 连续调用返回不同广告文本。"""
        sub_bot_id = await _create_bot(bot_repo, 7200001)

        await _create_ad(ad_repo, "Ad Alpha", "specific", sub_bot_id, priority=10)
        await _create_ad(ad_repo, "Ad Beta", "specific", sub_bot_id, priority=5)

        svc = AdInjectorService(ad_repo)

        result1 = await svc.inject(text="msg1", sub_bot_id=sub_bot_id)
        result2 = await svc.inject(text="msg2", sub_bot_id=sub_bot_id)

        # 两次注入应包含不同的广告文本
        assert "Text for Ad Alpha" in result1.text or "Text for Ad Beta" in result1.text
        assert "Text for Ad Alpha" in result2.text or "Text for Ad Beta" in result2.text
        # 关键断言：两次的广告文本不同
        ad_text_1 = result1.text.split("━━━━━━━━━━━━━━━")[-1].strip()
        ad_text_2 = result2.text.split("━━━━━━━━━━━━━━━")[-1].strip()
        assert ad_text_1 != ad_text_2, "inject() 应轮询返回不同广告"

    async def test_inject_increments_impression(
        self, ad_repo: AdRepo, bot_repo: BotRepo
    ):
        """展示后 impression_count 递增（轮询模式下仍正确计数）。"""
        sub_bot_id = await _create_bot(bot_repo, 7200002)

        id_a = await _create_ad(ad_repo, "Count A", "specific", sub_bot_id, priority=10)
        id_b = await _create_ad(ad_repo, "Count B", "specific", sub_bot_id, priority=5)

        svc = AdInjectorService(ad_repo)

        # 调用 4 次 → 每个广告展示 2 次
        for _ in range(4):
            await svc.inject(text="hi", sub_bot_id=sub_bot_id)

        ad_a = await ad_repo.get_by_id(id_a)
        ad_b = await ad_repo.get_by_id(id_b)

        assert ad_a is not None
        assert ad_b is not None
        assert ad_a.impression_count + ad_b.impression_count == 4
        # 等权轮询时，每个广告应展示 2 次
        assert ad_a.impression_count == 2
        assert ad_b.impression_count == 2


# ═══════════════════════════════════════════════════════════════════
# 4. 事务测试
# ═══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestRotationTransaction:
    """验证轮询操作的事务一致性。"""

    async def test_rotation_single_transaction(
        self, ad_repo: AdRepo, bot_repo: BotRepo, session_factory
    ):
        """读+选+写在同一事务内（通过检查 session 使用验证）。"""
        sub_bot_id = await _create_bot(bot_repo, 7300001)

        await _create_ad(ad_repo, "Tx A", "specific", sub_bot_id, priority=10)
        await _create_ad(ad_repo, "Tx B", "specific", sub_bot_id, priority=5)

        # get_next_ad 应在单次 session 上下文中完成读+选+写
        # 通过 mock session_factory 来验证只进入了一次 context manager
        call_count = 0
        original_factory = ad_repo._session_factory

        class CountingFactory:
            """代理 session_factory，记录调用次数。"""

            def __call__(self):
                nonlocal call_count
                call_count += 1
                return original_factory()

        ad_repo._session_factory = CountingFactory()

        await ad_repo.get_next_ad(sub_bot_id)

        # get_next_ad 整体应只使用 1 个 session（1 次事务）
        assert call_count == 1, (
            f"get_next_ad 应在单一事务中完成，但创建了 {call_count} 个 session"
        )

        # 恢复
        ad_repo._session_factory = original_factory
