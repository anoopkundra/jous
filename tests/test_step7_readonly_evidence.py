"""Synthetic retention tests. No connection, credentials, or host environment."""
import copy
import importlib.util
from pathlib import Path
import unittest

import test_step7_atomic_runner as fixture

path = fixture.ROOT/'services/api/infrastructure/step7_readonly_evidence.py'
spec = importlib.util.spec_from_file_location('step7_retention', path)
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)
runner = fixture.runner


class RetentionTests(unittest.TestCase):
    def wrap(self, catalog=None, **kwargs):
        catalog = catalog or fixture.PublicCatalog()
        class SyntheticConnection:
            def execute(self, statement, params):
                sql = str(statement)
                if sql.startswith("SELECT pg_catalog.current_setting('"):
                    setting = sql.split("'")[1]
                    return fixture.Result([{'value':catalog.scalar(runner.text('SHOW '+setting))}])
                if 'has_schema_privilege(:role,:schema' in sql or sql.startswith('SELECT count(*)'):
                    return fixture.Result([{'value':catalog.scalar(statement, params)}])
                return catalog.execute(statement, params)
        return retention.EvidenceConnection(SyntheticConnection(), runner.text,
            tls_verified=True, target_verified=True, read_only_verified=True, **kwargs)

    def failure(self, catalog, before=None):
        connection = self.wrap(catalog)
        def collect(c):
            if before: before(c)
            runner.public_inventory(c)
        with self.assertRaises(retention.EvidenceFailure) as caught:
            connection.collect(collect, runner.Stop)
        self.assertEqual(str(caught.exception), 'PUBLIC_ROUTINES_SET')
        return caught.exception.document

    def test_exact_match_passes(self):
        result = self.wrap().collect(runner.public_inventory, runner.Stop)
        self.assertTrue(result['collection_complete'])
        self.assertFalse(result['execution_approved'])
        delta = result['public_routine_sets'][0]
        self.assertEqual(delta['expected_identities'], delta['observed_identities'])
        self.assertEqual(delta['added_identities'], [])
        self.assertEqual(delta['missing_identities'], [])

    def test_added_identity_retained_and_rejected(self):
        c = fixture.PublicCatalog()
        added = copy.deepcopy(c.routines[0]); added['name'] = 'unreviewed_extra'
        c.routines.append(added)
        result = self.failure(c)
        self.assertEqual(result['public_routine_sets'][0]['added_identities'],
                         retention.primitive([runner.routine_identity(added)]))

    def test_missing_identity_retained_and_rejected(self):
        c = fixture.PublicCatalog(); missing = c.routines.pop()
        result = self.failure(c)
        self.assertEqual(result['public_routine_sets'][0]['missing_identities'],
                         retention.primitive([runner.routine_identity(missing)]))

    def test_multiple_deltas_deterministic(self):
        c = fixture.PublicCatalog()
        referents = {(r['schema'],r['proname']) for r in
                     c.structural['referent_bindings']['functions']}
        removable = [r for r in c.routines if (r['schema'],r['name']) not in referents][:2]
        self.assertEqual(len(removable), 2)
        for row in removable: c.routines.remove(row)
        for name in ('z_extra', 'a_extra'):
            row = copy.deepcopy(c.routines[0]); row['name'] = name; c.routines.append(row)
        first = self.failure(c)['public_routine_sets']
        c.routines.reverse()
        self.assertEqual(first, self.failure(c)['public_routine_sets'])
        self.assertEqual(len(first[0]['added_identities']), 2)
        self.assertEqual(len(first[0]['missing_identities']), 2)

    def test_operator_boolean_values_retained_before_failure(self):
        c = fixture.PublicCatalog(); c.routines.pop()
        def before(connection):
            runner.rows(connection, runner._STRUCTURAL_QUERIES['operators'], {'ids':[514]})
        result = self.failure(c, before)
        op = result['observations'][0]['rows'][0]
        self.assertEqual(op, c.structural['referent_bindings']['operators'][0])
        self.assertIs(type(op['oprcanmerge']), bool)
        self.assertIs(type(op['oprcanhash']), bool)

    def test_incomplete_non_approving_and_finalized(self):
        c = fixture.PublicCatalog(); c.routines.pop()
        connection = self.wrap(c)
        with self.assertRaises(retention.EvidenceFailure) as caught:
            connection.collect(runner.public_inventory, runner.Stop)
        d = caught.exception.document
        self.assertEqual(d['status'], 'INCOMPLETE_FAIL_CLOSED')
        for key in ('collection_complete','execution_approved','migration_ready'):
            self.assertIs(d[key], False)
        self.assertEqual(d['failure_gate'], 'PUBLIC_ROUTINES_SET')
        self.assertIsNone(d['post_0002_raw_policy_contract'])
        with self.assertRaises(ValueError): connection.collect(lambda c: None, runner.Stop)
        with self.assertRaises(ValueError): connection.execute(runner.text('SELECT 1'))

    def test_duplicate_identity_rejected_and_preserved(self):
        c = fixture.PublicCatalog(); c.routines.append(copy.deepcopy(c.routines[0]))
        d = self.failure(c)['public_routine_sets'][0]
        self.assertEqual(d['observed_count'], d['expected_count']+1)
        self.assertEqual(d['added_identities'], [])

    def test_identity_fields_are_exact(self):
        for field in ('schema','name','routine_kind','identity_input_types'):
            c = fixture.PublicCatalog()
            if field == 'identity_input_types':
                c.routines[0][field] = [{'schema':'pg_catalog','name':'int8'}]
            else: c.routines[0][field] = 'different'
            d = self.failure(c)['public_routine_sets'][0]
            self.assertEqual(len(d['added_identities']), 1)
            self.assertEqual(len(d['missing_identities']), 1)

    def test_exception_details_not_disclosed(self):
        def fail(c): raise RuntimeError('synthetic-sensitive-detail')
        with self.assertRaises(retention.EvidenceFailure) as caught:
            self.wrap().collect(fail, runner.Stop)
        self.assertNotIn('synthetic-sensitive-detail', retention.canonical(caught.exception.document))

    def test_unverified_boundary_rejected(self):
        with self.assertRaises(ValueError):
            retention.EvidenceConnection(None, str, tls_verified=False,
                target_verified=True, read_only_verified=True)

    def test_primitive_type_rejected(self):
        with self.assertRaises(ValueError): retention.primitive(object())

    def test_no_connection_or_filesystem_api(self):
        tree = __import__('ast').parse(path.read_bytes())
        imports = {n.names[0].name for n in tree.body if isinstance(n, __import__('ast').Import)}
        self.assertEqual(imports, {'copy','hashlib','json','re'})
        self.assertNotIn('open(', path.read_text())

    def test_select_and_parameter_boundary(self):
        for sql in ('UPDATE anything', 'SELECT 1; SELECT 2','SELECT pg_get_expr(1,2)'):
            with self.assertRaises(ValueError): self.wrap().execute(runner.text(sql))
        with self.assertRaises(ValueError):
            self.wrap().execute(runner.text('SELECT 1'), {'password':'synthetic'})

    def test_bounded_retention(self):
        c = self.wrap(); c.MAX_BYTES = 1
        with self.assertRaises(retention.EvidenceFailure) as caught:
            c.collect(runner.public_inventory, runner.Stop)
        self.assertFalse(caught.exception.document['collection_complete'])

    def test_select_whitespace_forms(self):
        class Inert:
            def __init__(self): self.calls = []
            def execute(self, sql, params):
                self.calls.append(str(sql)); return fixture.Result([{'value':1}])
        for whitespace in (' ', '\n', '\r', '\r\n', '\t', ' \t\r\n\f\v'):
            for keyword in ('SELECT','select','SeLeCt'):
                with self.subTest(whitespace=repr(whitespace),keyword=keyword):
                    fake = Inert()
                    c = retention.EvidenceConnection(fake,str,tls_verified=True,
                        target_verified=True,read_only_verified=True)
                    sql = keyword+whitespace+'1'
                    self.assertEqual(c.scalar(sql),1)
                    self.assertEqual(fake.calls,[sql])

    def test_non_select_lookalikes_and_stacked_statements(self):
        class NeverExecute:
            def execute(self,*args): raise AssertionError('REJECTED_SQL_REACHED_EXECUTION')
        bad = ('SELECTED 1','SELECTfoo 1','SELECT_foo 1','SELECT',
               'INSERT INTO t VALUES (1)','UPDATE t SET x=1','DELETE FROM t',
               'CREATE TABLE t(x int)','ALTER TABLE t ADD x int','DROP TABLE t',
               'GRANT SELECT ON t TO x','REVOKE SELECT ON t FROM x','DO $$BEGIN END$$',
               'MERGE INTO t','CALL f()','COPY t TO STDOUT',
               'SELECT 1; SELECT 2','SELECT\n1; DELETE FROM t',
               'SELECT 1;','SELECT/*comment*/1','SELECT\u00a01','\u017fELECT 1')
        for sql in bad:
            c = retention.EvidenceConnection(NeverExecute(),str,tls_verified=True,
                target_verified=True,read_only_verified=True)
            with self.subTest(sql=sql),self.assertRaises(ValueError):c.execute(sql)

    def test_complete_reviewed_preflight_sequence(self):
        # Actual production SELECT functions and their assertions run against
        # independently shaped synthetic catalog data. No mutating preflight,
        # migration pipeline, advisory lock, or target connection is invoked.
        catalog = fixture.Catalog(); c = self.wrap(catalog)
        def sequence(connection):
            runner.revision(connection,'0001_identity_project')
            runner.table_state(connection)
            runner.rows(connection,runner._STRUCTURAL_QUERIES['operators'],{'ids':[514]})
            self.assertEqual(runner.policies(connection),[])
            runner.role_gate(connection)
            runner.baseline_membership(connection)
            runner.verify_ownership(connection,False)
            runner.privilege_boundary(connection)  # Previously rejected SELECT\n.
            runner.verify_direct_authority(connection,False)
            runner.public_inventory(connection)
            runner.verify_grants(connection,False)
        d = c.collect(sequence,runner.Stop)
        self.assertTrue(d['collection_complete'])
        self.assertTrue(any(x['sql'].startswith('SELECT\n') for x in d['observations']))
        self.assertTrue(d['public_routine_sets'])
        self.assertFalse(d['execution_approved'])

    def test_all_reviewed_projection_lexical_forms(self):
        # Review every SELECT literal/f-string prefix on the bounded production
        # catalog surface, plus scalar target/identity and expanded inventories.
        ast = __import__('ast')
        source = ast.parse((fixture.ROOT/'services/api/infrastructure/apply_step7_atomic.py').read_bytes())
        functions = {'collect_public_inventory','verify_structural_contract','memberships',
            'authority','baseline_membership','role_gate','privilege_boundary','table_state',
            'revision','verify_ownership','verify_direct_authority','verify_grants','verify_routines'}
        projections = list(runner._STRUCTURAL_QUERIES.values()) + [runner._VIEW_QUERY,
            runner._DEFAULT_QUERY,runner._DATABASE_QUERY,runner._DEPENDENCY_QUERY]
        for node in source.body:
            if isinstance(node,ast.FunctionDef) and node.name in functions:
                for value in ast.walk(node):
                    if (isinstance(value,ast.Constant) and type(value.value) is str
                        and value.value.lstrip().upper().startswith('SELECT')
                        and len(value.value.strip()) > 6):
                        projections.append(value.value)
        projections += [
            "SELECT current_user::pg_catalog.text AS current_user,session_user::pg_catalog.text AS session_user,current_setting('transaction_read_only') AS transaction_read_only",
            "SELECT d.oid,d.defaclrole FROM pg_catalog.pg_default_acl d",
            "SELECT n.oid,n.nspname,n.nspowner FROM pg_catalog.pg_namespace n",
            "SELECT o.oid,o.oprcanmerge,o.oprcanhash FROM pg_catalog.pg_operator o WHERE o.oid=514"]
        class Inert:
            def execute(self,*args): return fixture.Result([])
        c = retention.EvidenceConnection(Inert(),str,tls_verified=True,
            target_verified=True,read_only_verified=True)
        for sql in projections:
            with self.subTest(sql=sql):c.execute(sql)
        self.assertGreater(len(projections),40)
