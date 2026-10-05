"""PostgreSQL infrastructure only. Construction never opens a connection."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import Settings
from .database_context import DatabaseContext


class DatabaseUnavailable(RuntimeError):
    """Safe absence-of-configuration error; contains no connection details."""


ROLE_CHECK = """SELECT session_user = 'jous_runtime' AND current_user = 'jous_runtime'
 AND NOT r.rolsuper AND NOT r.rolbypassrls AND NOT r.rolcreatedb AND NOT r.rolcreaterole
 AND NOT r.rolreplication AND NOT r.rolinherit
 AND NOT pg_catalog.has_database_privilege(r.oid, current_database(), 'CREATE')
 AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_database d WHERE d.datname=current_database() AND d.datdba=r.oid)
 AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles other WHERE other.oid <> r.oid
                  AND pg_catalog.pg_has_role(r.oid, other.oid, 'MEMBER'))
 AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_class c WHERE c.relowner=r.oid)
 AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n WHERE n.nspowner=r.oid)
 AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_proc p WHERE p.proowner=r.oid)
 AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n WHERE n.nspname NOT LIKE 'pg_%'
     AND n.nspname <> 'information_schema' AND pg_catalog.has_schema_privilege(r.oid,n.oid,'CREATE'))
 FROM pg_catalog.pg_roles r WHERE r.rolname=current_user"""
TEMP_EVIDENCE = """SELECT
 pg_catalog.has_database_privilege(r.oid,d.oid,'TEMP') AS effective_temp,
 EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(d.datacl,pg_catalog.acldefault('d',d.datdba))) a
         WHERE a.grantee=0 AND a.privilege_type='TEMPORARY') AS public_temp,
 EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(d.datacl,pg_catalog.acldefault('d',d.datdba))) a
         WHERE a.grantee=0 AND a.privilege_type='TEMPORARY' AND a.is_grantable) AS public_grant_option,
 EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(d.datacl,pg_catalog.acldefault('d',d.datdba))) a
         WHERE a.grantee=r.oid AND a.privilege_type='TEMPORARY') AS direct_temp,
 EXISTS (SELECT 1 FROM pg_catalog.pg_roles other WHERE other.oid<>r.oid
         AND pg_catalog.pg_has_role(r.oid,other.oid,'MEMBER')) AS memberships,
 d.datdba=r.oid AS database_owner,
 pg_catalog.has_database_privilege(r.oid,d.oid,'CREATE') AS database_create,
 EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n WHERE n.nspname NOT LIKE 'pg_%'
         AND n.nspname<>'information_schema' AND pg_catalog.has_schema_privilege(r.oid,n.oid,'CREATE')) AS schema_create,
 r.rolsuper OR r.rolbypassrls OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication
 OR r.rolinherit OR NOT r.rolcanlogin AS unsafe_attributes
 FROM pg_catalog.pg_database d CROSS JOIN pg_catalog.pg_roles r
 WHERE d.datname=current_database() AND r.rolname='jous_runtime'
 AND current_user=r.rolname AND session_user=r.rolname"""


def classify_runtime_temp(evidence):
    """Catalog evidence only; PUBLIC is an ACL source, not provider branding."""
    fields = {'effective_temp', 'public_temp', 'public_grant_option', 'direct_temp',
              'memberships', 'database_owner', 'database_create', 'schema_create', 'unsafe_attributes'}
    if (not isinstance(evidence, dict) or set(evidence) != fields
            or any(type(value) is not bool for value in evidence.values())
            or any(evidence[name] for name in fields - {'effective_temp', 'public_temp'})
            or evidence['effective_temp'] != evidence['public_temp']):
        raise DatabaseUnavailable("Runtime database safety check failed")
    return 'MANAGED_PUBLIC_TEMP_BASELINE' if evidence['effective_temp'] else 'NO_TEMP_PRIVILEGE'


async def runtime_temp_evidence(connection):
    try:
        rows = (await connection.execute(text(TEMP_EVIDENCE))).mappings().all()
        if len(rows) != 1:
            raise DatabaseUnavailable("Runtime database safety check failed")
        evidence = dict(rows[0])
        return {'classification': classify_runtime_temp(evidence), **evidence}
    except Exception:
        raise DatabaseUnavailable("Runtime database safety check failed") from None


BASELINE_CHECK = """SELECT COALESCE(pg_catalog.current_setting('jous.user_id',true),'') = ''
 AND COALESCE(pg_catalog.current_setting('jous.organization_id',true),'') = ''"""
STATE_CHECK = """SELECT
 (SELECT count(*) FROM public.alembic_version WHERE version_num='0002_runtime_rls') = 1
 AND (SELECT count(*) FROM public.alembic_version) = 1
 AND (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='public' AND c.relname IN ('users','organizations','organization_memberships','projects')
       AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity) = 4
 AND (SELECT count(*) FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
      JOIN pg_catalog.pg_roles r ON r.oid=p.proowner WHERE n.nspname='jous_security'
       AND p.proname IN ('resolve_user','organization_is_active') AND p.prosecdef
       AND p.provolatile='s' AND p.proparallel='u' AND r.rolname='jous_security_reader'
       AND p.proconfig=ARRAY['search_path=pg_catalog, pg_temp']
       AND NOT EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,
                       pg_catalog.acldefault('f',p.proowner))) a WHERE a.grantee NOT IN
                       (p.proowner, (SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_runtime')))) = 2
 AND (SELECT count(*) FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='jous_security') = 2
 AND NOT pg_catalog.has_schema_privilege('jous_security_reader','jous_security','CREATE')
 AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n,
     LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
     WHERE n.nspname='jous_security' AND a.grantee=0)"""


async def validate_runtime(connection, *, state=True):
    """Catalog/connectivity checks only; never reads domain rows or calls helpers."""
    try:
        for sql in (ROLE_CHECK, BASELINE_CHECK, STATE_CHECK) if state else (ROLE_CHECK, BASELINE_CHECK):
            if await connection.scalar(text(sql)) is not True:
                raise DatabaseUnavailable("Unsafe runtime database configuration")
        await runtime_temp_evidence(connection)
        if state:
            # No extra policy may widen authority. Expressions are reviewed in the migration.
            rows = (await connection.execute(text("SELECT tablename, policyname, permissive, roles, cmd "
                "FROM pg_catalog.pg_policies WHERE schemaname='public' AND tablename IN "
                "('users','organizations','organization_memberships','projects')"))).all()
            expected = set()
            commands = {"users": ("SELECT",), "organization_memberships": ("SELECT",),
                        "organizations": ("SELECT", "UPDATE"), "projects": ("SELECT", "INSERT", "UPDATE")}
            for table, actions in commands.items():
                expected.add((table, f"jous_{table}_guard", "RESTRICTIVE", ("jous_runtime",), "ALL"))
                expected.update((table, f"jous_{table}_{cmd.lower()}", "PERMISSIVE", ("jous_runtime",), cmd)
                                for cmd in actions)
                if table in ("users", "organizations"):
                    expected.add((table, f"jous_{table}_helper_read", "PERMISSIVE", ("jous_security_reader",), "SELECT"))
            if {(r[0], r[1], r[2], tuple(r[3]), r[4]) for r in rows} != expected:
                raise DatabaseUnavailable("Unsafe runtime database configuration")
            safe_tables = await connection.scalar(text("SELECT NOT EXISTS (SELECT 1 FROM "
                "(VALUES ('users'),('organizations'),('organization_memberships'),('projects')) t(name) "
                "CROSS JOIN (VALUES ('DELETE'),('TRUNCATE'),('TRIGGER'),('REFERENCES')) p(priv) "
                "CROSS JOIN (VALUES ('jous_runtime'),('jous_security_reader')) r(name) "
                "WHERE pg_catalog.has_table_privilege(CAST(r.name AS pg_catalog.name), 'public.' || t.name, p.priv))"))
            if safe_tables is not True:
                raise DatabaseUnavailable("Unsafe runtime database configuration")
            allowed = {
                "users": {"SELECT": {"id", "status"}},
                "organizations": {"SELECT": {"id", "name", "status", "created_at", "updated_at"},
                                  "UPDATE": {"name", "updated_at"}},
                "organization_memberships": {"SELECT": {"id", "user_id", "organization_id", "role", "status", "created_at", "updated_at"}},
                "projects": {"SELECT": {"id", "organization_id", "name", "description", "status", "created_at", "updated_at"},
                             "INSERT": {"id", "organization_id", "name", "description"},
                             "UPDATE": {"name", "description", "updated_at"}}}
            reader = {"users": {"id", "auth_issuer", "auth_subject", "status"}, "organizations": {"id", "status"}}
            privileges = (await connection.execute(text("SELECT c.relname, a.attname, r.name, p.priv, "
                "pg_catalog.has_column_privilege(CAST(r.name AS pg_catalog.name), c.oid, a.attnum, p.priv) "
                "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                "JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid "
                "CROSS JOIN (VALUES ('jous_runtime'),('jous_security_reader')) r(name) "
                "CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('REFERENCES')) p(priv) "
                "WHERE n.nspname='public' AND c.relname IN "
                "('users','organizations','organization_memberships','projects') "
                "AND a.attnum>0 AND NOT a.attisdropped"))).all()
            if not privileges:
                raise DatabaseUnavailable("Unsafe runtime database configuration")
            for table, column, role, privilege, actual in privileges:
                expected = (column in allowed[table].get(privilege, set()) if role == "jous_runtime"
                            else privilege == "SELECT" and column in reader.get(table, set()))
                if actual is not expected:
                    raise DatabaseUnavailable("Unsafe runtime database configuration")
            helper_safe = await connection.scalar(text("SELECT NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls "
                "AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolinherit "
                "AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member=r.oid) "
                "AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_class c WHERE c.relowner=r.oid) "
                "FROM pg_catalog.pg_roles r WHERE r.rolname='jous_security_reader'"))
            if helper_safe is not True:
                raise DatabaseUnavailable("Unsafe runtime database configuration")
            unrelated_safe = await connection.scalar(text("SELECT NOT EXISTS (SELECT 1 FROM pg_catalog.pg_class c "
                "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                "CROSS JOIN (VALUES ('jous_runtime'),('jous_security_reader')) r(name) "
                "WHERE c.relkind IN ('r','v','m','f','p') AND n.nspname NOT LIKE 'pg_%' "
                "AND n.nspname <> 'information_schema' AND NOT (n.nspname='public' AND "
                "((r.name='jous_runtime' AND c.relname IN ('users','organizations','organization_memberships','projects','alembic_version')) "
                "OR (r.name='jous_security_reader' AND c.relname IN ('users','organizations')))) "
                "AND (pg_catalog.has_any_column_privilege(CAST(r.name AS pg_catalog.name),c.oid,'SELECT,INSERT,UPDATE,REFERENCES') "
                "OR pg_catalog.has_table_privilege(CAST(r.name AS pg_catalog.name),c.oid,'DELETE,TRUNCATE,TRIGGER'))) "
                "AND NOT pg_catalog.has_table_privilege('jous_runtime','public.alembic_version',"
                "'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES')"))
            if unrelated_safe is not True:
                raise DatabaseUnavailable("Unsafe runtime database configuration")
    except Exception:
        raise DatabaseUnavailable("Runtime database safety check failed") from None


class Database:
    def __init__(self, settings: Settings):
        self._connection_cleanup_tasks = {}
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

    async def discard_connection(self, connection):
        # Coalesce cleanup: callers retain ownership until this task completes.
        # No outer context may race a second close with physical termination.
        task = self._connection_cleanup_tasks.get(connection)
        if task is None:
            if connection.closed or connection.invalidated:
                return

            async def terminate():
                # PoolProxiedConnection.driver_connection is public, but becomes
                # unavailable after detach. Retain it BEFORE releasing the record.
                # SQLAlchemy 2.0.54 swallows unexpected detached-close exceptions;
                # therefore use only asyncpg's public driver close/terminate APIs
                # and verify its public is_closed() result before dropping ownership.
                physical = await connection.get_raw_connection()
                driver = physical.driver_connection
                connection.sync_connection.detach()
                try:
                    try:
                        await driver.close(timeout=min(2.0, self.timeout_seconds))
                        closed = driver.is_closed() is True
                    except Exception:
                        closed = False
                    if not closed:
                        driver.terminate()
                        if driver.is_closed() is not True:
                            raise DatabaseUnavailable("Database connection cleanup failed")
                finally:
                    # Detached invalidate retires the proxy; it is deliberately
                    # AFTER the complete driver termination/fallback attempt.
                    await connection.invalidate()

            task = asyncio.create_task(terminate())
            self._connection_cleanup_tasks[connection] = task
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
            except Exception:
                break
        try:
            task.result()
        except Exception:
            raise DatabaseUnavailable("Database connection cleanup failed") from None
        finally:
            if self._connection_cleanup_tasks.get(connection) is task:
                self._connection_cleanup_tasks.pop(connection, None)
        if cancelled:
            raise asyncio.CancelledError

    async def check(self) -> None:
        """Bounded runtime connectivity/safety probe; never reads tenant data."""
        if self.engine is None:
            raise DatabaseUnavailable("Database is not configured")
        try:
            async with asyncio.timeout(self.timeout_seconds):
                async with self.engine.connect() as connection:
                    try:
                        await validate_runtime(connection)
                        if await connection.scalar(text("SELECT 1")) != 1:
                            raise DatabaseUnavailable("Database check failed")
                    except BaseException as error:
                        try:
                            await self.discard_connection(connection)
                        except DatabaseUnavailable:
                            error.add_note("Database connection cleanup failed")
                        raise
        except TimeoutError:
            raise
        except Exception:
            raise DatabaseUnavailable("Runtime database check failed") from None

    @asynccontextmanager
    async def scoped_transaction(self):
        """Hold the physical connection until commit/rollback and security cleanup finish."""
        if self.engine is None or self.session_factory is None:
            raise DatabaseUnavailable("Database is not configured")
        context = None
        async with self.engine.connect() as connection:
            async with self.session_factory(bind=connection) as session:
                try:
                    async with session.begin():
                        async with asyncio.timeout(self.timeout_seconds):
                            await validate_runtime(session)
                            context = DatabaseContext(session)
                            await context.initialize()
                        session.info["jous_context"] = context
                        yield session
                except BaseException as error:
                    # External binding keeps the connection checked out even after
                    # session rollback. Detach synchronously before asynchronous close:
                    # uncertain/contaminated connections can NEVER reenter the pool.
                    try:
                        await self.discard_connection(connection)
                    except DatabaseUnavailable:
                        error.add_note("Database connection cleanup failed")
                    raise
                finally:
                    session.info.pop("jous_context", None)
                    if context is not None:
                        context.clear()

    async def dispose(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
