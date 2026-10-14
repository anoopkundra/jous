"""Read-only pre-permit prerequisite knowledge, never an acquisition capability.

Request values are structural claims. A separately trusted composition root owns
the qualification adapter; it cannot be selected inside a request. No constructor,
VALID label, matching hash or checked-state label authenticates those claims.
The adapter must independently verify the complete exact bundle, including the
provenance/current applicability of the frozen predecessor result. Production
adapter qualification/wiring is outside this candidate. No clock is acquired and
no fixed admission/envelope UTC, operation identity or durable evidence is issued.
"""
from dataclasses import dataclass, fields
from enum import StrEnum
from hashlib import sha256
from types import FunctionType, MethodType

from . import fixture_lease_service as s
from . import fixture_lease_protocol as p
from . import fixture_lease_contract as c
from . import fixture_lease_predecessor_resolution as pr


class CommandHistory(StrEnum):
    NEW = 'NEW'
    EXACT_REPLAY = 'EXACT_REPLAY'
    MISMATCH = 'MISMATCH'
    UNKNOWN = 'UNKNOWN'


class GapKnowledge(StrEnum):
    CLEAR = 'CLEAR'
    UNRESOLVED = 'UNRESOLVED'
    UNKNOWN = 'UNKNOWN'


class GateState(StrEnum):
    CHECKED = 'CHECKED_PREREQUISITE_KNOWLEDGE'
    FAIL_CLOSED = 'FAIL_CLOSED'
    HANDOFF = 'HANDOFF'


class GateReason(StrEnum):
    CHECKED = 'CHECKED'
    MALFORMED = 'MALFORMED'
    COMMAND = 'COMMAND'
    REQUESTER = 'REQUESTER'
    AUTHORIZATION = 'AUTHORIZATION'
    PREDECESSOR = 'PREDECESSOR'
    APPROVAL = 'APPROVAL'
    TIME = 'TIME'
    CURRENT_CONTEXT = 'CURRENT_CONTEXT'
    REPLAY = 'REPLAY'
    HISTORY = 'HISTORY'
    UNRESOLVED = 'UNRESOLVED'
    UNAVAILABLE = 'UNAVAILABLE'
    UNQUALIFIED = 'UNQUALIFIED'
    QUALIFICATION_BINDING = 'QUALIFICATION_BINDING'


@dataclass(frozen=True, repr=False)
class AuthorizationEvidence:
    """Claimed exact authorization scope/validity, not operator authentication."""
    context: s.CommandContext
    principal: str
    activation: s.ActivationIdentity
    reference: s.EvidenceReference
    validity: s.EvidenceValidity
    valid_from_us: int
    deadline: s.InclusiveDeadline

    def __post_init__(self):
        _children(self)
        s.require(type(self.context) is s.CommandContext and type(self.activation) is s.ActivationIdentity)
        s.identity(self.principal)
        s.require(type(self.reference) is s.EvidenceReference and type(self.validity) is s.EvidenceValidity)
        s.integer(self.valid_from_us)
        s.require(type(self.deadline) is s.InclusiveDeadline and self.valid_from_us <= self.deadline.utc_us)


@dataclass(frozen=True, repr=False)
class ApprovalEvidence:
    """Existing transition approval plus supplied current applicability facts.

    NOT_APPLICABLE describes only the additional independent transition approval;
    the trusted verifier must still qualify artifact/root approval integrity.
    """
    applicability: s.ApprovalApplicability
    verified: s.VerifiedApproval | None
    reference: s.EvidenceReference | None
    validity: s.EvidenceValidity
    valid_from_us: int | None
    deadline: s.InclusiveDeadline | None

    def __post_init__(self):
        _children(self)
        s.require(type(self.applicability) is s.ApprovalApplicability and type(self.validity) is s.EvidenceValidity)
        s.require(self.verified is None or type(self.verified) is s.VerifiedApproval)
        s.require(self.reference is None or type(self.reference) is s.EvidenceReference)
        if self.valid_from_us is not None: s.integer(self.valid_from_us)
        s.require(self.deadline is None or type(self.deadline) is s.InclusiveDeadline)


@dataclass(frozen=True, repr=False)
class TimeEvidence:
    sample: s.QualifiedSample
    profile: s.QualifiedClockProfile
    point: s.MonotonicPoint
    propagation: s.QualifiedPropagationError
    freshness_applicability: s.TimingApplicability
    freshness_deadline: s.StrictDeadline | None
    lease_applicability: s.TimingApplicability
    lease_deadline: s.StrictDeadline | None

    def __post_init__(self):
        _children(self)
        s.require(type(self.sample) is s.QualifiedSample and type(self.profile) is s.QualifiedClockProfile)
        s.require(type(self.point) is s.MonotonicPoint and type(self.propagation) is s.QualifiedPropagationError)
        for applicability, deadline in ((self.freshness_applicability, self.freshness_deadline),
                                        (self.lease_applicability, self.lease_deadline)):
            s.require(type(applicability) is s.TimingApplicability)
            s.require(deadline is None or type(deadline) is s.StrictDeadline)


@dataclass(frozen=True, repr=False)
class HistoryEvidence:
    """Supplied read-only history/current-context facts; CLEAR is not proof."""
    context: s.CommandContext
    activation: s.ActivationIdentity
    reference: s.EvidenceReference
    command: CommandHistory
    acquisition: GapKnowledge
    publication: GapKnowledge
    completion: GapKnowledge
    activation_status: pr.CurrentStatus
    host_status: pr.HostStatus
    fencing_status: pr.FencingStatus

    def __post_init__(self):
        _children(self)
        s.require(type(self.context) is s.CommandContext and type(self.activation) is s.ActivationIdentity)
        s.require(type(self.reference) is s.EvidenceReference and type(self.command) is CommandHistory)
        s.require(all(type(v) is GapKnowledge for v in (self.acquisition, self.publication, self.completion)))
        s.require(type(self.activation_status) is pr.CurrentStatus and type(self.host_status) is pr.HostStatus
                  and type(self.fencing_status) is pr.FencingStatus)


@dataclass(frozen=True, repr=False)
class PrerequisiteBundle:
    canonical_command: bytes
    command: p.CommandPayload
    context: s.CommandContext
    requester: s.AuthenticatedRequester
    authorization: AuthorizationEvidence
    predecessor: pr.ResolutionResult
    activation: s.ActivationIdentity
    approved_host: str
    approval: ApprovalEvidence
    time: TimeEvidence
    history: HistoryEvidence

    def __post_init__(self):
        _children(self)
        s.require(type(self.canonical_command) is bytes and type(self.command) is p.CommandPayload)
        s.require(type(self.context) is s.CommandContext and type(self.requester) is s.AuthenticatedRequester)
        s.require(type(self.authorization) is AuthorizationEvidence and type(self.predecessor) is pr.ResolutionResult)
        s.require(type(self.activation) is s.ActivationIdentity and type(self.approval) is ApprovalEvidence)
        s.require(type(self.time) is TimeEvidence and type(self.history) is HistoryEvidence)
        s.identity(self.approved_host)


@dataclass(frozen=True, repr=False)
class QualificationEvidence:
    """Read-verifier response, not proof when provided as a request value.

    Accepted only as the result of the independently composed verifier invocation.
    Exact bundle equality includes command/predecessor bytes, not merely digests.
    """
    bundle: PrerequisiteBundle
    validity: s.EvidenceValidity
    reference: s.EvidenceReference

    def __post_init__(self):
        _children(self)
        s.require(type(self.bundle) is PrerequisiteBundle and type(self.validity) is s.EvidenceValidity
                  and type(self.reference) is s.EvidenceReference)


@dataclass(frozen=True, repr=False)
class TrustedPrerequisiteVerifier:
    """Trusted composition dependency; request callers cannot select this seam.

    The composer supplies read-only qualification code, never a request callback.
    Exact function/method checks enforce shape only, not provider authentication.
    No function-name rule. A compromised composition root is outside this module's
    input boundary, as with the frozen predecessor capability adapter.
    """
    verify: object

    def __post_init__(self):
        s.require(type(self) is TrustedPrerequisiteVerifier)
        s.require(type(self.verify) is FunctionType or type(self.verify) is MethodType)


def _kind(value):
    kind = type(value)
    own = (AuthorizationEvidence, ApprovalEvidence, TimeEvidence, HistoryEvidence,
           PrerequisiteBundle, QualificationEvidence)
    frozen = (s.CommandContext, s.AuthenticatedRequester, s.VerifiedApproval,
        s.ActivationIdentity, s.EvidenceReference, s.ResolvedCheckpointEvidence,
        s.QualifiedSample, s.QualifiedClockProfile, s.MonotonicPoint,
        s.QualifiedPropagationError, s.UtcInterval, s.InclusiveDeadline, s.StrictDeadline, s.TimeEvaluation,
        c.ArtifactBytes, p.CommandPayload, p.Parameters, p.Reference,
        pr.ResolutionResult, pr.QualifiedCurrentContext, pr.CurrentBinding,
        pr.ContextQualification, pr.ResolutionObservation, pr.ResolutionQualification)
    s.require(any(kind is approved for approved in own + frozen))
    return kind


def _children(value):
    kind = _kind(value)
    for field in fields(kind): _revalidate(getattr(value, field.name))


def _revalidate(value):
    """Closed exact types before fields, traversal, equality or validators."""
    kind = type(value)
    if value is None: return
    if kind is bytes:
        s.require(len(value) <= max(c.MAX_ARTIFACT_BYTES, len(p.PREFIX) + 6 + 18 * (4 + p.MAX_FIELD)))
        return
    if kind is str:
        s.require(len(value.encode('utf-8')) <= p.MAX_FIELD)
        return
    if kind is int or kind is bool: return  # Integer validators still reject bool.
    if kind is tuple:
        # Each v1 reference has a fixed header, three lengths, two nonempty
        # textual fields and a 32-byte digest; derive a loose collection bound.
        s.require(len(value) <= p.MAX_FIELD // (len(p.PREFIX) + 6 + 12 + 2 + 32))
        for item in value: _revalidate(item)
        return
    enums = (CommandHistory, GapKnowledge, s.ApprovalApplicability, s.EvidenceValidity,
        s.TimingApplicability, c.Command, c.Operation, c.Phase, c.ArtifactType,
        p.ExecutionState, p.QuarantineReason, pr.PredecessorProfile, pr.CurrentStatus,
        pr.HostStatus, pr.FencingStatus, pr.ResolutionState, pr.ResolutionReason)
    if any(kind is approved for approved in enums): return
    kind = _kind(value)
    _children(value)
    if kind is pr.ResolutionResult: return  # Semantic validation is step 5 below.
    if kind is s.ResolvedCheckpointEvidence:
        s.require(len(value.exact_bytes) <= len(p.PREFIX) + 6 + 11 * (4 + p.MAX_FIELD))
    if any(kind is approved for approved in (p.CommandPayload, p.Parameters, p.Reference)):
        p.encode_record(value)
    else:
        kind.__post_init__(value)


def _check(bundle):
    """Pure prerequisite coherence; never external qualification."""
    try:
        s.require(type(bundle) is PrerequisiteBundle)
        _revalidate(bundle)
    except (s.TimeRejected, p.ProtocolRejected, c.ContractRejected, UnicodeError, AttributeError, RecursionError):
        return GateReason.MALFORMED, None
    command, context = bundle.command, bundle.context
    try:
        decoded = p.decode_record(bundle.canonical_command, p.CommandPayload)
        s.require(p.command_bytes(command) == bundle.canonical_command and decoded == command)
        expected = s.CommandContext(command.command_id, sha256(bundle.canonical_command).digest(),
            command.command_kind, command.operation, command.phase, command.expected_revision,
            s.EvidenceReference(command.authorization_reference.artifact_id,
                                command.authorization_reference.artifact_sha256))
        s.require(context == expected)
    except (s.TimeRejected, p.ProtocolRejected): return GateReason.COMMAND, None
    if bundle.requester.principal != command.authenticated_principal:
        return GateReason.REQUESTER, None
    authorization = bundle.authorization
    if (authorization.context != context or authorization.principal != bundle.requester.principal
            or authorization.activation != bundle.activation or authorization.reference != context.authorization
            or authorization.validity is not s.EvidenceValidity.VALID):
        return GateReason.AUTHORIZATION, None
    predecessor = bundle.predecessor
    try:
        pr.ResolutionResult.__post_init__(predecessor)
        s.require(predecessor.state is pr.ResolutionState.CHECKED and predecessor.read_attempted)
        current = predecessor.context.requested
        s.require(current.activation == bundle.activation and current.approved_host == bundle.approved_host)
        s.require((command.register_id, command.issuer_generation, command.activation_id) ==
                  (bundle.activation.register_id, bundle.activation.generation, bundle.activation.activation_id))
        s.require(bundle.approved_host == bundle.activation.host_identity)
    except (s.TimeRejected, p.ProtocolRejected, AttributeError): return GateReason.PREDECESSOR, None
    approval = bundle.approval
    required = command.command_kind not in (c.Command.RECORD_EXECUTION, c.Command.QUARANTINE)
    if (approval.validity is not s.EvidenceValidity.VALID
            or approval.applicability is s.ApprovalApplicability.UNKNOWN
            or required != (approval.applicability is s.ApprovalApplicability.REQUIRED)):
        return GateReason.APPROVAL, None
    if required:
        verified = approval.verified
        if verified is None or approval.reference is None or approval.valid_from_us is None or approval.deadline is None:
            return GateReason.APPROVAL, None
        approval_target = (command.binding_reference if command.command_kind in (c.Command.ACQUIRE, c.Command.ADVANCE)
                           else command.parameters.primary_evidence_reference)
        if (verified.context != context or verified.requester != bundle.requester.principal
                or verified.evidence != approval.reference or verified.evidence.sha256 != command.approval_record_hash
                or verified.artifact.artifact_type != approval_target.artifact_type
                or verified.artifact.evidence_sha256 != approval_target.artifact_sha256):
            return GateReason.APPROVAL, None
    elif any(v is not None for v in (approval.verified, approval.reference, approval.valid_from_us, approval.deadline)):
        return GateReason.APPROVAL, None
    time = bundle.time
    try:
        evaluated = s.evaluate_time(time.sample, time.profile, time.point, time.propagation)
        interval = evaluated.interval
        s.require(s.valid_from_satisfied(interval, authorization.valid_from_us))
        s.require(s.inclusive_bound(interval, authorization.deadline) is s.TimingBound.SATISFIED)
        if required:
            s.require(s.valid_from_satisfied(interval, approval.valid_from_us))
            s.require(s.inclusive_bound(interval, approval.deadline) is s.TimingBound.SATISFIED)
        for applicability, deadline in ((time.freshness_applicability, time.freshness_deadline),
                                        (time.lease_applicability, time.lease_deadline)):
            s.require(applicability is not s.TimingApplicability.UNKNOWN)
            s.require((applicability is s.TimingApplicability.REQUIRED) == (deadline is not None))
            if deadline is not None: s.require(s.strict_bound(interval, deadline) is s.TimingBound.SATISFIED)
    except s.TimeRejected: return GateReason.TIME, None
    history = bundle.history
    if (history.context != context or history.activation != bundle.activation
            or history.activation_status is not pr.CurrentStatus.CURRENT
            or history.host_status is not pr.HostStatus.APPROVED or history.fencing_status is not pr.FencingStatus.CLEAR):
        return GateReason.CURRENT_CONTEXT, None
    if history.command is CommandHistory.EXACT_REPLAY: return GateReason.REPLAY, None
    if history.command is not CommandHistory.NEW: return GateReason.HISTORY, None
    if any(gap is not GapKnowledge.CLEAR for gap in (history.acquisition, history.publication, history.completion)):
        return GateReason.UNRESOLVED, None
    return None, evaluated


def _snapshot(value):
    """Exact immutable comparison projection of an already closed value graph.

    Preserve full bytes and all fields; hashing is not a substitute. This captures
    the evaluated request before callback execution, including redundant witnesses.
    """
    kind = type(value)
    if value is None or any(kind is approved for approved in (str, bytes, int, bool)):
        return kind, value
    if kind is tuple: return kind, tuple(_snapshot(item) for item in value)
    enums = (CommandHistory, GapKnowledge, s.ApprovalApplicability, s.EvidenceValidity,
        s.TimingApplicability, c.Command, c.Operation, c.Phase, c.ArtifactType,
        p.ExecutionState, p.QuarantineReason, pr.PredecessorProfile, pr.CurrentStatus,
        pr.HostStatus, pr.FencingStatus, pr.ResolutionState, pr.ResolutionReason)
    if any(kind is approved for approved in enums): return kind, value
    kind = _kind(value)
    return kind, tuple((field.name, _snapshot(getattr(value, field.name))) for field in fields(kind))


@dataclass(frozen=True, repr=False, init=False)
class GateResult:
    """Evaluator-issued in-memory knowledge; no future reusable authority."""
    bundle: PrerequisiteBundle | None
    qualification: QualificationEvidence | None
    time_evaluation: s.TimeEvaluation | None
    state: GateState
    reason: GateReason

    def __init__(self, *args, **kwargs):
        raise TypeError('Use prerequisite evaluation through trusted composition')

    def __post_init__(self):
        s.require(type(self) is GateResult and type(self.state) is GateState and type(self.reason) is GateReason)
        s.require(self.bundle is None or type(self.bundle) is PrerequisiteBundle)
        if self.bundle is None:
            s.require(self.state is GateState.FAIL_CLOSED and self.reason is GateReason.MALFORMED
                      and self.qualification is None and self.time_evaluation is None)
            return
        _revalidate(self.bundle)
        reason, evaluated = _check(self.bundle)
        if self.state is GateState.CHECKED:
            s.require(self.reason is GateReason.CHECKED and type(self.qualification) is QualificationEvidence)
            _revalidate(self.qualification)
            s.require(reason is None and self.qualification.validity is s.EvidenceValidity.VALID
                      and self.qualification.bundle == self.bundle)
            s.require(type(self.time_evaluation) is s.TimeEvaluation)
            _revalidate(self.time_evaluation)
            s.require(self.time_evaluation == evaluated)
        else:
            s.require(self.reason is not GateReason.CHECKED and self.qualification is None and self.time_evaluation is None)
            handoff = self.reason in (GateReason.REPLAY, GateReason.HISTORY, GateReason.UNRESOLVED)
            s.require(self.state is (GateState.HANDOFF if handoff else GateState.FAIL_CLOSED))
            if self.reason in (GateReason.UNAVAILABLE, GateReason.UNQUALIFIED, GateReason.QUALIFICATION_BINDING):
                s.require(reason is None)
            else:
                s.require(self.reason is reason)

    @property
    def permit_acquisition_permitted(self): return False
    @property
    def transaction_owned(self): return False
    @property
    def local_mutation_permitted(self): return False
    @property
    def sql_permitted(self): return False
    @property
    def candidate_retention_permitted(self): return False
    @property
    def publication_permitted(self): return False
    @property
    def completion_permitted(self): return False
    @property
    def ack_delivery_permitted(self): return False
    @property
    def active_permitted(self): return False
    @property
    def retry_permitted(self): return False
    @property
    def fence_clearance_permitted(self): return False
    @property
    def recovery_execution_permitted(self): return False
    @property
    def local_commit_confirmed(self): return False
    @property
    def permit_owned(self): return False
    @property
    def envelope_retained(self): return False
    @property
    def fixed_utc_established(self): return False


def _result(bundle, reason, qualification=None, evaluated=None):
    # Private assembly from the evaluator only, not a request-side proof factory.
    state = (GateState.CHECKED if reason is None else GateState.HANDOFF
             if reason in (GateReason.REPLAY, GateReason.HISTORY, GateReason.UNRESOLVED) else GateState.FAIL_CLOSED)
    result = object.__new__(GateResult)
    for name, value in (('bundle', bundle), ('qualification', qualification), ('time_evaluation', evaluated),
                        ('state', state), ('reason', GateReason.CHECKED if reason is None else reason)):
        object.__setattr__(result, name, value)
    GateResult.__post_init__(result)
    return result


def _unavailable_after_callback(bundle):
    # An ordinary read failure does not exempt retained input from revalidation.
    reason, _ = _check(bundle)
    if reason is not None: return _result(None if reason is GateReason.MALFORMED else bundle, reason)
    return _result(bundle, GateReason.UNAVAILABLE)


def evaluate_prerequisites(bundle, verifier=None):
    """One read-only qualification callback after all mandatory pure checks.

    The verifier must qualify the exact bundle and all claimed applicability,
    current authority/history and predecessor provenance, not echo its VALID bits.
    Repeated evaluation creates no original operation and carries no permission.
    """
    reason, evaluated = _check(bundle)
    if reason is not None:
        return _result(None if reason is GateReason.MALFORMED else bundle, reason)
    if type(verifier) is not TrustedPrerequisiteVerifier:
        return _result(bundle, GateReason.UNAVAILABLE)
    try:
        TrustedPrerequisiteVerifier.__post_init__(verifier)
    except (s.TimeRejected, AttributeError): return _result(bundle, GateReason.UNAVAILABLE)
    original = _snapshot(bundle)
    try:
        qualified = verifier.verify(bundle)
    except s.CapabilityUnavailable: return _unavailable_after_callback(bundle)
    except (AssertionError, TypeError): raise
    except Exception:
        # Only the explicitly composed external/read qualification call. Internal
        # codecs/predicates and returned-evidence validation remain outside this.
        return _unavailable_after_callback(bundle)
    reason, evaluated = _check(bundle)
    if reason is not None: return _result(None if reason is GateReason.MALFORMED else bundle, reason)
    try:
        s.require(type(qualified) is QualificationEvidence)
        _revalidate(qualified)
    except (s.TimeRejected, p.ProtocolRejected, c.ContractRejected, UnicodeError, AttributeError, RecursionError):
        return _result(bundle, GateReason.UNQUALIFIED)
    if qualified.validity is not s.EvidenceValidity.VALID:
        return _result(bundle, GateReason.UNQUALIFIED)
    if _snapshot(qualified.bundle) != original or _snapshot(bundle) != original:
        return _result(bundle, GateReason.QUALIFICATION_BINDING)
    # Revalidate exact supplied material after the callback as well, so mutation
    # through privileged copied-object fixtures cannot bypass the pure checks.
    return _result(bundle, None, qualified, evaluated)
