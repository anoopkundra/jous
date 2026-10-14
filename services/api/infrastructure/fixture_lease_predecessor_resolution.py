"""Normal pre-permit read-only predecessor knowledge; no operational permission.

Qualification is supplied independently, never manufactured by construction,
matching metadata or hashing. Only the explicitly trusted injected resolver runs,
once, after context checks. No permit, transaction, persistence or recovery occurs.
Genesis/replacement profiles and IL.7 resumption are separate authorities.
"""
from dataclasses import dataclass, fields
from enum import StrEnum
from hashlib import sha256
from types import FunctionType, MethodType

from . import fixture_lease_service as s
from . import fixture_lease_protocol as p
from . import fixture_lease_checkpoints as checkpoints


class PredecessorProfile(StrEnum):
    NORMAL_COMMAND = 'NORMAL_COMMAND'
    GENESIS = 'GENESIS'
    REPLACEMENT = 'REPLACEMENT'


class CurrentStatus(StrEnum):
    CURRENT = 'CURRENT'
    SUPERSEDED = 'SUPERSEDED'
    UNKNOWN = 'UNKNOWN'


class HostStatus(StrEnum):
    APPROVED = 'APPROVED'
    UNAPPROVED = 'UNAPPROVED'
    UNKNOWN = 'UNKNOWN'


class FencingStatus(StrEnum):
    CLEAR = 'CLEAR'
    FENCED = 'FENCED'
    RECOVERY_ONLY = 'RECOVERY_ONLY'
    UNKNOWN = 'UNKNOWN'


class ResolutionState(StrEnum):
    CHECKED = 'CHECKED_PREDECESSOR_RESOLUTION_KNOWLEDGE'
    FAIL_CLOSED = 'FAIL_CLOSED'


class ResolutionReason(StrEnum):
    CHECKED = 'CHECKED'
    MISSING_CONTEXT = 'MISSING_CONTEXT'
    MALFORMED_CONTEXT = 'MALFORMED_CONTEXT'
    UNQUALIFIED_CONTEXT = 'UNQUALIFIED_CONTEXT'
    CONTEXT_MISMATCH = 'CONTEXT_MISMATCH'
    CURRENT_AUTHORITY = 'CURRENT_AUTHORITY'
    UNSUPPORTED_PROFILE = 'UNSUPPORTED_PROFILE'
    REVISION = 'REVISION'
    UNAVAILABLE = 'UNAVAILABLE'
    RESOLVER_EXCEPTION = 'RESOLVER_EXCEPTION'
    MISSING_RESULT = 'MISSING_RESULT'
    MALFORMED_RESULT = 'MALFORMED_RESULT'
    UNQUALIFIED_RESULT = 'UNQUALIFIED_RESULT'
    QUALIFICATION_MISMATCH = 'QUALIFICATION_MISMATCH'
    PREDECESSOR_MISMATCH = 'PREDECESSOR_MISMATCH'
    CHECKPOINT_MISMATCH = 'CHECKPOINT_MISMATCH'


@dataclass(frozen=True, repr=False)
class CurrentBinding:
    """Expected protected pointer/generation and immutable representation facts.

    These are supplied upstream, not acquired from local storage here. Authority
    names the protected authority namespace; its qualified reference must cover
    the selected activation, approved host, pointer and immutable protocol binding.
    """
    activation: s.ActivationIdentity
    approved_host: str
    authority: s.EvidenceReference
    representation: str
    representation_authority: s.EvidenceReference
    profile: PredecessorProfile
    revision: int
    event_sequence: int
    event_digest: bytes
    state_digest: bytes

    def __post_init__(self):
        _children(self)
        s.require(type(self.activation) is s.ActivationIdentity)
        s.require(type(self.authority) is s.EvidenceReference
                  and type(self.representation_authority) is s.EvidenceReference)
        s.identity(self.approved_host); s.identity(self.representation)
        s.require(type(self.profile) is PredecessorProfile)
        p.uint(self.revision); p.uint(self.event_sequence)
        p.digest_value(self.event_digest); p.digest_value(self.state_digest)


@dataclass(frozen=True, repr=False)
class ContextQualification:
    """Untrusted claims of CURRENT facts, including freshness and no unresolved gap.

    The trusted adapter must independently verify this reference for the binding and
    status bundle at the upstream evaluation. This value does not qualify itself
    or provide future reusable authority; no clock profile is selected here.
    """
    binding: CurrentBinding
    validity: s.EvidenceValidity
    reference: s.EvidenceReference
    activation_status: CurrentStatus
    host_status: HostStatus
    fencing_status: FencingStatus

    def __post_init__(self):
        _children(self)
        s.require(type(self.binding) is CurrentBinding and type(self.reference) is s.EvidenceReference)
        s.require(type(self.validity) is s.EvidenceValidity and type(self.activation_status) is CurrentStatus)
        s.require(type(self.host_status) is HostStatus and type(self.fencing_status) is FencingStatus)


@dataclass(frozen=True, repr=False)
class QualifiedCurrentContext:
    requested: CurrentBinding
    qualification: ContextQualification | None

    def __post_init__(self):
        _children(self)
        s.require(type(self.requested) is CurrentBinding)
        s.require(self.qualification is None or type(self.qualification) is ContextQualification)


@dataclass(frozen=True, repr=False)
class ResolutionQualification:
    """Untrusted claimed witness for the exact current-context resolution.

    reference must resolve authenticated linearizable current-pointer/ancestry
    qualification for this exact request AND exact predecessor bytes/facts. It
    is not a fabricated reference, transport status or structural success flag.
    """
    context: QualifiedCurrentContext
    predecessor: s.ResolvedCheckpointEvidence
    validity: s.EvidenceValidity
    reference: s.EvidenceReference

    def __post_init__(self):
        _children(self)
        s.require(type(self.context) is QualifiedCurrentContext
                  and type(self.predecessor) is s.ResolvedCheckpointEvidence)
        s.require(type(self.validity) is s.EvidenceValidity and type(self.reference) is s.EvidenceReference)


@dataclass(frozen=True, repr=False)
class ResolutionObservation:
    predecessor: s.ResolvedCheckpointEvidence
    qualification: ResolutionQualification | None

    def __post_init__(self):
        _children(self)
        s.require(type(self.predecessor) is s.ResolvedCheckpointEvidence)
        s.require(self.qualification is None or type(self.qualification) is ResolutionQualification)


@dataclass(frozen=True, repr=False)
class TrustedPredecessorAdapter:
    """Composition-time dependency, NEVER accepted from request evidence.

    The trusted composer explicitly binds independent qualification verification
    and the frozen resolve_predecessor(activation) read here. Construction is not
    authentication, production-provider approval or qualification of any request.
    These callbacks are trusted code, not caller claims: deployments must protect
    their composition root. Deterministic test adapters use this same seam.
    Callback concrete-type checks enforce shape only; names confer no authority.
    """
    verify_context: object
    read: object
    verify_resolution: object

    def __post_init__(self):
        s.require(type(self) is TrustedPredecessorAdapter)
        for operation in (self.verify_context, self.read, self.verify_resolution):
            s.require(type(operation) is FunctionType or type(operation) is MethodType)



def _dataclass_type(value):
    kind = type(value)
    allowed = (CurrentBinding, ContextQualification, QualifiedCurrentContext,
        ResolutionQualification, ResolutionObservation, s.ActivationIdentity,
        s.EvidenceReference, s.ResolvedCheckpointEvidence)
    s.require(any(kind is approved for approved in allowed))
    return kind


def _children(value):
    kind = _dataclass_type(value)
    for field in fields(kind): _revalidate(getattr(value, field.name))


def _revalidate(value):
    """Closed concrete identities before ANY foreign instance behavior."""
    kind = type(value)
    if value is None or any(kind is approved for approved in (str, bytes, int)): return
    enums = (PredecessorProfile, CurrentStatus, HostStatus, FencingStatus, s.EvidenceValidity)
    if any(kind is approved for approved in enums): return
    kind = _dataclass_type(value)
    if kind.__module__ != __name__: _children(value)
    if kind is s.ResolvedCheckpointEvidence:
        # Resource bound derived from the already-published eleven-field v1
        # frame, not a competing codec or an arbitrary whole-STATE limit.
        # The frozen decoder must still check every individual field/count/tag.
        s.require(type(value.exact_bytes) is bytes)
        maximum = len(p.PREFIX) + 2 + 4 + 11 * (4 + p.MAX_FIELD)
        s.require(len(value.exact_bytes) <= maximum)
    kind.__post_init__(value)


def _precheck(context):
    if context is None: return ResolutionReason.MISSING_CONTEXT
    try:
        s.require(type(context) is QualifiedCurrentContext)
        _revalidate(context)
    except (s.TimeRejected, p.ProtocolRejected, UnicodeError, RecursionError, AttributeError):
        return ResolutionReason.MALFORMED_CONTEXT
    expected, qualified = context.requested, context.qualification
    if qualified is None or qualified.validity is not s.EvidenceValidity.VALID:
        return ResolutionReason.UNQUALIFIED_CONTEXT
    if expected != qualified.binding: return ResolutionReason.CONTEXT_MISMATCH
    if (qualified.activation_status is not CurrentStatus.CURRENT
            or qualified.host_status is not HostStatus.APPROVED
            or qualified.fencing_status is not FencingStatus.CLEAR
            or expected.approved_host != expected.activation.host_identity):
        return ResolutionReason.CURRENT_AUTHORITY
    if expected.profile is not PredecessorProfile.NORMAL_COMMAND or expected.representation != p.STATE_2:
        return ResolutionReason.UNSUPPORTED_PROFILE
    if not (0 < expected.revision < p.MAX_UINT and expected.event_sequence > 0):
        return ResolutionReason.REVISION
    return None


def _postcheck(context, observed):
    if observed is None: return ResolutionReason.MISSING_RESULT
    try:
        s.require(type(observed) is ResolutionObservation)
        _revalidate(observed)
    except (s.TimeRejected, p.ProtocolRejected, UnicodeError, RecursionError, AttributeError):
        return ResolutionReason.MALFORMED_RESULT
    witness = observed.qualification
    if witness is None or witness.validity is not s.EvidenceValidity.VALID:
        return ResolutionReason.UNQUALIFIED_RESULT
    if witness.context != context or witness.predecessor != observed.predecessor:
        return ResolutionReason.QUALIFICATION_MISMATCH
    expected, predecessor = context.requested, observed.predecessor
    if ((predecessor.activation, predecessor.reference, predecessor.revision,
         predecessor.event_sequence, predecessor.event_digest, predecessor.state_digest,
         predecessor.representation, predecessor.representation_authority) !=
        (expected.activation, expected.activation.checkpoint, expected.revision,
         expected.event_sequence, expected.event_digest, expected.state_digest,
         expected.representation, expected.representation_authority)):
        return ResolutionReason.PREDECESSOR_MISMATCH
    try:
        # The exact frozen NORMAL_COMMAND decoder owns framing, not this boundary.
        decoded = checkpoints.decode_checkpoint(predecessor.exact_bytes)
        s.require(sha256(predecessor.exact_bytes).digest() == predecessor.reference.sha256)
        activation = expected.activation
        authority = expected.representation_authority
        s.require((decoded.register_id, decoded.generation, decoded.activation_id,
            decoded.revision, decoded.event_sequence, decoded.event_digest, decoded.state_digest,
            decoded.reference.host, decoded.reference.representation,
            decoded.reference.representation_authority_id, decoded.reference.representation_authority_sha256) ==
            (activation.register_id, activation.generation, activation.activation_id,
             expected.revision, expected.event_sequence, expected.event_digest, expected.state_digest,
             expected.approved_host, expected.representation, authority.identity, authority.sha256))
    except (s.TimeRejected, p.ProtocolRejected): return ResolutionReason.CHECKPOINT_MISMATCH
    return None


@dataclass(frozen=True, repr=False, init=False)
class ResolutionResult:
    """In-memory checked knowledge/handoff only; no executed fence or permission.

    A later permit boundary must independently enforce its own current gates.
    None means unavailable material, never authoritative absence or no effect.
    """
    context: QualifiedCurrentContext | None
    observation: ResolutionObservation | None
    read_attempted: bool
    state: ResolutionState
    reason: ResolutionReason

    def __init__(self, *args, **kwargs):
        # Results are evaluator-issued knowledge. Public field construction or
        # dataclasses.replace cannot turn request-side claims into CHECKED facts.
        raise TypeError('Resolution results must be evaluated through trusted composition')

    def __post_init__(self):
        s.require(type(self) is ResolutionResult)
        s.require(type(self.read_attempted) is bool and type(self.state) is ResolutionState
                  and type(self.reason) is ResolutionReason)
        s.require(self.context is None or type(self.context) is QualifiedCurrentContext)
        s.require(self.observation is None or type(self.observation) is ResolutionObservation)
        if self.reason is ResolutionReason.MALFORMED_CONTEXT and self.context is None:
            s.require(not self.read_attempted and self.observation is None and self.state is ResolutionState.FAIL_CLOSED)
            return
        pre = _precheck(self.context)
        if pre is not None:
            s.require(pre is not ResolutionReason.MALFORMED_CONTEXT and self.reason is pre
                and not self.read_attempted and self.observation is None and self.state is ResolutionState.FAIL_CLOSED)
            return
        if self.reason is ResolutionReason.UNQUALIFIED_CONTEXT:
            s.require(self.state is ResolutionState.FAIL_CLOSED and not self.read_attempted
                      and self.observation is None)
            return
        if self.reason is ResolutionReason.UNQUALIFIED_RESULT:
            s.require(self.state is ResolutionState.FAIL_CLOSED and self.read_attempted
                      and self.observation is not None)
            _revalidate(self.observation)
            return
        if self.observation is None:
            s.require(self.state is ResolutionState.FAIL_CLOSED)
            s.require((self.reason is ResolutionReason.UNAVAILABLE)
                or (self.read_attempted and self.reason in (ResolutionReason.RESOLVER_EXCEPTION,
                    ResolutionReason.MISSING_RESULT, ResolutionReason.MALFORMED_RESULT)))
            return
        reason = _postcheck(self.context, self.observation)
        s.require(reason is not ResolutionReason.MALFORMED_RESULT and self.read_attempted)
        s.require((self.state is ResolutionState.CHECKED and self.reason is ResolutionReason.CHECKED and reason is None)
            or (self.state is ResolutionState.FAIL_CLOSED and self.reason is reason and reason is not None))

    @property
    def local_write_permitted(self): return False
    @property
    def transaction_owned(self): return False
    @property
    def sql_permitted(self): return False
    @property
    def permit_acquisition_permitted(self): return False
    @property
    def candidate_retention_permitted(self): return False
    @property
    def checkpoint_publication_permitted(self): return False
    @property
    def permit_completion_permitted(self): return False
    @property
    def ack_delivery_permitted(self): return False
    @property
    def active_permitted(self): return False
    @property
    def fence_clearance_permitted(self): return False
    @property
    def recovery_execution_permitted(self): return False
    @property
    def local_commit_confirmed(self): return False
    @property
    def permit_owned(self): return False
    @property
    def authoritative_absence(self): return False
    @property
    def retry_permitted(self): return False


def _result(context, observation, read_attempted, state, reason):
    """Internal output assembly after the evaluator's independent verification.

    This is not a request-side qualification factory or a durable witness.
    Privileged Python mutation of module internals is outside this composition
    boundary; externally supplied values never enter through this helper.
    """
    result = object.__new__(ResolutionResult)
    for name, value in (('context', context), ('observation', observation),
                        ('read_attempted', read_attempted), ('state', state), ('reason', reason)):
        object.__setattr__(result, name, value)
    ResolutionResult.__post_init__(result)
    return result


def _verified(operation, *values):
    """Isolated trusted qualification read; never catch internal validation errors."""
    try:
        verdict = operation(*values)
    except s.CapabilityUnavailable:
        return False
    except (AssertionError, TypeError):
        raise
    except Exception:
        # Ordinary external qualification outage only; no diagnostic access.
        return False
    return type(verdict) is s.EvidenceValidity and verdict is s.EvidenceValidity.VALID


def resolve_predecessor(context: QualifiedCurrentContext | None,
                        adapter: TrustedPredecessorAdapter | None) -> ResolutionResult:
    """Closed structure -> trusted qualification -> single read -> qualification.

    The adapter is a separately injected trusted composition dependency. Raw
    functions, unrelated methods and request witnesses are never capabilities.
    No request VALID label or exact metadata establishes qualification. This
    function cannot authenticate an untrusted composition root or select providers.
    """
    pre = _precheck(context)
    if pre is not None:
        retained = None if pre is ResolutionReason.MALFORMED_CONTEXT else context
        return _result(retained, None, False, ResolutionState.FAIL_CLOSED, pre)
    if type(adapter) is not TrustedPredecessorAdapter:
        return _result(context, None, False, ResolutionState.FAIL_CLOSED, ResolutionReason.UNAVAILABLE)
    try:
        TrustedPredecessorAdapter.__post_init__(adapter)
    except (s.TimeRejected, AttributeError):
        return _result(context, None, False, ResolutionState.FAIL_CLOSED, ResolutionReason.UNAVAILABLE)
    if not _verified(adapter.verify_context, context):
        return _result(context, None, False, ResolutionState.FAIL_CLOSED, ResolutionReason.UNQUALIFIED_CONTEXT)
    try:
        observed = adapter.read(context.requested.activation)
    except s.CapabilityUnavailable:
        return _result(context, None, True, ResolutionState.FAIL_CLOSED, ResolutionReason.UNAVAILABLE)
    except (AssertionError, TypeError):
        raise
    except Exception:
        # Isolated protected read only; internal errors are not swallowed.
        return _result(context, None, True, ResolutionState.FAIL_CLOSED, ResolutionReason.RESOLVER_EXCEPTION)
    reason = _postcheck(context, observed)
    if reason is None and not _verified(adapter.verify_resolution, context, observed):
        reason = ResolutionReason.UNQUALIFIED_RESULT
    if reason is ResolutionReason.MALFORMED_RESULT: observed = None
    return _result(context, observed, True,
        ResolutionState.CHECKED if reason is None else ResolutionState.FAIL_CLOSED,
        ResolutionReason.CHECKED if reason is None else reason)
