"""Increment D: one original candidate association and qualified retention knowledge.

Composition, not request evidence, selects the independently trusted verifier,
association implementation and qualifier. Their shape is not authentication.
Protected history enforces immutable association and cross-evaluation safety.
No publication, permit effect, clock, SQLite, recovery or runtime wiring exists.
"""
from dataclasses import dataclass, fields
from enum import StrEnum
from hashlib import sha256
from types import FunctionType, MethodType

from . import fixture_lease_candidate_preparation as c
from . import fixture_lease_service as s
from . import fixture_lease_publication_gate as g


class AssociationHistory(StrEnum):
    EXACT_EXISTING = 'EXACT_EXISTING'
    ELIGIBLE_FIRST_ASSOCIATION = 'ELIGIBLE_FIRST_ASSOCIATION'
    CONFLICT = 'CONFLICT'
    UNKNOWN_HISTORY = 'UNKNOWN_HISTORY'
    PROVEN_PRE_DISPATCH_FAILURE = 'PROVEN_PRE_DISPATCH_FAILURE'


class ProgressionStatus(StrEnum):
    CLEAR = 'CLEAR'
    PROHIBITED = 'PROHIBITED'
    UNKNOWN = 'UNKNOWN'


class ObservationKind(StrEnum):
    RETURNED_CANDIDATE = 'RETURNED_CANDIDATE'
    MALFORMED_RETURN = 'MALFORMED_RETURN'
    CAPABILITY_UNAVAILABLE = 'CAPABILITY_UNAVAILABLE'
    EXTERNAL_UNAVAILABLE = 'EXTERNAL_UNAVAILABLE'
    TIMEOUT = 'TIMEOUT'


class AssociationDisposition(StrEnum):
    RETAINED = 'RETAINED'
    CONFLICT = 'CONFLICT'
    PROVEN_NON_DISPATCH = 'PROVEN_NON_DISPATCH'
    UNKNOWN = 'UNKNOWN'


class RetentionState(StrEnum):
    RETAINED = 'RETAINED'
    REJECTED = 'REJECTED'
    UNRESOLVED = 'UNRESOLVED'


class RetentionReason(StrEnum):
    RETAINED_FIRST_ASSOCIATION = 'RETAINED_FIRST_ASSOCIATION'
    RETAINED_EXACT_EXISTING = 'RETAINED_EXACT_EXISTING'
    INVALID_C_SOURCE = 'INVALID_C_SOURCE'
    NOT_PREPARED = 'NOT_PREPARED'
    UPSTREAM_UNRESOLVED = 'UPSTREAM_UNRESOLVED'
    UNQUALIFIED_C_PROVENANCE = 'UNQUALIFIED_C_PROVENANCE'
    HISTORICAL_T1_INVALID = 'HISTORICAL_T1_INVALID'
    PROGRESSION_PROHIBITED = 'PROGRESSION_PROHIBITED'
    PROGRESSION_UNKNOWN = 'PROGRESSION_UNKNOWN'
    ASSOCIATION_CONFLICT = 'ASSOCIATION_CONFLICT'
    UNKNOWN_HISTORY = 'UNKNOWN_HISTORY'
    PROVEN_PRE_DISPATCH_FAILURE = 'PROVEN_PRE_DISPATCH_FAILURE'
    PROVEN_PRE_DISPATCH_UNAVAILABLE = 'PROVEN_PRE_DISPATCH_UNAVAILABLE'
    ELIGIBLE_FIRST_ASSOCIATION = 'ELIGIBLE_FIRST_ASSOCIATION'
    ELIGIBILITY_UNAVAILABLE = 'ELIGIBILITY_UNAVAILABLE'
    ELIGIBILITY_MALFORMED = 'ELIGIBILITY_MALFORMED'
    ELIGIBILITY_UNQUALIFIED = 'ELIGIBILITY_UNQUALIFIED'
    POST_EFFECT_UNKNOWN = 'POST_EFFECT_UNKNOWN'
    CONFIRMATION_UNAVAILABLE = 'CONFIRMATION_UNAVAILABLE'
    CONFIRMATION_MALFORMED = 'CONFIRMATION_MALFORMED'
    CONFIRMATION_UNBOUND = 'CONFIRMATION_UNBOUND'
    CONFIRMATION_CONFLICT = 'CONFIRMATION_CONFLICT'
    PROVEN_NON_DISPATCH = 'PROVEN_NON_DISPATCH'
    INSTABILITY = 'INSTABILITY'
    EVIDENCE_CONTRADICTION = 'EVIDENCE_CONTRADICTION'
    PROGRAMMING_DEFECT = 'PROGRAMMING_DEFECT'


@dataclass(frozen=True, repr=False)
class TrustedCandidateRetentionAdapter:
    """Trusted composition contract: verify/qualify are independent read-only
    qualification, not syntax echoes. associate implements the frozen capability,
    enforces protected immutable original history, and never retries/falls back.
    No callback may perform publication, permit effects or recovery. Names and
    constructors cannot create trust. Production realization is separately gated.
    """
    authority: s.EvidenceReference
    implementation: s.EvidenceReference
    verify: object
    associate: object
    qualify: object


@dataclass(frozen=True, repr=False)
class EligibilityQualification:
    """Authentic COMPLETE assessment, not necessarily positive eligibility.

    A VALID reference must independently bind genuine C execution provenance,
    historical T1/COMMIT/snapshot, candidate/context and the assessed protected
    namespace, progression and original association history immediately before
    dispatch. Negative provenance/T1 reasons also require independent proof of
    claimed non-dispatch. Unknown prior effects cannot be hidden by those reasons.
    No current permit-expiry consumption test is part of this assessment.
    """
    source: c.PreparationResult
    authority: s.EvidenceReference
    implementation: s.EvidenceReference
    validity: s.EvidenceValidity
    reference: s.EvidenceReference
    history: AssociationHistory
    progression: ProgressionStatus
    reason: RetentionReason
    retention: g.CandidateRetentionEvidence | None


@dataclass(frozen=True, repr=False)
class AssociationObservation:
    source: c.PreparationResult
    eligibility: EligibilityQualification
    kind: ObservationKind
    returned_candidate: s.CheckpointCandidate | None


@dataclass(frozen=True, repr=False)
class AssociationQualification:
    """Independent bound disposition proof, never authority from construction.

    RETAINED proves exact durable protected existence, immutable original-key
    association, full original bindings and retained-history lifetime. NON_DISPATCH
    positively proves no dispatch, never absence of response. A candidate echo,
    exception or matching digest cannot establish either claim.
    """
    observation: AssociationObservation
    authority: s.EvidenceReference
    implementation: s.EvidenceReference
    validity: s.EvidenceValidity
    reference: s.EvidenceReference
    disposition: AssociationDisposition
    reason: RetentionReason
    retention: g.CandidateRetentionEvidence | None


@dataclass(frozen=True, repr=False)
class _RetainedCandidate:
    source: c.PreparationResult
    eligibility: EligibilityQualification
    retention: g.CandidateRetentionEvidence
    disposition: AssociationQualification | None
    association_invoked: bool
    reconciliation_required: bool


@dataclass(frozen=True, repr=False)
class _RejectedCandidate:
    source: c.PreparationResult | None
    eligibility: EligibilityQualification | None
    disposition: AssociationQualification | None
    association_invoked: bool
    reconciliation_required: bool


@dataclass(frozen=True, repr=False)
class _UnresolvedCandidate:
    source: c.PreparationResult
    eligibility: EligibilityQualification | None
    observation: AssociationObservation | None
    disposition: AssociationQualification | None
    association_invoked: bool
    reconciliation_required: bool


@dataclass(frozen=True, repr=False, init=False)
class RetentionResult:
    state: RetentionState
    reason: RetentionReason
    verification_attempted: bool
    qualification_attempted: bool
    retained: _RetainedCandidate | None
    rejected: _RejectedCandidate | None
    unresolved: _UnresolvedCandidate | None

    def __init__(self, *args, **kwargs):
        raise TypeError('Use CandidateRetainer.retain_candidate')

    def __bool__(self):
        raise TypeError('Retention knowledge is not permission')

    def __copy__(self):
        raise TypeError('Use candidate retention')

    def __deepcopy__(self, memo):
        raise TypeError('Use candidate retention')


_PERMISSIONS = ('publication_permitted', 'predecessor_cas_permitted',
    'publication_disposition_permitted', 'completion_permitted', 'cancellation_permitted',
    'renewal_permitted', 'reacquisition_permitted', 'ack_construction_permitted',
    'ack_delivery_permitted', 'ack_redelivery_permitted', 'recovery_execution_permitted',
    'fence_clearance_permitted', 'runtime_activation_permitted',
    'second_association_permitted', 'retry_permitted')
for _name in _PERMISSIONS:
    setattr(RetentionResult, _name, property(lambda self: False))


class _RetentionEvaluationInterrupted(BaseException):
    """Process-local only. Loss/death/allocation failure proves no non-dispatch.
    Original programming/interruption identity remains in __cause__. Restart and
    protected-system fencing/recovery are not implemented by this handoff.
    """
    def __init__(self, result):
        self.result = result


class _Malformed(ValueError):
    pass


def _require(condition):
    if not condition:
        raise _Malformed()


_ENUMS = c._ENUMS + (AssociationHistory, ProgressionStatus, ObservationKind,
    AssociationDisposition, RetentionState, RetentionReason)
_VALUES = c._DATACLASSES + (c.PreparationResult, EligibilityQualification,
    AssociationObservation, AssociationQualification, g.CandidateRetentionEvidence,
    _RetainedCandidate, _RejectedCandidate, _UnresolvedCandidate, RetentionResult)
_INVALID = (_Malformed, c._Bad) + c._INVALID
_AVAILABILITY = (s.CapabilityUnavailable, c.a.ExternalAvailabilityFailure, TimeoutError)


def _project(value):
    """Closed exact graph; identity memo only after classification. No size cap."""
    active, memo = set(), {}

    def visit(item):
        kind = type(item)
        if any(kind is t for t in (type(None), str, bytes, int, bool)):
            return kind, item
        if any(kind is t for t in _ENUMS):
            _require(any(item is member for member in kind))
            return kind, item
        _require(kind is tuple or any(kind is t for t in _VALUES))
        identity = id(item)
        _require(identity not in active)
        if identity in memo:
            return memo[identity]
        active.add(identity)
        if kind is tuple:
            projected = kind, tuple(visit(v) for v in item)
        else:
            children = []
            for field in fields(kind):
                try:
                    child = object.__getattribute__(item, field.name)
                except AttributeError:
                    raise _Malformed() from None
                projected_child = visit(child)
                _require(c._matches(child, field.type))
                children.append((field.name, projected_child))
            projected = kind, tuple(children)
        active.remove(identity)
        memo[identity] = projected
        return projected

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


def _copy(value):
    return _detach(_project(value))


def _stable(value, projection):
    try:
        return _project(value) == projection
    except _Malformed:
        return False


def _reference(value):
    _require(type(value) is s.EvidenceReference)
    s.EvidenceReference.__post_init__(value)


def _source(value):
    _require(type(value) is c.PreparationResult)
    if value.state is not c.PreparationState.PREPARED:
        _require(value.prepared is None and value.reason is not c.PreparationReason.PREPARED
                 and value.diagnostic is value.reason)
        return
    _require(value.reason is c.PreparationReason.PREPARED and value.qualification_attempted
             and value.diagnostic is None and type(value.prepared) is c._PreparedCandidate)
    material = value.prepared
    _require(c._domain(material.request.completion) is None)
    _require(material.provenance.validity is s.EvidenceValidity.VALID
             and material.provenance.request == material.request)
    for ref in (material.provenance.authority, material.provenance.implementation,
                material.provenance.reference):
        _reference(ref)
    c._bindings(material.request)
    c._snapshot(material.request)
    candidate, done = material.candidate, material.request.completion.completed
    s.CheckpointCandidate.__post_init__(candidate)
    _require(candidate.envelope == done.envelope)
    parsed = c.checkpoints.decode_checkpoint(candidate.exact_bytes)
    env, activation = done.envelope, done.envelope.activation
    _require((parsed.register_id, parsed.generation, parsed.activation_id, parsed.revision,
              parsed.event_sequence, parsed.event_digest, parsed.state_digest, parsed.utc_us,
              parsed.predecessor_digest) ==
             (activation.register_id, activation.generation, activation.activation_id,
              env.predecessor.revision + 1, done.event_sequence, done.event_digest,
              done.state_digest, env.fixed_utc_us, sha256(env.predecessor.exact_bytes).digest()))
    ref = parsed.reference
    authority = env.predecessor.representation_authority
    _require((ref.command_id, ref.command_sha256, ref.permit_id, ref.permit_sha256,
              ref.host, ref.representation, ref.representation_authority_id,
              ref.representation_authority_sha256, ref.admission_id, ref.admission_sha256) ==
             (env.context.command_id, env.context.payload_sha256, env.permit_reference.identity,
              env.permit_reference.sha256, activation.host_identity, env.predecessor.representation,
              authority.identity, authority.sha256, env.reference.identity, env.reference.sha256))
    _require(parsed.approval_id == (None if env.approval is None else env.approval.identity))
    _require((candidate.revision, candidate.fixed_utc_us, candidate.event_sequence,
              candidate.event_digest, candidate.state_digest) ==
             (parsed.revision, parsed.utc_us, parsed.event_sequence,
              parsed.event_digest, parsed.state_digest))


def _namespace(source):
    return source.prepared.request.completion.original.observation.source.prepared.material.source.attempt.bundle.predecessor.context.requested.authority


def _retention(evidence, source):
    _require(type(evidence) is g.CandidateRetentionEvidence)
    _reference(evidence.reference)
    _require(evidence.qualification is s.EvidenceValidity.VALID)
    s.verify_candidate_association(source.prepared.candidate, evidence.candidate)
    _require(evidence.operation == source.prepared.candidate.operation)


def _eligibility(value, source, authority, implementation):
    _require(type(value) is EligibilityQualification)
    for ref in (value.authority, value.implementation, value.reference):
        _reference(ref)
    _require(value.source == source and value.authority == authority
             and value.implementation == implementation)
    h, r = value.history, value.reason
    if h is AssociationHistory.EXACT_EXISTING:
        _require(r is RetentionReason.RETAINED_EXACT_EXISTING)
        _retention(value.retention, source)
    else:
        _require(value.retention is None)
        if h is AssociationHistory.ELIGIBLE_FIRST_ASSOCIATION:
            expected = {ProgressionStatus.CLEAR: RetentionReason.ELIGIBLE_FIRST_ASSOCIATION,
                ProgressionStatus.PROHIBITED: RetentionReason.PROGRESSION_PROHIBITED,
                ProgressionStatus.UNKNOWN: RetentionReason.PROGRESSION_UNKNOWN}
            _require(r is expected[value.progression])
        elif h is AssociationHistory.CONFLICT:
            _require(r is RetentionReason.ASSOCIATION_CONFLICT)
        elif h is AssociationHistory.UNKNOWN_HISTORY:
            _require(r is RetentionReason.UNKNOWN_HISTORY)
        else:
            _require(h is AssociationHistory.PROVEN_PRE_DISPATCH_FAILURE and r in (
                RetentionReason.UNQUALIFIED_C_PROVENANCE, RetentionReason.HISTORICAL_T1_INVALID,
                RetentionReason.PROVEN_PRE_DISPATCH_FAILURE,
                RetentionReason.PROVEN_PRE_DISPATCH_UNAVAILABLE))


def _disposition(value, observation, authority, implementation):
    _require(type(value) is AssociationQualification)
    for ref in (value.authority, value.implementation, value.reference):
        _reference(ref)
    _require(value.observation == observation and value.authority == authority
             and value.implementation == implementation)
    expected = {AssociationDisposition.RETAINED: RetentionReason.RETAINED_FIRST_ASSOCIATION,
        AssociationDisposition.CONFLICT: RetentionReason.CONFIRMATION_CONFLICT,
        AssociationDisposition.PROVEN_NON_DISPATCH: RetentionReason.PROVEN_NON_DISPATCH,
        AssociationDisposition.UNKNOWN: RetentionReason.POST_EFFECT_UNKNOWN}
    _require(value.reason is expected[value.disposition])
    if value.disposition is AssociationDisposition.RETAINED:
        _retention(value.retention, observation.source)
    else:
        _require(value.retention is None)


def _issue(state, reason, source=None, eligibility=None, observation=None,
           disposition=None, invoked=False, verified=False, qualified=False):
    retained = rejected = unresolved = None
    if state is RetentionState.RETAINED:
        evidence = eligibility.retention if disposition is None else disposition.retention
        retained = _RetainedCandidate(source, eligibility, evidence, disposition, invoked,
                                     eligibility.progression is not ProgressionStatus.CLEAR)
    elif state is RetentionState.REJECTED:
        rejected = _RejectedCandidate(source, eligibility, disposition, invoked,
                                     source is not None and source.prepared is not None)
    else:
        _require(source is not None)
        unresolved = _UnresolvedCandidate(source, eligibility, observation, disposition, invoked, True)
    result = object.__new__(RetentionResult)
    for name, value in (('state', state), ('reason', reason), ('verification_attempted', verified),
            ('qualification_attempted', qualified), ('retained', retained),
            ('rejected', rejected), ('unresolved', unresolved)):
        object.__setattr__(result, name, value)
    return _copy(result)


@dataclass(frozen=True, repr=False, init=False)
class CandidateRetainer:
    _adapter: object
    _authority: s.EvidenceReference
    _implementation: s.EvidenceReference
    _verify: object
    _associate: object
    _qualify: object

    def __init__(self, adapter: TrustedCandidateRetentionAdapter):
        if type(self) is not CandidateRetainer or type(adapter) is not TrustedCandidateRetentionAdapter:
            raise TypeError('Exact TrustedCandidateRetentionAdapter required')
        try:
            authority = _copy(object.__getattribute__(adapter, 'authority'))
            implementation = _copy(object.__getattribute__(adapter, 'implementation'))
            _reference(authority); _reference(implementation)
            callbacks = tuple(object.__getattribute__(adapter, n) for n in ('verify', 'associate', 'qualify'))
            _require(all(type(v) is FunctionType or type(v) is MethodType for v in callbacks))
        except (AttributeError,) + _INVALID:
            raise TypeError('Malformed candidate retention composition') from None
        for name, value in zip(('_adapter', '_authority', '_implementation', '_verify', '_associate', '_qualify'),
                               (adapter, authority, implementation) + callbacks):
            object.__setattr__(self, name, value)

    def _composition_stable(self):
        adapter = self._adapter
        try:
            return (_project(object.__getattribute__(adapter, 'authority')) == _project(self._authority)
                and _project(object.__getattribute__(adapter, 'implementation')) == _project(self._implementation)
                and all(object.__getattribute__(adapter, n) is captured for n, captured in
                    zip(('verify', 'associate', 'qualify'), (self._verify, self._associate, self._qualify))))
        except (AttributeError, _Malformed):
            return False

    def retain_candidate(self, source: c.PreparationResult) -> RetentionResult:
        reject, unknown, retained = RetentionState.REJECTED, RetentionState.UNRESOLVED, RetentionState.RETAINED
        try:
            _require(type(source) is c.PreparationResult)
            projection = _project(source)
            saved = _detach(projection)
            _source(saved)
        except _INVALID:
            return _issue(reject, RetentionReason.INVALID_C_SOURCE)
        if saved.state is c.PreparationState.UNRESOLVED:
            return _issue(unknown, RetentionReason.UPSTREAM_UNRESOLVED, saved)
        if saved.state is not c.PreparationState.PREPARED:
            return _issue(reject, RetentionReason.NOT_PREPARED, saved)
        if not _stable(source, projection) or not self._composition_stable():
            return _issue(unknown, RetentionReason.INSTABILITY, saved)
        if _namespace(saved) != self._authority:
            return _issue(unknown, RetentionReason.ELIGIBILITY_UNQUALIFIED, saved)
        request = _detach(projection)
        try:
            response = self._verify(request)
        except _AVAILABILITY:
            reason = (RetentionReason.ELIGIBILITY_UNAVAILABLE if _stable(source, projection)
                      and _stable(request, projection) and self._composition_stable() else RetentionReason.INSTABILITY)
            return _issue(unknown, reason, saved, verified=True)
        if not _stable(source, projection) or not _stable(request, projection) or not self._composition_stable():
            return _issue(unknown, RetentionReason.INSTABILITY, saved, verified=True)
        response_projection = None
        malformed = False
        try:
            _require(type(response) is EligibilityQualification)
            response_projection = _project(response)
            eligibility = _detach(response_projection)
            _eligibility(eligibility, saved, self._authority, self._implementation)
        except _INVALID:
            malformed = True
        if response_projection is not None and not _stable(response, response_projection):
            return _issue(unknown, RetentionReason.INSTABILITY, saved, verified=True)
        if malformed:
            return _issue(unknown, RetentionReason.ELIGIBILITY_MALFORMED, saved, verified=True)
        if eligibility.validity is not s.EvidenceValidity.VALID:
            return _issue(unknown, RetentionReason.ELIGIBILITY_UNQUALIFIED, saved, eligibility, verified=True)
        h = eligibility.history
        if h is AssociationHistory.EXACT_EXISTING:
            return _issue(retained, RetentionReason.RETAINED_EXACT_EXISTING, saved, eligibility, verified=True)
        if h is AssociationHistory.UNKNOWN_HISTORY:
            return _issue(unknown, eligibility.reason, saved, eligibility, verified=True)
        if h in (AssociationHistory.CONFLICT, AssociationHistory.PROVEN_PRE_DISPATCH_FAILURE):
            return _issue(reject, eligibility.reason, saved, eligibility, verified=True)
        if eligibility.progression is not ProgressionStatus.CLEAR:
            state = reject if eligibility.progression is ProgressionStatus.PROHIBITED else unknown
            return _issue(state, eligibility.reason, saved, eligibility, verified=True)
        candidate = _copy(saved.prepared.candidate)
        candidate_projection = _project(candidate)
        if (not _stable(source, projection) or not _stable(request, projection)
                or not _stable(response, response_projection)
                or not _stable(candidate, candidate_projection) or not self._composition_stable()):
            return _issue(unknown, RetentionReason.INSTABILITY, saved, eligibility, verified=True)
        # Fallback knowledge and signal are allocated BEFORE possible-effect entry.
        fallback = _issue(unknown, RetentionReason.PROGRAMMING_DEFECT, saved, eligibility,
                          invoked=True, verified=True)
        interrupted = _RetentionEvaluationInterrupted(fallback)
        observation = disposition = None
        qualification_attempted = False
        try:
            # This is the single syntactic association-call site. Callable entry
            # means possible dispatch, never proof of dispatch/non-dispatch.
            try:
                returned = self._associate(candidate)
                kind = ObservationKind.RETURNED_CANDIDATE
            except _AVAILABILITY as error:
                returned = None
                kind = (ObservationKind.CAPABILITY_UNAVAILABLE if type(error) is s.CapabilityUnavailable else
                        ObservationKind.TIMEOUT if type(error) is TimeoutError else ObservationKind.EXTERNAL_UNAVAILABLE)
            if (not _stable(source, projection) or not _stable(request, projection)
                    or not _stable(candidate, candidate_projection)
                    or not _stable(response, response_projection) or not self._composition_stable()):
                return _issue(unknown, RetentionReason.INSTABILITY, saved, eligibility, invoked=True, verified=True)
            if kind is ObservationKind.RETURNED_CANDIDATE:
                try:
                    _require(type(returned) is s.CheckpointCandidate)
                    returned_projection = _project(returned)
                    copied_return = _detach(returned_projection)
                    s.verify_candidate_association(saved.prepared.candidate, copied_return)
                    _require(_stable(returned, returned_projection))
                except _INVALID:
                    observation = AssociationObservation(_copy(saved), _copy(eligibility),
                                                         ObservationKind.MALFORMED_RETURN, None)
                    return _issue(unknown, RetentionReason.CONFIRMATION_UNBOUND, saved, eligibility,
                                  observation, invoked=True, verified=True)
            else:
                copied_return = None
            observation = AssociationObservation(_copy(saved), _copy(eligibility), kind, copied_return)
            observed_projection = _project(observation)
            qs, qe, qo = _copy(saved), _copy(eligibility), _copy(observation)
            ps, pe, po = _project(qs), _project(qe), _project(qo)
            qualification_attempted = True
            try:
                confirmation = self._qualify(qs, qe, qo)
            except _AVAILABILITY:
                changed = (not _stable(qs, ps) or not _stable(qe, pe) or not _stable(qo, po)
                    or not _stable(source, projection) or not _stable(request, projection)
                    or not _stable(response, response_projection)
                    or not _stable(candidate, candidate_projection)
                    or (kind is ObservationKind.RETURNED_CANDIDATE and not _stable(returned, returned_projection))
                    or not self._composition_stable())
                return _issue(unknown, RetentionReason.INSTABILITY if changed else RetentionReason.CONFIRMATION_UNAVAILABLE,
                              saved, eligibility, observation, invoked=True, verified=True, qualified=True)
            if (not _stable(qs, ps) or not _stable(qe, pe) or not _stable(qo, po)
                    or not _stable(source, projection) or not _stable(request, projection)
                    or not _stable(response, response_projection)
                    or not _stable(candidate, candidate_projection)
                    or (kind is ObservationKind.RETURNED_CANDIDATE and not _stable(returned, returned_projection))
                    or not self._composition_stable() or not _stable(observation, observed_projection)):
                return _issue(unknown, RetentionReason.INSTABILITY, saved, eligibility, observation,
                              invoked=True, verified=True, qualified=True)
            confirmation_projection = None
            malformed = False
            try:
                _require(type(confirmation) is AssociationQualification)
                confirmation_projection = _project(confirmation)
                checked = _detach(confirmation_projection)
                _disposition(checked, observation, self._authority, self._implementation)
            except _INVALID:
                malformed = True
            if confirmation_projection is not None and not _stable(confirmation, confirmation_projection):
                return _issue(unknown, RetentionReason.INSTABILITY, saved, eligibility, observation,
                              invoked=True, verified=True, qualified=True)
            if malformed:
                return _issue(unknown, RetentionReason.CONFIRMATION_MALFORMED, saved, eligibility, observation,
                              invoked=True, verified=True, qualified=True)
            if checked.validity is not s.EvidenceValidity.VALID:
                return _issue(unknown, RetentionReason.CONFIRMATION_UNBOUND, saved, eligibility, observation,
                              invoked=True, verified=True, qualified=True)
            disposition = checked
            state = (retained if checked.disposition is AssociationDisposition.RETAINED else
                     reject if checked.disposition is AssociationDisposition.PROVEN_NON_DISPATCH else unknown)
            return _issue(state, checked.reason, saved, eligibility, observation, disposition,
                          invoked=True, verified=True, qualified=True)
        except BaseException as error:
            # No dependency is invoked here. Preserve available qualified facts
            # when allocation permits; otherwise the preallocated fallback remains.
            try:
                interrupted.result = _issue(unknown, RetentionReason.PROGRAMMING_DEFECT,
                    saved, eligibility, observation, disposition, invoked=True,
                    verified=True, qualified=qualification_attempted)
            except BaseException:
                pass
            raise interrupted from error
