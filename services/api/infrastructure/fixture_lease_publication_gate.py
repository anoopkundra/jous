"""Pure initial-publication prerequisite knowledge, never reusable permission.

All qualification/provenance claims are supplied by separate qualified owners.
Constructors cannot establish local COMMIT, external retention or current authority.
No transaction, clock, capability or external effect is owned here. Later IL.7
resumption and operational fencing are separate from these in-memory values.
"""
from dataclasses import dataclass, fields
from enum import StrEnum

from . import fixture_lease_protocol as p
from . import fixture_lease_service as s
from . import fixture_lease_checkpoints as checkpoints
from . import fixture_lease_outcomes as outcomes


class GateState(StrEnum):
    SATISFIED = 'SATISFIED'
    FAIL_CLOSED = 'FAIL_CLOSED'


class GateReason(StrEnum):
    SATISFIED = 'SATISFIED'
    MISSING = 'MISSING'
    MALFORMED = 'MALFORMED'
    LOCAL_COMMIT = 'LOCAL_COMMIT'
    CANDIDATE = 'CANDIDATE'
    RETENTION = 'RETENTION'
    CURRENT_AUTHORITY = 'CURRENT_AUTHORITY'
    TIME = 'TIME'
    HISTORY = 'HISTORY'


class CurrentStatus(StrEnum):
    ELIGIBLE = 'ELIGIBLE'
    INELIGIBLE = 'INELIGIBLE'
    UNKNOWN = 'UNKNOWN'


class InitialOperationState(StrEnum):
    INITIAL = 'INITIAL'
    ATTEMPTED = 'ATTEMPTED'
    UNKNOWN = 'UNKNOWN'


@dataclass(frozen=True, repr=False)
class LocalCompletionEvidence:
    """Qualified COMMIT provenance and immutable retained reconstruction material.

    reference must resolve to this exact candidate/snapshot and COMMIT outcome.
    An ACK or matching snapshot alone is not a confirmed COMMIT assertion.
    """
    candidate: s.CheckpointCandidate
    state: outcomes.LocalCommitState
    qualification: s.EvidenceValidity
    reference: s.EvidenceReference
    completion: p.CommandRow
    events: tuple
    projection: p.StateProjection
    context: p.StateContext
    head: checkpoints.CommittedHead
    keys: tuple
    definite_expiry: bool

    def __post_init__(self):
        s.require(type(self.candidate) is s.CheckpointCandidate)
        s.require(type(self.state) is outcomes.LocalCommitState and type(self.qualification) is s.EvidenceValidity)
        s.require(type(self.reference) is s.EvidenceReference and type(self.completion) is p.CommandRow)
        s.require(type(self.events) is tuple and all(type(x) is p.EventPayload for x in self.events))
        s.require(type(self.projection) is p.StateProjection and type(self.context) is p.StateContext)
        s.require(all(type(x) is tuple for x in (self.projection.reservations,
            self.projection.claims, self.projection.commands, self.keys)))
        s.require(type(self.head) is checkpoints.CommittedHead and all(type(x) is bytes for x in self.keys))
        s.require(type(self.definite_expiry) is bool)
        _children(self)


@dataclass(frozen=True, repr=False)
class CandidateRetentionEvidence:
    """Separately qualified immutable external association, NOT publication.

    reference resolves retention of these exact bytes under this original key.
    Equality of candidate bytes does not qualify this independent assertion.
    """
    candidate: s.CheckpointCandidate
    operation: s.OriginalOperation
    qualification: s.EvidenceValidity
    reference: s.EvidenceReference

    def __post_init__(self):
        s.require(type(self.candidate) is s.CheckpointCandidate and type(self.operation) is s.OriginalOperation)
        s.require(type(self.qualification) is s.EvidenceValidity and type(self.reference) is s.EvidenceReference)
        _children(self)
        s.require(self.operation == self.candidate.operation)


@dataclass(frozen=True, repr=False)
class CurrentAuthorityEvidence:
    """Qualified current claims covering exactly the supplied evaluation interval.

    Each validity is independently supplied; no constructor authenticates claims.
    The qualification reference binds this complete operation/context/time bundle,
    including initial-operation status, host approval and fencing eligibility.
    """
    candidate: s.CheckpointCandidate
    operation: s.OriginalOperation
    permit: s.CommandPermit
    principal: str
    activation: s.ActivationIdentity
    host: str
    predecessor: s.ResolvedCheckpointEvidence
    representation: str
    representation_authority: s.EvidenceReference
    permit_validity: s.EvidenceValidity
    activation_validity: s.EvidenceValidity
    host_validity: s.EvidenceValidity
    fencing_validity: s.EvidenceValidity
    predecessor_validity: s.EvidenceValidity
    representation_validity: s.EvidenceValidity
    activation_status: CurrentStatus
    host_status: CurrentStatus
    fencing_status: CurrentStatus
    initial_operation: InitialOperationState
    qualification: s.EvidenceReference
    point: s.MonotonicPoint
    interval: s.UtcInterval

    def __post_init__(self):
        for value, cls in ((self.candidate, s.CheckpointCandidate), (self.operation, s.OriginalOperation),
            (self.permit, s.CommandPermit), (self.activation, s.ActivationIdentity),
            (self.predecessor, s.ResolvedCheckpointEvidence), (self.representation_authority, s.EvidenceReference),
            (self.qualification, s.EvidenceReference), (self.point, s.MonotonicPoint), (self.interval, s.UtcInterval)):
            s.require(type(value) is cls)
        for value in (self.principal, self.host, self.representation): s.identity(value)
        for value in (self.permit_validity, self.activation_validity, self.host_validity,
            self.fencing_validity, self.predecessor_validity, self.representation_validity):
            s.require(type(value) is s.EvidenceValidity)
        for value in (self.activation_status, self.host_status, self.fencing_status):
            s.require(type(value) is CurrentStatus)
        s.require(type(self.initial_operation) is InitialOperationState)
        _children(self)


@dataclass(frozen=True, repr=False)
class CurrentTimeEvidence:
    """Qualified publication-point coverage, not an acquired clock sample.

    qualification covers this candidate, point and evaluated interval. Deadlines
    and their applicability are qualified by that same supplied assertion.
    """
    candidate: s.CheckpointCandidate
    qualification: s.EvidenceValidity
    reference: s.EvidenceReference
    sample: s.QualifiedSample
    profile: s.QualifiedClockProfile
    point: s.MonotonicPoint
    propagation: s.QualifiedPropagationError
    covered_interval: s.UtcInterval
    fixing_to_refresh: s.QualifiedPropagationError | None
    authorization_timing: s.TimingApplicability
    authorization_deadline: s.InclusiveDeadline | None
    freshness_timing: s.TimingApplicability
    freshness_deadline: s.StrictDeadline | None

    def __post_init__(self):
        for value, cls in ((self.candidate, s.CheckpointCandidate), (self.reference, s.EvidenceReference),
            (self.sample, s.QualifiedSample), (self.profile, s.QualifiedClockProfile),
            (self.point, s.MonotonicPoint), (self.propagation, s.QualifiedPropagationError),
            (self.covered_interval, s.UtcInterval)):
            s.require(type(value) is cls)
        s.require(type(self.qualification) is s.EvidenceValidity)
        s.require(self.fixing_to_refresh is None or type(self.fixing_to_refresh) is s.QualifiedPropagationError)
        for applicability, deadline, cls in ((self.authorization_timing, self.authorization_deadline, s.InclusiveDeadline),
            (self.freshness_timing, self.freshness_deadline, s.StrictDeadline)):
            s.require(type(applicability) is s.TimingApplicability)
            s.require(deadline is None or type(deadline) is cls)
            s.require((applicability is s.TimingApplicability.REQUIRED and deadline is not None)
                or (applicability is not s.TimingApplicability.REQUIRED and deadline is None))
        _children(self)


@dataclass(frozen=True, repr=False)
class GateInputs:
    candidate: s.CheckpointCandidate
    local: LocalCompletionEvidence | None
    retention: CandidateRetentionEvidence | None
    authority: CurrentAuthorityEvidence | None
    time: CurrentTimeEvidence | None
    prior: outcomes.Disposition | None

    def __post_init__(self):
        s.require(type(self.candidate) is s.CheckpointCandidate)
        for value, cls in ((self.local, LocalCompletionEvidence), (self.retention, CandidateRetentionEvidence),
            (self.authority, CurrentAuthorityEvidence), (self.time, CurrentTimeEvidence),
            (self.prior, outcomes.Disposition)):
            s.require(value is None or type(value) is cls)
        _children(self)


def _dataclass_type(value):
    """Concrete identity only: no instance or foreign metaclass dispatch.

    type(value) bypasses instance __class__/attribute hooks. Identity comparisons
    also avoid equality/hash hooks on foreign classes. Only then may we inspect.
    """
    kind = type(value)
    allowed = (LocalCompletionEvidence, CandidateRetentionEvidence, CurrentAuthorityEvidence,
        CurrentTimeEvidence, GateInputs, s.EvidenceReference, s.CommandContext,
        s.CommandPermit, s.ActivationIdentity, s.ResolvedCheckpointEvidence,
        s.RetainedAdmissionEnvelope, s.RetainedTimeFixing, s.CheckpointCandidate,
        s.OriginalOperation, s.PublicationResult, s.CompletionResult, s.QualifiedSample,
        s.QualifiedClockProfile, s.MonotonicPoint, s.QualifiedPropagationError,
        s.UtcInterval, s.InclusiveDeadline, s.StrictDeadline, p.CommandRow,
        p.EventPayload, p.StateProjection, p.StateContext, p.MetadataRow,
        p.ReservationRow, p.ClaimRow, checkpoints.CommittedHead,
        outcomes.Disposition, outcomes.RecoveryHandoff)
    s.require(any(kind is approved for approved in allowed))
    return kind


def _children(value):
    kind = _dataclass_type(value)
    # Discover fields on the approved concrete class, never a foreign instance.
    for field in fields(kind): _revalidate(getattr(value, field.name))


def _revalidate(value):
    """Recheck exact frozen types before traversal or validator dispatch.

    Frozen protocol rows have no constructor validator; IL.5B reconstruction
    validates their full canonical semantics instead. Tuples are repeatable input.
    """
    kind = type(value)
    if value is None or any(kind is approved for approved in (str, bytes, int, bool)): return
    enums = (GateState, GateReason, CurrentStatus, InitialOperationState,
        s.Command, s.Operation, s.Phase, s.EvidenceValidity, s.TimingApplicability,
        s.ApprovalApplicability, s.OperationKind, s.ExternalOutcome,
        p.ExecutionState, p.QuarantineReason, p.EventType, p.OutcomeCode,
        p.contract.LeaseStatus, p.contract.ArtifactType,
        outcomes.LocalCommitState, outcomes.Stage, outcomes.RequiredGate, outcomes.Reason)
    if any(kind is approved for approved in enums): return
    if kind is tuple:
        for item in value: _revalidate(item)
        return
    kind = _dataclass_type(value)
    validator = getattr(kind, '__post_init__', None)
    # Our constructors recurse themselves; avoid revisiting each supplied
    # snapshot subtree twice at every level. Frozen lower-layer constructors
    # are shallow, so their children still need independent revalidation.
    if kind.__module__ != __name__: _children(value)
    if validator is not None: validator(value)


def _time_valid(candidate, time, authority):
    envelope = candidate.envelope
    fixing = envelope.fixing
    s.require(fixing is not None and fixing.envelope == envelope.reference
        and fixing.context == envelope.context and fixing.activation == envelope.activation
        and fixing.sample.validation == envelope.time_qualification and fixing.profile == time.profile)
    original = s.evaluate_time(fixing.sample, fixing.profile, fixing.point, fixing.propagation).interval
    s.require(original == envelope.fixing_interval and original.lower_us == candidate.fixed_utc_us)
    if time.sample != fixing.sample:
        s.require(time.fixing_to_refresh is not None and s.refresh_consistent(
            fixing.sample, time.sample, time.profile, time.fixing_to_refresh))
    interval = s.evaluate_time(time.sample, time.profile, time.point, time.propagation).interval
    s.require(time.qualification is s.EvidenceValidity.VALID and time.covered_interval == interval)
    s.require(authority.point == time.point and authority.interval == interval)
    s.require(interval.lower_us >= candidate.fixed_utc_us)
    s.require(s.valid_from_satisfied(interval, authority.permit.valid_from_us))
    s.require(s.strict_bound(interval, s.StrictDeadline(authority.permit.valid_until_us)) is s.TimingBound.SATISFIED)
    for applicability, deadline, predicate in ((time.authorization_timing, time.authorization_deadline, s.inclusive_bound),
        (time.freshness_timing, time.freshness_deadline, s.strict_bound)):
        s.require(applicability is not s.TimingApplicability.UNKNOWN)
        if deadline is not None: s.require(predicate(interval, deadline) is s.TimingBound.SATISFIED)


def _evaluate(inputs):
    if inputs is None: return GateReason.MISSING
    try:
        s.require(type(inputs) is GateInputs)
        _revalidate(inputs)
    except (ValueError, TypeError, AttributeError, RecursionError):
        return GateReason.MALFORMED
    candidate = inputs.candidate
    local, retention, authority, time = inputs.local, inputs.retention, inputs.authority, inputs.time
    if local is None or local.state is not outcomes.LocalCommitState.CONFIRMED or local.qualification is not s.EvidenceValidity.VALID:
        return GateReason.LOCAL_COMMIT
    try:
        s.verify_candidate_association(candidate, local.candidate)
        checkpoints.validate_candidate(candidate, candidate.envelope, local.completion, local.events,
            local.projection, local.context, local.head, candidate.operation, keys=local.keys,
            definite_expiry=local.definite_expiry)
    except (ValueError, TypeError, AttributeError): return GateReason.CANDIDATE
    if inputs.prior is not None:
        # Revalidation above preserves IL.5C knowledge. Even exact same-lineage
        # confirmation/history means this is no longer an initial progression.
        try: s.verify_candidate_association(candidate, inputs.prior.candidate)
        except (ValueError, TypeError, AttributeError): return GateReason.HISTORY
        return GateReason.HISTORY
    if retention is None or retention.qualification is not s.EvidenceValidity.VALID:
        return GateReason.RETENTION
    try:
        s.verify_candidate_association(candidate, retention.candidate)
        s.require(retention.operation == candidate.operation)
    except (ValueError, TypeError, AttributeError): return GateReason.RETENTION
    if authority is None: return GateReason.CURRENT_AUTHORITY
    try:
        s.verify_candidate_association(candidate, authority.candidate)
        env = candidate.envelope
        s.require(authority.operation == candidate.operation and authority.permit.evidence == candidate.operation.permit
            and authority.permit.context == env.context and authority.principal == env.principal
            and authority.permit.activation == env.activation and authority.activation == env.activation
            and authority.host == env.activation.host_identity and authority.predecessor == env.predecessor
            and authority.representation == env.predecessor.representation
            and authority.representation_authority == env.predecessor.representation_authority)
        s.require(all(x is s.EvidenceValidity.VALID for x in (authority.permit_validity, authority.activation_validity,
            authority.host_validity, authority.fencing_validity, authority.predecessor_validity, authority.representation_validity)))
        s.require(all(x is CurrentStatus.ELIGIBLE for x in
            (authority.activation_status, authority.host_status, authority.fencing_status)))
        s.require(authority.initial_operation is InitialOperationState.INITIAL)
    except (ValueError, TypeError, AttributeError): return GateReason.CURRENT_AUTHORITY
    if time is None: return GateReason.TIME
    try:
        s.verify_candidate_association(candidate, time.candidate)
        _time_valid(candidate, time, authority)
    except (ValueError, TypeError, AttributeError): return GateReason.TIME
    return GateReason.SATISFIED


@dataclass(frozen=True, repr=False)
class GateResult:
    """In-memory prerequisite knowledge only; neither retention nor permission.

    SATISFIED applies only to this supplied evaluation, never future reuse.
    FAIL_CLOSED describes a required handoff; it does not execute any fence.
    """
    inputs: GateInputs | None
    state: GateState
    reason: GateReason

    def __post_init__(self):
        s.require(type(self.state) is GateState and type(self.reason) is GateReason)
        s.require(self.inputs is None or type(self.inputs) is GateInputs)
        # Malformed graphs are discarded at the public boundary. This finite
        # absence marker carries no payload or affirmative knowledge.
        if self.inputs is None and self.reason is GateReason.MALFORMED:
            s.require(self.state is GateState.FAIL_CLOSED)
            return
        reason = _evaluate(self.inputs)
        s.require(reason is not GateReason.MALFORMED)
        s.require(self.reason is reason and (self.state is GateState.SATISFIED) == (reason is GateReason.SATISFIED))

    @property
    def publication_permitted(self): return False
    @property
    def completion_permitted(self): return False
    @property
    def ack_delivery_permitted(self): return False
    @property
    def runtime_active_permitted(self): return False
    @property
    def retry_permitted(self): return False
    @property
    def fence_clearance_permitted(self): return False


def evaluate_publication_gate(inputs: GateInputs | None) -> GateResult:
    """Classify supplied prerequisites; no capabilities or operational effects."""
    reason = _evaluate(inputs)
    if reason is GateReason.MALFORMED:
        return GateResult(None, GateState.FAIL_CLOSED, reason)
    return GateResult(inputs, GateState.SATISFIED if reason is GateReason.SATISFIED else GateState.FAIL_CLOSED, reason)
