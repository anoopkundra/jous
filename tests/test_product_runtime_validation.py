"""Mock catalog tests; explicitly not PostgreSQL security certification."""
import importlib.util
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch
from jous_api import product_runtime_validation as v
from jous_api.database import Database,DatabaseUnavailable,STATE_CHECK,PRODUCT_STATE_CHECK
from jous_api.task_models import tasks,executions,POLICIES,TASK_COLUMNS,EXECUTION_COLUMNS,TASK_CHECKS
from jous_api.product_policy_canonicalization import canonical_policy_expression


class ValidatorTests(unittest.IsolatedAsyncioTestCase):
    def connection(self,mutate=None):
        columns=v.expected_columns()
        constraints=[(table,name,*row) for (table,name),row in v.expected_constraints().items()]
        source_checks={
            (table.name,str(constraint.name)):str(constraint.sqltext)
            for table in (tasks,executions) for constraint in table.constraints
            if constraint.__class__.__name__=='CheckConstraint'
        }
        # Model the unnormalized SQL returned by pg_get_expr, rather than
        # feeding the validator's own canonical expectations back as input.
        constraints=[row[:12]+(source_checks.get((row[0],row[1]),row[12]),)
                     for row in constraints]
        indexes=[(table,name,*row) for (table,name),row in v.expected_indexes().items()]
        policies=[(table,name,'r' if cmd=='SELECT' else 'a',True,['jous_runtime'],sql if cmd=='SELECT' else None,sql if cmd=='INSERT' else None) for name,(table,cmd,sql) in POLICIES.items()]
        grants=[(table,col,role,priv,role=='jous_runtime' and (priv=='SELECT' or priv=='INSERT' and col not in ('created_at','recorded_at')))
                for table,cols in [('tasks',TASK_COLUMNS),('executions',EXECUTION_COLUMNS)] for col in cols for role in ('jous_runtime','jous_security_reader') for priv in ('SELECT','INSERT','UPDATE','REFERENCES')]
        responses=[columns,constraints,indexes,policies,grants]
        if mutate:mutate(responses)
        connection=SimpleNamespace(scalar=AsyncMock(return_value=True),execute=AsyncMock(side_effect=[SimpleNamespace(all=lambda rows=rows:rows) for rows in responses]))
        return connection
    async def run_validation(self,connection):
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def scope(c):yield
        with patch.object(v,'validate_product_foundation',new_callable=AsyncMock) as foundation,patch.object(v,'catalog_resolution',scope):
            await v.validate_product_runtime(connection);foundation.assert_awaited_once_with(connection)
    async def test_exact_mock_catalog_passes(self):await self.run_validation(self.connection())
    async def test_stage_observer_reports_bounded_ordered_timings(self):
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def scope(c):yield
        events=[]
        with patch.object(v,'validate_product_foundation',new_callable=AsyncMock),patch.object(v,'catalog_resolution',scope):
            await v.validate_product_runtime(self.connection(),stage_observer=lambda name,elapsed,error:events.append((name,elapsed,error)))
        self.assertEqual([row[0] for row in events],['FOUNDATION','PRODUCT_RLS_ENCODING','COLUMNS','CONSTRAINTS','INDEXES','POLICIES','ACL_TABLE_PRIVILEGES','COLUMN_PRIVILEGES'])
        self.assertTrue(all(isinstance(row[1],float) and row[1]>=0 and row[2] is None for row in events))
    async def test_stage_observer_failure_cannot_change_validation(self):
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def scope(c):yield
        def broken_observer(*_):raise RuntimeError('diagnostic observer failure')
        with patch.object(v,'validate_product_foundation',new_callable=AsyncMock),patch.object(v,'catalog_resolution',scope):
            await v.validate_product_runtime(self.connection(),stage_observer=broken_observer)
    async def test_mutated_catalog_grants_policies_fail_closed(self):
        mutations=[lambda r:r[0].pop(),lambda r:r[1].pop(),lambda r:r[2].pop(),lambda r:r[3].pop(),lambda r:r[4].pop(),
                   lambda r:r[3].append(('tasks','unexpected','r',True,['public'],'true',None))]
        for mutation in mutations:
            with self.assertRaises(DatabaseUnavailable):await self.run_validation(self.connection(mutation))
    async def test_role_rls_or_public_grant_failure_denies(self):
        c=self.connection();c.scalar.return_value=False
        with self.assertRaises(DatabaseUnavailable):await self.run_validation(c)
    def test_schema_exact_column_order_defaults_and_checks(self):
        self.assertEqual(tuple(tasks.columns.keys()),TASK_COLUMNS);self.assertEqual(tuple(executions.columns.keys()),EXECUTION_COLUMNS)
        self.assertEqual([c.name for c in tasks.columns if c.server_default],['created_at'])
        self.assertEqual([c.name for c in executions.columns if c.server_default],['recorded_at'])
        self.assertNotIn('updated_at',tasks.columns);self.assertNotIn('status',tasks.columns)
        self.assertIn('0002_runtime_rls',STATE_CHECK);self.assertNotIn('0003_',STATE_CHECK)
        self.assertIn('0004_product_acl_hardening',PRODUCT_STATE_CHECK)
        self.assertNotIn('0003_project_tasks_executions',PRODUCT_STATE_CHECK)
        source=Path('services/api/src/jous_api/database.py').read_text()
        self.assertIn('await verify_runtime_policy_authority(connection)',source)
        self.assertIn('(self._validator or validate_runtime)(connection)',source)
        self.assertIn('(self._validator or validate_runtime)(session)',source)
        self.assertNotIn('state=False',Path(v.__file__).read_text())
    def test_literal_migration_matches_metadata(self):
        spec=importlib.util.spec_from_file_location('v12_migration','services/api/migrations/versions/0003_project_tasks_executions.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.down_revision,'0002_runtime_rls')
        text='\n'.join(module.UPGRADE_SQL)
        additive_execution_constraint='ck_executions_credential_authority_ref'
        for name in [c.name for t in (tasks,executions) for c in t.constraints
                     if c.name != additive_execution_constraint]:self.assertIn(name,text)
        # Dispatch provenance was added forward-only by V1.4C 0009, not by the
        # frozen V1.2 execution migration whose literal contract is checked here.
        economic=Path('services/api/migrations/versions/0009_economic_ledger_core.py').read_text()
        self.assertIn(f'ADD CONSTRAINT {additive_execution_constraint}',economic)
        self.assertEqual(text.count('CREATE POLICY '),4);self.assertNotIn('NOT EXISTS',text)
        self.assertNotIn('SECURITY DEFINER',text)


class ErrorCodeCanonicalizationTests(unittest.IsolatedAsyncioTestCase):
    def connection_with_error_code_check(self, sql):
        validator=ValidatorTests()
        connection=validator.connection()
        responses=list(connection.execute.side_effect)
        constraints=responses[1].all()
        for i,row in enumerate(constraints):
            if row[0:2]==('executions','ck_executions_error_code'):
                constraints[i]=row[:12]+(sql,)
                break
        else:
            raise AssertionError('error-code constraint fixture missing')
        responses[1]=SimpleNamespace(all=lambda:constraints)
        connection.execute.side_effect=responses
        return connection

    async def run_validation(self, connection):
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def scope(c): yield
        with patch.object(v,'validate_product_foundation',new_callable=AsyncMock),patch.object(v,'catalog_resolution',scope):
            await v.validate_product_runtime(connection)

    async def test_migration_and_postgresql_catalog_renderings_are_equivalent(self):
        original=v.ERROR_CODE_MIGRATION_EXPRESSION
        catalog=v.ERROR_CODE_CATALOG_EXPRESSION
        self.assertEqual(v.canonical_error_code_expression(original),original)
        self.assertEqual(v.canonical_error_code_expression(catalog),original)

        spec=importlib.util.spec_from_file_location('v12_migration','services/api/migrations/versions/0003_project_tasks_executions.py')
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        sql='\n'.join(migration.UPGRADE_SQL)
        self.assertIn('CONSTRAINT ck_executions_error_code CHECK ('+original+')',sql)

        await self.run_validation(self.connection_with_error_code_check(catalog))

    async def test_unapproved_error_code_constraint_variants_fail_closed(self):
        catalog=v.ERROR_CODE_CATALOG_EXPRESSION
        bad=(
            catalog.replace("'provider_timeout'::text", "'provider_timeout'::text, 'extra'::text"),
            catalog.replace(", 'provider_timeout'::text", ''),
            catalog.replace('error_code IS NULL','error_code IS NOT NULL'),
            catalog.replace('error_code = ANY','error_code <> ANY'),
            catalog.replace('= ANY','= ALL'),
            catalog.replace("'not_dispatched'::text", "'not_dispatched'::varchar"),
        )
        for sql in bad:
            with self.subTest(sql=sql):
                self.assertIsNone(v.canonical_error_code_expression(sql))
                with self.assertRaises(DatabaseUnavailable):
                    await self.run_validation(self.connection_with_error_code_check(sql))


class ProductPolicyCanonicalizationTests(unittest.IsolatedAsyncioTestCase):
    MANAGED_EXECUTIONS_INSERT = """((actor_user_id = CASE WHEN ((length(current_setting('jous.user_id'::text, true)) = 36) AND (current_setting('jous.user_id'::text, true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)) THEN (current_setting('jous.user_id'::text, true))::uuid ELSE NULL::uuid END) AND (EXISTS ( SELECT 1 FROM public.tasks t WHERE ((executions.task_id = t.id) AND (executions.organization_id = t.organization_id) AND (executions.project_id = t.project_id) AND (executions.actor_user_id = t.actor_user_id) AND (executions.dispatch_claim_id = t.dispatch_claim_id) AND (EXISTS ( SELECT 1 FROM public.organization_memberships m WHERE ((m.organization_id = t.organization_id) AND (m.user_id = CASE WHEN ((length(current_setting('jous.user_id'::text, true)) = 36) AND (current_setting('jous.user_id'::text, true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)) THEN (current_setting('jous.user_id'::text, true))::uuid ELSE NULL::uuid END) AND ((m.status)::text = 'active'::text) AND ((m.role)::text = 'owner'::text)))) AND ((executions.request_started_at IS NULL) OR ((executions.request_started_at >= t.created_at) AND (executions.request_started_at < t.dispatch_deadline_at))) AND ((executions.response_received_at IS NULL) OR (executions.response_received_at >= t.created_at))))))"""
    MANAGED_TASKS_INSERT = """((organization_id =
CASE
    WHEN ((length(current_setting('jous.organization_id'::text, true)) = 36) AND (current_setting('jous.organization_id'::text, true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)) THEN (current_setting('jous.organization_id'::text, true))::uuid
    ELSE NULL::uuid
END) AND jous_security.organization_is_active(organization_id) AND (EXISTS ( SELECT 1
   FROM public.users u
  WHERE ((u.id =
        CASE
            WHEN ((length(current_setting('jous.user_id'::text, true)) = 36) AND (current_setting('jous.user_id'::text, true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)) THEN (current_setting('jous.user_id'::text, true))::uuid
            ELSE NULL::uuid
        END) AND ((u.status)::text = 'active'::text)))) AND (EXISTS ( SELECT 1
   FROM public.organization_memberships m
  WHERE ((m.organization_id = tasks.organization_id) AND (m.user_id =
        CASE
            WHEN ((length(current_setting('jous.user_id'::text, true)) = 36) AND (current_setting('jous.user_id'::text, true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)) THEN (current_setting('jous.user_id'::text, true))::uuid
            ELSE NULL::uuid
        END) AND ((m.status)::text = 'active'::text) AND ((m.role)::text = ANY ((ARRAY['owner'::character varying, 'member'::character varying])::text[]))))) AND (EXISTS ( SELECT 1
   FROM public.projects p
  WHERE ((p.organization_id = tasks.organization_id) AND (p.id = tasks.project_id) AND ((p.status)::text = 'active'::text)))) AND (EXISTS ( SELECT 1
   FROM public.organization_memberships m
  WHERE ((m.organization_id = tasks.organization_id) AND (m.user_id =
        CASE
            WHEN ((length(current_setting('jous.user_id'::text, true)) = 36) AND (current_setting('jous.user_id'::text, true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)) THEN (current_setting('jous.user_id'::text, true))::uuid
            ELSE NULL::uuid
        END) AND ((m.status)::text = 'active'::text) AND ((m.role)::text = 'owner'::text)))) AND (actor_user_id =
CASE
    WHEN ((length(current_setting('jous.user_id'::text, true)) = 36) AND (current_setting('jous.user_id'::text, true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)) THEN (current_setting('jous.user_id'::text, true))::uuid
    ELSE NULL::uuid
END))"""
    MANAGED_TASKS_SELECT = """((organization_id =
CASE
    WHEN ((length(current_setting('jous.organization_id'::text, true)) = 36) AND (current_setting('jous.organization_id'::text, true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)) THEN (current_setting('jous.organization_id'::text, true))::uuid
    ELSE NULL::uuid
END) AND jous_security.organization_is_active(organization_id) AND (EXISTS ( SELECT 1
   FROM public.users u
  WHERE ((u.id =
        CASE
            WHEN ((length(current_setting('jous.user_id'::text, true)) = 36) AND (current_setting('jous.user_id'::text, true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)) THEN (current_setting('jous.user_id'::text, true))::uuid
            ELSE NULL::uuid
        END) AND ((u.status)::text = 'active'::text)))) AND (EXISTS ( SELECT 1
   FROM public.organization_memberships m
  WHERE ((m.organization_id = tasks.organization_id) AND (m.user_id =
        CASE
            WHEN ((length(current_setting('jous.user_id'::text, true)) = 36) AND (current_setting('jous.user_id'::text, true) ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text)) THEN (current_setting('jous.user_id'::text, true))::uuid
            ELSE NULL::uuid
        END) AND ((m.status)::text = 'active'::text) AND ((m.role)::text = ANY ((ARRAY['owner'::character varying, 'member'::character varying])::text[]))))) AND (EXISTS ( SELECT 1
   FROM public.projects p
  WHERE ((p.organization_id = tasks.organization_id) AND (p.id = tasks.project_id) AND ((p.status)::text = 'active'::text)))))"""

    def test_exact_managed_executions_insert_and_other_source_policies(self):
        source=POLICIES['jous_executions_insert'][2]
        self.assertEqual(canonical_policy_expression(source,policy_name='jous_executions_insert'),
                         canonical_policy_expression(self.MANAGED_EXECUTIONS_INSERT,
                                                     policy_name='jous_executions_insert'))
        for name in ('jous_tasks_select','jous_tasks_insert','jous_executions_select'):
            with self.subTest(policy=name):
                self.assertIsNotNone(canonical_policy_expression(POLICIES[name][2]))

    def test_exact_managed_tasks_insert_matches_source(self):
        source=canonical_policy_expression(
            POLICIES['jous_tasks_insert'][2],policy_name='jous_tasks_insert')
        managed=canonical_policy_expression(
            self.MANAGED_TASKS_INSERT,policy_name='jous_tasks_insert')
        self.assertEqual(source,managed)

    def test_exact_managed_tasks_select_matches_source(self):
        source=canonical_policy_expression(
            POLICIES['jous_tasks_select'][2],policy_name='jous_tasks_select')
        managed=canonical_policy_expression(
            self.MANAGED_TASKS_SELECT,policy_name='jous_tasks_select')
        self.assertEqual(source,managed)

    def test_tasks_select_target_qualification_is_position_and_policy_bound(self):
        source=POLICIES['jous_tasks_select'][2]
        expected=canonical_policy_expression(source,policy_name='jous_tasks_select')
        mutations=(
            self.MANAGED_TASKS_SELECT.replace("((organization_id =", "((project_id =",1),
            self.MANAGED_TASKS_SELECT.replace("organization_id =\nCASE", "projects.organization_id =\nCASE",1),
            self.MANAGED_TASKS_SELECT.replace(
                "jous_security.organization_is_active(organization_id)",
                "jous_security.organization_is_active(project_id)",1),
            self.MANAGED_TASKS_SELECT.replace(
                "jous_security.organization_is_active(organization_id) AND",
                "organization_id = organization_id AND",1),
            self.MANAGED_TASKS_SELECT.replace("m.organization_id = tasks.organization_id",
                                              "m.organization_id = organization_id",1),
            self.MANAGED_TASKS_SELECT.replace("p.organization_id = tasks.organization_id",
                                              "p.organization_id = projects.organization_id",1),
            self.MANAGED_TASKS_SELECT.replace("p.id = tasks.project_id", "p.id = tasks.organization_id",1),
        )
        for index,candidate in enumerate(mutations):
            with self.subTest(index=index):
                try:
                    actual=canonical_policy_expression(candidate,policy_name='jous_tasks_select')
                except ValueError:
                    continue
                self.assertNotEqual(expected,actual)
        self.assertNotEqual(
            canonical_policy_expression(source,policy_name='jous_tasks_insert'),
            canonical_policy_expression(self.MANAGED_TASKS_SELECT,
                                        policy_name='jous_tasks_insert'))
        changed_source=source.replace("tasks.organization_id =", "other_relation.organization_id =",1)
        self.assertNotEqual(expected,canonical_policy_expression(
            changed_source,policy_name='jous_tasks_select'))

    def test_tasks_select_managed_semantic_mutations_fail_closed(self):
        expected=canonical_policy_expression(
            POLICIES['jous_tasks_select'][2],policy_name='jous_tasks_select')
        managed=self.MANAGED_TASKS_SELECT
        mutations=(
            managed.replace("'jous.organization_id'::text", "'jous.project_id'::text",1),
            managed.replace("'jous.user_id'::text", "'jous.other_id'::text",1),
            managed.replace("'^[0-9a-f]{8}-", "'^[0-9a-f]{7}-",1),
            managed.replace("))::uuid", "))::text",1),
            managed.replace("organization_is_active", "organization_is_enabled",1),
            managed.replace("organization_is_active(organization_id)",
                            "organization_is_active(project_id)",1),
            managed.replace("organization_is_active(organization_id) AND", "",1),
            managed.replace("public.users u", "public.projects u",1),
            managed.replace("u.id =", "u.organization_id =",1),
            managed.replace("'active'::text", "'inactive'::text",1),
            managed.replace("public.organization_memberships m", "public.users m",1),
            managed.replace("m.organization_id = tasks.organization_id",
                            "m.organization_id = tasks.project_id",1),
            managed.replace("m.user_id =", "m.organization_id =",1),
            managed.replace("m.status", "m.role",1),
            managed.replace("'owner'::character varying", "'admin'::character varying",1),
            managed.replace("'member'::character varying", "'guest'::character varying",1),
            managed.replace("'owner'::character varying, ", "",1),
            managed.replace(", 'member'::character varying", "",1),
            managed.replace("ARRAY['owner'::character varying, 'member'::character varying]",
                            "ARRAY['member'::character varying, 'owner'::character varying]",1),
            managed.replace("ARRAY['owner'::character varying, 'member'::character varying]",
                            "ARRAY['owner'::character varying, 'member'::character varying, 'guest'::character varying]",1),
            managed.replace("(m.role)::text", "(m.status)::text",1),
            managed.replace("= ANY", "<> ANY",1),
            managed.replace("ANY", "ALL",1),
            managed.replace("character varying", "text",1),
            managed.replace("::text[]", "::varchar[]",1),
            managed.replace("::text[]", "",1),
            managed.replace("public.projects p", "public.users p",1),
            managed.replace("p.organization_id = tasks.organization_id",
                            "p.organization_id = tasks.project_id",1),
            managed.replace("p.id = tasks.project_id", "p.id = tasks.organization_id",1),
            managed.replace("p.status", "p.role",1),
            managed.replace("AND (EXISTS ( SELECT 1\n   FROM public.projects p", "AND TRUE",1),
            managed.replace(" AND ", " OR ",1),
            managed+" trailing",
            managed[:-1],
        )
        for index,candidate in enumerate(mutations):
            with self.subTest(index=index):
                try:
                    actual=canonical_policy_expression(candidate,policy_name='jous_tasks_select')
                except ValueError:
                    continue
                self.assertNotEqual(expected,actual)

    def test_tasks_insert_target_qualification_is_position_and_policy_bound(self):
        expected=canonical_policy_expression(
            POLICIES['jous_tasks_insert'][2],policy_name='jous_tasks_insert')
        mutations=(
            self.MANAGED_TASKS_INSERT.replace("((organization_id =", "((project_id =",1),
            self.MANAGED_TASKS_INSERT.replace("jous_security.organization_is_active(organization_id)",
                                              "jous_security.organization_is_active(project_id)",1),
            self.MANAGED_TASKS_INSERT.replace("(actor_user_id =", "(project_id =",1),
            self.MANAGED_TASKS_INSERT.replace("tasks.organization_id", "projects.organization_id",1),
            self.MANAGED_TASKS_INSERT.replace("m.organization_id = tasks.organization_id",
                                              "m.organization_id = organization_id",1),
        )
        for index,candidate in enumerate(mutations):
            with self.subTest(index=index):
                try:
                    actual=canonical_policy_expression(candidate,policy_name='jous_tasks_insert')
                except ValueError:
                    continue
                self.assertNotEqual(expected,actual)
        self.assertNotEqual(
            canonical_policy_expression(POLICIES['jous_tasks_insert'][2],
                                        policy_name='jous_tasks_select'),
            canonical_policy_expression(self.MANAGED_TASKS_INSERT,
                                        policy_name='jous_tasks_select'))

    def test_tasks_insert_managed_semantic_mutations_fail_closed(self):
        expected=canonical_policy_expression(
            POLICIES['jous_tasks_insert'][2],policy_name='jous_tasks_insert')
        managed=self.MANAGED_TASKS_INSERT
        mutations=(
            managed.replace("'jous.organization_id'::text", "'jous.project_id'::text",1),
            managed.replace("'jous.user_id'::text", "'jous.other_id'::text",1),
            managed.replace("{8}-[0-9a-f]", "{7}-[0-9a-f]",1),
            managed.replace("))::uuid", "))::text",1),
            managed.replace("organization_is_active", "organization_is_enabled",1),
            managed.replace("organization_is_active(organization_id)",
                            "organization_is_active(project_id)",1),
            managed.replace("public.users u", "public.projects u",1),
            managed.replace("public.organization_memberships m", "public.users m",1),
            managed.replace("public.projects p", "public.users p",1),
            managed.replace("'active'::text", "'inactive'::text",1),
            managed.replace("'owner'::character varying", "'admin'::character varying",1),
            managed.replace("'member'::character varying", "'guest'::character varying",1),
            managed.replace("'owner'::character varying, ", "",1),
            managed.replace(", 'member'::character varying", "",1),
            managed.replace("'member'::character varying", "'owner'::character varying",1),
            managed.replace("ARRAY['owner'::character varying, 'member'::character varying]",
                            "ARRAY['member'::character varying, 'owner'::character varying]",1),
            managed.replace("ARRAY['owner'::character varying, 'member'::character varying]",
                            "ARRAY['owner'::character varying, 'member'::character varying, 'guest'::character varying]",1),
            managed.replace("(m.role)::text", "(m.status)::text",1),
            managed.replace("= ANY", "<> ANY",1),
            managed.replace("ANY", "ALL",1),
            managed.replace("character varying", "text",1),
            managed.replace("::text[]", "::varchar[]",1),
            managed.replace("::text[]", "",1),
            managed.replace("m.organization_id = tasks.organization_id",
                            "m.organization_id = tasks.project_id",1),
            managed.replace("m.user_id =", "m.organization_id =",1),
            managed.replace("p.id = tasks.project_id", "p.id = tasks.organization_id",1),
            managed.replace("(actor_user_id =", "(project_id =",1),
            managed.replace("EXISTS ( SELECT 1\n   FROM public.projects p", "TRUE",1),
            managed.replace(" AND ", " OR ",1),
            managed+" trailing",
            managed[:-1],
        )
        for index,candidate in enumerate(mutations):
            with self.subTest(index=index):
                try:
                    actual=canonical_policy_expression(candidate,policy_name='jous_tasks_insert')
                except ValueError:
                    continue
                self.assertNotEqual(expected,actual)

    async def test_managed_policy_ast_is_used_and_metadata_stays_exact(self):
        connection=ValidatorTests().connection()
        responses=list(connection.execute.side_effect)
        rows=responses[3].all()
        for index,row in enumerate(rows):
            if row[1]=='jous_executions_insert':
                rows[index]=row[:6]+(self.MANAGED_EXECUTIONS_INSERT,)
                break
        else:raise AssertionError('executions insert policy fixture missing')
        responses[3]=SimpleNamespace(all=lambda:rows)
        connection.execute.side_effect=responses
        await ValidatorTests().run_validation(connection)

        connection=ValidatorTests().connection()
        responses=list(connection.execute.side_effect)
        rows=responses[3].all()
        for index,row in enumerate(rows):
            if row[1]=='jous_executions_insert':
                rows[index]=(row[0],row[1],row[2],row[3],['public'],row[5],row[6])
                break
        responses[3]=SimpleNamespace(all=lambda:rows)
        connection.execute.side_effect=responses
        with self.assertRaises(DatabaseUnavailable):
            await ValidatorTests().run_validation(connection)

    async def test_exact_managed_tasks_insert_is_used_by_product_validator(self):
        connection=ValidatorTests().connection()
        responses=list(connection.execute.side_effect)
        rows=responses[3].all()
        for index,row in enumerate(rows):
            if row[1]=='jous_tasks_insert':
                rows[index]=row[:6]+(self.MANAGED_TASKS_INSERT,)
                break
        else:raise AssertionError('tasks insert policy fixture missing')
        responses[3]=SimpleNamespace(all=lambda:rows)
        connection.execute.side_effect=responses
        await ValidatorTests().run_validation(connection)

    async def test_exact_managed_tasks_select_is_using_only_in_product_validator(self):
        connection=ValidatorTests().connection()
        responses=list(connection.execute.side_effect)
        rows=responses[3].all()
        for index,row in enumerate(rows):
            if row[1]=='jous_tasks_select':
                rows[index]=(row[0],row[1],row[2],row[3],row[4],
                             self.MANAGED_TASKS_SELECT,None)
                break
        else:raise AssertionError('tasks select policy fixture missing')
        responses[3]=SimpleNamespace(all=lambda:rows)
        connection.execute.side_effect=responses
        await ValidatorTests().run_validation(connection)

        for field in ('table','command','permissive','roles'):
            connection=ValidatorTests().connection()
            responses=list(connection.execute.side_effect)
            rows=responses[3].all()
            for index,row in enumerate(rows):
                if row[1]=='jous_tasks_select':
                    values=list(row)
                    if field=='table':values[0]='executions'
                    elif field=='command':values[2]='a'
                    elif field=='permissive':values[3]=False
                    else:values[4]=['public']
                    rows[index]=tuple(values)
                    break
            responses[3]=SimpleNamespace(all=lambda:rows)
            connection.execute.side_effect=responses
            with self.subTest(field=field),self.assertRaises(DatabaseUnavailable):
                await ValidatorTests().run_validation(connection)

        for using,check in ((None,None),(None,self.MANAGED_TASKS_SELECT)):
            connection=ValidatorTests().connection()
            responses=list(connection.execute.side_effect)
            rows=responses[3].all()
            for index,row in enumerate(rows):
                if row[1]=='jous_tasks_select':
                    rows[index]=(row[0],row[1],row[2],row[3],row[4],using,check)
                    break
            responses[3]=SimpleNamespace(all=lambda:rows)
            connection.execute.side_effect=responses
            with self.subTest(using=using,check_present=check is not None),self.assertRaises(DatabaseUnavailable):
                await ValidatorTests().run_validation(connection)

    async def test_policy_metadata_and_using_check_placement_remain_exact(self):
        for field in ('table','command','permissive','roles','placement'):
            connection=ValidatorTests().connection()
            responses=list(connection.execute.side_effect)
            rows=responses[3].all()
            for index,row in enumerate(rows):
                if row[1]!='jous_executions_insert':continue
                values=list(row)
                if field=='table':values[0]='tasks'
                elif field=='command':values[2]='r'
                elif field=='permissive':values[3]=False
                elif field=='roles':values[4]=['public']
                else:values[5],values[6]=values[6],values[5]
                rows[index]=tuple(values)
                break
            responses[3]=SimpleNamespace(all=lambda:rows)
            connection.execute.side_effect=responses
            with self.subTest(field=field),self.assertRaises(DatabaseUnavailable):
                await ValidatorTests().run_validation(connection)

        # A malformed expression in a clause that should be absent must not
        # collapse to None and appear equal to the expected NULL slot.
        connection=ValidatorTests().connection()
        responses=list(connection.execute.side_effect)
        rows=responses[3].all()
        for index,row in enumerate(rows):
            if row[1]=='jous_tasks_select':
                rows[index]=row[:6]+('unsupported syntax',)
                break
        responses[3]=SimpleNamespace(all=lambda:rows)
        connection.execute.side_effect=responses
        with self.assertRaises(DatabaseUnavailable):
            await ValidatorTests().run_validation(connection)

    def test_security_semantic_mutations_fail_closed(self):
        original=self.MANAGED_EXECUTIONS_INSERT
        expected=canonical_policy_expression(original,policy_name='jous_executions_insert')
        self.assertIsNotNone(expected)
        mutations=(
            original.replace("'jous.user_id'::text", "'jous.other_id'::text",1),
            original.replace("'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text",
                             "'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{13}$'::text",1),
            original.replace("current_setting('jous.user_id'::text, true) ~", "current_setting('jous.user_id'::text, true) !~",1),
            original.replace("'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'::text",
                             "'not-a-uuid'::text",1),
            original.replace("))::uuid ELSE NULL::uuid", ")) ELSE NULL::uuid",1),
            original.replace("))::uuid ELSE NULL::uuid", "))::text ELSE NULL::uuid",1),
            original.replace("= 36", "= 35",1),
            original.replace("ELSE NULL::uuid END", "ELSE '00000000-0000-0000-0000-000000000000'::uuid END",1),
            original.replace("'active'::text", "'inactive'::text",1),
            original.replace("'owner'::text", "'member'::text",1),
            original.replace("public.organization_memberships m", "public.users m",1),
            original.replace("public.tasks t", "public.projects t",1),
            original.replace("public.tasks t", "public.tasks x",1).replace("t.","x."),
            original.replace("executions.task_id = t.id", "executions.task_id = t.organization_id",1),
            original.replace(" AND (executions.dispatch_claim_id = t.dispatch_claim_id)", "",1),
            original.replace("executions.organization_id = t.organization_id", "executions.organization_id = t.id",1),
            original.replace("executions.project_id = t.project_id", "executions.project_id = t.id",1),
            original.replace("executions.actor_user_id = t.actor_user_id", "executions.actor_user_id = t.id",1),
            original.replace("executions.dispatch_claim_id = t.dispatch_claim_id", "executions.dispatch_claim_id = t.id",1),
            original.replace("executions.request_started_at IS NULL", "executions.request_started_at IS NOT NULL",1),
            original.replace("executions.response_received_at IS NULL", "executions.response_received_at IS NOT NULL",1),
            original.replace("t.created_at", "t.updated_at",1),
            original.replace("t.dispatch_deadline_at", "t.created_at",1),
            original.replace("request_started_at < t.dispatch_deadline_at", "request_started_at <= t.dispatch_deadline_at",1),
            original.replace("request_started_at >= t.created_at", "request_started_at > t.created_at",1),
            original.replace(" AND ", " OR ",1),
            original.replace("AND ((executions.response_received_at", "AND (executions.task_id IS NOT NULL) AND ((executions.response_received_at",1),
            original.replace("AND (EXISTS ( SELECT 1 FROM public.organization_memberships", "AND TRUE",1),
            original+' trailing',
            original[:-1],
        )
        for index,candidate in enumerate(mutations):
            with self.subTest(index=index,candidate=candidate[:100]):
                try:
                    actual=canonical_policy_expression(
                        candidate,policy_name='jous_executions_insert')
                except ValueError:
                    continue
                self.assertNotEqual(actual,expected)

    def test_present_unsupported_policy_expression_never_means_absent_clause(self):
        for expression in ('unsupported syntax', 'TRUE @@@', "EXISTS (SELECT 1"):
            with self.subTest(expression=expression),self.assertRaises(ValueError):
                canonical_policy_expression(expression,policy_name='jous_tasks_insert')
        with self.assertRaises(ValueError):
            canonical_policy_expression(None,policy_name='jous_tasks_insert')

    def test_tasks_insert_role_in_matches_only_proven_typed_any_shape(self):
        source="m.role IN ('owner','member')"
        managed="((m.role)::text = ANY ((ARRAY['owner'::character varying, 'member'::character varying])::text[]))"
        expected=canonical_policy_expression(source,policy_name='jous_tasks_insert')
        self.assertEqual(expected,canonical_policy_expression(
            managed,policy_name='jous_tasks_insert'))
        source_policy=canonical_policy_expression(
            POLICIES['jous_tasks_insert'][2],policy_name='jous_tasks_insert')
        def contains_role_members(node):
            return (isinstance(node,tuple) and
                    (node==expected or any(contains_role_members(child)
                                           for child in node if isinstance(child,tuple))))
        self.assertTrue(contains_role_members(source_policy))

        mutations=(
            managed.replace("'owner'::character varying", "'member'::character varying",1),
            managed.replace("'member'::character varying", "'owner'::character varying",1),
            managed.replace(", 'member'::character varying", "",1),
            managed.replace("'member'::character varying", "'other'::character varying",1),
            managed.replace("ARRAY['owner'::character varying, 'member'::character varying]",
                            "ARRAY['member'::character varying, 'owner'::character varying]",1),
            managed.replace("ARRAY['owner'::character varying, 'member'::character varying]",
                            "ARRAY['owner'::character varying, 'member'::character varying, 'guest'::character varying]",1),
            managed.replace("m.role", "m.status",1),
            managed.replace(" = ANY ", " <> ANY ",1),
            managed.replace("ANY", "ALL",1),
            managed.replace("character varying", "text",1),
            managed.replace("character varying", "varchar",1),
            managed.replace("::text[]", "::varchar[]",1),
            managed.replace("::text[]", "",1),
        )
        for index,candidate in enumerate(mutations):
            with self.subTest(index=index):
                try:
                    actual=canonical_policy_expression(candidate,policy_name='jous_tasks_insert')
                except ValueError:
                    continue
                self.assertNotEqual(expected,actual)


class CheckGroupingCanonicalizationTests(unittest.IsolatedAsyncioTestCase):
    MANAGED_TASK_JSON_SHAPES = """((jsonb_typeof(context_package) = 'object'::text) AND (context_package ? 'schema_version'::text) AND ((context_package -> 'schema_version'::text) = '1'::jsonb) AND (jsonb_typeof(request_parameters) = 'object'::text) AND (request_parameters ? 'schema_version'::text) AND ((request_parameters -> 'schema_version'::text) = '1'::jsonb) AND (jsonb_typeof(token_bound_evidence) = 'object'::text) AND (token_bound_evidence ? 'schema_version'::text) AND ((token_bound_evidence -> 'schema_version'::text) = '1'::jsonb) AND (context_package ?& ARRAY['snapshot'::text, 'instruction'::text, 'provenance'::text]) AND (jsonb_typeof((context_package -> 'snapshot'::text)) = 'object'::text) AND (jsonb_typeof((context_package -> 'instruction'::text)) = 'object'::text) AND (jsonb_typeof((context_package -> 'provenance'::text)) = 'object'::text) AND (request_parameters ?& ARRAY['route_id'::text, 'catalog_digest'::text, 'route_snapshot'::text, 'limits'::text, 'execution'::text]) AND (jsonb_typeof((request_parameters -> 'route_id'::text)) = 'string'::text) AND (jsonb_typeof((request_parameters -> 'catalog_digest'::text)) = 'string'::text) AND (jsonb_typeof((request_parameters -> 'route_snapshot'::text)) = 'object'::text) AND (jsonb_typeof((request_parameters -> 'limits'::text)) = 'object'::text) AND (jsonb_typeof((request_parameters -> 'execution'::text)) = 'object'::text) AND (token_bound_evidence ?& ARRAY['asset_revision'::text, 'asset_hashes'::text, 'method'::text, 'template_branch'::text, 'input_token_upper_bound'::text, 'context_capacity'::text, 'output_allowance'::text, 'safety_margin'::text, 'hosted_authority_state'::text]) AND (jsonb_typeof((token_bound_evidence -> 'asset_hashes'::text)) = 'object'::text) AND (jsonb_typeof((token_bound_evidence -> 'context_capacity'::text)) = 'number'::text) AND (jsonb_typeof((token_bound_evidence -> 'method'::text)) = 'string'::text) AND (jsonb_typeof((token_bound_evidence -> 'hosted_authority_state'::text)) = 'string'::text))"""

    MANAGED_IDENTIFIER_BOUNDS_RENDERING = (
        '(((reported_model_id IS NULL) OR ((length(btrim(reported_model_id)) > 0) AND '
        '(octet_length(reported_model_id) <= 255))) AND ((reported_provider_id IS NULL) OR '
        '((length(btrim(reported_provider_id)) > 0) AND (octet_length(reported_provider_id) <= 255))) '
        'AND ((provider_request_id IS NULL) OR ((length(btrim(provider_request_id)) > 0) AND '
        '(octet_length(provider_request_id) <= 255))) AND ((provider_response_id IS NULL) OR '
        '((length(btrim(provider_response_id)) > 0) AND (octet_length(provider_response_id) <= 255))) '
        'AND ((finish_reason IS NULL) OR ((length(btrim(finish_reason)) > 0) AND '
        '(octet_length(finish_reason) <= 255))))'
    )
    EXPECTED_IDENTIFIER_BOUNDS_RENDERING = (
        '(reported_model_id IS NULL OR (length(btrim(reported_model_id)) > 0 AND '
        'octet_length(reported_model_id) <= 255)) AND (reported_provider_id IS NULL OR '
        '(length(btrim(reported_provider_id)) > 0 AND octet_length(reported_provider_id) <= 255)) '
        'AND (provider_request_id IS NULL OR (length(btrim(provider_request_id)) > 0 AND '
        'octet_length(provider_request_id) <= 255)) AND (provider_response_id IS NULL OR '
        '(length(btrim(provider_response_id)) > 0 AND octet_length(provider_response_id) <= 255)) '
        'AND (finish_reason IS NULL OR (length(btrim(finish_reason)) > 0 AND '
        'octet_length(finish_reason) <= 255))'
    )
    # Exact managed pg_get_expr AST captured by the restricted runtime
    # diagnostic. Raw managed SQL was not retained, so the regression is at
    # the AST transformation boundary rather than a synthesized SQL string.
    MANAGED_OUTCOME_AST = ast.literal_eval(r"""('AND', (('OR', (('AND', (('ATOM', (('word', 'status'), ('operator', '='), ('literal', "'succeeded'"), ('operator', '::'), ('word', 'text'))), ('ATOM', (('word', 'response_text'), ('word', 'IS'), ('word', 'NOT'), ('word', 'NULL'))), ('ATOM', (('word', 'error_code'), ('word', 'IS'), ('word', 'NULL'))))), ('AND', (('ATOM', (('word', 'status'), ('operator', '='), ('literal', "'refused'"), ('operator', '::'), ('word', 'text'))), ('ATOM', (('word', 'error_code'), ('word', 'IS'), ('word', 'NULL'))))), ('AND', (('ATOM', (('word', 'status'), ('operator', '='), ('literal', "'known_error'"), ('operator', '::'), ('word', 'text'))), ('ATOM', (('word', 'error_code'), ('word', 'IS'), ('word', 'NOT'), ('word', 'NULL'))), ('ATOM', (('word', 'error_code'), ('operator', '='), ('word', 'ANY'), ('punctuation', '('), ('word', 'ARRAY'), ('punctuation', '['), ('literal', "'not_dispatched'"), ('operator', '::'), ('word', 'text'), ('punctuation', ','), ('literal', "'supplier_rejected'"), ('operator', '::'), ('word', 'text'), ('punctuation', ','), ('literal', "'rate_limited'"), ('operator', '::'), ('word', 'text'), ('punctuation', ','), ('literal', "'malformed_response'"), ('operator', '::'), ('word', 'text'), ('punctuation', ','), ('literal', "'response_too_large'"), ('operator', '::'), ('word', 'text'), ('punctuation', ','), ('literal', "'metadata_inconsistent'"), ('operator', '::'), ('word', 'text'), ('punctuation', ']'), ('punctuation', ')'))), ('ATOM', (('word', 'response_text'), ('word', 'IS'), ('word', 'NULL'))))), ('AND', (('ATOM', (('word', 'status'), ('operator', '='), ('literal', "'unknown'"), ('operator', '::'), ('word', 'text'))), ('ATOM', (('word', 'error_code'), ('word', 'IS'), ('word', 'NOT'), ('word', 'NULL'))), ('ATOM', (('word', 'error_code'), ('operator', '='), ('word', 'ANY'), ('punctuation', '('), ('word', 'ARRAY'), ('punctuation', '['), ('literal', "'transport_ambiguous'"), ('operator', '::'), ('word', 'text'), ('punctuation', ','), ('literal', "'provider_timeout'"), ('operator', '::'), ('word', 'text'), ('punctuation', ']'), ('punctuation', ')'))), ('ATOM', (('word', 'response_text'), ('word', 'IS'), ('word', 'NULL'))))))), ('OR', (('ATOM', (('word', 'error_code'), ('word', 'IS'), ('word', 'DISTINCT'), ('word', 'FROM'), ('literal', "'not_dispatched'"), ('operator', '::'), ('word', 'text'))), ('AND', (('ATOM', (('word', 'request_started_at'), ('word', 'IS'), ('word', 'NULL'))), ('ATOM', (('word', 'response_received_at'), ('word', 'IS'), ('word', 'NULL'))), ('ATOM', (('word', 'reported_model_id'), ('word', 'IS'), ('word', 'NULL'))), ('ATOM', (('word', 'reported_provider_id'), ('word', 'IS'), ('word', 'NULL'))), ('ATOM', (('word', 'provider_request_id'), ('word', 'IS'), ('word', 'NULL'))), ('ATOM', (('word', 'provider_response_id'), ('word', 'IS'), ('word', 'NULL'))), ('ATOM', (('word', 'finish_reason'), ('word', 'IS'), ('word', 'NULL'))), ('ATOM', (('word', 'usage'), ('word', 'IS'), ('word', 'NULL'))), ('ATOM', (('word', 'usage_status'), ('operator', '='), ('literal', "'unavailable'"), ('operator', '::'), ('word', 'text')))))))))""")

    def connection_with_check(self, table, name, sql):
        connection=ValidatorTests().connection()
        responses=list(connection.execute.side_effect)
        constraints=responses[1].all()
        for i,row in enumerate(constraints):
            if row[0:2]==(table,name):
                constraints[i]=row[:12]+(sql,)
                break
        else:
            raise AssertionError(f'{table}.{name} fixture missing')
        responses[1]=SimpleNamespace(all=lambda:constraints)
        connection.execute.side_effect=responses
        return connection

    @staticmethod
    def mutate_first_atom(node, predicate, mutate):
        if node[0]=='ATOM' and predicate(node[1]):
            return ('ATOM',mutate(node[1]))
        if node[0] in ('AND','OR'):
            children=list(node[1])
            for i,child in enumerate(children):
                changed=CheckGroupingCanonicalizationTests.mutate_first_atom(
                    child,predicate,mutate)
                if changed!=child:
                    children[i]=changed
                    return node[0],tuple(children)
        return node

    @staticmethod
    def replace_token(tokens, old, new):
        values=list(tokens)
        index=values.index(old)
        values[index]=new
        return tuple(values)

    async def run_validation(self, connection):
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def scope(c): yield
        with patch.object(v,'validate_product_foundation',new_callable=AsyncMock),patch.object(v,'catalog_resolution',scope):
            await v.validate_product_runtime(connection)

    def test_exact_managed_json_shapes_sql_matches_source_and_mutations_fail(self):
        source=TASK_CHECKS['ck_tasks_json_shapes']
        expected=v.canonical_check_expression(source,'tasks','ck_tasks_json_shapes')
        actual=v.canonical_check_expression(
            self.MANAGED_TASK_JSON_SHAPES,'tasks','ck_tasks_json_shapes')
        self.assertIsNotNone(expected)
        self.assertEqual(actual,expected)

        mutations=(
            self.MANAGED_TASK_JSON_SHAPES.replace("'schema_version'::text", "'schema_ver'::text",1),
            self.MANAGED_TASK_JSON_SHAPES.replace("'provenance'::text]", "]",1),
            self.MANAGED_TASK_JSON_SHAPES.replace("'provenance'::text]", "'other'::text]",1),
            self.MANAGED_TASK_JSON_SHAPES.replace(
                "'snapshot'::text, 'instruction'::text, 'provenance'::text",
                "'provenance'::text, 'instruction'::text, 'snapshot'::text",1),
            self.MANAGED_TASK_JSON_SHAPES.replace(
                "context_package ? 'schema_version'::text",
                "context_package @> 'schema_version'::text",1),
            self.MANAGED_TASK_JSON_SHAPES.replace(
                "context_package ?& ARRAY", "context_package ? ARRAY",1),
            self.MANAGED_TASK_JSON_SHAPES.replace(
                "context_package -> 'schema_version'::text",
                "context_package ->> 'schema_version'::text",1),
            self.MANAGED_TASK_JSON_SHAPES.replace('jsonb_typeof(context_package)',
                                                   'json_typeof(context_package)',1),
            self.MANAGED_TASK_JSON_SHAPES.replace("'object'::text", "'array'::text",1),
            self.MANAGED_TASK_JSON_SHAPES.replace("'object'::text", "'object'::varchar",1),
            self.MANAGED_TASK_JSON_SHAPES.replace("'string'::text", "'boolean'::text",1),
            self.MANAGED_TASK_JSON_SHAPES.replace("'number'::text", "'integer'::text",1),
            self.MANAGED_TASK_JSON_SHAPES.replace("'1'::jsonb", "'2'::jsonb",1),
            self.MANAGED_TASK_JSON_SHAPES.replace("'1'::jsonb", "'1'",1),
            self.MANAGED_TASK_JSON_SHAPES.replace("'1'::jsonb", "'1'::text",1),
            self.MANAGED_TASK_JSON_SHAPES.replace(
                "'schema_version'::text", "'schema_version'::varchar",1),
            self.MANAGED_TASK_JSON_SHAPES.replace(
                "'snapshot'::text", "'snapshot'::varchar",1),
            self.MANAGED_TASK_JSON_SHAPES.replace('context_package ?', 'other_package ?',1),
            self.MANAGED_TASK_JSON_SHAPES.replace(' AND ', ' OR ',1),
            self.MANAGED_TASK_JSON_SHAPES + ' AND',
        )
        for candidate in mutations:
            with self.subTest(candidate=candidate[:100]):
                self.assertNotEqual(v.canonical_check_expression(
                    candidate,'tasks','ck_tasks_json_shapes'),expected)

    def test_managed_identifier_bounds_grouping_matches_expected(self):
        expected=v.expected_constraints()[('executions','ck_executions_identifier_bounds')][-1]
        model_constraint=next(c for c in executions.constraints
                              if c.name=='ck_executions_identifier_bounds')
        self.assertEqual(str(model_constraint.sqltext),self.EXPECTED_IDENTIFIER_BOUNDS_RENDERING)
        self.assertEqual(v.canonical_check_expression(
            self.EXPECTED_IDENTIFIER_BOUNDS_RENDERING,
            'executions','ck_executions_identifier_bounds'),expected)
        actual=v.canonical_check_expression(
            self.MANAGED_IDENTIFIER_BOUNDS_RENDERING,
            'executions','ck_executions_identifier_bounds')
        self.assertEqual(actual,expected)

    def test_exact_managed_usage_bounds_ast_matches_model_and_preserves_cast(self):
        expected_ast=('OR',(
            ('ATOM',(('word','usage'),('word','IS'),('word','NULL'))),
            ('ATOM',(('word','octet_length'),('punctuation','('),
                     ('word','usage'),('operator','::'),('word','text'),
                     ('punctuation',')'),('operator','<='),('number','32768')))))
        managed_ast=('OR',(
            ('ATOM',(('word','usage'),('word','IS'),('word','NULL'))),
            ('ATOM',(('word','octet_length'),('punctuation','('),
                     ('punctuation','('),('word','usage'),('punctuation',')'),
                     ('operator','::'),('word','text'),('punctuation',')'),
                     ('operator','<='),('number','32768')))))
        expected_full=('c',False,False,True,(),None,None,(),' ',' ',expected_ast)
        managed_full=('c',False,False,True,(),None,None,(),' ',' ',managed_ast)
        self.assertEqual(v.canonicalize_check_ast(managed_full[-1]),
                         v.canonicalize_check_ast(expected_full[-1]))

        # AST token vectors are the exact observed catalog/model evidence;
        # these mutations each change one semantic component only.
        def mutate_comparison(fn):
            comparison_tokens=expected_ast[1][1][1]
            return ('OR',(expected_ast[1][0],('ATOM',fn(comparison_tokens))))
        mutations=(
            lambda:mutate_comparison(lambda tokens:tuple(
                ('word','other_usage') if t==('word','usage') else t for t in tokens)),
            lambda:mutate_comparison(lambda tokens:tuple(
                ('word','jsonb') if t==('word','text') else t for t in tokens)),
            lambda:mutate_comparison(lambda tokens:tuple(
                t for t in tokens if t not in (('operator','::'),('word','text')))),
            lambda:mutate_comparison(lambda tokens:tuple(
                ('number','32769') if t==('number','32768') else t for t in tokens)),
            lambda:mutate_comparison(lambda tokens:tuple(
                ('operator','<') if t==('operator','<=') else t for t in tokens)),
            lambda:('OR',(('ATOM',(('word','usage'),('word','IS'),
                                  ('word','NOT'),('word','NULL'))),expected_ast[1][1])),
        )
        expected=v.canonicalize_check_ast(expected_ast)
        self.assertIsNotNone(expected)
        for mutate in mutations:
            with self.subTest(candidate=mutate()):
                self.assertNotEqual(v.canonicalize_check_ast(mutate()),expected)

    def test_exact_managed_usage_shape_ast_and_function_literal_cast_negatives(self):
        usage_null=('ATOM',(('word','usage'),('word','IS'),('word','NULL')))
        expected_function=('ATOM',(('word','jsonb_typeof'),('punctuation','('),
                                    ('word','usage'),('punctuation',')'),('operator','='),
                                    ('literal',"'object'")))
        managed_function=('ATOM',(('word','jsonb_typeof'),('punctuation','('),
                                   ('word','usage'),('punctuation',')'),('operator','='),
                                   ('literal',"'object'"),('operator','::'),('word','text')))
        jsonb_value=('ATOM',(('word','usage'),('operator','<>'),('literal',"'{}'"),
                             ('operator','::'),('word','jsonb')))
        expected_ast=('OR',(usage_null,('AND',(expected_function,jsonb_value))))
        managed_ast=('OR',(usage_null,('AND',(managed_function,jsonb_value))))
        # These are the supplied exact parsed catalog/model expressions.
        expected_full=('c',False,False,True,(),None,None,(),' ',' ',expected_ast)
        managed_full=('c',False,False,True,(),None,None,(),' ',' ',managed_ast)
        expected=v.canonicalize_check_ast(expected_full[-1])
        self.assertEqual(v.canonicalize_check_ast(managed_full[-1]),expected)

        def mutate_atom(node,predicate,mutation):
            kind,value=node
            if kind=='ATOM' and predicate(value):
                return ('ATOM',mutation(value))
            if kind in ('AND','OR'):
                for i,child in enumerate(value):
                    changed=mutate_atom(child,predicate,mutation)
                    if changed!=child:
                        children=list(value);children[i]=changed
                        return kind,tuple(children)
            return node

        function_compare=lambda tokens: ('word','jsonb_typeof') in tokens
        usage_null=lambda tokens: tokens[:3]==(('word','usage'),('word','IS'),('word','NULL'))
        jsonb_compare=lambda tokens: ('word','jsonb') in tokens and ('operator','<>') in tokens
        candidates=[]
        candidates.append(mutate_atom(managed_ast,function_compare,lambda t:tuple(
            ('literal',"'array'") if x==('literal',"'object'") else x for x in t)))
        candidates.append(mutate_atom(managed_ast,function_compare,lambda t:tuple(
            ('word','other_usage') if x==('word','usage') else x for x in t)))
        candidates.append(mutate_atom(managed_ast,function_compare,lambda t:tuple(
            ('word','jsonb_type') if x==('word','jsonb_typeof') else x for x in t)))
        candidates.append(mutate_atom(managed_ast,function_compare,lambda t:tuple(
            ('word','varchar') if x==('word','text') else x for x in t)))
        candidates.append(mutate_atom(managed_ast,jsonb_compare,lambda t:tuple(
            x for x in t if x not in (('operator','::'),('word','jsonb')))))
        candidates.append(mutate_atom(managed_ast,jsonb_compare,lambda t:tuple(
            ('word','text') if x==('word','jsonb') else x for x in t)))
        candidates.append(mutate_atom(managed_ast,function_compare,lambda t:tuple(
            ('operator','<>') if x==('operator','=') else x for x in t)))
        candidates.append(mutate_atom(managed_ast,usage_null,lambda t:t[:2]+(('word','NOT'),)+t[2:]))
        for candidate in candidates:
            with self.subTest(candidate=repr(candidate)[:140]):
                self.assertNotEqual(v.canonicalize_check_ast(candidate),expected)

        self.assertNotEqual(v.canonical_check_expression("usage <> '{}'::jsonb"),
                            v.canonical_check_expression("usage <> '{}'"))
        self.assertNotEqual(v.canonical_check_expression("usage <> '{}'::jsonb"),
                            v.canonical_check_expression("usage <> '{}'::text"))
        for malformed in ('jsonb_typeof(usage = \'object\'::text',
                          'jsonb_typeof(usage,) = \'object\'::text',
                          'jsonb_typeof(usage) = \'object\'::text trailing'):
            self.assertIsNone(v.canonical_check_expression(malformed))

    def test_exact_managed_deadline_order_ast_and_interval_mutations(self):
        finite_created=('ATOM',(('word','isfinite'),('punctuation','('),
                                 ('word','created_at'),('punctuation',')')))
        finite_deadline=('ATOM',(('word','isfinite'),('punctuation','('),
                                  ('word','dispatch_deadline_at'),('punctuation',')')))
        deadline_after_created=('ATOM',(('word','dispatch_deadline_at'),
                                        ('operator','>'),('word','created_at')))
        expected_interval=('ATOM',(('word','dispatch_deadline_at'),('operator','<='),
                                   ('word','created_at'),('operator','+'),
                                   ('word','interval'),('literal',"'40 seconds'")))
        managed_interval=('ATOM',(('word','dispatch_deadline_at'),('operator','<='),
                                  ('punctuation','('),('word','created_at'),
                                  ('operator','+'),('literal',"'00:00:40'"),
                                  ('operator','::'),('word','interval'),
                                  ('punctuation',')')))
        expected_ast=('AND',(finite_created,finite_deadline,deadline_after_created,
                             expected_interval))
        managed_ast=('AND',(finite_created,finite_deadline,deadline_after_created,
                            managed_interval))
        expected_full=('c',False,False,True,(),None,None,(),' ',' ',expected_ast)
        managed_full=('c',False,False,True,(),None,None,(),' ',' ',managed_ast)
        expected=v.canonicalize_check_ast(expected_full[-1])
        self.assertEqual(v.canonicalize_check_ast(managed_full[-1]),expected)

        def mutate_atom(node,predicate,mutation):
            kind,value=node
            if kind=='ATOM' and predicate(value):return ('ATOM',mutation(value))
            if kind in ('AND','OR'):
                for i,child in enumerate(value):
                    changed=mutate_atom(child,predicate,mutation)
                    if changed!=child:
                        children=list(value);children[i]=changed
                        return kind,tuple(children)
            return node
        interval_pred=lambda tokens: ('word','dispatch_deadline_at') in tokens and ('operator','<=') in tokens
        candidates=[]
        candidates.append(mutate_atom(managed_ast,interval_pred,lambda t:tuple(
            ('literal',"'00:00:41'") if x==('literal',"'00:00:40'") else x for x in t)))
        candidates.append(mutate_atom(expected_ast,interval_pred,lambda t:tuple(
            ('literal',"'41 seconds'") if x==('literal',"'40 seconds'") else x for x in t)))
        candidates.append(mutate_atom(managed_ast,interval_pred,lambda t:tuple(
            ('word','other_created_at') if x==('word','created_at') else x for x in t)))
        candidates.append(mutate_atom(managed_ast,interval_pred,lambda t:tuple(
            ('word','other_deadline') if x==('word','dispatch_deadline_at') else x for x in t)))
        candidates.append(mutate_atom(managed_ast,interval_pred,lambda t:tuple(
            ('operator','<') if x==('operator','<=') else x for x in t)))
        candidates.append(mutate_atom(managed_ast,interval_pred,lambda t:tuple(
            ('operator','-') if x==('operator','+') else x for x in t)))
        candidates.append(mutate_atom(managed_ast,interval_pred,lambda t:tuple(
            ('word','text') if x==('word','interval') else x for x in t)))
        candidates.append(mutate_atom(managed_ast,interval_pred,lambda t:tuple(
            x for x in t if x not in (('operator','::'),('word','interval')))))
        candidates.append(mutate_atom(managed_ast,interval_pred,lambda t:tuple(
            ('literal',"'00:00:40 malformed'") if x==('literal',"'00:00:40'") else x for x in t)))
        candidates.append(mutate_atom(managed_ast,interval_pred,lambda t:t+(('operator','+'),('number','1'))))
        candidates.append(('AND',(finite_deadline,deadline_after_created,managed_interval)))
        candidates.append(mutate_atom(managed_ast,lambda t:t==finite_created[1],lambda t:tuple(
            ('word','isfinite_changed') if x==('word','isfinite') else x for x in t)))
        candidates.append(mutate_atom(managed_ast,lambda t:t==finite_deadline[1],lambda t:tuple(
            ('word','isfinite_changed') if x==('word','isfinite') else x for x in t)))
        candidates.append(mutate_atom(managed_ast,lambda t:t==deadline_after_created[1],lambda t:tuple(
            ('operator','>=') if x==('operator','>') else x for x in t)))
        candidates.append(('OR',managed_ast[1]))
        changed_boolean=('AND',(finite_created,finite_deadline,
                                ('OR',(deadline_after_created,managed_interval))))
        candidates.append(changed_boolean)
        for index,candidate in enumerate(candidates):
            with self.subTest(index=index,candidate=repr(candidate)[:150]):
                self.assertNotEqual(v.canonicalize_check_ast(candidate),expected)

    def test_simple_identifier_cast_operand_parens_are_the_only_cast_unwrap(self):
        self.assertEqual(v.canonical_check_expression('octet_length(usage::text) <= 32768'),
                         v.canonical_check_expression('octet_length((usage)::text) <= 32768'))
        unequal=(
            ('usage::text','usage::jsonb'),
            ('usage::text','other_usage::text'),
            ('usage::text','usage'),
            ('((a + b))::text','a + b::text'),
            ('((length(a)))::text','length(a)::text'),
        )
        for left,right in unequal:
            with self.subTest(left=left,right=right):
                left_ast=v.canonical_check_expression(left)
                right_ast=v.canonical_check_expression(right)
                self.assertIsNotNone(left_ast)
                self.assertIsNotNone(right_ast)
                self.assertNotEqual(left_ast,right_ast)
        self.assertIsNone(v.canonical_check_expression('octet_length((usage)::text <= 32768'))

    def test_canonicalizer_preserves_consumption_tokens_and_precedence(self):
        self.assertIsNone(v.canonical_check_expression('x = 1 AND'))
        self.assertIsNone(v.canonical_check_expression('x = 1 @ y'))
        self.assertIsNone(v.canonical_check_expression('(x = 1'))
        left=v.canonical_check_expression("x = 'a AND b' AND y::text = 'c'")
        right=v.canonical_check_expression("((x = 'a AND b')) AND ((y::text = 'c'))")
        self.assertEqual(left,right)
        self.assertNotEqual(v.canonical_check_expression("x = 'a AND b'"),
                            v.canonical_check_expression("x = 'a OR b'"))
        self.assertNotEqual(v.canonical_check_expression('x = 3'),
                            v.canonical_check_expression('x = 3::text'))
        self.assertNotEqual(v.canonical_check_expression('length(x) = 3'),
                            v.canonical_check_expression('length(x) = 3::text'))
        self.assertNotEqual(
            v.canonical_check_expression('x = 1 AND (y = 2 OR z = 3)'),
            v.canonical_check_expression('(x = 1 AND y = 2) OR z = 3'))

    def test_exact_managed_outcome_ast_matches_model_and_mutations_do_not(self):
        expected=v.canonical_check_expression(
            str(next(c for c in executions.constraints
                     if c.name=='ck_executions_outcome_shape').sqltext),
            'executions','ck_executions_outcome_shape')
        actual=v.canonicalize_check_ast(self.MANAGED_OUTCOME_AST)
        self.assertEqual(actual,expected)

        def change_atom(predicate, mutate):
            return self.mutate_first_atom(self.MANAGED_OUTCOME_AST,predicate,mutate)

        status_success=lambda tokens: ('word','status') in tokens and ('literal',"'succeeded'") in tokens
        any_error=lambda tokens: ('word','ANY') in tokens and ('literal',"'not_dispatched'") in tokens
        status_unavailable=lambda tokens: ('word','usage_status') in tokens
        distinct=lambda tokens: ('word','DISTINCT') in tokens
        null_test=lambda tokens: ('word','error_code') in tokens and ('word','NULL') in tokens and ('word','IS') in tokens
        bad_actuals=[]
        bad_actuals.append(change_atom(status_success,lambda t:self.replace_token(t,('literal',"'succeeded'"),('literal',"'refused'"))))
        bad_actuals.append(change_atom(any_error,lambda t:self.replace_token(t,('literal',"'metadata_inconsistent'"),('literal',"'other_code'"))))
        bad_actuals.append(change_atom(any_error,lambda t:self.replace_token(t,('operator','='),('operator','<>'))))
        bad_actuals.append(change_atom(any_error,lambda t:self.replace_token(t,('word','ANY'),('word','ALL'))))
        bad_actuals.append(change_atom(any_error,lambda t:self.replace_token(t,('word','text'),('word','varchar'))))
        bad_actuals.append(change_atom(status_success,lambda t:t[:1]+(('operator','::'),('word','text'))+t[1:]))
        bad_actuals.append(change_atom(null_test,lambda t:t[:2]+(('word','NOT'),)+t[2:]))
        bad_actuals.append(change_atom(distinct,lambda t:t[:2]+(('word','NOT'),)+t[2:]))
        bad_actuals.append(change_atom(status_unavailable,lambda t:self.replace_token(t,('literal',"'unavailable'"),('literal',"'available'"))))

        # Delete, substitute and reorder an ordered IN/ARRAY member after the
        # exact managed AST has been reduced to its proven IN_LIST nodes.
        canonical=actual
        def mutate_first_list(node, mutate):
            if node[0]=='IN_LIST':return ('IN_LIST',mutate(node[1]))
            if node[0] in ('AND','OR'):
                children=list(node[1])
                for i,child in enumerate(children):
                    changed=mutate_first_list(child,mutate)
                    if changed!=child:
                        children[i]=changed
                        return node[0],tuple(children)
            return node
        def remove_member(data):
            identifier,members=data
            return identifier,members[:-1]
        def substitute_member(data):
            identifier,members=data
            return identifier,members[:-1]+(('literal',"'other_code'"),)
        def reorder_members(data):
            identifier,members=data
            return identifier,(members[1],members[0],*members[2:])
        for mutation in (remove_member,substitute_member,reorder_members):
            bad_actuals.append(mutate_first_list(canonical,mutation))
        first_status_or=actual[1][0]
        bad_actuals.append(('AND',(('AND',first_status_or[1]),actual[1][1])))

        for candidate in bad_actuals:
            with self.subTest(candidate=repr(candidate)[:120]):
                normalized=v.canonicalize_check_ast(candidate)
                self.assertNotEqual(normalized,expected)
        self.assertIsNone(v.canonical_check_expression(
            "(status = 'succeeded'::text AND)",
            'executions','ck_executions_outcome_shape'))

    async def test_managed_identifier_bounds_catalog_form_passes_validator(self):
        await self.run_validation(self.connection_with_check(
            'executions','ck_executions_identifier_bounds',
            self.MANAGED_IDENTIFIER_BOUNDS_RENDERING))

    async def test_identifier_bounds_semantic_mutations_fail_closed(self):
        original=self.MANAGED_IDENTIFIER_BOUNDS_RENDERING
        bad=(
            original.replace('<= 255','< 255',1),
            original.replace('<= 255','',1),
            original.replace('reported_model_id','reported_model',1),
            original.replace('octet_length(reported_model_id) <= 255',
                             'octet_length(reported_model_id)::bigint <= 255',1),
            original.replace(') AND (octet_length(reported_model_id)',
                             ') OR (octet_length(reported_model_id)',1),
            original.replace('reported_model_id IS NULL','reported_model_id IS NOT NULL',1),
            original[:-1],
        )
        for sql in bad:
            with self.subTest(sql=sql):
                self.assertNotEqual(v.canonical_check_expression(
                    sql,'executions','ck_executions_identifier_bounds'),
                    v.expected_constraints()[('executions','ck_executions_identifier_bounds')][-1])
                with self.assertRaises(DatabaseUnavailable):
                    await self.run_validation(self.connection_with_check(
                        'executions','ck_executions_identifier_bounds',sql))

    def test_unrelated_malformed_check_is_not_repaired_by_grouping(self):
        malformed='(usage IS NULL OR (jsonb_typeof(usage) = \'object\' AND))'
        self.assertIsNone(v.canonical_check_expression(
            malformed,'executions','ck_executions_usage_shape'))

    def test_token_bounds_between_and_addition_catalog_grouping(self):
        source=TASK_CHECKS['ck_tasks_token_bounds']
        self.assertEqual(
            source,
            'input_token_upper_bound BETWEEN 0 AND 28467 AND output_allowance = 1024 '
            'AND safety_margin = 3277 AND input_token_upper_bound + output_allowance '
            '+ safety_margin <= 32768')
        # The managed fixture is the exact supplied token/AST evidence
        # expressed as SQL: expanded inclusive bounds and PostgreSQL's
        # ((a + b) + c) comparison grouping.
        managed=(
            '(input_token_upper_bound >= 0 AND input_token_upper_bound <= 28467) '
            'AND output_allowance = 1024 AND safety_margin = 3277 AND '
            '((input_token_upper_bound + output_allowance) + safety_margin) <= 32768')
        self.assertEqual(
            v.canonical_check_expression(source,'tasks','ck_tasks_token_bounds'),
            v.canonical_check_expression(managed,'tasks','ck_tasks_token_bounds'))

        expected_between=v.canonical_check_expression('x BETWEEN 0 AND 28467')
        expanded_between=v.canonical_check_expression('(x >= 0 AND x <= 28467)')
        self.assertEqual(expected_between,expanded_between)
        self.assertEqual(expected_between[0],'AND')
        bad_between=(
            'x BETWEEN 1 AND 28467',
            'x BETWEEN 0 AND 28468',
            'y BETWEEN 0 AND 28467',
            'x > 0 AND x <= 28467',
            'x >= 0 AND x < 28467',
            'x <= 28467',
            'x >= 0',
            'x >= 0 AND y <= 28467',
            'x <= 28467 AND x >= 0',
            'x BETWEEN 28467 AND 0',
            'x BETWEEN 0 OR x <= 28467',
            'x BETWEEN 0 AND',
            'x BETWEEN 0 28467',
        )
        for candidate in bad_between:
            with self.subTest(between=candidate):
                self.assertNotEqual(v.canonical_check_expression(candidate),expected_between)
        for malformed in ('x BETWEEN 0 AND', 'x BETWEEN 0 28467',
                          'x BETWEEN low AND 28467'):
            self.assertIsNone(v.canonical_check_expression(malformed))

        model_sum=v.canonical_check_expression('x + y + z <= 32768')
        managed_sum=v.canonical_check_expression('((x + y) + z) <= 32768')
        self.assertEqual(model_sum,managed_sum)
        bad_sums=(
            'a + y + z <= 32768',
            'y + x + z <= 32768',
            'x + y <= 32768',
            'x + y + y <= 32768',
            'x - y + z <= 32768',
            'x + y + z < 32768',
            'x + y + z <= 32769',
            'x + (y * z) <= 32768',
            'x + y + z <= 32768 +',
        )
        for candidate in bad_sums:
            with self.subTest(addition=candidate):
                self.assertNotEqual(v.canonical_check_expression(candidate),model_sum)

        # The source contract constants remain literal and unchanged in the
        # canonical representation, including the independent fixed bounds.
        canonical=v.canonical_check_expression(source,'tasks','ck_tasks_token_bounds')
        representation=repr(canonical)
        for constant in ('28467','1024','3277','32768'):
            self.assertIn(constant,representation)
