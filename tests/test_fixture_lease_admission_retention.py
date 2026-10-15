"""Synthetic composition tests, not production-provider durability proof."""
import ast
import copy
from dataclasses import replace, FrozenInstanceError, dataclass
from enum import StrEnum
import importlib.util
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
old=runpy.run_path(str(ROOT/'tests/test_fixture_lease_admission_envelope.py'))
e,a,g,s=(old[n] for n in ('e','a','g','s'))
spec=importlib.util.spec_from_file_location('_il4a_pure.fixture_lease_admission_retention',
    ROOT/'services/api/infrastructure/fixture_lease_admission_retention.py')
r=importlib.util.module_from_spec(spec); sys.modules[spec.name]=r; spec.loader.exec_module(r)


PERMISSIONS=('current_permit_consumable','admission_coverage_confirmed','begin_permitted','transaction_owned',
    'sql_permitted','writer_admission_permitted','local_mutation_permitted','local_commit_confirmed',
    'candidate_construction_permitted','candidate_retention_permitted','publication_permitted','completion_permitted',
    'ack_construction_permitted','ack_delivery_permitted','active_permitted','retry_permitted','reacquisition_permitted',
    'fence_clearance_permitted','recovery_execution_permitted','runtime_activation_permitted')


class RetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture=old['EnvelopeTests']; fixture.setUpClass()
        cls.template=e.prepare_admission_envelope(fixture.original)
        cls.upstream=e.prepare_admission_envelope(fixture.unresolved)

    def setUp(self):
        self.prepared=r._copy(self.template)
        self.expected=r._copy(self.template)
        self.events=[]
        self.authority=r._copy(r._authority(self.expected))
        self.reference=s.EvidenceReference('externally-retained-envelope',b'e'*32)
        self.proof=s.EvidenceReference('external-retention-proof',b'q'*32)
        self.verify_error=self.retain_error=self.qualify_error=None
        self.verify_value=self.receipt_value=self.confirmation_value=None
        self.mutate=None
        self.adapter=r.TrustedRetentionAdapter(self.authority,self.verify,self.retain,self.qualify)

    def verify(self,prepared):
        self.events.append('verify')
        if self.mutate=='verify': object.__setattr__(prepared.material,'fixed_utc_us',99)
        if self.verify_error: raise self.verify_error
        if self.verify_value is not None: return self.verify_value
        return r.RetentionAuthorization(self.expected,self.expected.material.source.qualification.permit.evidence,
            self.authority,s.EvidenceValidity.VALID,self.proof)

    def receipt(self):
        bundle=self.expected.material.source.attempt.bundle
        index=r.OriginalRecordIndex(bundle.context,bundle.requester.principal,bundle.activation,
            self.expected.material.source.qualification.permit.evidence,self.reference)
        return r.RetentionReceipt(r._copy(self.expected.material),self.reference,index)

    def retain(self,material):
        self.events.append('retain')
        self.assertEqual(r._project(material),r._project(self.expected.material))
        if self.mutate=='retain': object.__setattr__(material,'fixed_utc_us',99)
        if self.retain_error: raise self.retain_error
        return self.receipt() if self.receipt_value is None else self.receipt_value

    def qualify(self,prepared,receipt):
        self.events.append('qualify')
        if self.mutate=='qualify': object.__setattr__(receipt.index,'principal','substituted')
        if self.mutate=='qualify-source': object.__setattr__(prepared.material,'fixed_utc_us',99)
        if self.qualify_error: raise self.qualify_error
        if self.confirmation_value is not None: return self.confirmation_value
        return self.confirmation(receipt)

    def confirmation(self,receipt=None,**changes):
        return replace(r.RetentionConfirmation(self.receipt() if receipt is None else receipt,self.authority,
            s.EvidenceValidity.VALID,s.EvidenceValidity.VALID,s.EvidenceValidity.VALID,self.proof),**changes)

    def run_gate(self): return r.retain_original_envelope(self.prepared,self.adapter)

    def permissions(self,result):
        for name in PERMISSIONS: self.assertIs(getattr(result,name),False)

    def test_qualified_success_exact_order(self):
        result=self.run_gate()
        self.assertIs(result.state,r.RetentionState.RETAINED)
        self.assertEqual(self.events,['verify','retain','qualify'])
        self.assertIs(type(result.envelope),s.RetainedAdmissionEnvelope)
        self.assertIs(type(result.envelope.fixing),s.RetainedTimeFixing)
        self.assertEqual(result.envelope.reference,self.reference)
        self.assertEqual(result.confirmation.receipt.index.permit,self.expected.material.source.qualification.permit.evidence)
        self.permissions(result)

    def test_fixed_time_and_both_qualification_roles_preserved(self):
        result=self.run_gate(); material=self.expected.material
        self.assertEqual(result.envelope.fixed_utc_us,material.fixed_utc_us)
        self.assertEqual(result.envelope.fixing_interval,material.evaluation.interval)
        self.assertEqual(result.envelope.time_qualification,material.sample_validation)
        self.assertNotEqual(result.envelope.time_qualification,material.acquisition_qualification)
        time=material.source.qualification.time
        self.assertEqual((result.envelope.fixing.sample,result.envelope.fixing.profile,result.envelope.fixing.point,
            result.envelope.fixing.propagation),(time.sample,time.profile,time.point,time.propagation))
        self.assertEqual(result.confirmation.receipt.material.acquisition_qualification,material.acquisition_qualification)

    def test_default_zero_calls(self):
        result=r.retain_original_envelope(self.prepared)
        self.assertIs(result.state,r.RetentionState.FAIL_CLOSED)
        self.assertEqual(self.events,[])
        self.permissions(result)

    def test_bare_material_is_not_authority(self):
        result=r.retain_original_envelope(self.prepared.material,self.adapter)
        self.assertIs(result.state,r.RetentionState.FAIL_CLOSED)
        self.assertEqual(self.events,[])

    def test_upstream_uncertainty_preserved_without_retention(self):
        result=r.retain_original_envelope(self.upstream,self.adapter)
        self.assertIs(result.state,r.RetentionState.HANDOFF)
        self.assertFalse(result.dispatched)
        self.assertEqual(self.events,[])
        self.assertEqual(result.prepared,self.upstream)
        self.permissions(result)

    def test_lost_response_none(self):
        def retain(material): self.events.append('retain'); return None
        self.adapter=r.TrustedRetentionAdapter(self.authority,self.verify,retain,self.qualify)
        self.assertIs(self.run_gate().state,r.RetentionState.HANDOFF)
        self.assertEqual(self.events,['verify','retain'])

    def test_success_detached_from_all_callback_references(self):
        result=self.run_gate()
        original=result.envelope.fixed_utc_us
        object.__setattr__(self.prepared.material,'fixed_utc_us',99)
        object.__setattr__(self.expected.material.source.qualification.permit.evidence,'identity','changed')
        object.__setattr__(self.reference,'identity','changed')
        r.RetentionResult.__post_init__(result)
        self.assertEqual(result.envelope.fixed_utc_us,original)
        self.assertEqual(result.envelope.reference.identity,'externally-retained-envelope')

    def test_result_constructor_and_replacement_rejected(self):
        with self.assertRaises(TypeError): r.RetentionResult()
        with self.assertRaises(TypeError): replace(self.run_gate(),dispatched=False)

    def test_result_immutable_and_contradiction_revalidated(self):
        result=self.run_gate()
        with self.assertRaises(FrozenInstanceError): result.dispatched=False
        object.__setattr__(result,'dispatched',False)
        with self.assertRaises(s.TimeRejected): r.RetentionResult.__post_init__(result)

    def test_internal_assertion_propagates(self):
        with patch.object(e,'_source_validate',side_effect=AssertionError('internal')):
            with self.assertRaises(AssertionError): self.run_gate()
        self.assertEqual(self.events,[])

    def test_internal_runtime_error_propagates(self):
        with patch.object(e,'_source_validate',side_effect=RuntimeError('internal')):
            with self.assertRaises(RuntimeError): self.run_gate()
        self.assertEqual(self.events,[])

    def test_adapter_callbacks_snapshotted(self):
        def verify(prepared):
            object.__setattr__(self.adapter,'retain',lambda material:self.fail('replacement invoked'))
            return self.verify(prepared)
        self.adapter=r.TrustedRetentionAdapter(self.authority,verify,self.retain,self.qualify)
        self.assertIs(self.run_gate().state,r.RetentionState.RETAINED)

    def test_ast_side_effect_boundary(self):
        text=(ROOT/'services/api/infrastructure/fixture_lease_admission_retention.py').read_text()
        tree=ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node,ast.Import): self.fail('Unexpected import')
            if isinstance(node,ast.ImportFrom) and node.level==0:
                self.assertIn(node.module,{'dataclasses','enum','types'})
            if isinstance(node,ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
                self.assertNotIn(name,{'open','getenv','now','time','obtain','transaction','execute','publish',
                    'complete','send','deepcopy','repr','str','getattr','hasattr','isinstance','is_dataclass','pickle','eval','exec'})
        self.assertNotIn('__name__',text)
        self.assertNotIn('except Exception',text)


def path_set(root,path,value):
    for name in path.split('.')[:-1]: root=getattr(root,name)
    object.__setattr__(root,path.split('.')[-1],value)


def malformed_case(name,path,value):
    def test(self):
        path_set(self.prepared,path,value)
        result=self.run_gate()
        self.assertIs(result.state,r.RetentionState.FAIL_CLOSED)
        self.assertEqual(self.events,[])
        self.permissions(result)
    setattr(RetentionTests,'test_predispatch_'+name,test)

for name,path,value in (
    ('fixed_utc','material.fixed_utc_us',99),('bool_utc','material.fixed_utc_us',True),
    ('command_bytes','material.source.attempt.bundle.canonical_command',b'other'),
    ('command_identity','material.source.attempt.bundle.context.command_id','other'),
    ('principal','material.source.attempt.bundle.requester.principal','other'),
    ('approval','material.source.attempt.bundle.approval.validity',s.EvidenceValidity.UNKNOWN),
    ('predecessor','material.source.attempt.bundle.predecessor.observation.predecessor.exact_bytes',b'other'),
    ('representation','material.source.attempt.bundle.predecessor.context.requested.representation','other'),
    ('permit_evidence','material.source.qualification.exact_evidence',b'other'),
    ('sample_validation','material.sample_validation',s.EvidenceReference('other',b'z'*32))): malformed_case(name,path,value)


def authorization_case(name,change):
    def test(self):
        self.verify_value=change(self)
        result=self.run_gate()
        self.assertIs(result.state,r.RetentionState.FAIL_CLOSED)
        self.assertEqual(self.events,['verify'])
        self.permissions(result)
    setattr(RetentionTests,'test_authorization_'+name,test)
def auth(t): return r.RetentionAuthorization(t.expected,t.expected.material.source.qualification.permit.evidence,
    t.authority,s.EvidenceValidity.VALID,t.proof)
for name,change in {
    'false':lambda t:False,'bare_valid':lambda t:s.EvidenceValidity.VALID,
    'unknown':lambda t:replace(auth(t),validity=s.EvidenceValidity.UNKNOWN),
    'invalid':lambda t:replace(auth(t),validity=s.EvidenceValidity.INVALID),
    'wrong_permit':lambda t:replace(auth(t),permit=s.EvidenceReference('provider-native-id',b'z'*32)),
    'wrong_authority':lambda t:replace(auth(t),authority=s.EvidenceReference('other',b'z'*32)),
}.items(): authorization_case(name,change)


def receipt_case(name,change):
    def test(self):
        self.receipt_value=change(self)
        result=self.run_gate()
        self.assertIs(result.state,r.RetentionState.HANDOFF)
        self.assertEqual(self.events,['verify','retain'])
        self.permissions(result)
    setattr(RetentionTests,'test_receipt_'+name,test)
for name,change in {
    'false':lambda t:False,'bare_valid':lambda t:s.EvidenceValidity.VALID,
    'wrong_permit':lambda t:replace(t.receipt(),index=replace(t.receipt().index,permit=s.EvidenceReference('provider-id',b'z'*32))),
    'wrong_context':lambda t:replace(t.receipt(),index=replace(t.receipt().index,context=replace(t.expected.material.source.attempt.bundle.context,command_id='other'))),
    'wrong_principal':lambda t:replace(t.receipt(),index=replace(t.receipt().index,principal='other')),
    'wrong_generation':lambda t:replace(t.receipt(),index=replace(t.receipt().index,activation=replace(t.receipt().index.activation,generation=2))),
    'wrong_envelope_index':lambda t:replace(t.receipt(),index=replace(t.receipt().index,envelope=s.EvidenceReference('other',b'z'*32))),
    'missing_index':lambda t:forged(t.receipt(),index=None),
    'wrong_time':lambda t:forged_material(t,'fixed_utc_us',99),
    'wrong_time_reference':lambda t:forged_material(t,'sample_validation',t.proof),
    'wrong_material_bytes':lambda t:forged_receipt_command(t),
}.items(): receipt_case(name,change)

def forged(value,**changes):
    result=copy.copy(value)
    for name,value in changes.items(): object.__setattr__(result,name,value)
    return result
def forged_material(t,field,value):
    receipt=t.receipt()
    object.__setattr__(receipt.material,field,value)
    return receipt
def forged_receipt_command(t):
    receipt=t.receipt()
    path_set(receipt,'material.source.attempt.bundle.canonical_command',b'other')
    return receipt


def confirmation_case(name,change):
    def test(self):
        self.confirmation_value=change(self)
        result=self.run_gate()
        self.assertIs(result.state,r.RetentionState.HANDOFF)
        self.assertEqual(self.events,['verify','retain','qualify'])
        self.permissions(result)
    setattr(RetentionTests,'test_confirmation_'+name,test)
for name,change in {
    'false':lambda t:False,'bare_valid':lambda t:s.EvidenceValidity.VALID,
    'unqualified':lambda t:t.confirmation(validity=s.EvidenceValidity.UNKNOWN),
    'rejected':lambda t:t.confirmation(validity=s.EvidenceValidity.INVALID),
    'unknown_durability':lambda t:t.confirmation(durable=s.EvidenceValidity.UNKNOWN),
    'no_durability':lambda t:t.confirmation(durable=s.EvidenceValidity.INVALID),
    'unknown_index':lambda t:t.confirmation(indexed=s.EvidenceValidity.UNKNOWN),
    'no_index':lambda t:t.confirmation(indexed=s.EvidenceValidity.INVALID),
    'wrong_authority':lambda t:t.confirmation(authority=s.EvidenceReference('other',b'z'*32)),
    'wrong_receipt_ref':lambda t:t.confirmation(receipt=replace(t.receipt(),reference=s.EvidenceReference('other',b'z'*32))),
}.items(): confirmation_case(name,change)


def error_case(stage,exception,bounded):
    def test(self):
        setattr(self,stage+'_error',exception('sensitive diagnostic'))
        if bounded:
            result=self.run_gate()
            self.assertIs(result.state,r.RetentionState.FAIL_CLOSED if stage=='verify' else r.RetentionState.HANDOFF)
            self.assertNotIn('sensitive',result.reason.value)
            self.permissions(result)
        else:
            with self.assertRaises(exception): self.run_gate()
        self.assertLessEqual(self.events.count('retain'),1)
    setattr(RetentionTests,'test_error_'+stage+'_'+exception.__name__,test)
for stage in ('verify','retain','qualify'):
    for exception,bounded in ((s.CapabilityUnavailable,True),(a.ExternalAvailabilityFailure,True),(TimeoutError,True),
                              (AssertionError,False),(RuntimeError,False)):
        error_case(stage,exception,bounded)


def mutation_case(stage,failed):
    def test(self):
        self.mutate=stage
        if failed: setattr(self,'qualify_error' if stage.startswith('qualify') else stage+'_error',a.ExternalAvailabilityFailure())
        result=self.run_gate()
        self.assertIsNot(result.state,r.RetentionState.RETAINED)
        self.assertIs(result.reason,r.RetentionReason.MUTATED)
        self.assertEqual(result.prepared.material.fixed_utc_us,10)
        self.assertLessEqual(self.events.count('retain'),1)
        self.permissions(result)
    setattr(RetentionTests,'test_mutation_'+stage+'_'+str(failed),test)
for stage in ('verify','retain','qualify','qualify-source'):
    for failed in (False,True): mutation_case(stage,failed)


class Foreign:
    calls=[]
    def __getattribute__(self,name): Foreign.calls.append('attribute'); raise AssertionError()
    def __eq__(self,other): Foreign.calls.append('eq'); raise AssertionError()
    def __hash__(self): Foreign.calls.append('hash'); raise AssertionError()
    def __iter__(self): Foreign.calls.append('iter'); raise AssertionError()
    def __repr__(self): Foreign.calls.append('repr'); raise AssertionError()
    def __str__(self): Foreign.calls.append('str'); raise AssertionError()
    def __call__(self,*args): Foreign.calls.append('call'); raise AssertionError()


def foreign_case(location):
    def test(self):
        Foreign.calls=[]
        prepared=self.prepared; adapter=self.adapter
        if location=='root': prepared=Foreign()
        elif location=='adapter': adapter=Foreign()
        elif location=='nested': path_set(prepared,'material.source.qualification.time.point',Foreign())
        elif location=='receipt': self.receipt_value=Foreign()
        elif location=='confirmation': self.confirmation_value=Foreign()
        elif location=='subclass':
            class Bad(r.TrustedRetentionAdapter,Foreign): pass
            adapter=object.__new__(Bad)
        elif location=='metaclass':
            class Meta(type):
                def __getattribute__(self,name): Foreign.calls.append('meta_attr'); raise AssertionError()
                def __eq__(self,other): Foreign.calls.append('meta_eq'); raise AssertionError()
                def __hash__(self): Foreign.calls.append('meta_hash'); raise AssertionError()
            class Bad(metaclass=Meta): pass
            prepared=object.__new__(Bad)
        elif location=='function':
            def retain(*args): Foreign.calls.append('called')
            adapter=retain
        elif location=='method':
            class Owner:
                def retain(self,*args): Foreign.calls.append('called')
            adapter=Owner().retain
        result=r.retain_original_envelope(prepared,adapter)
        self.assertIsNot(result.state,r.RetentionState.RETAINED)
        self.assertEqual(Foreign.calls,[])
        self.assertLessEqual(self.events.count('retain'),1)
    setattr(RetentionTests,'test_foreign_'+location,test)
for location in ('root','adapter','nested','receipt','confirmation','subclass','metaclass','function','method'):
    foreign_case(location)


if __name__=='__main__': unittest.main()
