"""Increment F: genuine synthetic E/B/C/D path and offline adversarial adapters."""
import ast
import copy
from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import runpy
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
efixture = runpy.run_path(str(ROOT / 'tests/test_fixture_lease_publication_qualification.py'))
e = efixture['e']
service, g, o, d, c, p = e.s, e.g, e.o, e.d, e.c, e.p
name = e.__package__ + '.fixture_lease_publication'
spec = importlib.util.spec_from_file_location(name, ROOT / 'services/api/infrastructure/fixture_lease_publication.py')
f = importlib.util.module_from_spec(spec)
sys.modules[name] = f
spec.loader.exec_module(f)


class Hostile:
    def __getattribute__(self, name): raise AssertionError('foreign attribute access')
    def __eq__(self, other): raise AssertionError('foreign equality')
    def __hash__(self): raise AssertionError('foreign hashing')
    def __repr__(self): raise AssertionError('foreign repr')


def changed(inputs, target, **changes):
    return replace(inputs, **{target: replace(getattr(inputs, target), **changes)})


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        factory = efixture['PublicationTests']
        factory.setUpClass()
        case = factory('test_genuine_path_canonical_gate_and_exact_detachment')
        case.setUp()
        cls.template = case.run_e()
        if cls.template.state is not e.S.QUALIFIED:
            raise AssertionError('genuine synthetic E qualification failed')

    def setUp(self):
        self.source = f._copy(self.template)
        self.authority = f._copy(d._namespace(self.source.qualified.source.retained.source))
        self.implementation = service.EvidenceReference('F-independent-qualification', b'f' * 32)
        self.reference = service.EvidenceReference('F-qualified-dispatch-and-outcome', b'r' * 32)
        self.calls = []
        self.request = self.response = self.observation = self.confirmation = None
        self.effect_candidate = None
        self.transform = self.input_transform = self.verify_hook = self.publish_hook = self.qualify_hook = None
        self.confirm_transform = None
        self.verify_error = self.publish_error = self.qualify_error = None
        self.provenance = self.validity = self.coverage_validity = service.EvidenceValidity.VALID
        self.coverage_present = True
        self.decision = f.DispatchDecision.ELIGIBLE
        self.disposition = f.PublicationDispositionKind.CONFIRMED
        self.return_outcome = service.ExternalOutcome.CONFIRMED
        self.return_override = False
        self.return_value = None
        self.adapter = f.TrustedPublicationAdapter(self.authority, self.implementation,
            self.verify, self.publish, self.qualify)
        self.publisher = f.CheckpointPublisher(self.adapter)

    def inputs(self, source):
        inputs = f._copy(source.qualified.gate.inputs)
        # F is a separately qualified later coverage interval, never reused E authority.
        time = inputs.time
        point = replace(time.point, ticks_ns=time.point.ticks_ns + 1000)
        propagation = replace(time.propagation, elapsed_ns=time.propagation.elapsed_ns + 1000)
        interval = service.evaluate_time(time.sample, time.profile, point, propagation).interval
        inputs = replace(inputs, authority=replace(inputs.authority, point=point, interval=interval),
            time=replace(time, point=point, propagation=propagation, covered_interval=interval))
        return inputs if self.input_transform is None else self.input_transform(inputs)

    def verify(self, request):
        self.calls.append('verify')
        self.request = request
        if self.verify_error is not None: raise self.verify_error
        if self.verify_hook is not None: self.verify_hook(request)
        inputs = self.inputs(request.source) if self.provenance is service.EvidenceValidity.VALID else None
        coverage = None
        if self.decision is f.DispatchDecision.ELIGIBLE and inputs is not None and self.coverage_present:
            coverage = f.PublicationDispatchCoverage(f._copy(request), inputs.candidate, inputs.candidate.operation,
                self.authority, self.implementation, self.coverage_validity, self.reference,
                inputs.authority.point, inputs.authority.interval)
        result = f.PublicationDispatchAssessment(f._copy(request), self.authority, self.implementation,
            self.validity, self.reference, self.provenance, self.decision, inputs, coverage)
        self.response = result if self.transform is None else self.transform(result)
        return self.response

    def publish(self, candidate):
        self.calls.append('publish')
        self.effect_candidate = candidate
        if self.publish_hook is not None: self.publish_hook(candidate)
        if self.publish_error is not None: raise self.publish_error
        if self.return_override: return self.return_value
        return service.PublicationResult(self.return_outcome, candidate,
            None if self.return_outcome is service.ExternalOutcome.UNKNOWN else self.reference)

    def qualify(self, observation):
        self.calls.append('qualify')
        self.observation = observation
        if self.qualify_hook is not None: self.qualify_hook(observation)
        if self.qualify_error is not None: raise self.qualify_error
        publication = None
        if self.disposition is not f.PublicationDispositionKind.PROVEN_NON_DISPATCH:
            outcome = {f.PublicationDispositionKind.CONFIRMED: service.ExternalOutcome.CONFIRMED,
                f.PublicationDispositionKind.DEFINITELY_REJECTED: service.ExternalOutcome.DEFINITELY_REJECTED,
                f.PublicationDispositionKind.UNKNOWN: service.ExternalOutcome.UNKNOWN}[self.disposition]
            publication = service.PublicationResult(outcome, f._copy(observation.dispatch.inputs.candidate),
                None if outcome is service.ExternalOutcome.UNKNOWN else self.reference)
        result = f.PublicationDispositionAssessment(f._copy(observation), self.authority,
            self.implementation, service.EvidenceValidity.VALID, self.reference, self.disposition, publication)
        self.confirmation = result if self.confirm_transform is None else self.confirm_transform(result)
        return self.confirmation

    def run_f(self): return self.publisher.publish_checkpoint(self.source)

    def check(self, result, state, reason, published=0, gate=None):
        self.assertIs(result.state, state)
        self.assertIs(result.reason, reason)
        self.assertEqual(self.calls.count('publish'), published)
        self.assertLessEqual(self.calls.count('verify'), 1)
        self.assertLessEqual(self.calls.count('qualify'), 1)
        self.assertEqual(result.publication_invoked, bool(published))
        if gate is not None: self.assertEqual(result.gate_evaluated, gate)
        payloads = (result.published, result.not_submitted, result.rejected, result.unresolved)
        self.assertEqual(sum(x is not None for x in payloads), 1)
        payload = next(x for x in payloads if x is not None)
        if state in (f.S.UNRESOLVED, f.S.DEFINITELY_REJECTED): self.assertTrue(payload.reconciliation_required)
        for name in f._PERMISSIONS: self.assertIs(getattr(result, name), False)
        return payload

    def test_genuine_publication_exact_subject_and_detachment(self):
        payload = self.check(self.run_f(), f.S.PUBLISHED, f.R.PUBLISHED, 1, True)
        self.assertEqual(self.calls, ['verify', 'publish', 'qualify'])
        self.assertEqual(self.effect_candidate, self.source.qualified.gate.inputs.candidate)
        self.assertIsNot(self.effect_candidate, self.source.qualified.gate.inputs.candidate)
        self.assertIsNot(self.response.request, self.request)
        self.assertIsNot(self.response.request.source, self.request.source)
        self.assertIsNot(payload.source, self.source)
        self.assertIsNot(payload.qualification, self.confirmation)
        self.assertFalse(payload.reconciliation_required)
        self.assertIs(payload.disposition.required_gate, o.RequiredGate.ORIGINAL_COMPLETION)
        self.assertTrue(payload.disposition.completion_required)
        self.assertIs(payload.disposition.local_commit, o.LocalCommitState.CONFIRMED)
        self.assertEqual(payload.source.qualified.gate.inputs.candidate.fixed_utc_us,
                         payload.dispatch.inputs.candidate.fixed_utc_us)
        self.assertGreater(payload.dispatch.inputs.time.point.ticks_ns,
                           payload.source.qualified.gate.inputs.time.point.ticks_ns)

    def test_e_gate_result_uses_canonical_result_owner_validation(self):
        gate = self.source.qualified.gate
        self.assertIs(type(gate), g.GateResult)
        # Semantic source validation succeeds without claiming genuine issuance
        # or performing trusted verification/publication on its own.
        self.assertFalse(f._source(self.source))
        self.assertEqual(self.calls, [])
        # Correcting root ownership must not bypass canonical result validation.
        object.__setattr__(gate, 'reason', g.GateReason.TIME)
        with self.assertRaises(f._INVALID):
            f._source(self.source)
        self.assertEqual(self.calls, [])

    def test_rev2_bootstrap_code_replacement_never_executes(self):
        bootstrap = f.CheckpointPublisher._composition_stable
        calls = []
        # Match the bootstrap's zero-closure shape without adding module globals.
        # The temporary recording global is restored in cleanup.
        namespace = bootstrap.__globals__
        key = '_rev2_bootstrap_calls'
        namespace[key] = calls
        exec('def replacement(self):\n    _rev2_bootstrap_calls.append(1)\n    return False', namespace)
        replacement_code = namespace.pop('replacement').__code__
        original = bootstrap.__code__
        try:
            bootstrap.__code__ = replacement_code
            result = self.run_f()
            self.check(result, f.S.UNRESOLVED, f.R.DEPENDENCY_INSTABILITY, gate=False)
            self.assertEqual(calls, [])
            self.assertEqual(self.calls, [])
            self.assertFalse(result.verification_attempted)
            self.assertFalse(result.qualification_attempted)
            self.assertIsNone(result.unresolved.source)
        finally:
            bootstrap.__code__ = original
            namespace.pop(key, None)

    def test_rev2_entry_failure_is_fresh_after_caller_mutation(self):
        with patch.object(f, '_source', lambda value: None):
            first = self.run_f()
            object.__setattr__(first, 'state', f.S.PUBLISHED)
            object.__setattr__(first.unresolved, 'source', self.source)
            second = self.run_f()
        self.assertIsNot(second, first)
        self.assertIsNot(second.unresolved, first.unresolved)
        payload = self.check(second, f.S.UNRESOLVED, f.R.DEPENDENCY_INSTABILITY, gate=False)
        self.assertIsNone(payload.source)
        self.assertIsNone(payload.dispatch)
        self.assertIsNone(payload.observation)
        self.assertIsNone(payload.qualification)
        self.assertIsNone(payload.disposition)
        self.assertIsNone(second.published)
        self.assertFalse(second.verification_attempted)
        self.assertFalse(second.qualification_attempted)
        self.assertEqual(self.calls, [])

    def test_rev2_interruption_before_return_retains_dispatch(self):
        error = RuntimeError('publication interrupted')
        self.publish_error = error
        with self.assertRaises(f._PublicationEvaluationInterrupted) as caught:
            self.run_f()
        result = caught.exception.result
        payload = self.check(result, f.S.UNRESOLVED, f.R.EVALUATION_INTERRUPTED, 1, True)
        self.assertIs(caught.exception.__cause__, error)
        self.assertIsNotNone(payload.dispatch)
        self.assertIsNot(payload.dispatch, self.response)
        self.assertIsNone(payload.observation)
        self.assertIsNone(payload.qualification)
        self.assertIsNone(payload.disposition)
        self.assertFalse(result.qualification_attempted)
        self.assertEqual(self.calls, ['verify', 'publish'])

    def test_rev2_qualifier_interruption_retains_dispatch_and_observation(self):
        error = RuntimeError('qualifier interrupted')
        self.qualify_error = error
        with self.assertRaises(f._PublicationEvaluationInterrupted) as caught:
            self.run_f()
        result = caught.exception.result
        payload = self.check(result, f.S.UNRESOLVED, f.R.EVALUATION_INTERRUPTED, 1, True)
        self.assertIs(caught.exception.__cause__, error)
        self.assertIsNotNone(payload.dispatch)
        self.assertIsNotNone(payload.observation)
        self.assertIsNot(payload.observation, self.observation)
        self.assertIs(payload.observation.kind, f.PublicationObservationKind.RETURNED)
        self.assertIsNone(payload.qualification)
        self.assertIsNone(payload.disposition)
        self.assertTrue(result.qualification_attempted)
        self.assertEqual(self.calls, ['verify', 'publish', 'qualify'])

    def test_rev2_late_interruption_retains_qualified_disposition(self):
        original = f._issue
        error = RuntimeError('final result interrupted')
        def issue(state, *args, **kwargs):
            if state is f.S.PUBLISHED: raise error
            return original(state, *args, **kwargs)
        with patch.object(f, '_issue', issue):
            self.publisher = f.CheckpointPublisher(self.adapter)
            with self.assertRaises(f._PublicationEvaluationInterrupted) as caught:
                self.run_f()
        result = caught.exception.result
        payload = self.check(result, f.S.UNRESOLVED, f.R.EVALUATION_INTERRUPTED, 1, True)
        self.assertIs(caught.exception.__cause__, error)
        self.assertIsNotNone(payload.dispatch)
        self.assertIsNotNone(payload.observation)
        self.assertIsNotNone(payload.qualification)
        self.assertIsNotNone(payload.disposition)
        self.assertIsNot(payload.qualification, self.confirmation)
        self.assertIs(payload.disposition.outcome, service.ExternalOutcome.CONFIRMED)
        self.assertTrue(result.qualification_attempted)
        self.assertEqual(self.calls, ['verify', 'publish', 'qualify'])

    def test_rev2_failed_enrichment_keeps_preallocated_evidence_floor(self):
        original = f._issue
        error = MemoryError('snapshot allocation failed')
        def issue(state, reason, *args, **kwargs):
            if reason is f.R.EVALUATION_INTERRUPTED and len(args) >= 3:
                raise error
            return original(state, reason, *args, **kwargs)
        with patch.object(f, '_issue', issue):
            self.publisher = f.CheckpointPublisher(self.adapter)
            with self.assertRaises(f._PublicationEvaluationInterrupted) as caught:
                self.run_f()
        payload = self.check(caught.exception.result, f.S.UNRESOLVED,
                             f.R.EVALUATION_INTERRUPTED, 1, True)
        self.assertIs(caught.exception.__cause__, error)
        self.assertIsNotNone(payload.dispatch)
        self.assertIsNone(payload.observation)
        self.assertIsNone(payload.qualification)
        self.assertIsNone(payload.disposition)
        self.assertEqual(self.calls, ['verify', 'publish'])

    def check_rev3_enrichment_replacement(self, canonical):
        target = o.publication_disposition if canonical else self.qualify.__func__
        original_code = target.__code__
        namespace = target.__globals__
        delegate = types.FunctionType(original_code, namespace, argdefs=target.__defaults__)
        delegate.__kwdefaults__ = target.__kwdefaults__
        hits = []
        namespace['_rev3_hits'] = hits
        namespace['_rev3_delegate'] = delegate
        exec('def _rev3_replacement(*args, **kwargs):\n'
             '    _rev3_hits.append(1)\n'
             '    return _rev3_delegate(*args, **kwargs)', namespace)
        replacement_code = namespace.pop('_rev3_replacement').__code__
        original_issue = f._issue
        enrichment_calls = []
        def issue(state, reason, *args, **kwargs):
            result = original_issue(state, reason, *args, **kwargs)
            if (reason is f.R.EVALUATION_INTERRUPTED and len(args) == (4 if canonical else 3)
                    and not enrichment_calls):
                enrichment_calls.append(1)
                target.__code__ = replacement_code
            return result
        try:
            with patch.object(f, '_issue', issue):
                self.publisher = f.CheckpointPublisher(self.adapter)
                result = self.run_f()
            payload = self.check(result, f.S.UNRESOLVED, f.R.DEPENDENCY_INSTABILITY, 1, True)
            self.assertEqual(enrichment_calls, [1])
            self.assertEqual(hits, [])
            self.assertIsNotNone(payload.dispatch)
            self.assertIsNotNone(payload.observation)
            self.assertIsNot(payload.dispatch, self.response)
            self.assertIsNot(payload.observation, self.observation)
            self.assertIsNone(payload.disposition)
            self.assertEqual(result.qualification_attempted, canonical)
            if canonical:
                self.assertIsNotNone(payload.qualification)
                self.assertIsNot(payload.qualification, self.confirmation)
                self.assertEqual(self.calls, ['verify', 'publish', 'qualify'])
            else:
                self.assertIsNone(payload.qualification)
                self.assertEqual(self.calls, ['verify', 'publish'])
        finally:
            target.__code__ = original_code
            namespace.pop('_rev3_hits', None)
            namespace.pop('_rev3_delegate', None)

    def test_rev3_enrichment_blocks_changed_qualifier(self):
        self.check_rev3_enrichment_replacement(False)

    def test_rev3_enrichment_blocks_changed_canonical_disposition(self):
        self.check_rev3_enrichment_replacement(True)

    def test_closed_results_and_correlation(self):
        result = self.run_f()
        for operation in (lambda: f.PublicationResult(), lambda: replace(result), lambda: copy.copy(result),
                lambda: copy.deepcopy(result), lambda: bool(result), lambda: f._EvaluationBinding()):
            with self.assertRaises(TypeError): operation()
        with self.assertRaises(TypeError):
            type('ForgedResult', (f.PublicationResult,), {})
        with self.assertRaises(AttributeError): result.reason = f.R.DISPOSITION_UNKNOWN
        marker = self.request.evaluation
        self.assertIs(f._copy(marker), marker)
        for operation in (lambda: copy.copy(marker), lambda: copy.deepcopy(marker)):
            with self.assertRaises(TypeError): operation()

    def test_e_rejected_root_is_not_external_rejection(self):
        self.source = e._issue(e.S.REJECTED, e.R.CURRENT_AUTHORITY_INELIGIBLE, self.source.qualified.source)
        self.check(self.run_f(), f.S.NOT_SUBMITTED, f.R.E_REJECTED, gate=False)
        self.assertEqual(self.calls, [])

    def test_e_unresolved_root_preserves_handoff(self):
        self.source = e._issue(e.S.UNRESOLVED, e.R.PREDECESSOR_UNKNOWN, self.source.qualified.source)
        self.check(self.run_f(), f.S.UNRESOLVED, f.R.E_UNRESOLVED, gate=False)
        self.assertEqual(self.calls, [])

    def test_inherited_reconciliation_cannot_be_cleared(self):
        object.__setattr__(self.source.qualified, 'reconciliation_required', True)
        self.check(self.run_f(), f.S.UNRESOLVED, f.R.INHERITED_RECONCILIATION, gate=False)
        self.assertEqual(self.calls, [])

    def test_replayed_assessment_equal_source_different_evaluation(self):
        self.run_f()
        old = self.response
        self.calls.clear()
        self.transform = lambda value: old
        self.check(self.run_f(), f.S.UNRESOLVED, f.R.DISPATCH_ASSESSMENT_UNBOUND, gate=False)
        self.assertIsNot(old.request.evaluation, self.request.evaluation)

    def test_equal_response_alone_is_not_retention_or_publication_truth(self):
        self.disposition = f.PublicationDispositionKind.UNKNOWN
        self.check(self.run_f(), f.S.UNRESOLVED, f.R.DISPOSITION_UNKNOWN, 1)

    def test_qualified_external_definite_rejection(self):
        self.return_outcome = service.ExternalOutcome.DEFINITELY_REJECTED
        self.disposition = f.PublicationDispositionKind.DEFINITELY_REJECTED
        self.check(self.run_f(), f.S.DEFINITELY_REJECTED, f.R.EXTERNAL_DEFINITELY_REJECTED, 1)

    def test_cas_conflict_without_closed_original_proof_stays_unknown(self):
        self.return_outcome = service.ExternalOutcome.DEFINITELY_REJECTED
        self.disposition = f.PublicationDispositionKind.UNKNOWN
        self.check(self.run_f(), f.S.UNRESOLVED, f.R.DISPOSITION_UNKNOWN, 1)

    def test_proven_non_dispatch_after_entry_is_not_external_closed_rejection(self):
        self.publish_error = service.CapabilityUnavailable('synthetic')
        self.disposition = f.PublicationDispositionKind.PROVEN_NON_DISPATCH
        payload = self.check(self.run_f(), f.S.NOT_SUBMITTED, f.R.PROVEN_NON_DISPATCH, 1)
        self.assertTrue(payload.reconciliation_required)

    def test_concurrent_exact_selection_requires_independent_confirmation(self):
        self.return_outcome = service.ExternalOutcome.UNKNOWN
        self.check(self.run_f(), f.S.PUBLISHED, f.R.PUBLISHED, 1)

    def test_concurrent_conflicting_head_is_not_overwritten_or_rebased(self):
        original = f._copy(self.source.qualified.gate.inputs.candidate)
        self.return_outcome = service.ExternalOutcome.UNKNOWN
        self.disposition = f.PublicationDispositionKind.UNKNOWN
        self.check(self.run_f(), f.S.UNRESOLVED, f.R.DISPOSITION_UNKNOWN, 1)
        self.assertEqual(self.effect_candidate, original)

    def test_later_evaluation_unknown_history_does_not_blindly_resubmit(self):
        self.disposition = f.PublicationDispositionKind.UNKNOWN
        self.check(self.run_f(), f.S.UNRESOLVED, f.R.DISPOSITION_UNKNOWN, 1)
        self.calls.clear()
        self.decision = f.DispatchDecision.UNKNOWN
        self.input_transform = lambda i: changed(i, 'authority', initial_operation=g.InitialOperationState.UNKNOWN)
        self.check(self.run_f(), f.S.UNRESOLVED, f.R.PUBLICATION_HISTORY_UNKNOWN, gate=True)
        self.assertEqual(self.calls, ['verify'])

    def test_initial_guard_before_replaced_source_traversal(self):
        replacement = []
        def bad(value): replacement.append(value); raise AssertionError('must not run')
        with patch.object(f, '_project', bad):
            result = self.run_f()
        payload = self.check(result, f.S.UNRESOLVED, f.R.DEPENDENCY_INSTABILITY, gate=False)
        self.assertEqual(replacement, [])
        self.assertEqual(self.calls, [])
        self.assertIsNone(payload.source)
        self.assertFalse(result.verification_attempted)
        self.assertFalse(result.qualification_attempted)

    def test_initial_guard_before_replaced_frozen_source_helper(self):
        replacement = []
        original = e._source
        def delegated(value): replacement.append(value); return original(value)
        with patch.object(e, '_source', delegated):
            self.check(self.run_f(), f.S.UNRESOLVED, f.R.DEPENDENCY_INSTABILITY, gate=False)
        self.assertEqual(replacement, [])
        self.assertEqual(self.calls, [])

    def test_original_verify_request_mutation_not_masked_by_detached_response(self):
        def mutate(candidate):
            self.assertIsNot(self.request.source, self.response.request.source)
            object.__setattr__(self.request.source.qualified.gate.inputs.candidate, 'event_sequence', 998)
        self.publish_hook = mutate
        self.check(self.run_f(), f.S.UNRESOLVED, f.R.REQUEST_INSTABILITY, 1)
        self.assertEqual(self.calls, ['verify', 'publish'])

    def test_original_verify_request_mutation_during_qualification(self):
        self.qualify_hook = lambda obs: object.__setattr__(self.request.source.qualified.gate.inputs.candidate,
                                                         'event_sequence', 998)
        self.check(self.run_f(), f.S.UNRESOLVED, f.R.REQUEST_INSTABILITY, 1)

    def test_instability_priority_source_request_response_dependency(self):
        def mutate(obs):
            object.__setattr__(self.source.qualified.gate.inputs.candidate, 'event_sequence', 997)
            object.__setattr__(self.request.source.qualified.gate.inputs.candidate, 'event_sequence', 998)
            object.__setattr__(self.response.inputs.candidate, 'event_sequence', 999)
            object.__setattr__(self.adapter.implementation, 'identity', 'changed')
        self.qualify_hook = mutate
        self.check(self.run_f(), f.S.UNRESOLVED, f.R.SOURCE_INSTABILITY, 1)

    def test_returned_publication_mutation_during_qualification(self):
        response = []
        original = self.publish
        def effect(candidate):
            value = original(candidate); response.append(value); return value
        self.adapter = replace(self.adapter, publish=effect)
        self.publisher = f.CheckpointPublisher(self.adapter)
        self.qualify_hook = lambda obs: object.__setattr__(response[0], 'evidence', self.authority)
        self.check(self.run_f(), f.S.UNRESOLVED, f.R.EFFECT_EVIDENCE_INSTABILITY, 1)

    def test_source_subclass_and_hostile_type_never_dispatch(self):
        class Sub(e.PublicationQualificationResult): pass
        for value in (Hostile(), object.__new__(Sub), object.__new__(e.PublicationQualificationResult)):
            self.source = value
            self.check(self.run_f(), f.S.NOT_SUBMITTED, f.R.INVALID_E_SOURCE, gate=False)
        self.assertEqual(self.calls, [])

    def test_original_completion_and_fixed_time_are_preserved(self):
        before = self.source.qualified.source.retained.source.prepared
        result = self.run_f()
        after = result.published.source.qualified.source.retained.source.prepared
        self.assertEqual(before.request.completion.t1, after.request.completion.t1)
        self.assertEqual(before.request.completion.t2, after.request.completion.t2)
        self.assertEqual(before.candidate.exact_bytes, after.candidate.exact_bytes)
        self.assertEqual(before.candidate.sha256, after.candidate.sha256)
        self.assertEqual(before.candidate.envelope.permit_reference, after.candidate.operation.permit)

    def test_binding_failure_precedes_advertised_decision(self):
        self.decision = f.DispatchDecision.INELIGIBLE
        self.transform = lambda a: replace(a, inputs=replace(a.inputs,
            candidate=replace(a.inputs.candidate, event_sequence=999)))
        self.check(self.run_f(),f.S.UNRESOLVED,f.R.SOURCE_BINDING_MISMATCH,gate=False)

    def test_negative_decision_cannot_conceal_unknown_premise(self):
        self.decision = f.DispatchDecision.INELIGIBLE
        self.input_transform = lambda i: changed(i,'authority',host_validity=service.EvidenceValidity.UNKNOWN)
        self.check(self.run_f(),f.S.UNRESOLVED,f.R.CANONICAL_GATE_CONTRADICTION,gate=True)

    def test_eligible_decision_cannot_conceal_negative_authority(self):
        self.input_transform = lambda i: changed(i,'authority',host_validity=service.EvidenceValidity.INVALID)
        self.coverage_present = False
        self.check(self.run_f(),f.S.UNRESOLVED,f.R.CANONICAL_GATE_CONTRADICTION,gate=True)

    def test_equal_valued_forgery_cannot_manufacture_e_issuance(self):
        self.source = f._copy(self.source)
        self.provenance = service.EvidenceValidity.INVALID
        self.decision = f.DispatchDecision.INELIGIBLE
        self.check(self.run_f(),f.S.NOT_SUBMITTED,f.R.E_PROVENANCE_INVALID,gate=False)

    def test_lost_process_local_handoff_does_not_prove_absence(self):
        self.publish_error = KeyboardInterrupt('synthetic')
        with self.assertRaises(f._PublicationEvaluationInterrupted): self.run_f()
        self.calls.clear()
        self.publish_error = None
        self.decision = f.DispatchDecision.UNKNOWN
        self.input_transform = lambda i: changed(i,'authority',initial_operation=g.InitialOperationState.UNKNOWN)
        self.check(self.run_f(),f.S.UNRESOLVED,f.R.PUBLICATION_HISTORY_UNKNOWN,gate=True)
        self.assertEqual(self.calls,['verify'])

    def test_dependency_replaced_during_canonical_reconstruction(self):
        original = e.cp.construct_candidate
        original_completed = p.validate_completed_command
        reached=[]
        replacement_calls=[]
        def delegated(*args,**kwargs):
            replacement_calls.append(True)
            return original_completed(*args,**kwargs)
        def reconstruction(*args,**kwargs):
            value=original(*args,**kwargs)
            if self.calls and not reached:
                handle=patch.object(p,'validate_completed_command',delegated)
                handle.start();self.addCleanup(handle.stop)
                reached.append(True)
            return value
        # Capture the deliberate synthetic reconstruction executable at composition.
        with patch.object(e.cp,'construct_candidate',reconstruction):
            self.publisher=f.CheckpointPublisher(self.adapter)
            result=self.run_f()
        self.check(result,f.S.UNRESOLVED,f.R.DEPENDENCY_INSTABILITY,gate=True)
        self.assertEqual(len(reached),1)
        self.assertEqual(self.calls,['verify'])

    def test_pre_entry_helper_replacement_during_verification_never_executes(self):
        reached=[]
        def replacement(value):reached.append(value);raise AssertionError('changed projection')
        def mutate(a):
            handle=patch.object(f,'_project',replacement);handle.start();self.addCleanup(handle.stop)
            return a
        self.transform=mutate
        self.check(self.run_f(),f.S.UNRESOLVED,f.R.DEPENDENCY_INSTABILITY,gate=False)
        self.assertEqual(reached,[])

    def test_post_entry_helper_replacement_never_erases_possible_effect(self):
        reached=[]
        def replacement(value):reached.append(value);raise AssertionError('changed projection')
        def mutate(candidate):
            handle=patch.object(f,'_project',replacement);handle.start();self.addCleanup(handle.stop)
        self.publish_hook=mutate
        self.check(self.run_f(),f.S.UNRESOLVED,f.R.DEPENDENCY_INSTABILITY,1)
        self.assertEqual(reached,[])

    def test_large_shared_history_has_no_arbitrary_graph_cap(self):
        # Closed traversal retains full history and sharing without graph-wide limits.
        row = self.source.qualified.source.retained.source.prepared.request.snapshot.completion
        values = tuple(row for _ in range(70000))
        captured = f._project(values)
        detached = f._detach(captured)
        self.assertEqual(len(detached), 70000)
        self.assertIs(detached[0], detached[-1])
        self.assertTrue(f._equal(captured, f._project(detached)))

    def test_valid_from_boundary_uses_canonical_model_without_permit_replacement(self):
        inputs=self.inputs(self.source)
        subject=replace(inputs.authority.permit,valid_from_us=16)
        for elapsed,expected in ((6000,None),(5000,(e.S.REJECTED,e.R.TEMPORAL_OUTSIDE)),
                                 (5500,(e.S.UNRESOLVED,e.R.TEMPORAL_UNCERTAIN))):
            current=time_at(inputs,elapsed)
            authority=replace(current.authority,permit=subject)
            self.assertEqual(e._time_reason(inputs.candidate,authority,current.time),expected)
        self.assertEqual(self.calls,[])

    def test_complete_guard_fixed_enum_and_schema_domains(self):
        tables=self.publisher._tables
        enums=next(entries for owner,name,mapping,entries in tables if owner is p and name=='_ENUMS')
        schemas=next(entries for owner,name,mapping,entries in tables if owner is p and name=='_SCHEMAS')
        self.assertEqual(tuple(k for k,v in enums),('Command','Operation','Phase','ArtifactType','LeaseStatus',
            'ExecutionState','QuarantineReason','EventType','OutcomeCode'))
        self.assertEqual(tuple(k for k,v in schemas),(p.Reference,p.Parameters,p.CommandPayload,p.EventPayload,
            p.AckPayload,p.MetadataRow,p.ReservationRow,p.ClaimRow,p.CommandRow))
        for owner,name,mapping,entries in tables:
            for key,value in entries:
                with patch.dict(mapping,{key:object()}):
                    self.assertFalse(self.publisher._composition_stable())
        self.assertTrue(self.publisher._composition_stable())

    def test_original_response_mutation_is_not_masked_by_qualifier_copy(self):
        self.qualify_hook=lambda observation:object.__setattr__(self.response.inputs.authority,'host','changed')
        self.check(self.run_f(),f.S.UNRESOLVED,f.R.RESPONSE_INSTABILITY,1)

    def test_qualifier_request_mutation_and_availability_keep_invocation(self):
        def mutate(observation):
            object.__setattr__(observation.dispatch.inputs.candidate,'event_sequence',998)
            raise TimeoutError('synthetic lost qualifier response')
        self.qualify_hook=mutate
        self.check(self.run_f(),f.S.UNRESOLVED,f.R.REQUEST_INSTABILITY,1)

    def test_verifier_request_mutation_and_effect_availability_keep_invocation(self):
        self.publish_hook=lambda candidate:object.__setattr__(self.request.source.qualified.gate.inputs.candidate,'event_sequence',998)
        self.publish_error=TimeoutError('synthetic lost response')
        self.check(self.run_f(),f.S.UNRESOLVED,f.R.REQUEST_INSTABILITY,1)

    def test_independent_evidence_can_resolve_malformed_transport_without_query(self):
        self.return_override=True;self.return_value=Hostile()
        payload=self.check(self.run_f(),f.S.PUBLISHED,f.R.PUBLISHED,1)
        self.assertIs(payload.observation.kind,f.PublicationObservationKind.MALFORMED_RETURN)
        self.assertIsNone(payload.observation.publication)
        self.assertEqual(self.calls,['verify','publish','qualify'])

    def test_no_dependency_or_result_override_parameter(self):
        with self.assertRaises(TypeError):self.publisher.publish_checkpoint(self.source,self.adapter)
        class Foreign(f.TrustedPublicationAdapter):pass
        for value in (Hostile(),None,Foreign(self.authority,self.implementation,self.verify,self.publish,self.qualify),
                replace(self.adapter,verify=None),replace(self.adapter,authority=None)):
            with self.assertRaises(TypeError):f.CheckpointPublisher(value)

    def test_original_63_and_frozen_repository_unchanged(self):
        def git(*args): return subprocess.check_output(['git', *args], cwd=ROOT).decode().strip()
        self.assertEqual(git('diff', '--name-only'), '')
        self.assertEqual(git('diff', '--cached', '--name-only'), '')
        additions = {'services/api/infrastructure/fixture_lease_publication.py', 'tests/test_fixture_lease_publication.py'}
        original = [v for v in git('ls-files', '--others', '--exclude-standard').splitlines() if v not in additions]
        digest = hashlib.sha256('\n'.join(v+' '+hashlib.sha256((ROOT/v).read_bytes()).hexdigest()
                                        for v in original).encode()).hexdigest()
        self.assertEqual(len(original), 63)
        self.assertEqual(digest, 'b6be9425bc0dbd474eef3c68b14fa592ec178689b8117eab04379253be45c250')


def source_case(name, transform):
    def test(self):
        value = transform(self.source)
        if value is not None: self.source = value
        self.check(self.run_f(), f.S.NOT_SUBMITTED, f.R.INVALID_E_SOURCE, gate=False)
        self.assertEqual(self.calls, [])
    setattr(PublicationTests, 'test_source_'+name, test)


for _name, _transform in (
    ('candidate', lambda v: v.qualified.gate.inputs.candidate),
    ('gate_inputs', lambda v: v.qualified.gate.inputs), ('gate_result', lambda v: v.qualified.gate),
    ('private_payload', lambda v: v.qualified), ('bytes', lambda v: b'candidate'),
    ('list', lambda v: [v]), ('mapping', lambda v: {'source': v}),
    ('wrong_reason', lambda v: object.__setattr__(v, 'reason', e.R.PREDECESSOR_UNKNOWN)),
    ('wrong_flag', lambda v: object.__setattr__(v, 'gate_evaluated', False)),
    ('cycle', lambda v: object.__setattr__(v.qualified.source.retained.source.prepared.request.snapshot, 'events', (v,))),
    ('mutable_history', lambda v: object.__setattr__(v.qualified.source.retained.source.prepared.request.snapshot, 'events', [])),
    ('historical_T1', lambda v: object.__setattr__(v.qualified.source.retained.source.prepared.request.completion, 't1', None)),
    ('commit', lambda v: object.__setattr__(v.qualified.source.retained.source.prepared.request.completion.local,
        'storage_result', c.store.LocalStorageResult.LOCAL_STORAGE_ROLLBACK_CONFIRMED)),
): source_case(_name, _transform)


def assessment_case(name, transform, reason, state=None, gate=False):
    def test(self):
        self.transform = lambda value: transform(self, value)
        self.check(self.run_f(), state or f.S.UNRESOLVED, reason, gate=gate)
    setattr(PublicationTests, 'test_assessment_'+name, test)


for _name, _transform, _reason in (
    ('foreign', lambda t,a: Hostile(), f.R.DISPATCH_ASSESSMENT_MALFORMED),
    ('missing', lambda t,a: None, f.R.DISPATCH_ASSESSMENT_MALFORMED),
    ('missing_inputs', lambda t,a: replace(a, inputs=None), f.R.DISPATCH_ASSESSMENT_MALFORMED),
    ('wrong_authority', lambda t,a: replace(a, authority=service.EvidenceReference('wrong', b'x'*32)), f.R.DISPATCH_ASSESSMENT_UNBOUND),
    ('wrong_implementation', lambda t,a: replace(a, implementation=service.EvidenceReference('wrong', b'x'*32)), f.R.DISPATCH_ASSESSMENT_UNBOUND),
    ('wrong_marker', lambda t,a: replace(a, request=replace(a.request, evaluation=object.__new__(f._EvaluationBinding))), f.R.DISPATCH_ASSESSMENT_UNBOUND),
    ('coverage_binding', lambda t,a: replace(a, coverage=replace(a.coverage, operation=service.OriginalOperation(a.coverage.operation.permit,
        service.OperationKind.PERMIT_COMPLETION))), f.R.DISPATCH_ASSESSMENT_UNBOUND),
): assessment_case(_name, _transform, _reason, gate=_name=='coverage_binding')

for _validity in (service.EvidenceValidity.INVALID, service.EvidenceValidity.UNKNOWN):
    assessment_case('coverage_'+_validity.value,
        lambda t,a,v=_validity:replace(a,coverage=replace(a.coverage,validity=v)),
        f.R.DISPATCH_COVERAGE_UNQUALIFIED,gate=True)


def response_case(name, value):
    def test(self):
        self.return_override=True
        self.return_value=value(self)
        self.disposition=f.PublicationDispositionKind.UNKNOWN
        self.check(self.run_f(),f.S.UNRESOLVED,f.R.DISPOSITION_UNKNOWN,1)
        self.assertIsNone(self.observation.publication)
        self.assertIn(self.observation.kind,(f.PublicationObservationKind.MALFORMED_RETURN,
                                            f.PublicationObservationKind.UNBOUND_RETURN))
    setattr(PublicationTests,'test_response_'+name,test)


response_case('none',lambda t:None)
response_case('foreign',lambda t:Hostile())
response_case('candidate_echo',lambda t:t.source.qualified.gate.inputs.candidate)
response_case('wrong_candidate',lambda t:service.PublicationResult(service.ExternalOutcome.CONFIRMED,
    replace(t.source.qualified.gate.inputs.candidate,event_sequence=999),t.reference))


def time_at(inputs,elapsed,error=0):
    time=inputs.time
    point=replace(time.point,ticks_ns=time.sample.anchor.ticks_ns+elapsed)
    propagation=replace(time.propagation,elapsed_ns=elapsed,error_ns=error)
    interval=service.evaluate_time(time.sample,time.profile,point,propagation).interval
    return replace(inputs,time=replace(time,point=point,propagation=propagation,covered_interval=interval),
                   authority=replace(inputs.authority,point=point,interval=interval))


def shape_case(validity, provenance, decision, material, coverage):
    def test(self):
        self.validity, self.provenance, self.decision = validity, provenance, decision
        # Start from a complete otherwise-valid assessment; deliberately control shape.
        def transform(a):
            inputs = self.inputs(a.request.source) if material else None
            cov = a.coverage
            if coverage and cov is None:
                positive = self.inputs(a.request.source)
                cov = f.PublicationDispatchCoverage(f._copy(a.request), positive.candidate, positive.candidate.operation,
                    self.authority, self.implementation, service.EvidenceValidity.VALID, self.reference,
                    positive.authority.point, positive.authority.interval)
            return replace(a, inputs=inputs, coverage=cov if coverage else None)
        self.transform = transform
        valid_shape = ((provenance is service.EvidenceValidity.INVALID and decision is f.DispatchDecision.INELIGIBLE
                        and not material and not coverage)
            or (provenance is service.EvidenceValidity.UNKNOWN and decision is f.DispatchDecision.UNKNOWN
                        and not material and not coverage)
            or (provenance is service.EvidenceValidity.VALID and material
                        and (decision is f.DispatchDecision.ELIGIBLE or not coverage)))
        if not valid_shape:
            self.check(self.run_f(), f.S.UNRESOLVED, f.R.DISPATCH_ASSESSMENT_MALFORMED, gate=False)
        elif validity is not service.EvidenceValidity.VALID:
            self.check(self.run_f(), f.S.UNRESOLVED, f.R.DISPATCH_ASSESSMENT_UNQUALIFIED, gate=False)
        elif provenance is not service.EvidenceValidity.VALID:
            self.check(self.run_f(), f.S.NOT_SUBMITTED if provenance is service.EvidenceValidity.INVALID else f.S.UNRESOLVED,
                f.R.E_PROVENANCE_INVALID if provenance is service.EvidenceValidity.INVALID else f.R.E_PROVENANCE_UNKNOWN, gate=False)
        elif decision is not f.DispatchDecision.ELIGIBLE:
            self.check(self.run_f(), f.S.UNRESOLVED, f.R.CANONICAL_GATE_CONTRADICTION, gate=True)
        elif not coverage:
            self.check(self.run_f(), f.S.UNRESOLVED, f.R.DISPATCH_COVERAGE_UNQUALIFIED, gate=True)
        else:
            self.check(self.run_f(), f.S.PUBLISHED, f.R.PUBLISHED, 1, True)
    suffix = '_'.join((validity.value, provenance.value, decision.value, str(int(material)), str(int(coverage))))
    setattr(PublicationTests, 'test_shape_'+suffix, test)


# Exhaust every source/decision/presence shape for VALID outer validity. The five
# structurally supported shapes are also checked under both unauthenticated validities.
for _prov in service.EvidenceValidity:
    for _dec in f.DispatchDecision:
        for _material in (False, True):
            for _cov in (False, True):
                shape_case(service.EvidenceValidity.VALID, _prov, _dec, _material, _cov)
for _valid in (service.EvidenceValidity.INVALID, service.EvidenceValidity.UNKNOWN):
    for _prov, _dec, _material in ((service.EvidenceValidity.INVALID, f.DispatchDecision.INELIGIBLE, False),
            (service.EvidenceValidity.UNKNOWN, f.DispatchDecision.UNKNOWN, False),
            (service.EvidenceValidity.VALID, f.DispatchDecision.ELIGIBLE, True),
            (service.EvidenceValidity.VALID, f.DispatchDecision.INELIGIBLE, True),
            (service.EvidenceValidity.VALID, f.DispatchDecision.UNKNOWN, True)):
        shape_case(_valid, _prov, _dec, _material, False)


def input_case(name, transform, decision, state, reason):
    def test(self):
        self.decision = decision
        self.input_transform = transform
        self.check(self.run_f(), state, reason, gate=True)
    setattr(PublicationTests, 'test_inputs_'+name, test)


for _field in ('permit_validity', 'activation_validity', 'host_validity', 'fencing_validity', 'representation_validity'):
    for _valid in (service.EvidenceValidity.INVALID, service.EvidenceValidity.UNKNOWN):
        input_case(_field+'_'+_valid.value, lambda i,k=_field,v=_valid: changed(i,'authority',**{k:v}),
            f.DispatchDecision.INELIGIBLE if _valid is service.EvidenceValidity.INVALID else f.DispatchDecision.UNKNOWN,
            f.S.NOT_SUBMITTED if _valid is service.EvidenceValidity.INVALID else f.S.UNRESOLVED,
            f.R.CURRENT_AUTHORITY_INELIGIBLE if _valid is service.EvidenceValidity.INVALID else f.R.CURRENT_AUTHORITY_UNKNOWN)
for _field in ('activation_status','host_status','fencing_status'):
    for _status in (g.CurrentStatus.INELIGIBLE,g.CurrentStatus.UNKNOWN):
        input_case(_field+'_'+_status.value, lambda i,k=_field,v=_status: changed(i,'authority',**{k:v}),
            f.DispatchDecision.INELIGIBLE if _status is g.CurrentStatus.INELIGIBLE else f.DispatchDecision.UNKNOWN,
            f.S.NOT_SUBMITTED if _status is g.CurrentStatus.INELIGIBLE else f.S.UNRESOLVED,
            f.R.CURRENT_AUTHORITY_INELIGIBLE if _status is g.CurrentStatus.INELIGIBLE else f.R.CURRENT_AUTHORITY_UNKNOWN)
for _valid in (service.EvidenceValidity.INVALID,service.EvidenceValidity.UNKNOWN):
    input_case('predecessor_'+_valid.value,lambda i,v=_valid: changed(i,'authority',predecessor_validity=v),
        f.DispatchDecision.INELIGIBLE if _valid is service.EvidenceValidity.INVALID else f.DispatchDecision.UNKNOWN,
        f.S.NOT_SUBMITTED if _valid is service.EvidenceValidity.INVALID else f.S.UNRESOLVED,
        f.R.PREDECESSOR_MISMATCH if _valid is service.EvidenceValidity.INVALID else f.R.PREDECESSOR_UNKNOWN)
for _history in (g.InitialOperationState.ATTEMPTED,g.InitialOperationState.UNKNOWN):
    input_case('history_'+_history.value,lambda i,v=_history: changed(i,'authority',initial_operation=v),
        f.DispatchDecision.UNKNOWN,f.S.UNRESOLVED,f.R.PUBLICATION_HISTORY_NON_INITIAL
        if _history is g.InitialOperationState.ATTEMPTED else f.R.PUBLICATION_HISTORY_UNKNOWN)
for _target,_reason in (('local',f.R.HISTORICAL_EVIDENCE_CONTRADICTION),('retention',f.R.RETENTION_UNQUALIFIED),
        ('authority',f.R.CURRENT_AUTHORITY_UNKNOWN),('time',f.R.TIME_UNQUALIFIED)):
    input_case('missing_'+_target,lambda i,k=_target: replace(i,**{k:None}), f.DispatchDecision.UNKNOWN,f.S.UNRESOLVED,_reason)
for _name,_transform,_reason in (
    ('local_invalid',lambda i:changed(i,'local',qualification=service.EvidenceValidity.INVALID),f.R.HISTORICAL_EVIDENCE_CONTRADICTION),
    ('retention_unknown',lambda i:changed(i,'retention',qualification=service.EvidenceValidity.UNKNOWN),f.R.RETENTION_UNQUALIFIED),
    ('time_unknown',lambda i:changed(i,'time',qualification=service.EvidenceValidity.UNKNOWN),f.R.TIME_UNQUALIFIED),
    ('time_profile_binding',lambda i:changed(i,'time',profile=replace(i.time.profile,source='other')),f.R.TIME_BINDING_MISMATCH),
    ('authorization_unknown',lambda i:changed(i,'time',authorization_timing=service.TimingApplicability.UNKNOWN),f.R.TIME_UNQUALIFIED),
    ('freshness_unknown',lambda i:changed(i,'time',freshness_timing=service.TimingApplicability.UNKNOWN),f.R.TIME_UNQUALIFIED),
    ('history_before_historical',lambda i:replace(changed(i,'authority',initial_operation=g.InitialOperationState.UNKNOWN),local=None),f.R.PUBLICATION_HISTORY_UNKNOWN),
    ('historical_before_retention',lambda i:replace(i,local=None,retention=None),f.R.HISTORICAL_EVIDENCE_CONTRADICTION),
    ('unknown_before_negative',lambda i:changed(i,'authority',permit_validity=service.EvidenceValidity.INVALID,host_validity=service.EvidenceValidity.UNKNOWN),f.R.CURRENT_AUTHORITY_UNKNOWN),
):input_case(_name,_transform,f.DispatchDecision.UNKNOWN,f.S.UNRESOLVED,_reason)

for _name,_transform,_reason in (
    ('domain',lambda i:changed(i,'time',point=replace(i.time.point,domain_id='foreign')),f.R.TIME_UNQUALIFIED),
    ('process',lambda i:changed(i,'time',point=replace(i.time.point,process_id='foreign')),f.R.TIME_UNQUALIFIED),
    ('range',lambda i:changed(i,'time',point=replace(i.time.point,ticks_ns=100001)),f.R.TIME_UNQUALIFIED),
    ('propagation_binding',lambda i:changed(i,'time',propagation=replace(i.time.propagation,elapsed_ns=999)),f.R.TIME_UNQUALIFIED),
    ('width',lambda i:changed(i,'time',propagation=replace(i.time.propagation,error_ns=6000)),f.R.TIME_UNQUALIFIED),
    ('covered_interval_binding',lambda i:changed(i,'time',covered_interval=service.UtcInterval(1,2)),f.R.TIME_BINDING_MISMATCH),
    ('sample_refresh_binding',lambda i:changed(i,'time',sample=replace(i.time.sample,source='foreign')),f.R.TIME_BINDING_MISMATCH),
):input_case('timing_'+_name,_transform,f.DispatchDecision.UNKNOWN,f.S.UNRESOLVED,_reason)


for _outcome in service.ExternalOutcome:
    def prior_test(self,outcome=_outcome):
        self.decision=f.DispatchDecision.UNKNOWN
        def transform(i):
            published=service.PublicationResult(outcome,i.candidate,None if outcome is service.ExternalOutcome.UNKNOWN else self.reference)
            prior=o.publication_disposition(i.candidate,published,local_commit=o.LocalCommitState.CONFIRMED,
                qualification=service.EvidenceValidity.VALID)
            return replace(i,prior=prior)
        self.input_transform=transform
        reason=f.R.PUBLICATION_HISTORY_NON_INITIAL if outcome is service.ExternalOutcome.CONFIRMED else f.R.PUBLICATION_HISTORY_UNKNOWN
        self.check(self.run_f(),f.S.UNRESOLVED,reason,gate=True)
    setattr(PublicationTests,'test_prior_'+_outcome.value,prior_test)

for _name,_elapsed,_error,_decision,_state,_reason in (
    ('permit_inside',9000,0,f.DispatchDecision.ELIGIBLE,f.S.PUBLISHED,f.R.PUBLISHED),
    ('permit_equal',10000,0,f.DispatchDecision.INELIGIBLE,f.S.NOT_SUBMITTED,f.R.TEMPORAL_OUTSIDE),
    ('permit_after',11000,0,f.DispatchDecision.INELIGIBLE,f.S.NOT_SUBMITTED,f.R.TEMPORAL_OUTSIDE),
    ('permit_overlap',9500,100,f.DispatchDecision.UNKNOWN,f.S.UNRESOLVED,f.R.TEMPORAL_UNCERTAIN),
):
    def temporal_test(self,elapsed=_elapsed,error=_error,decision=_decision,state=_state,reason=_reason):
        self.decision=decision
        self.input_transform=lambda i:time_at(i,elapsed,error)
        self.check(self.run_f(),state,reason,1 if state is f.S.PUBLISHED else 0,True)
    setattr(PublicationTests,'test_temporal_'+_name,temporal_test)

for _field in ('authorization','freshness'):
    for _relative in ('future','equal','past','overlap'):
        def deadline_test(self,field=_field,relative=_relative):
            positive=relative=='future' or (relative=='equal' and field=='authorization')
            self.decision=(f.DispatchDecision.ELIGIBLE if positive else
                f.DispatchDecision.UNKNOWN if relative=='overlap' else f.DispatchDecision.INELIGIBLE)
            def transform(i):
                i=time_at(i,6000,100 if relative=='overlap' else 0)
                deadline=16 if relative in ('equal','overlap') else 17 if relative=='future' else 15
                cls=service.InclusiveDeadline if field=='authorization' else service.StrictDeadline
                return changed(i,'time',**{field+'_timing':service.TimingApplicability.REQUIRED,
                                           field+'_deadline':cls(deadline)})
            self.input_transform=transform
            state=f.S.PUBLISHED if positive else f.S.UNRESOLVED if relative=='overlap' else f.S.NOT_SUBMITTED
            reason=f.R.PUBLISHED if positive else f.R.TEMPORAL_UNCERTAIN if relative=='overlap' else f.R.TEMPORAL_OUTSIDE
            self.check(self.run_f(),state,reason,1 if positive else 0,True)
        setattr(PublicationTests,'test_deadline_'+_field+'_'+_relative,deadline_test)


def binding_case(name, mutate, reason):
    def test(self):
        def transform(a):
            value=f._copy(a.inputs);mutate(value);return replace(a,inputs=value)
        self.transform=transform
        self.check(self.run_f(),f.S.UNRESOLVED,reason,gate=False)
    setattr(PublicationTests,'test_binding_'+name,test)


binding_case('candidate',lambda i:object.__setattr__(i.candidate,'event_sequence',999),f.R.SOURCE_BINDING_MISMATCH)
binding_case('original_operation',lambda i:object.__setattr__(i.authority,'operation',service.OriginalOperation(i.candidate.operation.permit,
    service.OperationKind.PERMIT_COMPLETION)),f.R.SOURCE_BINDING_MISMATCH)
binding_case('committed_transition',lambda i:object.__setattr__(i.local,'head',replace(i.local.head,state_digest=b'x'*32)),f.R.SOURCE_BINDING_MISMATCH)
binding_case('retention_reference',lambda i:object.__setattr__(i.retention,'reference',service.EvidenceReference('wrong',b'x'*32)),f.R.SOURCE_BINDING_MISMATCH)
binding_case('predecessor_subject',lambda i:object.__setattr__(i.authority,'predecessor',replace(i.authority.predecessor,revision=999)),f.R.DISPATCH_ASSESSMENT_UNBOUND)
binding_case('permit_interval',lambda i:object.__setattr__(i.authority,'permit',replace(i.authority.permit,valid_until_us=999)),f.R.DISPATCH_ASSESSMENT_UNBOUND)


def availability_case(stage, error_type):
    def test(self):
        error=error_type('synthetic availability')
        setattr(self,stage+'_error',error)
        self.disposition=f.PublicationDispositionKind.UNKNOWN
        reason={'verify':f.R.DISPATCH_QUALIFICATION_UNAVAILABLE,'publish':f.R.DISPOSITION_UNKNOWN,
                'qualify':f.R.DISPOSITION_QUALIFICATION_UNAVAILABLE}[stage]
        self.check(self.run_f(),f.S.UNRESOLVED,reason,0 if stage=='verify' else 1)
    setattr(PublicationTests,'test_availability_'+stage+'_'+error_type.__name__,test)


def exception_case(stage, error_type):
    def test(self):
        error=error_type('synthetic defect')
        setattr(self,stage+'_error',error)
        if stage=='verify':
            with self.assertRaises(error_type) as caught:self.run_f()
            self.assertIs(caught.exception,error)
            self.assertEqual(self.calls,['verify'])
        else:
            with self.assertRaises(f._PublicationEvaluationInterrupted) as caught:self.run_f()
            self.assertIs(caught.exception.__cause__,error)
            payload=self.check(caught.exception.result,f.S.UNRESOLVED,f.R.EVALUATION_INTERRUPTED,1)
            self.assertTrue(payload.reconciliation_required)
            self.assertIs(payload.source.qualified.source.retained.source.prepared.request.completion.local.storage_result,
                          c.store.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
    setattr(PublicationTests,'test_exception_'+stage+'_'+error_type.__name__,test)


for _stage in ('verify','publish','qualify'):
    for _error in (service.CapabilityUnavailable,c.a.ExternalAvailabilityFailure,TimeoutError):availability_case(_stage,_error)
    for _error in (RuntimeError,AssertionError,TypeError,MemoryError,KeyboardInterrupt,SystemExit):exception_case(_stage,_error)


def disposition_case(name, transform, reason):
    def test(self):
        self.confirm_transform=lambda value:transform(self,value)
        self.check(self.run_f(),f.S.UNRESOLVED,reason,1)
    setattr(PublicationTests,'test_disposition_'+name,test)


for _name,_transform,_reason in (
    ('foreign',lambda t,a:Hostile(),f.R.DISPOSITION_MALFORMED),
    ('none',lambda t,a:None,f.R.DISPOSITION_MALFORMED),
    ('invalid',lambda t,a:replace(a,validity=service.EvidenceValidity.INVALID),f.R.DISPOSITION_UNQUALIFIED),
    ('unknown',lambda t,a:replace(a,validity=service.EvidenceValidity.UNKNOWN),f.R.DISPOSITION_UNQUALIFIED),
    ('wrong_authority',lambda t,a:replace(a,authority=service.EvidenceReference('foreign',b'x'*32)),f.R.DISPOSITION_UNBOUND),
    ('wrong_observation',lambda t,a:replace(a,observation=replace(a.observation,kind=f.PublicationObservationKind.TIMEOUT)),f.R.DISPOSITION_UNBOUND),
    ('missing_publication',lambda t,a:replace(a,publication=None),f.R.DISPOSITION_MALFORMED),
    ('outcome_contradiction',lambda t,a:replace(a,disposition=f.PublicationDispositionKind.DEFINITELY_REJECTED),f.R.DISPOSITION_CONTRADICTION),
    ('non_dispatch_with_result',lambda t,a:replace(a,disposition=f.PublicationDispositionKind.PROVEN_NON_DISPATCH),f.R.DISPOSITION_CONTRADICTION),
):disposition_case(_name,_transform,_reason)


def dispatch_replacement(name, owner, field, entry=None, mapping=False):
    def test(self):
        calls=[]
        original=getattr(owner,field)
        def record(*args,**kwargs):calls.append(True);return (original if entry is None else original[entry])(*args,**kwargs)
        def mutate(a):
            if mapping:
                handle=patch.object(owner,field,dict(original))
            elif entry is not None:
                handle=patch.dict(original,{entry:record if field=='_ENUMS' else (99,99,())})
            else:handle=patch.object(owner,field,record)
            handle.start();self.addCleanup(handle.stop)
            return a
        self.transform=mutate
        self.check(self.run_f(),f.S.UNRESOLVED,f.R.DEPENDENCY_INSTABILITY,gate=False)
        self.assertEqual(calls,[])
        self.assertEqual(self.calls,['verify'])
    setattr(PublicationTests,'test_dependency_'+name,test)


dispatch_replacement('protocol_completed',p,'validate_completed_command')
dispatch_replacement('enum_entry',p,'_ENUMS','Command')
dispatch_replacement('enum_mapping',p,'_ENUMS',mapping=True)
dispatch_replacement('schema_entry',p,'_SCHEMAS',p.CommandPayload)
dispatch_replacement('schema_mapping',p,'_SCHEMAS',mapping=True)
dispatch_replacement('timing',service,'evaluate_time')
dispatch_replacement('codec',p,'decode_record')
dispatch_replacement('gate',g,'evaluate_publication_gate')


class StaticContractTests(unittest.TestCase):
    def test_exact_reason_and_permission_sets_and_single_call_sites(self):
        self.assertEqual(len(f.PublicationReason),42)
        self.assertEqual(len(f._PERMISSIONS),15)
        tree=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_publication.py').read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
        for name in ('_verify','_gate','_publish','_qualify','_canonical'):
            self.assertEqual(sum(isinstance(n.func,ast.Attribute) and n.func.attr==name for n in calls),1,name)
        forbidden={'construct_candidate','query_publication','complete_original','query_completion','obtain',
            'renew','deliver','redeliver','commit','execute','connect','measure','sleep'}
        self.assertEqual([n.func.attr for n in calls if isinstance(n.func,ast.Attribute) and n.func.attr in forbidden],[])

    def test_all_33_frozen_reason_mappings(self):
        mapping=dict(f._E_TO_F)
        self.assertEqual(set(mapping),set(e.PublicationQualificationReason))
        self.assertEqual(len(f._E_TO_F),33)
        exact={
            'QUALIFIED':None,'INVALID_D_SOURCE':'E_REJECTED','NOT_RETAINED':'E_REJECTED',
            'UPSTREAM_UNRESOLVED':'E_UNRESOLVED','INHERITED_RECONCILIATION':'E_UNRESOLVED',
            'UNQUALIFIED_D_PROVENANCE':'E_REJECTED','D_PROVENANCE_UNKNOWN':'E_UNRESOLVED',
            'CANDIDATE_BINDING_MISMATCH':'SOURCE_BINDING_MISMATCH','ORIGINAL_OPERATION_MISMATCH':'SOURCE_BINDING_MISMATCH',
            'COMMITTED_TRANSITION_MISMATCH':'SOURCE_BINDING_MISMATCH','RETENTION_BINDING_MISMATCH':'SOURCE_BINDING_MISMATCH',
            'ASSESSMENT_BINDING_MISMATCH':'DISPATCH_ASSESSMENT_UNBOUND','MALFORMED_ASSESSMENT':'DISPATCH_ASSESSMENT_MALFORMED',
            'UNQUALIFIED_ASSESSMENT':'DISPATCH_ASSESSMENT_UNQUALIFIED','DEPENDENCY_UNAVAILABLE':'DISPATCH_QUALIFICATION_UNAVAILABLE'}
        for reason in e.PublicationQualificationReason:
            expected=exact.get(reason.value,reason.value)
            self.assertEqual(None if mapping[reason] is None else mapping[reason].value,expected)


if __name__ == '__main__': unittest.main()
