"""Increment C synthetic/offline provenance and non-effect boundary tests."""
import ast
from dataclasses import fields, replace
from hashlib import sha256
import importlib.util
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
fixture = runpy.run_path(str(ROOT / 'tests/test_fixture_lease_commands.py'))
commands, p, store = fixture['core'], fixture['p'], fixture['s']
name = fixture['PACKAGE'] + '.fixture_lease_candidate_preparation'
spec = importlib.util.spec_from_file_location(name,
    ROOT / 'services/api/infrastructure/fixture_lease_candidate_preparation.py')
c = importlib.util.module_from_spec(spec)
sys.modules[name] = c
spec.loader.exec_module(c)
s, cp = c.service, c.checkpoints


def clone(value):
    return c._detach(c._project(value))


def build_material():
    case = fixture['QualifiedWriterTests']('test_valid_consumption_windows_expire_before_t2')
    case.setUp()
    try:
        result = case.run_b()
        def rows(source, target):
            return tuple(p.decode_record(p.encode_record(commands._adapt(v, target)), target)
                         for v in case.store.read_rows(source))
        completions = rows(store.CommandRow, p.CommandRow)
        completion = next(v for v in completions if v.command_id == case.command.command_id)
        events = tuple(commands._event(v) for v in case.store.read_rows(store.EventRow)
                       if v.command_id == case.command.command_id)
        projection = p.StateProjection(rows(store.MetadataRow, p.MetadataRow)[0],
            rows(store.ReservationRow, p.ReservationRow), rows(store.ClaimRow, p.ClaimRow), completions)
        keys = tuple(v.canonical_key for v in projection.claims
                     if v.reservation_id == result.completed.reservation.reservation_id)
        return result, c.CommittedSnapshot(completion, events, projection, case.context, keys, False)
    finally:
        case.tearDown()


class PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = build_material()

    def setUp(self):
        self.completion, self.snapshot = clone(self.material)
        self.calls = []
        self.authority = s.EvidenceReference('independent-preparation-authority', b'a'*32)
        self.implementation = s.EvidenceReference('qualified-local-verifier', b'i'*32)
        self.reference = s.EvidenceReference('authenticated-B-and-snapshot-provenance', b'r'*32)
        self.validity = s.EvidenceValidity.VALID
        self.hook = None
        self.response_hook = None
        self.verifier = c.TrustedPreparationVerifier(self.authority, self.implementation, self.verify)
        self.preparer = c.CandidatePreparer(self.verifier)

    def verify(self, request):
        self.calls.append(request)
        if self.hook:
            self.hook(request)
        response = c.PreparationQualification(request, self.authority, self.implementation,
                                                self.validity, self.reference)
        return response if self.response_hook is None else self.response_hook(response)

    def prepare(self):
        return self.preparer.prepare_candidate(self.completion, self.snapshot)

    def test_success_exact_single_canonical_derivation(self):
        with patch.object(cp, 'construct_candidate', wraps=cp.construct_candidate) as construct:
            result = self.prepare()
        self.assertIs(result.state, c.PreparationState.PREPARED)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(construct.call_count, 1)
        self.assertIs(type(result.prepared.candidate), s.CheckpointCandidate)
        self.assertEqual(result.prepared.candidate.envelope, self.completion.completed.envelope)
        self.assertEqual(result.prepared.candidate.operation.kind, s.OperationKind.CHECKPOINT_PUBLICATION)
        self.assertEqual(result.prepared.request, c.PreparationRequest(self.completion, self.snapshot))

    def rejected(self, reason=None):
        with patch.object(cp, 'construct_candidate', side_effect=AssertionError('premature constructor')):
            result = self.prepare()
        self.assertIs(result.state, c.PreparationState.REJECTED)
        if reason is not None:
            self.assertIs(result.reason, reason)
        self.assertFalse(result.qualification_attempted)
        self.assertIsNone(result.prepared)
        self.assertEqual(self.calls, [])
        return result

    def test_repeat_is_byte_identical(self):
        first, second = self.prepare(), self.prepare()
        self.assertEqual(first.prepared.candidate.exact_bytes, second.prepared.candidate.exact_bytes)
        self.assertEqual(first.prepared.candidate.sha256, second.prepared.candidate.sha256)
        self.assertEqual(len(self.calls), 2)  # one per evaluator invocation, no retry

    def test_exact_canonical_mapping(self):
        result = self.prepare()
        done, snap = self.completion.completed, self.snapshot
        expected = cp.construct_candidate(done.envelope, snap.completion, snap.events,
            snap.projection, snap.context, cp.CommittedHead(done.event_sequence, done.event_digest,
            done.state_digest), s.OriginalOperation(done.envelope.permit_reference,
            s.OperationKind.CHECKPOINT_PUBLICATION), keys=snap.keys, definite_expiry=snap.definite_expiry)
        self.assertEqual(result.prepared.candidate, expected)
        self.assertEqual(tuple(f.name for f in fields(c._PreparedCandidate)),
                         ('candidate', 'request', 'provenance'))

    def test_result_cannot_be_constructed_replaced_or_truthy(self):
        result = self.prepare()
        with self.assertRaises(TypeError): bool(result)
        with self.assertRaises(TypeError): c.PreparationResult()
        with self.assertRaises(TypeError): replace(result, reason=c.PreparationReason.PREPARED)
        self.assertFalse(any(hasattr(result, name) for name in (
            'publish', 'associate_candidate', 'complete_original', 'deliver', 'retry',
            'publication_permitted', 'completion_permitted', 'ack_delivery_permitted')))

    def test_forged_matching_b_requires_independent_provenance(self):
        # Structurally indistinguishable values cannot prove trusted execution.
        self.completion = replace(self.completion, local=replace(self.completion.local))
        self.validity = s.EvidenceValidity.INVALID
        with patch.object(cp, 'construct_candidate', side_effect=AssertionError('unqualified')):
            result = self.prepare()
        self.assertIs(result.state, c.PreparationState.REJECTED)
        self.assertIs(result.reason, c.PreparationReason.UNQUALIFIED)
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(result.prepared)

    def test_malformed_composition_raises_type_error(self):
        class VerifierSubclass(c.TrustedPreparationVerifier):
            pass
        configurations = (
            None, self.verify, Hostile(),
            VerifierSubclass(self.authority, self.implementation, self.verify),
            replace(self.verifier, authority=None),
            replace(self.verifier, implementation='foreign'),
            replace(self.verifier, authority=object.__new__(s.EvidenceReference)),
            replace(self.verifier, verify=None),
            replace(self.verifier, verify=Hostile()),
            object.__new__(c.TrustedPreparationVerifier),
        )
        for configuration in configurations:
            with self.subTest(configuration_type=type(configuration).__name__):
                with self.assertRaises(TypeError):
                    c.CandidatePreparer(configuration)
        for name in ('authority', 'implementation'):
            reference = clone(self.authority)
            object.__setattr__(reference, 'identity', '')
            with self.assertRaises(TypeError):
                c.CandidatePreparer(replace(self.verifier, **{name: reference}))
        self.assertEqual(self.calls, [])

    def test_response_source_mutation_is_rejected_without_construction(self):
        project = c._project
        observed = []
        def capture(value):
            projection = project(value)
            if type(value) is c.PreparationQualification:
                observed.append(value)
                if len(observed) == 1:
                    object.__setattr__(value.reference, 'identity', 'changed-during-capture')
            return projection
        with (patch.object(c, '_project', capture),
              patch.object(cp, 'construct_candidate', side_effect=AssertionError('mutated response')) as construct):
            result = self.prepare()
        self.assertIs(result.state, c.PreparationState.REJECTED)
        self.assertIs(result.reason, c.PreparationReason.MUTATED)
        self.assertIsNone(result.prepared)
        self.assertTrue(result.qualification_attempted)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(observed), 2)
        self.assertEqual(construct.call_count, 0)

    def test_qualification_unknown(self):
        self.validity = s.EvidenceValidity.UNKNOWN
        with patch.object(cp, 'construct_candidate', side_effect=AssertionError('unknown')):
            result = self.prepare()
        self.assertIs(result.state, c.PreparationState.UNRESOLVED)
        self.assertIs(result.reason, c.PreparationReason.ASSOCIATION_UNKNOWN)
        self.assertTrue(result.qualification_attempted)
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(result.prepared)

    def test_dependency_executable_is_captured_at_construction(self):
        object.__setattr__(self.verifier, 'verify', lambda request: self.fail('replacement verifier'))
        self.assertIs(self.prepare().state, c.PreparationState.PREPARED)
        self.assertEqual(len(self.calls), 1)

    def test_composition_references_are_detached(self):
        expected_authority, expected_implementation = clone(self.authority), clone(self.implementation)
        object.__setattr__(self.verifier.authority, 'identity', 'substituted')
        object.__setattr__(self.verifier.implementation, 'identity', 'substituted')
        self.response_hook = lambda value: replace(value, authority=expected_authority,
                                                   implementation=expected_implementation)
        self.assertIs(self.prepare().state, c.PreparationState.PREPARED)

    def test_prepare_does_not_accept_dependency_or_alternate_constructor(self):
        for keyword in ('verifier', 'callback', 'adapter', 'provider', 'store', 'constructor', 'authority'):
            with self.assertRaises(TypeError):
                self.preparer.prepare_candidate(self.completion, self.snapshot, **{keyword: self.verify})
        self.assertEqual(self.calls, [])

    def test_verifier_gets_separate_request_and_output_has_no_caller_alias(self):
        result = self.prepare()
        request = self.calls[0]
        self.assertIsNot(request.completion, self.completion)
        self.assertIsNot(request.snapshot, self.snapshot)
        self.assertIsNot(result.prepared.request, request)
        self.assertIsNot(result.prepared.provenance.request, request)
        self.assertIsNot(result.prepared.request.completion, self.completion)
        expected = clone(result.prepared)
        object.__setattr__(self.snapshot.context, 'activation_id', 'after-return')
        object.__setattr__(request.snapshot.completion, 'command_id', 'after-response')
        object.__setattr__(self.reference, 'identity', 'after-proof-return')
        self.assertEqual(result.prepared, expected)

    def test_shared_immutable_nodes_are_accepted_and_detached(self):
        self.assertIs(self.prepare().state, c.PreparationState.PREPARED)
        ref = self.authority
        projection = c._project((ref, ref))
        copied = c._detach(projection)
        self.assertIs(copied[0], copied[1])
        self.assertIsNot(copied[0], ref)

    def test_cycles_reject_without_foreign_hooks(self):
        object.__setattr__(self.snapshot, 'keys', (self.snapshot,))
        self.rejected(c.PreparationReason.MALFORMED)

    def test_caller_mutation_before_qualification_is_detected(self):
        original = c._snapshot
        def checked(request):
            original(request)
            object.__setattr__(self.snapshot, 'keys', ())
        with patch.object(c, '_snapshot', checked):
            self.rejected(c.PreparationReason.MUTATED)

    def test_caller_mutation_during_qualification(self):
        self.hook = lambda request: object.__setattr__(self.completion.completed, 'event_digest', b'x'*32)
        result = self.prepare()
        self.assertIs(result.reason, c.PreparationReason.MUTATED)
        self.assertIsNone(result.prepared)
        self.assertTrue(result.qualification_attempted)

    def test_verifier_request_mutation_during_qualification(self):
        self.hook = lambda request: object.__setattr__(request.snapshot, 'keys', ())
        result = self.prepare()
        self.assertIs(result.reason, c.PreparationReason.MUTATED)
        self.assertEqual(len(self.calls), 1)

    def test_mutation_dominates_classified_unavailability(self):
        def unavailable(request):
            object.__setattr__(request.snapshot, 'keys', ())
            raise TimeoutError('not returned')
        self.hook = unavailable
        result = self.prepare()
        self.assertIs(result.state, c.PreparationState.REJECTED)
        self.assertIs(result.reason, c.PreparationReason.MUTATED)
        self.assertEqual(len(self.calls), 1)

    def test_historical_time_only_and_no_new_measurement(self):
        with (patch.object(commands, '_writer_time', side_effect=AssertionError('new measurement')),
              patch.object(commands, '_bind_timing', side_effect=AssertionError('timing binding'))):
            result = self.prepare()
        self.assertIs(result.state, c.PreparationState.PREPARED)
        self.assertEqual(result.prepared.candidate.fixed_utc_us, self.completion.completed.envelope.fixed_utc_us)
        self.assertGreater(self.completion.t2.evaluation.interval.lower_us,
                           self.completion.completed.permit.valid_until_us)

    def test_no_storage_clock_or_effect_capability_calls(self):
        with (patch.object(store.sqlite3, 'connect', side_effect=AssertionError('SQLite')),
             patch.object(store.LeaseStore, 'transaction', side_effect=AssertionError('writer')),
             patch.object(store.LeaseStore, 'read_rows', side_effect=AssertionError('reader')),
             patch.object(cp, 'validate_candidate', side_effect=AssertionError('second constructor')),
              patch.object(p, 'state_bytes', side_effect=AssertionError('whole STATE'))):
            result = self.prepare()
        self.assertIs(result.state, c.PreparationState.PREPARED)
        tree = ast.parse((ROOT / 'services/api/infrastructure/fixture_lease_candidate_preparation.py').read_text())
        imports = {n.module for n in ast.walk(tree) if type(n) is ast.ImportFrom}
        self.assertEqual(imports, {'collections.abc', 'dataclasses', 'enum', 'hashlib', 'types', 'typing', None})
        forbidden = {'connect', 'execute', 'open', 'read_rows', 'transaction', 'measure', 'monotonic_ns',
                     'time', 'sleep', 'associate_candidate', 'publish_candidate', 'query_publication',
                     'complete_original', 'deliver', 'recover', 'validate_candidate', 'state_bytes',
                     'LocalCompletionEvidence', 'uuid4', 'deepcopy', 'asdict'}
        called = {n.func.attr if type(n.func) is ast.Attribute else n.func.id
                  for n in ast.walk(tree) if type(n) is ast.Call
                  and (type(n.func) is ast.Attribute or type(n.func) is ast.Name)}
        self.assertFalse(called & forbidden)

    def test_large_history_no_old_tuple_or_aggregate_state_cap(self):
        old_bound = p.MAX_FIELD // (len(p.PREFIX) + 6 + 12 + 2 + 32)
        source = self.snapshot.projection.commands[0]
        command = p.decode_record(source.canonical_payload_bytes, p.CommandPayload)
        ack = p.decode_record(source.durable_ack_bytes, p.AckPayload)
        history = []
        for index in range(old_bound + 1):
            identity = 'zz-history-' + str(index).zfill(6)
            exact = p.command_bytes(replace(command, command_id=identity))
            retained_ack = p.ack_bytes(replace(ack, command_id=identity, command_payload_sha256=sha256(exact).digest()))
            history.append(replace(source, command_id=identity, canonical_payload_bytes=exact,
                                   canonical_payload_hash=sha256(exact).digest(), durable_ack_bytes=retained_ack))
        projection = replace(self.snapshot.projection, commands=self.snapshot.projection.commands + tuple(history))
        # Synthetic complete material: only the independent trusted test verifier
        # asserts provenance. Rebinding a digest alone would never qualify it.
        digest = p.state_digest(projection, self.snapshot.context)
        self.completion = replace(self.completion, completed=replace(self.completion.completed, state_digest=digest))
        self.snapshot = replace(self.snapshot, projection=projection)
        chunks_size = sum(map(len, p.state_chunks(projection, self.snapshot.context)))
        self.assertGreater(len(projection.commands), old_bound)
        self.assertGreater(chunks_size, p.MAX_BLOB)
        with patch.object(p, 'state_bytes', side_effect=AssertionError('aggregate allocation')):
            self.assertIs(self.prepare().state, c.PreparationState.PREPARED)

    def test_individual_protocol_field_limit_is_preserved(self):
        row = self.snapshot.projection.reservations[0]
        oversized = b'x' * (p.MAX_BLOB + 1)
        row = replace(row, immutable_db_projection=oversized, immutable_db_projection_hash=sha256(oversized).digest())
        self.snapshot = replace(self.snapshot, projection=replace(self.snapshot.projection, reservations=(row,)))
        self.rejected()

    def test_constructor_programming_defect_propagates_without_retry(self):
        with patch.object(cp, 'construct_candidate', side_effect=RuntimeError('canonical defect')) as construct:
            with self.assertRaisesRegex(RuntimeError, 'canonical defect'):
                self.prepare()
        self.assertEqual(construct.call_count, 1)
        self.assertEqual(len(self.calls), 1)

    def test_candidate_association_substitution_cannot_be_accepted(self):
        construct = cp.construct_candidate
        def substituted(*args, **kwargs):
            value = construct(*args, **kwargs)
            object.__setattr__(value, 'operation', s.OriginalOperation(self.reference,
                s.OperationKind.CHECKPOINT_PUBLICATION))
            return value
        with patch.object(cp, 'construct_candidate', substituted):
            with self.assertRaises((c._Bad, s.TimeRejected)):
                self.prepare()
        self.assertEqual(len(self.calls), 1)

    def test_forged_exact_enum_object_rejected_before_validation(self):
        label = str.__new__(p.OutcomeCode, 'SUCCESS')
        object.__setattr__(self.completion.local, 'outcome', label)
        self.rejected(c.PreparationReason.MALFORMED)

    def test_request_supplied_qualification_cannot_replace_b_provenance(self):
        self.completion = c.PreparationQualification(
            c.PreparationRequest(self.completion, self.snapshot), self.authority,
            self.implementation, s.EvidenceValidity.VALID, self.reference)
        self.rejected(c.PreparationReason.MALFORMED)

    def test_original_fixing_cannot_be_replaced_by_t2(self):
        fixing = self.completion.completed.envelope.fixing
        object.__setattr__(fixing, 'point', self.completion.t2.point)
        self.rejected()

    def test_recorded_t1_process_and_evaluation_must_match(self):
        point = replace(self.completion.t1, point=replace(self.completion.t1.point, process_id='foreign'))
        self.completion = replace(self.completion, t1=point,
            completed=replace(self.completion.completed, t1=point))
        self.rejected()

    def test_recorded_t2_evaluation_must_match(self):
        self.completion = replace(self.completion,
            t2=replace(self.completion.t2, evaluation=replace(self.completion.t2.evaluation, sample_age_upper_us=99)))
        self.rejected()

    def test_reference_syntax_cannot_override_invalid_provenance(self):
        self.validity = s.EvidenceValidity.INVALID
        self.response_hook = lambda value: replace(value, reference=self.authority)
        result = self.prepare()
        self.assertIs(result.reason, c.PreparationReason.UNQUALIFIED)
        self.assertIsNone(result.prepared)

    def test_foreign_snapshot_does_not_run_hooks(self):
        self.snapshot = Hostile()
        self.rejected(c.PreparationReason.MALFORMED)

    def test_protocol_scalar_subclasses_are_rejected(self):
        class Ticks(int):
            def __sub__(self, other): raise AssertionError('int subclass hook')
        object.__setattr__(self.completion.t2.point, 'ticks_ns', Ticks(4000))
        self.rejected(c.PreparationReason.MALFORMED)

    def test_bytes_subclass_is_rejected_before_hash(self):
        class ExactBytes(bytes):
            def __len__(self): raise AssertionError('bytes subclass hook')
        object.__setattr__(self.snapshot.completion, 'canonical_payload_bytes', ExactBytes(b'bad'))
        self.rejected(c.PreparationReason.MALFORMED)

    def test_consistent_forged_snapshot_is_not_its_own_provenance(self):
        projection = replace(self.snapshot.projection,
            metadata=replace(self.snapshot.projection.metadata, fixture_plan_sha256=b'x'*32))
        digest = p.state_digest(projection, self.snapshot.context)
        self.snapshot = replace(self.snapshot, projection=projection)
        self.completion = replace(self.completion, completed=replace(self.completion.completed, state_digest=digest))
        self.validity = s.EvidenceValidity.INVALID
        result = self.prepare()
        self.assertIs(result.reason, c.PreparationReason.UNQUALIFIED)
        self.assertEqual(len(self.calls), 1)


def local_case(name, change):
    def test(self):
        change(self)
        self.rejected()
    setattr(PreparationTests, 'test_local_' + name, test)


def set_snapshot(test, **values):
    test.snapshot = replace(test.snapshot, **values)


def set_done(test, **values):
    test.completion = replace(test.completion, completed=replace(test.completion.completed, **values))


for _name, _change in (
    ('missing_completion', lambda t: set_snapshot(t, completion=None)),
    ('missing_event', lambda t: set_snapshot(t, events=t.snapshot.events[:-1])),
    ('reordered_events', lambda t: set_snapshot(t, events=tuple(reversed(t.snapshot.events)))),
    ('extra_event', lambda t: set_snapshot(t, events=t.snapshot.events + t.snapshot.events[-1:])),
    ('noncontiguous_events', lambda t: set_snapshot(t, events=(replace(t.snapshot.events[0], event_sequence=99),)+t.snapshot.events[1:])),
    ('event_fixed_utc', lambda t: set_snapshot(t, events=(replace(t.snapshot.events[0], utc_time=99),)+t.snapshot.events[1:])),
    ('wrong_head', lambda t: set_done(t, event_sequence=99)),
    ('wrong_event_digest', lambda t: set_done(t, event_digest=b'x'*32)),
    ('wrong_state', lambda t: set_done(t, state_digest=b'x'*32)),
    ('wrong_keys', lambda t: set_snapshot(t, keys=())),
    ('duplicate_keys', lambda t: set_snapshot(t, keys=t.snapshot.keys*2)),
    ('wrong_revision', lambda t: set_done(t, reservation=replace(t.completion.completed.reservation, revision=9))),
    ('wrong_reservation', lambda t: set_done(t, reservation=replace(t.completion.completed.reservation, owner='other'))),
    ('missing_unrelated_command', lambda t: set_snapshot(t, projection=replace(t.snapshot.projection, commands=(t.snapshot.completion,)))),
    ('missing_unrelated_reservation', lambda t: set_snapshot(t, projection=replace(t.snapshot.projection, reservations=t.snapshot.projection.reservations[:1]))),
    ('later_state', lambda t: set_snapshot(t, projection=replace(t.snapshot.projection, metadata=replace(t.snapshot.projection.metadata, last_valid_utc=999)))),
    ('wrong_context', lambda t: set_snapshot(t, context=replace(t.snapshot.context, register_id='other'))),
    ('wrong_generation', lambda t: set_snapshot(t, context=replace(t.snapshot.context, issuer_generation=2))),
    ('wrong_activation', lambda t: set_snapshot(t, context=replace(t.snapshot.context, activation_id='other'))),
    ('wrong_representation', lambda t: set_snapshot(t, context=replace(t.snapshot.context, representation=p.STATE_1))),
    ('wrong_principal', lambda t: set_snapshot(t, completion=replace(t.snapshot.completion, authenticated_principal='other'))),
    ('wrong_command', lambda t: set_done(t, command_bytes=b'wrong')),
    ('wrong_ack', lambda t: set_done(t, ack_bytes=b'wrong')),
    ('wrong_permit', lambda t: set_done(t, permit=replace(t.completion.completed.permit, evidence=t.reference))),
    ('wrong_envelope', lambda t: set_done(t, envelope=replace(t.completion.completed.envelope, reference=t.reference))),
    ('wrong_predecessor', lambda t: set_done(t, envelope=replace(t.completion.completed.envelope,
        predecessor=replace(t.completion.completed.envelope.predecessor, state_digest=b'x'*32)))),
    ('wrong_operation', lambda t: set_done(t, permit=replace(t.completion.completed.permit,
        context=replace(t.completion.completed.permit.context, operation=c.contract.Operation.CANARY)))),
    ('wrong_approval', lambda t: set_done(t, envelope=replace(t.completion.completed.envelope, approval=None))),
    ('missing_t1', lambda t: setattr(t, 'completion', replace(t.completion, t1=None))),
    ('missing_t2', lambda t: setattr(t, 'completion', replace(t.completion, t2=None))),
    ('missing_completed', lambda t: setattr(t, 'completion', replace(t.completion, completed=None))),
    ('unconfirmed', lambda t: setattr(t, 'completion', replace(t.completion,
        local=replace(t.completion.local, storage_result=None)))),
    ('wrong_model_sample', lambda t: object.__setattr__(t.completion.original.observation.model, 'sample', t.reference)),
    ('wrong_model_profile', lambda t: object.__setattr__(t.completion.original.support, 'profile', t.reference)),
    ('wrong_representation_authority', lambda t: object.__setattr__(
        t.completion.completed.envelope.predecessor, 'representation_authority', t.reference)),
    ('wrong_host', lambda t: object.__setattr__(t.completion.completed.envelope.activation, 'host_identity', 'other')),
    ('wrong_retained_principal', lambda t: object.__setattr__(t.completion.completed.envelope, 'principal', 'other')),
    ('wrong_fixed_utc', lambda t: object.__setattr__(t.completion.completed.envelope, 'fixed_utc_us', 99)),
    ('wrong_time', lambda t: set_done(t, last_valid_utc=99)),
    ('wrong_t1', lambda t: setattr(t, 'completion', replace(t.completion,
        t1=replace(t.completion.t1, evaluation=replace(t.completion.t1.evaluation, sample_age_upper_us=99))))),
    ('wrong_t2', lambda t: setattr(t, 'completion', replace(t.completion,
        t2=replace(t.completion.t2, point=replace(t.completion.t2.point, domain_id='other'))))),
    ('backward_t2', lambda t: setattr(t, 'completion', replace(t.completion,
        t2=replace(t.completion.t2, point=replace(t.completion.t2.point, ticks_ns=0))))),
    ('event_list', lambda t: set_snapshot(t, events=list(t.snapshot.events))),
    ('key_list', lambda t: set_snapshot(t, keys=list(t.snapshot.keys))),
    ('key_set', lambda t: set_snapshot(t, keys=set(t.snapshot.keys))),
    ('key_dict', lambda t: set_snapshot(t, keys={})),
    ('event_iterator', lambda t: set_snapshot(t, events=iter(t.snapshot.events))),
    ('state_iterator', lambda t: set_snapshot(t, projection=replace(t.snapshot.projection, commands=iter(t.snapshot.projection.commands)))),
    ('forged_state_label', lambda t: setattr(t, 'completion', replace(t.completion, local=replace(t.completion.local, outcome='SUCCESS')))),
    ('non_bool', lambda t: set_snapshot(t, definite_expiry=1)),
): local_case(_name, _change)


def upstream_case(name, transform, reason, state):
    def test(self):
        self.completion = transform(self)
        with patch.object(cp, 'construct_candidate', side_effect=AssertionError('upstream')):
            result = self.prepare()
        self.assertIs(result.state, state)
        self.assertIs(result.reason, reason)
        self.assertFalse(result.qualification_attempted)
        self.assertIsNone(result.prepared)
        self.assertEqual(self.calls, [])
    setattr(PreparationTests, 'test_upstream_' + name, test)


for _name, _transform, _reason, _state in (
    ('replay', lambda t: replace(t.completion.local, replayed=True), c.PreparationReason.NOT_NEW_TRANSITION, c.PreparationState.REJECTED),
    ('mismatch', lambda t: replace(t.completion.local, outcome=p.OutcomeCode.REPLAY_MISMATCH), c.PreparationReason.NOT_NEW_TRANSITION, c.PreparationState.REJECTED),
    ('bare_local', lambda t: t.completion.local, c.PreparationReason.NOT_NEW_TRANSITION, c.PreparationState.REJECTED),
    ('unknown', lambda t: replace(t.completion, local=replace(t.completion.local, outcome=p.OutcomeCode.STORAGE_UNKNOWN)), c.PreparationReason.UPSTREAM_UNRESOLVED, c.PreparationState.UNRESOLVED),
    ('reconciliation', lambda t: replace(t.completion, reconciliation_required=True), c.PreparationReason.UPSTREAM_UNRESOLVED, c.PreparationState.UNRESOLVED),
    ('cleanup', lambda t: replace(t.completion, reconciliation_required=True, reason=store._CommitCleanupReason.CURSOR_CLOSE), c.PreparationReason.UPSTREAM_UNRESOLVED, c.PreparationState.UNRESOLVED),
    ('contradiction', lambda t: replace(t.completion, later_contradiction=t.reference), c.PreparationReason.UPSTREAM_UNRESOLVED, c.PreparationState.UNRESOLVED),
): upstream_case(_name, _transform, _reason, _state)


def response_case(name, transform):
    def test(self):
        self.response_hook = lambda response: transform(self, response)
        with patch.object(cp, 'construct_candidate', side_effect=AssertionError('malformed qualification')):
            result = self.prepare()
        self.assertIs(result.reason, c.PreparationReason.MALFORMED_QUALIFICATION)
        self.assertIs(result.state, c.PreparationState.REJECTED)
        self.assertTrue(result.qualification_attempted)
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(result.prepared)
    setattr(PreparationTests, 'test_response_' + name, test)


for _name, _transform in (
    ('bool', lambda t, v: True), ('none', lambda t, v: None),
    ('authority', lambda t, v: replace(v, authority=t.reference)),
    ('implementation', lambda t, v: replace(v, implementation=t.reference)),
    ('reference', lambda t, v: replace(v, reference='reference-syntax')),
    ('reference_shape', lambda t, v: replace(v, reference=object.__new__(s.EvidenceReference))),
    ('request', lambda t, v: replace(v, request=replace(v.request, snapshot=replace(v.request.snapshot, keys=())))),
    ('validity_label', lambda t, v: replace(v, validity='VALID')),
): response_case(_name, _transform)


def exception_case(name, error, classified):
    def test(self):
        def failure(request): raise error('test-only failure')
        self.hook = failure
        if classified:
            result = self.prepare()
            self.assertIs(result.reason, c.PreparationReason.DEPENDENCY_UNAVAILABLE)
            self.assertIs(result.state, c.PreparationState.UNRESOLVED)
            self.assertIsNone(result.prepared)
            self.assertTrue(result.qualification_attempted)
        else:
            with self.assertRaises(error): self.prepare()
        self.assertEqual(len(self.calls), 1)
    setattr(PreparationTests, 'test_exception_' + name, test)


for _name, _error, _classified in (
    ('capability', s.CapabilityUnavailable, True), ('availability', c.a.ExternalAvailabilityFailure, True),
    ('timeout', TimeoutError, True), ('value', ValueError, False), ('runtime', RuntimeError, False),
    ('type', TypeError, False), ('attribute', AttributeError, False), ('assertion', AssertionError, False),
    ('interrupt', KeyboardInterrupt, False), ('exit', SystemExit, False), ('memory', MemoryError, False),
): exception_case(_name, _error, _classified)


def hostile_case(name, make):
    def test(self):
        self.completion = make(self)
        self.rejected(c.PreparationReason.MALFORMED)
    setattr(PreparationTests, 'test_hostile_' + name, test)


class Hostile:
    def __getattribute__(self, name): raise AssertionError('foreign traversal')
    def __eq__(self, other): raise AssertionError('foreign equality')
    def __hash__(self): raise AssertionError('foreign hash')
    def __repr__(self): raise AssertionError('foreign repr')


class Principal(str):
    def encode(self, *args): raise AssertionError('primitive subclass')


class ForeignCompletion(commands._QualifiedCompletion):
    def __getattribute__(self, name): raise AssertionError('subclass traversal')


def hostile_principal(test):
    object.__setattr__(test.completion.completed.envelope, 'principal', Principal('owner'))
    return test.completion


for _name, _make in (
    ('root', lambda t: Hostile()),
    ('subclass', lambda t: object.__new__(ForeignCompletion)),
    ('primitive_subclass', lambda t: hostile_principal(t)),
    ('nested', lambda t: replace(t.completion, original=Hostile())),
): hostile_case(_name, _make)


if __name__ == '__main__':
    unittest.main()
