"""Testable collector lifecycle; no connections, credentials, or SQL execution.

Future authorized callers provide an already TLS/target/read-only verified
EvidenceConnection and owned cleanup operations. Writers receive non-secret
bytes only. Neither a complete snapshot nor an amendment authorizes execution.
"""
import copy
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import tempfile


REQUIRED_GATES = frozenset(('client_tls', 'target', 'read_only', 'server_database',
    'revision', 'tables', 'operator', 'policies', 'roles_memberships',
    'ownership_collision', 'privilege_boundary', 'structural_dependencies',
    'public_compatibility', 'effective_grants', 'migration_admin'))


def encode(document):
    return (json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + '\n').encode('utf-8')


def atomic_publish(path, payload, *, expected_sha256):
    """Future local writer. Preserve existing artifact on pre-replace failure.

    This is not a compare-and-swap against hostile concurrent filesystem writers.
    The separately authorized caller must own the isolated artifact destination.
    Never pass archive-controlled paths. No symlinks/reparse destinations allowed.
    """
    path = Path(path)
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or (hasattr(ancestor, 'is_junction') and ancestor.is_junction()):
            raise ValueError('ARTIFACT_REDIRECTION')
    current = path.read_bytes() if path.exists() else None
    observed = hashlib.sha256(current).hexdigest() if current is not None else None
    if observed != expected_sha256:
        raise ValueError('ARTIFACT_PREIMAGE_CHANGED')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent,
                prefix=path.name + '.', suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        if temporary.read_bytes() != payload:
            raise ValueError('ARTIFACT_WRITE_MISMATCH')
        os.replace(temporary, path)
        temporary = None
        if path.read_bytes() != payload:
            raise ValueError('ARTIFACT_POSTIMAGE_CHANGED')
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@dataclass
class FinalizationState:
    # All post-cleanup inputs and outcomes are initialized unconditionally.
    evidence: object
    metadata: dict = field(default_factory=dict)
    passed_gates: set = field(default_factory=set)
    document: dict | None = None
    primary_payload: bytes | None = None
    primary_written: bool = False
    primary_identity: dict | None = None
    amendment_bytes: bytes | None = None
    amendment_payload: bytes | None = None
    amendment_written: bool = False
    amendment_identity: dict | None = None
    cleanup: dict = field(default_factory=lambda: {
        'rollback': 'NOT_ATTEMPTED', 'close': 'NOT_ATTEMPTED', 'dispose': 'NOT_ATTEMPTED'})
    finalization_failure: str | None = None
    secondary_failure: str | None = None
    phase: str = 'READY'

    def record_gate(self, name):
        if self.phase != 'COLLECTING' or name not in REQUIRED_GATES:
            raise ValueError('UNREVIEWED_COLLECTION_GATE')
        self.passed_gates.add(name)


def incomplete(document, gate, reason):
    result = copy.deepcopy(document)
    result.update(status='INCOMPLETE_FAIL_CLOSED', collection_complete=False,
        compatibility_approved=False, execution_approved=False, migration_ready=False)
    if not result.get('failure_gate'):
        result.update(failure_gate=gate, failure_reason=reason)
    return result


async def run_lifecycle(state, *, collection, rollback, close, dispose,
        primary_writer, amendment_reader=None, amendment_writer=None,
        primary_serializer=encode, amendment_serializer=encode):
    """One-shot lifecycle. Injected collection is the reviewed SELECT-only path.

    Cleanup callbacks are attempted separately even after BaseException. Failed
    cleanup prevents publication; the state retains an explicitly incomplete
    document for operator recovery. Primary publication is independent of every
    amendment input/operation. No exception message, repr, or traceback is stored.
    """
    if state.phase != 'READY':
        raise ValueError('FINALIZATION_ALREADY_STARTED')
    state.phase = 'COLLECTING'
    interrupted = False
    try:
        state.document = await collection(state)
    except BaseException:
        interrupted = True
    finally:
        # Do not perform fallible document copying/serialization before cleanup.
        state.phase = 'CLEANUP'
        for name, operation in (('rollback', rollback), ('close', close), ('dispose', dispose)):
            try:
                await operation()
            except BaseException:
                state.cleanup[name] = 'FAILED'
            else:
                state.cleanup[name] = 'PASS'
    # Recover the authoritative retained document, not a caller-created substitute.
    # The evidence object remains owned throughout cleanup and finalization.
    try:
        retained = (state.evidence.failure_document('COLLECTOR_EXCEPTION') if interrupted
                    else state.evidence.retained_document())
        if retained is None:
            retained = state.evidence.failure_document('COLLECTION_DOCUMENT_MISSING')
        state.document = retained
    except BaseException:
        state.finalization_failure = 'DOCUMENT_FINALIZATION_FAILED'
        state.phase = 'FAILED'
        return state
    if state.document.get('collection_complete') is True and state.passed_gates != REQUIRED_GATES:
        state.document = incomplete(state.document, 'COLLECTION_GATES_INCOMPLETE',
            'Not every required pre-migration gate passed.')
    state.document.update(execution_approved=False, compatibility_approved=False,
        migration_ready=False,
        cleanup=copy.deepcopy(state.cleanup), passed_gates=sorted(state.passed_gates))
    try:
        metadata = copy.deepcopy(state.metadata)
        encode(metadata)  # Invalid ancillary metadata must not suppress observations.
        state.document['lifecycle_metadata'] = metadata
    except BaseException:
        state.secondary_failure = 'METADATA_FINALIZATION_FAILED'
    if any(value != 'PASS' for value in state.cleanup.values()):
        state.finalization_failure = 'CLEANUP_FAILED'
        state.document = incomplete(state.document, 'CLEANUP_FAILED',
            'Cleanup did not fully succeed; primary publication withheld.')
        state.phase = 'FAILED'
        return state
    state.phase = 'PRIMARY'
    try:
        state.primary_payload = primary_serializer(state.document)
        if type(state.primary_payload) is not bytes:
            raise ValueError('PRIMARY_SERIALIZER_TYPE')
        if json.loads(state.primary_payload) != state.document:
            raise ValueError('PRIMARY_SERIALIZER_MISMATCH')
    except BaseException:
        state.finalization_failure = 'PRIMARY_SERIALIZATION_FAILED'
        state.document = incomplete(state.document, state.finalization_failure,
            'Primary serialization failed; no complete artifact was published.')
        state.phase = 'FAILED'
        return state
    try:
        primary_writer(state.primary_payload)
    except BaseException:
        state.finalization_failure = 'PRIMARY_WRITE_FAILED'
        state.document = incomplete(state.document, state.finalization_failure,
            'Primary write was not confirmed; no complete artifact is claimed.')
        state.phase = 'FAILED'
        return state
    state.primary_written = True
    state.primary_identity = {'size': len(state.primary_payload),
        'sha256': hashlib.sha256(state.primary_payload).hexdigest()}
    # No secondary lookup/validation/serialization can suppress the primary write.
    if state.document['collection_complete'] is not True:
        state.phase = 'FINISHED'
        return state
    if amendment_reader is None and amendment_writer is None:
        state.phase = 'FINISHED'
        return state
    state.phase = 'AMENDMENT'
    stage = 'AMENDMENT_INPUT_FAILED'
    try:
        state.amendment_bytes = amendment_reader()
        if type(state.amendment_bytes) is not bytes:
            raise ValueError('AMENDMENT_INPUT_TYPE')
        amendment = json.loads(state.amendment_bytes)
        if type(amendment) is not dict or amendment.get('execution_approved') is not False:
            raise ValueError('AMENDMENT_NOT_FAIL_CLOSED')
        # The amendment is always non-executable; actual observed values stay in
        # primary evidence. Linking it does not automatically approve any drift.
        amendment.update(execution_approved=False,
            managed_evidence_sha256=state.primary_identity['sha256'])
        stage = 'AMENDMENT_SERIALIZATION_FAILED'
        state.amendment_payload = amendment_serializer(amendment)
        if type(state.amendment_payload) is not bytes:
            raise ValueError('AMENDMENT_SERIALIZER_TYPE')
        if json.loads(state.amendment_payload) != amendment:
            raise ValueError('AMENDMENT_SERIALIZER_MISMATCH')
        stage = 'AMENDMENT_WRITE_FAILED'
        amendment_writer(state.amendment_payload)
        state.amendment_written = True
        state.amendment_identity = {'size': len(state.amendment_payload),
            'sha256': hashlib.sha256(state.amendment_payload).hexdigest()}
    except BaseException:
        state.secondary_failure = stage
    state.phase = 'FINISHED'
    return state
