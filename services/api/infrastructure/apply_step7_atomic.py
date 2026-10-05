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
MIGRATION_BLOB = '0e2cf9e7cefcb40110359eded43e48a3e74f67d7'
MIGRATION_PATH = 'services/api/migrations/versions/0002_runtime_rls.py'
IDENTITY_PATHS = ('services/api/infrastructure/apply_step7_atomic.py',
    'services/api/migrations', 'services/api/alembic.ini',
    'services/api/infrastructure/runtime_roles.sql', 'services/api/src/jous_api',
    'services/api/pyproject.toml', 'services/api/requirements.lock')
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
    return {'identity': identity, 'tables': tables, 'memberships': baseline}


def verify_ownership(c, migrated):
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
    extras = rows(c, """SELECT s.classid::regclass::text AS class FROM pg_catalog.pg_shdepend s
      JOIN pg_catalog.pg_roles r ON r.oid=s.refobjid WHERE s.refclassid='pg_catalog.pg_authid'::regclass
      AND s.deptype='o' AND r.rolname IN ('jous_runtime','jous_security_reader')
      AND NOT (s.classid='pg_catalog.pg_proc'::regclass AND r.rolname='jous_security_reader'
        AND s.dbid=(SELECT oid FROM pg_catalog.pg_database WHERE datname=current_database())
        AND s.objid IN (SELECT p.oid FROM pg_catalog.pg_proc p
          JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='jous_security'
          AND p.proname IN ('resolve_user','organization_is_active')))""")
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


def verify_grants(c, migrated):
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
        require(r['allowed'] is expected and r['grantable'] is False, 'RELATION_PRIVILEGES')
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
    actual = rows(c, f"""SELECT n.nspname,p.proname,
      pg_catalog.oidvectortypes(p.proargtypes) AS args,p.prokind,r.role,
      pg_catalog.has_function_privilege(r.role::pg_catalog.name,p.oid,'EXECUTE') AS allowed,
      pg_catalog.has_function_privilege(r.role::pg_catalog.name,p.oid,
        'EXECUTE WITH GRANT OPTION') AS grantable
      FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
      CROSS JOIN (VALUES ('jous_runtime'),('jous_security_reader')) r(role)
      WHERE {USER_NAMESPACE}""")
    seen = set()
    expected = {(name, args, role) for name,args in
        (('resolve_user','text, text'),('organization_is_active','uuid'))
        for role in ('jous_runtime','jous_security_reader')} if migrated else set()
    for row in actual:
        key = (row['proname'],row['args'],row['role'])
        permitted = (migrated and row['nspname']=='jous_security'
                     and row['prokind']=='f' and key in expected)
        # Owners have implicit grant authority; only the exact helper owner is allowed.
        owner_grant = permitted and row['role']=='jous_security_reader'
        require(row['allowed'] is bool(permitted) and row['grantable'] is bool(owner_grant),
                'ROUTINE_PRIVILEGES')
        if permitted:
            require(key not in seen, 'ROUTINE_DUPLICATE')
            seen.add(key)
    require(seen == expected, 'ROUTINE_CATALOG_INCOMPLETE')


def policies(c):
    return rows(c, """SELECT tablename,policyname,permissive,roles,cmd,qual,with_check
      FROM pg_catalog.pg_policies WHERE schemaname='public'
      AND tablename IN ('users','organizations','organization_memberships','projects')""")


class GuardStructure:
    """Recognize only the expression vocabulary in the four pinned 0002 guards.

    This is not a general SQL parser. There is no SQL execution/planning fallback.
    Parenthesis formatting, catalog qualification of builtins, safe text coercions,
    CAST-to-uuid spelling, and literal IN/ANY spelling are the only equivalences.
    Unknown syntax is a STOP, including otherwise valid PostgreSQL SQL.
    """
    token = re.compile(r"\s*(::|'(?:[^']|'')*'|[a-zA-Z_][a-zA-Z_0-9]*|[0-9]+|[().,=~\[\]])")

    def __init__(self, expression):
        require(isinstance(expression,str) and len(expression)<20000, 'POLICY_EXPRESSION')
        self.tokens=[]
        pos=0
        while pos<len(expression.rstrip()):
            match=self.token.match(expression,pos)
            require(match is not None, 'POLICY_SYNTAX')
            value=match.group(1)
            self.tokens.append(value if value.startswith("'") else value.lower())
            pos=match.end()
        self.index=0

    def peek(self):
        return self.tokens[self.index] if self.index<len(self.tokens) else None

    def take(self, expected=None):
        value=self.peek()
        require(value is not None and (expected is None or value==expected), 'POLICY_SYNTAX')
        self.index+=1
        return value

    def name(self):
        value=self.take()
        require(re.fullmatch('[a-z_][a-z_0-9]*',value), 'POLICY_NAME')
        while self.peek()=='.':
            self.take('.'); value+='.'+self.take()
        return value

    def type_name(self):
        value=self.name()
        if value in ('character','pg_catalog.character'):
            self.take('varying'); value='varchar'
        value=value.removeprefix('pg_catalog.')
        require(value in ('uuid','text','varchar'), 'POLICY_TYPE')
        array=False
        if self.peek()=='[':
            self.take('['); self.take(']'); array=True
        return value,array

    @staticmethod
    def cast(node, datatype):
        kind,array=datatype
        if node==('literal','null') and not array:
            return node
        if array:
            require(kind in ('text','varchar') and node[0]=='array', 'POLICY_TYPE')
            return node
        # Only literal strings and known varchar/text-valued guard operands get
        # deparser-inserted text coercion elision. UUID-to-text is never elided.
        text_value=(node[0]=='string' or
            (node[0]=='column' and node[1].split('.')[-1] in ('status','role')) or
            (node[0]=='call' and node[1] in ('current_setting','coalesce')))
        if kind in ('text','varchar') and text_value:
            return node
        return ('cast',kind,node)

    def primary(self):
        value=self.peek()
        if value=='(':
            self.take('('); node=self.expr(); self.take(')')
        elif value=='not':
            self.take(); node=('not',self.expr(30))
        elif value=='case':
            self.take(); self.take('when'); condition=self.expr()
            self.take('then'); yes=self.expr(); self.take('else'); no=self.expr()
            self.take('end'); node=('case',condition,yes,no)
        elif value=='exists':
            self.take(); self.take('('); self.take('select'); self.take('1'); self.take('from')
            table=self.name()
            require(table in {'public.'+t for t in TABLES}, 'POLICY_RELATION')
            if self.peek()=='as': self.take()
            alias=self.name(); require(alias in ('u','m','o'), 'POLICY_ALIAS')
            self.take('where'); condition=self.expr(); self.take(')')
            node=('exists',table,alias,condition)
        elif value=='cast':
            self.take(); self.take('('); operand=self.expr(); self.take('as')
            datatype=self.type_name(); self.take(')'); node=self.cast(operand,datatype)
        elif value=='array':
            self.take(); self.take('['); operands=[self.expr()]
            while self.peek()==',': self.take(); operands.append(self.expr())
            self.take(']'); require(all(n[0]=='string' for n in operands), 'POLICY_ARRAY')
            node=('array',tuple(operands))
        elif value in ('true','false','null'):
            node=('literal',self.take())
        elif value and value.startswith("'"):
            node=('string',self.take()[1:-1].replace("''", "'"))
        elif value and value.isdigit():
            node=('number',self.take())
        else:
            name=self.name()
            if self.peek()=='(':
                if name in ('pg_catalog.current_setting','pg_catalog.length','pg_catalog.coalesce'):
                    name=name.removeprefix('pg_catalog.')
                require(name in ('current_setting','length','coalesce',
                    'jous_security.organization_is_active'), 'POLICY_FUNCTION')
                self.take('('); args=[self.expr()]
                while self.peek()==',': self.take(); args.append(self.expr())
                self.take(')')
                require(len(args)==(2 if name in ('current_setting','coalesce') else 1),
                        'POLICY_FUNCTION')
                node=('call',name,tuple(args))
            else:
                require(name in {'id','user_id','organization_id','status','role',
                    'u.id','u.status','m.organization_id','organizations.id',
                    'o.id','projects.organization_id'}, 'POLICY_COLUMN')
                node=('column',name)
        while self.peek()=='::':
            self.take(); node=self.cast(node,self.type_name())
        return node

    def expr(self, minimum=0):
        left=self.primary()
        while True:
            op=self.peek()
            precedence={'or':5,'and':10,'=':20,'~':20,'operator':20,'in':20}.get(op,-1)
            if precedence<minimum: return left
            self.take()
            if op=='operator':
                self.take('('); self.take('pg_catalog'); self.take('.')
                op=self.take(); require(op in ('=','~'), 'POLICY_OPERATOR'); self.take(')')
            if op=='in':
                self.take('('); members=[self.expr()]
                while self.peek()==',': self.take(); members.append(self.expr())
                self.take(')'); require(all(n[0]=='string' for n in members), 'POLICY_ARRAY')
                left=('in',left,tuple(members)); continue
            if op=='=' and self.peek()=='any':
                self.take(); self.take('('); array=self.expr(); self.take(')')
                require(array[0]=='array', 'POLICY_ARRAY')
                left=('in',left,array[1]); continue
            right=self.expr(precedence+1)
            if op in ('and','or'):
                operands=left[1] if left[0]==op else (left,)
                operands+=right[1] if right[0]==op else (right,)
                left=(op,operands)
            else:
                left=(op,left,right)

    def result(self):
        result=self.expr()
        require(self.peek() is None, 'POLICY_SYNTAX')
        return result


def policy_structure(expression):
    try:
        return GuardStructure(expression).result()
    except Stop:
        raise
    except (RecursionError, IndexError, TypeError, ValueError):
        raise Stop('POLICY_STRUCTURE') from None


def verify_policies(c, module):
    expected = {}
    for t, commands in module.COMMANDS.items():
        guard = module.GUARDS[t]
        expected[(t,f'jous_{t}_guard')] = ('RESTRICTIVE',['jous_runtime'],'ALL',guard,guard)
        for cmd in commands:
            expected[(t,f'jous_{t}_{cmd.lower()}')] = (
                'PERMISSIVE',['jous_runtime'],cmd,None if cmd=='INSERT' else guard,
                guard if cmd in ('INSERT','UPDATE') else None)
        if t in ('users','organizations'):
            expected[(t,f'jous_{t}_helper_read')] = ('PERMISSIVE',['jous_security_reader'],'SELECT','true',None)
    actual = policies(c)
    require(len(actual) == len(expected) and
            {(r['tablename'],r['policyname']) for r in actual} == set(expected), 'POLICY_SET')
    for r in actual:
        e = expected[(r['tablename'],r['policyname'])]
        require((r['permissive'],r['roles'],r['cmd']) == e[:3], 'POLICY_CONTRACT')
        for field, expr in zip(('qual','with_check'),e[3:]):
            require((r[field] is None) == (expr is None), 'POLICY_CLAUSE')
            if expr is not None:
                require(policy_structure(r[field]) == policy_structure(expr),
                        'POLICY_EXPRESSION_MISMATCH')


def verify_helpers(c, statements, ids):
    actual = rows(c, """SELECT n.nspname,p.proname,pg_catalog.oidvectortypes(p.proargtypes) AS args,
      p.prorettype::regtype::text AS returns,p.proowner,p.prosecdef,p.provolatile,p.proparallel,
      p.proconfig,p.prosrc,l.lanname,p.proisstrict,p.prokind,
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
                and r['args'] == ('text, text' if name=='resolve_user' else 'uuid')
                and r['returns'] == ('uuid' if name=='resolve_user' else 'boolean')
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
    schema = one(c, """SELECT r.rolname AS owner FROM pg_catalog.pg_namespace n
      JOIN pg_catalog.pg_roles r ON r.oid=n.nspowner WHERE n.nspname='jous_security'""")
    require(schema == {'owner':'postgres'}, 'SCHEMA_OWNER')
    schema_acl = rows(c, """SELECT a.grantee,a.privilege_type,a.is_grantable
      FROM pg_catalog.pg_namespace n,
      LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
      WHERE n.nspname='jous_security' AND a.grantee<>n.nspowner""")
    require(len(schema_acl)==2 and {tuple(r.values()) for r in schema_acl} ==
            {(ids['jous_runtime'],'USAGE',False),(ids['jous_security_reader'],'USAGE',False)}, 'SCHEMA_ACL')


def verify_security(c, baseline):
    revision(c,'0002_runtime_rls')
    ids = role_gate(c)
    privilege_boundary(c)
    verify_ownership(c,True)
    state = table_state(c)
    require(all(r['owner']==next(b['owner'] for b in baseline['tables'] if b['relname']==r['relname'])
                and r['relrowsecurity'] is True and r['relforcerowsecurity'] is True for r in state), 'TABLE_RLS')
    module, statements = migration_contract()
    verify_helpers(c,statements,ids)
    verify_policies(c,module)
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
