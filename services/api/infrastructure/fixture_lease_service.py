"""IL.2 capability boundaries and pure timing predicates; no operational permission.

Values are structural claims supplied by separately qualified adapters, not proof.
No default adapter establishes any external fact. No I/O, clocks or discovery here.
"""
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from hashlib import sha256
from typing import Protocol

from fixture_lease_contract import ArtifactBytes, Command, Operation, Phase


class CapabilityUnavailable(RuntimeError):
    """External fact unavailable; never authoritative absence or success."""


class TimeRejected(ValueError):
    """Invalid/uncertain evidence; diagnostics do not expose supplied values."""


def require(condition):
    if not condition:
        raise TimeRejected("TIME_UNCERTAIN")


def integer(value, lower=-(1 << 63), upper=(1 << 63) - 1):
    require(type(value) is int and lower <= value <= upper)


def identity(value):
    require(type(value) is str and 0 < len(value.encode('utf-8')) <= 255
            and bool(value.strip()))


@dataclass(frozen=True)
class EvidenceReference:
    """Reference only; construction verifies neither evidence nor approval."""
    identity: str
    sha256: bytes

    def __post_init__(self):
        identity(self.identity)
        require(type(self.sha256) is bytes and len(self.sha256) == 32)


@dataclass(frozen=True)
class CommandContext:
    command_id: str
    payload_sha256: bytes
    command: Command
    operation: Operation
    phase: Phase
    reservation_revision: int
    authorization: EvidenceReference

    def __post_init__(self):
        identity(self.command_id)
        require(type(self.payload_sha256) is bytes and len(self.payload_sha256) == 32)
        require(type(self.command) is Command and type(self.operation) is Operation
                and type(self.phase) is Phase)
        integer(self.reservation_revision, 0)
        require(type(self.authorization) is EvidenceReference)


@dataclass(frozen=True)
class AuthenticatedRequester:
    """Adapter-established claim; cannot authenticate its own construction."""
    principal: str
    evidence: EvidenceReference

    def __post_init__(self):
        identity(self.principal)
        require(type(self.evidence) is EvidenceReference)


@dataclass(frozen=True)
class VerifiedApproval:
    approver: str
    requester: str
    context: CommandContext
    artifact: ArtifactBytes
    evidence: EvidenceReference

    def __post_init__(self):
        identity(self.approver)
        identity(self.requester)
        require(self.approver != self.requester)
        require(type(self.context) is CommandContext and type(self.artifact) is ArtifactBytes
                and type(self.evidence) is EvidenceReference)


@dataclass(frozen=True)
class ActivationIdentity:
    register_id: str
    generation: int
    activation_id: str
    host_identity: str
    checkpoint: EvidenceReference

    def __post_init__(self):
        for value in (self.register_id, self.activation_id, self.host_identity):
            identity(value)
        integer(self.generation, 1)
        require(type(self.checkpoint) is EvidenceReference)


class AuthorityPresence(StrEnum):
    AUTHORITATIVE_ABSENT = 'AUTHORITATIVE_ABSENT'
    AUTHORITATIVE_PRESENT = 'AUTHORITATIVE_PRESENT'


@dataclass(frozen=True)
class ActivationObservation:
    """Absence requires positive external evidence, not lookup failure."""
    presence: AuthorityPresence
    evidence: EvidenceReference
    activation: ActivationIdentity | None

    def __post_init__(self):
        require(type(self.presence) is AuthorityPresence and type(self.evidence) is EvidenceReference)
        require((self.presence is AuthorityPresence.AUTHORITATIVE_ABSENT and self.activation is None)
                or (self.presence is AuthorityPresence.AUTHORITATIVE_PRESENT
                    and type(self.activation) is ActivationIdentity))


@dataclass(frozen=True)
class CommandPermit:
    context: CommandContext
    activation: ActivationIdentity
    valid_from_us: int
    valid_until_us: int
    evidence: EvidenceReference

    def __post_init__(self):
        require(type(self.context) is CommandContext and type(self.activation) is ActivationIdentity
                and type(self.evidence) is EvidenceReference)
        integer(self.valid_from_us)
        integer(self.valid_until_us)
        require(self.valid_from_us <= self.valid_until_us)


class RequesterAuthentication(Protocol):
    def authenticate(self, request: EvidenceReference) -> AuthenticatedRequester: ...


class ApprovalVerification(Protocol):
    def verify(self, requester: AuthenticatedRequester, context: CommandContext,
               artifact: ArtifactBytes) -> VerifiedApproval: ...


class ActivationAuthority(Protocol):
    def observe(self, register_id: str) -> ActivationObservation: ...


class CommandPermits(Protocol):
    def obtain(self, context: CommandContext, activation: ActivationIdentity) -> CommandPermit: ...
    def complete(self, permit: CommandPermit, checkpoint: EvidenceReference) -> EvidenceReference: ...
    def reconcile(self, context: CommandContext, evidence: EvidenceReference) -> EvidenceReference: ...


class ProtectedCheckpoints(Protocol):
    def read(self, activation: ActivationIdentity) -> EvidenceReference: ...
    def publish(self, permit: CommandPermit, predecessor: EvidenceReference,
                successor: EvidenceReference) -> EvidenceReference: ...


class TrustedTimeEvidence(Protocol):
    def qualify(self, raw: 'RawTimeEvidence', profile: 'QualifiedClockProfile') -> 'QualifiedSample': ...


class MonotonicMeasurement(Protocol):
    def measure(self) -> 'MonotonicPoint': ...


class RejectingCapabilities:
    """Implements all defaults by raising before any action; never a no-op success."""
    def authenticate(self, request): raise CapabilityUnavailable('AUTHENTICATION_UNAVAILABLE')
    def verify(self, requester, context, artifact): raise CapabilityUnavailable('APPROVAL_UNAVAILABLE')
    def observe(self, register_id): raise CapabilityUnavailable('ACTIVATION_UNAVAILABLE')
    def obtain(self, context, activation): raise CapabilityUnavailable('PERMIT_UNAVAILABLE')
    def complete(self, permit, checkpoint): raise CapabilityUnavailable('COMPLETION_UNAVAILABLE')
    def reconcile(self, context, evidence): raise CapabilityUnavailable('RECONCILIATION_UNAVAILABLE')
    def read(self, activation): raise CapabilityUnavailable('CHECKPOINT_UNAVAILABLE')
    def publish(self, permit, predecessor, successor): raise CapabilityUnavailable('CHECKPOINT_UNAVAILABLE')
    def qualify(self, raw, profile): raise CapabilityUnavailable('TRUSTED_TIME_UNAVAILABLE')
    def measure(self): raise CapabilityUnavailable('MONOTONIC_UNAVAILABLE')


@dataclass(frozen=True)
class UtcInterval:
    lower_us: int
    upper_us: int

    def __post_init__(self):
        integer(self.lower_us)
        integer(self.upper_us)
        require(self.lower_us <= self.upper_us)


@dataclass(frozen=True)
class MonotonicPoint:
    process_id: str
    domain_id: str
    ticks_ns: int

    def __post_init__(self):
        identity(self.process_id)
        identity(self.domain_id)
        integer(self.ticks_ns, 0)


@dataclass(frozen=True)
class RawTimeEvidence:
    source: str
    evidence: EvidenceReference

    def __post_init__(self):
        identity(self.source)
        require(type(self.evidence) is EvidenceReference)


@dataclass(frozen=True)
class QualifiedClockProfile:
    """Externally qualified limits, not a selected production profile.

    Error is supplied separately per decision; IL.2 does not invent a drift model.
    Qualification must account for every error component exactly once.
    """
    profile: EvidenceReference
    source: str
    qualification: EvidenceReference
    max_elapsed_ns: int
    max_sample_age_us: int
    max_command_uncertainty_us: int
    refresh_consistency_us: int

    def __post_init__(self):
        identity(self.source)
        require(type(self.profile) is EvidenceReference and type(self.qualification) is EvidenceReference)
        for value in (self.max_elapsed_ns, self.max_sample_age_us,
                      self.max_command_uncertainty_us, self.refresh_consistency_us):
            integer(value, 0)


@dataclass(frozen=True)
class QualifiedSample:
    sample: EvidenceReference
    source: str
    profile: EvidenceReference
    validation: EvidenceReference
    utc: UtcInterval
    anchor: MonotonicPoint

    def __post_init__(self):
        identity(self.source)
        require(all(type(x) is EvidenceReference for x in (self.sample, self.profile, self.validation)))
        require(type(self.utc) is UtcInterval and type(self.anchor) is MonotonicPoint)


@dataclass(frozen=True)
class QualifiedPropagationError:
    """External qualification of E(elapsed), explicitly bound to this evaluation.

    Nanoseconds permit exact sub-microsecond input. No constructor proves the bound.
    """
    sample: EvidenceReference
    profile: EvidenceReference
    elapsed_ns: int
    error_ns: int
    qualification: EvidenceReference

    def __post_init__(self):
        require(all(type(x) is EvidenceReference for x in (self.sample, self.profile, self.qualification)))
        integer(self.elapsed_ns, 0)
        integer(self.error_ns, 0)


@dataclass(frozen=True)
class TimeEvaluation:
    interval: UtcInterval
    command_uncertainty_us: int
    sample_age_upper_us: int

    def __post_init__(self):
        require(type(self.interval) is UtcInterval)
        integer(self.command_uncertainty_us, 0)
        integer(self.sample_age_upper_us, 0)
        require(self.command_uncertainty_us == self.interval.upper_us - self.interval.lower_us)


def floor_us(nanoseconds):
    return Fraction(nanoseconds, 1000).__floor__()


def ceil_us(nanoseconds):
    return Fraction(nanoseconds, 1000).__ceil__()


def evaluate_time(sample, profile, current, error):
    """Necessary qualified timing evaluation, NEVER complete operational permission."""
    require(type(sample) is QualifiedSample and type(profile) is QualifiedClockProfile
            and type(current) is MonotonicPoint and type(error) is QualifiedPropagationError)
    require(sample.profile == profile.profile and sample.source == profile.source)
    require((sample.anchor.process_id, sample.anchor.domain_id)
            == (current.process_id, current.domain_id))
    elapsed = current.ticks_ns - sample.anchor.ticks_ns
    integer(elapsed, 0)
    require(elapsed <= profile.max_elapsed_ns and error.elapsed_ns == elapsed)
    require(error.sample == sample.sample and error.profile == sample.profile)
    lower = sample.utc.lower_us + floor_us(elapsed - error.error_ns)
    upper = sample.utc.upper_us + ceil_us(elapsed + error.error_ns)
    interval = UtcInterval(lower, upper)
    width = upper - lower
    age = ceil_us(elapsed + error.error_ns)
    require(width <= profile.max_command_uncertainty_us and age <= profile.max_sample_age_us)
    return TimeEvaluation(interval, width, age)


class TimingBound(StrEnum):
    SATISFIED = 'SATISFIED'
    OUTSIDE = 'OUTSIDE'
    UNCERTAIN = 'UNCERTAIN'


@dataclass(frozen=True)
class InclusiveDeadline:
    utc_us: int
    def __post_init__(self): integer(self.utc_us)


@dataclass(frozen=True)
class StrictDeadline:
    utc_us: int
    def __post_init__(self): integer(self.utc_us)


def inclusive_bound(interval, deadline):
    require(type(interval) is UtcInterval and type(deadline) is InclusiveDeadline)
    if interval.upper_us <= deadline.utc_us: return TimingBound.SATISFIED
    if interval.lower_us > deadline.utc_us: return TimingBound.OUTSIDE
    return TimingBound.UNCERTAIN


def strict_bound(interval, deadline):
    require(type(interval) is UtcInterval and type(deadline) is StrictDeadline)
    if interval.upper_us < deadline.utc_us: return TimingBound.SATISFIED
    if interval.lower_us >= deadline.utc_us: return TimingBound.OUTSIDE
    return TimingBound.UNCERTAIN


def valid_from_satisfied(interval, valid_from_us):
    require(type(interval) is UtcInterval)
    integer(valid_from_us)
    return interval.lower_us >= valid_from_us


def refresh_consistent(old_sample, new_sample, profile, old_error):
    """Pure comparison; new evidence must be independently validated externally.

    Return consistency only, not recovery/permission. Never splice/narrow intervals.
    """
    require(type(old_sample) is QualifiedSample and type(new_sample) is QualifiedSample
            and type(profile) is QualifiedClockProfile and type(old_error) is QualifiedPropagationError)
    require(new_sample.sample != old_sample.sample)
    propagated = evaluate_time(old_sample, profile, new_sample.anchor, old_error)
    require(new_sample.profile == profile.profile and new_sample.source == profile.source)
    # Validate complete new sample and its width/age at its own capture independently.
    require(new_sample.utc.upper_us - new_sample.utc.lower_us <= profile.max_command_uncertainty_us)
    tolerance = profile.refresh_consistency_us
    gap = max(new_sample.utc.lower_us - propagated.interval.upper_us,
              propagated.interval.lower_us - new_sample.utc.upper_us, 0)
    return gap <= tolerance


# IL.5A: structural claims from independently qualified inputs; no I/O or issuer.
class ApprovalApplicability(StrEnum):
    REQUIRED = 'REQUIRED'
    NOT_APPLICABLE = 'NOT_APPLICABLE'
    UNKNOWN = 'UNKNOWN'


class AdmissionReason(StrEnum):
    UNAVAILABLE = 'UNAVAILABLE'
    COMMAND = 'COMMAND'
    ACTIVATION = 'ACTIVATION'
    PREDECESSOR = 'PREDECESSOR'
    REPRESENTATION = 'REPRESENTATION'
    APPROVAL = 'APPROVAL'
    TIME = 'TIME'
    COVERAGE = 'COVERAGE'
    UTC = 'UTC'
    CHECKER = 'CHECKER'


class AdmissionDisposition(StrEnum):
    ADMIT = 'ADMIT'
    REJECT = 'REJECT'


@dataclass(frozen=True)
class AdmissionDecision:
    disposition: AdmissionDisposition
    reason: AdmissionReason | None

    def __post_init__(self):
        require(type(self.disposition) is AdmissionDisposition)
        require((self.disposition is AdmissionDisposition.ADMIT and self.reason is None)
                or (self.disposition is AdmissionDisposition.REJECT and type(self.reason) is AdmissionReason))


def _digest(raw, digest):
    require(type(raw) is bytes and bool(raw))
    require(type(digest) is bytes and len(digest) == 32 and sha256(raw).digest() == digest)


@dataclass(frozen=True)
class ResolvedCheckpointEvidence:
    """Externally qualified predecessor facts; construction checks integrity, not authority."""
    reference: EvidenceReference
    exact_bytes: bytes
    activation: ActivationIdentity
    revision: int
    event_sequence: int
    event_digest: bytes
    state_digest: bytes
    representation: str
    representation_authority: EvidenceReference

    def __post_init__(self):
        require(type(self.reference) is EvidenceReference and type(self.activation) is ActivationIdentity)
        _digest(self.exact_bytes, self.reference.sha256)
        integer(self.revision, 0); integer(self.event_sequence, 0)
        require(all(type(x) is bytes and len(x) == 32 for x in (self.event_digest, self.state_digest)))
        identity(self.representation)
        require(type(self.representation_authority) is EvidenceReference)
        require(self.activation.checkpoint == self.reference)


@dataclass(frozen=True)
class RetainedTimeFixing:
    """Original qualified fixing chain, retained independently of current refresh."""
    envelope: EvidenceReference
    context: CommandContext
    activation: ActivationIdentity
    sample: QualifiedSample
    profile: QualifiedClockProfile
    point: MonotonicPoint
    propagation: QualifiedPropagationError

    def __post_init__(self):
        require(type(self.envelope) is EvidenceReference and type(self.context) is CommandContext
                and type(self.activation) is ActivationIdentity)
        require(type(self.sample) is QualifiedSample and type(self.profile) is QualifiedClockProfile
                and type(self.point) is MonotonicPoint and type(self.propagation) is QualifiedPropagationError)


@dataclass(frozen=True)
class RetainedAdmissionEnvelope:
    """Immutable externally retained evidence reference; no envelope wire codec here."""
    reference: EvidenceReference
    canonical_command_bytes: bytes
    context: CommandContext
    principal: str
    permit_reference: EvidenceReference
    activation: ActivationIdentity
    predecessor: ResolvedCheckpointEvidence
    approval_applicability: ApprovalApplicability
    approval: EvidenceReference | None
    fixed_utc_us: int
    fixing_interval: UtcInterval
    time_qualification: EvidenceReference
    fixing: RetainedTimeFixing | None = None

    def __post_init__(self):
        require(type(self.reference) is EvidenceReference and type(self.context) is CommandContext)
        _digest(self.canonical_command_bytes, self.context.payload_sha256)
        identity(self.principal)
        require(type(self.permit_reference) is EvidenceReference)
        require(type(self.activation) is ActivationIdentity and type(self.predecessor) is ResolvedCheckpointEvidence)
        require(type(self.approval_applicability) is ApprovalApplicability)
        require(self.approval is None or type(self.approval) is EvidenceReference)
        integer(self.fixed_utc_us)
        require(type(self.fixing_interval) is UtcInterval and type(self.time_qualification) is EvidenceReference)
        require(self.fixed_utc_us == self.fixing_interval.lower_us)
        require(self.fixing is None or type(self.fixing) is RetainedTimeFixing)


class TimingApplicability(StrEnum):
    REQUIRED = 'REQUIRED'
    NOT_APPLICABLE = 'NOT_APPLICABLE'
    UNKNOWN = 'UNKNOWN'


class EvidenceValidity(StrEnum):
    VALID = 'VALID'
    INVALID = 'INVALID'
    UNKNOWN = 'UNKNOWN'


@dataclass(frozen=True)
class AdmissionCoverage:
    """Already-qualified coverage of the actual admission point, not a new clock model."""
    qualification: EvidenceReference
    envelope: EvidenceReference
    context: CommandContext
    activation: ActivationIdentity
    point: MonotonicPoint
    interval: UtcInterval

    def __post_init__(self):
        require(type(self.qualification) is EvidenceReference and type(self.envelope) is EvidenceReference)
        require(type(self.context) is CommandContext and type(self.activation) is ActivationIdentity)
        require(type(self.point) is MonotonicPoint and type(self.interval) is UtcInterval)


@dataclass(frozen=True)
class AdmissionEvidence:
    envelope: RetainedAdmissionEnvelope
    permit: CommandPermit | None
    sample: QualifiedSample
    profile: QualifiedClockProfile
    current: MonotonicPoint
    propagation: QualifiedPropagationError
    admission_coverage: AdmissionCoverage | None
    authorization_deadline: InclusiveDeadline | None
    freshness_deadline: StrictDeadline | None
    permit_validity: EvidenceValidity
    approval_validity: EvidenceValidity
    authorization_timing: TimingApplicability
    freshness_timing: TimingApplicability
    fixing_to_refresh: QualifiedPropagationError | None = None

    def __post_init__(self):
        require(type(self.envelope) is RetainedAdmissionEnvelope)
        require(self.permit is None or type(self.permit) is CommandPermit)
        require(type(self.sample) is QualifiedSample and type(self.profile) is QualifiedClockProfile
                and type(self.current) is MonotonicPoint and type(self.propagation) is QualifiedPropagationError)
        require(self.admission_coverage is None or type(self.admission_coverage) is AdmissionCoverage)
        require(self.authorization_deadline is None or type(self.authorization_deadline) is InclusiveDeadline)
        require(self.freshness_deadline is None or type(self.freshness_deadline) is StrictDeadline)
        require(type(self.permit_validity) is EvidenceValidity and type(self.approval_validity) is EvidenceValidity)
        require(type(self.authorization_timing) is TimingApplicability
                and type(self.freshness_timing) is TimingApplicability)
        require(self.fixing_to_refresh is None or type(self.fixing_to_refresh) is QualifiedPropagationError)
        # NOT_APPLICABLE is separately qualified; None never means UNKNOWN.
        # Coverage is independently qualified for this exact envelope/context,
        # process/domain and actual admission point. A reference alone is NOT proof.


@dataclass(frozen=True)
class AdmissionFacts:
    canonical_command_bytes: bytes
    context: CommandContext
    principal: str
    register_id: str
    generation: int
    activation_id: str
    host_identity: str
    representation: str
    representation_authority: EvidenceReference
    event_sequence: int
    event_digest: bytes
    state_digest: bytes
    recovery_required: bool
    target_revision: int | None
    owned_keys: tuple[bytes, ...]
    retained_references: tuple[EvidenceReference, ...]
    approval_record_sha256: bytes
    last_valid_utc_us: int
    proposed_utc_us: int
    proposed_last_valid_utc_us: int

    def __post_init__(self):
        require(type(self.context) is CommandContext)
        _digest(self.canonical_command_bytes, self.context.payload_sha256)
        for x in (self.principal, self.register_id, self.activation_id, self.host_identity, self.representation): identity(x)
        integer(self.generation, 1); integer(self.event_sequence, 0)
        require(type(self.representation_authority) is EvidenceReference)
        require(all(type(x) is bytes and len(x) == 32 for x in (self.event_digest, self.state_digest)))
        require(type(self.recovery_required) is bool)
        if self.target_revision is not None: integer(self.target_revision, 0)
        require(type(self.owned_keys) is tuple and all(type(x) is bytes for x in self.owned_keys))
        require(self.owned_keys == tuple(sorted(set(self.owned_keys))))
        require(type(self.retained_references) is tuple and all(type(x) is EvidenceReference for x in self.retained_references))
        require(type(self.approval_record_sha256) is bytes and len(self.approval_record_sha256) == 32)
        integer(self.last_valid_utc_us)
        integer(self.proposed_utc_us); integer(self.proposed_last_valid_utc_us)


def validate_admission(evidence: AdmissionEvidence | None, facts: AdmissionFacts) -> AdmissionDecision:
    """Pure binding checks. Qualification/coverage must be established elsewhere.

    No constructor/checker manufactures authentication, permission or time proof.
    The supplied coverage qualification must cover the actual writer admission;
    IL.5A neither chooses a production coverage model nor acquires measurements.
    """
    def reject(reason): return AdmissionDecision(AdmissionDisposition.REJECT, reason)
    if type(evidence) is not AdmissionEvidence or type(facts) is not AdmissionFacts:
        return reject(AdmissionReason.UNAVAILABLE)
    envelope, permit = evidence.envelope, evidence.permit
    if permit is None or evidence.permit_validity is not EvidenceValidity.VALID:
        return reject(AdmissionReason.UNAVAILABLE)
    if (permit.evidence != envelope.permit_reference or envelope.context != facts.context or permit.context != facts.context
            or envelope.principal != facts.principal
            or envelope.canonical_command_bytes != facts.canonical_command_bytes):
        return reject(AdmissionReason.COMMAND)
    if ((facts.context.command is Command.ACQUIRE
         and (facts.target_revision is not None or facts.context.reservation_revision != 0))
            or (facts.context.command is not Command.ACQUIRE
                and facts.target_revision != facts.context.reservation_revision)):
        return reject(AdmissionReason.COMMAND)
    activation = envelope.activation
    if (permit.activation != activation or facts.recovery_required
            or (activation.register_id, activation.generation, activation.activation_id, activation.host_identity)
            != (facts.register_id, facts.generation, facts.activation_id, facts.host_identity)):
        return reject(AdmissionReason.ACTIVATION)
    predecessor = envelope.predecessor
    if (predecessor.activation != activation or activation.checkpoint != predecessor.reference
            or (predecessor.event_sequence, predecessor.event_digest, predecessor.state_digest)
            != (facts.event_sequence, facts.event_digest, facts.state_digest)
            or predecessor.revision == (1 << 63)-1):
        return reject(AdmissionReason.PREDECESSOR)
    if (facts.representation != 'JOUS_CORE1A_STATE_REPRESENTATION_2'
            or (facts.representation, facts.representation_authority)
            != (predecessor.representation, predecessor.representation_authority)):
        return reject(AdmissionReason.REPRESENTATION)
    required = facts.context.command in (Command.ACQUIRE, Command.ADVANCE, Command.RELEASE, Command.RECOVER)
    if (envelope.approval_applicability is ApprovalApplicability.UNKNOWN
            or required != (envelope.approval_applicability is ApprovalApplicability.REQUIRED)
            or (required and evidence.approval_validity is not EvidenceValidity.VALID)
            or (required and (envelope.approval is None or envelope.approval.sha256 != facts.approval_record_sha256))
            or (not required and envelope.approval is not None)):
        return reject(AdmissionReason.APPROVAL)
    for applicability, deadline in ((evidence.authorization_timing, evidence.authorization_deadline),
                                    (evidence.freshness_timing, evidence.freshness_deadline)):
        if (applicability is TimingApplicability.UNKNOWN
                or (applicability is TimingApplicability.REQUIRED and deadline is None)
                or (applicability is TimingApplicability.NOT_APPLICABLE and deadline is not None)):
            return reject(AdmissionReason.TIME)
    coverage = evidence.admission_coverage
    if (coverage is None or coverage.envelope != envelope.reference or coverage.context != facts.context
            or coverage.activation != activation or coverage.point != evidence.current):
        return reject(AdmissionReason.COVERAGE)
    try:
        fixing = envelope.fixing
        if (fixing is None or fixing.envelope != envelope.reference or fixing.context != facts.context
                or fixing.activation != activation or fixing.profile != evidence.profile
                or fixing.sample.validation != envelope.time_qualification):
            return reject(AdmissionReason.UTC)
        original = evaluate_time(fixing.sample, fixing.profile, fixing.point, fixing.propagation)
        if original.interval != envelope.fixing_interval or original.interval.lower_us != envelope.fixed_utc_us:
            return reject(AdmissionReason.UTC)
        if evidence.sample != fixing.sample:
            if (evidence.fixing_to_refresh is None or not refresh_consistent(
                    fixing.sample, evidence.sample, fixing.profile, evidence.fixing_to_refresh)):
                return reject(AdmissionReason.TIME)
        interval = evaluate_time(evidence.sample, evidence.profile, evidence.current, evidence.propagation).interval
        if coverage.interval != interval:
            return reject(AdmissionReason.COVERAGE)
        if (not valid_from_satisfied(interval, permit.valid_from_us)
                or strict_bound(interval, StrictDeadline(permit.valid_until_us)) is not TimingBound.SATISFIED):
            return reject(AdmissionReason.TIME)
        if interval.lower_us < facts.last_valid_utc_us:
            return reject(AdmissionReason.TIME)
        if (evidence.authorization_deadline is not None
                and inclusive_bound(interval, evidence.authorization_deadline) is not TimingBound.SATISFIED):
            return reject(AdmissionReason.TIME)
        if (evidence.freshness_deadline is not None
                and strict_bound(interval, evidence.freshness_deadline) is not TimingBound.SATISFIED):
            return reject(AdmissionReason.TIME)
    except TimeRejected:
        return reject(AdmissionReason.TIME)
    if (envelope.fixed_utc_us != facts.proposed_utc_us
            or facts.proposed_last_valid_utc_us != interval.lower_us):
        return reject(AdmissionReason.UTC)
    return AdmissionDecision(AdmissionDisposition.ADMIT, None)


class AdmissionChecker(Protocol):
    def __call__(self, evidence: AdmissionEvidence, facts: AdmissionFacts) -> AdmissionDecision: ...


class OperationKind(StrEnum):
    CHECKPOINT_PUBLICATION = 'CHECKPOINT_PUBLICATION'
    PERMIT_COMPLETION = 'PERMIT_COMPLETION'


@dataclass(frozen=True)
class OriginalOperation:
    """Original permit evidence plus closed kind, in its qualified authority namespace."""
    permit: EvidenceReference
    kind: OperationKind

    def __post_init__(self):
        require(type(self.permit) is EvidenceReference and type(self.kind) is OperationKind)


@dataclass(frozen=True)
class CheckpointCandidate:
    exact_bytes: bytes
    sha256: bytes
    envelope: RetainedAdmissionEnvelope
    operation: OriginalOperation
    revision: int
    fixed_utc_us: int
    event_sequence: int
    event_digest: bytes
    state_digest: bytes

    def __post_init__(self):
        _digest(self.exact_bytes, self.sha256)
        require(type(self.envelope) is RetainedAdmissionEnvelope and type(self.operation) is OriginalOperation)
        require(self.operation.kind is OperationKind.CHECKPOINT_PUBLICATION
                and self.operation.permit == self.envelope.permit_reference)
        integer(self.revision, 1); integer(self.fixed_utc_us); integer(self.event_sequence, 1)
        require(all(type(x) is bytes and len(x) == 32 for x in (self.event_digest, self.state_digest)))
        require(self.event_sequence > self.envelope.predecessor.event_sequence)
        require(self.envelope.activation == self.envelope.predecessor.activation)
        require(self.envelope.predecessor.representation == 'JOUS_CORE1A_STATE_REPRESENTATION_2')
        required = self.envelope.context.command in (Command.ACQUIRE, Command.ADVANCE, Command.RELEASE, Command.RECOVER)
        require((required and self.envelope.approval_applicability is ApprovalApplicability.REQUIRED
                 and self.envelope.approval is not None)
                or (not required and self.envelope.approval_applicability is ApprovalApplicability.NOT_APPLICABLE
                    and self.envelope.approval is None))
        require(self.revision == self.envelope.predecessor.revision + 1
                and self.fixed_utc_us == self.envelope.fixed_utc_us)
        # Candidate bytes are already canonical/qualified by the later codec gate;
        # this increment implements association integrity, not a checkpoint codec.


def verify_candidate_association(original, proposed):
    require(type(original) is CheckpointCandidate and type(proposed) is CheckpointCandidate)
    require(original == proposed)  # Exact bytes and all context, never hash-only.
    return original


class ExternalOutcome(StrEnum):
    CONFIRMED = 'CONFIRMED'
    DEFINITELY_REJECTED = 'DEFINITELY_REJECTED'
    UNKNOWN = 'UNKNOWN'


@dataclass(frozen=True)
class PublicationResult:
    """Already-qualified result bound to the exact original candidate/operation.

    Evidence resolves authenticated confirmation or definite nonoccurrence for
    this entire candidate context. A reference/constructor alone proves neither;
    no transport status conversion is performed here.
    """
    outcome: ExternalOutcome
    candidate: CheckpointCandidate
    evidence: EvidenceReference | None

    def __post_init__(self):
        require(type(self.outcome) is ExternalOutcome and type(self.candidate) is CheckpointCandidate)
        require(self.evidence is None or type(self.evidence) is EvidenceReference)
        require(self.outcome is ExternalOutcome.UNKNOWN or self.evidence is not None)


@dataclass(frozen=True)
class CompletionResult:
    """Already-qualified original completion evidence; UNKNOWN remains unresolved."""
    outcome: ExternalOutcome
    operation: OriginalOperation
    publication: PublicationResult
    evidence: EvidenceReference | None

    def __post_init__(self):
        require(type(self.outcome) is ExternalOutcome and type(self.operation) is OriginalOperation)
        require(type(self.publication) is PublicationResult
                and self.publication.outcome is ExternalOutcome.CONFIRMED)
        require(self.operation.kind is OperationKind.PERMIT_COMPLETION
                and self.operation.permit == self.publication.candidate.operation.permit)
        require(self.evidence is None or type(self.evidence) is EvidenceReference)
        require(self.outcome is ExternalOutcome.UNKNOWN or self.evidence is not None)


def verify_publication_result(candidate, result):
    require(type(result) is PublicationResult)
    verify_candidate_association(candidate, result.candidate)
    return result


def verify_completion_result(operation, publication, result):
    require(type(result) is CompletionResult and result.operation == operation
            and result.publication == publication)
    return result


class NormalCheckpointCapabilities(Protocol):
    """Companion contracts only; preserve the existing IL.2 protocols unchanged.

    Adapters must qualify results against exact inputs and use the binding helpers.
    Queries read the supplied original key without submission or new identities.
    Resolution includes the qualified activation namespace, not command_id alone.
    """
    def resolve_predecessor(self, activation: ActivationIdentity) -> ResolvedCheckpointEvidence: ...
    def resolve_envelope(self, context: CommandContext, principal: str, activation: ActivationIdentity) -> RetainedAdmissionEnvelope: ...
    def associate_candidate(self, candidate: CheckpointCandidate) -> CheckpointCandidate: ...
    def publish_candidate(self, candidate: CheckpointCandidate) -> PublicationResult: ...
    def query_publication(self, candidate: CheckpointCandidate) -> PublicationResult: ...
    def complete_original(self, operation: OriginalOperation, publication: PublicationResult) -> CompletionResult: ...
    def query_completion(self, operation: OriginalOperation, publication: PublicationResult) -> CompletionResult: ...


class RejectingNormalCapabilities:
    def __call__(self, evidence, facts):
        return AdmissionDecision(AdmissionDisposition.REJECT, AdmissionReason.UNAVAILABLE)
    def resolve_predecessor(self, activation): raise CapabilityUnavailable('CHECKPOINT_UNAVAILABLE')
    def resolve_envelope(self, context, principal, activation): raise CapabilityUnavailable('ENVELOPE_UNAVAILABLE')
    def associate_candidate(self, candidate): raise CapabilityUnavailable('CANDIDATE_UNAVAILABLE')
    def publish_candidate(self, candidate): raise CapabilityUnavailable('PUBLICATION_UNAVAILABLE')
    def query_publication(self, candidate):
        return PublicationResult(ExternalOutcome.UNKNOWN, candidate, None)
    def complete_original(self, operation, publication): raise CapabilityUnavailable('COMPLETION_UNAVAILABLE')
    def query_completion(self, operation, publication):
        return CompletionResult(ExternalOutcome.UNKNOWN, operation, publication, None)
