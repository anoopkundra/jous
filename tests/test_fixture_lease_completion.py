"""Synthetic offline certification of Increment G's completion boundary."""
import copy
from dataclasses import replace
import importlib.util
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
fixture = runpy.run_path(str(ROOT / 'tests/test_fixture_lease_publication.py'))
f = fixture['f']
name = f.__package__ + '.fixture_lease_completion'
spec = importlib.util.spec_from_file_location(name, ROOT / 'services/api/infrastructure/fixture_lease_completion.py')
g = importlib.util.module_from_spec(spec)
sys.modules[name] = g
spec.loader.exec_module(g)
s, o, V, R, S = g.service, g.outcomes, g.V, g.R, g.S


class UnavailableCompositionTests(unittest.TestCase):
    def check_unavailable(self, result, reason=R.COMPOSITION_UNAVAILABLE):
        self.assertIs(type(result), g.CompletionResult)
        self.assertIs(result.state, S.UNRESOLVED)
        self.assertIs(result.reason, reason)
        self.assertEqual(tuple(getattr(result, name) for name in ('verification_attempted',
            'completion_entry_consumed', 'completion_invoked', 'qualification_attempted',
            'disposition_evaluated')), (False,) * 5)
        self.assertIs(result.next_required_gate, o.RequiredGate.RECOVERY_HANDOFF)
        self.assertIs(type(result.unresolved), g._CompletionPayload)
        self.assertTrue(result.unresolved.reconciliation_required)
        self.assertFalse(result.unresolved.owner_entry_attempted)
        for name in ('source', 'request', 'eligibility', 'entry_decision', 'observation',
                'qualification', 'canonical_observation', 'disposition'):
            self.assertIsNone(getattr(result.unresolved, name))
        for name in ('completed', 'not_submitted', 'rejected'): self.assertIsNone(getattr(result, name))
        for name in g._PERMISSIONS: self.assertIs(getattr(result, name), False)

    def test_unavailable_hostile_source_setter(self):
        completer, calls = g.CheckpointCompleter(), []
        def hostile(*args): calls.append(True); raise AssertionError('payload source setter executed')
        with patch.object(g._CompletionPayload, 'source', property(hostile, hostile), create=True):
            result = completer.complete_original(None)
        self.check_unavailable(result)
        self.assertEqual(calls, [])
        self.assertNotIn('_owner', vars(completer))
        self.assertNotIn('_adapter', vars(completer))

    def test_unavailable_hostile_constructor_and_result_setter(self):
        for kind in ('payload_constructor', 'result_setter'):
            with self.subTest(kind=kind):
                completer, calls = g.CheckpointCompleter(), []
                def hostile(*args): calls.append(True); raise AssertionError('failure machinery executed')
                target, name, replacement = ((g._CompletionPayload, '__init__', hostile)
                    if kind == 'payload_constructor'
                    else (g.CompletionResult, 'state', property(hostile, hostile)))
                with patch.object(target, name, replacement, create=True):
                    result = completer.complete_original(None)
                self.check_unavailable(result)
                self.assertEqual(calls, [])

    def test_unavailable_issue_copy_not_invoked(self):
        completer, calls = g.CheckpointCompleter(), []
        def issue(*args, **kwargs): calls.append('issue'); raise AssertionError('issue executed')
        def copy(*args, **kwargs): calls.append('copy'); raise AssertionError('copy executed')
        with patch.object(g, '_issue', issue), patch.object(g, '_copy', copy):
            result = completer.complete_original(None)
        self.check_unavailable(result)
        self.assertEqual(calls, [])

    def test_unavailable_records_are_fresh(self):
        completer = g.CheckpointCompleter()
        first, second = completer.complete_original(None), completer.complete_original(None)
        self.check_unavailable(first); self.check_unavailable(second)
        self.assertIsNot(first, second)
        self.assertIsNot(first.unresolved, second.unresolved)
        self.assertEqual(vars(first), vars(second))

    def test_unavailable_bootstrap_code_precedence(self):
        completer = g.CheckpointCompleter()
        original = g._composition_stable.__code__
        calls = []
        g._test_unavailable_bootstrap_calls = calls
        replacement = compile('def changed(value):\n _test_unavailable_bootstrap_calls.append(True)\n return True\n',
            '<unavailable bootstrap replacement>', 'exec').co_consts[0]
        try:
            g._composition_stable.__code__ = replacement
            result = completer.complete_original(None)
        finally:
            g._composition_stable.__code__ = original
            del g._test_unavailable_bootstrap_calls
        self.check_unavailable(result, R.DEPENDENCY_INSTABILITY)
        self.assertEqual(calls, [])


class CompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        factory = fixture['PublicationTests']
        factory.setUpClass()
        case = factory('test_genuine_publication_exact_subject_and_detachment')
        case.setUp()
        cls.template = case.run_f()
        if cls.template.state is not f.S.PUBLISHED: raise AssertionError('genuine F fixture failed')

    def setUp(self):
        self.source = f._copy(self.template)
        self.authority = f._copy(self.source.published.dispatch.authority)
        self.implementation = s.EvidenceReference('G-independent-completion', b'g' * 32)
        self.reference = s.EvidenceReference('G-authenticated-closure', b'r' * 32)
        self.calls = []
        self.verify_hook = self.complete_hook = self.qualify_hook = None
        self.verify_error = self.complete_error = self.qualify_error = None
        self.transform = self.qualify_transform = None
        self.outcome = s.ExternalOutcome.CONFIRMED
        self.validity = V.VALID
        self.raw_override = False
        self.raw_value = None
        self.request = self.assessment = self.observation = self.confirmation = None
        self.owner = g._CompletionEntryOwner(self.source, authority=self.authority,
            implementation=self.implementation)
        self.adapter = g.TrustedCompletionAdapter(self.authority, self.implementation,
            self.verify, self.complete, self.qualify)
        self.completer = g.CheckpointCompleter(self.adapter, owner=self.owner)

    def verify(self, request, owner):
        frame = sys._getframe(1).f_locals
        self.assertTrue(frame['verified'])
        self.assertFalse(frame['consumed'])
        self.assertFalse(frame['invoked'])
        self.calls.append('verify')
        self.request = request
        if self.verify_error is not None: raise self.verify_error
        if self.verify_hook is not None: self.verify_hook(request, owner)
        genuine = owner is self.owner and g._same(request.source, self.source)
        result = g.CompletionEligibilityAssessment(g._copy(request), self.authority,
            self.implementation, V.VALID, self.reference, V.VALID if genuine else V.INVALID,
            V.VALID, V.VALID, V.VALID, V.VALID, V.VALID, g.ContinuityStatus.PENDING)
        self.assessment = result if self.transform is None else self.transform(result)
        return self.assessment

    def complete(self, operation, publication):
        frame = sys._getframe(1).f_locals
        self.assertTrue(frame['verified'] and frame['consumed'] and frame['invoked'])
        self.assertFalse(frame['qualified'] or frame['evaluated'])
        self.assertIs(self.owner._state, g._EntryState.ENTERED)
        self.calls.append('complete')
        if self.complete_hook is not None: self.complete_hook(operation, publication)
        if self.complete_error is not None: raise self.complete_error
        if self.raw_override: return self.raw_value
        return s.CompletionResult(self.outcome, operation, publication,
            None if self.outcome is s.ExternalOutcome.UNKNOWN else self.reference)

    def qualify(self, observation):
        frame = sys._getframe(1).f_locals
        self.assertTrue(frame['verified'] and frame['consumed'] and frame['invoked'] and frame['qualified'])
        self.assertFalse(frame['evaluated'])
        self.calls.append('qualify')
        self.observation = observation
        if self.qualify_hook is not None: self.qualify_hook(observation)
        if self.qualify_error is not None: raise self.qualify_error
        result = g.CompletionQualificationAssessment(g._copy(observation), self.authority,
            self.implementation, self.validity, self.reference,
            s.CompletionResult(self.outcome, g._copy(observation.request.operation),
                g._copy(observation.request.publication),
                None if self.outcome is s.ExternalOutcome.UNKNOWN else self.reference)
            if self.validity is V.VALID else None)
        self.confirmation = result if self.qualify_transform is None else self.qualify_transform(result)
        return self.confirmation

    def run_g(self): return self.completer.complete_original(self.source)

    def check(self, result, reason, flags, effects=0):
        self.assertIs(result.reason, reason)
        state = (S.COMPLETED if reason is R.COMPLETED else S.DEFINITELY_REJECTED
            if reason is R.EXTERNAL_DEFINITELY_REJECTED else S.NOT_SUBMITTED
            if reason in (R.INVALID_F_SOURCE, R.F_NOT_PUBLISHED, R.F_PROVENANCE_INVALID)
            else S.UNRESOLVED)
        self.assertIs(result.state, state)
        self.assertIs(result.next_required_gate, o.RequiredGate.CURRENT_DELIVERY_QUALIFICATION
            if state is S.COMPLETED else o.RequiredGate.RECOVERY_HANDOFF)
        self.assertEqual(tuple(getattr(result, name) for name in ('verification_attempted',
            'completion_entry_consumed', 'completion_invoked', 'qualification_attempted',
            'disposition_evaluated')), tuple(bool(flag) for flag in flags))
        self.assertEqual(self.calls.count('complete'), effects)
        for name in g._PERMISSIONS: self.assertIs(getattr(result, name), False)
        payloads = (result.completed, result.not_submitted, result.rejected, result.unresolved)
        self.assertEqual(sum(p is not None for p in payloads), 1)
        payload = next(p for p in payloads if p is not None)
        self.assertEqual(payload.reconciliation_required, result.state is not S.COMPLETED)
        self.assertLessEqual(self.calls.count('verify'), 1)
        self.assertLessEqual(self.calls.count('qualify'), 1)
        self.assertEqual(self.calls.count('verify'), int(bool(flags[0])))
        self.assertEqual(self.calls.count('qualify'), int(bool(flags[3])))
        return payload

    def test_confirmed(self):
        payload = self.check(self.run_g(), R.COMPLETED, (1,1,1,1,1), 1)
        self.assertIs(payload.disposition.required_gate, o.RequiredGate.CURRENT_DELIVERY_QUALIFICATION)
        self.assertEqual(self.calls, ['verify', 'complete', 'qualify'])
        self.assertEqual(payload.request.operation.permit,
            self.source.published.qualification.publication.candidate.operation.permit)
        self.assertIs(payload.request.operation.kind, s.OperationKind.PERMIT_COMPLETION)
        self.assertIs(payload.entry_decision, g.EntryDecision.ENTERED_NOW)
        self.assertIs(self.owner._state, g._EntryState.ENTERED)

    def test_missing_composition(self):
        self.check(g.CheckpointCompleter().complete_original(self.source),
            R.COMPOSITION_UNAVAILABLE, (0,0,0,0,0))

    def test_structural_invalid(self):
        self.source = object()
        self.check(self.run_g(), R.INVALID_F_SOURCE, (0,0,0,0,0))

    def function_state_failure(self):
        self.assertFalse(g._composition_stable(self.completer))
        result = self.completer.complete_original(None)
        payload = self.check(result, R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        self.assertFalse(payload.owner_entry_attempted)
        self.assertEqual(self.calls, [])
        self.assertIs(self.owner._state, g._EntryState.PENDING)

    def test_issue_state_control(self):
        self.assertTrue(g._composition_stable(self.completer))
        self.check(self.completer.complete_original(None), R.INVALID_F_SOURCE, (0,0,0,0,0))
        self.assertEqual(self.calls, [])
        self.assertIs(self.owner._state, g._EntryState.PENDING)

    def test_issue_state_positional_defaults(self):
        original, calls = g._issue.__defaults__, []
        class Hostile:
            def __bool__(self): calls.append('bool'); raise AssertionError('default used')
        try:
            g._issue.__defaults__ = (Hostile(),)
            self.function_state_failure()
            # Even identical contained values do not authorize a new container.
            g._issue.__defaults__ = tuple(list(original))
            self.assertIsNot(g._issue.__defaults__, original)
            self.function_state_failure()
        finally: g._issue.__defaults__ = original
        self.assertEqual(calls, [])

    def test_issue_state_keyword_replacement(self):
        original = g._issue.__kwdefaults__
        try:
            g._issue.__kwdefaults__ = dict(original)
            self.assertIsNot(g._issue.__kwdefaults__, original)
            self.function_state_failure()
        finally: g._issue.__kwdefaults__ = original

    def test_issue_state_keyword_inplace_and_count(self):
        mapping, calls = g._issue.__kwdefaults__, []
        entries = tuple(mapping.items())
        key = next(key for key, _ in entries if key == 'source')
        hostile = self.hostile_key(key, calls)
        for mode in ('value', 'add', 'remove', 'foreign_key'):
            with self.subTest(mode=mode):
                try:
                    if mode == 'value': mapping[key] = object()
                    elif mode == 'add': mapping['unexpected_default'] = None
                    elif mode == 'remove': del mapping[key]
                    else:
                        del mapping[key]; mapping[hostile] = None
                    calls.clear()
                    self.assertIs(g._issue.__kwdefaults__, mapping)
                    self.function_state_failure()
                    self.assertEqual(calls, [])
                finally:
                    mapping.clear(); mapping.update(entries)

    def initializer_closure_failure(self, cls):
        initializer, calls = cls.__init__, []
        index = initializer.__code__.co_freevars.index('__dataclass_builtins_object__')
        cell = initializer.__closure__[index]
        original = cell.cell_contents
        class Hostile:
            @staticmethod
            def __setattr__(*args):
                calls.append('setter'); raise AssertionError('changed initializer closure used')
        try:
            cell.cell_contents = Hostile
            self.function_state_failure()
        finally: cell.cell_contents = original
        self.assertEqual(calls, [])

    def test_issue_state_payload_closure(self):
        self.initializer_closure_failure(g._CompletionPayload)

    def test_issue_state_request_closure(self):
        self.initializer_closure_failure(g.CompletionRequest)

    def test_issue_state_observation_closure(self):
        self.initializer_closure_failure(g.CompletionObservation)

    def initializer_empty_failure(self, cls):
        initializer, calls = cls.__init__, []
        index = initializer.__code__.co_freevars.index('__dataclass_builtins_object__')
        cell, code = initializer.__closure__[index], initializer.__code__
        original, previous_profile = cell.cell_contents, sys.getprofile()
        def observe(frame, event, arg):
            if event == 'call' and frame.f_code is code: calls.append('initializer')
        try:
            del cell.cell_contents
            with self.assertRaisesRegex(ValueError, '^Cell is empty$'):
                g.types.GetSetDescriptorType.__get__(g.types.CellType.__dict__['cell_contents'],
                    cell, g.types.CellType)
            sys.setprofile(observe)
            self.function_state_failure()
        finally:
            sys.setprofile(previous_profile)
            cell.cell_contents = original
        self.assertIs(cell.cell_contents, original)
        self.assertEqual(calls, [])

    def test_issue_state_payload_closure_empty(self):
        self.initializer_empty_failure(g._CompletionPayload)

    def test_issue_state_request_closure_empty(self):
        self.initializer_empty_failure(g.CompletionRequest)

    def test_issue_state_observation_closure_empty(self):
        self.initializer_empty_failure(g.CompletionObservation)

    def test_issue_state_callback_observation_closure_empty(self):
        initializer, calls = g.CompletionObservation.__init__, []
        index = initializer.__code__.co_freevars.index('__dataclass_builtins_object__')
        cell, code = initializer.__closure__[index], initializer.__code__
        original, previous_profile = cell.cell_contents, sys.getprofile()
        def observe(frame, event, arg):
            if event == 'call' and frame.f_code is code: calls.append('initializer')
        def mutate(*args):
            del cell.cell_contents
            with self.assertRaisesRegex(ValueError, '^Cell is empty$'):
                g.types.GetSetDescriptorType.__get__(g.types.CellType.__dict__['cell_contents'],
                    cell, g.types.CellType)
            sys.setprofile(observe)
        self.complete_hook = mutate
        try: result = self.run_g()
        finally:
            sys.setprofile(previous_profile)
            cell.cell_contents = original
        self.assertIs(cell.cell_contents, original)
        payload = self.check(result, R.DEPENDENCY_INSTABILITY, (1,1,1,0,0), 1)
        self.assertTrue(payload.owner_entry_attempted)
        self.assertIs(payload.entry_decision, g.EntryDecision.ENTERED_NOW)
        self.assertIsNotNone(payload.source)
        self.assertIsNotNone(payload.request)
        self.assertIsNotNone(payload.eligibility)
        self.assertIsNone(payload.observation)
        self.assertIsNone(payload.qualification)
        self.assertIsNone(payload.canonical_observation)
        self.assertIsNone(payload.disposition)
        self.assertEqual(self.calls, ['verify', 'complete'])
        self.assertEqual(calls, [])
        self.assertIs(self.owner._state, g._EntryState.ENTERED)

    def test_issue_state_callback_observation_closure(self):
        initializer, calls = g.CompletionObservation.__init__, []
        index = initializer.__code__.co_freevars.index('__dataclass_builtins_object__')
        cell = initializer.__closure__[index]
        original = cell.cell_contents
        class Hostile:
            @staticmethod
            def __setattr__(*args):
                calls.append('setter'); raise AssertionError('changed observation constructor used')
        def mutate(*args): cell.cell_contents = Hostile
        self.complete_hook = mutate
        try: result = self.run_g()
        finally: cell.cell_contents = original
        payload = self.check(result, R.DEPENDENCY_INSTABILITY, (1,1,1,0,0), 1)
        self.assertIsNotNone(payload.source)
        self.assertIsNotNone(payload.request)
        self.assertIsNotNone(payload.eligibility)
        self.assertIsNone(payload.observation)
        self.assertIsNone(payload.qualification)
        self.assertIsNone(payload.canonical_observation)
        self.assertEqual(self.calls, ['verify', 'complete'])
        self.assertEqual(calls, [])
        self.assertIs(self.owner._state, g._EntryState.ENTERED)

    def test_shared_owner_across_evaluators(self):
        self.run_g()
        self.calls.clear()
        other = g.CheckpointCompleter(self.adapter, owner=self.owner)
        self.check(other.complete_original(g._copy(self.source)), R.COMPLETION_ALREADY_ENTERED,
            (1,1,0,0,0))

    def test_owner_has_exact_slots_no_reset_or_copy(self):
        self.assertEqual(g._CompletionEntryOwner.__slots__, ('_binding', '_lock', '_state'))
        for action in (copy.copy, copy.deepcopy):
            with self.assertRaises(TypeError): action(self.owner)
        with self.assertRaises(TypeError): self.owner._state = g._EntryState.PENDING
        with self.assertRaises(TypeError):
            self.owner.__init__(self.source, authority=self.authority, implementation=self.implementation)
        with self.assertRaises(TypeError):
            type('ForeignOwner', (g._CompletionEntryOwner,), {})

    def test_result_closed_and_fresh_entry_failures(self):
        with patch.object(g, '_source', lambda value: None):
            first = self.run_g()
            object.__setattr__(first, 'state', S.COMPLETED)
            second = self.run_g()
        self.assertIsNot(first, second)
        self.check(second, R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        with self.assertRaises(TypeError): bool(second)
        with self.assertRaises(TypeError): g.CompletionResult()
        with self.assertRaises(TypeError): copy.copy(second)
        with self.assertRaises(TypeError): copy.deepcopy(second)
        with self.assertRaises(TypeError): replace(second, reason=R.COMPLETED)
        with self.assertRaises(TypeError): type('ForeignResult', (g.CompletionResult,), {})

    def test_bootstrap_code_replacement_executes_zero(self):
        calls = []
        original = g._composition_stable.__code__
        # No closure may be transplanted into a function with a different layout.
        replacement = type(g._composition_stable)(compile(
            'def x(value):\n _test_bootstrap_calls.append(True)\n return True\n',
            '<replacement>', 'exec').co_consts[0], {})
        g._test_bootstrap_calls = calls
        try:
            g._composition_stable.__code__ = replacement.__code__
            self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        finally:
            g._composition_stable.__code__ = original
            del g._test_bootstrap_calls
        self.assertEqual(calls, [])

    def test_source_helper_replacement_zero_calls(self):
        calls = []
        def hostile(value): calls.append(True); raise AssertionError()
        with patch.object(g, '_source', hostile):
            self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        self.assertEqual(calls, [])

    def test_field_descriptor_replacement_zero_calls(self):
        calls = []
        def hostile(value): calls.append(True); raise AssertionError()
        with patch.object(f.PublicationResult, 'state', property(hostile), create=True):
            self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        self.assertEqual(calls, [])

    def test_illegal_graph_and_acyclic_aliases(self):
        for value in ([], {}, set(), frozenset(), bytearray(), memoryview(b''), iter(()), self.owner):
            with self.assertRaises(g._INVALID): g._project(value)
        reference = s.EvidenceReference('alias', b'a' * 32)
        detached = g._copy((reference, reference))
        self.assertIs(detached[0], detached[1])
        self.assertIsNot(detached[0], reference)
        cycle = object.__new__(g.CompletionObservation)
        object.__setattr__(cycle, 'request', cycle)
        with self.assertRaises(g._INVALID): g._project(cycle)

    def test_reason_and_permission_counts(self):
        self.assertEqual(len(tuple(g.CompletionReason)), 39)
        self.assertEqual(len(set(reason.value for reason in g.CompletionReason)), 39)
        self.assertEqual(len(g._PERMISSIONS), 20)
        self.assertEqual(tuple(reason for reason, _ in g._REASON_FLAGS), tuple(g.CompletionReason))
        self.assertEqual(len(g._LEGAL_FLAGS), 6)
        for reason in (R.ENTRY_INTERRUPTED, R.ENTRY_STATE_UNKNOWN, R.EVALUATION_INTERRUPTED):
            with self.assertRaises(g._INVALID): g._issue(reason)

    def test_nested_subclass_hooks_execute_zero(self):
        calls = []
        class Hostile(s.EvidenceReference):
            def __getattribute__(self, name): calls.append('get'); raise AssertionError()
            def __eq__(self, other): calls.append('eq'); raise AssertionError()
            def __hash__(self): calls.append('hash'); raise AssertionError()
            def __repr__(self): calls.append('repr'); raise AssertionError()
        reference = object.__new__(Hostile)
        object.__setattr__(reference, 'identity', 'hostile')
        object.__setattr__(reference, 'sha256', b'x' * 32)
        object.__setattr__(self.source.published.qualification.publication, 'evidence', reference)
        self.check(self.run_g(), R.INVALID_F_SOURCE, (0,0,0,0,0))
        self.assertEqual(calls, [])

    def test_shared_owner_across_adapter_instances(self):
        self.run_g()
        self.calls.clear()
        adapter = g.TrustedCompletionAdapter(self.authority, self.implementation,
            self.verify, self.complete, self.qualify)
        self.assertIsNot(adapter, self.adapter)
        completer = g.CheckpointCompleter(adapter, owner=self.owner)
        self.check(completer.complete_original(g._copy(self.source)),
            R.COMPLETION_ALREADY_ENTERED, (1,1,0,0,0))

    def test_owner_concurrent_transition_is_single(self):
        import threading
        barrier = threading.Barrier(3)
        results = []
        binding = self.owner._binding
        lock = self.owner._lock
        def worker():
            barrier.wait()
            results.append(self.owner.try_enter(binding, lock))
        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads: thread.start()
        barrier.wait()
        for thread in threads: thread.join()
        self.assertEqual(results.count(g.EntryDecision.ENTERED_NOW), 1)
        self.assertTrue(all(item in (g.EntryDecision.ENTERED_NOW, g.EntryDecision.ALREADY_ENTERED,
            g.EntryDecision.BUSY) for item in results))

    def test_qualifier_exception_retains_observation(self):
        error = RuntimeError('qualifier programming failure')
        self.qualify_error = error
        with self.assertRaises(g._CompletionEvaluationInterrupted) as raised: self.run_g()
        self.assertIs(raised.exception.__cause__, error)
        payload = self.check(raised.exception.result, R.EVALUATION_INTERRUPTED, (1,1,1,1,0), 1)
        self.assertIsNotNone(payload.eligibility)
        self.assertIsNotNone(payload.observation)
        self.assertIsNone(payload.qualification)
        self.assertIsNone(payload.disposition)

    def test_before_entry_programming_exception_propagates(self):
        error = AssertionError('verification programming failure')
        self.verify_error = error
        with self.assertRaises(AssertionError) as raised: self.run_g()
        self.assertIs(raised.exception, error)
        self.assertEqual(self.calls, ['verify'])

    def test_live_request_operation_is_independently_detached(self):
        class StopBeforeOwner(BaseException): pass
        sentinel = StopBeforeOwner('live request isolation inspected')
        observed = []
        def record_ids(root):
            seen, records, pending = set(), set(), [root]
            while pending:
                value = pending.pop()
                kind, identity = type(value), id(value)
                if identity in seen: continue
                seen.add(identity)
                if g._ATOM_IDS.get(id(kind)) is kind or id(kind) in g._ENUM_MEMBERS: continue
                if kind is tuple:
                    pending.extend(value)
                    continue
                schema = g._FIELD_TYPES[id(kind)]
                self.assertIs(schema[0], kind)
                records.add(identity)
                pending.extend(object.__getattribute__(value, name) for name, _ in schema[1])
            return records
        def inspect_request(request, owner):
            frame = sys._getframe(2).f_locals
            saved = frame['saved']
            publication = saved.published.qualification.publication
            saved_permit = publication.candidate.envelope.permit_reference
            self.assertIsNot(request.source, saved)
            self.assertIs(type(request.operation.permit), s.EvidenceReference)
            self.assertIsNot(request.operation.permit, saved_permit)
            shared = record_ids(saved) & record_ids(request)
            self.assertEqual(shared, set())
            self.assertTrue(g._same(request.operation.permit, saved_permit))
            self.assertTrue(g._same(request.operation, g._operation(saved)))
            self.assertIs(request.operation.kind, s.OperationKind.PERMIT_COMPLETION)
            self.assertTrue(g._same(request.source, saved))
            self.assertTrue(g._same(request.publication, publication))
            self.assertTrue(g._same(request.operation.permit, request.publication.candidate.operation.permit))
            self.assertTrue(g._same(request.owner_binding.operation, request.operation))
            s.verify_publication_result(publication.candidate, request.publication)
            self.assertIs(owner, self.owner)
            self.assertTrue(frame['verified'])
            for flag in ('attempted', 'consumed', 'invoked', 'qualified', 'evaluated'):
                self.assertFalse(frame[flag])
            self.impl02_evidence = dict(permit_alias=False, shared_nonatom_records=len(shared),
                canonical_equal=True, owner_entry_attempted=frame['attempted'])
            observed.append(True)
            raise sentinel
        self.verify_hook = inspect_request
        with self.assertRaises(StopBeforeOwner) as raised: self.run_g()
        self.assertIs(raised.exception, sentinel)
        self.assertEqual(observed, [True])
        self.assertEqual(self.calls, ['verify'])
        self.assertEqual(self.calls.count('verify'), 1)
        self.assertEqual(self.calls.count('complete'), 0)
        self.assertEqual(self.calls.count('qualify'), 0)
        self.assertIs(self.owner._state, g._EntryState.PENDING)

    def test_same_original_operation_and_publication_unchanged(self):
        before = g._project(self.source)
        self.run_g()
        self.assertTrue(g._equal(before, g._project(self.source)))

    def owner_fault(self, mode):
        import inspect
        source, first = inspect.getsourcelines(g._CompletionEntryOwner.try_enter)
        marker = ('_MEMBER_SET' if mode in ('pending', 'release_pending')
            else 'return EntryDecision.ENTERED_NOW'
            if mode in ('entered', 'unknown', 'missing', 'illegal', 'hostile')
            else '_LOCK_RELEASE(expected_lock)')
        line = first + next(index for index, text in enumerate(source) if marker in text)
        error = RuntimeError('owner fault ' + mode)
        code = g._CompletionEntryOwner.try_enter.__code__
        fired = []
        saved_get = g._MEMBER_GET
        saved_slot = g._CompletionEntryOwner.__dict__['_state']
        hostile_calls = []
        def hostile(value): hostile_calls.append(True); raise AssertionError('hostile state getter')
        def trace(frame, event, arg):
            if frame.f_code is code and event == 'line' and frame.f_lineno == line and not fired:
                fired.append(True)
                if mode == 'unknown': g._MEMBER_GET = lambda *args: None
                if mode == 'missing': object.__delattr__(self.owner, '_state')
                if mode == 'illegal': object.__setattr__(self.owner, '_state', object())
                if mode == 'hostile': g._CompletionEntryOwner._state = property(hostile)
                if mode.startswith('release'):
                    g._LOCK_RELEASE(self.owner._lock)
                    if mode == 'release_unknown': object.__delattr__(self.owner, '_state')
                    if mode == 'release_pending': raise error
                else: raise error
            return trace if frame.f_code is code else None
        try:
            sys.settrace(trace)
            try:
                self.run_g()
            except BaseException as raised:
                return raised, error, fired
        finally:
            sys.settrace(None)
            g._MEMBER_GET = saved_get
            g._CompletionEntryOwner._state = saved_slot
            self.assertEqual(hostile_calls, [])
        self.fail('owner fault did not interrupt')

    def test_owner_safe_pending_original_exception(self):
        raised, original, fired = self.owner_fault('pending')
        self.assertEqual(len(fired), 1)
        self.assertIs(raised, original)
        self.assertEqual(self.calls, ['verify'])
        self.assertIs(self.owner._state, g._EntryState.PENDING)

    def test_owner_safe_entered_carrier(self):
        raised, original, fired = self.owner_fault('entered')
        self.assertEqual(len(fired), 1)
        self.assertIsInstance(raised, g._CompletionEvaluationInterrupted)
        self.assertIs(raised.__cause__, original)
        self.check(raised.result, R.ENTRY_INTERRUPTED, (1,1,0,0,0))
        self.assertIs(self.owner._state, g._EntryState.ENTERED)

    def test_owner_emergency_dependency_unknown(self):
        raised, original, fired = self.owner_fault('unknown')
        self.assertEqual(len(fired), 1)
        self.assertIsInstance(raised, g._CompletionEvaluationInterrupted)
        self.assertIs(raised.__cause__, original)
        self.check(raised.result, R.ENTRY_STATE_UNKNOWN, (1,0,0,0,0))

    def test_native_release_failure_safe_entered(self):
        raised, _, fired = self.owner_fault('release_entered')
        self.assertEqual(len(fired), 1)
        self.assertIsInstance(raised, g._CompletionEvaluationInterrupted)
        self.assertIsInstance(raised.__cause__, RuntimeError)
        self.check(raised.result, R.ENTRY_INTERRUPTED, (1,1,0,0,0))

    def test_native_release_failure_unknown_state(self):
        raised, _, fired = self.owner_fault('release_unknown')
        self.assertEqual(len(fired), 1)
        self.assertIsInstance(raised, g._CompletionEvaluationInterrupted)
        self.assertIsInstance(raised.__cause__, RuntimeError)
        self.check(raised.result, R.ENTRY_STATE_UNKNOWN, (1,0,0,0,0))

    def test_native_state_getter_failure_keeps_original_cause(self):
        raised, original, _ = self.owner_fault('missing')
        self.assertIs(raised.__cause__, original)
        self.check(raised.result, R.ENTRY_STATE_UNKNOWN, (1,0,0,0,0))

    def test_illegal_state_is_not_pending(self):
        raised, original, _ = self.owner_fault('illegal')
        self.assertIs(raised.__cause__, original)
        self.check(raised.result, R.ENTRY_STATE_UNKNOWN, (1,0,0,0,0))

    def test_changed_slot_hostile_getter_executes_zero(self):
        raised, original, _ = self.owner_fault('hostile')
        self.assertIs(raised.__cause__, original)
        self.check(raised.result, R.ENTRY_STATE_UNKNOWN, (1,0,0,0,0))

    def test_defensive_release_failure_safe_pending(self):
        raised, original, _ = self.owner_fault('release_pending')
        self.assertIs(type(raised), RuntimeError)
        self.assertIs(raised.__context__, original)
        self.assertIs(self.owner._state, g._EntryState.PENDING)
        self.assertNotIn('complete', self.calls)

    def test_root_not_submitted(self):
        self.source = f._issue(f.S.NOT_SUBMITTED, f.R.INVALID_E_SOURCE)
        self.check(self.run_g(), R.F_NOT_PUBLISHED, (0,0,0,0,0))

    def test_root_unresolved(self):
        self.source = f._issue(f.S.UNRESOLVED, f.R.DEPENDENCY_INSTABILITY)
        self.check(self.run_g(), R.F_UNRESOLVED, (0,0,0,0,0))

    def test_root_definitely_rejected_is_not_published(self):
        payload = self.source.published
        publication = s.PublicationResult(s.ExternalOutcome.DEFINITELY_REJECTED,
            f._copy(payload.qualification.publication.candidate), self.reference)
        qualification = replace(payload.qualification,
            disposition=f.PublicationDispositionKind.DEFINITELY_REJECTED, publication=publication)
        disposition = o.publication_disposition(publication.candidate, publication,
            local_commit=o.LocalCommitState.CONFIRMED, qualification=V.VALID)
        self.source = f._issue(f.S.DEFINITELY_REJECTED, f.R.EXTERNAL_DEFINITELY_REJECTED,
            source=payload.source, dispatch=payload.dispatch, observation=payload.observation,
            qualification=qualification, disposition=disposition,
            verified=True, evaluated=True, invoked=True, qualified=True)
        self.check(self.run_g(), R.F_NOT_PUBLISHED, (0,0,0,0,0))

    def test_progression_block_precedes_remaining_positive_checks(self):
        object.__setattr__(self.source.published, 'reconciliation_required', True)
        self.check(self.run_g(), R.PROGRESSION_PROHIBITED, (0,0,0,0,0))

    def test_remaining_positive_inconsistency_is_invalid(self):
        object.__setattr__(self.source.published.dispatch, 'decision', f.DispatchDecision.INELIGIBLE)
        self.check(self.run_g(), R.INVALID_F_SOURCE, (0,0,0,0,0))

    def test_eligibility_malformed(self):
        self.transform = lambda value: None
        self.check(self.run_g(), R.ELIGIBILITY_MALFORMED, (1,0,0,0,0))

    def test_eligibility_binding(self):
        self.transform = lambda value: replace(value, request=replace(value.request,
            evaluation_binding=object.__new__(g._EvaluationBinding)))
        self.check(self.run_g(), R.ELIGIBILITY_BINDING_MISMATCH, (1,0,0,0,0))

    def test_owner_busy(self):
        g._LOCK_ACQUIRE(self.owner._lock, False)
        try: self.check(self.run_g(), R.COMPETING_EXECUTION, (1,0,0,0,0))
        finally: g._LOCK_RELEASE(self.owner._lock)

    def test_owner_binding_mismatch_is_non_dispatch(self):
        import inspect
        _, start = inspect.getsourcelines(g._CompletionEntryOwner.try_enter)
        code, original = g._CompletionEntryOwner.try_enter.__code__, self.owner._binding
        substituted = g._copy(original)
        fired = []
        def trace(frame, event, arg):
            if frame.f_code is code and event == 'line' and frame.f_lineno == start + 1 and not fired:
                fired.append(True)
                object.__setattr__(self.owner, '_binding', substituted)
            return trace if frame.f_code is code else None
        try:
            sys.settrace(trace)
            self.check(self.run_g(), R.ELIGIBILITY_BINDING_MISMATCH, (1,0,0,0,0))
        finally:
            sys.settrace(None)
            object.__setattr__(self.owner, '_binding', original)
        self.assertEqual(fired, [True])
        self.assertIs(self.owner._state, g._EntryState.PENDING)

    def test_qualification_binding_mismatch(self):
        self.qualify_transform = lambda value: replace(value,
            authority=s.EvidenceReference('foreign', b'x' * 32))
        self.check(self.run_g(), R.QUALIFICATION_BINDING_MISMATCH, (1,1,1,1,0), 1)

    def test_qualification_malformed(self):
        self.qualify_transform = lambda value: replace(value, completion=None)
        self.check(self.run_g(), R.QUALIFICATION_MALFORMED, (1,1,1,1,0), 1)

    def test_source_mutation_not_hidden_by_detached_request(self):
        def mutate(request, owner):
            object.__setattr__(self.source.published, 'reconciliation_required', True)
        self.verify_hook = mutate
        self.check(self.run_g(), R.SOURCE_INSTABILITY, (1,0,0,0,0))

    def test_request_mutation(self):
        def mutate(request, owner):
            object.__setattr__(request, 'implementation', s.EvidenceReference('changed', b'x' * 32))
        self.verify_hook = mutate
        self.check(self.run_g(), R.REQUEST_INSTABILITY, (1,0,0,0,0))

    def test_dependency_change_during_verify(self):
        original = g._qualification
        def mutate(request, owner): g._qualification = lambda *args: None
        self.verify_hook = mutate
        try: self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (1,0,0,0,0))
        finally: g._qualification = original

    def test_dependency_change_during_completion(self):
        original = g._qualification
        def mutate(operation, publication): g._qualification = lambda *args: None
        self.complete_hook = mutate
        try: self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (1,1,1,0,0), 1)
        finally: g._qualification = original

    def test_dependency_change_during_qualification(self):
        original = g._source
        self.qualify_hook = lambda observation: setattr(g, '_source', lambda value: None)
        try: self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (1,1,1,1,0), 1)
        finally: g._source = original

    def test_dependency_change_after_owner_before_completion(self):
        code = g._CompletionEntryOwner.try_enter.__code__
        old = g._qualification
        def trace(frame, event, arg):
            if frame.f_code is code and event == 'return' and arg is g.EntryDecision.ENTERED_NOW:
                g._qualification = lambda *args: None
            return trace if frame.f_code is code else None
        try:
            sys.settrace(trace)
            self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (1,1,0,0,0))
        finally:
            sys.settrace(None)
            g._qualification = old

    def replace_emergency(self, identical=False):
        original = self.completer._emergency
        calls = []
        def replacement(*args):
            calls.append(True)
            raise AssertionError('replacement emergency dependency executed')
        elements = list(original)
        if not identical: elements[13] = replacement
        self.completer._emergency = tuple(elements)
        self.assertIsNot(self.completer._emergency, original)
        return calls

    def test_emergency_container_replacement_guard(self):
        self.assertTrue(g._composition_stable(self.completer))
        calls = self.replace_emergency()
        self.assertFalse(g._composition_stable(self.completer))
        self.assertEqual(calls, [])
        self.assertIs(self.owner._state, g._EntryState.PENDING)
        self.assertEqual(self.calls, [])

    def test_emergency_identical_elements_replacement(self):
        calls = self.replace_emergency(identical=True)
        self.assertFalse(g._composition_stable(self.completer))
        self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        self.assertEqual(calls, [])
        self.assertIs(self.owner._state, g._EntryState.PENDING)

    def test_emergency_replacement_before_evaluation(self):
        calls = self.replace_emergency()
        self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        self.assertEqual(calls, [])
        self.assertEqual(self.calls, [])
        self.assertIs(self.owner._state, g._EntryState.PENDING)

    def test_emergency_replacement_after_owner_consumption(self):
        code = g._CompletionEntryOwner.try_enter.__code__
        calls = []
        def trace(frame, event, arg):
            if frame.f_code is code and event == 'return' and arg is g.EntryDecision.ENTERED_NOW:
                calls.append(self.replace_emergency())
            return trace if frame.f_code is code else None
        try:
            sys.settrace(trace)
            self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (1,1,0,0,0))
        finally: sys.settrace(None)
        self.assertEqual(calls, [[]])
        self.assertEqual(self.calls, ['verify'])
        self.assertIs(self.owner._state, g._EntryState.ENTERED)

    def test_emergency_replacement_during_owner_exception(self):
        import inspect
        lines, first = inspect.getsourcelines(g._CompletionEntryOwner.try_enter)
        line = first + next(i for i, text in enumerate(lines)
            if 'return EntryDecision.ENTERED_NOW' in text)
        code = g._CompletionEntryOwner.try_enter.__code__
        original = RuntimeError('owner interrupted after emergency replacement')
        calls = []
        def trace(frame, event, arg):
            if frame.f_code is code and event == 'line' and frame.f_lineno == line:
                calls.append(self.replace_emergency())
                raise original
            return trace if frame.f_code is code else None
        try:
            sys.settrace(trace)
            with self.assertRaises(g._CompletionEvaluationInterrupted) as raised: self.run_g()
        finally: sys.settrace(None)
        self.assertIs(raised.exception.__cause__, original)
        self.check(raised.exception.result, R.ENTRY_INTERRUPTED, (1,1,0,0,0))
        self.assertEqual(calls, [[]])
        self.assertEqual(self.calls, ['verify'])

    def test_unexpected_after_consumption_before_completion(self):
        import inspect
        lines, start = inspect.getsourcelines(g.CheckpointCompleter.complete_original)
        line = start + next(index for index, text in enumerate(lines)
            if 'latest = entered_floor' in text) + 2
        code = g.CheckpointCompleter.complete_original.__code__
        original = RuntimeError('post-owner interruption')
        def trace(frame, event, arg):
            if frame.f_code is code and event == 'line' and frame.f_lineno == line: raise original
            return trace if frame.f_code is code else None
        try:
            sys.settrace(trace)
            with self.assertRaises(g._CompletionEvaluationInterrupted) as raised: self.run_g()
        finally: sys.settrace(None)
        self.assertIs(raised.exception.__cause__, original)
        self.check(raised.exception.result, R.ENTRY_INTERRUPTED, (1,1,0,0,0))

    def test_dependency_change_after_canonical_entry(self):
        old = g._qualification
        canonical = o.completion_disposition
        def mutate(*args, **kwargs):
            result = canonical(*args, **kwargs)
            g._qualification = lambda *args: None
            return result
        with patch.object(o, 'completion_disposition', mutate):
            completer = g.CheckpointCompleter(self.adapter, owner=self.owner)
            try: self.check(completer.complete_original(self.source),
                R.DEPENDENCY_INSTABILITY, (1,1,1,1,1), 1)
            finally: g._qualification = old

    def test_returned_response_mutation(self):
        raw = []
        def remember(operation, publication):
            result = s.CompletionResult(s.ExternalOutcome.CONFIRMED, operation, publication, self.reference)
            raw.append(result)
            self.raw_override, self.raw_value = True, result
        self.complete_hook = remember
        self.qualify_hook = lambda observation: object.__setattr__(raw[0], 'evidence',
            s.EvidenceReference('changed', b'x' * 32))
        self.check(self.run_g(), R.RESPONSE_INSTABILITY, (1,1,1,1,0), 1)

    def test_canonical_output_mutation(self):
        canonical, copier, raw = o.completion_disposition, g._copy, []
        def remember(*args, **kwargs):
            result = canonical(*args, **kwargs)
            raw.append(result)
            return result
        def enrich(value):
            result = copier(value)
            if raw and type(value) is g.CompletionResult:
                object.__setattr__(raw[0], 'completion_problem', o.Reason.MALFORMED)
            return result
        with patch.object(o, 'completion_disposition', remember), patch.object(g, '_copy', enrich):
            completer = g.CheckpointCompleter(self.adapter, owner=self.owner)
            payload = self.check(completer.complete_original(self.source),
                R.DISPOSITION_INSTABILITY, (1,1,1,1,1), 1)
        self.assertIsNotNone(payload.disposition)

    def test_malformed_return_is_not_retained(self):
        self.raw_override, self.raw_value = True, object()
        self.outcome = s.ExternalOutcome.UNKNOWN
        payload = self.check(self.run_g(), R.COMPLETION_UNKNOWN, (1,1,1,1,1), 1)
        self.assertIs(payload.observation.kind, g.CompletionObservationKind.MALFORMED_RETURN)
        self.assertIsNone(payload.observation.returned)

    def test_unbound_return_is_not_retained(self):
        publication = replace(self.source.published.qualification.publication,
            evidence=s.EvidenceReference('foreign publication evidence', b'x' * 32))
        self.raw_override = True
        self.raw_value = s.CompletionResult(s.ExternalOutcome.UNKNOWN,
            g._operation(self.source), publication, None)
        self.outcome = s.ExternalOutcome.UNKNOWN
        payload = self.check(self.run_g(), R.COMPLETION_UNKNOWN, (1,1,1,1,1), 1)
        self.assertIs(payload.observation.kind, g.CompletionObservationKind.UNBOUND_RETURN)
        self.assertIsNone(payload.observation.returned)

    def test_effect_argument_mutation(self):
        def mutate(operation, publication):
            self.raw_value = s.CompletionResult(self.outcome, g._copy(operation),
                g._copy(publication), self.reference)
            self.raw_override = True
            object.__setattr__(operation, 'permit', s.EvidenceReference('changed', b'x' * 32))
        self.complete_hook = mutate
        self.check(self.run_g(), R.EFFECT_EVIDENCE_INSTABILITY, (1,1,1,0,0), 1)
        self.assertNotIn('qualify', self.calls)
        self.assertIs(self.owner._state, g._EntryState.ENTERED)

    def hostile_key(self, key, calls):
        collision = hash(key)
        class Hostile:
            def __hash__(self): calls.append('hash'); return collision
            def __eq__(self, other): calls.append('eq'); return False
            def __str__(self): calls.append('str'); raise AssertionError('foreign str')
            def __repr__(self): calls.append('repr'); raise AssertionError('foreign repr')
        return Hostile()

    def test_hold_hostile_protected_table(self):
        mapping = g._FIELD_TYPES
        original = dict(mapping)
        key = next(iter(mapping))
        calls = []
        hostile = self.hostile_key(key, calls)
        value = mapping.pop(key)
        mapping[hostile] = value
        calls.clear()
        try: result = self.run_g()
        finally:
            mapping.clear(); mapping.update(original)
        self.assertEqual(calls, [])
        self.check(result, R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        self.assertEqual(self.calls, [])
        self.assertIs(self.owner._state, g._EntryState.PENDING)

    def test_hold_hostile_module_binding(self):
        mapping = vars(g)
        key = next(key for key in mapping if key == '_operation')
        calls = []
        hostile = self.hostile_key(key, calls)
        value = mapping.pop(key)
        mapping[hostile] = value
        calls.clear()
        try: result = self.run_g()
        finally:
            recorded = list(calls)
            del mapping[hostile]; mapping[key] = value
        self.assertEqual(recorded, [])
        self.check(result, R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        self.assertEqual(self.calls, [])
        self.assertIs(self.owner._state, g._EntryState.PENDING)

    def test_hold_hostile_class_and_descriptor_views(self):
        # Native class dictionaries admit only string attribute names. A native
        # mappingproxy over a corrupted backing dictionary exercises the same
        # prepared-view read without invoking a key hook during validation.
        key = 'present-none'
        self.assertIs(g._identity_lookup({key: None}, key), None)
        self.assertIsNot(g._identity_lookup({}, key), None)
        for family in ('binding', 'descriptor', 'adapter'):
            with self.subTest(family=family):
                calls = []
                if family == 'binding':
                    index, row = next((i, row) for i, row in enumerate(self.completer._binding_reads)
                        if type(row[1]) is g.types.MappingProxyType and row[3] is not None)
                    _, view, key, value = row
                else:
                    attr = '_descriptors' if family == 'descriptor' else '_adapter_views'
                    view, entries = getattr(self.completer, attr)[0]
                    key, value = entries[0]
                backing = dict(view)
                del backing[key]
                hostile = self.hostile_key(key, calls)
                backing[hostile] = value
                proxy = g.types.MappingProxyType(backing)
                calls.clear()
                if family == 'binding':
                    original = self.completer._binding_reads
                    changed = list(original); changed[index] = (g._identity_lookup, proxy, key, value)
                    self.completer._binding_reads = tuple(changed)
                else:
                    original = getattr(self.completer, attr)
                    setattr(self.completer, attr, ((proxy, entries),) + original[1:])
                try: result = self.run_g()
                finally:
                    if family == 'binding': self.completer._binding_reads = original
                    else: setattr(self.completer, attr, original)
                self.assertEqual(calls, [])
                self.check(result, R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
                self.assertEqual(self.calls, [])
                self.assertIs(self.owner._state, g._EntryState.PENDING)

    def test_hold_hostile_emergency_binding(self):
        original_enter = g._CompletionEntryOwner.try_enter
        original_error = RuntimeError('owner fault with corrupted emergency binding')
        mapping, calls = vars(g), []
        key = next(key for key in mapping if key == '_MEMBER_GET')
        value = mapping[key]
        hostile = self.hostile_key(key, calls)
        def enter(owner, binding, lock):
            original_enter(owner, binding, lock)
            del mapping[key]; mapping[hostile] = value
            calls.clear()
            raise original_error
        try:
            with patch.object(g._CompletionEntryOwner, 'try_enter', enter):
                completer = g.CheckpointCompleter(self.adapter, owner=self.owner)
                with self.assertRaises(g._CompletionEvaluationInterrupted) as raised:
                    completer.complete_original(self.source)
        finally:
            recorded = list(calls)
            if key not in mapping:
                del mapping[hostile]; mapping[key] = value
        self.assertEqual(recorded, [])
        self.assertIs(raised.exception.__cause__, original_error)
        self.check(raised.exception.result, R.ENTRY_STATE_UNKNOWN, (1,0,0,0,0))
        self.assertEqual(self.calls, ['verify'])

    def test_hold_prebootstrap_failure_descriptors(self):
        calls = []
        def getter(value): calls.append('get'); raise AssertionError('replaced getter')
        def setter(value, replacement): calls.append('set'); raise AssertionError('replaced setter')
        with patch.object(g.CompletionResult, 'state', property(getter), create=True), \
                patch.object(g._CompletionPayload, 'source', property(getter, setter), create=True):
            first = self.run_g()
            second = self.run_g()
        self.assertIsNot(first, second)
        self.assertIsNot(first.unresolved, second.unresolved)
        self.check(first, R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        self.check(second, R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        self.assertEqual(calls, [])
        self.assertEqual(self.calls, [])
        self.assertIs(self.owner._state, g._EntryState.PENDING)

    def failure_descriptor_mutation(self, stage):
        calls, patches = [], []
        def getter(value): calls.append('get'); raise AssertionError('replaced getter')
        def setter(value, replacement): calls.append('set'); raise AssertionError('replaced setter')
        def mutate(*args):
            for cls, name, descriptor in ((g.CompletionResult, 'state', property(getter)),
                    (g._CompletionPayload, 'source', property(getter, setter))):
                replacement = patch.object(cls, name, descriptor, create=True)
                replacement.start(); patches.append(replacement)
        setattr(self, stage + '_hook', mutate)
        try: result = self.run_g()
        finally:
            for replacement in reversed(patches): replacement.stop()
        flags = (1,0,0,0,0) if stage == 'verify' else (1,1,1,0,0)
        payload = self.check(result, R.DEPENDENCY_INSTABILITY, flags, int(stage == 'complete'))
        self.assertIsNotNone(payload.source)
        self.assertIsNotNone(payload.request)
        if stage == 'complete': self.assertIsNotNone(payload.eligibility)
        self.assertEqual(calls, [])

    def test_hold_callback_failure_descriptors(self): self.failure_descriptor_mutation('verify')
    def test_hold_postentry_failure_descriptors(self): self.failure_descriptor_mutation('complete')

    def test_hold_preentry_carrier_dependencies(self):
        calls = []
        def hostile(*args): calls.append(True); raise AssertionError('changed carrier machinery')
        carrier = g._CompletionEvaluationInterrupted
        for name, value in (('__new__', staticmethod(hostile)), ('__init__', hostile),
                ('result', property(hostile, hostile))):
            with self.subTest(name=name):
                with patch.object(carrier, name, value, create=True): result = self.run_g()
                self.check(result, R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        original_code = carrier.__init__.__code__
        def changed_init(self, result):
            if carrier is not None: raise AssertionError('changed init code')
        replacement_code = changed_init.__code__
        try:
            carrier.__init__.__code__ = replacement_code
            result = self.run_g()
        finally: carrier.__init__.__code__ = original_code
        self.check(result, R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        self.assertEqual(calls, [])
        self.assertEqual(self.calls, [])
        self.assertIs(self.owner._state, g._EntryState.PENDING)

    def carrier_mutation_interruption(self, stage):
        carrier, hooks, patches = g._CompletionEvaluationInterrupted, [], []
        original_error = RuntimeError('interruption after carrier mutation: ' + stage)
        def hostile(*args): hooks.append(True); raise TypeError('changed carrier machinery')
        def interrupt(*args, **kwargs):
            for name, value in (('__new__', staticmethod(hostile)), ('__init__', hostile),
                    ('result', property(hostile, hostile))):
                replacement = patch.object(carrier, name, value, create=True)
                replacement.start(); patches.append(replacement)
            raise original_error
        try:
            if stage == 'canonical':
                with patch.object(o, 'completion_disposition', interrupt):
                    completer = g.CheckpointCompleter(self.adapter, owner=self.owner)
                    with self.assertRaises(carrier) as raised: completer.complete_original(self.source)
            else:
                setattr(self, stage + '_hook', interrupt)
                with self.assertRaises(carrier) as raised: self.run_g()
            # Inspect native exception storage while the hostile result descriptor
            # is still installed: issuance/reporting must not need its getter.
            stored = BaseException.__dict__['__dict__'].__get__(raised.exception, carrier)['result']
        finally:
            for replacement in reversed(patches): replacement.stop()
        self.assertIs(type(raised.exception), carrier)
        self.assertIs(raised.exception.result, stored)
        self.assertIs(raised.exception.__cause__, original_error)
        flags = (1,1,1,stage != 'complete',stage == 'canonical')
        payload = self.check(stored, R.EVALUATION_INTERRUPTED, flags, 1)
        self.assertIsNotNone(payload.eligibility)
        if stage != 'complete': self.assertIsNotNone(payload.observation)
        if stage == 'canonical': self.assertIsNotNone(payload.qualification)
        self.assertIsNone(payload.disposition)
        self.assertEqual(hooks, [])
        self.assertIs(self.owner._state, g._EntryState.ENTERED)

    def test_hold_carrier_completion_interruption(self): self.carrier_mutation_interruption('complete')
    def test_hold_carrier_qualifier_interruption(self): self.carrier_mutation_interruption('qualify')
    def test_hold_carrier_canonical_interruption(self): self.carrier_mutation_interruption('canonical')

    def test_hold_carriers_fresh_per_evaluation(self):
        original_error = RuntimeError('safe pending; retain per-evaluation carriers')
        snapshots = []
        def enter(owner, binding, lock):
            frame = sys._getframe(1).f_locals
            snapshots.append(tuple(frame[name] for name in
                ('entry_carrier', 'unknown_carrier', 'evaluation_carrier')))
            raise original_error
        with patch.object(g._CompletionEntryOwner, 'try_enter', enter):
            completer = g.CheckpointCompleter(self.adapter, owner=self.owner)
            for _ in range(2):
                with self.assertRaises(RuntimeError) as raised: completer.complete_original(self.source)
                self.assertIs(raised.exception, original_error)
        self.assertEqual(len(snapshots), 2)
        for a in snapshots[0]:
            for b in snapshots[1]: self.assertIsNot(a, b)
        self.assertEqual(len({id(value) for group in snapshots for value in group}), 6)
        self.assertEqual(self.calls, ['verify', 'verify'])
        self.assertIs(self.owner._state, g._EntryState.PENDING)

    def test_replaced_native_descriptor_rejected_before_entry(self):
        calls = []
        def hostile(*args): calls.append(True); raise AssertionError()
        with patch.object(g, '_LOCK_RELEASE', hostile):
            self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        self.assertEqual(calls, [])

    def test_owner_substitution_does_not_authenticate_restart(self):
        foreign = g._CompletionEntryOwner(self.source, authority=self.authority,
            implementation=self.implementation)
        other = g.CheckpointCompleter(self.adapter, owner=foreign)
        self.check(other.complete_original(self.source), R.F_PROVENANCE_INVALID, (1,0,0,0,0))

    def test_competing_findings_preserve_priority(self):
        self.transform = lambda value: replace(value, source_provenance=V.UNKNOWN,
            historical_evidence=V.INVALID, normal_progression=V.INVALID,
            continuity=g.ContinuityStatus.CONTRADICTORY)
        self.check(self.run_g(), R.F_PROVENANCE_UNKNOWN, (1,0,0,0,0))

    def test_bootstrap_snapshot_cannot_execute_changed_qualifier(self):
        original = g._copy
        qualifier = self.qualify.__func__
        old_code = qualifier.__code__
        body = compile('def changed(self, observation):\n raise AssertionError("changed qualifier ran")\n',
            '<changed qualifier>', 'exec').co_consts[0]
        def enrich(value):
            result = original(value)
            if type(value) is g.CompletionObservation:
                qualifier.__code__ = body
            return result
        # Compose with a fixed captured enrichment helper; mutation occurs during
        # normal allocation, after the prior check and before the next dependency.
        with patch.object(g, '_copy', enrich):
            completer = g.CheckpointCompleter(self.adapter, owner=self.owner)
            try:
                result = completer.complete_original(self.source)
                payload = self.check(result, R.DEPENDENCY_INSTABILITY, (1,1,1,0,0), 1)
                self.assertIsNotNone(payload.observation)
                self.assertIsNone(payload.qualification)
                self.assertNotIn('qualify', self.calls)
            finally: qualifier.__code__ = old_code

    def test_snapshot_cannot_execute_changed_canonical_disposition(self):
        original = g._copy
        canonical = o.completion_disposition
        old_code = canonical.__code__
        body = compile('def changed(*args, **kwargs):\n raise AssertionError("changed canonical ran")\n',
            '<changed canonical>', 'exec').co_consts[0]
        def enrich(value):
            result = original(value)
            if type(value) is s.CompletionResult:
                canonical.__code__ = body
            return result
        with patch.object(g, '_copy', enrich):
            completer = g.CheckpointCompleter(self.adapter, owner=self.owner)
            try:
                payload = self.check(completer.complete_original(self.source),
                    R.DEPENDENCY_INSTABILITY, (1,1,1,1,0), 1)
                self.assertIsNotNone(payload.qualification)
                self.assertIsNone(payload.canonical_observation)
                self.assertIsNone(payload.disposition)
            finally: canonical.__code__ = old_code

    def test_canonical_contradiction(self):
        with patch.object(o, 'completion_disposition', lambda *args, **kwargs: None):
            completer = g.CheckpointCompleter(self.adapter, owner=self.owner)
            self.check(completer.complete_original(self.source),
                R.CANONICAL_DISPOSITION_CONTRADICTION, (1,1,1,1,1), 1)

    def test_canonical_exception_retains_qualification(self):
        original = RuntimeError('canonical interpretation failure')
        def explode(*args, **kwargs): raise original
        with patch.object(o, 'completion_disposition', explode):
            completer = g.CheckpointCompleter(self.adapter, owner=self.owner)
            with self.assertRaises(g._CompletionEvaluationInterrupted) as raised:
                completer.complete_original(self.source)
        self.assertIs(raised.exception.__cause__, original)
        payload = self.check(raised.exception.result, R.EVALUATION_INTERRUPTED, (1,1,1,1,1), 1)
        self.assertIsNotNone(payload.observation)
        self.assertIsNotNone(payload.qualification)
        self.assertIsNone(payload.disposition)

    def test_failed_enrichment_preserves_safe_recovery_handoff(self):
        issuer = g._issue
        original = MemoryError('snapshot enrichment failure')
        self.outcome = s.ExternalOutcome.UNKNOWN
        def enrich(*args, **kwargs):
            if kwargs.get('disposition') is not None: raise original
            return issuer(*args, **kwargs)
        with patch.object(g, '_issue', enrich):
            completer = g.CheckpointCompleter(self.adapter, owner=self.owner)
            with self.assertRaises(g._CompletionEvaluationInterrupted) as raised:
                completer.complete_original(self.source)
        self.assertIs(raised.exception.__cause__, original)
        payload = self.check(raised.exception.result, R.EVALUATION_INTERRUPTED, (1,1,1,1,1), 1)
        self.assertIsNotNone(payload.disposition)
        self.assertIsNotNone(payload.disposition.recovery)
        self.assertIsNotNone(payload.qualification)
        self.assertIsNotNone(payload.observation)


def unqualified_case(validity):
    def test(self):
        self.validity = validity
        payload = self.check(self.run_g(), R.QUALIFICATION_UNQUALIFIED, (1,1,1,1,1), 1)
        self.assertIsNotNone(payload.disposition)
        self.assertIsNone(payload.qualification.completion)
        self.assertIs(payload.disposition.required_gate, o.RequiredGate.RECOVERY_HANDOFF)
    setattr(CompletionTests, 'test_unqualified_' + validity.value, test)


for validity in (V.INVALID, V.UNKNOWN): unqualified_case(validity)


def interruption_case(stage, error_type):
    def test(self):
        error = error_type('synthetic interruption')
        setattr(self, stage + '_error', error)
        if stage == 'verify':
            with self.assertRaises(error_type) as raised: self.run_g()
            self.assertIs(raised.exception, error)
            self.assertNotIn('complete', self.calls)
        else:
            with self.assertRaises(g._CompletionEvaluationInterrupted) as raised: self.run_g()
            self.assertIs(raised.exception.__cause__, error)
            self.check(raised.exception.result, R.EVALUATION_INTERRUPTED,
                (1,1,1,stage == 'qualify',0), 1)
    setattr(CompletionTests, 'test_interruption_' + stage + '_' + error_type.__name__, test)


for stage in ('verify', 'complete', 'qualify'):
    for error_type in (AssertionError, RuntimeError, KeyboardInterrupt, SystemExit, MemoryError):
        interruption_case(stage, error_type)


def eligibility_case(name, changes, expected):
    def test(self):
        self.transform = lambda value: replace(value, **changes)
        self.check(self.run_g(), expected, (1,0,0,0,0))
    setattr(CompletionTests, 'test_eligibility_' + name, test)


for field, validity, reason in (
    ('validity', V.INVALID, R.ELIGIBILITY_UNQUALIFIED),
    ('validity', V.UNKNOWN, R.ELIGIBILITY_UNQUALIFIED),
    ('source_provenance', V.INVALID, R.F_PROVENANCE_INVALID),
    ('source_provenance', V.UNKNOWN, R.F_PROVENANCE_UNKNOWN),
    ('publication_confirmation', V.INVALID, R.PUBLICATION_UNQUALIFIED),
    ('publication_confirmation', V.UNKNOWN, R.PUBLICATION_UNQUALIFIED),
    ('historical_evidence', V.INVALID, R.HISTORICAL_EVIDENCE_CONTRADICTION),
    ('historical_evidence', V.UNKNOWN, R.HISTORICAL_EVIDENCE_UNQUALIFIED),
    ('completion_binding', V.INVALID, R.COMPLETION_BINDING_UNQUALIFIED),
    ('completion_binding', V.UNKNOWN, R.COMPLETION_BINDING_UNQUALIFIED),
    ('normal_progression', V.INVALID, R.PROGRESSION_PROHIBITED),
    ('normal_progression', V.UNKNOWN, R.PROGRESSION_UNKNOWN),
    ('continuity_qualification', V.INVALID, R.CONTINUITY_UNQUALIFIED),
    ('continuity_qualification', V.UNKNOWN, R.CONTINUITY_UNQUALIFIED),
): eligibility_case(field + '_' + validity.value, {field: validity}, reason)

for continuity, reason in (
    (g.ContinuityStatus.MISSING, R.CONTINUITY_UNQUALIFIED),
    (g.ContinuityStatus.LOST, R.CONTINUITY_LOST),
    (g.ContinuityStatus.EARLIER_ENTRY, R.COMPLETION_ALREADY_ENTERED),
    (g.ContinuityStatus.CLOSED, R.COMPLETION_ALREADY_CLOSED),
    (g.ContinuityStatus.COMPETING, R.COMPETING_EXECUTION),
    (g.ContinuityStatus.CONTRADICTORY, R.CONTINUITY_CONTRADICTION),
): eligibility_case(continuity.value, {'continuity': continuity}, reason)


def outcome_case(outcome):
    def test(self):
        self.outcome = outcome
        reason = {s.ExternalOutcome.CONFIRMED: R.COMPLETED,
            s.ExternalOutcome.DEFINITELY_REJECTED: R.EXTERNAL_DEFINITELY_REJECTED,
            s.ExternalOutcome.UNKNOWN: R.COMPLETION_UNKNOWN}[outcome]
        payload = self.check(self.run_g(), reason, (1,1,1,1,1), 1)
        self.assertIs(payload.observation.kind, g.CompletionObservationKind.RETURNED)
        self.assertIs(payload.observation.returned.outcome, outcome)
    setattr(CompletionTests, 'test_outcome_' + outcome.value, test)


for outcome in s.ExternalOutcome: outcome_case(outcome)


def availability_case(stage, error_type):
    def test(self):
        setattr(self, stage + '_error', error_type('synthetic availability'))
        if stage == 'complete': self.outcome = s.ExternalOutcome.UNKNOWN
        reason = {'verify': R.ELIGIBILITY_UNAVAILABLE, 'complete': R.COMPLETION_UNKNOWN,
            'qualify': R.QUALIFICATION_UNAVAILABLE}[stage]
        flags = {'verify': (1,0,0,0,0), 'complete': (1,1,1,1,1), 'qualify': (1,1,1,1,0)}[stage]
        payload = self.check(self.run_g(), reason, flags, 0 if stage == 'verify' else 1)
        if stage == 'complete':
            kind = (g.CompletionObservationKind.TIMEOUT if error_type is TimeoutError else
                g.CompletionObservationKind.CAPABILITY_UNAVAILABLE if error_type is s.CapabilityUnavailable
                else g.CompletionObservationKind.EXTERNAL_UNAVAILABLE)
            self.assertIs(payload.observation.kind, kind)
            self.assertIsNone(payload.observation.returned)
    setattr(CompletionTests, 'test_availability_' + stage + '_' + error_type.__name__, test)


for stage in ('verify', 'complete', 'qualify'):
    for error_type in g._AVAILABILITY:
        availability_case(stage, error_type)


def protocol_table_case(table, entry):
    def test(self):
        original = getattr(f.p, table)
        if entry:
            key = 'Command' if table == '_ENUMS' else f.p.Reference
            with patch.dict(original, {key: object()}):
                self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
        else:
            with patch.object(f.p, table, dict(original)):
                self.check(self.run_g(), R.DEPENDENCY_INSTABILITY, (0,0,0,0,0))
    setattr(CompletionTests, 'test_protocol_' + table + ('_entry' if entry else '_mapping'), test)


for table in ('_ENUMS', '_SCHEMAS'):
    for entry in (False, True): protocol_table_case(table, entry)


# Every numbered REV4 routing obligation is linked to an executable assertion.
# Continuation rows intentionally share the complete positive-path test.
ROUTING_ROWS = (
    'missing_composition', 'bootstrap_code_replacement_executes_zero', 'structural_invalid',
    'remaining_positive_inconsistency_is_invalid', 'root_not_submitted',
    'root_definitely_rejected_is_not_published', 'root_unresolved',
    'progression_block_precedes_remaining_positive_checks', 'availability_verify_CapabilityUnavailable',
    'eligibility_malformed', 'eligibility_binding', 'eligibility_validity_INVALID',
    'eligibility_validity_UNKNOWN', 'eligibility_source_provenance_INVALID',
    'eligibility_source_provenance_UNKNOWN', 'eligibility_publication_confirmation_INVALID',
    'eligibility_publication_confirmation_UNKNOWN', 'eligibility_historical_evidence_INVALID',
    'eligibility_historical_evidence_UNKNOWN', 'eligibility_completion_binding_INVALID',
    'eligibility_completion_binding_UNKNOWN', 'eligibility_normal_progression_INVALID',
    'eligibility_normal_progression_UNKNOWN', 'eligibility_MISSING', 'eligibility_LOST',
    'eligibility_EARLIER_ENTRY', 'eligibility_CLOSED', 'eligibility_COMPETING',
    'eligibility_CONTRADICTORY', 'confirmed', 'confirmed', 'shared_owner_across_evaluators',
    'owner_binding_mismatch_is_non_dispatch', 'owner_busy', 'owner_safe_pending_original_exception',
    'owner_safe_entered_carrier', 'owner_emergency_dependency_unknown',
    'native_release_failure_safe_entered', 'native_release_failure_unknown_state',
    'outcome_CONFIRMED', 'outcome_DEFINITELY_REJECTED', 'outcome_UNKNOWN',
    'availability_complete_TimeoutError', 'availability_complete_CapabilityUnavailable',
    'availability_complete_ExternalAvailabilityFailure', 'malformed_return_is_not_retained',
    'unbound_return_is_not_retained', 'availability_qualify_CapabilityUnavailable',
    'qualification_malformed', 'qualification_binding_mismatch', 'unqualified_INVALID',
    'unqualified_UNKNOWN', 'confirmed', 'outcome_DEFINITELY_REJECTED', 'outcome_UNKNOWN',
    'canonical_contradiction', 'dependency_change_during_verify',
    'dependency_change_after_owner_before_completion', 'dependency_change_during_completion',
    'dependency_change_during_qualification', 'dependency_change_after_canonical_entry',
    'before_entry_programming_exception_propagates', 'unexpected_after_consumption_before_completion',
    'interruption_complete_RuntimeError', 'source_mutation_not_hidden_by_detached_request',
    'request_mutation', 'returned_response_mutation', 'canonical_output_mutation',
    'effect_argument_mutation')


def test_routing_manifest(self):
    self.assertEqual(len(ROUTING_ROWS), 69)
    for name in ROUTING_ROWS:
        self.assertTrue(callable(getattr(CompletionTests, 'test_' + name)))


CompletionTests.test_all_69_routing_rows_have_executable_assertions = test_routing_manifest


if __name__ == '__main__': unittest.main()
