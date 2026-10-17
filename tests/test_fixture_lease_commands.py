"""IL.4B disposable synthetic SQLite only; no operational authority or register."""
import ast
from dataclasses import fields, replace
from hashlib import sha256
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = '_il4b_synthetic'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / 'services/api/infrastructure')]
sys.modules[PACKAGE] = package
for name in ('fixture_lease_contract', 'fixture_lease_protocol', 'fixture_lease_store', 'fixture_lease_service', 'fixture_lease_commands'):
    spec = importlib.util.spec_from_file_location(PACKAGE + '.' + name,
        ROOT / 'services/api/infrastructure' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    if name == 'fixture_lease_contract':
        sys.modules[name] = module  # IL.3's frozen top-level contract import.
    spec.loader.exec_module(module)
c = sys.modules[PACKAGE + '.fixture_lease_contract']
p = sys.modules[PACKAGE + '.fixture_lease_protocol']
s = sys.modules[PACKAGE + '.fixture_lease_store']
core = sys.modules[PACKAGE + '.fixture_lease_commands']


def command_import_boundary(tree):
    expected={
        (0,'dataclasses',( ('dataclass',None),('fields',None),('replace',None) )),
        (0,'hashlib',( ('sha256',None), )),
        (0,'types',( ('FunctionType',None),('MethodType',None) )),
        (1,None,( ('fixture_lease_protocol','p'), )),
        (1,None,( ('fixture_lease_store','s'), )),
        (1,None,( ('fixture_lease_service','service'), )),
        (1,None,( ('fixture_lease_admission_qualification','qualification_values'), )),
    }
    observed=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):return False
        if isinstance(node,ast.ImportFrom):
            observed.append((node.level,node.module,tuple((a.name,a.asname) for a in node.names)))
    return len(observed)==len(expected) and set(observed)==expected


class CommandsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='jous-synthetic-il4b-')
        self.path = Path(self.directory.name) / 'disposable.sqlite'
        self.context = p.StateContext(p.STATE_2, 'g', 1, 'x')
        projection = p.StateProjection(p.MetadataRow(1, 1, 'g', 1, 'x', *([b'q'*32]*4), 0, 0), (), (), ())
        metadata = s.MetadataRow(1, 1, 'g', 1, 'x', *([b'q'*32]*4), 0,
            p.GENESIS_EVENT_DIGEST, p.state_digest(projection, self.context), 0, 0)
        self.binding = self.artifact('binding', c.ArtifactType.PROVISIONING_REQUEST)
        self.authorization = self.artifact('authorization', c.ArtifactType.AUTHORIZATION)
        self.evidence = self.artifact('evidence', c.ArtifactType.PROVENANCE_EVIDENCE)
        self.release_evidence = self.artifact('release', c.ArtifactType.RELEASE_EVIDENCE)
        self.recovery_evidence = self.artifact('recovery', c.ArtifactType.RECOVERY_EVIDENCE)
        connection = sqlite3.connect(self.path, isolation_level=None)
        connection.executescript(s.SCHEMA_SQL)
        for row in (metadata, self.binding, self.authorization, self.evidence,
                    self.release_evidence, self.recovery_evidence):
            table = s.SPECS[type(row)][0]
            values = s._values(row)
            connection.execute('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in values)+')', values)
        connection.close()
        self.store = s.LeaseStore(self.path, 'g')
        self.command, self.material = self.acquire()

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def artifact(self, name, kind):
        raw, approval = ('artifact-'+name).encode(), ('approval-'+name).encode()
        return s.ArtifactRow(name, kind, raw, sha256(raw).digest(), approval,
            sha256(approval).digest(), 'approver', 'authorization',
            c.Operation.FIXTURE_PROVISIONING, c.Phase.PRE_AUTH, None)

    def ref(self, artifact):
        return p.Reference(artifact.artifact_id, artifact.artifact_type, artifact.sha256)

    def acquire(self, command_id='create', reservation_id='r', key_id='s'):
        params = p.Parameters(reservation_id, None, self.ref(self.binding), None, None, (), 100, 90, None)
        command = p.CommandPayload(c.Command.ACQUIRE, 'owner', 'g', 1, 'x', command_id, '', 0,
            c.Operation.FIXTURE_PROVISIONING, c.Phase.PRE_AUTH, self.binding.artifact_type,
            self.binding.sha256, key_id, self.ref(self.binding), self.binding.approval_record_hash,
            self.ref(self.authorization), (), params)
        raw = b'immutable-db-projection'
        row = s.ReservationRow(reservation_id, 'g', key_id, c.Operation.FIXTURE_PROVISIONING,
            c.Phase.PRE_AUTH, self.binding.artifact_type, self.binding.artifact_id,
            self.binding.sha256, raw, sha256(raw).digest(), 'owner', 'authorization',
            0, 0, 0, 100, 90, 0, c.LeaseStatus.LEASED, 0, s.ExecutionState.NOT_STARTED, None, None, None)
        key = c.ConflictKey.fixture_set(c.DatabaseTargetScope('g'), key_id).canonical_bytes
        claim = s.ClaimRow(key, reservation_id, 0, self.binding.artifact_id)
        return command, core.PreparedTransition(row, (claim,), (), 0, 0)

    def execute(self, command=None, material=None):
        return core.complete(self.store, self.command if command is None else command,
                             self.context, self.material if material is None else material)

    def mutate(self, command_id='mutate', expected=None):
        row = self.store.read_rows(s.ReservationRow)[0]
        revision = row.revision if expected is None else expected
        refs = (self.ref(self.evidence),)
        command = replace(self.command, command_kind=c.Command.RECORD_EXECUTION,
            command_id=command_id, reservation_id='r', expected_revision=revision,
            approval_record_hash=self.evidence.approval_record_hash, evidence_references=refs,
            parameters=p.Parameters('r', None, None, p.ExecutionState.STARTED, None,
                                    refs, None, None, refs[0]))
        material = core.PreparedTransition(replace(row, revision=revision+1,
            execution_state=s.ExecutionState.STARTED), (), (), 1, 1)
        return command, material

    def raw(self, sql, parameters=()):
        connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def snapshot(self):
        return {name: self.raw('SELECT * FROM '+name+' ORDER BY 1') for name in
            ('REGISTER_METADATA','APPROVED_ARTIFACTS','RESERVATIONS','BLOCKING_CLAIMS','COMMANDS','EVENTS')}

    def reject_without_change(self, command, material, error=Exception):
        before = self.snapshot()
        with self.assertRaises(error):
            self.execute(command, material)
        self.assertEqual(before, self.snapshot())

    def test_create_revision_zero_and_exact_payload(self):
        result = self.execute()
        self.assertEqual(result.outcome, p.OutcomeCode.SUCCESS)
        self.assertEqual(result.storage_result, s.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        self.assertFalse(result.replayed)
        self.assertEqual(self.store.read_rows(s.ReservationRow)[0].revision, 0)
        row = self.store.read_rows(s.CommandRow)[0]
        self.assertEqual(row.canonical_payload_bytes, p.command_bytes(self.command))
        self.assertEqual(row.canonical_payload_hash, p.command_digest(self.command))
        self.assertEqual(row.durable_ack_bytes, result.retained_ack_bytes)

    def test_create_requires_absence_no_upsert(self):
        self.execute()
        self.reject_without_change(replace(self.command, command_id='duplicate-target'), self.material,
                                   core.CommandRejected)

    def test_first_and_later_mutation_exact_revision(self):
        self.execute()
        command, material = self.mutate()
        self.execute(command, material)
        self.assertEqual(self.store.read_rows(s.ReservationRow)[0].revision, 1)
        command, material = self.mutate('later')
        self.execute(command, material)
        self.assertEqual(self.store.read_rows(s.ReservationRow)[0].revision, 2)

    def test_mutation_requires_existing_target(self):
        refs=(self.ref(self.evidence),)
        command=replace(self.command, command_kind=c.Command.RECORD_EXECUTION,
            reservation_id='r', evidence_references=refs, approval_record_hash=self.evidence.approval_record_hash,
            parameters=p.Parameters('r',None,None,p.ExecutionState.STARTED,None,refs,None,None,refs[0]))
        self.reject_without_change(command, replace(self.material, reservation=replace(
            self.material.reservation, revision=1)), core.CommandRejected)

    def test_stale_revision_rejects(self):
        self.execute()
        command, material = self.mutate(expected=1)
        self.reject_without_change(command, material, core.CommandRejected)

    def test_create_nonzero_expected_revision_rejects(self):
        self.reject_without_change(replace(self.command, expected_revision=1), self.material, p.ProtocolRejected)

    def test_exact_replay_no_writes(self):
        original = self.execute()
        before = self.snapshot()
        result = core.complete(self.store, self.command, self.context)
        self.assertTrue(result.replayed)
        self.assertEqual(result.retained_ack_bytes, original.retained_ack_bytes)
        self.assertEqual(before, self.snapshot())

    def test_replay_after_later_mutation_ignores_current_revision(self):
        original = self.execute()
        command, material = self.mutate()
        self.execute(command, material)
        before = self.snapshot()
        replay = core.complete(self.store, self.command, self.context)
        self.assertEqual(replay.retained_ack_bytes, original.retained_ack_bytes)
        self.assertEqual(before, self.snapshot())

    def test_replay_after_unrelated_command(self):
        original = self.execute()
        command, material = self.acquire('other', 'other-r', 'other-s')
        self.execute(command, material)
        before = self.snapshot()
        self.assertEqual(core.complete(self.store,self.command,self.context).retained_ack_bytes,
                         original.retained_ack_bytes)
        self.assertEqual(before,self.snapshot())

    def test_replay_mismatch_changed_payload(self):
        self.execute()
        command=replace(self.command,parameters=replace(self.command.parameters,proposed_expires_at=99))
        before=self.snapshot()
        result=self.execute(command)
        self.assertEqual(result.outcome,p.OutcomeCode.REPLAY_MISMATCH)
        self.assertIsNone(result.retained_ack_bytes)
        self.assertEqual(before,self.snapshot())
        self.assertEqual(len(self.store.read_rows(s.CommandRow)),1)

    def test_replay_mismatch_changed_principal(self):
        self.execute()
        before=self.snapshot()
        result=self.execute(replace(self.command,authenticated_principal='other'))
        self.assertEqual(result.outcome,p.OutcomeCode.REPLAY_MISMATCH)
        self.assertEqual(before,self.snapshot())

    def test_replay_mismatch_changed_expected_revision(self):
        self.execute()
        command,material=self.mutate()
        self.execute(command,material)
        before=self.snapshot()
        result=self.execute(replace(command,expected_revision=1),material)
        self.assertEqual(result.outcome,p.OutcomeCode.REPLAY_MISMATCH)
        self.assertIsNone(result.retained_ack_bytes)
        self.assertEqual(before,self.snapshot())

    def test_hash_only_equality_insufficient(self):
        self.execute()
        command=replace(self.command,parameters=replace(self.command.parameters,proposed_expires_at=99))
        altered=p.command_bytes(command)
        original_hash=p.command_digest(self.command)
        class Collision:
            def digest(self): return original_hash
        def fake(data): return Collision() if data==altered else sha256(data)
        before=self.snapshot()
        with patch.object(core,'sha256',side_effect=fake):
            result=self.execute(command)
        self.assertEqual(result.outcome,p.OutcomeCode.REPLAY_MISMATCH)
        self.assertEqual(before,self.snapshot())

    def test_claim_conflict_full_key_rejects_without_adoption(self):
        self.execute()
        command,material=self.acquire('conflict','another-r','s')
        self.reject_without_change(command,material,s.StorageRejected)

    def test_unsupported_representation_no_fallback(self):
        before=self.snapshot()
        for value in (p.STATE_1,'unknown'):
            with self.assertRaises(core.CommandRejected):
                core.complete(self.store,self.command,replace(self.context,representation=value),self.material)
        self.assertEqual(before,self.snapshot())

    def test_state_digest_deterministic_across_reopen(self):
        self.execute()
        metadata=self.store.read_rows(s.MetadataRow)[0]
        self.store.close()
        self.store=s.LeaseStore(self.path,'g')
        self.assertEqual(metadata,self.store.read_rows(s.MetadataRow)[0])
        self.assertTrue(core.complete(self.store,self.command,self.context).replayed)

    def test_state_tamper_rejects(self):
        self.execute()
        self.raw('UPDATE REGISTER_METADATA SET state_digest=?',(b'!'*32,))
        self.reject_without_change(self.command,self.material,p.ProtocolRejected)

    def test_head_tamper_rejects(self):
        self.execute()
        self.raw('UPDATE REGISTER_METADATA SET last_event_digest=?',(b'!'*32,))
        self.reject_without_change(self.command,self.material,core.CommandRejected)

    def test_event_bytes_tamper_rejects(self):
        self.execute()
        self.raw('UPDATE EVENTS SET event_bytes=? WHERE event_sequence=2',(b'invalid',))
        self.reject_without_change(self.command,self.material,p.ProtocolRejected)

    def test_event_digest_and_prior_chain_tamper_rejects(self):
        self.execute()
        self.raw('UPDATE EVENTS SET prior_digest=? WHERE event_sequence=2',(b'!'*32,))
        self.reject_without_change(self.command,self.material,core.CommandRejected)

    def test_busy_begin_no_retry(self):
        connection=sqlite3.connect(self.path,isolation_level=None)
        connection.execute('BEGIN IMMEDIATE')
        try:
            with self.assertRaises(s.StorageRejected): self.execute()
        finally:
            connection.execute('ROLLBACK')
            connection.close()
        self.assertEqual(self.store.read_rows(s.CommandRow),())

    def test_locked_begin_no_retry(self):
        connection=self.store._connection
        calls=[]
        class Locked:
            def __getattr__(self,name): return getattr(connection,name)
            def execute(self,sql,*args):
                calls.append(sql)
                if sql=='BEGIN IMMEDIATE':
                    error=sqlite3.OperationalError('synthetic locked')
                    error.sqlite_errorcode=sqlite3.SQLITE_LOCKED
                    raise error
                return connection.execute(sql,*args)
        self.store._connection=Locked()
        before=self.snapshot()
        with self.assertRaises(s.StorageRejected): self.execute()
        self.assertEqual(calls.count('BEGIN IMMEDIATE'),1)
        self.assertFalse(self.store._poisoned)
        self.assertEqual(before,self.snapshot())

    def test_explicit_snapshot_byte_order_and_writer_lifetime(self):
        with self.store.transaction() as writer:
            identifiers=['z-artifact','a-artifact','ÃƒÆ’Ã‚Â©-artifact']
            for name in identifiers: writer.insert(self.artifact(name,c.ArtifactType.PROVENANCE_EVIDENCE))
            rows=tuple(writer.iter_rows(s.ArtifactRow))
            self.assertEqual([row.artifact_id.encode() for row in rows],
                             sorted(row.artifact_id.encode() for row in rows))
        with self.assertRaises(s.StorageRejected): writer.lookup(s.MetadataRow,1)
        with self.assertRaises(s.StorageRejected): tuple(writer.iter_rows(s.CommandRow))

    def test_failure_after_begin_before_mutation(self):
        before=self.snapshot()
        with patch.object(core,'_transition',side_effect=core.CommandRejected('synthetic')):
            with self.assertRaises(core.CommandRejected): self.execute()
        self.assertEqual(before,self.snapshot())

    def test_failure_after_reservation_and_claim_mutation(self):
        before=self.snapshot()
        with patch.object(core,'_append',side_effect=core.CommandRejected('synthetic')):
            with self.assertRaises(core.CommandRejected): self.execute()
        self.assertEqual(before,self.snapshot())

    def test_failure_after_event_insert(self):
        before=self.snapshot()
        original=s.TransactionWriter.insert
        def fail(writer,row):
            original(writer,row)
            if type(row) is s.EventRow: raise core.CommandRejected('synthetic')
        with patch.object(s.TransactionWriter,'insert',fail):
            with self.assertRaises(core.CommandRejected): self.execute()
        self.assertEqual(before,self.snapshot())

    def test_failure_after_command_insert(self):
        before=self.snapshot()
        with patch.object(s.TransactionWriter,'complete_metadata',side_effect=core.CommandRejected('synthetic')):
            with self.assertRaises(core.CommandRejected): self.execute()
        self.assertEqual(before,self.snapshot())

    def test_failure_during_resulting_state_digest(self):
        before=self.snapshot()
        original=p.state_digest
        calls=0
        def fail(projection,context):
            nonlocal calls
            calls+=1
            if calls==2: raise p.ProtocolRejected('synthetic')
            return original(projection,context)
        with patch.object(p,'state_digest',side_effect=fail):
            with self.assertRaises(p.ProtocolRejected): self.execute()
        self.assertEqual(before,self.snapshot())

    def test_commit_uncertainty_busy_is_diagnostic_and_poisoned(self):
        reader=sqlite3.connect(self.path,isolation_level=None,timeout=0)
        reader.execute('BEGIN')
        reader.execute('SELECT * FROM REGISTER_METADATA').fetchall()
        try:
            result=self.execute()
            self.assertEqual(result.outcome,p.OutcomeCode.STORAGE_UNKNOWN)
            self.assertIsNone(result.retained_ack_bytes)
            self.assertIsNone(result.storage_result)
            self.assertTrue(self.store._poisoned)
            with self.assertRaises(s.StorageRejected): self.execute()
        finally:
            reader.execute('ROLLBACK')
            reader.close()
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'),[(0,)])

    def test_commit_ack_lost_no_success_or_retry(self):
        connection=self.store._connection
        calls=[]
        class LostAck:
            def __getattr__(self,name): return getattr(connection,name)
            def execute(self,sql,*args):
                calls.append(sql)
                result=connection.execute(sql,*args)
                if sql=='COMMIT': raise sqlite3.OperationalError('synthetic lost commit acknowledgement')
                return result
        self.store._connection=LostAck()
        result=self.execute()
        self.assertEqual(result.outcome,p.OutcomeCode.STORAGE_UNKNOWN)
        self.assertIsNone(result.retained_ack_bytes)
        self.assertTrue(self.store._poisoned)
        self.assertEqual(calls.count('COMMIT'),1)
        self.assertNotIn('ROLLBACK',calls)
        # The durable SUCCESS really exists in this injection: UNKNOWN must not
        # become a durable diagnostic row or an assertion that rollback occurred.
        self.assertEqual(self.raw('SELECT outcome_code FROM COMMANDS'),[('SUCCESS',)])
        with self.assertRaises(s.StorageRejected): self.execute()

    def test_rollback_failure_poisoned_unknown(self):
        connection=self.store._connection
        calls=[]
        class RollbackFailure:
            def __getattr__(self,name): return getattr(connection,name)
            def execute(self,sql,*args):
                calls.append(sql)
                if sql=='ROLLBACK': raise sqlite3.OperationalError('synthetic rollback failure')
                return connection.execute(sql,*args)
        self.store._connection=RollbackFailure()
        with patch.object(core,'_append',side_effect=core.CommandRejected('synthetic')):
            result=self.execute()
        self.assertEqual(result.outcome,p.OutcomeCode.STORAGE_UNKNOWN)
        self.assertIsNone(result.retained_ack_bytes)
        self.assertTrue(self.store._poisoned)
        self.assertEqual(calls.count('ROLLBACK'),1)
        self.assertNotIn('COMMIT',calls)
        with self.assertRaises(s.StorageRejected): self.execute()

    def test_success_not_returned_before_commit_confirmation(self):
        connection=self.store._connection
        calls=[]
        class CommitFailure:
            def __getattr__(self,name): return getattr(connection,name)
            def execute(self,sql,*args):
                calls.append(sql)
                if sql=='COMMIT': raise sqlite3.OperationalError('synthetic pre-commit failure')
                return connection.execute(sql,*args)
        self.store._connection=CommitFailure()
        result=self.execute()
        self.assertEqual(result.outcome,p.OutcomeCode.STORAGE_UNKNOWN)
        self.assertIsNone(result.retained_ack_bytes)
        self.assertEqual(calls.count('COMMIT'),1)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'),[(0,)])

    def test_metadata_update_failure_rolls_back_all_effects(self):
        before=self.snapshot()
        original=s.TransactionWriter.complete_metadata
        calls=0
        def fail(writer,expected,replacement):
            nonlocal calls
            calls+=1
            if calls==2: raise core.CommandRejected('synthetic final metadata failure')
            return original(writer,expected,replacement)
        with patch.object(s.TransactionWriter,'complete_metadata',fail):
            with self.assertRaises(core.CommandRejected): self.execute()
        self.assertEqual(before,self.snapshot())

    def test_malformed_payload_and_missing_ack_reject(self):
        self.execute()
        before=self.snapshot()
        self.raw('UPDATE COMMANDS SET canonical_payload_bytes=?,canonical_payload_hash=?',
                 (b'malformed',sha256(b'malformed').digest()))
        with self.assertRaises(p.ProtocolRejected): self.execute()
        # Restore only inside this disposable corruption fixture.
        self.raw('UPDATE COMMANDS SET canonical_payload_bytes=?,canonical_payload_hash=?',
                 (p.command_bytes(self.command),p.command_digest(self.command)))
        self.assertEqual(before,self.snapshot())
        connection=sqlite3.connect(self.path,isolation_level=None)
        connection.execute('PRAGMA ignore_check_constraints=ON')
        connection.execute('UPDATE COMMANDS SET durable_ack_bytes=NULL')
        connection.close()
        with self.assertRaises(s.StorageRejected): self.execute()

    def test_ack_event_interval_tamper_even_with_recomputed_state(self):
        self.execute()
        row=self.store.read_rows(s.CommandRow)[0]
        ack=p.decode_record(row.durable_ack_bytes,p.AckPayload)
        # A well-framed but incorrect ACK endpoint is not a valid completion.
        bad=p.ack_bytes(replace(ack,first_event_sequence=2,event_count=2))
        with self.store.transaction() as writer:
            # SQL corruption is test-only; production writer has no SQL escape.
            self.store._connection.execute('UPDATE COMMANDS SET durable_ack_bytes=?',(bad,))
            metadata=writer.lookup(s.MetadataRow,1)
            digest=p.state_digest(core._projection(writer),self.context)
            writer.complete_metadata(metadata,replace(metadata,state_digest=digest))
        self.reject_without_change(self.command,self.material,core.CommandRejected)

    def test_missing_event_rejects_without_replay(self):
        self.execute()
        self.raw('DELETE FROM EVENTS WHERE event_sequence=2')
        self.reject_without_change(self.command,self.material,core.CommandRejected)

    def test_revision_overflow_rejects_without_success(self):
        self.execute()
        with self.store.transaction() as writer:
            self.store._connection.execute('UPDATE RESERVATIONS SET revision=?',(p.MAX_UINT,))
            metadata=writer.lookup(s.MetadataRow,1)
            writer.complete_metadata(metadata,replace(metadata,
                state_digest=p.state_digest(core._projection(writer),self.context)))
        command,material=self.mutate(expected=p.MAX_UINT)
        self.reject_without_change(command,material,core.CommandRejected)

    def test_diagnostic_rows_never_valid_completed_state(self):
        self.execute()
        for outcome in (s.OutcomeCode.REPLAY_MISMATCH,s.OutcomeCode.STORAGE_UNKNOWN):
            self.raw('UPDATE COMMANDS SET outcome_code=?,durable_ack_bytes=NULL',(outcome.value,))
            with self.assertRaises(p.ProtocolRejected): self.execute()
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'),[(1,)])

    def test_expiry_quarantine_supplied_effects_retain_claims(self):
        self.execute()
        refs=(self.ref(self.evidence),)
        command=replace(self.command,command_kind=c.Command.QUARANTINE,command_id='expiry',
            reservation_id='r',evidence_references=refs,approval_record_hash=self.evidence.approval_record_hash,
            parameters=p.Parameters('r',None,None,None,p.QuarantineReason.EXPIRED_UNRECONCILED,
                                    refs,None,None,refs[0]))
        row=replace(self.material.reservation,revision=1,lease_status=c.LeaseStatus.QUARANTINED,
                    expired_condition=1,quarantine_reason=s.QuarantineReason.EXPIRED_UNRECONCILED)
        result=self.execute(command,core.PreparedTransition(row,(),(),101,101,True))
        self.assertEqual(result.outcome,p.OutcomeCode.SUCCESS)
        self.assertEqual([row.event_type.value for row in self.store.read_rows(s.EventRow)[3:]],
                         ['EXPIRED','QUARANTINED','ACKNOWLEDGED'])
        self.assertEqual(len(self.store.read_rows(s.ClaimRow)),1)
        self.assertTrue(core.complete(self.store,command,self.context).replayed)

    def test_release_exact_supplied_claim_deletion(self):
        self.execute()
        refs=(self.ref(self.release_evidence),)
        command=replace(self.command,command_kind=c.Command.RELEASE,command_id='release-command',
            reservation_id='r',evidence_references=refs,approval_record_hash=self.release_evidence.approval_record_hash,
            parameters=p.Parameters('r',None,None,None,None,refs,None,None,refs[0]))
        row=replace(self.material.reservation,revision=1,lease_status=c.LeaseStatus.RELEASED,
                    release_evidence_artifact_id=self.release_evidence.artifact_id)
        material=core.PreparedTransition(row,(),self.material.claim_inserts,1,1)
        result=self.execute(command,material)
        self.assertEqual(self.store.read_rows(s.ClaimRow),())
        ack=p.decode_record(result.retained_ack_bytes,p.AckPayload)
        self.assertEqual(ack.canonical_key_set_digest,p.key_set_digest(()))

    def test_typed_update_and_claim_ownership_checks(self):
        self.execute()
        before=self.snapshot()
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction() as writer:
                writer.delete_claim(replace(self.material.claim_inserts[0],reservation_id='other'))
        self.assertEqual(before,self.snapshot())
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction() as writer:
                row=writer.lookup(s.ReservationRow,'r')
                writer.replace_reservation(row,replace(row,revision=2))
        self.assertEqual(before,self.snapshot())
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction() as writer:
                metadata=writer.lookup(s.MetadataRow,1)
                writer.complete_metadata(metadata,replace(metadata,activation_id='unauthorized'))
        self.assertEqual(before,self.snapshot())

    def test_large_history_streams_and_release_after_4096(self):
        self.execute()
        template,_=self.mutate()
        key_digest=p.key_set_digest((self.material.claim_inserts[0].canonical_key,))
        # Test-only bulk fixture assembly avoids quadratic deferred-FK debt scans.
        # Production opening/transactions still enforce the exact IL.3 FK profile.
        metadata=self.store.read_rows(s.MetadataRow)[0]
        row=self.store.read_rows(s.ReservationRow)[0]
        connection=sqlite3.connect(self.path,isolation_level=None)
        def insert(value):
            table=s.SPECS[type(value)][0]
            values=s._values(value)
            connection.execute('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in values)+')',values)
        try:
            connection.execute('BEGIN IMMEDIATE')
            sequence,prior=metadata.last_event_sequence,metadata.last_event_digest
            for index in range(4096):
                command=replace(template,command_id=f'history-{index:08d}',expected_revision=row.revision)
                next_row=replace(row,revision=row.revision+1,execution_state=s.ExecutionState.STARTED)
                row=next_row
                event_list=[]
                for kind in p.event_order(command.command_kind):
                    sequence+=1
                    event=p.EventPayload(sequence,command.command_id,'r','g',1,'x',kind,1,
                        prior,row.revision,self.binding.artifact_id,self.evidence.artifact_id)
                    raw=p.event_bytes(event)
                    prior=p.event_digest(event)
                    insert(s.EventRow(sequence,command.command_id,'r','g',1,'x',s.EventType(kind),
                        1,event.prior_digest,raw,prior,row.revision,self.binding.artifact_id,self.evidence.artifact_id))
                    event_list.append(event)
                raw=p.command_bytes(command)
                ack=p.AckPayload(command.command_id,sha256(raw).digest(),'owner','g',1,'x','r',row.revision,
                    'owner',command.operation,command.phase,command.binding_kind,command.binding_sha256,
                    key_digest,command.approval_record_hash,command.authorization_reference,
                    command.evidence_references,1,0,100,90,event_list[0].event_sequence,sequence,
                    len(event_list),prior,p.OutcomeCode.SUCCESS)
                insert(s.CommandRow(command.command_id,'owner',s.Command(command.command_kind),raw,
                    sha256(raw).digest(),command.expected_revision,'r',s.OutcomeCode.SUCCESS,p.ack_bytes(ack),sequence))
            connection.execute('UPDATE RESERVATIONS SET revision=?,execution_state=? WHERE reservation_id=?',
                               (row.revision,row.execution_state.value,'r'))
            connection.execute('COMMIT')
        finally:
            connection.close()
        # Full schema/foreign-key/row validation precedes the real completion test.
        self.store.close()
        self.store=s.LeaseStore(self.path,'g')
        with self.store.transaction() as writer:
            projected=replace(metadata,last_valid_utc=1)
            writer.complete_metadata(metadata,projected)
            digest=p.state_digest(core._projection(writer),self.context)
            writer.complete_metadata(projected,replace(projected,last_event_sequence=sequence,
                last_event_digest=prior,state_digest=digest))
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'),[(4097,)])
        refs=(self.ref(self.release_evidence),)
        command=replace(template,command_kind=c.Command.RELEASE,command_id='release-large-history',
            expected_revision=4096,approval_record_hash=self.release_evidence.approval_record_hash,
            evidence_references=refs,parameters=p.Parameters('r',None,None,None,None,refs,None,None,refs[0]))
        released=replace(row,revision=4097,lease_status=c.LeaseStatus.RELEASED,
                         release_evidence_artifact_id=self.release_evidence.artifact_id)
        with patch.object(p,'state_chunks',wraps=p.state_chunks) as streaming:
            result=self.execute(command,core.PreparedTransition(released,(),self.material.claim_inserts,2,2))
        self.assertEqual(result.outcome,p.OutcomeCode.SUCCESS)
        self.assertGreaterEqual(streaming.call_count,2)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'),[(4098,)])
        self.assertEqual(self.store.read_rows(s.ClaimRow),())

    def test_caught_statement_failure_writer_rollback_only(self):
        before=self.snapshot()
        with self.assertRaises(s.StorageRejected):
            with self.store.transaction() as writer:
                try: writer.insert(self.binding)
                except s.StorageRejected: pass
                with self.assertRaises(s.StorageRejected): writer.lookup(s.MetadataRow,1)
        self.assertEqual(writer.result,s.LocalStorageResult.LOCAL_STORAGE_ROLLBACK_CONFIRMED)
        self.assertEqual(before,self.snapshot())

    def test_schema_and_import_boundaries_unchanged(self):
        self.assertEqual(len(s.SPECS),6)
        store_ast=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_store.py').read_text())
        imports={node.module for node in ast.walk(store_ast) if isinstance(node,ast.ImportFrom)}
        self.assertEqual(imports,{'contextlib','dataclasses','enum','hashlib','pathlib','fixture_lease_contract',None})
        self.assertEqual([(n.level, tuple((a.name,a.asname) for a in n.names)) for n in ast.walk(store_ast)
                          if isinstance(n,ast.ImportFrom) and n.module is None],
                         [(1,(('fixture_lease_commands','commands'),))])
        commands_ast=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_commands.py').read_text())
        self.assertTrue(command_import_boundary(commands_ast))


    def structural_status(self, status):
        # Synthetic durable setup, not lifecycle policy. Rebind exact STATE digest.
        self.raw('UPDATE RESERVATIONS SET lease_status=?,quarantine_reason=? WHERE reservation_id=?',
            (status.value,s.QuarantineReason.EXPIRED_UNRECONCILED.value if status==c.LeaseStatus.QUARANTINED else None,'r'))
        with self.store.transaction() as writer:
            metadata=writer.lookup(s.MetadataRow,1)
            writer.complete_metadata(metadata,replace(metadata,
                state_digest=p.state_digest(core._projection(writer),self.context)))

    def structural_command(self, kind):
        row=self.store.read_rows(s.ReservationRow)[0]
        artifact=(self.release_evidence if kind==c.Command.RELEASE else
                  self.recovery_evidence if kind==c.Command.RECOVER else self.evidence)
        refs=(self.ref(artifact),)
        command=replace(self.command,command_kind=kind,command_id='structural-'+kind.value,
            reservation_id='r',expected_revision=row.revision,
            approval_record_hash=artifact.approval_record_hash,evidence_references=refs,
            parameters=p.Parameters('r',None,None,
                p.ExecutionState.STARTED if kind==c.Command.RECORD_EXECUTION else None,
                p.QuarantineReason.EXPIRED_UNRECONCILED if kind==c.Command.QUARANTINE else None,
                refs,None,None,refs[0]))
        after=replace(row,revision=row.revision+1)
        deletes=()
        if kind==c.Command.QUARANTINE:
            after=replace(after,lease_status=c.LeaseStatus.QUARANTINED,
                          quarantine_reason=s.QuarantineReason.EXPIRED_UNRECONCILED)
        if kind==c.Command.RECORD_EXECUTION:
            after=replace(after,execution_state=s.ExecutionState.STARTED)
        if kind in (c.Command.RELEASE,c.Command.RECOVER):
            after=replace(after,lease_status=c.LeaseStatus.RELEASED,
                **({'release_evidence_artifact_id':artifact.artifact_id} if kind==c.Command.RELEASE
                   else {'recovery_evidence_artifact_id':artifact.artifact_id}))
            deletes=self.store.read_rows(s.ClaimRow)
        return command,core.PreparedTransition(after,(),deletes,1,1)

    def structural_advance(self, phase=c.Phase.AUTH_IDENTITIES_BOUND):
        row=self.store.read_rows(s.ReservationRow)[0]
        artifact=replace(self.artifact('next-binding',c.ArtifactType.PROVISIONING_REQUEST),phase=phase)
        with self.store.transaction() as writer: writer.insert(artifact)
        command=replace(self.command,command_kind=c.Command.ADVANCE,command_id='advance',
            reservation_id='r',expected_revision=row.revision,phase=phase,
            binding_reference=self.ref(artifact),binding_sha256=artifact.sha256,
            approval_record_hash=artifact.approval_record_hash,evidence_references=(self.ref(self.evidence),),
            parameters=p.Parameters('r',self.ref(self.binding),self.ref(artifact),None,None,
                (self.ref(self.evidence),),None,None,self.ref(self.evidence)))
        after=replace(row,revision=row.revision+1,phase=phase,
                      binding_artifact_id=artifact.artifact_id,binding_sha256=artifact.sha256)
        return command,core.PreparedTransition(after,(),(),1,1)

    def test_structural_original_quarantined_release_zero_effect(self):
        self.execute();self.structural_status(c.LeaseStatus.QUARANTINED)
        command,material=self.structural_command(c.Command.RELEASE)
        self.reject_without_change(command,material)
        # Ordinary validation rejection leaves the handle usable.
        command,material=self.structural_command(c.Command.RECOVER)
        self.assertEqual(self.execute(command,material).outcome,p.OutcomeCode.SUCCESS)

    def test_structural_original_record_execution_claim_add_zero_effect(self):
        self.execute();command,material=self.mutate()
        key=c.ConflictKey.fixture_set(c.DatabaseTargetScope('g'),'extra').canonical_bytes
        claim=s.ClaimRow(key,'r',1,self.binding.artifact_id)
        self.reject_without_change(command,replace(material,claim_inserts=(claim,)))
        self.assertEqual(self.execute(command,material).outcome,p.OutcomeCode.SUCCESS)

    def test_structural_record_execution_claim_delete_zero_effect(self):
        self.execute();command,material=self.mutate()
        self.reject_without_change(command,replace(material,claim_deletes=self.store.read_rows(s.ClaimRow)))

    def test_structural_original_same_phase_advance_zero_effect(self):
        self.execute();command,material=self.structural_advance(c.Phase.PRE_AUTH)
        self.reject_without_change(command,material)

    def test_structural_valid_advance_and_historical_replay(self):
        original=self.execute();command,material=self.structural_advance()
        self.assertEqual(self.execute(command,material).outcome,p.OutcomeCode.SUCCESS)
        before=self.snapshot();replay=core.complete(self.store,self.command,self.context)
        self.assertEqual(replay.retained_ack_bytes,original.retained_ack_bytes)
        self.assertEqual(before,self.snapshot())

    def test_structural_positive_quarantine_matrix(self):
        self.execute()
        for status in (c.LeaseStatus.LEASED,c.LeaseStatus.EXPIRED,c.LeaseStatus.QUARANTINED):
            with self.subTest(status=status):
                self.structural_status(status)
                command,material=self.structural_command(c.Command.QUARANTINE)
                command=replace(command,command_id='quarantine-'+status.value)
                self.assertEqual(self.execute(command,material).outcome,p.OutcomeCode.SUCCESS)

    def test_structural_expired_ordinary_release(self):
        self.execute();self.structural_status(c.LeaseStatus.EXPIRED)
        command,material=self.structural_command(c.Command.RELEASE)
        self.assertEqual(self.execute(command,material).outcome,p.OutcomeCode.SUCCESS)

    def test_structural_forbidden_status_and_advance_claim_family(self):
        self.execute();command,material=self.mutate()
        self.reject_without_change(command,replace(material,reservation=replace(material.reservation,
            lease_status=c.LeaseStatus.EXPIRED)))
        command,material=self.structural_advance()
        claim=s.ClaimRow(c.ConflictKey.fixture_set(c.DatabaseTargetScope('g'),'wrong').canonical_bytes,
                        'r',1,'next-binding')
        self.reject_without_change(command,replace(material,claim_inserts=(claim,)))

    def test_structural_projection_bytes_and_hash_reject(self):
        self.execute();command,material=self.mutate()
        for raw,digest in ((b'changed',sha256(b'changed').digest()),
                           (material.reservation.immutable_db_projection,b'z'*32)):
            self.reject_without_change(command,replace(material,reservation=replace(material.reservation,
                immutable_db_projection=raw,immutable_db_projection_hash=digest)))

    def test_structural_artifact_resolution_fail_closed(self):
        self.execute();command,material=self.mutate()
        original=core._structural_projection
        for alteration in ('absent','hash','type'):
            def altered(writer,row,claims):
                real=writer.lookup
                def lookup(cls,key):
                    artifact=real(cls,key)
                    if cls is s.ArtifactRow and key==row.binding_artifact_id:
                        if alteration=='absent': return None
                        if alteration=='hash': return replace(artifact,sha256=b'z'*32)
                        return replace(artifact,artifact_type=c.ArtifactType.FIXTURE_MANIFEST)
                    return artifact
                with patch.object(writer,'lookup',side_effect=lookup):
                    return original(writer,row,claims)
            with patch.object(core,'_structural_projection',side_effect=altered):
                self.reject_without_change(command,material)

    def test_structural_advance_issuer_subject_addition(self):
        self.execute();command,material=self.structural_advance()
        claim=s.ClaimRow(c.ConflictKey.issuer_subject('issuer','subject').canonical_bytes,
                        'r',1,'next-binding')
        result=self.execute(command,replace(material,claim_inserts=(claim,)))
        self.assertEqual(result.outcome,p.OutcomeCode.SUCCESS)
        self.assertEqual(len(self.store.read_rows(s.ClaimRow)),2)

    def test_structural_release_incomplete_claim_deletion(self):
        self.execute();command,material=self.structural_command(c.Command.RELEASE)
        self.reject_without_change(command,replace(material,claim_deletes=()))

    def test_structural_delete_reinsert_circumvention(self):
        self.execute();command,material=self.mutate()
        claim=self.store.read_rows(s.ClaimRow)[0]
        self.reject_without_change(command,replace(material,claim_deletes=(claim,),
                                                  claim_inserts=(replace(claim,introduced_revision=1),)))

    def test_structural_record_execution_after_quarantine_rejects(self):
        self.execute();self.structural_status(c.LeaseStatus.QUARANTINED)
        command,material=self.mutate()
        self.reject_without_change(command,material)

    def test_structural_recover_from_leased_rejects(self):
        self.execute();command,material=self.structural_command(c.Command.RECOVER)
        self.reject_without_change(command,material)

    def test_structural_replay_after_two_later_transitions(self):
        first=self.execute()
        for name in ('later-one','later-two'):
            command,material=self.mutate(command_id=name)
            self.execute(command,material)
        before=self.snapshot()
        result=core.complete(self.store,self.command,self.context)
        self.assertTrue(result.replayed)
        self.assertEqual(result.retained_ack_bytes,first.retained_ack_bytes)
        self.assertEqual(before,self.snapshot())

    def admission_evidence(self, command=None, material=None):
        v=core.service;command=self.command if command is None else command
        material=self.material if material is None else material
        ref=v.EvidenceReference('qualified',b'q'*32)
        metadata=self.store.read_rows(s.MetadataRow)[0]
        cp=v.EvidenceReference('predecessor',sha256(b'synthetic-predecessor').digest())
        activation=v.ActivationIdentity('g',1,'x','host',cp)
        context=v.CommandContext(command.command_id,p.command_digest(command),command.command_kind,
            command.operation,command.phase,command.expected_revision,
            v.EvidenceReference(command.authorization_reference.artifact_id,command.authorization_reference.artifact_sha256))
        predecessor=v.ResolvedCheckpointEvidence(cp,b'synthetic-predecessor',activation,0,
            metadata.last_event_sequence,metadata.last_event_digest,metadata.state_digest,p.STATE_2,ref)
        permit=v.CommandPermit(context,activation,0,100,ref)
        required=command.command_kind in (c.Command.ACQUIRE,c.Command.ADVANCE,c.Command.RELEASE,c.Command.RECOVER)
        envelope=v.RetainedAdmissionEnvelope(ref,p.command_bytes(command),context,command.authenticated_principal,
            permit.evidence,activation,predecessor,
            v.ApprovalApplicability.REQUIRED if required else v.ApprovalApplicability.NOT_APPLICABLE,
            v.EvidenceReference('approval',command.approval_record_hash) if required else None,
            material.utc_time,v.UtcInterval(material.utc_time,material.utc_time),ref)
        anchor=v.MonotonicPoint('test-process','test-domain',0)
        sample=v.QualifiedSample(ref,'test-source',ref,ref,v.UtcInterval(material.utc_time,material.utc_time),anchor)
        profile=v.QualifiedClockProfile(ref,'test-source',ref,1000,1000,10,0)
        propagation=v.QualifiedPropagationError(ref,ref,0,0,ref)
        evidence=v.AdmissionEvidence(envelope,permit,sample,profile,anchor,propagation,
            v.AdmissionCoverage(ref,envelope.reference,context,activation,anchor,sample.utc),
            v.InclusiveDeadline(100),v.StrictDeadline(100),v.EvidenceValidity.VALID,v.EvidenceValidity.VALID,
            v.TimingApplicability.REQUIRED,v.TimingApplicability.REQUIRED)
        fixing=v.RetainedTimeFixing(envelope.reference,context,activation,sample,profile,anchor,propagation)
        evidence=replace(evidence,envelope=replace(envelope,fixing=fixing))
        return evidence,ref

    def admitted(self, command=None, material=None, evidence=None, checker=None, host='host'):
        command=self.command if command is None else command
        material=self.material if material is None else material
        valid,authority=self.admission_evidence(command,material)
        return core.complete_admitted(self.store,command,self.context,material,
            evidence=valid if evidence is None else evidence,host_identity=host,
            representation_authority=authority,checker=core.service.validate_admission if checker is None else checker)

    def test_il5a_valid_admission_shared_mutation_path(self):
        result=self.admitted()
        self.assertEqual(result.outcome,p.OutcomeCode.SUCCESS)
        self.assertEqual(self.store.read_rows(s.CommandRow)[0].canonical_payload_bytes,p.command_bytes(self.command))
        command,material=self.mutate()
        self.assertEqual(self.admitted(command,material).outcome,p.OutcomeCode.SUCCESS)
        self.assertEqual(self.store.read_rows(s.ReservationRow)[0].revision,1)

    def test_il5a_historical_replay_and_mismatch_bypass_seam(self):
        first=self.execute()
        command,material=self.mutate();self.execute(command,material)
        before=self.snapshot()
        def forbidden(*args):raise AssertionError('seam invoked')
        replay=core.complete_admitted(self.store,self.command,self.context,checker=forbidden)
        self.assertTrue(replay.replayed);self.assertEqual(replay.retained_ack_bytes,first.retained_ack_bytes)
        changed=replace(self.command,authenticated_principal='changed')
        mismatch=core.complete_admitted(self.store,changed,self.context,checker=forbidden)
        self.assertEqual(mismatch.outcome,p.OutcomeCode.REPLAY_MISMATCH)
        self.assertEqual(before,self.snapshot())

    def test_il5a_checker_reject_exception_and_malformed_zero_effect(self):
        v=core.service
        def exception(*args):raise RuntimeError('synthetic checker error')
        checkers=(exception,lambda *a:True,lambda *a:None,
                  lambda *a:v.AdmissionDecision(v.AdmissionDisposition.REJECT,v.AdmissionReason.UNAVAILABLE))
        for checker in checkers:
            before=self.snapshot()
            with self.assertRaises(core.CommandRejected):self.admitted(checker=checker)
            self.assertEqual(before,self.snapshot());self.assertFalse(self.store._poisoned)
        self.assertEqual(self.admitted().outcome,p.OutcomeCode.SUCCESS)

    def test_il5a_evidence_failures_six_table_zero_effect(self):
        v=core.service;evidence,_=self.admission_evidence()
        activation=evidence.envelope.activation
        variants=(replace(evidence,permit=None),
            replace(evidence,permit_validity=v.EvidenceValidity.INVALID),
            replace(evidence,permit=replace(evidence.permit,valid_until_us=0)),
            replace(evidence,permit=replace(evidence.permit,activation=replace(activation,activation_id='wrong'))),
            replace(evidence,permit=replace(evidence.permit,activation=replace(activation,generation=2))),
            replace(evidence,envelope=replace(evidence.envelope,approval=None)),
            replace(evidence,envelope=replace(evidence.envelope,approval_applicability=v.ApprovalApplicability.UNKNOWN)),
            replace(evidence,approval_validity=v.EvidenceValidity.UNKNOWN),
            replace(evidence,admission_coverage=None),
            replace(evidence,envelope=replace(evidence.envelope,principal='wrong')),
            replace(evidence,envelope=replace(evidence.envelope,predecessor=replace(
                evidence.envelope.predecessor,representation_authority=v.EvidenceReference('wrong',b'z'*32)))),
            replace(evidence,envelope=replace(evidence.envelope,predecessor=replace(
                evidence.envelope.predecessor,representation='unknown'))))
        for variant in variants:
            before=self.snapshot()
            with self.assertRaises(core.CommandRejected):self.admitted(evidence=variant)
            self.assertEqual(before,self.snapshot());self.assertFalse(self.store._poisoned)
        before=self.snapshot()
        with self.assertRaises(core.CommandRejected):self.admitted(host='wrong')
        self.assertEqual(before,self.snapshot())

    def test_il5a_time_overlap_coverage_and_utc_zero_effect(self):
        v=core.service;evidence,_=self.admission_evidence()
        overlap=v.UtcInterval(0,1)
        variants=(replace(evidence,sample=replace(evidence.sample,utc=overlap),
            admission_coverage=replace(evidence.admission_coverage,interval=overlap),
            permit=replace(evidence.permit,valid_until_us=1)),
            replace(evidence,admission_coverage=replace(evidence.admission_coverage,
                context=replace(evidence.envelope.context,command_id='wrong'))),
            replace(evidence,envelope=replace(evidence.envelope,fixed_utc_us=1,fixing_interval=v.UtcInterval(1,1))))
        for variant in variants:
            before=self.snapshot()
            with self.assertRaises(core.CommandRejected):self.admitted(evidence=variant)
            self.assertEqual(before,self.snapshot())

    def test_il5a_seam_after_structure_before_first_write(self):
        trace=[];original_transition=core._transition;original_insert=s.TransactionWriter.insert
        def transition(*args):
            original_transition(*args);trace.append('structure')
        def checker(evidence,facts):
            self.assertTrue(self.store._writer._active)
            self.assertIs(type(facts),core.service.AdmissionFacts)
            self.assertFalse(hasattr(facts,'writer'));self.assertFalse(hasattr(facts,'store'))
            trace.append('admission');return core.service.validate_admission(evidence,facts)
        def insert(writer,row):
            self.assertIn('admission',trace);trace.append('write');return original_insert(writer,row)
        with patch.object(core,'_transition',transition),patch.object(s.TransactionWriter,'insert',insert):
            self.admitted(checker=checker)
        self.assertEqual(trace[:3],['structure','admission','write'])

    def test_il5a_stale_and_structural_rejection_precede_seam(self):
        self.execute();command,material=self.mutate(expected=1)
        checker=unittest.mock.Mock(side_effect=AssertionError('seam'))
        before=self.snapshot()
        with self.assertRaises(core.CommandRejected):self.admitted(command,material,checker=checker)
        checker.assert_not_called();self.assertEqual(before,self.snapshot())
        command,material=self.structural_advance(c.Phase.PRE_AUTH)
        before=self.snapshot()
        with self.assertRaises(core.CommandRejected):self.admitted(command,material,checker=checker)
        checker.assert_not_called();self.assertEqual(before,self.snapshot())

    def test_il5a_no_clock_or_capability_acquisition(self):
        v=core.service
        with (patch.object(v.RejectingCapabilities,'obtain',side_effect=AssertionError('permit')),
              patch.object(v.RejectingCapabilities,'publish',side_effect=AssertionError('publish'))):
            self.admitted()
        tree=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_commands.py').read_text())
        forbidden={'sleep','open','connect','time','now','measure','obtain','publish','complete_original'}
        self.assertFalse(any(isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
            and node.func.attr in forbidden for node in ast.walk(tree)))

    def test_il5a_admitted_commit_ack_loss_preserves_unknown(self):
        evidence,authority=self.admission_evidence()
        connection=self.store._connection;calls=[]
        class LostAck:
            def __getattr__(self,name):return getattr(connection,name)
            def execute(self,sql,*args):
                calls.append(sql);result=connection.execute(sql,*args)
                if sql=='COMMIT':raise sqlite3.OperationalError('synthetic lost ACK')
                return result
        self.store._connection=LostAck()
        result=core.complete_admitted(self.store,self.command,self.context,self.material,
            evidence=evidence,host_identity='host',representation_authority=authority)
        self.assertEqual(result.outcome,p.OutcomeCode.STORAGE_UNKNOWN)
        self.assertIsNone(result.retained_ack_bytes);self.assertTrue(self.store._poisoned)
        self.assertEqual(calls.count('COMMIT'),1);self.assertNotIn('ROLLBACK',calls)
        self.assertEqual(self.raw('SELECT outcome_code FROM COMMANDS'),[('SUCCESS',)])

    def test_il5a_admitted_rollback_uncertainty(self):
        evidence,authority=self.admission_evidence()
        connection=self.store._connection;calls=[]
        class BrokenRollback:
            def __getattr__(self,name):return getattr(connection,name)
            def execute(self,sql,*args):
                calls.append(sql)
                if sql=='ROLLBACK':raise sqlite3.OperationalError('synthetic rollback failure')
                return connection.execute(sql,*args)
        self.store._connection=BrokenRollback()
        with patch.object(core,'_append',side_effect=core.CommandRejected('synthetic')):
            result=core.complete_admitted(self.store,self.command,self.context,self.material,
            evidence=evidence,host_identity='host',representation_authority=authority)
        self.assertEqual(result.outcome,p.OutcomeCode.STORAGE_UNKNOWN)
        self.assertIsNone(result.retained_ack_bytes);self.assertTrue(self.store._poisoned)
        self.assertEqual(calls.count('ROLLBACK'),1);self.assertNotIn('COMMIT',calls)

    def test_il5a_checker_cannot_override_mandatory_binding_rejection(self):
        v=core.service;evidence,_=self.admission_evidence()
        invalid=replace(evidence,permit_validity=v.EvidenceValidity.INVALID)
        checker=unittest.mock.Mock(return_value=v.AdmissionDecision(v.AdmissionDisposition.ADMIT,None))
        before=self.snapshot()
        with self.assertRaises(core.CommandRejected):self.admitted(evidence=invalid,checker=checker)
        checker.assert_not_called();self.assertEqual(before,self.snapshot())
        self.assertFalse(self.store._poisoned)

    def refreshed_command_evidence(self):
        v=core.service;evidence,authority=self.admission_evidence();fixing=evidence.envelope.fixing
        anchor=replace(fixing.sample.anchor,ticks_ns=1000)
        sample=replace(fixing.sample,sample=v.EvidenceReference('refresh',b'r'*32),
            validation=v.EvidenceReference('current-validation',b'v'*32),utc=v.UtcInterval(1,1),anchor=anchor)
        error=v.QualifiedPropagationError(fixing.sample.sample,fixing.sample.profile,1000,0,authority)
        propagation=v.QualifiedPropagationError(sample.sample,sample.profile,0,0,authority)
        evidence=replace(evidence,sample=sample,current=anchor,propagation=propagation,
            fixing_to_refresh=error,admission_coverage=replace(evidence.admission_coverage,point=anchor,interval=sample.utc))
        return evidence,authority

    def test_il5a_refresh_real_admitted_path_keeps_original_envelope(self):
        v=core.service;evidence,authority=self.refreshed_command_evidence();envelope=evidence.envelope
        material=replace(self.material,last_valid_utc=1)
        self.assertNotEqual(envelope.time_qualification,evidence.sample.validation)
        self.assertTrue(v.refresh_consistent(envelope.fixing.sample,evidence.sample,evidence.profile,evidence.fixing_to_refresh))
        result=core.complete_admitted(self.store,self.command,self.context,material,evidence=evidence,
            host_identity='host',representation_authority=authority)
        self.assertEqual(result.outcome,p.OutcomeCode.SUCCESS)
        self.assertEqual(p.decode_record(result.retained_ack_bytes,p.AckPayload).issued_at,0)
        self.assertEqual(self.store.read_rows(s.MetadataRow)[0].last_valid_utc,1)
        self.assertIs(evidence.envelope,envelope);self.assertEqual(envelope.time_qualification,envelope.fixing.sample.validation)

    def test_il5a_refresh_real_inconsistent_path_six_table_zero_effect(self):
        v=core.service;evidence,authority=self.refreshed_command_evidence()
        sample=replace(evidence.sample,utc=v.UtcInterval(50,50))
        invalid=replace(evidence,sample=sample,admission_coverage=replace(evidence.admission_coverage,interval=sample.utc))
        self.assertFalse(v.refresh_consistent(evidence.envelope.fixing.sample,sample,evidence.profile,evidence.fixing_to_refresh))
        before=self.snapshot();checker=unittest.mock.Mock(return_value=v.AdmissionDecision(v.AdmissionDisposition.ADMIT,None))
        with self.assertRaises(core.CommandRejected):
            core.complete_admitted(self.store,self.command,self.context,replace(self.material,last_valid_utc=50),
                evidence=invalid,host_identity='host',representation_authority=authority,checker=checker)
        checker.assert_not_called();self.assertEqual(before,self.snapshot());self.assertFalse(self.store._poisoned)
        result=core.complete_admitted(self.store,self.command,self.context,replace(self.material,last_valid_utc=1),
            evidence=evidence,host_identity='host',representation_authority=authority)
        self.assertEqual(result.outcome,p.OutcomeCode.SUCCESS)

    def test_il5a_architecture_exact_origin_positive_negative(self):
        production=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_commands.py').read_text(encoding='utf-8'))
        self.assertTrue(command_import_boundary(production))
        for source in ('from .orchestration_service import fixture_lease_service as service',
                       'from .orchestration_service import fixture_lease_service',
                       'from .. import fixture_lease_service as service',
                       'from .provider import fixture_lease_service as service'):
            probe=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_commands.py').read_text(encoding='utf-8')
                           .replace('from . import fixture_lease_service as service',source))
            self.assertFalse(command_import_boundary(probe),source)
        missing=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_commands.py').read_text(encoding='utf-8')
                         .replace('from . import fixture_lease_service as service',''))
        self.assertFalse(command_import_boundary(missing))


class QualifiedWriterTests(unittest.TestCase):
    artifact = CommandsTests.artifact
    ref = CommandsTests.ref
    acquire = CommandsTests.acquire
    execute = CommandsTests.execute
    raw = CommandsTests.raw
    tearDown = CommandsTests.tearDown

    def setUp(self):
        CommandsTests.setUp(self)
        self.execute()  # Real synthetic retained predecessor; not genesis fallback.
        self.command, self.material = self.acquire('b-command', 'b-reservation', 'b-set')
        self.material = replace(self.material, utc_time=10, last_valid_utc=999)
        self.q = core.qualification_values
        self.v = core.service
        if not hasattr(type(self), 'template'):
            type(self).template = self.make_qualification()
        self.qualified = self.q._copy(type(self).template)
        self.points = [1000, 4000]
        self.calls = []
        self.error_value = 0
        self.measure_hook = None
        self.qualifier_hook = None
        self.proof_transform = None
        self.impl = self.v.EvidenceReference('approved-local-implementation', b'i'*32)
        self.measurement = self.v.EvidenceReference('approved-local-measurement', b'm'*32)
        self.proof = self.v.EvidenceReference('independent-local-qualification', b'q'*32)
        self.applicability = self.v.TimingApplicability.NOT_APPLICABLE
        self.deadline = None
        self.adapter = core.LocalTimingAdapter(self.qualified.inputs.support, self.impl, self.measurement,
                                               self.qualify_local, self.measure, self.error)

    def make_qualification(self):
        q, v = self.q, self.v
        g, a, r = q.g, q.a, q.r
        pr, cp = g.pr, g.pr.checkpoints
        proof = v.EvidenceReference('synthetic-independent-proof', b'z'*32)
        metadata = self.store.read_rows(s.MetadataRow)[0]
        ref = cp.NormalReference('seed', b'c'*32, 'seed-permit', b'p'*32, 'host', p.STATE_2,
                                  proof.identity, proof.sha256, 'seed-envelope', b'e'*32)
        raw = cp.checkpoint_bytes(cp.NormalCheckpoint('g', 1, 'x', 1, metadata.last_event_sequence,
            metadata.last_event_digest, metadata.state_digest, 0, b'0'*32, ref, 'approval'))
        pointer = v.EvidenceReference('protected-predecessor', sha256(raw).digest())
        activation = v.ActivationIdentity('g', 1, 'x', 'host', pointer)
        predecessor = v.ResolvedCheckpointEvidence(pointer, raw, activation, 1, metadata.last_event_sequence,
            metadata.last_event_digest, metadata.state_digest, p.STATE_2, proof)
        binding = pr.CurrentBinding(activation, 'host', proof, p.STATE_2, proof,
            pr.PredecessorProfile.NORMAL_COMMAND, 1, metadata.last_event_sequence,
            metadata.last_event_digest, metadata.state_digest)
        current = pr.QualifiedCurrentContext(binding, pr.ContextQualification(binding, v.EvidenceValidity.VALID,
            proof, pr.CurrentStatus.CURRENT, pr.HostStatus.APPROVED, pr.FencingStatus.CLEAR))
        resolved = pr.resolve_predecessor(current, pr.TrustedPredecessorAdapter(
            lambda value: v.EvidenceValidity.VALID,
            lambda value: pr.ResolutionObservation(predecessor,
                pr.ResolutionQualification(current, predecessor, v.EvidenceValidity.VALID, proof)),
            lambda *values: v.EvidenceValidity.VALID))
        command = self.command
        context = v.CommandContext(command.command_id, p.command_digest(command), command.command_kind,
            command.operation, command.phase, command.expected_revision,
            v.EvidenceReference(command.authorization_reference.artifact_id, command.authorization_reference.artifact_sha256))
        auth = g.AuthorizationEvidence(context, 'owner', activation, context.authorization,
            v.EvidenceValidity.VALID, 0, v.InclusiveDeadline(12))
        approval = v.EvidenceReference('approval', command.approval_record_hash)
        approved = g.ApprovalEvidence(v.ApprovalApplicability.REQUIRED,
            v.VerifiedApproval('independent', 'owner', context,
                c.ArtifactBytes(self.binding.artifact_type, self.binding.exact_bytes), approval),
            approval, v.EvidenceValidity.VALID, 0, v.InclusiveDeadline(12))
        if command.command_kind in (c.Command.RECORD_EXECUTION, c.Command.QUARANTINE):
            approved = g.ApprovalEvidence(v.ApprovalApplicability.NOT_APPLICABLE, None, None,
                                          v.EvidenceValidity.VALID, None, None)
        point = v.MonotonicPoint('process', 'domain', 0)
        sample = v.QualifiedSample(proof, 'synthetic-source', proof, proof, v.UtcInterval(10, 10), point)
        profile = v.QualifiedClockProfile(proof, 'synthetic-source', proof, 100000, 100, 10, 0)
        propagation = v.QualifiedPropagationError(proof, proof, 0, 0, proof)
        time = g.TimeEvidence(sample, profile, point, propagation, v.TimingApplicability.REQUIRED,
            v.StrictDeadline(40), v.TimingApplicability.NOT_APPLICABLE, None)
        history = g.HistoryEvidence(context, activation, proof, g.CommandHistory.NEW,
            g.GapKnowledge.CLEAR, g.GapKnowledge.CLEAR, g.GapKnowledge.CLEAR,
            pr.CurrentStatus.CURRENT, pr.HostStatus.APPROVED, pr.FencingStatus.CLEAR)
        bundle = g.PrerequisiteBundle(p.command_bytes(command), command, context,
            v.AuthenticatedRequester('owner', proof), auth, resolved, activation, 'host', approved, time, history)
        gate = g.evaluate_prerequisites(bundle, g.TrustedPrerequisiteVerifier(
            lambda value: g.QualificationEvidence(value, v.EvidenceValidity.VALID, proof)))
        request = a.AcquisitionInput(bundle, gate)
        permit_bytes = b'synthetic exact original permit'
        permit = v.CommandPermit(context, activation, 0, 13,
                                  v.EvidenceReference('original-permit', sha256(permit_bytes).digest()))
        acquired = a.acquire_original_permit(request, a.TrustedAcquisitionAdapter(
            lambda value: g.QualificationEvidence(value.bundle, v.EvidenceValidity.VALID, proof),
            lambda *args: permit,
            lambda attempt, value: a.PermitQualification(attempt, value, permit_bytes, time,
                                                          v.EvidenceValidity.VALID, proof)))
        prepared = r.e.prepare_admission_envelope(acquired)
        envelope_ref = v.EvidenceReference('retained-envelope', b'r'*32)
        def receipt(material):
            return r.RetentionReceipt(material, envelope_ref,
                r.OriginalRecordIndex(context, 'owner', activation, permit.evidence, envelope_ref))
        retained = r.retain_original_envelope(prepared, r.TrustedRetentionAdapter(proof,
            lambda value: r.RetentionAuthorization(value, permit.evidence, proof, v.EvidenceValidity.VALID, proof),
            receipt,
            lambda value, observed: r.RetentionConfirmation(observed, proof, *([v.EvidenceValidity.VALID]*3), proof)))
        support = q.ModelSupport(proof, proof, proof, proof, sample.source, 100000, q.ErrorConventions.DESIGN7_NS_OUTWARD)
        observed = replace(time, point=replace(point, ticks_ns=500),
                           propagation=replace(propagation, elapsed_ns=500))
        def qualify(value):
            return q.CurrentQualification(value, proof, proof, *([v.EvidenceValidity.VALID]*9),
                auth, approved, observed, q.PropagationModelBinding(support, sample.sample,
                    'process', 'domain', 500, 90000, v.EvidenceValidity.VALID, proof))
        result = q.qualify_admission_inputs(retained, q.TrustedQualificationAdapter(proof, (support,), qualify))
        self.assertIs(result.state, q.QualificationState.QUALIFIED)
        return result

    def qualify_local(self, inputs, implementation, measurement, measure, error):
        self.calls.append('qualify')
        self.assertIsNone(self.store._writer)
        if self.qualifier_hook: self.qualifier_hook()
        response = core.LocalTimingQualification(inputs, implementation, measurement, 'process', 'domain',
            self.v.EvidenceValidity.VALID, self.proof, self.applicability, self.deadline)
        return response if self.proof_transform is None else self.proof_transform(response)

    def measure(self):
        self.calls.append('m')
        self.assertIsNotNone(self.store._writer)
        if self.measure_hook: self.measure_hook()
        return self.v.MonotonicPoint('process', 'domain', self.points.pop(0))

    def error(self, elapsed):
        self.calls.append(('E', elapsed))
        return self.error_value

    def run_b(self):
        return core.complete_qualified(self.store, self.command, self.context, self.material,
                                       qualification=self.qualified, timing=self.adapter)

    def rewrite_qualification(self, row_type, field, value):
        def rewrite(projection):
            kind, data = projection
            if type(data) is tuple and data and type(data[0]) is tuple and type(data[0][0]) is str:
                data = tuple((name, (type(value), value) if kind is row_type and name == field
                              else rewrite(child)) for name, child in data)
            return kind, data
        # Synthetic qualified fixture construction, not a production authority API.
        self.qualified = self.q.a._copy_projection(rewrite(self.q._project(self.qualified)))

    def test_valid_consumption_windows_expire_before_t2(self):
        result = self.run_b()
        self.assertEqual(result.local.outcome, p.OutcomeCode.SUCCESS)
        self.assertEqual(result.t1.evaluation.interval.lower_us, 11)
        self.assertEqual(result.t2.evaluation.interval.lower_us, 14)
        self.assertFalse(result.reconciliation_required)
        self.assertEqual(self.calls, ['qualify', 'm', ('E', 1000), 'm', ('E', 4000)])
        self.assertEqual(self.store.read_rows(s.MetadataRow)[0].last_valid_utc, 11)
        self.assertEqual(p.decode_record(result.local.retained_ack_bytes, p.AckPayload).issued_at, 10)
        self.assertEqual(self.material.last_valid_utc, 999)
        with self.assertRaises(TypeError): bool(result)
        for name in ('publish', 'complete', 'ack_delivery_permitted', 'retry_permitted', 'begin_permitted'):
            self.assertFalse(hasattr(result, name))

    def test_t1_reads_then_mutation_and_t2_sealed_no_reads(self):
        trace = []
        lookup, insert = s.TransactionWriter.lookup, s.TransactionWriter.insert
        validate = s._validate_register
        def read(writer, *args):
            trace.append('read'); return lookup(writer, *args)
        def write(writer, *args):
            self.assertIn('m1', trace); trace.append('write'); return insert(writer, *args)
        def audit(*args):
            trace.append('audit'); return validate(*args)
        def measured():
            if len(self.points) == 2:
                trace.append('m1')
            else:
                self.assertTrue(self.store._writer._sealed)
                self.assertEqual(self.store._writer._cursors, [])
                trace.append('m2')
        self.measure_hook = measured
        with patch.object(s.TransactionWriter, 'lookup', read), patch.object(s.TransactionWriter, 'insert', write), patch.object(s, '_validate_register', audit):
            result = self.run_b()
        self.assertEqual(result.local.outcome, p.OutcomeCode.SUCCESS)
        self.assertEqual(trace[-2:], ['audit', 'm2'])
        self.assertNotIn('read', trace[trace.index('m1')+1:trace.index('write')])

    def test_captured_dependency_replacement_cannot_escape(self):
        def replacement():
            object.__setattr__(self.adapter, 'measure', lambda: self.fail('replacement measure'))
            object.__setattr__(self.adapter, 'evaluate_error_ns', lambda n: self.fail('replacement E'))
            object.__setattr__(self.adapter, 'qualify', lambda *a: self.fail('late qualification'))
        self.qualifier_hook = replacement
        self.assertEqual(self.run_b().local.outcome, p.OutcomeCode.SUCCESS)

    def test_t2_completion_unknown_rejects_before_begin(self):
        self.applicability = self.v.TimingApplicability.UNKNOWN
        with self.assertRaises(core.CommandRejected): self.run_b()
        self.assertEqual(self.calls, ['qualify'])

    def test_required_strict_completion_deadline_blocks_commit(self):
        self.applicability = self.v.TimingApplicability.REQUIRED
        self.deadline = self.v.StrictDeadline(14)
        result = self.run_b()
        self.assertEqual(result.local.outcome, p.OutcomeCode.CLOCK_REJECTED)
        self.assertTrue(result.reconciliation_required)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), [(1,)])
        self.assertFalse(self.store._connection.in_transaction)

    def test_inclusive_completion_equality_and_no_reservation_expiry_gate(self):
        self.applicability = self.v.TimingApplicability.REQUIRED
        self.deadline = self.v.InclusiveDeadline(14)
        self.assertEqual(self.run_b().local.outcome, p.OutcomeCode.SUCCESS)

    def test_t2_freshness_failure_zero_commit(self):
        self.points = [1000, 40000]
        self.assertEqual(self.run_b().local.outcome, p.OutcomeCode.CLOCK_REJECTED)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), [(1,)])

    def test_later_contradiction_preserves_confirmed_storage(self):
        result = self.run_b()
        before = self.raw('SELECT canonical_payload_hash FROM COMMANDS ORDER BY command_id')
        blocked = core._later_contradiction(self.store, result, self.proof)
        self.assertIs(blocked.local, result.local)
        self.assertEqual(blocked.local.storage_result, s.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        self.assertTrue(blocked.reconciliation_required)
        self.assertTrue(self.store._poisoned)
        self.assertEqual(before, self.raw('SELECT canonical_payload_hash FROM COMMANDS ORDER BY command_id'))

    def test_replay_mismatch_no_new_measurement(self):
        first = self.run_b()
        self.calls.clear()
        self.points = []
        replay = self.run_b()
        self.assertIs(type(replay), core.LocalCommandResult)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.retained_ack_bytes, first.local.retained_ack_bytes)
        self.assertEqual(self.calls, ['qualify'])
        self.calls.clear()
        self.command = replace(self.command, authenticated_principal='changed')
        mismatch = self.run_b()
        self.assertEqual(mismatch.outcome, p.OutcomeCode.REPLAY_MISMATCH)
        self.assertEqual(self.calls, ['qualify'])

    def test_programming_defect_preserved_after_cleanup(self):
        def broken(n): raise AssertionError('implementation defect')
        self.adapter = replace(self.adapter, evaluate_error_ns=broken)
        with self.assertRaisesRegex(AssertionError, 'implementation defect'): self.run_b()
        self.assertFalse(self.store._connection.in_transaction)
        self.assertTrue(self.store._poisoned)

    def test_caller_mutation_during_measurement_rejects_without_mutation(self):
        self.measure_hook = lambda: object.__setattr__(self.material.reservation, 'owner', 'changed')
        self.assertEqual(self.run_b().local.outcome, p.OutcomeCode.AUTHORITY_REJECTED)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), [(1,)])

    def test_commit_uncertainty_preserves_unknown(self):
        connection = self.store._connection
        calls = []
        class LostCommit:
            def __getattr__(inner, name): return getattr(connection, name)
            def execute(inner, sql, *args):
                calls.append(sql)
                cursor = connection.execute(sql, *args)
                if sql == 'COMMIT': raise sqlite3.OperationalError('lost response')
                return cursor
        self.store._connection = LostCommit()
        result = self.run_b()
        self.assertEqual(result.local.outcome, p.OutcomeCode.STORAGE_UNKNOWN)
        self.assertIsNone(result.local.storage_result)
        self.assertTrue(result.reconciliation_required)
        self.assertIsNot(result.reason, s._CommitCleanupReason.CURSOR_CLOSE)
        self.assertIsNone(result.local.retained_ack_bytes)
        self.assertTrue(self.store._poisoned)
        self.assertEqual(calls.count('COMMIT'), 1)
        self.assertNotIn('ROLLBACK', calls)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), [(2,)])

    def commit_close_failure(self):
        connection, calls, closes = self.store._connection, [], []
        class CommitCursor:
            def __init__(inner, cursor): inner.cursor = cursor
            def close(inner):
                closes.append('COMMIT')
                inner.cursor.close()
                raise RuntimeError('COMMIT cursor close failed after confirmed execute')
        class Connection:
            def __getattr__(inner, name): return getattr(connection, name)
            def execute(inner, sql, *args):
                calls.append(sql)
                cursor = connection.execute(sql, *args)
                return CommitCursor(cursor) if sql == 'COMMIT' else cursor
        self.store._connection = Connection()
        return connection, calls, closes

    def test_confirmed_commit_close_failure_survives_b_boundary(self):
        connection, calls, closes = self.commit_close_failure()
        result = self.run_b()
        self.assertIs(type(result.local), core.LocalCommandResult)
        self.assertEqual(result.local.outcome, p.OutcomeCode.SUCCESS)
        self.assertIs(result.local.storage_result, s.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        self.assertTrue(result.reconciliation_required)
        self.assertIs(result.reason, s._CommitCleanupReason.CURSOR_CLOSE)
        self.assertEqual(result.reason.value, 'POST_COMMIT_CURSOR_CLOSE')
        self.assertIsNotNone(result.t1)
        self.assertIsNotNone(result.t2)
        self.assertIsNotNone(result.completed)
        self.assertEqual(result.local.retained_ack_bytes, result.completed.ack_bytes)
        self.assertEqual(self.raw('SELECT durable_ack_bytes FROM COMMANDS WHERE command_id=?',
                                  (self.command.command_id,)), [(result.local.retained_ack_bytes,)])
        self.assertTrue(self.store._poisoned)
        self.assertFalse(connection.in_transaction)
        self.assertEqual(calls.count('COMMIT'), 1)
        self.assertNotIn('ROLLBACK', calls)
        self.assertEqual(closes, ['COMMIT'])
        with self.assertRaises(TypeError): bool(result)
        for name in ('publish', 'publication_permitted', 'permit_completion_permitted',
                     'ack_delivery_permitted', 'recovery_execution_permitted', 'retry_permitted'):
            self.assertFalse(hasattr(result, name))

    def test_replay_commit_cleanup_preserves_historical_result_without_measurement(self):
        first = self.run_b()
        self.calls.clear()
        self.points = []
        connection, calls, closes = self.commit_close_failure()
        result = self.run_b()
        self.assertTrue(result.local.replayed)
        self.assertEqual(result.local.retained_ack_bytes, first.local.retained_ack_bytes)
        self.assertIs(result.local.storage_result, s.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        self.assertTrue(result.reconciliation_required)
        self.assertIsNone(result.t1)
        self.assertIsNone(result.t2)
        self.assertEqual(self.calls, ['qualify'])
        self.assertEqual(calls.count('COMMIT'), 1)
        self.assertNotIn('ROLLBACK', calls)
        self.assertEqual(closes, ['COMMIT'])
        self.assertFalse(connection.in_transaction)

    def test_non_b_commit_cleanup_retains_storage_rejected_contract(self):
        first = self.run_b()
        connection, calls, closes = self.commit_close_failure()
        with self.assertRaises(s.StorageRejected) as caught:
            core.complete_admitted(self.store, self.command, self.context)
        self.assertIs(type(caught.exception), s._ConfirmedCommitCleanup)
        self.assertIs(caught.exception.storage_result, s.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        self.assertEqual(calls.count('COMMIT'), 1)
        self.assertNotIn('ROLLBACK', calls)
        self.assertEqual(closes, ['COMMIT'])
        self.assertTrue(self.store._poisoned)
        self.assertFalse(connection.in_transaction)

    def test_zero_durable_access_after_m2_and_one_commit(self):
        connection = self.store._connection
        after_m2, calls = [], []
        class Trap:
            def __getattr__(inner, name): return getattr(connection, name)
            def execute(inner, sql, *args):
                calls.append(sql)
                if after_m2: self.assertEqual(sql, 'COMMIT')
                return connection.execute(sql, *args)
        self.store._connection = Trap()
        self.measure_hook = lambda: after_m2.append(True) if len(self.points) == 1 else None
        self.assertEqual(self.run_b().local.outcome, p.OutcomeCode.SUCCESS)
        self.assertEqual(calls.count('COMMIT'), 1)

    def test_t2_failure_zero_commit_attempts(self):
        connection = self.store._connection
        calls = []
        class Trace:
            def __getattr__(inner, name): return getattr(connection, name)
            def execute(inner, sql, *args):
                calls.append(sql); return connection.execute(sql, *args)
        self.store._connection = Trace()
        self.points = [1000, 90001]
        self.assertTrue(self.run_b().reconciliation_required)
        self.assertNotIn('COMMIT', calls)
        self.assertEqual(calls.count('ROLLBACK'), 1)

    def test_stale_durable_predecessor_rejects_without_new_mutation(self):
        other, effects = self.acquire('unrelated', 'other-r', 'other-set')
        self.execute(other, effects)
        before = self.raw('SELECT count(*) FROM COMMANDS')
        self.assertTrue(self.run_b().reconciliation_required)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), before)

    def test_invalid_qualification_never_enters_begin(self):
        self.qualified = self.q.qualify_admission_inputs(None)
        with self.assertRaises((core.CommandRejected, self.v.TimeRejected)): self.run_b()
        self.assertEqual(self.calls, [])

    def test_fixed_finalizer_has_no_transaction_closure_or_public_token(self):
        self.assertIsNone(core._finalize_qualified.__closure__)
        for name in ('prepare_commit', 'authorize_commit', 'suspend'):
            self.assertFalse(hasattr(s.TransactionWriter, name))
            self.assertFalse(hasattr(s.LeaseStore, name))
        self.assertNotIn('finalizer', core._Finalization.__dataclass_fields__)
        self.assertFalse(any(name in core._Finalization.__dataclass_fields__ for name in ('store', 'writer', 'connection')))

    def test_required_inputs_have_no_none_defaults(self):
        self.assertIsNone(core.complete_qualified.__defaults__)
        self.assertIsNone(core.complete_qualified.__kwdefaults__)

    def test_scope_exhaustion_does_not_trigger_lazy_qualification(self):
        self.points = [1000, 90001]
        self.run_b()
        self.assertEqual(self.calls.count('qualify'), 1)
        self.assertNotIn(('E', 90001), self.calls)

    def test_t2_sample_age_includes_error(self):
        def rewrite(projection):
            kind, data = projection
            if type(data) is tuple and data and type(data[0]) is tuple and type(data[0][0]) is str:
                data = tuple((name, (int, 90) if kind is self.v.QualifiedClockProfile and name == 'max_sample_age_us'
                              else rewrite(child)) for name, child in data)
            return kind, data
        self.qualified = self.q.a._copy_projection(rewrite(self.q._project(self.qualified)))
        self.adapter = replace(self.adapter, evaluate_error_ns=lambda n: 1000 if n == 90000 else 0)
        self.points = [1000, 90000]
        self.assertEqual(self.run_b().local.outcome, p.OutcomeCode.CLOCK_REJECTED)

    def test_t2_uncertainty_failure(self):
        self.adapter = replace(self.adapter, evaluate_error_ns=lambda n: 6000 if n == 4000 else 0)
        self.assertEqual(self.run_b().local.outcome, p.OutcomeCode.CLOCK_REJECTED)

    def test_reservation_expiry_does_not_supply_completion_bound(self):
        # Build retained history whose immutable reservation expiry lies between
        # T1 and T2. RECORD_EXECUTION has independently qualified lease N/A;
        # this does not manufacture a universal reservation-expiry gate.
        self.tearDown()
        CommandsTests.setUp(self)
        self.command = replace(self.command, parameters=replace(self.command.parameters,
            proposed_expires_at=13, proposed_completion_deadline=12))
        self.material = replace(self.material, reservation=replace(self.material.reservation,
            expires_at=13, completion_deadline=12))
        self.execute()
        self.command, self.material = CommandsTests.mutate(self, 'b-expiry-record')
        self.material = replace(self.material, utc_time=10, last_valid_utc=999)
        self.qualified = self.make_qualification()
        self.adapter = replace(self.adapter, support=self.qualified.inputs.support)
        self.assertIs(self.qualified.inputs.observation.time.lease_applicability,
                      self.v.TimingApplicability.NOT_APPLICABLE)
        result = self.run_b()
        self.assertEqual(result.local.outcome, p.OutcomeCode.SUCCESS)
        self.assertGreater(result.t2.evaluation.interval.lower_us, result.completed.reservation.expires_at)

    def test_known_local_invalidation_before_dispatch_cancels_commit(self):
        self.measure_hook = lambda: setattr(self.store, '_poisoned', True) if len(self.points) == 1 else None
        result = self.run_b()
        self.assertTrue(result.reconciliation_required)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), [(1,)])

    def test_error_implementation_cannot_be_its_own_qualifier(self):
        self.adapter = replace(self.adapter, qualify=self.adapter.evaluate_error_ns)
        with self.assertRaises(core.CommandRejected): self.run_b()
        self.assertEqual(self.calls, [])

    def test_partial_iterator_traps_after_m2_without_sqlite_advance(self):
        held = []
        gather = core._gather_admission
        def gathering(writer, *args):
            result = gather(writer, *args)
            iterator = writer.iter_rows(s.ArtifactRow)
            next(iterator)
            held.append(iterator)
            return result
        def at_point():
            if len(self.points) == 1:
                with self.assertRaises(s.StorageRejected): next(held[0])
        self.measure_hook = at_point
        with patch.object(core, '_gather_admission', gathering):
            result = self.run_b()
        self.assertTrue(result.reconciliation_required)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), [(1,)])

    def test_qualification_timeout_is_prebegin_only(self):
        def unavailable(*args): raise TimeoutError('qualification unavailable')
        self.adapter = replace(self.adapter, qualify=unavailable)
        with self.assertRaises(core.CommandRejected): self.run_b()
        self.assertEqual(self.calls, [])
        self.assertFalse(self.store._connection.in_transaction)

    def test_callback_owned_point_mutation_cannot_change_elapsed_binding(self):
        point = self.v.MonotonicPoint('process', 'domain', 1000)
        def error(n):
            object.__setattr__(point, 'ticks_ns', 4000)
            return 0
        self.adapter = replace(self.adapter, measure=lambda: point, evaluate_error_ns=error)
        self.assertTrue(self.run_b().reconciliation_required)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), [(1,)])

    def test_qualified_rounding_uses_existing_outward_conventions(self):
        self.error_value = 500
        result = self.run_b()
        self.assertEqual(result.local.outcome, p.OutcomeCode.SUCCESS)
        self.assertEqual(result.t1.evaluation.interval, self.v.UtcInterval(10, 12))
        self.assertEqual(result.t1.evaluation.sample_age_upper_us, 2)
        self.assertEqual(result.t2.evaluation.interval, self.v.UtcInterval(13, 15))

    def test_busy_begin_rejected_once_without_poison_or_measurement(self):
        other = sqlite3.connect(self.path, isolation_level=None)
        try:
            other.execute('BEGIN IMMEDIATE')
            result = self.run_b()
            self.assertEqual(result.local.outcome, p.OutcomeCode.BUSY_REJECTED)
            self.assertTrue(result.reconciliation_required)
            self.assertFalse(self.store._poisoned)
            self.assertEqual(self.calls, ['qualify'])
        finally:
            other.execute('ROLLBACK'); other.close()

    def test_uncertain_commit_cleanup_is_not_nonexecution_proof(self):
        connection, calls = self.store._connection, []
        class BeforeCommit:
            def __getattr__(inner, name): return getattr(connection, name)
            def execute(inner, sql, *args):
                calls.append(sql)
                if sql == 'COMMIT': raise sqlite3.OperationalError('unproven dispatch')
                return connection.execute(sql, *args)
        self.store._connection = BeforeCommit()
        result = self.run_b()
        self.assertEqual(result.local.outcome, p.OutcomeCode.STORAGE_UNKNOWN)
        self.assertEqual(calls.count('COMMIT'), 1)
        self.assertEqual(calls.count('ROLLBACK'), 1)
        self.assertTrue(result.reconciliation_required)
        self.assertTrue(self.store._poisoned)

    def test_t2_rollback_uncertainty_has_no_commit_or_false_rejection(self):
        connection, calls = self.store._connection, []
        class BrokenRollback:
            def __getattr__(inner, name): return getattr(connection, name)
            def execute(inner, sql, *args):
                calls.append(sql)
                if sql == 'ROLLBACK': raise sqlite3.OperationalError('cleanup unavailable')
                return connection.execute(sql, *args)
        self.store._connection = BrokenRollback()
        self.points = [1000, 90001]
        result = self.run_b()
        self.assertEqual(result.local.outcome, p.OutcomeCode.STORAGE_UNKNOWN)
        self.assertNotIn('COMMIT', calls)
        self.assertEqual(calls.count('ROLLBACK'), 1)
        self.assertTrue(self.store._poisoned)

    def test_unsupported_model_binding_rejects_before_qualification(self):
        self.adapter = replace(self.adapter, support=replace(self.adapter.support, interpretation=self.proof))
        with self.assertRaises(core.CommandRejected): self.run_b()
        self.assertEqual(self.calls, [])

    def test_genuine_lease_continuation_is_independently_applicable(self):
        self.rewrite_qualification(self.q.g.TimeEvidence, 'lease_applicability', self.v.TimingApplicability.REQUIRED)
        self.rewrite_qualification(self.q.g.TimeEvidence, 'lease_deadline', self.v.StrictDeadline(14))
        self.assertTrue(self.run_b().reconciliation_required)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), [(1,)])

    def test_foreign_qualification_rejected_without_hooks(self):
        class Foreign:
            def __getattribute__(inner, name): raise AssertionError('foreign traversal')
            def __eq__(inner, other): raise AssertionError('foreign equality')
        self.qualified = Foreign()
        with self.assertRaises((core.CommandRejected, self.v.TimeRejected)): self.run_b()
        self.assertEqual(self.calls, [])

    def test_precommit_confirmed_cleanup_signal_cannot_fabricate_confirmation(self):
        with patch.object(core, '_append', side_effect=s._ConfirmedCommitCleanup()):
            result = self.run_b()
        self.assertEqual(result.local.outcome, p.OutcomeCode.AUTHORITY_REJECTED)
        self.assertIsNone(result.local.storage_result)
        self.assertTrue(result.reconciliation_required)
        self.assertIsNot(result.reason, s._CommitCleanupReason.CURSOR_CLOSE)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), [(1,)])

    def test_statement_rejection_does_not_invent_clock_or_unknown_outcome(self):
        with patch.object(core, '_append', side_effect=s.StorageRejected('statement rejected')):
            result = self.run_b()
        self.assertIsNone(result.local)
        self.assertTrue(result.reconciliation_required)
        self.assertEqual(result.reason, self.v.AdmissionReason.UNAVAILABLE)
        self.assertFalse(self.store._connection.in_transaction)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), [(1,)])

    def test_existing_reservation_no_separate_read_between_m1_and_update(self):
        self.command = p.decode_record(self.store.read_rows(s.CommandRow)[0].canonical_payload_bytes, p.CommandPayload)
        self.command, self.material = CommandsTests.mutate(self, 'b-record')
        self.material = replace(self.material, utc_time=10, last_valid_utc=999)
        self.qualified = self.make_qualification()
        self.adapter = replace(self.adapter, support=self.qualified.inputs.support)
        connection = self.store._connection
        between, mutations = [], []
        self.measure_hook = lambda: between.append(True) if len(self.points) == 2 else None
        class FirstWrite:
            def __getattr__(inner, name): return getattr(connection, name)
            def execute(inner, sql, *args):
                if between:
                    self.assertTrue(sql.startswith('UPDATE RESERVATIONS'))
                    mutations.append(sql)
                    between.clear()
                return connection.execute(sql, *args)
        self.store._connection = FirstWrite()
        result = self.run_b()
        self.assertEqual(result.local.outcome, p.OutcomeCode.SUCCESS)
        self.assertEqual(len(mutations), 1)


def b_changed_proof_inputs(test, response, path, value):
    inputs = test.q._copy(response.inputs)
    owner = inputs
    names = path.split('.')
    for name in names[:-1]: owner = object.__getattribute__(owner, name)
    object.__setattr__(owner, names[-1], value)
    return replace(response, inputs=inputs)


def b_proof_case(name, transform):
    def test(self):
        self.proof_transform = lambda response: transform(self, response)
        with self.assertRaises((core.CommandRejected, self.v.TimeRejected)): self.run_b()
        self.assertEqual(self.calls, ['qualify'])
        self.assertFalse(self.store._connection.in_transaction)
    setattr(QualifiedWriterTests, 'test_proof_' + name, test)


for _name, _transform in (
    ('invalid', lambda t, v: replace(v, validity=t.v.EvidenceValidity.INVALID)),
    ('unknown', lambda t, v: replace(v, validity=t.v.EvidenceValidity.UNKNOWN)),
    ('boolean', lambda t, v: True),
    ('implementation', lambda t, v: replace(v, implementation=t.proof)),
    ('measurement', lambda t, v: replace(v, measurement=t.proof)),
    ('process', lambda t, v: replace(v, process_id='other')),
    ('domain', lambda t, v: replace(v, domain_id='other')),
    ('unknown_applicability', lambda t, v: replace(v, completion_applicability=t.v.TimingApplicability.UNKNOWN)),
    ('required_missing', lambda t, v: replace(v, completion_applicability=t.v.TimingApplicability.REQUIRED)),
    ('not_applicable_deadline', lambda t, v: replace(v, completion_deadline=t.v.StrictDeadline(100))),
    ('sample', lambda t, v: b_changed_proof_inputs(t, v, 'observation.time.sample.sample', t.proof)),
    ('profile', lambda t, v: b_changed_proof_inputs(t, v, 'observation.time.sample.profile', t.proof)),
    ('source', lambda t, v: b_changed_proof_inputs(t, v, 'observation.time.sample.source', 'other')),
    ('model', lambda t, v: b_changed_proof_inputs(t, v, 'support.model', t.proof)),
    ('interpretation', lambda t, v: b_changed_proof_inputs(t, v, 'support.interpretation', t.proof)),
): b_proof_case(_name, _transform)


def b_point_case(name, points, process='process', domain='domain'):
    def test(self):
        self.points = list(points)
        if process != 'process' or domain != 'domain':
            self.adapter = replace(self.adapter, measure=lambda: self.v.MonotonicPoint(process, domain, 1000))
        result = self.run_b()
        self.assertTrue(result.reconciliation_required)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), [(1,)])
    setattr(QualifiedWriterTests, 'test_point_' + name, test)


for _name, _points, _process, _domain in (
    ('before_scope', (0, 4000), 'process', 'domain'),
    ('beyond_scope', (90001, 90002), 'process', 'domain'),
    ('permit_expired_at_t1', (3000, 4000), 'process', 'domain'),
    ('backward_t2', (1000, 500), 'process', 'domain'),
    ('process', (1000, 4000), 'other', 'domain'),
    ('domain', (1000, 4000), 'process', 'other'),
): b_point_case(_name, _points, _process, _domain)


def b_error_case(name, value):
    def test(self):
        self.error_value = value
        result = self.run_b()
        self.assertEqual(result.local.outcome, p.OutcomeCode.CLOCK_REJECTED)
        self.assertEqual(self.raw('SELECT count(*) FROM COMMANDS'), [(1,)])
    setattr(QualifiedWriterTests, 'test_error_' + name, test)


def b_consumption_expiry_case(name):
    def test(self):
        self.rewrite_qualification(self.v.CommandPermit, 'valid_until_us', 13 if name == 'permit' else 100)
        self.rewrite_qualification(self.q.g.AuthorizationEvidence, 'deadline', self.v.InclusiveDeadline(12 if name == 'authorization' else 100))
        self.rewrite_qualification(self.q.g.ApprovalEvidence, 'deadline', self.v.InclusiveDeadline(12 if name == 'approval' else 100))
        result = self.run_b()
        self.assertEqual(result.local.outcome, p.OutcomeCode.SUCCESS)
        self.assertEqual(result.t2.evaluation.interval.lower_us, 14)
    setattr(QualifiedWriterTests, 'test_consumption_only_expiry_' + name, test)


for _name in ('permit', 'authorization', 'approval'): b_consumption_expiry_case(_name)


for _name, _value in (('bool', True), ('float', 0.0), ('negative', -1), ('foreign', object()),
                       ('overflow', 1 << 63), ('uncertainty', 100000)):
    b_error_case(_name, _value)


if __name__=='__main__':
    unittest.main(verbosity=2)
