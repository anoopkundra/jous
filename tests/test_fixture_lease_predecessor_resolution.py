"""Synthetic qualified read fixtures only; no permits, provider or database."""
import ast
import copy
from dataclasses import FrozenInstanceError, dataclass, replace
from enum import StrEnum
from hashlib import sha256
import importlib.util
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
fixtures = runpy.run_path(str(ROOT/'tests/test_fixture_lease_checkpoints.py'))
s, p, q = fixtures['s'], fixtures['p'], fixtures['q']
spec = importlib.util.spec_from_file_location('_il4a_pure.fixture_lease_predecessor_resolution',
    ROOT/'services/api/infrastructure/fixture_lease_predecessor_resolution.py')
r = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r
spec.loader.exec_module(r)


class FakeResolver:
    def __init__(self, observed=None, error=None):
        self.observed, self.error, self.calls = observed, error, []
    def resolve_predecessor(self, activation):
        self.calls.append(activation)
        if self.error is not None: raise self.error
        return self.observed


def import_boundary(tree):
    expected = {(0,'dataclasses',(('dataclass',None),('fields',None))),
        (0,'enum',(('StrEnum',None),)),(0,'hashlib',(('sha256',None),)),
        (0,'types',(('FunctionType',None),('MethodType',None))),
        (1,None,(('fixture_lease_service','s'),)),
        (1,None,(('fixture_lease_protocol','p'),)),(1,None,(('fixture_lease_checkpoints','checkpoints'),))}
    seen=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import): return False
        if isinstance(node,ast.ImportFrom):seen.append((node.level,node.module,tuple((x.name,x.asname) for x in node.names)))
    return len(seen)==len(expected) and set(seen)==expected


class PredecessorResolutionTests(unittest.TestCase):
    def setUp(self):
        f=fixtures['CheckpointsTests']();f.setUp()
        self.predecessor=f.material()[0].predecessor
        self.ref=s.EvidenceReference('synthetic-qualification',b'q'*32)
        e=self.predecessor
        binding=r.CurrentBinding(e.activation,e.activation.host_identity,
            s.EvidenceReference('protected-authority',b'a'*32),e.representation,
            e.representation_authority,r.PredecessorProfile.NORMAL_COMMAND,e.revision,
            e.event_sequence,e.event_digest,e.state_digest)
        qualified=r.ContextQualification(binding,s.EvidenceValidity.VALID,self.ref,
            r.CurrentStatus.CURRENT,r.HostStatus.APPROVED,r.FencingStatus.CLEAR)
        self.context=r.QualifiedCurrentContext(binding,qualified)
        self.observed=r.ResolutionObservation(e,r.ResolutionQualification(self.context,e,s.EvidenceValidity.VALID,self.ref))

    def adapter(self, fake, expected=None, observed=None):
        # Explicit trusted TEST composition, independent of request-side labels.
        expected = self.context if expected is None else expected
        observed = self.observed if observed is None else observed
        return r.TrustedPredecessorAdapter(
            lambda context: s.EvidenceValidity.VALID if context == expected else s.EvidenceValidity.INVALID,
            fake.resolve_predecessor,
            lambda context, result: s.EvidenceValidity.VALID
                if context == expected and result == observed else s.EvidenceValidity.INVALID)

    def resolve(self, context=None, observed=None, error=None):
        fake=FakeResolver(self.observed if observed is None else observed,error)
        result=r.resolve_predecessor(self.context if context is None else context,self.adapter(fake))
        return result,fake

    def no_permission(self,result):
        for name in ('local_write_permitted','transaction_owned','sql_permitted','permit_acquisition_permitted',
            'candidate_retention_permitted','checkpoint_publication_permitted','permit_completion_permitted',
            'ack_delivery_permitted','active_permitted','fence_clearance_permitted','recovery_execution_permitted',
            'local_commit_confirmed','permit_owned','authoritative_absence','retry_permitted'):
            self.assertIs(getattr(result,name),False)

    def pre_closed(self,context,reason=None):
        fake=FakeResolver(self.observed)
        result=r.resolve_predecessor(context,self.adapter(fake,expected=context))
        self.assertIs(result.state,r.ResolutionState.FAIL_CLOSED);self.assertEqual(fake.calls,[])
        self.assertFalse(result.read_attempted);self.no_permission(result)
        if reason is not None:self.assertIs(result.reason,reason)
        return result

    def post_closed(self,observed,reason=None):
        fake=FakeResolver(observed)
        result=r.resolve_predecessor(self.context,self.adapter(fake))
        self.assertIs(result.state,r.ResolutionState.FAIL_CLOSED);self.assertEqual(fake.calls,[self.context.requested.activation])
        self.assertTrue(result.read_attempted);self.no_permission(result)
        if reason is not None:self.assertIs(result.reason,reason)
        return result

    def request(self,**changes):return replace(self.context,requested=replace(self.context.requested,**changes))
    def qualify(self,**changes):return replace(self.context,qualification=replace(self.context.qualification,**changes))
    def observation_for(self,predecessor):
        return r.ResolutionObservation(predecessor,r.ResolutionQualification(self.context,predecessor,s.EvidenceValidity.VALID,self.ref))
    def forged(self,base,**changes):
        value=copy.copy(base)
        for name,changed in changes.items():object.__setattr__(value,name,changed)
        return value

    def test_qualified_happy_path_one_read(self):
        result,fake=self.resolve()
        self.assertIs(result.state,r.ResolutionState.CHECKED)
        self.assertEqual(fake.calls,[self.context.requested.activation])
        self.assertIs(result.observation,self.observed)
        self.assertIs(result.observation.predecessor.exact_bytes,self.predecessor.exact_bytes)
        self.assertIs(result.observation.qualification,self.observed.qualification)
        self.no_permission(result)
    def test_exact_binding_preserved(self):
        result,_=self.resolve();self.assertEqual(result.context,self.context)
        self.assertEqual(result.observation.predecessor,self.predecessor)
        self.assertEqual(result.observation.qualification.context,self.context)
    def test_matching_construction_without_qualification_fails(self):
        self.post_closed(r.ResolutionObservation(self.predecessor,None),r.ResolutionReason.UNQUALIFIED_RESULT)
    def test_raw_frozen_result_cannot_qualify_itself(self):self.post_closed(self.predecessor,r.ResolutionReason.MALFORMED_RESULT)
    def test_missing_context(self):self.pre_closed(None,r.ResolutionReason.MISSING_CONTEXT)
    def test_malformed_context(self):self.pre_closed({'qualified':True},r.ResolutionReason.MALFORMED_CONTEXT)
    def test_missing_context_qualification(self):self.pre_closed(replace(self.context,qualification=None),r.ResolutionReason.UNQUALIFIED_CONTEXT)
    def test_unknown_context_qualification(self):self.pre_closed(self.qualify(validity=s.EvidenceValidity.UNKNOWN))
    def test_invalid_context_qualification(self):self.pre_closed(self.qualify(validity=s.EvidenceValidity.INVALID))
    def test_stale_activation(self):self.pre_closed(self.qualify(activation_status=r.CurrentStatus.SUPERSEDED))
    def test_unknown_activation(self):self.pre_closed(self.qualify(activation_status=r.CurrentStatus.UNKNOWN))
    def test_wrong_register_pre(self):self.pre_closed(self.request(activation=replace(self.context.requested.activation,register_id='other')))
    def test_wrong_generation_pre(self):self.pre_closed(self.request(activation=replace(self.context.requested.activation,generation=2)))
    def test_wrong_activation_pre(self):self.pre_closed(self.request(activation=replace(self.context.requested.activation,activation_id='other')))
    def test_wrong_host_pre(self):self.pre_closed(self.request(approved_host='other'))
    def test_unapproved_host_pre(self):self.pre_closed(self.qualify(host_status=r.HostStatus.UNAPPROVED))
    def test_unknown_host_pre(self):self.pre_closed(self.qualify(host_status=r.HostStatus.UNKNOWN))
    def test_fenced_pre(self):self.pre_closed(self.qualify(fencing_status=r.FencingStatus.FENCED))
    def test_recovery_only_pre(self):self.pre_closed(self.qualify(fencing_status=r.FencingStatus.RECOVERY_ONLY))
    def test_unknown_fencing_pre(self):self.pre_closed(self.qualify(fencing_status=r.FencingStatus.UNKNOWN))
    def test_representation_mismatch_pre(self):self.pre_closed(self.request(representation=p.STATE_1))
    def test_authority_reference_mismatch_pre(self):self.pre_closed(self.request(authority=s.EvidenceReference('other',b'x'*32)))
    def test_representation_authority_mismatch_pre(self):self.pre_closed(self.request(representation_authority=s.EvidenceReference('other',b'x'*32)))
    def test_unsupported_profile_pre(self):
        for profile in (r.PredecessorProfile.GENESIS,r.PredecessorProfile.REPLACEMENT):
            binding=replace(self.context.requested,profile=profile)
            self.pre_closed(replace(self.context,requested=binding,qualification=replace(self.context.qualification,binding=binding)),r.ResolutionReason.UNSUPPORTED_PROFILE)
    def test_qualified_unsupported_representation_pre(self):
        binding=replace(self.context.requested,representation=p.STATE_1)
        self.pre_closed(replace(self.context,requested=binding,qualification=replace(self.context.qualification,binding=binding)),r.ResolutionReason.UNSUPPORTED_PROFILE)
    def test_qualified_wrong_host_cannot_be_current(self):
        binding=replace(self.context.requested,approved_host='other')
        self.pre_closed(replace(self.context,requested=binding,qualification=replace(self.context.qualification,binding=binding)))
    def test_revision_overflow_pre(self):
        binding=replace(self.context.requested,revision=p.MAX_UINT)
        self.pre_closed(replace(self.context,requested=binding,qualification=replace(self.context.qualification,binding=binding)),r.ResolutionReason.REVISION)
    def test_non_normal_zero_head_pre(self):
        binding=replace(self.context.requested,revision=0,event_sequence=0)
        self.pre_closed(replace(self.context,requested=binding,qualification=replace(self.context.qualification,binding=binding)),r.ResolutionReason.REVISION)
    def test_wrong_activation_post(self):self.post_closed(self.observation_for(replace(self.predecessor,activation=replace(self.predecessor.activation,activation_id='other'))))
    def test_wrong_register_post(self):self.post_closed(self.observation_for(replace(self.predecessor,activation=replace(self.predecessor.activation,register_id='other'))))
    def test_wrong_generation_post(self):self.post_closed(self.observation_for(replace(self.predecessor,activation=replace(self.predecessor.activation,generation=2))))
    def test_wrong_host_post(self):self.post_closed(self.observation_for(replace(self.predecessor,activation=replace(self.predecessor.activation,host_identity='other'))))
    def test_wrong_revision_post(self):self.post_closed(self.observation_for(replace(self.predecessor,revision=2)))
    def test_wrong_head_post(self):self.post_closed(self.observation_for(replace(self.predecessor,event_sequence=4)))
    def test_wrong_event_digest_post(self):self.post_closed(self.observation_for(replace(self.predecessor,event_digest=b'x'*32)))
    def test_wrong_state_post(self):self.post_closed(self.observation_for(replace(self.predecessor,state_digest=b'x'*32)))
    def test_wrong_representation_post(self):self.post_closed(self.observation_for(replace(self.predecessor,representation=p.STATE_1)))
    def test_wrong_representation_authority_post(self):self.post_closed(self.observation_for(replace(self.predecessor,representation_authority=s.EvidenceReference('other',b'x'*32))))
    def test_wrong_representation_authority_digest_post(self):self.post_closed(self.observation_for(replace(self.predecessor,representation_authority=replace(self.predecessor.representation_authority,sha256=b'x'*32))))
    def test_missing_qualification_post(self):self.post_closed(replace(self.observed,qualification=None))
    def test_unknown_qualification_post(self):self.post_closed(replace(self.observed,qualification=replace(self.observed.qualification,validity=s.EvidenceValidity.UNKNOWN)))
    def test_invalid_qualification_post(self):self.post_closed(replace(self.observed,qualification=replace(self.observed.qualification,validity=s.EvidenceValidity.INVALID)))
    def test_qualification_context_mismatch(self):
        context=self.request(authority=s.EvidenceReference('other',b'x'*32))
        self.post_closed(replace(self.observed,qualification=replace(self.observed.qualification,context=context)),r.ResolutionReason.QUALIFICATION_MISMATCH)
    def test_qualification_predecessor_mismatch(self):
        other=replace(self.predecessor,revision=2)
        self.post_closed(replace(self.observed,qualification=replace(self.observed.qualification,predecessor=other)),r.ResolutionReason.QUALIFICATION_MISMATCH)
    def test_missing_result(self):self.post_closed(None,r.ResolutionReason.MISSING_RESULT)
    def test_malformed_result(self):self.post_closed('success',r.ResolutionReason.MALFORMED_RESULT)
    def test_wrong_bytes_stale_hash(self):
        bad=self.forged(self.predecessor,exact_bytes=self.predecessor.exact_bytes+b'x')
        self.post_closed(self.forged(self.observed,predecessor=bad),r.ResolutionReason.MALFORMED_RESULT)
    def test_wrong_digest(self):
        bad=self.forged(self.predecessor,reference=replace(self.predecessor.reference,sha256=b'x'*32))
        self.post_closed(self.forged(self.observed,predecessor=bad),r.ResolutionReason.MALFORMED_RESULT)
    def test_inherited_normal_frame_bound_before_hashing(self):
        maximum=len(p.PREFIX)+2+4+11*(4+p.MAX_FIELD)
        predecessor=self.forged(self.predecessor,exact_bytes=b'x'*(maximum+1))
        observed=self.forged(self.observed,predecessor=predecessor)
        with patch.object(s,'sha256',side_effect=AssertionError('unbounded hashing')):
            self.post_closed(observed,r.ResolutionReason.MALFORMED_RESULT)
    def test_wrong_predecessor_identity_post(self):
        pointer=replace(self.predecessor.reference,identity='foreign-pointer')
        activation=replace(self.predecessor.activation,checkpoint=pointer)
        predecessor=replace(self.predecessor,reference=pointer,activation=activation)
        self.post_closed(self.observation_for(predecessor),r.ResolutionReason.PREDECESSOR_MISMATCH)
    def test_equal_hash_claim_does_not_replace_qualified_exact_bytes(self):
        # Synthetic collision oracle: keep metadata/reference/digest identical
        # while changing canonical bytes. Qualification still retains the exact
        # original bytes, so equality of hashes cannot substitute another object.
        raw=q.checkpoint_bytes(replace(q.decode_checkpoint(self.predecessor.exact_bytes),utc_us=2))
        class CollisionDigest:
            def digest(self):return self.predecessor_digest
        digest=CollisionDigest();digest.predecessor_digest=self.predecessor.reference.sha256
        with patch.object(s,'sha256',return_value=digest):
            predecessor=replace(self.predecessor,exact_bytes=raw)
            observed=replace(self.observed,predecessor=predecessor)
            self.post_closed(observed,r.ResolutionReason.QUALIFICATION_MISMATCH)

    def coherent_wire_substitution(self,**changes):
        raw=q.checkpoint_bytes(replace(q.decode_checkpoint(self.predecessor.exact_bytes),**changes))
        pointer=s.EvidenceReference('new-pointer',sha256(raw).digest())
        activation=replace(self.predecessor.activation,checkpoint=pointer)
        predecessor=replace(self.predecessor,reference=pointer,exact_bytes=raw,activation=activation)
        binding=replace(self.context.requested,activation=activation)
        context=replace(self.context,requested=binding,qualification=replace(self.context.qualification,binding=binding))
        observation=r.ResolutionObservation(predecessor,r.ResolutionQualification(context,predecessor,s.EvidenceValidity.VALID,self.ref))
        fake=FakeResolver(observation);result=r.resolve_predecessor(context,self.adapter(fake,expected=context))
        self.assertEqual(len(fake.calls),1);self.assertIs(result.state,r.ResolutionState.FAIL_CLOSED)
        self.assertIs(result.reason,r.ResolutionReason.CHECKPOINT_MISMATCH)
        return result
    def test_rehashed_wrong_wire_revision_reaches_decoder_binding(self):self.coherent_wire_substitution(revision=2)
    def test_rehashed_wrong_wire_state_reaches_decoder_binding(self):self.coherent_wire_substitution(state_digest=b'x'*32)
    def test_rehashed_wrong_wire_host_reaches_decoder_binding(self):
        reference=replace(q.decode_checkpoint(self.predecessor.exact_bytes).reference,host='other')
        self.coherent_wire_substitution(reference=reference)
    def test_rehashed_unsupported_bytes_reject_no_sniffing(self):
        raw=b'unsupported';pointer=s.EvidenceReference('new-pointer',sha256(raw).digest())
        activation=replace(self.predecessor.activation,checkpoint=pointer)
        prior=replace(self.predecessor,exact_bytes=raw,reference=pointer,activation=activation)
        binding=replace(self.context.requested,activation=activation)
        context=replace(self.context,requested=binding,qualification=replace(self.context.qualification,binding=binding))
        observed=r.ResolutionObservation(prior,r.ResolutionQualification(context,prior,s.EvidenceValidity.VALID,self.ref))
        fake=FakeResolver(observed);result=r.resolve_predecessor(context,self.adapter(fake,expected=context))
        self.assertIs(result.reason,r.ResolutionReason.CHECKPOINT_MISMATCH);self.assertEqual(len(fake.calls),1)
    def test_default_rejecting_resolver(self):
        result=r.resolve_predecessor(self.context,self.adapter(s.RejectingNormalCapabilities()))
        self.assertIs(result.reason,r.ResolutionReason.UNAVAILABLE);self.assertTrue(result.read_attempted);self.no_permission(result)
    def test_no_resolver(self):
        result=r.resolve_predecessor(self.context,None)
        self.assertFalse(result.read_attempted);self.assertIs(result.reason,r.ResolutionReason.UNAVAILABLE)
    def test_wrong_capability_method_never_called(self):
        for method in (s.RejectingCapabilities().obtain,
            s.RejectingNormalCapabilities().associate_candidate,
            s.RejectingNormalCapabilities().publish_candidate,
            s.RejectingNormalCapabilities().complete_original):
            result=r.resolve_predecessor(self.context,method)
            self.assertFalse(result.read_attempted);self.assertIs(result.reason,r.ResolutionReason.UNAVAILABLE)
    def test_unnamed_arbitrary_callback_never_called(self):
        calls=[]
        def arbitrary_effect(activation):calls.append(activation);raise AssertionError('effect')
        result=r.resolve_predecessor(self.context,arbitrary_effect)
        self.assertEqual(calls,[]);self.assertFalse(result.read_attempted)
    def test_hostile_callable_name_rejected_without_equality(self):
        calls=[]
        class ForeignName(str):
            def __eq__(self,other):calls.append('eq');raise AssertionError('name callback')
            def __ne__(self,other):calls.append('ne');raise AssertionError('name callback')
        def resolve_predecessor(activation):calls.append('read');return self.observed
        resolve_predecessor.__name__=ForeignName('resolve_predecessor')
        result=r.resolve_predecessor(self.context,resolve_predecessor)
        self.assertFalse(result.read_attempted);self.assertEqual(calls,[])
    def test_resolver_exception_bounded_no_retry(self):
        for error in (RuntimeError('secret\n'+'x'*10000),ValueError('unsafe'),TimeoutError('lost')):
            result,fake=self.resolve(error=error)
            self.assertEqual(len(fake.calls),1);self.assertIs(result.reason,r.ResolutionReason.RESOLVER_EXCEPTION)
            self.assertIsNone(result.observation);self.assertLess(len(repr(result)),128);self.no_permission(result)
    def test_resolver_programming_assertion_distinguishable(self):
        fake=FakeResolver(error=AssertionError('programming defect'))
        with self.assertRaises(AssertionError):r.resolve_predecessor(self.context,self.adapter(fake))
        self.assertEqual(len(fake.calls),1)
    def test_internal_programming_assertion_not_swallowed(self):
        with patch.object(q,'decode_checkpoint',side_effect=AssertionError('internal defect')):
            with self.assertRaises(AssertionError):self.resolve()
    def test_function_injected_read(self):
        calls=[]
        def resolve_predecessor(activation):calls.append(activation);return self.observed
        adapter=r.TrustedPredecessorAdapter(lambda context:s.EvidenceValidity.VALID,
            resolve_predecessor,lambda context,observed:s.EvidenceValidity.VALID)
        result=r.resolve_predecessor(self.context,adapter)
        self.assertIs(result.state,r.ResolutionState.CHECKED);self.assertEqual(len(calls),1)
    def test_IL5PR_01_fabricated_valid_claims_without_adapter(self):
        # Rehashed, internally coherent synthetic lineage still has no authority.
        raw=q.checkpoint_bytes(replace(q.decode_checkpoint(self.predecessor.exact_bytes),
            register_id='fabricated',generation=2,activation_id='fabricated',
            reference=replace(q.decode_checkpoint(self.predecessor.exact_bytes).reference,host='fabricated')))
        pointer=s.EvidenceReference('fabricated',sha256(raw).digest())
        activation=replace(self.predecessor.activation,register_id='fabricated',generation=2,
                           activation_id='fabricated',host_identity='fabricated',checkpoint=pointer)
        pred=replace(self.predecessor,activation=activation,reference=pointer,exact_bytes=raw)
        binding=replace(self.context.requested,activation=activation,approved_host='fabricated',
            authority=s.EvidenceReference('fabricated-authority',b'f'*32))
        context=replace(self.context,requested=binding,qualification=replace(self.context.qualification,binding=binding))
        observed=r.ResolutionObservation(pred,r.ResolutionQualification(context,pred,s.EvidenceValidity.VALID,self.ref))
        fake=FakeResolver(observed)
        result=r.resolve_predecessor(context,None)
        self.assertIs(result.state,r.ResolutionState.FAIL_CLOSED);self.assertEqual(fake.calls,[])
        # Independent trusted verifier rejects fabricated lineage despite VALID claims.
        result=r.resolve_predecessor(context,self.adapter(fake))
        self.assertIs(result.reason,r.ResolutionReason.UNQUALIFIED_CONTEXT);self.assertEqual(fake.calls,[])

    def test_IL5PR_01_resolution_claim_cannot_self_certify(self):
        raw=q.checkpoint_bytes(replace(q.decode_checkpoint(self.predecessor.exact_bytes),utc_us=2))
        pointer=s.EvidenceReference('new-pointer',sha256(raw).digest())
        activation=replace(self.predecessor.activation,checkpoint=pointer)
        pred=replace(self.predecessor,activation=activation,reference=pointer,exact_bytes=raw)
        binding=replace(self.context.requested,activation=activation)
        context=replace(self.context,requested=binding,qualification=replace(self.context.qualification,binding=binding))
        observed=r.ResolutionObservation(pred,r.ResolutionQualification(context,pred,s.EvidenceValidity.VALID,self.ref))
        self.assertIsNone(r._postcheck(context,observed))
        fake=FakeResolver(observed)
        result=r.resolve_predecessor(context,self.adapter(fake,expected=context))
        self.assertIs(result.reason,r.ResolutionReason.UNQUALIFIED_RESULT)
        self.assertEqual(len(fake.calls),1);self.no_permission(result)

    def test_IL5PR_02_callable_descriptor_name_never_inspected(self):
        calls=[]
        class Foreign:
            @property
            def __name__(self):calls.append('name');raise AssertionError('descriptor')
            def __call__(self,*args):calls.append('call');raise AssertionError('effect')
        result=r.resolve_predecessor(self.context,Foreign())
        self.assertIs(result.reason,r.ResolutionReason.UNAVAILABLE);self.assertEqual(calls,[])

    def test_IL5PR_02_plain_named_function_rejected(self):
        calls=[]
        def resolve_predecessor(activation):calls.append(activation);return self.observed
        result=r.resolve_predecessor(self.context,resolve_predecessor)
        self.assertIs(result.reason,r.ResolutionReason.UNAVAILABLE);self.assertEqual(calls,[])

    def test_IL5PR_02_unrelated_named_method_rejected(self):
        fake=FakeResolver(self.observed)
        result=r.resolve_predecessor(self.context,fake.resolve_predecessor)
        self.assertIs(result.reason,r.ResolutionReason.UNAVAILABLE);self.assertEqual(fake.calls,[])

    def test_trusted_composition_exact_order(self):
        events=[]
        def context_check(context):events.append('context');return s.EvidenceValidity.VALID
        def read(activation):events.append('read');return self.observed
        def resolution_check(context,observed):events.append('resolution');return s.EvidenceValidity.VALID
        adapter=r.TrustedPredecessorAdapter(context_check,read,resolution_check)
        result=r.resolve_predecessor(self.context,adapter)
        self.assertIs(result.state,r.ResolutionState.CHECKED)
        self.assertEqual(events,['context','read','resolution']);self.no_permission(result)

    def qualification_failure(self,stage,verdict=None,error=None):
        events=[];fake=FakeResolver(self.observed)
        def check(*values):
            events.append(stage)
            if error is not None:raise error
            return verdict
        adapter=r.TrustedPredecessorAdapter(check if stage=='context' else lambda context:s.EvidenceValidity.VALID,
            fake.resolve_predecessor,check if stage=='resolution' else lambda context,observed:s.EvidenceValidity.VALID)
        result=r.resolve_predecessor(self.context,adapter)
        self.assertIs(result.state,r.ResolutionState.FAIL_CLOSED)
        self.assertEqual(len(fake.calls),0 if stage=='context' else 1)
        self.assertEqual(events,[stage]);self.no_permission(result)
        return result

    def test_context_verification_unavailable(self):self.qualification_failure('context',error=s.CapabilityUnavailable())
    def test_context_verification_unknown(self):self.qualification_failure('context',s.EvidenceValidity.UNKNOWN)
    def test_context_verification_rejected(self):self.qualification_failure('context',s.EvidenceValidity.INVALID)
    def test_resolution_verification_unavailable(self):self.qualification_failure('resolution',error=s.CapabilityUnavailable())
    def test_resolution_verification_unknown(self):self.qualification_failure('resolution',s.EvidenceValidity.UNKNOWN)
    def test_resolution_verification_rejected(self):self.qualification_failure('resolution',s.EvidenceValidity.INVALID)
    def test_verifier_ordinary_external_exception_bounded(self):
        for stage in ('context','resolution'):self.qualification_failure(stage,error=RuntimeError('sensitive'*1000))
    def test_verifier_assertion_propagates(self):
        for stage in ('context','resolution'):
            with self.assertRaises(AssertionError):self.qualification_failure(stage,error=AssertionError('programming'))
    def test_foreign_verifier_return_no_callbacks(self):
        calls=[]
        class Foreign:
            def __getattribute__(self,name):calls.append(name);raise AssertionError('callback')
            def __eq__(self,other):calls.append('eq');raise AssertionError('callback')
        for stage in ('context','resolution'):self.qualification_failure(stage,object.__new__(Foreign))
        self.assertEqual(calls,[])
    def test_adapter_confusion_request_and_witness(self):
        for value in (self.context,self.context.qualification,self.observed.qualification,self.observed):
            result=r.resolve_predecessor(self.context,value)
            self.assertIs(result.reason,r.ResolutionReason.UNAVAILABLE);self.assertFalse(result.read_attempted)
    def test_adapter_subclass_rejected_without_callbacks(self):
        calls=[]
        class Foreign(r.TrustedPredecessorAdapter):
            def __getattribute__(self,name):calls.append(name);raise AssertionError('callback')
        result=r.resolve_predecessor(self.context,object.__new__(Foreign))
        self.assertIs(result.reason,r.ResolutionReason.UNAVAILABLE);self.assertEqual(calls,[])
    def test_adapter_hostile_metaclass_no_callbacks(self):
        calls=[]
        class Meta(type):
            def __eq__(self,other):calls.append('eq');raise AssertionError('callback')
            def __getattribute__(self,name):calls.append(name);raise AssertionError('callback')
        class Foreign(metaclass=Meta):pass
        result=r.resolve_predecessor(self.context,object.__new__(Foreign))
        self.assertIs(result.reason,r.ResolutionReason.UNAVAILABLE);self.assertEqual(calls,[])
    def test_malformed_adapter_callback_rejected_without_execution(self):
        calls=[]
        class Foreign:
            def __getattribute__(self,name):calls.append(name);raise AssertionError('callback')
            def __call__(self,*args):calls.append('call');raise AssertionError('callback')
        adapter=self.forged(self.adapter(FakeResolver(self.observed)),verify_context=object.__new__(Foreign))
        result=r.resolve_predecessor(self.context,adapter)
        self.assertIs(result.reason,r.ResolutionReason.UNAVAILABLE);self.assertEqual(calls,[])
    def test_structural_failure_zero_qualification_calls(self):
        events=[]
        def check(*values):events.append('verification');raise AssertionError('too early')
        adapter=r.TrustedPredecessorAdapter(check,check,check)
        for context in (self.hostile_pre(object()),self.qualify(fencing_status=r.FencingStatus.FENCED),
                        self.request(representation=p.STATE_1),None):
            result=r.resolve_predecessor(context,adapter)
            self.assertIs(result.state,r.ResolutionState.FAIL_CLOSED)
        self.assertEqual(events,[])
    def test_structural_result_failure_zero_resolution_verification(self):
        events=[];fake=FakeResolver(self.hostile_post(object()))
        def check(*values):events.append('verification');raise AssertionError('too early')
        adapter=r.TrustedPredecessorAdapter(lambda context:s.EvidenceValidity.VALID,fake.resolve_predecessor,check)
        result=r.resolve_predecessor(self.context,adapter)
        self.assertIs(result.reason,r.ResolutionReason.MALFORMED_RESULT)
        self.assertEqual(len(fake.calls),1);self.assertEqual(events,[])
    def test_internal_runtime_error_propagates(self):
        with patch.object(q,'decode_checkpoint',side_effect=RuntimeError('internal defect')):
            with self.assertRaises(RuntimeError):self.resolve()
    def test_public_checked_result_cannot_self_certify(self):
        with self.assertRaises(TypeError):r.ResolutionResult(self.context,self.observed,True,
            r.ResolutionState.CHECKED,r.ResolutionReason.CHECKED)
    def test_adapter_immutable(self):
        adapter=self.adapter(FakeResolver(self.observed))
        with self.assertRaises(FrozenInstanceError):adapter.read=lambda activation:self.observed

    def test_no_other_capability(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name in ('resolve_envelope','associate_candidate','publish_candidate','query_publication','complete_original','query_completion'):
                stack.enter_context(patch.object(s.RejectingNormalCapabilities,name,side_effect=AssertionError('effect')))
            stack.enter_context(patch.object(s.RejectingCapabilities,'obtain',side_effect=AssertionError('permit')))
            result,_=self.resolve();self.assertIs(result.state,r.ResolutionState.CHECKED)
    def test_no_io_clock_environment_owned_by_boundary(self):
        with (patch('builtins.open',side_effect=AssertionError('filesystem')),
              patch('time.time',side_effect=AssertionError('clock')),
              patch('os.getenv',side_effect=AssertionError('environment'))):
            result,_=self.resolve();self.assertIs(result.state,r.ResolutionState.CHECKED)
    def test_frozen_decoder_exercised(self):
        with patch.object(q,'decode_checkpoint',wraps=q.decode_checkpoint) as decoder:
            self.resolve();self.assertGreater(decoder.call_count,0)
    def test_immutable_result_and_evidence(self):
        result,_=self.resolve()
        for value in (self.context,self.context.requested,self.context.qualification,self.observed,self.observed.qualification,result):
            with self.assertRaises(FrozenInstanceError):value.extra=True
    def test_direct_result_contradictions(self):
        good,_=self.resolve();bad=self.post_closed(replace(self.observed,qualification=None))
        for result in (good,bad):
            with self.assertRaises(TypeError):replace(result,state=r.ResolutionState.CHECKED if result.state is r.ResolutionState.FAIL_CLOSED else r.ResolutionState.FAIL_CLOSED)
            with self.assertRaises(TypeError):replace(result,reason=r.ResolutionReason.UNAVAILABLE)
            with self.assertRaises(TypeError):replace(result,read_attempted=False)
    def test_permissions_cannot_be_constructor_fields(self):
        result,_=self.resolve()
        for name in ('local_commit_confirmed','permit_owned','active_permitted','ack_delivery_permitted','retry_permitted'):
            with self.assertRaises(TypeError):replace(result,**{name:True})
    def test_bool_integer_and_subclass_rejected(self):
        for name in ('revision','event_sequence'):
            with self.assertRaises((s.TimeRejected,p.ProtocolRejected)):replace(self.context.requested,**{name:True})
        with self.assertRaises(s.TimeRejected):replace(self.context.requested,activation=replace(self.predecessor.activation,generation=True))
    def test_redacted_bounded_diagnostics(self):
        result,_=self.resolve()
        self.assertLess(len(repr(result)),128);self.assertNotIn('synthetic',repr(result))
        self.assertTrue(all(len(x.value)<=32 for x in r.ResolutionReason))

    def hostile_pre(self,foreign):
        binding=self.forged(self.context.requested,authority=foreign)
        return self.forged(self.context,requested=binding)
    def hostile_post(self,foreign):
        predecessor=self.forged(self.predecessor,representation_authority=foreign)
        return self.forged(self.observed,predecessor=predecessor)
    def hostile(self,method):
        calls=[]
        def callback(instance,*args):calls.append(method);raise AssertionError('foreign callback')
        cls=type('Foreign',(),{method:callback})
        foreign=object.__new__(cls)
        self.pre_closed(self.hostile_pre(foreign),r.ResolutionReason.MALFORMED_CONTEXT)
        self.post_closed(self.hostile_post(foreign),r.ResolutionReason.MALFORMED_RESULT)
        self.assertEqual(calls,[])
    def test_hostile_getattribute(self):self.hostile('__getattribute__')
    def test_hostile_getattr(self):self.hostile('__getattr__')
    def test_hostile_iteration(self):self.hostile('__iter__')
    def test_hostile_equality(self):self.hostile('__eq__')
    def test_hostile_hash(self):self.hostile('__hash__')
    def test_hostile_repr(self):self.hostile('__repr__')
    def test_hostile_str(self):self.hostile('__str__')
    def test_hostile_dataclass(self):
        calls=[]
        @dataclass(frozen=True)
        class Foreign:
            def __getattribute__(self,name):calls.append(name);raise AssertionError('callback')
            def __post_init__(self):calls.append('post_init');raise AssertionError('callback')
        foreign=object.__new__(Foreign)
        self.pre_closed(self.hostile_pre(foreign));self.post_closed(self.hostile_post(foreign));self.assertEqual(calls,[])
    def test_hostile_enum(self):
        calls=[]
        class Foreign(StrEnum):
            ITEM='foreign'
            def __getattribute__(self,name):calls.append(name);return object.__getattribute__(self,name)
        foreign=Foreign.ITEM;calls.clear()
        self.pre_closed(self.hostile_pre(foreign));self.post_closed(self.hostile_post(foreign));self.assertEqual(calls,[])
    def test_hostile_primitive_subclasses(self):
        for base,arg in ((str,'foreign'),(bytes,b'foreign'),(int,1)):
            calls=[]
            def access(instance,name):calls.append(name);raise AssertionError('callback')
            cls=type('Foreign',(base,),{'__getattribute__':access});foreign=cls(arg)
            self.pre_closed(self.hostile_pre(foreign));self.post_closed(self.hostile_post(foreign));self.assertEqual(calls,[])
    def test_hostile_metaclass(self):
        calls=[]
        class Meta(type):
            def __getattribute__(cls,name):calls.append(name);raise AssertionError('class callback')
            def __eq__(cls,other):calls.append('eq');raise AssertionError('class callback')
            def __hash__(cls):calls.append('hash');raise AssertionError('class callback')
        class Foreign(metaclass=Meta):pass
        foreign=object.__new__(Foreign)
        self.pre_closed(self.hostile_pre(foreign));self.post_closed(self.hostile_post(foreign));self.assertEqual(calls,[])
    def test_hostile_value_subclass(self):
        calls=[]
        class Foreign(s.EvidenceReference):
            def __getattribute__(self,name):calls.append(name);raise AssertionError('callback')
        foreign=object.__new__(Foreign)
        self.pre_closed(self.hostile_pre(foreign));self.post_closed(self.hostile_post(foreign));self.assertEqual(calls,[])
    def test_untrusted_resolver_object_not_inspected(self):
        calls=[]
        class Foreign:
            def __getattribute__(self,name):calls.append(name);raise AssertionError('callback')
            def __call__(self,*args):calls.append('call');raise AssertionError('callback')
        result=r.resolve_predecessor(self.context,object.__new__(Foreign))
        self.assertIs(result.reason,r.ResolutionReason.UNAVAILABLE);self.assertFalse(result.read_attempted);self.assertEqual(calls,[])
    def test_architecture_and_hostile_classifier_guard(self):
        tree=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_predecessor_resolution.py').read_text())
        self.assertTrue(import_boundary(tree))
        forbidden={'isinstance','is_dataclass','hasattr','open','connect','execute','getenv','now','time','sleep',
                   'run','obtain','associate_candidate','publish_candidate','complete_original','query_completion'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr','')
                self.assertNotIn(name,forbidden)
    def test_prohibited_imports(self):
        for name in ('fixture_lease_commands','fixture_lease_store','provider','sqlite3','requests','subprocess','os','runtime'):
            self.assertFalse(import_boundary(ast.parse('from . import '+name)))


if __name__=='__main__':unittest.main(verbosity=2)
