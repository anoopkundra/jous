"""Increment C: local committed-snapshot qualification and candidate knowledge.

Snapshot acquisition is outside this module. The separately composed verifier
must authenticate the exact frozen-B execution provenance AND complete snapshot
association. Matching values, constructors and VALID labels cannot prove that
assertion. Its reference identifies the independently qualified provenance basis,
not a reference manufactured from the candidate. Python is not a sandbox against
a compromised trusted composer or privileged mutation of module internals.

No clock, storage, provider, retention, publication, completion or delivery is
selected or invoked. PREPARED is detached knowledge, never effect permission.
"""
from collections.abc import Iterable
from dataclasses import dataclass, fields
from enum import StrEnum
from hashlib import sha256
from types import FunctionType, MethodType, UnionType
from typing import get_args, get_origin

from . import fixture_lease_commands as commands
from . import fixture_lease_checkpoints as checkpoints

protocol, service, store = commands.p, commands.service, commands.s
q = commands.qualification_values
r, a, g, pr, e = q.r, q.a, q.g, q.g.pr, q.r.e
contract = protocol.contract


class PreparationState(StrEnum):
    PREPARED = 'PREPARED'
    REJECTED = 'REJECTED'
    UNRESOLVED = 'UNRESOLVED'


class PreparationReason(StrEnum):
    PREPARED = 'PREPARED'
    MALFORMED = 'MALFORMED'
    NOT_NEW_TRANSITION = 'NOT_NEW_TRANSITION'
    BINDING = 'BINDING'
    SNAPSHOT = 'SNAPSHOT'
    MUTATED = 'MUTATED'
    UNQUALIFIED = 'UNQUALIFIED'
    MALFORMED_QUALIFICATION = 'MALFORMED_QUALIFICATION'
    DEPENDENCY_UNAVAILABLE = 'DEPENDENCY_UNAVAILABLE'
    ASSOCIATION_UNKNOWN = 'ASSOCIATION_UNKNOWN'
    UPSTREAM_UNRESOLVED = 'UPSTREAM_UNRESOLVED'


@dataclass(frozen=True, repr=False)
class CommittedSnapshot:
    completion: protocol.CommandRow
    events: tuple[protocol.EventPayload, ...]
    projection: protocol.StateProjection
    context: protocol.StateContext
    keys: tuple[bytes, ...]
    definite_expiry: bool


@dataclass(frozen=True, repr=False)
class PreparationRequest:
    completion: commands._QualifiedCompletion
    snapshot: CommittedSnapshot


@dataclass(frozen=True, repr=False)
class PreparationQualification:
    """Trusted verifier response, not self-authenticating request evidence.

    VALID asserts observation of this exact detached B result from the trusted
    frozen-B path after confirmed COMMIT, and that the complete snapshot is the
    same new transition/original operation. reference must genuinely identify
    that provenance basis. Echoes or reference syntax alone cannot qualify it.
    """
    request: PreparationRequest
    authority: service.EvidenceReference
    implementation: service.EvidenceReference
    validity: service.EvidenceValidity
    reference: service.EvidenceReference


@dataclass(frozen=True, repr=False)
class TrustedPreparationVerifier:
    """Composition-only trust root. verify(request) is local read-only.

    The selected executable must independently authenticate the assertion in
    PreparationQualification, without SQLite/files/provider/network access,
    lazy discovery, waits, retries or effects. Function shape is not provenance.
    """
    authority: service.EvidenceReference
    implementation: service.EvidenceReference
    verify: object


@dataclass(frozen=True, repr=False)
class _PreparedCandidate:
    candidate: service.CheckpointCandidate
    request: PreparationRequest
    provenance: PreparationQualification


@dataclass(frozen=True, repr=False, init=False)
class PreparationResult:
    state: PreparationState
    reason: PreparationReason
    qualification_attempted: bool
    prepared: _PreparedCandidate | None
    diagnostic: PreparationReason | None

    def __init__(self, *args, **kwargs):
        raise TypeError('Use CandidatePreparer.prepare_candidate')

    def __bool__(self):
        raise TypeError('Prepared knowledge is not effect permission')

    def __copy__(self):
        raise TypeError('Use candidate preparation')

    def __deepcopy__(self, memo):
        raise TypeError('Use candidate preparation')


class _Bad(ValueError):
    def __init__(self, reason=PreparationReason.MALFORMED):
        self.reason = reason


def _need(condition, reason=PreparationReason.MALFORMED):
    if not condition:
        raise _Bad(reason)


# Closed type lists, not module discovery or request-selected validator dispatch.
_ENUMS = (PreparationState, PreparationReason, service.ApprovalApplicability,
    service.EvidenceValidity, service.TimingApplicability, service.AdmissionReason,
    service.OperationKind, contract.Command, contract.Operation, contract.Phase,
    contract.ArtifactType, contract.LeaseStatus, protocol.ExecutionState,
    protocol.QuarantineReason, protocol.EventType, protocol.OutcomeCode,
    store.ExecutionState, store.QuarantineReason, store.LocalStorageResult,
    store._CommitCleanupReason, q.QualificationState, q.QualificationReason,
    q.ErrorConventions, r.RetentionState, r.RetentionReason, e.PreparationState,
    e.PreparationReason, a.AcquisitionState, a.AcquisitionReason, g.GateState,
    g.GateReason, g.CommandHistory, g.GapKnowledge, pr.PredecessorProfile,
    pr.CurrentStatus, pr.HostStatus, pr.FencingStatus, pr.ResolutionState,
    pr.ResolutionReason)
_DATACLASSES = (CommittedSnapshot, PreparationRequest, PreparationQualification,
    _PreparedCandidate, commands._QualifiedCompletion, commands.LocalCommandResult,
    commands._CompletedEvidence, commands._PointEvidence, store.ReservationRow,
    protocol.Reference, protocol.Parameters, protocol.CommandPayload,
    protocol.EventPayload, protocol.AckPayload, protocol.MetadataRow,
    protocol.ReservationRow, protocol.ClaimRow, protocol.CommandRow,
    protocol.StateProjection, protocol.StateContext, service.EvidenceReference,
    service.CommandContext, service.AuthenticatedRequester, service.VerifiedApproval,
    service.ActivationIdentity, service.CommandPermit, service.UtcInterval,
    service.MonotonicPoint, service.QualifiedSample, service.QualifiedClockProfile,
    service.QualifiedPropagationError, service.TimeEvaluation,
    service.InclusiveDeadline, service.StrictDeadline,
    service.ResolvedCheckpointEvidence, service.RetainedTimeFixing,
    service.RetainedAdmissionEnvelope, service.OriginalOperation,
    service.CheckpointCandidate, contract.ArtifactBytes, q.ModelSupport,
    q.PropagationModelBinding, q.CurrentQualification, q.QualifiedAdmissionInputs,
    q.AdmissionQualificationResult, r.RetentionResult, r.OriginalRecordIndex,
    r.RetentionAuthorization, r.RetentionReceipt, r.RetentionConfirmation,
    e.PreparationResult, e.PreparedEnvelopeMaterial, a.AcquisitionResult,
    a.AcquisitionInput, a.PermitQualification, g.GateResult,
    g.AuthorizationEvidence, g.ApprovalEvidence, g.TimeEvidence, g.HistoryEvidence,
    g.PrerequisiteBundle, g.QualificationEvidence, pr.ResolutionResult,
    pr.QualifiedCurrentContext, pr.CurrentBinding, pr.ContextQualification,
    pr.ResolutionObservation, pr.ResolutionQualification)


def _matches(value, annotation):
    """Trusted field metadata only; evidence was classified before this check."""
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is UnionType:
        return any(_matches(value, part) for part in args)
    if origin is tuple or origin is Iterable:
        if type(value) is not tuple:
            return False
        if origin is Iterable or (len(args) == 2 and args[1] is Ellipsis):
            return all(_matches(v, args[0]) for v in value)
        return len(value) == len(args) and all(_matches(v, t) for v, t in zip(value, args))
    # Frozen writer projections legitimately retain the store's enum classes.
    if annotation is protocol.ExecutionState:
        return type(value) is protocol.ExecutionState or type(value) is store.ExecutionState
    if annotation is protocol.QuarantineReason:
        return type(value) is protocol.QuarantineReason or type(value) is store.QuarantineReason
    return type(value) is annotation


def _project(value):
    """Exact closed graph, no collection cap; memoize identities after acceptance.

    Cycles reject, shared immutable nodes are allowed. Projection retains only
    exact primitive/enum values and trusted class tags, never caller objects.
    """
    active, memo = set(), {}

    def visit(item):
        kind = type(item)
        if any(kind is t for t in (type(None), str, bytes, int, bool)):
            return kind, item
        if any(kind is t for t in _ENUMS):
            _need(any(item is member for member in kind))
            return kind, item
        _need(kind is tuple or any(kind is t for t in _DATACLASSES))
        identity = id(item)
        _need(identity not in active)
        if identity in memo:
            return memo[identity]
        active.add(identity)
        if kind is tuple:
            result = kind, tuple(visit(child) for child in item)
        else:
            children = []
            for field in fields(kind):
                try:
                    child = object.__getattribute__(item, field.name)
                except AttributeError:
                    raise _Bad() from None  # Missing field on an accepted class.
                projected = visit(child)
                _need(_matches(child, field.type))
                children.append((field.name, projected))
            result = kind, tuple(children)
        active.remove(identity)
        memo[identity] = result
        return result

    return visit(value)


def _detach(projection):
    memo = {}

    def copy(node):
        kind, data = node
        if any(kind is t for t in (type(None), str, bytes, int, bool) + _ENUMS):
            return data
        identity = id(node)
        if identity in memo:
            return memo[identity]
        if kind is tuple:
            value = tuple(copy(child) for child in data)
        else:
            value = object.__new__(kind)
            for name, child in data:
                object.__setattr__(value, name, copy(child))
        memo[identity] = value
        return value

    return copy(projection)


def _unchanged(value, projection):
    try:
        return _project(value) == projection
    except _Bad:
        return False


def _result(state, reason, attempted=False, prepared=None):
    _need((state is PreparationState.PREPARED) == (prepared is not None))
    value = object.__new__(PreparationResult)
    for name, item in (('state', state), ('reason', reason),
            ('qualification_attempted', attempted), ('prepared', prepared),
            ('diagnostic', None if prepared is not None else reason)):
        object.__setattr__(value, name, item)
    return value


_INVALID = (protocol.ProtocolRejected, service.TimeRejected, contract.ContractRejected)


def _domain(completion):
    local = completion if type(completion) is commands.LocalCommandResult else completion.local
    if (local is not None and local.outcome is protocol.OutcomeCode.STORAGE_UNKNOWN):
        return PreparationState.UNRESOLVED, PreparationReason.UPSTREAM_UNRESOLVED
    if type(completion) is commands._QualifiedCompletion:
        if (completion.reconciliation_required or completion.reason is not None
                or completion.later_contradiction is not None):
            return PreparationState.UNRESOLVED, PreparationReason.UPSTREAM_UNRESOLVED
    if type(completion) is commands.LocalCommandResult or (local is not None and
            (local.replayed or local.outcome is not protocol.OutcomeCode.SUCCESS)):
        return PreparationState.REJECTED, PreparationReason.NOT_NEW_TRANSITION
    _need(local is not None and local.storage_result is store.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
    _need(completion.completed is not None and completion.t1 is not None and completion.t2 is not None)
    return None


def _bindings(request):
    b, snapshot = request.completion, request.snapshot
    done, original = b.completed, b.original
    # This validates frozen structural semantics, not B execution provenance.
    q._validate(original)
    observation = original.observation
    envelope = observation.source.envelope
    permit = observation.source.prepared.material.source.qualification.permit
    _need(done.envelope == envelope and done.permit == permit, PreparationReason.BINDING)
    _need(done.t1 == b.t1, PreparationReason.BINDING)
    _need(done.command_bytes == envelope.canonical_command_bytes == snapshot.completion.canonical_payload_bytes,
          PreparationReason.BINDING)
    _need(b.local.retained_ack_bytes == done.ack_bytes == snapshot.completion.durable_ack_bytes,
          PreparationReason.BINDING)
    for point in (b.t1, b.t2):
        service.MonotonicPoint.__post_init__(point.point)
        service.QualifiedPropagationError.__post_init__(point.propagation)
        service.EvidenceReference.__post_init__(point.propagation.qualification)
        evaluation = service.evaluate_time(observation.time.sample, observation.time.profile,
                                           point.point, point.propagation)
        _need(evaluation == point.evaluation, PreparationReason.BINDING)
        model = observation.model
        _need((point.point.process_id, point.point.domain_id) == (model.process_id, model.domain_id)
              and model.min_elapsed_ns <= point.propagation.elapsed_ns <= model.max_elapsed_ns,
              PreparationReason.BINDING)
    _need(b.t2.point.ticks_ns >= b.t1.point.ticks_ns, PreparationReason.BINDING)
    _need(b.t1.propagation.qualification == b.t2.propagation.qualification, PreparationReason.BINDING)
    interval = b.t1.evaluation.interval
    _need(service.valid_from_satisfied(interval, permit.valid_from_us)
          and service.strict_bound(interval, service.StrictDeadline(permit.valid_until_us))
          is service.TimingBound.SATISFIED, PreparationReason.BINDING)
    auth, approval = observation.authorization, observation.approval
    _need(service.valid_from_satisfied(interval, auth.valid_from_us)
          and service.inclusive_bound(interval, auth.deadline) is service.TimingBound.SATISFIED,
          PreparationReason.BINDING)
    if approval.applicability is service.ApprovalApplicability.REQUIRED:
        _need(service.valid_from_satisfied(interval, approval.valid_from_us)
              and service.inclusive_bound(interval, approval.deadline) is service.TimingBound.SATISFIED,
              PreparationReason.BINDING)
    # Historical B predicates only. Consumption windows are NOT reapplied at T2.
    for point in (b.t1, b.t2):
        for applicability, deadline in (
                (observation.time.freshness_applicability, observation.time.freshness_deadline),
                (observation.time.lease_applicability, observation.time.lease_deadline)):
            _need(applicability is not service.TimingApplicability.UNKNOWN, PreparationReason.BINDING)
            if applicability is service.TimingApplicability.REQUIRED:
                _need(service.strict_bound(point.evaluation.interval, deadline)
                      is service.TimingBound.SATISFIED, PreparationReason.BINDING)
    _need(done.last_valid_utc == b.t1.evaluation.interval.lower_us
          == snapshot.projection.metadata.last_valid_utc, PreparationReason.BINDING)
    _need(done.last_valid_utc >= envelope.fixed_utc_us, PreparationReason.BINDING)
    prior = checkpoints.decode_checkpoint(envelope.predecessor.exact_bytes)
    pred, activation = envelope.predecessor, envelope.activation
    _need((prior.register_id, prior.generation, prior.activation_id, prior.revision,
           prior.event_sequence, prior.event_digest, prior.state_digest) ==
          (activation.register_id, activation.generation, activation.activation_id,
           pred.revision, pred.event_sequence, pred.event_digest, pred.state_digest), PreparationReason.BINDING)
    _need(pred.activation == activation and activation.checkpoint == pred.reference,
          PreparationReason.BINDING)
    _need(sha256(pred.exact_bytes).digest() == pred.reference.sha256, PreparationReason.BINDING)
    authority = pred.representation_authority
    _need((prior.reference.host, prior.reference.representation,
           prior.reference.representation_authority_id, prior.reference.representation_authority_sha256) ==
          (activation.host_identity, pred.representation, authority.identity, authority.sha256),
          PreparationReason.BINDING)
    _need(pred.revision < protocol.MAX_UINT and pred.representation == snapshot.context.representation,
          PreparationReason.BINDING)


def _snapshot(request):
    b, snap = request.completion, request.snapshot
    done, envelope = b.completed, b.completed.envelope
    pred = envelope.predecessor
    command, ack = protocol.validate_completed_command(snap.completion, snap.events,
        previous_sequence=pred.event_sequence, previous_digest=pred.event_digest,
        digests=tuple(protocol.event_digest(v) for v in snap.events),
        definite_expiry=snap.definite_expiry, keys=snap.keys)
    context = service.CommandContext(command.command_id, protocol.command_digest(command),
        command.command_kind, command.operation, command.phase, command.expected_revision,
        service.EvidenceReference(command.authorization_reference.artifact_id,
                                  command.authorization_reference.artifact_sha256))
    _need(envelope.context == context and envelope.principal == command.authenticated_principal,
          PreparationReason.BINDING)
    _need((command.register_id, command.issuer_generation, command.activation_id) ==
          (envelope.activation.register_id, envelope.activation.generation, envelope.activation.activation_id) ==
          (snap.context.register_id, snap.context.issuer_generation, snap.context.activation_id),
          PreparationReason.BINDING)
    _need(ack.issued_at == envelope.fixed_utc_us, PreparationReason.BINDING)
    _need((ack.final_event_sequence, ack.final_event_digest) == (done.event_sequence, done.event_digest),
          PreparationReason.SNAPSHOT)
    _need(ack.canonical_key_set_digest == done.key_digest, PreparationReason.SNAPSHOT)
    required = command.command_kind in (contract.Command.ACQUIRE, contract.Command.ADVANCE,
                                        contract.Command.RELEASE, contract.Command.RECOVER)
    _need(envelope.approval_applicability is (service.ApprovalApplicability.REQUIRED if required
          else service.ApprovalApplicability.NOT_APPLICABLE), PreparationReason.BINDING)
    _need((envelope.approval is not None and envelope.approval.sha256 == command.approval_record_hash)
          if required else envelope.approval is None, PreparationReason.BINDING)
    _need(snap.projection.metadata.recovery_required == 0, PreparationReason.SNAPSHOT)
    target = tuple(v for v in snap.projection.reservations if v.reservation_id == ack.reservation_id)
    _need(len(target) == 1, PreparationReason.SNAPSHOT)
    expected = protocol.ReservationRow(*(object.__getattribute__(done.reservation, f.name)
                                         for f in fields(protocol.ReservationRow)))
    _need(protocol.encode_record(target[0]) == protocol.encode_record(expected), PreparationReason.SNAPSHOT)
    checkpoints._command_result_coherent(command, target[0])
    row = target[0]
    _need((row.register_id, row.fixture_set_id, row.owner, row.revision,
           row.operation_type, row.phase, row.binding_kind, row.binding_artifact_id,
           row.binding_sha256, row.acquired_at, row.expires_at, row.completion_deadline) ==
          (ack.register_id, command.fixture_set_id, ack.owner, ack.resulting_revision,
           ack.operation, ack.phase, ack.binding_kind, command.binding_reference.artifact_id,
           ack.binding_sha256, ack.acquired_at, ack.expires_at, ack.completion_deadline),
          PreparationReason.SNAPSHOT)
    _need(tuple(v.canonical_key for v in snap.projection.claims if v.reservation_id == ack.reservation_id)
          == snap.keys, PreparationReason.SNAPSHOT)
    retained = tuple(v for v in snap.projection.commands if v.command_id == snap.completion.command_id)
    _need(len(retained) == 1 and retained[0] == snap.completion, PreparationReason.SNAPSHOT)
    # Frozen STATE-2 exhausts complete tuples, with canonical ordering and no
    # history cap or concatenated aggregate STATE allocation.
    _need(protocol.state_digest(snap.projection, snap.context) == done.state_digest,
          PreparationReason.SNAPSHOT)
    reservations = {v.reservation_id: v for v in snap.projection.reservations}
    for row in snap.projection.reservations:
        _need(row.register_id == snap.context.register_id, PreparationReason.SNAPSHOT)
        if row.lease_status is not contract.LeaseStatus.RELEASED:
            _need(any(v.reservation_id == row.reservation_id for v in snap.projection.claims),
                  PreparationReason.SNAPSHOT)
    for claim in snap.projection.claims:
        _need(claim.reservation_id in reservations, PreparationReason.SNAPSHOT)
        owner = reservations[claim.reservation_id]
        _need(owner.lease_status is not contract.LeaseStatus.RELEASED
              and claim.introduced_revision <= owner.revision, PreparationReason.SNAPSHOT)
    for row in snap.projection.commands:
        historical = protocol.decode_record(row.canonical_payload_bytes, protocol.CommandPayload)
        retained_ack = protocol.decode_record(row.durable_ack_bytes, protocol.AckPayload)
        _need(row.command_id == historical.command_id == retained_ack.command_id
              and row.authenticated_principal == historical.authenticated_principal == retained_ack.principal
              and row.command_kind is historical.command_kind
              and row.expected_revision == historical.expected_revision
              and row.reservation_id == retained_ack.reservation_id
              and row.reservation_id in reservations
              and row.canonical_payload_hash == protocol.command_digest(historical)
              == retained_ack.command_payload_sha256
              and row.transition_event_sequence == retained_ack.final_event_sequence,
              PreparationReason.SNAPSHOT)


@dataclass(frozen=True, repr=False, init=False)
class CandidatePreparer:
    """Trusted composition captures one verifier; prepare accepts values only."""
    _verify: object
    _authority: service.EvidenceReference
    _implementation: service.EvidenceReference

    def __init__(self, verifier):
        if type(self) is not CandidatePreparer or type(verifier) is not TrustedPreparationVerifier:
            raise TypeError('Exact TrustedPreparationVerifier required')
        try:
            verify = object.__getattribute__(verifier, 'verify')
            source_authority = object.__getattribute__(verifier, 'authority')
            source_implementation = object.__getattribute__(verifier, 'implementation')
        except AttributeError:
            raise TypeError('Incomplete verifier configuration') from None
        try:
            _need(type(verify) is FunctionType or type(verify) is MethodType)
            authority = _detach(_project(source_authority))
            implementation = _detach(_project(source_implementation))
            _need(type(authority) is service.EvidenceReference and type(implementation) is service.EvidenceReference)
            service.EvidenceReference.__post_init__(authority)
            service.EvidenceReference.__post_init__(implementation)
        except (_Bad, service.TimeRejected):
            raise TypeError('Malformed verifier configuration') from None
        for name, value in (('_verify', verify), ('_authority', authority), ('_implementation', implementation)):
            object.__setattr__(self, name, value)

    def prepare_candidate(self, completion, snapshot):
        rejected, unresolved = PreparationState.REJECTED, PreparationState.UNRESOLVED
        try:
            _need(type(completion) is commands._QualifiedCompletion or type(completion) is commands.LocalCommandResult)
            detached = _detach(_project(completion))
            domain = _domain(detached)
            if domain is not None:
                return _result(*domain)
            _need(type(snapshot) is CommittedSnapshot)
            caller = PreparationRequest(completion, snapshot)
            original = _project(caller)
            saved = _detach(original)
            _bindings(saved)
            _snapshot(saved)
        except _Bad as error:
            return _result(rejected, error.reason)
        except _INVALID:
            return _result(rejected, PreparationReason.SNAPSHOT)
        if not _unchanged(caller, original):
            return _result(rejected, PreparationReason.MUTATED)
        verify, authority, implementation = self._verify, self._authority, self._implementation
        request = _detach(original)
        try:
            response = verify(request)
        except (service.CapabilityUnavailable, a.ExternalAvailabilityFailure, TimeoutError):
            if not _unchanged(caller, original) or not _unchanged(request, original):
                return _result(rejected, PreparationReason.MUTATED, True)
            return _result(unresolved, PreparationReason.DEPENDENCY_UNAVAILABLE, True)
        if not _unchanged(caller, original) or not _unchanged(request, original):
            return _result(rejected, PreparationReason.MUTATED, True)
        response_projection = None
        malformed_response = False
        try:
            _need(type(response) is PreparationQualification)
            response_projection = _project(response)
            provenance = _detach(response_projection)
            for ref in (provenance.authority, provenance.implementation, provenance.reference):
                service.EvidenceReference.__post_init__(ref)
            _need(provenance.authority == authority and provenance.implementation == implementation)
            _need(_project(provenance.request) == original)
        except (_Bad,) + _INVALID:
            malformed_response = True
        if response_projection is not None and not _unchanged(response, response_projection):
            return _result(rejected, PreparationReason.MUTATED, True)
        if malformed_response:
            return _result(rejected, PreparationReason.MALFORMED_QUALIFICATION, True)
        if provenance.validity is service.EvidenceValidity.INVALID:
            return _result(rejected, PreparationReason.UNQUALIFIED, True)
        if provenance.validity is service.EvidenceValidity.UNKNOWN:
            return _result(unresolved, PreparationReason.ASSOCIATION_UNKNOWN, True)
        done, snap = saved.completion.completed, saved.snapshot
        operation = service.OriginalOperation(done.envelope.permit_reference,
                                              service.OperationKind.CHECKPOINT_PUBLICATION)
        head = checkpoints.CommittedHead(done.event_sequence, done.event_digest, done.state_digest)
        candidate = checkpoints.construct_candidate(done.envelope, snap.completion, snap.events,
            snap.projection, snap.context, head, operation, keys=snap.keys, definite_expiry=snap.definite_expiry)
        # Association checks only: never call reconstructing validate_candidate.
        projected = _project(candidate)
        _need(type(candidate) is service.CheckpointCandidate)
        service.CheckpointCandidate.__post_init__(candidate)
        _need(candidate.envelope == done.envelope and candidate.operation == operation)
        _need((candidate.revision, candidate.fixed_utc_us, candidate.event_sequence,
               candidate.event_digest, candidate.state_digest) ==
              (done.envelope.predecessor.revision + 1, done.envelope.fixed_utc_us,
               done.event_sequence, done.event_digest, done.state_digest))
        payload = _PreparedCandidate(_detach(projected), saved, provenance)
        return _result(PreparationState.PREPARED, PreparationReason.PREPARED, True,
                       _detach(_project(payload)))
