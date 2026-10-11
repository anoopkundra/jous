"""IL.3 local storage only. No lease/command permission, genesis or operational init.

SCHEMA_SQL is a frozen schema definition, not an initializer. Only synthetic tests
create databases. Opening validates existing files; no repair/migration is attempted.
Successful transaction exit proves only LOCAL_STORAGE_COMMIT_CONFIRMED, never an ack.
Private SQLite internals are not a security boundary against hostile Python callers;
future issuer access control and filesystem qualification remain mandatory.
"""
from contextlib import contextmanager
from dataclasses import dataclass, fields
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
import sqlite3

from fixture_lease_contract import (
    ArtifactType, Command, LeaseStatus, Operation, Phase, decode_conflict,
)

SCHEMA_VERSION = 1
MAX_INTEGER = (1 << 63) - 1
MAX_BYTES = 1024 * 1024


class StorageRejected(RuntimeError):
    """Finite fail-closed storage error, without supplied paths/data/SQL."""


class StorageOutcomeUncertain(StorageRejected):
    """Commit/rollback not proven. Handle suspended; no retry or success inference."""


class LocalStorageResult(StrEnum):
    LOCAL_STORAGE_COMMIT_CONFIRMED = 'LOCAL_STORAGE_COMMIT_CONFIRMED'
    LOCAL_STORAGE_ROLLBACK_CONFIRMED = 'LOCAL_STORAGE_ROLLBACK_CONFIRMED'


class ExecutionState(StrEnum):
    NOT_STARTED = 'NOT_STARTED'
    STARTED = 'STARTED'
    STOPPED_KNOWN = 'STOPPED_KNOWN'
    UNKNOWN = 'UNKNOWN'


class QuarantineReason(StrEnum):
    CLOCK_UNCERTAIN = 'CLOCK_UNCERTAIN'
    STORAGE_UNCERTAIN = 'STORAGE_UNCERTAIN'
    AUTHORITY_UNCERTAIN = 'AUTHORITY_UNCERTAIN'
    ACK_UNCERTAIN = 'ACK_UNCERTAIN'
    PHASE_UNCERTAIN = 'PHASE_UNCERTAIN'
    EXECUTION_UNCERTAIN = 'EXECUTION_UNCERTAIN'
    EXPIRED_UNRECONCILED = 'EXPIRED_UNRECONCILED'
    EVIDENCE_MISMATCH = 'EVIDENCE_MISMATCH'
    INTEGRITY_FAILURE = 'INTEGRITY_FAILURE'


class OutcomeCode(StrEnum):
    SUCCESS = 'SUCCESS'
    CONFLICT_REJECTED = 'CONFLICT_REJECTED'
    BUSY_REJECTED = 'BUSY_REJECTED'
    MALFORMED_REJECTED = 'MALFORMED_REJECTED'
    APPROVAL_REJECTED = 'APPROVAL_REJECTED'
    AUTHORITY_REJECTED = 'AUTHORITY_REJECTED'
    CLOCK_REJECTED = 'CLOCK_REJECTED'
    PHASE_REJECTED = 'PHASE_REJECTED'
    REVISION_REJECTED = 'REVISION_REJECTED'
    REPLAY_MISMATCH = 'REPLAY_MISMATCH'
    CLOSURE_REJECTED = 'CLOSURE_REJECTED'
    STORAGE_UNKNOWN = 'STORAGE_UNKNOWN'


class EventType(StrEnum):
    REQUESTED = 'REQUESTED'
    REJECTED = 'REJECTED'
    RESERVED = 'RESERVED'
    ACKNOWLEDGED = 'ACKNOWLEDGED'
    PHASE_ADVANCE_REQUESTED = 'PHASE_ADVANCE_REQUESTED'
    PHASE_ADVANCED = 'PHASE_ADVANCED'
    EXECUTION_RECORDED = 'EXECUTION_RECORDED'
    EXPIRED = 'EXPIRED'
    QUARANTINED = 'QUARANTINED'
    RELEASE_REQUESTED = 'RELEASE_REQUESTED'
    RELEASED = 'RELEASED'
    RECOVERY_APPROVED = 'RECOVERY_APPROVED'
    RECOVERED = 'RECOVERED'


def _require(condition):
    if not condition:
        raise StorageRejected('STORAGE_REJECTED')


# Explicit field domains generate identical SQL and strict typed serialization.
# No column name/type is accepted from a caller.
ID = 'id'
DIGEST = 'digest'
BLOB = 'blob'
UINT = 'uint'
UTC = 'utc'
BOOL = 'bool'
KEY = 'key'


@dataclass(frozen=True)
class MetadataRow:
    singleton: int
    schema_version: int
    register_id: str
    issuer_generation: int
    activation_id: str
    fixture_plan_sha256: bytes
    bootstrap_amendment_sha256: bytes
    provisioning_contract_sha256: bytes
    design_sha256: bytes
    last_event_sequence: int
    last_event_digest: bytes
    state_digest: bytes
    last_valid_utc: int
    recovery_required: int


@dataclass(frozen=True)
class ArtifactRow:
    artifact_id: str
    artifact_type: ArtifactType
    exact_bytes: bytes
    sha256: bytes
    approval_record_bytes: bytes
    approval_record_hash: bytes
    approver: str
    authorization_ref: str
    operation_type: Operation
    phase: Phase
    predecessor_artifact_id: str | None


@dataclass(frozen=True)
class ReservationRow:
    reservation_id: str
    register_id: str
    fixture_set_id: str
    operation_type: Operation
    phase: Phase
    binding_kind: ArtifactType
    binding_artifact_id: str
    binding_sha256: bytes
    immutable_db_projection: bytes
    immutable_db_projection_hash: bytes
    owner: str
    authorization_ref: str
    requested_at: int
    acquired_at: int
    acknowledged_at: int
    expires_at: int
    completion_deadline: int
    revision: int
    lease_status: LeaseStatus
    expired_condition: int
    execution_state: ExecutionState
    release_evidence_artifact_id: str | None
    quarantine_reason: QuarantineReason | None
    recovery_evidence_artifact_id: str | None


@dataclass(frozen=True)
class ClaimRow:
    canonical_key: bytes
    reservation_id: str
    introduced_revision: int
    originating_artifact_id: str


@dataclass(frozen=True)
class CommandRow:
    command_id: str
    authenticated_principal: str
    command_kind: Command
    canonical_payload_bytes: bytes
    canonical_payload_hash: bytes
    expected_revision: int
    reservation_id: str | None
    outcome_code: OutcomeCode
    durable_ack_bytes: bytes | None
    transition_event_sequence: int | None


@dataclass(frozen=True)
class EventRow:
    event_sequence: int
    command_id: str
    reservation_id: str | None
    register_id: str
    issuer_generation: int
    activation_id: str
    event_type: EventType
    utc_time: int
    prior_digest: bytes
    event_bytes: bytes
    event_digest: bytes
    revision: int
    artifact_id: str | None
    evidence_artifact_id: str | None


# A trailing '?' denotes explicitly nullable fields only.
SPECS = {
    MetadataRow: ('REGISTER_METADATA', (
        UINT, UINT, ID, UINT, ID, DIGEST, DIGEST, DIGEST, DIGEST,
        UINT, DIGEST, DIGEST, UTC, BOOL)),
    ArtifactRow: ('APPROVED_ARTIFACTS', (
        ID, ArtifactType, BLOB, DIGEST, BLOB, DIGEST, ID, ID, Operation, Phase, 'id?')),
    ReservationRow: ('RESERVATIONS', (
        ID, ID, ID, Operation, Phase, ArtifactType, ID, DIGEST, BLOB, DIGEST,
        ID, ID, UTC, UTC, UTC, UTC, UTC, UINT, LeaseStatus, BOOL, ExecutionState,
        'id?', (QuarantineReason, True), 'id?')),
    ClaimRow: ('BLOCKING_CLAIMS', (KEY, ID, UINT, ID)),
    CommandRow: ('COMMANDS', (
        ID, ID, Command, BLOB, DIGEST, UINT, 'id?', OutcomeCode, 'blob?', 'uint?')),
    EventRow: ('EVENTS', (
        UINT, ID, 'id?', ID, UINT, ID, EventType, UTC, DIGEST, BLOB, DIGEST,
        UINT, 'id?', 'id?')),
}


def _domain(domain):
    if type(domain) is tuple:
        return domain
    if type(domain) is str and domain.endswith('?'):
        return domain[:-1], True
    return domain, False


def _validate(value, domain, decode=False):
    kind, optional = _domain(domain)
    if value is None:
        _require(optional)
        return None
    if isinstance(kind, type) and issubclass(kind, StrEnum):
        if decode:
            _require(type(value) is str)
            try:
                return kind(value)
            except ValueError:
                raise StorageRejected('UNKNOWN_DURABLE_ENUM') from None
        _require(type(value) is kind)
        return value.value
    if kind == ID:
        _require(type(value) is str and bool(value.strip()))
        try:
            encoded = value.encode('utf-8', 'strict')
        except UnicodeError:
            raise StorageRejected('INVALID_IDENTIFIER') from None
        _require(1 <= len(encoded) <= 255)
    elif kind in (DIGEST, BLOB, KEY):
        _require(type(value) is bytes)
        if kind == DIGEST:
            _require(len(value) == 32)
        else:
            _require(1 <= len(value) <= MAX_BYTES)
        if kind == KEY:
            try:
                decode_conflict(value)
            except ValueError:
                raise StorageRejected('INVALID_CANONICAL_KEY') from None
    else:
        _require(type(value) is int and -(1 << 63) <= value <= MAX_INTEGER)
        if kind == UINT:
            _require(value >= 0)
        if kind == BOOL:
            _require(value in (0, 1))
    return value


def _values(row):
    _require(type(row) in SPECS)
    domains = SPECS[type(row)][1]
    return tuple(_validate(getattr(row, field.name), domain)
                 for field, domain in zip(fields(row), domains))


def _decode(row_type, values):
    _require(type(values) is tuple and len(values) == len(fields(row_type)))
    row = row_type(*(_validate(value, domain, True)
                     for value, domain in zip(values, SPECS[row_type][1])))
    _validate_row(row)
    return row


def _validate_row(row):
    _values(row)
    if type(row) is MetadataRow:
        _require(row.singleton == 1 and row.schema_version == SCHEMA_VERSION
                 and row.issuer_generation >= 1)
    elif type(row) is ArtifactRow:
        _require(sha256(row.exact_bytes).digest() == row.sha256)
        _require(sha256(row.approval_record_bytes).digest() == row.approval_record_hash)
        _require((row.operation_type is Operation.FIXTURE_PROVISIONING
                  and row.phase in (Phase.PRE_AUTH, Phase.AUTH_IDENTITIES_BOUND))
                 or (row.operation_type is not Operation.FIXTURE_PROVISIONING
                     and row.phase is Phase.NOT_APPLICABLE))
        if row.artifact_type is ArtifactType.PROVISIONING_REQUEST:
            _require(row.operation_type is Operation.FIXTURE_PROVISIONING)
        if row.artifact_type is ArtifactType.FIXTURE_MANIFEST:
            _require(row.operation_type is Operation.CANARY)
    elif type(row) is ReservationRow:
        _require((row.operation_type is Operation.FIXTURE_PROVISIONING
                  and row.phase in (Phase.PRE_AUTH, Phase.AUTH_IDENTITIES_BOUND)
                  and row.binding_kind is ArtifactType.PROVISIONING_REQUEST)
                 or (row.operation_type is Operation.CANARY and row.phase is Phase.NOT_APPLICABLE
                     and row.binding_kind is ArtifactType.FIXTURE_MANIFEST))
        _require(row.requested_at <= row.acquired_at <= row.acknowledged_at
                 < row.expires_at and row.completion_deadline < row.expires_at)
        _require(sha256(row.immutable_db_projection).digest() == row.immutable_db_projection_hash)
        if row.lease_status is LeaseStatus.QUARANTINED:
            _require(row.quarantine_reason is not None)
        if row.lease_status is LeaseStatus.RELEASED:
            _require(row.release_evidence_artifact_id is not None
                     or row.recovery_evidence_artifact_id is not None)
    elif type(row) is CommandRow:
        _require(sha256(row.canonical_payload_bytes).digest() == row.canonical_payload_hash)
        if row.outcome_code is OutcomeCode.SUCCESS:
            _require(row.durable_ack_bytes is not None and row.transition_event_sequence is not None
                     and row.reservation_id is not None)
        else:
            _require(row.durable_ack_bytes is None)
    elif type(row) is EventRow:
        _require(row.event_sequence >= 1 and row.issuer_generation >= 1)


def _column(name, domain):
    kind, optional = _domain(domain)
    sql_type = ('TEXT' if kind == ID or isinstance(kind, type) else
                'BLOB' if kind in (DIGEST, BLOB, KEY) else 'INTEGER')
    checks = []
    if kind == ID:
        checks.append(f"length(CAST({name} AS BLOB)) BETWEEN 1 AND 255 AND length(trim({name})) > 0")
    elif isinstance(kind, type):
        allowed = ','.join("'" + x.value + "'" for x in kind)
        checks.append(f'{name} IN ({allowed})')
    elif kind == DIGEST:
        checks.append(f'length({name}) = 32')
    elif kind in (BLOB, KEY):
        checks.append(f'length({name}) BETWEEN 1 AND {MAX_BYTES}')
    elif kind == UINT:
        checks.append(f'{name} >= 0')
    elif kind == BOOL:
        checks.append(f'{name} IN (0,1)')
    return f'{name} {sql_type}' + ('' if optional else ' NOT NULL') + ''.join(
        f' CHECK ({check})' for check in checks)


# All foreign keys RESTRICT. Deferred cyclic command/event links close at commit.
EXTRAS = {
    MetadataRow: ['PRIMARY KEY(singleton)', 'CHECK(singleton = 1)',
                  f'CHECK(schema_version = {SCHEMA_VERSION})', 'UNIQUE(register_id)',
                  'CHECK(issuer_generation >= 1)'],
    ArtifactRow: ['PRIMARY KEY(artifact_id)', 'UNIQUE(artifact_type,sha256)',
                  'FOREIGN KEY(predecessor_artifact_id) REFERENCES APPROVED_ARTIFACTS(artifact_id) ON DELETE RESTRICT',
                  "CHECK((operation_type = 'FIXTURE_PROVISIONING' AND phase IN ('PRE_AUTH_PROVISIONING_REQUEST','AUTH_IDENTITIES_BOUND')) OR (operation_type != 'FIXTURE_PROVISIONING' AND phase = 'NOT_APPLICABLE'))",
                  "CHECK(artifact_type != 'PROVISIONING_REQUEST' OR operation_type = 'FIXTURE_PROVISIONING')",
                  "CHECK(artifact_type != 'FIXTURE_MANIFEST' OR operation_type = 'CANARY')"],
    ReservationRow: ['PRIMARY KEY(reservation_id)',
        'FOREIGN KEY(register_id) REFERENCES REGISTER_METADATA(register_id) ON DELETE RESTRICT',
        'FOREIGN KEY(binding_artifact_id) REFERENCES APPROVED_ARTIFACTS(artifact_id) ON DELETE RESTRICT',
        'FOREIGN KEY(release_evidence_artifact_id) REFERENCES APPROVED_ARTIFACTS(artifact_id) ON DELETE RESTRICT',
        'FOREIGN KEY(recovery_evidence_artifact_id) REFERENCES APPROVED_ARTIFACTS(artifact_id) ON DELETE RESTRICT',
        "CHECK((operation_type = 'FIXTURE_PROVISIONING' AND phase IN ('PRE_AUTH_PROVISIONING_REQUEST','AUTH_IDENTITIES_BOUND') AND binding_kind = 'PROVISIONING_REQUEST') OR (operation_type = 'CANARY' AND phase = 'NOT_APPLICABLE' AND binding_kind = 'FIXTURE_MANIFEST'))",
        'CHECK(requested_at <= acquired_at AND acquired_at <= acknowledged_at AND acknowledged_at < expires_at AND completion_deadline < expires_at)',
        "CHECK(lease_status != 'QUARANTINED' OR quarantine_reason IS NOT NULL)",
        "CHECK(lease_status != 'RELEASED' OR release_evidence_artifact_id IS NOT NULL OR recovery_evidence_artifact_id IS NOT NULL)"],
    ClaimRow: ['PRIMARY KEY(canonical_key)',
        'FOREIGN KEY(reservation_id) REFERENCES RESERVATIONS(reservation_id) ON DELETE RESTRICT',
        'FOREIGN KEY(originating_artifact_id) REFERENCES APPROVED_ARTIFACTS(artifact_id) ON DELETE RESTRICT'],
    CommandRow: ['PRIMARY KEY(command_id)',
        'FOREIGN KEY(reservation_id) REFERENCES RESERVATIONS(reservation_id) ON DELETE RESTRICT',
        'FOREIGN KEY(transition_event_sequence) REFERENCES EVENTS(event_sequence) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED',
        "CHECK((outcome_code = 'SUCCESS' AND durable_ack_bytes IS NOT NULL AND transition_event_sequence IS NOT NULL AND reservation_id IS NOT NULL) OR (outcome_code != 'SUCCESS' AND durable_ack_bytes IS NULL))"],
    EventRow: ['PRIMARY KEY(event_sequence)', 'CHECK(event_sequence >= 1)',
        'CHECK(issuer_generation >= 1)', 'UNIQUE(event_digest)',
        'FOREIGN KEY(command_id) REFERENCES COMMANDS(command_id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED',
        'FOREIGN KEY(reservation_id) REFERENCES RESERVATIONS(reservation_id) ON DELETE RESTRICT',
        'FOREIGN KEY(register_id) REFERENCES REGISTER_METADATA(register_id) ON DELETE RESTRICT',
        'FOREIGN KEY(artifact_id) REFERENCES APPROVED_ARTIFACTS(artifact_id) ON DELETE RESTRICT',
        'FOREIGN KEY(evidence_artifact_id) REFERENCES APPROVED_ARTIFACTS(artifact_id) ON DELETE RESTRICT'],
}
TABLE_SQL = {
    cls: 'CREATE TABLE ' + table + ' (' + ', '.join(
        [_column(field.name, domain) for field, domain in zip(fields(cls), domains)]
        + EXTRAS[cls]) + ') STRICT'
    for cls, (table, domains) in SPECS.items()
}
SCHEMA_SQL = ';\n'.join(TABLE_SQL.values()) + ';\n'


def _runtime():
    _require(sqlite3.sqlite_version_info >= (3, 45, 0) and sqlite3.threadsafety != 0)


def _profile(connection):
    # Inspect durable journal mode before connection-local PRAGMAs. Never repair it.
    _require(connection.execute('PRAGMA journal_mode').fetchone() == ('delete',))
    for name, value in (('synchronous', 3), ('foreign_keys', 1), ('busy_timeout', 0),
                        ('locking_mode', 'normal'), ('read_uncommitted', 0)):
        connection.execute(f'PRAGMA {name}={value}')
        _require(connection.execute(f'PRAGMA {name}').fetchone() == (value,))
    databases = connection.execute('PRAGMA database_list').fetchall()
    # integrity_check may instantiate SQLite's built-in temp schema. It is not
    # an ATTACH; no caller-created objects or third database are permitted.
    _require(databases[0][1] == 'main' and all(row[1] in ('main', 'temp') for row in databases))
    _require(connection.execute('SELECT count(*) FROM sqlite_temp_schema').fetchone() == (0,))


def _schema(connection):
    expected = sorted((SPECS[cls][0], TABLE_SQL[cls]) for cls in SPECS)
    actual = connection.execute(
        "SELECT name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    _require(actual == expected)
    # Also reject unexpected internal objects; SQLite-owned autoindexes are frozen
    # by exact CREATE TABLE constraints, not caller-generated index definitions.
    internal = connection.execute(
        "SELECT type,name,sql FROM sqlite_schema WHERE name LIKE 'sqlite_%'").fetchall()
    expected_indexes = {('index', 'sqlite_autoindex_' + table + '_' + str(number), None)
                        for table, count in (('REGISTER_METADATA', 1), ('APPROVED_ARTIFACTS', 2),
                                             ('RESERVATIONS', 1), ('BLOCKING_CLAIMS', 1),
                                             ('COMMANDS', 1), ('EVENTS', 1))
                        for number in range(1, count + 1)}
    _require(set(internal) == expected_indexes)


def _rows(connection, row_type):
    table = SPECS[row_type][0]
    names = ','.join(field.name for field in fields(row_type))
    return tuple(_decode(row_type, row) for row in connection.execute(
        f'SELECT {names} FROM {table} ORDER BY {fields(row_type)[0].name}').fetchall())


def _validate_register(connection, register_id):
    _schema(connection)
    _require(connection.execute('PRAGMA integrity_check').fetchall() == [('ok',)])
    _require(connection.execute('PRAGMA foreign_key_check').fetchall() == [])
    data = {cls: _rows(connection, cls) for cls in SPECS}
    _require(len(data[MetadataRow]) == 1 and data[MetadataRow][0].register_id == register_id)
    metadata = data[MetadataRow][0]
    artifacts = {row.artifact_id: row for row in data[ArtifactRow]}
    reservations = {row.reservation_id: row for row in data[ReservationRow]}
    commands = {row.command_id: row for row in data[CommandRow]}
    events = {row.event_sequence: row for row in data[EventRow]}
    for row in data[ReservationRow]:
        artifact = artifacts[row.binding_artifact_id]
        _require((row.binding_kind, row.binding_sha256, row.operation_type, row.phase)
                 == (artifact.artifact_type, artifact.sha256, artifact.operation_type, artifact.phase))
        for ref, kind in ((row.release_evidence_artifact_id, ArtifactType.RELEASE_EVIDENCE),
                          (row.recovery_evidence_artifact_id, ArtifactType.RECOVERY_EVIDENCE)):
            if ref is not None:
                _require(artifacts[ref].artifact_type is kind)
    for row in data[ClaimRow]:
        reservation = reservations[row.reservation_id]
        _require(reservation.lease_status is not LeaseStatus.RELEASED
                 and row.introduced_revision <= reservation.revision)
        _require(artifacts[row.originating_artifact_id].operation_type is reservation.operation_type)
    for reservation in data[ReservationRow]:
        if reservation.lease_status is not LeaseStatus.RELEASED:
            _require(any(claim.reservation_id == reservation.reservation_id for claim in data[ClaimRow]))
    for row in data[EventRow]:
        _require(row.register_id == metadata.register_id and row.issuer_generation <= metadata.issuer_generation)
        _require(commands[row.command_id].reservation_id == row.reservation_id)
    for row in data[CommandRow]:
        if row.transition_event_sequence is not None:
            _require(events[row.transition_event_sequence].command_id == row.command_id)
    # Event-chain/state-digest computation and complete claim derivation are IL.4+.


class TransactionWriter:
    """Typed insert-only primitives, no SQL, transitions, delete, replay or ack builder."""
    def __init__(self, store):
        self._store = store
        self._active = True
        self._failed = False
        self.result = None

    def insert(self, row):
        if not self._active or self._failed or self._store._writer is not self or self._store._poisoned:
            raise StorageRejected('WRITER_INACTIVE')
        try:
            _validate_row(row)
            table = SPECS[type(row)][0]
            names = ','.join(field.name for field in fields(row))
            values = _values(row)
            placeholders = ','.join('?' for _ in values)
            self._store._connection.execute(f'INSERT INTO {table} ({names}) VALUES ({placeholders})', values)
        except BaseException as error:
            if isinstance(error, sqlite3.Error) and getattr(error, 'sqlite_errorcode', 0) & 255 in (
                    sqlite3.SQLITE_FULL, sqlite3.SQLITE_IOERR, sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB):
                self._store._poisoned = True
            self._failed = True
            if isinstance(error, (StorageRejected, sqlite3.Error)):
                raise StorageRejected('WRITE_REJECTED') from None
            raise


class LeaseStore:
    """Existing-only storage handle. This handle does NOT prove issuer authority."""
    def __init__(self, path, register_id):
        _runtime()
        _validate(register_id, ID)
        _require(type(path) is Path or isinstance(path, Path))
        _require(path.is_absolute())
        # Reject lexical redirection; no directory or file creation.
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            raise StorageRejected('PATH_REJECTED') from None
        _require(path == resolved)
        _require(path.is_file())
        self._connection = None
        self._writer = None
        self._poisoned = False
        self._register_id = register_id
        try:
            self._connection = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True,
                                               isolation_level=None, timeout=0)
            self._connection.enable_load_extension(False)
            _profile(self._connection)
            self._connection.execute('BEGIN')
            _validate_register(self._connection, register_id)
            self._connection.execute('ROLLBACK')
        except (sqlite3.Error, StorageRejected, KeyError):
            if self._connection is not None:
                self._connection.close()
            self._poisoned = True
            raise StorageRejected('OPEN_REJECTED') from None

    def read_rows(self, row_type):
        _require(not self._poisoned and self._connection is not None and self._writer is None)
        _require(row_type in SPECS)
        try:
            self._connection.execute('BEGIN')
            _validate_register(self._connection, self._register_id)
            result = _rows(self._connection, row_type)
            self._connection.execute('ROLLBACK')
            return result
        except (sqlite3.Error, StorageRejected, KeyError):
            self._poisoned = True
            raise StorageRejected('READ_REJECTED') from None

    @contextmanager
    def transaction(self):
        _require(not self._poisoned and self._connection is not None and self._writer is None)
        try:
            _profile(self._connection)
            self._connection.execute('BEGIN IMMEDIATE')
        except sqlite3.Error as error:
            if getattr(error, 'sqlite_errorcode', 0) & 255 not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                self._poisoned = True
            raise StorageRejected('BEGIN_REJECTED') from None
        except StorageRejected:
            self._poisoned = True
            raise
        writer = TransactionWriter(self)
        self._writer = writer
        try:
            yield writer
            _require(not writer._failed)
            _validate_register(self._connection, self._register_id)
        except BaseException:
            try:
                self._connection.execute('ROLLBACK')
                writer.result = LocalStorageResult.LOCAL_STORAGE_ROLLBACK_CONFIRMED
            except BaseException:
                self._poisoned = True
                raise StorageOutcomeUncertain('ROLLBACK_UNKNOWN') from None
            raise
        else:
            try:
                self._connection.execute('COMMIT')
                writer.result = LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED
            except BaseException:
                self._poisoned = True
                # Best-effort bounded cleanup, NEVER claim rollback of unknown commit.
                try:
                    if self._connection.in_transaction:
                        self._connection.execute('ROLLBACK')
                except BaseException:
                    pass
                raise StorageOutcomeUncertain('COMMIT_UNKNOWN') from None
        finally:
            writer._active = False
            self._writer = None

    def close(self):
        _require(self._writer is None)
        if self._connection is not None:
            try:
                self._connection.close()
            except sqlite3.Error:
                self._poisoned = True
                raise StorageOutcomeUncertain('CLOSE_UNKNOWN') from None
            finally:
                self._connection = None
