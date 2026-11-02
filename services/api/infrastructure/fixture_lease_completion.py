"""One original-permit completion in a qualified uninterrupted orchestration.

Composition authenticates continuity; constructors, copied evidence and fresh
owners do not. Native local entry control is neither a journal nor restart
authority. Results are knowledge only and grant no downstream permission.
"""
from dataclasses import dataclass, fields
from enum import StrEnum
import _thread
import sys
import types

from . import fixture_lease_publication as f

service, outcomes = f.service, f.o
V = service.EvidenceValidity


class CompletionState(StrEnum):
    COMPLETED = 'COMPLETED'
    NOT_SUBMITTED = 'NOT_SUBMITTED'
    DEFINITELY_REJECTED = 'DEFINITELY_REJECTED'
    UNRESOLVED = 'UNRESOLVED'


class CompletionReason(StrEnum):
    COMPLETED = 'COMPLETED'
    INVALID_F_SOURCE = 'INVALID_F_SOURCE'
    F_NOT_PUBLISHED = 'F_NOT_PUBLISHED'
    F_UNRESOLVED = 'F_UNRESOLVED'
    COMPOSITION_UNAVAILABLE = 'COMPOSITION_UNAVAILABLE'
    F_PROVENANCE_INVALID = 'F_PROVENANCE_INVALID'
    F_PROVENANCE_UNKNOWN = 'F_PROVENANCE_UNKNOWN'
    ELIGIBILITY_UNAVAILABLE = 'ELIGIBILITY_UNAVAILABLE'
    ELIGIBILITY_MALFORMED = 'ELIGIBILITY_MALFORMED'
    ELIGIBILITY_BINDING_MISMATCH = 'ELIGIBILITY_BINDING_MISMATCH'
    ELIGIBILITY_UNQUALIFIED = 'ELIGIBILITY_UNQUALIFIED'
    PUBLICATION_UNQUALIFIED = 'PUBLICATION_UNQUALIFIED'
    HISTORICAL_EVIDENCE_CONTRADICTION = 'HISTORICAL_EVIDENCE_CONTRADICTION'
    HISTORICAL_EVIDENCE_UNQUALIFIED = 'HISTORICAL_EVIDENCE_UNQUALIFIED'
    COMPLETION_BINDING_UNQUALIFIED = 'COMPLETION_BINDING_UNQUALIFIED'
    PROGRESSION_PROHIBITED = 'PROGRESSION_PROHIBITED'
    PROGRESSION_UNKNOWN = 'PROGRESSION_UNKNOWN'
    CONTINUITY_UNQUALIFIED = 'CONTINUITY_UNQUALIFIED'
    CONTINUITY_LOST = 'CONTINUITY_LOST'
    COMPLETION_ALREADY_ENTERED = 'COMPLETION_ALREADY_ENTERED'
    COMPLETION_ALREADY_CLOSED = 'COMPLETION_ALREADY_CLOSED'
    COMPETING_EXECUTION = 'COMPETING_EXECUTION'
    CONTINUITY_CONTRADICTION = 'CONTINUITY_CONTRADICTION'
    SOURCE_INSTABILITY = 'SOURCE_INSTABILITY'
    REQUEST_INSTABILITY = 'REQUEST_INSTABILITY'
    RESPONSE_INSTABILITY = 'RESPONSE_INSTABILITY'
    DEPENDENCY_INSTABILITY = 'DEPENDENCY_INSTABILITY'
    DISPOSITION_INSTABILITY = 'DISPOSITION_INSTABILITY'
    EFFECT_EVIDENCE_INSTABILITY = 'EFFECT_EVIDENCE_INSTABILITY'
    QUALIFICATION_UNAVAILABLE = 'QUALIFICATION_UNAVAILABLE'
    QUALIFICATION_MALFORMED = 'QUALIFICATION_MALFORMED'
    QUALIFICATION_BINDING_MISMATCH = 'QUALIFICATION_BINDING_MISMATCH'
    QUALIFICATION_UNQUALIFIED = 'QUALIFICATION_UNQUALIFIED'
    CANONICAL_DISPOSITION_CONTRADICTION = 'CANONICAL_DISPOSITION_CONTRADICTION'
    EXTERNAL_DEFINITELY_REJECTED = 'EXTERNAL_DEFINITELY_REJECTED'
    COMPLETION_UNKNOWN = 'COMPLETION_UNKNOWN'
    EVALUATION_INTERRUPTED = 'EVALUATION_INTERRUPTED'
    ENTRY_INTERRUPTED = 'ENTRY_INTERRUPTED'
    ENTRY_STATE_UNKNOWN = 'ENTRY_STATE_UNKNOWN'


class ContinuityStatus(StrEnum):
    PENDING = 'PENDING'
    MISSING = 'MISSING'
    LOST = 'LOST'
    EARLIER_ENTRY = 'EARLIER_ENTRY'
    CLOSED = 'CLOSED'
    COMPETING = 'COMPETING'
    CONTRADICTORY = 'CONTRADICTORY'


class EntryDecision(StrEnum):
    ENTERED_NOW = 'ENTERED_NOW'
    ALREADY_ENTERED = 'ALREADY_ENTERED'
    BINDING_MISMATCH = 'BINDING_MISMATCH'
    BUSY = 'BUSY'


class _EntryState(StrEnum):
    PENDING = 'PENDING'
    ENTERED = 'ENTERED'


class CompletionObservationKind(StrEnum):
    RETURNED = 'RETURNED'
    MALFORMED_RETURN = 'MALFORMED_RETURN'
    UNBOUND_RETURN = 'UNBOUND_RETURN'
    CAPABILITY_UNAVAILABLE = 'CAPABILITY_UNAVAILABLE'
    EXTERNAL_UNAVAILABLE = 'EXTERNAL_UNAVAILABLE'
    TIMEOUT = 'TIMEOUT'


class _EvaluationBinding:
    __slots__ = ()
    def __new__(cls): raise TypeError('Evaluator-local correlation only')
    def __copy__(self): raise TypeError('Evaluator-local correlation only')
    def __deepcopy__(self, memo): raise TypeError('Evaluator-local correlation only')
    def __reduce_ex__(self, protocol): raise TypeError('Not serializable')


@dataclass(frozen=True, repr=False)
class TrustedCompletionAdapter:
    authority: service.EvidenceReference
    implementation: service.EvidenceReference
    verify: object
    complete: object
    qualify: object


@dataclass(frozen=True, repr=False)
class _CompletionOwnerBinding:
    source: f.PublicationResult
    operation: service.OriginalOperation
    publication: service.PublicationResult
    authority: service.EvidenceReference
    implementation: service.EvidenceReference


@dataclass(frozen=True, repr=False)
class CompletionRequest:
    source: f.PublicationResult
    operation: service.OriginalOperation
    publication: service.PublicationResult
    authority: service.EvidenceReference
    implementation: service.EvidenceReference
    owner_binding: _CompletionOwnerBinding
    evaluation_binding: _EvaluationBinding


@dataclass(frozen=True, repr=False)
class CompletionEligibilityAssessment:
    request: CompletionRequest
    authority: service.EvidenceReference
    implementation: service.EvidenceReference
    validity: service.EvidenceValidity
    reference: service.EvidenceReference | None
    source_provenance: service.EvidenceValidity
    publication_confirmation: service.EvidenceValidity
    historical_evidence: service.EvidenceValidity
    completion_binding: service.EvidenceValidity
    normal_progression: service.EvidenceValidity
    continuity_qualification: service.EvidenceValidity
    continuity: ContinuityStatus


@dataclass(frozen=True, repr=False)
class CompletionObservation:
    request: CompletionRequest
    eligibility: CompletionEligibilityAssessment
    kind: CompletionObservationKind
    returned: service.CompletionResult | None


@dataclass(frozen=True, repr=False)
class CompletionQualificationAssessment:
    observation: CompletionObservation
    authority: service.EvidenceReference
    implementation: service.EvidenceReference
    validity: service.EvidenceValidity
    reference: service.EvidenceReference | None
    completion: service.CompletionResult | None


@dataclass(frozen=True, repr=False)
class _CompletionPayload:
    source: f.PublicationResult | None
    request: CompletionRequest | None
    eligibility: CompletionEligibilityAssessment | None
    owner_entry_attempted: bool
    entry_decision: EntryDecision | None
    observation: CompletionObservation | None
    qualification: CompletionQualificationAssessment | None
    canonical_observation: outcomes.Disposition | None
    disposition: outcomes.Disposition | None
    reconciliation_required: bool


@dataclass(frozen=True, repr=False, init=False)
class CompletionResult:
    state: CompletionState
    reason: CompletionReason
    verification_attempted: bool
    completion_entry_consumed: bool
    completion_invoked: bool
    qualification_attempted: bool
    disposition_evaluated: bool
    next_required_gate: outcomes.RequiredGate
    completed: _CompletionPayload | None
    not_submitted: _CompletionPayload | None
    rejected: _CompletionPayload | None
    unresolved: _CompletionPayload | None

    def __init__(self, *args, **kwargs): raise TypeError('Use complete_original')
    def __init_subclass__(cls, **kwargs): raise TypeError('Closed completion result')
    def __copy__(self): raise TypeError('Use complete_original')
    def __deepcopy__(self, memo): raise TypeError('Use complete_original')
    def __bool__(self): raise TypeError('Knowledge is not permission')
    def __reduce_ex__(self, protocol): raise TypeError('Not serializable')


_PERMISSIONS = ('permit_acquisition_permitted', 'permit_reacquisition_permitted',
    'permit_renewal_permitted', 'permit_cancellation_permitted', 'publication_permitted',
    'cas_permitted', 'publication_query_permitted', 'publication_retry_permitted',
    'completion_permitted', 'completion_retry_permitted', 'completion_query_permitted',
    'ack_construction_permitted', 'ack_delivery_permitted', 'ack_redelivery_permitted',
    'delivery_qualification_permitted', 'recovery_execution_permitted',
    'fence_clearance_permitted', 'runtime_progression_permitted',
    'candidate_retention_permitted', 'local_mutation_permitted')
for _name in _PERMISSIONS:
    setattr(CompletionResult, _name, property(lambda self: False))


class _CompletionEvaluationInterrupted(BaseException):
    def __init__(self, result):
        self.result = result
        super().__init__('Original completion interrupted; reconciliation required')


class _Malformed(ValueError):
    pass


S, R = CompletionState, CompletionReason
_LEGAL_FLAGS = tuple(tuple(character == '1' for character in text)
    for text in ('00000', '10000', '11000', '11100', '11110', '11111'))
_REASON_FLAGS = (
    (R.COMPLETED, _LEGAL_FLAGS[5:]),
    (R.INVALID_F_SOURCE, _LEGAL_FLAGS[:1]),
    (R.F_NOT_PUBLISHED, _LEGAL_FLAGS[:1]),
    (R.F_UNRESOLVED, _LEGAL_FLAGS[:1]),
    (R.COMPOSITION_UNAVAILABLE, _LEGAL_FLAGS[:1]),
    (R.F_PROVENANCE_INVALID, _LEGAL_FLAGS[1:2]),
    (R.F_PROVENANCE_UNKNOWN, _LEGAL_FLAGS[1:2]),
    (R.ELIGIBILITY_UNAVAILABLE, _LEGAL_FLAGS[1:2]),
    (R.ELIGIBILITY_MALFORMED, _LEGAL_FLAGS[1:2]),
    (R.ELIGIBILITY_BINDING_MISMATCH, _LEGAL_FLAGS[1:2]),
    (R.ELIGIBILITY_UNQUALIFIED, _LEGAL_FLAGS[1:2]),
    (R.PUBLICATION_UNQUALIFIED, _LEGAL_FLAGS[1:2]),
    (R.HISTORICAL_EVIDENCE_CONTRADICTION, _LEGAL_FLAGS[1:2]),
    (R.HISTORICAL_EVIDENCE_UNQUALIFIED, _LEGAL_FLAGS[1:2]),
    (R.COMPLETION_BINDING_UNQUALIFIED, _LEGAL_FLAGS[1:2]),
    (R.PROGRESSION_PROHIBITED, _LEGAL_FLAGS[:2]),
    (R.PROGRESSION_UNKNOWN, _LEGAL_FLAGS[1:2]),
    (R.CONTINUITY_UNQUALIFIED, _LEGAL_FLAGS[1:2]),
    (R.CONTINUITY_LOST, _LEGAL_FLAGS[1:2]),
    (R.COMPLETION_ALREADY_ENTERED, _LEGAL_FLAGS[1:3]),
    (R.COMPLETION_ALREADY_CLOSED, _LEGAL_FLAGS[1:2]),
    (R.COMPETING_EXECUTION, _LEGAL_FLAGS[1:2]),
    (R.CONTINUITY_CONTRADICTION, _LEGAL_FLAGS[1:2]),
    (R.SOURCE_INSTABILITY, _LEGAL_FLAGS),
    (R.REQUEST_INSTABILITY, _LEGAL_FLAGS),
    (R.RESPONSE_INSTABILITY, _LEGAL_FLAGS[1:]),
    (R.DEPENDENCY_INSTABILITY, _LEGAL_FLAGS),
    (R.DISPOSITION_INSTABILITY, _LEGAL_FLAGS[5:]),
    (R.EFFECT_EVIDENCE_INSTABILITY, _LEGAL_FLAGS[1:]),
    (R.QUALIFICATION_UNAVAILABLE, _LEGAL_FLAGS[4:5]),
    (R.QUALIFICATION_MALFORMED, _LEGAL_FLAGS[4:5]),
    (R.QUALIFICATION_BINDING_MISMATCH, _LEGAL_FLAGS[4:5]),
    (R.QUALIFICATION_UNQUALIFIED, _LEGAL_FLAGS[5:]),
    (R.CANONICAL_DISPOSITION_CONTRADICTION, _LEGAL_FLAGS[5:]),
    (R.EXTERNAL_DEFINITELY_REJECTED, _LEGAL_FLAGS[5:]),
    (R.COMPLETION_UNKNOWN, _LEGAL_FLAGS[5:]),
    (R.EVALUATION_INTERRUPTED, _LEGAL_FLAGS[3:]),
    (R.ENTRY_INTERRUPTED, _LEGAL_FLAGS[2:3]),
    (R.ENTRY_STATE_UNKNOWN, _LEGAL_FLAGS[1:2]),
)
_INVALID = (_Malformed,) + f._INVALID
_AVAILABILITY = f._AVAILABILITY
_ENUMS = f._ENUMS + (ContinuityStatus, EntryDecision, CompletionObservationKind,
    CompletionState, CompletionReason)
_VALUES = f._VALUES + (_CompletionOwnerBinding, CompletionRequest,
    CompletionEligibilityAssessment, CompletionObservation,
    CompletionQualificationAssessment, _CompletionPayload, CompletionResult)
_ATOMS = f._ATOMS + (_EvaluationBinding,)
_ATOM_IDS = {id(cls): cls for cls in _ATOMS}
_ENUM_MEMBERS = {id(cls): (cls, tuple(cls)) for cls in _ENUMS}
# Incorporate the frozen descriptors, rather than discovering new upstream fields.
_FIELD_TYPES = dict(f._FIELD_TYPES)
_FIELD_TYPES.update({id(cls): (cls, tuple((field.name, field.type) for field in fields(cls)))
    for cls in _VALUES if not any(cls is old for old in f._VALUES)})


def _require(condition):
    if not condition: raise _Malformed()


def _project(value):
    active, memo = set(), {}
    def visit(item):
        kind = type(item)
        if _ATOM_IDS.get(id(kind)) is kind: return kind, item
        enum = _ENUM_MEMBERS.get(id(kind))
        if enum is not None and enum[0] is kind:
            _require(any(item is member for member in enum[1]))
            return kind, item
        schema = _FIELD_TYPES.get(id(kind))
        _require(kind is tuple or (schema is not None and schema[0] is kind))
        identity = id(item)
        _require(identity not in active)
        if identity in memo: return memo[identity]
        active.add(identity)
        if kind is tuple:
            result = kind, tuple(visit(child) for child in item)
        else:
            children = []
            for name, annotation in schema[1]:
                try: child = object.__getattribute__(item, name)
                except AttributeError: raise _Malformed() from None
                node = visit(child)
                _require(type(child) is annotation or f.c._matches(child, annotation))
                children.append((name, node))
            result = kind, tuple(children)
        active.remove(identity)
        memo[identity] = result
        return result
    try:
        return visit(value)
    finally:
        # Break the recursive closure's private memo cycle promptly. Accepted
        # records/aliases remain owned by the returned projection, not this memo.
        visit = None


def _detach(projection):
    memo = {}
    def detach(node):
        kind, data = node
        if _ATOM_IDS.get(id(kind)) is kind or id(kind) in _ENUM_MEMBERS: return data
        if id(node) in memo: return memo[id(node)]
        if kind is tuple:
            result = tuple(detach(child) for child in data)
        else:
            result = object.__new__(kind)
            for name, child in data: object.__setattr__(result, name, detach(child))
        memo[id(node)] = result
        return result
    try:
        return detach(projection)
    finally:
        detach = None


def _equal(left, right):
    seen = set()
    def compare(a, b):
        if a is b: return True
        kind, data = a
        other, value = b
        if kind is not other: return False
        if id(kind) in _ENUM_MEMBERS or kind not in (type(None), str, bytes, int, bool) and id(kind) in _ATOM_IDS:
            return data is value
        if id(kind) in _ATOM_IDS: return data == value
        pair = id(a), id(b)
        if pair in seen: return True
        seen.add(pair)
        if len(data) != len(value): return False
        if kind is tuple: return all(compare(x, y) for x, y in zip(data, value))
        return all(name == other_name and compare(x, y)
                   for (name, x), (other_name, y) in zip(data, value))
    try:
        return compare(left, right)
    finally:
        compare = None


def _copy(value): return _detach(_project(value))
def _same(left, right): return _equal(_project(left), _project(right))


def _reference(value):
    _require(type(value) is service.EvidenceReference)
    f._reference(value)


def _values_valid(value):
    """Canonical value consistency, never cached provenance or eligibility.

    Independent copies of an identical closed value have the same pure value
    invariant. Keep their successful checks local to this traversal; correlation
    atoms remain identity-sensitive. This does not cache a gate's authority or
    avoid the separately required provenance, continuity or outcome assessment.
    """
    seen, validated = set(), {}
    projection = _project(value)
    def validate(item, node):
        kind = type(item)
        if id(kind) in _ATOM_IDS or id(kind) in _ENUM_MEMBERS: return
        if id(item) in seen: return
        seen.add(id(item))
        if kind is tuple:
            for child, child_node in zip(item, node[1]): validate(child, child_node)
        else:
            for name, child_node in node[1]:
                validate(object.__getattribute__(item, name), child_node)
            validator = _VALIDATORS.get(id(kind))
            if validator is not None:
                previous = validated.setdefault(id(kind), [])
                if not any(_equal(node, old) for old in previous):
                    validator(item)
                    previous.append(node)
    try:
        validate(value, projection)
    finally:
        validate = None


_VALIDATORS = {id(cls): cls.__post_init__ for cls in _VALUES if hasattr(cls, '__post_init__')}


def _source(source):
    """Structure first, root second, progression fence third, positive agreement last.

    This proves no issuance; the independent verifier still authenticates F.
    """
    _require(type(source) is f.PublicationResult)
    _values_valid(source)
    expected = ((f.S.PUBLISHED, 'published', f._PublishedCheckpoint),
        (f.S.NOT_SUBMITTED, 'not_submitted', f._NotSubmittedCheckpoint),
        (f.S.DEFINITELY_REJECTED, 'rejected', f._RejectedCheckpoint),
        (f.S.UNRESOLVED, 'unresolved', f._UnresolvedCheckpoint))
    selected = next((item for item in expected if source.state is item[0]), None)
    _require(selected is not None)
    _require(sum(value is not None for value in (source.published, source.not_submitted,
        source.rejected, source.unresolved)) == 1)
    payload = object.__getattribute__(source, selected[1])
    _require(type(payload) is selected[2])
    _require(not source.gate_evaluated or source.verification_attempted)
    _require(not source.publication_invoked or source.gate_evaluated)
    _require(not source.qualification_attempted or source.publication_invoked)
    if source.state is not f.S.PUBLISHED:
        _require(source.reason is not f.R.PUBLISHED)
        if payload.source is not None: f._source(payload.source)
        if source.state is f.S.UNRESOLVED: _require(payload.reconciliation_required)
        disposition = (None if source.state is f.S.NOT_SUBMITTED else payload.disposition)
        canonical = f._issue(source.state, source.reason, source=payload.source,
            dispatch=payload.dispatch, observation=payload.observation,
            qualification=payload.qualification, disposition=disposition,
            verified=source.verification_attempted, evaluated=source.gate_evaluated,
            invoked=source.publication_invoked, qualified=source.qualification_attempted)
        _require(_same(canonical, source))
        return R.F_UNRESOLVED if source.state is f.S.UNRESOLVED else R.F_NOT_PUBLISHED
    _require(source.reason is f.R.PUBLISHED and source.verification_attempted
        and source.gate_evaluated and source.publication_invoked and source.qualification_attempted)
    # Read flags only after exact fixed-field/value validation; never clear a fence.
    fence = False
    visited = set()
    def fenced(item):
        nonlocal fence
        kind = type(item)
        if id(kind) in _ATOM_IDS or id(kind) in _ENUM_MEMBERS or id(item) in visited: return
        visited.add(id(item))
        if kind is tuple:
            for child in item: fenced(child)
            return
        for name, _ in _FIELD_TYPES[id(kind)][1]:
            child = object.__getattribute__(item, name)
            if name == 'reconciliation_required' and child is True: fence = True
            if kind is outcomes.Disposition and name in ('recovery', 'prior_recovery') and child is not None:
                fence = True
            fenced(child)
    fenced(source)
    if fence: return R.PROGRESSION_PROHIBITED
    _require(f._source(payload.source) is False)
    _require(payload.dispatch.validity is V.VALID and payload.dispatch.source_provenance is V.VALID)
    f._assessment(payload.dispatch)
    _require(_same(payload.dispatch.request.source, payload.source))
    _require(f.e._bindings(payload.source.qualified.source, payload.dispatch.inputs) is None)
    _require(f._coverage(payload.dispatch, payload.dispatch.request,
        payload.dispatch.authority, payload.dispatch.implementation) is None)
    gate = f.g.evaluate_publication_gate(payload.dispatch.inputs)
    _require(gate.state is f.g.GateState.SATISFIED)
    _require(payload.observation.dispatch.validity is V.VALID
        and _same(payload.observation.dispatch, payload.dispatch)
        and _same(payload.observation.request, payload.dispatch.request))
    _require(f._disposition(payload.qualification, payload.observation,
        payload.dispatch.authority, payload.dispatch.implementation) is None)
    _require(payload.qualification.validity is V.VALID
        and payload.qualification.disposition is f.PublicationDispositionKind.CONFIRMED)
    publication = payload.qualification.publication
    _require(type(publication) is service.PublicationResult
        and publication.outcome is service.ExternalOutcome.CONFIRMED)
    service.verify_publication_result(payload.dispatch.inputs.candidate, publication)
    disposition = payload.disposition
    _require(disposition.stage is outcomes.Stage.PUBLICATION
        and disposition.local_commit is outcomes.LocalCommitState.CONFIRMED
        and disposition.outcome is service.ExternalOutcome.CONFIRMED
        and disposition.required_gate is outcomes.RequiredGate.ORIGINAL_COMPLETION
        and _same(disposition.publication, publication)
        and _same(disposition.candidate, publication.candidate))
    return None


def _operation(source):
    publication = source.published.qualification.publication
    return service.OriginalOperation(publication.candidate.envelope.permit_reference,
        service.OperationKind.PERMIT_COMPLETION)


_LOCK_ALLOCATE, _LOCK_TYPE = _thread.allocate_lock, _thread.LockType
_LOCK_ACQUIRE, _LOCK_RELEASE = _thread.LockType.acquire, _thread.LockType.release
_MEMBER_TYPE = types.MemberDescriptorType
_MEMBER_GET, _MEMBER_SET = types.MemberDescriptorType.__get__, types.MemberDescriptorType.__set__
_DICT_GET, _PROXY_GET = dict.get, types.MappingProxyType.get
_DICT_ITEMS, _PROXY_ITEMS = dict.items, types.MappingProxyType.items
_NATIVE_NEW, _NATIVE_DICT_SET = object.__new__, dict.__setitem__
_NATIVE_STORAGE_GET = types.GetSetDescriptorType.__get__
_EXCEPTION_NEW, _EXCEPTION_INIT = BaseException.__new__, BaseException.__init__


def _identity_lookup(mapping, key, dict_items=_DICT_ITEMS, proxy_items=_PROXY_ITEMS,
                     dict_type=dict, type_of=type, missing=object()):
    # Never hash or compare a live stored key. The manifest owns exact key identities.
    entries = dict_items(mapping) if type_of(mapping) is dict_type else proxy_items(mapping)
    for stored, value in entries:
        if stored is key: return value
    return missing


class _CompletionEntryOwner:
    __slots__ = ('_binding', '_lock', '_state')

    def __init__(self, source, *, authority, implementation):
        try:
            _MEMBER_GET(_OWNER_BINDING_SLOT, self, _CompletionEntryOwner)
        except AttributeError:
            pass
        else:
            raise TypeError('Completion entry owner cannot be reinitialized')
        try:
            saved = _copy(source)
            _require(_source(saved) is None)
            _reference(authority); _reference(implementation)
            namespace = f.d._namespace(saved.published.source.qualified.source.retained.source)
            _require(_same(namespace, authority))
            binding = _CompletionOwnerBinding(saved, _operation(saved),
                _copy(saved.published.qualification.publication), _copy(authority), _copy(implementation))
        except _INVALID:
            raise TypeError('Malformed completion owner composition') from None
        object.__setattr__(self, '_binding', binding)
        object.__setattr__(self, '_lock', _LOCK_ALLOCATE())
        object.__setattr__(self, '_state', _EntryState.PENDING)

    def __init_subclass__(cls, **kwargs): raise TypeError('Closed entry owner')
    def __setattr__(self, name, value): raise TypeError('No supported owner mutation/reset')
    def __delattr__(self, name): raise TypeError('No supported owner mutation/reset')
    def __copy__(self): raise TypeError('Owner is orchestration-local')
    def __deepcopy__(self, memo): raise TypeError('Owner is orchestration-local')
    def __reduce_ex__(self, protocol): raise TypeError('Owner is not serializable')

    def try_enter(self, expected_binding, expected_lock):
        if (_MEMBER_GET(_OWNER_BINDING_SLOT, self, _CompletionEntryOwner) is not expected_binding
                or _MEMBER_GET(_OWNER_LOCK_SLOT, self, _CompletionEntryOwner) is not expected_lock):
            return EntryDecision.BINDING_MISMATCH
        if not _LOCK_ACQUIRE(expected_lock, False): return EntryDecision.BUSY
        try:
            if (_MEMBER_GET(_OWNER_BINDING_SLOT, self, _CompletionEntryOwner) is not expected_binding
                    or _MEMBER_GET(_OWNER_LOCK_SLOT, self, _CompletionEntryOwner) is not expected_lock):
                return EntryDecision.BINDING_MISMATCH
            state = _MEMBER_GET(_OWNER_STATE_SLOT, self, _CompletionEntryOwner)
            if state is _EntryState.ENTERED: return EntryDecision.ALREADY_ENTERED
            _require(state is _EntryState.PENDING)
            _MEMBER_SET(_OWNER_STATE_SLOT, self, _EntryState.ENTERED)
            return EntryDecision.ENTERED_NOW
        finally:
            _LOCK_RELEASE(expected_lock)


_OWNER_BINDING_SLOT = _CompletionEntryOwner.__dict__['_binding']
_OWNER_LOCK_SLOT = _CompletionEntryOwner.__dict__['_lock']
_OWNER_STATE_SLOT = _CompletionEntryOwner.__dict__['_state']


def _issue(reason, flags=(False, False, False, False, False), *, source=None,
           request=None, eligibility=None, attempted=False, decision=None,
           observation=None, qualification=None, canonical=None, disposition=None,
           carrier=False):
    _require(type(reason) is R and type(flags) is tuple and len(flags) == 5
        and all(type(flag) is bool for flag in flags))
    _require(any(reason is member and flags in legal for member, legal in _REASON_FLAGS))
    _require(flags in ((False, False, False, False, False), (True, False, False, False, False),
        (True, True, False, False, False), (True, True, True, False, False),
        (True, True, True, True, False), (True, True, True, True, True)))
    interrupted = reason in (R.ENTRY_INTERRUPTED, R.ENTRY_STATE_UNKNOWN, R.EVALUATION_INTERRUPTED)
    _require(not interrupted or carrier)
    state = (S.COMPLETED if reason is R.COMPLETED else S.DEFINITELY_REJECTED
        if reason is R.EXTERNAL_DEFINITELY_REJECTED else S.NOT_SUBMITTED
        if reason in (R.INVALID_F_SOURCE, R.F_NOT_PUBLISHED, R.F_PROVENANCE_INVALID)
        else S.UNRESOLVED)
    if state in (S.COMPLETED, S.DEFINITELY_REJECTED):
        _require(all(flags) and type(disposition) is outcomes.Disposition)
        _require(type(source) is f.PublicationResult and type(request) is CompletionRequest
            and type(eligibility) is CompletionEligibilityAssessment
            and type(observation) is CompletionObservation
            and type(qualification) is CompletionQualificationAssessment
            and type(canonical) is outcomes.Disposition
            and attempted is True and decision is EntryDecision.ENTERED_NOW
            and _same(canonical, disposition))
        _require(disposition.stage is outcomes.Stage.COMPLETION and qualification is not None
            and qualification.validity is V.VALID)
        _require(disposition.outcome is (service.ExternalOutcome.CONFIRMED
            if state is S.COMPLETED else service.ExternalOutcome.DEFINITELY_REJECTED))
        _require(disposition.required_gate is (outcomes.RequiredGate.CURRENT_DELIVERY_QUALIFICATION
            if state is S.COMPLETED else outcomes.RequiredGate.RECOVERY_HANDOFF))
    if state is S.NOT_SUBMITTED: _require(not flags[1] and not flags[2])
    if reason is R.ENTRY_INTERRUPTED: _require(flags == (True, True, False, False, False))
    if reason is R.ENTRY_STATE_UNKNOWN: _require(flags == (True, False, False, False, False))
    if reason is R.EVALUATION_INTERRUPTED: _require(flags[2])
    payload = _CompletionPayload(source, request, eligibility, attempted, decision, observation,
        qualification, canonical, disposition, state is not S.COMPLETED)
    result = object.__new__(CompletionResult)
    names = ('verification_attempted', 'completion_entry_consumed', 'completion_invoked',
        'qualification_attempted', 'disposition_evaluated')
    for name, value in zip(names, flags): object.__setattr__(result, name, value)
    object.__setattr__(result, 'state', state)
    object.__setattr__(result, 'reason', reason)
    object.__setattr__(result, 'next_required_gate', outcomes.RequiredGate.CURRENT_DELIVERY_QUALIFICATION
        if state is S.COMPLETED else outcomes.RequiredGate.RECOVERY_HANDOFF)
    for name, selected in (('completed', S.COMPLETED), ('not_submitted', S.NOT_SUBMITTED),
            ('rejected', S.DEFINITELY_REJECTED), ('unresolved', S.UNRESOLVED)):
        object.__setattr__(result, name, payload if state is selected else None)
    return _copy(result)


def _eligibility(value, request, authority, implementation):
    try:
        _require(type(value) is CompletionEligibilityAssessment)
        _project(value)
        for name in ('validity', 'source_provenance', 'publication_confirmation',
                'historical_evidence', 'completion_binding', 'normal_progression',
                'continuity_qualification'):
            _require(type(object.__getattribute__(value, name)) is V)
        _require(type(value.continuity) is ContinuityStatus)
        if value.reference is not None: _reference(value.reference)
        _require(value.validity is not V.VALID or value.reference is not None)
    except _INVALID:
        return R.ELIGIBILITY_MALFORMED
    if not (_same(value.request, request) and _same(value.authority, authority)
            and _same(value.implementation, implementation)
            and _same(request.owner_binding.source, request.source)
            and _same(request.owner_binding.operation, request.operation)
            and _same(request.owner_binding.publication, request.publication)
            and _same(request.owner_binding.authority, authority)
            and _same(request.owner_binding.implementation, implementation)):
        return R.ELIGIBILITY_BINDING_MISMATCH
    if value.validity is not V.VALID: return R.ELIGIBILITY_UNQUALIFIED
    if value.source_provenance is V.INVALID: return R.F_PROVENANCE_INVALID
    if value.source_provenance is V.UNKNOWN: return R.F_PROVENANCE_UNKNOWN
    if value.publication_confirmation is not V.VALID: return R.PUBLICATION_UNQUALIFIED
    if value.historical_evidence is V.INVALID: return R.HISTORICAL_EVIDENCE_CONTRADICTION
    if value.historical_evidence is V.UNKNOWN: return R.HISTORICAL_EVIDENCE_UNQUALIFIED
    if value.completion_binding is not V.VALID: return R.COMPLETION_BINDING_UNQUALIFIED
    if value.normal_progression is V.INVALID: return R.PROGRESSION_PROHIBITED
    if value.normal_progression is V.UNKNOWN: return R.PROGRESSION_UNKNOWN
    if value.continuity_qualification is not V.VALID or value.continuity is ContinuityStatus.MISSING:
        return R.CONTINUITY_UNQUALIFIED
    for member, reason in ((ContinuityStatus.PENDING, None),
            (ContinuityStatus.LOST, R.CONTINUITY_LOST),
            (ContinuityStatus.EARLIER_ENTRY, R.COMPLETION_ALREADY_ENTERED),
            (ContinuityStatus.CLOSED, R.COMPLETION_ALREADY_CLOSED),
            (ContinuityStatus.COMPETING, R.COMPETING_EXECUTION),
            (ContinuityStatus.CONTRADICTORY, R.CONTINUITY_CONTRADICTION)):
        if value.continuity is member: return reason
    raise _Malformed()


def _qualification(value, observation, authority, implementation):
    try:
        _require(type(value) is CompletionQualificationAssessment)
        _project(value)
        _require(type(value.validity) is V)
        if value.reference is not None: _reference(value.reference)
        if value.validity is V.VALID:
            _require(value.reference is not None and type(value.completion) is service.CompletionResult)
            service.CompletionResult.__post_init__(value.completion)
        else: _require(value.completion is None)
    except _INVALID:
        return R.QUALIFICATION_MALFORMED
    if not (_same(value.observation, observation) and _same(value.authority, authority)
            and _same(value.implementation, implementation)):
        return R.QUALIFICATION_BINDING_MISMATCH
    if value.validity is V.VALID:
        try:
            service.verify_completion_result(observation.request.operation,
                observation.request.publication, value.completion)
        except _INVALID:
            return R.QUALIFICATION_BINDING_MISMATCH
    return None


def _dependencies():
    module = sys.modules[__name__]
    names = ('_require', '_project', '_detach', '_equal', '_copy', '_same', '_reference',
        '_values_valid', '_source', '_operation', '_issue', '_eligibility', '_qualification',
        '_dependencies', '_tables', '_composition_stable', 'f', 'service', 'outcomes', 'V', 'S', 'R',
        '_INVALID', '_AVAILABILITY', '_VALUES', '_ATOMS', '_ENUMS', '_PERMISSIONS', '_VALIDATORS',
        '_LEGAL_FLAGS', '_REASON_FLAGS',
        'CompletionResult', 'CompletionRequest', 'CompletionEligibilityAssessment',
        'CompletionObservation', 'CompletionQualificationAssessment', '_CompletionPayload',
        '_CompletionOwnerBinding', '_EvaluationBinding', '_CompletionEvaluationInterrupted',
        'CompletionState', 'CompletionReason', 'ContinuityStatus', 'EntryDecision',
        'CompletionObservationKind', '_EntryState', '_CompletionEntryOwner',
        'TrustedCompletionAdapter', 'CheckpointCompleter', '_LOCK_ALLOCATE', '_LOCK_TYPE',
        '_LOCK_ACQUIRE', '_LOCK_RELEASE', '_MEMBER_TYPE', '_MEMBER_GET', '_MEMBER_SET',
        '_DICT_GET', '_PROXY_GET', '_DICT_ITEMS', '_PROXY_ITEMS', '_identity_lookup',
        '_NATIVE_NEW', '_NATIVE_DICT_SET', '_NATIVE_STORAGE_GET', '_EXCEPTION_NEW', '_EXCEPTION_INIT',
        '_OWNER_BINDING_SLOT', '_OWNER_LOCK_SLOT', '_OWNER_STATE_SLOT')
    groups = ((module, names), (service, ('verify_completion_result', 'CompletionResult')),
        (service.CompletionResult, ('__init__', '__post_init__')),
        (outcomes, ('completion_disposition',)),
        (_CompletionEntryOwner, ('__init__', 'try_enter', '_binding', '_lock', '_state',
            '__setattr__', '__delattr__', '__getattribute__', '__copy__', '__deepcopy__', '__reduce_ex__')),
        (CheckpointCompleter, ('__init__', 'complete_original')),
        (_thread, ('allocate_lock', 'LockType')),
        (_LOCK_TYPE, ('acquire', 'release')),
        (types, ('MemberDescriptorType', 'MappingProxyType', 'GetSetDescriptorType',
            'FunctionType', 'CellType')),
        (types.FunctionType, ('__defaults__', '__kwdefaults__', '__closure__')),
        (types.CellType, ('cell_contents',)),
        (types.MemberDescriptorType, ('__get__', '__set__')),
        (types.GetSetDescriptorType, ('__get__',)),
        (object, ('__new__',)), (BaseException, ('__new__', '__init__', '__dict__')),
        (_CompletionEvaluationInterrupted, ('__new__', '__init__')),
        (_identity_lookup, ('__defaults__',)),
        (dict, ('get', 'items', '__setitem__')),
        (types.MappingProxyType, ('get', 'items')),
        (_EntryState, ('PENDING', 'ENTERED')))
    bindings = f._dependencies() + tuple((owner, name, getattr(owner, name))
        for owner, names in groups for name in names)
    bindings += tuple((cls, '__init__', cls.__init__) for cls in _VALUES if cls not in f._VALUES)
    bindings += tuple((cls, name, getattr(cls, name)) for cls in _VALUES + _ENUMS + (_EntryState,)
        for name in ('__getattribute__', '__eq__', '__hash__'))
    bindings += tuple((cls, member.name, member) for cls in _ENUMS for member in _ENUM_MEMBERS[id(cls)][1])
    bindings += tuple((CompletionResult, name, getattr(CompletionResult, name)) for name in
        _PERMISSIONS + ('__init__', '__copy__', '__deepcopy__', '__bool__'))
    bindings += tuple((validator, '__code__', validator.__code__) for validator in _VALIDATORS.values())
    bindings += tuple((cls, '__post_init__', _VALIDATORS[id(cls)]) for cls in _VALUES
        if id(cls) in _VALIDATORS)
    return bindings + tuple((value, '__code__', value.__code__) for _, _, value in bindings
        if type(value) is types.FunctionType)


def _tables():
    module = sys.modules[__name__]
    return f._tables() + tuple((module, name, mapping, tuple(mapping.items()))
        for name, mapping in (('_FIELD_TYPES', _FIELD_TYPES), ('_ATOM_IDS', _ATOM_IDS),
            ('_ENUM_MEMBERS', _ENUM_MEMBERS), ('_VALIDATORS', _VALIDATORS)))


def _composition_stable(completer):
    try:
        if completer._storage is not completer._captured_storage: return False
        if completer._failure_defaults is not completer._captured_failure_defaults: return False
        lookup = completer._captured_lookup
        if (completer._lookup is not lookup or lookup.__code__ is not completer._lookup_code
                or lookup.__defaults__ is not completer._lookup_defaults): return False
        if object.__getattribute__(completer, '_emergency') is not object.__getattribute__(
                completer, '_captured_emergency'): return False
        for cls, original in completer._mros:
            if type.__getattribute__(cls, '__mro__') is not original: return False
        for lookup, owner, name, original in completer._binding_reads:
            if lookup is None:
                if object.__getattribute__(owner, name) is not original: return False
            elif completer._lookup(owner, name) is not original: return False
        # Native access bindings above are qualified before inspecting the
        # explicit issuance defaults and the three evaluator-used initializers.
        if completer._function_state is not completer._captured_function_state: return False
        (getset_get, member_get, dict_items, function_type, cell_type,
            defaults_slot, kwdefaults_slot, closure_slot, contents_slot,
            issue, defaults, default_entries, kwdefaults, kw_entries,
            initializers) = completer._captured_function_state
        current = getset_get(defaults_slot, issue, function_type)
        if current is not defaults: return False
        if current is not None and len(current) != len(default_entries): return False
        for actual, expected in zip(() if current is None else current, default_entries):
            if actual is not expected: return False
        current = getset_get(kwdefaults_slot, issue, function_type)
        if current is not kwdefaults: return False
        if current is not None and len(current) != len(kw_entries): return False
        for key, value in (() if current is None else dict_items(current)):
            if not any(key is saved_key and value is saved_value
                    for saved_key, saved_value in kw_entries): return False
        for cls, initializer, code, closure, cells in initializers:
            if completer._lookup(cls.__dict__, '__init__') is not initializer: return False
            if initializer.__code__ is not code: return False
            current = member_get(closure_slot, initializer, function_type)
            if current is not closure or len(current) != len(cells): return False
            for cell, (saved_cell, contents) in zip(current, cells):
                if cell is not saved_cell: return False
                try:
                    actual_contents = getset_get(contents_slot, cell, cell_type)
                except ValueError:
                    # The qualified native cell getter reports an empty cell.
                    return False
                if actual_contents is not contents: return False
        for owner, name, mapping, entries in completer._tables:
            if completer._lookup(owner.__dict__, name) is not mapping or type(mapping) is not dict: return False
            if len(mapping) != len(entries): return False
            for key, value in entries:
                if completer._lookup(mapping, key) is not value: return False
        for view, entries in completer._descriptors:
            if len(view) != len(entries): return False
            for name, captured in entries:
                if completer._lookup(view, name) is not captured: return False
        for view, entries in completer._adapter_views:
            if len(view) != len(entries): return False
            for name, captured in entries:
                if completer._lookup(view, name) is not captured: return False
        for name, value in completer._adapter_fields:
            if object.__getattribute__(completer._adapter, name) is not value: return False
        if (completer._verify is not completer._adapter_fields[2][1]
                or completer._complete is not completer._adapter_fields[3][1]
                or completer._qualify is not completer._adapter_fields[4][1]
                or completer._canonical is not outcomes.completion_disposition
                or completer._enter is not _CompletionEntryOwner.try_enter): return False
        owner = completer._owner
        if type(owner) is not _CompletionEntryOwner: return False
        if _MEMBER_GET(_OWNER_BINDING_SLOT, owner, _CompletionEntryOwner) is not completer._owner_binding:
            return False
        if _MEMBER_GET(_OWNER_LOCK_SLOT, owner, _CompletionEntryOwner) is not completer._owner_lock:
            return False
        if type(completer._owner_lock) is not _LOCK_TYPE: return False
        for name, original in completer._binding_fields:
            if object.__getattribute__(completer._owner_binding, name) is not original: return False
        for reference, identity, digest in completer._references:
            if type(reference) is not service.EvidenceReference: return False
            current_identity = object.__getattribute__(reference, 'identity')
            current_digest = object.__getattribute__(reference, 'sha256')
            if type(current_identity) is not str or type(current_digest) is not bytes: return False
            if current_identity != identity or current_digest != digest: return False
        return True
    except (AttributeError,) + _INVALID:
        return False


class CheckpointCompleter:
    def __init__(self, adapter=None, *, owner=None):
        self._available = adapter is not None and owner is not None
        self._result_type, self._payload_type = CompletionResult, _CompletionPayload
        # Captured native instance-dictionary access bypasses replaceable record
        # field descriptors. These immutable defaults never come from a result.
        self._storage = (_NATIVE_NEW, _NATIVE_STORAGE_GET, _NATIVE_DICT_SET,
            CompletionResult.__dict__['__dict__'], _CompletionPayload.__dict__['__dict__'],
            BaseException.__dict__['__dict__'], _EXCEPTION_NEW, _EXCEPTION_INIT,
            _CompletionEvaluationInterrupted)
        self._captured_storage = self._storage
        self._failure_defaults = (('state', S.UNRESOLVED), ('reason', R.DEPENDENCY_INSTABILITY),
            ('verification_attempted', False), ('completion_entry_consumed', False),
            ('completion_invoked', False), ('qualification_attempted', False),
            ('disposition_evaluated', False), ('next_required_gate', outcomes.RequiredGate.RECOVERY_HANDOFF),
            ('completed', None), ('not_submitted', None), ('rejected', None))
        self._captured_failure_defaults = self._failure_defaults
        self._composition_unavailable_reason = R.COMPOSITION_UNAVAILABLE
        self._lookup = self._captured_lookup = _identity_lookup
        self._lookup_code, self._lookup_defaults = _identity_lookup.__code__, _identity_lookup.__defaults__
        self._bootstrap, self._bootstrap_code = _composition_stable, _composition_stable.__code__
        if not self._available: return
        try:
            _require(type(adapter) is TrustedCompletionAdapter and type(owner) is _CompletionEntryOwner)
            _reference(adapter.authority); _reference(adapter.implementation)
            callbacks = adapter.verify, adapter.complete, adapter.qualify
            _require(all(type(fn) in (types.FunctionType, types.MethodType) for fn in callbacks))
            self._adapter, self._owner = adapter, owner
            self._adapter_fields = tuple((name, object.__getattribute__(adapter, name))
                for name in ('authority', 'implementation', 'verify', 'complete', 'qualify'))
            self._adapter_views = tuple((base.__dict__, tuple(base.__dict__.items()))
                for base in TrustedCompletionAdapter.__mro__)
            self._authority, self._implementation = _copy(adapter.authority), _copy(adapter.implementation)
            self._references = tuple((value, value.identity, value.sha256)
                for value in (adapter.authority, adapter.implementation))
            self._verify, self._complete, self._qualify = callbacks
            self._canonical = outcomes.completion_disposition
            self._owner_binding = _MEMBER_GET(_OWNER_BINDING_SLOT, owner, _CompletionEntryOwner)
            self._saved_binding = _copy(self._owner_binding)
            self._binding_projection = _project(self._saved_binding)
            self._binding_fields = tuple((name, object.__getattribute__(self._owner_binding, name))
                for name, _ in _FIELD_TYPES[id(_CompletionOwnerBinding)][1])
            self._owner_lock = _MEMBER_GET(_OWNER_LOCK_SLOT, owner, _CompletionEntryOwner)
            _require(type(self._owner_lock) is _LOCK_TYPE)
            self._enter = _CompletionEntryOwner.try_enter
            # Fixed native emergency references belong to composition. Evaluation
            # only unpacks them; no dictionary views are discovered on failure.
            self._emergency = (owner, _CompletionEntryOwner, sys.modules[__name__].__dict__,
                _CompletionEntryOwner.__dict__, types.__dict__, types.MemberDescriptorType.__dict__,
                _EntryState, _EntryState.__dict__, _EntryState.PENDING, _EntryState.ENTERED,
                _OWNER_STATE_SLOT, _MEMBER_TYPE, _MEMBER_GET, _DICT_GET, _PROXY_GET,
                dict.__dict__, types.MappingProxyType.__dict__)
            self._captured_emergency = self._emergency
            self._bindings = _dependencies() + tuple((fn.__func__ if type(fn) is types.MethodType else fn,
                '__code__', (fn.__func__ if type(fn) is types.MethodType else fn).__code__) for fn in callbacks)
            tables = []
            for target, name, mapping, entries in _tables():
                _require(type(mapping) is dict and len(mapping) == len(entries))
                key = next(key for key in target.__dict__ if type(key) is str and key == name)
                # Frozen manifests may regenerate equal integer IDs. Capture the
                # actual stored keys now, not those reconstructed manifest keys.
                tables.append((target, key, mapping, tuple(_DICT_ITEMS(mapping))))
            self._tables = tuple(tables)
            reads = []
            for target, name, original in self._bindings:
                if type(target) is types.ModuleType:
                    key = next(key for key in target.__dict__ if type(key) is str and key == name)
                    reads.append((_identity_lookup, target.__dict__, key, original))
                elif isinstance(target, type):
                    # Fixed manifest owners only. Native reads of their prepared
                    # class dictionaries cannot invoke a substituted descriptor.
                    for base in target.__mro__:
                        view = base.__dict__
                        key = next((key for key in view if type(key) is str and key == name), name)
                        reads.append((_identity_lookup, view, key, _identity_lookup(view, key)))
                else:
                    reads.append((None, target, name, original))
            self._binding_reads = tuple(reads)
            # Fixed function-state manifest, captured only at trusted composition.
            getset_get, member_get = _NATIVE_STORAGE_GET, _MEMBER_GET
            function_type, cell_type = types.FunctionType, types.CellType
            defaults_slot = function_type.__dict__['__defaults__']
            kwdefaults_slot = function_type.__dict__['__kwdefaults__']
            closure_slot = function_type.__dict__['__closure__']
            contents_slot = cell_type.__dict__['cell_contents']
            defaults = getset_get(defaults_slot, _issue, function_type)
            kwdefaults = getset_get(kwdefaults_slot, _issue, function_type)
            initializers = []
            for cls in (_CompletionPayload, CompletionRequest, CompletionObservation):
                initializer = cls.__init__
                closure = member_get(closure_slot, initializer, function_type)
                initializers.append((cls, initializer, initializer.__code__, closure,
                    tuple((cell, getset_get(contents_slot, cell, cell_type)) for cell in closure)))
            self._function_state = (getset_get, member_get, _DICT_ITEMS, function_type, cell_type,
                defaults_slot, kwdefaults_slot, closure_slot, contents_slot,
                _issue, defaults, () if defaults is None else tuple(defaults),
                kwdefaults, () if kwdefaults is None else tuple(_DICT_ITEMS(kwdefaults)),
                tuple(initializers))
            self._captured_function_state = self._function_state
            self._descriptors = tuple((cls.__dict__, tuple(cls.__dict__.items()))
                for cls in _VALUES + (_CompletionEvaluationInterrupted,))
            self._comparison_views = {id(cls): tuple((base.__dict__, tuple(base.__dict__.items()))
                for base in cls.__mro__) for cls in _VALUES}
            self._mros = tuple((cls, cls.__mro__) for cls in _VALUES + _ENUMS
                + (_CompletionEntryOwner, _CompletionEvaluationInterrupted, BaseException))
        except (AttributeError,) + _INVALID:
            raise TypeError('Malformed completion composition') from None

    def complete_original(self, source):
        # Only captured native allocation/storage precedes the bootstrap check.
        # In particular, neither record field descriptors nor constructors run.
        (native_new, storage_get, store, result_slot, payload_slot, exception_slot,
            exception_new, exception_init, carrier_type) = self._captured_storage
        result_type, payload_type = self._result_type, self._payload_type
        failure = native_new(result_type)
        payload = native_new(payload_type)
        failure_data = storage_get(result_slot, failure, result_type)
        payload_data = storage_get(payload_slot, payload, payload_type)
        for name in ('source', 'request', 'eligibility', 'entry_decision', 'observation',
                'qualification', 'canonical_observation', 'disposition'):
            store(payload_data, name, None)
        store(payload_data, 'owner_entry_attempted', False)
        store(payload_data, 'reconciliation_required', True)
        for name, value in self._captured_failure_defaults: store(failure_data, name, value)
        store(failure_data, 'unresolved', payload)
        dependency_reason = failure_data['reason']
        unresolved_state = failure_data['state']
        recovery_gate = failure_data['next_required_gate']
        bootstrap, code = self._bootstrap, self._bootstrap_code
        if bootstrap.__code__ is not code: return failure
        if not self._available:
            store(failure_data, 'reason', self._composition_unavailable_reason)
            return failure
        if not bootstrap(self): return failure
        try:
            projection = _project(source)
            saved = _detach(projection)
            route = _source(saved)
        except _INVALID:
            if bootstrap.__code__ is not code or not bootstrap(self): return failure
            return _issue(R.INVALID_F_SOURCE)
        if bootstrap.__code__ is not code or not bootstrap(self): return failure
        if route is not None: return _issue(route, source=saved)
        verified = consumed = invoked = qualified = evaluated = attempted = False
        request = eligibility = observation = qualification = canonical = disposition = decision = None
        witnesses = [(source, projection, R.SOURCE_INSTABILITY)]
        latest = None
        # This evaluation-local comparison uses only captured native operations
        # and fixed descriptor views. It can establish earlier-category mutation
        # without calling a replaced semantic helper or adopting a changed table.
        atom_types, enum_types = _ATOMS, _ENUMS
        comparison_views = self._comparison_views
        native_get, native_proxy_get = object.__getattribute__, self._captured_lookup
        lookup_code, lookup_defaults = self._lookup_code, self._lookup_defaults
        native_type_get = type.__getattribute__
        record_mros = {id(cls): mro for cls, mro in self._mros}
        earlier_categories = (R.SOURCE_INSTABILITY, R.REQUEST_INSTABILITY, R.RESPONSE_INSTABILITY)
        later_categories = (R.DISPOSITION_INSTABILITY, R.EFFECT_EVIDENCE_INSTABILITY)

        def unchanged(original, expected):
            if (native_proxy_get.__code__ is not lookup_code
                    or native_proxy_get.__defaults__ is not lookup_defaults): return None
            seen = set()
            def compare(value, node):
                kind, data = node
                if type(value) is not kind: return False
                if any(kind is item for item in atom_types):
                    if kind is type(None) or kind is str or kind is bytes or kind is int or kind is bool:
                        return value == data
                    return value is data
                if any(kind is item for item in enum_types): return value is data
                pair = id(value), id(node)
                if pair in seen: return True
                seen.add(pair)
                if kind is tuple:
                    return len(value) == len(data) and all(compare(child, child_node)
                        for child, child_node in zip(value, data))
                views = comparison_views.get(id(kind))
                if views is None: return False
                if native_type_get(kind, '__mro__') is not record_mros[id(kind)]: return None
                for view, entries in views:
                    if len(view) != len(entries): return None
                    for name, captured in entries:
                        if native_proxy_get(view, name) is not captured:
                            # A changed descriptor is dependency instability, not
                            # permission to invoke it or infer source mutation.
                            return None
                for name, child_node in data:
                    try: child = native_get(value, name)
                    except AttributeError: return False
                    agreement = compare(child, child_node)
                    if agreement is not True: return agreement
                return True
            try:
                return compare(original, expected)
            finally:
                compare = None

        def issue(reason, *, carrier=False):
            return _issue(reason, (verified, consumed, invoked, qualified, evaluated),
                source=saved, request=request, eligibility=eligibility, attempted=attempted,
                decision=decision, observation=observation, qualification=qualification,
                canonical=canonical, disposition=disposition, carrier=carrier)

        # A sealed failure allocator preserves the latest detached floor without
        # calling a changed graph helper. No failed dependency is used to report it.
        def fail(reason):
            result = native_new(result_type)
            body = native_new(payload_type)
            result_data = storage_get(result_slot, result, result_type)
            body_data = storage_get(payload_slot, body, payload_type)
            floor = (storage_get(payload_slot,
                storage_get(result_slot, latest, result_type)['unresolved'], payload_type)
                if latest is not None else None)
            for name in ('source', 'request', 'eligibility', 'owner_entry_attempted',
                    'entry_decision', 'observation', 'qualification', 'canonical_observation', 'disposition'):
                value = floor[name] if floor is not None else (
                    saved if name == 'source' else attempted if name == 'owner_entry_attempted'
                    else decision if name == 'entry_decision' else None)
                store(body_data, name, value)
            store(body_data, 'reconciliation_required', True)
            for name, value in (('state', unresolved_state), ('reason', reason),
                    ('verification_attempted', verified), ('completion_entry_consumed', consumed),
                    ('completion_invoked', invoked), ('qualification_attempted', qualified),
                    ('disposition_evaluated', evaluated),
                    ('next_required_gate', recovery_gate),
                    ('completed', None), ('not_submitted', None), ('rejected', None), ('unresolved', body)):
                store(result_data, name, value)
            return result

        def stability():
            for category in earlier_categories:
                for original, expected, reason in witnesses:
                    if reason is category and unchanged(original, expected) is False: return reason
            if bootstrap.__code__ is not code or not bootstrap(self): return dependency_reason
            if unchanged(self._owner_binding, self._binding_projection) is not True:
                return dependency_reason
            if unchanged(self._saved_binding, self._binding_projection) is not True:
                return dependency_reason
            for category in later_categories:
                for original, expected, reason in witnesses:
                    if reason is category and unchanged(original, expected) is not True: return reason
            return None

        request = CompletionRequest(_copy(saved), _copy(_operation(saved)),
            _copy(saved.published.qualification.publication), _copy(self._authority),
            _copy(self._implementation), _copy(self._saved_binding), object.__new__(_EvaluationBinding))
        witnesses.append((request, _project(request), R.REQUEST_INSTABILITY))
        latest = issue(R.DEPENDENCY_INSTABILITY)
        reason = stability()
        if reason is not None: return fail(reason)
        verified = True
        try:
            response = self._verify(request, self._owner)
        except _AVAILABILITY:
            reason = stability()
            return fail(reason) if reason is not None else issue(R.ELIGIBILITY_UNAVAILABLE)
        reason = stability()
        if reason is not None: return fail(reason)
        try:
            response_projection = _project(response)
            eligibility = _detach(response_projection)
        except _INVALID:
            return issue(R.ELIGIBILITY_MALFORMED)
        witnesses.append((response, response_projection, R.RESPONSE_INSTABILITY))
        reason = _eligibility(eligibility, request, self._authority, self._implementation)
        unstable = stability()
        if unstable is not None: return fail(unstable)
        if reason is not None:
            if reason is R.ELIGIBILITY_MALFORMED: eligibility = None
            return issue(reason)
        # Every effect argument, emergency reference and interruption carrier is
        # ready before the owner can consume entry. Owners never enter evidence.
        operation, publication = _copy(request.operation), _copy(request.publication)
        availability, capability_type, timeout_type = _AVAILABILITY, service.CapabilityUnavailable, TimeoutError
        returned_kind, malformed_kind, unbound_kind = (CompletionObservationKind.RETURNED,
            CompletionObservationKind.MALFORMED_RETURN, CompletionObservationKind.UNBOUND_RETURN)
        timeout_kind, capability_kind, external_kind = (CompletionObservationKind.TIMEOUT,
            CompletionObservationKind.CAPABILITY_UNAVAILABLE, CompletionObservationKind.EXTERNAL_UNAVAILABLE)
        witnesses.extend(((operation, _project(operation), R.EFFECT_EVIDENCE_INSTABILITY),
            (publication, _project(publication), R.EFFECT_EVIDENCE_INSTABILITY)))
        (owner, owner_type, module_dict, owner_dict, types_dict, descriptor_dict,
            state_type, state_dict, pending, entered, state_slot, member_type, member_get,
            dict_get, proxy_get, dict_view, proxy_view) = self._captured_emergency
        binding, lock, enter, complete = self._owner_binding, self._owner_lock, self._enter, self._complete
        attempted = True
        entered_floor = _issue(R.ENTRY_INTERRUPTED, (True, True, False, False, False),
            source=saved, request=request, eligibility=eligibility, attempted=True,
            carrier=True)
        unknown_floor = _issue(R.ENTRY_STATE_UNKNOWN, (True, False, False, False, False),
            source=saved, request=request, eligibility=eligibility, attempted=True,
            carrier=True)
        possible_floor = _issue(R.EVALUATION_INTERRUPTED, (True, True, True, False, False),
            source=saved, request=request, eligibility=eligibility, attempted=True,
            carrier=True)
        # The exception type may acquire a hostile constructor after composition.
        # Allocate through BaseException's captured natives, never that constructor.
        entry_carrier = exception_new(carrier_type)
        unknown_carrier = exception_new(carrier_type)
        evaluation_carrier = exception_new(carrier_type)
        for carrier, floor in ((entry_carrier, entered_floor),
                (unknown_carrier, unknown_floor), (evaluation_carrier, possible_floor)):
            exception_init(carrier, 'Original completion interrupted; reconciliation required')
            store(storage_get(exception_slot, carrier, carrier_type), 'result', floor)
        entered_data = storage_get(payload_slot,
            storage_get(result_slot, entered_floor, result_type)['unresolved'], payload_type)
        possible_data = storage_get(payload_slot,
            storage_get(result_slot, possible_floor, result_type)['unresolved'], payload_type)
        possible_result_data = storage_get(result_slot, possible_floor, result_type)
        emergency_lookup = self._captured_lookup
        attempted = False
        reason = stability()
        if reason is not None: return fail(reason)
        attempted = True
        try:
            decision = enter(owner, binding, lock)
        except BaseException as original:
            # One native state read maximum. Identity checks use previously
            # captured live dictionaries and native descriptors only.
            safe, state = False, None
            try:
                if (emergency_lookup.__code__ is lookup_code
                        and emergency_lookup.__defaults__ is lookup_defaults
                        and type(owner) is owner_type
                        and emergency_lookup(module_dict, '_CompletionEntryOwner') is owner_type
                        and emergency_lookup(owner_dict, '_state') is state_slot
                        and type(state_slot) is member_type
                        and emergency_lookup(module_dict, '_OWNER_STATE_SLOT') is state_slot
                        and emergency_lookup(module_dict, '_MEMBER_GET') is member_get
                        and emergency_lookup(module_dict, '_MEMBER_TYPE') is member_type
                        and emergency_lookup(dict_view, 'get') is dict_get
                        and emergency_lookup(proxy_view, 'get') is proxy_get
                        and emergency_lookup(dict_view, 'items') is lookup_defaults[0]
                        and emergency_lookup(proxy_view, 'items') is lookup_defaults[1]
                        and emergency_lookup(types_dict, 'MemberDescriptorType') is member_type
                        and emergency_lookup(descriptor_dict, '__get__') is member_get
                        and emergency_lookup(module_dict, '_EntryState') is state_type
                        and emergency_lookup(state_dict, 'PENDING') is pending
                        and emergency_lookup(state_dict, 'ENTERED') is entered
                        and type(pending) is state_type and type(entered) is state_type):
                    state = member_get(state_slot, owner, owner_type)
                    safe = state is pending or state is entered
            except BaseException:
                safe = False
            if safe and state is pending: raise
            if safe and state is entered: raise entry_carrier from original
            raise unknown_carrier from original
        if type(decision) is not EntryDecision:
            raise unknown_carrier from _Malformed()
        if decision is EntryDecision.ALREADY_ENTERED:
            consumed = True
            return issue(R.COMPLETION_ALREADY_ENTERED)
        if decision is EntryDecision.BINDING_MISMATCH: return issue(R.ELIGIBILITY_BINDING_MISMATCH)
        if decision is EntryDecision.BUSY: return issue(R.COMPETING_EXECUTION)
        consumed = True
        latest = entered_floor
        try:
            store(entered_data, 'entry_decision', decision)
            store(possible_data, 'entry_decision', decision)
            reason = stability()
            if reason is not None: return fail(reason)
            invoked = True
            try:
                raw = complete(operation, publication)
                kind = returned_kind
            except availability as unavailable:
                raw = None
                kind = (timeout_kind if isinstance(unavailable, timeout_type)
                    else capability_kind if isinstance(unavailable, capability_type) else external_kind)
            latest = possible_floor
            reason = stability()
            if reason is not None: return fail(reason)
            returned = None
            if kind is returned_kind:
                try:
                    _require(type(raw) is service.CompletionResult)
                    raw_projection = _project(raw)
                    returned = _detach(raw_projection)
                    service.CompletionResult.__post_init__(returned)
                except _INVALID:
                    kind = malformed_kind
                    returned = None
                else:
                    witnesses.append((raw, raw_projection, R.RESPONSE_INSTABILITY))
                    try:
                        service.verify_completion_result(operation, publication, returned)
                    except _INVALID:
                        kind, returned = unbound_kind, None
            observation = CompletionObservation(_copy(request), _copy(eligibility), kind, returned)
            # These are already detached, evaluator-owned records. Advance the
            # preallocated evidence floor before any further allocation. A failed
            # enrichment must not discard knowledge already safely obtained.
            store(possible_data, 'observation', observation)
            latest = possible_floor
            witnesses.append((observation, _project(observation), R.EFFECT_EVIDENCE_INSTABILITY))
            qualifier_request = _copy(observation)
            witnesses.append((qualifier_request, _project(qualifier_request), R.REQUEST_INSTABILITY))
            reason = stability()
            if reason is not None: return fail(reason)
            qualified = True
            # Preallocated reached-flag floor; no enrichment in the handler.
            store(possible_result_data, 'qualification_attempted', True)
            try:
                qualified_response = self._qualify(qualifier_request)
            except _AVAILABILITY:
                reason = stability()
                return fail(reason) if reason is not None else issue(R.QUALIFICATION_UNAVAILABLE)
            reason = stability()
            if reason is not None: return fail(reason)
            try:
                qualified_projection = _project(qualified_response)
                qualification = _detach(qualified_projection)
            except _INVALID:
                return issue(R.QUALIFICATION_MALFORMED)
            witnesses.append((qualified_response, qualified_projection, R.RESPONSE_INSTABILITY))
            reason = _qualification(qualification, observation, self._authority, self._implementation)
            unstable = stability()
            if unstable is not None: return fail(unstable)
            if reason is not None:
                if reason is R.QUALIFICATION_MALFORMED: qualification = None
                return issue(reason)
            store(possible_data, 'qualification', qualification)
            latest = possible_floor
            candidate = _copy(publication.candidate)
            canonical_publication = _copy(publication)
            canonical_completion = _copy(qualification.completion if qualification.validity is V.VALID
                else observation.returned)
            prior = _copy(saved.published.disposition)
            witnesses.extend((item, _project(item), R.EFFECT_EVIDENCE_INSTABILITY)
                for item in (candidate, canonical_publication, canonical_completion, prior))
            reason = stability()
            if reason is not None: return fail(reason)
            evaluated = True
            store(possible_result_data, 'disposition_evaluated', True)
            raw_disposition = self._canonical(candidate, canonical_publication, canonical_completion,
                local_commit=outcomes.LocalCommitState.CONFIRMED,
                publication_qualification=V.VALID, completion_qualification=qualification.validity,
                prior=prior)
            reason = stability()
            if reason is not None: return fail(reason)
            try:
                _require(type(raw_disposition) is outcomes.Disposition)
                canonical_projection = _project(raw_disposition)
                canonical = _detach(canonical_projection)
                outcomes.Disposition.__post_init__(canonical)
                _require(canonical.stage is outcomes.Stage.COMPLETION
                    and _same(canonical.candidate, candidate)
                    and _same(canonical.operation, operation)
                    and _same(canonical.publication, publication)
                    and _same(canonical.completion, canonical_completion)
                    and canonical.prior_recovery is None
                    and canonical.local_commit is outcomes.LocalCommitState.CONFIRMED
                    and canonical.publication_qualification is V.VALID
                    and canonical.completion_qualification is qualification.validity)
            except _INVALID:
                return issue(R.CANONICAL_DISPOSITION_CONTRADICTION)
            store(possible_data, 'canonical_observation', canonical)
            store(possible_data, 'disposition', canonical)
            latest = possible_floor
            witnesses.append((raw_disposition, canonical_projection, R.DISPOSITION_INSTABILITY))
            disposition = canonical
            reason = stability()
            if reason is not None: return fail(reason)
            if qualification.validity is not V.VALID:
                reason = R.QUALIFICATION_UNQUALIFIED
            elif disposition.outcome is service.ExternalOutcome.CONFIRMED:
                _require(disposition.required_gate is outcomes.RequiredGate.CURRENT_DELIVERY_QUALIFICATION
                    and disposition.recovery is None and disposition.prior_recovery is None)
                reason = R.COMPLETED
            elif disposition.outcome is service.ExternalOutcome.DEFINITELY_REJECTED:
                reason = R.EXTERNAL_DEFINITELY_REJECTED
            else: reason = R.COMPLETION_UNKNOWN
            result = issue(reason)
            unstable = stability()
            return fail(unstable) if unstable is not None else result
        except BaseException as original:
            if not invoked: raise entry_carrier from original
            raise evaluation_carrier from original
