"""Original acquisition and qualified observation only; no admission authority.

The application composition root selects TrustedAcquisitionAdapter outside the
request boundary. Construction is dependency injection, not authentication.
Its obtain operation implements the frozen CommandPermits.obtain contract; the
protected authority, not this process, enforces durable original single-flight
history. Repeated evaluations are not authorized retries. No client identity,
envelope, durable journal, provider selection or clock acquisition is made here.
"""
from dataclasses import dataclass, fields
from enum import StrEnum
from hashlib import sha256
from types import FunctionType, MethodType

from . import fixture_lease_permit_gate as g
from . import fixture_lease_service as s


class ExternalAvailabilityFailure(RuntimeError):
    """Adapter-classified external availability failure; carries no diagnostics.

    Unclassified RuntimeError and programming errors propagate. An adapter must
    not classify its own programming/invariant defects as external failures.
    """


class AcquisitionState(StrEnum):
    QUALIFIED = 'QUALIFIED_ORIGINAL_PERMIT_OBSERVATION'
    PRE_DISPATCH_FAILURE = 'PRE_DISPATCH_FAILURE'
    UNRESOLVED_HANDOFF = 'UNRESOLVED_HANDOFF'


class AcquisitionReason(StrEnum):
    QUALIFIED = 'QUALIFIED'
    MALFORMED = 'MALFORMED'
    PREREQUISITES = 'PREREQUISITES'
    AUTHORITY_UNAVAILABLE = 'AUTHORITY_UNAVAILABLE'
    UNQUALIFIED_PREREQUISITES = 'UNQUALIFIED_PREREQUISITES'
    MUTATED = 'MUTATED'
    ACQUISITION_UNAVAILABLE = 'ACQUISITION_UNAVAILABLE'
    PERMIT_MALFORMED = 'PERMIT_MALFORMED'
    QUALIFICATION_UNAVAILABLE = 'QUALIFICATION_UNAVAILABLE'
    UNQUALIFIED_PERMIT = 'UNQUALIFIED_PERMIT'


@dataclass(frozen=True, repr=False)
class AcquisitionInput:
    bundle: g.PrerequisiteBundle
    checked: g.GateResult

    def __post_init__(self):
        _children(self)
        s.require(type(self.bundle) is g.PrerequisiteBundle and type(self.checked) is g.GateResult)
        s.require(self.checked.state is g.GateState.CHECKED)
        s.require(g._snapshot(self.bundle) == g._snapshot(self.checked.bundle))


@dataclass(frozen=True, repr=False)
class PermitQualification:
    """Trusted qualifier response, never proof when supplied as request data.

    Qualification establishes original protected acquisition provenance,
    single-flight/current history, authority and fencing eligibility, exact
    opaque immutable evidence encoding and all attempt bindings. The time
    evidence must cover this actual observation, not merely an earlier check.
    No permit codec is introduced here: the external qualifier authenticates
    its evidence encoding. Locally, exact bytes and SHA256 are mandatory.
    """
    attempt: AcquisitionInput
    permit: s.CommandPermit
    exact_evidence: bytes
    time: g.TimeEvidence
    validity: s.EvidenceValidity
    reference: s.EvidenceReference

    def __post_init__(self):
        _children(self)
        s.require(type(self.attempt) is AcquisitionInput and type(self.permit) is s.CommandPermit)
        s.require(type(self.exact_evidence) is bytes and 0 < len(self.exact_evidence) <= g.c.MAX_ARTIFACT_BYTES)
        s.require(sha256(self.exact_evidence).digest() == self.permit.evidence.sha256)
        s.require(type(self.time) is g.TimeEvidence and type(self.validity) is s.EvidenceValidity)
        s.require(type(self.reference) is s.EvidenceReference)


@dataclass(frozen=True, repr=False)
class TrustedAcquisitionAdapter:
    """Composition authority, separate from all request-side evidence.

    verify_prerequisites(attempt) independently qualifies the complete bundle
    and checked predecessor provenance, returning frozen QualificationEvidence.
    obtain(context, activation) implements CommandPermits.obtain exactly once.
    qualify(attempt, permit) independently observes/qualifies that original
    attempt and returns PermitQualification. It never obtains another permit.
    Function/method restrictions are shape checks only, never name authority.
    A malicious composer is outside the untrusted request boundary. Production
    authentication, protected single-flight and wiring remain separately gated.
    """
    verify_prerequisites: object
    obtain: object
    qualify: object

    def __post_init__(self):
        s.require(type(self) is TrustedAcquisitionAdapter)
        for name in ('verify_prerequisites', 'obtain', 'qualify'):
            kind = type(object.__getattribute__(self, name))
            s.require(kind is FunctionType or kind is MethodType)


def _children(value):
    kind = type(value)
    s.require(any(kind is approved for approved in (AcquisitionInput, PermitQualification, s.CommandPermit)))
    for field in fields(kind): _validate(object.__getattribute__(value, field.name))


def _validate(value):
    """Exact classification precedes every instance traversal/validator call."""
    kind = type(value)
    if kind is g.GateResult:
        # GateResult is deliberately not part of the frozen generic allowlist.
        for name in ('bundle', 'qualification', 'time_evaluation'):
            g._revalidate(object.__getattribute__(value, name))
        s.require(type(object.__getattribute__(value, 'state')) is g.GateState)
        s.require(type(object.__getattribute__(value, 'reason')) is g.GateReason)
        g.GateResult.__post_init__(value)
    elif any(kind is approved for approved in (AcquisitionInput, PermitQualification, s.CommandPermit)):
        if kind is s.CommandPermit: _children(value)
        kind.__post_init__(value)
    else:
        g._revalidate(value)


def _projection(value):
    """Full exact graph projection; call only after closed validation."""
    kind = type(value)
    if kind is g.GateState or kind is g.GateReason: return kind, value
    if any(kind is approved for approved in (AcquisitionInput, PermitQualification, s.CommandPermit, g.GateResult)):
        return kind, tuple((f.name, _projection(object.__getattribute__(value, f.name))) for f in fields(kind))
    return g._snapshot(value)


def _copy_projection(projection):
    """Rebuild detached values from the validated immutable projection only.

    No deepcopy, pickle, user hooks, constructors or arbitrary object traversal.
    Callers cannot pass a projection into the public entry point as authority.
    """
    kind, data = projection
    if kind is type(None) or any(kind is t for t in (str, bytes, int, bool)):
        return data
    if kind is tuple: return tuple(_copy_projection(v) for v in data)
    # Enum projection contains the exact already-accepted singleton.
    if type(data) is kind: return data
    result = object.__new__(kind)
    for name, child in data: object.__setattr__(result, name, _copy_projection(child))
    return result


_REJECTIONS = (s.TimeRejected, g.p.ProtocolRejected, g.c.ContractRejected,
               AttributeError, UnicodeError, RecursionError)


def _unchanged(value, projection):
    try:
        _validate(value)
        return _projection(value) == projection
    except _REJECTIONS:
        return False


def _qualification_checks(q, attempt, permit):
    s.require(q.validity is s.EvidenceValidity.VALID)
    s.require(_projection(q.attempt) == _projection(attempt))
    s.require(_projection(q.permit) == _projection(permit))
    bundle = attempt.bundle
    s.require(permit.context == bundle.context and permit.activation == bundle.activation)
    # Current qualification cannot change the selected profile/domain, immutable
    # deadlines or applicability. No admission/envelope UTC is fixed here.
    old, now = bundle.time, q.time
    s.require(now.profile == old.profile)
    # This narrow increment propagates the already-qualified sample. Refresh
    # acquisition/consistency is upstream work; a new or rewritten sample is
    # not silently accepted as continuation of the old qualification.
    s.require(now.sample == old.sample)
    s.require((now.point.process_id, now.point.domain_id) == (old.point.process_id, old.point.domain_id))
    s.require(now.point.ticks_ns >= old.point.ticks_ns)
    s.require((now.freshness_applicability, now.freshness_deadline, now.lease_applicability, now.lease_deadline) ==
              (old.freshness_applicability, old.freshness_deadline, old.lease_applicability, old.lease_deadline))
    # Reuse the complete frozen timing/auth/approval/current-context predicates
    # against the supplied independently qualified observation time.
    current = object.__new__(g.PrerequisiteBundle)
    for f in fields(g.PrerequisiteBundle):
        object.__setattr__(current, f.name, now if f.name == 'time' else object.__getattribute__(bundle, f.name))
    reason, evaluated = g._check(current)
    s.require(reason is None)
    s.require(s.valid_from_satisfied(evaluated.interval, permit.valid_from_us))
    s.require(s.strict_bound(evaluated.interval, s.StrictDeadline(permit.valid_until_us)) is s.TimingBound.SATISFIED)


@dataclass(frozen=True, repr=False, init=False)
class AcquisitionResult:
    """Observation/handoff knowledge only; never a reusable capability."""
    state: AcquisitionState
    reason: AcquisitionReason
    attempt: AcquisitionInput | None
    qualification: PermitQualification | None
    acquisition_attempted: bool

    def __init__(self, *args, **kwargs):
        raise TypeError('Use acquisition through trusted composition')

    def __post_init__(self):
        s.require(type(self) is AcquisitionResult and type(self.state) is AcquisitionState)
        s.require(type(self.reason) is AcquisitionReason and type(self.acquisition_attempted) is bool)
        if self.attempt is not None:
            s.require(type(self.attempt) is AcquisitionInput)
            _validate(self.attempt)
        if self.state is AcquisitionState.QUALIFIED:
            s.require(self.reason is AcquisitionReason.QUALIFIED and self.acquisition_attempted)
            s.require(type(self.qualification) is PermitQualification and self.attempt is not None)
            _validate(self.qualification)
            _qualification_checks(self.qualification, self.attempt, self.qualification.permit)
        else:
            s.require(self.qualification is None and self.reason is not AcquisitionReason.QUALIFIED)
            s.require(self.acquisition_attempted is (self.state is AcquisitionState.UNRESOLVED_HANDOFF))
            s.require(not self.acquisition_attempted or self.attempt is not None)
            pre = (AcquisitionReason.MALFORMED, AcquisitionReason.PREREQUISITES,
                   AcquisitionReason.AUTHORITY_UNAVAILABLE, AcquisitionReason.UNQUALIFIED_PREREQUISITES)
            post = (AcquisitionReason.ACQUISITION_UNAVAILABLE, AcquisitionReason.PERMIT_MALFORMED,
                    AcquisitionReason.QUALIFICATION_UNAVAILABLE, AcquisitionReason.UNQUALIFIED_PERMIT)
            s.require(self.reason is AcquisitionReason.MUTATED or self.reason in (post if self.acquisition_attempted else pre))

    @property
    def begin_permitted(self): return False
    @property
    def sql_permitted(self): return False
    @property
    def transaction_owned(self): return False
    @property
    def writer_admission_permitted(self): return False
    @property
    def local_mutation_permitted(self): return False
    @property
    def local_commit_confirmed(self): return False
    @property
    def envelope_retained(self): return False
    @property
    def candidate_construction_permitted(self): return False
    @property
    def candidate_retention_permitted(self): return False
    @property
    def publication_permitted(self): return False
    @property
    def publication_retry_permitted(self): return False
    @property
    def completion_permitted(self): return False
    @property
    def ack_construction_permitted(self): return False
    @property
    def ack_delivery_permitted(self): return False
    @property
    def active_permitted(self): return False
    @property
    def fence_clearance_permitted(self): return False
    @property
    def acquisition_retry_permitted(self): return False
    @property
    def recovery_execution_permitted(self): return False


def _result(state, reason, attempt=None, qualification=None):
    result = object.__new__(AcquisitionResult)
    for name, value in (('state', state), ('reason', reason), ('attempt', attempt),
                        ('qualification', qualification), ('acquisition_attempted', state is not AcquisitionState.PRE_DISPATCH_FAILURE)):
        object.__setattr__(result, name, value)
    AcquisitionResult.__post_init__(result)
    return result


def acquire_original_permit(request, adapter=None):
    """Closed validation -> verification -> one obtain -> qualification -> stop.

    Only explicitly classified external failures are bounded. AssertionError,
    unexpected RuntimeError and trusted internal defects remain distinguishable.
    Once obtain is entered every unavailable/unqualified outcome is unresolved,
    including a rejecting default: no absence/non-dispatch inference is made.
    """
    pre, handoff = AcquisitionState.PRE_DISPATCH_FAILURE, AcquisitionState.UNRESOLVED_HANDOFF
    try:
        s.require(type(request) is AcquisitionInput)
        _validate(request)
    except _REJECTIONS:
        return _result(pre, AcquisitionReason.PREREQUISITES if type(request) is AcquisitionInput else AcquisitionReason.MALFORMED)
    projection = _projection(request)
    saved = _copy_projection(projection)
    _validate(saved)
    if type(adapter) is not TrustedAcquisitionAdapter:
        return _result(pre, AcquisitionReason.AUTHORITY_UNAVAILABLE, saved)
    try:
        TrustedAcquisitionAdapter.__post_init__(adapter)
    except (s.TimeRejected, AttributeError):
        return _result(pre, AcquisitionReason.AUTHORITY_UNAVAILABLE, saved)
    # Snapshot the trusted dependency's exact callbacks too; callbacks cannot
    # replace later stages by mutating the adapter during this evaluation.
    verify, obtain, qualify = adapter.verify_prerequisites, adapter.obtain, adapter.qualify
    try:
        verified = verify(request)
    except (s.CapabilityUnavailable, ExternalAvailabilityFailure):
        return _result(pre, AcquisitionReason.MUTATED if not _unchanged(request, projection)
                       else AcquisitionReason.AUTHORITY_UNAVAILABLE, saved)
    if not _unchanged(request, projection): return _result(pre, AcquisitionReason.MUTATED, saved)
    try:
        s.require(type(verified) is g.QualificationEvidence)
        g._revalidate(verified)
        s.require(verified.validity is s.EvidenceValidity.VALID)
        s.require(g._snapshot(verified.bundle) == g._snapshot(saved.bundle))
    except _REJECTIONS:
        return _result(pre, AcquisitionReason.UNQUALIFIED_PREREQUISITES, saved)
    try:
        permit = obtain(request.bundle.context, request.bundle.activation)
    except (s.CapabilityUnavailable, ExternalAvailabilityFailure):
        return _result(handoff, AcquisitionReason.MUTATED if not _unchanged(request, projection)
                       else AcquisitionReason.ACQUISITION_UNAVAILABLE, saved)
    if not _unchanged(request, projection): return _result(handoff, AcquisitionReason.MUTATED, saved)
    try:
        s.require(type(permit) is s.CommandPermit)
        _validate(permit)
        s.require(permit.context == saved.bundle.context and permit.activation == saved.bundle.activation)
    except _REJECTIONS:
        return _result(handoff, AcquisitionReason.PERMIT_MALFORMED, saved)
    permit_projection = _projection(permit)
    saved_permit = _copy_projection(permit_projection)
    try:
        qualified = qualify(request, permit)
    except (s.CapabilityUnavailable, ExternalAvailabilityFailure):
        mutated = not _unchanged(request, projection) or not _unchanged(permit, permit_projection)
        return _result(handoff, AcquisitionReason.MUTATED if mutated else AcquisitionReason.QUALIFICATION_UNAVAILABLE, saved)
    if not _unchanged(request, projection) or not _unchanged(permit, permit_projection):
        return _result(handoff, AcquisitionReason.MUTATED, saved)
    try:
        s.require(type(qualified) is PermitQualification)
        _validate(qualified)
        _qualification_checks(qualified, saved, saved_permit)
    except _REJECTIONS:
        return _result(handoff, AcquisitionReason.UNQUALIFIED_PERMIT, saved)
    # Detach all returned evidence from references retained by callbacks.
    copied = _copy_projection(_projection(qualified))
    return _result(AcquisitionState.QUALIFIED, AcquisitionReason.QUALIFIED, saved, copied)
