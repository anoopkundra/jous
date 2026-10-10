"""Offline synthetic regression tests; no catalog values constitute evidence."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_step7_atomic_runner as fixture
from jous_api import step7_catalog as catalog

runner = fixture.runner
ROOT = fixture.ROOT


class ConsolidatedTests(unittest.TestCase):
    def test_namespace_exact_system_and_numeric_temporary_rule(self):
        from jous_api.database import ROLE_CHECK, TEMP_EVIDENCE
        for sql in (ROLE_CHECK, TEMP_EVIDENCE, catalog.USER_NAMESPACE, runner.USER_NAMESPACE):
            self.assertIn("n.nspname NOT IN ('pg_catalog','information_schema','pg_toast')", sql)
            self.assertIn("n.nspname !~ '^pg_(temp|toast_temp)_[0-9]+$'", sql)
        for name in ('pg_catalog','information_schema','pg_toast','pg_temp_0','pg_temp_123','pg_toast_temp_12'):
            with self.subTest(name=name): self.assertFalse(catalog.user_namespace(name))
        for name in ('pgx','pg_foo','pg_attacker','pg_temp','pg_temp_x','pg_temp_1x','pg_temp_-1','pg_temp_Ù¡'):
            with self.subTest(name=name): self.assertTrue(catalog.user_namespace(name))

    def test_default_count_all_three_representations(self):
        base = fixture.synthetic_manifest()
        targets = [('routines','default_argument_count','identity_input_types'),
                   ('default_structures','default_argument_count','input_type_oids'),
                   ('functions','pronargdefaults','input_type_oids')]
        for group,field,args in targets:
            for invalid in (-1,True,1.0,'0'):
                data=copy.deepcopy(base)
                entries=data['referent_bindings'][group] if group=='functions' else data[group]
                entries[0][field]=invalid
                with self.subTest(group=group,value=invalid),self.assertRaises(runner.Stop):
                    runner.parse_manifest(json.dumps(data).encode())
            data=copy.deepcopy(base)
            entries=data['referent_bindings'][group] if group=='functions' else data[group]
            entries[0][field]=len(entries[0][args])+1
            with self.subTest(group=group),self.assertRaises(runner.Stop):
                runner.parse_manifest(json.dumps(data).encode())
        # Collected values must reject bool too: dict equality alone treats False
        # as 0 and True as 1, so schema-only manifest checks are insufficient.
        for invalid in (-1, False, True, 999):
            observed=fixture.PublicCatalog()
            observed.routines[0]['default_argument_count']=invalid
            with self.subTest(observed='routine',value=invalid),self.assertRaises(runner.Stop):
                runner.public_inventory(observed)
            for group,field in (('default_structures','default_argument_count'),('functions','pronargdefaults')):
                observed=fixture.PublicCatalog()
                entries=observed.structural['referent_bindings'][group] if group=='functions' else observed.structural[group]
                entries[0][field]=invalid
                with self.subTest(observed=group,value=invalid),self.assertRaises(runner.Stop):
                    runner.verify_structural_contract(observed,base)

    def test_operator_fields_required_strict_bool(self):
        base=fixture.synthetic_manifest()
        for field in ('oprcanmerge','oprcanhash'):
            for invalid in (None,0,1,'false'):
                data=copy.deepcopy(base);data['referent_bindings']['operators'][0][field]=invalid
                with self.subTest(field=field,value=invalid),self.assertRaises(runner.Stop):
                    runner.parse_manifest(json.dumps(data).encode())
            data=copy.deepcopy(base);del data['referent_bindings']['operators'][0][field]
            with self.assertRaises(runner.Stop):runner.parse_manifest(json.dumps(data).encode())
        self.assertIn('o.oprcanmerge,o.oprcanhash',runner._STRUCTURAL_QUERIES['operators'])
        for field in ('oprcanmerge','oprcanhash'):
            observed=fixture.PublicCatalog()
            entry=observed.structural['referent_bindings']['operators'][0]
            entry[field]=int(entry[field])
            with self.assertRaises(runner.Stop):runner.verify_structural_contract(observed,base)

    def test_real_base_and_unresolved_candidate_cannot_execute(self):
        import io
        from contextlib import redirect_stdout
        for name in ('step7_public_compat_manifest.json','step7_public_compat_amendment_candidate.json'):
            with self.subTest(name=name),self.assertRaises(runner.Stop):
                fixture._BASE_PARSE((ROOT/'services/api/infrastructure'/name).read_bytes())
        self.assertIsNone(catalog.APPROVED_POLICY_CONTRACT)
        with self.assertRaises(ValueError):catalog.verify_policy_records([],None)
        with (patch.object(runner,'trusted_launch_gate'),patch.object(runner,'cached_jous_gate'),
              patch.object(runner,'repository_gate'),
              patch.object(runner.execution_contract(),'load_final_contract',side_effect=runner.Stop('CONTRACT_HASH')),
              patch.object(runner,'create_async_engine') as engine):
            self.assertEqual(runner.main(['--confirm-managed-mutation',
                '--approved-execution-sha','1'*40]),1)
            engine.assert_not_called()

    def test_original_manifest_unchanged(self):
        content=(ROOT/runner.MANIFEST_PATH).read_bytes()
        self.assertEqual(len(content),316705)
        self.assertEqual(hashlib.sha256(content).hexdigest(),runner.MANIFEST_SHA)

    def test_numeric_helpers_and_owned_oid_exception(self):
        c=fixture.Catalog();c.migrated=True
        ids=runner.verify_helpers(c,c.statements,{'jous_runtime':51,'jous_security_reader':50})
        self.assertEqual(ids,(301,302))
        runner.verify_ownership(c,True,ids)
        ownership_sql=next(sql for sql in c.events if 'SELECT s.classid' in sql)
        self.assertIn('LEFT JOIN pg_catalog.pg_class',ownership_sql)
        self.assertIn('AND NOT COALESCE(',ownership_sql)
        with patch.dict(c.overrides,{'SELECT s.classid':[dict(classid=999999,objid=301,objsubid=0,
                class_namespace=None,class_name=None)]}),self.assertRaises(runner.Stop):
            runner.verify_ownership(c,True,ids)
        with self.assertRaises(runner.Stop):runner.verify_ownership(c,True)
        for field,value in (('args',[25]),('args',[True,25]),('returns',16),('routine_oid',True),('namespace_oid',0)):
            data=c.execute('p.proargtypes::pg_catalog.oid[] AS args').all()
            target=next(r for r in data if r['proname']=='resolve_user');target[field]=value
            with self.subTest(field=field),patch.dict(c.overrides,{'p.proargtypes::pg_catalog.oid[] AS args':data}),self.assertRaises(runner.Stop):
                runner.verify_helpers(c,c.statements,{'jous_runtime':51,'jous_security_reader':50})

    def test_opaque_null_and_unexpected_policy_rejection(self):
        base=copy.deepcopy(fixture._CATALOG_MODULE.APPROVED_POLICY_CONTRACT)
        for field,value in (('using_tree',None),('using_tree',''),('check_tree',True),
                            ('role_oids',[True]),('role_contract',False),('permissive',1)):
            data=copy.deepcopy(base);data[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):catalog.verify_policy_records(data,base)
        extra=dict(base[0],policy_oid=9999,policy_name='unexpected')
        with self.assertRaises(ValueError):catalog.verify_policy_records(base+[extra],base)
        # A name CASE in the projection binds role identity; the inventory WHERE
        # must never filter unexpected policy names out of the returned rows.
        inventory_filter=catalog.POLICY_SQL.split(" WHERE n.nspname='public'",1)[1]
        self.assertNotIn('polname',inventory_filter)
        self.assertIn('p.polqual::pg_catalog.text',catalog.POLICY_SQL)
        self.assertNotIn('WHERE n.nspname',catalog.ALL_POLICY_SQL)
        self.assertNotIn('c.relname IN',catalog.ALL_POLICY_SQL)
        for field,value in (('command','d'),('permissive',True),('check_tree',None)):
            data=copy.deepcopy(base);data[0][field]=value
            with self.subTest(proposed_contract=field),self.assertRaises(ValueError):
                catalog.verify_policy_records(data,data)

    def test_changed_migration_pin(self):
        content=(ROOT/runner.MIGRATION_PATH).read_bytes().replace(b'\r\n',b'\n')
        actual=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        self.assertEqual(actual,runner.MIGRATION_BLOB)
        self.assertNotEqual(actual,'0e2cf9e7cefcb40110359eded43e48a3e74f67d7')

    def test_production_no_formatter_or_deparser_path(self):
        import ast
        forbidden=('oidvectortypes','regtype','regclass','pg_policies','pg_get_expr','pg_get_viewdef',"NOT LIKE 'pg_%'")
        for name in ('services/api/infrastructure/apply_step7_atomic.py',runner.MIGRATION_PATH,
                     'services/api/src/jous_api/database.py','services/api/src/jous_api/step7_catalog.py',
                     'tests/validate_managed_runtime_security.py'):
            content=(ROOT/name).read_text()
            for pattern in forbidden:
                with self.subTest(name=name,pattern=pattern):self.assertNotIn(pattern,content)
        # Historical patterns are permitted only while both legacy CLI entry
        # points stop unconditionally before any work, not as alternate guards.
        for name in ('validate_managed_access.py','validate_managed_migrations.py'):
            tree=ast.parse((ROOT/'tests'/name).read_text())
            main=next(node for node in tree.body if isinstance(node,ast.AsyncFunctionDef)
                      and node.name=='main')
            self.assertIsInstance(main.body[0],ast.Raise)
            self.assertIn('retired',ast.unparse(main.body[0]))
