"""Guarded synthetic mutation coverage for the final contract; no live I/O."""
import copy
import hashlib
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_step7_atomic_runner as fixture

r=fixture.runner
f=r.execution_contract()

class M1Tests(unittest.TestCase):
    def base(self): return json.loads((fixture.ROOT/r.MANIFEST_PATH).read_bytes())
    def test_exact(self):
        b=f.apply_m1(self.base());self.assertIs(b['referent_bindings']['operators'][0]['oprcanhash'],False)
        r.parse_manifest(f.canonical(b))
    def test_artifact_mutations(self):
        m=f.load(f.M1_PATH,f.M1_SHA)
        changes=[('oprcanmerge',True),('oprcanhash',True),('oprcanmerge',0),('oprcanhash',1)]
        for key,v in changes:
            changed=copy.deepcopy(m);changed['add_fields'][key]=v
            with self.subTest(key=key,value=v),patch.object(f,'load',return_value=changed),self.assertRaises(f.ContractRejected):f.apply_m1(self.base())
        for change in [lambda x:x['add_fields'].pop('oprcanmerge'),
                       lambda x:x.update(evidence_sha256='0'*64),
                       lambda x:x['observation'].update(operator_oid=515),
                       lambda x:x['add_fields'].update(oprname='+')]:
            changed=copy.deepcopy(m);change(changed)
            with patch.object(f,'load',return_value=changed),self.assertRaises(f.ContractRejected):f.apply_m1(self.base())
    def test_existing_field_overwrite(self):
        for change in [lambda x:x['referent_bindings']['operators'][0].update(oprname='+'),
                       lambda x:x['referent_bindings']['operators'][0].update(oprcanmerge=False),
                       lambda x:x['referent_bindings']['operators'].append(copy.deepcopy(x['referent_bindings']['operators'][0]))]:
            b=self.base();change(b)
            with self.assertRaises(f.ContractRejected):f.apply_m1(b)
    def test_hash_before_parse(self):
        original=Path.read_bytes
        with patch.object(Path,'read_bytes',lambda p:original(p)+b' ' if p.name.endswith('operator514_amendment.json') else original(p)):
            with self.assertRaisesRegex(f.ContractRejected,'^CONTRACT_HASH$'):f.apply_m1(self.base())
    def test_duplicate_nonfinite_and_unknown(self):
        for raw in [b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":Infinity}']:
            with self.assertRaises(f.ContractRejected):f.parse(raw)
        m=f.load(f.M1_PATH,f.M1_SHA);m['unknown']=False
        with patch.object(f,'load',return_value=m),self.assertRaisesRegex(f.ContractRejected,'M1_SCHEMA'):f.apply_m1(self.base())

class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.contract=f.load_final_contract();self.data=f._read(self.contract,f.ApprovedFinalContract)
        self.material=copy.deepcopy(fixture.final_material(False))
        self.query=lambda c,sql,params=None:copy.deepcopy(self.material[sql])
    def pair(self):
        e=f.freeze_pre_migration_bindings(None,self.contract,self.query)
        h=f.verify_created_security_objects(None,self.contract,e,self.query)
        return e,h
    def policies(self):
        e,h=self.pair();expected=f.instantiate_policy_expectations(self.contract,e,h)
        rows=[dict(row,policy_oid=1000+i) for i,row in enumerate(f._read(expected,f.ExpectedPolicySet))]
        return expected,rows
    def test_all_templates_and_slots(self):
        self.assertEqual(len(self.data['templates']),19)
        self.assertEqual(sum(len(t['slots']) for t in self.data['templates']),31)
        self.assertEqual(sum(p['qual_template'] is None or p['with_check_template'] is None for p in self.data['policies']),7)
        expected,rows=self.policies();f.verify_policy_rows(expected,f._issue(f.ObservedPolicySet,rows))
    def test_each_slot_original_mutation(self):
        for i,t in enumerate(self.data['templates']):
            for j,_ in enumerate(t['slots']):
                data=copy.deepcopy(self.data);data['templates'][i]['slots'][j]['original_decimal']='99999'
                with self.subTest(template=i,slot=j),self.assertRaisesRegex(f.ContractRejected,'POLICY_TEMPLATE_MISMATCH'):f.validate_templates(data)
    def test_slot_context_offset_length_and_overlap(self):
        i=next(i for i,t in enumerate(self.data['templates']) if len(t['slots'])>1)
        for field,value in [('context_before','wrong'),('context_after','wrong'),('offset',0),('offset',True),('length',0),('length',999999),('binding','policy:unknown')]:
            data=copy.deepcopy(self.data);data['templates'][i]['slots'][0][field]=value
            with self.subTest(field=field),self.assertRaises(f.ContractRejected):f.validate_templates(data)
        for action in ['remove','duplicate','overlap']:
            data=copy.deepcopy(self.data);slots=data['templates'][i]['slots']
            if action=='remove':slots.pop()
            elif action=='duplicate':slots.append(copy.deepcopy(slots[0]))
            else:slots[1]['offset']=slots[0]['offset']
            with self.subTest(action=action),self.assertRaises(f.ContractRejected):
                # Loader enforces global count as well as slot validation.
                with patch.object(f,'load',return_value=data):f.load_final_contract()
    def test_shorter_longer_and_invalid_oid(self):
        for value in [1,4294967295]:
            e,h=self.pair();b=f._read(e,f.VerifiedExistingBindings);b['relations'][0]['oid']=value
            e=f._issue(f.VerifiedExistingBindings,b)
            hdata=f._read(h,f.VerifiedCreatedBindings);hdata['existing_sha256']=hashlib.sha256(e.payload).hexdigest()
            h=f._issue(f.VerifiedCreatedBindings,hdata)
            expected=f.instantiate_policy_expectations(self.contract,e,h)
            self.assertEqual(len(f._read(expected,f.ExpectedPolicySet)),13)
        for value in [0,-1,4294967296,True]:
            self.material[f.CREATED_SQL][1]['oid']=value
            with self.subTest(value=value),self.assertRaises(f.ContractRejected):self.pair()
    def test_hash_parent_and_missing_referents(self):
        original=Path.read_bytes
        with patch.object(Path,'read_bytes',lambda p:original(p)+b' ' if p.name.endswith('policy_template_contract.json') else original(p)):
            with self.assertRaisesRegex(f.ContractRejected,'CONTRACT_HASH'):f.load_final_contract()
        for action in [lambda d:d['parents'].update(base='0'*64),lambda d:d.pop('builtins'),
                       lambda d:d['builtins'].pop('functions'),lambda d:d.update(migration_execution_approved=True)]:
            data=copy.deepcopy(self.data);action(data)
            with patch.object(f,'load',return_value=data),self.assertRaises(f.ContractRejected):f.load_final_contract()
    def test_builtin_each_oid_and_identity(self):
        for kind,entries in self.data['builtins'].items():
            for i,row in enumerate(entries):
                for field,value in [('oid',4294967295),('schema','public')]:
                    actual=fixture.builtin_observations();actual[kind][i][field]=value
                    with self.subTest(kind=kind,oid=row['oid'],field=field),self.assertRaises(f.ContractRejected):f.verify_builtins(actual,self.data['builtins'])
    def test_builtin_every_metadata_field(self):
        for kind,entries in self.data['builtins'].items():
            for i,row in enumerate(entries):
                for field,value in row.items():
                    if field=='oid':continue
                    changed=not value if type(value) is bool else value+1 if type(value) is int else 'mutated'
                    actual=fixture.builtin_observations();actual[kind][i][field]=changed
                    with self.subTest(kind=kind,oid=row['oid'],field=field),self.assertRaises(f.ContractRejected):f.verify_builtins(actual,self.data['builtins'])
    def test_builtin_missing_duplicate_unexpected(self):
        for kind in self.data['builtins']:
            for mode in ['missing','duplicate','unexpected']:
                actual=fixture.builtin_observations()
                if mode=='missing':actual[kind].pop()
                elif mode=='duplicate':actual[kind].append(copy.deepcopy(actual[kind][0]))
                else:actual[kind].append(dict(actual[kind][0],oid=4294967295))
                with self.subTest(kind=kind,mode=mode),self.assertRaisesRegex(f.ContractRejected,'BUILTIN_REFERENT_'+mode.upper()):f.verify_builtins(actual,self.data['builtins'])
    def test_type_io_first_failure(self):
        actual=fixture.builtin_observations();next(t for t in actual['types'] if t['oid']==2950)['typinput']=47
        with self.assertRaisesRegex(f.ContractRejected,'^TYPE_IO_LINKAGE_MISMATCH$'):f.verify_builtins(actual,self.data['builtins'])
    def test_relation_fields(self):
        for field,value in [('oid',201),('owner_oid',51),('owner','other'),('relkind','v'),
                            ('relpersistence','u'),('relispartition',True),('inheritance',True),
                            ('relrowsecurity',False),('relforcerowsecurity',True)]:
            original=self.material[f.RELATION_SQL][0][field];self.material[f.RELATION_SQL][0][field]=value
            with self.subTest(field=field),self.assertRaises(f.ContractRejected):self.pair()
            self.material[f.RELATION_SQL][0][field]=original
    def test_column_every_field(self):
        fields={'attnum':2,'attname':'renamed','atttypid':25,'atttypmod':36,'attcollation':100,
            'attnotnull':False,'attisdropped':True,'attidentity':'a','attgenerated':'s','has_default':True}
        for field,value in fields.items():
            old=self.material[f.COLUMN_SQL][0][field];self.material[f.COLUMN_SQL][0][field]=value
            with self.subTest(field=field),self.assertRaises(f.ContractRejected):self.pair()
            self.material[f.COLUMN_SQL][0][field]=old
    def test_column_add_remove_and_same_type_exchange(self):
        original=copy.deepcopy(self.material[f.COLUMN_SQL])
        for action in ['add','remove','exchange']:
            cols=copy.deepcopy(original)
            if action=='add':cols.append(dict(cols[0],attnum=8))
            elif action=='remove':cols.pop(0)
            else:cols[3]['attname'],cols[4]['attname']=cols[4]['attname'],cols[3]['attname']
            self.material[f.COLUMN_SQL]=cols
            with self.subTest(action=action),self.assertRaises(f.ContractRejected):self.pair()
        self.material[f.COLUMN_SQL]=original
    def test_context_mutations(self):
        for field,value in [('server_version','17.10'),('server_version_num',170012),('datcollversion','153.14'),('datname','other')]:
            old=self.material[f.TARGET_SQL][0][field];self.material[f.TARGET_SQL][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(f.ContractRejected,'TARGET_CONTEXT_MISMATCH'):self.pair()
            self.material[f.TARGET_SQL][0][field]=old
    def test_created_metadata_and_acl(self):
        for field,value in [('prosrc','changed'),('oid',0),('namespace_oid',0),('proowner',51),('prolang',12),('provariadic',25),('prosecdef',False)]:
            old=self.material[f.CREATED_SQL][0][field];self.material[f.CREATED_SQL][0][field]=value
            with self.subTest(field=field),self.assertRaises(f.ContractRejected):self.pair()
            self.material[f.CREATED_SQL][0][field]=old
        self.material[f.CREATED_ACL_SQL].append(dict(self.material[f.CREATED_ACL_SQL][0],grantee=0))
        with self.assertRaisesRegex(f.ContractRejected,'HELPER_ACL'):self.pair()
    def test_policy_every_metadata_and_raw_field(self):
        expected,rows=self.policies()
        for field,value in [('relation_oid',999),('relation_name','other'),('owner_oid',51),('namespace','other'),
            ('policy_name','other'),('command','d'),('permissive',True),('role_oids',[50]),('role_contract',False),
            ('using_tree','one byte changed'),('check_tree',None)]:
            actual=copy.deepcopy(rows);actual[0][field]=value
            with self.subTest(field=field),self.assertRaises(f.ContractRejected):f.verify_policy_rows(expected,f._issue(f.ObservedPolicySet,actual))
    def test_policy_missing_extra_duplicate_and_replacement(self):
        expected,rows=self.policies()
        for action in ['missing','extra','duplicate','replacement','oid_collision']:
            actual=copy.deepcopy(rows)
            if action=='missing':actual.pop()
            elif action=='extra':actual.append(dict(actual[0],policy_oid=99999,policy_name='unknown'))
            elif action=='duplicate':actual[-1]=copy.deepcopy(actual[0])
            elif action=='replacement':actual[0]['policy_name']='replacement'
            else:actual[1]['policy_oid']=actual[0]['policy_oid']
            with self.subTest(action=action),self.assertRaisesRegex(f.ContractRejected,'POLICY_INVENTORY_MISMATCH'):f.verify_policy_rows(expected,f._issue(f.ObservedPolicySet,actual))
    def test_policy_oid_continuity(self):
        expected,rows=self.policies();continuity=f.verify_policy_rows(expected,f._issue(f.ObservedPolicySet,rows))
        rows[0]['policy_oid']=99999
        with self.assertRaisesRegex(f.ContractRejected,'POLICY_CONTINUITY_MISMATCH'):f.verify_policy_rows(expected,f._issue(f.ObservedPolicySet,rows),continuity)
    def test_raw_rte_bitmap_and_null_mutations(self):
        expected,rows=self.policies()
        for token in [':relid ',':selectedCols ',':eref ',':opno ']:
            actual=copy.deepcopy(rows);row=next(x for x in actual if token in (x['using_tree'] or ''))
            row['using_tree']=row['using_tree'].replace(token,token+'X',1)
            with self.subTest(token=token),self.assertRaisesRegex(f.ContractRejected,'POLICY_TEMPLATE_MISMATCH'):f.verify_policy_rows(expected,f._issue(f.ObservedPolicySet,actual))
        for i,row in enumerate(rows):
            for key in ['using_tree','check_tree']:
                actual=copy.deepcopy(rows);actual[i][key]=None if row[key] is not None else 'non-null'
                with self.subTest(i=i,key=key),self.assertRaises(f.ContractRejected):f.verify_policy_rows(expected,f._issue(f.ObservedPolicySet,actual))
    def test_no_self_learning_or_forged_binding(self):
        e,h=self.pair();expected,rows=self.policies();actual=f._issue(f.ObservedPolicySet,rows)
        for args in [(actual,e,h),(self.contract,actual,h),(self.contract,e,actual),
                     (f.ApprovedFinalContract(self.contract.payload),e,h),
                     (self.contract,f.VerifiedExistingBindings(e.payload),h)]:
            with self.assertRaisesRegex(f.ContractRejected,'BINDING_TRUST_TYPE'):f.instantiate_policy_expectations(*args)
        with self.assertRaises(f.ContractRejected):f.verify_policy_rows(actual,actual)
    def test_revalidate_two_pass_and_historical_injection(self):
        e,h=self.pair();self.material[f.RELATION_SQL]=copy.deepcopy(fixture.final_material(True)[f.RELATION_SQL])
        f.revalidate_existing_bindings(None,self.contract,e,self.query)
        self.material[f.RELATION_SQL][0]['oid']=16483
        with self.assertRaises(f.ContractRejected):f.revalidate_existing_bindings(None,self.contract,e,self.query)
    def test_bitmap_offset_and_io_contract_mutation(self):
        for section,field,value,gate in [('bitmap','offset',8,'PERMISSION_BITMAP_MISMATCH'),
            ('io','io_parameter',0,'TYPE_IO_LINKAGE_MISMATCH'),
            ('io','output_typmod',36,'TYPE_IO_LINKAGE_MISMATCH')]:
            data=copy.deepcopy(self.data);data[section][field]=value
            with self.subTest(section=section,field=field),patch.object(f,'load',return_value=data),self.assertRaisesRegex(f.ContractRejected,gate):f.load_final_contract()
    def test_both_historical_fixture_clause_bytes(self):
        # Independent actual bytes come from frozen historical data, never the instantiator.
        golden=json.loads((fixture.ROOT/'docs/decisions/JOUS.CORE.1A.step7-post0002-policy-golden-candidate.json').read_bytes())
        for index,fixture_data in enumerate(golden['fixtures']):
            material=copy.deepcopy(self.material);bindings=golden['bindings']['fixture'+str(index+1)]
            role_ids={name:bindings['role:'+name] for name in ['postgres','jous_runtime','jous_security_reader']}
            material[f.ROLE_SQL]=[dict(oid=i,rolname=n) for n,i in role_ids.items()]
            oidmap={}
            for row in material[f.RELATION_SQL]:
                old=row['oid'];row['oid']=bindings['relation:'+row['name']];oidmap[old]=row['oid'];row['owner_oid']=role_ids['postgres']
            for col in material[f.COLUMN_SQL]:col['attrelid']=oidmap[col['attrelid']]
            for row in material[f.CREATED_SQL]:
                row['oid']=bindings['helper:'+row['proname']];row['namespace_oid']=bindings['namespace:jous_security']
                row['nspowner']=role_ids['postgres'];row['proowner']=role_ids['jous_security_reader']
            for row in material[f.CREATED_ACL_SQL]:
                row['grantor']=role_ids['jous_security_reader'];row['grantee']=role_ids['jous_runtime'] if row['grantee']==51 else role_ids['jous_security_reader']
            for row in material[f.CREATED_SCHEMA_ACL_SQL]:row['grantee']=role_ids['jous_runtime'] if row['grantee']==51 else role_ids['jous_security_reader']
            query=lambda c,sql,params=None:copy.deepcopy(material[sql])
            existing=f.freeze_pre_migration_bindings(None,self.contract,query)
            created=f.verify_created_security_objects(None,self.contract,existing,query)
            expected=f._read(f.instantiate_policy_expectations(self.contract,existing,created),f.ExpectedPolicySet)
            actual={(p['relname'],p['polname']):p for p in fixture_data['policies']}
            for row in expected:
                historic=actual[(row['relation_name'],row['policy_name'])]
                with self.subTest(fixture=index,policy=row['policy_name']):
                    self.assertEqual(row['using_tree'],historic['qual'])
                    self.assertEqual(row['check_tree'],historic['with_check'])

    def test_no_production_optional_contract(self):
        self.assertIn('execution_contract().load_final_contract()',inspect.getsource(r.public_contract))
        self.assertNotIn('APPROVED_POLICY_CONTRACT',inspect.getsource(r.verify_security))
        self.assertNotIn('amendment_candidate',inspect.getsource(r.public_contract))
        self.assertEqual(list(inspect.signature(r.public_contract).parameters),[])

class FinalLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_policy_failure_rolls_back(self):
        catalog=fixture.Catalog();catalog.overrides['SELECT p.oid AS policy_oid']=[]
        connection=fixture.AsyncConnection(catalog);engine=fixture.EngineFake(connection)
        with self.assertRaisesRegex(r.Stop,'ROLLED_BACK'):
            await fixture.execute_test(engine,lambda c:fixture.PIPELINE(c,migrate=lambda c:setattr(c,'migrated',True)))
        self.assertNotIn('commit',connection.events);self.assertEqual(connection.events.count('rollback'),1)
    async def test_second_pass_failure_rolls_back(self):
        catalog=fixture.Catalog();connection=fixture.AsyncConnection(catalog);engine=fixture.EngineFake(connection)
        calls=0
        def verify(c,b):
            nonlocal calls
            calls+=1
            if calls==2:
                changed=fixture.synthetic_policies(c.module);changed[0]['policy_oid']=99999
                c.overrides['SELECT p.oid AS policy_oid']=changed
            r.verify_security(c,b)
        with self.assertRaisesRegex(r.Stop,'ROLLED_BACK'):
            await fixture.execute_test(engine,lambda c:fixture.PIPELINE(c,migrate=lambda c:setattr(c,'migrated',True),verify=verify))
        self.assertEqual(calls,2);self.assertFalse(catalog.temp);self.assertNotIn('commit',connection.events)
    async def test_success_single_commit(self):
        catalog=fixture.Catalog();connection=fixture.AsyncConnection(catalog);engine=fixture.EngineFake(connection)
        self.assertEqual(await fixture.execute_test(engine,lambda c:fixture.PIPELINE(c,migrate=lambda c:setattr(c,'migrated',True))),'COMMITTED')
        self.assertEqual(connection.events.count('commit'),1);self.assertFalse(catalog.temp)
