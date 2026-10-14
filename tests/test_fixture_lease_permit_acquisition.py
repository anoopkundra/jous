"""Synthetic original acquisition adversarial tests; no real provider or I/O."""
import ast
import copy
from dataclasses import replace, FrozenInstanceError, dataclass
from enum import StrEnum
from hashlib import sha256
import importlib.util
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
old = runpy.run_path(str(ROOT/'tests/test_fixture_lease_permit_gate.py'))
g, s, p, pr = old['g'], old['s'], old['p'], old['pr']
spec = importlib.util.spec_from_file_location('_il4a_pure.fixture_lease_permit_acquisition',
    ROOT/'services/api/infrastructure/fixture_lease_permit_acquisition.py')
a = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = a
spec.loader.exec_module(a)


def forged(value, **changes):
    result = copy.copy(value)
    for name, change in changes.items(): object.__setattr__(result, name, change)
    return result


PERMISSIONS = ('begin_permitted', 'sql_permitted', 'transaction_owned', 'writer_admission_permitted',
    'local_mutation_permitted', 'local_commit_confirmed', 'envelope_retained', 'candidate_construction_permitted',
    'candidate_retention_permitted', 'publication_permitted', 'publication_retry_permitted', 'completion_permitted',
    'ack_construction_permitted', 'ack_delivery_permitted', 'active_permitted', 'fence_clearance_permitted',
    'acquisition_retry_permitted', 'recovery_execution_permitted')


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        fixture = old['GateTests'](); fixture.setUp()
        self.bundle = fixture.bundle
        self.checked = fixture.evaluate()[0]
        self.request = a.AcquisitionInput(self.bundle, self.checked)
        self.expected = a._copy_projection(a._projection(self.request))
        self.events = []
        self.raw = b'synthetic immutable original permit evidence'
        self.permit = s.CommandPermit(self.bundle.context, self.bundle.activation, 0, 20,
            s.EvidenceReference('original-permit', sha256(self.raw).digest()))
        self.ref = s.EvidenceReference('qualified-original-attempt', b'q'*32)
        self.verify_value = None
        self.permit_value = self.permit
        self.qualify_value = None
        self.verify_error = self.obtain_error = self.qualify_error = None
        self.mutate = None
        self.adapter = a.TrustedAcquisitionAdapter(self.verify, self.obtain, self.qualify)

    def verify(self, request):
        self.events.append('verify')
        if self.mutate == 'verify': object.__setattr__(request.bundle.context, 'command_id', 'substituted')
        if self.verify_error: raise self.verify_error
        if self.verify_value is not None: return self.verify_value
        return g.QualificationEvidence(self.expected.bundle, s.EvidenceValidity.VALID, self.ref)

    def obtain(self, context, activation):
        self.events.append('obtain')
        self.assertEqual(context, self.expected.bundle.context)
        self.assertEqual(activation, self.expected.bundle.activation)
        if self.mutate == 'obtain': object.__setattr__(context, 'command_id', 'substituted')
        if self.obtain_error: raise self.obtain_error
        return self.permit_value

    def qualify(self, request, permit):
        self.events.append('qualify')
        if self.mutate == 'qualify': object.__setattr__(permit, 'valid_until_us', 99)
        if self.mutate == 'qualify-request': object.__setattr__(request.bundle.requester, 'principal', 'substituted')
        if self.qualify_error: raise self.qualify_error
        if self.qualify_value is not None: return self.qualify_value
        return self.qualification()

    def qualification(self, **changes):
        return replace(a.PermitQualification(self.expected, self.permit, self.raw,
            self.bundle.time, s.EvidenceValidity.VALID, self.ref), **changes)

    def run_gate(self, request=None, adapter=None):
        return a.acquire_original_permit(self.request if request is None else request,
            self.adapter if adapter is None else adapter)

    def assert_permissions(self, result):
        for name in PERMISSIONS: self.assertIs(getattr(result, name), False)

    def test_success_order_and_exact_original_identity(self):
        result = self.run_gate()
        self.assertIs(result.state, a.AcquisitionState.QUALIFIED)
        self.assertEqual(self.events, ['verify', 'obtain', 'qualify'])
        self.assertEqual(result.qualification.permit, self.permit)
        self.assertEqual(result.qualification.exact_evidence, self.raw)
        self.assertEqual(a._projection(result.attempt), a._projection(self.expected))
        self.assertIsNot(result.attempt, self.request)
        self.assert_permissions(result)

    def test_default_no_dispatch(self):
        result = a.acquire_original_permit(self.request)
        self.assertIs(result.state, a.AcquisitionState.PRE_DISPATCH_FAILURE)
        self.assertEqual(self.events, [])
        self.assert_permissions(result)

    def test_detached_success_survives_callback_reference_mutation(self):
        result = self.run_gate()
        object.__setattr__(self.bundle.context, 'command_id', 'later mutation')
        object.__setattr__(self.permit, 'valid_until_us', 99)
        a.AcquisitionResult.__post_init__(result)
        self.assertEqual(result.qualification.permit.valid_until_us, 20)
        self.assertEqual(result.attempt.bundle.context.command_id, 'new-command')

    def test_fabricated_checked_does_not_bypass_independent_verification(self):
        self.verify_value = g.QualificationEvidence(self.bundle, s.EvidenceValidity.UNKNOWN, self.ref)
        result = self.run_gate()
        self.assertIs(result.state, a.AcquisitionState.PRE_DISPATCH_FAILURE)
        self.assertEqual(self.events, ['verify'])

    def test_result_constructor_and_replace_cannot_mint_success(self):
        with self.assertRaises(TypeError): a.AcquisitionResult()
        with self.assertRaises(TypeError): replace(self.run_gate(), acquisition_attempted=False)

    def test_direct_contradictory_input_rejected(self):
        with self.assertRaises(s.TimeRejected): a.AcquisitionInput(self.bundle, forged(self.checked, state=g.GateState.FAIL_CLOSED))

    def test_frozen_result_mutation_revalidated(self):
        result = self.run_gate()
        with self.assertRaises(FrozenInstanceError): result.reason = a.AcquisitionReason.MALFORMED
        object.__setattr__(result, 'acquisition_attempted', False)
        with self.assertRaises(s.TimeRejected): a.AcquisitionResult.__post_init__(result)

    def test_repeated_evaluation_has_no_local_retry_state(self):
        self.run_gate(); self.run_gate()
        self.assertEqual(self.events, ['verify', 'obtain', 'qualify']*2)
        # Each explicit evaluation is single-call. Protected single-flight is
        # the composed authority's obligation, never a process-local flag.

    def test_equal_digest_unequal_canonical_bytes(self):
        changed = forged(self.bundle, canonical_command=self.bundle.canonical_command[:-1]+b'x')
        result = self.run_gate(forged(self.request, bundle=changed))
        self.assertIs(result.state, a.AcquisitionState.PRE_DISPATCH_FAILURE)
        self.assertEqual(self.events, [])

    def test_internal_runtime_error_propagates(self):
        with patch.object(g, '_check', side_effect=RuntimeError('internal defect')):
            with self.assertRaises(RuntimeError): self.run_gate()
        self.assertEqual(self.events, [])

    def test_internal_assertion_propagates(self):
        with patch.object(g, '_check', side_effect=AssertionError('internal defect')):
            with self.assertRaises(AssertionError): self.run_gate()

    def test_qualified_time_cannot_claim_envelope_utc(self):
        result = self.run_gate()
        self.assertFalse(result.envelope_retained)
        self.assertFalse(hasattr(result, 'fixed_utc'))

    def test_production_import_and_ast_effect_guard(self):
        source = (ROOT/'services/api/infrastructure/fixture_lease_permit_acquisition.py').read_text()
        tree = ast.parse(source)
        allowed = {'dataclasses', 'enum', 'hashlib', 'types'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): self.fail('Unexpected import')
            if isinstance(node, ast.ImportFrom) and node.level == 0: self.assertIn(node.module, allowed)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {'open','eval','exec','getattr','hasattr','isinstance','callable','repr','str','hash'})
        self.assertNotIn('__name__', source)
        self.assertNotIn('except Exception', source)


def pre_case(name, change):
    def test(self):
        request = change(self)
        result = self.run_gate(request)
        self.assertIs(result.state, a.AcquisitionState.PRE_DISPATCH_FAILURE)
        self.assertEqual(self.events, [])
        self.assert_permissions(result)
    setattr(AcquisitionTests, 'test_pre_'+name, test)


for name, change in {
    'command_digest': lambda t: forged(t.bundle.context, payload_sha256=b'z'*32),
    'command_id': lambda t: forged(t.bundle.context, command_id='other'),
    'principal': lambda t: forged(t.bundle.requester, principal='other'),
    'authorization': lambda t: forged(t.bundle.authorization, validity=s.EvidenceValidity.UNKNOWN),
    'activation': lambda t: forged(t.bundle.activation, activation_id='other'),
    'register': lambda t: forged(t.bundle.activation, register_id='other'),
    'generation': lambda t: forged(t.bundle.activation, generation=2),
    'generation_bool': lambda t: forged(t.bundle.activation, generation=True),
    'host': lambda t: forged(t.bundle.activation, host_identity='other'),
}.items():
    field = 'context' if name.startswith('command_') else 'requester' if name=='principal' else 'authorization' if name=='authorization' else 'activation'
    pre_case(name, lambda t, change=change, field=field: forged(t.request, bundle=forged(t.bundle, **{field:change(t)})))

for name, field, value in (
    ('replay','command',g.CommandHistory.EXACT_REPLAY), ('history_unknown','command',g.CommandHistory.UNKNOWN),
    ('acquisition_gap','acquisition',g.GapKnowledge.UNRESOLVED), ('publication_gap','publication',g.GapKnowledge.UNKNOWN),
    ('completion_gap','completion',g.GapKnowledge.UNRESOLVED), ('stale','activation_status',pr.CurrentStatus.SUPERSEDED),
    ('fenced','fencing_status',pr.FencingStatus.FENCED), ('recovery','fencing_status',pr.FencingStatus.RECOVERY_ONLY),
    ('unapproved_host','host_status',pr.HostStatus.UNAPPROVED)):
    pre_case(name, lambda t, field=field,value=value: forged(t.request, bundle=forged(t.bundle, history=forged(t.bundle.history, **{field:value}))))

for name, state in [('fail_closed',g.GateState.FAIL_CLOSED),('handoff',g.GateState.HANDOFF)]:
    pre_case(name, lambda t,state=state: forged(t.request, checked=forged(t.checked,state=state)))
pre_case('oversized_command', lambda t: forged(t.request,bundle=forged(t.bundle,canonical_command=b'x'*(2*g.c.MAX_ARTIFACT_BYTES))))
pre_case('malformed_time', lambda t: forged(t.request,bundle=forged(t.bundle,time=forged(t.bundle.time,point=forged(t.bundle.time.point,ticks_ns=True)))))


def qualification_case(name, change):
    def test(self):
        self.qualify_value = change(self)
        result = self.run_gate()
        self.assertIs(result.state, a.AcquisitionState.UNRESOLVED_HANDOFF)
        self.assertEqual(self.events, ['verify','obtain','qualify'])
        self.assert_permissions(result)
    setattr(AcquisitionTests, 'test_qualification_'+name, test)


for name, change in {
    'unknown': lambda t: t.qualification(validity=s.EvidenceValidity.UNKNOWN),
    'invalid': lambda t: t.qualification(validity=s.EvidenceValidity.INVALID),
    'foreign': lambda t: object(),
    'missing': lambda t: False,
    'wrong_attempt': lambda t: forged(t.qualification(),attempt=forged(t.expected,bundle=forged(t.expected.bundle,approved_host='other'))),
    'wrong_permit_identity': lambda t: t.qualification(permit=replace(t.permit,evidence=replace(t.permit.evidence,identity='other'))),
    'wrong_evidence': lambda t: forged(t.qualification(),exact_evidence=b'other'),
    'oversized_evidence': lambda t: forged(t.qualification(),exact_evidence=b'x'*(g.c.MAX_ARTIFACT_BYTES+1)),
    'empty_evidence': lambda t: forged(t.qualification(),exact_evidence=b''),
    'profile': lambda t: t.qualification(time=replace(t.bundle.time,profile=replace(t.bundle.time.profile,qualification=t.ref))),
    'process': lambda t: t.qualification(time=replace(t.bundle.time,point=replace(t.bundle.time.point,process_id='restart'))),
    'domain': lambda t: t.qualification(time=replace(t.bundle.time,point=replace(t.bundle.time.point,domain_id='other'))),
    'coverage': lambda t: t.qualification(time=replace(t.bundle.time,point=replace(t.bundle.time.point,ticks_ns=1000))),
    'freshness': lambda t: t.qualification(time=replace(t.bundle.time,freshness_deadline=s.StrictDeadline(10))),
}.items(): qualification_case(name, change)


def permit_case(name, changes):
    def test(self):
        self.permit_value = forged(self.permit, **changes(self))
        result = self.run_gate()
        self.assertIs(result.state, a.AcquisitionState.UNRESOLVED_HANDOFF)
        self.assertEqual(self.events.count('obtain'), 1)
        self.assert_permissions(result)
    setattr(AcquisitionTests, 'test_permit_'+name, test)


for name, changes in {
    'lost_response': lambda t: {},
    'context': lambda t: {'context':replace(t.permit.context,command_id='other')},
    'activation': lambda t: {'activation':replace(t.permit.activation,host_identity='other')},
    'bool_interval': lambda t: {'valid_from_us':True},
    'expired': lambda t: {'valid_until_us':9},
    'strict_equality': lambda t: {'valid_until_us':10},
    'not_yet_valid': lambda t: {'valid_from_us':11},
}.items():
    if name=='lost_response':
        def lost(self):
            self.permit_value = None
            result=self.run_gate()
            self.assertIs(result.state,a.AcquisitionState.UNRESOLVED_HANDOFF)
            self.assertEqual(self.events,['verify','obtain'])
        setattr(AcquisitionTests,'test_permit_lost_response',lost)
    else: permit_case(name,changes)


def error_case(stage, exception, propagated):
    def test(self):
        setattr(self, stage+'_error', exception('sensitive external text'))
        if propagated:
            with self.assertRaises(exception): self.run_gate()
        else:
            result=self.run_gate()
            expected=a.AcquisitionState.PRE_DISPATCH_FAILURE if stage=='verify' else a.AcquisitionState.UNRESOLVED_HANDOFF
            self.assertIs(result.state,expected)
            self.assertNotIn('sensitive',result.reason.value)
            self.assert_permissions(result)
        self.assertLessEqual(self.events.count('obtain'),1)
    setattr(AcquisitionTests,'test_error_'+stage+'_'+exception.__name__,test)

for stage in ('verify','obtain','qualify'):
    for exception,propagated in ((a.ExternalAvailabilityFailure,False),(s.CapabilityUnavailable,False),(AssertionError,True),(RuntimeError,True),(TypeError,True)):
        error_case(stage,exception,propagated)


def mutation_case(stage, outcome):
    def test(self):
        self.mutate=stage
        if outcome=='exception': setattr(self,('obtain' if stage=='obtain' else 'qualify' if stage.startswith('qualify') else 'verify')+'_error',a.ExternalAvailabilityFailure())
        if outcome=='reject':
            if stage=='verify': self.verify_value=False
            elif stage=='obtain': self.permit_value=None
            else: self.qualify_value=False
        result=self.run_gate()
        self.assertIsNot(result.state,a.AcquisitionState.QUALIFIED)
        self.assertIs(result.reason,a.AcquisitionReason.MUTATED)
        self.assertEqual(result.attempt.bundle.context.command_id,'new-command')
        self.assertLessEqual(self.events.count('obtain'),1)
        self.assert_permissions(result)
    setattr(AcquisitionTests,'test_mutation_'+stage+'_'+outcome,test)

for stage in ('verify','obtain','qualify','qualify-request'):
    for outcome in ('success','reject','exception'):
        mutation_case(stage,outcome)


class Foreign:
    calls=[]
    def __getattribute__(self,name): Foreign.calls.append('attribute'); raise AssertionError('hostile')
    def __iter__(self): Foreign.calls.append('iter'); raise AssertionError('hostile')
    def __eq__(self,other): Foreign.calls.append('eq'); raise AssertionError('hostile')
    def __hash__(self): Foreign.calls.append('hash'); raise AssertionError('hostile')
    def __repr__(self): Foreign.calls.append('repr'); raise AssertionError('hostile')
    def __str__(self): Foreign.calls.append('str'); raise AssertionError('hostile')
    def __call__(self,*args): Foreign.calls.append('call'); raise AssertionError('hostile')


def hostile_case(location):
    def test(self):
        Foreign.calls=[]
        foreign=Foreign()
        request=self.request; adapter=self.adapter
        if location=='root': request=foreign
        elif location=='adapter': adapter=foreign
        elif location=='nested': request=forged(request,bundle=forged(self.bundle,requester=foreign))
        elif location=='checked': request=forged(request,checked=foreign)
        elif location=='returned': self.permit_value=foreign
        else: self.qualify_value=foreign
        result=a.acquire_original_permit(request,adapter)
        self.assertIsNot(result.state,a.AcquisitionState.QUALIFIED)
        self.assertEqual(Foreign.calls,[])
        self.assertLessEqual(self.events.count('obtain'),1)
    setattr(AcquisitionTests,'test_hostile_'+location,test)
for location in ('root','adapter','nested','checked','returned','qualified'): hostile_case(location)


def substitute_case(name, factory):
    def test(self):
        calls=[]
        substitute=factory(calls,self)
        result=a.acquire_original_permit(self.request,substitute)
        self.assertIs(result.state,a.AcquisitionState.PRE_DISPATCH_FAILURE)
        self.assertEqual(calls,[]); self.assertEqual(self.events,[])
    setattr(AcquisitionTests,'test_adapter_'+name,test)

def raw(calls,t):
    def obtain(*args): calls.append('called')
    return obtain
def method(calls,t):
    class Owner:
        def obtain(self,*args): calls.append('called')
    return Owner().obtain
def subclass(calls,t):
    class Sub(a.TrustedAcquisitionAdapter): pass
    return object.__new__(Sub)
def meta(calls,t):
    class Meta(type):
        def __eq__(self,other): calls.append('metaclass equality'); return True
        def __hash__(self): calls.append('metaclass hash'); return 1
        def __getattribute__(self,name): calls.append('metaclass attribute'); return super().__getattribute__(name)
    class Mimic(metaclass=Meta): pass
    return object.__new__(Mimic)
for name,factory in {'raw_same_name':raw,'unrelated_method':method,'subclass':subclass,'hostile_metaclass':meta,
                     'request':lambda c,t:t.request,'valid_claim':lambda c,t:t.qualification()}.items(): substitute_case(name,factory)


def predecessor_case(name, field, value):
    def change(t):
        predecessor=t.bundle.predecessor
        observed=forged(predecessor.observation,predecessor=forged(predecessor.observation.predecessor,**{field:value}))
        return forged(t.request,bundle=forged(t.bundle,predecessor=forged(predecessor,observation=observed)))
    pre_case('predecessor_'+name,change)
for name,field,value in (
    ('bytes','exact_bytes',b'substitution'), ('digest','reference',s.EvidenceReference('other',b'z'*32)),
    ('revision','revision',99), ('sequence','event_sequence',99), ('head','event_digest',b'z'*32),
    ('state','state_digest',b'z'*32), ('representation','representation','unsupported'),
    ('authority','representation_authority',s.EvidenceReference('other',b'z'*32))): predecessor_case(name,field,value)


def time_case(name, lower, upper, qualified):
    def test(self):
        if name=='valid_from_equality':
            self.permit=replace(self.permit,valid_from_us=10)
            self.permit_value=self.permit
        if lower < 10:
            time=replace(self.bundle.time,sample=replace(self.bundle.time.sample,utc=s.UtcInterval(lower,upper)))
        else:
            ticks=(lower+upper-20)*500
            error=(upper-lower)*1000//2
            time=replace(self.bundle.time,point=replace(self.bundle.time.point,ticks_ns=ticks),
                propagation=replace(self.bundle.time.propagation,elapsed_ns=ticks,error_ns=error))
        self.qualify_value=self.qualification(time=time)
        result=self.run_gate()
        self.assertIs(result.state,a.AcquisitionState.QUALIFIED if qualified else a.AcquisitionState.UNRESOLVED_HANDOFF)
        self.assertEqual(self.events,['verify','obtain','qualify'])
        self.assert_permissions(result)
    setattr(AcquisitionTests,'test_time_'+name,test)
for name,lower,upper,qualified in (
    ('permit_overlap',19,21,False), ('valid_from_equality',10,10,True), ('valid_from_outside',-1,0,False),
    ('strict_equality',20,20,False), ('authorization_outside',21,21,False), ('valid_interval',11,12,True)):
    time_case(name,lower,upper,qualified)


def extra_case(name):
    def test(self):
        if name=='inclusive_authorization':
            self.permit=replace(self.permit,valid_until_us=21); self.permit_value=self.permit
            self.qualify_value=self.qualification(time=replace(self.bundle.time,point=replace(self.bundle.time.point,ticks_ns=10000),
                propagation=replace(self.bundle.time.propagation,elapsed_ns=10000)))
            self.assertIs(self.run_gate().state,a.AcquisitionState.QUALIFIED)
        elif name=='rejecting_obtain':
            self.adapter=a.TrustedAcquisitionAdapter(self.verify,s.RejectingCapabilities().obtain,self.qualify)
            self.assertIs(self.run_gate().state,a.AcquisitionState.UNRESOLVED_HANDOFF)
            self.assertEqual(self.events,['verify'])
        elif name=='fabricated_command_permit_qualifier':
            self.qualify_value=self.permit
            self.assertIs(self.run_gate().state,a.AcquisitionState.UNRESOLVED_HANDOFF)
        elif name=='adapter_mutation':
            def verify(request):
                object.__setattr__(self.adapter,'obtain',lambda *args:self.fail('replacement callback'))
                return self.verify(request)
            self.adapter=a.TrustedAcquisitionAdapter(verify,self.obtain,self.qualify)
            self.assertIs(self.run_gate().state,a.AcquisitionState.QUALIFIED)
            self.assertEqual(self.events,['verify','obtain','qualify'])
        elif name=='foreign_dataclass':
            @dataclass(frozen=True)
            class Bad(Foreign):
                def __post_init__(self): Foreign.calls.append('post_init')
            Foreign.calls=[]
            obj=object.__new__(Bad)
            request=forged(self.request,bundle=forged(self.bundle,requester=obj))
            self.assertIs(a.acquire_original_permit(request,self.adapter).state,a.AcquisitionState.PRE_DISPATCH_FAILURE)
            self.assertEqual(Foreign.calls,[])
        elif name=='foreign_enum':
            class Bad(StrEnum): VALID='VALID'
            self.verify_value=forged(g.QualificationEvidence(self.bundle,s.EvidenceValidity.VALID,self.ref),validity=Bad.VALID)
            self.assertIs(self.run_gate().state,a.AcquisitionState.PRE_DISPATCH_FAILURE)
            self.assertEqual(self.events,['verify'])
        elif name=='primitive_subclass':
            class Bad(bytes):
                def __eq__(self,other): self.fail('foreign equality')
            result=self.run_gate(forged(self.request,bundle=forged(self.bundle,canonical_command=Bad(self.bundle.canonical_command))))
            self.assertIs(result.state,a.AcquisitionState.PRE_DISPATCH_FAILURE)
            self.assertEqual(self.events,[])
        elif name=='request_subclass':
            class Bad(a.AcquisitionInput):
                def __getattribute__(self,name): raise AssertionError('foreign attribute')
            result=self.run_gate(object.__new__(Bad))
            self.assertIs(result.state,a.AcquisitionState.PRE_DISPATCH_FAILURE)
            self.assertEqual(self.events,[])
        elif name=='descriptor':
            class Bad:
                @property
                def obtain(self): Foreign.calls.append('descriptor'); raise AssertionError()
                @property
                def __name__(self): Foreign.calls.append('name'); raise AssertionError()
            Foreign.calls=[]
            result=self.run_gate(adapter=Bad())
            self.assertIs(result.state,a.AcquisitionState.PRE_DISPATCH_FAILURE)
            self.assertEqual(Foreign.calls,[])
    setattr(AcquisitionTests,'test_extra_'+name,test)
for name in ('inclusive_authorization','rejecting_obtain','fabricated_command_permit_qualifier','adapter_mutation',
             'foreign_dataclass','foreign_enum','primitive_subclass','request_subclass','descriptor'): extra_case(name)


if __name__ == '__main__': unittest.main()
