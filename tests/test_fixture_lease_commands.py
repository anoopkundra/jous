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
for name in ('fixture_lease_contract', 'fixture_lease_protocol', 'fixture_lease_store', 'fixture_lease_commands'):
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
        self.assertEqual(imports,{'contextlib','dataclasses','enum','hashlib','pathlib','fixture_lease_contract'})
        commands_ast=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_commands.py').read_text())
        self.assertFalse(any(isinstance(node,ast.ImportFrom) and node.module and
            'service' in node.module for node in ast.walk(commands_ast)))

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


if __name__=='__main__':
    unittest.main(verbosity=2)
