"""Offline exact-contract mutations; retained routine source is inert data."""
import copy
import hashlib
import importlib.util
import json
import unittest

import test_step7_atomic_runner as fixtures

spec = importlib.util.spec_from_file_location('authorize_amendment', fixtures.ROOT /
    'services/api/infrastructure/step7_realtime_authorize_amendment.py')
amendment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(amendment)


class AuthorizeAmendmentTests(unittest.TestCase):
    def setUp(self):
        self.contract = copy.deepcopy(amendment.load_amendment()['targeted_contract'])
        self.base_bytes = (fixtures.ROOT / fixtures.runner.MANIFEST_PATH).read_bytes()
        self.candidate = amendment.build_candidate(self.base_bytes)
        inventory = self.candidate['inventory_contract']
        self.inventory = dict(relations=copy.deepcopy(inventory['relations']),
            routines=copy.deepcopy(inventory['routines']),
            bindings=copy.deepcopy(inventory['rls_auto_enable']['bindings']))

    def reject_core(self, field, value):
        contract = copy.deepcopy(self.contract)
        contract['core'][0][field] = value
        with self.assertRaises(amendment.AmendmentRejected):
            amendment.verify_targeted_snapshot(contract)

    def verify(self):
        return amendment.verify_reviewed_inventory(self.inventory, self.contract, fixtures.runner)

    def test_exact_reviewed_97_set_accepted(self):
        result = self.verify()
        self.assertEqual(len(result['inventory_contract']['routines']), 97)
        self.assertFalse(result['execution_approved'])
        self.assertFalse(result['migration_execution_approved'])
        self.assertFalse(result['runtime_activation_approved'])
        self.assertIsNone(result['post_0002_raw_policy_contract'])

    def test_exact_stable_and_numeric_identity(self):
        core = self.contract['core'][0]
        self.assertEqual(fixtures.runner.routine_identity(amendment.routine_entry()), amendment.IDENTITY)
        self.assertEqual([core[k] for k in ('oid','pronamespace','proowner','prolang')],
                         [17784,16559,17270,13619])
        self.assertEqual(core['proargtypes'], [25]*5+[1009]*2)
        self.assertEqual(core['prorettype'], 2249)
        self.assertEqual(core['proallargtypes'][-2:], [1000,1000])
        self.assertEqual(core['proargnames'][-2:], ['read_allowed','write_allowed'])

    def test_body_hash_mismatch_rejected(self):
        self.reject_core('prosrc', self.contract['core'][0]['prosrc'] + ' ')

    def test_owner_mismatch_rejected(self):
        for field, value in (('proowner',17271), ('owner','postgres')):
            with self.subTest(field=field): self.reject_core(field,value)

    def test_namespace_mismatch_rejected(self):
        for field,value in (('pronamespace',16560), ('namespace','public')):
            with self.subTest(field=field): self.reject_core(field,value)

    def test_language_mismatch_rejected(self):
        for field,value in (('prolang',13620),('lanname','sql')):
            with self.subTest(field=field): self.reject_core(field,value)

    def test_security_definer_change_rejected(self):
        self.reject_core('prosecdef',True)

    def test_argument_return_contract_mismatch_rejected(self):
        for field,value in (('proargtypes',[25]*7),('proargmodes',['i']*9),
                ('proallargtypes',[25]*9),('proargnames',['wrong']*9),
                ('prorettype',16),('pronargdefaults',1),('provariadic',25)):
            with self.subTest(field=field): self.reject_core(field,value)

    def test_behavior_and_null_metadata_mismatch_rejected(self):
        for field,value in (('provolatile','s'),('proparallel','s'),('proisstrict',True),
                ('proleakproof',True),('proretset',True),('proconfig',[]),
                ('probin','different'),('prosqlbody','tree')):
            with self.subTest(field=field): self.reject_core(field,value)

    def test_acl_addition_rejected(self):
        self.contract['routine_acl_effective'].append(copy.deepcopy(self.contract['routine_acl_effective'][0]))
        with self.assertRaises(amendment.AmendmentRejected): self.verify()

    def test_acl_removal_rejected(self):
        self.contract['routine_acl_effective'].pop()
        with self.assertRaises(amendment.AmendmentRejected): self.verify()

    def test_acl_grant_option_change_rejected(self):
        self.contract['routine_acl_effective'][0]['is_grantable'] = True
        with self.assertRaises(amendment.AmendmentRejected): self.verify()

    def test_acl_raw_null_and_provenance_rejected(self):
        self.contract['routine_acl_raw'][0]['proacl_is_null'] = True
        self.contract['routine_acl_raw'][0]['raw_proacl'] = None
        self.contract['public_execute_provenance'] = 'DEFAULT_ACL'
        with self.assertRaises(amendment.AmendmentRejected): self.verify()

    def test_dependency_addition_rejected(self):
        self.contract['dependencies'].append(copy.deepcopy(self.contract['dependencies'][0]))
        with self.assertRaises(amendment.AmendmentRejected): self.verify()

    def test_dependency_removal_rejected(self):
        self.contract['dependencies'].pop()
        with self.assertRaises(amendment.AmendmentRejected): self.verify()

    def test_dependency_binding_unresolved_rejected(self):
        self.contract['dependency_bindings'][0]['status'] = 'UNRESOLVED'
        with self.assertRaises(amendment.AmendmentRejected): self.verify()

    def test_runtime_schema_usage_relaxation_rejected(self):
        next(x for x in self.contract['reachability'] if x['rolname']=='jous_runtime')['schema_usage'] = True
        with self.assertRaises(amendment.AmendmentRejected): self.verify()

    def test_reader_schema_usage_relaxation_rejected(self):
        next(x for x in self.contract['reachability'] if x['rolname']=='jous_security_reader')['schema_usage'] = True
        with self.assertRaises(amendment.AmendmentRejected): self.verify()

    def test_owner_membership_set_inherit_rejected(self):
        for role in ('jous_runtime','jous_security_reader'):
            for field in ('owner_member','owner_set','owner_inherited'):
                with self.subTest(role=role,field=field):
                    contract=copy.deepcopy(self.contract)
                    next(x for x in contract['reachability'] if x['rolname']==role)[field]=True
                    with self.assertRaises(amendment.AmendmentRejected):
                        amendment.verify_targeted_snapshot(contract)

    def test_unknown_98th_public_routine_rejected(self):
        extra=copy.deepcopy(self.inventory['routines'][0]);extra['name']='unknown_future'
        self.inventory['routines'].append(extra)
        with self.assertRaisesRegex(fixtures.runner.Stop,'PUBLIC_ROUTINES_SET'): self.verify()

    def test_missing_reviewed_authorize_rejected(self):
        self.inventory['routines']=[x for x in self.inventory['routines']
            if fixtures.runner.routine_identity(x)!=amendment.IDENTITY]
        with self.assertRaisesRegex(fixtures.runner.Stop,'PUBLIC_ROUTINES_SET'): self.verify()

    def test_duplicate_public_identity_rejected(self):
        self.inventory['routines'].append(copy.deepcopy(amendment.routine_entry()))
        with self.assertRaisesRegex(fixtures.runner.Stop,'PUBLIC_ROUTINES_SET'): self.verify()

    def test_inventory_body_and_schema_constraints_independently_rejected(self):
        for field,value in (('source_sha256','0'*64),('schema_usage',
                {'jous_runtime':True,'jous_security_reader':False})):
            inventory=copy.deepcopy(self.inventory)
            next(x for x in inventory['routines'] if x['name']=='authorize' and x['schema']=='realtime')[field]=value
            with self.assertRaisesRegex(fixtures.runner.Stop,'PUBLIC_ROUTINES_DRIFT'):
                amendment.verify_reviewed_inventory(inventory,self.contract,fixtures.runner)

    def test_multiset_order_is_not_authority(self):
        for key in amendment.MULTISETS: self.contract[key].reverse()
        self.verify()

    def test_strict_boolean_type_not_integer(self):
        self.contract['reachability'][0]['schema_usage']=0
        with self.assertRaises(amendment.AmendmentRejected): self.verify()

    def test_extra_and_missing_snapshot_keys_rejected(self):
        for key in ('extra','core'):
            contract=copy.deepcopy(self.contract)
            if key=='extra':contract[key]=None
            else:contract.pop(key)
            with self.assertRaises(amendment.AmendmentRejected):
                amendment.verify_targeted_snapshot(contract)

    def test_base_identity_cannot_change(self):
        with self.assertRaises(amendment.AmendmentRejected):
            amendment.build_candidate(self.base_bytes+b' ')
        self.assertEqual(hashlib.sha256(self.base_bytes).hexdigest(),amendment.BASE_SHA256)

    def test_exact_source_evidence_and_linkage(self):
        path=fixtures.ROOT/'docs/decisions/JOUS.CORE.1A.step7-realtime-authorize-candidate.json'
        original=json.loads(path.read_bytes())['lifecycle_metadata']['results']
        self.assertEqual(self.contract['core'][0]['prosrc'],original['core'][0]['prosrc'])
        self.assertEqual(hashlib.sha256(self.contract['core'][0]['prosrc'].encode()).hexdigest(),amendment.BODY_SHA256)
        self.assertEqual(self.candidate['targeted_evidence_sha256'],
            '9dc1911c466a4f9d7d22dcc936158ee23aa45b6322f49dbcf07fc8ada7e5bcca')
        self.assertEqual(self.candidate['parent_evidence_sha256'],
            '922b335f605d9f96b14791bdb2d4896d2c55f43e7ad0f0116417c54a2826ee79')
