"""IL.4B internal local completion, never issuer permission or operational ACK.

All transition, identity, approval, timing and lifecycle facts are structural
inputs established elsewhere. No clocks, permits, dispatch, network or recovery.
"""
from dataclasses import dataclass, fields, replace
from hashlib import sha256

from . import fixture_lease_protocol as p
from . import fixture_lease_store as s


class CommandRejected(ValueError):
    """Confirmed rejection; no completed command or ACK is fabricated."""


def require(condition):
    if not condition:
        raise CommandRejected('COMMAND_CORE_REJECTED')


@dataclass(frozen=True)
class PreparedTransition:
    reservation: s.ReservationRow
    claim_inserts: tuple[s.ClaimRow, ...]
    claim_deletes: tuple[s.ClaimRow, ...]
    utc_time: int
    last_valid_utc: int
    definite_expiry: bool = False


@dataclass(frozen=True)
class LocalCommandResult:
    outcome: p.OutcomeCode
    retained_ack_bytes: bytes | None
    replayed: bool
    storage_result: s.LocalStorageResult | None


def _adapt(row, cls):
    # Only fixed protocol projections are accepted; metadata exclusions are
    # enforced by that frozen projection's field list.
    return cls(*(getattr(row, field.name) for field in fields(cls)))


def _projection(writer):
    metadata = writer.lookup(s.MetadataRow, 1)
    require(metadata is not None)
    return p.StateProjection(_adapt(metadata, p.MetadataRow),
        (_adapt(row, p.ReservationRow) for row in writer.iter_rows(s.ReservationRow)),
        (_adapt(row, p.ClaimRow) for row in writer.iter_rows(s.ClaimRow)),
        (_adapt(row, p.CommandRow) for row in writer.iter_rows(s.CommandRow)))


def _event(row):
    event = p.decode_record(row.event_bytes, p.EventPayload)
    require(_adapt(row, p.EventPayload) == event)
    require(sha256(row.event_bytes).digest() == row.event_digest)
    return event


def _references(writer, command):
    refs = (command.binding_reference, command.authorization_reference) + command.evidence_references
    if command.parameters.prior_binding is not None:
        refs += (command.parameters.prior_binding,)
    for ref in refs:
        artifact = writer.lookup(s.ArtifactRow, ref.artifact_id)
        require(artifact is not None)
        require((artifact.artifact_type, artifact.sha256) == (ref.artifact_type, ref.artifact_sha256))
        if ref == command.binding_reference:
            require((artifact.operation_type, artifact.phase) == (command.operation, command.phase))
        # The store also recomputes exact artifact and approval byte hashes.
    approval_ref = (command.binding_reference if command.command_kind in
        (p.contract.Command.ACQUIRE, p.contract.Command.ADVANCE)
        else command.parameters.primary_evidence_reference)
    require(approval_ref is not None)
    require(writer.lookup(s.ArtifactRow, approval_ref.artifact_id).approval_record_hash
            == command.approval_record_hash)


def _completed(writer, row):
    protocol_row = _adapt(row, p.CommandRow)
    require(row.outcome_code == s.OutcomeCode.SUCCESS and row.durable_ack_bytes is not None)
    ack = p.decode_record(row.durable_ack_bytes, p.AckPayload)
    reservation = writer.lookup(s.ReservationRow, ack.reservation_id)
    require(reservation is not None)
    require((ack.owner, ack.acquired_at, ack.expires_at, ack.completion_deadline) ==
            (reservation.owner, reservation.acquired_at, reservation.expires_at, reservation.completion_deadline))
    # A command has at most four events under this frozen protocol. The global
    # snapshot audit also rejects any event outside its command's ACK interval.
    require(ack.event_count <= 4)
    event_rows = []
    for event in writer.event_interval(ack.first_event_sequence, ack.final_event_sequence):
        event_rows.append(event)
        require(len(event_rows) <= 4)
    require(len(event_rows) > 0)
    events = tuple(_event(event) for event in event_rows)
    first = events[0].event_sequence
    predecessor = writer.lookup(s.EventRow, first - 1) if first > 1 else None
    require(first == 1 or predecessor is not None)
    prior_digest = p.GENESIS_EVENT_DIGEST if first == 1 else predecessor.event_digest
    expiry = events[0].event_type == p.EventType.EXPIRED
    command, ack = p.validate_completed_command(protocol_row, events, previous_sequence=first - 1,
        previous_digest=prior_digest, digests=tuple(row.event_digest for row in event_rows),
        definite_expiry=expiry)
    _references(writer, command)
    return command, ack


def _snapshot(writer, metadata, context):
    # Streaming validation in the same BEGIN IMMEDIATE snapshot. No diagnostic
    # outcomes are filtered out: the frozen STATE codec rejects every such row.
    p.verify_state_digest(_projection(writer), context, metadata.state_digest)
    sequence, digest = 0, p.GENESIS_EVENT_DIGEST
    last_command_id, last_ack = None, None
    for row in writer.iter_rows(s.EventRow):
        event = _event(row)
        require(event.register_id == metadata.register_id)
        require(event.issuer_generation <= metadata.issuer_generation)
        require(event.event_sequence == sequence + 1 and event.prior_digest == digest)
        if event.command_id != last_command_id:
            command_row = writer.lookup(s.CommandRow, event.command_id)
            require(command_row is not None and command_row.outcome_code == s.OutcomeCode.SUCCESS)
            last_ack = p.decode_record(command_row.durable_ack_bytes, p.AckPayload)
            last_command_id = event.command_id
        require(last_ack.command_id == event.command_id
                and last_ack.first_event_sequence <= event.event_sequence <= last_ack.final_event_sequence)
        sequence, digest = event.event_sequence, row.event_digest
    require((sequence, digest) == (metadata.last_event_sequence, metadata.last_event_digest))
    for row in writer.iter_rows(s.CommandRow):
        _completed(writer, row)


def _structural_projection(writer, row, claims):
    c = p.contract
    artifact = writer.lookup(s.ArtifactRow, row.binding_artifact_id)
    require(artifact is not None)
    require((artifact.artifact_id, artifact.artifact_type, artifact.sha256) ==
            (row.binding_artifact_id, row.binding_kind, row.binding_sha256))
    require(sha256(artifact.exact_bytes).digest() == artifact.sha256)
    require((artifact.operation_type, artifact.phase) == (row.operation_type, row.phase))
    binding = c.Binding(row.operation_type, row.phase,
                        c.ArtifactBytes(artifact.artifact_type, artifact.exact_bytes))
    return c.DurableStructuralProjection(row.reservation_id, row.fixture_set_id, row.owner,
        binding, row.lease_status, row.expires_at, row.completion_deadline, row.revision,
        row.immutable_db_projection, row.immutable_db_projection_hash,
        tuple(c.decode_conflict(claim.canonical_key) for claim in claims), row.register_id)


def _structural_transition(writer, command, material, previous):
    c = p.contract
    owned = tuple(writer.claims_for(material.reservation.reservation_id))
    proposed = {claim.canonical_key: claim for claim in owned}
    for claim in material.claim_deletes:
        require(proposed.get(claim.canonical_key) == claim)
        del proposed[claim.canonical_key]
    for claim in material.claim_inserts:
        require(claim.canonical_key not in {item.canonical_key for item in owned})
        require(claim.canonical_key not in proposed)
        proposed[claim.canonical_key] = claim
    after = _structural_projection(writer, material.reservation,
                                   tuple(proposed[key] for key in sorted(proposed)))
    if previous is None:
        require(command.command_kind == c.Command.ACQUIRE and not owned)
        require(after.status == c.LeaseStatus.LEASED)
        return
    if command.command_kind in (c.Command.RECORD_EXECUTION, c.Command.QUARANTINE):
        require(not material.claim_inserts and not material.claim_deletes)
    elif command.command_kind == c.Command.ADVANCE:
        require(not material.claim_deletes)
    elif command.command_kind in (c.Command.RELEASE, c.Command.RECOVER):
        require(not material.claim_inserts)
    before = _structural_projection(writer, previous, owned)
    evidence = None
    if command.command_kind in (c.Command.RELEASE, c.Command.RECOVER):
        ref = command.parameters.primary_evidence_reference
        artifact = writer.lookup(s.ArtifactRow, ref.artifact_id)
        require(artifact is not None and artifact.artifact_type == ref.artifact_type
                and artifact.sha256 == ref.artifact_sha256
                and sha256(artifact.exact_bytes).digest() == artifact.sha256)
        evidence = c.ArtifactBytes(artifact.artifact_type, artifact.exact_bytes)
    require(c.durably_permitted_transition(before, after, command.command_kind, evidence))


def _transition(writer, metadata, command, material, previous):
    require(type(material) is PreparedTransition)
    require(type(material.reservation) is s.ReservationRow)
    require(type(material.claim_inserts) is tuple and type(material.claim_deletes) is tuple)
    p.utc(material.utc_time)
    p.utc(material.last_valid_utc)
    require(type(material.definite_expiry) is bool)
    row = material.reservation
    require((command.register_id, command.issuer_generation, command.activation_id) ==
            (metadata.register_id, metadata.issuer_generation, metadata.activation_id))
    require((row.reservation_id, row.register_id, row.fixture_set_id) ==
            (command.parameters.target_reservation_id, command.register_id, command.fixture_set_id))
    require((row.operation_type, row.phase, row.binding_kind, row.binding_artifact_id, row.binding_sha256) ==
            (command.operation, command.phase, command.binding_kind,
             command.binding_reference.artifact_id, command.binding_sha256))
    require(row.authorization_ref == command.authorization_reference.artifact_id)
    _references(writer, command)
    if command.command_kind == p.contract.Command.ACQUIRE:
        require(previous is None and command.expected_revision == 0 and row.revision == 0)
        require(row.owner == command.authenticated_principal)
        require(row.expires_at == command.parameters.proposed_expires_at
                and row.completion_deadline == command.parameters.proposed_completion_deadline)
        require(not material.claim_deletes)
    else:
        require(previous is not None and command.expected_revision == previous.revision)
        require(previous.revision < p.MAX_UINT and row.revision == previous.revision + 1)
        # Immutable reservation facts must never be replaced by caller assertions.
        for name in ('reservation_id', 'register_id', 'fixture_set_id', 'operation_type',
                     'immutable_db_projection', 'immutable_db_projection_hash', 'owner',
                     'requested_at', 'acquired_at', 'acknowledged_at', 'expires_at', 'completion_deadline'):
            require(getattr(previous, name) == getattr(row, name))
        if command.command_kind != p.contract.Command.ADVANCE:
            for name in ('phase', 'binding_kind', 'binding_artifact_id', 'binding_sha256'):
                require(getattr(previous, name) == getattr(row, name))
        else:
            require((previous.binding_artifact_id, previous.binding_kind, previous.binding_sha256) ==
                (command.parameters.prior_binding.artifact_id, command.parameters.prior_binding.artifact_type,
                 command.parameters.prior_binding.artifact_sha256))
    # These check consistency of the separately supplied effects, not eligibility.
    if command.command_kind == p.contract.Command.RECORD_EXECUTION:
        require(row.execution_state == command.parameters.execution_state)
    if command.command_kind == p.contract.Command.QUARANTINE:
        require(row.lease_status == s.LeaseStatus.QUARANTINED
                and row.quarantine_reason == command.parameters.quarantine_reason)
    if command.command_kind in (p.contract.Command.RELEASE, p.contract.Command.RECOVER):
        require(row.lease_status == s.LeaseStatus.RELEASED)
        evidence_id = command.parameters.primary_evidence_reference.artifact_id
        require((row.release_evidence_artifact_id if command.command_kind == p.contract.Command.RELEASE
                 else row.recovery_evidence_artifact_id) == evidence_id)
    else:
        require(row.lease_status != s.LeaseStatus.RELEASED and not material.claim_deletes)
    for claim in material.claim_inserts + material.claim_deletes:
        require(type(claim) is s.ClaimRow and claim.reservation_id == row.reservation_id)
    require(len({claim.canonical_key for claim in material.claim_inserts}) == len(material.claim_inserts))
    require(len({claim.canonical_key for claim in material.claim_deletes}) == len(material.claim_deletes))
    for claim in material.claim_inserts:
        require(claim.introduced_revision == row.revision)
        require(writer.lookup(s.ArtifactRow, claim.originating_artifact_id) is not None)
    _structural_transition(writer, command, material, previous)
    p.event_order(command.command_kind, definite_expiry=material.definite_expiry)


def _append(writer, metadata, command, material):
    prior = metadata.last_event_digest
    sequence = metadata.last_event_sequence
    events, digests = [], []
    primary = command.parameters.primary_evidence_reference
    for kind in p.event_order(command.command_kind, definite_expiry=material.definite_expiry):
        sequence += 1
        p.uint(sequence)
        event = p.EventPayload(sequence, command.command_id, material.reservation.reservation_id,
            command.register_id, command.issuer_generation, command.activation_id, kind,
            material.utc_time, prior, material.reservation.revision,
            command.binding_reference.artifact_id, None if primary is None else primary.artifact_id)
        raw = p.event_bytes(event)
        digest = sha256(raw).digest()
        writer.insert(s.EventRow(event.event_sequence, event.command_id, event.reservation_id,
            event.register_id, event.issuer_generation, event.activation_id, s.EventType(event.event_type),
            event.utc_time, event.prior_digest, raw, digest, event.revision,
            event.artifact_id, event.evidence_artifact_id))
        events.append(event)
        digests.append(digest)
        prior = digest
    return tuple(events), tuple(digests)


def complete(store, command, context, material=None):
    """One local transaction; supplied facts are not self-authenticating authority.

    Replay material is ignored after exact durable recognition. This result is
    NEVER operational ACK delivery. Confirmed validation/storage rejection raises;
    uncertain commit/rollback yields STORAGE_UNKNOWN without an ACK or retry.
    """
    raw = p.command_bytes(command)
    require(type(context) is p.StateContext and context.representation == p.STATE_2)
    require(type(store) is s.LeaseStore)
    result = None
    try:
        with store.transaction() as writer:
            metadata = writer.lookup(s.MetadataRow, 1)
            require(metadata is not None)
            durable = writer.lookup(s.CommandRow, command.command_id)
            _snapshot(writer, metadata, context)
            if durable is not None:
                _completed(writer, durable)
                if (durable.authenticated_principal != command.authenticated_principal
                        or durable.canonical_payload_bytes != raw
                        or durable.canonical_payload_hash != sha256(raw).digest()):
                    result = LocalCommandResult(p.OutcomeCode.REPLAY_MISMATCH, None, False, None)
                else:
                    result = LocalCommandResult(p.OutcomeCode.SUCCESS, durable.durable_ack_bytes, True, None)
            else:
                previous = writer.lookup(s.ReservationRow, command.parameters.target_reservation_id)
                _transition(writer, metadata, command, material, previous)
                if previous is None:
                    writer.insert(material.reservation)
                else:
                    writer.replace_reservation(previous, material.reservation)
                for claim in material.claim_deletes:
                    writer.delete_claim(claim)
                for claim in material.claim_inserts:
                    writer.insert(claim)
                events, digests = _append(writer, metadata, command, material)
                row = material.reservation
                keys = tuple(claim.canonical_key for claim in writer.claims_for(row.reservation_id))
                ack = p.AckPayload(command.command_id, sha256(raw).digest(), command.authenticated_principal,
                    command.register_id, command.issuer_generation, command.activation_id,
                    row.reservation_id, row.revision, row.owner, command.operation, command.phase,
                    command.binding_kind, command.binding_sha256, p.key_set_digest(keys),
                    command.approval_record_hash, command.authorization_reference, command.evidence_references,
                    material.utc_time, row.acquired_at, row.expires_at, row.completion_deadline,
                    events[0].event_sequence, events[-1].event_sequence, len(events), digests[-1], p.OutcomeCode.SUCCESS)
                p.validate_ack(ack, command, events, previous_sequence=metadata.last_event_sequence,
                    previous_digest=metadata.last_event_digest, digests=digests,
                    transition_event_sequence=events[-1].event_sequence,
                    definite_expiry=material.definite_expiry, keys=keys)
                retained = p.ack_bytes(ack)
                writer.insert(s.CommandRow(command.command_id, command.authenticated_principal,
                    s.Command(command.command_kind), raw, sha256(raw).digest(), command.expected_revision,
                    row.reservation_id, s.OutcomeCode.SUCCESS, retained, events[-1].event_sequence))
                # Persist the supplied validated lower-time projection before
                # streaming, so STATE is read solely from the actual writer snapshot.
                projected = replace(metadata, last_valid_utc=material.last_valid_utc)
                writer.complete_metadata(metadata, projected)
                digest = p.state_digest(_projection(writer), context)
                completed = replace(projected, last_event_sequence=events[-1].event_sequence,
                    last_event_digest=digests[-1], state_digest=digest)
                writer.complete_metadata(projected, completed)
                result = LocalCommandResult(p.OutcomeCode.SUCCESS, retained, False, None)
        require(writer.result == s.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        return replace(result, storage_result=writer.result)
    except s.StorageOutcomeUncertain:
        return LocalCommandResult(p.OutcomeCode.STORAGE_UNKNOWN, None, False, None)
