"""Offline contracts only. These do not prove PostgreSQL RLS enforcement."""
import asyncio
import importlib.util
import io
import re
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from alembic import command
from alembic.config import Config
from jous_api.access import AccessService
from jous_api.config import Settings, ConfigurationError, load_settings, load_migration_settings
from jous_api.database import Database, DatabaseUnavailable, validate_runtime
from jous_api.database_context import DatabaseContext
from jous_api.dependencies import get_session, get_request_identity
from jous_api.identity import AccessDenied, RequestIdentity, OrganizationScope, VerifiedPrincipal
from test_access_foundation import context_session

ROOT = Path(__file__).resolve().parents[1]


class ContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_bind_order_parameterization_and_switch_denial(self):
        session = context_session()
        context = DatabaseContext(session)
        with self.assertRaises(AccessDenied):
            await context.bind_user(uuid4())
        await context.initialize()
        user, org = uuid4(), uuid4()
        await context.bind_user(user)
        await context.bind_organization(org)
        calls = session.execute.call_args_list
        self.assertIn("'', true", str(calls[0].args[0]))
        self.assertEqual(calls[1].args[1], {"value": str(user)})
        self.assertEqual(calls[2].args[1], {"value": str(org)})
        self.assertNotIn(str(user), str(calls[1].args[0]))
        for operation in (context.initialize(), context.bind_user(uuid4()), context.bind_organization(uuid4())):
            with self.assertRaises(AccessDenied):
                await operation
        with self.assertRaises(AccessDenied):
            context.require_organization(uuid4(), org)
        context.clear()
        with self.assertRaises(AccessDenied):
            context.require_user(user)

    async def test_savepoint_and_no_transaction_deny(self):
        session = context_session()
        context = DatabaseContext(session)
        session.in_nested_transaction = lambda: True
        with self.assertRaises(AccessDenied):
            await context.initialize()
        session.in_nested_transaction = lambda: False
        await context.initialize()
        session.in_transaction = lambda: False
        with self.assertRaises(AccessDenied):
            await context.bind_user(uuid4())

    async def test_exact_resolution_membership_before_org_and_failure_no_bind(self):
        session = context_session()
        service = AccessService(session)
        user, org = uuid4(), uuid4()
        session.scalar.side_effect = [user, org, org]
        identity = await service.resolve(VerifiedPrincipal("Exact/Issuer", "ExactSubject"))
        self.assertEqual(session.scalar.call_args_list[0].args[1],
                         {"issuer": "Exact/Issuer", "subject": "ExactSubject"})
        scope = await service.organization(identity, org)
        self.assertEqual(scope, OrganizationScope(user, org))
        self.assertIn("organization_memberships", str(session.scalar.call_args_list[1].args[0]))
        self.assertEqual(service.context.organization_id, org)
        with self.assertRaises(AccessDenied):
            await service.organization(identity, uuid4())
        denied = context_session(user)
        denied.scalar.return_value = None
        with self.assertRaises(AccessDenied):
            await AccessService(denied).organization(RequestIdentity(user), org)
        denied.execute.assert_not_called()
        self.assertIsNone(denied.info["jous_context"].organization_id)

    async def test_concurrent_contexts_do_not_share_state(self):
        contexts = [DatabaseContext(context_session()) for _ in range(10)]
        users = [uuid4() for _ in contexts]
        async def bind(context, user):
            await context.initialize()
            await asyncio.sleep(0)
            await context.bind_user(user)
        await asyncio.gather(*(bind(c, u) for c, u in zip(contexts, users)))
        self.assertEqual([c.user_id for c in contexts], users)

    async def test_incomplete_context_cannot_create_access_service(self):
        session = context_session()
        session.info.clear()
        with self.assertRaises(AccessDenied):
            AccessService(session)


class TransactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_commit_exception_cancellation_and_commit_failure_cleanup(self):
        for failure in (None, RuntimeError, asyncio.CancelledError, "commit"):
            with self.subTest(failure=failure):
                database = Database(Settings(environment="test"))
                session = context_session()
                transaction = MagicMock()
                transaction.__aenter__ = AsyncMock()
                transaction.__aexit__ = AsyncMock(return_value=False)
                if failure == "commit":
                    transaction.__aexit__.side_effect = RuntimeError("commit failed")
                session.begin = MagicMock(return_value=transaction)
                manager = MagicMock()
                manager.__aenter__ = AsyncMock(return_value=session)
                manager.__aexit__ = AsyncMock(return_value=False)
                database.session_factory = MagicMock(return_value=manager)
                connection = MagicMock()
                connection.closed = connection.invalidated = False
                proxy = MagicMock()
                proxy.driver_connection.close = AsyncMock()
                proxy.driver_connection.is_closed.return_value = True
                connection.get_raw_connection = AsyncMock(return_value=proxy)
                connection.run_sync = AsyncMock()
                connection.invalidate = AsyncMock()
                connection_manager = MagicMock()
                connection_manager.__aenter__ = AsyncMock(return_value=connection)
                connection_manager.__aexit__ = AsyncMock(return_value=False)
                database.engine = MagicMock()
                database.engine.connect.return_value = connection_manager
                with patch("jous_api.database.validate_runtime", new_callable=AsyncMock) as guard:
                    try:
                        async with database.scoped_transaction() as value:
                            context = value.info["jous_context"]
                            self.assertTrue(context.initialized)
                            if isinstance(failure, type):
                                raise failure()
                    except (RuntimeError, asyncio.CancelledError):
                        self.assertIsNotNone(failure)
                    else:
                        self.assertIsNone(failure)
                    guard.assert_awaited_once()
                transaction.__aexit__.assert_awaited_once()
                manager.__aexit__.assert_awaited_once()
                if failure:
                    connection.invalidate.assert_awaited_once()
                    connection.sync_connection.detach.assert_called_once()
                else:
                    connection.invalidate.assert_not_called()
                    connection.sync_connection.detach.assert_not_called()
                self.assertNotIn("jous_context", session.info)
                self.assertFalse(context.initialized)

    async def test_invalid_guard_does_not_initialize_or_yield(self):
        database = Database(Settings(environment="test"))
        with self.assertRaises(DatabaseUnavailable):
            async with database.scoped_transaction():
                self.fail("Unconfigured database yielded")

    async def test_cleanup_failure_preserves_original_application_error(self):
        database = Database(Settings(environment='test'))
        session = context_session()
        transaction, manager, connection_manager = MagicMock(), MagicMock(), MagicMock()
        transaction.__aenter__ = AsyncMock()
        transaction.__aexit__ = AsyncMock(return_value=False)
        session.begin = MagicMock(return_value=transaction)
        manager.__aenter__ = AsyncMock(return_value=session)
        manager.__aexit__ = AsyncMock(return_value=False)
        connection_manager.__aenter__ = AsyncMock(return_value=MagicMock())
        connection_manager.__aexit__ = AsyncMock(return_value=False)
        database.session_factory = MagicMock(return_value=manager)
        database.engine = MagicMock()
        database.engine.connect.return_value = connection_manager
        original = RuntimeError('original application failure')
        with patch('jous_api.database.validate_runtime', new_callable=AsyncMock), \
             patch.object(database, 'discard_connection', new_callable=AsyncMock,
                          side_effect=DatabaseUnavailable('Database connection cleanup failed')):
            with self.assertRaises(RuntimeError) as raised:
                async with database.scoped_transaction():
                    raise original
        self.assertIs(raised.exception, original)
        self.assertEqual(original.__notes__, ['Database connection cleanup failed'])
        self.assertNotIn('credential', str(raised.exception))

    def test_verified_principal_precedes_session_dependency(self):
        import inspect
        from jous_api.dependencies import get_verified_principal
        self.assertIs(inspect.signature(get_session).parameters["principal"].default.dependency,
                      get_verified_principal)


class PhysicalTerminationTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, *, close_failure=False, terminate_failure=False, cancel=False):
        from sqlalchemy.engine import Engine, URL
        from sqlalchemy.pool import QueuePool
        from sqlalchemy.dialects.postgresql.asyncpg import dialect, AsyncAdapt_asyncpg_connection
        from sqlalchemy.util.concurrency import greenlet_spawn
        class Driver:
            def __init__(self):
                self.close_attempts = self.terminations = 0
                self.closed = False
            async def close(self, timeout):
                self.close_attempts += 1
                if close_failure:
                    raise RuntimeError('credential-sensitive-driver-detail')
                self.closed = True
            def terminate(self):
                self.terminations += 1
                if terminate_failure:
                    raise RuntimeError('credential-sensitive-termination-detail')
                self.closed = True
            def is_closed(self):
                return self.closed
        class DBAPI:
            class Error(Exception):
                pass
            class _asyncpg:
                class PostgresError(Exception):
                    pass
        drivers = []
        def creator():
            driver = Driver()
            drivers.append(driver)
            return AsyncAdapt_asyncpg_connection(DBAPI(), driver)
        pg = dialect()
        engine = Engine(QueuePool(creator, pool_size=1, max_overflow=0, dialect=pg), pg, URL.create('postgresql'))
        engine.pool.logger.disabled = True
        sync = engine.connect()
        driver = drivers[0]
        entered, release = asyncio.Event(), asyncio.Event()
        class Bridge:
            sync_connection = sync
            @property
            def closed(self): return sync.closed
            @property
            def invalidated(self): return sync.invalidated
            async def get_raw_connection(self): return sync.connection
            async def run_sync(self, fn): return await greenlet_spawn(fn, sync)
            async def invalidate(self): return await greenlet_spawn(sync.invalidate)
        database = Database(Settings(environment='test'))
        bridge = Bridge()
        original_close = driver.close
        async def gated_close(timeout):
            entered.set()
            await release.wait()
            await original_close(timeout)
        driver.close = gated_close
        task = asyncio.create_task(database.discard_connection(bridge))
        second = None
        try:
            await asyncio.wait_for(entered.wait(), 1)
            self.assertIsNone(sync.connection.driver_connection, 'Must already be detached')
            second = asyncio.create_task(database.discard_connection(bridge))
            if cancel: task.cancel()
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            with engine.connect() as next_connection:
                self.assertIsNot(next_connection.connection.driver_connection, driver)
            release.set()
            results = await asyncio.wait_for(asyncio.gather(task, second, return_exceptions=True), 2)
            self.assertEqual(driver.close_attempts, 1)
            self.assertEqual(driver.terminations, int(close_failure))
            if terminate_failure:
                for result in results:
                    self.assertIsInstance(result, DatabaseUnavailable)
                    self.assertEqual(str(result), 'Database connection cleanup failed')
                    self.assertNotIn('credential', str(result))
            else:
                self.assertTrue(driver.is_closed(), 'Cleanup returned without physical termination')
                if cancel: self.assertIsInstance(results[0], asyncio.CancelledError)
                else: self.assertIsNone(results[0])
                self.assertIsNone(results[1])
            with engine.connect() as next_connection:
                self.assertIsNot(next_connection.connection.driver_connection, driver)
        finally:
            release.set()
            await asyncio.gather(*(t for t in (task, second) if t is not None), return_exceptions=True)
            sync.close()
            engine.dispose()

    async def test_unexpected_graceful_failure_requires_force_termination(self):
        await self.exercise(close_failure=True)

    async def test_normal_driver_close_and_duplicate_cleanup(self):
        await self.exercise()

    async def test_cancelled_cleanup_finishes_fallback(self):
        await self.exercise(close_failure=True, cancel=True)

    async def test_fallback_failure_is_bounded_not_success(self):
        await self.exercise(close_failure=True, terminate_failure=True)


class ConfigurationTests(unittest.TestCase):
    def test_no_fallback_or_admin_ingestion(self):
        runtime = "postgresql://jous_runtime:runtime-secret@host/jous"
        admin = "postgresql://admin:admin-secret@host/jous"
        self.assertIsNone(load_settings({"JOUS_MIGRATION_DATABASE_URL": admin}).database_url)
        with self.assertRaises(ConfigurationError):
            load_migration_settings({"JOUS_DATABASE_URL": runtime})
        settings = load_migration_settings({"JOUS_DATABASE_URL": runtime, "JOUS_MIGRATION_DATABASE_URL": admin})
        self.assertEqual(settings.database_url.get_secret_value(), admin)
        self.assertNotIn("admin-secret", repr(settings))
        with self.assertRaises(ConfigurationError) as error:
            load_migration_settings({"JOUS_MIGRATION_DATABASE_URL": "secret-invalid"})
        self.assertNotIn("secret-invalid", str(error.exception))


class GuardTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def temp_evidence(public=False):
        return dict(effective_temp=public, public_temp=public, public_grant_option=False,
                    direct_temp=False, memberships=False, database_owner=False,
                    database_create=False, schema_create=False, unsafe_attributes=False)

    async def test_bounded_temp_provenance(self):
        from jous_api.database import classify_runtime_temp, runtime_temp_evidence
        for public, expected in ((False, 'NO_TEMP_PRIVILEGE'), (True, 'MANAGED_PUBLIC_TEMP_BASELINE')):
            evidence = self.temp_evidence(public)
            self.assertEqual(classify_runtime_temp(evidence), expected)
            connection = AsyncMock()
            result = MagicMock()
            result.mappings.return_value.all.return_value = [evidence]
            connection.execute.return_value = result
            self.assertEqual((await runtime_temp_evidence(connection))['classification'], expected)
            connection.execute.assert_awaited_once()

    async def test_temp_elevations_and_ambiguous_provenance_fail_closed(self):
        from jous_api.database import classify_runtime_temp, runtime_temp_evidence
        faults = ('direct_temp', 'public_grant_option', 'memberships', 'database_owner',
                  'database_create', 'schema_create', 'unsafe_attributes')
        for fault in faults:
            evidence = self.temp_evidence(True)
            evidence[fault] = True
            with self.subTest(fault=fault), self.assertRaises(DatabaseUnavailable):
                classify_runtime_temp(evidence)
        for evidence in (None, {}, {**self.temp_evidence(), 'effective_temp': True},
                         {**self.temp_evidence(True), 'direct_temp': 0}):
            with self.assertRaises(DatabaseUnavailable):
                classify_runtime_temp(evidence)
        for rows in ([], [self.temp_evidence(), self.temp_evidence()]):
            connection = AsyncMock()
            result = MagicMock()
            result.mappings.return_value.all.return_value = rows
            connection.execute.return_value = result
            with self.assertRaises(DatabaseUnavailable):
                await runtime_temp_evidence(connection)
        connection = AsyncMock()
        connection.execute.side_effect = RuntimeError('secret-driver-state')
        with self.assertRaises(DatabaseUnavailable) as error:
            await runtime_temp_evidence(connection)
        self.assertNotIn('secret', str(error.exception))

    async def test_independent_validator_rejects_direct_temp_without_production_classifier(self):
        spec = importlib.util.spec_from_file_location('temp_validator', ROOT / 'tests/validate_managed_runtime_security.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for direct, grant in ((False, False), (True, False), (False, True)):
            connection = AsyncMock()
            row_result, acl_result = MagicMock(), MagicMock()
            row_result.mappings.return_value.one.return_value = dict(runtime_oid=42, effective_temp=True, database_acl='metadata')
            entries = [dict(grantee=0, privilege_type='TEMPORARY', is_grantable=grant)]
            if direct:
                entries.append(dict(grantee=42, privilege_type='TEMPORARY', is_grantable=False))
            acl_result.mappings.return_value.all.return_value = entries
            connection.execute.side_effect = [row_result, acl_result]
            with patch.object(module, 'runtime_temp_evidence', side_effect=AssertionError('must remain independent')):
                if direct or grant:
                    with self.assertRaises(RuntimeError):
                        await module.independent_temp_evidence(connection)
                else:
                    self.assertTrue((await module.independent_temp_evidence(connection))['public_temp'])

    def test_role_sql_retains_strict_guards_and_temp_acl_sources(self):
        from jous_api.database import ROLE_CHECK, TEMP_EVIDENCE
        self.assertIn("current_database(), 'CREATE'", ROLE_CHECK)
        for clause in ('d.datdba=r.oid', 'pg_has_role', 'c.relowner=r.oid',
                       'n.nspowner=r.oid', 'p.proowner=r.oid', 'has_schema_privilege',
                       'rolsuper', 'rolbypassrls', 'rolcreatedb', 'rolcreaterole',
                       'rolreplication', 'rolinherit'):
            self.assertIn(clause, ROLE_CHECK)
        for clause in ('aclexplode', 'acldefault', 'a.grantee=0', 'a.grantee=r.oid',
                       'a.is_grantable', "a.privilege_type='TEMPORARY'"):
            self.assertIn(clause, TEMP_EVIDENCE)

    def complete_connection(self):
        connection = AsyncMock()
        connection.scalar.return_value = True
        commands = {"users": ("SELECT",), "organization_memberships": ("SELECT",),
                    "organizations": ("SELECT", "UPDATE"), "projects": ("SELECT", "INSERT", "UPDATE")}
        policies = []
        for table, actions in commands.items():
            policies.append((table, f"jous_{table}_guard", "RESTRICTIVE", ['jous_runtime'], 'ALL'))
            for action in actions:
                policies.append((table, f"jous_{table}_{action.lower()}", "PERMISSIVE", ['jous_runtime'], action))
            if table in ('users', 'organizations'):
                policies.append((table, f"jous_{table}_helper_read", "PERMISSIVE", ['jous_security_reader'], 'SELECT'))
        privileges = [('projects','status','jous_runtime','UPDATE',False),
                      ('projects','organization_id','jous_runtime','UPDATE',False),
                      ('users','auth_subject','jous_runtime','SELECT',False),
                      ('users','auth_subject','jous_security_reader','SELECT',True),
                      ('organization_memberships','role','jous_security_reader','SELECT',False)]
        policy_result, privilege_result = MagicMock(), MagicMock()
        policy_result.all.return_value = policies
        privilege_result.all.return_value = privileges
        temp_result = MagicMock()
        temp_result.mappings.return_value.all.return_value = [self.temp_evidence()]
        connection.execute.side_effect = [temp_result, policy_result, privilege_result]
        return connection, policies, privileges

    async def test_expected_catalog_and_acl_contract_passes(self):
        for public in (False, True):
            connection, _, _ = self.complete_connection()
            temp_result = connection.execute.side_effect
            # Rebuild the ordered results to exercise real validate_runtime,
            # including classification, for both accepted platform baselines.
            results = list(temp_result)
            results[0].mappings.return_value.all.return_value = [self.temp_evidence(public)]
            connection.execute.side_effect = results
            await validate_runtime(connection)

    def test_validator_reports_checked_provenance(self):
        source = (ROOT / 'tests/validate_managed_runtime_security.py').read_text()
        self.assertIn('await validate_runtime(connection)', source)
        self.assertIn('await independent_temp_evidence(connection)', source)
        self.assertIn('production = await runtime_temp_evidence(connection)', source)
        self.assertNotIn('TEMP = safe', source)


    async def test_extra_permissive_policy_and_project_status_grant_deny(self):
        for fault in ('policy', 'status', 'helper_memberships'):
            connection, policies, privileges = self.complete_connection()
            if fault == 'policy':
                policies.append(('projects','allow_all','PERMISSIVE',['public'],'ALL'))
            elif fault == 'status':
                privileges[0] = (*privileges[0][:-1],True)
            else:
                privileges[-1] = (*privileges[-1][:-1],True)
            with self.assertRaises(DatabaseUnavailable):
                await validate_runtime(connection)

    async def test_configured_startup_guard_failure_disposes(self):
        from jous_api.main import create_app
        app = create_app(Settings(environment='test',database_url='postgresql://wrong:placeholder@invalid/db'))
        with patch.object(app.state.database,'check',new_callable=AsyncMock,
                          side_effect=DatabaseUnavailable('Runtime database safety check failed')), \
             patch.object(app.state.database,'dispose',new_callable=AsyncMock) as dispose:
            with self.assertRaises(DatabaseUnavailable):
                async with app.router.lifespan_context(app):
                    self.fail('Unsafe runtime started')
            dispose.assert_awaited_once()

    async def test_wrong_role_bypass_membership_or_dirty_baseline_fail_safe(self):
        for results in ([False], [True, False], [True, True, False]):
            connection = AsyncMock()
            connection.scalar.side_effect = results
            with self.assertRaises(DatabaseUnavailable) as error:
                await validate_runtime(connection)
            self.assertEqual(str(error.exception), "Runtime database safety check failed")

    async def test_driver_exception_is_redacted(self):
        connection = AsyncMock()
        connection.scalar.side_effect = RuntimeError("postgresql://secret:password@private/db")
        with self.assertRaises(DatabaseUnavailable) as error:
            await validate_runtime(connection)
        self.assertNotIn("password", str(error.exception))


class MigrationContractTests(unittest.TestCase):
    def render(self, downgrade=False):
        output = io.StringIO()
        config = Config(str(ROOT / "services/api/alembic.ini"), output_buffer=output)
        with patch("asyncpg.connect", new_callable=AsyncMock) as network:
            if downgrade:
                command.downgrade(config, "0002_runtime_rls:0001_identity_project", sql=True)
            else:
                command.upgrade(config, "0001_identity_project:0002_runtime_rls", sql=True)
            network.assert_not_called()
        return output.getvalue()

    def test_two_minimal_helpers_guarded_context_and_bounded_grants(self):
        sql = self.render()
        self.assertEqual(sql, self.render())
        self.assertEqual(sql.count("SECURITY DEFINER"), 2)
        self.assertEqual(sql.count("CREATE FUNCTION"), 2)
        self.assertEqual(sql.count("FORCE ROW LEVEL SECURITY"), 4)
        self.assertEqual(sql.count("AS RESTRICTIVE"), 4)
        self.assertIn("SET search_path = pg_catalog, pg_temp", sql)
        self.assertIn("CASE WHEN", sql)
        self.assertIn("ELSE NULL END", sql)
        self.assertIn("REVOKE ALL ON FUNCTION", sql)
        self.assertNotIn("GRANT DELETE", sql)
        self.assertNotIn("GRANT TRUNCATE", sql)
        self.assertNotIn("GRANT UPDATE (status", sql)
        self.assertNotIn("GRANT UPDATE (organization_id", sql)
        self.assertNotIn("CREATE TABLE", sql)
        for body in sql.split("$function$")[1::2]:
            self.assertNotIn("organization_memberships", body)
            self.assertNotIn("projects", body)
            self.assertNotIn("INSERT", body)

    def test_helper_acls_precede_final_ownership_transfer(self):
        sql = self.render()
        grant_create = sql.index("GRANT CREATE ON SCHEMA jous_security TO jous_security_reader;")
        revoke_create = sql.index("REVOKE CREATE ON SCHEMA jous_security FROM jous_security_reader;")
        for signature in ("resolve_user(text, text)", "organization_is_active(uuid)"):
            with self.subTest(signature=signature):
                name = signature.split("(")[0]
                create = sql.index(f"CREATE FUNCTION jous_security.{name}(")
                revoke = sql.index(f"REVOKE ALL ON FUNCTION jous_security.{signature} FROM PUBLIC;")
                grant = sql.index(f"GRANT EXECUTE ON FUNCTION jous_security.{signature} TO jous_runtime;")
                transfer = sql.index(f"ALTER FUNCTION jous_security.{signature} OWNER TO jous_security_reader;")
                self.assertLess(create, revoke)
                self.assertLess(revoke, grant)
                self.assertLess(grant, transfer)
                self.assertLess(grant_create, transfer)
                self.assertLess(transfer, revoke_create)
                # Policy calls may follow transfer; function-management commands may not.
                management = re.findall(
                    rf"(?:CREATE(?: OR REPLACE)?|ALTER|DROP) FUNCTION jous_security\.{name}\b[^;]*;"
                    rf"|(?:GRANT|REVOKE)[^;]*ON FUNCTION jous_security\.{name}\b[^;]*;",
                    sql, re.DOTALL,
                )
                self.assertEqual(len(management), 4)
                self.assertEqual(management[-1],
                                 f"ALTER FUNCTION jous_security.{signature} OWNER TO jous_security_reader;")
        self.assertIn("GRANT SELECT (id, auth_issuer, auth_subject, status) ON public.users TO jous_security_reader;", sql)
        self.assertIn("GRANT SELECT (id, status) ON public.organizations TO jous_security_reader;", sql)
        helper_table_grants = re.findall(r"GRANT [^;]*ON (?:TABLE )?public\.[^;]*TO jous_security_reader;", sql)
        self.assertEqual(len(helper_table_grants), 2)
        self.assertNotIn("SET ROLE", sql)

    def test_downgrade_preserves_enabled_rls_and_domain_tables(self):
        sql = self.render(True)
        self.assertNotIn("DISABLE ROW LEVEL SECURITY", sql)
        self.assertNotIn("DROP TABLE", sql)
        self.assertNotIn("CASCADE", sql)
        self.assertEqual(sql.count("NO FORCE ROW LEVEL SECURITY"), 4)
        self.assertIn("REVOKE UPDATE (", sql)

    def test_bootstrap_and_validator_are_opt_in_not_discovered(self):
        sql = (ROOT / "services/api/infrastructure/runtime_roles.sql").read_text()
        self.assertIn("Existing Jous role state requires review", sql)
        self.assertNotIn("PASSWORD '", sql)
        self.assertNotIn("CREATE ROLE jous_owner", sql)
        path = ROOT / "tests/validate_managed_runtime_security.py"
        spec = importlib.util.spec_from_file_location("validator_import_probe", path)
        with patch("asyncpg.connect", new_callable=AsyncMock) as network:
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
            network.assert_not_called()

    def test_managed_fingerprint_rejects_other_project_and_ignores_password(self):
        path = ROOT / 'tests/validate_managed_runtime_security.py'
        spec = importlib.util.spec_from_file_location('fingerprint_probe',path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        host='region.pooler.supabase.com'
        a=Settings(environment='test',database_url=f'postgresql://postgres.{module.PROJECT_REFERENCE}:secret-a@{host}:5432/postgres')
        b=Settings(environment='test',database_url=f'postgresql://jous_runtime.{module.PROJECT_REFERENCE}:secret-b@{host}:5432/postgres')
        self.assertEqual(module.fingerprint(a),module.fingerprint(b))
        with self.assertRaises(RuntimeError):
            module.fingerprint(Settings(environment='test',database_url=f'postgresql://postgres.other:secret@{host}:5432/postgres'))


class RemediationTests(unittest.IsolatedAsyncioTestCase):
    def validator(self):
        spec = importlib.util.spec_from_file_location('remediation_validator', ROOT / 'tests/validate_managed_runtime_security.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_routing_overrides_rejected_before_engine_creation(self):
        module = self.validator()
        base = f'postgresql://jous_runtime.{module.PROJECT_REFERENCE}:placeholder@region.pooler.supabase.com:5432/postgres'
        for query in ('host=evil', 'user=evil', 'database=evil', 'dbname=evil', 'port=9999',
                      'host=a&host=b', 'hostaddr=127.0.0.1', 'dsn=postgresql%3A%2F%2Fevil',
                      'h%6fst=evil', 'HOST=evil', 'host=good&host=evil', 'service=evil',
                      'ssl=require', 'server_settings=evil'):
            with self.subTest(query=query), self.assertRaises(RuntimeError):
                module.fingerprint(Settings(environment='test', database_url=base+'?'+query))
        from sqlalchemy.dialects.postgresql.asyncpg import dialect
        from sqlalchemy.engine import make_url
        args, effective = dialect().create_connect_args(make_url(base).set(drivername='postgresql+asyncpg'))
        self.assertEqual(args, [])
        self.assertEqual(effective['host'], 'region.pooler.supabase.com')
        self.assertEqual(effective['user'], 'jous_runtime.'+module.PROJECT_REFERENCE)
        self.assertEqual(effective['database'], 'postgres')
        self.assertEqual(effective['port'], 5432)

    async def test_authorized_writes_use_real_permission_service_and_new_project_scope(self):
        from jous_api.identity import ProjectScope
        from jous_api.permissions import Action, PermissionService
        module = self.validator()
        for role in ('member', 'owner'):
            with self.subTest(role=role):
                scope = OrganizationScope(uuid4(), uuid4())
                session = context_session()
                session.info['jous_context'].user_id = scope.user_id
                session.info['jous_context'].organization_id = scope.organization_id
                project_rows, writes, checks = {}, [], []

                async def scalar(statement):
                    # Persistence double only: real AccessService constructs scoped
                    # queries and real PermissionService evaluates each action.
                    selected = str(statement.selected_columns[0])
                    params = statement.compile().params.values()
                    self.assertIn(scope.user_id, params)
                    self.assertIn(scope.organization_id, params)
                    if selected == 'organization_memberships.role':
                        checks.append('role')
                        return role
                    if selected == 'projects.id':
                        checks.append('project')
                        return next((key for key in project_rows if key in params), None)
                    checks.append('organization')
                    return scope.organization_id

                async def execute(statement, params):
                    sql = str(statement)
                    result = MagicMock()
                    if sql.startswith('INSERT INTO public.projects'):
                        self.assertTrue(checks and checks[-1] == 'role', 'INSERT must follow authorization')
                        self.assertEqual(params['org'], scope.organization_id)
                        project_rows[params['id']] = (params['name'], params['description'])
                        writes.append('project.insert')
                        result.one_or_none.return_value = (params['id'], params['org'], params['name'], params['description'])
                    elif sql.startswith('UPDATE public.projects'):
                        self.assertIn('project', checks, 'UPDATE must revalidate the created Project')
                        self.assertIn(params['id'], project_rows)
                        self.assertEqual(params['org'], scope.organization_id)
                        project_rows[params['id']] = ('updated-control', 'update-control')
                        writes.append('project.update')
                        result.one_or_none.return_value = (params['id'], *project_rows[params['id']])
                    else:
                        self.assertTrue(sql.startswith('UPDATE public.organizations'))
                        self.assertEqual(role, 'owner')
                        writes.append('organization.update')
                        result.one_or_none.return_value = (scope.organization_id, 'owner-update-control')
                    return result

                session.scalar.side_effect = scalar
                session.execute.side_effect = execute
                permissions = PermissionService(AccessService(session))
                with patch.object(permissions, 'authorize', wraps=permissions.authorize) as authorize:
                    await module.authorized_writes(session, permissions, scope, owner=role == 'owner')
                    calls = authorize.call_args_list
                    self.assertEqual(calls[0].args, (scope, Action.CREATE_PROJECT))
                    created = next(iter(project_rows))
                    self.assertEqual(calls[1].args, (ProjectScope(scope.user_id, scope.organization_id, created),
                                                    Action.UPDATE_PROJECT))
                    if role == 'owner':
                        self.assertEqual(calls[2].args, (scope, Action.UPDATE_ORGANIZATION_NAME))
                self.assertEqual(writes, ['project.insert', 'project.update'] +
                                 (['organization.update'] if role == 'owner' else []))
                self.assertEqual(project_rows[created], ('updated-control', 'update-control'))
                before = session.execute.await_count
                with self.assertRaises(AccessDenied):
                    await permissions.authorize(scope, Action.UPDATE_PROJECT)
                self.assertEqual(session.execute.await_count, before)

    async def test_deny_all_insert_or_update_cannot_pass_positive_evidence(self):
        module = self.validator()
        scope = OrganizationScope(uuid4(), uuid4())
        for fault in ('insert', 'update', 'organization'):
            session = AsyncMock()
            permissions = AsyncMock()
            async def execute(statement, params):
                sql = str(statement)
                result = MagicMock()
                if sql.startswith('INSERT'):
                    row = None if fault == 'insert' else (params['id'], scope.organization_id, 'positive-control', 'insert-control')
                elif 'UPDATE public.projects' in sql:
                    row = None if fault == 'update' else (params['id'], 'updated-control', 'update-control')
                else:
                    row = None
                result.one_or_none.return_value = row
                return result
            session.execute.side_effect = execute
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                await module.authorized_writes(session, permissions, scope, owner=True)
        import inspect
        source = inspect.getsource(module.runtime_tests)
        self.assertIn('await authorized_writes(', source)
        self.assertIn('finally:\n                await session.rollback()', source)

    async def test_concurrent_failure_drains_sibling_before_cleanup(self):
        module = self.validator()
        started, drained = asyncio.Event(), asyncio.Event()
        async def sibling():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                drained.set()
        async def failure():
            await started.wait()
            raise RuntimeError('controlled failure')
        with self.assertRaises(ExceptionGroup):
            await asyncio.wait_for(module.concurrent_checks(sibling(), failure()), 1)
        self.assertTrue(drained.is_set())
