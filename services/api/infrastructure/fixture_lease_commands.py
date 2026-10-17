"""Shared local completion, never operational ACK or downstream permission.

Legacy entries accept structural facts. Qualified B binds independently proven
inputs before BEGIN and evaluates captured local timing at writer-owned T1/T2.
No provider selection, permit effect, publication, delivery or recovery occurs.
"""
from dataclasses import dataclass, fields, replace
from hashlib import sha256
from types import FunctionType, MethodType

from . import fixture_lease_protocol as p
from . import fixture_lease_store as s
from . import fixture_lease_service as service
from . import fixture_lease_admission_qualification as qualification_values


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


@dataclass(frozen=True, repr=False)
class LocalTimingQualification:
    """Independent verifier response, never authority when supplied by a caller.

    Proof covers the exact inputs AND actual captured measurement/error function
    implementations identified by implementation/measurement, including purity,
    bounded deterministic execution, no lazy I/O, units and error accounting.
    Completion applicability is independently qualified over the whole A scope.
    """
    inputs: qualification_values.QualifiedAdmissionInputs
    implementation: service.EvidenceReference
    measurement: service.EvidenceReference
    process_id: str
    domain_id: str
    validity: service.EvidenceValidity
    proof: service.EvidenceReference
    completion_applicability: service.TimingApplicability
    completion_deadline: service.InclusiveDeadline | service.StrictDeadline | None


@dataclass(frozen=True, repr=False)
class LocalTimingAdapter:
    """Trusted composition dependency, selected outside request evidence.

    qualify(inputs, implementation, measurement, measure, evaluate_error_ns)
    independently authenticates exact implementation identities and bindings.
    It does not ask the error function to certify itself. Only qualify may do
    read-only external qualification, BEFORE BEGIN. The two captured executable
    references are trusted code, not detached evidence or a Python sandbox.
    """
    support: qualification_values.ModelSupport
    implementation: service.EvidenceReference
    measurement: service.EvidenceReference
    qualify: object
    measure: object
    evaluate_error_ns: object


@dataclass(frozen=True, repr=False)
class _TimingEvidence:
    inputs: qualification_values.QualifiedAdmissionInputs
    implementation: service.EvidenceReference
    measurement: service.EvidenceReference
    proof: service.EvidenceReference
    completion_applicability: service.TimingApplicability
    completion_deadline: service.InclusiveDeadline | service.StrictDeadline | None


@dataclass(frozen=True, repr=False)
class _BoundTiming:
    # Detached evidence and captured executable references are separate roles.
    evidence: _TimingEvidence
    measure: object
    evaluate_error_ns: object


@dataclass(frozen=True)
class _PointEvidence:
    point: service.MonotonicPoint
    propagation: service.QualifiedPropagationError
    evaluation: service.TimeEvaluation


@dataclass(frozen=True, repr=False)
class _CompletedEvidence:
    envelope: service.RetainedAdmissionEnvelope
    permit: service.CommandPermit
    command_bytes: bytes
    ack_bytes: bytes
    reservation: s.ReservationRow
    key_digest: bytes
    event_sequence: int
    event_digest: bytes
    state_digest: bytes
    last_valid_utc: int
    t1: _PointEvidence


@dataclass(repr=False)
class _Finalization:
    # Private per-invocation context: no store/writer/connection/iterator and no
    # finalizer callback. Store captures the one module-level finalizer.
    bound: _BoundTiming
    completed: _CompletedEvidence | None = None
    t1: _PointEvidence | None = None
    t2: _PointEvidence | None = None
    replayed: bool = False
    cleanup_reason: s._CommitCleanupReason | None = None


@dataclass(frozen=True, repr=False)
class _QualifiedCompletion:
    local: LocalCommandResult | None
    original: qualification_values.QualifiedAdmissionInputs
    t1: _PointEvidence | None
    t2: _PointEvidence | None
    completed: _CompletedEvidence | None
    reason: service.AdmissionReason | s._CommitCleanupReason | None
    reconciliation_required: bool
    later_contradiction: service.EvidenceReference | None = None

    def __bool__(self):
        raise TypeError('Local storage knowledge is not operational permission')


def _copy_evidence(value):
    return qualification_values._copy(value)


def _bind_timing(result, adapter):
    q = qualification_values
    require(type(result) is q.AdmissionQualificationResult)
    original = q._project(result)
    saved = q._copy(result)
    q._validate(saved)
    require(saved.state is q.QualificationState.QUALIFIED)
    require(type(adapter) is LocalTimingAdapter)
    support, implementation, measurement = adapter.support, adapter.implementation, adapter.measurement
    qualify, measure, error = adapter.qualify, adapter.measure, adapter.evaluate_error_ns
    require(all(type(fn) is FunctionType or type(fn) is MethodType for fn in (qualify, measure, error)))
    qualify_identity = (qualify.__func__, qualify.__self__) if type(qualify) is MethodType else (qualify, None)
    for executable in (measure, error):
        executable_identity = ((executable.__func__, executable.__self__) if type(executable) is MethodType
                               else (executable, None))
        require(not (qualify_identity[0] is executable_identity[0]
                     and qualify_identity[1] is executable_identity[1]))
    q._validate(support)
    require(q._project(support) == q._project(saved.inputs.support))
    for ref in (implementation, measurement):
        require(type(ref) is service.EvidenceReference)
        q.r._validate(ref)
    implementation, measurement = _copy_evidence(implementation), _copy_evidence(measurement)
    request = q._copy(saved.inputs)
    request_projection = q._project(request)
    # One separately composed qualification, never delegated to E itself.
    try:
        response = qualify(request, _copy_evidence(implementation), _copy_evidence(measurement), measure, error)
    except (service.CapabilityUnavailable, qualification_values.a.ExternalAvailabilityFailure, TimeoutError):
        require(q._unchanged(result, original) and q._unchanged(request, request_projection))
        raise CommandRejected('LOCAL_TIMING_UNAVAILABLE') from None
    require(q._unchanged(result, original) and q._unchanged(request, request_projection))
    require(type(response) is LocalTimingQualification)
    require(type(response.inputs) is q.QualifiedAdmissionInputs)
    require(q._project(response.inputs) == request_projection)
    for ref in (response.implementation, response.measurement, response.proof):
        require(type(ref) is service.EvidenceReference)
        q.r._validate(ref)
    require(response.implementation == implementation and response.measurement == measurement)
    require(response.validity is service.EvidenceValidity.VALID)
    model = saved.inputs.observation.model
    require(type(response.process_id) is str and type(response.domain_id) is str)
    require((response.process_id, response.domain_id) == (model.process_id, model.domain_id))
    applicability, deadline = response.completion_applicability, response.completion_deadline
    require(type(applicability) is service.TimingApplicability)
    require(applicability is not service.TimingApplicability.UNKNOWN)
    require((applicability is service.TimingApplicability.REQUIRED) == (deadline is not None))
    if deadline is not None:
        require(type(deadline) is service.InclusiveDeadline or type(deadline) is service.StrictDeadline)
        q.r._validate(deadline)
        deadline = _copy_evidence(deadline)
    evidence = _TimingEvidence(saved.inputs, implementation, measurement, _copy_evidence(response.proof),
                               applicability, deadline)
    return _BoundTiming(evidence, measure, error)


def _writer_time(bound, previous=None):
    evidence = bound.evidence
    observation = evidence.inputs.observation
    time, model = observation.time, observation.model
    # Executable references were captured/qualified before BEGIN; never resolve
    # a method/provider/model here. Only this local measurement is performed.
    measure, error_function = bound.measure, bound.evaluate_error_ns
    point = measure()
    service.require(type(point) is service.MonotonicPoint)
    qualification_values.r._validate(point)
    point_snapshot = qualification_values.r._project(point)
    service.require((point.process_id, point.domain_id) == (model.process_id, model.domain_id))
    elapsed = point.ticks_ns - time.sample.anchor.ticks_ns
    service.integer(elapsed, 0)
    service.require(model.min_elapsed_ns <= elapsed <= model.max_elapsed_ns)
    if previous is not None:
        service.require(point.ticks_ns >= previous.ticks_ns)
    error = error_function(elapsed)
    service.require(qualification_values.r._project(point) == point_snapshot)
    service.integer(error, 0)
    propagation = service.QualifiedPropagationError(time.sample.sample, time.profile.profile,
        elapsed, error, evidence.proof)
    evaluation = service.evaluate_time(time.sample, time.profile, point, propagation)
    return _PointEvidence(_copy_evidence(point), propagation, evaluation)


def _continuing_bounds(bound, evaluation):
    evidence = bound.evidence
    observation = evidence.inputs.observation
    service.require(all(v is service.EvidenceValidity.VALID for v in qualification_values._validities(observation)))
    interval = evaluation.interval
    for applicability, deadline in (
            (observation.time.freshness_applicability, observation.time.freshness_deadline),
            (observation.time.lease_applicability, observation.time.lease_deadline),
            (evidence.completion_applicability, evidence.completion_deadline)):
        service.require(applicability is not service.TimingApplicability.UNKNOWN)
        service.require((applicability is service.TimingApplicability.REQUIRED) == (deadline is not None))
        if deadline is not None:
            check = service.strict_bound if type(deadline) is service.StrictDeadline else service.inclusive_bound
            service.require(check(interval, deadline) is service.TimingBound.SATISFIED)


def _finalize_qualified(payload):
    """Fixed store-owned finalizer. No transaction-frame closure or durable I/O."""
    require(type(payload) is _Finalization)
    if payload.replayed:
        require(payload.completed is None and payload.t1 is None)
        return
    completed, bound = payload.completed, payload.bound
    require(type(completed) is _CompletedEvidence and type(payload.t1) is _PointEvidence)
    t2 = _writer_time(bound, payload.t1.point)
    _continuing_bounds(bound, t2.evaluation)
    require(t2.evaluation.interval.lower_us >= completed.last_valid_utc)
    require(completed.last_valid_utc == payload.t1.evaluation.interval.lower_us)
    ack = p.decode_record(completed.ack_bytes, p.AckPayload)
    require(completed.envelope.fixed_utc_us == ack.issued_at)
    require(completed.command_bytes == completed.envelope.canonical_command_bytes)
    require(ack.command_payload_sha256 == sha256(completed.command_bytes).digest())
    require((ack.reservation_id, ack.resulting_revision, ack.canonical_key_set_digest,
             ack.final_event_sequence, ack.final_event_digest) ==
            (completed.reservation.reservation_id, completed.reservation.revision,
             completed.key_digest, completed.event_sequence, completed.event_digest))
    require(completed.permit.evidence == completed.envelope.permit_reference)
    require(type(completed.state_digest) is bytes and len(completed.state_digest) == 32)
    payload.t2 = t2


def _later_contradiction(store, result, evidence):
    """Deny progression only; no qualification, compensation or IL.7 execution.

    Trusted orchestration reports a contradiction of evidence actually relied
    upon. Local poisoning is NOT protected/issuer-wide fencing. No clear path.
    """
    require(type(store) is s.LeaseStore and type(result) is _QualifiedCompletion)
    require(type(evidence) is service.EvidenceReference)
    qualification_values.r._validate(evidence)
    store._poisoned = True
    return replace(result, reconciliation_required=True, reason=service.AdmissionReason.TIME,
                   later_contradiction=_copy_evidence(evidence))


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


def _complete(store, command, context, material=None, admission=None, finalization=None, unchanged=None):
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
        transaction = store.transaction() if finalization is None else store._qualified_transaction(finalization)
        with transaction as writer:
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
                if finalization is not None:
                    material = _admit_qualified(writer, metadata, command, raw, context, material,
                                                previous, finalization, unchanged)
                elif admission is not None:
                    _admit(writer, metadata, command, raw, context, material, previous, admission)
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
                if finalization is not None:
                    envelope = finalization.bound.evidence.inputs.observation.source.envelope
                    permit = finalization.bound.evidence.inputs.observation.source.prepared.material.source.qualification.permit
                    finalization.completed = _CompletedEvidence(envelope, permit, raw, retained, row,
                        p.key_set_digest(keys), completed.last_event_sequence, completed.last_event_digest,
                        completed.state_digest, completed.last_valid_utc, finalization.t1)
            if finalization is not None and finalization.completed is None:
                # Historical recognition has no new-transition T1/T2 finalizer.
                # The store still validates/seals and commits its read-only body.
                finalization.replayed = True
        require(writer.result == s.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        return replace(result, storage_result=writer.result)
    except s._ConfirmedCommitCleanup as error:
        if finalization is None:
            # Preserve the legacy StorageRejected exception contract. Only B
            # has a bounded reconciliation wrapper for this confirmed fact.
            raise
        require(type(result) is LocalCommandResult
                and writer.result is s.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED
                and error.storage_result is writer.result
                and error.reason is s._CommitCleanupReason.CURSOR_CLOSE)
        finalization.cleanup_reason = error.reason
        return replace(result, storage_result=writer.result)
    except s.StorageOutcomeUncertain:
        return LocalCommandResult(p.OutcomeCode.STORAGE_UNKNOWN, None, False, None)



def complete(store, command, context, material=None):
    """Legacy local-only completion; no IL.5 operational admission/delivery."""
    return _complete(store, command, context, material)


def complete_admitted(store: s.LeaseStore, command: p.CommandPayload, context: p.StateContext,
                      material: PreparedTransition | None = None, *,
                      evidence: service.AdmissionEvidence | None = None,
                      host_identity: str | None = None,
                      representation_authority: service.EvidenceReference | None = None,
                      checker: service.AdmissionChecker = service.validate_admission) -> LocalCommandResult:
    """Distinct IL.5A entry. No external acquisition, orchestration or delivery.

    Checker contract is synchronous/pure and receives no writer/store/connection.
    Already-qualified inputs do not gain qualification by construction here.
    Replay bypasses new admission, including unavailable evidence/checker.
    """
    return _complete(store, command, context, material,
                     (evidence, host_identity, representation_authority, checker))


def _admit(writer, metadata, command, raw, context, material, previous, admission):
    evidence, host, representation_authority, checker = admission
    facts = _gather_admission(writer, metadata, command, raw, context, material, previous,
                              host, representation_authority)
    try:
        decision = service.validate_admission(evidence, facts)
        require(decision.disposition is service.AdmissionDisposition.ADMIT)
        if checker is not service.validate_admission:
            decision = checker(evidence, facts)
    except Exception:
        raise CommandRejected('ADMISSION_CHECKER_REJECTED') from None
    require(type(decision) is service.AdmissionDecision
            and decision.disposition is service.AdmissionDisposition.ADMIT)


def _gather_admission(writer, metadata, command, raw, context, material, previous, host, representation_authority):
    approval_ref = (command.binding_reference if command.command_kind in
        (p.contract.Command.ACQUIRE, p.contract.Command.ADVANCE)
        else command.parameters.primary_evidence_reference)
    artifact = writer.lookup(s.ArtifactRow, approval_ref.artifact_id)
    refs = (command.binding_reference, command.authorization_reference) + command.evidence_references
    retained = tuple(service.EvidenceReference(ref.artifact_id,
        writer.lookup(s.ArtifactRow, ref.artifact_id).sha256) for ref in refs)
    # All durable inputs are read while the same writer transaction is active.
    try:
        return service.AdmissionFacts(raw,
            service.CommandContext(command.command_id, sha256(raw).digest(), command.command_kind,
                command.operation, command.phase, command.expected_revision,
                service.EvidenceReference(command.authorization_reference.artifact_id,
                                          command.authorization_reference.artifact_sha256)),
            command.authenticated_principal, metadata.register_id, metadata.issuer_generation,
            metadata.activation_id, host, context.representation, representation_authority,
            metadata.last_event_sequence, metadata.last_event_digest, metadata.state_digest,
            bool(metadata.recovery_required), None if previous is None else previous.revision,
            tuple(claim.canonical_key for claim in writer.claims_for(material.reservation.reservation_id)),
            retained, artifact.approval_record_hash, metadata.last_valid_utc,
            material.utc_time, material.last_valid_utc)
    except service.TimeRejected:
        raise CommandRejected('ADMISSION_CHECKER_REJECTED') from None


def _material_projection(material):
    require(type(material) is PreparedTransition and type(material.reservation) is s.ReservationRow)
    require(type(material.claim_inserts) is tuple and type(material.claim_deletes) is tuple)
    require(type(material.definite_expiry) is bool)
    p.utc(material.utc_time); p.utc(material.last_valid_utc)
    for claim in material.claim_inserts + material.claim_deletes:
        require(type(claim) is s.ClaimRow)
    return (s._values(material.reservation), tuple(s._values(v) for v in material.claim_inserts),
            tuple(s._values(v) for v in material.claim_deletes), material.utc_time,
            material.last_valid_utc, material.definite_expiry)


def _copy_material(material):
    _material_projection(material)
    return replace(material, reservation=replace(material.reservation),
                   claim_inserts=tuple(replace(v) for v in material.claim_inserts),
                   claim_deletes=tuple(replace(v) for v in material.claim_deletes))


def _admit_qualified(writer, metadata, command, raw, context, material, previous, payload, unchanged):
    bound = payload.bound
    observation = bound.evidence.inputs.observation
    envelope = observation.source.envelope
    facts = _gather_admission(writer, metadata, command, raw, context, material, previous,
                              envelope.activation.host_identity, envelope.predecessor.representation_authority)
    # All admission durable reads have now finished. Facts, command and effects
    # are detached exact values; measurement functions receive none of them.
    point = _writer_time(bound)
    payload.t1 = point
    interval = point.evaluation.interval
    require(material.utc_time == envelope.fixed_utc_us)
    effective = replace(material, last_valid_utc=interval.lower_us)
    facts = replace(facts, proposed_last_valid_utc_us=interval.lower_us)
    auth, approval = observation.authorization, observation.approval
    service.require(service.valid_from_satisfied(interval, auth.valid_from_us))
    service.require(service.inclusive_bound(interval, auth.deadline) is service.TimingBound.SATISFIED)
    if approval.applicability is service.ApprovalApplicability.REQUIRED:
        service.require(service.valid_from_satisfied(interval, approval.valid_from_us))
        service.require(service.inclusive_bound(interval, approval.deadline) is service.TimingBound.SATISFIED)
    _continuing_bounds(bound, point.evaluation)
    permit = observation.source.prepared.material.source.qualification.permit
    evidence = service.AdmissionEvidence(envelope, permit, observation.time.sample, observation.time.profile,
        point.point, point.propagation,
        service.AdmissionCoverage(bound.evidence.proof, envelope.reference, envelope.context,
            envelope.activation, point.point, interval), auth.deadline, observation.time.freshness_deadline,
        observation.continuity, approval.validity, service.TimingApplicability.REQUIRED,
        observation.time.freshness_applicability, observation.fixing_to_refresh)
    decision = service.validate_admission(evidence, facts)
    require(decision.disposition is service.AdmissionDisposition.ADMIT)
    unchanged()
    return effective


def complete_qualified(store, command, context, material, *, qualification, timing):
    """Bounded B entry; mandatory qualified inputs, no downstream effects.

    This does not acquire/retain a permit or execute recovery. Historical lookup
    remains in the shared core; no new-transition measurement runs for replay.
    Executable purity and implementation authentication are trusted composition
    requirements, not guarantees provided by Python function/class names.
    """
    require(type(store) is s.LeaseStore and type(context) is p.StateContext)
    q = qualification_values
    # Exact classification precedes codecs, traversal and equality.
    command_projection = q._project(command)
    q.g._revalidate(command)
    detached_command = q._copy(command)
    detached_context = replace(context)
    material_projection = _material_projection(material)
    detached_material = _copy_material(material)
    source_projection = q._project(qualification)
    bound = _bind_timing(qualification, timing)
    payload = _Finalization(bound)

    def unchanged():
        require(q._unchanged(qualification, source_projection))
        require(q._project(command) == command_projection)
        require(_material_projection(material) == material_projection)
        require(q._project(detached_command) == command_projection)
        require(_material_projection(detached_material) == material_projection)
    unchanged()
    try:
        local = _complete(store, detached_command, detached_context, detached_material,
                          finalization=payload, unchanged=unchanged)
    except s._BeginBusy:
        local = LocalCommandResult(p.OutcomeCode.BUSY_REJECTED, None, False, None)
        return _QualifiedCompletion(local, bound.evidence.inputs, None, None, None,
                                    service.AdmissionReason.UNAVAILABLE, True)
    except (CommandRejected, service.TimeRejected, s.StorageRejected) as error:
        # Confirmed local rejection is NOT closure of the original permit.
        store._poisoned = True
        if isinstance(error, s.StorageRejected):
            # Preserve the distinction: a confirmed storage rejection has no
            # command outcome here. Do not invent CLOCK or STORAGE_UNKNOWN.
            local, reason = None, service.AdmissionReason.UNAVAILABLE
        else:
            clock = isinstance(error, service.TimeRejected)
            local = LocalCommandResult(p.OutcomeCode.CLOCK_REJECTED if clock else p.OutcomeCode.AUTHORITY_REJECTED,
                                       None, False, None)
            reason = service.AdmissionReason.TIME if clock else service.AdmissionReason.CHECKER
        return _QualifiedCompletion(local, bound.evidence.inputs, payload.t1, payload.t2,
                                    payload.completed, reason, True)
    except BaseException:
        store._poisoned = True
        raise
    if payload.cleanup_reason is not None:
        require(local.storage_result is s.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        return _QualifiedCompletion(local, bound.evidence.inputs, payload.t1, payload.t2,
                                    payload.completed, payload.cleanup_reason, True)
    if payload.completed is None and local.outcome is not p.OutcomeCode.STORAGE_UNKNOWN:
        return local
    unresolved = local.outcome is p.OutcomeCode.STORAGE_UNKNOWN
    return _QualifiedCompletion(local, bound.evidence.inputs, payload.t1, payload.t2,
                                payload.completed, service.AdmissionReason.UNAVAILABLE if unresolved else None,
                                unresolved)
