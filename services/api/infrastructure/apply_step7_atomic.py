"""Opt-in operator migration. Import/help are offline; never use at app startup."""
# sys is built-in; os/path are frozen on the supported CPython launch.
# Remove repository search paths BEFORE importing any shadowable library.
import sys
import os
if os.__spec__.origin != 'frozen' or os.path.__spec__.origin != 'frozen':
    raise RuntimeError('TRUSTED_CPYTHON_REQUIRED')
_BOOT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
def _repository_path(value):
    path = os.path.normcase(os.path.realpath(value or os.getcwd()))
    root = os.path.normcase(_BOOT_ROOT)
    # The reviewed operator's venv installation is a trusted startup/dependency
    # boundary, not repository source. Its site hooks cannot be attested here.
    venv = os.path.join(root, '.venv')
    return (path == root or path.startswith(root + os.sep)) and not (
        path == venv or path.startswith(venv + os.sep))
sys.path[:] = [value for value in sys.path if not _repository_path(value)]
sys.dont_write_bytecode = True  # Reading caches is addressed separately below.

import argparse
import base64
import asyncio
import hashlib
import importlib.util
from pathlib import Path
import re
import ssl
import subprocess
from urllib.parse import urlsplit

# Installed dependencies are deliberately deferred until the execution gate.
command = Config = text = dialect = make_url = create_async_engine = NullPool = None
_APPROVED_SHA = None
_VERIFIED_SOURCES = {}


def load_dependencies():
    global command, Config, text, dialect, make_url, create_async_engine, NullPool
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql.asyncpg import dialect
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool


ROOT = Path(__file__).resolve().parents[3]
MIGRATION_BLOB = 'cae08d9cf548480fb5d064becca1e89ca2dd898b'
MIGRATION_PATH = 'services/api/migrations/versions/0002_runtime_rls.py'
IDENTITY_PATHS = ('services/api/infrastructure/apply_step7_atomic.py',
    'services/api/migrations', 'services/api/alembic.ini',
    'services/api/infrastructure/runtime_roles.sql', 'services/api/src/jous_api',
    'services/api/pyproject.toml', 'services/api/requirements.lock',
    'services/api/infrastructure/step7_realtime_authorize_amendment.py',
    'services/api/infrastructure/step7_realtime_authorize_amendment.json',
    'services/api/infrastructure/step7_operator514_amendment.json',
    'services/api/infrastructure/step7_policy_template_contract.json',
    'services/api/infrastructure/step7_public_compat_manifest.json')
CA_SHA = '807025ad50d4ed219d2c9c7d299c004f824eb00cf7f65afef607d07b72e6cafa'
PROJECT = 'aqcixpoorbhjgvdkdjqd'
TABLES = ('users', 'organizations', 'organization_memberships', 'projects')
GRANT = ('GRANT jous_security_reader TO postgres '
         'WITH ADMIN FALSE, INHERIT FALSE, SET TRUE GRANTED BY postgres')
REVOKE = 'REVOKE jous_security_reader FROM postgres GRANTED BY postgres RESTRICT'
LOCK = int.from_bytes(hashlib.sha256(b'jous/core.1a/step7/atomic').digest()[:8], 'big', signed=True)


class Stop(RuntimeError):
    """Messages are fixed categories, never external exception strings."""


def require(ok, category):
    if not ok:
        raise Stop(category)


def repository_gate(approved_sha, run=subprocess.run):
    # The separately approved commit is an external trust anchor, not derived from HEAD.
    require(isinstance(approved_sha, str) and re.fullmatch('[0-9a-f]{40}', approved_sha),
            'APPROVED_EXECUTION_SHA_REQUIRED')
    def git(*args, binary=False):
        result = run(['git', *args], cwd=ROOT, capture_output=True, text=not binary, check=True)
        return result.stdout if binary else result.stdout.strip()
    try:
        require(git('rev-parse', 'HEAD') == approved_sha, 'REPOSITORY_HEAD')
        require(git('rev-parse', 'origin/main') == approved_sha, 'REPOSITORY_ORIGIN')
        require(not git('status', '--porcelain', '--untracked-files=no'), 'REPOSITORY_DIRTY')
        entries = git('ls-tree', '-r', '--full-tree', approved_sha, '--', *IDENTITY_PATHS)
        artifacts = {}
        verified_sources = {}
        for entry in entries.splitlines():
            metadata, name = entry.split('\t', 1)
            mode, kind, blob = metadata.split()
            require(mode in ('100644', '100755') and kind == 'blob', 'ARTIFACT_KIND')
            require(name not in artifacts, 'ARTIFACT_DUPLICATE')
            artifacts[name] = blob
            path = ROOT / name
            require(not path.is_symlink() and path.is_file(), 'ARTIFACT_MISSING')
            # Git blobs contain LF canonical bytes; tolerate only checkout CRLF conversion.
            content = path.read_bytes().replace(b'\r\n', b'\n')
            require(content == git('cat-file', 'blob', blob, binary=True), 'ARTIFACT_MISMATCH')
            if name.endswith('.py'):
                verified_sources[name] = content
        for name in IDENTITY_PATHS:
            path = ROOT / name
            if path.is_dir():
                present = {item.relative_to(ROOT).as_posix() for item in path.rglob('*')
                           if item.is_file() and '__pycache__' not in item.parts}
                require(present == {key for key in artifacts if key.startswith(name + '/')},
                        'ARTIFACT_TREE_MISMATCH')
            else:
                require(name in artifacts, 'ARTIFACT_MISSING')
        require(artifacts.get(MIGRATION_PATH) == MIGRATION_BLOB, 'MIGRATION_IDENTITY')
        # Include committed infrastructure siblings as approved imports, but never
        # accept untracked files there or anywhere under src/migrations.
        all_entries = git('ls-tree', '-r', '--full-tree', approved_sha, '--',
                          'services/api/infrastructure', 'services/api/src', 'services/api/migrations')
        surface = {entry.split('\t', 1)[1] for entry in all_entries.splitlines()}
        execution_surface_gate(surface)
        global _VERIFIED_SOURCES
        _VERIFIED_SOURCES = verified_sources
    except Stop:
        raise
    except Exception:
        raise Stop('REPOSITORY_UNAVAILABLE') from None


def execution_surface_gate(artifacts):
    """No repository bytecode or unapproved executable imports; never remove files."""
    surfaces = ('services/api/infrastructure', 'services/api/migrations', 'services/api/src')
    for name in surfaces:
        for path in (ROOT / name).rglob('*'):
            require(not path.is_symlink(), 'EXECUTION_SYMLINK')
            require(path.name.lower() != '__pycache__' and path.suffix.lower() not in ('.pyc', '.pyo'),
                    'REPOSITORY_BYTECODE')
            if path.is_file() and path.suffix.lower() in ('.py', '.pth', '.pyd', '.so', '.dll'):
                require(path.relative_to(ROOT).as_posix() in artifacts, 'UNAPPROVED_IMPORT_SURFACE')
    # Root is removed from sys.path, and must never be reintroduced by dependencies.
    require(not any(_repository_path(value) for value in sys.path), 'REPOSITORY_IMPORT_PATH')


def cached_jous_gate():
    """Require a fresh application namespace; origin never substitutes for identity."""
    require(not any(name == 'jous_api' or name.startswith('jous_api.')
                    for name in tuple(sys.modules)), 'PRELOADED_JOUS_MODULE')


def trusted_launch_gate():
    require(sys.flags.isolated and sys.flags.ignore_environment and sys.dont_write_bytecode,
            'ISOLATED_LAUNCH_REQUIRED')
    # Startup hooks already ran; the documented interpreter/site installation is trusted.
    for module in tuple(sys.modules.values()):
        path = getattr(module, '__file__', None)
        require(not path or not _repository_path(path) or
                os.path.realpath(path) == os.path.realpath(__file__), 'PRELOADED_REPOSITORY_MODULE')


def verified_module(module_id, path):
    """Compile reviewed source bytes directly; no SourceFileLoader/cache lookup."""
    from types import ModuleType
    path = Path(path).resolve()
    require(path.suffix == '.py' and path.is_relative_to(ROOT), 'SOURCE_PATH')
    content = path.read_bytes().replace(b'\r\n', b'\n')
    name = path.relative_to(ROOT).as_posix()
    if name == MIGRATION_PATH:
        blob = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        require(blob == MIGRATION_BLOB, 'MIGRATION_IDENTITY')
    else:
        require(_VERIFIED_SOURCES.get(name) == content, 'SOURCE_IDENTITY')
    module = ModuleType(module_id)
    module.__file__ = str(path)
    module.__package__ = module_id if path.name == '__init__.py' else module_id.rpartition('.')[0]
    exec(compile(content, str(path), 'exec', dont_inherit=True), module.__dict__)
    return module


def install_source_importer():
    cached_jous_gate()
    # Only the verified Jous package is needed by env.py. No repository path is
    # added to sys.path, so untracked namespace/shadow packages cannot participate.
    import importlib.abc
    class Loader(importlib.abc.Loader):
        def __init__(self, path): self.path = path
        def create_module(self, spec): return None
        def exec_module(self, module):
            loaded = verified_module(module.__name__, self.path)
            module.__dict__.update({key:value for key,value in loaded.__dict__.items()
                                  if key not in ('__spec__','__loader__','__package__')})
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname != 'jous_api' and not fullname.startswith('jous_api.'):
                return None
            relative = 'services/api/src/' + fullname.replace('.', '/')
            package = relative + '/__init__.py'
            source = package if package in _VERIFIED_SOURCES else relative + '.py'
            require(source in _VERIFIED_SOURCES, 'UNAPPROVED_REPOSITORY_IMPORT')
            return importlib.util.spec_from_file_location(fullname, ROOT/source,
                loader=Loader(ROOT/source), submodule_search_locations=[] if source == package else None)
    sys.meta_path.insert(0, Finder())


def approved_ca(pem):
    # Full match rules out bundles, PEM preambles and ignored trailing input.
    require(isinstance(pem, str) and re.fullmatch(
        r'\s*-----BEGIN CERTIFICATE-----\r?\n[A-Za-z0-9+/=\r\n\t ]+\r?\n-----END CERTIFICATE-----\s*',
        pem), 'CA_SINGLE_CERTIFICATE')
    try:
        payload = re.search(r'-----BEGIN CERTIFICATE-----\s*(.*?)\s*-----END CERTIFICATE-----',
                            pem, re.S).group(1)
        compact = re.sub(r'[\r\n\t ]', '', payload)
        der = base64.b64decode(compact, validate=True)
        require(base64.b64encode(der).decode('ascii') == compact, 'CA_BASE64')
        require(hashlib.sha256(der).hexdigest() == CA_SHA, 'CA_FINGERPRINT')
        # DER cadata loads precisely this certificate and no default trust roots.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=der)
        require(context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
                and context.get_ca_certs(binary_form=True) == [der], 'TLS_REQUIRED')
        return context
    except Stop:
        raise
    except Exception:
        raise Stop('CA_UNAVAILABLE') from None


# Exact system namespaces and numeric PostgreSQL temporary namespaces only.
# In particular pgx/pga/pg1 remain user schemas and are always audited.
USER_NAMESPACE = """n.nspname NOT IN ('pg_catalog','information_schema','pg_toast')
    AND n.nspname !~ '^pg_(temp|toast_temp)_[0-9]+$'"""


MANIFEST_PATH = 'services/api/infrastructure/step7_public_compat_manifest.json'
MANIFEST_SHA = '60efef97d11e85a0be679a32f5aa3163f35017f4bebf8d6120bdb183731734e0'

# A deliberately closed data schema; optional SQL NULL is distinct from empty arrays.
_TYPE = {'schema':'str','name':'str'}
_ACL = {'grantor':'str','grantee':'str','privilege':'str','grant_option':'bool'}
_USAGE = {'jous_runtime':'bool','jous_security_reader':'bool'}
_EXTENSION = {'name':'str','version':'str'}
_OWNER = {key:'bool' for key in ('rolsuper','rolbypassrls','rolcreatedb',
    'rolcreaterole','rolreplication','rolinherit','rolcanlogin')}
_ROUTINE = dict(schema='str',name='str',routine_kind='str',
    identity_input_types=[_TYPE],return_type=_TYPE,returns_set='bool',
    parameter_names=('null',['str']),parameter_modes=('null',['str']),
    all_argument_types=('null',[_TYPE]),default_argument_count='int',
    variadic_type=('null',_TYPE),
    owner='str',owner_attributes=_OWNER,language='str',security_definer='bool',
    volatility='str',parallel='str',strict='bool',leakproof='bool',
    proconfig=('null',['str']),public_acl=[_ACL],direct_jous_grants=[],
    extension_membership=('null',_EXTENSION),schema_usage=_USAGE,
    execution_context='str',parsed_sql_body='bool')
_RELATION = dict(schema='str',name='str',object_type='str',owner='str',
    public_acl=[_ACL],direct_jous_grants=[],extension_membership=_EXTENSION,
    columns=[dict(name='str',type=_TYPE,type_modifier='int',not_null='bool')],
    reloptions=('null',['str']),schema_usage=_USAGE)
_BINDING = dict(name='str',event='str',enabled='str',tags=['str'],owner='str')
_SPECIAL = dict(schema='str',name='str',identity_input_types=[_TYPE],
    source_sha256='str',bindings=[_BINDING])


_REFERENTS = {'collations': [{'collcollate': ('null', 'str'),
                 'collctype': ('null', 'str'),
                 'collencoding': 'int',
                 'collisdeterministic': 'bool',
                 'colllocale': ('null', 'str'),
                 'collname': 'str',
                 'collprovider': 'str',
                 'collversion': ('null', 'str'),
                 'oid': 'int',
                 'schema': 'str'}],
 'columns': [{'attcollation': 'int',
              'attisdropped': 'bool',
              'attname': 'str',
              'attnotnull': 'bool',
              'attnum': 'int',
              'attrelid': 'int',
              'atttypid': 'int',
              'atttypmod': 'int'}],
 'extensions': [{'extname': 'str',
                 'extnamespace': 'int',
                 'extowner': 'int',
                 'extversion': 'str',
                 'oid': 'int'}],
 'functions': [{'input_type_oids': ['int'],
                'lanname': 'str',
                'modes': ('null', ['str']),
                'oid': 'int',
                'owner': 'str',
                'proallargtypes': ('null', ['int']),
                'proargnames': ('null', ['str']),
                'probin': ('null', 'str'),
                'proconfig': ('null', ['str']),
                'proisstrict': 'bool',
                'prokind': 'str',
                'prolang': 'int',
                'proleakproof': 'bool',
                'proname': 'str',
                'pronamespace': 'int',
                'pronargdefaults': 'int',
                'proowner': 'int',
                'proparallel': 'str',
                'proretset': 'bool',
                'prorettype': 'int',
                'prosecdef': 'bool',
                'prosqlbody_present': 'bool',
                'prosrc_sha256': 'str',
                'provolatile': 'str',
                'schema': 'str'}],
 'language_names': [{'lanname': 'str', 'oid': 'int'}],
 'languages': [{'laninline': 'int',
                'lanispl': 'bool',
                'lanname': 'str',
                'lanowner': 'int',
                'lanplcallfoid': 'int',
                'lanpltrusted': 'bool',
                'lanvalidator': 'int',
                'oid': 'int'}],
 'namespaces': [{'nspname': 'str', 'nspowner': 'int', 'oid': 'int'}],
 'operators': [{'oprcanmerge': 'bool', 'oprcanhash': 'bool', 'implementation_oid': 'int',
                'join_oid': 'int',
                'oid': 'int',
                'oprcom': 'int',
                'oprkind': 'str',
                'oprleft': 'int',
                'oprname': 'str',
                'oprnegate': 'int',
                'oprresult': 'int',
                'oprright': 'int',
                'restriction_oid': 'int',
                'schema': 'str'}],
 'relations': [{'oid': 'int',
                'owner': 'str',
                'relkind': 'str',
                'relname': 'str',
                'reloftype': 'int',
                'reloptions': ('null', ['str']),
                'relowner': 'int',
                'reltype': 'int',
                'schema': 'str'}],
 'types': [{'namespace_oid': 'int',
            'oid': 'int',
            'schema': 'str',
            'typalign': 'str',
            'typarray': 'int',
            'typbasetype': 'int',
            'typbyval': 'bool',
            'typcategory': 'str',
            'typcollation': 'int',
            'typelem': 'int',
            'typlen': 'int',
            'typname': 'str',
            'typowner': 'int',
            'typrelid': 'int',
            'typtype': 'str',
            'typtypmod': 'int'}]}
_VIEW_STRUCTURE = {'ev_action': 'str', 'ev_action_sha256': 'str', 'ev_class': 'int', 'ev_enabled': 'str', 'ev_qual': 'str', 'ev_qual_sha256': 'str', 'ev_type': 'str', 'is_instead': 'bool', 'oid': 'int', 'relname': 'str', 'rulename': 'str', 'schema': 'str'}
_DEFAULT_STRUCTURE = {'all_argument_type_oids': ('null', ['int']), 'default_argument_count': 'int', 'input_type_oids': ['int'], 'name': 'str', 'parameter_modes': ('null', ['str']), 'parameter_names': ('null', ['str']), 'raw_proargdefaults': 'str', 'raw_proargdefaults_sha256': 'str', 'routine_oid': 'int', 'schema': 'str'}
_TARGET = {'project_ref': 'str', 'server_version': 'str', 'server_version_num': 'int', 'database': {'datcollate': 'str', 'datcollversion': 'str', 'datctype': 'str', 'daticurules': ('null', 'str'), 'datlocale': 'str', 'datlocprovider': 'str', 'datname': 'str', 'encoding': 'int', 'oid': 'int'}}
_DEPENDENCIES = {'roots': [{'classid': 'int', 'objid': 'int'}], 'edges': [{'classid': 'int', 'deptype': 'str', 'objid': 'int', 'objsubid': 'int', 'refclassid': 'int', 'refobjid': 'int', 'refobjsubid': 'int'}]}

def data_shape(value, schema):
    """Validate exact keys and Python types; JSON booleans are never integers."""
    if isinstance(schema, tuple):
        return any(data_shape(value, item) for item in schema)
    if isinstance(schema, dict):
        return type(value) is dict and set(value)==set(schema) and all(
            data_shape(value[key], spec) for key,spec in schema.items())
    if isinstance(schema, list):
        return type(value) is list and (not value if not schema else
            all(data_shape(item,schema[0]) for item in value))
    return (value is None if schema=='null' else
            type(value) is {'str':str,'bool':bool,'int':int}[schema])


def routine_identity(entry):
    return (entry['schema'],entry['name'],entry['routine_kind'],
        tuple((t['schema'],t['name']) for t in entry['identity_input_types']))


def parse_manifest(content):
    """Data-only parser. Never evaluate defaults, bodies, identities or paths."""
    import json
    import unicodedata
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'MANIFEST_DUPLICATE_KEY')
            result[key]=value
        return result
    def invalid_constant(value):
        raise Stop('MANIFEST_NONFINITE')
    try:
        require(type(content) is bytes and len(content)<1000000,'MANIFEST_SIZE')
        data=json.loads(content.decode('utf-8'),object_pairs_hook=pairs,
                        parse_constant=invalid_constant)
        def unicode_check(value):
            if isinstance(value,str):
                require(not any(unicodedata.category(c) in ('Cf','Cs') or
                    (unicodedata.category(c)=='Cc' and c not in '\t\n\r') for c in value),
                        'MANIFEST_UNICODE')
            elif isinstance(value,dict):
                for key,item in value.items(): unicode_check(key); unicode_check(item)
            elif isinstance(value,list):
                for item in value: unicode_check(item)
        unicode_check(data)
        top={'manifest_schema','manifest_version','reviewed_extension_versions',
             'relations','routines','rls_auto_enable','target_contract','view_structures',
             'default_structures','referent_bindings','dependency_contract'}
        require(type(data) is dict and set(data)==top,'MANIFEST_SCHEMA')
        require(data['manifest_schema']=='jous.step7.public-compatibility'
                and type(data['manifest_version']) is int and data['manifest_version']==2,
                'MANIFEST_VERSION')
        require(data['reviewed_extension_versions']==
                {'pgcrypto':'1.3','uuid-ossp':'1.1','pg_stat_statements':'1.11'},
                'MANIFEST_EXTENSIONS')
        require(data_shape(data['relations'],[_RELATION]),'MANIFEST_RELATION_SCHEMA')
        require(type(data['routines']) is list,'MANIFEST_ROUTINE_SCHEMA')
        for entry in data['routines']:
            require(type(entry) is dict,'MANIFEST_ROUTINE_SCHEMA')
            extra=(dict(library_reference='str',entry_point_symbol='str')
                   if entry.get('language')=='c' else
                   dict(source='str',source_sha256='str',fingerprint_algorithm='str'))
            require(data_shape(entry,{**_ROUTINE,**extra}),'MANIFEST_ROUTINE_SCHEMA')
            require(valid_default_count(entry['default_argument_count'], len(entry['identity_input_types'])), 'MANIFEST_DEFAULT_COUNT')
            require(entry['language'] in ('c','sql','plpgsql')
                    and entry['routine_kind']=='f' and not entry['parsed_sql_body'],
                    'MANIFEST_ROUTINE_KIND')
            require(entry['public_acl']==[dict(grantor=entry['owner'],grantee='PUBLIC',
                    privilege='EXECUTE',grant_option=False)],'MANIFEST_ACL')
            require(all(v is (entry['schema']=='public') for v in entry['schema_usage'].values()),
                    'MANIFEST_REACHABILITY')
            if entry['language']=='c':
                require(entry['extension_membership'] is not None and
                    entry['extension_membership']['version']==data['reviewed_extension_versions'].get(
                        entry['extension_membership']['name']), 'MANIFEST_C_EXTENSION')
            else:
                require(hashlib.sha256(entry['source'].encode('utf-8')).hexdigest()==entry['source_sha256']
                    and re.fullmatch('[0-9a-f]{64}',entry['source_sha256']) and
                    entry['fingerprint_algorithm']=='SHA256_UTF8_PROSRC_EXACT','MANIFEST_FINGERPRINT')
        require(data_shape(data['rls_auto_enable'],_SPECIAL),'MANIFEST_SPECIAL_SCHEMA')
        require(len(data['relations'])==2 and len(data['routines'])==96,'MANIFEST_COUNTS')
        ids=[routine_identity(e) for e in data['routines']]
        require(len(set(ids))==96,'MANIFEST_IDENTITIES')
        counts={schema:sum(e['schema']==schema for e in data['routines'])
                for schema in ('auth','extensions','graphql_public','public','realtime','storage')}
        require(counts==dict(auth=4,extensions=54,graphql_public=1,public=1,realtime=17,storage=19)
                and sum(e['language']=='c' for e in data['routines'])==48,'MANIFEST_COUNTS')
        require({(e['schema'],e['name']) for e in data['relations']}==
                {('extensions','pg_stat_statements'),('extensions','pg_stat_statements_info')},
                'MANIFEST_RELATIONS')
        for entry in data['relations']:
            require(entry['object_type']=='v' and entry['owner']=='postgres'
                and entry['public_acl']==[dict(grantor='postgres',grantee='PUBLIC',
                    privilege='SELECT',grant_option=False)]
                and entry['extension_membership']==dict(name='pg_stat_statements',version='1.11')
                and entry['schema_usage']==dict(jous_runtime=False,jous_security_reader=False)
,
                'MANIFEST_RELATION_CONTRACT')
        special=data['rls_auto_enable']
        callback=next(e for e in data['routines'] if e['schema']=='public' and e['name']=='rls_auto_enable')
        require(special==dict(schema='public',name='rls_auto_enable',identity_input_types=[],
                source_sha256='2782e98b348aca7d6f6f73c420fd78d2e094957dd7a52b0483d4c34f29d2a7a1',
                bindings=[dict(name='ensure_rls',event='ddl_command_end',enabled='O',
                    tags=['CREATE TABLE','CREATE TABLE AS','SELECT INTO'],owner='postgres')])
                and callback['source_sha256']==special['source_sha256']
                and callback['return_type']==dict(schema='pg_catalog',name='event_trigger')
                and callback['language']=='plpgsql' and callback['owner']=='postgres'
                and callback['security_definer'] is True and callback['proconfig']==['search_path=pg_catalog']
                and callback['extension_membership'] is None
                and callback['execution_context']=='event_trigger'
                and not callback['identity_input_types']
                and [routine_identity(e) for e in data['routines'] if e['security_definer']]==
                    [routine_identity(callback)],'MANIFEST_EVENT_CALLBACK')
        validate_structural_manifest(data)
        return data
    except Stop:
        raise
    except Exception:
        raise Stop('MANIFEST_INVALID') from None


# SQL projections are trusted source constants, never manifest-generated SQL.
_STRUCTURAL_QUERIES = {
 'types': """SELECT t.oid,t.typnamespace AS namespace_oid,n.nspname AS schema,t.typname,
 t.typowner,t.typtype::pg_catalog.text AS typtype,t.typcategory::pg_catalog.text AS typcategory,t.typlen,t.typbyval,t.typalign::pg_catalog.text AS typalign,t.typelem,t.typarray,
 t.typbasetype,t.typrelid,t.typtypmod,t.typcollation FROM pg_catalog.pg_type t
 JOIN pg_catalog.pg_namespace n ON n.oid=t.typnamespace WHERE t.oid=ANY(:ids)""",
 'functions': """SELECT p.oid,n.nspname AS schema,p.proname,p.pronamespace,p.proowner,
 r.rolname AS owner,p.prolang,l.lanname,p.prokind::pg_catalog.text AS prokind,p.proargtypes::pg_catalog.oid[] AS input_type_oids,
 p.proallargtypes,p.proargnames,p.proargmodes::pg_catalog.text[] AS modes,p.pronargdefaults,
 p.prorettype,p.proretset,p.probin,p.prosrc,p.proconfig,p.prosecdef,p.provolatile::pg_catalog.text AS provolatile,
 p.proparallel::pg_catalog.text AS proparallel,p.proisstrict,p.proleakproof,(p.prosqlbody IS NOT NULL) AS prosqlbody_present
 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
 JOIN pg_catalog.pg_roles r ON r.oid=p.proowner JOIN pg_catalog.pg_language l ON l.oid=p.prolang
 WHERE p.oid=ANY(:ids)""",
 'namespaces': 'SELECT oid,nspname,nspowner FROM pg_catalog.pg_namespace WHERE oid=ANY(:ids)',
 'languages': """SELECT oid,lanname,lanowner,lanispl,lanpltrusted,lanplcallfoid,laninline,
 lanvalidator FROM pg_catalog.pg_language WHERE oid=ANY(:ids)""",
 'language_names': 'SELECT oid,lanname FROM pg_catalog.pg_language WHERE oid=ANY(:ids)',
 'extensions': 'SELECT oid,extname,extversion,extnamespace,extowner FROM pg_catalog.pg_extension WHERE oid=ANY(:ids)',
 'operators': """SELECT o.oid,n.nspname AS schema,o.oprname,o.oprkind::pg_catalog.text AS oprkind,o.oprleft,o.oprright,
 o.oprcanmerge,o.oprcanhash,o.oprresult,o.oprcode::pg_catalog.oid AS implementation_oid,o.oprcom,o.oprnegate,
 o.oprrest::pg_catalog.oid AS restriction_oid,o.oprjoin::pg_catalog.oid AS join_oid FROM pg_catalog.pg_operator o
 JOIN pg_catalog.pg_namespace n ON n.oid=o.oprnamespace WHERE o.oid=ANY(:ids)""",
 'collations': """SELECT c.oid,n.nspname AS schema,c.collname,c.collprovider::pg_catalog.text AS collprovider,c.collencoding,
 c.collisdeterministic,c.collcollate,c.collctype,c.colllocale,c.collversion
 FROM pg_catalog.pg_collation c JOIN pg_catalog.pg_namespace n ON n.oid=c.collnamespace
 WHERE c.oid=ANY(:ids)""",
 'relations': """SELECT c.oid,n.nspname AS schema,c.relname,c.relkind::pg_catalog.text AS relkind,c.relowner,r.rolname AS owner,
 c.reltype,c.reloftype,c.reloptions FROM pg_catalog.pg_class c
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_catalog.pg_roles r ON r.oid=c.relowner WHERE c.oid=ANY(:ids)""",
 'columns': """SELECT attrelid,attnum,attname,atttypid,atttypmod,attcollation,attisdropped,attnotnull
 FROM pg_catalog.pg_attribute WHERE attrelid=ANY(:ids) AND attnum>0""",
}
_VIEW_QUERY = """SELECT w.oid,w.ev_class,n.nspname AS schema,c.relname,w.rulename,w.ev_type::pg_catalog.text AS ev_type,
 w.ev_enabled::pg_catalog.text AS ev_enabled,w.is_instead,w.ev_qual::pg_catalog.text AS ev_qual,
 w.ev_action::pg_catalog.text AS ev_action FROM pg_catalog.pg_rewrite w
 JOIN pg_catalog.pg_class c ON c.oid=w.ev_class
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE w.oid=ANY(:ids)"""
_DEFAULT_QUERY = """SELECT p.oid AS routine_oid,n.nspname AS schema,p.proname AS name,
 p.proargtypes::pg_catalog.oid[] AS input_type_oids,p.proallargtypes AS all_argument_type_oids,
 p.proargnames AS parameter_names,p.proargmodes::pg_catalog.text[] AS parameter_modes,
 p.pronargdefaults AS default_argument_count,p.proargdefaults::pg_catalog.text AS raw_proargdefaults
 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
 WHERE p.oid=ANY(:ids)"""
_DATABASE_QUERY = """SELECT oid,datname,encoding,datlocprovider::pg_catalog.text AS datlocprovider,datcollate,datctype,datlocale,
 daticurules,datcollversion FROM pg_catalog.pg_database WHERE datname=pg_catalog.current_database()"""
_DEPENDENCY_QUERY = """SELECT classid,objid,objsubid,refclassid,refobjid,refobjsubid,deptype::pg_catalog.text AS deptype
 FROM pg_catalog.pg_depend WHERE classid=:classid AND objid=ANY(:ids)"""


def structural_key(kind, entry):
    if kind=='columns': return (entry['attrelid'],entry['attnum'])
    return entry['oid']


# Catalog OIDs are unsigned 32-bit identifiers. Zero denotes absence only in
# explicitly optional reference fields, never real identity/owner fields.
_OID_FIELDS = {
 'types': (('oid','namespace_oid','typowner'),
           ('typelem','typarray','typbasetype','typrelid','typcollation')),
 'functions': (('oid','pronamespace','proowner','prolang','prorettype'),()),
 'namespaces': (('oid','nspowner'),()),
 'languages': (('oid','lanowner','lanplcallfoid'),('laninline','lanvalidator')),
 'language_names': (('oid',),()),
 'extensions': (('oid','extnamespace','extowner'),()),
 'operators': (('oid','oprleft','oprright','oprresult','implementation_oid'),
               ('oprcom','oprnegate','restriction_oid','join_oid')),
 'collations': (('oid',),()),
 'relations': (('oid','relowner','reltype'),('reloftype',)),
 'columns': (('attrelid','atttypid'),('attcollation',)),
}


def catalog_oid(value, optional=False):
    return type(value) is int and (0 if optional else 1)<=value<=4294967295


def validate_catalog_domains(data):
    def fields(entry, required, optional=()):
        require(all(catalog_oid(entry[k]) for k in required) and
                all(catalog_oid(entry[k],True) for k in optional),'MANIFEST_OID_DOMAIN')
    fields(data['target_contract']['database'],('oid',))
    for kind,entries in data['referent_bindings'].items():
        for entry in entries:
            fields(entry,*_OID_FIELDS[kind])
            if kind=='columns':
                require(type(entry['attnum']) is int and 1<=entry['attnum']<=32767,
                        'MANIFEST_SUBOBJECT_DOMAIN')
            if kind=='functions':
                require(valid_default_count(entry['pronargdefaults'], len(entry['input_type_oids'])), 'MANIFEST_DEFAULT_COUNT')
                require(all(catalog_oid(v) for v in entry['input_type_oids']) and
                    (entry['proallargtypes'] is None or all(catalog_oid(v) for v in entry['proallargtypes'])),
                    'MANIFEST_OID_DOMAIN')
    for entry in data['view_structures']:fields(entry,('oid','ev_class'))
    for entry in data['default_structures']:
        require(valid_default_count(entry['default_argument_count'], len(entry['input_type_oids'])), 'MANIFEST_DEFAULT_COUNT')
        fields(entry,('routine_oid',))
        require(all(catalog_oid(v) for v in entry['input_type_oids']) and
            (entry['all_argument_type_oids'] is None or
             all(catalog_oid(v) for v in entry['all_argument_type_oids'])), 'MANIFEST_OID_DOMAIN')
    for entry in data['dependency_contract']['roots']:fields(entry,('classid','objid'))
    for entry in data['dependency_contract']['edges']:
        fields(entry,('classid','objid','refclassid','refobjid'))
        require(all(type(entry[k]) is int and 0<=entry[k]<=2147483647
                    for k in ('objsubid','refobjsubid')),'MANIFEST_SUBOBJECT_DOMAIN')


def validate_structural_manifest(data):
    for key,schema in (('target_contract',_TARGET),('view_structures',[_VIEW_STRUCTURE]),
        ('default_structures',[_DEFAULT_STRUCTURE]),('referent_bindings',_REFERENTS),
        ('dependency_contract',_DEPENDENCIES)):
        require(data_shape(data[key],schema),'MANIFEST_STRUCTURAL_SCHEMA')
    validate_catalog_domains(data)
    required = {
        'types': {16,17,20,23,25,26,701,1009,1184,1700,2249,2278,2280,2281,2950,2951,3802,16409,16426,17326},
        'functions': {141,13616,13617,13618,16406,16423,16665,17327,17346,17367,17368,17591,17592,17594,17596,17598,17599},
        'namespaces': {11,16392,16546,16559,16567},'languages': {13619},
        'language_names': {12,13,14,13619},'extensions': {13615,16393},
        'operators': {514},'collations': {100},'relations': {16407,16424,17324}}
    refs=data['referent_bindings']
    for kind,entries in refs.items():
        keys=[structural_key(kind,e) for e in entries]
        require(len(keys)==len(set(keys)),'MANIFEST_STRUCTURAL_DUPLICATE')
        require((len(keys)==55 if kind=='columns' else set(keys)==required[kind]),
                'MANIFEST_REFERENTS')
    require(data['target_contract']==dict(project_ref=PROJECT,server_version='17.11',
        server_version_num=170011,database=dict(oid=5,datname='postgres',encoding=6,
        datlocprovider='i',datcollate='en_US.UTF-8',datctype='en_US.UTF-8',datlocale='en-US',
        daticurules=None,datcollversion='153.121')),'MANIFEST_TARGET')
    require({(e['oid'],e['ev_class']) for e in data['view_structures']}==
        {(16410,16407),(16427,16424)} and len(data['view_structures'])==2,'MANIFEST_VIEW_ROOTS')
    defaults=data['default_structures']
    require(len(defaults)==11 and {e['routine_oid'] for e in defaults}==
        required['functions']-{141,13616,13617,13618,16406,16423},'MANIFEST_DEFAULT_ROOTS')
    for entry in data['view_structures']:
        for key in ('ev_action','ev_qual'):
            require(hashlib.sha256(entry[key].encode('utf-8')).hexdigest()==entry[key+'_sha256'],
                'MANIFEST_RAW_HASH')
    for entry in defaults:
        require(hashlib.sha256(entry['raw_proargdefaults'].encode('utf-8')).hexdigest()==
            entry['raw_proargdefaults_sha256'],'MANIFEST_RAW_HASH')
    for entry in refs['functions']:
        require(re.fullmatch('[0-9a-f]{64}',entry['prosrc_sha256']) is not None,
                'MANIFEST_REFERENT_HASH')
    dep=data['dependency_contract']
    roots=[(e['classid'],e['objid']) for e in dep['roots']]
    edges=[tuple(e[k] for k in sorted(e)) for e in dep['edges']]
    require(len(roots)==len(set(roots)) and len(edges)==len(set(edges))==47,
        'MANIFEST_DEPENDENCIES')
    require(all((e['classid'],e['objid']) in roots for e in dep['edges']),
        'MANIFEST_DEPENDENCY_ROOT')
    classes={'types':1247,'functions':1255,'relations':1259,'languages':2612,
             'operators':2617,'collations':3456}
    required_roots={(classes[kind],e['oid']) for kind in classes for e in refs[kind]}
    required_roots.update((2618,e['oid']) for e in data['view_structures'])
    require(set(roots)==required_roots,'MANIFEST_DEPENDENCY_ROOTS')



def exact_structural_rows(actual, expected, key, category):
    observed=[key(e) for e in actual]
    require(len(observed)==len(set(observed)) and set(observed)=={key(e) for e in expected},
        'STRUCTURAL_'+category+'_SET')
    require({key(e):e for e in actual}=={key(e):e for e in expected},
        'STRUCTURAL_'+category+'_DRIFT')


def verify_structural_contract(c, manifest):
    """Built-in catalog scalars only: no referenced code, formatter or AST parser."""
    target=manifest['target_contract']
    require(c.scalar(text('SHOW server_version'))==target['server_version'] and
        c.scalar(text('SHOW server_version_num'))==str(target['server_version_num']),
        'STRUCTURAL_POSTGRES_VERSION')
    actual=rows(c,_DATABASE_QUERY)
    require(actual==[target['database']],'STRUCTURAL_DATABASE_DRIFT')
    for kind,query,oidkey,rawfields in (
        ('view_structures',_VIEW_QUERY,'oid',('ev_qual','ev_action')),
        ('default_structures',_DEFAULT_QUERY,'routine_oid',('raw_proargdefaults',))):
        expected=manifest[kind]
        actual=rows(c,query,dict(ids=[e[oidkey] for e in expected]))
        for e in actual:
            if kind=='default_structures':
                require(valid_default_count(e['default_argument_count'],len(e['input_type_oids'])),
                        'STRUCTURAL_DEFAULT_COUNT')
            for field in rawfields:
                require(type(e[field]) is str,'STRUCTURAL_RAW_TYPE')
                e[field+'_sha256']=hashlib.sha256(e[field].encode('utf-8')).hexdigest()
        exact_structural_rows(actual,expected,lambda e:e[oidkey],kind.upper())
    for kind,query in _STRUCTURAL_QUERIES.items():
        expected=manifest['referent_bindings'][kind]
        ids=sorted({e['attrelid'] if kind=='columns' else e['oid'] for e in expected})
        actual=rows(c,query,dict(ids=ids))
        if kind=='functions':
            for e in actual:
                require(valid_default_count(e['pronargdefaults'],len(e['input_type_oids'])),
                        'STRUCTURAL_DEFAULT_COUNT')
                e['prosrc_sha256']=hashlib.sha256(e.pop('prosrc').encode('utf-8')).hexdigest()
        if kind=='operators':
            require(all(type(e.get(field)) is bool for e in actual
                        for field in ('oprcanmerge','oprcanhash')), 'STRUCTURAL_OPERATOR_BOOLEAN')
        exact_structural_rows(actual,expected,lambda e:structural_key(kind,e),kind.upper())
    actual=[]
    roots=manifest['dependency_contract']['roots']
    for classid in sorted({e['classid'] for e in roots}):
        actual.extend(rows(c,_DEPENDENCY_QUERY,dict(classid=classid,
            ids=[e['objid'] for e in roots if e['classid']==classid])))
    exact_structural_rows(actual,manifest['dependency_contract']['edges'],
        lambda e:tuple(e[k] for k in sorted(e)),'DEPENDENCIES')


def load_public_manifest():
    # Compact UTF-8/no literal newlines survives Git autocrlf without accepting
    # alternative bytes. Any byte drift stops, unlike Python checkout source.
    path=ROOT/MANIFEST_PATH
    require(path.is_file() and not path.is_symlink(),'MANIFEST_PATH')
    content=path.read_bytes()
    require(hashlib.sha256(content).hexdigest()==MANIFEST_SHA,'MANIFEST_HASH')
    amended = execution_contract().apply_m1(execution_contract().parse(content))
    return parse_manifest(execution_contract().canonical(amended))


def _compare_public_inventory(actual, manifest):
    # Pure metadata comparator only; never independently sufficient for approval.
    """Complete set equality, followed by exact metadata/ACL/reachability equality."""
    require(type(actual) is dict and set(actual)=={'relations','routines','bindings'},
            'PUBLIC_INVENTORY_SHAPE')
    for kind,identity in (('relations',lambda e:(e['schema'],e['name'])),
                          ('routines',routine_identity)):
        observed=actual[kind]; expected=manifest[kind]
        keys=[identity(e) for e in observed]
        require(len(keys)==len(set(keys)) and set(keys)=={identity(e) for e in expected},
                'PUBLIC_'+kind.upper()+'_SET')
        by_id={identity(e):e for e in expected}
        for entry in observed:
            if kind=='routines':
                require(valid_default_count(entry['default_argument_count'],len(entry['identity_input_types'])),
                        'PUBLIC_DEFAULT_COUNT')
            require(entry==by_id[identity(entry)],'PUBLIC_'+kind.upper()+'_DRIFT')
    require(actual['bindings']==manifest['rls_auto_enable']['bindings'],'PUBLIC_EVENT_BINDINGS')
    # ACL remains authority even for blocked lookup; context is not a generic safety flag.
    routine_capabilities = {
        routine_identity(e):dict(object_acl_authority='PUBLIC_EXECUTE',
            usable_object_capability={
                role:('REVIEWED_EVENT_CALLBACK_PUBLIC_ACL' if e['execution_context']=='event_trigger'
                      else 'TRIGGER_CONTEXT_PUBLIC_ACL' if e['execution_context']=='trigger'
                      else 'SCHEMA_LOOKUP_REACHABLE' if usage else 'SCHEMA_LOOKUP_BLOCKED')
                for role,usage in e['schema_usage'].items()})
        for e in actual['routines']}
    relation_capabilities = {
        (e['schema'],e['name']):dict(object_acl_authority='PUBLIC_SELECT',
            usable_object_capability={role:('SCHEMA_LOOKUP_REACHABLE' if usage else
                'SCHEMA_LOOKUP_BLOCKED') for role,usage in e['schema_usage'].items()})
        for e in actual['relations']}
    return dict(routines=routine_capabilities,relations=relation_capabilities)


def public_contract():
    # Recheck bytes on every verification; no mutable live-state learning/cache.
    supplement = authorize_contract()
    supplement.load_amendment()  # Exact SHA before parsing/using supplement.
    execution_contract().load_final_contract()  # Mandatory policy/referent gate.
    base = load_public_manifest()
    base['routines'].append(supplement.routine_entry())
    require(len(base['routines']) == 97 and len({routine_identity(x) for x in
            base['routines']}) == 97, 'COMPOSED_PUBLIC_IDENTITIES')
    return base


_FINAL_CONTRACT_MODULE = None

def execution_contract():
    global _FINAL_CONTRACT_MODULE
    path = ROOT/'services/api/src/jous_api/step7_execution_contract.py'
    content = path.read_bytes().replace(b'\r\n', b'\n')
    require(_VERIFIED_SOURCES.get(path.relative_to(ROOT).as_posix()) == content, 'SOURCE_IDENTITY')
    if _FINAL_CONTRACT_MODULE is None:
        _FINAL_CONTRACT_MODULE = verified_module('step7_execution_contract', path)
    return _FINAL_CONTRACT_MODULE


def final_gate(operation, *args):
    try:
        return operation(*args)
    except execution_contract().ContractRejected as error:
        raise Stop(str(error)) from None


def authorize_contract():
    return verified_module('step7_authorize_contract',
        ROOT/'services/api/infrastructure/step7_realtime_authorize_amendment.py')


def verify_public_compatibility(c):
    # The only production approval gate: live supplement AND exact 97 inventory.
    return _compare_public_inventory(public_inventory(c), public_contract())

def public_inventory(c):
    try:
        return collect_public_inventory(c)
    except Stop:
        raise
    except Exception:
        raise Stop('PUBLIC_CATALOG_INVALID') from None


def collect_public_inventory(c):
    """Catalog-only complete PUBLIC ACL inventory; no routine is invoked."""
    import json
    q = lambda sql, params=None: rows(c, sql, params)
    digest = lambda value: hashlib.sha256(value.encode('utf-8')).hexdigest()
    role_names = ('jous_runtime', 'jous_security_reader')
    try:
        authorize_contract().collect_snapshot(c, rows)
    except ValueError as error:
        raise Stop(str(error) if str(error).startswith(('AUTHORIZE_', 'AMENDMENT_'))
                   else 'AUTHORIZE_CATALOG_INVALID') from None
    verify_structural_contract(c, public_contract())
    type_map = {x['oid']: {'schema': x['schema'], 'name': x['name']} for x in q('SELECT t.oid,n.nspname AS schema,t.typname AS name FROM pg_catalog.pg_type t JOIN pg_catalog.pg_namespace n ON n.oid=t.typnamespace')}
    usage = lambda schema: {role: c.scalar(text("SELECT pg_catalog.has_schema_privilege(:role,:schema,'USAGE')"), {'role': role, 'schema': schema}) for role in role_names}

    def public_acl(table, oid, relkind=None):
        acl, owner, kind = ('proacl', 'proowner', 'f') if table == 'pg_catalog.pg_proc' else ('relacl', 'relowner', 's' if relkind == 'S' else 'r')
        return q("SELECT grantor.rolname AS grantor,'PUBLIC' AS grantee,a.privilege_type AS privilege,a.is_grantable AS grant_option FROM " + table + ' obj CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(obj.' + acl + ",pg_catalog.acldefault('" + kind + "',obj." + owner + '))) a LEFT JOIN pg_catalog.pg_roles grantor ON grantor.oid=a.grantor WHERE obj.oid=:oid AND a.grantee=0 ORDER BY 1,3', {'oid': oid})
    routine_sql = "SELECT p.oid,n.nspname AS schema,p.proname AS name,p.prokind::pg_catalog.text AS kind,p.proargtypes::pg_catalog.oid[] AS input_types,p.proallargtypes AS all_types,p.proargnames,p.proargmodes::pg_catalog.text[] AS modes,p.pronargdefaults,p.prorettype AS return_type,p.proretset,p.provariadic,p.prosrc,p.prosqlbody IS NOT NULL AS parsed_sql_body,p.probin,p.proconfig,p.prosecdef,p.provolatile::pg_catalog.text AS volatility,p.proparallel::pg_catalog.text AS parallel,p.proisstrict,p.proleakproof,l.lanname,o.rolname AS owner,o.rolsuper,o.rolbypassrls,o.rolcreatedb,o.rolcreaterole,o.rolreplication,o.rolinherit,o.rolcanlogin,e.extname,e.extversion FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace JOIN pg_catalog.pg_roles o ON o.oid=p.proowner JOIN pg_catalog.pg_language l ON l.oid=p.prolang LEFT JOIN pg_catalog.pg_depend d ON d.classid=1255 AND d.objid=p.oid AND d.deptype='e' AND d.refclassid=3079 AND d.objsubid=0 AND d.refobjsubid=0 LEFT JOIN pg_catalog.pg_extension e ON e.oid=d.refobjid WHERE " + USER_NAMESPACE + " AND EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE') ORDER BY n.nspname,p.proname,p.oid"
    live = q(routine_sql)
    expected=public_contract()
    identities=[(x['schema'],x['name'],x['kind'],tuple((type_map[t]['schema'],type_map[t]['name']) for t in x['input_types'])) for x in live]
    # Optional read-only diagnostic boundary; comparison below stays authoritative.
    if hasattr(c, 'observe_routine_sets'):
        c.observe_routine_sets([routine_identity(e) for e in expected['routines']], identities)
    require(len(identities)==len(set(identities)) and set(identities)=={routine_identity(e) for e in expected['routines']},'PUBLIC_ROUTINES_SET')
    attrs = ('rolsuper', 'rolbypassrls', 'rolcreatedb', 'rolcreaterole', 'rolreplication', 'rolinherit', 'rolcanlogin')
    routines = []
    for x in live:
        require(valid_default_count(x['pronargdefaults'],len(x['input_types'])), 'PUBLIC_DEFAULT_COUNT')
        entry = {'schema': x['schema'], 'name': x['name'], 'parsed_sql_body': x['parsed_sql_body'], 'routine_kind': x['kind'], 'identity_input_types': [type_map[t] for t in x['input_types']], 'return_type': type_map[x['return_type']], 'returns_set': x['proretset'], 'parameter_names': x['proargnames'], 'parameter_modes': x['modes'], 'all_argument_types': None if x['all_types'] is None else [type_map[t] for t in x['all_types']], 'default_argument_count': x['pronargdefaults'], 'variadic_type': type_map.get(x['provariadic']), 'owner': x['owner'], 'owner_attributes': {k: x[k] for k in attrs}, 'language': x['lanname'], 'security_definer': x['prosecdef'], 'volatility': x['volatility'], 'parallel': x['parallel'], 'strict': x['proisstrict'], 'leakproof': x['proleakproof'], 'proconfig': None if x['proconfig'] is None else sorted(x['proconfig']), 'public_acl': public_acl('pg_catalog.pg_proc', x['oid']), 'direct_jous_grants': [], 'extension_membership': None if x['extname'] is None else {'name': x['extname'], 'version': x['extversion']}, 'schema_usage': usage(x['schema']), 'execution_context': 'event_trigger' if type_map[x['return_type']]['name'] == 'event_trigger' else 'trigger' if type_map[x['return_type']]['name'] == 'trigger' else 'ordinary_function'}
        if x['lanname'] == 'c':
            entry.update(library_reference=x['probin'], entry_point_symbol=x['prosrc'])
        else:
            entry.update(source=x['prosrc'], source_sha256=digest(x['prosrc']), fingerprint_algorithm='SHA256_UTF8_PROSRC_EXACT')
        routines.append(entry)
    sort_key = lambda x: (x['schema'], x['name'], json.dumps(x.get('identity_input_types', []), sort_keys=True, separators=(',', ':')))
    routines.sort(key=sort_key)
    relations_sql = "SELECT c.oid,n.nspname AS schema,c.relname AS name,c.relkind::pg_catalog.text AS kind,o.rolname AS owner,c.reloptions,e.extname,e.extversion FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace JOIN pg_catalog.pg_roles o ON o.oid=c.relowner LEFT JOIN pg_catalog.pg_depend d ON d.classid=1259 AND d.objid=c.oid AND d.deptype='e' AND d.refclassid=3079 AND d.objsubid=0 AND d.refobjsubid=0 LEFT JOIN pg_catalog.pg_extension e ON e.oid=d.refobjid WHERE " + USER_NAMESPACE + ' AND EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault(CASE WHEN c.relkind=\'S\' THEN \'s\'::pg_catalog."char" ELSE \'r\'::pg_catalog."char" END,c.relowner))) a WHERE a.grantee=0) ORDER BY n.nspname,c.relname'
    relrows = q(relations_sql)
    identities=[(x['schema'],x['name']) for x in relrows]
    require(len(identities)==len(set(identities)) and set(identities)=={(e['schema'],e['name']) for e in expected['relations']},'PUBLIC_RELATIONS_SET')
    relations = []
    for x in relrows:
        cols = q('SELECT attname AS name,atttypid AS type_oid,atttypmod AS type_modifier,attnotnull AS not_null FROM pg_catalog.pg_attribute WHERE attrelid=:oid AND attnum>0 AND NOT attisdropped ORDER BY attnum', {'oid': x['oid']})
        for col in cols:
            col['type'] = type_map[col.pop('type_oid')]
        entry = {'schema': x['schema'], 'name': x['name'], 'object_type': x['kind'], 'owner': x['owner'], 'public_acl': public_acl('pg_catalog.pg_class', x['oid'], x['kind']), 'direct_jous_grants': [], 'extension_membership': None if x['extname'] is None else {'name': x['extname'], 'version': x['extversion']}, 'columns': cols, 'reloptions': None if x['reloptions'] is None else sorted(x['reloptions']), 'schema_usage': usage(x['schema'])}
        relations.append(entry)
    binding_sql = "SELECT e.evtname AS name,e.evtevent AS event,e.evtenabled::pg_catalog.text AS enabled,e.evttags AS tags,o.rolname AS owner FROM pg_catalog.pg_event_trigger e JOIN pg_catalog.pg_roles o ON o.oid=e.evtowner WHERE e.evtfoid=(SELECT p.oid FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname='rls_auto_enable') ORDER BY e.evtname"
    bindings = q(binding_sql)
    for x in bindings:
        x['tags'] = sorted(x['tags'])
    return {'relations': relations, 'routines': routines, 'bindings': bindings}


def connection_gate(secret, ca_path):
    try:
        raw = urlsplit(secret)
        url = make_url(secret).set(drivername='postgresql+asyncpg')
        require(raw.scheme in ('postgres', 'postgresql') and not raw.query and not raw.fragment
                and not url.query and url.database == 'postgres' and url.port == 5432
                and url.username == 'postgres.' + PROJECT
                and bool(url.host) and re.fullmatch(r'[a-z0-9-]+\.pooler\.supabase\.com', url.host),
                'TARGET_REJECTED')
        args, effective = dialect().create_connect_args(url)
        require(not args and effective == {'host': url.host, 'database': 'postgres',
                'user': url.username, 'password': url.password, 'port': 5432}, 'TARGET_OVERRIDE')
        pem = Path(ca_path).read_text(encoding='ascii')
        context = approved_ca(pem)
        return url, context
    except Stop:
        raise
    except Exception:
        raise Stop('TARGET_OR_CA_UNAVAILABLE') from None


def migration_contract():
    """Read the SHA-gated migration; capture operations without executing SQL."""
    path = ROOT / MIGRATION_PATH
    content = path.read_bytes().replace(b'\r\n', b'\n')
    blob = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
    require(blob == MIGRATION_BLOB, 'MIGRATION_IDENTITY')
    module = verified_module('step7_reviewed_contract', path)
    statements = []
    class Capture:
        execute = staticmethod(statements.append)
    module.op = Capture()
    module.upgrade()
    return module, statements


def rows(c, sql, params=None):
    return [dict(row) for row in c.execute(text(sql), params or {}).mappings().all()]


def one(c, sql):
    result = rows(c, sql)
    require(len(result) == 1, 'CATALOG_SHAPE')
    return result[0]


def memberships(c):
    return rows(c, """SELECT m.roleid,m.member,m.grantor,r.rolname AS role_name,
      u.rolname AS member_name,g.rolname AS grantor_name,g.rolsuper AS grantor_super,
      m.admin_option,m.inherit_option,m.set_option
      FROM pg_catalog.pg_auth_members m JOIN pg_catalog.pg_roles r ON r.oid=m.roleid
      JOIN pg_catalog.pg_roles u ON u.oid=m.member JOIN pg_catalog.pg_roles g ON g.oid=m.grantor
      WHERE r.rolname='jous_security_reader' AND u.rolname='postgres' ORDER BY m.grantor""")


def authority(c, expected_set):
    a = one(c, """SELECT pg_catalog.pg_has_role('postgres','jous_security_reader','SET') AS can_set,
       pg_catalog.pg_has_role('postgres','jous_security_reader','USAGE') AS inherited""")
    require(a == {'can_set': expected_set, 'inherited': False}, 'MEMBERSHIP_AUTHORITY')


def baseline_membership(c):
    result = memberships(c)
    require(len(result) == 1, 'MEMBERSHIP_BASELINE')
    r = result[0]
    # The automatic creator grant is attributed to the cluster bootstrap superuser (OID 10).
    require(r['role_name'] == 'jous_security_reader' and r['member_name'] == 'postgres'
            and r['grantor'] == 10 and r['grantor_super'] is True
            and r['grantor_name'] != 'postgres' and r['admin_option'] is True
            and r['inherit_option'] is False and r['set_option'] is False,
            'MEMBERSHIP_PROVENANCE')
    authority(c, False)
    return result


def verify_membership(c, baseline, temporary):
    actual = memberships(c)
    if temporary:
        original = [r for r in actual if r['grantor'] == baseline[0]['grantor']]
        added = [r for r in actual if r['grantor_name'] == 'postgres']
        require(original == baseline and len(actual) == 2 and len(added) == 1, 'TEMP_MEMBERSHIP')
        r = added[0]
        require(r['roleid'] == baseline[0]['roleid'] and r['member'] == baseline[0]['member']
                and r['grantor'] == r['member'] and r['admin_option'] is False
                and r['inherit_option'] is False and r['set_option'] is True,
                'TEMP_MEMBERSHIP_OPTIONS')
    else:
        require(actual == baseline, 'MEMBERSHIP_RESTORATION')
    authority(c, temporary)


def role_gate(c):
    actual = rows(c, """SELECT oid,rolname,rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,
      rolcreaterole,rolreplication,rolinherit FROM pg_catalog.pg_roles
      WHERE rolname IN ('jous_runtime','jous_security_reader') ORDER BY rolname""")
    require(len(actual) == 2, 'ROLE_MISSING')
    for r in actual:
        require(r['rolcanlogin'] is (r['rolname'] == 'jous_runtime')
                and all(r[k] is False for k in ('rolsuper','rolbypassrls','rolcreatedb',
                    'rolcreaterole','rolreplication','rolinherit')), 'ROLE_ATTRIBUTES')
    require(not rows(c, """SELECT m.roleid FROM pg_catalog.pg_auth_members m
      JOIN pg_catalog.pg_roles r ON r.oid=m.member
      WHERE r.rolname IN ('jous_runtime','jous_security_reader')"""), 'ROLE_OUTBOUND_MEMBERSHIP')
    require(not rows(c, """SELECT m.roleid FROM pg_catalog.pg_auth_members m
      JOIN pg_catalog.pg_roles r ON r.oid=m.roleid JOIN pg_catalog.pg_roles u ON u.oid=m.member
      WHERE r.rolname IN ('jous_runtime','jous_security_reader') AND u.rolname<>'postgres'"""),
      'ROLE_INBOUND_MEMBERSHIP')
    runtime_admin = rows(c, """SELECT m.admin_option,m.inherit_option,m.set_option,m.grantor
      FROM pg_catalog.pg_auth_members m JOIN pg_catalog.pg_roles r ON r.oid=m.roleid
      JOIN pg_catalog.pg_roles u ON u.oid=m.member
      WHERE r.rolname='jous_runtime' AND u.rolname='postgres'""")
    require(runtime_admin == [{'admin_option':True,'inherit_option':False,'set_option':False,
                               'grantor':10}], 'RUNTIME_ADMIN_MEMBERSHIP')
    return {r['rolname']: r['oid'] for r in actual}


def privilege_boundary(c):
    for role in ('jous_runtime', 'jous_security_reader'):
        a = one(c, f"""SELECT
          pg_catalog.has_database_privilege('{role}',d.oid,'CREATE') AS db_create,
          d.datdba=r.oid AS db_owner,
          pg_catalog.has_database_privilege('{role}',d.oid,'TEMP') AS temp,
          EXISTS (SELECT 1 FROM pg_catalog.aclexplode(COALESCE(d.datacl,
            pg_catalog.acldefault('d',d.datdba))) a
            WHERE a.grantee=r.oid AND a.privilege_type='TEMPORARY') AS direct_temp,
          EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n WHERE {USER_NAMESPACE}
            AND pg_catalog.has_schema_privilege(r.oid,n.oid,'CREATE')) AS schema_create,
          EXISTS (SELECT 1 FROM pg_catalog.pg_class o WHERE o.relowner=r.oid) AS relation_owner,
          EXISTS (SELECT 1 FROM pg_catalog.pg_namespace o WHERE o.nspowner=r.oid) AS schema_owner
          FROM pg_catalog.pg_database d CROSS JOIN pg_catalog.pg_roles r
          WHERE d.datname=current_database() AND r.rolname='{role}'""")
        require(a == dict(db_create=False, db_owner=False, temp=True, direct_temp=False,
                         schema_create=False, relation_owner=False, schema_owner=False), 'PRIVILEGE_BOUNDARY')
    public = rows(c, """SELECT a.privilege_type,a.is_grantable FROM pg_catalog.pg_database d,
      LATERAL pg_catalog.aclexplode(COALESCE(d.datacl,pg_catalog.acldefault('d',d.datdba))) a
      WHERE d.datname=current_database() AND a.grantee=0 ORDER BY 1""")
    require(public == [{'privilege_type':'CONNECT','is_grantable':False},
                       {'privilege_type':'TEMPORARY','is_grantable':False}], 'PUBLIC_DATABASE_ACL')
    public_schema = rows(c, """SELECT a.privilege_type,a.is_grantable FROM pg_catalog.pg_namespace n,
      LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
      WHERE n.nspname='public' AND a.grantee=0 ORDER BY 1""")
    require(public_schema == [{'privilege_type':'USAGE','is_grantable':False}], 'PUBLIC_SCHEMA_ACL')


def table_state(c):
    result = rows(c, """SELECT c.relname,r.rolname AS owner,c.relrowsecurity,c.relforcerowsecurity
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      JOIN pg_catalog.pg_roles r ON r.oid=c.relowner WHERE n.nspname='public'
      AND c.relname IN ('users','organizations','organization_memberships','projects')
      AND c.relkind='r' ORDER BY c.relname""")
    require({r['relname'] for r in result} == set(TABLES) and len(result) == 4, 'TABLE_BASELINE')
    counts = [c.scalar(text(f'SELECT count(*) FROM public.{t}')) for t in TABLES]
    require(all(type(count) is int and count == 0 for count in counts), 'ROW_COUNT')
    return result


def revision(c, expected):
    require(rows(c, 'SELECT version_num FROM public.alembic_version') ==
            [{'version_num': expected}], 'REVISION')


def preflight(c):
    c.execute(text('SET LOCAL search_path = pg_catalog'))
    c.execute(text("SET LOCAL statement_timeout = '30s'"))
    c.execute(text("SET LOCAL lock_timeout = '5s'"))
    identity = one(c, """SELECT current_user::text AS role,session_user::text AS session,
      current_database() AS database,pg_catalog.pg_backend_pid() AS pid,
      pg_catalog.pg_current_xact_id()::text AS xid,
      current_setting('server_version_num')::integer AS version,
      r.rolcreaterole,r.rolbypassrls,d.datdba=r.oid AS db_owner
      FROM pg_catalog.pg_roles r JOIN pg_catalog.pg_database d ON d.datname=current_database()
      WHERE r.rolname=current_user""")
    require(identity['role'] == identity['session'] == 'postgres'
            and identity['database'] == 'postgres' and 170000 <= identity['version'] < 180000
            and identity['rolcreaterole'] is True and identity['rolbypassrls'] is True
            and identity['db_owner'] is True, 'ADMIN_TARGET')
    require(c.scalar(text('SELECT pg_catalog.pg_try_advisory_xact_lock(:key)'), {'key': LOCK})
            is True, 'RUNNER_LOCK')
    role_gate(c)
    privilege_boundary(c)
    revision(c, '0001_identity_project')
    tables = table_state(c)
    require(all(r['owner'] == 'postgres' and r['relrowsecurity'] is True
                and r['relforcerowsecurity'] is False for r in tables), 'TABLE_SECURITY_BASELINE')
    require(not rows(c, "SELECT oid FROM pg_catalog.pg_namespace WHERE nspname='jous_security'"),
            'SCHEMA_COLLISION')
    require(not policies(c), 'POLICY_BASELINE')
    baseline = baseline_membership(c)
    verify_grants(c, migrated=False)
    verify_ownership(c, migrated=False)
    final = execution_contract()
    contract = final_gate(final.load_final_contract)
    frozen = final_gate(final.freeze_pre_migration_bindings, c, contract, rows)
    return {'identity': identity, 'tables': tables, 'memberships': baseline,
            'final_contract': contract, 'existing_bindings': frozen,
            'created_bindings': None, 'policy_continuity': None}


def verify_ownership(c, migrated, helper_oids=()):
    actual = rows(c, """SELECT n.nspname,p.proname,r.rolname AS owner FROM pg_catalog.pg_proc p
      JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
      JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
      WHERE r.rolname IN ('jous_runtime','jous_security_reader') ORDER BY 1,2""")
    expected = ([{'nspname':'jous_security','proname':name,'owner':'jous_security_reader'}
                 for name in ('organization_is_active','resolve_user')] if migrated else [])
    require(actual == expected, 'FUNCTION_OWNERSHIP')
    require(not rows(c, """SELECT d.oid FROM pg_catalog.pg_database d
      JOIN pg_catalog.pg_roles r ON r.oid=d.datdba
      WHERE r.rolname IN ('jous_runtime','jous_security_reader')"""), 'DATABASE_OWNERSHIP')
    # pg_shdepend records ownership for other object classes too (types, languages, etc.).
    require(not migrated or (len(helper_oids)==2 and len(set(helper_oids))==2 and all(catalog_oid(v) for v in helper_oids)), 'VERIFIED_HELPER_OWNERSHIP_REQUIRED')
    extras = rows(c, """SELECT s.classid,s.objid,s.objsubid,
      cn.nspname AS class_namespace,cc.relname AS class_name
      FROM pg_catalog.pg_shdepend s
      LEFT JOIN pg_catalog.pg_class cc ON cc.oid=s.classid
      LEFT JOIN pg_catalog.pg_namespace cn ON cn.oid=cc.relnamespace
      JOIN pg_catalog.pg_roles r ON r.oid=s.refobjid
      WHERE s.refclassid=(SELECT c.oid FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='pg_catalog' AND c.relname='pg_authid')
      AND s.deptype='o' AND r.rolname IN ('jous_runtime','jous_security_reader')
      AND NOT COALESCE((cn.nspname='pg_catalog' AND cc.relname='pg_proc'
        AND r.rolname='jous_security_reader' AND s.objsubid=0
        AND s.dbid=(SELECT oid FROM pg_catalog.pg_database WHERE datname=current_database())
        AND s.objid=ANY(CAST(:helper_oids AS pg_catalog.oid[]))),FALSE)""",
        {'helper_oids':list(helper_oids)})
    require(not extras, 'UNEXPECTED_OWNERSHIP')


RUNTIME = {
    'users': {'SELECT': {'id','status'}},
    'organizations': {'SELECT': {'id','name','status','created_at','updated_at'},
                      'UPDATE': {'name','updated_at'}},
    'organization_memberships': {'SELECT': {'id','user_id','organization_id','role','status','created_at','updated_at'}},
    'projects': {'SELECT': {'id','organization_id','name','description','status','created_at','updated_at'},
                 'INSERT': {'id','organization_id','name','description'},
                 'UPDATE': {'name','description','updated_at'}},
}
READER = {'users': {'SELECT': {'id','auth_issuer','auth_subject','status'}},
          'organizations': {'SELECT': {'id','status'}}}


def verify_direct_authority(c, migrated):
    """Independent direct ACL audit: PUBLIC compatibility never masks a grant."""
    roles="a.grantee IN (SELECT oid FROM pg_catalog.pg_roles WHERE rolname IN ('jous_runtime','jous_security_reader'))"
    require(not rows(c, f"""SELECT d.datname FROM pg_catalog.pg_database d,
        LATERAL pg_catalog.aclexplode(d.datacl) a WHERE {roles}"""),'DIRECT_DATABASE_ACL')
    schema=rows(c,f"""SELECT n.nspname,r.rolname,a.privilege_type,a.is_grantable
        FROM pg_catalog.pg_namespace n,LATERAL pg_catalog.aclexplode(n.nspacl) a
        JOIN pg_catalog.pg_roles r ON r.oid=a.grantee WHERE {roles}""")
    expected=[dict(nspname='jous_security',rolname=role,privilege_type='USAGE',is_grantable=False)
              for role in ('jous_runtime','jous_security_reader')] if migrated else []
    require(len(schema)==len(expected) and sorted(schema,key=lambda e:e['rolname'])==
            sorted(expected,key=lambda e:e['rolname']),'DIRECT_SCHEMA_ACL')
    columns=rows(c,f"""SELECT n.nspname,c.relname,att.attname,r.rolname,
        a.privilege_type,a.is_grantable FROM pg_catalog.pg_attribute att
        JOIN pg_catalog.pg_class c ON c.oid=att.attrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
        LATERAL pg_catalog.aclexplode(att.attacl) a
        JOIN pg_catalog.pg_roles r ON r.oid=a.grantee WHERE {roles}""")
    expected=[dict(nspname='public',relname=t,attname=col,rolname=role,
                   privilege_type=priv,is_grantable=False)
        for role,contract in (('jous_runtime',RUNTIME),('jous_security_reader',READER))
        for t,privs in contract.items() for priv,cols in privs.items() for col in cols] if migrated else []
    key=lambda e:tuple(e[k] for k in ('nspname','relname','attname','rolname','privilege_type','is_grantable'))
    require(len(columns)==len(expected) and {key(e) for e in columns}=={key(e) for e in expected},
            'DIRECT_COLUMN_ACL')
    routines=rows(c,f"""SELECT n.nspname,p.proname,r.rolname,
        (SELECT COALESCE(pg_catalog.string_agg(CASE WHEN tn.nspname='pg_catalog' THEN t.typname::pg_catalog.text ELSE tn.nspname::pg_catalog.text||'.'||t.typname::pg_catalog.text END, ', ' ORDER BY arg.pos),'') FROM pg_catalog.unnest(p.proargtypes::pg_catalog.oid[]) WITH ORDINALITY arg(oid,pos) JOIN pg_catalog.pg_type t ON t.oid=arg.oid JOIN pg_catalog.pg_namespace tn ON tn.oid=t.typnamespace) AS args,a.privilege_type,a.is_grantable
        FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace,
        LATERAL pg_catalog.aclexplode(p.proacl) a
        JOIN pg_catalog.pg_roles r ON r.oid=a.grantee WHERE {roles}""")
    expected=[dict(nspname='jous_security',proname=name,args=args,rolname=role,
                   privilege_type='EXECUTE',is_grantable=False)
        for name,args in (('resolve_user','text, text'),('organization_is_active','uuid'))
        for role in ('jous_runtime','jous_security_reader')] if migrated else []
    key=lambda e:tuple(e[k] for k in ('nspname','proname','args','rolname','privilege_type','is_grantable'))
    require(len(routines)==len(expected) and {key(e) for e in routines}=={key(e) for e in expected},
            'DIRECT_ROUTINE_ACL')
    # Column PUBLIC ACLs have no reviewed exception, including on approved views.
    require(not rows(c,f"""SELECT att.attname FROM pg_catalog.pg_attribute att
        JOIN pg_catalog.pg_class c ON c.oid=att.attrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
        LATERAL pg_catalog.aclexplode(att.attacl) a WHERE {USER_NAMESPACE}
        AND a.grantee=0"""),'PUBLIC_COLUMN_ACL')
    reachable=rows(c,f"""SELECT n.nspname,r.rolname FROM pg_catalog.pg_namespace n
        CROSS JOIN pg_catalog.pg_roles r WHERE {USER_NAMESPACE}
        AND r.rolname IN ('jous_runtime','jous_security_reader')
        AND pg_catalog.has_schema_privilege(r.oid,n.oid,'USAGE')""")
    expected={(schema,role) for schema in (('public','jous_security') if migrated else ('public',))
              for role in ('jous_runtime','jous_security_reader')}
    require(len(reachable)==len(expected) and
            {(e['nspname'],e['rolname']) for e in reachable}==expected,'SCHEMA_REACHABILITY')


def verify_grants(c, migrated):
    verify_direct_authority(c, migrated)
    verify_public_compatibility(c)
    manifest = public_contract()
    table_acl = rows(c, """SELECT n.nspname,c.relname,r.rolname,a.privilege_type,a.is_grantable
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
      LATERAL pg_catalog.aclexplode(c.relacl) a JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
      WHERE r.rolname IN ('jous_runtime','jous_security_reader')""")
    require(table_acl == ([{'nspname':'public','relname':'alembic_version','rolname':'jous_runtime',
        'privilege_type':'SELECT','is_grantable':False}] if migrated else []), 'DIRECT_TABLE_ACL')
    # Exhaustive effective privilege matrix includes future/unrelated relations and grant options.
    actual = rows(c, f"""SELECT n.nspname,c.relname,a.attname,r.role,p.priv,
      pg_catalog.has_column_privilege(r.role::pg_catalog.name,c.oid,a.attnum,p.priv) AS allowed,
      pg_catalog.has_column_privilege(r.role::pg_catalog.name,c.oid,a.attnum,p.priv||' WITH GRANT OPTION') AS grantable
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
      CROSS JOIN (VALUES ('jous_runtime'),('jous_security_reader')) r(role)
      CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('REFERENCES')) p(priv)
      WHERE {USER_NAMESPACE}
      AND c.relkind IN ('r','v','m','f','p') AND a.attnum>0 AND NOT a.attisdropped""")
    require(bool(actual), 'GRANT_CATALOG_EMPTY')
    seen = set()
    for r in actual:
        expected = False
        if migrated and r['nspname'] == 'public':
            contract = RUNTIME if r['role'] == 'jous_runtime' else READER
            expected = r['attname'] in contract.get(r['relname'], {}).get(r['priv'], set())
            if r['relname'] == 'alembic_version' and r['role'] == 'jous_runtime':
                expected = r['priv'] == 'SELECT'
        platform = any(e['schema']==r['nspname'] and e['name']==r['relname']
            and r['priv']=='SELECT' and any(col['name']==r['attname'] for col in e['columns'])
            for e in manifest['relations'])
        require(r['allowed'] is (expected or platform) and r['grantable'] is False, 'RELATION_PRIVILEGES')
        if expected:
            seen.add((r['role'], r['relname'], r['priv'], r['attname']))
    if migrated:
        expected_seen = {(role,t,p,col) for role,contract in
            (('jous_runtime',RUNTIME),('jous_security_reader',READER))
            for t,perms in contract.items() for p,cols in perms.items() for col in cols}
        expected_seen.add(('jous_runtime','alembic_version','SELECT','version_num'))
        require(seen == expected_seen, 'GRANT_CATALOG_INCOMPLETE')
    require(not rows(c, f"""SELECT c.oid FROM pg_catalog.pg_class c
      JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      CROSS JOIN (VALUES ('jous_runtime'),('jous_security_reader')) r(role)
      WHERE {USER_NAMESPACE}
      AND c.relkind IN ('r','v','m','f','p')
      AND pg_catalog.has_table_privilege(r.role::pg_catalog.name,c.oid,'DELETE,TRUNCATE,TRIGGER,MAINTAIN')"""),
      'TABLE_PRIVILEGES')
    require(not rows(c, f"""SELECT c.oid FROM pg_catalog.pg_class c
      JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      CROSS JOIN (VALUES ('jous_runtime'),('jous_security_reader')) r(role)
      WHERE c.relkind='S' AND {USER_NAMESPACE}
      AND pg_catalog.has_sequence_privilege(r.role::pg_catalog.name,c.oid,'USAGE,SELECT,UPDATE')"""), 'SEQUENCE_PRIVILEGES')
    # PUBLIC is OID 0, not a pg_roles row. No applicable future-object grants allowed.
    require(not rows(c, """SELECT d.oid,a.grantee,a.privilege_type,a.is_grantable
      FROM pg_catalog.pg_default_acl d,
      LATERAL pg_catalog.aclexplode(d.defaclacl) a
      WHERE a.grantee=0 OR a.grantee IN
        (SELECT oid FROM pg_catalog.pg_roles WHERE rolname IN
         ('jous_runtime','jous_security_reader'))"""), 'DEFAULT_PRIVILEGES')
    verify_routines(c, migrated)


def verify_routines(c, migrated):
    # All pg_proc kinds share routine EXECUTE ACL semantics. Never call the routines.
    verify_public_compatibility(c)
    manifest = public_contract()
    actual = rows(c, f"""SELECT n.nspname,p.proname,
      (SELECT COALESCE(pg_catalog.string_agg(CASE WHEN tn.nspname='pg_catalog' THEN t.typname::pg_catalog.text ELSE tn.nspname::pg_catalog.text||'.'||t.typname::pg_catalog.text END, ', ' ORDER BY arg.pos),'') FROM pg_catalog.unnest(p.proargtypes::pg_catalog.oid[]) WITH ORDINALITY arg(oid,pos) JOIN pg_catalog.pg_type t ON t.oid=arg.oid JOIN pg_catalog.pg_namespace tn ON tn.oid=t.typnamespace) AS args,p.prokind::pg_catalog.text AS prokind,r.role,
      (SELECT COALESCE(pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object('schema',tn.nspname,'name',t.typname)
        ORDER BY arg.pos),'[]'::pg_catalog.jsonb) FROM pg_catalog.unnest(p.proargtypes::pg_catalog.oid[]) WITH ORDINALITY arg(oid,pos)
        JOIN pg_catalog.pg_type t ON t.oid=arg.oid
        JOIN pg_catalog.pg_namespace tn ON tn.oid=t.typnamespace) AS input_types,
      pg_catalog.has_function_privilege(r.role::pg_catalog.name,p.oid,'EXECUTE') AS allowed,
      pg_catalog.has_function_privilege(r.role::pg_catalog.name,p.oid,
        'EXECUTE WITH GRANT OPTION') AS grantable
      FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
      CROSS JOIN (VALUES ('jous_runtime'),('jous_security_reader')) r(role)
      WHERE {USER_NAMESPACE}""")
    seen = set()
    platform_seen = set()
    expected = {(name, args, role) for name,args in
        (('resolve_user','text, text'),('organization_is_active','uuid'))
        for role in ('jous_runtime','jous_security_reader')} if migrated else set()
    for row in actual:
        key = (row['proname'],row['args'],row['role'])
        permitted = (migrated and row['nspname']=='jous_security'
                     and row['prokind']=='f' and key in expected)
        # Owners have implicit grant authority; only the exact helper owner is allowed.
        owner_grant = permitted and row['role']=='jous_security_reader'
        platform = any(e['schema']==row['nspname'] and e['name']==row['proname']
            and e['routine_kind']==row['prokind'] and e['identity_input_types']==row.get('input_types')
            for e in manifest['routines'])
        require(row['allowed'] is bool(permitted or platform) and row['grantable'] is bool(owner_grant),
                'ROUTINE_PRIVILEGES')
        if platform:
            identity=(row['nspname'],row['proname'],row['prokind'],
                tuple((t['schema'],t['name']) for t in row['input_types']),row['role'])
            require(identity not in platform_seen,'ROUTINE_DUPLICATE')
            platform_seen.add(identity)
        if permitted:
            require(key not in seen, 'ROUTINE_DUPLICATE')
            seen.add(key)
    require(seen == expected, 'ROUTINE_CATALOG_INCOMPLETE')
    require(platform_seen=={(*routine_identity(e),role) for e in manifest['routines']
        for role in ('jous_runtime','jous_security_reader')},'PUBLIC_ROUTINE_CAPABILITY_INCOMPLETE')


def catalog_contract():
    return verified_module('step7_catalog_contract', ROOT/'services/api/src/jous_api/step7_catalog.py')


def valid_default_count(value, input_count):
    return type(value) is int and type(input_count) is int and 0 <= value <= input_count


def policies(c):
    return rows(c, catalog_contract().POLICY_SQL)


def verify_policies(c, expected, continuity):
    final = execution_contract()
    actual = final.collect_actual_policy_rows(c, rows, catalog_contract().POLICY_SQL)
    return final_gate(final.verify_policy_rows, expected, actual, continuity)


def verify_helpers(c, statements, ids):
    actual = rows(c, """SELECT n.nspname,n.oid AS namespace_oid,p.oid AS routine_oid,p.proname,p.proargtypes::pg_catalog.oid[] AS args,
      p.prorettype AS returns,p.proowner,p.prosecdef,p.provolatile::pg_catalog.text AS provolatile,p.proparallel::pg_catalog.text AS proparallel,
      p.proconfig,p.prosrc,l.lanname,p.proisstrict,p.prokind::pg_catalog.text AS prokind,
      p.proargnames,p.proargmodes,p.proallargtypes,p.pronargdefaults,
      p.proargdefaults IS NULL AS no_defaults,p.prosqlbody IS NULL AS text_body
      FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
      JOIN pg_catalog.pg_language l ON l.oid=p.prolang WHERE n.nspname='jous_security'""")
    require(len(actual) == 2 and {r['proname'] for r in actual} ==
            {'resolve_user','organization_is_active'}, 'HELPER_SET')
    for r in actual:
        name = r['proname']
        create = next(s for s in statements if s.startswith('CREATE FUNCTION jous_security.'+name+'('))
        body = create.split('$function$')[1].strip()
        require(r['nspname']=='jous_security'
                and r['proargnames']==(['p_issuer','p_subject'] if name=='resolve_user'
                                        else ['p_organization_id'])
                and r['proargmodes'] is None and r['proallargtypes'] is None
                and r['pronargdefaults']==0 and r['no_defaults'] is True and r['text_body'] is True
                and all(catalog_oid(v) for v in (r['routine_oid'],r['namespace_oid'],r['proowner']))
                and type(r['pronargdefaults']) is int
                and r['args'] == ([25,25] if name=='resolve_user' else [2950])
                and all(type(v) is int for v in r['args'])
                and type(r['returns']) is int and r['returns'] == (2950 if name=='resolve_user' else 16)
                and r['proowner'] == ids['jous_security_reader'] and r['prosecdef'] is True
                and r['provolatile']=='s' and r['proparallel']=='u'
                and r['proconfig']==['search_path=pg_catalog, pg_temp']
                and r['lanname']=='sql' and r['proisstrict'] is False and r['prokind']=='f'
                and r['prosrc'].strip()==body, 'HELPER_DEFINITION')
    acl = rows(c, """SELECT p.proname,a.grantor,a.grantee,a.privilege_type,a.is_grantable
      FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace,
      LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
      WHERE n.nspname='jous_security'""")
    expected = {(name,ids['jous_security_reader'],grantee,'EXECUTE',False)
                for name in ('resolve_user','organization_is_active')
                for grantee in (ids['jous_runtime'],ids['jous_security_reader'])}
    require(len(acl)==4 and {tuple(r[k] for k in ('proname','grantor','grantee','privilege_type','is_grantable'))
            for r in acl} == expected, 'HELPER_ACL')
    require(len({r['routine_oid'] for r in actual})==2 and len({r['namespace_oid'] for r in actual})==1, 'HELPER_IDENTITY')
    schema = one(c, """SELECT r.rolname AS owner FROM pg_catalog.pg_namespace n
      JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='jous_security'""")
    require(schema == {'owner':'postgres'}, 'SCHEMA_OWNER')
    schema_acl = rows(c, """SELECT a.grantee,a.privilege_type,a.is_grantable
      FROM pg_catalog.pg_namespace n,
      LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
      WHERE n.nspname='jous_security' AND a.grantee<>n.nspowner""")
    require(len(schema_acl)==2 and {tuple(r.values()) for r in schema_acl} ==
            {(ids['jous_runtime'],'USAGE',False),(ids['jous_security_reader'],'USAGE',False)}, 'SCHEMA_ACL')
    return tuple(sorted(r['routine_oid'] for r in actual))


def verify_security(c, baseline):
    revision(c,'0002_runtime_rls')
    ids = role_gate(c)
    privilege_boundary(c)
    state = table_state(c)
    require(all(r['owner']==next(b['owner'] for b in baseline['tables'] if b['relname']==r['relname'])
                and r['relrowsecurity'] is True and r['relforcerowsecurity'] is True for r in state), 'TABLE_RLS')
    module, statements = migration_contract()
    helper_oids = verify_helpers(c,statements,ids)
    verify_ownership(c,True,helper_oids)
    final = execution_contract()
    contract = baseline['final_contract']
    final_gate(final.revalidate_existing_bindings,c,contract,baseline['existing_bindings'],rows)
    created = final_gate(final.verify_created_security_objects,c,contract,baseline['existing_bindings'],rows)
    if baseline['created_bindings'] is not None:
        final_gate(final.exact,created.payload.decode('utf-8'),
                   baseline['created_bindings'].payload.decode('utf-8'),'POLICY_CONTINUITY_MISMATCH')
    expected = final_gate(final.instantiate_policy_expectations,contract,baseline['existing_bindings'],created)
    continuity = verify_policies(c,expected,baseline['policy_continuity'])
    baseline['created_bindings'] = created
    baseline['policy_continuity'] = continuity
    verify_grants(c,True)
    identity = one(c, """SELECT pg_catalog.pg_backend_pid() AS pid,
      pg_catalog.pg_current_xact_id()::text AS xid""")
    require(identity == {k:baseline['identity'][k] for k in ('pid','xid')}, 'TRANSACTION_CONTINUITY')


def alembic_upgrade(c):
    # Dependencies/engine setup must not preload application code before env.py.
    cached_jous_gate()
    require(c.in_transaction(), 'OUTER_TRANSACTION_REQUIRED')
    transaction = c.get_transaction()
    config = Config(str(ROOT/'services/api/alembic.ini'))
    config.attributes['connection'] = c
    # Repeat identity/surface gates immediately before any migration loading.
    if _APPROVED_SHA is not None:
        repository_gate(_APPROVED_SHA)
    cached_jous_gate()
    from alembic.util import pyfiles
    original = pyfiles.load_module_py
    def source_only(module_id, path):
        require(Path(path).resolve().is_relative_to(ROOT/'services/api/migrations'), 'MIGRATION_LOADER_PATH')
        return verified_module(module_id, path)
    pyfiles.load_module_py = source_only
    try:
        command.upgrade(config,'0002_runtime_rls')
    finally:
        pyfiles.load_module_py = original
    require(c.in_transaction() and c.get_transaction() is transaction and transaction.is_active,
            'ALEMBIC_TRANSACTION_ESCAPE')


def pipeline(c, *, inspect=preflight, verify=verify_security, migrate=alembic_upgrade,
             membership_check=verify_membership):
    require(c.in_transaction(), 'OUTER_TRANSACTION_REQUIRED')
    baseline = inspect(c)
    c.execute(text(GRANT))
    membership_check(c,baseline['memberships'],True)
    migrate(c)
    verify(c,baseline)
    c.execute(text(REVOKE))
    membership_check(c,baseline['memberships'],False)
    verify(c,baseline)
    membership_check(c,baseline['memberships'],False)


async def drain(operation):
    """Do not abandon mandatory rollback/close on repeated caller cancellation."""
    task = asyncio.create_task(operation)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            break
    result = task.result()
    return result, cancelled


async def execute(engine):
    connection = transaction = driver = None
    phase = 'PRE_COMMIT'
    outcome = None
    try:
        connection = await engine.connect()
        # Capture once while the connection is valid; never revalidate/reconnect in cleanup.
        proxy = await connection.get_raw_connection()
        driver = proxy.driver_connection
        transaction = await connection.begin()
        await connection.run_sync(pipeline)
        phase = 'COMMIT'
        await transaction.commit()
        outcome = 'COMMITTED'
    except BaseException:
        outcome = 'UNKNOWN' if phase == 'COMMIT' else 'ROLLED_BACK'
        if phase != 'COMMIT' and transaction is not None:
            try:
                await drain(transaction.rollback())
            except BaseException:
                outcome = 'ROLLBACK_UNCONFIRMED'
        elif phase != 'COMMIT' and transaction is None:
            outcome = 'NOT_STARTED'
    finally:
        async def cleanup():
            try:
                if connection is not None:
                    try:
                        try:
                            if not connection.closed and not connection.invalidated:
                                connection.sync_connection.detach()
                        finally:
                            require(driver is not None,'DRIVER_UNAVAILABLE')
                            try:
                                await driver.close(timeout=2)
                                closed = driver.is_closed() is True
                            except Exception:
                                closed = False
                            if not closed:
                                driver.terminate()
                            require(driver.is_closed() is True,'TERMINATION_UNCONFIRMED')
                    finally:
                        try:
                            if not connection.closed:
                                await connection.invalidate()
                        finally:
                            await connection.close()
            finally:
                await engine.dispose()
        try:
            await drain(cleanup())
        except BaseException:
            outcome = ('COMMITTED_CLEANUP_UNCONFIRMED' if outcome == 'COMMITTED' else
                       'UNKNOWN' if phase == 'COMMIT' else 'CLEANUP_UNCONFIRMED')
    require(outcome == 'COMMITTED', outcome or 'NOT_STARTED')
    return outcome


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-managed-mutation', action='store_true')
    parser.add_argument('--ca-file', type=Path)
    parser.add_argument('--approved-execution-sha')
    args = parser.parse_args(argv)
    try:
        require(args.confirm_managed_mutation, 'MUTATION_CONFIRMATION_REQUIRED')
        cached_jous_gate()
        trusted_launch_gate()
        repository_gate(args.approved_execution_sha)
        global _APPROVED_SHA
        _APPROVED_SHA = args.approved_execution_sha
        public_contract()
        final_gate(execution_contract().load_final_contract)
        install_source_importer()
        load_dependencies()
        cached_jous_gate()
        require(args.ca_file is not None, 'CA_REQUIRED')
        secret = os.environ.get('JOUS_MIGRATION_DATABASE_URL')
        require(bool(secret), 'MIGRATION_CREDENTIAL_REQUIRED')
        url, context = connection_gate(secret,args.ca_file)
        engine = create_async_engine(url,poolclass=NullPool,echo=False,hide_parameters=True,
            connect_args={'ssl':context,'timeout':10,'command_timeout':30})
        result = asyncio.run(execute(engine))
        print('STEP7_ATOMIC: '+result)
        return 0
    except BaseException as error:
        # No raw exceptions, tracebacks, URLs or exception chains at the operator boundary.
        category = str(error) if isinstance(error,Stop) else 'OPERATOR_FAILURE'
        print('STEP7_ATOMIC: '+category)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
