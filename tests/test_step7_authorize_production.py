"""Independent catalog mutations through the mandatory production gate."""
import copy
import inspect
from pathlib import Path
import unittest
from unittest.mock import patch

import test_step7_atomic_runner as fixture

r = fixture.runner


class ProductionAuthorizeTests(unittest.TestCase):
    def reject(self, mutation, gate):
        c = fixture.PublicCatalog()
        mutation(c)
        with self.assertRaisesRegex(r.Stop, '^'+gate+'$'):
            r.verify_public_compatibility(c)

    def test_exact_97_production_success(self):
        result=r.verify_public_compatibility(fixture.PublicCatalog())
        self.assertEqual(len(result['routines']),97)

    def test_old_96_rejected(self):
        self.reject(lambda c:c.routines.remove(next(x for x in c.routines if
            x['schema']=='realtime' and x['name']=='authorize')), 'PUBLIC_ROUTINES_SET')

    def test_identity_only_partial_snapshot_rejected(self):
        self.reject(lambda c:c.supplement.update(core=[]), 'AUTHORIZE_CORE')

    def test_missing_reachability_rejected(self):
        self.reject(lambda c:c.supplement.update(reachability=[]), 'AUTHORIZE_REACHABILITY')

    def test_supplement_verifier_cannot_be_skipped(self):
        c=fixture.PublicCatalog()
        with patch.object(r,'authorize_contract',side_effect=r.Stop('SUPPLEMENT_REQUIRED')):
            with self.assertRaisesRegex(r.Stop,'^SUPPLEMENT_REQUIRED$'):r.verify_public_compatibility(c)

    def test_supplement_hash_before_parse(self):
        original=Path.read_bytes
        def changed(path):
            data=original(path)
            return data+b' ' if path.name=='step7_realtime_authorize_amendment.json' else data
        c=fixture.PublicCatalog()
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(r.Stop,'^AMENDMENT_HASH$'):r.verify_public_compatibility(c)

    def test_base_hash_before_parse(self):
        original=Path.read_bytes
        def changed(path):
            data=original(path)
            return data+b' ' if path.name=='step7_public_compat_manifest.json' else data
        c=fixture.PublicCatalog()
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(r.Stop,'^MANIFEST_HASH$'):r.verify_public_compatibility(c)

    def test_no_optional_flags_or_public_legacy_comparator(self):
        self.assertEqual(list(inspect.signature(r.verify_public_compatibility).parameters),['c'])
        self.assertFalse(hasattr(r,'compare_public_inventory'))
        self.assertIn('verify_public_compatibility(c)',inspect.getsource(r.verify_grants))
        self.assertIn('verify_public_compatibility(c)',inspect.getsource(r.verify_routines))

    def test_independent_acl_field_mutations(self):
        for field,value in (('grantee',17756),('grantee_name','jous_runtime'),
                ('grantor',16388),('grantor_name','postgres'),
                ('privilege_type','USAGE'),('is_grantable',True)):
            with self.subTest(field=field):
                self.reject(lambda c:c.supplement['routine_acl_effective'][0].update({field:value}),
                            'AUTHORIZE_ROUTINE_ACL_EFFECTIVE')

    def test_acl_add_remove_duplicate(self):
        for action in ('add','remove','duplicate'):
            def mutate(c):
                rows=c.supplement['routine_acl_effective']
                if action=='remove':rows.pop()
                elif action=='duplicate':rows.append(copy.deepcopy(rows[0]))
                else:
                    row=copy.deepcopy(rows[0]);row.update(grantee=17756,grantee_name='jous_runtime');rows.append(row)
            with self.subTest(action=action):self.reject(mutate,'AUTHORIZE_ROUTINE_ACL_EFFECTIVE')

    def test_independent_dependency_field_mutations(self):
        for field,value in (('refclassid',1255),('refobjid',17784),('deptype','e')):
            with self.subTest(field=field):
                self.reject(lambda c:c.supplement['dependencies'][0].update({field:value}),
                            'AUTHORIZE_DEPENDENCIES')

    def test_dependency_add_remove_extension(self):
        for action in ('add','remove','extension'):
            def mutate(c):
                rows=c.supplement['dependencies']
                if action=='remove':rows.pop()
                else:
                    row=copy.deepcopy(rows[0])
                    if action=='extension':row.update(refclassid=3079,refobjid=1,deptype='e')
                    rows.append(row)
            with self.subTest(action=action):self.reject(mutate,'AUTHORIZE_DEPENDENCIES')

    def test_unresolved_dependency_binding(self):
        self.reject(lambda c:c.supplement['dependency_bindings'][0].update(rows=[]),
                    'AUTHORIZE_DEPENDENCY_BINDINGS')

    def test_independent_body_changes(self):
        for action in ('byte','whitespace','crlf','unicode','null','missing'):
            def mutate(c):
                core=c.supplement['core'][0];source=core['prosrc']
                if action=='missing':core.pop('prosrc')
                elif action=='null':core['prosrc']=None
                elif action=='crlf':core['prosrc']=source.replace('\n','\r\n')
                elif action=='unicode':core['prosrc']=source+'\u0130'
                elif action=='whitespace':core['prosrc']=source+' '
                else:core['prosrc']='X'+source[1:]
            with self.subTest(action=action):self.reject(mutate,'AUTHORIZE_CORE')

    def test_hash_cannot_substitute_for_mutated_source(self):
        # Keeping the approved claimed hash does not save mutated source bytes.
        self.reject(lambda c:c.supplement['core'][0].update(prosrc='changed'), 'AUTHORIZE_CORE')

    def test_independent_inventory_mutations(self):
        for action in ('original_missing','authorize_missing','unknown','duplicate','identity'):
            def mutate(c):
                if action=='original_missing':c.routines.remove(next(x for x in c.routines if x['schema']=='auth'))
                elif action=='authorize_missing':c.routines.remove(next(x for x in c.routines if x['name']=='authorize'))
                elif action=='identity':next(x for x in c.routines if x['name']=='authorize')['name']='authorize_new'
                else:
                    row=copy.deepcopy(c.routines[0])
                    if action=='unknown':row['name']='unknown_98th'
                    c.routines.append(row)
            with self.subTest(action=action):self.reject(mutate,'PUBLIC_ROUTINES_SET')

    def test_each_role_each_reachability_constraint(self):
        for role in ('jous_runtime','jous_security_reader'):
            for field,value in (('schema_usage',True),('routine_execute',False),
                    ('owner_member',True),('owner_set',True),('owner_inherited',True)):
                def mutate(c):next(x for x in c.supplement['reachability'] if x['rolname']==role)[field]=value
                with self.subTest(role=role,field=field):self.reject(mutate,'AUTHORIZE_REACHABILITY')

    def test_numeric_and_behavior_constraints(self):
        for field,value in (('oid',17785),('pronamespace',1),('proowner',16388),
                ('prolang',1),('prosecdef',True),('provolatile','s'),('proparallel','s'),
                ('proisstrict',True),('proleakproof',True),('proretset',True),
                ('pronargdefaults',1),('provariadic',25),('proconfig',[]),
                ('probin','other'),('prosqlbody','tree'),('prorettype',16),
                ('proargtypes',[25]),('proargmodes',['i']),('proargnames',['wrong'])):
            with self.subTest(field=field):
                self.reject(lambda c:c.supplement['core'][0].update({field:value}), 'AUTHORIZE_CORE')
