"""Explicitly gated PostgreSQL 17 disposable UsageEvent/RLS acceptance."""
import asyncio
import json
import os
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
ENABLED = os.environ.get("JOUS_V14_DISPOSABLE_AUTHORIZED") == "YES"


def _urls():
    if not ENABLED or os.environ.get("JOUS_V14_DISPOSABLE_ALLOW_MIGRATION") != "YES":
        raise RuntimeError("Explicit disposable migration authorization required")
    values = [os.environ.get("JOUS_V14_DISPOSABLE_" + key + "_URL", "")
              for key in ("ADMIN", "RUNTIME")]
    parsed = [urlsplit(value) for value in values]
    for url in parsed:
        if (url.scheme != "postgresql" or url.hostname not in {"127.0.0.1", "localhost"}
                or not url.path.startswith("/jous_v14_disposable_") or url.query or url.fragment
                or not url.username):
            raise RuntimeError("Dedicated loopback disposable PostgreSQL target required")
    if parsed[0].path != parsed[1].path or parsed[0].port != parsed[1].port:
        raise RuntimeError("Separate principals must use the same disposable database")
    if parsed[0].username == parsed[1].username or parsed[1].username != "jous_runtime":
        raise RuntimeError("Disposable admin/runtime principals must be distinct")
    return values


@unittest.skipUnless(ENABLED, "Explicit fresh disposable PostgreSQL authorization required")
class UsageEventPostgreSQLTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin_url, cls.runtime_url = _urls()

        async def bootstrap_and_migrate():
            import asyncpg
            from sqlalchemy.ext.asyncio import create_async_engine
            from alembic.config import Config
            from alembic import command

            admin = await asyncpg.connect(cls.admin_url)
            try:
                if not await admin.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname=current_user"):
                    raise RuntimeError("Disposable migration principal must be superuser")
                sentinel = await admin.fetchval(
                    "SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
                if sentinel != "JOUS_V14_DISPOSABLE_AUTHORIZED":
                    raise RuntimeError("Disposable database sentinel missing")
                await admin.execute("CREATE ROLE jous_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
                await admin.execute("CREATE ROLE jous_security_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
                await admin.execute("CREATE ROLE anon NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
                await admin.execute("CREATE ROLE authenticated NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
                await admin.execute("CREATE ROLE service_role NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
                await admin.execute("GRANT USAGE ON SCHEMA public TO jous_runtime,jous_security_reader")
            finally:
                await admin.close()
            engine = create_async_engine(cls.admin_url.replace("postgresql://", "postgresql+asyncpg://", 1))
            try:
                async with engine.begin() as connection:
                    def upgrade(sync_connection, revision):
                        config = Config(str(ROOT / "services/api/alembic.ini"))
                        config.attributes["connection"] = sync_connection
                        command.upgrade(config, revision)
                    # V1.1 identity objects are locally migrated, then the isolated
                    # fixture installs the same pre-0002 RLS-enabled baseline that
                    # managed project databases already have.
                    await connection.run_sync(upgrade, "0001_identity_project")
                    for table in ("users", "organizations", "organization_memberships", "projects"):
                        await connection.execute(__import__("sqlalchemy").text(
                            f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"))
                    await connection.run_sync(upgrade, "0006_snapshot_binding")
                # Reproduce the managed postgres/public defaults only for the
                # two new revisions, preserving the established earlier tables.
                admin = await asyncpg.connect(cls.admin_url)
                try:
                    await admin.execute("ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT TRUNCATE, REFERENCES, TRIGGER, MAINTAIN ON TABLES TO anon, authenticated, service_role")
                finally:
                    await admin.close()
                async with engine.begin() as connection:
                    await connection.run_sync(upgrade, "0008_usage_event_acl_hardening")
            finally:
                await engine.dispose()

        asyncio.run(bootstrap_and_migrate())

    async def asyncSetUp(self):
        import asyncpg
        self.admin = await asyncpg.connect(self.admin_url)
        self.runtime = await asyncpg.connect(self.runtime_url)
        self.owner, self.other, self.org, self.other_org, self.project, self.second_project, self.foreign_project = [uuid4() for _ in range(7)]
        now = datetime.now(timezone.utc)
        await self.admin.execute("INSERT INTO public.users(id) VALUES($1),($2)", self.owner, self.other)
        for org in (self.org, self.other_org):
            await self.admin.execute("INSERT INTO public.organizations(id,name) VALUES($1,'Usage fixture')", org)
        for user, org in ((self.owner, self.org), (self.other, self.other_org)):
            await self.admin.execute("INSERT INTO public.organization_memberships(id,user_id,organization_id,role) VALUES($1,$2,$3,'owner')",
                                     uuid4(), user, org)
        for project, org in ((self.project, self.org), (self.second_project, self.org),
                             (self.foreign_project, self.other_org)):
            await self.admin.execute("INSERT INTO public.projects(id,organization_id,name) VALUES($1,$2,'Usage fixture')", project, org)
        self.task = dict(id=uuid4(), organization_id=self.org, project_id=self.project,
            actor_user_id=self.owner, client_request_id=uuid4(), request_sha256=b'a'*32,
            prompt='Usage fixture', context_package={'schema_version':1,'snapshot':{},'instruction':{},'provenance':{}},
            context_sha256=b'b'*32, logical_model_id='jous.text.general.v1', supplier_id='supplier-a',
            supplier_native_model_id='native-a', underlying_provider='provider-a', admission_version='offline.v1',
            request_parameters={'schema_version':1,'route_id':'route-a','catalog_digest':'a',
                'route_snapshot':{},'limits':{},'execution':{}}, tokenizer_manifest_sha256=b'c'*32,
            template_branch='plain', token_bound_method='LOCAL_PROVISIONAL',
            token_bound_evidence={'schema_version':1,'asset_revision':'pinned','asset_hashes':{},
                'method':'LOCAL_PROVISIONAL','template_branch':'plain','input_token_upper_bound':1,
                'context_capacity':32768,'output_allowance':1024,'safety_margin':3277,
                'hosted_authority_state':'HOSTED_TOKEN_TEMPLATE_AUTHORITY_UNRESOLVED'},
            input_token_upper_bound=1, output_allowance=1024, safety_margin=3277,
            dispatch_claim_id=uuid4(), dispatch_deadline_at=now+timedelta(seconds=20))
        await self.admin.execute("""INSERT INTO public.tasks
            (id,organization_id,project_id,actor_user_id,client_request_id,request_sha256,prompt,
             context_package,context_sha256,logical_model_id,supplier_id,supplier_native_model_id,
             underlying_provider,admission_version,request_parameters,tokenizer_manifest_sha256,
             template_branch,token_bound_method,token_bound_evidence,input_token_upper_bound,
             output_allowance,safety_margin,dispatch_claim_id,dispatch_deadline_at)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11,$12,$13,$14,$15::jsonb,$16,
                   $17,$18,$19::jsonb,$20,$21,$22,$23,$24)""",
            *[self.task[key] for key in ("id","organization_id","project_id","actor_user_id","client_request_id",
              "request_sha256","prompt")], json.dumps(self.task["context_package"]), self.task["context_sha256"],
            self.task["logical_model_id"], self.task["supplier_id"], self.task["supplier_native_model_id"],
            self.task["underlying_provider"], self.task["admission_version"], json.dumps(self.task["request_parameters"]),
            self.task["tokenizer_manifest_sha256"], self.task["template_branch"], self.task["token_bound_method"],
            json.dumps(self.task["token_bound_evidence"]), self.task["input_token_upper_bound"],
            self.task["output_allowance"], self.task["safety_margin"], self.task["dispatch_claim_id"],
            self.task["dispatch_deadline_at"])
        self.execution = dict(id=uuid4(), task_id=self.task["id"], organization_id=self.org,
            project_id=self.project, actor_user_id=self.owner, dispatch_claim_id=self.task["dispatch_claim_id"],
            status="succeeded", response_text="ok", reported_model_id=None, reported_provider_id="provider-a",
            provider_request_id=None, provider_response_id=None, finish_reason=None,
            usage={"input_tokens":11,"output_tokens":7,"total_tokens":18}, usage_status="available",
            error_code=None, request_started_at=now, response_received_at=now)
        await self.admin.execute("""INSERT INTO public.executions
            (id,task_id,organization_id,project_id,actor_user_id,dispatch_claim_id,status,response_text,
             reported_provider_id,usage,usage_status,request_started_at,response_received_at)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11,$12,$13)""",
            self.execution["id"],self.execution["task_id"],self.org,self.project,self.owner,
            self.execution["dispatch_claim_id"],self.execution["status"],self.execution["response_text"],
            self.execution["reported_provider_id"],json.dumps(self.execution["usage"]),
            self.execution["usage_status"],self.execution["request_started_at"],self.execution["response_received_at"])

    async def asyncTearDown(self):
        try:
            await self.admin.execute("DELETE FROM public.usage_events WHERE organization_id=ANY($1::uuid[])", [self.org, self.other_org])
            await self.admin.execute("DELETE FROM public.executions WHERE organization_id=ANY($1::uuid[])", [self.org, self.other_org])
            await self.admin.execute("DELETE FROM public.tasks WHERE organization_id=ANY($1::uuid[])", [self.org, self.other_org])
            await self.admin.execute("DELETE FROM public.projects WHERE organization_id=ANY($1::uuid[])", [self.org, self.other_org])
            await self.admin.execute("DELETE FROM public.organization_memberships WHERE organization_id=ANY($1::uuid[])", [self.org, self.other_org])
            await self.admin.execute("DELETE FROM public.organizations WHERE id=ANY($1::uuid[])", [self.org, self.other_org])
            await self.admin.execute("DELETE FROM public.users WHERE id=ANY($1::uuid[])", [self.owner, self.other])
        finally:
            await self.runtime.close()
            await self.admin.close()

    async def _append(self, *, task=None, execution=None, version=None, supersedes=None):
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from jous_api.usage_events import normalize_execution, persist_usage_event
        task = task or SimpleNamespace(**self.task)
        execution = execution or SimpleNamespace(**self.execution, recorded_at=self.execution["response_received_at"])
        event = normalize_execution(task, execution,
            normalizer_version=version or "jous.execution-usage.v1",
            supersedes_usage_event_id=supersedes)
        engine = create_async_engine(self.runtime_url.replace("postgresql://", "postgresql+asyncpg://", 1))
        try:
            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as session, session.begin():
                await session.execute(__import__("sqlalchemy").text(
                    "SELECT set_config('jous.user_id',:user_id,true),set_config('jous.organization_id',:org_id,true)"),
                    {"user_id": str(self.owner), "org_id": str(self.org)})
                result = await persist_usage_event(session, event)
            return event
        finally:
            await engine.dispose()

    async def test_runtime_can_insert_and_replay_exact_event_once(self):
        event = await self._append()
        repeated = await self._append()
        self.assertEqual(event.usage_event_id, repeated.usage_event_id)
        self.assertEqual(await self.admin.fetchval("SELECT count(*) FROM public.usage_events WHERE execution_id=$1", self.execution["id"]), 1)

    async def test_runtime_rls_blocks_other_tenant_and_update_delete(self):
        event = await self._append()
        await self.runtime.execute("SELECT set_config('jous.user_id',$1,false),set_config('jous.organization_id',$2,false)",
                                   str(self.other),str(self.other_org))
        self.assertEqual(await self.runtime.fetchval("SELECT count(*) FROM public.usage_events WHERE usage_event_id=$1", event.usage_event_id), 0)
        import asyncpg
        with self.assertRaises(asyncpg.InsufficientPrivilegeError):
            await self.runtime.execute("UPDATE public.usage_events SET usage_status='PARTIAL' WHERE usage_event_id=$1",event.usage_event_id)
        with self.assertRaises(asyncpg.InsufficientPrivilegeError):
            await self.runtime.execute("DELETE FROM public.usage_events WHERE usage_event_id=$1",event.usage_event_id)

    async def test_composite_source_binding_rejects_forged_project(self):
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import text
        from jous_api.usage_events import normalize_execution, persist_usage_event
        forged_task = SimpleNamespace(**self.task)
        forged_execution = SimpleNamespace(**self.execution, recorded_at=self.execution["response_received_at"])
        forged_task.project_id = self.second_project
        forged_execution.project_id = self.second_project
        event = normalize_execution(forged_task, forged_execution)
        engine = create_async_engine(self.runtime_url.replace("postgresql://", "postgresql+asyncpg://", 1))
        try:
            maker = async_sessionmaker(engine, expire_on_commit=False)
            with self.assertRaises(SQLAlchemyError):
                async with maker() as session, session.begin():
                    await session.execute(text(
                        "SELECT set_config('jous.user_id',:user_id,true),set_config('jous.organization_id',:org_id,true)"),
                        {"user_id": str(self.owner), "org_id": str(self.org)})
                    await persist_usage_event(session, event)
        finally:
            await engine.dispose()
        self.assertEqual(await self.admin.fetchval(
            "SELECT count(*) FROM public.usage_events WHERE execution_id=$1", self.execution["id"]), 0)

    async def test_runtime_cannot_invent_usage_against_execution_source(self):
        from dataclasses import replace
        import hashlib
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import text
        from jous_api.usage_events import canonical_json, normalize_execution, persist_usage_event
        event = normalize_execution(SimpleNamespace(**self.task),
            SimpleNamespace(**self.execution, recorded_at=self.execution["response_received_at"]))
        payload = json.loads(event.canonical_payload)
        payload["input_tokens"] = 999
        encoded = canonical_json(payload)
        forged = replace(event, input_tokens=999, canonical_payload=encoded,
                         evidence_sha256=hashlib.sha256(encoded.encode("utf-8")).digest())
        engine = create_async_engine(self.runtime_url.replace("postgresql://", "postgresql+asyncpg://", 1))
        try:
            maker = async_sessionmaker(engine, expire_on_commit=False)
            with self.assertRaises(SQLAlchemyError):
                async with maker() as session, session.begin():
                    await session.execute(text(
                        "SELECT set_config('jous.user_id',:user_id,true),set_config('jous.organization_id',:org_id,true)"),
                        {"user_id": str(self.owner), "org_id": str(self.org)})
                    await persist_usage_event(session, forged)
        finally:
            await engine.dispose()
        self.assertEqual(await self.admin.fetchval(
            "SELECT count(*) FROM public.usage_events WHERE execution_id=$1", self.execution["id"]), 0)

    async def test_correction_is_append_only_and_competing_successor_rejected(self):
        original = await self._append()
        corrected = await self._append(version="jous.execution-usage.v2",supersedes=original.usage_event_id)
        from sqlalchemy.exc import IntegrityError
        with self.assertRaises(IntegrityError) as rejected:
            await self._append(version="jous.execution-usage.v3",supersedes=original.usage_event_id)
        self.assertEqual(rejected.exception.orig.sqlstate, "23505")
        self.assertEqual(await self.admin.fetchval("SELECT count(*) FROM public.usage_events WHERE execution_id=$1", self.execution["id"]), 2)
        self.assertEqual(corrected.supersedes_usage_event_id, original.usage_event_id)

    async def test_runtime_privilege_matrix_and_rls_are_installed(self):
        state = await self.admin.fetchrow("SELECT relrowsecurity,relforcerowsecurity,relowner::regrole::text FROM pg_class WHERE oid='public.usage_events'::regclass")
        self.assertEqual(tuple(state), (True,True,"postgres"))
        self.assertFalse(await self.admin.fetchval("SELECT has_table_privilege('jous_runtime','public.usage_events','UPDATE') OR has_table_privilege('jous_runtime','public.usage_events','DELETE')"))
        self.assertFalse(await self.admin.fetchval("SELECT has_table_privilege('jous_security_reader','public.usage_events','SELECT')"))
        runtime_columns = await self.admin.fetch("""SELECT a.attname,
            has_column_privilege('jous_runtime',c.oid,a.attnum,'SELECT'),
            has_column_privilege('jous_runtime',c.oid,a.attnum,'INSERT'),
            has_column_privilege('jous_runtime',c.oid,a.attnum,'UPDATE'),
            has_column_privilege('jous_runtime',c.oid,a.attnum,'REFERENCES')
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
            WHERE n.nspname='public' AND c.relname='usage_events' ORDER BY a.attnum""")
        self.assertEqual(len(runtime_columns), 30)
        for name, can_select, can_insert, can_update, can_reference in runtime_columns:
            self.assertTrue(can_select, name)
            self.assertEqual(can_insert, name != "recorded_at", name)
            self.assertFalse(can_update, name)
            self.assertFalse(can_reference, name)
        self.assertFalse(await self.admin.fetchval("""SELECT has_table_privilege(
            'jous_runtime','public.usage_events','SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')"""))
        for role in ("anon", "authenticated", "service_role"):
            self.assertFalse(await self.admin.fetchval(
                "SELECT has_table_privilege($1,'public.usage_events','SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')", role))
        self.assertFalse(await self.admin.fetchval("""SELECT EXISTS (
            SELECT 1 FROM pg_default_acl d CROSS JOIN LATERAL aclexplode(d.defaclacl) a
            WHERE d.defaclrole=(SELECT oid FROM pg_roles WHERE rolname='postgres')
              AND d.defaclnamespace IN (0,(SELECT oid FROM pg_namespace WHERE nspname='public'))
              AND d.defaclobjtype='r' AND a.grantee IN
                ((SELECT oid FROM pg_roles WHERE rolname='anon'),
                 (SELECT oid FROM pg_roles WHERE rolname='authenticated'),
                 (SELECT oid FROM pg_roles WHERE rolname='service_role'))
        )"""))
        await self.admin.execute("CREATE TABLE public.usage_events_acl_probe(id integer)")
        try:
            for role in ("anon", "authenticated", "service_role"):
                self.assertFalse(await self.admin.fetchval(
                    "SELECT has_table_privilege($1,'public.usage_events_acl_probe','SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')", role))
        finally:
            await self.admin.execute("DROP TABLE public.usage_events_acl_probe")
        for relation in ("tasks", "executions", "route_decisions"):
            for role in ("anon", "authenticated", "service_role"):
                self.assertFalse(await self.admin.fetchval(
                    "SELECT has_table_privilege($1,format('public.%I',$2::text),'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')",
                    role, relation))

    async def test_catalog_types_match_model_semantically(self):
        from jous_api.usage_event_validation import _expected_columns, _types_equivalent
        expected = _expected_columns()
        rows = await self.admin.fetch("""SELECT a.attname,format_type(a.atttypid,a.atttypmod),
            a.attnotnull,pg_get_expr(d.adbin,d.adrelid)
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_attribute a ON a.attrelid=c.oid
            LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
            WHERE n.nspname='public' AND c.relname='usage_events'
              AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum""")
        self.assertEqual(len(rows), 30)
        self.assertEqual({row['attname'] for row in rows}, set(expected))
        for row in rows:
            type_name, not_null, default = expected[row['attname']]
            self.assertTrue(_types_equivalent(type_name, row['format_type']), row['attname'])
            self.assertEqual(row['attnotnull'], not_null, row['attname'])
            if row['attname'] == 'recorded_at':
                self.assertIn('statement_timestamp', row['pg_get_expr'])
            else:
                self.assertIsNone(row['pg_get_expr'], row['attname'])

    async def test_validator_acl_queries_accept_hardened_relation_and_defaults(self):
        from sqlalchemy import text
        from jous_api.usage_event_validation import DEFAULT_ACL_SQL, ROLE_RELATION_AUTHORITY_SQL
        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine(self.admin_url.replace("postgresql://", "postgresql+asyncpg://", 1))
        try:
            async with engine.connect() as connection:
                self.assertEqual(await connection.scalar(text(DEFAULT_ACL_SQL)), 0)
                self.assertEqual(await connection.scalar(text(ROLE_RELATION_AUTHORITY_SQL)), 0)
        finally:
            await engine.dispose()

    async def _finalize_through_runtime(self, *, fail_after_execution=False):
        from unittest.mock import patch
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from jous_api.task_service import SQLUnit
        from jous_supply.contracts import Outcome

        await self.admin.execute("DELETE FROM public.executions WHERE id=$1", self.execution["id"])
        engine = create_async_engine(self.runtime_url.replace("postgresql://", "postgresql+asyncpg://", 1))
        try:
            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as session:
                try:
                    async with session.begin():
                        await session.execute(text(
                            "SELECT set_config('jous.user_id',:user_id,true),set_config('jous.organization_id',:org_id,true)"),
                            {"user_id": str(self.owner), "org_id": str(self.org)})
                        task_row = (await session.execute(text(
                            "SELECT * FROM public.tasks WHERE id=:task_id"), {"task_id": self.task["id"]})).mappings().one()
                        task = SimpleNamespace(**task_row)
                        unit = SQLUnit(session, SimpleNamespace(id=self.project, organization_id=self.org), self.owner)
                        observed = max(datetime.now(timezone.utc) - timedelta(seconds=1), task.created_at)
                        outcome = Outcome("succeeded", response_text="ok",
                            usage={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
                            usage_status="available", request_started_at=observed,
                            response_received_at=observed)
                        if fail_after_execution:
                            with patch("jous_api.task_service.persist_usage_event", side_effect=RuntimeError("simulated persistence interruption")):
                                await unit.finalize(task, outcome)
                        else:
                            await unit.finalize(task, outcome)
                except RuntimeError:
                    if not fail_after_execution:
                        raise
        finally:
            await engine.dispose()

    async def test_execution_and_usage_commit_atomically(self):
        await self._finalize_through_runtime()
        self.assertEqual(await self.admin.fetchval(
            "SELECT count(*) FROM public.executions WHERE task_id=$1", self.task["id"]), 1)
        self.assertEqual(await self.admin.fetchval(
            "SELECT count(*) FROM public.usage_events WHERE task_id=$1", self.task["id"]), 1)

    async def test_interrupted_usage_write_rolls_back_execution(self):
        await self._finalize_through_runtime(fail_after_execution=True)
        self.assertEqual(await self.admin.fetchval(
            "SELECT count(*) FROM public.executions WHERE task_id=$1", self.task["id"]), 0)
        self.assertEqual(await self.admin.fetchval(
            "SELECT count(*) FROM public.usage_events WHERE task_id=$1", self.task["id"]), 0)
