"""Offline synthetic IL.5C knowledge classification; no external effects."""
import ast
import copy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import importlib.util
from itertools import product
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
fixtures = runpy.run_path(str(ROOT / 'tests/test_fixture_lease_checkpoints.py'))
s = fixtures['s']
spec = importlib.util.spec_from_file_location('_il4a_pure.fixture_lease_outcomes',
    ROOT / 'services/api/infrastructure/fixture_lease_outcomes.py')
o = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = o
spec.loader.exec_module(o)


class OutcomesTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures['CheckpointsTests'](); fixture.setUp()
        self.candidate = fixture.candidate()
        self.evidence = s.EvidenceReference('synthetic-result', b'e'*32)
        self.publication = self.pub(s.ExternalOutcome.CONFIRMED)
        self.operation = s.OriginalOperation(self.candidate.operation.permit, s.OperationKind.PERMIT_COMPLETION)

    def pub(self, outcome, candidate=None):
        return s.PublicationResult(outcome, self.candidate if candidate is None else candidate,
            None if outcome is s.ExternalOutcome.UNKNOWN else self.evidence)

    def completion(self, outcome):
        return s.CompletionResult(outcome, self.operation, self.publication,
            None if outcome is s.ExternalOutcome.UNKNOWN else self.evidence)

    def publication_gate(self, result=None, **kwargs):
        return o.publication_disposition(self.candidate, result,
            local_commit=o.LocalCommitState.CONFIRMED, qualification=s.EvidenceValidity.VALID, **kwargs)

    def completion_gate(self, result=None, **kwargs):
        return o.completion_disposition(self.candidate, self.publication, result,
            local_commit=o.LocalCommitState.CONFIRMED, publication_qualification=s.EvidenceValidity.VALID,
            completion_qualification=s.EvidenceValidity.VALID, **kwargs)

    def assert_closed(self, disposition):
        self.assertEqual(disposition.required_gate, o.RequiredGate.RECOVERY_HANDOFF)
        self.assertIsNotNone(disposition.recovery)
        self.assertEqual(disposition.recovery.candidate, self.candidate)
        self.assertEqual(disposition.recovery.operation, disposition.operation)
        self.assert_no_permission(disposition)

    def assert_no_permission(self, disposition):
        for name in ('ack_delivery_authorized','runtime_active_authorized',
            'automatic_publication_retry_authorized','automatic_completion_retry_authorized','fence_clearance_authorized'):
            self.assertIs(getattr(disposition,name),False)

    def substituted(self, candidate):
        disposition=self.publication_gate(self.pub(s.ExternalOutcome.CONFIRMED,candidate))
        self.assert_closed(disposition)
        self.assertIsNone(disposition.outcome)
        self.assertEqual(disposition.reason,o.Reason.BINDING_MISMATCH)

    def test_publication_confirmed_completion_gate_only(self):
        d=self.publication_gate(self.publication)
        self.assertEqual(d.outcome,s.ExternalOutcome.CONFIRMED)
        self.assertEqual(d.required_gate,o.RequiredGate.ORIGINAL_COMPLETION)
        self.assertIsNone(d.recovery);self.assert_no_permission(d)

    def test_publication_definitely_rejected(self):
        d=self.publication_gate(self.pub(s.ExternalOutcome.DEFINITELY_REJECTED))
        self.assert_closed(d);self.assertEqual(d.outcome,s.ExternalOutcome.DEFINITELY_REJECTED)

    def test_publication_unknown(self):
        d=self.publication_gate(self.pub(s.ExternalOutcome.UNKNOWN))
        self.assert_closed(d);self.assertEqual(d.outcome,s.ExternalOutcome.UNKNOWN)
        self.assertEqual(d.operation,self.candidate.operation)

    def test_publication_missing(self):
        d=self.publication_gate();self.assert_closed(d)
        self.assertIsNone(d.outcome);self.assertEqual(d.reason,o.Reason.MISSING)

    def test_publication_unqualified(self):
        for qualification in (s.EvidenceValidity.UNKNOWN,s.EvidenceValidity.INVALID,None,True):
            d=o.publication_disposition(self.candidate,self.publication,
                local_commit=o.LocalCommitState.CONFIRMED,qualification=qualification)
            self.assert_closed(d);self.assertIsNone(d.outcome)
            self.assertEqual(d.reason,o.Reason.UNQUALIFIED)

    def test_publication_malformed_type(self):
        for result in (True,'CONFIRMED',{},object(),s.CapabilityUnavailable('unsafe')):
            d=self.publication_gate(result);self.assert_closed(d)
            self.assertEqual(d.reason,o.Reason.MALFORMED);self.assertIsNone(d.publication)

    def test_publication_malformed_typed_outcome(self):
        forged=copy.copy(self.publication);object.__setattr__(forged,'outcome','CONFIRMED')
        d=self.publication_gate(forged);self.assert_closed(d)
        self.assertEqual(d.reason,o.Reason.MALFORMED);self.assertIsNone(d.outcome)

    def test_publication_missing_confirmed_evidence(self):
        forged=copy.copy(self.publication);object.__setattr__(forged,'evidence',None)
        self.assert_closed(self.publication_gate(forged))

    def test_publication_candidate_bytes_mismatch(self):
        self.substituted(replace(self.candidate,exact_bytes=b'other',sha256=sha256(b'other').digest()))

    def test_publication_digest_mismatch(self):
        forged=copy.copy(self.candidate);object.__setattr__(forged,'sha256',b'x'*32)
        self.substituted(forged)

    def test_publication_predecessor_mismatch(self):
        env=self.candidate.envelope
        prior=replace(env.predecessor,revision=env.predecessor.revision+1)
        self.substituted(replace(self.candidate,revision=self.candidate.revision+1,envelope=replace(env,predecessor=prior)))

    def test_publication_permit_mismatch(self):
        ref=s.EvidenceReference('other-permit',b'x'*32)
        self.substituted(replace(self.candidate,envelope=replace(self.candidate.envelope,permit_reference=ref),
            operation=s.OriginalOperation(ref,s.OperationKind.CHECKPOINT_PUBLICATION)))

    def test_publication_host_mismatch(self):
        env=self.candidate.envelope;activation=replace(env.activation,host_identity='other')
        self.substituted(replace(self.candidate,envelope=replace(env,activation=activation,
            predecessor=replace(env.predecessor,activation=activation))))

    def test_publication_activation_mismatch(self):
        env=self.candidate.envelope;activation=replace(env.activation,activation_id='other')
        self.substituted(replace(self.candidate,envelope=replace(env,activation=activation,
            predecessor=replace(env.predecessor,activation=activation))))

    def test_publication_representation_authority_mismatch(self):
        env=self.candidate.envelope
        self.substituted(replace(self.candidate,envelope=replace(env,predecessor=replace(env.predecessor,
            representation_authority=s.EvidenceReference('other-authority',b'x'*32)))))

    def test_publication_representation_mismatch(self):
        env=copy.copy(self.candidate.envelope);prior=copy.copy(env.predecessor)
        object.__setattr__(prior,'representation','unsupported');object.__setattr__(env,'predecessor',prior)
        forged=copy.copy(self.candidate);object.__setattr__(forged,'envelope',env)
        self.substituted(forged)

    def test_publication_principal_mismatch(self):
        self.substituted(replace(self.candidate,envelope=replace(self.candidate.envelope,principal='other')))

    def test_publication_operation_kind_mismatch(self):
        forged=copy.copy(self.candidate);object.__setattr__(forged,'operation',self.operation)
        self.substituted(forged)

    def test_publication_local_commit_unknown_blocks_progression(self):
        d=o.publication_disposition(self.candidate,self.publication,qualification=s.EvidenceValidity.VALID)
        self.assert_closed(d);self.assertEqual(d.reason,o.Reason.LOCAL_COMMIT_NOT_CONFIRMED)

    def test_completion_confirmed_delivery_qualification_only(self):
        d=self.completion_gate(self.completion(s.ExternalOutcome.CONFIRMED))
        self.assertEqual(d.required_gate,o.RequiredGate.CURRENT_DELIVERY_QUALIFICATION)
        self.assertIsNone(d.recovery);self.assert_no_permission(d)

    def test_completion_without_confirmed_publication(self):
        for pub in (None,self.pub(s.ExternalOutcome.UNKNOWN),self.pub(s.ExternalOutcome.DEFINITELY_REJECTED)):
            d=o.completion_disposition(self.candidate,pub,self.completion(s.ExternalOutcome.CONFIRMED),
                local_commit=o.LocalCommitState.CONFIRMED,publication_qualification=s.EvidenceValidity.VALID,
                completion_qualification=s.EvidenceValidity.VALID)
            self.assert_closed(d);self.assertIsNone(d.outcome)

    def test_completion_without_qualified_publication(self):
        d=o.completion_disposition(self.candidate,self.publication,self.completion(s.ExternalOutcome.CONFIRMED),
            local_commit=o.LocalCommitState.CONFIRMED,completion_qualification=s.EvidenceValidity.VALID)
        self.assert_closed(d);self.assertEqual(d.reason,o.Reason.PUBLICATION_NOT_CONFIRMED)

    def test_completion_definitely_rejected(self):
        d=self.completion_gate(self.completion(s.ExternalOutcome.DEFINITELY_REJECTED))
        self.assert_closed(d);self.assertEqual(d.outcome,s.ExternalOutcome.DEFINITELY_REJECTED)

    def test_completion_unknown(self):
        d=self.completion_gate(self.completion(s.ExternalOutcome.UNKNOWN))
        self.assert_closed(d);self.assertEqual(d.outcome,s.ExternalOutcome.UNKNOWN)

    def test_completion_missing(self):
        d=self.completion_gate();self.assert_closed(d);self.assertEqual(d.reason,o.Reason.MISSING)

    def test_completion_unqualified(self):
        d=o.completion_disposition(self.candidate,self.publication,self.completion(s.ExternalOutcome.CONFIRMED),
            local_commit=o.LocalCommitState.CONFIRMED,publication_qualification=s.EvidenceValidity.VALID)
        self.assert_closed(d);self.assertIsNone(d.outcome)

    def test_completion_operation_substitution(self):
        forged=copy.copy(self.completion(s.ExternalOutcome.CONFIRMED))
        object.__setattr__(forged,'operation',s.OriginalOperation(s.EvidenceReference('other',b'x'*32),s.OperationKind.PERMIT_COMPLETION))
        self.assert_closed(self.completion_gate(forged))

    def test_completion_different_publication(self):
        other=replace(self.publication,evidence=s.EvidenceReference('other-confirmation',b'x'*32))
        result=replace(self.completion(s.ExternalOutcome.CONFIRMED),publication=other)
        d=self.completion_gate(result);self.assert_closed(d)
        self.assertEqual(d.reason,o.Reason.BINDING_MISMATCH)
        self.assertIs(d.completion,result)

    def test_completion_malformed(self):
        for result in (True,{},'CONFIRMED'):
            self.assert_closed(self.completion_gate(result))

    def test_completion_local_commit_unknown(self):
        d=o.completion_disposition(self.candidate,self.publication,self.completion(s.ExternalOutcome.CONFIRMED),
            publication_qualification=s.EvidenceValidity.VALID,completion_qualification=s.EvidenceValidity.VALID)
        self.assert_closed(d);self.assertEqual(d.reason,o.Reason.LOCAL_COMMIT_NOT_CONFIRMED)

    def test_later_resolution_preserves_original_operation_and_fence(self):
        initial=self.publication_gate(self.pub(s.ExternalOutcome.UNKNOWN))
        refined=self.publication_gate(self.publication,prior=initial)
        self.assertEqual(refined.outcome,s.ExternalOutcome.CONFIRMED)
        self.assertEqual(refined.operation,initial.operation)
        self.assert_closed(refined);self.assertEqual(refined.reason,o.Reason.PRIOR_FENCE)
        self.assertIs(refined.prior_recovery,initial.recovery)

    def test_completion_later_resolution_does_not_clear_fence(self):
        initial=self.completion_gate(self.completion(s.ExternalOutcome.UNKNOWN))
        refined=self.completion_gate(self.completion(s.ExternalOutcome.CONFIRMED),prior=initial)
        self.assertEqual(refined.outcome,s.ExternalOutcome.CONFIRMED)
        self.assert_closed(refined);self.assertEqual(refined.operation,initial.operation)

    def test_prior_operation_substitution_rejects(self):
        prior=self.publication_gate(self.publication)
        changed=replace(self.candidate,envelope=replace(self.candidate.envelope,principal='other'))
        with self.assertRaises(s.TimeRejected):
            o.publication_disposition(changed,self.pub(s.ExternalOutcome.UNKNOWN,changed),prior=prior)

    def test_default_unknown_results_remain_unknown(self):
        supplied=s.PublicationResult(s.ExternalOutcome.UNKNOWN,self.candidate,None)
        d=o.publication_disposition(self.candidate,supplied,local_commit=o.LocalCommitState.CONFIRMED)
        self.assert_closed(d);self.assertEqual(d.outcome,s.ExternalOutcome.UNKNOWN)
        d=o.completion_disposition(self.candidate,self.publication,self.completion(s.ExternalOutcome.UNKNOWN),
            local_commit=o.LocalCommitState.CONFIRMED,publication_qualification=s.EvidenceValidity.VALID)
        self.assert_closed(d);self.assertEqual(d.outcome,s.ExternalOutcome.UNKNOWN)

    def test_dispositions_and_handoffs_immutable(self):
        d=self.publication_gate(self.pub(s.ExternalOutcome.UNKNOWN))
        for value,field,new in ((d,'reason',o.Reason.NEXT_GATE),(d.recovery,'reason',o.Reason.NEXT_GATE)):
            with self.assertRaises(FrozenInstanceError):setattr(value,field,new)
        with self.assertRaises(s.TimeRejected):replace(d,reason='arbitrary unsafe text')

    def test_no_result_grants_operational_permission(self):
        for outcome in s.ExternalOutcome:
            self.assert_no_permission(self.publication_gate(self.pub(outcome)))
            self.assert_no_permission(self.completion_gate(self.completion(outcome)))

    def test_frozen_binding_helpers_exercised(self):
        with (patch.object(s,'verify_publication_result',wraps=s.verify_publication_result) as pub,
              patch.object(s,'verify_completion_result',wraps=s.verify_completion_result) as complete):
            self.publication_gate(self.publication)
            self.completion_gate(self.completion(s.ExternalOutcome.CONFIRMED))
            self.assertGreater(pub.call_count,0);self.assertGreater(complete.call_count,0)

    def test_no_capability_invocation(self):
        with (patch.object(s.RejectingNormalCapabilities,'publish_candidate',side_effect=AssertionError('effect')),
             patch.object(s.RejectingNormalCapabilities,'complete_original',side_effect=AssertionError('effect')),
             patch.object(s.RejectingNormalCapabilities,'query_publication',side_effect=AssertionError('effect')),
             patch.object(s.RejectingNormalCapabilities,'query_completion',side_effect=AssertionError('effect'))):
            self.publication_gate(self.publication)
            self.completion_gate(self.completion(s.ExternalOutcome.CONFIRMED))

    def test_architecture_and_purity(self):
        tree=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_outcomes.py').read_text())
        expected={(0,'dataclasses',(('dataclass',None),)),(0,'enum',(('StrEnum',None),)),
                  (1,None,(('fixture_lease_service','service'),))}
        seen=[]
        forbidden={'open','connect','execute','getenv','now','time','sleep','run','publish_candidate',
                   'complete_original','query_completion','query_publication','obtain'}
        for node in ast.walk(tree):
            self.assertNotIsInstance(node,ast.Import)
            if isinstance(node,ast.ImportFrom):seen.append((node.level,node.module,tuple((a.name,a.asname) for a in node.names)))
            if isinstance(node,ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr','')
                self.assertNotIn(name,forbidden)
        self.assertEqual(set(seen),expected);self.assertEqual(len(seen),len(expected))

    def test_invalid_original_identity_not_fabricated(self):
        with self.assertRaises(s.TimeRejected):o.publication_disposition(None)
        bad=copy.copy(self.candidate);object.__setattr__(bad,'sha256',b'x'*32)
        with self.assertRaises(s.TimeRejected):o.publication_disposition(bad)

    def test_unqualified_rejection_never_fabricates_nonoccurrence(self):
        d=o.publication_disposition(self.candidate,self.pub(s.ExternalOutcome.DEFINITELY_REJECTED),
            local_commit=o.LocalCommitState.CONFIRMED)
        self.assert_closed(d);self.assertIsNone(d.outcome)
        d=o.completion_disposition(self.candidate,self.publication,self.completion(s.ExternalOutcome.DEFINITELY_REJECTED),
            local_commit=o.LocalCommitState.CONFIRMED,publication_qualification=s.EvidenceValidity.VALID)
        self.assert_closed(d);self.assertIsNone(d.outcome)

    def test_not_committed_and_strict_local_state(self):
        d=o.publication_disposition(self.candidate,self.publication,
            local_commit=o.LocalCommitState.NOT_COMMITTED,qualification=s.EvidenceValidity.VALID)
        self.assert_closed(d)
        for state in (True,'CONFIRMED',None):
            with self.assertRaises(s.TimeRejected):o.publication_disposition(self.candidate,self.publication,local_commit=state)

    def test_recovery_evidence_preserved_exactly(self):
        result=self.pub(s.ExternalOutcome.UNKNOWN);d=self.publication_gate(result)
        self.assertIs(d.publication,result);self.assertIs(d.recovery.publication,result)
        self.assertIs(d.recovery.candidate,self.candidate)
        self.assertEqual(d.recovery.operation,self.candidate.operation)
        self.assertEqual(d.recovery.candidate.envelope,self.candidate.envelope)

    def test_bounded_reasons_and_no_arbitrary_diagnostics(self):
        d=self.publication_gate(s.CapabilityUnavailable('secret\n'+('x'*10000)))
        self.assertEqual(d.reason,o.Reason.MALFORMED)
        self.assertIsNone(d.publication)
        self.assertTrue(all(len(reason.value)<=32 and '\n' not in reason.value for reason in o.Reason))
        self.assertFalse(hasattr(d,'diagnostic'))

    def test_completion_retains_publication_fence(self):
        prior=self.publication_gate(self.pub(s.ExternalOutcome.UNKNOWN))
        d=self.completion_gate(self.completion(s.ExternalOutcome.CONFIRMED),prior=prior)
        self.assert_closed(d);self.assertEqual(d.reason,o.Reason.PRIOR_FENCE)
        self.assertIs(d.prior_recovery,prior.recovery)

    def test_illegal_disposition_constructor_combination(self):
        d=self.publication_gate(self.publication)
        with self.assertRaises(s.TimeRejected):replace(d,publication=None)
        with self.assertRaises(s.TimeRejected):replace(d,required_gate=o.RequiredGate.CURRENT_DELIVERY_QUALIFICATION)

    def test_incidental_representations_do_not_dump_evidence(self):
        d=self.publication_gate(self.pub(s.ExternalOutcome.UNKNOWN))
        for value in (d,d.recovery):
            text=repr(value)
            self.assertLess(len(text),128)
            self.assertNotIn('synthetic-result',text)
            self.assertNotIn('exact_bytes',text)
            self.assertNotIn('canonical_command_bytes',text)

    def test_direct_publication_outcome_contradictions(self):
        for actual,changed in ((s.ExternalOutcome.UNKNOWN,s.ExternalOutcome.CONFIRMED),
            (s.ExternalOutcome.UNKNOWN,s.ExternalOutcome.DEFINITELY_REJECTED),
            (s.ExternalOutcome.DEFINITELY_REJECTED,s.ExternalOutcome.CONFIRMED),
            (s.ExternalOutcome.CONFIRMED,s.ExternalOutcome.DEFINITELY_REJECTED),
            (s.ExternalOutcome.CONFIRMED,s.ExternalOutcome.UNKNOWN)):
            d=self.publication_gate(self.pub(actual))
            with self.assertRaises(s.TimeRejected):replace(d,outcome=changed)

    def test_history_rejects_malformed_observations(self):
        d=self.publication_gate(self.pub(s.ExternalOutcome.UNKNOWN))
        malformed=copy.copy(d.publication);object.__setattr__(malformed,'outcome','CONFIRMED')
        with self.assertRaises(s.TimeRejected):replace(d.recovery,publication=malformed)
        for field in ('ack_delivery_authorized','runtime_active_authorized',
                      'automatic_publication_retry_authorized','automatic_completion_retry_authorized',
                      'fence_clearance_authorized'):
            with self.assertRaises(TypeError):replace(d,**{field:True})

    def test_direct_completion_outcome_contradictions(self):
        for actual,changed in product(s.ExternalOutcome,s.ExternalOutcome):
            if actual==changed:continue
            d=self.completion_gate(self.completion(actual))
            with self.assertRaises(s.TimeRejected):replace(d,outcome=changed)

    def test_definitive_recovery_requires_retained_qualification(self):
        for stage in o.Stage:
            for outcome in (s.ExternalOutcome.CONFIRMED,s.ExternalOutcome.DEFINITELY_REJECTED):
                # Keep a legitimate earlier fence to exercise the recovery branch.
                prior=self.publication_gate(self.pub(s.ExternalOutcome.UNKNOWN))
                d=(self.publication_gate(self.pub(outcome),prior=prior) if stage==o.Stage.PUBLICATION
                   else self.completion_gate(self.completion(outcome),prior=prior))
                field='publication_qualification' if stage==o.Stage.PUBLICATION else 'completion_qualification'
                for qualification in (s.EvidenceValidity.UNKNOWN,s.EvidenceValidity.INVALID):
                    with self.assertRaises(s.TimeRejected):replace(d,**{field:qualification})
                if stage==o.Stage.COMPLETION:
                    with self.assertRaises(s.TimeRejected):replace(d,publication_qualification=s.EvidenceValidity.UNKNOWN)

    def foreign_candidate(self, dimension):
        # Preserve canonical byte/digest consistency while changing one lineage
        # identity. These remain synthetic qualified-input claims, not permission.
        q=fixtures['q'];p=fixtures['p'];env=self.candidate.envelope
        wire=q.decode_checkpoint(self.candidate.exact_bytes);reference=wire.reference
        activation=env.activation;predecessor=env.predecessor
        if dimension in ('host','activation','generation'):
            changes={'host':{'host_identity':'other'},'activation':{'activation_id':'other'},
                     'generation':{'generation':2}}[dimension]
            activation=replace(activation,**changes);predecessor=replace(predecessor,activation=activation)
            if dimension=='host':reference=replace(reference,host=activation.host_identity)
            if dimension=='activation':wire=replace(wire,activation_id=activation.activation_id)
            if dimension=='generation':wire=replace(wire,generation=activation.generation)
        if dimension=='representation':
            authority=s.EvidenceReference('foreign-authority',b'x'*32)
            predecessor=replace(predecessor,representation_authority=authority)
            reference=replace(reference,representation_authority_id=authority.identity,
                              representation_authority_sha256=authority.sha256)
        if dimension=='principal':
            command=replace(p.decode_record(env.canonical_command_bytes,p.CommandPayload),authenticated_principal='other')
            raw=p.command_bytes(command)
            env=replace(env,principal='other',canonical_command_bytes=raw,
                        context=replace(env.context,payload_sha256=sha256(raw).digest()))
            reference=replace(reference,command_sha256=sha256(raw).digest())
        if dimension=='permit':
            permit=s.EvidenceReference('foreign-permit',b'x'*32)
            env=replace(env,permit_reference=permit)
            reference=replace(reference,permit_id=permit.identity,permit_sha256=permit.sha256)
        env=replace(env,activation=activation,predecessor=predecessor)
        raw=q.checkpoint_bytes(replace(wire,reference=reference))
        return replace(self.candidate,exact_bytes=raw,sha256=sha256(raw).digest(),envelope=env,
                       operation=s.OriginalOperation(env.permit_reference,s.OperationKind.CHECKPOINT_PUBLICATION))

    def test_foreign_embedded_history_constructor_and_entry_points(self):
        current=self.publication_gate(self.pub(s.ExternalOutcome.UNKNOWN))
        for dimension in ('host','activation','generation','representation','principal','permit'):
            foreign=self.foreign_candidate(dimension)
            handoff=o.publication_disposition(foreign,s.PublicationResult(s.ExternalOutcome.UNKNOWN,foreign,None),
                local_commit=o.LocalCommitState.CONFIRMED).recovery
            with self.subTest(dimension=dimension):
                with self.assertRaises(s.TimeRejected):replace(current,prior_recovery=handoff)
                forged=copy.copy(current);object.__setattr__(forged,'prior_recovery',handoff)
                with self.assertRaises(s.TimeRejected):self.publication_gate(self.publication,prior=forged)
                with self.assertRaises(s.TimeRejected):self.completion_gate(self.completion(s.ExternalOutcome.CONFIRMED),prior=forged)

    def test_foreign_operation_embedded_history_rejected(self):
        current=self.publication_gate(self.pub(s.ExternalOutcome.UNKNOWN))
        for kind in s.OperationKind:
            foreign=s.OriginalOperation(s.EvidenceReference('foreign-permit',b'x'*32),kind)
            with self.assertRaises(s.TimeRejected):replace(current.recovery,operation=foreign)
            forged=copy.copy(current.recovery);object.__setattr__(forged,'operation',foreign)
            with self.assertRaises(s.TimeRejected):replace(current,prior_recovery=forged)
            prior=copy.copy(current);object.__setattr__(prior,'prior_recovery',forged)
            with self.assertRaises(s.TimeRejected):self.publication_gate(self.publication,prior=prior)

    def test_legitimate_cross_stage_history_and_gate_obligations(self):
        prior=self.publication_gate(self.pub(s.ExternalOutcome.UNKNOWN))
        refined=self.publication_gate(self.publication,prior=prior)
        self.assertIs(refined.prior_recovery,prior.recovery)
        self.assertEqual(refined.outcome,s.ExternalOutcome.CONFIRMED)
        self.assertEqual(refined.required_gate,o.RequiredGate.RECOVERY_HANDOFF)
        # The exact publication is confirmed; original completion remains the
        # outstanding external gate, subject to preserved recovery authority.
        self.assertIsNone(refined.completion);self.assert_no_permission(refined)
        self.assertTrue(refined.completion_required)
        completion=self.completion_gate(self.completion(s.ExternalOutcome.CONFIRMED),prior=refined)
        self.assertEqual(completion.outcome,s.ExternalOutcome.CONFIRMED)
        self.assertIsNotNone(completion.prior_recovery);self.assert_closed(completion)
        self.assertTrue(completion.delivery_qualification_required)
        self.assertFalse(completion.completion_required)

    def test_same_operation_completion_refinement_preserves_delivery_obligation(self):
        prior=self.completion_gate(self.completion(s.ExternalOutcome.UNKNOWN))
        refined=self.completion_gate(self.completion(s.ExternalOutcome.CONFIRMED),prior=prior)
        self.assertEqual(refined.operation,prior.operation)
        self.assertIs(refined.prior_recovery,prior.recovery)
        self.assertTrue(refined.delivery_qualification_required)
        self.assert_closed(refined)

    def test_supported_invariant_matrix(self):
        states=(None,*s.ExternalOutcome);count=0
        prior=self.publication_gate(self.pub(s.ExternalOutcome.UNKNOWN))
        for stage in o.Stage:
            completion_states=(None,) if stage==o.Stage.PUBLICATION else states
            for pub_state,completion_state,pq,cq,local,history in product(states,completion_states,
                s.EvidenceValidity,s.EvidenceValidity,o.LocalCommitState,(None,prior)):
                if stage==o.Stage.PUBLICATION and cq is not s.EvidenceValidity.UNKNOWN:continue
                pub=None if pub_state is None else self.pub(pub_state)
                completion=None if completion_state is None else self.completion(completion_state)
                if stage==o.Stage.PUBLICATION:
                    d=o.publication_disposition(self.candidate,pub,local_commit=local,qualification=pq,prior=history)
                else:
                    d=o.completion_disposition(self.candidate,pub,completion,local_commit=local,
                        publication_qualification=pq,completion_qualification=cq,prior=history)
                # Independent authority oracle: publication prerequisite, exact
                # result state and supplied qualification determine knowledge.
                pub_known=pub_state if pub_state is s.ExternalOutcome.UNKNOWN or pq is s.EvidenceValidity.VALID else None
                if stage==o.Stage.PUBLICATION:expected=pub_known
                elif pub_known is not s.ExternalOutcome.CONFIRMED:expected=None
                else:expected=completion_state if completion_state is s.ExternalOutcome.UNKNOWN or cq is s.EvidenceValidity.VALID else None
                self.assertIs(d.outcome,expected);self.assert_no_permission(d)
                clean=(expected is s.ExternalOutcome.CONFIRMED and local is o.LocalCommitState.CONFIRMED and history is None)
                gate=(o.RequiredGate.ORIGINAL_COMPLETION if stage==o.Stage.PUBLICATION
                      else o.RequiredGate.CURRENT_DELIVERY_QUALIFICATION) if clean else o.RequiredGate.RECOVERY_HANDOFF
                self.assertIs(d.required_gate,gate)
                self.assertEqual(d.completion_required,local is o.LocalCommitState.CONFIRMED
                    and pub_known is s.ExternalOutcome.CONFIRMED
                    and not (stage==o.Stage.COMPLETION and expected is s.ExternalOutcome.CONFIRMED))
                self.assertEqual(d.delivery_qualification_required,local is o.LocalCommitState.CONFIRMED
                    and stage==o.Stage.COMPLETION and expected is s.ExternalOutcome.CONFIRMED)
                self.assertEqual(d.recovery is not None,not clean)
                for proposed in states:
                    if proposed is expected:self.assertEqual(replace(d,outcome=proposed),d)
                    else:
                        with self.assertRaises(s.TimeRejected):replace(d,outcome=proposed)
                for proposed in o.RequiredGate:
                    if proposed is gate:self.assertEqual(replace(d,required_gate=proposed),d)
                    else:
                        with self.assertRaises(s.TimeRejected):replace(d,required_gate=proposed)
                if d.recovery is not None:
                    with self.assertRaises(s.TimeRejected):replace(d,recovery=None)
                count+=1
        self.assertEqual(count,936)


if __name__ == '__main__':unittest.main(verbosity=2)
