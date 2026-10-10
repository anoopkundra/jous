"""Guarded offline authority, transport and canary tests. No real credentials."""
import sys
import os
from pathlib import Path
import importlib.util
ROOT = Path(__file__).resolve().parents[1]
os.environ = dict(SystemRoot='C:/Windows', TEMP='C:/Users/anoop/AppData/Local/Temp', TMP='C:/Users/anoop/AppData/Local/Temp')
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value
foundation = module('runtime_guard', 'tests/test_step7_managed_readonly_diagnostic.py')
import platform
import asyncio
import copy
import hashlib
import inspect
import io
import json
import ssl
import unittest
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'services/api/src')]
with patch.object(platform, 'uname', return_value=foundation.TEST_UNAME):
    import test_step7_atomic_runner as fixture
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'services/api/src')]
from jous_api import runtime_policy as policy, runtime_transport as transport
from jous_api import step7_execution_contract as f
from jous_api.config import Settings
from jous_api.database import Database, DatabaseUnavailable
canary = module('runtime_canary_under_test', 'services/api/infrastructure/validate_runtime_canary.py')

URL = 'postgresql://jous_runtime.aqcixpoorbhjgvdkdjqd:INERT@aws-0-ca-central-1.pooler.supabase.com:5432/postgres'

class PolicyConnection:
    def __init__(self):
        self.material = copy.deepcopy(fixture.final_material(True))
        self.rows = fixture.synthetic_policies(None)
        self.events = []
    def execute(self, statement, parameters=None):
        sql = str(statement)
        self.events.append(sql)
        if sql == 'SET LOCAL search_path = pg_catalog, pg_temp':
            return None
        if sql == policy.step7_catalog.POLICY_SQL:
            return fixture.Result(copy.deepcopy(self.rows))
        if sql not in self.material:
            raise AssertionError('UNEXPECTED_QUERY')
        return fixture.Result(copy.deepcopy(self.material[sql]))

    def begin_nested(self):
        return MagicMock()
    def scalar(self, statement):
        assert str(statement) == "SELECT pg_catalog.current_setting('search_path')"
        return 'pg_catalog, pg_temp'

class PolicyAuthorityTests(unittest.TestCase):
    def test_frozen_authority_exact_pass_and_observation_last(self):
        c = PolicyConnection()
        self.assertIsInstance(policy.verify(c), f.VerifiedPolicyContinuity)
        self.assertEqual(c.events[-1], policy.step7_catalog.POLICY_SQL)
        self.assertIn(f.CREATED_SQL, c.events[:-1])
    def test_missing_authority_rejected_before_observation(self):
        c = PolicyConnection()
        with patch.object(f, 'load_final_contract', side_effect=FileNotFoundError), self.assertRaises(FileNotFoundError):
            policy.verify(c)
        self.assertEqual(c.events, [])
    def test_hash_mismatch(self):
        connection = PolicyConnection()
        original = Path.read_bytes
        with patch.object(Path, 'read_bytes', lambda p: original(p)+b' ' if p.name=='step7_policy_template_contract.json' else original(p)):
            with self.assertRaisesRegex(f.ContractRejected, 'CONTRACT_HASH'):
                policy.verify(connection)
    def test_malformed_authority(self):
        data = f._read(f.load_final_contract(), f.ApprovedFinalContract)
        data.pop('builtins')
        with patch.object(f, 'load', return_value=data), self.assertRaises(f.ContractRejected):
            policy.verify(PolicyConnection())
    def test_policy_mutations(self):
        for mutate in (lambda r:r[0].update(using_tree='{MUTATED}'), lambda r:r.pop(),
                       lambda r:r.append(dict(r[0], policy_oid=9999)),
                       lambda r:r[0].update(role_oids=[999]), lambda r:r[0].update(owner_oid=999)):
            c = PolicyConnection(); mutate(c.rows)
            with self.subTest(rows=len(c.rows)), self.assertRaises(f.ContractRejected):
                policy.verify(c)
    def test_bindings_cannot_come_from_policy(self):
        c = PolicyConnection();c.material[f.RELATION_SQL][0]['name']='substituted'
        with self.assertRaises(f.ContractRejected):policy.verify(c)
        self.assertNotIn(policy.step7_catalog.POLICY_SQL,c.events)
    def test_same_migration_runtime_authority(self):
        self.assertEqual(f.POLICY_SHA, fixture.runner.execution_contract().POLICY_SHA)
        runtime = PolicyConnection();policy.verify(runtime)
        self.assertNotIn('APPROVED_POLICY_CONTRACT',inspect.getsource(policy))
        self.assertIn('verify_policy_rows',inspect.getsource(policy))
    def test_missing_helper_or_changed_owner(self):
        for mutation in (lambda m:m[f.CREATED_SQL].pop(), lambda m:m[f.CREATED_SQL][0].update(proowner=999)):
            c=PolicyConnection();mutation(c.material)
            with self.assertRaises(f.ContractRejected):policy.verify(c)

class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pem,cls.der=fixture.certificate('offline runtime CA')
    def context(self):
        with patch.object(transport,'CA_SHA',hashlib.sha256(self.der).hexdigest()):
            return transport.pinned_context(self.pem)
    def test_valid_pinned_tls(self):
        context=self.context()
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.get_ca_certs(binary_form=True),[self.der])
    def test_real_pin_rejects_synthetic_ca(self):
        with self.assertRaises(transport.TransportRejected):transport.pinned_context(self.pem)
    def test_bundle_or_malformed_ca(self):
        for pem in (self.pem+self.pem,'invalid',self.pem+'unapproved'):
            with self.assertRaises(transport.TransportRejected):transport.pinned_context(pem)
    def test_disabled_verification_and_hostname(self):
        for fault in ('hostname','certificate'):
            context=self.context();context.check_hostname=False
            if fault=='certificate':context.verify_mode=ssl.CERT_NONE
            with patch.object(transport,'CA_SHA',hashlib.sha256(self.der).hexdigest()),self.assertRaises(transport.TransportRejected):
                transport.validate_context(context,self.der)
    def test_valid_target(self):transport.validate_target(URL)
    def test_wrong_target_and_admin(self):
        for url in (URL.replace('jous_runtime.','postgres.'),URL.replace('pooler.supabase.com','attacker.invalid'),
                    URL.replace(':5432',':6543'),URL.replace('/postgres','/other'),URL+'?ssl=disable',URL+'#fragment','invalid'):
            with self.assertRaises(transport.TransportRejected):transport.validate_target(url)
    def test_pool_receives_secure_arguments(self):
        settings=Settings(environment='production',database_url=URL,database_ca_file='offline-public-ca')
        context=self.context()
        with patch.object(transport.Path,'read_text',return_value=self.pem),patch.object(transport,'CA_SHA',hashlib.sha256(self.der).hexdigest()),\
             patch('jous_api.database.create_async_engine',return_value=MagicMock()) as create:
            Database(settings)
        args=create.call_args.kwargs
        self.assertEqual(args['pool_size'],2);self.assertEqual(args['max_overflow'],0)
        self.assertEqual(args['connect_args']['ssl'].verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(args['connect_args']['ssl'].check_hostname)
        self.assertEqual(args['connect_args']['target_session_attrs'],'any')
        self.assertNotIn('ssl',str(create.call_args.args[0]))
    def test_no_insecure_fallback_or_pool_on_error(self):
        settings=Settings(environment='production',database_url=URL)
        with patch('jous_api.database.create_async_engine') as create,self.assertRaises(DatabaseUnavailable):Database(settings)
        create.assert_not_called()
    def test_missing_authority_prevents_pool(self):
        with patch('jous_api.database.step7_execution_contract.load_final_contract',side_effect=FileNotFoundError),\
             patch('jous_api.database.create_async_engine') as create,self.assertRaises(FileNotFoundError):
            Database(Settings(environment='production',database_url=URL))
        create.assert_not_called()
    def test_approved_target_pin_cannot_silently_diverge(self):
        self.assertEqual(transport.CA_SHA,fixture.runner.CA_SHA)
        self.assertEqual(transport.PROJECT,fixture.runner.PROJECT)
        self.assertEqual(transport.HOST,foundation.d.HOST)
    def test_real_driver_parsing_keeps_explicit_tls_and_no_discovery(self):
        import asyncpg.connect_utils as driver
        context=self.context()
        kwargs=dict(dsn=None,host=transport.HOST,port=5432,user='jous_runtime.'+transport.PROJECT,
                    password='INERT',passfile=None,database='postgres',command_timeout=None,
                    statement_cache_size=100,max_cached_statement_lifetime=300,
                    max_cacheable_statement_size=15360,ssl=context,direct_tls=False,
                    server_settings=None,target_session_attrs='any',krbsrvname='postgres',
                    gsslib='sspi',service=None,servicefile=None)
        addresses,parameters,_=driver._parse_connect_arguments(**kwargs)
        self.assertIs(parameters.ssl,context)
        self.assertEqual(addresses,[(transport.HOST,5432)])
        self.assertEqual(parameters.target_session_attrs,driver.SessionAttribute.any)
        self.assertNotIn(parameters.sslmode,(driver.SSLMode.allow,driver.SSLMode.prefer))

def fixture_data():
    return dict(schema='jous.runtime-canary-fixtures.v1',project=transport.PROJECT,
                issuer='https://approved.invalid/auth/v1',actors=[dict(subject='actor-'+str(i),
                    user=str(UUID(int=i+1)),organization=str(UUID(int=i+11)),project=str(UUID(int=i+21))) for i in (0,1)])

class CanaryTests(unittest.IsolatedAsyncioTestCase):
    def fixture(self):
        data=fixture_data();raw=json.dumps(data).encode()
        with patch.object(Path,'read_bytes',return_value=raw):return canary.load_manifest('offline',hashlib.sha256(raw).hexdigest())
    def settings(self):return Settings(environment='production',database_url=URL,auth_issuer=fixture_data()['issuer'],
        auth_jwks_url=fixture_data()['issuer']+'/.well-known/jwks.json')
    def scoped_fake(self, fixture_value, session_factory):
        from contextlib import asynccontextmanager
        from jous_api.identity import RequestIdentity, OrganizationScope, ProjectScope
        sessions=[]
        runtime=MagicMock();runtime.timeout_seconds=0.2;runtime.check=AsyncMock()
        @asynccontextmanager
        async def scope():
            session=session_factory();sessions.append(session)
            yield session
        runtime.scoped_transaction=scope
        def access(session):
            actor=fixture_value['actors'][(len(sessions)-1)%2]
            service=MagicMock();service.resolve=AsyncMock(return_value=RequestIdentity(actor['user']))
            service.organization=AsyncMock(return_value=OrganizationScope(actor['user'],actor['organization']))
            service.project=AsyncMock(side_effect=lambda scope,project:ProjectScope(scope.user_id,scope.organization_id,project))
            return service
        return runtime,sessions,access
    async def test_confirmation_and_production_mode(self):
        for args in ({},{'confirmed':True},{'production_canary':True}):
            with patch.object(canary,'Database') as database,self.assertRaises(canary.CanaryRejected):
                await canary.run(self.settings(),self.fixture(),**args)
            database.assert_not_called()
    async def test_exact_stage_order_and_disposal(self):
        runtime=MagicMock();runtime.check=AsyncMock();runtime.dispose=AsyncMock()
        events=[]
        async def startup():events.append('startup')
        runtime.check.side_effect=startup
        patches=[patch.object(canary,name,new=AsyncMock(side_effect=lambda *args,n=name:events.append(n))) for name in canary.CHECKS[1:]]
        for item in patches:item.start();self.addCleanup(item.stop)
        with patch.object(canary,'Database',return_value=runtime):
            result=await canary.run(self.settings(),self.fixture(),confirmed=True,production_canary=True)
        self.assertEqual(events,list(canary.CHECKS));self.assertEqual(result['decision'],'PASS')
        self.assertFalse(result['runtime_activation']);self.assertFalse(result['public_traffic']);runtime.dispose.assert_awaited_once()
    async def test_stage_failure_closed_sanitized_and_disposes(self):
        runtime=MagicMock();runtime.check=AsyncMock(side_effect=RuntimeError('POSTGRESQL://u:SECRET@x/db'));runtime.dispose=AsyncMock()
        with patch.object(canary,'Database',return_value=runtime),patch.object(canary,'positive') as positive:
            result=await canary.run(self.settings(),self.fixture(),confirmed=True,production_canary=True)
        self.assertEqual(result['decision'],'FAIL');self.assertNotIn('SECRET',json.dumps(result));positive.assert_not_called()
        runtime.dispose.assert_awaited_once()
    async def test_admin_identity_cannot_construct_runtime_pool(self):
        settings=Settings(environment='production',database_url=URL.replace('jous_runtime.','postgres.'),auth_issuer=fixture_data()['issuer'],
                          auth_jwks_url=fixture_data()['issuer']+'/.well-known/jwks.json')
        with patch('jous_api.database.create_async_engine') as create:
            result=await canary.run(settings,self.fixture(),confirmed=True,production_canary=True)
        self.assertEqual(result['decision'],'FAIL');create.assert_not_called()
    def test_manifest_hash_and_closedness(self):
        raw=json.dumps(fixture_data()).encode()
        with patch.object(Path,'read_bytes',return_value=raw),self.assertRaises(canary.CanaryRejected):canary.load_manifest('offline','0'*64)
        data=fixture_data();data['admin_url']='INERT';raw=json.dumps(data).encode()
        with patch.object(Path,'read_bytes',return_value=raw),self.assertRaises(canary.CanaryRejected):canary.load_manifest('offline',hashlib.sha256(raw).hexdigest())
    def test_cli_requires_confirmation_before_settings(self):
        output=io.StringIO()
        with patch.object(canary,'load_settings',side_effect=AssertionError('credential access')) as loader,redirect_stdout(output):
            self.assertEqual(canary.main([]),1)
        loader.assert_not_called();self.assertNotIn('credential',output.getvalue())
    def test_coverage_and_no_admin_no_server_import(self):
        source=inspect.getsource(canary)
        for name in ('positive','cross_tenant','missing_invalid_context','forbidden_privileges','physical_reuse','cancellation'):
            self.assertIn(name,canary.CHECKS)
        self.assertNotIn('load_migration_settings',source);self.assertNotIn('JOUS_MIGRATION_DATABASE_URL',source)
        self.assertNotIn('create_app',source);self.assertNotIn('uvicorn',source)
        self.assertNotIn('fixtures(admin',source)
    def test_domain_writes_have_finally_rollback(self):
        self.assertIn('finally:\n            # Even an unexpectedly',inspect.getsource(canary.scoped))
        self.assertIn('await session.rollback()',inspect.getsource(canary.scoped))
        self.assertIn('await session.rollback()',inspect.getsource(canary.missing_invalid_context))
        self.assertIn('await session.rollback()',inspect.getsource(canary.forbidden_privileges))
    def test_reuse_cancellation_and_forbidden_contract(self):
        self.assertIn('pg_backend_pid',inspect.getsource(canary.physical_reuse))
        self.assertIn('BASELINE_CHECK',inspect.getsource(canary.physical_reuse))
        self.assertIn('transaction.commit()',inspect.getsource(canary.physical_reuse))
        self.assertIn('task.cancel()',inspect.getsource(canary.cancellation))
        self.assertIn('await asyncio.gather',inspect.getsource(canary.cancellation))
        self.assertIn('ALTER ROLE jous_runtime BYPASSRLS',canary.FORBIDDEN)
    async def test_scoped_always_rolls_back_on_failure(self):
        session=MagicMock();session.rollback=AsyncMock()
        cm=MagicMock();cm.__aenter__=AsyncMock(return_value=session);cm.__aexit__=AsyncMock(return_value=False)
        runtime=MagicMock();runtime.scoped_transaction.return_value=cm
        with patch.object(canary,'AccessService',side_effect=RuntimeError('inert')):
            with self.assertRaises(RuntimeError):await canary.scoped(runtime,self.fixture(),0,AsyncMock())
        session.rollback.assert_awaited_once()
    async def test_scoped_success_also_rolls_back(self):
        from jous_api.identity import RequestIdentity, OrganizationScope, ProjectScope
        fixture_value=self.fixture();actor=fixture_value['actors'][0]
        session=MagicMock();session.rollback=AsyncMock()
        cm=MagicMock();cm.__aenter__=AsyncMock(return_value=session);cm.__aexit__=AsyncMock(return_value=False)
        runtime=MagicMock();runtime.scoped_transaction.return_value=cm
        access=MagicMock();access.resolve=AsyncMock(return_value=RequestIdentity(actor['user']))
        access.organization=AsyncMock(return_value=OrganizationScope(actor['user'],actor['organization']))
        access.project=AsyncMock(return_value=ProjectScope(actor['user'],actor['organization'],actor['project']))
        check=AsyncMock()
        with patch.object(canary,'AccessService',return_value=access):await canary.scoped(runtime,fixture_value,0,check)
        check.assert_awaited_once();session.rollback.assert_awaited_once()
    async def test_negative_query_unexpected_success_rejected(self):
        session=MagicMock();session.execute=AsyncMock()
        cm=MagicMock();cm.__aenter__=AsyncMock();cm.__aexit__=AsyncMock(return_value=False)
        session.begin_nested.return_value=cm
        with self.assertRaises(canary.CanaryRejected):await canary.denied(session,canary.FORBIDDEN[0])
    async def test_negative_query_requires_exact_permission_error(self):
        from sqlalchemy.exc import DBAPIError
        for state in ('42501','08006'):
            error=type('InertError',(Exception,),{'sqlstate':state})('INERT SECRET')
            session=MagicMock();session.execute=AsyncMock(side_effect=DBAPIError('inert',None,error))
            cm=MagicMock();cm.__aenter__=AsyncMock();cm.__aexit__=AsyncMock(return_value=False)
            session.begin_nested.return_value=cm
            if state=='42501':await canary.denied(session,canary.FORBIDDEN[0])
            else:
                with self.assertRaises(canary.CanaryRejected):await canary.denied(session,canary.FORBIDDEN[0])
    def test_cli_secret_exceptions_cannot_reach_stdout_or_stderr(self):
        from contextlib import redirect_stderr
        for secret in ('POSTGRESQL://u:s%253Aecret@x/db','token=INERT_SECRET'):
            out,err=io.StringIO(),io.StringIO()
            with patch.object(canary.final,'load_final_contract',side_effect=RuntimeError(secret)),redirect_stdout(out),redirect_stderr(err):
                self.assertEqual(canary.main(['--confirm-production-canary','--production-canary']),1)
            self.assertNotIn(secret,out.getvalue()+err.getvalue());self.assertEqual(err.getvalue(),'')
    def test_help_no_credentials(self):
        with patch.object(canary,'load_settings',side_effect=AssertionError('credentials')) as loader,redirect_stdout(io.StringIO()):
            self.assertEqual(canary.main(['--help']),0)
        loader.assert_not_called()
    async def test_positive_write_stage_executes_and_rolls_back_both_tenants(self):
        def session_factory():
            session=MagicMock();session.rollback=AsyncMock()
            async def scalar(statement,params):
                sql=str(statement)
                if sql.startswith('INSERT INTO public.projects'):return params['id']
                if sql.startswith('UPDATE public.projects'):return params['description']
                raise AssertionError('UNEXPECTED_QUERY')
            session.scalar=AsyncMock(side_effect=scalar)
            return session
        value=self.fixture();runtime,sessions,access=self.scoped_fake(value,session_factory)
        permissions=MagicMock();permissions.authorize=AsyncMock()
        with patch.object(canary,'AccessService',side_effect=access),patch.object(canary,'PermissionService',return_value=permissions):
            await canary.positive(runtime,value)
        self.assertEqual(len(sessions),2)
        for index,session in enumerate(sessions):
            self.assertEqual(session.scalar.call_args_list[0].args[1]['org'],value['actors'][index]['organization'])
            self.assertEqual(session.scalar.await_count,2);session.rollback.assert_awaited_once()
        self.assertEqual(permissions.authorize.await_count,4)
    async def test_cross_tenant_stage_uses_other_tenant_and_rollback(self):
        from sqlalchemy.exc import DBAPIError
        def session_factory():
            session=MagicMock();session.rollback=AsyncMock();session.scalar=AsyncMock(return_value=None)
            async def execute(statement,params):
                if str(statement).startswith('UPDATE public.projects'):return MagicMock(rowcount=0)
                error=type('Denied',(Exception,),{'sqlstate':'42501'})('inert')
                raise DBAPIError('inert',None,error)
            session.execute=AsyncMock(side_effect=execute)
            cm=MagicMock();cm.__aenter__=AsyncMock();cm.__aexit__=AsyncMock(return_value=False)
            session.begin_nested.return_value=cm
            return session
        value=self.fixture();runtime,sessions,access=self.scoped_fake(value,session_factory)
        with patch.object(canary,'AccessService',side_effect=access):await canary.cross_tenant(runtime,value)
        self.assertEqual(len(sessions),2)
        for index,session in enumerate(sessions):
            other=value['actors'][1-index]
            self.assertEqual(session.scalar.call_args_list[0].args[1]['id'],other['project'])
            self.assertEqual(session.execute.call_args_list[-1].args[1]['org'],other['organization'])
            session.rollback.assert_awaited_once()
    async def test_physical_reuse_executes_commit_rollback_and_baseline(self):
        connection=MagicMock();state={'clean':True};events=[]
        async def rollback():state['clean']=True;events.append('rollback')
        async def begin():
            transaction=MagicMock()
            async def commit():state['clean']=True;events.append('commit')
            transaction.commit=AsyncMock(side_effect=commit);transaction.rollback=AsyncMock(side_effect=rollback)
            return transaction
        async def execute(statement,params=None):
            if str(statement) != 'SET LOCAL search_path = pg_catalog, pg_temp':state['clean']=False
            events.append(str(statement))
        async def scalar(statement,params=None):
            if str(statement) == "SELECT pg_catalog.current_setting('search_path')":return 'pg_catalog, pg_temp'
            sql=str(statement)
            if sql==canary.BASELINE_CHECK:return state['clean']
            if 'pg_backend_pid' in sql:return 99
            if sql.startswith('SELECT id FROM public.projects'):return params['id']
            raise AssertionError('UNEXPECTED_QUERY')
        connection.begin=AsyncMock(side_effect=begin);connection.rollback=AsyncMock(side_effect=rollback)
        connection.begin_nested=AsyncMock(return_value=MagicMock(rollback=AsyncMock()))
        connection.execute=AsyncMock(side_effect=execute);connection.scalar=AsyncMock(side_effect=scalar)
        runtime=MagicMock();cm=runtime.engine.connect.return_value
        cm.__aenter__=AsyncMock(return_value=connection);cm.__aexit__=AsyncMock(return_value=False)
        with patch.object(canary,'validate_runtime',new=AsyncMock()):await canary.physical_reuse(runtime,self.fixture())
        self.assertEqual(events.count('commit'),1);self.assertGreaterEqual(events.count('rollback'),4)
        self.assertEqual(connection.begin.await_count,2);self.assertTrue(state['clean'])
    async def test_cancellation_executes_scoped_rollback_and_recheck(self):
        def session_factory():
            session=MagicMock();session.rollback=AsyncMock()
            async def sleep(statement):await asyncio.Event().wait()
            session.execute=AsyncMock(side_effect=sleep)
            return session
        value=self.fixture();runtime,sessions,access=self.scoped_fake(value,session_factory)
        with patch.object(canary,'AccessService',side_effect=access):await canary.cancellation(runtime,value)
        self.assertEqual(len(sessions),1);sessions[0].rollback.assert_awaited_once();runtime.check.assert_awaited_once()


class ResolutionTests(unittest.IsolatedAsyncioTestCase):
    class Connection:
        def __init__(self, path='attacker, pg_catalog, public'):
            self.path = self.inherited = path
            self.events = []
            self.context = {'user': 'retained-user', 'organization': 'retained-org'}
            self.policy = PolicyConnection()
            self.fail_set = self.fail_check = self.fail_cleanup = False
            self.fail_query = False
            self.pause = None
        async def begin_nested(self):
            return self.savepoint()
        def savepoint(self):
            before = (self.path, dict(self.context))
            self.events.append('SAVEPOINT')
            outer = self
            class Point:
                def restore(self):
                    outer.events.append('ROLLBACK TO SAVEPOINT')
                    if outer.fail_cleanup: raise RuntimeError('inert cleanup')
                    outer.path, outer.context = before
                async def rollback(self): self.restore()
            return Point()
        async def execute(self, sql, parameters=None):
            return self.execute_sync(sql, parameters)
        def execute_sync(self, sql, parameters=None):
            from jous_api.database import TEMP_EVIDENCE
            sql = str(sql); self.events.append(sql)
            if sql == 'SET LOCAL search_path = pg_catalog, pg_temp':
                if self.fail_set: raise RuntimeError('inert failure')
                self.path = 'pg_catalog, pg_temp'; return None
            assert self.path == 'pg_catalog, pg_temp', 'HOSTILE_RESOLUTION'
            if sql == TEMP_EVIDENCE:
                return fixture.Result([dict(effective_temp=False, public_temp=False,
                    public_grant_option=False,direct_temp=False,memberships=False,
                    database_owner=False,database_create=False,schema_create=False,
                    unsafe_attributes=False)])
            if 'has_column_privilege' in sql:
                return fixture.Result([('projects','status','jous_runtime','UPDATE',False)])
            return self.policy.execute(sql, parameters)
        async def scalar(self, sql):
            value = self.scalar_sync(sql)
            if self.pause and str(sql) != "SELECT pg_catalog.current_setting('search_path')":
                self.pause.set(); await asyncio.Event().wait()
            return value
        def scalar_sync(self, sql):
            sql = str(sql); self.events.append(sql)
            if sql == "SELECT pg_catalog.current_setting('search_path')":
                return 'attacker' if self.fail_check else self.path
            assert self.path == 'pg_catalog, pg_temp', 'HOSTILE_RESOLUTION'
            if self.fail_query: raise RuntimeError('inert query failure')
            return True
        async def run_sync(self, callback):
            outer = self
            class Sync:
                def begin_nested(self):
                    point = outer.savepoint()
                    return MagicMock(rollback=point.restore)
                execute = lambda self, sql, parameters=None: outer.execute_sync(sql, parameters)
                scalar = lambda self, sql: outer.scalar_sync(sql)
            return callback(Sync())

    async def verify(self, connection):
        from jous_api.database import validate_runtime
        await validate_runtime(connection)

    async def test_inherited_hostile_path(self):
        c = self.Connection(); await self.verify(c)
        self.assertEqual(c.path,c.inherited)
        self.assertEqual(c.events[:3],['SAVEPOINT','SET LOCAL search_path = pg_catalog, pg_temp',
            "SELECT pg_catalog.current_setting('search_path')"])
    async def test_attacker_before_catalog_all_checks_exact(self):
        c = self.Connection('attacker, pg_catalog'); await self.verify(c)
        self.assertIn(policy.step7_catalog.POLICY_SQL,c.events)
        self.assertEqual(c.path,'attacker, pg_catalog')
    async def test_reused_connection_reestablishes_boundary(self):
        c = self.Connection(); await self.verify(c)
        c.path = 'second_attacker, pg_catalog'; await self.verify(c)
        self.assertEqual(c.path,'second_attacker, pg_catalog')
        self.assertEqual(c.events.count('SET LOCAL search_path = pg_catalog, pg_temp'),6)
    async def test_establishment_failure_stops_checks(self):
        c=self.Connection();c.fail_set=True
        with self.assertRaises(DatabaseUnavailable):await self.verify(c)
        self.assertEqual(c.events,['SAVEPOINT','SET LOCAL search_path = pg_catalog, pg_temp','ROLLBACK TO SAVEPOINT'])
    async def test_wrong_effective_boundary_stops_checks(self):
        c=self.Connection();c.fail_check=True
        with self.assertRaises(DatabaseUnavailable):await self.verify(c)
        self.assertEqual(len(c.events),4)
        self.assertEqual(c.path,c.inherited)
    async def test_commit_does_not_leak_override(self):
        c=self.Connection();await self.verify(c)
        # No override remains even before the outer commit/pool return.
        self.assertEqual(c.path,c.inherited)
        await self.verify(c)
    async def test_rollback_does_not_leak_override(self):
        c=self.Connection();c.fail_query=True
        with self.assertRaises(DatabaseUnavailable):await self.verify(c)
        self.assertEqual(c.path,c.inherited)
    async def test_cancellation_restores_boundary(self):
        c=self.Connection();c.pause=asyncio.Event()
        task=asyncio.create_task(self.verify(c));await c.pause.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(c.path,c.inherited)
        self.assertEqual(c.events[-1],'ROLLBACK TO SAVEPOINT')
    async def test_cleanup_uncertainty_fails_closed(self):
        c=self.Connection();c.fail_cleanup=True
        with self.assertRaises(DatabaseUnavailable):await self.verify(c)
    async def test_existing_user_org_context_is_unchanged(self):
        c=self.Connection();before=dict(c.context);await self.verify(c)
        self.assertEqual(c.context,before)
    async def test_policy_mismatch_restores_and_denies(self):
        c=self.Connection();c.policy.rows[0]['using_tree']='{MUTATED}'
        with self.assertRaises(DatabaseUnavailable):await self.verify(c)
        self.assertEqual(c.path,c.inherited)
    async def test_direct_temp_evidence_is_guarded(self):
        from jous_api.database import runtime_temp_evidence
        c=self.Connection();await runtime_temp_evidence(c)
        self.assertEqual(c.events[1],'SET LOCAL search_path = pg_catalog, pg_temp')
        self.assertEqual(c.path,c.inherited)
    async def test_real_async_session_avoids_unconditional_flush(self):
        from jous_api.runtime_resolution import catalog_resolution
        from sqlalchemy.ext.asyncio import AsyncSession
        c=self.Connection();session=AsyncSession(autoflush=False)
        with patch.object(session,'connection',AsyncMock(return_value=c)), \
             patch.object(session,'execute',AsyncMock(side_effect=c.execute)), \
             patch.object(session,'scalar',AsyncMock(side_effect=c.scalar)), \
             patch.object(session,'flush',AsyncMock(side_effect=AssertionError('NO_FLUSH'))), \
             patch.object(session,'begin_nested',side_effect=AssertionError('NO_SESSION_SAVEPOINT')):
            async with catalog_resolution(session):self.assertEqual(c.path,'pg_catalog, pg_temp')
        self.assertEqual(c.path,c.inherited)
    async def test_real_sqlalchemy_transaction_savepoint_order(self):
        from sqlalchemy.engine import Engine, URL
        from sqlalchemy.engine.default import DefaultDialect
        from sqlalchemy.pool import StaticPool
        from jous_api.runtime_resolution import catalog_resolution_sync
        events=[]
        class Cursor:
            description=None;rowcount=-1
            def execute(self,sql,params):
                events.append(sql)
                self.description=[('search_path',None,None,None,None,None,None)] if sql.startswith('SELECT') else None
            def fetchone(self):return ('pg_catalog, pg_temp',)
            def close(self):pass
        class Driver:
            def cursor(self):return Cursor()
            def rollback(self):events.append('OUTER ROLLBACK')
            def commit(self):events.append('OUTER COMMIT')
            def close(self):pass
        engine=Engine(StaticPool(creator=Driver),DefaultDialect(),URL.create('inert'))
        with engine.connect() as connection:
            with catalog_resolution_sync(connection):
                self.assertTrue(connection.in_transaction())
            self.assertFalse(connection.in_nested_transaction())
            connection.commit()
        self.assertTrue(events[0].startswith('SAVEPOINT'))
        self.assertEqual(events[1],'SET LOCAL search_path = pg_catalog, pg_temp')
        self.assertTrue(events[3].startswith('ROLLBACK TO SAVEPOINT'))
        self.assertIn('OUTER COMMIT',events)

    async def test_complete_security_wire_inventory_is_guarded(self):
        from jous_api import database as db
        c=self.Connection();await self.verify(c)
        final_queries={f.TARGET_SQL,f.ROLE_SQL,f.TYPE_SQL,f.FUNCTION_SQL,
            f.OPERATOR_SQL,f.COLLATION_SQL,f.RELATION_SQL,f.COLUMN_SQL,
            f.CREATED_SQL,f.CREATED_ACL_SQL,f.CREATED_SCHEMA_ACL_SQL,
            policy.step7_catalog.POLICY_SQL}
        self.assertTrue(final_queries.issubset(set(c.events)))
        application_queries={sql for sql in c.events if sql.startswith('SELECT')}
        self.assertEqual(len(application_queries),21)  # 20 checks plus safe path observation
        self.assertTrue({db.ROLE_CHECK,db.BASELINE_CHECK,db.STATE_CHECK,db.TEMP_EVIDENCE}.issubset(application_queries))
        path=c.inherited;stack=[]
        for sql in c.events:
            if sql=='SAVEPOINT':stack.append(path)
            elif sql=='ROLLBACK TO SAVEPOINT':path=stack.pop()
            elif sql=='SET LOCAL search_path = pg_catalog, pg_temp':path='pg_catalog, pg_temp'
            elif sql.startswith('SELECT'):
                self.assertEqual(path,'pg_catalog, pg_temp',sql)
        self.assertEqual(path,c.inherited);self.assertFalse(stack)


class TempNamespaceTests(unittest.IsolatedAsyncioTestCase):
    # Independent PG17 lookup model: runtime-config-client.html/search_path.
    # No SQL is executed. Qualified names bypass the path; temp is implicit
    # first for types/relations only when it exists and is not explicitly listed.
    @staticmethod
    def lookup(configured, kind, name, temporary=True):
        if '.' in name:return name.split('.')[0]
        path=[item.strip() for item in configured.split(',')]
        if 'pg_catalog' not in path:path.insert(0,'pg_catalog')
        if kind in ('type','relation'):
            if temporary and 'pg_temp' not in path:path.insert(0,'pg_temp')
            if not temporary:path=[item for item in path if item!='pg_temp']
        else:path=[item for item in path if item!='pg_temp']
        # Adversarial catalog contains same-signature/name objects in each
        # attacker/temp namespace; the real catalog has the reviewed objects.
        return path[0]

    @staticmethod
    def references(sql):
        import re
        # Finite inspection only, not a rewriter. Literals are opaque. The
        # complete exact SQL is obtained from real verifier execution sites.
        code=re.sub(r"'(?:''|[^'])*'", "''", sql)
        types=re.findall(r'::\s*((?:\w+\.)?\w+)(?:\[\])?',code)
        types+=re.findall(r'\bCAST\([^)]*\bAS\s+((?:\w+\.)?\w+)\s*\)',code)
        relations=re.findall(r'\b(?:FROM|JOIN)\s+((?:\w+\.)?\w+)',code)
        calls=re.findall(r'\b((?:\w+\.)?\w+)\s*\(',code)
        grammar={'ANY','ARRAY','AS','CAST','COALESCE','EXISTS','IN','JOIN','VALUES',
                 'NOT','FROM','WHERE','AND','OR','SELECT'}
        aliases={'t','p','r'}  # Inline VALUES relation column aliases only.
        functions=[v for v in calls if v.upper() not in grammar and v not in aliases]
        operators=re.findall(r'!~|<>|\|\||=|>|<',code)
        implicit=re.findall(r'\b(?:NOT\s+)?IN\s*\(|\bANY\s*\(',code)
        collations=re.findall(r'\bCOLLATE\s+((?:\w+\.)?\w+)',code)
        schemas={v.split('.')[0] for v in types+relations+functions+collations if '.' in v}
        return dict(types=types,relations=relations,functions=functions,
                    operators=operators,implicit=implicit,collations=collations,schemas=schemas)

    class Connection(ResolutionTests.Connection):
        def __init__(self, path='attacker, pg_catalog', temporary=True):
            super().__init__(path);self.temporary=temporary;self.checked=[]
            self.observation=None
        def audit(self, sql):
            refs=TempNamespaceTests.references(sql)
            for kind,key in [('type','types'),('relation','relations'),('function','functions')]:
                for name in refs[key]:
                    winner=TempNamespaceTests.lookup(self.path,kind,name,self.temporary)
                    expected=name.split('.')[0] if '.' in name else 'pg_catalog'
                    if winner!=expected:raise RuntimeError('TEMP_NAMESPACE_SHADOW')
            for operator in refs['operators']+refs['implicit']:
                assert TempNamespaceTests.lookup(self.path,'operator',operator,self.temporary)=='pg_catalog'
            self.checked.append((sql,refs))
        def execute_sync(self, sql, parameters=None):
            value=str(sql)
            if value.startswith('SET LOCAL search_path = '):
                self.events.append(value)
                if self.fail_set:raise RuntimeError('inert setup failure')
                self.path=value.split(' = ',1)[1];return None
            self.audit(value)
            return super().execute_sync(sql,parameters)
        def scalar_sync(self, sql):
            if str(sql)=="SELECT pg_catalog.current_setting('search_path')":
                self.events.append(str(sql))
                return self.observation if self.observation is not None else self.path
            self.audit(str(sql));return super().scalar_sync(sql)

    async def verify(self, c):
        from jous_api.database import validate_runtime
        await validate_runtime(c)

    def test_previous_configured_path_is_not_effective_lookup_order(self):
        self.assertEqual(self.lookup('pg_catalog','type','text'),'pg_temp')
        self.assertEqual(self.lookup('pg_catalog','type','oid'),'pg_temp')
        self.assertEqual(self.lookup('pg_catalog','relation','pg_roles'),'pg_temp')
        self.assertEqual(self.lookup('pg_catalog','function','current_setting'),'pg_catalog')
        self.assertEqual(self.lookup('pg_catalog','operator','='),'pg_catalog')
    def test_explicit_order_fixes_types_and_relations(self):
        for kind,name in [('type','text'),('type','oid'),('relation','pg_roles')]:
            self.assertEqual(self.lookup('pg_catalog, pg_temp',kind,name),'pg_catalog')
    def test_temp_first_is_unsafe(self):
        self.assertEqual(self.lookup('pg_temp, pg_catalog','type','text'),'pg_temp')
    async def test_production_guard_prevents_shadow_text(self):
        c=self.Connection();await self.verify(c)
        self.assertTrue(any('text' in refs['types'] for _,refs in c.checked))
    async def test_production_guard_prevents_shadow_oid_and_array(self):
        c=self.Connection();await self.verify(c)
        self.assertTrue(any('oid' in refs['types'] for _,refs in c.checked))
        self.assertTrue(any('::oid[]' in sql for sql,_ in c.checked))
    def test_all_actual_relations_are_qualified(self):
        for sql in PolicyConnection().material:
            for name in self.references(sql)['relations']:
                self.assertIn('.',name)
                self.assertEqual(self.lookup('pg_catalog','relation',name),name.split('.')[0])
        self.assertEqual(self.lookup('pg_catalog','relation','pg_roles'),'pg_temp')
    async def test_pooled_connection_existing_temp_namespace(self):
        c=self.Connection();await self.verify(c);await self.verify(c)
        self.assertTrue(c.temporary);self.assertEqual(c.path,c.inherited)
    async def test_no_temp_namespace_does_not_require_creation(self):
        c=self.Connection(temporary=False);await self.verify(c)
        self.assertFalse(c.temporary);self.assertEqual(c.path,c.inherited)
    async def test_all_explicit_hostile_orders_replaced(self):
        for path in ['pg_temp, pg_catalog','attacker_schema, pg_catalog',
                     'pg_temp, attacker_schema, pg_catalog']:
            c=self.Connection(path);await self.verify(c)
            self.assertEqual(c.path,path)
    async def test_nonapproved_observations_fail_closed(self):
        for path in ['pg_catalog','pg_temp, pg_catalog','attacker_schema, pg_catalog',
                     'pg_temp, attacker_schema, pg_catalog','pg_catalog, pg_temp, public']:
            c=self.Connection();c.observation=path
            with self.assertRaises(DatabaseUnavailable):await self.verify(c)
            self.assertFalse(c.checked);self.assertEqual(c.path,c.inherited)
    async def test_setup_failure(self):
        c=self.Connection();c.fail_set=True
        with self.assertRaises(DatabaseUnavailable):await self.verify(c)
        self.assertFalse(c.checked);self.assertEqual(c.path,c.inherited)
    async def test_verification_failure_restores_path(self):
        c=self.Connection();c.policy.rows[0]['using_tree']='{MUTATED}'
        with self.assertRaises(DatabaseUnavailable):await self.verify(c)
        self.assertEqual(c.path,c.inherited)
    async def test_savepoint_failure_is_not_success(self):
        c=self.Connection();c.fail_cleanup=True
        with self.assertRaises(DatabaseUnavailable):await self.verify(c)
    async def test_cancellation_restores_path(self):
        c=self.Connection();c.pause=asyncio.Event()
        task=asyncio.create_task(self.verify(c));await c.pause.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(c.path,c.inherited)
    async def test_restoration_precedes_orm_and_preserves_context(self):
        c=self.Connection('public, attacker');before=dict(c.context)
        await self.verify(c)
        self.assertEqual(c.path,'public, attacker');self.assertEqual(c.context,before)
        self.assertEqual(c.events[-1],'ROLLBACK TO SAVEPOINT')
    async def test_complete_independent_wire_reference_inventory(self):
        c=self.Connection();await self.verify(c)
        definitions={sql for sql,_ in c.checked}
        self.assertEqual(len(definitions),20)
        cast_queries={sql for sql,refs in c.checked if any('.' not in t for t in refs['types'])}
        self.assertEqual(len(cast_queries),8)  # Includes TARGET_SQL, beyond seven review examples.
        expected_functions={'current_setting','current_database','count','pg_catalog.current_setting',
            'pg_catalog.has_database_privilege','pg_catalog.pg_has_role','pg_catalog.has_schema_privilege',
            'pg_catalog.aclexplode','pg_catalog.acldefault','pg_catalog.has_table_privilege',
            'pg_catalog.has_column_privilege','pg_catalog.has_any_column_privilege'}
        actual_functions={name for _,refs in c.checked for name in refs['functions']}
        self.assertEqual(actual_functions,expected_functions)
        for _,refs in c.checked:
            self.assertTrue(refs['operators'] or refs['implicit'])
            self.assertLessEqual(refs['schemas'],{'pg_catalog','public'})
            self.assertFalse(refs['collations'])  # No explicit collation-name lookup.
            self.assertLessEqual({name.split('.')[-1] for name in refs['types']},
                                 {'text','oid','integer','name'})
    def test_pg_temp_alias_and_qualified_references(self):
        self.assertEqual(self.lookup('pg_catalog, pg_temp','type','text',True),'pg_catalog')
        self.assertEqual(self.lookup('pg_catalog, pg_temp','type','text',False),'pg_catalog')
        self.assertEqual(self.lookup('pg_temp, attacker','type','pg_catalog.text'),'pg_catalog')
        self.assertEqual(self.lookup('pg_temp, attacker','relation','public.projects'),'public')

    async def test_old_production_guard_accepts_path_but_type_audit_rejects(self):
        from jous_api import runtime_resolution as resolution
        c=self.Connection()
        # Replay the previous guard with only its two path constants reverted.
        # Its server observation passes; independent type lookup still fails.
        with patch.object(resolution,'SET_PATH','SET LOCAL search_path = pg_catalog'), \
             patch.object(resolution,'VERIFICATION_PATH','pg_catalog'):
            with self.assertRaisesRegex(RuntimeError,'TEMP_NAMESPACE_SHADOW'):
                async with resolution.catalog_resolution(c):
                    self.assertEqual(c.path,'pg_catalog')
                    c.audit(f.TYPE_SQL)
        self.assertEqual(c.path,c.inherited)
    async def test_observation_exception_stops_checks_and_restores(self):
        c=self.Connection()
        original=c.scalar
        async def observed(sql):
            if str(sql)=="SELECT pg_catalog.current_setting('search_path')":
                raise RuntimeError('SYNTHETIC_SECRET')
            return await original(sql)
        c.scalar=observed
        with self.assertRaises(DatabaseUnavailable) as result:await self.verify(c)
        self.assertNotIn('SYNTHETIC_SECRET',str(result.exception))
        self.assertFalse(c.checked);self.assertEqual(c.path,c.inherited)

if __name__=='__main__':
    if sys.argv[1:] == ['--existing']:
        # Existing FastAPI tests use thread-backed sync handlers. Permit only a
        # passive idle poll; all native network/process/write audit guards remain.
        import time
        class CooperativeSelector(foundation.TimerSelector):
            def select(self, timeout=None):
                if self.get_map():
                    raise RuntimeError('OFFLINE_ASYNC_IO')
                time.sleep(0.001 if timeout is None else max(0, timeout))
                return []
        policy_loop = asyncio.WindowsSelectorEventLoopPolicy()
        policy_loop._loop_factory = lambda: foundation.TimerLoop(CooperativeSelector())
        asyncio.set_event_loop_policy(policy_loop)
        suite = unittest.defaultTestLoader.loadTestsFromNames((
            'test_runtime_security_foundation', 'test_database_foundation',
            'test_access_foundation', 'test_action_authorization',
            'test_authentication_foundation', 'test_process_foundation'))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        raise SystemExit(not result.wasSuccessful())
    unittest.main(verbosity=2)
