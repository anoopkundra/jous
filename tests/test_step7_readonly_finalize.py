"""Inert, synchronous coroutine tests of the complete finalization lifecycle."""
import copy
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import unittest

import test_step7_readonly_evidence as fixtures

spec = importlib.util.spec_from_file_location('step7_finalize', fixtures.fixture.ROOT /
    'services/api/infrastructure/step7_readonly_finalize.py')
finalize = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = finalize
spec.loader.exec_module(finalize)


def drive(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as finished:
        return finished.value
    raise AssertionError('Synthetic lifecycle unexpectedly requested asynchronous IO')


class FinalizationTests(unittest.TestCase):
    def setup_state(self, catalog=None):
        self.events = []
        self.written = {}
        return finalize.FinalizationState(fixtures.RetentionTests().wrap(catalog))

    def run_state(self, state, **overrides):
        async def collection(s):
            self.events.append('collection')
            for gate in finalize.REQUIRED_GATES:
                s.record_gate(gate)
            return s.evidence.collect(fixtures.runner.public_inventory, fixtures.runner.Stop)
        def cleanup(name):
            async def operation():
                self.events.append(name)
            return operation
        def primary(payload):
            self.events.append('primary')
            self.written['primary'] = payload
        def amendment():
            self.events.append('amendment_input')
            return b'{"execution_approved":false}'
        def secondary(payload):
            self.events.append('amendment_write')
            self.written['amendment'] = payload
        args = dict(collection=collection, rollback=cleanup('rollback'),
            close=cleanup('close'), dispose=cleanup('dispose'), primary_writer=primary,
            amendment_reader=amendment, amendment_writer=secondary)
        args.update(overrides)
        return drive(finalize.run_lifecycle(state, **args))

    def assert_incomplete(self, state):
        self.assertEqual(state.document['status'], 'INCOMPLETE_FAIL_CLOSED')
        for key in ('collection_complete', 'compatibility_approved',
                    'execution_approved', 'migration_ready'):
            self.assertIs(state.document[key], False)

    def test_complete_order_and_primary_success(self):
        s = self.run_state(self.setup_state())
        self.assertEqual(self.events, ['collection', 'rollback', 'close', 'dispose',
                                     'primary', 'amendment_input', 'amendment_write'])
        self.assertTrue(s.primary_written)
        self.assertTrue(json.loads(self.written['primary'])['collection_complete'])
        self.assertFalse(json.loads(self.written['amendment'])['execution_approved'])

    def test_public_mismatch_retains_exact_delta(self):
        c = fixtures.fixture.PublicCatalog()
        missing = c.routines.pop()
        s = self.run_state(self.setup_state(c))
        self.assert_incomplete(s)
        self.assertTrue(s.primary_written)
        self.assertEqual(s.document['failure_gate'], 'PUBLIC_ROUTINES_SET')
        self.assertEqual(s.document['public_routine_sets'][0]['missing_identities'],
                         fixtures.retention.primitive([fixtures.runner.routine_identity(missing)]))
        self.assertNotIn('amendment_input', self.events)

    def test_early_failure_retains_operator_booleans(self):
        s = self.setup_state()
        async def collect(state):
            def queries(e):
                fixtures.runner.rows(e, fixtures.runner._STRUCTURAL_QUERIES['operators'], {'ids':[514]})
                raise fixtures.runner.Stop('EARLY_GATE')
            return state.evidence.collect(queries, fixtures.runner.Stop)
        self.run_state(s, collection=collect)
        self.assert_incomplete(s)
        self.assertTrue(s.document['observations'])
        op = s.document['observations'][0]['rows'][0]
        self.assertIs(type(op['oprcanmerge']), bool)
        self.assertIs(type(op['oprcanhash']), bool)
        self.assertTrue(s.primary_written)

    def test_amendment_serializer_failure_preserves_primary(self):
        def fail(_): raise KeyboardInterrupt()
        s = self.run_state(self.setup_state(), amendment_serializer=fail)
        self.assertTrue(s.primary_written)
        self.assertEqual(s.secondary_failure, 'AMENDMENT_SERIALIZATION_FAILED')
        self.assertEqual(json.loads(self.written['primary']), s.document)

    def test_amendment_write_failure_preserves_primary(self):
        def fail(_): raise SystemExit()
        s = self.run_state(self.setup_state(), amendment_writer=fail)
        self.assertTrue(s.primary_written)
        self.assertEqual(s.secondary_failure, 'AMENDMENT_WRITE_FAILED')

    def test_missing_and_invalid_amendment_inputs(self):
        for value in (None, b'bad json', b'{}', b'{"execution_approved":true}'):
            with self.subTest(value=value):
                s = self.run_state(self.setup_state(), amendment_reader=lambda: value)
                self.assertTrue(s.primary_written)
                self.assertEqual(s.secondary_failure, 'AMENDMENT_INPUT_FAILED')

    def test_missing_amendment_reader(self):
        s = self.run_state(self.setup_state(), amendment_reader=None)
        self.assertTrue(s.primary_written)
        self.assertEqual(s.secondary_failure, 'AMENDMENT_INPUT_FAILED')

    def test_primary_serialization_failure(self):
        def fail(_): raise ValueError()
        s = self.run_state(self.setup_state(), primary_serializer=fail)
        self.assert_incomplete(s)
        self.assertFalse(s.primary_written)
        self.assertEqual(s.finalization_failure, 'PRIMARY_SERIALIZATION_FAILED')

    def test_primary_serialization_wrong_type_or_document(self):
        for value in ('not bytes', b'{}'):
            s = self.run_state(self.setup_state(), primary_serializer=lambda _: value)
            self.assert_incomplete(s)
            self.assertFalse(s.primary_written)

    def test_primary_write_failure(self):
        def fail(_): raise OSError()
        s = self.run_state(self.setup_state(), primary_writer=fail)
        self.assert_incomplete(s)
        self.assertFalse(s.primary_written)
        self.assertEqual(s.finalization_failure, 'PRIMARY_WRITE_FAILED')
        self.assertIsNotNone(s.primary_payload)

    def test_rollback_failure(self):
        async def fail(): raise KeyboardInterrupt()
        s = self.run_state(self.setup_state(), rollback=fail)
        self.assert_incomplete(s)
        self.assertEqual(s.cleanup, {'rollback':'FAILED', 'close':'PASS', 'dispose':'PASS'})
        self.assertFalse(s.primary_written)

    def test_close_and_dispose_failure(self):
        async def fail(): raise SystemExit()
        for name in ('close', 'dispose'):
            s = self.run_state(self.setup_state(), **{name:fail})
            self.assert_incomplete(s)
            self.assertEqual(s.cleanup[name], 'FAILED')
            self.assertFalse(s.primary_written)

    def test_missing_gate_cannot_claim_complete(self):
        s = self.setup_state()
        async def collect(state):
            return state.evidence.collect(fixtures.runner.public_inventory, fixtures.runner.Stop)
        self.run_state(s, collection=collect)
        self.assert_incomplete(s)
        self.assertEqual(s.document['failure_gate'], 'COLLECTION_GATES_INCOMPLETE')

    def test_returned_document_cannot_override_authoritative_failure(self):
        s = self.setup_state()
        async def collect(state):
            state.evidence.failure_document('EARLY_GATE')
            return {'collection_complete':True}
        self.run_state(s, collection=collect)
        self.assert_incomplete(s)
        self.assertEqual(s.document['failure_gate'], 'EARLY_GATE')

    def test_snapshot_copy_failure_still_cleans_up(self):
        s = self.setup_state()
        def fail(): raise MemoryError()
        s.evidence.retained_document = fail
        self.run_state(s)
        self.assertEqual(s.cleanup, dict.fromkeys(('rollback','close','dispose'), 'PASS'))
        self.assertEqual(s.finalization_failure, 'DOCUMENT_FINALIZATION_FAILED')
        self.assertFalse(s.primary_written)

    def test_invalid_metadata_does_not_suppress_primary(self):
        s = self.setup_state(); s.metadata = {'invalid':object()}
        self.run_state(s)
        self.assertTrue(s.primary_written)
        self.assertEqual(s.secondary_failure, 'METADATA_FINALIZATION_FAILED')

    def test_all_inputs_initialized_and_lifecycle_one_shot(self):
        s = self.setup_state()
        self.assertIsNone(s.amendment_bytes)
        self.assertIsNone(s.primary_payload)
        self.run_state(s, amendment_reader=None, amendment_writer=None)
        with self.assertRaisesRegex(ValueError, 'FINALIZATION_ALREADY_STARTED'):
            self.run_state(s)

    def test_incomplete_never_reads_amendment(self):
        s = self.setup_state()
        async def fail(state): raise KeyboardInterrupt()
        self.run_state(s, collection=fail)
        self.assert_incomplete(s)
        self.assertTrue(s.primary_written)
        self.assertIsNone(s.amendment_bytes)

    def test_atomic_writer_preserves_preimage_on_failed_check(self):
        with tempfile.TemporaryDirectory(prefix='jous-offline-finalize-') as directory:
            path = Path(directory) / 'synthetic.json'
            path.write_bytes(b'old synthetic evidence')
            with self.assertRaisesRegex(ValueError, 'ARTIFACT_PREIMAGE_CHANGED'):
                finalize.atomic_publish(path, b'new synthetic evidence', expected_sha256=None)
            self.assertEqual(path.read_bytes(), b'old synthetic evidence')

    def test_atomic_writer_new_and_replacement(self):
        with tempfile.TemporaryDirectory(prefix='jous-offline-finalize-') as directory:
            path = Path(directory) / 'synthetic.json'
            finalize.atomic_publish(path, b'first', expected_sha256=None)
            finalize.atomic_publish(path, b'second',
                expected_sha256=finalize.hashlib.sha256(b'first').hexdigest())
            self.assertEqual(path.read_bytes(), b'second')
            self.assertEqual(list(Path(directory).iterdir()), [path])
