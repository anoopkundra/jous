"""PostgreSQL infrastructure only. Construction never opens a connection."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import Settings


class DatabaseUnavailable(RuntimeError):
    """Safe absence-of-configuration error; contains no connection details."""


class Database:
    def __init__(self, settings: Settings):
        self.timeout_seconds = settings.database_timeout_seconds
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None
        if settings.database_url is not None:
            url = make_url(settings.database_url.get_secret_value()).set(
                drivername="postgresql+asyncpg")
            # Small fixed pool per API process. No overflow or eager checkout.
            self.engine = create_async_engine(
                url, pool_size=2, max_overflow=0,
                pool_timeout=self.timeout_seconds, pool_pre_ping=True,
                connect_args={"timeout": self.timeout_seconds},
                echo=False, hide_parameters=True)
            self.session_factory = async_sessionmaker(
                self.engine, expire_on_commit=False, autoflush=False)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """One caller-owned unit of work: commit success, rollback failure, close always.

        Never share the yielded session between concurrent tasks.
        Beginning an empty unit of work does not itself check out a connection.
        """
        if self.session_factory is None:
            raise DatabaseUnavailable("Database is not configured")
        async with self.session_factory() as session:
            async with session.begin():
                yield session

    async def check(self) -> None:
        """Explicit, bounded connectivity probe; does not inspect schema/readiness of domains."""
        if self.engine is None:
            raise DatabaseUnavailable("Database is not configured")
        async with asyncio.timeout(self.timeout_seconds):
            async with self.engine.connect() as connection:
                if await connection.scalar(text("SELECT 1")) != 1:
                    raise DatabaseUnavailable("Database check failed")

    async def dispose(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
