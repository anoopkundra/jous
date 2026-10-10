"""F1/F2/F3 authority tests separate from verifier mutation tests; offline only."""
import copy
import hashlib
import inspect
import json
import unittest
from unittest.mock import patch
import step7_catalog_observations as independent
import step7_bki_regenerate as generator
import test_step7_atomic_runner as fixture

f=fixture.runner.execution_contract()

class CatalogRemediationTests(unittest.TestCase):
    def setUp(self):
        self.actual=independent.observations()
        self.data=f._read(f.load_final_contract(),f.ApprovedFinalContract)
        self.expected=self.data['builtins']
    def reject_actual(self,kind,key,value,oid=None):
        actual=copy.deepcopy(self.actual)
        row=next(r for r in actual[kind] if r['oid']==oid) if oid else actual[kind][0]
        row[key]=value
        with self.assertRaisesRegex(f.ContractRejected,'^BUILTIN_REFERENT_MISMATCH$'):
            f.verify_builtins(actual,self.expected)
    def reject_expected(self,kind,key,value,oid=None,gate='BUILTIN_EXPECTED_DOMAIN'):
        data=copy.deepcopy(self.data)
        row=next(r for r in data['builtins'][kind] if r['oid']==oid) if oid else data['builtins'][kind][0]
        row[key]=value
        with patch.object(f,'load',return_value=data),self.assertRaisesRegex(f.ContractRejected,'^'+gate+'$'):
            f.load_final_contract()
    # Authority/correctness: these values come from retained source, never from the policy artifact.
    def test_independent_fixture_against_pinned_bki(self):
        self.assertEqual(independent.from_authority(),self.actual)
        functions=self.actual['functions'];internal=next(t for t in self.actual['types'] if t['oid']==2281)
        self.assertTrue(all(type(p['prokind']) is str and p['prokind']=='f' and p['proowner']==10 for p in functions))
        self.assertEqual((internal['typlen'],internal['typalign']),(8,'d'))
    def test_independent_authority_agrees_with_contract(self):
        authority=independent.from_authority()
        f.verify_builtins(authority,self.expected)
    def test_bootstrap_owner_and_managed_stable_name_authority(self):
        receipt=json.loads((independent.ROOT/'AUTHORITY.json').read_bytes())
        binding=receipt['owner_name_authority']
        raw=(fixture.ROOT/fixture.runner.MANIFEST_PATH).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),binding['base_sha256'])
        proc=next(p for p in json.loads(raw)['referent_bindings']['functions'] if p['oid']==141)
        self.assertEqual((proc['proowner'],proc['owner']),(10,'supabase_admin'))
        for kind,field in [('types','typowner'),('functions','proowner'),('operators','oprowner'),('collations','collowner')]:
            self.assertTrue(all(row[field]==10 and row['owner']=='supabase_admin' for row in self.actual[kind]))
    def test_generator_field_aware_and_reproducible(self):
        self.assertEqual(generator.regenerate(self.data),self.data)
        raw=generator.catalog('pg_proc',{65})[65]
        self.assertEqual(raw['prokind'],'f');self.assertIs(raw['prosecdef'],False)
        raw=generator.catalog('pg_type',{2281})[2281]
        self.assertEqual((raw['typlen'],raw['typalign']),(8,'d'))
    def test_generator_unresolved_macro_rejected(self):
        original=generator.EVIDENCE
        original_read=type(original).read_text
        def read(path,*args,**kwargs):
            raw=original_read(path,*args,**kwargs)
            return raw.replace('SIZEOF_POINTER','UNAPPROVED_POINTER') if path.name=='postgres.bki' else raw
        with patch.object(type(original),'read_text',read),self.assertRaisesRegex(ValueError,'BKI_INTEGER_OR_MACRO'):
            generator.catalog('pg_type',{2281})
    def test_only_approved_semantic_artifact_changes(self):
        old=copy.deepcopy(self.data)
        for kind,rows in old['builtins'].items():
            for row in rows:
                row.pop('owner');row.pop({'types':'typowner','functions':'proowner','operators':'oprowner','collations':'collowner'}[kind])
                if kind=='functions':row['prokind']=False
                if kind=='types' and row['oid']==2281:row.update(typlen='SIZEOF_POINTER',typalign='ALIGNOF_POINTER')
        old['provenance']=old['provenance'][:-3]
        hashes={hashlib.sha256((json.dumps(old,sort_keys=True,indent=i,separators=s,ensure_ascii=False)+n).encode()).hexdigest()
            for i in (None,2) for s in (None,(',',':')) for n in ('','\n')}
        self.assertIn('c17babca210ee9679549c56e36259bc0b04d5c8731484b34e2a9e323bd7ad99d',hashes)
    # Verifier mutation: independent actual fixture must match the production contract exactly.
    def test_correct_query_representations_pass(self):
        f.verify_builtins(self.actual,self.expected)
        self.assertIn('p.prokind::text AS prokind',f.FUNCTION_SQL)
        for sql,owner in [(f.TYPE_SQL,'typowner'),(f.FUNCTION_SQL,'proowner'),(f.OPERATOR_SQL,'oprowner'),(f.COLLATION_SQL,'collowner')]:
            self.assertIn(owner,sql);self.assertIn('pg_catalog.pg_roles',sql);self.assertIn('AS owner',sql)
    def test_actual_false_true_wrong_prokind_rejected(self):
        for value in (False,True,'p','x',None):
            with self.subTest(value=value):self.reject_actual('functions','prokind',value)
    def test_expected_false_true_wrong_prokind_before_credentials(self):
        for value in (False,True,'p','ff',None):
            with self.subTest(value=value):self.reject_expected('functions','prokind',value)
    def test_actual_pointer_macros_and_wrong_values_rejected(self):
        for key,value in [('typlen','SIZEOF_POINTER'),('typalign','ALIGNOF_POINTER'),('typlen',4),('typalign','i')]:
            with self.subTest(key=key,value=value):self.reject_actual('types',key,value,2281)
    def test_expected_pointer_macros_and_wrong_values_rejected(self):
        for key,value in [('typlen','SIZEOF_POINTER'),('typalign','ALIGNOF_POINTER'),('typlen',4),('typalign','i'),('typlen',True)]:
            with self.subTest(key=key,value=value):self.reject_expected('types',key,value,2281)
    def test_representative_boolean_char_integer_domains(self):
        for kind,key,value in [('functions','prosecdef',0),('functions','prosecdef','f'),('types','typalign',False),('types','typlen',True)]:
            with self.subTest(kind=kind,key=key):self.reject_expected(kind,key,value)
    def test_every_function_owner_mutation_rejected(self):
        for row in self.actual['functions']:
            for key,value in [('proowner',16388),('owner','postgres')]:
                with self.subTest(oid=row['oid'],key=key):self.reject_actual('functions',key,value,row['oid'])
    def test_missing_function_owner_rejected(self):
        for key in ('proowner','owner'):
            actual=copy.deepcopy(self.actual);actual['functions'][0].pop(key)
            with self.assertRaisesRegex(f.ContractRejected,'BUILTIN_REFERENT_MISMATCH'):f.verify_builtins(actual,self.expected)
    def test_observed_owner_cannot_establish_expected_owner(self):
        for key,value in [('proowner',16388),('owner','postgres')]:
            self.reject_expected('functions',key,value,gate='BUILTIN_EXPECTED_OWNER')
    def test_other_builtin_owners_enforced(self):
        for kind,key in [('types','typowner'),('operators','oprowner'),('collations','collowner')]:
            with self.subTest(kind=kind):self.reject_actual(kind,key,16388)
    def test_expected_only_mutation_caught_by_authority(self):
        for key,value in [('prokind',False),('proowner',16388)]:
            expected=copy.deepcopy(self.expected);expected['functions'][0][key]=value
            with self.assertRaisesRegex(f.ContractRejected,'BUILTIN_REFERENT_MISMATCH'):f.verify_builtins(self.actual,expected)
    def test_mock_only_mutation_fails_verifier(self):
        self.reject_actual('functions','prosrc','wrong_internal_symbol')
    def test_expected_actual_do_not_share_mutable_objects(self):
        material=fixture.final_material(False)
        self.assertIsNot(material[f.FUNCTION_SQL],self.expected['functions'])
        before=copy.deepcopy(self.expected)
        self.actual['functions'][0]['prokind']='p'
        self.assertEqual(self.expected,before)
        self.assertEqual(independent.observations()['functions'][0]['prokind'],'f')
        self.assertNotIn("d['builtins']",inspect.getsource(fixture.final_material))
    def test_impossible_expected_fails_before_lifecycle(self):
        data=copy.deepcopy(self.data);data['builtins']['functions'][0]['prokind']=False
        with patch.object(f,'load',return_value=data),self.assertRaisesRegex(f.ContractRejected,'BUILTIN_EXPECTED_DOMAIN'):
            fixture.runner.public_contract()
    def test_no_installed_postgresql_test_dependency(self):
        self.assertNotIn('C:/Program Files',inspect.getsource(independent))
        self.assertNotIn('step7_bki_regenerate',inspect.getsource(independent))
    def test_frozen_inputs_unchanged(self):
        receipt=json.loads((independent.ROOT/'AUTHORITY.json').read_bytes())
        for path,sha in receipt['frozen_inputs'].items():
            self.assertEqual(hashlib.sha256((fixture.ROOT/path).read_bytes()).hexdigest(),sha,path)
