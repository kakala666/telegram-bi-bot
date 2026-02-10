from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class BaseRepository:
    """Repository 基类，提供 session 工厂注入"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
