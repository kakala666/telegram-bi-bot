from __future__ import annotations

from sqlalchemy import delete, select, update

from app.database.models import AdConfig, AdRotationState
from app.dto import AdDTO
from app.repositories.base import BaseRepository


class AdRepo(BaseRepository):
    """ad_configs 表操作"""

    @staticmethod
    def _to_dto(row: AdConfig) -> AdDTO:
        return AdDTO(
            id=row.id,
            name=row.name,
            ad_text=row.ad_text,
            ad_url=row.ad_url,
            button_text=row.button_text,
            button_url=row.button_url,
            is_active=row.is_active,
            target_type=row.target_type,
            target_bot_id=row.target_bot_id,
            priority=row.priority,
            impression_count=row.impression_count,
        )

    async def create(
        self,
        name: str,
        ad_text: str,
        ad_url: str | None,
        button_text: str | None,
        button_url: str | None,
        target_type: str,
        target_bot_id: int | None,
        priority: int,
    ) -> AdDTO:
        """创建广告"""
        async with self._session_factory() as session:
            ad = AdConfig(
                name=name,
                ad_text=ad_text,
                ad_url=ad_url,
                button_text=button_text,
                button_url=button_url,
                target_type=target_type,
                target_bot_id=target_bot_id,
                priority=priority,
            )
            session.add(ad)
            await session.commit()
            await session.refresh(ad)
            return self._to_dto(ad)

    async def get_by_id(self, id: int) -> AdDTO | None:
        """按主键查询"""
        async with self._session_factory() as session:
            result = await session.get(AdConfig, id)
            return self._to_dto(result) if result else None

    async def get_all(self) -> list[AdDTO]:
        """查询所有广告（管理员列表用）"""
        async with self._session_factory() as session:
            stmt = select(AdConfig).order_by(AdConfig.priority.desc())
            result = await session.scalars(stmt)
            return [self._to_dto(row) for row in result.all()]

    async def get_active_for_bot(self, sub_bot_id: int) -> AdDTO | None:
        """获取某Bot应展示的广告

        优先级逻辑:
        1. 该Bot的专属广告（target_type='specific', target_bot_id=sub_bot_id, is_active=True）
           按 priority DESC 取第一条
        2. 没有专属广告 -> 全局广告（target_type='global', is_active=True）
           按 priority DESC 取第一条
        3. 都没有 -> 返回 None
        """
        async with self._session_factory() as session:
            specific_stmt = (
                select(AdConfig)
                .where(
                    AdConfig.target_type == "specific",
                    AdConfig.target_bot_id == sub_bot_id,
                    AdConfig.is_active == True,  # noqa: E712
                )
                .order_by(AdConfig.priority.desc())
                .limit(1)
            )
            specific = await session.scalar(specific_stmt)
            if specific:
                return self._to_dto(specific)

            global_stmt = (
                select(AdConfig)
                .where(
                    AdConfig.target_type == "global",
                    AdConfig.is_active == True,  # noqa: E712
                )
                .order_by(AdConfig.priority.desc())
                .limit(1)
            )
            global_ad = await session.scalar(global_stmt)
            if global_ad:
                return self._to_dto(global_ad)

            return None

    async def get_active_ads_for_pool(
        self, pool_type: str, sub_bot_id: int
    ) -> list[AdDTO]:
        """获取指定池的活跃广告列表，按 priority DESC, id ASC 排序。"""
        async with self._session_factory() as session:
            if pool_type == "specific":
                stmt = (
                    select(AdConfig)
                    .where(
                        AdConfig.target_type == "specific",
                        AdConfig.target_bot_id == sub_bot_id,
                        AdConfig.is_active == True,  # noqa: E712
                    )
                    .order_by(AdConfig.priority.desc(), AdConfig.id.asc())
                )
            else:
                stmt = (
                    select(AdConfig)
                    .where(
                        AdConfig.target_type == "global",
                        AdConfig.is_active == True,  # noqa: E712
                    )
                    .order_by(AdConfig.priority.desc(), AdConfig.id.asc())
                )
            result = await session.scalars(stmt)
            return [self._to_dto(row) for row in result.all()]

    async def get_next_ad(self, sub_bot_id: int) -> AdDTO | None:
        """轮询获取下一条广告。

        优先 specific 池，无则回退 global 池。
        使用 AdRotationState 持久化游标，在同一事务内完成读+选+写。
        """
        async with self._session_factory() as session:
            # 1. 确定池类型和候选列表
            specific_stmt = (
                select(AdConfig)
                .where(
                    AdConfig.target_type == "specific",
                    AdConfig.target_bot_id == sub_bot_id,
                    AdConfig.is_active == True,  # noqa: E712
                )
                .order_by(AdConfig.priority.desc(), AdConfig.id.asc())
            )
            specific_rows = (await session.scalars(specific_stmt)).all()

            if specific_rows:
                pool_type = "specific"
                scope_id = sub_bot_id
                candidates = specific_rows
            else:
                global_stmt = (
                    select(AdConfig)
                    .where(
                        AdConfig.target_type == "global",
                        AdConfig.is_active == True,  # noqa: E712
                    )
                    .order_by(AdConfig.priority.desc(), AdConfig.id.asc())
                )
                global_rows = (await session.scalars(global_stmt)).all()
                if not global_rows:
                    return None
                pool_type = "global"
                scope_id = 0 if pool_type == "global" else sub_bot_id
                candidates = global_rows

            # 2. 读取或创建 rotation state
            state_stmt = select(AdRotationState).where(
                AdRotationState.scope_type == pool_type,
                AdRotationState.scope_id == scope_id,
            )
            state = await session.scalar(state_stmt)

            if state is None:
                state = AdRotationState(
                    scope_type=pool_type,
                    scope_id=scope_id,
                    cursor=0,
                    version=0,
                )
                session.add(state)
                await session.flush()

            # 3. 选择广告（cursor 取模保证不越界）
            cursor = state.cursor % len(candidates)
            chosen = candidates[cursor]

            # 4. 更新 cursor
            state.cursor = (cursor + 1) % len(candidates)
            state.version += 1

            # 5. 递增 impression_count（SQL 原子递增）
            await session.execute(
                update(AdConfig)
                .where(AdConfig.id == chosen.id)
                .values(impression_count=AdConfig.impression_count + 1)
            )

            await session.commit()

            return self._to_dto(chosen)

    async def update(
        self,
        id: int,
        name: str | None = None,
        ad_text: str | None = None,
        ad_url: str | None = None,
        button_text: str | None = None,
        button_url: str | None = None,
        is_active: bool | None = None,
        target_type: str | None = None,
        target_bot_id: int | None = None,
        priority: int | None = None,
    ) -> None:
        """更新广告（只更新非None的字段）"""
        values: dict = {}
        if name is not None:
            values["name"] = name
        if ad_text is not None:
            values["ad_text"] = ad_text
        if ad_url is not None:
            values["ad_url"] = ad_url
        if button_text is not None:
            values["button_text"] = button_text
        if button_url is not None:
            values["button_url"] = button_url
        if is_active is not None:
            values["is_active"] = is_active
        if target_type is not None:
            values["target_type"] = target_type
        if target_bot_id is not None:
            values["target_bot_id"] = target_bot_id
        if priority is not None:
            values["priority"] = priority

        if not values:
            return

        async with self._session_factory() as session:
            stmt = update(AdConfig).where(AdConfig.id == id).values(**values)
            await session.execute(stmt)
            await session.commit()

    async def increment_impression(self, id: int) -> None:
        """递增展示计数"""
        async with self._session_factory() as session:
            stmt = (
                update(AdConfig)
                .where(AdConfig.id == id)
                .values(impression_count=AdConfig.impression_count + 1)
            )
            await session.execute(stmt)
            await session.commit()

    async def delete(self, id: int) -> None:
        """删除广告"""
        async with self._session_factory() as session:
            stmt = delete(AdConfig).where(AdConfig.id == id)
            await session.execute(stmt)
            await session.commit()
