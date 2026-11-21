"""Closed-world successor coverage; never connects or applies a migration."""
import unittest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint,ForeignKeyConstraint,UniqueConstraint,PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID,BYTEA,JSONB
from jous_api.models import Base,Project
from jous_api.task_models import Task,Execution,tasks,executions,TASK_COLUMNS,EXECUTION_COLUMNS,TASK_CHECKS,EXECUTION_CHECKS
from jous_api.usage_event_models import usage_events
from jous_api.economic_models import (supplier_funding_authorities, economic_receipts,
                                      ledger_accounts, ledger_transactions, ledger_entries)
from test_schema_foundation import INI


class ProductSchemaTests(unittest.TestCase):
    def test_closed_v14_table_composition_and_orders(self):
        self.assertEqual(set(Base.metadata.tables),{'public.'+n for n in
            ('users','organizations','organization_memberships','projects','tasks','executions','usage_events',
             'supplier_funding_authorities','economic_receipts','ledger_accounts','ledger_transactions','ledger_entries')})
        self.assertEqual(tuple(tasks.columns.keys()),TASK_COLUMNS)
        self.assertEqual(tuple(executions.columns.keys()),EXECUTION_COLUMNS)
    def test_no_record_mutability_or_client_defaults(self):
        from jous_api.persistence import Record
        for cls,table,stamp in [(Task,tasks,'created_at'),(Execution,executions,'recorded_at')]:
            self.assertFalse(issubclass(cls,Record));self.assertNotIn('updated_at',table.c)
            for c in table.c:
                self.assertIsNone(c.default);self.assertIsNone(c.onupdate)
                self.assertEqual(c.server_default is not None,c.name==stamp)
            self.assertEqual(str(table.c[stamp].server_default.arg),'statement_timestamp()')
            self.assertTrue(table.c[stamp].type.timezone)
        self.assertNotIn('status',tasks.c)
        self.assertTrue(all(not c.nullable for c in tasks.c))
        nullable={'response_text','reported_model_id','reported_provider_id','provider_request_id',
                  'provider_response_id','finish_reason','usage','error_code','request_started_at','response_received_at',
                  'credential_authority_ref'}
        self.assertEqual({c.name for c in executions.c if c.nullable},nullable)
    def test_exact_types(self):
        for name in ('id','organization_id','project_id','actor_user_id','client_request_id','dispatch_claim_id'):
            self.assertIsInstance(tasks.c[name].type,UUID)
        for name in ('request_sha256','context_sha256','tokenizer_manifest_sha256'):
            self.assertIsInstance(tasks.c[name].type,BYTEA)
        for name in ('context_package','request_parameters','token_bound_evidence'):
            self.assertIsInstance(tasks.c[name].type,JSONB)
        self.assertIsInstance(executions.c.usage.type,JSONB)
        for name in ('request_started_at','response_received_at','recorded_at'):
            self.assertTrue(executions.c[name].type.timezone)
    def test_exact_uniques_and_project_addition(self):
        def uniques(table):return {c.name:tuple(c.columns.keys()) for c in table.constraints if isinstance(c,UniqueConstraint)}
        self.assertEqual(uniques(Project.__table__),{'uq_projects_organization_id_id':('organization_id','id')})
        self.assertEqual(uniques(tasks),{
            'uq_tasks_request':('organization_id','project_id','actor_user_id','client_request_id'),
            'uq_tasks_dispatch_claim_id':('dispatch_claim_id',),
            'uq_tasks_execution_binding':('id','organization_id','project_id','actor_user_id','dispatch_claim_id')})
        self.assertEqual(uniques(executions),{'uq_executions_task_id':('task_id',),
                                           'uq_executions_dispatch_claim_id':('dispatch_claim_id',)})
    def test_exact_constraints_fks_and_indexes(self):
        expected={
            'fk_tasks_project_binding':(('organization_id','project_id'),('public.projects.organization_id','public.projects.id')),
            'fk_tasks_actor_user':(('actor_user_id',),('public.users.id',)),
            'fk_executions_task_binding':(('task_id','organization_id','project_id','actor_user_id','dispatch_claim_id'),
                tuple('public.tasks.'+n for n in ('id','organization_id','project_id','actor_user_id','dispatch_claim_id')))}
        actual={}
        for table,checks in [(tasks,TASK_CHECKS),(executions,EXECUTION_CHECKS)]:
            self.assertEqual({c.name:str(c.sqltext) for c in table.constraints if isinstance(c,CheckConstraint)},checks)
            self.assertEqual(table.primary_key.name,'pk_'+table.name)
            self.assertEqual(tuple(table.primary_key.columns.keys()),('id',))
            for c in table.constraints:
                self.assertIsInstance(c,(CheckConstraint,ForeignKeyConstraint,UniqueConstraint,PrimaryKeyConstraint))
                if isinstance(c,ForeignKeyConstraint):
                    actual[c.name]=(tuple(c.columns.keys()),tuple(e.target_fullname for e in c.elements))
                    self.assertEqual(c.ondelete,'RESTRICT');self.assertEqual(c.onupdate,'RESTRICT')
                    self.assertIs(c.deferrable,False);self.assertEqual(c.initially,'IMMEDIATE')
        self.assertEqual(actual,expected)
        self.assertEqual({(i.name,tuple(i.columns.keys())) for i in tasks.indexes},
                         {('ix_tasks_project_created_id',('organization_id','project_id','created_at','id'))})
        self.assertEqual(set(executions.indexes),set())
    def test_exact_linear_migration_chain(self):
        scripts=ScriptDirectory.from_config(Config(str(INI)))
        self.assertEqual(scripts.get_heads(),['0009_economic_ledger_core'])
        revisions=list(scripts.walk_revisions())
        self.assertEqual([(r.revision,r.down_revision) for r in revisions],[
            ('0009_economic_ledger_core','0008_usage_event_acl_hardening'),
            ('0008_usage_event_acl_hardening','0007_usage_events'),
            ('0007_usage_events','0006_snapshot_binding'),
            ('0006_snapshot_binding','0005_route_economics'),
            ('0005_route_economics','0004_product_acl_hardening'),
            ('0004_product_acl_hardening','0003_project_tasks_executions'),
            ('0003_project_tasks_executions','0002_runtime_rls'),
            ('0002_runtime_rls','0001_identity_project'),('0001_identity_project',None)])

    def test_all_migration_revisions_fit_alembic_version_num_capacity(self):
        scripts=ScriptDirectory.from_config(Config(str(INI)))
        capacity=32
        revisions=list(scripts.walk_revisions())
        self.assertTrue(revisions)
        for script in revisions:
            with self.subTest(revision=script.revision):
                self.assertLessEqual(len(script.revision),capacity)
        self.assertLessEqual(len('0004_product_acl_hardening'),capacity)
        self.assertLessEqual(len('0005_route_economics'),capacity)
        self.assertLessEqual(len('0006_snapshot_binding'),capacity)
        self.assertLessEqual(len('0008_usage_event_acl_hardening'),capacity)
        self.assertLessEqual(len('0009_economic_ledger_core'),capacity)

    def test_usage_event_schema_is_additive_and_immutable_shaped(self):
        self.assertEqual(usage_events.primary_key.name,'pk_usage_events')
        self.assertEqual({c.name for c in usage_events.constraints if isinstance(c,UniqueConstraint)}, {
            'uq_usage_events_source_identity','uq_usage_events_single_successor','uq_usage_events_binding'})
        self.assertFalse(any(c.name and c.name.startswith('uq_executions') for c in executions.constraints
                             if isinstance(c,UniqueConstraint) and c.name != 'uq_executions_task_id'
                             and c.name != 'uq_executions_dispatch_claim_id'))
        self.assertEqual(usage_events.c.recorded_at.server_default.arg.text,'statement_timestamp()')
        self.assertFalse(usage_events.c.recorded_at.nullable)
        self.assertTrue(usage_events.c.input_tokens.nullable)
        self.assertIn('UNAVAILABLE',str(next(c.sqltext for c in usage_events.constraints
                                             if isinstance(c,CheckConstraint) and c.name=='ck_usage_events_status_values')))
    def test_error_outcomes_cannot_pass_checks_as_sql_null(self):
        shape=EXECUTION_CHECKS['ck_executions_outcome_shape']
        self.assertIn("status = 'known_error' AND error_code IS NOT NULL",shape)
        self.assertIn("status = 'unknown' AND error_code IS NOT NULL",shape)


class LiteralMigrationTests(unittest.TestCase):
    """Independent source oracle: no validator expected_* or model constants."""
    @classmethod
    def setUpClass(cls):
        import ast
        from pathlib import Path
        cls.path=Path(__file__).resolve().parents[1]/'services/api/migrations/versions/0003_project_tasks_executions.py'
        tree=ast.parse(cls.path.read_text())
        cls.values={node.targets[0].id:ast.literal_eval(node.value) for node in tree.body
                    if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('revision','down_revision','UPGRADE_SQL')}
        cls.sql=cls.values['UPGRADE_SQL']

    def test_literal_revision_tables_columns_types_defaults(self):
        import re
        self.assertEqual(self.values['revision'],'0003_project_tasks_executions')
        self.assertEqual(self.values['down_revision'],'0002_runtime_rls')
        ddl={re.search(r'CREATE TABLE public\.(\w+)',x).group(1):x for x in self.sql if 'CREATE TABLE' in x}
        self.assertEqual(set(ddl),{'tasks','executions'})
        task='id organization_id project_id actor_user_id client_request_id request_sha256 prompt context_package context_sha256 logical_model_id supplier_id supplier_native_model_id underlying_provider admission_version request_parameters tokenizer_manifest_sha256 template_branch token_bound_method token_bound_evidence input_token_upper_bound output_allowance safety_margin dispatch_claim_id dispatch_deadline_at created_at'.split()
        execution='id task_id organization_id project_id actor_user_id dispatch_claim_id status response_text reported_model_id reported_provider_id provider_request_id provider_response_id finish_reason usage usage_status error_code request_started_at response_received_at recorded_at'.split()
        nullable=set('response_text reported_model_id reported_provider_id provider_request_id provider_response_id finish_reason usage error_code request_started_at response_received_at'.split())
        for table,names in [('tasks',task),('executions',execution)]:
            columns=[line.strip().rstrip(',') for line in ddl[table].splitlines() if line.startswith('\t') and not line.strip().startswith('CONSTRAINT')]
            self.assertEqual([x.split()[0] for x in columns],names)
            for name,line in zip(names,columns):
                typ='UUID' if name in {'id','task_id','organization_id','project_id','actor_user_id','client_request_id','dispatch_claim_id'} else 'BYTEA' if name.endswith('sha256') else 'JSONB' if name in {'context_package','request_parameters','token_bound_evidence','usage'} else 'INTEGER' if name in {'input_token_upper_bound','output_allowance','safety_margin'} else 'TIMESTAMP WITH TIME ZONE' if name.endswith('_at') else 'TEXT'
                suffix=' DEFAULT statement_timestamp()' if name in {'created_at','recorded_at'} else ''
                suffix+=' NOT NULL' if table=='tasks' or name not in nullable else ''
                self.assertEqual(line,f'{name} {typ}{suffix}')

    def test_literal_security_grants_policies_fks_and_index(self):
        import re
        text='\n'.join(self.sql)
        self.assertEqual(text.count('ON DELETE RESTRICT ON UPDATE RESTRICT NOT DEFERRABLE INITIALLY IMMEDIATE'),3)
        for fragment in (
            'uq_projects_organization_id_id UNIQUE (organization_id, id)',
            'uq_tasks_request UNIQUE (organization_id, project_id, actor_user_id, client_request_id)',
            'uq_tasks_execution_binding UNIQUE (id, organization_id, project_id, actor_user_id, dispatch_claim_id)',
            'FOREIGN KEY(organization_id, project_id) REFERENCES public.projects (organization_id, id)',
            'FOREIGN KEY(actor_user_id) REFERENCES public.users (id)',
            'FOREIGN KEY(task_id, organization_id, project_id, actor_user_id, dispatch_claim_id) REFERENCES public.tasks (id, organization_id, project_id, actor_user_id, dispatch_claim_id)',
            'uq_executions_task_id UNIQUE (task_id)', 'uq_executions_dispatch_claim_id UNIQUE (dispatch_claim_id)'):
            self.assertIn(fragment,text)
        self.assertEqual([x for x in self.sql if x.startswith('CREATE INDEX')],['CREATE INDEX ix_tasks_project_created_id ON public.tasks (organization_id, project_id, created_at, id)'])
        policies=[x for x in self.sql if x.startswith('CREATE POLICY')]
        self.assertEqual(len(policies),4)
        for table in ('tasks','executions'):
            self.assertIn(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY',self.sql)
            self.assertIn(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY',self.sql)
            for command in ('SELECT','INSERT'):
                matches=[x for x in policies if x.startswith(f'CREATE POLICY jous_{table}_{command.lower()} ON public.{table} AS PERMISSIVE FOR {command} TO jous_runtime')]
                self.assertEqual(len(matches),1)
                if table=='executions' and command=='INSERT':self.assertNotIn('NOT EXISTS',matches[0])
        grants=[x for x in self.sql if x.startswith('GRANT')]
        self.assertEqual(len(grants),4)
        for statement in grants:
            self.assertRegex(statement,r'^GRANT (SELECT|INSERT) \([a-z0-9_, ]+\) ON public\.(tasks|executions) TO jous_runtime$')
            self.assertNotIn('GRANT OPTION',statement)
            if statement.startswith('GRANT INSERT'):
                self.assertNotIn('created_at',statement);self.assertNotIn('recorded_at',statement)
        for statement in self.sql:
            self.assertNotRegex(statement,r'^GRANT (UPDATE|DELETE|TRUNCATE|REFERENCES|TRIGGER|ALL)')

    def test_frozen_literal_check_policy_and_grant_content(self):
        # Source-owned digests freeze exact literal expressions, not a live DB or
        # the validator's generated catalog. Semantic assertions above supplement them.
        import hashlib
        expected = {'checks': '09dab19dab809dbb34beeac4f047cbd04435924b089cb66bebf0eb10f1a8f861', 'policies': '24b7d1eb0222210bb3616e0c0899d91a9b70cd35148ae0b3f9513d603d50f972', 'grants': 'f0d24db669267f573a4e3df8d01b5beda4808f6bb24194403587942e86093cbb'}
        for label,predicate in [('checks',lambda x:'CREATE TABLE' in x),('policies',lambda x:x.startswith('CREATE POLICY')),('grants',lambda x:x.startswith('GRANT'))]:
            actual=hashlib.sha256('\n'.join(x for x in self.sql if predicate(x)).encode()).hexdigest()
            self.assertEqual(actual,expected[label])


class ProductRelationAclMigrationTests(unittest.TestCase):
    """Source-level migration contract tests; no database is opened or changed."""
    @classmethod
    def setUpClass(cls):
        import ast
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        cls.path=root/'services/api/migrations/versions/0004_product_relation_acl_hardening.py'
        cls.source=cls.path.read_text()
        tree=ast.parse(cls.source)
        cls.values={node.targets[0].id:ast.literal_eval(node.value)
                    for node in tree.body if isinstance(node,ast.Assign)
                    and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)
                    and node.targets[0].id in ('revision','down_revision','UPGRADE_SQL')}
        old=ast.parse((root/'services/api/migrations/versions/0003_project_tasks_executions.py').read_text())
        cls.v3_values={node.targets[0].id:ast.literal_eval(node.value)
                       for node in old.body if isinstance(node,ast.Assign)
                       and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)
                       and node.targets[0].id in ('revision','down_revision','UPGRADE_SQL')}
        cls.sql='\n'.join(cls.values['UPGRADE_SQL'])

    def test_revision_continuity_and_owner_preserving_acl_algorithm(self):
        self.assertEqual(self.values['revision'],'0004_product_acl_hardening')
        self.assertEqual(self.values['down_revision'],'0003_project_tasks_executions')
        self.assertIn("n.nspname = 'public'",self.sql)
        self.assertIn("c.relname IN ('tasks', 'executions')",self.sql)
        self.assertIn("c.relkind = 'r'",self.sql)
        self.assertIn('acl.grantee <> target.relowner',self.sql)
        self.assertIn('acl.grantee <> c.relowner',self.sql)
        self.assertNotIn('ALTER TABLE public.tasks OWNER',self.sql)
        self.assertNotIn('ALTER TABLE public.executions OWNER',self.sql)
        self.assertNotIn('OWNER TO',self.sql)
        self.assertIn("IF grantee_oid = 0 THEN",self.sql)
        self.assertIn("grantee_sql := 'PUBLIC'",self.sql)
        self.assertIn('pg_catalog.quote_ident(grantee_name::text)',self.sql)
        format_sql = 'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM %s'
        self.assertEqual(self.sql.count(format_sql), 1)
        self.assertNotIn('%%I', self.sql)
        self.assertNotIn('%%s', self.sql)
        self.assertNotIn('CASCADE',self.sql)
        self.assertNotIn('RESTRICT',self.sql)
        self.assertIn('acl.grantee <> target.relowner',self.sql)
        self.assertIn('IF grantee_oid = 0 THEN',self.sql)
        self.assertIn("grantee_sql := 'PUBLIC'",self.sql)
        self.assertIn('pg_catalog.quote_ident(grantee_name::text)',self.sql)
        self.assertIn('IF non_owner_acl_exists THEN',self.sql)
        self.assertIn('pg_catalog.aclexplode(',self.sql)
        self.assertIn("pg_catalog.acldefault('r', target.relowner)",self.sql)

    def test_dynamic_acl_coverage_has_no_optional_role_or_fixed_grantee_list(self):
        # The migration follows ACL grantee OIDs already attached to each target
        # relation. Optional and unexpected roles need not be provisioned by name.
        for role in ('anon','authenticated','service_role','jous_runtime',
                     'jous_security_reader','unexpected role "quoted"'):
            with self.subTest(role=role):
                self.assertNotIn("'"+role+"'",self.sql)
        self.assertIn('FOR grantee_oid IN',self.sql)
        self.assertIn('SELECT DISTINCT acl.grantee',self.sql)
        self.assertIn('WHERE acl.grantee <> target.relowner',self.sql)
        self.assertIn('IF grantee_oid = 0 THEN',self.sql)
        self.assertIn('pg_catalog.quote_ident(grantee_name::text)',self.sql)
        # Owner-only input yields no loop rows and therefore no revoke or grant.
        self.assertIn('IF non_owner_acl_exists THEN',self.sql)
        self.assertIn('RAISE EXCEPTION',self.sql)
        self.assertNotRegex(self.sql,r'(?im)^\s*GRANT\b')

    def test_no_broad_grants_and_frozen_column_contract_is_untouched(self):
        v3_grants=[s for s in self.v3_values['UPGRADE_SQL'] if s.startswith('GRANT ')]
        self.assertEqual(len(v3_grants),4)
        self.assertTrue(all('ON public.tasks TO jous_runtime' in s or
                            'ON public.executions TO jous_runtime' in s for s in v3_grants))
        self.assertTrue(all(s.startswith(('GRANT SELECT (','GRANT INSERT (')) for s in v3_grants))
        self.assertTrue(all('created_at' not in s and 'recorded_at' not in s
                            for s in v3_grants if s.startswith('GRANT INSERT ')))
        self.assertNotRegex(self.sql,r'(?im)^\s*GRANT\b')
        self.assertNotRegex(self.sql,r'(?im)^\s*REVOKE\s+[^;]*\([^)]*\)\s+ON\s+public\.')
        self.assertIn('REVOKE ALL ON TABLE public.tasks FROM jous_security_reader',
                      '\n'.join(self.v3_values['UPGRADE_SQL']))
        self.assertIn('REVOKE ALL ON TABLE public.executions FROM jous_security_reader',
                      '\n'.join(self.v3_values['UPGRADE_SQL']))

    def test_product_schema_and_security_objects_are_not_touched(self):
        for forbidden in ('CREATE TABLE','DROP TABLE','ALTER TABLE','CREATE POLICY',
                          'DROP POLICY','CREATE INDEX','DROP INDEX','ADD CONSTRAINT',
                          'DROP CONSTRAINT','OWNER TO','ENABLE ROW LEVEL SECURITY',
                          'FORCE ROW LEVEL SECURITY'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,self.sql)

    def test_validator_relation_acl_predicate_matches_migration_postcondition(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1]/
                'services/api/src/jous_api/product_runtime_validation.py').read_text()
        validator_fragment="a.grantee<>c.relowner"
        self.assertIn(validator_fragment,source.replace(' ','').replace('\n',''))
        self.assertIn('acl.grantee <> c.relowner',self.sql)
        self.assertIn("COALESCE(c.relacl, pg_catalog.acldefault('r', c.relowner))",self.sql)
        self.assertIn("COALESCE(target.relacl, pg_catalog.acldefault('r', target.relowner))",self.sql)

    def test_downgrade_does_not_recreate_unknown_grants(self):
        self.assertIn('def downgrade():',self.source)
        self.assertIn('pre-0004 grants',self.source)
        downgrade=self.source.split('def downgrade():',1)[1]
        self.assertIn('pass',downgrade)
        self.assertNotRegex(downgrade,r'(?im)^\s*(GRANT|ALTER|CREATE)\b')
