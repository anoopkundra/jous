"""IL.4A pure canonical protocol. Structural validity is never permission.

No storage, clock, environment discovery, activation or lifecycle decisions.
Authority: JOUS.CORE.1A.il4-command-event-state-protocol-amendment.md.
"""

from dataclasses import dataclass, make_dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Iterable

from . import fixture_lease_contract as contract


class ProtocolRejected(ValueError):
    """Malformed, unsupported or inconsistent supplied protocol material."""


def require(condition):
    if not condition:
        raise ProtocolRejected("LEASE_PROTOCOL_REJECTED")


PREFIX = b"JOUS-FIXTURE-LEASE"
MAX_FIELD = 65535
MAX_BLOB = 1048576
MAX_UINT = (1 << 63) - 1
STATE_1 = "JOUS_CORE1A_STATE_REPRESENTATION_1"
STATE_2 = "JOUS_CORE1A_STATE_REPRESENTATION_2"
GENESIS_EVENT_DIGEST = sha256(b"JOUS-FIXTURE-LEASE-GENESIS-V1").digest()


class ExecutionState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    STARTED = "STARTED"
    STOPPED_KNOWN = "STOPPED_KNOWN"
    UNKNOWN = "UNKNOWN"


class QuarantineReason(StrEnum):
    CLOCK_UNCERTAIN = "CLOCK_UNCERTAIN"
    STORAGE_UNCERTAIN = "STORAGE_UNCERTAIN"
    AUTHORITY_UNCERTAIN = "AUTHORITY_UNCERTAIN"
    ACK_UNCERTAIN = "ACK_UNCERTAIN"
    PHASE_UNCERTAIN = "PHASE_UNCERTAIN"
    EXECUTION_UNCERTAIN = "EXECUTION_UNCERTAIN"
    EXPIRED_UNRECONCILED = "EXPIRED_UNRECONCILED"
    EVIDENCE_MISMATCH = "EVIDENCE_MISMATCH"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"


class EventType(StrEnum):
    REQUESTED = "REQUESTED"
    REJECTED = "REJECTED"
    RESERVED = "RESERVED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PHASE_ADVANCE_REQUESTED = "PHASE_ADVANCE_REQUESTED"
    PHASE_ADVANCED = "PHASE_ADVANCED"
    EXECUTION_RECORDED = "EXECUTION_RECORDED"
    EXPIRED = "EXPIRED"
    QUARANTINED = "QUARANTINED"
    RELEASE_REQUESTED = "RELEASE_REQUESTED"
    RELEASED = "RELEASED"
    RECOVERY_APPROVED = "RECOVERY_APPROVED"
    RECOVERED = "RECOVERED"


class OutcomeCode(StrEnum):
    SUCCESS = "SUCCESS"
    CONFLICT_REJECTED = "CONFLICT_REJECTED"
    BUSY_REJECTED = "BUSY_REJECTED"
    MALFORMED_REJECTED = "MALFORMED_REJECTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    AUTHORITY_REJECTED = "AUTHORITY_REJECTED"
    CLOCK_REJECTED = "CLOCK_REJECTED"
    PHASE_REJECTED = "PHASE_REJECTED"
    REVISION_REJECTED = "REVISION_REJECTED"
    REPLAY_MISMATCH = "REPLAY_MISMATCH"
    CLOSURE_REJECTED = "CLOSURE_REJECTED"
    STORAGE_UNKNOWN = "STORAGE_UNKNOWN"


def u32(value):
    require(type(value) is int and 0 <= value <= 0xffffffff)
    return value.to_bytes(4, "big")


def uint(value):
    require(type(value) is int and 0 <= value <= MAX_UINT)
    return value.to_bytes(8, "big")


def utc(value):
    require(type(value) is int and -(1 << 63) <= value <= MAX_UINT)
    return value.to_bytes(8, "big", signed=True)


def boolean(value):
    require(type(value) is bool)
    return b"\x01" if value else b"\x00"


def identifier(value):
    require(isinstance(value, str))
    try:
        raw = value.encode("utf-8", "strict")
    except UnicodeError as error:
        raise ProtocolRejected("LEASE_PROTOCOL_REJECTED") from error
    require(1 <= len(raw) <= 255 and not value.isspace())
    return raw


def digest_value(value):
    require(type(value) is bytes and len(value) == 32)
    return value


def blob(value):
    require(type(value) is bytes and 1 <= len(value) <= MAX_BLOB)
    return value


def frame(version, tag, fields):
    require(type(version) is int and version in (1, 2))
    require(type(tag) is int and 0 <= tag <= 255)
    fields = tuple(fields)
    result = [PREFIX, bytes((version, tag)), u32(len(fields))]
    for field in fields:
        require(type(field) is bytes)
        require(len(field) <= (MAX_FIELD if version == 1 else MAX_BLOB + 1))
        result.extend((u32(len(field)), field))
    return b"".join(result)


class _Reader:
    def __init__(self, raw):
        require(type(raw) is bytes)
        self.raw, self.pos = raw, 0

    def take(self, size):
        require(type(size) is int and 0 <= size <= len(self.raw) - self.pos)
        value = self.raw[self.pos:self.pos + size]
        self.pos += size
        return value

    def count(self):
        return int.from_bytes(self.take(4), "big")

    def end(self):
        require(self.pos == len(self.raw))


def _read_frame(reader, version, tag, count):
    require(reader.take(len(PREFIX)) == PREFIX)
    require(reader.take(2) == bytes((version, tag)))
    require(reader.count() == count)
    fields = []
    for _ in range(count):
        size = reader.count()
        require(size <= (MAX_FIELD if version == 1 else MAX_BLOB + 1))
        fields.append(reader.take(size))
    return tuple(fields)


def parse_frame(raw, version, tag, count):
    reader = _Reader(raw)
    fields = _read_frame(reader, version, tag, count)
    reader.end()
    return fields


def collection(items):
    """Already recursively framed items; containing field frames this once."""
    items = tuple(items)
    require(all(type(item) is bytes for item in items))
    return u32(len(items)) + b"".join(items)


# Fixed schemas generate immutable named value types, not caller-defined maps.
# Domain strings below are private, exhaustive implementation descriptors.
_SCHEMAS = {}
_ENUMS = {
    "Command": contract.Command, "Operation": contract.Operation,
    "Phase": contract.Phase, "ArtifactType": contract.ArtifactType,
    "LeaseStatus": contract.LeaseStatus, "ExecutionState": ExecutionState,
    "QuarantineReason": QuarantineReason, "EventType": EventType,
    "OutcomeCode": OutcomeCode,
}


def _record(name, version, tag, specification):
    schema = tuple(tuple(field.split(":")) for field in specification.split())
    types = {"U": int, "T": int, "BOOL": int, "H": bytes,
             "BYTES": bytes, "KEY": bytes, "ID": str, "TARGET": str,
             "REFS": tuple[globals().get("Reference", object), ...],
             "R": globals().get("Reference", object),
             "P": globals().get("Parameters", object)}
    fields = []
    for field_name, domain in schema:
        optional = domain.startswith("?")
        base = domain.lstrip("?")
        annotation = types.get(base, _ENUMS.get(base, object))
        if optional:
            annotation = annotation | None
        fields.append((field_name, annotation))
    cls = make_dataclass(name, fields, frozen=True, namespace={"__module__": __name__})
    _SCHEMAS[cls] = (version, tag, schema)
    return cls


Reference = _record("Reference", 1, 17,
                    "artifact_id:ID artifact_type:ArtifactType artifact_sha256:H")
Parameters = _record("Parameters", 1, 16,
    "target_reservation_id:ID prior_binding:?R new_binding:?R "
    "execution_state:?ExecutionState quarantine_reason:?QuarantineReason "
    "supporting_refs:REFS proposed_expires_at:?T proposed_completion_deadline:?T "
    "primary_evidence_reference:?R")
CommandPayload = _record("CommandPayload", 1, 5,
    "command_kind:Command authenticated_principal:ID register_id:ID "
    "issuer_generation:U activation_id:ID command_id:ID reservation_id:TARGET "
    "expected_revision:U operation:Operation phase:Phase binding_kind:ArtifactType "
    "binding_sha256:H fixture_set_id:ID binding_reference:R approval_record_hash:H "
    "authorization_reference:R evidence_references:REFS parameters:P")
EventPayload = _record("EventPayload", 1, 6,
    "event_sequence:U command_id:ID reservation_id:?ID register_id:ID "
    "issuer_generation:U activation_id:ID event_type:EventType utc_time:T "
    "prior_digest:H revision:U artifact_id:?ID evidence_artifact_id:?ID")
AckPayload = _record("AckPayload", 1, 10,
    "command_id:ID command_payload_sha256:H principal:ID register_id:ID "
    "issuer_generation:U activation_id:ID reservation_id:ID resulting_revision:U "
    "owner:ID operation:Operation phase:Phase binding_kind:ArtifactType "
    "binding_sha256:H canonical_key_set_digest:H approval_record_hash:H "
    "authorization_reference:R evidence_references:REFS issued_at:T acquired_at:T "
    "expires_at:T completion_deadline:T first_event_sequence:U "
    "final_event_sequence:U event_count:U final_event_digest:H outcome_code:OutcomeCode")
MetadataRow = _record("MetadataRow", 2, 12,
    "singleton:U schema_version:U register_id:ID issuer_generation:U activation_id:ID "
    "fixture_plan_sha256:H bootstrap_amendment_sha256:H provisioning_contract_sha256:H "
    "design_sha256:H last_valid_utc:T recovery_required:BOOL")
ReservationRow = _record("ReservationRow", 2, 13,
    "reservation_id:ID register_id:ID fixture_set_id:ID operation_type:Operation "
    "phase:Phase binding_kind:ArtifactType binding_artifact_id:ID binding_sha256:H "
    "immutable_db_projection:BYTES immutable_db_projection_hash:H owner:ID "
    "authorization_ref:ID requested_at:T acquired_at:T acknowledged_at:T expires_at:T "
    "completion_deadline:T revision:U lease_status:LeaseStatus expired_condition:BOOL "
    "execution_state:ExecutionState release_evidence_artifact_id:?ID "
    "quarantine_reason:?QuarantineReason recovery_evidence_artifact_id:?ID")
ClaimRow = _record("ClaimRow", 2, 14,
    "canonical_key:KEY reservation_id:ID introduced_revision:U originating_artifact_id:ID")
CommandRow = _record("CommandRow", 2, 15,
    "command_id:ID authenticated_principal:ID command_kind:Command "
    "canonical_payload_bytes:BYTES canonical_payload_hash:H expected_revision:U "
    "reservation_id:?ID outcome_code:OutcomeCode durable_ack_bytes:?BYTES "
    "transition_event_sequence:?U")


def _enum(domain, value):
    require(isinstance(value, str))
    try:
        return _ENUMS[domain](value).value.encode("utf-8")
    except ValueError as error:
        raise ProtocolRejected("LEASE_PROTOCOL_REJECTED") from error


def _encode(domain, value):
    if domain.startswith("?"):
        return b"\x00" if value is None else b"\x01" + _encode(domain[1:], value)
    if domain == "U":
        return uint(value)
    if domain == "T":
        return utc(value)
    if domain == "BOOL":
        require(type(value) is int and value in (0, 1))
        return uint(value)
    if domain == "ID":
        return identifier(value)
    if domain == "TARGET":
        return b"" if value == "" else identifier(value)
    if domain == "H":
        return digest_value(value)
    if domain == "BYTES":
        return blob(value)
    if domain == "KEY":
        require(type(value) is bytes)
        try:
            contract.decode_conflict(value)
        except (ValueError, TypeError) as error:
            raise ProtocolRejected("LEASE_PROTOCOL_REJECTED") from error
        return value
    if domain in ("R", "P"):
        require(type(value) is (Reference if domain == "R" else Parameters))
        return encode_record(value)
    if domain == "REFS":
        validate_references(value)
        return collection(encode_record(ref) for ref in value)
    return _enum(domain, value)


def _decode(domain, raw):
    if domain.startswith("?"):
        require(len(raw) >= 1 and raw[0] in (0, 1))
        if raw[0] == 0:
            require(raw == b"\x00")
            return None
        return _decode(domain[1:], raw[1:])
    if domain in ("U", "T", "BOOL"):
        require(len(raw) == 8)
        value = int.from_bytes(raw, "big", signed=domain == "T")
        require(_encode(domain, value) == raw)
        return value
    if domain in ("H", "BYTES", "KEY"):
        require(_encode(domain, raw) == raw)
        return raw
    if domain in ("R", "P"):
        return decode_record(raw, Reference if domain == "R" else Parameters)
    if domain == "REFS":
        reader = _Reader(raw)
        count = reader.count()
        # The count cannot request more members than the remaining bytes permit.
        require(count <= (len(raw) - 4) // (len(PREFIX) + 6))
        values = []
        for _ in range(count):
            start = reader.pos
            _read_frame(reader, 1, 17, 3)
            values.append(decode_record(raw[start:reader.pos], Reference))
        reader.end()
        values = tuple(values)
        validate_references(values)
        return values
    try:
        value = raw.decode("utf-8", "strict")
    except UnicodeError as error:
        raise ProtocolRejected("LEASE_PROTOCOL_REJECTED") from error
    require(_encode(domain, value) == raw)
    return value if domain in ("ID", "TARGET") else _ENUMS[domain](value)


def validate_references(refs):
    require(type(refs) is tuple)
    previous = None
    ids = set()
    for ref in refs:
        require(type(ref) is Reference)
        key = (identifier(ref.artifact_id), _enum("ArtifactType", ref.artifact_type),
               digest_value(ref.artifact_sha256))
        require(previous is None or previous < key)
        require(key[0] not in ids)
        ids.add(key[0])
        previous = key


def canonical_references(refs):
    refs = tuple(refs)
    require(all(type(ref) is Reference for ref in refs))
    result = tuple(sorted(refs, key=lambda ref: (identifier(ref.artifact_id),
        _enum("ArtifactType", ref.artifact_type), digest_value(ref.artifact_sha256))))
    validate_references(result)
    return result


def _validate_binding(operation, phase, kind):
    if operation == contract.Operation.FIXTURE_PROVISIONING:
        require(phase in (contract.Phase.PRE_AUTH, contract.Phase.AUTH_IDENTITIES_BOUND))
        require(kind == contract.ArtifactType.PROVISIONING_REQUEST)
    else:
        require(operation == contract.Operation.CANARY)
        require(phase == contract.Phase.NOT_APPLICABLE)
        require(kind == contract.ArtifactType.FIXTURE_MANIFEST)


def validate_primary(parameters, kind):
    require(type(parameters) is Parameters)
    _enum("Command", kind)
    validate_references(parameters.supporting_refs)
    primary = parameters.primary_evidence_reference
    require((primary is None) == (not parameters.supporting_refs))
    if kind != contract.Command.ACQUIRE:
        require(primary is not None)
    if primary is not None:
        require(type(primary) is Reference and parameters.supporting_refs.count(primary) == 1)
        if kind == contract.Command.RELEASE:
            require(primary.artifact_type == contract.ArtifactType.RELEASE_EVIDENCE)
        if kind == contract.Command.RECOVER:
            require(primary.artifact_type == contract.ArtifactType.RECOVERY_EVIDENCE)
    return primary


def verify_references(references, approved_references):
    """Compare exact supplied structural identities; this does not prove approval.

    The caller must separately establish retained approved artifact/approval
    bytes and authority. Serialization position assigns no semantic role.
    """
    validate_references(references)
    approved_references = canonical_references(approved_references)
    approved = {ref.artifact_id: ref for ref in approved_references}
    for ref in references:
        require(approved.get(ref.artifact_id) == ref)


def validate_evidence(parameters, kind, approved_references):
    primary = validate_primary(parameters, kind)
    verify_references(parameters.supporting_refs, approved_references)
    return primary


def validate_command(command):
    require(type(command) is CommandPayload)
    p, kind = command.parameters, command.command_kind
    require(type(p) is Parameters)
    uint(command.issuer_generation)
    _enum("Command", kind)
    require(command.issuer_generation >= 1)
    require(type(command.binding_reference) is Reference)
    require(type(command.authorization_reference) is Reference)
    require(command.binding_kind == command.binding_reference.artifact_type)
    require(command.binding_sha256 == command.binding_reference.artifact_sha256)
    require(command.authorization_reference.artifact_type == contract.ArtifactType.AUTHORIZATION)
    require(command.evidence_references == p.supporting_refs)
    _validate_binding(command.operation, command.phase, command.binding_kind)
    validate_primary(p, kind)
    acquire = kind == contract.Command.ACQUIRE
    require(command.reservation_id == "" if acquire else command.reservation_id == p.target_reservation_id)
    if acquire:
        require(command.expected_revision == 0)
    require((p.proposed_expires_at is not None) == acquire)
    require((p.proposed_completion_deadline is not None) == acquire)
    if acquire:
        utc(p.proposed_expires_at)
        utc(p.proposed_completion_deadline)
        require(p.proposed_completion_deadline < p.proposed_expires_at)
    require((p.prior_binding is not None) == (kind == contract.Command.ADVANCE))
    require((p.new_binding is not None) == (kind in (contract.Command.ACQUIRE, contract.Command.ADVANCE)))
    if p.new_binding is not None:
        require(p.new_binding == command.binding_reference)
    if kind == contract.Command.ADVANCE:
        require(p.prior_binding.artifact_type == contract.ArtifactType.PROVISIONING_REQUEST)
        require(p.new_binding.artifact_type == contract.ArtifactType.PROVISIONING_REQUEST)
    require((p.execution_state is not None) == (kind == contract.Command.RECORD_EXECUTION))
    require((p.quarantine_reason is not None) == (kind == contract.Command.QUARANTINE))


def _validate_record(value):
    if type(value) is CommandPayload:
        validate_command(value)
    elif type(value) is EventPayload:
        require(value.event_sequence >= 1 and value.issuer_generation >= 1)
        if value.event_sequence == 1:
            require(value.prior_digest == GENESIS_EVENT_DIGEST)
    elif type(value) is AckPayload:
        require(value.issuer_generation >= 1 and value.outcome_code == OutcomeCode.SUCCESS)
        require(value.first_event_sequence >= 1 and value.event_count >= 1)
        require(value.final_event_sequence - value.first_event_sequence + 1 == value.event_count)
        require(value.authorization_reference.artifact_type == contract.ArtifactType.AUTHORIZATION)
        _validate_binding(value.operation, value.phase, value.binding_kind)
        require(value.acquired_at <= value.issued_at)
        require(value.completion_deadline < value.expires_at)
    elif type(value) is MetadataRow:
        require(value.singleton == 1 and value.schema_version == 1 and value.issuer_generation >= 1)
    elif type(value) is ReservationRow:
        _validate_binding(value.operation_type, value.phase, value.binding_kind)
        require(value.requested_at <= value.acquired_at <= value.acknowledged_at < value.expires_at)
        require(value.completion_deadline < value.expires_at)
        require(sha256(value.immutable_db_projection).digest() == value.immutable_db_projection_hash)
        if value.lease_status == contract.LeaseStatus.QUARANTINED:
            require(value.quarantine_reason is not None)
        if value.lease_status == contract.LeaseStatus.RELEASED:
            require(value.release_evidence_artifact_id is not None or value.recovery_evidence_artifact_id is not None)
    elif type(value) is CommandRow:
        require(sha256(value.canonical_payload_bytes).digest() == value.canonical_payload_hash)
        # This record belongs exclusively to the completed-command STATE projection.
        require(value.outcome_code == OutcomeCode.SUCCESS)
        require(value.reservation_id is not None and value.durable_ack_bytes is not None
                and value.transition_event_sequence is not None)


def encode_record(value):
    require(type(value) in _SCHEMAS)
    version, tag, schema = _SCHEMAS[type(value)]
    fields = tuple(_encode(domain, getattr(value, name)) for name, domain in schema)
    _validate_record(value)
    return frame(version, tag, fields)


def decode_record(raw, cls):
    require(cls in _SCHEMAS)
    version, tag, schema = _SCHEMAS[cls]
    fields = parse_frame(raw, version, tag, len(schema))
    value = cls(*(_decode(domain, field) for (_, domain), field in zip(schema, fields)))
    require(encode_record(value) == raw)
    return value


def command_bytes(command):
    require(type(command) is CommandPayload)
    return encode_record(command)


def command_digest(command):
    return sha256(command_bytes(command)).digest()


def event_bytes(event):
    require(type(event) is EventPayload)
    return encode_record(event)


def event_digest(event):
    return sha256(event_bytes(event)).digest()


def ack_bytes(ack):
    require(type(ack) is AckPayload)
    return encode_record(ack)


def key_set_digest(keys):
    keys = tuple(keys)
    previous = None
    for key in keys:
        _encode("KEY", key)
        require(previous is None or previous < key)
        previous = key
    return sha256(collection(keys)).digest()


def event_order(kind, *, definite_expiry=False):
    """Supplied expiry fact; this function never evaluates lifecycle eligibility."""
    require(type(definite_expiry) is bool)
    orders = {
        contract.Command.ACQUIRE: ("REQUESTED", "RESERVED", "ACKNOWLEDGED"),
        contract.Command.ADVANCE: ("PHASE_ADVANCE_REQUESTED", "PHASE_ADVANCED", "ACKNOWLEDGED"),
        contract.Command.RECORD_EXECUTION: ("EXECUTION_RECORDED", "ACKNOWLEDGED"),
        contract.Command.QUARANTINE: (("EXPIRED", "QUARANTINED", "ACKNOWLEDGED")
            if definite_expiry else ("QUARANTINED", "ACKNOWLEDGED")),
        contract.Command.RELEASE: ("RELEASE_REQUESTED", "RELEASED", "ACKNOWLEDGED"),
        contract.Command.RECOVER: ("RECOVERY_APPROVED", "RECOVERED", "RELEASED", "ACKNOWLEDGED"),
    }
    require(kind in orders and (not definite_expiry or kind == contract.Command.QUARANTINE))
    return tuple(EventType(value) for value in orders[kind])


def validate_event_chain(events, *, previous_sequence, previous_digest, digests):
    events, digests = tuple(events), tuple(digests)
    uint(previous_sequence)
    digest_value(previous_digest)
    require(len(events) == len(digests) and len(events) > 0)
    if previous_sequence == 0:
        require(previous_digest == GENESIS_EVENT_DIGEST)
    for event, digest in zip(events, digests):
        require(type(event) is EventPayload)
        require(event.event_sequence == previous_sequence + 1)
        require(event.prior_digest == previous_digest)
        require(event_digest(event) == digest_value(digest))
        previous_sequence, previous_digest = event.event_sequence, digest
    return previous_digest


def validate_ack(ack, command, events, *, previous_sequence, previous_digest,
                 digests, transition_event_sequence, definite_expiry=False, keys=None):
    """Verify supplied complete interval; retained ACKs are never regenerated."""
    uint(transition_event_sequence)
    ack_bytes(ack)
    command_bytes(command)
    events = tuple(events)
    final_digest = validate_event_chain(events, previous_sequence=previous_sequence,
        previous_digest=previous_digest, digests=digests)
    require(tuple(event.event_type for event in events) == event_order(
        command.command_kind, definite_expiry=definite_expiry))
    require(ack.command_payload_sha256 == command_digest(command))
    pairs = ((ack.command_id, command.command_id), (ack.principal, command.authenticated_principal),
        (ack.register_id, command.register_id), (ack.issuer_generation, command.issuer_generation),
        (ack.activation_id, command.activation_id), (ack.reservation_id, command.parameters.target_reservation_id),
        (ack.operation, command.operation), (ack.phase, command.phase),
        (ack.binding_kind, command.binding_kind), (ack.binding_sha256, command.binding_sha256),
        (ack.approval_record_hash, command.approval_record_hash),
        (ack.authorization_reference, command.authorization_reference),
        (ack.evidence_references, command.evidence_references))
    require(all(left == right for left, right in pairs))
    require(ack.resulting_revision == (0 if command.command_kind == contract.Command.ACQUIRE
                                     else command.expected_revision + 1))
    if command.command_kind == contract.Command.ACQUIRE:
        require(ack.expires_at == command.parameters.proposed_expires_at)
        require(ack.completion_deadline == command.parameters.proposed_completion_deadline)
    primary = command.parameters.primary_evidence_reference
    for event in events:
        require(event.command_id == ack.command_id and event.reservation_id == ack.reservation_id)
        require(event.register_id == ack.register_id and event.issuer_generation == ack.issuer_generation)
        require(event.activation_id == ack.activation_id and event.revision == ack.resulting_revision)
        require(event.utc_time == ack.issued_at and event.artifact_id == command.binding_reference.artifact_id)
        require(event.evidence_artifact_id == (None if primary is None else primary.artifact_id))
    require(ack.first_event_sequence == events[0].event_sequence)
    require(ack.final_event_sequence == events[-1].event_sequence == transition_event_sequence)
    require(ack.event_count == len(events) and ack.final_event_digest == final_digest)
    if keys is not None:
        require(ack.canonical_key_set_digest == key_set_digest(keys))


def validate_completed_command(row, events, *, previous_sequence, previous_digest,
                               digests, definite_expiry=False, keys=None):
    """Pure consistency of supplied retained material, not persisted replay lookup.

    Approval/artifact resolution, current STATE/head integrity and permission are
    additional gates outside this module. Historical ACK bytes remain unchanged.
    """
    require(type(row) is CommandRow and row.outcome_code == OutcomeCode.SUCCESS)
    encode_record(row)
    command = decode_record(row.canonical_payload_bytes, CommandPayload)
    ack = decode_record(row.durable_ack_bytes, AckPayload)
    require(row.command_id == command.command_id == ack.command_id)
    require(row.authenticated_principal == command.authenticated_principal == ack.principal)
    require(row.command_kind == command.command_kind and row.expected_revision == command.expected_revision)
    require(row.reservation_id == ack.reservation_id)
    require(row.canonical_payload_hash == command_digest(command) == ack.command_payload_sha256)
    validate_ack(ack, command, events, previous_sequence=previous_sequence,
        previous_digest=previous_digest, digests=digests,
        transition_event_sequence=row.transition_event_sequence,
        definite_expiry=definite_expiry, keys=keys)
    return command, ack


@dataclass(frozen=True)
class StateContext:
    representation: str
    register_id: str
    issuer_generation: int
    activation_id: str


@dataclass(frozen=True)
class StateProjection:
    metadata: MetadataRow
    reservations: Iterable[ReservationRow]
    claims: Iterable[ClaimRow]
    commands: Iterable[CommandRow]


def state_chunks(projection, context):
    """Canonical chunks, not implementation-selected protocol segmentation.

    Row iterables must already be in canonical key order. At most one encoded
    row is materialized at a time; retained history is never counted or capped.
    Exhaust the iterator before trusting a digest or serialized result.
    """
    require(type(context) is StateContext and context.representation == STATE_2)
    identifier(context.register_id)
    uint(context.issuer_generation)
    identifier(context.activation_id)
    require(type(projection) is StateProjection and type(projection.metadata) is MetadataRow)
    metadata = projection.metadata
    require((metadata.register_id, metadata.issuer_generation, metadata.activation_id) ==
            (context.register_id, context.issuer_generation, context.activation_id))
    yield PREFIX + b"\x02\x08" + u32(4) + b"\x02"
    yield encode_record(metadata)
    for cls, rows, key_name in ((ReservationRow, projection.reservations, "reservation_id"),
                              (ClaimRow, projection.claims, "canonical_key"),
                              (CommandRow, projection.commands, "command_id")):
        yield b"\x03"
        previous = None
        for row in rows:
            require(type(row) is cls)
            key = getattr(row, key_name)
            key = _encode("KEY" if cls is ClaimRow else "ID", key)
            require(previous is None or previous < key)
            previous = key
            yield b"\x01"
            yield encode_record(row)
        yield b"\x00"


def state_bytes(projection, context):
    return b"".join(state_chunks(projection, context))


def state_digest(projection, context):
    digest = sha256()
    for chunk in state_chunks(projection, context):
        digest.update(chunk)
    return digest.digest()


def verify_state_digest(projection, context, expected):
    require(state_digest(projection, context) == digest_value(expected))


def decode_state(raw, context):
    """Strict materialized decoder for bounded fixtures; no representation sniffing."""
    require(type(context) is StateContext and context.representation == STATE_2)
    reader = _Reader(raw)
    require(reader.take(len(PREFIX) + 7) == PREFIX + b"\x02\x08" + u32(4) + b"\x02")
    start = reader.pos
    _read_frame(reader, 2, 12, 11)
    metadata = decode_record(raw[start:reader.pos], MetadataRow)
    collections = []
    for cls in (ReservationRow, ClaimRow, CommandRow):
        require(reader.take(1) == b"\x03")
        values = []
        while True:
            marker = reader.take(1)
            require(marker in (b"\x00", b"\x01"))
            if marker == b"\x00":
                break
            start = reader.pos
            version, tag, schema = _SCHEMAS[cls]
            _read_frame(reader, version, tag, len(schema))
            values.append(decode_record(raw[start:reader.pos], cls))
        collections.append(tuple(values))
    reader.end()
    result = StateProjection(metadata, *collections)
    require(state_bytes(result, context) == raw)
    return result
