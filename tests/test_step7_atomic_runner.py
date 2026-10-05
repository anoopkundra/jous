"""Network-free operator contracts; fake catalogs are not live PostgreSQL evidence."""
import asyncio
from contextlib import redirect_stdout
import copy
import importlib.util
import io
import hashlib
from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pathlib import Path
import ssl
import sqlite3
import re
import tempfile
import sys
import subprocess
import textwrap
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy.engine import Engine, URL
from sqlalchemy.engine.default import DefaultDialect
from sqlalchemy.pool import QueuePool
from alembic.runtime.migration import MigrationContext

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT/'services/api/infrastructure/apply_step7_atomic.py'
spec = importlib.util.spec_from_file_location('step7_operator', PATH)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.load_dependencies()
# Tests intentionally use a non-isolated process; production mutation requires -I.
runner._VERIFIED_SOURCES = {p.relative_to(ROOT).as_posix(): p.read_bytes().replace(b'\r\n',b'\n')
    for directory in ('services/api/src/jous_api','services/api/migrations')
    for p in (ROOT/directory).rglob('*.py')}
PIPELINE = runner.pipeline
APPROVED_SHA = '1'*40
SECRET = 'password-token-DO-NOT-PRINT'
URL_TEXT = f'postgresql://postgres.{runner.PROJECT}:{SECRET}@aws-0-ca-central-1.pooler.supabase.com:5432/postgres'


def certificate(name):
    # Public CA fixtures generated in memory; private keys never persisted or printed.
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)])
    now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
        .public_key(key.public_key()).serial_number(1).not_valid_before(now-timedelta(days=1))
        .not_valid_after(now+timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True)
        .sign(key,hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.PEM).decode(),cert.public_bytes(serialization.Encoding.DER)


class Result:
    def __init__(self, value): self.value = value
    def mappings(self): return self
    def all(self): return self.value


class Catalog:
    """Independent shaped catalog fixtures; production assertions are not mocked."""
    def __init__(self):
        self.migrated = False
        self.temp = False
        self.events = []
        self.overrides = {}
        self.original = dict(roleid=50, member=100, grantor=10, role_name='jous_security_reader',
            member_name='postgres', grantor_name='bootstrap_admin', grantor_super=True,
            admin_option=True, inherit_option=False, set_option=False)
        self.roles = [dict(oid=oid,rolname=name,rolcanlogin=login,rolsuper=False,
            rolbypassrls=False,rolcreatedb=False,rolcreaterole=False,rolreplication=False,rolinherit=False)
            for oid,name,login in ((51,'jous_runtime',True),(50,'jous_security_reader',False))]
        self.module, self.statements = runner.migration_contract()
        self.transaction = SimpleNamespace(is_active=True)

    def in_transaction(self): return True
    def get_transaction(self): return self.transaction
    def execute(self, sql, params=None):
        s = str(sql)
        self.events.append(s)
        if s == runner.GRANT: self.temp = True; return Result([])
        if s == runner.REVOKE: self.temp = False; return Result([])
        for marker,value in self.overrides.items():
            if marker in s: return Result(copy.deepcopy(value))
        if 'm.roleid,m.member,m.grantor' in s:
            result = [copy.deepcopy(self.original)]
            if self.temp:
                result.append({**self.original,'grantor':100,'grantor_name':'postgres',
                    'grantor_super':False,'admin_option':False,'set_option':True})
            return Result(result)
        if "AS can_set" in s: return Result([dict(can_set=self.temp,inherited=False)])
        if 'SELECT oid,rolname,rolcanlogin' in s: return Result(copy.deepcopy(self.roles))
        if 'SELECT m.admin_option,m.inherit_option,m.set_option,m.grantor' in s:
            return Result([dict(admin_option=True,inherit_option=False,set_option=False,grantor=10)])
        if 'current_user::text AS role' in s:
            return Result([dict(role='postgres',session='postgres',database='postgres',pid=1,xid='2',
                version=170006,rolcreaterole=True,rolbypassrls=True,db_owner=True)])
        if 'AS db_create' in s:
            return Result([dict(db_create=False,db_owner=False,temp=True,direct_temp=False,
                schema_create=False,relation_owner=False,schema_owner=False)])
        if 'a.privilege_type,a.is_grantable FROM pg_catalog.pg_database' in s:
            return Result([dict(privilege_type='CONNECT',is_grantable=False),
                           dict(privilege_type='TEMPORARY',is_grantable=False)])
        if "n.nspname='public' AND a.grantee=0" in s:
            return Result([dict(privilege_type='USAGE',is_grantable=False)])
        if 'SELECT version_num' in s:
            return Result([dict(version_num='0002_runtime_rls' if self.migrated else '0001_identity_project')])
        if 'SELECT c.relname,r.rolname AS owner' in s:
            return Result([dict(relname=t,owner='postgres',relrowsecurity=True,
                relforcerowsecurity=self.migrated) for t in sorted(runner.TABLES)])
        if 'SELECT tablename,policyname' in s:
            result=[]
            if self.migrated:
                for t,commands in self.module.COMMANDS.items():
                    g=self.module.GUARDS[t]
                    result.append(dict(tablename=t,policyname=f'jous_{t}_guard',permissive='RESTRICTIVE',
                        roles=['jous_runtime'],cmd='ALL',qual=g,with_check=g))
                    for cmd in commands:
                        result.append(dict(tablename=t,policyname=f'jous_{t}_{cmd.lower()}',permissive='PERMISSIVE',
                            roles=['jous_runtime'],cmd=cmd,qual=None if cmd=='INSERT' else g,
                            with_check=g if cmd in ('INSERT','UPDATE') else None))
                    if t in ('users','organizations'):
                        result.append(dict(tablename=t,policyname=f'jous_{t}_helper_read',permissive='PERMISSIVE',
                            roles=['jous_security_reader'],cmd='SELECT',qual='true',with_check=None))
            return Result(result)
        if 'SELECT n.nspname,p.proname,r.rolname AS owner' in s:
            return Result([dict(nspname='jous_security',proname=n,owner='jous_security_reader')
                for n in ('organization_is_active','resolve_user')] if self.migrated else [])
        if 'SELECT n.nspname,c.relname,r.rolname,a.privilege_type' in s:
            return Result([dict(nspname='public',relname='alembic_version',rolname='jous_runtime',
                privilege_type='SELECT',is_grantable=False)] if self.migrated else [])
        if 'SELECT n.nspname,c.relname,a.attname,r.role,p.priv' in s:
            result=[]
            for role,contract in (('jous_runtime',runner.RUNTIME),('jous_security_reader',runner.READER)):
                for t,perms in contract.items():
                    for p,cols in perms.items():
                        result.extend(dict(nspname='public',relname=t,attname=col,role=role,priv=p,
                            allowed=self.migrated,grantable=False) for col in cols)
            result.append(dict(nspname='public',relname='alembic_version',attname='version_num',
                role='jous_runtime',priv='SELECT',allowed=self.migrated,grantable=False))
            return Result(result)
        if 'has_function_privilege' in s:
            return Result([dict(nspname='jous_security',proname=n,args=args,prokind='f',role=role,
                allowed=True,grantable=role=='jous_security_reader')
                for n,args in (('resolve_user','text, text'),('organization_is_active','uuid'))
                for role in ('jous_runtime','jous_security_reader')] if self.migrated else [])
        if 'pg_catalog.oidvectortypes' in s:
            result=[]
            for n in ('resolve_user','organization_is_active'):
                create=next(s for s in self.statements if s.startswith('CREATE FUNCTION jous_security.'+n+'('))
                result.append(dict(nspname='jous_security',proargnames=['p_issuer','p_subject'] if n=='resolve_user'
                    else ['p_organization_id'],proargmodes=None,proallargtypes=None,pronargdefaults=0,
                    no_defaults=True,text_body=True,proname=n,args='text, text' if n=='resolve_user' else 'uuid',
                    returns='uuid' if n=='resolve_user' else 'boolean',proowner=50,prosecdef=True,
                    provolatile='s',proparallel='u',proconfig=['search_path=pg_catalog, pg_temp'],
                    prosrc=create.split('$function$')[1],lanname='sql',proisstrict=False,prokind='f'))
            return Result(result)
        if 'SELECT p.proname,a.grantor,a.grantee' in s:
            return Result([dict(proname=n,grantor=50,grantee=grantee,privilege_type='EXECUTE',is_grantable=False)
                for n in ('resolve_user','organization_is_active') for grantee in (50,51)])
        if 'SELECT r.rolname AS owner FROM pg_catalog.pg_namespace' in s:
            return Result([dict(owner='postgres')])
        if "n.nspname='jous_security' AND a.grantee<>n.nspowner" in s:
            return Result([dict(grantee=grantee,privilege_type='USAGE',is_grantable=False) for grantee in (50,51)])
        if 'SELECT pg_catalog.pg_backend_pid() AS pid' in s:
            return Result([dict(pid=1,xid='2')])
        # Empty forbidden-object/ACL queries and transaction-local SETs.
        if s.startswith('SET LOCAL') or any(x in s for x in
            ('WHERE nspname=', 'm.roleid FROM', 'SELECT d.oid', 'SELECT s.classid',
             'SELECT c.oid', 'SELECT d.oid FROM pg_catalog.pg_default_acl')):
            return Result([])
        raise AssertionError('Unmodelled offline query: '+s)

    def scalar(self, sql, params=None):
        s=str(sql)
        if 'pg_try_advisory_xact_lock' in s: return True
        if s.startswith('SELECT count(*)'): return self.overrides.get('count',0)
        raise AssertionError('Unmodelled scalar')


class Driver:
    def __init__(self): self.closed=False; self.events=[]
    async def close(self,timeout=None): self.events.append('physical_close'); self.closed=True
    def terminate(self): self.events.append('terminate'); self.closed=True
    def is_closed(self): return self.closed


class AsyncConnection:
    def __init__(self,catalog):
        self.catalog=catalog; self.events=[]; self.closed=False; self.invalidated=False
        self.driver=Driver(); self.sync_connection=SimpleNamespace(detach=lambda:self.events.append('detach'))
        self.fail_commit=False; self.fail_rollback=False
    async def get_raw_connection(self): return SimpleNamespace(driver_connection=self.driver)
    async def begin(self): self.events.append('begin'); return self
    async def run_sync(self,fn): self.events.append('work'); return fn(self.catalog)
    async def commit(self):
        self.events.append('commit')
        if self.fail_commit: raise RuntimeError(SECRET)
    async def rollback(self):
        self.events.append('rollback')
        if self.fail_rollback: raise RuntimeError(SECRET)
    async def invalidate(self): self.events.append('invalidate'); self.invalidated=True
    async def close(self): self.events.append('close'); self.closed=True


class EngineFake:
    def __init__(self,c): self.c=c; self.disposed=False
    async def connect(self): return self.c
    async def dispose(self): self.disposed=True


async def execute_test(engine, work):
    # Lifecycle fault injection is test-local; production execute has no work bypass.
    with patch.object(runner,'pipeline',work):
        return await runner.execute(engine)


class LocalGates(unittest.TestCase):
    def setUp(self):
        # Existing Git-gate fixtures test source identity, not the real checkout's
        # test-created caches. ExecutionSurfaceTests exercises the real surface gate.
        self.addCleanup(setattr, runner, '_APPROVED_SHA', None)
        # Unrelated gate fixtures run in the suite's already-used interpreter.
        # CachedJousTests exercises the real namespace gate without mocking it.
        self.namespace = patch.object(runner, 'cached_jous_gate')
        self.namespace.start(); self.addCleanup(self.namespace.stop)
        self.surface = patch.object(runner, 'execution_surface_gate')
        self.surface.start(); self.addCleanup(self.surface.stop)
        self.launch = patch.object(runner, 'trusted_launch_gate')
        self.launch.start(); self.addCleanup(self.launch.stop)

    def test_wrong_target_fails_before_engine_creation(self):
        with (patch.object(runner,'repository_gate'), patch.dict(runner.os.environ,
                {'JOUS_MIGRATION_DATABASE_URL':URL_TEXT+'?host=evil'},clear=True),
                patch.object(runner,'create_async_engine') as engine, redirect_stdout(io.StringIO()) as output):
            self.assertEqual(runner.main(['--confirm-managed-mutation','--approved-execution-sha',APPROVED_SHA,'--ca-file','unused']),1)
            engine.assert_not_called(); self.assertNotIn(SECRET,output.getvalue())

    def test_import_and_help_never_connect(self):
        with patch('sqlalchemy.ext.asyncio.create_async_engine') as engine, patch('asyncpg.connect') as network:
            spec.loader.exec_module(runner)
            runner.load_dependencies()
            runner._VERIFIED_SOURCES = {p.relative_to(ROOT).as_posix(): p.read_bytes().replace(b'\r\n',b'\n')
                for directory in ('services/api/src/jous_api','services/api/migrations')
                for p in (ROOT/directory).rglob('*.py')}
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as e:
                runner.main(['--help'])
            self.assertEqual(e.exception.code,0)
            engine.assert_not_called(); network.assert_not_called()

    def test_confirmation_before_environment_or_engine(self):
        with (patch.object(runner,'repository_gate') as gate, patch.object(runner,'create_async_engine') as engine,
                redirect_stdout(io.StringIO()) as output):
            self.assertEqual(runner.main([]),1)
            gate.assert_not_called(); engine.assert_not_called()
            self.assertNotIn(SECRET,output.getvalue())

    def repo(self,head=None,origin=None,dirty='',mismatch=False,migration_drift=False):
        files={}
        for name in runner.IDENTITY_PATHS:
            path=ROOT/name
            items=path.rglob('*') if path.is_dir() else [path]
            for item in items:
                if item.is_file() and '__pycache__' not in item.parts:
                    data=item.read_bytes().replace(b'\r\n',b'\n')
                    blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
                    files[item.relative_to(ROOT).as_posix()]=(blob,data)
        def run(args,**kwargs):
            command=args[1]
            if command=='rev-parse':
                value=(head or APPROVED_SHA) if args[2]=='HEAD' else (origin or APPROVED_SHA)
            elif command=='status': value=dirty
            elif command=='ls-tree':
                value='\n'.join('100644 blob '+('0'*40 if migration_drift and name==runner.MIGRATION_PATH else blob)
                    +'\t'+name for name,(blob,data) in files.items())
            elif command=='cat-file':
                value=next((data for blob,data in files.values() if blob==args[3]),b'migration drift')
                if mismatch: value+=b'changed'
            else: raise AssertionError(args)
            return SimpleNamespace(stdout=value)
        return run

    def test_wrong_head(self):
        with self.assertRaises(runner.Stop): runner.repository_gate(APPROVED_SHA,self.repo(head='wrong'))
    def test_wrong_origin(self):
        with self.assertRaises(runner.Stop): runner.repository_gate(APPROVED_SHA,self.repo(origin='wrong'))
    def test_dirty_tracked(self):
        with self.assertRaises(runner.Stop): runner.repository_gate(APPROVED_SHA,self.repo(dirty=' M tracked'))
    def test_protected_untracked_allowed(self):
        run=self.repo(); seen=[]
        def capture(args,**kwargs): seen.append(args); return run(args,**kwargs)
        runner.repository_gate(APPROVED_SHA,capture)
        self.assertTrue(any('--untracked-files=no' in args for args in seen))
    def test_artifact_mismatch(self):
        with self.assertRaisesRegex(runner.Stop,'ARTIFACT_MISMATCH'):
            runner.repository_gate(APPROVED_SHA,self.repo(mismatch=True))
    def test_approved_exact_identity(self):
        runner.repository_gate(APPROVED_SHA,self.repo())
    def test_migration_blob_drift(self):
        original=Path.read_bytes
        def read(path):
            value=original(path)
            return value+b'\n# unreviewed drift\n' if path==ROOT/runner.MIGRATION_PATH else value
        with patch.object(Path,'read_bytes',read), self.assertRaisesRegex(runner.Stop,'MIGRATION_IDENTITY'):
            runner.repository_gate(APPROVED_SHA,self.repo())

    def test_ignored_security_source_file_rejected(self):
        run=self.repo()
        original=Path.rglob
        def extra(path,pattern):
            items=list(original(path,pattern))
            if path==ROOT/'services/api/src/jous_api': items.append(path/'unexpected.py')
            return iter(items)
        original_file=Path.is_file
        def is_file(path): return True if path.name=='unexpected.py' else original_file(path)
        with patch.object(Path,'rglob',extra), patch.object(Path,'is_file',is_file), self.assertRaisesRegex(runner.Stop,'ARTIFACT_TREE_MISMATCH'):
            runner.repository_gate(APPROVED_SHA,run)

    def test_missing_or_malformed_approval_before_connection(self):
        for sha in (None,'HEAD','1'*39,'g'*40):
            with self.subTest(sha=sha), patch.object(runner,'create_async_engine') as engine, redirect_stdout(io.StringIO()):
                args=['--confirm-managed-mutation']+(['--approved-execution-sha',sha] if sha else [])
                self.assertEqual(runner.main(args),1); engine.assert_not_called()

    def test_wrong_ca_fingerprint(self):
        pem,der=certificate('wrong')
        with patch.object(runner.Path,'read_text',return_value=pem):
            with self.assertRaisesRegex(runner.Stop,'CA_FINGERPRINT'):
                runner.connection_gate(URL_TEXT,'unused')

    def test_target_routing_and_project_adversaries(self):
        variants=[URL_TEXT.replace(runner.PROJECT,'other'),URL_TEXT.replace(':5432/',':6543/'),
            URL_TEXT.replace('/postgres','/other'),URL_TEXT+'#fragment']
        variants += [URL_TEXT+'?'+q for q in ('host=evil','user=evil','database=evil','dbname=evil',
            'port=1','dsn=evil','host=a&host=b','%68ost=evil','HOST=evil','host=')]
        for value in variants:
            with self.subTest(value=value.split('@')[-1]), self.assertRaises(runner.Stop):
                runner.connection_gate(value,'unused')

    def test_verified_tls_and_effective_arguments(self):
        pem,der=certificate('approved fixture')
        with patch.object(runner.Path,'read_text',return_value=pem), patch.object(runner,'CA_SHA',hashlib.sha256(der).hexdigest()):
            url,ctx=runner.connection_gate(URL_TEXT,'unused')
        self.assertEqual(url.database,'postgres'); self.assertTrue(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode,ssl.CERT_REQUIRED)
        self.assertEqual(ctx.get_ca_certs(binary_form=True),[der])

    def test_single_ca_rejects_bundle_and_external_material(self):
        pem,der=certificate('approved fixture'); other,_=certificate('unrelated fixture')
        with patch.object(runner,'CA_SHA',hashlib.sha256(der).hexdigest()):
            for value in (pem+other,other+pem,pem+'trailing','leading'+pem,'',other):
                with self.subTest(case=value[:30]), patch.object(runner.Path,'read_text',return_value=value), self.assertRaises(runner.Stop):
                    runner.connection_gate(URL_TEXT,'unused')

    def test_runtime_credential_never_falls_back(self):
        with (patch.object(runner,'repository_gate'), patch.dict(runner.os.environ,
                {'JOUS_DATABASE_URL':URL_TEXT},clear=True), redirect_stdout(io.StringIO()) as output,
                patch.object(runner,'create_async_engine') as engine):
            self.assertEqual(runner.main(['--confirm-managed-mutation','--approved-execution-sha',APPROVED_SHA,'--ca-file','unused']),1)
            engine.assert_not_called(); self.assertIn('MIGRATION_CREDENTIAL_REQUIRED',output.getvalue())


class CatalogTests(unittest.TestCase):
    def setUp(self): self.c=Catalog()
    def test_success_pipeline_uses_real_assertions(self):
        runner.pipeline(self.c,migrate=lambda c:setattr(c,'migrated',True))
        self.assertFalse(self.c.temp)
        self.assertEqual(self.c.events.count(runner.GRANT),1)
        self.assertEqual(self.c.events.count(runner.REVOKE),1)
        self.assertNotIn('COMMIT',self.c.events)

    def test_baseline_revision_rejected_before_grant(self):
        self.c.overrides['SELECT version_num']=[{'version_num':'unexpected'}]
        with self.assertRaises(runner.Stop): runner.pipeline(self.c)
        self.assertNotIn(runner.GRANT,self.c.events)

    def test_role_attributes_rejected_before_grant(self):
        for attr in ('rolsuper','rolbypassrls','rolcreatedb','rolcreaterole','rolreplication','rolinherit'):
            with self.subTest(attr=attr):
                c=Catalog(); c.roles[0][attr]=True
                with self.assertRaises(runner.Stop): runner.pipeline(c)
                self.assertNotIn(runner.GRANT,c.events)

    def test_unexpected_grantor(self):
        self.c.original['grantor']=123
        with self.assertRaisesRegex(runner.Stop,'MEMBERSHIP_PROVENANCE'): runner.preflight(self.c)
    def test_unexpected_inbound_membership(self):
        self.c.overrides["AND u.rolname<>'postgres'"]=[dict(roleid=50)]
        with self.assertRaisesRegex(runner.Stop,'ROLE_INBOUND_MEMBERSHIP'): runner.preflight(self.c)
    def test_preexisting_temporary_row(self):
        self.c.temp=True
        with self.assertRaisesRegex(runner.Stop,'MEMBERSHIP_BASELINE'): runner.preflight(self.c)
    def test_temporary_options_exact(self):
        baseline=runner.baseline_membership(self.c)
        self.c.temp=True
        runner.verify_membership(self.c,baseline,True)
        altered=self.c.execute('SELECT m.roleid,m.member,m.grantor').all()
        altered[1]['inherit_option']=True
        self.c.overrides['m.roleid,m.member,m.grantor']=altered
        with self.assertRaises(runner.Stop): runner.verify_membership(self.c,baseline,True)
    def test_complete_membership_restoration(self):
        baseline=runner.baseline_membership(self.c)
        self.c.original['admin_option']=False
        with self.assertRaisesRegex(runner.Stop,'MEMBERSHIP_RESTORATION'):
            runner.verify_membership(self.c,baseline,False)
    def test_effective_set_must_restore_false(self):
        baseline=runner.baseline_membership(self.c)
        self.c.overrides['AS can_set']=[dict(can_set=True,inherited=False)]
        with self.assertRaises(runner.Stop): runner.verify_membership(self.c,baseline,False)

    def migrated(self):
        baseline=runner.preflight(self.c); self.c.migrated=True
        return baseline

    def test_post_revision_exact(self):
        b=self.migrated(); self.c.overrides['SELECT version_num']=[{'version_num':'0001_identity_project'}]
        with self.assertRaises(runner.Stop): runner.verify_security(self.c,b)
    def test_wrong_helper_owner(self):
        b=self.migrated()
        data=self.c.execute('SELECT p.proname,pg_catalog.oidvectortypes').all(); data[0]['proowner']=100
        self.c.overrides['pg_catalog.oidvectortypes']=data
        with self.assertRaisesRegex(runner.Stop,'HELPER_DEFINITION'): runner.verify_security(self.c,b)
    def test_helper_acl_public_missing_runtime_or_grant_option(self):
        for mode in ('public','missing_runtime','grant_option'):
            with self.subTest(mode=mode):
                self.c=Catalog(); b=self.migrated()
                data=self.c.execute('SELECT p.proname,a.grantor,a.grantee').all()
                if mode=='public': data[0]['grantee']=0
                elif mode=='missing_runtime': data=[r for r in data if r['grantee']!=51]
                else: data[0]['is_grantable']=True
                self.c.overrides['SELECT p.proname,a.grantor,a.grantee']=data
                with self.assertRaisesRegex(runner.Stop,'HELPER_ACL'): runner.verify_security(self.c,b)
    def test_unexpected_runtime_helper_grants(self):
        for role in ('jous_runtime','jous_security_reader'):
            self.c=Catalog(); b=self.migrated()
            self.c.overrides['SELECT n.nspname,c.relname,r.rolname,a.privilege_type']=[dict(
                nspname='public',relname='projects',rolname=role,privilege_type='UPDATE',is_grantable=False)]
            with self.assertRaises(runner.Stop): runner.verify_security(self.c,b)
    def test_force_rls_missing(self):
        b=self.migrated(); data=self.c.execute('SELECT c.relname,r.rolname AS owner').all()
        data[0]['relforcerowsecurity']=False
        self.c.overrides['SELECT c.relname,r.rolname AS owner']=data
        with self.assertRaisesRegex(runner.Stop,'TABLE_RLS'): runner.verify_security(self.c,b)
    def test_policy_names_roles_commands_expressions(self):
        for field,value in (('policyname','unexpected'),('roles',['public']),('cmd','ALL'),
                            ('permissive','RESTRICTIVE'),('qual','true')):
            with self.subTest(field=field):
                self.c=Catalog(); b=self.migrated()
                data=self.c.execute('SELECT tablename,policyname').all()
                data[1][field]=value
                self.c.overrides['SELECT tablename,policyname']=data
                with self.assertRaises(runner.Stop): runner.verify_security(self.c,b)
    def test_unknown_policy_function_operator_type_and_statement_rejected(self):
        for expression in ('evil()', 'OPERATOR(public.evil)(id)', "'x'::public.evil",
            'pg_catalog.jous_security.organization_is_active(organization_id)',
            "CAST('x' AS attacker.dangerous_type)", "'x'::attacker.dangerous_type",
            'true; COMMIT', '"evil"()', 'true /* comment */'):
            with self.subTest(expression=expression), self.assertRaises(runner.Stop):
                runner.policy_structure(expression)

    def test_unavailable_policy_structure_fails_closed(self):
        for expr in (None,'', '(((true)', 'true false', "'unterminated"):
            with self.subTest(expr=expr), self.assertRaises(runner.Stop): runner.policy_structure(expr)

    def test_policy_verification_never_plans_or_executes_expressions(self):
        baseline=self.migrated()
        with patch.object(self.c,'scalar',side_effect=lambda sql,*a: 0 if str(sql).startswith('SELECT count(*)')
                          else (_ for _ in ()).throw(AssertionError('planning not allowed'))):
            runner.verify_security(self.c,baseline)
        self.assertFalse(any('EXPLAIN' in sql for sql in self.c.events))

    def test_policy_structural_attacks(self):
        guard=self.c.module.GUARDS['organization_memberships']
        attacks=[guard.replace('jous_security.organization_is_active','jous_security.wrong'),
            guard.replace('organization_is_active(organization_id)','organization_is_active(id)'),
            guard.replace('AND jous_security.organization_is_active(organization_id)',''),
            guard+' AND jous_security.organization_is_active(organization_id)',
            guard.replace(' AND ',' OR ',1), 'NOT ('+guard+')',
            guard.replace('user_id =','organization_id =',1)]
        expected=runner.policy_structure(guard)
        for attack in attacks:
            with self.subTest(attack=attack):
                try: actual=runner.policy_structure(attack)
                except runner.Stop: continue
                self.assertNotEqual(actual,expected)

    def test_safe_deparser_equivalences_preserve_structure(self):
        for expected,actual in (
            ("status = 'active'", "((status)::text = 'active'::text)"),
            ("role IN ('owner','member')", "((role)::text = ANY ((ARRAY['owner'::character varying,'member'::character varying])::text[]))"),
            ("CAST(pg_catalog.current_setting('jous.user_id',true) AS pg_catalog.uuid)",
             "(current_setting('jous.user_id'::text,true))::uuid"),
            ('NULL','NULL::uuid'),
            ('true AND (false AND true)','((true AND false) AND true)')):
            self.assertEqual(runner.policy_structure(expected),runner.policy_structure(actual))

    def test_helper_parameter_binding_and_identity(self):
        for name in ('resolve_user','organization_is_active'):
            for field,value in (('proargnames',['p_subject','p_issuer']),('proargmodes',['i']),
                ('pronargdefaults',1),('no_defaults',False),('text_body',False),('nspname','pgx')):
                c=Catalog(); b=runner.preflight(c); c.migrated=True
                data=c.execute('SELECT pg_catalog.oidvectortypes').all()
                target=next(r for r in data if r['proname']==name); target[field]=value
                c.overrides['pg_catalog.oidvectortypes']=data
                with self.subTest(name=name,field=field), self.assertRaisesRegex(runner.Stop,'HELPER_DEFINITION'):
                    runner.verify_security(c,b)

    def test_namespace_filter_semantics_offline(self):
        # Execute the exact namespace predicate in in-memory SQLite with PostgreSQL
        # regex semantics supplied locally. No PostgreSQL/network connection exists.
        with sqlite3.connect(':memory:') as database:
            database.create_function('regexp',2,lambda pattern,name: re.search(pattern,name) is not None)
            predicate=runner.USER_NAMESPACE.replace(' !~ ',' NOT REGEXP ')
            for name in ('pgx','pga','pg1','public','jous_security','pg_temp_abc'):
                self.assertEqual(database.execute('SELECT n.nspname FROM (SELECT ? AS nspname) n WHERE '+predicate,(name,)).fetchall(),[(name,)])
            for name in ('pg_catalog','information_schema','pg_toast','pg_temp_12','pg_toast_temp_12'):
                self.assertEqual(database.execute('SELECT n.nspname FROM (SELECT ? AS nspname) n WHERE '+predicate,(name,)).fetchall(),[])

    def test_pgx_schema_create_rejected(self):
        c=Catalog(); data=c.execute('SELECT AS db_create').all(); data[0]['schema_create']=True
        c.overrides['AS db_create']=data
        with self.assertRaisesRegex(runner.Stop,'PRIVILEGE_BOUNDARY'): runner.preflight(c)
        self.assertTrue(any(runner.USER_NAMESPACE in sql for sql in c.events))

    def test_pgx_relation_and_sequence_privileges_rejected(self):
        for mode in ('column','sequence'):
            c=Catalog(); b=runner.preflight(c); c.migrated=True
            if mode=='column':
                data=c.execute('SELECT n.nspname,c.relname,a.attname,r.role,p.priv').all()
                data.append(dict(nspname='pgx',relname='secret',attname='id',role='jous_runtime',priv='SELECT',allowed=True,grantable=False))
                c.overrides['SELECT n.nspname,c.relname,a.attname,r.role,p.priv']=data
            else: c.overrides["WHERE c.relkind='S'"]=[dict(oid=999)]
            with self.subTest(mode=mode), self.assertRaises(runner.Stop): runner.verify_security(c,b)
            relevant=[sql for sql in c.events if 'has_column_privilege' in sql or 'has_sequence_privilege' in sql]
            self.assertTrue(all(runner.USER_NAMESPACE in sql for sql in relevant))

    def test_unexpected_routine_authority_rejected(self):
        for schema in ('public','pgx'):
            for role in ('jous_runtime','jous_security_reader'):
                for kind in ('f','p','a','w'):
                    for grantable in (False,True):
                        c=Catalog(); c.migrated=True
                        data=c.execute('SELECT has_function_privilege').all()
                        data.append(dict(nspname=schema,proname='unexpected',args='',prokind=kind,
                            role=role,allowed=True,grantable=grantable))
                        c.overrides['has_function_privilege']=data
                        with self.subTest(schema=schema,role=role,kind=kind,grantable=grantable), self.assertRaisesRegex(runner.Stop,'ROUTINE_PRIVILEGES'):
                            runner.verify_routines(c,True)
                        self.assertTrue(runner.USER_NAMESPACE in c.events[-1])

    def test_public_default_acl_rejected(self):
        for grantee in (0,50,51):
            for privilege in ('SELECT','EXECUTE','USAGE','CREATE'):
                c=Catalog(); c.overrides['FROM pg_catalog.pg_default_acl']=[dict(oid=1,grantee=grantee,privilege_type=privilege,is_grantable=False)]
                with self.subTest(grantee=grantee,privilege=privilege), self.assertRaisesRegex(runner.Stop,'DEFAULT_PRIVILEGES'):
                    runner.preflight(c)
                self.assertNotIn(runner.GRANT,c.events)
                self.assertIn('a.grantee=0',c.events[-1])

    def test_public_temp_and_create_privilege_paths_rejected(self):
        for field in ('db_create','db_owner','direct_temp','schema_create','relation_owner','schema_owner'):
            with self.subTest(field=field):
                c=Catalog(); data=c.execute('SELECT AS db_create').all(); data[0][field]=True
                c.overrides['AS db_create']=data
                with self.assertRaises(runner.Stop): runner.preflight(c)
                self.assertNotIn(runner.GRANT,c.events)

    def test_membership_original_survives_temporary_row(self):
        baseline=runner.baseline_membership(self.c); self.c.temp=True
        actual=self.c.execute('SELECT m.roleid,m.member,m.grantor').all()
        actual[0]['set_option']=True
        self.c.overrides['m.roleid,m.member,m.grantor']=actual
        with self.assertRaises(runner.Stop): runner.verify_membership(self.c,baseline,True)

    def test_row_count_change(self):
        b=self.migrated(); self.c.overrides['count']=1
        with self.assertRaisesRegex(runner.Stop,'ROW_COUNT'): runner.verify_security(self.c,b)
    def test_continuity_change(self):
        b=self.migrated(); self.c.overrides['SELECT pg_catalog.pg_backend_pid() AS pid']=[dict(pid=99,xid='2')]
        with self.assertRaisesRegex(runner.Stop,'TRANSACTION_CONTINUITY'): runner.verify_security(self.c,b)
    def test_exact_grant_cleanup_contract(self):
        self.assertEqual(runner.GRANT,'GRANT jous_security_reader TO postgres WITH ADMIN FALSE, INHERIT FALSE, SET TRUE GRANTED BY postgres')
        self.assertEqual(runner.REVOKE,'REVOKE jous_security_reader FROM postgres GRANTED BY postgres RESTRICT')


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_grant_execution_failure_rolls_back(self):
        catalog=Catalog(); c=AsyncConnection(catalog); e=EngineFake(c)
        original=catalog.execute
        def sql(value,*args):
            if str(value)==runner.GRANT: raise RuntimeError(SECRET)
            return original(value,*args)
        catalog.execute=sql
        with self.assertRaisesRegex(runner.Stop,'ROLLED_BACK'):
            await runner.execute(e)
        self.assertNotIn('commit',c.events); self.assertEqual(c.events.count('rollback'),1)

    async def test_graceful_failure_falls_back_to_termination(self):
        c=AsyncConnection(Catalog()); e=EngineFake(c)
        c.driver.close=AsyncMock(side_effect=RuntimeError(SECRET))
        await execute_test(e,lambda c:None)
        self.assertEqual(c.driver.events,['terminate'])
        self.assertTrue(c.driver.closed and c.closed and e.disposed)

    async def test_termination_failure_not_reported_as_clean_success(self):
        c=AsyncConnection(Catalog()); e=EngineFake(c)
        c.driver.close=AsyncMock(side_effect=RuntimeError(SECRET))
        c.driver.terminate=lambda:(_ for _ in ()).throw(RuntimeError(SECRET))
        with self.assertRaisesRegex(runner.Stop,'COMMITTED_CLEANUP_UNCONFIRMED') as error:
            await execute_test(e,lambda c:None)
        self.assertNotIn(SECRET,str(error.exception)); self.assertTrue(c.closed and e.disposed)

    async def test_commit_only_after_final_verification(self):
        catalog=Catalog(); connection=AsyncConnection(catalog); engine=EngineFake(connection)
        def work(c): PIPELINE(c,migrate=lambda c:setattr(c,'migrated',True))
        self.assertEqual(await execute_test(engine,work),'COMMITTED')
        self.assertEqual(connection.events.count('commit'),1)
        self.assertNotIn('rollback',connection.events)
        self.assertFalse(catalog.temp); self.assertTrue(connection.closed); self.assertTrue(engine.disposed)
        self.assertTrue(connection.driver.closed)

    async def test_every_precommit_boundary_rolls_back(self):
        for boundary in ('preflight','temporary_check','migration','post_verify','cleanup','final_verify'):
            with self.subTest(boundary=boundary):
                catalog=Catalog(); connection=AsyncConnection(catalog); engine=EngineFake(connection)
                def work(c):
                    calls=0
                    def fail(): raise RuntimeError(SECRET)
                    def inspect(c):
                        if boundary=='preflight': fail()
                        return {'memberships':[catalog.original]}
                    def member(c,b,t):
                        if boundary=='temporary_check' and t: fail()
                    def migrate(c):
                        if boundary=='migration': fail()
                    def verify(c,b):
                        nonlocal calls
                        calls+=1
                        if (boundary=='post_verify' and calls==1) or (boundary=='final_verify' and calls==2): fail()
                    original=c.execute
                    def execute(sql,*a):
                        if str(sql)==runner.REVOKE and boundary=='cleanup': fail()
                        return original(sql,*a)
                    c.execute=execute
                    PIPELINE(c,inspect=inspect,verify=verify,migrate=migrate,membership_check=member)
                with self.assertRaisesRegex(runner.Stop,'ROLLED_BACK') as error:
                    await execute_test(engine,work)
                self.assertNotIn(SECRET,str(error.exception))
                self.assertEqual(connection.events.count('rollback'),1)
                self.assertNotIn('commit',connection.events)
                self.assertTrue(connection.closed and engine.disposed and connection.driver.closed)

    async def test_commit_uncertainty_never_retries(self):
        c=AsyncConnection(Catalog()); c.fail_commit=True; e=EngineFake(c)
        with self.assertRaisesRegex(runner.Stop,'UNKNOWN'): await execute_test(e,lambda c:None)
        self.assertEqual(c.events.count('commit'),1); self.assertNotIn('rollback',c.events)
        self.assertTrue(c.driver.closed and c.closed and e.disposed)

    async def test_rollback_failure_not_claimed_success(self):
        c=AsyncConnection(Catalog()); c.fail_rollback=True
        with self.assertRaisesRegex(runner.Stop,'ROLLBACK_UNCONFIRMED'):
            await execute_test(EngineFake(c),lambda c:(_ for _ in ()).throw(RuntimeError(SECRET)))
        self.assertNotIn('commit',c.events); self.assertTrue(c.driver.closed)

    async def test_cancellation_waits_for_rollback_and_close(self):
        c=AsyncConnection(Catalog()); e=EngineFake(c)
        started=asyncio.Event(); release=asyncio.Event()
        async def rollback():
            c.events.append('rollback'); started.set(); await release.wait()
        c.rollback=rollback
        async def run_sync(fn): await asyncio.Event().wait()
        c.run_sync=run_sync
        task=asyncio.create_task(runner.execute(e))
        await asyncio.sleep(0); task.cancel(); await started.wait(); task.cancel()
        await asyncio.sleep(0); self.assertFalse(task.done())
        release.set()
        with self.assertRaisesRegex(runner.Stop,'ROLLED_BACK'): await task
        self.assertTrue(c.closed and e.disposed and c.driver.closed)
        self.assertNotIn('commit',c.events)


class RealExternalTransactionTests(unittest.TestCase):
    def test_installed_alembic_env_joins_real_sqlalchemy_transaction(self):
        # A fresh isolated child avoids relying on application modules imported by
        # other suite tests. It uses fake DBAPI only, never a PostgreSQL connection.
        code = textwrap.dedent(r"""
            from pathlib import Path
            from types import ModuleType
            from unittest.mock import patch
            import importlib.machinery
            from sqlalchemy.engine import Engine, URL
            from sqlalchemy.engine.default import DefaultDialect
            from sqlalchemy.pool import NullPool
            from alembic.runtime.migration import MigrationContext
            from alembic.util import pyfiles
            root = Path.cwd()
            path = root/'services/api/infrastructure/apply_step7_atomic.py'
            runner = ModuleType('step7_offline_integration')
            runner.__file__ = str(path)
            exec(compile(path.read_bytes(), str(path), 'exec'), runner.__dict__)
            runner._VERIFIED_SOURCES = {
                p.relative_to(root).as_posix(): p.read_bytes().replace(b'\r\n', b'\n')
                for directory in ('services/api/src/jous_api', 'services/api/migrations')
                for p in (root/directory).rglob('*.py')}
            runner.install_source_importer()
            runner.load_dependencies()
            class DBAPI:
                def __init__(self): self.commits = 0
                def rollback(self): pass
                def commit(self): self.commits += 1
                def close(self): pass
            physical = DBAPI()
            engine = Engine(NullPool(lambda: physical), DefaultDialect(), URL.create('fake'))
            seen = []
            loaded = []
            original_source = runner.verified_module
            original_loader = pyfiles.load_module_py
            original_code = importlib.machinery.SourceFileLoader.get_code
            def source(module_id, path):
                loaded.append(Path(path).resolve())
                return original_source(module_id, path)
            def reject_repository_cache(loader, name):
                if Path(loader.path).resolve().is_relative_to(root) and '.venv' not in Path(loader.path).parts:
                    raise AssertionError('repository cached-code loader used')
                return original_code(loader, name)
            with engine.connect() as connection:
                outer = connection.begin()
                def migrations(context, **kwargs):
                    seen.append(context.connection)
                    assert context._in_external_transaction
                    steps = context._migrations_fn(('0001_identity_project',), context)
                    assert len(steps) == 1
                    function = steps[0].migration_fn
                    assert function.__globals__['revision'] == '0002_runtime_rls'
                    assert Path(function.__code__.co_filename) == root/runner.MIGRATION_PATH
                    with context.begin_transaction(_per_migration=True):
                        assert connection.get_transaction() is outer
                with (patch.object(runner, 'verified_module', source),
                      patch.object(importlib.machinery.SourceFileLoader, 'get_code', reject_repository_cache),
                      patch.object(MigrationContext, 'run_migrations', migrations),
                      patch('asyncpg.connect') as network,
                      patch('sqlalchemy.ext.asyncio.create_async_engine') as other_engine,
                      patch.object(runner, 'create_async_engine') as runner_engine):
                    runner.alembic_upgrade(connection)
                    network.assert_not_called()
                    other_engine.assert_not_called()
                    runner_engine.assert_not_called()
                assert seen == [connection]
                assert root/'services/api/migrations/env.py' in loaded
                assert root/runner.MIGRATION_PATH in loaded
                assert any(p.name == 'config.py' and 'jous_api' in p.parts for p in loaded)
                assert pyfiles.load_module_py is original_loader
                assert physical.commits == 0 and outer.is_active
                outer.rollback()
            assert physical.commits == 0
            engine.dispose()
            print('OFFLINE_SOURCE_ONLY_0002_PASS')
        """)
        result = subprocess.run([sys.executable, '-I', '-B', '-'], input=code,
            cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('OFFLINE_SOURCE_ONLY_0002_PASS', result.stdout)


class ExecutionSurfaceTests(unittest.TestCase):
    def surface(self, extra=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in ('services/api/infrastructure', 'services/api/migrations/versions',
                     'services/api/src/jous_api'):
            (root/name).mkdir(parents=True)
        source = root/'services/api/src/jous_api/__init__.py'
        source.write_text('VALUE = 1\n')
        if extra:
            path = root/extra
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(b'not executable test data')
        return root, {'services/api/src/jous_api/__init__.py'}

    def test_no_cache_surface_allowed(self):
        root, artifacts = self.surface()
        with patch.object(runner,'ROOT',root): runner.execution_surface_gate(artifacts)

    def test_caches_and_shadow_modules_fail_closed(self):
        for extra in ('services/api/migrations/versions/__pycache__/0002_runtime_rls.cpython-312.pyc',
                      'services/api/src/jous_api/__pycache__/config.cpython-312.pyc',
                      'services/api/infrastructure/__pycache__/apply_step7_atomic.cpython-312.pyc',
                      'services/api/infrastructure/ssl.py', 'services/api/src/shadow/__init__.py',
                      'services/api/migrations/sitecustomize.py', 'services/api/src/inject.pth'):
            with self.subTest(extra=extra):
                root, artifacts = self.surface(extra)
                with patch.object(runner,'ROOT',root), self.assertRaises(runner.Stop):
                    runner.execution_surface_gate(artifacts)

    def test_source_contract_never_calls_cached_loader(self):
        with patch('importlib.machinery.SourceFileLoader.get_code',side_effect=AssertionError('cached loader')):
            module, statements = runner.migration_contract()
            self.assertEqual(module.revision,'0002_runtime_rls')
            self.assertTrue(statements)

    def test_late_cache_gate_prevents_alembic_loading(self):
        c = Catalog()
        with (patch.object(runner,'cached_jous_gate'),
              patch.object(runner,'_APPROVED_SHA',APPROVED_SHA),
              patch.object(runner,'repository_gate',side_effect=runner.Stop('REPOSITORY_BYTECODE')) as gate,
              patch.object(runner.command,'upgrade') as upgrade):
            with self.assertRaisesRegex(runner.Stop,'REPOSITORY_BYTECODE'): runner.alembic_upgrade(c)
            gate.assert_called_once_with(APPROVED_SHA); upgrade.assert_not_called()

    def test_untrusted_launch_fails_before_credentials(self):
        with (patch.object(runner,'cached_jous_gate'),
              patch.object(runner.sys,'flags',SimpleNamespace(isolated=0,ignore_environment=0)),
              patch.object(runner.os.environ,'get',side_effect=lambda name, *args: (_ for _ in ()).throw(AssertionError('credential access')) if name == 'JOUS_MIGRATION_DATABASE_URL' else None),
              redirect_stdout(io.StringIO()) as output):
            self.assertEqual(runner.main(['--confirm-managed-mutation','--approved-execution-sha',APPROVED_SHA]),1)
            self.assertIn('ISOLATED_LAUNCH_REQUIRED',output.getvalue())

    def test_repository_search_paths_removed_before_shadowable_imports(self):
        # Execute the actual frozen/built-in-only bootstrap without any payload imports.
        prefix = PATH.read_text().split('import argparse',1)[0]
        paths = [str(ROOT/'services/api/infrastructure'),str(ROOT/'services/api/src'),str(ROOT),
                 str(Path(sys.base_prefix)/'Lib')]
        with patch.object(sys,'path',paths):
            exec(compile(prefix,str(PATH),'exec'),{'__file__':str(PATH)})
            self.assertEqual(sys.path,[str(Path(sys.base_prefix)/'Lib')])

    def test_strict_base64_rejects_excess_padding_and_payload(self):
        pem,der=certificate('strict fixture')
        with patch.object(runner,'CA_SHA',hashlib.sha256(der).hexdigest()):
            self.assertEqual(runner.approved_ca(pem).get_ca_certs(binary_form=True),[der])
            for payload in ('AAAA\n','=\n','!\n'):
                value=pem.replace('-----END CERTIFICATE-----',payload+'-----END CERTIFICATE-----')
                with self.subTest(payload=payload), self.assertRaises(runner.Stop): runner.approved_ca(value)
            lines=pem.splitlines()
            truncated='\n'.join(lines[:1]+[lines[1][:-1]]+lines[2:])+'\n'
            with self.assertRaises(runner.Stop): runner.approved_ca(truncated)


class BoundaryRegressionTests(unittest.TestCase):
    def test_matching_timestamp_bytecode_rejected_without_loading(self):
        fixture = ExecutionSurfaceTests()
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            for path in ('services/api/infrastructure','services/api/src','services/api/migrations/versions'):
                (root/path).mkdir(parents=True)
            source=root/runner.MIGRATION_PATH
            approved=(ROOT/runner.MIGRATION_PATH).read_bytes()
            source.write_bytes(approved)
            cache=source.parent/'__pycache__'/ '0002_runtime_rls.cpython-312.pyc'
            cache.parent.mkdir()
            import struct
            # Matching timestamp/size header, inert payload; no code is executed.
            cache.write_bytes(importlib.util.MAGIC_NUMBER+struct.pack('<III',0,int(source.stat().st_mtime),len(approved))+b'inert')
            with (patch.object(runner,'ROOT',root),
                  patch.object(runner,'trusted_launch_gate'),
                  patch.object(runner,'cached_jous_gate'),
                  patch.object(runner,'repository_gate',side_effect=lambda sha: runner.execution_surface_gate({runner.MIGRATION_PATH})),
                  patch.object(runner.os.environ,'get',side_effect=lambda key,*args: (_ for _ in ()).throw(AssertionError('credentials read')) if key=='JOUS_MIGRATION_DATABASE_URL' else None),
                  patch.object(runner,'create_async_engine') as engine, redirect_stdout(io.StringIO()) as output):
                self.assertEqual(runner.main(['--confirm-managed-mutation','--approved-execution-sha',APPROVED_SHA]),1)
                engine.assert_not_called(); self.assertIn('REPOSITORY_BYTECODE',output.getvalue())

    def test_second_gate_detects_actual_late_cache(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            for path in ('services/api/infrastructure','services/api/src','services/api/migrations'):
                (root/path).mkdir(parents=True)
            c=Catalog()
            with patch.object(runner,'ROOT',root):
                runner.execution_surface_gate(set())
                (root/'services/api/migrations/late.pyc').write_bytes(b'inert')
                with (patch.object(runner,'cached_jous_gate'),
                      patch.object(runner,'_APPROVED_SHA',APPROVED_SHA),
                      patch.object(runner,'repository_gate',side_effect=lambda sha: runner.execution_surface_gate(set())),
                      patch.object(runner.command,'upgrade') as upgrade, self.assertRaisesRegex(runner.Stop,'REPOSITORY_BYTECODE')):
                    runner.alembic_upgrade(c)
                upgrade.assert_not_called()

    def test_deferred_dependencies_not_imported_on_import_or_help(self):
        namespace={'__file__':str(PATH),'__name__':'fresh_operator'}
        with patch('builtins.__import__',wraps=__import__) as imports:
            exec(compile(PATH.read_bytes(),str(PATH),'exec'),namespace)
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit): namespace['main'](['--help'])
            self.assertFalse(any(call.args[0].startswith(('alembic','sqlalchemy','jous_api')) for call in imports.call_args_list))


class CachedJousTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, runner, '_APPROVED_SHA', None)

    def clean_modules(self):
        # Test-only fresh-interpreter fixture. Production never purges modules.
        return {name: module for name, module in sys.modules.items()
                if name != 'jous_api' and not name.startswith('jous_api.')}

    def inert_module(self, name, origin=None):
        module = ModuleType(name)
        module.__file__ = origin
        module.__spec__ = SimpleNamespace(origin=origin)
        return module

    def environment_spy(self, reads):
        original = runner.os.environ.get
        def get(name, *args):
            if name == 'JOUS_MIGRATION_DATABASE_URL':
                reads.append(name)
                return None
            return original(name, *args)
        return get

    def arguments(self):
        return ['--confirm-managed-mutation', '--approved-execution-sha', APPROVED_SHA,
                '--ca-file', 'unused']

    def test_cached_namespace_fails_before_repository_or_credentials_regardless_of_origin(self):
        cases = (('jous_api', None), ('jous_api.config', None),
                 ('jous_api.database', str(ROOT/'.venv/Lib/site-packages/jous_api/database.py')),
                 ('jous_api.anything', str(Path(sys.base_prefix)/'Lib/jous_api/anything.py')))
        for name, origin in cases:
            modules = self.clean_modules()
            candidate = self.inert_module(name, origin)
            modules[name] = candidate
            reads = []
            with (self.subTest(name=name), patch.object(sys, 'modules', modules),
                  patch.object(runner, 'repository_gate') as repository,
                  patch.object(runner, 'load_dependencies') as dependencies,
                  patch.object(runner, 'create_async_engine') as engine,
                  patch.object(runner.os.environ, 'get', self.environment_spy(reads)),
                  redirect_stdout(io.StringIO()) as output):
                self.assertEqual(runner.main(self.arguments()), 1)
                self.assertIn('PRELOADED_JOUS_MODULE', output.getvalue())
                repository.assert_not_called(); dependencies.assert_not_called(); engine.assert_not_called()
                self.assertEqual(reads, [])
                self.assertIs(sys.modules[name], candidate)  # No silent purge.

    def test_unrelated_similar_name_allowed(self):
        modules = self.clean_modules()
        modules['jous_api2'] = self.inert_module('jous_api2')
        with patch.object(sys, 'modules', modules): runner.cached_jous_gate()

    def test_clean_namespace_loads_verified_package_and_submodule(self):
        import importlib
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = {'services/api/src/jous_api/__init__.py': b'TOKEN = 1\n',
                       'services/api/src/jous_api/config.py': b'TOKEN = 2\n'}
            for name, content in sources.items():
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
            with (patch.object(sys, 'modules', self.clean_modules()),
                  patch.object(sys, 'meta_path', list(sys.meta_path)),
                  patch.object(runner, 'ROOT', root), patch.object(runner, '_VERIFIED_SOURCES', sources),
                  patch.object(runner, 'verified_module', wraps=runner.verified_module) as source,
                  patch('importlib.machinery.SourceFileLoader.get_code', side_effect=AssertionError('cached loader'))):
                runner.cached_jous_gate()
                runner.install_source_importer()
                package = importlib.import_module('jous_api')
                module = importlib.import_module('jous_api.config')
                self.assertEqual((package.TOKEN, module.TOKEN), (1, 2))
                self.assertEqual([call.args[0] for call in source.call_args_list], ['jous_api', 'jous_api.config'])
                self.assertIs(sys.modules['jous_api.config'], module)

    def test_importer_refuses_cached_namespace_without_purging(self):
        modules = self.clean_modules()
        candidate = self.inert_module('jous_api.config')
        modules['jous_api.config'] = candidate
        with patch.object(sys, 'modules', modules), self.assertRaisesRegex(runner.Stop, 'PRELOADED_JOUS_MODULE'):
            runner.install_source_importer()
        self.assertIs(modules['jous_api.config'], candidate)

    def test_between_repository_gate_and_importer_is_detected(self):
        modules = self.clean_modules(); reads = []
        def repository(sha): modules['jous_api'] = self.inert_module('jous_api')
        with (patch.object(sys, 'modules', modules), patch.object(runner, 'trusted_launch_gate'),
              patch.object(runner, 'repository_gate', side_effect=repository),
              patch.object(runner, 'load_dependencies') as dependencies,
              patch.object(runner, 'create_async_engine') as engine,
              patch.object(runner.os.environ, 'get', self.environment_spy(reads)),
              redirect_stdout(io.StringIO()) as output):
            self.assertEqual(runner.main(self.arguments()), 1)
            self.assertIn('PRELOADED_JOUS_MODULE', output.getvalue())
            dependencies.assert_not_called(); engine.assert_not_called(); self.assertEqual(reads, [])

    def test_dependency_preload_detected_before_credentials(self):
        modules = self.clean_modules(); reads = []
        def dependencies(): modules['jous_api.database'] = self.inert_module('jous_api.database')
        with (patch.object(sys, 'modules', modules), patch.object(sys, 'meta_path', list(sys.meta_path)),
              patch.object(runner, 'trusted_launch_gate'), patch.object(runner, 'repository_gate'),
              patch.object(runner, 'load_dependencies', side_effect=dependencies),
              patch.object(runner, 'create_async_engine') as engine,
              patch.object(runner.os.environ, 'get', self.environment_spy(reads)),
              redirect_stdout(io.StringIO()) as output):
            self.assertEqual(runner.main(self.arguments()), 1)
            self.assertIn('PRELOADED_JOUS_MODULE', output.getvalue())
            engine.assert_not_called(); self.assertEqual(reads, [])
            self.assertIn('jous_api.database', sys.modules)

    def test_later_preload_detected_before_alembic(self):
        modules = self.clean_modules()
        with patch.object(sys, 'modules', modules):
            runner.cached_jous_gate()
            modules['jous_api.config'] = self.inert_module('jous_api.config')
            connection = SimpleNamespace(in_transaction=lambda: (_ for _ in ()).throw(AssertionError('connection used')))
            with patch.object(runner.command, 'upgrade') as upgrade, self.assertRaisesRegex(runner.Stop, 'PRELOADED_JOUS_MODULE'):
                runner.alembic_upgrade(connection)
            upgrade.assert_not_called()

    def test_unrelated_name_proceeds_to_credential_gate(self):
        modules = self.clean_modules(); reads = []
        modules['jous_api2'] = self.inert_module('jous_api2')
        with (patch.object(sys, 'modules', modules), patch.object(sys, 'meta_path', list(sys.meta_path)),
              patch.object(runner, 'trusted_launch_gate'), patch.object(runner, 'repository_gate'),
              patch.object(runner, 'load_dependencies'),
              patch.object(runner.os.environ, 'get', self.environment_spy(reads)),
              patch.object(runner, 'create_async_engine') as engine, redirect_stdout(io.StringIO()) as output):
            self.assertEqual(runner.main(self.arguments()), 1)
            self.assertIn('MIGRATION_CREDENTIAL_REQUIRED', output.getvalue())
            self.assertEqual(reads, ['JOUS_MIGRATION_DATABASE_URL']); engine.assert_not_called()
