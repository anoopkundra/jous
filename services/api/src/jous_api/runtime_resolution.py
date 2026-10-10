"""Exact catalog resolution within a rollback-only verification savepoint.

The savepoint begins inside SQLAlchemy's outer transaction (autobegin for
AsyncConnection, explicit begin for scoped AsyncSession). Rolling it back
restores the incoming path without setting a session-persistent value or
changing the outer user/org context. Cleanup uncertainty propagates to the
caller's existing physical-connection disposal path.
"""
from contextlib import asynccontextmanager, contextmanager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

# Explicit pg_temp placement suppresses its implicit precedence for types and
# relations; functions/operators never search temporary namespaces (PG17).
VERIFICATION_PATH = 'pg_catalog, pg_temp'
SET_PATH = 'SET LOCAL search_path = pg_catalog, pg_temp'
CHECK_PATH = "SELECT pg_catalog.current_setting('search_path')"


@asynccontextmanager
async def catalog_resolution(connection):
    # Connection-level savepoints avoid AsyncSession.begin_nested's unconditional
    # ORM flush. Verification must not flush pending application writes.
    boundary = await connection.connection() if isinstance(connection, AsyncSession) else connection
    savepoint = await boundary.begin_nested()
    try:
        await connection.execute(text(SET_PATH))
        if await connection.scalar(text(CHECK_PATH)) != VERIFICATION_PATH:
            raise RuntimeError('RUNTIME_CATALOG_RESOLUTION')
        yield
    finally:
        await savepoint.rollback()


@contextmanager
def catalog_resolution_sync(connection):
    boundary = connection.connection() if isinstance(connection, Session) else connection
    savepoint = boundary.begin_nested()
    try:
        connection.execute(text(SET_PATH))
        if connection.scalar(text(CHECK_PATH)) != VERIFICATION_PATH:
            raise RuntimeError('RUNTIME_CATALOG_RESOLUTION')
        yield
    finally:
        savepoint.rollback()
