"""PREPARED ONLY: explicit, separately authorized disposable PostgreSQL gate.

Never included by the offline gate. Requires an isolated loopback PostgreSQL
cluster bootstrapped through exact 0002 with reviewed roles/Step 7 prerequisites.
The admin URL is a disposable-cluster superuser; runtime URL is jous_runtime.
The database comment must be the explicit disposable sentinel below. Migration
0003 is applied once from exact 0002, never downgraded or applied elsewhere.
"""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from uuid import uuid4
from datetime import datetime,timedelta,timezone

ROOT=Path(__file__).resolve().parents[2]
ENABLED=os.environ.get('JOUS_V12_DISPOSABLE_AUTHORIZED')=='YES'


def targets():
    if not ENABLED or os.environ.get('JOUS_V12_DISPOSABLE_ALLOW_MIGRATION')!='YES':
        raise RuntimeError('Separate disposable migration/security authorization required')
    values=[os.environ.get('JOUS_V12_DISPOSABLE_'+kind+'_URL','') for kind in ('ADMIN','RUNTIME')]
    parsed=[urlsplit(v) for v in values]
    for url in parsed:
        if url.scheme!='postgresql' or url.hostname!='127.0.0.1' or not url.path.startswith('/jous_v12_disposable_') or url.query or url.fragment or not url.username:
            raise RuntimeError('Explicit isolated loopback disposable target required')
    if (parsed[0].hostname,parsed[0].port,parsed[0].path)!=(parsed[1].hostname,parsed[1].port,parsed[1].path) or parsed[1].username!='jous_runtime' or parsed[0].username==parsed[1].username:
        raise RuntimeError('Separated admin/runtime principals on one disposable target required')
    return values


@unittest.skipUnless(ENABLED,'Separate disposable PostgreSQL authorization required; DO NOT run offline')
class DisposableProductSecurity(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.urls=targets()
        async def migrate():
            import asyncpg
            connection=await asyncpg.connect(cls.urls[0])
            try:
                if not await connection.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname=current_user"):
                    raise RuntimeError('Isolated fixture administrator required')
                if await connection.fetchval("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")!='JOUS_V12_DISPOSABLE_AUTHORIZED':
                    raise RuntimeError('Disposable database sentinel missing')
                if await connection.fetchval('SELECT version_num FROM public.alembic_version')!='0002_runtime_rls':
                    raise RuntimeError('Gate requires exact pristine 0002 predecessor; no reset/repair performed')
            finally:await connection.close()
            from sqlalchemy.ext.asyncio import create_async_engine
            from alembic.config import Config
            from alembic import command
            engine=create_async_engine(cls.urls[0].replace('postgresql://','postgresql+asyncpg://',1))
            try:
                async with engine.begin() as conn:
                    def upgrade(sync):
                        cfg=Config(str(ROOT/'services/api/alembic.ini'));cfg.attributes['connection']=sync
                        command.upgrade(cfg,'0003_project_tasks_executions')
                    await conn.run_sync(upgrade)
            finally:await engine.dispose()
        asyncio.run(migrate())

    async def asyncSetUp(self):
        import asyncpg
        self.admin=await asyncpg.connect(self.urls[0]);self.runtime=await asyncpg.connect(self.urls[1])
        self.owner,self.member,self.other,self.org,self.other_org,self.project,self.second,self.foreign=[uuid4() for _ in range(8)]
        self.seed_users=[self.owner,self.member,self.other];self.seed_orgs=[self.org,self.other_org]
        for user in self.seed_users:await self.admin.execute('INSERT INTO public.users(id) VALUES($1)',user)
        for org in self.seed_orgs:await self.admin.execute("INSERT INTO public.organizations(id,name) VALUES($1,'Disposable')",org)
        for user,org,role in [(self.owner,self.org,'owner'),(self.member,self.org,'member'),(self.other,self.other_org,'owner')]:
            await self.admin.execute('INSERT INTO public.organization_memberships(id,user_id,organization_id,role) VALUES($1,$2,$3,$4)',uuid4(),user,org,role)
        for project,org in [(self.project,self.org),(self.second,self.org),(self.foreign,self.other_org)]:
            await self.admin.execute("INSERT INTO public.projects(id,organization_id,name) VALUES($1,$2,'Disposable')",project,org)
        await self.context(self.owner,self.org)

    async def asyncTearDown(self):
        # Only this test's UUID-scoped fixtures; never truncate or reset a database.
        try:
            for table in ('executions','tasks','projects','organization_memberships'):
                await self.admin.execute(f'DELETE FROM public.{table} WHERE organization_id=ANY($1::uuid[])',self.seed_orgs)
            await self.admin.execute('DELETE FROM public.organizations WHERE id=ANY($1::uuid[])',self.seed_orgs)
            await self.admin.execute('DELETE FROM public.users WHERE id=ANY($1::uuid[])',self.seed_users)
        finally:
            await self.runtime.close();await self.admin.close()

    async def context(self,user,org,connection=None):
        await (connection or self.runtime).execute("SELECT set_config('jous.user_id',$1,false),set_config('jous.organization_id',$2,false)",str(user),str(org))

    def claim(self,**changes):
        now=datetime.now(timezone.utc)
        value=dict(id=uuid4(),organization_id=self.org,project_id=self.project,actor_user_id=self.owner,
            client_request_id=uuid4(),request_sha256=b'a'*32,prompt='Task',
            context_package={'schema_version':1,'snapshot':{},'instruction':{},'provenance':{}},context_sha256=b'b'*32,
            logical_model_id='jous.text.general.v1',supplier_id='hugging_face',supplier_native_model_id='Qwen/Qwen3-32B:deepinfra',underlying_provider='DeepInfra',admission_version='offline.v1',
            request_parameters={'schema_version':1,'route_id':'offline','catalog_digest':'a','route_snapshot':{},'limits':{},'execution':{}},
            tokenizer_manifest_sha256=b'c'*32,template_branch='non-thinking',token_bound_method='LOCAL_PROVISIONAL',
            token_bound_evidence={'schema_version':1,'asset_revision':'pinned','asset_hashes':{},'method':'LOCAL_PROVISIONAL','template_branch':'non-thinking','input_token_upper_bound':1,'context_capacity':32768,'output_allowance':1024,'safety_margin':3277,'hosted_authority_state':'HOSTED_TOKEN_TEMPLATE_AUTHORITY_UNRESOLVED'},
            input_token_upper_bound=1,output_allowance=1024,safety_margin=3277,dispatch_claim_id=uuid4(),dispatch_deadline_at=now+timedelta(seconds=39))
        value.update(changes);return value

    def terminal(self,task,**changes):
        value=dict(id=uuid4(),task_id=task['id'],organization_id=task['organization_id'],project_id=task['project_id'],actor_user_id=task['actor_user_id'],dispatch_claim_id=task['dispatch_claim_id'],status='known_error',response_text=None,reported_model_id=None,reported_provider_id=None,provider_request_id=None,provider_response_id=None,finish_reason=None,usage=None,usage_status='unavailable',error_code='not_dispatched',request_started_at=None,response_received_at=None)
        value.update(changes);return value

    async def insert(self,table,value,connection=None,conflict=False):
        # Identifiers are harness-owned; values are always bound parameters.
        assert table in ('tasks','executions')
        columns=list(value);args=[];slots=[]
        for i,key in enumerate(columns,1):
            val=value[key]
            if key in ('context_package','request_parameters','token_bound_evidence','usage') and val is not None:args.append(json.dumps(val));slots.append(f'${i}::jsonb')
            else:args.append(val);slots.append(f'${i}')
        suffix=' ON CONFLICT ON CONSTRAINT uq_tasks_request DO NOTHING' if conflict else ''
        return await (connection or self.runtime).fetchval(f"INSERT INTO public.{table} ({','.join(columns)}) VALUES ({','.join(slots)}){suffix} RETURNING id",*args)

    async def denied(self,operation):
        import asyncpg
        with self.assertRaises((asyncpg.InsufficientPrivilegeError,asyncpg.CheckViolationError,asyncpg.ForeignKeyViolationError,asyncpg.UniqueViolationError)):
            async with self.runtime.transaction():await operation()

    async def validate(self):
        from jous_api.config import Settings
        from jous_api.database import Database
        from jous_api.product_runtime_validation import validate_product_runtime
        from pydantic import SecretStr
        db=Database(Settings(environment='test',database_url=SecretStr(self.urls[1])),validator=validate_product_runtime)
        try:await db.check()
        finally:await db.dispose()

    async def test_catalog_revision_validator_and_exact_rls(self):
        self.assertEqual(await self.admin.fetchval('SELECT version_num FROM public.alembic_version'),'0003_project_tasks_executions')
        await self.validate() # Strict source-owned expressions; no permissive pg_get_expr adaptation.
        tables=await self.admin.fetch("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace AND relname IN ('tasks','executions')")
        self.assertEqual(len(tables),2)
        for row in tables:self.assertTrue(row['relrowsecurity']);self.assertTrue(row['relforcerowsecurity'])
        policies=await self.admin.fetch("SELECT tablename,policyname,cmd,roles FROM pg_policies WHERE schemaname='public' AND tablename IN ('tasks','executions')")
        self.assertEqual({(r['tablename'],r['policyname'],r['cmd'],tuple(r['roles'])) for r in policies},{(t,f'jous_{t}_{c.lower()}',c,('jous_runtime',)) for t in ('tasks','executions') for c in ('SELECT','INSERT')})

    async def test_owner_member_reads_cross_tenant_project_actor_and_gucs(self):
        task=self.claim();await self.insert('tasks',task)
        self.assertEqual(await self.runtime.fetchval('SELECT id FROM public.tasks WHERE id=$1',task['id']),task['id'])
        self.assertEqual(await self.runtime.fetchval('SELECT count(*) FROM public.tasks WHERE id=$1 AND project_id=$2',task['id'],self.second),0)
        await self.context(self.member,self.org)
        self.assertEqual(await self.runtime.fetchval('SELECT count(*) FROM public.tasks WHERE id=$1',task['id']),1)
        await self.denied(lambda:self.insert('tasks',self.claim(actor_user_id=self.member)))
        await self.context(self.other,self.other_org)
        self.assertEqual(await self.runtime.fetchval('SELECT count(*) FROM public.tasks WHERE id=$1',task['id']),0)
        await self.denied(lambda:self.insert('tasks',self.claim()))
        await self.context(self.owner,self.org)
        await self.denied(lambda:self.insert('tasks',self.claim(actor_user_id=self.member)))
        await self.denied(lambda:self.insert('tasks',self.claim(project_id=self.foreign)))
        for malformed in ('','not-a-uuid'):
            await self.context(malformed,malformed)
            self.assertEqual(await self.runtime.fetchval('SELECT count(*) FROM public.tasks'),0)
            await self.denied(lambda:self.insert('tasks',self.claim()))

    async def test_active_member_cannot_finalize_existing_owner_task(self):
        import asyncpg
        task=self.claim()
        await self.insert('tasks',task) # Owner claim with an otherwise valid binding.
        await self.context(self.member,self.org)
        self.assertEqual(await self.runtime.fetchval('SELECT count(*) FROM public.tasks WHERE id=$1',task['id']),1)
        with self.assertRaises(asyncpg.InsufficientPrivilegeError):
            async with self.runtime.transaction():
                await self.insert('executions',self.terminal(task))
        self.assertEqual(await self.runtime.fetchval('SELECT count(*) FROM public.executions WHERE task_id=$1',task['id']),0)

    async def test_genuinely_unset_context_denies_runtime_reads_and_inserts(self):
        import asyncpg
        fresh=await asyncpg.connect(self.urls[1])
        try:
            # No context() or set_config() call on this fresh physical connection.
            self.assertIsNone(await fresh.fetchval("SELECT current_setting('jous.user_id',true)"))
            self.assertIsNone(await fresh.fetchval("SELECT current_setting('jous.organization_id',true)"))
            self.assertEqual(await fresh.fetchval('SELECT count(*) FROM public.tasks'),0)
            self.assertEqual(await fresh.fetchval('SELECT count(*) FROM public.executions'),0)
            with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                async with fresh.transaction():await self.insert('tasks',self.claim(),fresh)
        finally:await fresh.close()

    async def test_exact_execution_binding_and_revocation(self):
        task=self.claim();await self.insert('tasks',task)
        for change in ({'task_id':uuid4()},{'project_id':self.second},{'actor_user_id':self.member},{'dispatch_claim_id':uuid4()},{'organization_id':self.other_org}):
            await self.denied(lambda change=change:self.insert('executions',self.terminal(task,**change)))
        await self.admin.execute("UPDATE public.organization_memberships SET status='inactive' WHERE user_id=$1 AND organization_id=$2",self.owner,self.org)
        await self.denied(lambda:self.insert('executions',self.terminal(task)))
        await self.admin.execute("UPDATE public.organization_memberships SET status='active' WHERE user_id=$1 AND organization_id=$2",self.owner,self.org)
        await self.insert('executions',self.terminal(task))

    async def test_concurrent_claim_and_terminal_uniqueness(self):
        import asyncpg
        task=self.claim()
        async def claim(value):
            c=await asyncpg.connect(self.urls[1])
            try:
                await self.context(self.owner,self.org,c)
                async with c.transaction():return await self.insert('tasks',value,c,conflict=True)
            finally:await c.close()
        other={**task,'id':uuid4(),'dispatch_claim_id':uuid4()}
        results=await asyncio.gather(claim(task),claim(other))
        self.assertEqual(sum(x is not None for x in results),1)
        winner=task if results[0] else other
        different={**other,'id':uuid4(),'dispatch_claim_id':uuid4(),'request_sha256':b'z'*32}
        self.assertIsNone(await claim(different))
        stored=await self.runtime.fetchval('SELECT request_sha256 FROM public.tasks WHERE id=$1',winner['id'])
        self.assertNotEqual(stored,different['request_sha256']) # Application must return conflict, never identity.
        async def terminal():
            c=await asyncpg.connect(self.urls[1])
            try:
                await self.context(self.owner,self.org,c)
                try:
                    async with c.transaction():await self.insert('executions',self.terminal(winner),c)
                    return True
                except asyncpg.UniqueViolationError:return False
            finally:await c.close()
        self.assertEqual(sorted(await asyncio.gather(terminal(),terminal())),[False,True])

    async def test_composite_fk_and_restrictive_delete(self):
        task=self.claim();await self.insert('tasks',task)
        import asyncpg
        for table,key in [('projects',self.project),('users',self.owner),('organizations',self.org)]:
            with self.assertRaises(asyncpg.ForeignKeyViolationError):await self.admin.execute(f'DELETE FROM public.{table} WHERE id=$1',key)
        bad=self.claim(project_id=self.foreign)
        with self.assertRaises(asyncpg.ForeignKeyViolationError):await self.insert('tasks',bad,self.admin)

    async def test_effective_grants_and_runtime_mutation_denials(self):
        for table in ('tasks','executions'):
            for privilege in ('UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'):
                self.assertFalse(await self.runtime.fetchval('SELECT has_table_privilege(current_user,$1,$2)','public.'+table,privilege))
            self.assertFalse(await self.runtime.fetchval("SELECT has_any_column_privilege('jous_security_reader',$1,'SELECT,INSERT,UPDATE,REFERENCES')",'public.'+table))
            for query in (f'UPDATE public.{table} SET id=id',f'DELETE FROM public.{table}',f'TRUNCATE public.{table}'):
                await self.denied(lambda query=query:self.runtime.execute(query))
        self.assertEqual(await self.admin.fetchval("SELECT count(*) FROM information_schema.role_column_grants WHERE table_schema='public' AND table_name IN ('tasks','executions') AND grantee='PUBLIC'"),0)

    async def test_negative_catalog_policy_object_public_and_inherited_grants(self):
        from jous_api.database import DatabaseUnavailable
        mutations=[
            ('GRANT SELECT(id) ON public.tasks TO PUBLIC','REVOKE SELECT(id) ON public.tasks FROM PUBLIC'),
            ('GRANT UPDATE(prompt) ON public.tasks TO jous_runtime','REVOKE UPDATE(prompt) ON public.tasks FROM jous_runtime'),
            ('ALTER TABLE public.tasks NO FORCE ROW LEVEL SECURITY','ALTER TABLE public.tasks FORCE ROW LEVEL SECURITY'),
            ('CREATE POLICY unexpected ON public.tasks FOR SELECT TO jous_runtime USING (true)','DROP POLICY unexpected ON public.tasks'),
            ('CREATE TABLE public.unexpected_v12(id uuid); GRANT SELECT ON public.unexpected_v12 TO jous_runtime','DROP TABLE public.unexpected_v12'),
            ('CREATE ROLE jous_v12_bad_priv NOLOGIN; GRANT UPDATE(prompt) ON public.tasks TO jous_v12_bad_priv; GRANT jous_v12_bad_priv TO jous_runtime','REVOKE jous_v12_bad_priv FROM jous_runtime; REVOKE ALL ON public.tasks FROM jous_v12_bad_priv; REVOKE UPDATE(prompt) ON public.tasks FROM jous_v12_bad_priv; DROP ROLE jous_v12_bad_priv')]
        for change,undo in mutations:
            try:
                await self.admin.execute(change)
                with self.assertRaises(DatabaseUnavailable):await self.validate()
            finally:await self.admin.execute(undo)

    async def test_actual_null_usage_and_timestamp_check_shapes(self):
        task=self.claim();await self.insert('tasks',task)
        now=datetime.now(timezone.utc)
        bad=[
            ({'status':'known_error','error_code':None},'ck_executions_outcome_shape'),
            ({'status':'unknown','error_code':None},'ck_executions_outcome_shape'),
            ({'response_text':None},'ck_executions_outcome_shape'),
            ({'usage_status':'available','usage':None},'ck_executions_usage_status'),
            ({'usage_status':'unavailable','usage':{'input_tokens':1}},'ck_executions_usage_status'),
            ({'usage_status':'partial','usage':[]},'ck_executions_usage_shape'),
            ({'request_started_at':now,'response_received_at':now-timedelta(seconds=1)},'ck_executions_timestamp_order'),
            ({'request_started_at':None,'response_received_at':now},'ck_executions_timestamp_order'),
            ({'recorded_at':now-timedelta(days=1),'request_started_at':now},'ck_executions_timestamp_order')]
        for change,constraint in bad:
            # Superuser bypasses RLS, not CHECKs. A valid empty success isolates
            # usage/timestamp checks from the special not_dispatched outcome.
            import asyncpg
            value=self.terminal(task,status='succeeded',error_code=None,response_text='')
            value.update(change)
            with self.assertRaises(asyncpg.CheckViolationError) as error:
                await self.insert('executions',value,self.admin)
            self.assertEqual(error.exception.constraint_name,constraint)
        await self.insert('executions',self.terminal(task,status='succeeded',error_code=None,response_text=''))
