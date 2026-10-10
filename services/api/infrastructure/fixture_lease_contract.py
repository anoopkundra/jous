"""IL.1 pure lease values and necessary structural predicates.

Authority: fixture-lease-implementation-design.md sections 3, 8, 10, 12.
No function verifies approval, freshness, provenance, authority or live state.
Passing a predicate is NEVER execution permission. No I/O or environment discovery.
"""

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from hashlib import sha256
from uuid import UUID


class ContractRejected(ValueError):
    """Finite failure; never include supplied identity bytes in diagnostics."""


def _require(condition):
    if not condition:
        raise ContractRejected("LEASE_CONTRACT_REJECTED")


class Operation(StrEnum):
    FIXTURE_PROVISIONING = "FIXTURE_PROVISIONING"
    CANARY = "CANARY"
    FIXTURE_MAINTENANCE = "FIXTURE_MAINTENANCE"
    FIXTURE_RETIREMENT = "FIXTURE_RETIREMENT"


class LeaseStatus(StrEnum):
    LEASED = "LEASED"
    EXPIRED = "EXPIRED"
    QUARANTINED = "QUARANTINED"
    RELEASED = "RELEASED"


class Phase(StrEnum):
    # PRE_AUTH is the short API name; wire/storage spelling follows authority.
    PRE_AUTH = "PRE_AUTH_PROVISIONING_REQUEST"
    AUTH_IDENTITIES_BOUND = "AUTH_IDENTITIES_BOUND"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class IssuerMode(StrEnum):
    RECOVERY_ONLY = "RECOVERY_ONLY"
    ACTIVE = "ACTIVE"


class ArtifactType(StrEnum):
    PROVISIONING_REQUEST = "PROVISIONING_REQUEST"
    FIXTURE_MANIFEST = "FIXTURE_MANIFEST"
    PROVENANCE_EVIDENCE = "PROVENANCE_EVIDENCE"
    RELEASE_EVIDENCE = "RELEASE_EVIDENCE"
    RECOVERY_EVIDENCE = "RECOVERY_EVIDENCE"
    AUTHORIZATION = "AUTHORIZATION"


class Command(StrEnum):
    ACQUIRE = "ACQUIRE"
    ADVANCE = "ADVANCE"
    RECORD_EXECUTION = "RECORD_EXECUTION"
    QUARANTINE = "QUARANTINE"
    RELEASE = "RELEASE"
    RECOVER = "RECOVER"


class ConflictFamily(IntEnum):
    FIXTURE_SET = 1
    DB_UUID = 2
    LOGICAL_ACTOR_ALLOCATION = 3
    ISSUER_SUBJECT = 4


PREFIX = b"JOUS-FIXTURE-LEASE"
VERSION = 1
MAX_FIELD_BYTES = 65535
MAX_ARTIFACT_BYTES = 1024 * 1024


def _text(value, maximum=MAX_FIELD_BYTES):
    _require(type(value) is str and bool(value.strip()))
    try:
        raw = value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise ContractRejected("LEASE_CONTRACT_REJECTED") from None
    _require(1 <= len(raw) <= maximum)
    return raw  # Preserve exact bytes: no trimming/folding/normalization.


@dataclass(frozen=True)
class DatabaseTargetScope:
    """Logical approved target identity; construction does not prove approval."""
    value: str

    def __post_init__(self):
        _text(self.value, 255)


@dataclass(frozen=True)
class ProviderAllocationScope:
    value: str

    def __post_init__(self):
        _text(self.value, 255)


def canonical_uuid(value):
    """Parse only canonical lowercase hyphenated approved-request UUID text."""
    _require(type(value) is str)
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        raise ContractRejected("LEASE_CONTRACT_REJECTED") from None
    _require(str(parsed) == value)
    return parsed


def frame_conflict(family, fields):
    """Encode exactly the four published conflict schemas, not arbitrary payloads."""
    _require(type(family) is ConflictFamily and type(fields) is tuple and len(fields) == 2)
    for index, field in enumerate(fields):
        _require(type(field) is bytes and 1 <= len(field) <= MAX_FIELD_BYTES)
        if family is ConflictFamily.DB_UUID and index == 1:
            _require(len(field) == 16)
        else:
            try:
                _text(field.decode("utf-8", errors="strict"))
            except UnicodeError:
                raise ContractRejected("LEASE_CONTRACT_REJECTED") from None
    if family in (ConflictFamily.FIXTURE_SET, ConflictFamily.DB_UUID,
                  ConflictFamily.LOGICAL_ACTOR_ALLOCATION):
        _require(len(fields[0]) <= 255)
    if family in (ConflictFamily.FIXTURE_SET, ConflictFamily.LOGICAL_ACTOR_ALLOCATION):
        _require(len(fields[1]) <= 255)
    return (PREFIX + bytes((VERSION, family.value)) + len(fields).to_bytes(4, "big")
            + b"".join(len(field).to_bytes(4, "big") + field for field in fields))


def decode_conflict(raw):
    """Strict inverse; reject unknown version/tag, wrong count and trailing bytes."""
    _require(type(raw) is bytes and len(raw) >= len(PREFIX) + 6)
    _require(raw.startswith(PREFIX) and raw[len(PREFIX)] == VERSION)
    try:
        family = ConflictFamily(raw[len(PREFIX) + 1])
    except ValueError:
        raise ContractRejected("LEASE_CONTRACT_REJECTED") from None
    cursor = len(PREFIX) + 2
    _require(int.from_bytes(raw[cursor:cursor + 4], "big") == 2)
    cursor += 4
    fields = []
    for _ in range(2):
        _require(cursor + 4 <= len(raw))
        length = int.from_bytes(raw[cursor:cursor + 4], "big")
        cursor += 4
        _require(1 <= length <= MAX_FIELD_BYTES and cursor + length <= len(raw))
        fields.append(raw[cursor:cursor + length])
        cursor += length
    _require(cursor == len(raw))
    key = ConflictKey(family, tuple(fields))
    _require(key.canonical_bytes == raw)
    return key


@dataclass(frozen=True)
class ConflictKey:
    """Equality/identity uses family and FULL fields, never a SHA256 digest."""
    family: ConflictFamily
    fields: tuple[bytes, bytes]

    def __post_init__(self):
        frame_conflict(self.family, self.fields)

    @property
    def canonical_bytes(self):
        return frame_conflict(self.family, self.fields)

    @classmethod
    def fixture_set(cls, scope, identifier):
        _require(type(scope) is DatabaseTargetScope)
        return cls(ConflictFamily.FIXTURE_SET, (_text(scope.value, 255), _text(identifier, 255)))

    @classmethod
    def db_uuid(cls, scope, identifier):
        _require(type(scope) is DatabaseTargetScope and type(identifier) is UUID)
        return cls(ConflictFamily.DB_UUID, (_text(scope.value, 255), identifier.bytes))

    @classmethod
    def logical_actor(cls, scope, identifier):
        _require(type(scope) is ProviderAllocationScope)
        return cls(ConflictFamily.LOGICAL_ACTOR_ALLOCATION,
                   (_text(scope.value, 255), _text(identifier, 255)))

    @classmethod
    def issuer_subject(cls, issuer, subject):
        return cls(ConflictFamily.ISSUER_SUBJECT, (_text(issuer), _text(subject)))


def canonical_conflict_set(keys):
    """Exact duplicate keys deduplicate; sorted complete bytes remain authority.

    Does not establish completeness or resolve contradictory symbolic mappings.
    """
    _require(type(keys) is tuple and all(type(key) is ConflictKey for key in keys))
    return tuple(sorted({key.canonical_bytes for key in keys}))


def sha256_evidence(raw):
    """Evidence/index digest only; never authoritative conflict identity."""
    _require(type(raw) is bytes)
    return sha256(raw).digest()


@dataclass(frozen=True)
class ArtifactBytes:
    """Typed bounded bytes, NOT an approved or semantically complete artifact."""
    artifact_type: ArtifactType
    exact_bytes: bytes

    def __post_init__(self):
        _require(type(self.artifact_type) is ArtifactType)
        _require(type(self.exact_bytes) is bytes and 1 <= len(self.exact_bytes) <= MAX_ARTIFACT_BYTES)

    @property
    def evidence_sha256(self):
        return sha256_evidence(self.exact_bytes)


@dataclass(frozen=True)
class Binding:
    """Typed artifact envelope. No approval/provenance/freshness assertion."""
    operation: Operation
    phase: Phase
    artifact: ArtifactBytes

    def __post_init__(self):
        _require(type(self.operation) is Operation and type(self.phase) is Phase)
        _require(type(self.artifact) is ArtifactBytes)
        if self.operation is Operation.FIXTURE_PROVISIONING:
            _require(self.phase in (Phase.PRE_AUTH, Phase.AUTH_IDENTITIES_BOUND))
            _require(self.artifact.artifact_type is ArtifactType.PROVISIONING_REQUEST)
        else:
            # Maintenance/retirement have no adopted binding authority.
            _require(self.operation is Operation.CANARY and self.phase is Phase.NOT_APPLICABLE)
            _require(self.artifact.artifact_type is ArtifactType.FIXTURE_MANIFEST)

    @property
    def provisioning_request_sha256(self):
        _require(self.operation is Operation.FIXTURE_PROVISIONING)
        return self.artifact.evidence_sha256

    @property
    def fixture_manifest_sha256(self):
        _require(self.operation is Operation.CANARY)
        return self.artifact.evidence_sha256


def phase_advance_allowed(operation, before, after):
    _require(type(operation) is Operation and type(before) is Phase and type(after) is Phase)
    return (operation is Operation.FIXTURE_PROVISIONING and before is Phase.PRE_AUTH
            and after is Phase.AUTH_IDENTITIES_BOUND)


def claims_remain_blocking(status):
    """Expiry/quarantine never free claims. RELEASED is not global availability."""
    _require(type(status) is LeaseStatus)
    return status is not LeaseStatus.RELEASED


@dataclass(frozen=True)
class ReservationValue:
    """Pure projection for structural transition checks, not an acknowledged lease."""
    reservation_id: str
    fixture_set_id: str
    owner: str
    binding: Binding
    status: LeaseStatus
    expires_at: int
    completion_deadline: int
    revision: int
    database_ids: tuple[UUID, ...]
    immutable_database_projection: bytes
    claims: tuple[ConflictKey, ...]

    def __post_init__(self):
        for value in (self.reservation_id, self.fixture_set_id, self.owner):
            _text(value, 255)
        _require(type(self.binding) is Binding and type(self.status) is LeaseStatus)
        for value in (self.expires_at, self.completion_deadline):
            _require(type(value) is int and -(1 << 63) <= value < (1 << 63))
        _require(self.expires_at > self.completion_deadline)
        _require(type(self.revision) is int and 0 <= self.revision < (1 << 64))
        _require(type(self.database_ids) is tuple and len(self.database_ids) == 8)
        _require(all(type(value) is UUID for value in self.database_ids))
        _require(len(set(self.database_ids)) == 8)
        _require(type(self.immutable_database_projection) is bytes
                 and 1 <= len(self.immutable_database_projection) <= MAX_ARTIFACT_BYTES)
        canonical_conflict_set(self.claims)
        _require(bool(self.claims) == claims_remain_blocking(self.status))


def structurally_permitted_transition(before, after, command, evidence=None):
    """Necessary shape only. Later service MUST verify all external gates.

    No clock, approval, closure, claims-completeness or execution fact is proven.
    Release/recovery evidence is merely typed bytes, never an approval boolean.
    """
    _require(type(before) is ReservationValue and type(after) is ReservationValue)
    _require(type(command) is Command)
    fixed = ("reservation_id", "fixture_set_id", "owner", "expires_at",
             "completion_deadline", "database_ids", "immutable_database_projection")
    if any(getattr(before, field) != getattr(after, field) for field in fixed):
        return False
    if after.revision != before.revision + 1 or before.status is LeaseStatus.RELEASED:
        return False
    if before.binding.operation is not after.binding.operation:
        return False
    old_keys = set(canonical_conflict_set(before.claims))
    new_keys = set(canonical_conflict_set(after.claims))
    if command is Command.ADVANCE:
        return (before.status is after.status is LeaseStatus.LEASED
                and phase_advance_allowed(before.binding.operation, before.binding.phase,
                                          after.binding.phase)
                and old_keys <= new_keys
                and all(decode_conflict(key).family is ConflictFamily.ISSUER_SUBJECT
                        for key in new_keys - old_keys))
    if before.binding != after.binding:
        return False
    if command is Command.RELEASE or command is Command.RECOVER:
        expected = (ArtifactType.RELEASE_EVIDENCE if command is Command.RELEASE
                    else ArtifactType.RECOVERY_EVIDENCE)
        return (after.status is LeaseStatus.RELEASED and not new_keys
                and type(evidence) is ArtifactBytes and evidence.artifact_type is expected
                and ((command is Command.RELEASE and before.status is not LeaseStatus.QUARANTINED)
                     or (command is Command.RECOVER and before.status is LeaseStatus.QUARANTINED)))
    if new_keys != old_keys:
        return False
    if command is Command.QUARANTINE:
        return after.status is LeaseStatus.QUARANTINED
    if command is Command.RECORD_EXECUTION:
        return before.status is after.status is LeaseStatus.LEASED
    return False  # ACQUIRE cannot replace an existing reservation; expiry cannot release.
