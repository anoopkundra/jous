"""OPT-IN MANAGED MUTATIONS. Never run by test discovery. No role/migration changes."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from jous_api.config import load_settings, load_migration_settings
from jous_api.database import Database, validate_runtime, BASELINE_CHECK
from jous_api.access import AccessService
from jous_api.identity import AccessDenied, VerifiedPrincipal, RequestIdentity
from jous_api.models import User, Organization, OrganizationMembership, Project
from jous_api.permissions import PermissionService, Action
from sqlalchemy.ext.asyncio import AsyncSession

TABLES = ('users', 'organizations', 'organization_memberships', 'projects')
HEAD = '0002_runtime_rls'
PROJECT_REFERENCE = 'aqcixpoorbhjgvdkdjqd'  # Public approved dedicated validation target.


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def fingerprint(settings):
    url = make_url(settings.database_url.get_secret_value())
    # asyncpg dialect merges URL query arguments over authority fields. No query
    # options are required by this controlled validator: reject all overrides,
    # including decoded/duplicate names, DSNs and multihost arguments.
    require(not url.query, 'Managed target query options are not permitted')
    require(url.username and url.database and url.port in (None, 5432, 6543),
            'Invalid managed target')
    # Regional pooler host + database name alone is NOT a project identity.
    direct = url.host == f'db.{PROJECT_REFERENCE}.supabase.co'
    pooled = bool(url.host and url.host.endswith('.pooler.supabase.com') and
                  (url.username or '').rpartition('.')[2] == PROJECT_REFERENCE)
    require(direct or pooled, 'Approved project reference could not be verified')
    return hashlib.sha256(f'{url.host}:{url.port or 5432}/{url.database}/{PROJECT_REFERENCE}'.encode()).hexdigest()[:16]


async def snapshot(engine):
    async with engine.connect() as connection:
        require(await connection.scalar(text('SELECT rolsuper OR rolbypassrls FROM pg_catalog.pg_roles '
            'WHERE rolname=current_user')), 'Unfiltered administrative visibility required')
        revision = (await connection.execute(text('SELECT version_num FROM public.alembic_version'))).scalars().all()
        counts = {table: await connection.scalar(text('SELECT count(*) FROM public.' + table)) for table in TABLES}
        server = (await connection.execute(text('SELECT current_database(), inet_server_addr()::text, inet_server_port()'))).one()
        # ACL/security catalog data only, never credentials or tenant row contents.
        queries = {
            'relations': "SELECT n.nspname,c.relname,c.oid,c.relowner,c.relrowsecurity,c.relforcerowsecurity,c.relacl::text "
                "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema' ORDER BY 1,2,3",
            'policies': 'SELECT schemaname,tablename,policyname,permissive,roles::text,cmd,qual,with_check FROM pg_catalog.pg_policies ORDER BY 1,2,3',
            'functions': "SELECT p.oid,p.proname,p.proowner,p.proacl::text,p.prosecdef,p.proconfig::text,p.prosrc "
                "FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='jous_security' ORDER BY 1",
            'roles': "SELECT oid,rolname,rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication,rolinherit "
                "FROM pg_catalog.pg_roles WHERE rolname IN ('jous_runtime','jous_security_reader') ORDER BY 2",
            'memberships': 'SELECT roleid,member,grantor,admin_option FROM pg_catalog.pg_auth_members ORDER BY 1,2,3',
            'column_acls': "SELECT c.oid,a.attnum,a.attacl::text FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n "
                "ON n.oid=c.relnamespace JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid WHERE n.nspname='public' "
                "AND c.relname IN ('users','organizations','organization_memberships','projects') AND a.attnum>0 ORDER BY 1,2",
            'extensions': 'SELECT oid,extname FROM pg_catalog.pg_extension ORDER BY 1'}
        security = {key: [list(row) for row in (await connection.execute(text(sql))).all()] for key, sql in queries.items()}
        return {'revision': revision, 'counts': counts, 'server': list(server), 'security': security}


async def cleanup(admin, manifest):
    marker = 'jous-step7-' + str(UUID(manifest['run_id']))
    require(manifest['issuer'] == marker, 'Invalid cleanup marker')
    ids = {table: [UUID(value) for value in manifest['ids'][table]] for table in TABLES}
    # Markers AND exact UUIDs prevent a manifest from selecting unrelated records.
    async with admin.engine.begin() as connection:
        await connection.execute(text('DELETE FROM public.projects WHERE id=ANY(CAST(:ids AS uuid[])) AND name=:marker'),
                                 {'ids': ids['projects'], 'marker': marker})
        await connection.execute(text('DELETE FROM public.organization_memberships m WHERE m.id=ANY(CAST(:ids AS uuid[])) '
            'AND EXISTS (SELECT 1 FROM public.users u WHERE u.id=m.user_id AND u.auth_issuer=:marker)'),
            {'ids': ids['organization_memberships'], 'marker': marker})
        await connection.execute(text('DELETE FROM public.organizations WHERE id=ANY(CAST(:ids AS uuid[])) AND name=:marker'),
                                 {'ids': ids['organizations'], 'marker': marker})
        await connection.execute(text('DELETE FROM public.users WHERE id=ANY(CAST(:ids AS uuid[])) AND auth_issuer=:marker'),
                                 {'ids': ids['users'], 'marker': marker})
    require(await snapshot(admin.engine) == manifest['baseline'], 'Cleanup/baseline verification failed')


async def expect_denied(connection, sql, params=None):
    # Restore transaction usability after each expected PostgreSQL denial.
    try:
        async with connection.begin_nested():
            await connection.execute(text(sql), params or {})
    except DBAPIError as error:
        require(getattr(error.orig, 'sqlstate', None) == '42501', 'Unexpected database failure during denial test')
    else:
        raise RuntimeError('Expected privilege/RLS denial did not occur')


async def fixtures(admin, manifest):
    ids = {table: [UUID(value) for value in manifest['ids'][table]] for table in TABLES}
    marker = manifest['issuer']
    async with admin.engine.begin() as connection:
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            users = [User(id=value, auth_issuer=marker, auth_subject=str(value),
                          status='inactive' if i==2 else 'active') for i,value in enumerate(ids['users'])]
            orgs = [Organization(id=value, name=marker, status='inactive' if i==2 else 'active')
                    for i,value in enumerate(ids['organizations'])]
            session.add_all(users + orgs)
            await session.flush()
            assignments = [(0,0,'owner','active'), (1,1,'member','active'), (2,0,'member','active'),
                           (0,2,'member','active'), (0,3,'member','inactive'), (3,0,'admin','active')]
            session.add_all([OrganizationMembership(id=value, user_id=users[u].id, organization_id=orgs[o].id,
                role=role,status=status) for value,(u,o,role,status) in zip(ids['organization_memberships'], assignments)])
            session.add_all([Project(id=value, organization_id=orgs[i].id, name=marker)
                             for i,value in enumerate(ids['projects'])])
            await session.flush()


async def authorized_writes(session, permissions, scope, *, owner):
    """Positive evidence is mandatory; every mutation stays in caller rollback."""
    await permissions.authorize(scope, Action.CREATE_PROJECT)
    project = uuid4()
    params = {'id': project, 'org': scope.organization_id, 'name': 'positive-control',
              'description': 'insert-control'}
    row = (await session.execute(text(
        'INSERT INTO public.projects(id,organization_id,name,description) '
        'VALUES (:id,:org,:name,:description) RETURNING id,organization_id,name,description'), params)).one_or_none()
    require(row is not None and tuple(row) == (project, scope.organization_id, 'positive-control', 'insert-control'),
            'Authorized Project INSERT failed')
    project_scope = await permissions.access.project(scope, project)
    await permissions.authorize(project_scope, Action.UPDATE_PROJECT)
    row = (await session.execute(text(
        "UPDATE public.projects SET name='updated-control',description='update-control' "
        'WHERE id=:id AND organization_id=:org RETURNING id,name,description'), params)).one_or_none()
    require(row is not None and tuple(row) == (project, 'updated-control', 'update-control'),
            'Authorized Project UPDATE failed')
    if owner:
        await permissions.authorize(scope, Action.UPDATE_ORGANIZATION_NAME)
        row = (await session.execute(text(
            "UPDATE public.organizations SET name='owner-update-control' WHERE id=:org RETURNING id,name"),
            {'org': scope.organization_id})).one_or_none()
        require(row is not None and tuple(row) == (scope.organization_id, 'owner-update-control'),
                'Authorized Organization UPDATE failed')


async def concurrent_checks(*checks):
    # TaskGroup cancels AND drains siblings before propagating failure to cleanup.
    async with asyncio.TaskGroup() as group:
        for check in checks:
            group.create_task(check)


async def runtime_tests(runtime, manifest, admin_role):
    ids = {table: [UUID(value) for value in manifest['ids'][table]] for table in TABLES}
    users, orgs, projects = (ids[table] for table in ('users','organizations','projects'))
    for actor, own in ((0,0),(1,1)):
        async with runtime.scoped_transaction() as session:
            access = AccessService(session)
            identity = await access.resolve(VerifiedPrincipal(manifest['issuer'], str(users[actor])))
            scope = await access.organization(identity, orgs[own])
            require((await access.project(scope,projects[own])).project_id == projects[own], 'Own access failed')
            await PermissionService(access).authorize(scope, Action.READ_ORGANIZATION)
            if actor == 1:
                try:
                    await PermissionService(access).authorize(scope, Action.UPDATE_ORGANIZATION_NAME)
                except AccessDenied:
                    pass
                else:
                    raise RuntimeError('Member acquired owner authority')
            require(await session.scalar(text('SELECT count(*) FROM public.organizations')) == 1, 'Unscoped Organization leaked')
            require(await session.scalar(text('SELECT count(*) FROM public.projects')) == 1, 'Unscoped Project leaked')
            # All positive and negative writes are rolled back, even on failure.
            try:
                await authorized_writes(session, PermissionService(access), scope, owner=actor == 0)
            finally:
                await session.rollback()
            # A fresh protected transaction is needed after rollback; do not reuse
            # a completed context for subsequent denial checks.
    for actor, own in ((0,0),(1,1)):
        async with runtime.scoped_transaction() as session:
            access = AccessService(session)
            identity = await access.resolve(VerifiedPrincipal(manifest['issuer'], str(users[actor])))
            scope = await access.organization(identity, orgs[own])
            other = 1-own
            result = await session.execute(text('UPDATE public.projects SET description=:value WHERE id=:id'),
                {'value':'must-not-persist','id':projects[other]})
            require(result.rowcount == 0, 'Cross-tenant update succeeded')
            result = await session.execute(text('UPDATE public.organizations SET name=:value WHERE id=:id'),
                {'value':'must-not-persist','id':orgs[other]})
            require(result.rowcount == 0, 'Cross-tenant Organization update succeeded')
            await expect_denied(session,'INSERT INTO public.projects(id,organization_id,name) VALUES (:id,:org,:name)',
                {'id':uuid4(),'org':orgs[other],'name':manifest['issuer']})
            await expect_denied(session,'UPDATE public.projects SET organization_id=:org WHERE id=:id',
                {'org':orgs[other],'id':projects[own]})
            await expect_denied(session,"UPDATE public.projects SET status='inactive' WHERE id=:id",{'id':projects[own]})
            # Force rollback of ALL write tests, including unexpected successful writes.
            await session.rollback()
    for user,org in ((users[2],orgs[0]), (users[0],orgs[2]), (users[0],orgs[3]),
                     (users[3],orgs[0]), (uuid4(),orgs[0]), (users[0],orgs[1])):
        async with runtime.engine.begin() as connection:
            await connection.execute(text("SELECT set_config('jous.user_id',:user,true), set_config('jous.organization_id',:org,true)"),
                                     {'user':str(user),'org':str(org)})
            require(await connection.scalar(text('SELECT count(*) FROM public.projects')) == 0,'Invalid relationship authorized')
    for user,org in (('', ''), ('malformed',str(orgs[0])), (str(users[0]),'malformed')):
        async with runtime.engine.begin() as connection:
            await connection.execute(text("SELECT set_config('jous.user_id',:user,true), set_config('jous.organization_id',:org,true)"),
                                     {'user':user,'org':org})
            require(await connection.scalar(text('SELECT count(*) FROM public.projects')) == 0,'Malformed context authorized')
            require(await connection.scalar(text('SELECT count(*) FROM public.organization_memberships')) == 0,'Malformed discovery authorized')
    async with runtime.engine.begin() as connection:
        require(await connection.scalar(text('SELECT count(*) FROM public.projects')) == 0,'Missing context authorized')
        for issuer,subject in ((manifest['issuer'],str(users[2])), (manifest['issuer'],'unknown'),
                               ('wrong-issuer',str(users[0])), ('','')):
            require(await connection.scalar(text('SELECT jous_security.resolve_user(:issuer,:subject)'),
                {'issuer':issuer,'subject':subject}) is None, 'Invalid identity resolved')
        for sql in ('CREATE TABLE public.jous_forbidden(id integer)', 'ALTER TABLE public.projects DISABLE ROW LEVEL SECURITY',
                    'DROP TABLE public.projects', 'ALTER POLICY jous_projects_select ON public.projects USING (true)',
                    "ALTER ROLE jous_runtime BYPASSRLS", 'SET ROLE jous_security_reader',
                    'DELETE FROM public.alembic_version', 'UPDATE public.organization_memberships SET role=role',
                    'UPDATE public.users SET status=status',
                    'INSERT INTO public.users(id) VALUES (gen_random_uuid())',
                    'INSERT INTO public.organization_memberships(id) VALUES (gen_random_uuid())',
                    'DELETE FROM public.projects',
                    'DELETE FROM public.organizations', 'DELETE FROM public.users',
                    'DELETE FROM public.organization_memberships'):
            await expect_denied(connection, sql)
        await expect_denied(connection,'SET ROLE "' + admin_role.replace('"','""') + '"')
    # Reuse one held physical connection. Commit/rollback/savepoint/exception reset context.
    async with runtime.engine.connect() as connection:
        pid = await connection.scalar(text('SELECT pg_backend_pid()'))
        await connection.rollback()
        for commit in (True, False):
            transaction = await connection.begin()
            await connection.execute(text("SELECT set_config('jous.user_id',:user,true),set_config('jous.organization_id',:org,true)"),
                                     {'user':str(users[0]),'org':str(orgs[0])})
            require(await connection.scalar(text('SELECT count(*) FROM public.projects')) == 1,'Pool fixture access failed')
            await (transaction.commit() if commit else transaction.rollback())
            require(await connection.scalar(text(BASELINE_CHECK)), 'Context survived transaction')
            require(await connection.scalar(text('SELECT pg_backend_pid()')) == pid,'Physical connection reuse not exercised')
            await connection.rollback()
        try:
            async with connection.begin():
                await connection.execute(text("SELECT set_config('jous.user_id',:user,true)"),{'user':str(users[0])})
                raise ValueError('controlled exception')
        except ValueError:
            pass
        require(await connection.scalar(text(BASELINE_CHECK)), 'Context survived exception')
        await connection.rollback()
    async def concurrent(actor):
        async with runtime.scoped_transaction() as session:
            access=AccessService(session)
            identity=await access.resolve(VerifiedPrincipal(manifest['issuer'],str(users[actor])))
            await access.organization(identity,orgs[actor])
            await asyncio.sleep(0)
            require(await session.scalar(text('SELECT id FROM public.projects')) == projects[actor], 'Concurrent scope leaked')
    await concurrent_checks(concurrent(0),concurrent(1))
    started=asyncio.Event()
    async def cancellable():
        async with runtime.scoped_transaction() as session:
            access=AccessService(session)
            await access.resolve(VerifiedPrincipal(manifest['issuer'],str(users[0])))
            started.set()
            await session.execute(text('SELECT pg_sleep(5)'))
    task=asyncio.create_task(cancellable())
    try:
        await asyncio.wait_for(started.wait(),runtime.timeout_seconds)
        task.cancel()
        try:
            await asyncio.wait_for(task,runtime.timeout_seconds+2)
        except asyncio.CancelledError:
            pass
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task,return_exceptions=True)
    await runtime.check()


async def run(args):
    require(args.opt_in_managed_validation, 'Explicit managed validation opt-in required')
    admin_settings=load_migration_settings()
    require(admin_settings.environment != 'production', 'Production target refused')
    require(fingerprint(admin_settings)==args.target_fingerprint,'Target mismatch')
    runtime_settings = None
    if not args.cleanup_only:
        runtime_settings = load_settings()
        require(runtime_settings.environment != 'production', 'Production target refused')
        require(runtime_settings.database_url is not None, 'Runtime URL required')
        require(fingerprint(runtime_settings) == args.target_fingerprint, 'Runtime target mismatch')
    admin=Database(admin_settings)
    runtime=None
    try:
        before=await snapshot(admin.engine)
        require(before['revision']==[HEAD], 'Expected Step 7 head required')
        path=Path(args.manifest)
        if args.cleanup_only:
            manifest=json.loads(path.read_text())
            require(manifest['fingerprint']==args.target_fingerprint,'Cleanup target mismatch')
            require(manifest['baseline']['server']==before['server'],'Cleanup server mismatch')
            await cleanup(admin,manifest)
            print('TARGETED CLEANUP / BASELINE: PASS')
            return
        runtime=Database(runtime_settings)
        async with runtime.engine.connect() as connection:
            await validate_runtime(connection)
            server=list((await connection.execute(text('SELECT current_database(),inet_server_addr()::text,inet_server_port()'))).one())
            require(server==before['server'],'Server identity mismatch')
        async with admin.engine.connect() as connection:
            admin_role=await connection.scalar(text('SELECT current_user'))
        require(all(count==0 for count in before['counts'].values()),'Nonempty domain baseline refused')
        manifest={'run_id':str(uuid4()),'fingerprint':args.target_fingerprint,'baseline':before,
                  'ids':{table:[str(uuid4()) for _ in range(count)] for table,count in zip(TABLES,(4,4,6,4))}}
        manifest['issuer']='jous-step7-'+manifest['run_id']
        # Exclusive creation before any write. Never overwrite existing manifests/artifacts.
        with path.open('x',encoding='utf-8') as output:
            json.dump(manifest,output,indent=2)
        try:
            await fixtures(admin,manifest)
            await runtime_tests(runtime,manifest,admin_role)
        finally:
            await cleanup(admin,manifest)
        print('REAL RUNTIME ISOLATION / POOL / PRIVILEGES / CLEANUP / REVISION: PASS')
    finally:
        if runtime is not None:
            await runtime.dispose()
        await admin.dispose()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--opt-in-managed-validation',action='store_true')
    parser.add_argument('--target-fingerprint',required=True)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--cleanup-only',action='store_true')
    args=parser.parse_args()
    try:
        asyncio.run(run(args))
    except Exception:
        # No exception text, URL, credentials or PostgreSQL detail is reflected.
        raise SystemExit('Managed validation failed. Retain manifest; review or retry targeted cleanup.') from None


if __name__=='__main__':
    main()
