"""IL.5B pure normal-successor evidence codec; construction grants no authority.

No retention, publication, permit completion or operational ACK delivery occurs.
Inputs must already be coherently acquired/qualified by their separate gates.
"""
from dataclasses import dataclass
from hashlib import sha256

from . import fixture_lease_protocol as p
from . import fixture_lease_service as service


@dataclass(frozen=True)
class NormalReference:
    command_id: str
    command_sha256: bytes
    permit_id: str
    permit_sha256: bytes
    host: str
    representation: str
    representation_authority_id: str
    representation_authority_sha256: bytes
    admission_id: str
    admission_sha256: bytes

    def __post_init__(self):
        for value in (self.command_id, self.permit_id, self.host, self.representation,
                      self.representation_authority_id, self.admission_id):
            p.require(type(value) is str); p.identifier(value)
        for value in (self.command_sha256, self.permit_sha256,
                      self.representation_authority_sha256, self.admission_sha256):
            p.digest_value(value)
        p.require(self.representation == p.STATE_2)


def reference_bytes(value):
    p.require(type(value) is NormalReference)
    return p.frame(1, 18, (p.identifier(value.command_id), value.command_sha256,
        p.identifier(value.permit_id), value.permit_sha256, p.identifier(value.host),
        p.identifier(value.representation), p.identifier(value.representation_authority_id),
        value.representation_authority_sha256, p.identifier(value.admission_id), value.admission_sha256))


def decode_reference(raw):
    fields = p.parse_frame(raw, 1, 18, 10)
    domains = ('ID', 'H', 'ID', 'H', 'ID', 'ID', 'ID', 'H', 'ID', 'H')
    value = NormalReference(*(p._decode(domain, field) for domain, field in zip(domains, fields)))
    p.require(reference_bytes(value) == raw)
    return value


@dataclass(frozen=True)
class NormalCheckpoint:
    register_id: str
    generation: int
    activation_id: str
    revision: int
    event_sequence: int
    event_digest: bytes
    state_digest: bytes
    utc_us: int
    predecessor_digest: bytes
    reference: NormalReference
    approval_id: str | None

    def __post_init__(self):
        for value in (self.register_id, self.activation_id):
            p.require(type(value) is str); p.identifier(value)
        for value in (self.generation, self.revision, self.event_sequence):
            p.uint(value); p.require(value > 0)
        for value in (self.event_digest, self.state_digest, self.predecessor_digest):
            p.digest_value(value)
        p.utc(self.utc_us)
        p.require(type(self.reference) is NormalReference)
        if self.approval_id is not None:
            p.require(type(self.approval_id) is str); p.identifier(self.approval_id)


def checkpoint_bytes(value):
    p.require(type(value) is NormalCheckpoint)
    approval = b'\x00' if value.approval_id is None else b'\x01' + p.identifier(value.approval_id)
    return p.frame(1, 7, (p.identifier(value.register_id), p.uint(value.generation),
        p.identifier(value.activation_id), p.uint(value.revision), p.uint(value.event_sequence),
        value.event_digest, value.state_digest, p.utc(value.utc_us), value.predecessor_digest,
        reference_bytes(value.reference), approval))


def decode_checkpoint(raw):
    fields = p.parse_frame(raw, 1, 7, 11)
    domains = ('ID', 'U', 'ID', 'U', 'U', 'H', 'H', 'T', 'H')
    value = NormalCheckpoint(*(p._decode(domain, field) for domain, field in zip(domains, fields)),
                             decode_reference(fields[9]), p._decode('?ID', fields[10]))
    p.require(checkpoint_bytes(value) == raw)
    return value


@dataclass(frozen=True)
class CommittedHead:
    """Supplied committed facts; construction alone proves neither commit nor authority."""
    event_sequence: int
    event_digest: bytes
    state_digest: bytes

    def __post_init__(self):
        p.uint(self.event_sequence); p.require(self.event_sequence > 0)
        p.digest_value(self.event_digest); p.digest_value(self.state_digest)


def _command_result_coherent(command, row):
    """Equality to explicit retained command facts, never transition legality.

    No BEFORE state, status/phase transition matrix or eligibility is evaluated.
    Global binding/revision/deadline equality is checked against the frozen ACK.
    """
    p.require(row.authorization_ref == command.authorization_reference.artifact_id)
    if command.command_kind == p.contract.Command.ACQUIRE:
        p.require(row.owner == command.authenticated_principal)
    if command.command_kind == p.contract.Command.RECORD_EXECUTION:
        p.require(row.execution_state == command.parameters.execution_state)
    if command.command_kind == p.contract.Command.QUARANTINE:
        p.require(row.quarantine_reason == command.parameters.quarantine_reason)
    if command.command_kind == p.contract.Command.RELEASE:
        p.require(row.release_evidence_artifact_id == command.parameters.primary_evidence_reference.artifact_id)
    if command.command_kind == p.contract.Command.RECOVER:
        p.require(row.recovery_evidence_artifact_id == command.parameters.primary_evidence_reference.artifact_id)


def construct_candidate(envelope: service.RetainedAdmissionEnvelope,
                        completion: p.CommandRow, events, projection: p.StateProjection,
                        context: p.StateContext, head: CommittedHead,
                        operation: service.OriginalOperation, *, keys,
                        definite_expiry: bool = False) -> service.CheckpointCandidate:
    """Validate one supplied committed snapshot, then derive its exact successor.

    Projection collections are consumed once through frozen STATE-2 streaming.
    No historical reconstruction from later mutable state is authorized here.
    """
    p.require(type(envelope) is service.RetainedAdmissionEnvelope)
    p.require(type(context) is p.StateContext and context.representation == p.STATE_2)
    p.require(type(head) is CommittedHead and type(operation) is service.OriginalOperation)
    p.require(operation.kind is service.OperationKind.CHECKPOINT_PUBLICATION
              and operation.permit == envelope.permit_reference)
    predecessor = envelope.predecessor
    # Only normal-profile predecessors are decoded here. Other profiles require
    # a separately authorized predecessor interface, never parser fallback.
    prior = decode_checkpoint(predecessor.exact_bytes)
    activation = envelope.activation
    p.require(predecessor.activation == activation and activation.checkpoint == predecessor.reference)
    p.require(sha256(predecessor.exact_bytes).digest() == predecessor.reference.sha256)
    p.require((prior.register_id, prior.generation, prior.activation_id, prior.revision,
               prior.event_sequence, prior.event_digest, prior.state_digest) ==
              (activation.register_id, activation.generation, activation.activation_id,
               predecessor.revision, predecessor.event_sequence,
               predecessor.event_digest, predecessor.state_digest))
    authority = predecessor.representation_authority
    p.require((prior.reference.host, prior.reference.representation,
               prior.reference.representation_authority_id,
               prior.reference.representation_authority_sha256) ==
              (activation.host_identity, predecessor.representation, authority.identity, authority.sha256))
    p.require(predecessor.representation == context.representation)
    p.require(predecessor.revision < p.MAX_UINT)
    events = tuple(events)
    keys = tuple(keys)
    command, ack = p.validate_completed_command(completion, events,
        previous_sequence=predecessor.event_sequence, previous_digest=predecessor.event_digest,
        digests=tuple(p.event_digest(event) for event in events),
        definite_expiry=definite_expiry, keys=keys)
    expected_context = service.CommandContext(command.command_id, p.command_digest(command),
        command.command_kind, command.operation, command.phase, command.expected_revision,
        service.EvidenceReference(command.authorization_reference.artifact_id,
                                  command.authorization_reference.artifact_sha256))
    p.require(envelope.context == expected_context and envelope.principal == command.authenticated_principal
              and envelope.canonical_command_bytes == completion.canonical_payload_bytes)
    p.require((command.register_id, command.issuer_generation, command.activation_id) ==
              (activation.register_id, activation.generation, activation.activation_id) ==
              (context.register_id, context.issuer_generation, context.activation_id))
    p.require(ack.issued_at == envelope.fixed_utc_us)
    p.require((head.event_sequence, head.event_digest) == (ack.final_event_sequence, ack.final_event_digest))
    required = command.command_kind in (p.contract.Command.ACQUIRE, p.contract.Command.ADVANCE,
                                        p.contract.Command.RELEASE, p.contract.Command.RECOVER)
    if required:
        p.require(envelope.approval_applicability is service.ApprovalApplicability.REQUIRED
                  and type(envelope.approval) is service.EvidenceReference
                  and envelope.approval.sha256 == command.approval_record_hash)
        approval_id = envelope.approval.identity
    else:
        p.require(envelope.approval_applicability is service.ApprovalApplicability.NOT_APPLICABLE
                  and envelope.approval is None)
        approval_id = None
    p.require(type(projection) is p.StateProjection and projection.metadata.recovery_required == 0)
    p.require(projection.metadata.last_valid_utc >= ack.issued_at)
    # Verify the exact retained completion is included, without collecting history.
    found = False
    target_found = False
    owned_keys = []
    def reservation_rows():
        nonlocal target_found
        for row in projection.reservations:
            p.require(type(row) is p.ReservationRow)
            if row.reservation_id == ack.reservation_id:
                target_found = True
                _command_result_coherent(command, row)
                p.require((row.register_id, row.fixture_set_id, row.owner, row.revision,
                           row.operation_type, row.phase, row.binding_kind, row.binding_artifact_id,
                           row.binding_sha256, row.acquired_at, row.expires_at, row.completion_deadline) ==
                          (ack.register_id, command.fixture_set_id, ack.owner, ack.resulting_revision,
                           ack.operation, ack.phase, ack.binding_kind, command.binding_reference.artifact_id,
                           ack.binding_sha256, ack.acquired_at, ack.expires_at, ack.completion_deadline))
            yield row
    def claim_rows():
        for row in projection.claims:
            p.require(type(row) is p.ClaimRow)
            if row.reservation_id == ack.reservation_id:
                owned_keys.append(row.canonical_key)
            yield row
    def completed_rows():
        nonlocal found
        for row in projection.commands:
            p.require(type(row) is p.CommandRow)
            if row.command_id == completion.command_id:
                p.require(row == completion); found = True
            yield row
    digest = p.state_digest(p.StateProjection(projection.metadata, reservation_rows(),
                                             claim_rows(), completed_rows()), context)
    p.require(found and target_found and tuple(owned_keys) == keys and digest == head.state_digest)
    reference = NormalReference(command.command_id, sha256(completion.canonical_payload_bytes).digest(),
        operation.permit.identity, operation.permit.sha256, activation.host_identity,
        context.representation, authority.identity, authority.sha256,
        envelope.reference.identity, envelope.reference.sha256)
    value = NormalCheckpoint(activation.register_id, activation.generation, activation.activation_id,
        predecessor.revision + 1, head.event_sequence, head.event_digest, digest,
        ack.issued_at, sha256(predecessor.exact_bytes).digest(), reference, approval_id)
    raw = checkpoint_bytes(value)
    return service.CheckpointCandidate(raw, sha256(raw).digest(), envelope, operation,
        value.revision, value.utc_us, value.event_sequence, value.event_digest, value.state_digest)


def validate_candidate(candidate, *args, **kwargs):
    """Reconstruct from the same retained snapshot; reject any substitution."""
    expected = construct_candidate(*args, **kwargs)
    service.verify_candidate_association(expected, candidate)
    p.require(checkpoint_bytes(decode_checkpoint(candidate.exact_bytes)) == expected.exact_bytes)
    return expected
