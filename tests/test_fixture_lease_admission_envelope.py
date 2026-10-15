"""Pure preparation tests using frozen, synthetic evaluator-issued knowledge."""
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

ROOT = Path(__file__).resolve().parents[1]
old = runpy.run_path(str(ROOT/'tests/test_fixture_lease_permit_acquisition.py'))
a, g, s, p, pr = (old[n] for n in ('a','g','s','p','pr'))
spec = importlib.util.spec_from_file_location('_il4a_pure.fixture_lease_admission_envelope',
    ROOT/'services/api/infrastructure/fixture_lease_admission_envelope.py')
e = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = e
spec.loader.exec_module(e)


def clone(source): return a._copy_projection(e._source_projection(source))


PERMISSIONS = ('external_retention_permitted','durability_confirmed','envelope_retained',
    'begin_permitted','transaction_owned','sql_permitted','writer_admission_permitted',
    'local_mutation_permitted','local_commit_confirmed','candidate_construction_permitted',
    'candidate_retention_permitted','publication_permitted','completion_permitted',
    'ack_construction_permitted','ack_delivery_permitted','active_permitted','retry_permitted',
    'reacquisition_permitted','fence_clearance_permitted','recovery_execution_permitted',
    'runtime_activation_permitted')


class EnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture=old['AcquisitionTests'](); fixture.setUp()
        cls.original=fixture.run_gate()
        cls.pre=a.acquire_original_permit(fixture.request)
        fixture.obtain_error=a.ExternalAvailabilityFailure()
        cls.unresolved=fixture.run_gate()

    def setUp(self): self.source=clone(self.original)

    def prepare(self): return e.prepare_admission_envelope(self.source)

    def permissions(self,result):
        for name in PERMISSIONS: self.assertIs(getattr(result,name),False)

    def closed(self):
        result=self.prepare()
        self.assertIs(result.state,e.PreparationState.FAIL_CLOSED)
        self.assertIsNone(result.material)
        self.permissions(result)

    def test_coherent_qualified_prepares(self):
        result=self.prepare()
        self.assertIs(result.state,e.PreparationState.PREPARED)
        self.permissions(result)
        self.assertEqual(e._source_projection(result.material.source),e._source_projection(self.source))

    def test_fixed_lower_bound_exact(self):
        result=self.prepare()
        time=self.source.qualification.time
        evaluated=s.evaluate_time(time.sample,time.profile,time.point,time.propagation)
        self.assertEqual(result.material.fixed_utc_us,evaluated.interval.lower_us)
        self.assertEqual(result.material.evaluation,evaluated)
        self.assertIs(type(result.material.fixed_utc_us),int)

    def test_determinism(self): self.assertEqual(self.prepare(),self.prepare())

    def test_distinct_time_reference_roles(self):
        material=self.prepare().material
        self.assertEqual(material.sample_validation,self.source.qualification.time.sample.validation)
        self.assertEqual(material.acquisition_qualification,self.source.qualification.reference)
        self.assertNotEqual(material.sample_validation,material.acquisition_qualification)
        wrong=copy.copy(material)
        object.__setattr__(wrong,'sample_validation',material.acquisition_qualification)
        with self.assertRaises(s.TimeRejected): e.PreparedEnvelopeMaterial.__post_init__(wrong)
        wrong=copy.copy(material)
        object.__setattr__(wrong,'acquisition_qualification',material.sample_validation)
        with self.assertRaises(s.TimeRejected): e.PreparedEnvelopeMaterial.__post_init__(wrong)

    def test_full_exact_permit_identity_and_bytes_retained(self):
        material=self.prepare().material
        self.assertEqual(material.source.qualification.permit.evidence,self.source.qualification.permit.evidence)
        self.assertEqual(material.source.qualification.exact_evidence,self.source.qualification.exact_evidence)

    def test_time_chain_preserved(self):
        material=self.prepare().material
        self.assertEqual(material.source.qualification.time,self.source.qualification.time)

    def test_not_a_retained_envelope(self):
        material=self.prepare().material
        self.assertIsNot(type(material),s.RetainedAdmissionEnvelope)
        self.assertIsNot(type(material),s.RetainedTimeFixing)
        self.assertFalse(hasattr(material,'reference'))
        self.assertFalse(hasattr(material,'envelope'))

    def test_no_caller_fixed_utc(self):
        with self.assertRaises(TypeError): e.prepare_admission_envelope(self.source,fixed_utc_us=77)
        material=self.prepare().material
        with self.assertRaises(TypeError): replace(material,fixed_utc_us=material.fixed_utc_us+1)
        for bad in (material.fixed_utc_us+1,True):
            wrong=copy.copy(material); object.__setattr__(wrong,'fixed_utc_us',bad)
            with self.assertRaises(s.TimeRejected): e.PreparedEnvelopeMaterial.__post_init__(wrong)

    def test_direct_result_and_replace_cannot_claim_prepared(self):
        with self.assertRaises(TypeError): e.PreparationResult()
        with self.assertRaises(TypeError): e.PreparedEnvelopeMaterial()
        with self.assertRaises(TypeError): replace(self.prepare(),state=e.PreparationState.HANDOFF)

    def test_material_frozen_and_revalidated(self):
        material=self.prepare().material
        with self.assertRaises(FrozenInstanceError): material.fixed_utc_us=0
        object.__setattr__(material,'fixed_utc_us',0)
        with self.assertRaises(s.TimeRejected): e.PreparedEnvelopeMaterial.__post_init__(material)

    def test_detachment_every_mutable_graph_node(self):
        result=self.prepare()
        expected=e._source_projection(result.material.source)
        source=self.source
        object.__setattr__(source.attempt.bundle.context,'command_id','changed')
        object.__setattr__(source.qualification.permit,'valid_until_us',99)
        object.__setattr__(source.qualification.time.point,'ticks_ns',99)
        object.__setattr__(source,'state',a.AcquisitionState.UNRESOLVED_HANDOFF)
        self.assertEqual(e._source_projection(result.material.source),expected)
        e.PreparationResult.__post_init__(result)

    def test_pre_dispatch_source_stays_nonqualified(self):
        result=e.prepare_admission_envelope(self.pre)
        self.assertIs(result.state,e.PreparationState.FAIL_CLOSED)
        self.assertIs(result.reason,e.PreparationReason.SOURCE_NOT_QUALIFIED)
        self.assertEqual(result.source,self.pre)
        self.permissions(result)

    def test_unresolved_handoff_preserved_and_detached(self):
        source=clone(self.unresolved)
        result=e.prepare_admission_envelope(source)
        self.assertIs(result.state,e.PreparationState.HANDOFF)
        self.assertIs(result.source.state,a.AcquisitionState.UNRESOLVED_HANDOFF)
        self.assertEqual(result.source.reason,source.reason)
        self.assertIsNot(result.source,source)
        self.permissions(result)

    def test_bare_qualification_does_not_self_certify(self):
        result=e.prepare_admission_envelope(self.source.qualification)
        self.assertIs(result.state,e.PreparationState.FAIL_CLOSED)

    def test_valid_label_does_not_self_certify(self):
        self.assertIs(e.prepare_admission_envelope(s.EvidenceValidity.VALID).state,e.PreparationState.FAIL_CLOSED)

    def test_required_approval_retained(self):
        material=self.prepare().material
        approval=material.source.attempt.bundle.approval
        self.assertIs(approval.applicability,s.ApprovalApplicability.REQUIRED)
        self.assertEqual(approval,self.source.attempt.bundle.approval)

    def test_not_applicable_qualified_path(self):
        fixture=old['AcquisitionTests'](); fixture.setUp()
        # Use the published positive RECORD_EXECUTION fixture and its frozen
        # qualification gates; no new approval ceremony or fabricated result.
        gate_fixture=old['old']['GateTests'](); gate_fixture.setUp()
        namespace=old['old']
        command=replace(p.decode_record(namespace['old']['fixtures']['D'],p.CommandPayload),
                        command_id='new-execution')
        context=gate_fixture.command_context(command)
        bundle=replace(gate_fixture.bundle,command=command,canonical_command=p.command_bytes(command),context=context,
            authorization=replace(gate_fixture.bundle.authorization,context=context),
            history=replace(gate_fixture.bundle.history,context=context),
            approval=g.ApprovalEvidence(s.ApprovalApplicability.NOT_APPLICABLE,None,None,s.EvidenceValidity.VALID,None,None))
        checked=gate_fixture.evaluate(bundle,expected=bundle)[0]
        request=a.AcquisitionInput(bundle,checked)
        permit=replace(fixture.permit,context=context,activation=bundle.activation)
        def verify(value): return g.QualificationEvidence(bundle,s.EvidenceValidity.VALID,fixture.ref)
        def obtain(context,activation): return permit
        def qualify(value,observed): return a.PermitQualification(request,observed,fixture.raw,bundle.time,s.EvidenceValidity.VALID,fixture.ref)
        source=a.acquire_original_permit(request,a.TrustedAcquisitionAdapter(verify,obtain,qualify))
        result=e.prepare_admission_envelope(source)
        self.assertIs(result.state,e.PreparationState.PREPARED)
        self.assertIsNone(result.material.source.attempt.bundle.approval.verified)

    def test_internal_assertion_propagates(self):
        with patch.object(s,'evaluate_time',side_effect=AssertionError('internal')):
            with self.assertRaises(AssertionError): self.prepare()

    def test_internal_runtime_error_propagates(self):
        with patch.object(s,'evaluate_time',side_effect=RuntimeError('internal')):
            with self.assertRaises(RuntimeError): self.prepare()

    def test_no_capabilities_or_clocks_invoked(self):
        with patch.object(a,'acquire_original_permit',side_effect=AssertionError('acquire')), \
             patch.object(g,'evaluate_prerequisites',side_effect=AssertionError('verify')):
            self.assertIs(self.prepare().state,e.PreparationState.PREPARED)

    def test_ast_purity_and_no_retained_constructor(self):
        text=(ROOT/'services/api/infrastructure/fixture_lease_admission_envelope.py').read_text()
        tree=ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node,ast.Import): self.fail('Unexpected import')
            if isinstance(node,ast.ImportFrom) and node.level==0: self.assertIn(node.module,{'dataclasses','enum'})
            if isinstance(node,ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
                self.assertNotIn(name,{'open','getenv','now','time','obtain','qualify','transaction','execute','publish',
                    'retain','complete','send','RetainedAdmissionEnvelope','RetainedTimeFixing','deepcopy','repr','str',
                    'getattr','hasattr','isinstance','is_dataclass','pickle','eval','exec'})
        self.assertNotIn('except Exception',text)

    def test_valid_from_equality(self):
        object.__setattr__(self.source.qualification.permit,'valid_from_us',10)
        self.assertIs(self.prepare().state,e.PreparationState.PREPARED)

    def test_signed_utc_minimum(self):
        lower=-(1<<63)
        fixture=old['AcquisitionTests'](); fixture.setUp()
        gate_fixture=old['old']['GateTests'](); gate_fixture.setUp()
        bundle=replace(gate_fixture.bundle,
            authorization=replace(gate_fixture.bundle.authorization,valid_from_us=lower,deadline=s.InclusiveDeadline(lower+1)),
            approval=replace(gate_fixture.bundle.approval,valid_from_us=lower,deadline=s.InclusiveDeadline(lower+1)),
            time=replace(gate_fixture.bundle.time,sample=replace(gate_fixture.bundle.time.sample,utc=s.UtcInterval(lower,lower)),
                         freshness_deadline=s.StrictDeadline(lower+1)))
        checked=gate_fixture.evaluate(bundle,expected=bundle)[0]
        request=a.AcquisitionInput(bundle,checked)
        permit=replace(fixture.permit,valid_from_us=lower,valid_until_us=lower+1)
        def verify(value): return g.QualificationEvidence(bundle,s.EvidenceValidity.VALID,fixture.ref)
        def obtain(context,activation): return permit
        def qualify(value,observed): return a.PermitQualification(request,observed,fixture.raw,bundle.time,s.EvidenceValidity.VALID,fixture.ref)
        source=a.acquire_original_permit(request,a.TrustedAcquisitionAdapter(verify,obtain,qualify))
        result=e.prepare_admission_envelope(source)
        self.assertIs(result.state,e.PreparationState.PREPARED)
        self.assertEqual(result.material.fixed_utc_us,lower)

    def test_signed_utc_maximum_cannot_satisfy_strict_permit(self):
        maximum=(1<<63)-1
        interval=s.UtcInterval(maximum,maximum)
        self.assertIsNot(s.strict_bound(interval,s.StrictDeadline(maximum)),s.TimingBound.SATISFIED)
        mutate_path(self.source,'qualification.time.sample.utc',interval)
        self.closed()

    def test_signed_utc_overflow_rejected(self):
        mutate_path(self.source,'qualification.time.sample.utc.upper_us',1<<63)
        self.closed()

    def test_equality_hash_claim_cannot_replace_command_bytes(self):
        original=self.source.attempt.bundle.canonical_command
        class Collision:
            def digest(inner): return self.source.attempt.bundle.context.payload_sha256
        mutate_path(self.source,'attempt.bundle.canonical_command',p.command_bytes(
            replace(self.source.attempt.bundle.command,command_id='other')))
        with patch.object(g,'sha256',return_value=Collision()): self.closed()
        self.assertNotEqual(original,self.source.attempt.bundle.canonical_command)

    def test_hostile_descriptor_not_invoked(self):
        calls=[]
        class Bad:
            @property
            def state(self): calls.append('descriptor'); raise AssertionError()
            @property
            def __name__(self): calls.append('name'); raise AssertionError()
        self.assertIs(e.prepare_admission_envelope(Bad()).state,e.PreparationState.FAIL_CLOSED)
        self.assertEqual(calls,[])


def mutate_path(root,path,value):
    obj=root
    for name in path.split('.')[:-1]: obj=getattr(obj,name)
    object.__setattr__(obj,path.split('.')[-1],value)


def negative(name,path,value):
    def test(self):
        mutate_path(self.source,path,value)
        self.closed()
    setattr(EnvelopeTests,'test_reject_'+name,test)

for name,path,value in (
    ('command_bytes','attempt.bundle.canonical_command',b'different'),
    ('command_digest','attempt.bundle.context.payload_sha256',b'z'*32),
    ('command_id','attempt.bundle.context.command_id','other'),
    ('principal','attempt.bundle.requester.principal','other'),
    ('authorization','attempt.bundle.authorization.reference',s.EvidenceReference('other',b'z'*32)),
    ('activation','attempt.bundle.activation.activation_id','other'),
    ('register','attempt.bundle.activation.register_id','other'),
    ('generation','attempt.bundle.activation.generation',2),
    ('bool_generation','attempt.bundle.activation.generation',True),
    ('host','attempt.bundle.approved_host','other'),
    ('predecessor_bytes','attempt.bundle.predecessor.observation.predecessor.exact_bytes',b'other'),
    ('predecessor_ref','attempt.bundle.predecessor.observation.predecessor.reference',s.EvidenceReference('other',b'z'*32)),
    ('revision','attempt.bundle.predecessor.observation.predecessor.revision',99),
    ('event_sequence','attempt.bundle.predecessor.observation.predecessor.event_sequence',99),
    ('event_digest','attempt.bundle.predecessor.observation.predecessor.event_digest',b'z'*32),
    ('state_digest','attempt.bundle.predecessor.observation.predecessor.state_digest',b'z'*32),
    ('representation','attempt.bundle.predecessor.context.requested.representation','unsupported'),
    ('representation_authority','attempt.bundle.predecessor.context.requested.representation_authority',s.EvidenceReference('other',b'z'*32)),
    ('permit_evidence','qualification.exact_evidence',b'substituted'),
    ('permit_context','qualification.permit.context.command_id','other'),
    ('permit_qualification','qualification.validity',s.EvidenceValidity.UNKNOWN),
    ('missing_approval','attempt.bundle.approval.verified',None),
    ('unknown_approval','attempt.bundle.approval.applicability',s.ApprovalApplicability.UNKNOWN),
    ('contradictory_approval','attempt.bundle.approval.applicability',s.ApprovalApplicability.NOT_APPLICABLE),
    ('sample_rewrite','qualification.time.sample.utc',s.UtcInterval(11,11)),
    ('profile','qualification.time.profile.source','other'),
    ('process','qualification.time.point.process_id','other'),
    ('domain','qualification.time.point.domain_id','other'),
    ('propagation','qualification.time.propagation.elapsed_ns',1),
    ('bool_utc','qualification.permit.valid_from_us',True),
    ('oversized_command','attempt.bundle.canonical_command',b'x'*(2*g.c.MAX_ARTIFACT_BYTES)),
    ('oversized_evidence','qualification.exact_evidence',b'x'*(g.c.MAX_ARTIFACT_BYTES+1)),
    ('strict_permit_equality','qualification.permit.valid_until_us',10),
    ('not_valid_yet','qualification.permit.valid_from_us',11)):
    negative(name,path,value)


def interval_case(name,ticks,error,valid_until,prepared):
    def test(self):
        q=self.source.qualification
        object.__setattr__(q.time.point,'ticks_ns',ticks)
        object.__setattr__(q.time.propagation,'elapsed_ns',ticks)
        object.__setattr__(q.time.propagation,'error_ns',error)
        object.__setattr__(q.permit,'valid_until_us',valid_until)
        result=self.prepare()
        self.assertIs(result.state,e.PreparationState.PREPARED if prepared else e.PreparationState.FAIL_CLOSED)
        if prepared:
            self.assertEqual(result.material.fixed_utc_us,10+s.floor_us(ticks-error))
        self.permissions(result)
    setattr(EnvelopeTests,'test_interval_'+name,test)
for args in (('inclusive_auth_equality',10000,0,21,True),('auth_overlap',10000,1000,30,False),
             ('strict_freshness_equality',30000,0,50,False),('permit_overlap',9000,2000,20,False),
             ('outward_rounding',1500,500,20,True)):
    interval_case(*args)


class Foreign:
    calls=[]
    def __getattribute__(self,name): Foreign.calls.append('attribute'); raise AssertionError()
    def __getattr__(self,name): Foreign.calls.append('getattr'); raise AssertionError()
    def __eq__(self,other): Foreign.calls.append('eq'); raise AssertionError()
    def __hash__(self): Foreign.calls.append('hash'); raise AssertionError()
    def __repr__(self): Foreign.calls.append('repr'); raise AssertionError()
    def __str__(self): Foreign.calls.append('str'); raise AssertionError()
    def __iter__(self): Foreign.calls.append('iter'); raise AssertionError()
    def __call__(self,*args): Foreign.calls.append('call'); raise AssertionError()


def hostile_case(name):
    def test(self):
        Foreign.calls=[]
        if name=='subclass':
            class Bad(a.AcquisitionResult,Foreign): pass
            root=object.__new__(Bad)
        elif name=='dataclass':
            @dataclass(frozen=True)
            class Bad(Foreign): pass
            root=object.__new__(Bad)
        elif name=='metaclass':
            class Meta(type):
                def __eq__(self,other): Foreign.calls.append('meta_eq'); raise AssertionError()
                def __hash__(self): Foreign.calls.append('meta_hash'); raise AssertionError()
                def __getattribute__(self,name): Foreign.calls.append('meta_attr'); raise AssertionError()
            class Bad(metaclass=Meta): pass
            root=object.__new__(Bad)
        elif name=='enum':
            class Bad(StrEnum): QUALIFIED='QUALIFIED_ORIGINAL_PERMIT_OBSERVATION'
            root=self.source; object.__setattr__(root,'state',Bad.QUALIFIED)
        elif name=='primitive':
            class Bad(bytes,Foreign): pass
            root=self.source; mutate_path(root,'attempt.bundle.canonical_command',Bad(b'other'))
        elif name=='nested':
            root=self.source; mutate_path(root,'qualification.time.point',Foreign())
        else: root=Foreign()
        result=e.prepare_admission_envelope(root)
        self.assertIs(result.state,e.PreparationState.FAIL_CLOSED)
        self.assertEqual(Foreign.calls,[])
    setattr(EnvelopeTests,'test_hostile_'+name,test)
for name in ('root','callable','subclass','dataclass','metaclass','enum','primitive','nested'): hostile_case(name)


if __name__=='__main__': unittest.main()
