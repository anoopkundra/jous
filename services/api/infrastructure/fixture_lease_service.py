"""IL.2 capability boundaries and pure timing predicates; no operational permission.

Values are structural claims supplied by separately qualified adapters, not proof.
No default adapter establishes any external fact. No I/O, clocks or discovery here.
"""
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
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
