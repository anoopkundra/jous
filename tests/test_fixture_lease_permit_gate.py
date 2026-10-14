"""Deterministic synthetic pre-permit qualification tests; no operational effects."""
import ast
import copy
from dataclasses import dataclass, replace, FrozenInstanceError
from enum import StrEnum
from hashlib import sha256
import importlib.util
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
old = runpy.run_path(str(ROOT/'tests/test_fixture_lease_predecessor_resolution.py'))
s, p, pr = old['s'], old['p'], old['r']
c = p.contract
spec = importlib.util.spec_from_file_location('_il4a_pure.fixture_lease_permit_gate',
    ROOT/'services/api/infrastructure/fixture_lease_permit_gate.py')
g = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = g
spec.loader.exec_module(g)


def forged(value, **changes):
    result = copy.copy(value)
    for name, change in changes.items(): object.__setattr__(result, name, change)
    return result


PERMISSIONS = ('permit_acquisition_permitted', 'transaction_owned', 'local_mutation_permitted',
    'sql_permitted', 'candidate_retention_permitted', 'publication_permitted', 'completion_permitted',
    'ack_delivery_permitted', 'active_permitted', 'retry_permitted', 'fence_clearance_permitted',
    'recovery_execution_permitted', 'local_commit_confirmed', 'permit_owned', 'envelope_retained',
    'fixed_utc_established')


class GateTests(unittest.TestCase):
    def setUp(self):
        previous = old['PredecessorResolutionTests'](); previous.setUp()
        fake = old['FakeResolver'](previous.observed)
        predecessor = pr.resolve_predecessor(previous.context, previous.adapter(fake))
        f = old['fixtures']['CheckpointsTests'](); f.setUp()
        self.artifact = c.ArtifactBytes(c.ArtifactType.PROVISIONING_REQUEST, b'synthetic-binding')
        command = f.values['command']
        reference = replace(command.binding_reference, artifact_sha256=self.artifact.evidence_sha256)
        command = replace(command, command_id='new-command', binding_sha256=reference.artifact_sha256,
                          binding_reference=reference, parameters=replace(command.parameters, new_binding=reference))
        context = self.command_context(command)
        requester = s.AuthenticatedRequester(command.authenticated_principal, s.EvidenceReference('authentication', b'r'*32))
        activation = predecessor.context.requested.activation
        authorization = g.AuthorizationEvidence(context, requester.principal, activation, context.authorization,
            s.EvidenceValidity.VALID, 0, s.InclusiveDeadline(20))
        approval_ref = s.EvidenceReference('approval', command.approval_record_hash)
        approval = g.ApprovalEvidence(s.ApprovalApplicability.REQUIRED,
            s.VerifiedApproval('independent', requester.principal, context, self.artifact, approval_ref),
            approval_ref, s.EvidenceValidity.VALID, 0, s.InclusiveDeadline(30))
        profile_ref = s.EvidenceReference('profile', b't'*32)
        sample_ref = s.EvidenceReference('sample', b'u'*32)
        point = s.MonotonicPoint('process', 'domain', 0)
        sample = s.QualifiedSample(sample_ref, 'synthetic-source', profile_ref,
            s.EvidenceReference('sample-validation', b'v'*32), s.UtcInterval(10, 10), point)
        profile = s.QualifiedClockProfile(profile_ref, 'synthetic-source', s.EvidenceReference('profile-validation', b'w'*32),
            100000, 100, 100, 100)
        propagation = s.QualifiedPropagationError(sample_ref, profile_ref, 0, 0, s.EvidenceReference('propagation', b'x'*32))
        time = g.TimeEvidence(sample, profile, point, propagation, s.TimingApplicability.REQUIRED,
            s.StrictDeadline(40), s.TimingApplicability.NOT_APPLICABLE, None)
        history = g.HistoryEvidence(context, activation, s.EvidenceReference('history', b'h'*32),
            g.CommandHistory.NEW, g.GapKnowledge.CLEAR, g.GapKnowledge.CLEAR, g.GapKnowledge.CLEAR,
            pr.CurrentStatus.CURRENT, pr.HostStatus.APPROVED, pr.FencingStatus.CLEAR)
        self.bundle = g.PrerequisiteBundle(p.command_bytes(command), command, context, requester,
            authorization, predecessor, activation, 'h', approval, time, history)
        self.ref = s.EvidenceReference('verified-bundle', b'q'*32)

    def command_context(self, command):
        return s.CommandContext(command.command_id, sha256(p.command_bytes(command)).digest(), command.command_kind,
            command.operation, command.phase, command.expected_revision,
            s.EvidenceReference(command.authorization_reference.artifact_id, command.authorization_reference.artifact_sha256))

    def evaluate(self, bundle=None, expected=None, validity=s.EvidenceValidity.VALID, error=None):
        bundle = self.bundle if bundle is None else bundle
        expected = self.bundle if expected is None else expected
        calls = []
        def verify(value):
            calls.append(value)
            if error is not None: raise error
            return g.QualificationEvidence(expected, validity if value == expected else s.EvidenceValidity.INVALID, self.ref)
        result = g.evaluate_prerequisites(bundle, g.TrustedPrerequisiteVerifier(verify))
        return result, calls

    def closed(self, bundle, reason=None):
        result, calls = self.evaluate(bundle)
        self.assertIsNot(result.state, g.GateState.CHECKED)
        self.assertEqual(calls, [])
        if reason is not None: self.assertIs(result.reason, reason)
        self.permissions(result)
        return result

    def permissions(self, result):
        for name in PERMISSIONS: self.assertIs(getattr(result, name), False)

    def interval(self, lower, upper):
        return replace(self.bundle, time=replace(self.bundle.time,
            sample=replace(self.bundle.time.sample, utc=s.UtcInterval(lower, upper))))

    def test_coherent_checked_success(self):
        result, calls = self.evaluate()
        self.assertIs(result.state, g.GateState.CHECKED); self.assertEqual(calls, [self.bundle])
        self.assertIs(result.bundle, self.bundle); self.assertEqual(result.qualification.bundle, self.bundle)
        self.assertEqual(result.time_evaluation.interval, s.UtcInterval(10, 10)); self.permissions(result)

    def test_constructor_claims_no_verifier_fail_closed(self):
        result = g.evaluate_prerequisites(self.bundle)
        self.assertIs(result.reason, g.GateReason.UNAVAILABLE); self.permissions(result)

    def test_fabricated_matching_approval_cannot_qualify(self):
        # All reference/hash labels cohere; independently configured verifier rejects the fabricated identity.
        ref = replace(self.bundle.approval.reference, identity='fabricated')
        approval = replace(self.bundle.approval, reference=ref,
            verified=replace(self.bundle.approval.verified, evidence=ref))
        result, calls = self.evaluate(replace(self.bundle, approval=approval))
        self.assertEqual(len(calls), 1); self.assertIs(result.reason, g.GateReason.UNQUALIFIED)

    def test_fabricated_matching_predecessor_cannot_qualify(self):
        claimed = forged(self.bundle.predecessor, context=replace(self.bundle.predecessor.context,
            qualification=replace(self.bundle.predecessor.context.qualification,
                reference=s.EvidenceReference('fabricated', b'f'*32))))
        # Change both redundant witnesses coherently; no constructor success establishes provenance.
        observed = replace(claimed.observation, qualification=replace(claimed.observation.qualification, context=claimed.context))
        claimed = forged(claimed, observation=observed)
        result, calls = self.evaluate(replace(self.bundle, predecessor=claimed))
        self.assertEqual(len(calls), 1); self.assertIs(result.reason, g.GateReason.UNQUALIFIED)

    def test_not_applicable_record_execution(self):
        command = p.decode_record(old['fixtures']['D'], p.CommandPayload)
        command = replace(command, command_id='new-execution'); context = self.command_context(command)
        bundle = replace(self.bundle, command=command, canonical_command=p.command_bytes(command), context=context,
            authorization=replace(self.bundle.authorization, context=context),
            approval=g.ApprovalEvidence(s.ApprovalApplicability.NOT_APPLICABLE, None, None, s.EvidenceValidity.VALID, None, None),
            history=replace(self.bundle.history, context=context))
        result, calls = self.evaluate(bundle, expected=bundle)
        self.assertIs(result.state, g.GateState.CHECKED); self.assertEqual(len(calls), 1); self.permissions(result)

    def test_equal_digest_unequal_canonical_bytes(self):
        raw = p.command_bytes(replace(self.bundle.command, command_id='different'))
        class Collision:
            def digest(inner): return self.bundle.context.payload_sha256
        with patch.object(g, 'sha256', return_value=Collision()):
            self.closed(replace(self.bundle, canonical_command=raw), g.GateReason.COMMAND)

    def test_predecessor_equal_digest_unequal_bytes(self):
        pred = self.bundle.predecessor.observation.predecessor
        altered = forged(pred, exact_bytes=pred.exact_bytes+b'x')
        observation = forged(self.bundle.predecessor.observation, predecessor=altered)
        result = forged(self.bundle.predecessor, observation=observation)
        self.closed(forged(self.bundle, predecessor=result), g.GateReason.MALFORMED)

    def test_authorization_inclusive_equality(self):
        bundle = self.interval(20, 20)
        result, _ = self.evaluate(bundle, expected=bundle); self.assertIs(result.state, g.GateState.CHECKED)
    def test_authorization_overlap(self): self.closed(self.interval(19, 21), g.GateReason.TIME)
    def test_authorization_definitely_expired(self): self.closed(self.interval(21, 21), g.GateReason.TIME)
    def test_valid_from_equal(self):
        bundle = replace(self.bundle, authorization=replace(self.bundle.authorization, valid_from_us=10))
        result, _ = self.evaluate(bundle, expected=bundle); self.assertIs(result.state, g.GateState.CHECKED)
    def test_valid_from_too_early(self):
        self.closed(replace(self.bundle, authorization=replace(self.bundle.authorization, valid_from_us=11)), g.GateReason.TIME)
    def test_strict_freshness_equal(self):
        self.closed(replace(self.bundle, time=replace(self.bundle.time, freshness_deadline=s.StrictDeadline(10))), g.GateReason.TIME)
    def test_strict_lease_equal(self):
        self.closed(replace(self.bundle, time=replace(self.bundle.time, lease_applicability=s.TimingApplicability.REQUIRED,
            lease_deadline=s.StrictDeadline(10))), g.GateReason.TIME)
    def test_approval_expired(self):
        self.closed(replace(self.bundle, approval=replace(self.bundle.approval, deadline=s.InclusiveDeadline(9))), g.GateReason.TIME)
    def test_approval_not_yet_valid(self):
        self.closed(replace(self.bundle, approval=replace(self.bundle.approval, valid_from_us=11)), g.GateReason.TIME)
    def test_approval_self_approval_rejected(self):
        bad = forged(self.bundle.approval.verified, approver=self.bundle.requester.principal)
        self.closed(forged(self.bundle, approval=forged(self.bundle.approval, verified=bad)), g.GateReason.MALFORMED)
    def test_time_exact_outward_rounding(self):
        time = replace(self.bundle.time, point=replace(self.bundle.time.point, ticks_ns=1),
            propagation=replace(self.bundle.time.propagation, elapsed_ns=1, error_ns=2))
        bundle = replace(self.bundle, time=time)
        result, _ = self.evaluate(bundle, expected=bundle)
        self.assertEqual(result.time_evaluation.interval, s.UtcInterval(9, 11))
    def test_no_fixed_envelope_utc(self):
        result, _ = self.evaluate(); self.assertFalse(result.fixed_utc_established)
        self.assertFalse(hasattr(result, 'fixed_utc_us'))

    def test_verifier_wrong_bundle_binding(self):
        other = replace(self.bundle, requester=replace(self.bundle.requester, evidence=replace(self.bundle.requester.evidence, identity='other')))
        result = g.evaluate_prerequisites(self.bundle, g.TrustedPrerequisiteVerifier(
            lambda bundle:g.QualificationEvidence(other, s.EvidenceValidity.VALID, self.ref)))
        self.assertIs(result.reason, g.GateReason.QUALIFICATION_BINDING)
    def test_verifier_cannot_replace_original_bundle_by_coherent_mutation(self):
        # A trusted-code mutation probe must not change what this evaluation binds.
        bundle = copy.copy(self.bundle)
        def verify(value):
            object.__setattr__(value, 'requester', replace(value.requester,
                evidence=s.EvidenceReference('replacement-authentication', b'z'*32)))
            return g.QualificationEvidence(value, s.EvidenceValidity.VALID, self.ref)
        result = g.evaluate_prerequisites(bundle, g.TrustedPrerequisiteVerifier(verify))
        self.assertIs(result.reason, g.GateReason.QUALIFICATION_BINDING)
    def test_returned_response_nested_foreign_callback_zero(self):
        callbacks=[]
        class Foreign:
            def __getattribute__(inner, name): callbacks.append(name); raise AssertionError('foreign')
        def verify(bundle):
            qualified = g.QualificationEvidence(bundle, s.EvidenceValidity.VALID, self.ref)
            return forged(qualified, reference=object.__new__(Foreign))
        result = g.evaluate_prerequisites(self.bundle, g.TrustedPrerequisiteVerifier(verify))
        self.assertIs(result.reason, g.GateReason.UNQUALIFIED); self.assertEqual(callbacks, [])
    def test_failed_predecessor_never_reinterpreted(self):
        result = pr.resolve_predecessor(self.bundle.predecessor.context, None)
        self.closed(replace(self.bundle, predecessor=result), g.GateReason.PREDECESSOR)
    def test_predecessor_revision_head_substitution(self):
        for field, value in (('revision',2),('event_sequence',4),('event_digest',b'z'*32),('state_digest',b'z'*32)):
            pred = replace(self.bundle.predecessor.observation.predecessor, **{field:value})
            observation = replace(self.bundle.predecessor.observation, predecessor=pred,
                qualification=replace(self.bundle.predecessor.observation.qualification, predecessor=pred))
            self.closed(replace(self.bundle, predecessor=forged(self.bundle.predecessor, observation=observation)),
                g.GateReason.PREDECESSOR)
    def test_result_revalidation_rejects_copied_contradiction(self):
        result, _ = self.evaluate()
        with self.assertRaises(s.TimeRejected):
            g.GateResult.__post_init__(forged(result, state=g.GateState.HANDOFF))
    def test_primitive_subclasses_callback_zero(self):
        for base, arg in ((str,'foreign'),(bytes,b'foreign'),(int,1)):
            callbacks=[]
            def hook(*args): callbacks.append('hook'); raise AssertionError('foreign')
            cls=type('Foreign',(base,),{'__getattribute__':hook})
            self.hostile(cls(arg)); self.assertEqual(callbacks, [])
    def test_adapter_cannot_be_hidden_inside_request(self):
        adapter = g.TrustedPrerequisiteVerifier(lambda bundle:None)
        self.closed(forged(self.bundle, requester=forged(self.bundle.requester, evidence=adapter)), g.GateReason.MALFORMED)
    def test_verifier_unknown(self):
        result, calls = self.evaluate(validity=s.EvidenceValidity.UNKNOWN)
        self.assertEqual(len(calls), 1); self.assertIs(result.reason, g.GateReason.UNQUALIFIED)
    def test_verifier_reject(self):
        result, calls = self.evaluate(validity=s.EvidenceValidity.INVALID)
        self.assertEqual(len(calls), 1); self.assertIs(result.reason, g.GateReason.UNQUALIFIED)
    def test_verifier_unavailable(self):
        result, calls = self.evaluate(error=s.CapabilityUnavailable())
        self.assertEqual(len(calls), 1); self.assertIs(result.reason, g.GateReason.UNAVAILABLE)
    def test_ordinary_verifier_failure_redacted(self):
        result, calls = self.evaluate(error=RuntimeError('sensitive\n'*1000))
        self.assertEqual(len(calls), 1); self.assertIs(result.reason, g.GateReason.UNAVAILABLE)
        self.assertNotIn('sensitive', repr(result)); self.assertLess(len(repr(result)), 128)
    def test_callback_failure_cannot_retain_malformed_mutated_input(self):
        bundle = copy.copy(self.bundle)
        def verify(value):
            object.__setattr__(value, 'requester', object())
            raise RuntimeError('external read failed')
        result = g.evaluate_prerequisites(bundle, g.TrustedPrerequisiteVerifier(verify))
        self.assertIs(result.reason, g.GateReason.MALFORMED); self.assertIsNone(result.bundle)
    def test_verifier_assertion_propagates(self):
        with self.assertRaises(AssertionError): self.evaluate(error=AssertionError('programming'))
    def test_internal_runtime_error_propagates(self):
        with patch.object(p, 'decode_record', side_effect=RuntimeError('internal')):
            with self.assertRaises(RuntimeError): self.evaluate()
    def test_internal_assertion_propagates(self):
        with patch.object(s, 'evaluate_time', side_effect=AssertionError('internal')):
            with self.assertRaises(AssertionError): self.evaluate()
    def test_fabricated_response_in_request_cannot_replace_verifier(self):
        claim = g.QualificationEvidence(self.bundle, s.EvidenceValidity.VALID, self.ref)
        result = g.evaluate_prerequisites(self.bundle, claim)
        self.assertIs(result.reason, g.GateReason.UNAVAILABLE)
    def test_raw_same_name_function_rejected(self):
        calls=[]
        def verify(bundle): calls.append(bundle); raise AssertionError('effect')
        result = g.evaluate_prerequisites(self.bundle, verify)
        self.assertIs(result.reason, g.GateReason.UNAVAILABLE); self.assertEqual(calls, [])
    def test_unrelated_method_rejected(self):
        calls=[]
        class Owner:
            def verify(inner, bundle): calls.append(bundle); raise AssertionError('effect')
        result = g.evaluate_prerequisites(self.bundle, Owner().verify)
        self.assertIs(result.reason, g.GateReason.UNAVAILABLE); self.assertEqual(calls, [])
    def test_verifier_malformed_return_no_callbacks(self):
        calls=[]
        class Foreign:
            def __getattribute__(inner, name): calls.append(name); raise AssertionError('foreign')
        result = g.evaluate_prerequisites(self.bundle, g.TrustedPrerequisiteVerifier(lambda bundle:object.__new__(Foreign)))
        self.assertIs(result.reason, g.GateReason.UNQUALIFIED); self.assertEqual(calls, [])
    def test_repeat_evaluation_no_operation(self):
        one, _ = self.evaluate(); two, _ = self.evaluate()
        self.assertEqual(one.bundle, two.bundle); self.assertEqual(one.qualification, two.qualification)
        self.permissions(one); self.permissions(two)
    def test_result_immutable_no_contradictory_construction(self):
        result, _ = self.evaluate()
        with self.assertRaises(FrozenInstanceError): result.state = g.GateState.FAIL_CLOSED
        with self.assertRaises(TypeError): replace(result, reason=g.GateReason.UNAVAILABLE)
        with self.assertRaises(TypeError): g.GateResult()
    def test_no_capabilities_or_io_invoked(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for owner, names in ((s.RejectingCapabilities, ('obtain','complete','reconcile')),
                                 (s.RejectingNormalCapabilities, ('resolve_predecessor','associate_candidate','publish_candidate','complete_original'))):
                for name in names: stack.enter_context(patch.object(owner, name, side_effect=AssertionError('forbidden')))
            for name in ('builtins.open','os.getenv','time.time','socket.socket'):
                stack.enter_context(patch(name, side_effect=AssertionError('forbidden')))
            self.assertIs(self.evaluate()[0].state, g.GateState.CHECKED)
    def test_command_resource_bound_before_verifier(self):
        raw = b'x'*(len(p.PREFIX)+6+18*(4+p.MAX_FIELD)+1)
        self.closed(forged(self.bundle, canonical_command=raw), g.GateReason.MALFORMED)
    def test_bool_integer_rejected(self):
        for value in (forged(self.bundle.context, reservation_revision=True),
                      forged(self.bundle.activation, generation=True)):
            field = 'context' if type(value) is s.CommandContext else 'activation'
            self.closed(forged(self.bundle, **{field:value}), g.GateReason.MALFORMED)
    def test_frozen_helpers_exercised(self):
        with patch.object(p, 'decode_record', wraps=p.decode_record) as command:
            with patch.object(pr.ResolutionResult, '__post_init__', autospec=True, side_effect=pr.ResolutionResult.__post_init__) as predecessor:
                with patch.object(s, 'evaluate_time', wraps=s.evaluate_time) as time:
                    self.evaluate(); self.assertGreater(command.call_count,0); self.assertGreater(predecessor.call_count,0); self.assertGreater(time.call_count,0)
    def hostile(self, foreign):
        calls=[]
        def verify(bundle): calls.append(bundle); raise AssertionError('too early')
        adapter = g.TrustedPrerequisiteVerifier(verify)
        for value in (foreign, forged(self.bundle, requester=foreign),
                      forged(self.bundle, requester=forged(self.bundle.requester, evidence=foreign))):
            result = g.evaluate_prerequisites(value, adapter)
            self.assertIs(result.reason, g.GateReason.MALFORMED)
        result = g.evaluate_prerequisites(self.bundle, foreign)
        self.assertIs(result.reason, g.GateReason.UNAVAILABLE); self.assertEqual(calls, [])
    def test_foreign_dataclass(self):
        callbacks=[]
        @dataclass(frozen=True)
        class Foreign:
            def __getattribute__(inner,name): callbacks.append(name); raise AssertionError('foreign')
            def __post_init__(inner): callbacks.append('post_init'); raise AssertionError('foreign')
        self.hostile(object.__new__(Foreign)); self.assertEqual(callbacks, [])
    def test_hostile_metaclass(self):
        callbacks=[]
        class Meta(type):
            def __getattribute__(inner,name): callbacks.append(name); raise AssertionError('foreign')
            def __eq__(inner,other): callbacks.append('eq'); raise AssertionError('foreign')
            def __hash__(inner): callbacks.append('hash'); raise AssertionError('foreign')
        class Foreign(metaclass=Meta): pass
        self.hostile(object.__new__(Foreign)); self.assertEqual(callbacks, [])
    def test_foreign_enum(self):
        callbacks=[]
        class Foreign(StrEnum):
            ITEM='foreign'
            def __getattribute__(inner,name): callbacks.append(name); return object.__getattribute__(inner,name)
        value=Foreign.ITEM; callbacks.clear(); self.hostile(value); self.assertEqual(callbacks, [])
    def test_accepted_type_subclass(self):
        callbacks=[]
        class Foreign(s.AuthenticatedRequester):
            def __getattribute__(inner,name): callbacks.append(name); raise AssertionError('foreign')
        self.hostile(object.__new__(Foreign)); self.assertEqual(callbacks, [])
    def test_adapter_subclass(self):
        callbacks=[]
        class Foreign(g.TrustedPrerequisiteVerifier):
            def __getattribute__(inner,name): callbacks.append(name); raise AssertionError('foreign')
        self.hostile(object.__new__(Foreign)); self.assertEqual(callbacks, [])
    def test_callable_descriptor(self):
        callbacks=[]
        class Foreign:
            @property
            def __name__(inner): callbacks.append('name'); raise AssertionError('foreign')
            def __call__(inner,*args): callbacks.append('call'); raise AssertionError('foreign')
        self.hostile(Foreign()); self.assertEqual(callbacks, [])
    def test_architecture(self):
        tree=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_permit_gate.py').read_bytes())
        allowed={'dataclasses','enum','hashlib','types'}
        relative={'fixture_lease_service','fixture_lease_protocol','fixture_lease_contract','fixture_lease_predecessor_resolution'}
        forbidden={'isinstance','is_dataclass','hasattr','open','connect','execute','getenv','now','time','obtain',
            'transaction','publish_candidate','complete_original','associate_candidate','resolve_predecessor'}
        for node in ast.walk(tree):
            self.assertNotIsInstance(node, ast.Import)
            if isinstance(node, ast.ImportFrom):
                self.assertTrue(node.level==0 and node.module in allowed or node.level==1 and all(n.name in relative for n in node.names))
            if isinstance(node, ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr','')
                self.assertNotIn(name,forbidden)


# Independent substitutions preserve the rest of the coherent fixture and prove
# failure before qualification rather than relying on a provider's rejection.
CASES = {
 'command_id':lambda t:replace(t.bundle,context=replace(t.bundle.context,command_id='other')),
 'canonical_payload':lambda t:replace(t.bundle,canonical_command=p.command_bytes(replace(t.bundle.command,command_id='other'))),
 'principal':lambda t:replace(t.bundle,requester=replace(t.bundle.requester,principal='other')),
 'authorization_reference':lambda t:replace(t.bundle,authorization=replace(t.bundle.authorization,reference=s.EvidenceReference('other',b'a'*32))),
 'authorization_unknown':lambda t:replace(t.bundle,authorization=replace(t.bundle.authorization,validity=s.EvidenceValidity.UNKNOWN)),
 'authorization_context':lambda t:replace(t.bundle,authorization=replace(t.bundle.authorization,context=replace(t.bundle.context,command_id='other'))),
 'activation':lambda t:replace(t.bundle,activation=replace(t.bundle.activation,activation_id='other')),
 'register':lambda t:replace(t.bundle,activation=replace(t.bundle.activation,register_id='other')),
 'generation':lambda t:replace(t.bundle,activation=replace(t.bundle.activation,generation=2)),
 'host':lambda t:replace(t.bundle,approved_host='other'),
 'approval_unknown':lambda t:replace(t.bundle,approval=replace(t.bundle.approval,applicability=s.ApprovalApplicability.UNKNOWN)),
 'approval_revoked':lambda t:replace(t.bundle,approval=replace(t.bundle.approval,validity=s.EvidenceValidity.INVALID)),
 'approval_missing':lambda t:replace(t.bundle,approval=replace(t.bundle.approval,verified=None)),
 'approval_identity':lambda t:replace(t.bundle,approval=replace(t.bundle.approval,reference=replace(t.bundle.approval.reference,identity='other'))),
 'approval_context':lambda t:replace(t.bundle,approval=replace(t.bundle.approval,verified=replace(t.bundle.approval.verified,context=replace(t.bundle.context,command_id='other')))),
 'approval_artifact':lambda t:replace(t.bundle,approval=replace(t.bundle.approval,verified=replace(t.bundle.approval.verified,artifact=c.ArtifactBytes(c.ArtifactType.PROVISIONING_REQUEST,b'other')))),
 'time_restart':lambda t:replace(t.bundle,time=replace(t.bundle.time,point=replace(t.bundle.time.point,process_id='other'))),
 'time_domain':lambda t:replace(t.bundle,time=replace(t.bundle.time,point=replace(t.bundle.time.point,domain_id='other'))),
 'time_profile':lambda t:replace(t.bundle,time=replace(t.bundle.time,profile=replace(t.bundle.time.profile,profile=s.EvidenceReference('other',b'a'*32)))),
 'time_source':lambda t:replace(t.bundle,time=replace(t.bundle.time,profile=replace(t.bundle.time.profile,source='other'))),
 'time_coverage':lambda t:replace(t.bundle,time=replace(t.bundle.time,propagation=replace(t.bundle.time.propagation,elapsed_ns=1))),
 'freshness_unknown':lambda t:replace(t.bundle,time=replace(t.bundle.time,freshness_applicability=s.TimingApplicability.UNKNOWN)),
 'freshness_missing':lambda t:replace(t.bundle,time=replace(t.bundle.time,freshness_deadline=None)),
 'lease_unknown':lambda t:replace(t.bundle,time=replace(t.bundle.time,lease_applicability=s.TimingApplicability.UNKNOWN)),
 'history_replay':lambda t:replace(t.bundle,history=replace(t.bundle.history,command=g.CommandHistory.EXACT_REPLAY)),
 'history_unknown':lambda t:replace(t.bundle,history=replace(t.bundle.history,command=g.CommandHistory.UNKNOWN)),
 'history_mismatch':lambda t:replace(t.bundle,history=replace(t.bundle.history,command=g.CommandHistory.MISMATCH)),
 'history_acquisition':lambda t:replace(t.bundle,history=replace(t.bundle.history,acquisition=g.GapKnowledge.UNRESOLVED)),
 'history_publication':lambda t:replace(t.bundle,history=replace(t.bundle.history,publication=g.GapKnowledge.UNRESOLVED)),
 'history_completion':lambda t:replace(t.bundle,history=replace(t.bundle.history,completion=g.GapKnowledge.UNRESOLVED)),
 'history_unknown_gap':lambda t:replace(t.bundle,history=replace(t.bundle.history,acquisition=g.GapKnowledge.UNKNOWN)),
 'history_context':lambda t:replace(t.bundle,history=replace(t.bundle.history,context=replace(t.bundle.context,command_id='other'))),
 'stale_activation':lambda t:replace(t.bundle,history=replace(t.bundle.history,activation_status=pr.CurrentStatus.SUPERSEDED)),
 'stale_host':lambda t:replace(t.bundle,history=replace(t.bundle.history,host_status=pr.HostStatus.UNAPPROVED)),
 'fenced':lambda t:replace(t.bundle,history=replace(t.bundle.history,fencing_status=pr.FencingStatus.FENCED)),
 'recovery_only':lambda t:replace(t.bundle,history=replace(t.bundle.history,fencing_status=pr.FencingStatus.RECOVERY_ONLY)),
}
for name, change in CASES.items():
    def test(self, change=change): self.closed(change(self))
    setattr(GateTests,'test_substitution_'+name,test)
for magic in ('__getattribute__','__getattr__','__iter__','__eq__','__hash__','__repr__','__str__'):
    def test(self, magic=magic):
        calls=[]
        def callback(*args): calls.append(magic); raise AssertionError('foreign callback')
        cls=type('Foreign',(),{magic:callback}); self.hostile(object.__new__(cls)); self.assertEqual(calls,[])
    setattr(GateTests,'test_zero_callback_'+magic,test)


if __name__=='__main__': unittest.main(verbosity=2)
