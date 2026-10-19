"""Increment D synthetic/offline contract tests. No operational provider exists."""
import ast
import copy
from dataclasses import replace
import importlib.util
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
fixtures = runpy.run_path(str(ROOT / 'tests/test_fixture_lease_candidate_preparation.py'))
c, s, cp = fixtures['c'], fixtures['s'], fixtures['cp']
name = c.__package__ + '.fixture_lease_candidate_retention'
spec = importlib.util.spec_from_file_location(name,
    ROOT / 'services/api/infrastructure/fixture_lease_candidate_retention.py')
d = importlib.util.module_from_spec(spec)
sys.modules[name] = d
spec.loader.exec_module(d)


def genuine_source():
    completion, snapshot = fixtures['build_material']()
    authority = s.EvidenceReference('C-independent-authority', b'a'*32)
    implementation = s.EvidenceReference('C-independent-implementation', b'i'*32)
    reference = s.EvidenceReference('C-observed-execution-and-complete-snapshot', b'c'*32)
    def verify(request):
        return c.PreparationQualification(request, authority, implementation,
                                           s.EvidenceValidity.VALID, reference)
    result = c.CandidatePreparer(c.TrustedPreparationVerifier(authority, implementation, verify)).prepare_candidate(
        completion, snapshot)
    if result.state is not c.PreparationState.PREPARED:
        raise AssertionError('synthetic C fixture did not prepare')
    return result


class RetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = genuine_source()

    def setUp(self):
        self.source = d._copy(self.template)
        self.authority = d._copy(d._namespace(self.source))
        self.implementation = s.EvidenceReference('D-qualified-implementation', b'i'*32)
        self.proof = s.EvidenceReference('D-independent-eligibility', b'e'*32)
        self.retention_proof = s.EvidenceReference('protected-exact-original-association', b'r'*32)
        self.history = d.AssociationHistory.ELIGIBLE_FIRST_ASSOCIATION
        self.progression = d.ProgressionStatus.CLEAR
        self.pre_reason = None
        self.pre_validity = s.EvidenceValidity.VALID
        self.post_validity = s.EvidenceValidity.VALID
        self.disposition = d.AssociationDisposition.RETAINED
        self.calls = []
        self.verify_hook = self.associate_hook = self.qualify_hook = None
        self.pre_transform = self.post_transform = None
        self.effect_error = None
        self.return_transform = None
        self.adapter = d.TrustedCandidateRetentionAdapter(self.authority, self.implementation,
                                                          self.verify, self.associate, self.qualify)
        self.retainer = d.CandidateRetainer(self.adapter)

    def evidence(self, source):
        candidate = d._copy(source.prepared.candidate)
        return d.g.CandidateRetentionEvidence(candidate, candidate.operation,
                                              s.EvidenceValidity.VALID, self.retention_proof)

    def verify(self, source):
        self.calls.append('verify')
        if self.verify_hook:
            self.verify_hook(source)
        reasons = {d.AssociationHistory.EXACT_EXISTING: d.RetentionReason.RETAINED_EXACT_EXISTING,
            d.AssociationHistory.CONFLICT: d.RetentionReason.ASSOCIATION_CONFLICT,
            d.AssociationHistory.UNKNOWN_HISTORY: d.RetentionReason.UNKNOWN_HISTORY,
            d.AssociationHistory.PROVEN_PRE_DISPATCH_FAILURE: d.RetentionReason.PROVEN_PRE_DISPATCH_FAILURE,
            d.AssociationHistory.ELIGIBLE_FIRST_ASSOCIATION: {
                d.ProgressionStatus.CLEAR: d.RetentionReason.ELIGIBLE_FIRST_ASSOCIATION,
                d.ProgressionStatus.PROHIBITED: d.RetentionReason.PROGRESSION_PROHIBITED,
                d.ProgressionStatus.UNKNOWN: d.RetentionReason.PROGRESSION_UNKNOWN}[self.progression]}
        response = d.EligibilityQualification(source, self.authority, self.implementation,
            self.pre_validity, self.proof, self.history, self.progression,
            self.pre_reason or reasons[self.history],
            self.evidence(source) if self.history is d.AssociationHistory.EXACT_EXISTING else None)
        return response if self.pre_transform is None else self.pre_transform(response)

    def associate(self, candidate):
        self.calls.append('associate')
        self.assertEqual(candidate, self.source.prepared.candidate)
        self.assertIsNot(candidate, self.source.prepared.candidate)
        if self.associate_hook:
            self.associate_hook(candidate)
        if self.effect_error is not None:
            raise self.effect_error
        return candidate if self.return_transform is None else self.return_transform(candidate)

    def qualify(self, source, eligibility, observation):
        self.calls.append('qualify')
        if self.qualify_hook:
            self.qualify_hook(source, eligibility, observation)
        reasons = {d.AssociationDisposition.RETAINED: d.RetentionReason.RETAINED_FIRST_ASSOCIATION,
            d.AssociationDisposition.CONFLICT: d.RetentionReason.CONFIRMATION_CONFLICT,
            d.AssociationDisposition.PROVEN_NON_DISPATCH: d.RetentionReason.PROVEN_NON_DISPATCH,
            d.AssociationDisposition.UNKNOWN: d.RetentionReason.POST_EFFECT_UNKNOWN}
        response = d.AssociationQualification(observation, self.authority, self.implementation,
            self.post_validity, self.proof, self.disposition, reasons[self.disposition],
            self.evidence(source) if self.disposition is d.AssociationDisposition.RETAINED else None)
        return response if self.post_transform is None else self.post_transform(response)

    def run_d(self):
        return self.retainer.retain_candidate(self.source)

    def check(self, result, state, invoked):
        self.assertIs(result.state, state)
        self.assertEqual(self.calls.count('associate'), invoked)
        self.assertLessEqual(self.calls.count('verify'), 1)
        self.assertLessEqual(self.calls.count('qualify'), 1)
        self.assertEqual(sum(v is not None for v in (result.retained, result.rejected, result.unresolved)), 1)
        payload = result.retained or result.rejected or result.unresolved
        self.assertIs(payload.association_invoked, bool(invoked))
        for permission in d._PERMISSIONS:
            self.assertIs(getattr(result, permission), False)
        return payload

    def test_first_success_exact_graph_and_order(self):
        result = self.run_d()
        payload = self.check(result, d.RetentionState.RETAINED, 1)
        self.assertEqual(self.calls, ['verify', 'associate', 'qualify'])
        self.assertIs(result.reason, d.RetentionReason.RETAINED_FIRST_ASSOCIATION)
        self.assertEqual(payload.source, self.source)
        self.assertEqual(payload.retention.candidate, self.source.prepared.candidate)
        self.assertFalse(payload.reconciliation_required)
        self.assertEqual(payload.source.prepared.request.completion.local,
                         self.source.prepared.request.completion.local)

    def test_result_closed_and_truthiness_rejected(self):
        result = self.run_d()
        for fn in (lambda: d.RetentionResult(), lambda: replace(result),
                   lambda: copy.copy(result), lambda: copy.deepcopy(result), lambda: bool(result)):
            with self.assertRaises(TypeError): fn()

    def test_constructor_requires_exact_well_formed_composition(self):
        class Sub(d.TrustedCandidateRetentionAdapter): pass
        for value in (None, self.verify, Hostile(), Sub(self.authority, self.implementation,
                self.verify, self.associate, self.qualify), replace(self.adapter, authority=None),
                replace(self.adapter, implementation=object.__new__(s.EvidenceReference)),
                replace(self.adapter, associate=None), object.__new__(d.TrustedCandidateRetentionAdapter)):
            with self.assertRaises(TypeError): d.CandidateRetainer(value)

    def test_no_dependency_override_at_evaluation(self):
        for key in ('adapter', 'provider', 'callback', 'candidate', 'operation'):
            with self.assertRaises(TypeError): self.retainer.retain_candidate(self.source, **{key: self.adapter})
        self.assertEqual(self.calls, [])

    def test_forged_matching_source_needs_independent_negative_assessment(self):
        self.source = d._copy(self.source)  # Exact values do not prove issuance.
        self.history = d.AssociationHistory.PROVEN_PRE_DISPATCH_FAILURE
        self.pre_reason = d.RetentionReason.UNQUALIFIED_C_PROVENANCE
        result = self.run_d()
        self.check(result, d.RetentionState.REJECTED, 0)
        self.assertEqual(self.calls, ['verify'])
        self.assertIs(result.reason, self.pre_reason)

    def test_authentic_negative_t1_assessment(self):
        self.history = d.AssociationHistory.PROVEN_PRE_DISPATCH_FAILURE
        self.pre_reason = d.RetentionReason.HISTORICAL_T1_INVALID
        result = self.run_d()
        self.check(result, d.RetentionState.REJECTED, 0)
        self.assertIs(result.reason, self.pre_reason)

    def test_invalid_source_is_local_not_qualified_predispatch_failure(self):
        self.source = self.source.prepared.candidate
        result = self.run_d()
        self.check(result, d.RetentionState.REJECTED, 0)
        self.assertIs(result.reason, d.RetentionReason.INVALID_C_SOURCE)
        self.assertEqual(self.calls, [])

    def test_historical_t1_corruption_rejected_locally(self):
        point = self.source.prepared.request.completion.t1.point
        object.__setattr__(point, 'ticks_ns', point.ticks_ns + 1)
        result = self.run_d()
        self.check(result, d.RetentionState.REJECTED, 0)
        self.assertEqual(self.calls, [])

    def test_later_expiry_has_no_new_measurement_or_publication_gate(self):
        b = self.source.prepared.request.completion
        self.assertGreater(b.t2.evaluation.interval.lower_us, b.completed.permit.valid_until_us)
        with (patch.object(c.commands, '_writer_time', side_effect=AssertionError('clock')),
              patch.object(c.q, 'qualify_admission_inputs', side_effect=AssertionError('fresh consumption')),
              patch.object(cp, 'construct_candidate', side_effect=AssertionError('second candidate')),
              patch.object(cp, 'validate_candidate', side_effect=AssertionError('reconstruction'))):
            result = self.run_d()
        self.check(result, d.RetentionState.RETAINED, 1)
        self.assertEqual(result.retained.retention.candidate.fixed_utc_us, b.completed.envelope.fixed_utc_us)

    def test_ordinary_checkpoint_gap_is_not_automatic_progression_fence(self):
        self.assertIs(self.run_d().state, d.RetentionState.RETAINED)

    def test_equal_return_without_independent_retention_is_unknown(self):
        self.post_validity = s.EvidenceValidity.UNKNOWN
        self.check(self.run_d(), d.RetentionState.UNRESOLVED, 1)

    def test_proven_post_entry_non_dispatch(self):
        self.effect_error = s.CapabilityUnavailable('not proof itself')
        self.disposition = d.AssociationDisposition.PROVEN_NON_DISPATCH
        result = self.run_d()
        self.check(result, d.RetentionState.REJECTED, 1)
        self.assertIs(result.reason, d.RetentionReason.PROVEN_NON_DISPATCH)

    def test_provider_unavailable_with_independently_proven_non_entry(self):
        self.history = d.AssociationHistory.PROVEN_PRE_DISPATCH_FAILURE
        self.pre_reason = d.RetentionReason.PROVEN_PRE_DISPATCH_UNAVAILABLE
        self.check(self.run_d(), d.RetentionState.REJECTED, 0)

    def test_qualified_resolution_of_lost_response_may_prove_exact_retention(self):
        self.effect_error = TimeoutError('lost')
        self.check(self.run_d(), d.RetentionState.RETAINED, 1)

    def test_stale_absence_concurrent_exact_association_requires_confirmation(self):
        external = {}
        def race(candidate): external['candidate'] = d._copy(candidate)
        self.associate_hook = race
        result = self.run_d()
        self.check(result, d.RetentionState.RETAINED, 1)
        self.assertEqual(external['candidate'], result.retained.retention.candidate)
        self.assertEqual(self.calls, ['verify', 'associate', 'qualify'])

    def test_stale_absence_concurrent_conflict_never_overwrites(self):
        protected = {'candidate': 'other immutable association'}
        self.associate_hook = lambda candidate: self.assertEqual(protected['candidate'], 'other immutable association')
        self.disposition = d.AssociationDisposition.CONFLICT
        self.check(self.run_d(), d.RetentionState.UNRESOLVED, 1)
        self.assertEqual(protected['candidate'], 'other immutable association')

    def test_stale_eligibility_alone_does_not_prove_final_state(self):
        self.disposition = d.AssociationDisposition.UNKNOWN
        self.check(self.run_d(), d.RetentionState.UNRESOLVED, 1)

    def test_cross_evaluation_unknown_history_prevents_blind_resubmission(self):
        self.disposition = d.AssociationDisposition.UNKNOWN
        first = self.run_d()
        self.check(first, d.RetentionState.UNRESOLVED, 1)
        self.calls.clear()
        self.history = d.AssociationHistory.UNKNOWN_HISTORY
        second = d.CandidateRetainer(self.adapter).retain_candidate(self.source)
        self.check(second, d.RetentionState.UNRESOLVED, 0)

    def test_cross_evaluation_needs_independent_current_history(self):
        self.disposition = d.AssociationDisposition.UNKNOWN
        self.run_d()
        self.calls.clear()
        # Synthetic protected resolution now positively warrants non-dispatch
        # and eligibility; absence of the first process's memory is not its proof.
        self.disposition = d.AssociationDisposition.RETAINED
        self.check(d.CandidateRetainer(self.adapter).retain_candidate(self.source), d.RetentionState.RETAINED, 1)

    def test_lost_process_local_exception_handoff_does_not_prove_non_dispatch(self):
        self.effect_error = RuntimeError('programming defect')
        try:
            self.run_d()
        except d._RetentionEvaluationInterrupted as signal:
            self.assertIs(type(signal.__cause__), RuntimeError)
        else:
            self.fail('missing exceptional handoff')
        # Do not supply the prior signal to the new evaluator: lost in-memory
        # knowledge is simulated without any process crash or journal.
        self.calls.clear(); self.effect_error = None
        self.history = d.AssociationHistory.UNKNOWN_HISTORY
        result = d.CandidateRetainer(self.adapter).retain_candidate(self.source)
        self.check(result, d.RetentionState.UNRESOLVED, 0)

    def test_post_return_aliases_cannot_mutate_issued_knowledge(self):
        result = self.run_d()
        expected = d._copy(result)
        object.__setattr__(self.source.prepared.candidate, 'event_sequence', 999)
        object.__setattr__(self.proof, 'identity', 'mutated-after-return')
        object.__setattr__(self.retention_proof, 'identity', 'mutated-after-return')
        self.assertEqual(result, expected)

    def test_shared_alias_accepted_and_detached(self):
        copied = d._copy((self.authority, self.authority))
        self.assertIs(copied[0], copied[1]); self.assertIsNot(copied[0], self.authority)
        self.check(self.run_d(), d.RetentionState.RETAINED, 1)

    def test_cycle_rejected_without_effect(self):
        object.__setattr__(self.source.prepared.request.snapshot, 'keys', (self.source,))
        self.check(self.run_d(), d.RetentionState.REJECTED, 0)
        self.assertEqual(self.calls, [])

    def test_response_source_stability_eligibility(self):
        project = d._project
        seen = []
        def capture(value):
            result = project(value)
            if type(value) is d.EligibilityQualification:
                seen.append(value)
                if len(seen) == 1: object.__setattr__(value.reference, 'identity', 'during-capture')
            return result
        with patch.object(d, '_project', capture): result = self.run_d()
        self.check(result, d.RetentionState.UNRESOLVED, 0)
        self.assertIs(result.reason, d.RetentionReason.INSTABILITY)

    def test_response_source_stability_confirmation(self):
        project = d._project
        seen = []
        def capture(value):
            result = project(value)
            if type(value) is d.AssociationQualification:
                seen.append(value)
                if len(seen) == 1: object.__setattr__(value.reference, 'identity', 'during-capture')
            return result
        with patch.object(d, '_project', capture): result = self.run_d()
        self.check(result, d.RetentionState.UNRESOLVED, 1)
        self.assertIs(result.reason, d.RetentionReason.INSTABILITY)

    def test_no_effect_expansion_and_one_syntactic_association_call(self):
        with (patch.object(c.store.sqlite3, 'connect', side_effect=AssertionError('SQLite')),
              patch.object(cp, 'construct_candidate', side_effect=AssertionError('candidate')),
              patch.object(cp, 'validate_candidate', side_effect=AssertionError('reconstruct')),
              patch.object(c.protocol, 'state_bytes', side_effect=AssertionError('whole STATE'))):
            self.check(self.run_d(), d.RetentionState.RETAINED, 1)
        tree = ast.parse((ROOT / 'services/api/infrastructure/fixture_lease_candidate_retention.py').read_text())
        called = [v.func.attr if type(v.func) is ast.Attribute else v.func.id
                  for v in ast.walk(tree) if type(v) is ast.Call
                  and type(v.func) in (ast.Attribute, ast.Name)]
        self.assertEqual(called.count('_associate'), 1)
        self.assertFalse(set(called) & {'construct_candidate', 'validate_candidate', 'CandidatePreparer',
            'publish_candidate', 'query_publication', 'publication_disposition', 'complete_original',
            'connect', 'execute', 'open', 'sleep', 'monotonic_ns', 'now', 'deliver', 'recover', 'state_bytes'})

    def test_non_prepared_rejection_and_upstream_unknown_preserved(self):
        for state, reason, expected in (
                (c.PreparationState.REJECTED,c.PreparationReason.NOT_NEW_TRANSITION,d.RetentionState.REJECTED),
                (c.PreparationState.UNRESOLVED,c.PreparationReason.UPSTREAM_UNRESOLVED,d.RetentionState.UNRESOLVED)):
            self.source = c._result(state,reason)
            result = self.run_d()
            self.check(result,expected,0)
            self.assertFalse(result.verification_attempted)
            self.assertEqual(self.calls,[])

    def test_final_before_entry_source_stability_guard(self):
        copied = d._copy
        def changed(value):
            result = copied(value)
            if type(value) is s.CheckpointCandidate:
                object.__setattr__(self.source.prepared.candidate,'event_sequence',999)
            return result
        with patch.object(d,'_copy',changed): result = self.run_d()
        self.check(result,d.RetentionState.UNRESOLVED,0)
        self.assertIs(result.reason,d.RetentionReason.INSTABILITY)

    def test_effect_candidate_alias_cannot_change_during_qualification(self):
        captured = []
        self.associate_hook = lambda candidate: captured.append(candidate)
        self.qualify_hook = lambda *args: object.__setattr__(captured[0],'event_sequence',999)
        result = self.run_d()
        self.check(result,d.RetentionState.UNRESOLVED,1)
        self.assertIs(result.reason,d.RetentionReason.INSTABILITY)

    def test_later_contradiction_preserves_confirmed_storage(self):
        self.post_validity = s.EvidenceValidity.INVALID
        payload = self.check(self.run_d(),d.RetentionState.UNRESOLVED,1)
        self.assertIs(payload.source.prepared.request.completion.local.storage_result,
                      c.store.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        self.assertTrue(payload.reconciliation_required)

    def test_defect_after_qualified_confirmation_preserves_available_proof(self):
        issue = d._issue
        original = RuntimeError('result finalization defect')
        def failure(state,*args,**kwargs):
            if state is d.RetentionState.RETAINED: raise original
            return issue(state,*args,**kwargs)
        with patch.object(d,'_issue',failure):
            with self.assertRaises(d._RetentionEvaluationInterrupted) as raised: self.run_d()
        self.assertIs(raised.exception.__cause__,original)
        payload = self.check(raised.exception.result,d.RetentionState.UNRESOLVED,1)
        self.assertIs(payload.disposition.disposition,d.AssociationDisposition.RETAINED)
        self.assertEqual(payload.disposition.retention.candidate,self.source.prepared.candidate)

    def test_exact_existing_requires_independent_retention_evidence(self):
        self.history = d.AssociationHistory.EXACT_EXISTING
        self.pre_transform = lambda value: replace(value,retention=None)
        self.check(self.run_d(),d.RetentionState.UNRESOLVED,0)

    def test_approved_large_complete_history_has_no_D_graph_or_state_cap(self):
        p = c.protocol
        material = d._copy(self.template.prepared.request)
        source_row = material.snapshot.projection.commands[0]
        command = p.decode_record(source_row.canonical_payload_bytes,p.CommandPayload)
        ack = p.decode_record(source_row.durable_ack_bytes,p.AckPayload)
        old_bound = p.MAX_FIELD // (len(p.PREFIX)+6+12+2+32)
        history = []
        for index in range(old_bound+1):
            identity = 'zz-D-history-'+str(index).zfill(6)
            raw = p.command_bytes(replace(command,command_id=identity))
            digest = d.sha256(raw).digest()
            ack_bytes = p.ack_bytes(replace(ack,command_id=identity,command_payload_sha256=digest))
            history.append(replace(source_row,command_id=identity,canonical_payload_bytes=raw,
                canonical_payload_hash=digest,durable_ack_bytes=ack_bytes))
        projection = replace(material.snapshot.projection,
            commands=material.snapshot.projection.commands+tuple(history))
        digest = p.state_digest(projection,material.snapshot.context)
        completion = replace(material.completion,completed=replace(material.completion.completed,state_digest=digest))
        snapshot = replace(material.snapshot,projection=projection)
        # The trusted synthetic C verifier authenticates this complete synthetic
        # fixture; rehashed data by itself would not establish provenance.
        def verify(request):
            proof = self.template.prepared.provenance
            return c.PreparationQualification(request,proof.authority,proof.implementation,
                                               s.EvidenceValidity.VALID,proof.reference)
        proof = self.template.prepared.provenance
        self.source = c.CandidatePreparer(c.TrustedPreparationVerifier(proof.authority,
            proof.implementation,verify)).prepare_candidate(completion,snapshot)
        self.assertIs(self.source.state,c.PreparationState.PREPARED)
        self.assertGreater(len(projection.commands),old_bound)
        self.assertGreater(sum(map(len,p.state_chunks(projection,snapshot.context))),p.MAX_BLOB)
        with patch.object(p,'state_bytes',side_effect=AssertionError('aggregate STATE')):
            self.check(self.run_d(),d.RetentionState.RETAINED,1)


def history_case(history, progression):
    def test(self):
        self.history, self.progression = history, progression
        result = self.run_d()
        if history is d.AssociationHistory.EXACT_EXISTING:
            payload = self.check(result, d.RetentionState.RETAINED, 0)
            self.assertIs(payload.reconciliation_required, progression is not d.ProgressionStatus.CLEAR)
        elif history is d.AssociationHistory.ELIGIBLE_FIRST_ASSOCIATION:
            state = {d.ProgressionStatus.CLEAR:d.RetentionState.RETAINED,
                d.ProgressionStatus.PROHIBITED:d.RetentionState.REJECTED,
                d.ProgressionStatus.UNKNOWN:d.RetentionState.UNRESOLVED}[progression]
            self.check(result, state, int(progression is d.ProgressionStatus.CLEAR))
        else:
            state = d.RetentionState.UNRESOLVED if history is d.AssociationHistory.UNKNOWN_HISTORY else d.RetentionState.REJECTED
            self.check(result, state, 0)
        for permission in d._PERMISSIONS: self.assertIs(getattr(result, permission), False)
    return test


for _history in d.AssociationHistory:
    for _progression in d.ProgressionStatus:
        setattr(RetentionTests, 'test_history_'+_history.name+'_'+_progression.name,
                history_case(_history, _progression))


def pre_case(name, transform):
    def test(self):
        self.pre_transform = transform
        result = self.run_d()
        self.check(result, d.RetentionState.UNRESOLVED, 0)
        self.assertEqual(self.calls, ['verify'])
    setattr(RetentionTests, 'test_pre_'+name, test)


for _name, _transform in (
    ('foreign', lambda v:Hostile()), ('none', lambda v:None),
    ('authority', lambda v:replace(v, authority=s.EvidenceReference('wrong',b'x'*32))),
    ('implementation', lambda v:replace(v, implementation=s.EvidenceReference('wrong',b'x'*32))),
    ('reference', lambda v:replace(v, reference=object.__new__(s.EvidenceReference))),
    ('source_binding', lambda v:replace(v, source=replace_source_candidate(v.source))),
    ('invalid', lambda v:replace(v, validity=s.EvidenceValidity.INVALID)),
    ('unknown', lambda v:replace(v, validity=s.EvidenceValidity.UNKNOWN)),
    ('invalid_reason_history', lambda v:replace(v, history=d.AssociationHistory.PROVEN_PRE_DISPATCH_FAILURE,
                                              reason=d.RetentionReason.INVALID_C_SOURCE)),
    ('prohibition_not_predispatch', lambda v:replace(v, history=d.AssociationHistory.PROVEN_PRE_DISPATCH_FAILURE,
                                                   reason=d.RetentionReason.PROGRESSION_PROHIBITED)),
    ('contradictory_clear', lambda v:replace(v, reason=d.RetentionReason.PROGRESSION_UNKNOWN)),
    ('contradictory_prohibited', lambda v:replace(v, progression=d.ProgressionStatus.PROHIBITED)),
    ('contradictory_unknown', lambda v:replace(v, progression=d.ProgressionStatus.UNKNOWN)),
    ('label', lambda v:replace(v, history='ELIGIBLE_FIRST_ASSOCIATION')),
): pre_case(_name, _transform)


def replace_source_candidate(source):
    value = d._copy(source)
    object.__setattr__(value.prepared.candidate, 'event_sequence', 999)
    return value


def post_case(name, transform):
    def test(self):
        self.post_transform = transform
        result = self.run_d()
        self.check(result, d.RetentionState.UNRESOLVED, 1)
        self.assertEqual(self.calls, ['verify', 'associate', 'qualify'])
    setattr(RetentionTests, 'test_post_'+name, test)


for _name, _transform in (
    ('foreign', lambda v:Hostile()), ('none', lambda v:None),
    ('authority', lambda v:replace(v, authority=s.EvidenceReference('wrong',b'x'*32))),
    ('implementation', lambda v:replace(v, implementation=s.EvidenceReference('wrong',b'x'*32))),
    ('reference', lambda v:replace(v, reference=None)),
    ('observation', lambda v:replace(v, observation=replace(v.observation, kind=d.ObservationKind.TIMEOUT,
                                                          returned_candidate=None))),
    ('missing_retention', lambda v:replace(v, retention=None)),
    ('unknown_validity', lambda v:replace(v, validity=s.EvidenceValidity.UNKNOWN)),
    ('invalid_validity', lambda v:replace(v, validity=s.EvidenceValidity.INVALID)),
    ('unqualified_retention', lambda v:replace(v, retention=replace(v.retention, qualification=s.EvidenceValidity.UNKNOWN))),
    ('wrong_operation', lambda v:replace(v, retention=corrupt_evidence(v.retention,'operation'))),
    ('wrong_bytes', lambda v:replace(v, retention=corrupt_evidence(v.retention,'exact_bytes'))),
    ('wrong_digest', lambda v:replace(v, retention=corrupt_evidence(v.retention,'sha256'))),
    ('wrong_envelope', lambda v:replace(v, retention=corrupt_evidence(v.retention,'envelope'))),
    ('wrong_permit', lambda v:replace(v, retention=corrupt_evidence(v.retention,'permit'))),
    ('wrong_predecessor', lambda v:replace(v, retention=corrupt_evidence(v.retention,'predecessor'))),
    ('wrong_transition', lambda v:replace(v, retention=corrupt_evidence(v.retention,'state_digest'))),
): post_case(_name, _transform)


def corrupt_evidence(evidence, field):
    value = d._copy(evidence)
    candidate = value.candidate
    if field=='operation': object.__setattr__(value, 'operation', s.OriginalOperation(candidate.operation.permit,s.OperationKind.PERMIT_COMPLETION))
    elif field=='envelope': object.__setattr__(candidate.envelope, 'principal', 'foreign')
    elif field=='permit': object.__setattr__(candidate.operation.permit, 'identity', 'foreign')
    elif field=='predecessor': object.__setattr__(candidate.envelope.predecessor, 'revision', 99)
    else: object.__setattr__(candidate, field, b'foreign' if field=='exact_bytes' else b'x'*32)
    return value


def exception_case(stage, error, classified):
    def test(self):
        original = error('synthetic failure')
        def fail(*args): raise original
        if stage=='verify': self.verify_hook=fail
        elif stage=='associate': self.effect_error=original
        else: self.qualify_hook=fail
        if classified:
            self.disposition = d.AssociationDisposition.UNKNOWN
            result = self.run_d()
            self.check(result,d.RetentionState.UNRESOLVED,int(stage!='verify'))
        elif stage=='verify':
            with self.assertRaises(error) as raised: self.run_d()
            self.assertIs(raised.exception, original)
            self.assertEqual(self.calls,['verify'])
        else:
            with self.assertRaises(d._RetentionEvaluationInterrupted) as raised: self.run_d()
            self.assertIs(raised.exception.__cause__,original)
            payload=self.check(raised.exception.result,d.RetentionState.UNRESOLVED,1)
            self.assertTrue(payload.reconciliation_required)
            self.assertIs(payload.source.prepared.request.completion.local.storage_result,
                          c.store.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
    setattr(RetentionTests,'test_exception_'+stage+'_'+error.__name__,test)


for _stage in ('verify','associate','qualify'):
    for _error in (s.CapabilityUnavailable,c.a.ExternalAvailabilityFailure,TimeoutError,
                   RuntimeError,AssertionError,ValueError,TypeError,AttributeError,
                   KeyboardInterrupt,SystemExit,MemoryError):
        exception_case(_stage,_error,_error in (s.CapabilityUnavailable,c.a.ExternalAvailabilityFailure,TimeoutError))


def mutation_case(stage, target):
    def test(self):
        def mutate(*args):
            if target=='source': object.__setattr__(self.source.prepared.candidate,'event_sequence',999)
            elif target=='composition': object.__setattr__(self.adapter,'associate',lambda candidate:self.fail('replacement'))
            else:
                value=args[0] if stage=='verify' else args[2] if stage=='qualify' else args[0]
                if stage=='verify': object.__setattr__(value.prepared.candidate,'event_sequence',999)
                elif stage=='qualify': object.__setattr__(value,'kind',d.ObservationKind.TIMEOUT)
                else: object.__setattr__(value,'event_sequence',999)
        if stage=='verify':self.verify_hook=mutate
        elif stage=='associate':self.associate_hook=mutate
        else:self.qualify_hook=mutate
        result=self.run_d()
        self.check(result,d.RetentionState.UNRESOLVED,int(stage!='verify'))
        self.assertIs(result.reason,d.RetentionReason.INSTABILITY)
    setattr(RetentionTests,'test_mutation_'+stage+'_'+target,test)


for _stage in ('verify','associate','qualify'):
    for _target in ('source','composition','request'):mutation_case(_stage,_target)


class Hostile:
    def __getattribute__(self,name):raise AssertionError('foreign traversal')
    def __eq__(self,other):raise AssertionError('foreign equality')
    def __hash__(self):raise AssertionError('foreign hashing')
    def __repr__(self):raise AssertionError('foreign repr')


def source_case(name, change):
    def test(self):
        self.source=change(self.source)
        result=self.run_d()
        self.check(result,d.RetentionState.REJECTED,0)
        self.assertEqual(self.calls,[])
    setattr(RetentionTests,'test_source_'+name,test)


def mutate_source(source,field,value):
    object.__setattr__(source,field,value)
    return source


class ForeignSource(c.PreparationResult):
    def __getattribute__(self,name):raise AssertionError('subclass traversal')


for _name,_change in (
    ('foreign',lambda v:Hostile()),('subclass',lambda v:object.__new__(ForeignSource)),
    ('bare_payload',lambda v:v.prepared),('bare_request',lambda v:v.prepared.request),
    ('bare_qualification',lambda v:v.prepared.provenance),('bytes',lambda v:v.prepared.candidate.exact_bytes),
    ('wrong_reason',lambda v:mutate_source(v,'reason',c.PreparationReason.MALFORMED)),
    ('not_attempted',lambda v:mutate_source(v,'qualification_attempted',False)),
    ('wrong_diagnostic',lambda v:mutate_source(v,'diagnostic',c.PreparationReason.MALFORMED)),
    ('missing_prepared',lambda v:mutate_source(v,'prepared',None)),
    ('foreign_prepared',lambda v:mutate_source(v,'prepared',Hostile())),
):source_case(_name,_change)


def return_case(name, change):
    def test(self):
        self.return_transform=change
        result=self.run_d()
        payload=self.check(result,d.RetentionState.UNRESOLVED,1)
        self.assertEqual(self.calls,['verify','associate'])
        self.assertIs(payload.observation.kind,d.ObservationKind.MALFORMED_RETURN)
        self.assertIsNone(payload.observation.returned_candidate)
    setattr(RetentionTests,'test_return_'+name,test)


for _name,_change in (
    ('foreign',lambda v:Hostile()),('none',lambda v:None),('list',lambda v:[v]),
    ('different_candidate',lambda v:replace(v,event_digest=b'x'*32)),
):return_case(_name,_change)


def nested_source_case(name, mutate):
    def test(self):
        mutate(self.source)
        self.check(self.run_d(),d.RetentionState.REJECTED,0)
        self.assertEqual(self.calls,[])
    setattr(RetentionTests,'test_nested_source_'+name,test)


class Ticks(int):
    def __sub__(self,other):raise AssertionError('integer subclass arithmetic')


for _name,_mutate in (
    ('list',lambda v:object.__setattr__(v.prepared.request.snapshot,'events',list(v.prepared.request.snapshot.events))),
    ('iterator',lambda v:object.__setattr__(v.prepared.request.snapshot,'keys',iter(v.prepared.request.snapshot.keys))),
    ('integer_subclass',lambda v:object.__setattr__(v.prepared.request.completion.t1.point,'ticks_ns',Ticks(1))),
    ('foreign_snapshot',lambda v:object.__setattr__(v.prepared.request,'snapshot',Hostile())),
    ('unqualified_C',lambda v:object.__setattr__(v.prepared.provenance,'validity',s.EvidenceValidity.UNKNOWN)),
    ('wrong_C_request',lambda v:object.__setattr__(v.prepared.provenance,'request',None)),
    ('wrong_candidate_bytes',lambda v:object.__setattr__(v.prepared.candidate,'exact_bytes',b'wrong')),
    ('wrong_candidate_digest',lambda v:object.__setattr__(v.prepared.candidate,'sha256',b'x'*32)),
    ('wrong_candidate_revision',lambda v:object.__setattr__(v.prepared.candidate,'revision',99)),
    ('wrong_fixed_time',lambda v:object.__setattr__(v.prepared.candidate,'fixed_utc_us',99)),
    ('wrong_operation_kind',lambda v:object.__setattr__(v.prepared.candidate.operation,'kind',s.OperationKind.PERMIT_COMPLETION)),
):nested_source_case(_name,_mutate)


def verifier_request_stability_case(stage, unavailable):
    def test(self):
        captured = []
        self.verify_hook = captured.append
        def detached_eligibility(response):
            detached = replace(response, source=d._copy(response.source))
            self.assertIsNot(detached.source, captured[0])
            self.assertIsNot(detached.source.prepared.candidate, captured[0].prepared.candidate)
            return detached
        self.pre_transform = detached_eligibility
        def mutate(*args):
            object.__setattr__(captured[0].prepared.candidate, 'event_sequence', 999)
            if unavailable:
                raise s.CapabilityUnavailable('synthetic unavailable after possible entry')
        if stage == 'associate':
            self.associate_hook = mutate
        else:
            self.qualify_hook = mutate
            # Confirmation also remains separate from the verifier request.
            self.post_transform = d._copy
        result = self.run_d()
        payload = self.check(result, d.RetentionState.UNRESOLVED, 1)
        self.assertIs(result.reason, d.RetentionReason.INSTABILITY)
        self.assertTrue(payload.association_invoked)
        self.assertTrue(payload.reconciliation_required)
        self.assertEqual(payload.source.prepared.request.completion.local,
                         self.source.prepared.request.completion.local)
        self.assertEqual(self.calls, ['verify', 'associate'] +
                         (['qualify'] if stage == 'qualify' else []))
    setattr(RetentionTests, 'test_detached_verifier_request_mutation_' + stage +
            ('_unavailable' if unavailable else '_returned'), test)


for _stage in ('associate', 'qualify'):
    for _unavailable in (False, True):
        verifier_request_stability_case(_stage, _unavailable)


if __name__=='__main__':unittest.main()
