"""IL.3 disposable synthetic SQLite tests. No operational register is initialized.

Power loss, commit/rollback I/O ambiguity and real filesystem flush durability need
separately scoped fault/VFS qualification; these tests do not pretend to prove them.
"""
import ast
from dataclasses import replace
from hashlib import sha256
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
for name in ('fixture_lease_contract', 'fixture_lease_store'):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'services/api/infrastructure' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
s = sys.modules['fixture_lease_store']
c = sys.modules['fixture_lease_contract']


def synthetic_database(path):
    """Test-only schema creation, never called by production existing-only opening."""
    connection = sqlite3.connect(path, isolation_level=None)
    connection.executescript(s.SCHEMA_SQL)
    metadata = s.MetadataRow(1, 1, 'synthetic-register', 1, 'synthetic-activation',
                            *([b'x'*32] * 4), 0, b'y'*32, b'z'*32, 0, 1)
    values = s._values(metadata)
    connection.execute('INSERT INTO REGISTER_METADATA VALUES (' + ','.join('?' for _ in values) + ')', values)
    connection.close()
    return metadata


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='jous-synthetic-il3-')
        self.path = Path(self.directory.name) / 'synthetic.sqlite'
        self.metadata = synthetic_database(self.path)
        self.store = s.LeaseStore(self.path, 'synthetic-register')
        self.artifact = s.ArtifactRow('synthetic-artifact', c.ArtifactType.PROVISIONING_REQUEST,
                                     b'synthetic-request', sha256(b'synthetic-request').digest(),
                                     b'synthetic-approval', sha256(b'synthetic-approval').digest(),
                                     'synthetic-approver', 'synthetic-authorization',
                                     c.Operation.FIXTURE_PROVISIONING, c.Phase.PRE_AUTH, None)
        projection = b'synthetic-projection'
        self.reservation = s.ReservationRow('synthetic-reservation', 'synthetic-register',
            'synthetic-set', c.Operation.FIXTURE_PROVISIONING, c.Phase.PRE_AUTH,
            c.ArtifactType.PROVISIONING_REQUEST, self.artifact.artifact_id, self.artifact.sha256,
            projection, sha256(projection).digest(), 'synthetic-owner', 'synthetic-authorization',
            0, 1, 2, 100, 90, 0, c.LeaseStatus.LEASED, 0, s.ExecutionState.NOT_STARTED,
            None, None, None)
        self.key = c.ConflictKey.db_uuid(c.DatabaseTargetScope('synthetic-target'), UUID(int=1)).canonical_bytes
        self.claim = s.ClaimRow(self.key, self.reservation.reservation_id, 0, self.artifact.artifact_id)

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def raw(self, sql, parameters=()):
        connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def populate(self):
        with self.store.transaction() as writer:
            writer.insert(self.artifact)
            writer.insert(self.reservation)
            writer.insert(self.claim)
        return writer

    def test_existing_only_roundtrip(self):
        self.assertEqual(self.store.read_rows(s.MetadataRow), (self.metadata,))
        writer = self.populate()
        self.assertIs(writer.result, s.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        self.assertEqual(self.store.read_rows(s.ArtifactRow), (self.artifact,))
        self.assertEqual(self.store.read_rows(s.ReservationRow), (self.reservation,))
        self.assertEqual(self.store.read_rows(s.ClaimRow), (self.claim,))
        self.store.close()
        self.store = s.LeaseStore(self.path, 'synthetic-register')
        self.assertEqual(self.store.read_rows(s.ClaimRow), (self.claim,))

    def test_missing_file_and_parent_never_created(self):
        for path in (self.path.parent / 'missing.sqlite', self.path.parent / 'missing-parent' / 'db.sqlite'):
            with self.assertRaises(s.StorageRejected): s.LeaseStore(path, 'synthetic-register')
            self.assertFalse(path.exists())
        self.assertFalse((self.path.parent / 'missing-parent').exists())

    def test_relative_path_rejected(self):
        with self.assertRaises(s.StorageRejected): s.LeaseStore(Path('synthetic.sqlite'), 'synthetic-register')

    def test_wrong_register(self):
        with self.assertRaises(s.StorageRejected): s.LeaseStore(self.path, 'wrong-register')

    def test_missing_table_rejected(self):
        self.raw('DROP TABLE EVENTS')
        with self.assertRaises(s.StorageRejected): s.LeaseStore(self.path, 'synthetic-register')

    def test_extra_table_rejected(self):
        self.raw('CREATE TABLE EXTRA(value TEXT) STRICT')
        with self.assertRaises(s.StorageRejected): s.LeaseStore(self.path, 'synthetic-register')
        self.assertTrue(self.raw("SELECT name FROM sqlite_schema WHERE name='EXTRA'"))

    def test_extra_index_rejected(self):
        self.raw('CREATE INDEX extra_index ON APPROVED_ARTIFACTS(approver)')
        with self.assertRaises(s.StorageRejected): s.LeaseStore(self.path, 'synthetic-register')

    def test_altered_table_rejected(self):
        self.raw('ALTER TABLE APPROVED_ARTIFACTS ADD COLUMN extra TEXT')
        with self.assertRaises(s.StorageRejected): s.LeaseStore(self.path, 'synthetic-register')

    def test_wrong_version_rejected_without_repair(self):
        connection = sqlite3.connect(self.path)
        connection.execute('PRAGMA ignore_check_constraints=ON')
        connection.execute('UPDATE REGISTER_METADATA SET schema_version=2')
        connection.commit()
        connection.close()
        with self.assertRaises(s.StorageRejected): s.LeaseStore(self.path, 'synthetic-register')
        self.assertEqual(self.raw('SELECT schema_version FROM REGISTER_METADATA'), [(2,)])

    def test_strict_tables(self):
        self.assertEqual(len([x for x in self.raw('PRAGMA table_list') if x[1] in
                              {v[0] for v in s.SPECS.values()} and x[5] == 1]), 6)
        with self.assertRaises(sqlite3.Error):
            self.raw("UPDATE REGISTER_METADATA SET last_valid_utc='not-an-integer'")

    def test_profile_exact(self):
        # Read-only inspection of private connection is test-only; no raw public API.
        for name, expected in [('journal_mode','delete'),('synchronous',3),('foreign_keys',1),
                               ('busy_timeout',0),('locking_mode','normal'),('read_uncommitted',0)]:
            self.assertEqual(self.store._connection.execute('PRAGMA '+name).fetchone()[0], expected)
        self.assertIsNone(self.store._connection.isolation_level)

    def test_wal_rejected_not_repaired(self):
        self.store.close()
        self.assertEqual(self.raw('PRAGMA journal_mode=WAL'), [('wal',)])
        with self.assertRaises(s.StorageRejected): s.LeaseStore(self.path, 'synthetic-register')
        self.assertEqual(self.raw('PRAGMA journal_mode'), [('wal',)])

    def test_begin_immediate_second_writer_rejects(self):
        second = s.LeaseStore(self.path, 'synthetic-register')
        try:
            with self.store.transaction():
                with self.assertRaises(s.StorageRejected):
                    with second.transaction(): self.fail('second writer acquired')
            with second.transaction() as writer:
                writer.insert(self.artifact)
        finally:
            second.close()

    def test_body_exception_confirmed_rollback(self):
        with self.assertRaisesRegex(ValueError, 'synthetic'):
            with self.store.transaction() as writer:
                writer.insert(self.artifact)
                raise ValueError('synthetic')
        self.assertIs(writer.result, s.LocalStorageResult.LOCAL_STORAGE_ROLLBACK_CONFIRMED)
        self.assertEqual(self.store.read_rows(s.ArtifactRow), ())

    def test_caught_statement_failure_still_rolls_back(self):
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction() as writer:
                writer.insert(self.artifact)
                with self.assertRaises(s.StorageRejected): writer.insert(self.artifact)
        self.assertIs(writer.result, s.LocalStorageResult.LOCAL_STORAGE_ROLLBACK_CONFIRMED)
        self.assertEqual(self.store.read_rows(s.ArtifactRow), ())

    def test_nested_transaction_rejected(self):
        with self.store.transaction():
            with self.assertRaises(s.StorageRejected):
                with self.store.transaction(): self.fail('nested')

    def test_writer_inactive_and_no_arbitrary_sql(self):
        with self.store.transaction() as writer: pass
        with self.assertRaises(s.StorageRejected): writer.insert(self.artifact)
        with self.assertRaises(s.StorageRejected): s.TransactionWriter(self.store).insert(self.artifact)
        self.assertFalse(hasattr(self.store, 'execute'))
        self.assertFalse(hasattr(writer, 'execute'))
        self.assertFalse(hasattr(self.store, 'insert'))

    def test_identity_preserved(self):
        row = replace(self.artifact, artifact_id=' Synthetic-? ', approver=' Reviewer ')
        with self.store.transaction() as writer: writer.insert(row)
        self.assertEqual(self.store.read_rows(s.ArtifactRow), (row,))

    def test_enum_roundtrips(self):
        row = self.artifact
        self.assertEqual(s._decode(s.ArtifactRow, s._values(row)), row)
        for enum in (c.ArtifactType,c.Operation,c.Phase,c.LeaseStatus,c.Command,
                     s.ExecutionState,s.QuarantineReason,s.OutcomeCode,s.EventType):
            for value in enum:
                self.assertIs(s._validate(value.value, enum, True), value)
            with self.assertRaises(s.StorageRejected): s._validate('UNKNOWN_VALUE', enum, True)

    def test_malformed_key_and_digest(self):
        for row in (replace(self.claim, canonical_key=b'bad'),
                    replace(self.artifact, sha256=b'x'),
                    replace(self.artifact, sha256=b'x'*32)):
            with self.assertRaises(s.StorageRejected):
                with self.store.transaction() as writer: writer.insert(row)

    def test_numeric_bounds_and_bool(self):
        for value in (True, False, -1, 1 << 63, 0.5):
            with self.assertRaises(s.StorageRejected):
                with self.store.transaction() as writer:
                    writer.insert(replace(self.artifact, predecessor_artifact_id=None))
                    writer.insert(replace(self.reservation, revision=value))
        for value in (True, 2):
            with self.assertRaises(s.StorageRejected): s._validate(value, s.BOOL)

    def test_duplicate_claim_global_full_bytes(self):
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction() as writer:
                writer.insert(self.artifact)
                writer.insert(self.reservation)
                writer.insert(self.claim)
                writer.insert(self.claim)
        self.assertEqual(self.store.read_rows(s.ClaimRow), ())

    def test_foreign_key_violation(self):
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction() as writer: writer.insert(self.claim)

    def test_phase_binding_and_deadline_rejected(self):
        for row in (replace(self.reservation, operation_type=c.Operation.CANARY),
                    replace(self.reservation, binding_kind=c.ArtifactType.FIXTURE_MANIFEST),
                    replace(self.reservation, completion_deadline=100),
                    replace(self.reservation, acknowledged_at=100)):
            with self.assertRaises(s.StorageRejected):
                with self.store.transaction() as writer:
                    writer.insert(self.artifact)
                    writer.insert(row)

    def test_ack_required_for_success(self):
        payload = b'synthetic-payload'
        command = s.CommandRow('synthetic-command','synthetic-principal',c.Command.ACQUIRE,
            payload,sha256(payload).digest(),0,None,s.OutcomeCode.SUCCESS,None,None)
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction() as writer: writer.insert(command)

    def test_command_event_deferred_fk_roundtrip(self):
        payload = b'synthetic-payload'
        command = s.CommandRow('synthetic-command','synthetic-principal',c.Command.ACQUIRE,
            payload,sha256(payload).digest(),0,self.reservation.reservation_id,
            s.OutcomeCode.SUCCESS,b'synthetic-retained-ack',1)
        event = s.EventRow(1,command.command_id,self.reservation.reservation_id,'synthetic-register',
            1,'synthetic-activation',s.EventType.ACKNOWLEDGED,2,b'x'*32,b'synthetic-event',b'y'*32,
            0,self.artifact.artifact_id,None)
        with self.store.transaction() as writer:
            for row in (self.artifact,self.reservation,self.claim,command,event): writer.insert(row)
        self.assertEqual(self.store.read_rows(s.CommandRow),(command,))
        self.assertEqual(self.store.read_rows(s.EventRow),(event,))

    def test_relational_binding_mismatch_rolls_back(self):
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction() as writer:
                writer.insert(self.artifact)
                writer.insert(replace(self.reservation,binding_sha256=b'z'*32))
                writer.insert(self.claim)
        self.assertEqual(self.store.read_rows(s.ArtifactRow),())

    def test_unreleased_reservation_without_claim_rejected(self):
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction() as writer:
                writer.insert(self.artifact)
                writer.insert(self.reservation)

    def test_expiry_preserves_claim(self):
        with self.store.transaction() as writer:
            writer.insert(self.artifact)
            writer.insert(replace(self.reservation,lease_status=c.LeaseStatus.EXPIRED,expired_condition=1))
            writer.insert(self.claim)
        self.assertEqual(self.store.read_rows(s.ClaimRow),(self.claim,))

    def test_corrupt_file_rejected(self):
        path = self.path.parent / 'corrupt.sqlite'
        path.write_bytes(b'synthetic-not-a-database')
        with self.assertRaises(s.StorageRejected): s.LeaseStore(path,'synthetic-register')
        self.assertEqual(path.read_bytes(),b'synthetic-not-a-database')

    def test_malformed_durable_row_and_poisoned_handle(self):
        self.raw('DROP TABLE EVENTS')
        with self.assertRaises(s.StorageRejected): self.store.read_rows(s.MetadataRow)
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction(): self.fail('poisoned handle wrote')

    def test_unknown_durable_enum_rejected(self):
        self.populate()
        connection=sqlite3.connect(self.path)
        connection.execute('PRAGMA ignore_check_constraints=ON')
        connection.execute("UPDATE RESERVATIONS SET lease_status='NEW_UNKNOWN'")
        connection.commit()
        connection.close()
        with self.assertRaises(s.StorageRejected): s.LeaseStore(self.path,'synthetic-register')

    def test_invalid_utf8_width(self):
        for value in ('', ' '*2, '\u00e9'*128):
            with self.assertRaises(s.StorageRejected): s._validate(value,s.ID)

    def test_runtime_floor_and_threadsafety(self):
        with patch.object(s.sqlite3, 'sqlite_version_info', (3,44,0)):
            with self.assertRaises(s.StorageRejected): s.LeaseStore(self.path,'synthetic-register')
        with patch.object(s.sqlite3, 'threadsafety', 0):
            with self.assertRaises(s.StorageRejected): s.LeaseStore(self.path,'synthetic-register')

    def test_schema_sql_constraints_directly(self):
        # Bypass Python serialization only to prove storage-level checks exist.
        with self.assertRaises(sqlite3.Error):
            self.raw('UPDATE REGISTER_METADATA SET recovery_required=2')
        with self.assertRaises(sqlite3.Error):
            self.raw('UPDATE REGISTER_METADATA SET register_id=NULL')
        values=s._values(self.artifact)
        with self.assertRaises(sqlite3.Error):
            self.raw('INSERT INTO APPROVED_ARTIFACTS VALUES ('+', '.join('?' for _ in values)+')',
                     values[:1]+('INVALID',)+values[2:])

    def test_all_record_type_roundtrips(self):
        self.assertEqual(s._decode(s.MetadataRow,s._values(self.metadata)),self.metadata)
        self.assertEqual(s._decode(s.ReservationRow,s._values(self.reservation)),self.reservation)
        self.assertEqual(s._decode(s.ClaimRow,s._values(self.claim)),self.claim)

    def test_no_overwrite_and_exact_artifact_bytes(self):
        with self.store.transaction() as writer: writer.insert(self.artifact)
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction() as writer:
                writer.insert(replace(self.artifact,exact_bytes=b'changed',sha256=sha256(b'changed').digest()))
        self.assertEqual(self.store.read_rows(s.ArtifactRow),(self.artifact,))

    def test_durable_malformed_key_and_relational_state(self):
        self.populate()
        self.raw('UPDATE BLOCKING_CLAIMS SET canonical_key=?',(b'malformed',))
        with self.assertRaises(s.StorageRejected): s.LeaseStore(self.path,'synthetic-register')

    def test_quarantine_retains_claims(self):
        with self.store.transaction() as writer:
            writer.insert(self.artifact)
            writer.insert(replace(self.reservation,lease_status=c.LeaseStatus.QUARANTINED,
                                 quarantine_reason=s.QuarantineReason.EXECUTION_UNCERTAIN))
            writer.insert(self.claim)
        self.assertEqual(self.store.read_rows(s.ClaimRow),(self.claim,))

    def test_disk_full_suspends_handle_without_retry(self):
        # Real bounded SQLite limit on this disposable register, no fault hooks.
        pages = self.store._connection.execute('PRAGMA page_count').fetchone()[0]
        self.store._connection.execute('PRAGMA max_page_count=' + str(pages + 1))
        payload = b'x' * s.MAX_BYTES
        row = replace(self.artifact, exact_bytes=payload, sha256=sha256(payload).digest())
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction() as writer: writer.insert(row)
        self.assertIsNone(writer.result)
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction(): self.fail('suspended handle retried')

    def test_commit_failure_suspends_and_does_not_claim_rollback(self):
        # A genuine shared reader blocks DELETE-journal COMMIT, with timeout zero.
        reader = sqlite3.connect(self.path, isolation_level=None, timeout=0)
        try:
            reader.execute('BEGIN')
            reader.execute('SELECT register_id FROM REGISTER_METADATA').fetchall()
            with self.assertRaises(s.StorageOutcomeUncertain):
                with self.store.transaction() as writer: writer.insert(self.artifact)
            self.assertIsNone(writer.result)
            with self.assertRaises(s.StorageRejected):
                with self.store.transaction(): self.fail('uncertain handle retried')
        finally:
            reader.execute('ROLLBACK')
            reader.close()

    def test_architecture_boundary(self):
        tree=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_store.py').read_text())
        imports={node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)}
        self.assertEqual(imports,{'contextlib','dataclasses','enum','hashlib','pathlib','fixture_lease_contract',None})
        self.assertEqual([(n.level, tuple((a.name,a.asname) for a in n.names)) for n in ast.walk(tree)
                          if isinstance(n,ast.ImportFrom) and n.module is None],
                         [(1,(('fixture_lease_commands','commands'),))])
        self.assertEqual({alias.name for node in ast.walk(tree) if isinstance(node,ast.Import)
                          for alias in node.names},{'sqlite3'})
        for forbidden in ('dispatch','replay','acquire','advance','release','recover','initialize'):
            self.assertFalse(hasattr(self.store,forbidden))
        self.assertEqual(len(s.SPECS),6)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='jous-b-cleanup-')
        self.path = Path(self.directory.name) / 'disposable.sqlite'
        synthetic_database(self.path)
        self.store = s.LeaseStore(self.path, 'synthetic-register')

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def test_begin_success_then_interruption_has_owned_cleanup(self):
        for error in (KeyboardInterrupt, SystemExit, RuntimeError):
            connection = self.store._connection
            calls = []
            class Interrupted:
                def __getattr__(inner, name): return getattr(connection, name)
                def execute(inner, sql, *args):
                    calls.append(sql)
                    cursor = connection.execute(sql, *args)
                    if sql == 'BEGIN IMMEDIATE': raise error('after successful BEGIN')
                    return cursor
            self.store._connection = Interrupted()
            try:
                with self.assertRaises(error):
                    with self.store.transaction(): self.fail('body entered')
                self.assertFalse(connection.in_transaction)
                self.assertEqual(calls.count('ROLLBACK'), 1)
                self.assertIsNone(self.store._writer)
                self.assertFalse(self.store._poisoned)
            finally:
                self.store._connection = connection

    def test_writer_construction_failure_rolls_back_once(self):
        with patch.object(s, 'TransactionWriter', side_effect=KeyboardInterrupt('construction')):
            with self.assertRaises(KeyboardInterrupt):
                with self.store.transaction(): self.fail('body')
        self.assertFalse(self.store._connection.in_transaction)
        self.assertIsNone(self.store._writer)

    def test_writer_install_failure_rolls_back_once(self):
        setter = s.LeaseStore.__setattr__
        def install(owner, name, value):
            if name == '_writer' and value is not None: raise SystemExit('installation')
            setter(owner, name, value)
        with patch.object(s.LeaseStore, '__setattr__', install):
            with self.assertRaises(SystemExit):
                with self.store.transaction(): self.fail('body')
        self.assertFalse(self.store._connection.in_transaction)
        self.assertIsNone(self.store._writer)

    def test_rollback_return_without_inactive_state_is_unknown(self):
        connection = self.store._connection
        calls = []
        class NoRollback:
            def __getattr__(inner, name): return getattr(connection, name)
            def execute(inner, sql, *args):
                calls.append(sql)
                if sql == 'ROLLBACK': return None
                return connection.execute(sql, *args)
        self.store._connection = NoRollback()
        with self.assertRaises(s.StorageOutcomeUncertain):
            with self.store.transaction(): raise ValueError('body')
        self.assertTrue(self.store._poisoned)
        self.assertEqual(calls.count('ROLLBACK'), 1)
        self.assertIsNone(self.store._writer)
        connection.execute('ROLLBACK')

    def test_state_observation_failure_poisoned(self):
        connection = self.store._connection
        class LostState:
            def __getattr__(inner, name):
                if name == 'in_transaction': raise RuntimeError('state unavailable')
                return getattr(connection, name)
        self.store._connection = LostState()
        with self.assertRaises(s.StorageOutcomeUncertain):
            with self.store.transaction(): raise KeyboardInterrupt()
        self.assertTrue(self.store._poisoned)
        connection.execute('ROLLBACK')

    def test_cursor_cleanup_uncertainty_still_attempts_rollback_once(self):
        calls = []
        class BrokenCursor:
            def close(inner):
                calls.append('close')
                raise RuntimeError('cursor close uncertain')
        with self.assertRaises(s.StorageOutcomeUncertain):
            with self.store.transaction() as writer:
                writer._cursors.append(BrokenCursor())
        self.assertEqual(calls, ['close'])
        self.assertFalse(self.store._connection.in_transaction)
        self.assertTrue(self.store._poisoned)
        self.assertIsNone(self.store._writer)

    def test_sealing_guards_insert_and_partial_generator_before_fetch(self):
        with self.assertRaises(s.StorageRejected), self.store.transaction() as writer:
            iterator = writer.iter_rows(s.MetadataRow)
            next(iterator)
            cursor = writer._cursors[0]
            writer._close_cursors()
            writer._sealed = True
            with self.assertRaises(s.StorageRejected): writer.insert(None)
            # A closed cursor would raise ProgrammingError if advanced first.
            with self.assertRaises(s.StorageRejected): next(iterator)
            with self.assertRaises(s.StorageRejected): writer.lookup(s.MetadataRow, 1)
            self.assertEqual(writer._cursors, [])


class FixedCursorTests(unittest.TestCase):
    setUp = StoreTests.setUp
    tearDown = StoreTests.tearDown
    populate = StoreTests.populate

    def intercept(self, prefix, *, zero=False, close_failure=False, malformed=False, fetch_failure=False):
        connection = self.store._connection
        calls, closes = [], []
        class Cursor:
            def __init__(inner, cursor): inner.cursor = cursor
            def __getattr__(inner, name): return getattr(inner.cursor, name)
            @property
            def rowcount(inner): return 0 if zero else inner.cursor.rowcount
            def fetchall(inner):
                if fetch_failure: raise ValueError('injected fetch failure')
                return inner.cursor.fetchall()
            def fetchmany(inner, count):
                rows = inner.cursor.fetchmany(count)
                return rows * 2 if malformed else rows
            def close(inner):
                closes.append(prefix)
                inner.cursor.close()
                if close_failure: raise RuntimeError('injected cursor-close failure')
        class Connection:
            def __getattr__(inner, name): return getattr(connection, name)
            def execute(inner, sql, *args):
                calls.append(sql)
                cursor = connection.execute(sql, *args)
                return Cursor(cursor) if sql.startswith(prefix) else cursor
        self.store._connection = Connection()
        return connection, calls, closes

    def write_failure(self, kind, zero, close_failure):
        self.populate()
        prefix = {'reservation': 'UPDATE RESERVATIONS', 'claim': 'DELETE FROM BLOCKING_CLAIMS',
                  'metadata': 'UPDATE REGISTER_METADATA'}[kind]
        connection, calls, closes = self.intercept(prefix, zero=zero, close_failure=close_failure)
        expected = s.StorageOutcomeUncertain if close_failure else s.StorageRejected
        with self.assertRaises(expected):
            with self.store.transaction() as writer:
                # With both errors, preserve the primary primitive rejection
                # until transaction cleanup observes sticky close uncertainty.
                with self.assertRaises(s.StorageRejected if zero else RuntimeError):
                    if kind == 'reservation':
                        writer.replace_reservation(self.reservation, replace(self.reservation, revision=1))
                    elif kind == 'claim': writer.delete_claim(self.claim)
                    else: writer.complete_metadata(self.metadata, replace(self.metadata, last_valid_utc=2))
                if close_failure: self.assertTrue(self.store._cursor_close_failed)
        self.assertEqual(closes, [prefix])
        self.assertEqual(calls.count('ROLLBACK'), 1)
        self.assertNotIn('COMMIT', calls)
        self.assertFalse(connection.in_transaction)
        self.assertEqual(self.store._poisoned, close_failure)

    def test_lookup_success_closes_once(self):
        connection, calls, closes = self.intercept('SELECT singleton,')
        with self.store.transaction() as writer:
            self.assertEqual(writer.lookup(s.MetadataRow, 1), self.metadata)
            self.assertEqual(closes, ['SELECT singleton,'])
        self.assertEqual(calls.count('COMMIT'), 1)
        self.assertFalse(connection.in_transaction)

    def test_lookup_semantic_rejection_and_close_failure_are_both_retained(self):
        connection, calls, closes = self.intercept('SELECT singleton,', malformed=True, close_failure=True)
        with self.assertRaises(s.StorageOutcomeUncertain):
            with self.store.transaction() as writer:
                with self.assertRaises(s.StorageRejected): writer.lookup(s.MetadataRow, 1)
                self.assertTrue(self.store._cursor_close_failed)
        self.assertEqual(len(closes), 1)
        self.assertEqual(calls.count('ROLLBACK'), 1)
        self.assertNotIn('COMMIT', calls)
        self.assertTrue(self.store._poisoned)
        self.assertFalse(connection.in_transaction)

    def test_fixed_query_close_failure_cannot_be_swallowed_into_clean_commit(self):
        connection, calls, closes = self.intercept('SELECT 1', close_failure=True)
        with self.assertRaises(s.StorageOutcomeUncertain):
            with self.store.transaction():
                with self.assertRaises(RuntimeError):
                    s._query(self.store._connection, 'SELECT 1', cleanup=self.store)
                self.assertTrue(self.store._cursor_close_failed)
        self.assertEqual(len(closes), 1)
        self.assertEqual(calls.count('ROLLBACK'), 1)
        self.assertNotIn('COMMIT', calls)
        self.assertTrue(self.store._poisoned)
        self.assertFalse(connection.in_transaction)

    def test_fixed_query_fetch_rejection_still_closes(self):
        connection, calls, closes = self.intercept('SELECT 1', fetch_failure=True)
        with self.assertRaisesRegex(ValueError, 'injected fetch failure'):
            with self.store.transaction():
                s._query(self.store._connection, 'SELECT 1', cleanup=self.store)
        self.assertEqual(len(closes), 1)
        self.assertEqual(calls.count('ROLLBACK'), 1)
        self.assertNotIn('COMMIT', calls)
        self.assertFalse(self.store._poisoned)
        self.assertFalse(connection.in_transaction)

    def test_profile_fixed_query_close_failure_is_sticky_before_writer_install(self):
        connection, calls, closes = self.intercept('PRAGMA journal_mode', close_failure=True)
        with self.assertRaises(s.StorageOutcomeUncertain):
            with self.store.transaction(): self.fail('body entered')
        self.assertEqual(len(closes), 1)
        self.assertNotIn('BEGIN IMMEDIATE', calls)
        self.assertNotIn('COMMIT', calls)
        self.assertTrue(self.store._poisoned)
        self.assertFalse(connection.in_transaction)

    def test_final_register_fixed_query_close_failure_blocks_commit(self):
        connection, calls, closes = self.intercept('PRAGMA integrity_check', close_failure=True)
        with self.assertRaises(s.StorageOutcomeUncertain):
            with self.store.transaction(): pass
        self.assertEqual(len(closes), 1)
        self.assertEqual(calls.count('ROLLBACK'), 1)
        self.assertNotIn('COMMIT', calls)
        self.assertTrue(self.store._poisoned)
        self.assertFalse(connection.in_transaction)

    def test_insert_close_failure_is_sticky(self):
        connection, calls, closes = self.intercept('INSERT INTO APPROVED_ARTIFACTS', close_failure=True)
        with self.assertRaises(s.StorageOutcomeUncertain):
            with self.store.transaction() as writer: writer.insert(self.artifact)
        self.assertEqual(len(closes), 1)
        self.assertEqual(calls.count('ROLLBACK'), 1)
        self.assertNotIn('COMMIT', calls)
        self.assertTrue(self.store._poisoned)
        self.assertFalse(connection.in_transaction)

    def test_begin_result_close_failure_rolls_back_once_and_poisoned(self):
        connection, calls, closes = self.intercept('BEGIN IMMEDIATE', close_failure=True)
        with self.assertRaises(s.StorageOutcomeUncertain):
            with self.store.transaction(): self.fail('body entered')
        self.assertEqual(len(closes), 1)
        self.assertEqual(calls.count('ROLLBACK'), 1)
        self.assertNotIn('COMMIT', calls)
        self.assertTrue(self.store._poisoned)
        self.assertFalse(connection.in_transaction)

    def test_rollback_result_close_failure_has_no_second_attempt(self):
        connection, calls, closes = self.intercept('ROLLBACK', close_failure=True)
        with self.assertRaises(s.StorageOutcomeUncertain):
            with self.store.transaction(): raise ValueError('primary body rejection')
        self.assertEqual(len(closes), 1)
        self.assertEqual(calls.count('ROLLBACK'), 1)
        self.assertTrue(self.store._poisoned)
        self.assertFalse(connection.in_transaction)

    def test_confirmed_commit_close_failure_is_not_unknown_commit(self):
        connection, calls, closes = self.intercept('COMMIT', close_failure=True)
        with self.assertRaises(s.StorageRejected) as caught:
            with self.store.transaction() as writer: pass
        self.assertIs(type(caught.exception), s._ConfirmedCommitCleanup)
        self.assertIs(caught.exception.storage_result, s.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        self.assertIs(caught.exception.reason, s._CommitCleanupReason.CURSOR_CLOSE)
        self.assertNotIsInstance(caught.exception, s.StorageOutcomeUncertain)
        self.assertIs(writer.result, s.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        self.assertEqual(len(closes), 1)
        self.assertEqual(calls.count('COMMIT'), 1)
        self.assertNotIn('ROLLBACK', calls)
        self.assertTrue(self.store._poisoned)
        self.assertFalse(connection.in_transaction)


def fixed_write_case(kind, zero, close_failure):
    def test(self): self.write_failure(kind, zero, close_failure)
    suffix = 'zero_and_close_failure' if zero and close_failure else ('zero' if zero else 'close_failure')
    setattr(FixedCursorTests, 'test_' + kind + '_' + suffix, test)


for _kind in ('reservation', 'claim', 'metadata'):
    for _zero, _close_failure in ((True, False), (False, True), (True, True)):
        fixed_write_case(_kind, _zero, _close_failure)


if __name__ == '__main__':
    unittest.main(verbosity=2)
