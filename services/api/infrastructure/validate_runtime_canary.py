"""Explicit production canary; no traffic server, admin login or fixture creation.

Requires separately approved pre-provisioned fixtures. All domain writes rollback.
The only commits exercise context reset in transactions containing no domain writes.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from jous_api.config import load_settings
from jous_api.runtime_resolution import catalog_resolution
from jous_api.database import Database, BASELINE_CHECK, validate_runtime
from jous_api.access import AccessService
from jous_api.identity import VerifiedPrincipal
from jous_api.permissions import PermissionService, Action
from jous_api import step7_execution_contract as final

CHECKS = ('startup', 'positive', 'cross_tenant', 'missing_invalid_context',
          'forbidden_privileges', 'physical_reuse', 'cancellation')
FORBIDDEN = (
    'SET ROLE jous_security_reader',
    'SET ROLE postgres',
    'ALTER ROLE jous_runtime BYPASSRLS',
    'ALTER TABLE public.projects DISABLE ROW LEVEL SECURITY',
    'CREATE TABLE public.jous_canary_forbidden(id pg_catalog.int4)',
    'UPDATE public.users SET status=status',
    'UPDATE public.organization_memberships SET role=role',
    'DELETE FROM public.projects',
    'DELETE FROM public.alembic_version',
)


class CanaryRejected(ValueError):
    pass


def require(value):
    if not value:
        raise CanaryRejected('CANARY_REJECTED')


def load_manifest(path, approved_sha):
    require(type(approved_sha) is str and re.fullmatch('[0-9a-f]{64}', approved_sha))
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == approved_sha)
    data = final.parse(raw)
    require(set(data) == {'schema', 'project', 'issuer', 'actors'})
    require(data['schema'] == 'jous.runtime-canary-fixtures.v1' and
            data['project'] == 'aqcixpoorbhjgvdkdjqd')
    require(type(data['issuer']) is str and data['issuer'].startswith('https://') and len(data['issuer']) <= 255)
    require(type(data['actors']) is list and len(data['actors']) == 2)
    result = []
    for actor in data['actors']:
        require(type(actor) is dict and set(actor) == {'subject', 'user', 'organization', 'project'})
        require(type(actor['subject']) is str and 0 < len(actor['subject']) <= 255)
        result.append(dict(subject=actor['subject'], **{k: UUID(actor[k]) for k in ('user', 'organization', 'project')}))
    for key in ('subject', 'user', 'organization', 'project'):
        require(result[0][key] != result[1][key])
    return dict(issuer=data['issuer'], actors=tuple(result))


async def denied(session, sql, params=None):
    try:
        async with session.begin_nested():
            await session.execute(text(sql), params or {})
    except DBAPIError as error:
        require(getattr(error.orig, 'sqlstate', None) == '42501')
    else:
        raise CanaryRejected('CANARY_REJECTED')


async def scoped(runtime, fixture, actor_index, check):
    actor = fixture['actors'][actor_index]
    async with runtime.scoped_transaction() as session:
        try:
            access = AccessService(session)
            identity = await access.resolve(VerifiedPrincipal(fixture['issuer'], actor['subject']))
            require(identity.user_id == actor['user'])
            scope = await access.organization(identity, actor['organization'])
            require((await access.project(scope, actor['project'])).project_id == actor['project'])
            await check(session, access, scope)
        finally:
            # Even an unexpectedly successful forbidden operation cannot persist.
            await session.rollback()


async def positive(runtime, fixture):
    for index in (0, 1):
        async def check(session, access, scope):
            permissions = PermissionService(access)
            await permissions.authorize(scope, Action.CREATE_PROJECT)
            project = uuid4()
            value = await session.scalar(text('INSERT INTO public.projects(id,organization_id,name,description) '
                'VALUES (:id,:org,:name,:description) RETURNING id'),
                dict(id=project, org=scope.organization_id, name='jous-canary-rollback', description='bounded control'))
            require(value == project)
            new_scope = await access.project(scope, project)
            await permissions.authorize(new_scope, Action.UPDATE_PROJECT)
            value = await session.scalar(text('UPDATE public.projects SET description=:description '
                'WHERE id=:id RETURNING description'), dict(id=project, description='updated rollback control'))
            require(value == 'updated rollback control')
        await scoped(runtime, fixture, index, check)


async def cross_tenant(runtime, fixture):
    for index in (0, 1):
        other = fixture['actors'][1-index]
        async def check(session, access, scope):
            for table, value in (('projects', other['project']), ('organizations', other['organization'])):
                # Finite table names only; no caller-supplied identifiers.
                require(await session.scalar(text('SELECT id FROM public.' + table + ' WHERE id=:id'), {'id': value}) is None)
            result = await session.execute(text('UPDATE public.projects SET description=:value WHERE id=:id'),
                dict(value='must rollback', id=other['project']))
            require(result.rowcount == 0)
            await denied(session, 'INSERT INTO public.projects(id,organization_id,name) VALUES (:id,:org,:name)',
                dict(id=uuid4(), org=other['organization'], name='must rollback'))
        await scoped(runtime, fixture, index, check)


async def missing_invalid_context(runtime, fixture):
    actor, other = fixture['actors']
    for user, organization in (('', ''), ('malformed', str(actor['organization'])),
                               (str(actor['user']), 'malformed'),
                               (str(actor['user']), str(other['organization']))):
        async with runtime.scoped_transaction() as session:
            try:
                await session.execute(text("SELECT pg_catalog.set_config('jous.user_id',:user,true), "
                    "pg_catalog.set_config('jous.organization_id',:org,true)"), dict(user=user, org=organization))
                require(await session.scalar(text('SELECT id FROM public.projects WHERE id=:id'),
                    dict(id=other['project'])) is None)
                await denied(session, 'INSERT INTO public.projects(id,organization_id,name) VALUES (:id,:org,:name)',
                    dict(id=uuid4(), org=other['organization'], name='must rollback'))
            finally:
                await session.rollback()


async def forbidden_privileges(runtime, fixture):
    async with runtime.scoped_transaction() as session:
        try:
            for sql in FORBIDDEN:
                await denied(session, sql)
        finally:
            await session.rollback()


async def physical_reuse(runtime, fixture):
    actor = fixture['actors'][0]
    async with runtime.engine.connect() as connection:
        await validate_runtime(connection)
        pid = await connection.scalar(text('SELECT pg_catalog.pg_backend_pid()'))
        await connection.rollback()
        for commit in (True, False):
            transaction = await connection.begin()
            try:
                await connection.execute(text("SELECT pg_catalog.set_config('jous.user_id',:user,true), "
                    "pg_catalog.set_config('jous.organization_id',:org,true)"),
                    dict(user=str(actor['user']), org=str(actor['organization'])))
                require(await connection.scalar(text('SELECT id FROM public.projects WHERE id=:id'),
                    dict(id=actor['project'])) == actor['project'])
                # These transactions contain no domain writes.
                await (transaction.commit() if commit else transaction.rollback())
                async with catalog_resolution(connection):
                    require(await connection.scalar(text(BASELINE_CHECK)) is True)
                require(await connection.scalar(text('SELECT pg_catalog.pg_backend_pid()')) == pid)
            finally:
                await connection.rollback()


async def cancellation(runtime, fixture):
    started = asyncio.Event()
    async def check(session, access, scope):
        started.set()
        await session.execute(text('SELECT pg_catalog.pg_sleep(5)'))
    task = asyncio.create_task(scoped(runtime, fixture, 0, check))
    try:
        await asyncio.wait_for(started.wait(), runtime.timeout_seconds)
        task.cancel()
        try:
            await asyncio.wait_for(task, runtime.timeout_seconds + 5)
        except asyncio.CancelledError:
            pass
        else:
            raise CanaryRejected('CANARY_REJECTED')
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    await runtime.check()


async def run(settings, fixture, *, confirmed=False, production_canary=False):
    require(confirmed is True and production_canary is True and settings.environment == 'production')
    require(settings.auth_issuer == fixture['issuer'])
    document = dict(schema='jous.runtime-canary-result.v1', decision='FAIL',
                    checks={}, runtime_activation=False, public_traffic=False, disposal=False)
    runtime = None
    try:
        runtime = Database(settings)
        await runtime.check()
        document['checks']['startup'] = 'PASS'
        for name, check in (('positive', positive), ('cross_tenant', cross_tenant),
                            ('missing_invalid_context', missing_invalid_context),
                            ('forbidden_privileges', forbidden_privileges),
                            ('physical_reuse', physical_reuse), ('cancellation', cancellation)):
            document['checks'][name] = 'FAIL'
            await check(runtime, fixture)
            document['checks'][name] = 'PASS'
        document['decision'] = 'PASS'
    except BaseException:
        document['decision'] = 'FAIL'
    finally:
        if runtime is not None:
            try:
                await runtime.dispose()
                document['disposal'] = True
            except BaseException:
                document['decision'] = 'FAIL'
    return document


def main(argv=None):
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise CanaryRejected('CANARY_REJECTED')
    try:
        parser = Parser(description=__doc__)
        parser.add_argument('--confirm-production-canary', action='store_true')
        parser.add_argument('--production-canary', action='store_true')
        parser.add_argument('--fixture-manifest')
        parser.add_argument('--approved-fixture-sha256')
        args = parser.parse_args(argv)
        require(args.confirm_production_canary and args.production_canary)
        final.load_final_contract()
        fixture = load_manifest(args.fixture_manifest, args.approved_fixture_sha256)
        settings = load_settings()  # Runtime settings only; never load migration settings.
        document = asyncio.run(run(settings, fixture, confirmed=True, production_canary=True))
    except SystemExit as error:
        if error.code == 0:
            return 0
        document = dict(schema='jous.runtime-canary-result.v1', decision='FAIL', runtime_activation=False, public_traffic=False)
    except BaseException:
        document = dict(schema='jous.runtime-canary-result.v1', decision='FAIL', runtime_activation=False, public_traffic=False)
    print(json.dumps(document, sort_keys=True))
    return 0 if document['decision'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
