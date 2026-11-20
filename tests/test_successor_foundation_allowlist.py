"""The successor must admit only its three named runtime relations."""
import re
import ast
import inspect
import textwrap
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from jous_api import database as db
from jous_api import route_economics_validation as route


@asynccontextmanager
async def scope(connection):
    yield


class Result:
    def all(self):
        return [('users', 'id', 'jous_runtime', 'SELECT', True)]


class Connection:
    def __init__(self, privileged, fail_first=False, fail_revision=False):
        self.privileged = privileged
        self.fail_first = fail_first
        self.fail_revision = fail_revision
        self.calls = 0

    async def scalar(self, statement):
        sql = str(statement)
        self.calls += 1
        if self.fail_first and self.calls == 1:
            return False
        if self.fail_revision and sql == db.ROUTE_ECONOMICS_STATE_CHECK:
            return False
        if 'has_any_column_privilege' in sql:
            match = re.search(r"r.name='jous_runtime' AND c.relname IN \(([^)]*)\)", sql)
            allowed = set(re.findall(r"'([^']+)'", match.group(1)))
            return self.privileged <= allowed
        return True

    async def execute(self, statement):
        return Result()


class FoundationAllowlistTests(unittest.IsolatedAsyncioTestCase):
    async def run_foundation(self, successor, names, fail_first=False, fail_revision=False):
        connection = Connection(set(names), fail_first, fail_revision)
        with patch.object(db, 'catalog_resolution', scope), \
             patch.object(db, 'runtime_temp_evidence', new_callable=AsyncMock), \
             patch.object(db, 'verify_runtime_policy_authority', new_callable=AsyncMock):
            await (db.validate_route_economics_foundation(connection) if successor
                   else db.validate_product_foundation(connection))

    async def test_v12_rejects_new_privileged_relation(self):
        with self.assertRaises(db.DatabaseUnavailable):
            await self.run_foundation(False, {'route_pricing_versions'})

    async def test_successor_accepts_exact_three(self):
        await self.run_foundation(True, {'route_pricing_versions', 'route_pricing_revocations', 'route_decisions'})

    async def test_successor_rejects_fourth_and_lookalike(self):
        for name in ('other_relation', 'route_decisions_extra', 'route_pricing_version'):
            with self.subTest(name=name), self.assertRaises(db.DatabaseUnavailable):
                await self.run_foundation(True, {name})

    async def test_identity_failure_remains_closed(self):
        with self.assertRaises(db.DatabaseUnavailable):
            await self.run_foundation(True, set(), fail_first=True)

    async def test_revision_failure_remains_closed(self):
        with self.assertRaises(db.DatabaseUnavailable):
            await self.run_foundation(True, set(), fail_revision=True)


def privilege_stages():
    """Execute the validator's actual ACL and privilege stages with fake catalog results."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(route.validate_route_economics_runtime)))
    stages = [node for node in ast.walk(tree) if isinstance(node, ast.With)
              and isinstance(node.items[0].context_expr, ast.Call)
              and any(isinstance(arg, ast.Constant) and arg.value in
                      ('ROUTE_ECONOMICS_ACLS', 'ROUTE_ECONOMICS_PRIVILEGES')
                      for arg in node.items[0].context_expr.args)]
    function = ast.AsyncFunctionDef(name='run', args=ast.arguments(posonlyargs=[], args=[ast.arg(arg='connection')],
        kwonlyargs=[], kw_defaults=[], defaults=[]), body=stages, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = dict(vars(route)); namespace['stage_observer'] = None
    exec(compile(module, '<validator privilege stages>', 'exec'), namespace)
    return namespace['run']


class PrivilegeConnection:
    def __init__(self, rows, relation_acl=0, column_acl=0):
        self.rows, self.relation_acl, self.column_acl = rows, relation_acl, column_acl

    async def scalar(self, statement):
        sql = str(statement)
        if sql == route.RELATION_ACL_SQL: return self.relation_acl
        if sql == route.COLUMN_ACL_SQL: return self.column_acl
        return True

    async def execute(self, statement):
        class Rows:
            def all(inner): return self.rows
        return Rows()


class SuccessorPrivilegeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.run_stages = privilege_stages()
        self.rows = [
            ('route_pricing_versions', 'pricing_version_id', True, False, False, False, False, False),
            ('route_pricing_revocations', 'pricing_version_id', True, False, False, False, False, False),
            ('route_decisions', 'task_id', True, True, False, False, False, False),
        ]

    async def test_expected_privileges_pass(self):
        await self.run_stages(PrivilegeConnection(self.rows))

    async def test_excess_privileges_rejected_for_each_relation(self):
        for i in range(3):
            rows = list(self.rows); row = list(rows[i]); row[4] = True; rows[i] = tuple(row)
            with self.subTest(relation=rows[i][0]), self.assertRaises(ValueError):
                await self.run_stages(PrivilegeConnection(rows))

    async def test_missing_required_privileges_rejected_for_each_relation(self):
        for i in range(3):
            rows = list(self.rows); row = list(rows[i]); row[2] = False; rows[i] = tuple(row)
            with self.subTest(relation=rows[i][0]), self.assertRaises(ValueError):
                await self.run_stages(PrivilegeConnection(rows))
        rows = list(self.rows); row = list(rows[2]); row[3] = False; rows[2] = tuple(row)
        with self.assertRaises(ValueError):
            await self.run_stages(PrivilegeConnection(rows))

    async def test_forbidden_grantees_rejected(self):
        for grantee in ('jous_security_reader', 'PUBLIC', 'anon', 'authenticated', 'service_role'):
            with self.subTest(grantee=grantee), self.assertRaises(ValueError):
                await self.run_stages(PrivilegeConnection(self.rows, column_acl=1))
        rows = list(self.rows); row = list(rows[0]); row[6] = True; rows[0] = tuple(row)
        with self.assertRaises(ValueError):
            await self.run_stages(PrivilegeConnection(rows))
