"""Network-free operator contracts; fake catalogs are not live PostgreSQL evidence."""
import asyncio
from step7_catalog_observations import observations as builtin_observations
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
# Only test data receives synthetic M1 values; production retains the unresolved base.
_BASE_LOAD = runner.load_public_manifest
_BASE_PARSE = runner.parse_manifest

def synthetic_manifest():
    return _BASE_LOAD()  # Mandatory reviewed M1 composition; no synthetic boolean injection.
runner.load_public_manifest = synthetic_manifest

runner._VERIFIED_SOURCES['services/api/infrastructure/step7_realtime_authorize_amendment.py'] = (ROOT/'services/api/infrastructure/step7_realtime_authorize_amendment.py').read_bytes().replace(b'\r\n',b'\n')
_CATALOG_MODULE = runner.catalog_contract()
_AUTHORIZE_MODULE = runner.authorize_contract()

from functools import lru_cache

@lru_cache(maxsize=2)
def final_material(migrated=False):
    f=runner.execution_contract();contract=f.load_final_contract();d=f._read(contract,f.ApprovedFinalContract)
    tables=[];columns=[];actual_builtins=builtin_observations()
    for index,e in enumerate(d['relations']):
        table=dict({k:v for k,v in e.items() if k!='columns'},oid=200+index,
            namespace_oid=2200,owner_oid=100,relrowsecurity=True,
            relforcerowsecurity=migrated,inheritance=False)
        tables.append(table)
        columns.extend(dict(c,attrelid=table['oid']) for c in e['columns'])
    _,statements=runner.migration_contract();helpers=[]
    for h in d['helpers']:
        body=next(q for q in statements if q.startswith('CREATE FUNCTION jous_security.'+h['name']+'(')).split('$function$')[1]
        helpers.append(dict(oid=301 if h['name']=='resolve_user' else 302,namespace_oid=300,
            schema='jous_security',namespace_owner='postgres',nspowner=100,proname=h['name'],proowner=50,
            prolang=14,language='sql',args=h['args'],returns=h['returns'],proargnames=h['argnames'],
            proargmodes=None,proallargtypes=None,prokind='f',prosecdef=True,provolatile='s',proparallel='u',
            proisstrict=False,proleakproof=False,proretset=False,provariadic=0,pronargdefaults=0,
            no_defaults=True,text_body=True,proconfig=['search_path=pg_catalog, pg_temp'],probin=None,prosrc=body))
    return {f.TARGET_SQL:[dict(d['target']['database'],server_version='17.11',server_version_num=170011)],
        f.ROLE_SQL:[dict(oid=100,rolname='postgres'),dict(oid=51,rolname='jous_runtime'),dict(oid=50,rolname='jous_security_reader')],
        f.TYPE_SQL:actual_builtins['types'],f.FUNCTION_SQL:actual_builtins['functions'],
        f.OPERATOR_SQL:actual_builtins['operators'],f.COLLATION_SQL:actual_builtins['collations'],
        f.RELATION_SQL:tables,f.COLUMN_SQL:columns,f.CREATED_SQL:helpers,
        f.CREATED_ACL_SQL:[dict(proname=h['name'],grantor=50,grantee=g,privilege_type='EXECUTE',is_grantable=False) for h in d['helpers'] for g in (50,51)],
        f.CREATED_SCHEMA_ACL_SQL:[dict(grantee=g,privilege_type='USAGE',is_grantable=False) for g in (50,51)]}


def synthetic_policies(module):
    f=runner.execution_contract();contract=f.load_final_contract()
    material=final_material(False)
    query=lambda c,sql,params=None:copy.deepcopy(material[sql])
    existing=f.freeze_pre_migration_bindings(None,contract,query)
    created=f.verify_created_security_objects(None,contract,existing,query)
    expected=f._read(f.instantiate_policy_expectations(contract,existing,created),f.ExpectedPolicySet)
    return [dict(row,policy_oid=1000+i) for i,row in enumerate(expected)]

_CATALOG_MODULE.APPROVED_POLICY_CONTRACT = synthetic_policies(runner.migration_contract()[0])
runner.catalog_contract = lambda: _CATALOG_MODULE

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


class PublicCatalog:
    """Catalog rows synthesized from the reviewed snapshot, not live expected learning.

    Mutations affect only observed rows. The production collector, schema validator
    and comparison run unchanged; no database/network calls are made.
    """
    def __init__(self):
        self.manifest=runner.public_contract()
        self.supplement=copy.deepcopy(runner.authorize_contract().load_amendment()['targeted_contract'])
        self.relations=copy.deepcopy(self.manifest['relations'])
        self.routines=copy.deepcopy(self.manifest['routines'])
        self.bindings=copy.deepcopy(self.manifest['rls_auto_enable']['bindings'])
        self.events=[]
        self.structural=copy.deepcopy({k:self.manifest[k] for k in ('target_contract','view_structures','default_structures','referent_bindings','dependency_contract')})
        self.function_sources={141:'int4mul',13616:'plpgsql_call_handler',13617:'plpgsql_inline_handler',13618:'plpgsql_validator'}
        self.types={}
        for e in self.routines:
            for t in e['identity_input_types']+[e['return_type']]+(e['all_argument_types'] or []):
                self.type_oid(t)
            if e['variadic_type']: self.type_oid(e['variadic_type'])
        for e in self.relations:
            for col in e['columns']: self.type_oid(col['type'])

    def type_oid(self,t):
        key=(t['schema'],t['name'])
        if key not in self.types:self.types[key]=len(self.types)+1
        return self.types[key]

    def result(self,s,params):
        for key,(sql,parameters) in _AUTHORIZE_MODULE.PROJECTIONS.items():
            if s==sql:
                if key in ('language_binding','namespace_binding'):
                    index=0 if key=='language_binding' else 1
                    return copy.deepcopy(self.supplement['dependency_bindings'][index]['rows'])
                return copy.deepcopy(self.supplement[key])
        if s==runner._DATABASE_QUERY:return [self.structural['target_contract']['database']]
        if s==runner._VIEW_QUERY:
            return [{k:v for k,v in e.items() if not k.endswith('_sha256')} for e in self.structural['view_structures']]
        if s==runner._DEFAULT_QUERY:
            return [{k:v for k,v in e.items() if not k.endswith('_sha256')} for e in self.structural['default_structures']]
        if s==runner._DEPENDENCY_QUERY:
            return [e for e in self.structural['dependency_contract']['edges'] if
                e['classid']==params['classid'] and e['objid'] in params['ids']]
        for kind,query in runner._STRUCTURAL_QUERIES.items():
            if s==query:
                result=copy.deepcopy(self.structural['referent_bindings'][kind])
                if kind=='functions':
                    for index,e in enumerate(result):
                        original=self.manifest['referent_bindings']['functions'][index % len(self.manifest['referent_bindings']['functions'])]
                        if original['oid'] in self.function_sources:
                            source=self.function_sources[original['oid']]
                        else:
                            source=next(r.get('source',r.get('entry_point_symbol')) for r in self.routines
                                if r['schema']==original['schema'] and r['name']==original['proname'])
                        e.pop('prosrc_sha256');e['prosrc']=source
                return result
        if 'SELECT t.oid,n.nspname AS schema,t.typname AS name' in s:
            return [dict(oid=oid,schema=t[0],name=t[1]) for t,oid in self.types.items()]
        if 'SELECT p.oid,n.nspname AS schema,p.proname AS name' in s:
            result=[]
            for oid,e in enumerate(self.routines,1000):
                ext=e['extension_membership'] or {}
                result.append(dict(oid=oid,schema=e['schema'],name=e['name'],display_args='unused',
                    kind=e['routine_kind'],input_types=[self.type_oid(t) for t in e['identity_input_types']],
                    all_types=None if e['all_argument_types'] is None else [self.type_oid(t) for t in e['all_argument_types']],
                    proargnames=e['parameter_names'],modes=e['parameter_modes'],
                    pronargdefaults=e['default_argument_count'],
                    return_type=self.type_oid(e['return_type']),proretset=e['returns_set'],
                    provariadic=self.type_oid(e['variadic_type']) if e['variadic_type'] else 0,
                    prosrc=e.get('source',e.get('entry_point_symbol')),parsed_sql_body=e['parsed_sql_body'],
                    probin=e.get('library_reference'),proconfig=e['proconfig'],prosecdef=e['security_definer'],
                    volatility=e['volatility'],parallel=e['parallel'],proisstrict=e['strict'],
                    proleakproof=e['leakproof'],lanname=e['language'],owner=e['owner'],
                    extname=ext.get('name'),extversion=ext.get('version'),**e['owner_attributes']))
            return result
        if 'SELECT c.oid,n.nspname AS schema,c.relname AS name' in s:
            return [dict(oid=oid,schema=e['schema'],name=e['name'],kind=e['object_type'],
                owner=e['owner'],reloptions=e['reloptions'],extname=(e['extension_membership'] or {}).get('name'),
                extversion=(e['extension_membership'] or {}).get('version'))
                for oid,e in enumerate(self.relations,2000)]
        if 'SELECT grantor.rolname AS grantor' in s:
            e=self.routines[params['oid']-1000] if 'FROM pg_catalog.pg_proc obj' in s else self.relations[params['oid']-2000]
            return e['public_acl']
        if 'SELECT attname AS name,atttypid AS type_oid' in s:
            return [dict(name=e['name'],type_oid=self.type_oid(e['type']),
                         type_modifier=e['type_modifier'],not_null=e['not_null'])
                    for e in self.relations[params['oid']-2000]['columns']]
        if 'SELECT e.evtname AS name' in s:return self.bindings
        if 'SELECT ev_action::pg_catalog.text AS nodes' in s:return [dict(nodes=self.relations[params['oid']-2000].get('view_nodes',''))]
        return None

    def execute(self,sql,params=None):
        s=str(sql);self.events.append(s)
        if s.startswith('SET LOCAL search_path'):return Result([])
        result=self.result(s,params or {})
        if result is None:raise AssertionError('Unmodelled PUBLIC catalog query')
        return Result(copy.deepcopy(result))

    def scalar(self,sql,params=None):
        self.events.append(str(sql))
        if str(sql)=='SHOW server_version':return self.structural['target_contract']['server_version']
        if str(sql)=='SHOW server_version_num':return str(self.structural['target_contract']['server_version_num'])
        if 'has_schema_privilege(:role,:schema' in str(sql):
            entries=[e for e in self.routines+self.relations if e['schema']==params['schema']]
            return entries[0]['schema_usage'][params['role']]
        raise AssertionError('Unmodelled PUBLIC scalar')

    def in_transaction(self):return True

    def routine_effective(self):
        return [dict(nspname=e['schema'],proname=e['name'],args='unused',
                     input_types=e['identity_input_types'],prokind=e['routine_kind'],role=role,
                     allowed=True,grantable=False)
                for e in self.routines for role in ('jous_runtime','jous_security_reader')]


class Catalog:
    """Independent shaped catalog fixtures; production assertions are not mocked."""
    def __init__(self):
        self.public=PublicCatalog()
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
        material=final_material(self.migrated)
        if s in material:return Result(copy.deepcopy(material[s]))
        public=self.public.result(s,params or {})
        if public is not None:return Result(copy.deepcopy(public))
        if 'SELECT d.datname FROM pg_catalog.pg_database' in s:return Result([])
        if 'SELECT n.nspname,r.rolname,a.privilege_type' in s:
            return Result([dict(nspname='jous_security',rolname=role,privilege_type='USAGE',is_grantable=False)
                for role in ('jous_runtime','jous_security_reader')] if self.migrated else [])
        if 'SELECT n.nspname,c.relname,att.attname,r.rolname' in s:
            return Result([dict(nspname='public',relname=t,attname=col,rolname=role,privilege_type=p,is_grantable=False)
                for role,contract in (('jous_runtime',runner.RUNTIME),('jous_security_reader',runner.READER))
                for t,privs in contract.items() for p,cols in privs.items() for col in cols] if self.migrated else [])
        if 'SELECT n.nspname,p.proname,r.rolname,' in s:
            return Result([dict(nspname='jous_security',proname=n,args=args,rolname=role,privilege_type='EXECUTE',is_grantable=False)
                for n,args in (('resolve_user','text, text'),('organization_is_active','uuid'))
                for role in ('jous_runtime','jous_security_reader')] if self.migrated else [])
        if 'SELECT att.attname FROM' in s:return Result([])
        if 'SELECT n.nspname,r.rolname FROM pg_catalog.pg_namespace' in s:
            return Result([dict(nspname=schema,rolname=role)
                for schema in (('public','jous_security') if self.migrated else ('public',))
                for role in ('jous_runtime','jous_security_reader')])
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
        if 'SELECT p.oid AS policy_oid' in s:
            return Result(synthetic_policies(self.module) if self.migrated else [])
        if 'SELECT n.nspname,p.proname,r.rolname AS owner' in s:
            return Result([dict(nspname='jous_security',proname=n,owner='jous_security_reader')
                for n in ('organization_is_active','resolve_user')] if self.migrated else [])
        if 'SELECT n.nspname,c.relname,r.rolname,a.privilege_type' in s:
            return Result([dict(nspname='public',relname='alembic_version',rolname='jous_runtime',
                privilege_type='SELECT',is_grantable=False)] if self.migrated else [])
        if 'SELECT n.nspname,c.relname,a.attname,r.role,p.priv' in s:
            result=[]
            for e in self.public.relations:
                for role in ('jous_runtime','jous_security_reader'):
                    result.extend(dict(nspname=e['schema'],relname=e['name'],attname=col['name'],
                        role=role,priv=p,allowed=p=='SELECT',grantable=False)
                        for col in e['columns'] for p in ('SELECT','INSERT','UPDATE','REFERENCES'))
            for role,contract in (('jous_runtime',runner.RUNTIME),('jous_security_reader',runner.READER)):
                for t,perms in contract.items():
                    for p,cols in perms.items():
                        result.extend(dict(nspname='public',relname=t,attname=col,role=role,priv=p,
                            allowed=self.migrated,grantable=False) for col in cols)
            result.append(dict(nspname='public',relname='alembic_version',attname='version_num',
                role='jous_runtime',priv='SELECT',allowed=self.migrated,grantable=False))
            return Result(result)
        if 'has_function_privilege' in s:
            return Result(self.public.routine_effective()+([dict(nspname='jous_security',proname=n,args=args,prokind='f',role=role,
                allowed=True,grantable=role=='jous_security_reader')
                for n,args in (('resolve_user','text, text'),('organization_is_active','uuid'))
                for role in ('jous_runtime','jous_security_reader')] if self.migrated else []))
        if 'p.proargtypes::pg_catalog.oid[] AS args' in s:
            result=[]
            for n in ('resolve_user','organization_is_active'):
                create=next(s for s in self.statements if s.startswith('CREATE FUNCTION jous_security.'+n+'('))
                result.append(dict(nspname='jous_security',namespace_oid=300,routine_oid=301 if n=='resolve_user' else 302,proargnames=['p_issuer','p_subject'] if n=='resolve_user'
                    else ['p_organization_id'],proargmodes=None,proallargtypes=None,pronargdefaults=0,
                    no_defaults=True,text_body=True,proname=n,args=[25,25] if n=='resolve_user' else [2950],
                    returns=2950 if n=='resolve_user' else 16,proowner=50,prosecdef=True,
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
        if s in ('SHOW server_version','SHOW server_version_num'):return self.public.scalar(sql,params)
        if 'has_schema_privilege(:role,:schema' in s:return self.public.scalar(sql,params)
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


class PublicCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.c=PublicCatalog()
        self.manifest=runner.load_public_manifest()

    def check(self):
        return runner.verify_public_compatibility(self.c)

    def reject_routine(self,field,value,language=None):
        entry=next(e for e in self.c.routines if language is None or e['language']==language)
        entry[field]=value
        with self.assertRaises(runner.Stop):self.check()

    def test_reviewed_full_catalog_and_capabilities(self):
        result=self.check()
        capabilities=result['routines']
        self.assertEqual(len(capabilities),97)
        self.assertEqual(len(result['relations']),2)
        self.assertTrue(all(e['object_acl_authority']=='PUBLIC_SELECT' and
            e['usable_object_capability']==dict(jous_runtime='SCHEMA_LOOKUP_BLOCKED',
                jous_security_reader='SCHEMA_LOOKUP_BLOCKED') for e in result['relations'].values()))
        self.assertEqual(len(self.manifest['relations']),2)
        self.assertEqual(sum(e['language']=='c' for e in self.manifest['routines']),48)
        self.assertEqual(sum(e['language'] in ('sql','plpgsql') for e in self.manifest['routines']),48)
        callback=next(e for e in self.manifest['routines'] if e['name']=='rls_auto_enable')
        self.assertEqual(capabilities[runner.routine_identity(callback)]['usable_object_capability'],
            dict(jous_runtime='REVIEWED_EVENT_CALLBACK_PUBLIC_ACL',
                 jous_security_reader='REVIEWED_EVENT_CALLBACK_PUBLIC_ACL'))
        for e in self.manifest['routines']:
            if e['schema']=='extensions' and e['execution_context']=='ordinary_function':
                self.assertEqual(capabilities[runner.routine_identity(e)]['usable_object_capability'],
                    dict(jous_runtime='SCHEMA_LOOKUP_BLOCKED',jous_security_reader='SCHEMA_LOOKUP_BLOCKED'))
        self.assertFalse(any('EXPLAIN' in s or 'PREPARE' in s for s in self.c.events))

    def test_pinned_manifest_bytes_and_counts(self):
        b=(ROOT/runner.MANIFEST_PATH).read_bytes()
        self.assertEqual(hashlib.sha256(b).hexdigest(),runner.MANIFEST_SHA)
        with self.assertRaisesRegex(runner.Stop,'MANIFEST_STRUCTURAL_SCHEMA'): runner.parse_manifest(b)

    def test_manifest_hash_mutation(self):
        with patch.object(Path,'read_bytes',return_value=(ROOT/runner.MANIFEST_PATH).read_bytes()+b' '):
            with self.assertRaisesRegex(runner.Stop,'MANIFEST_HASH'):runner.load_public_manifest()

    def test_manifest_closed_schema(self):
        import json
        cases=[]
        m=copy.deepcopy(self.manifest);m['unknown_security_rule']=True;cases.append(m)
        m=copy.deepcopy(self.manifest);m['manifest_version']=3;cases.append(m)
        m=copy.deepcopy(self.manifest);m['manifest_version']=True;cases.append(m)
        m=copy.deepcopy(self.manifest);del m['routines'];cases.append(m)
        m=copy.deepcopy(self.manifest);m['routines'][0]['trusted']=True;cases.append(m)
        m=copy.deepcopy(self.manifest);del m['routines'][0]['owner'];cases.append(m)
        m=copy.deepcopy(self.manifest);m['relations'][0]['schema_usage']['jous_runtime']='false';cases.append(m)
        m=copy.deepcopy(self.manifest);m['routines'][0]['owner']='x\u202ey';cases.append(m)
        for m in cases:
            with self.subTest(keys=list(m)),self.assertRaises(runner.Stop):
                runner.parse_manifest(json.dumps(m).encode())

    def test_manifest_duplicate_keys_and_nonfinite(self):
        b=(ROOT/runner.MANIFEST_PATH).read_bytes()
        for malformed in (b.replace(b'"manifest_version":2',b'"manifest_version":1,"manifest_version":1'),
                          b.replace(b'"manifest_version":2',b'"manifest_version":NaN'),
                          b.replace(b'"manifest_version":2',b'"manifest_version":Infinity')):
            with self.subTest(value=malformed[:15]),self.assertRaises(runner.Stop):runner.parse_manifest(malformed)

    def test_manifest_path_fixed_and_git_attested(self):
        self.assertIn(runner.MANIFEST_PATH,runner.IDENTITY_PATHS)
        self.assertEqual(runner.MANIFEST_PATH,'services/api/infrastructure/step7_public_compat_manifest.json')
        with tempfile.TemporaryDirectory() as directory,patch.object(runner,'ROOT',Path(directory)):
            with self.assertRaisesRegex(runner.Stop,'MANIFEST_PATH'):runner.load_public_manifest()

    def test_complete_inventory_rejects_unknown_routine_not_in_manifest(self):
        new=copy.deepcopy(self.c.routines[0]);new['name']='new_public_api'
        self.c.routines.append(new)
        with self.assertRaisesRegex(runner.Stop,'PUBLIC_ROUTINES_SET'):self.check()

    def test_new_overload(self):
        new=copy.deepcopy(self.c.routines[0]);new['identity_input_types']=[dict(schema='pg_catalog',name='text')]
        self.c.routines.append(new)
        with self.assertRaises(runner.Stop):self.check()

    def test_public_wrapper_and_jous_created_routine(self):
        for schema in ('public','jous_security','pgx'):
            self.c=PublicCatalog();new=copy.deepcopy(self.c.routines[0])
            new.update(schema=schema,name='unreviewed_wrapper',owner='postgres')
            self.c.routines.append(new)
            with self.subTest(schema=schema),self.assertRaises(runner.Stop):self.check()

    def test_new_procedure(self):
        self.reject_routine('routine_kind','p')

    def test_missing_and_duplicate_routine(self):
        for duplicate in (False,True):
            self.c=PublicCatalog()
            if duplicate:self.c.routines.append(copy.deepcopy(self.c.routines[0]))
            else:self.c.routines.pop()
            with self.subTest(duplicate=duplicate),self.assertRaises(runner.Stop):self.check()

    def test_new_relation_and_sequence(self):
        for kind in ('v','S','r'):
            self.c=PublicCatalog();new=copy.deepcopy(self.c.relations[0])
            new.update(schema='pgx',name='unexpected_public_object',object_type=kind)
            self.c.relations.append(new)
            with self.subTest(kind=kind),self.assertRaises(runner.Stop):self.check()

    def test_missing_relation(self):
        self.c.relations.pop()
        with self.assertRaises(runner.Stop):self.check()

    def test_relation_metadata_drift(self):
        for field,value in (('owner','attacker'),('reloptions',['security_invoker=true']),
                            ('object_type','m'),
                            ('extension_membership',dict(name='other',version='1.11'))):
            self.c=PublicCatalog();self.c.relations[0][field]=value
            with self.subTest(field=field),self.assertRaises(runner.Stop):self.check()

    def test_relation_column_identity_drift(self):
        for field,value in (('name','replaced'),('type',dict(schema='pg_catalog',name='text')),
                            ('type_modifier',10),('not_null',True)):
            self.c=PublicCatalog();col=self.c.relations[0]['columns'][0]
            if field=='type' and col[field]==value:value=dict(schema='pg_catalog',name='bool')
            if field=='not_null':value=not col[field]
            col[field]=value
            with self.subTest(field=field),self.assertRaises(runner.Stop):self.check()

    def test_public_acl_source_and_grant_option(self):
        for kind in ('routines','relations'):
            for field,value in (('grant_option',True),('grantor','attacker'),
                                ('privilege','INSERT'),('grantee','jous_runtime')):
                self.c=PublicCatalog();getattr(self.c,kind)[0]['public_acl'][0][field]=value
                with self.subTest(kind=kind,field=field),self.assertRaises(runner.Stop):self.check()

    def test_routine_metadata_drift(self):
        changes=[('owner','attacker'),('return_type',dict(schema='pg_catalog',name='void')),
            ('identity_input_types',[dict(schema='pg_catalog',name='uuid')]),
            ('security_definer',True),('proconfig',['search_path=public']),
            ('volatility','v'),('parallel','s'),('strict',True),('leakproof',True),
            ('parameter_names',['rebound']),('parameter_modes',['o']),
            ('default_argument_count',1),
            ('parsed_sql_body',True),('source','SELECT true;')]
        for field,value in changes:
            self.c=PublicCatalog();e=next(e for e in self.c.routines if e['schema']=='auth')
            if field in ('volatility','parallel','strict','leakproof') and e[field]==value:
                value=not value if type(value) is bool else ('s' if field=='volatility' else 'u')
            e[field]=value
            with self.subTest(field=field),self.assertRaises(runner.Stop):self.check()

    def test_extension_version_and_membership(self):
        for value in (dict(name='pgcrypto',version='1.4'),dict(name='other',version='1.3'),None):
            self.c=PublicCatalog()
            self.reject_routine('extension_membership',value,language='c')

    def test_c_library_and_symbol(self):
        for field in ('library_reference','entry_point_symbol'):
            self.c=PublicCatalog();self.reject_routine(field,'attacker',language='c')

    def test_owner_security_posture_drift(self):
        e=self.c.routines[0];e['owner_attributes']['rolsuper']=not e['owner_attributes']['rolsuper']
        with self.assertRaises(runner.Stop):self.check()

    def test_role_specific_schema_usage_drift(self):
        for role in ('jous_runtime','jous_security_reader'):
            for schema in ('auth','extensions','graphql_public','realtime','storage'):
                self.c=PublicCatalog()
                for e in self.c.routines+self.c.relations:
                    if e['schema']==schema:e['schema_usage'][role]=True
                with self.subTest(role=role,schema=schema),self.assertRaises(runner.Stop):self.check()

    def test_rls_callback_body_return_owner_definer_config(self):
        changes=[('source','BEGIN RETURN; END;'),('return_type',dict(schema='pg_catalog',name='void')),
                 ('owner','supabase_admin'),('security_definer',False),('proconfig',['search_path=public'])]
        for field,value in changes:
            self.c=PublicCatalog();e=next(e for e in self.c.routines if e['name']=='rls_auto_enable')
            e[field]=value
            with self.subTest(field=field),self.assertRaises(runner.Stop):self.check()

    def test_rls_callback_event_binding_drift(self):
        for mode in ('additional','missing','event','enabled','tags','owner'):
            self.c=PublicCatalog()
            if mode=='additional':self.c.bindings.append({**self.c.bindings[0],'name':'second'})
            elif mode=='missing':self.c.bindings=[]
            elif mode=='event':self.c.bindings[0]['event']='sql_drop'
            elif mode=='enabled':self.c.bindings[0]['enabled']='D'
            elif mode=='tags':self.c.bindings[0]['tags'].append('ALTER TABLE')
            else:self.c.bindings[0]['owner']='attacker'
            with self.subTest(mode=mode),self.assertRaises(runner.Stop):self.check()

    def test_direct_grants_cannot_hide_behind_public_compatibility(self):
        for role in ('jous_runtime','jous_security_reader'):
            for marker,entry in (
                ('SELECT n.nspname,c.relname,r.rolname,a.privilege_type',
                 dict(nspname='extensions',relname='pg_stat_statements',rolname=role,
                      privilege_type='SELECT',is_grantable=False)),
                ('SELECT n.nspname,p.proname,r.rolname,',
                 dict(nspname='auth',proname='uid',rolname=role,args='',privilege_type='EXECUTE',is_grantable=False)),
                ('SELECT n.nspname,c.relname,att.attname,r.rolname',
                 dict(nspname='extensions',relname='pg_stat_statements',attname='query',rolname=role,
                      privilege_type='SELECT',is_grantable=False))):
                c=Catalog();c.overrides[marker]=[entry]
                with self.subTest(role=role,marker=marker),self.assertRaises(runner.Stop):
                    runner.verify_grants(c,False)

    def test_direct_database_schema_public_column_and_default_grants(self):
        for marker,entry,reason in (
            ('SELECT d.datname FROM pg_catalog.pg_database',dict(datname='postgres'),'DIRECT_DATABASE_ACL'),
            ('SELECT n.nspname,r.rolname,a.privilege_type',dict(nspname='public',rolname='jous_runtime',privilege_type='CREATE',is_grantable=False),'DIRECT_SCHEMA_ACL'),
            ('SELECT att.attname FROM',dict(attname='query'),'PUBLIC_COLUMN_ACL'),
            ('SELECT d.oid,a.grantee',dict(oid=999,grantee=0,privilege_type='EXECUTE',is_grantable=False),'DEFAULT_PRIVILEGES')):
            c=Catalog();c.overrides[marker]=[entry]
            with self.subTest(marker=marker),self.assertRaisesRegex(runner.Stop,reason):
                runner.verify_grants(c,False)
            self.assertTrue(any(marker in sql for sql in c.events))

    def test_baseline_and_migrated_atomic_pipeline(self):
        c=Catalog()
        runner.pipeline(c,migrate=lambda c:setattr(c,'migrated',True))
        self.assertFalse(c.temp)
        self.assertEqual(c.events.count(runner.GRANT),1)
        self.assertEqual(c.events.count(runner.REVOKE),1)

    def test_public_drift_fails_before_temporary_membership(self):
        c=Catalog();c.public.routines.append(copy.deepcopy(c.public.routines[0]))
        with self.assertRaises(runner.Stop):runner.pipeline(c)
        self.assertNotIn(runner.GRANT,c.events)

    def test_manifest_failure_precedes_credential_access(self):
        with (patch.object(runner,'repository_gate'),patch.object(runner,'trusted_launch_gate'),
              patch.object(runner,'cached_jous_gate'),patch.object(runner,'load_public_manifest',
                  side_effect=runner.Stop('MANIFEST_HASH')),
              patch.object(runner.os.environ,'get',wraps=runner.os.environ.get) as credential,
              patch.object(runner,'create_async_engine') as engine,redirect_stdout(io.StringIO())):
            self.assertEqual(runner.main(['--confirm-managed-mutation',
                '--approved-execution-sha',APPROVED_SHA]),1)
        self.assertFalse(any(call.args[0] in ('JOUS_MIGRATION_DATABASE_URL','JOUS_DATABASE_URL')
            for call in credential.call_args_list))
        engine.assert_not_called()

    def test_effective_public_capability_matrix_complete(self):
        c=Catalog();c.overrides['p.prokind::pg_catalog.text AS prokind,r.role']=c.public.routine_effective()[:-1]
        with self.assertRaisesRegex(runner.Stop,'CAPABILITY_INCOMPLETE'):runner.verify_routines(c,False)

    def test_non_deparse_raw_drift(self):
        for kind,field,category in (('view_structures','ev_action','VIEW_STRUCTURES'),
                                   ('default_structures','raw_proargdefaults','DEFAULT_STRUCTURES')):
            for node in ('RELABELTYPE','COERCEVIAIO','COERCETODOMAIN','DOMAINVALUE','ROWEXPR',
                'ARRAYEXPR','SCALARARRAYOPEXPR','CASEEXPR','CASETESTEXPR','PARAM','VAR','FUNCEXPR',
                'OPEXPR','AGGREF','WINDOWFUNC','SUBLINK','SQLVALUEFUNCTION','COLLATEEXPR',
                'FIELDSELECT','FIELDSTORE','COALESCEEXPR','MINMAXEXPR','NULLTEST','BOOLEANTEST'):
                self.c=PublicCatalog()
                self.c.structural[kind][0][field]='{'+node+' :resulttype 999999 :resulttypmod 12}'
                with self.subTest(kind=kind,node=node),self.assertRaisesRegex(runner.Stop,'STRUCTURAL_'+category+'_DRIFT'):
                    self.check()
                self.assertFalse(any(re.search(r'pg_get_|format_type|oidvectortypes|regtype|regclass|regprocedure',sql) for sql in self.c.events))

    def test_finite_referent_and_dependency_drift(self):
        mutations=[('types','typname','attacker'),('types','oid',999999),
            ('functions','proname','attacker'),('functions','proconfig',['search_path=public']),
            ('operators','implementation_oid',999999),('columns','atttypmod',77),
            ('namespaces','nspowner',999999),('namespaces','nspname','attacker'),
            ('extensions','extversion','9.9'),('languages','lanplcallfoid',999999),
            ('collations','collprovider','i')]
        for kind,field,value in mutations:
            self.c=PublicCatalog();self.c.structural['referent_bindings'][kind][0][field]=value
            with self.subTest(kind=kind,field=field),self.assertRaisesRegex(runner.Stop,'STRUCTURAL_'+kind.upper()):self.check()
        for action in ('add','remove'):
            self.c=PublicCatalog();edges=self.c.structural['dependency_contract']['edges']
            if action=='remove':edges.pop()
            else:edges.append({**edges[0],'refobjid':999999})
            with self.subTest(action=action),self.assertRaisesRegex(runner.Stop,'STRUCTURAL_DEPENDENCIES_SET'):self.check()

    def test_database_and_version_drift(self):
        for field,value in dict(oid=99,datname='other',encoding=8,datlocprovider='c',
            datcollate='C',datctype='C',datlocale='other',daticurules='new',datcollversion='999').items():
            self.c=PublicCatalog();self.c.structural['target_contract']['database'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(runner.Stop,'STRUCTURAL_DATABASE_DRIFT'):self.check()
        self.c=PublicCatalog();self.c.structural['target_contract']['server_version']='17.12'
        with self.assertRaisesRegex(runner.Stop,'STRUCTURAL_POSTGRES_VERSION'):self.check()

    def test_manifest_v2_missing_duplicate_and_unknown_data(self):
        import json
        for category in ('types','functions','namespaces','languages','extensions','operators','collations','relations','columns'):
            for action in ('missing','duplicate','unknown_key'):
                m=copy.deepcopy(self.manifest);entries=m['referent_bindings'][category]
                if action=='missing':entries.pop()
                elif action=='duplicate':entries.append(copy.deepcopy(entries[0]))
                else:entries[0]['unreviewed_semantics']=True
                with self.subTest(category=category,action=action),self.assertRaisesRegex(runner.Stop,'MANIFEST_'):
                    runner.parse_manifest(json.dumps(m).encode())

    def test_operator_implementation_wal_layout_and_plpgsql_drift(self):
        for category,oid,field,value in (
            ('functions',141,'prosqlbody_present',True),
            ('functions',141,'proretset',True),
            ('operators',514,'oprresult',25),
            ('types',17326,'typrelid',999999),
            ('columns',17324,'attname','other'),
            ('languages',13619,'laninline',999999)):
            self.c=PublicCatalog();entries=self.c.structural['referent_bindings'][category]
            e=next(e for e in entries if e.get('oid',e.get('attrelid'))==oid);e[field]=value
            with self.subTest(category=category,field=field),self.assertRaisesRegex(runner.Stop,'STRUCTURAL_'+category.upper()+'_DRIFT'):self.check()

    def test_structural_missing_duplicate_and_empty_database(self):
        for category in ('types','functions','columns'):
            for action in ('missing','duplicate'):
                self.c=PublicCatalog();entries=self.c.structural['referent_bindings'][category]
                if action=='missing':entries.pop()
                else:entries.append(copy.deepcopy(entries[0]))
                with self.subTest(category=category,action=action),self.assertRaisesRegex(runner.Stop,'STRUCTURAL_'+category.upper()+'_SET'):self.check()
        self.c=PublicCatalog();original=self.c.result
        with patch.object(self.c,'result',side_effect=lambda sql,params:[] if sql==runner._DATABASE_QUERY else original(sql,params)):
            with self.assertRaisesRegex(runner.Stop,'STRUCTURAL_DATABASE_DRIFT'):self.check()

    def test_builtin_implementation_source_drift(self):
        self.c.function_sources[141]='unreviewed_int4mul'
        with self.assertRaisesRegex(runner.Stop,'STRUCTURAL_FUNCTIONS_DRIFT'):self.check()

    def test_no_native_formatters_in_production_collection(self):
        self.check()
        self.assertFalse(any(re.search(r'pg_get_|format_type|oidvectortypes|regtype|regclass|regprocedure|collation_actual_version',sql) for sql in self.c.events))

    def test_catalog_collection_never_uses_shadowable_relation_or_type_names(self):
        self.check()
        for sql in self.c.events:
            with self.subTest(sql=sql[:90]):
                self.assertFalse(re.search(r'\b(?:FROM|JOIN)\s+pg_(?:proc|type|namespace|class|roles|attribute|rewrite|depend|extension|event_trigger)\b',sql))
                self.assertFalse(re.search(r'::(?:text|oid|regclass|"char")\b',sql))


# Independent wire expectations: installed asyncpg CHAROID uses its bytea codec.
# SQL text projection changes the result type; production never decodes bytes.
_DRIVER_CHAR_FIELDS = {
 'database': ('',{'datlocprovider':'i'}),
 'view': ('w',{'ev_type':'1','ev_enabled':'O'}),
 'types': ('t',{'typtype':'b','typcategory':'B','typalign':'c'}),
 'functions': ('p',{'prokind':'f','provolatile':'i','proparallel':'s'}),
 'operators': ('o',{'oprkind':'b'}),
 'collations': ('c',{'collprovider':'d'}),
 'relations': ('c',{'relkind':'v'}),
 'dependencies': ('',{'deptype':'i'}),
}


def char_query(kind):
    return {'database':runner._DATABASE_QUERY,'view':runner._VIEW_QUERY,
            'dependencies':runner._DEPENDENCY_QUERY}.get(kind,runner._STRUCTURAL_QUERIES.get(kind))


def char_projection(alias,field):
    qualified=(alias+'.' if alias else '')+field
    return r'(?<![\w.])'+re.escape(qualified)+r'::pg_catalog\.text\s+AS\s+'+field+r'\b'


class DriverCharCatalog(PublicCatalog):
    """Inert driver model keyed to explicit SQL result projections, not a codec change."""
    def __init__(self):
        super().__init__();self.char_mutations={};self.before_projection=[]
    def result(self,sql,params):
        result=super().result(sql,params)
        if result is None:return None
        for kind,(alias,expected) in _DRIVER_CHAR_FIELDS.items():
            if sql!=char_query(kind):continue
            result=copy.deepcopy(result)
            for index,row in enumerate(result):
                for field,independent in expected.items():
                    # First rows have independently specified baseline values; remaining
                    # rows retain the reviewed catalog values while modeling wire types.
                    value=independent if index==0 and (kind!='dependencies' or row['classid']==1247) else row[field]
                    if (kind,field) in self.char_mutations and index==0:value=self.char_mutations[kind,field]
                    wire=value.encode('ascii');self.before_projection.append(wire)
                    row[field]=wire.decode('ascii') if re.search(char_projection(alias,field),sql) else wire
            return result
        return result


class DriverRepresentationTests(unittest.TestCase):
    def test_every_projection_casts_source_field_to_its_alias(self):
        for kind,(alias,fields) in _DRIVER_CHAR_FIELDS.items():
            for field in fields:
                with self.subTest(kind=kind,field=field):
                    self.assertRegex(char_query(kind),char_projection(alias,field))
        # Existing internal-char array and complete PUBLIC scalar projections.
        self.assertIn('p.proargmodes::pg_catalog.text[] AS parameter_modes',runner._DEFAULT_QUERY)
        self.assertIn('p.proargmodes::pg_catalog.text[] AS modes',runner._STRUCTURAL_QUERIES['functions'])

    def test_effective_routine_and_helper_projection_aliases(self):
        c=Catalog();original=c.execute
        def wire(sql,params=None):
            result=original(sql,params)
            if 'p.prokind::pg_catalog.text AS prokind,r.role' in str(sql):
                cast=bool(re.search(char_projection('p','prokind'),str(sql)))
                for row in result.value:row['prokind']='f' if cast else b'f'
            return result
        with patch.object(c,'execute',side_effect=wire):runner.verify_routines(c,False)
        actual=next(sql for sql in c.events if 'p.prokind::pg_catalog.text AS prokind,r.role' in sql)
        self.assertRegex(actual,char_projection('p','prokind'))
        c.migrated=True;runner.verify_helpers(c,c.statements,{'jous_runtime':51,'jous_security_reader':50})
        actual=next(sql for sql in c.events if 'p.prorettype AS returns' in sql)
        for field in ('prokind','provolatile','proparallel'):self.assertRegex(actual,char_projection('p',field))

    def test_driver_shaped_unchanged_baseline_passes(self):
        c=DriverCharCatalog();runner.verify_structural_contract(c,c.manifest)
        self.assertTrue(c.before_projection)
        self.assertTrue(all(type(v) is bytes for v in c.before_projection))

    def test_missing_cast_reproduces_bytes_rejection(self):
        c=DriverCharCatalog();original=c.result
        def uncast_result(sql,params):
            result=original(sql,params)
            if sql==runner._DATABASE_QUERY:
                result[0]['datlocprovider']=b'i'
            return result
        with patch.object(c,'result',side_effect=uncast_result):
            with self.assertRaisesRegex(runner.Stop,'^STRUCTURAL_DATABASE_DRIFT$'):
                runner.verify_structural_contract(c,c.manifest)

    def test_each_representative_char_drift_still_fails(self):
        categories={'database':'DATABASE','view':'VIEW_STRUCTURES','dependencies':'DEPENDENCIES'}
        for kind,(alias,fields) in _DRIVER_CHAR_FIELDS.items():
            for field in fields:
                c=DriverCharCatalog();c.char_mutations[kind,field]='x'
                reason='STRUCTURAL_'+categories.get(kind,kind.upper())+('_SET' if kind=='dependencies' else '_DRIFT')
                with self.subTest(kind=kind,field=field),self.assertRaisesRegex(runner.Stop,'^'+reason+'$'):
                    runner.verify_structural_contract(c,c.manifest)


class OidDomainTests(unittest.TestCase):
    def setUp(self):self.manifest=runner.load_public_manifest()
    def parse(self,data):
        import json
        return runner.parse_manifest(json.dumps(data).encode())
    def test_all_required_reference_and_identity_domains(self):
        for kind,required,optional in (
            ('types',('oid','namespace_oid','typowner'),('typelem','typarray','typbasetype','typrelid','typcollation')),
            ('functions',('oid','pronamespace','proowner','prolang','prorettype'),()),
            ('namespaces',('oid','nspowner'),()),('languages',('oid','lanowner','lanplcallfoid'),('laninline','lanvalidator')),
            ('language_names',('oid',),()),('extensions',('oid','extnamespace','extowner'),()),
            ('operators',('oid','oprleft','oprright','oprresult','implementation_oid'),('oprcom','oprnegate','restriction_oid','join_oid')),
            ('collations',('oid',),()),('relations',('oid','relowner','reltype'),('reloftype',)),
            ('columns',('attrelid','atttypid'),('attcollation',))):
            for field in required+optional:
                for invalid in ((-1,True,4294967296) if field in optional else (-1,0,True,4294967296)):
                    data=copy.deepcopy(self.manifest);data['referent_bindings'][kind][0][field]=invalid
                    with self.subTest(kind=kind,field=field,value=invalid),self.assertRaisesRegex(runner.Stop,'MANIFEST_(OID_DOMAIN|STRUCTURAL_SCHEMA)'):
                        self.parse(data)
    def test_independent_column_and_dependency_negative_probes(self):
        for field in ('classid','objid','refclassid','refobjid','objsubid','refobjsubid'):
            for invalid in (-1,True):
                data=copy.deepcopy(self.manifest);data['dependency_contract']['edges'][0][field]=invalid
                reason='MANIFEST_SUBOBJECT_DOMAIN' if field.endswith('subid') else 'MANIFEST_OID_DOMAIN'
                with self.subTest(field=field,value=invalid),self.assertRaisesRegex(runner.Stop,
                    'MANIFEST_STRUCTURAL_SCHEMA' if type(invalid) is bool else reason):self.parse(data)
        for field,invalid in [('attrelid',-1),('attrelid',0),('attnum',-1),('attnum',0),('attnum',32768)]:
            data=copy.deepcopy(self.manifest);data['referent_bindings']['columns'][0][field]=invalid
            with self.subTest(field=field,value=invalid),self.assertRaisesRegex(runner.Stop,
                'MANIFEST_OID_DOMAIN' if field=='attrelid' else 'MANIFEST_SUBOBJECT_DOMAIN'):self.parse(data)
    def test_array_and_structural_root_oid_domains(self):
        for kind,key in [('view_structures','ev_class'),('default_structures','routine_oid')]:
            data=copy.deepcopy(self.manifest);data[kind][0][key]=0
            with self.subTest(kind=kind),self.assertRaisesRegex(runner.Stop,'MANIFEST_OID_DOMAIN'):self.parse(data)
        data=copy.deepcopy(self.manifest);data['default_structures'][0]['input_type_oids'][0]=-1
        with self.assertRaisesRegex(runner.Stop,'MANIFEST_OID_DOMAIN'):self.parse(data)
    def test_reviewed_zero_sentinels_and_non_oid_negatives_preserved(self):
        parsed=self.parse(self.manifest)
        self.assertEqual(parsed,self.manifest)
        self.assertEqual(parsed['referent_bindings']['types'][0]['typelem'],0)
        self.assertEqual(parsed['referent_bindings']['operators'][0]['oprnegate'],0)
        self.assertEqual(parsed['dependency_contract']['edges'][0]['objsubid'],0)
        self.assertEqual(parsed['referent_bindings']['collations'][0]['collencoding'],-1)
        self.assertTrue(any(e['typlen']==-1 for e in parsed['referent_bindings']['types']))
        self.assertTrue(any(e['atttypmod']==-1 for e in parsed['referent_bindings']['columns']))


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
            fresh = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fresh)
            fresh.load_dependencies()
            fresh._VERIFIED_SOURCES = {p.relative_to(ROOT).as_posix(): p.read_bytes().replace(b'\r\n',b'\n')
                for directory in ('services/api/src/jous_api','services/api/migrations')
                for p in (ROOT/directory).rglob('*.py')}
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as e:
                fresh.main(['--help'])
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
        data=self.c.execute('p.proargtypes::pg_catalog.oid[] AS args').all(); data[0]['proowner']=100
        self.c.overrides['p.proargtypes::pg_catalog.oid[] AS args']=data
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
        for field,value in (('policy_name','unexpected'),('role_oids',[0]),('command','d'),
                            ('permissive',False),('using_tree','true')):
            with self.subTest(field=field):
                self.c=Catalog(); b=self.migrated()
                data=self.c.execute('SELECT p.oid AS policy_oid').all()
                data[1][field]=value
                self.c.overrides['SELECT p.oid AS policy_oid']=data
                with self.assertRaises(runner.Stop): runner.verify_security(self.c,b)
    def test_raw_policy_contract_is_exact_and_never_evaluated(self):
        contract = runner.catalog_contract()
        baseline = copy.deepcopy(contract.APPROVED_POLICY_CONTRACT)
        for key,value in (('using_tree', None),('using_tree','changed'),('check_tree',True),
                          ('policy_oid',True),('relation_oid',0),('role_oids',[True])):
            observed=copy.deepcopy(baseline);observed[0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                contract.verify_policy_records(observed,baseline)
        contract.verify_policy_records(baseline,baseline)
        with self.assertRaises(ValueError):contract.verify_policy_records(baseline,None)
        with self.assertRaises(ValueError):contract.verify_policy_records(baseline+[baseline[0]],baseline)

    def test_helper_parameter_binding_and_identity(self):
        for name in ('resolve_user','organization_is_active'):
            for field,value in (('proargnames',['p_subject','p_issuer']),('proargmodes',['i']),
                ('pronargdefaults',1),('no_defaults',False),('text_body',False),('nspname','pgx')):
                c=Catalog(); b=runner.preflight(c); c.migrated=True
                data=c.execute('SELECT p.proargtypes::pg_catalog.oid[] AS args').all()
                target=next(r for r in data if r['proname']==name); target[field]=value
                c.overrides['p.proargtypes::pg_catalog.oid[] AS args']=data
                with self.subTest(name=name,field=field), self.assertRaisesRegex(runner.Stop,'HELPER_DEFINITION'):
                    runner.verify_security(c,b)

    def test_namespace_filter_semantics_offline(self):
        contract=runner.catalog_contract()
        self.assertEqual(' '.join(runner.USER_NAMESPACE.split()),
                         ' '.join(contract.USER_NAMESPACE.split()))
        for name in ('pgx','pga','pg1','public','jous_security','pg_temp_abc','pg_foo','pg_attacker'):
            self.assertTrue(contract.user_namespace(name))
        for name in ('pg_catalog','information_schema','pg_toast','pg_temp_12','pg_toast_temp_12'):
            self.assertFalse(contract.user_namespace(name))

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
                        c.overrides['p.prokind::pg_catalog.text AS prokind,r.role']=data
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
        # An isolated module/import namespace exercises actual installed loaders.
        # Fake DBAPI only: no external process or PostgreSQL connection.
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
        modules = {name:module for name,module in sys.modules.items()
                   if name != 'jous_api' and not name.startswith('jous_api.')}
        with (patch.dict(sys.modules,modules,clear=True),patch.object(sys,'meta_path',list(sys.meta_path)),
              patch.object(sys,'path',list(sys.path)),redirect_stdout(io.StringIO()) as output):
            exec(compile(code,'<offline-source-integration>','exec'),{})
        self.assertIn('OFFLINE_SOURCE_ONLY_0002_PASS',output.getvalue())



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
