"""One initial protected publication, then independently qualified disposition.

Composition is the trust boundary. Values, references and enum labels do not
authenticate themselves. No query, retry, permit closure or recovery is owned
here. In-memory handoff knowledge has no process-crash durability guarantee.
"""
from dataclasses import dataclass, fields
from enum import StrEnum
from types import FunctionType, MethodType
import sys

from . import fixture_lease_publication_qualification as e

service, g, o, d, c, p = e.s, e.g, e.o, e.d, e.c, e.p


class PublicationState(StrEnum):
    PUBLISHED = 'PUBLISHED'
    NOT_SUBMITTED = 'NOT_SUBMITTED'
    DEFINITELY_REJECTED = 'DEFINITELY_REJECTED'
    UNRESOLVED = 'UNRESOLVED'


class PublicationReason(StrEnum):
    PUBLISHED = 'PUBLISHED'
    INVALID_E_SOURCE = 'INVALID_E_SOURCE'
    E_REJECTED = 'E_REJECTED'
    E_PROVENANCE_INVALID = 'E_PROVENANCE_INVALID'
    CURRENT_AUTHORITY_INELIGIBLE = 'CURRENT_AUTHORITY_INELIGIBLE'
    PREDECESSOR_MISMATCH = 'PREDECESSOR_MISMATCH'
    TEMPORAL_OUTSIDE = 'TEMPORAL_OUTSIDE'
    PROVEN_NON_DISPATCH = 'PROVEN_NON_DISPATCH'
    EXTERNAL_DEFINITELY_REJECTED = 'EXTERNAL_DEFINITELY_REJECTED'
    E_UNRESOLVED = 'E_UNRESOLVED'
    INHERITED_RECONCILIATION = 'INHERITED_RECONCILIATION'
    E_PROVENANCE_UNKNOWN = 'E_PROVENANCE_UNKNOWN'
    PUBLICATION_HISTORY_NON_INITIAL = 'PUBLICATION_HISTORY_NON_INITIAL'
    PUBLICATION_HISTORY_UNKNOWN = 'PUBLICATION_HISTORY_UNKNOWN'
    HISTORICAL_EVIDENCE_CONTRADICTION = 'HISTORICAL_EVIDENCE_CONTRADICTION'
    RETENTION_UNQUALIFIED = 'RETENTION_UNQUALIFIED'
    TIME_BINDING_MISMATCH = 'TIME_BINDING_MISMATCH'
    CURRENT_AUTHORITY_UNKNOWN = 'CURRENT_AUTHORITY_UNKNOWN'
    PREDECESSOR_UNKNOWN = 'PREDECESSOR_UNKNOWN'
    TEMPORAL_UNCERTAIN = 'TEMPORAL_UNCERTAIN'
    TIME_UNQUALIFIED = 'TIME_UNQUALIFIED'
    DISPATCH_COVERAGE_UNQUALIFIED = 'DISPATCH_COVERAGE_UNQUALIFIED'
    SOURCE_BINDING_MISMATCH = 'SOURCE_BINDING_MISMATCH'
    DISPATCH_ASSESSMENT_MALFORMED = 'DISPATCH_ASSESSMENT_MALFORMED'
    DISPATCH_ASSESSMENT_UNQUALIFIED = 'DISPATCH_ASSESSMENT_UNQUALIFIED'
    DISPATCH_ASSESSMENT_UNBOUND = 'DISPATCH_ASSESSMENT_UNBOUND'
    DISPOSITION_MALFORMED = 'DISPOSITION_MALFORMED'
    DISPOSITION_UNQUALIFIED = 'DISPOSITION_UNQUALIFIED'
    DISPOSITION_UNBOUND = 'DISPOSITION_UNBOUND'
    DISPOSITION_UNKNOWN = 'DISPOSITION_UNKNOWN'
    DISPOSITION_CONTRADICTION = 'DISPOSITION_CONTRADICTION'
    DISPATCH_QUALIFICATION_UNAVAILABLE = 'DISPATCH_QUALIFICATION_UNAVAILABLE'
    DISPOSITION_QUALIFICATION_UNAVAILABLE = 'DISPOSITION_QUALIFICATION_UNAVAILABLE'
    SOURCE_INSTABILITY = 'SOURCE_INSTABILITY'
    REQUEST_INSTABILITY = 'REQUEST_INSTABILITY'
    RESPONSE_INSTABILITY = 'RESPONSE_INSTABILITY'
    DEPENDENCY_INSTABILITY = 'DEPENDENCY_INSTABILITY'
    GATE_INSTABILITY = 'GATE_INSTABILITY'
    EFFECT_EVIDENCE_INSTABILITY = 'EFFECT_EVIDENCE_INSTABILITY'
    CANONICAL_GATE_CONTRADICTION = 'CANONICAL_GATE_CONTRADICTION'
    CANONICAL_DISPOSITION_CONTRADICTION = 'CANONICAL_DISPOSITION_CONTRADICTION'
    EVALUATION_INTERRUPTED = 'EVALUATION_INTERRUPTED'


class DispatchDecision(StrEnum):
    ELIGIBLE = 'ELIGIBLE'
    INELIGIBLE = 'INELIGIBLE'
    UNKNOWN = 'UNKNOWN'


class PublicationObservationKind(StrEnum):
    RETURNED = 'RETURNED'
    MALFORMED_RETURN = 'MALFORMED_RETURN'
    UNBOUND_RETURN = 'UNBOUND_RETURN'
    CAPABILITY_UNAVAILABLE = 'CAPABILITY_UNAVAILABLE'
    EXTERNAL_UNAVAILABLE = 'EXTERNAL_UNAVAILABLE'
    TIMEOUT = 'TIMEOUT'


class PublicationDispositionKind(StrEnum):
    CONFIRMED = 'CONFIRMED'
    DEFINITELY_REJECTED = 'DEFINITELY_REJECTED'
    PROVEN_NON_DISPATCH = 'PROVEN_NON_DISPATCH'
    UNKNOWN = 'UNKNOWN'


class _EvaluationBinding:
    __slots__ = ()

    def __new__(cls): raise TypeError('Evaluator-local correlation only')
    def __copy__(self): raise TypeError('Evaluator-local correlation only')
    def __deepcopy__(self, memo): raise TypeError('Evaluator-local correlation only')


@dataclass(frozen=True, repr=False)
class TrustedPublicationAdapter:
    """Selected outside requests; independent qualification is not construction.

    verify/qualify are local read-only and use already-qualified evidence only.
    publish realizes the original protected CAS seam with no hidden retries.
    Coverage authenticates the exact next invocation path, not a point sample.
    """
    authority: service.EvidenceReference
    implementation: service.EvidenceReference
    verify: object
    publish: object
    qualify: object


@dataclass(frozen=True, repr=False)
class PublicationDispatchRequest:
    source: e.PublicationQualificationResult
    evaluation: _EvaluationBinding


@dataclass(frozen=True, repr=False)
class PublicationDispatchCoverage:
    """Independent scope proof through actual entry; never reusable permission."""
    request: PublicationDispatchRequest
    candidate: service.CheckpointCandidate
    operation: service.OriginalOperation
    authority: service.EvidenceReference
    implementation: service.EvidenceReference
    validity: service.EvidenceValidity
    reference: service.EvidenceReference
    point: service.MonotonicPoint
    interval: service.UtcInterval


@dataclass(frozen=True, repr=False)
class PublicationDispatchAssessment:
    request: PublicationDispatchRequest
    authority: service.EvidenceReference
    implementation: service.EvidenceReference
    validity: service.EvidenceValidity
    reference: service.EvidenceReference
    source_provenance: service.EvidenceValidity
    decision: DispatchDecision
    inputs: g.GateInputs | None
    coverage: PublicationDispatchCoverage | None


@dataclass(frozen=True, repr=False)
class PublicationObservation:
    request: PublicationDispatchRequest
    dispatch: PublicationDispatchAssessment
    kind: PublicationObservationKind
    publication: service.PublicationResult | None


@dataclass(frozen=True, repr=False)
class PublicationDispositionAssessment:
    """VALID authenticates exact outcome/non-dispatch proof, not provider labels."""
    observation: PublicationObservation
    authority: service.EvidenceReference
    implementation: service.EvidenceReference
    validity: service.EvidenceValidity
    reference: service.EvidenceReference
    disposition: PublicationDispositionKind
    publication: service.PublicationResult | None


@dataclass(frozen=True, repr=False)
class _PublishedCheckpoint:
    source: e.PublicationQualificationResult
    dispatch: PublicationDispatchAssessment
    observation: PublicationObservation
    qualification: PublicationDispositionAssessment
    disposition: o.Disposition
    reconciliation_required: bool = False


@dataclass(frozen=True, repr=False)
class _NotSubmittedCheckpoint:
    source: e.PublicationQualificationResult | None
    dispatch: PublicationDispatchAssessment | None
    observation: PublicationObservation | None
    qualification: PublicationDispositionAssessment | None
    reconciliation_required: bool


@dataclass(frozen=True, repr=False)
class _RejectedCheckpoint:
    source: e.PublicationQualificationResult
    dispatch: PublicationDispatchAssessment
    observation: PublicationObservation
    qualification: PublicationDispositionAssessment
    disposition: o.Disposition
    reconciliation_required: bool = True


@dataclass(frozen=True, repr=False)
class _UnresolvedCheckpoint:
    source: e.PublicationQualificationResult | None
    dispatch: PublicationDispatchAssessment | None
    observation: PublicationObservation | None
    qualification: PublicationDispositionAssessment | None
    disposition: o.Disposition | None
    reconciliation_required: bool = True


@dataclass(frozen=True, repr=False, init=False)
class PublicationResult:
    state: PublicationState
    reason: PublicationReason
    verification_attempted: bool
    gate_evaluated: bool
    publication_invoked: bool
    qualification_attempted: bool
    published: _PublishedCheckpoint | None
    not_submitted: _NotSubmittedCheckpoint | None
    rejected: _RejectedCheckpoint | None
    unresolved: _UnresolvedCheckpoint | None

    def __init__(self, *args, **kwargs): raise TypeError('Use publish_checkpoint')
    def __init_subclass__(cls, **kwargs): raise TypeError('Closed publication result')
    def __bool__(self): raise TypeError('Publication knowledge is not permission')
    def __copy__(self): raise TypeError('Use publish_checkpoint')
    def __deepcopy__(self, memo): raise TypeError('Use publish_checkpoint')


_PERMISSIONS = e._PERMISSIONS
for _name in _PERMISSIONS:
    setattr(PublicationResult, _name, property(lambda self: False))


class _PublicationEvaluationInterrupted(BaseException):
    """Process-local handoff only; loss of this object proves no non-dispatch."""
    def __init__(self, result):
        self.result = result
        super().__init__('Publication evaluation interrupted; reconciliation required')


class _Malformed(ValueError):
    pass


S, R = PublicationState, PublicationReason
V = service.EvidenceValidity
_INVALID = (_Malformed,) + e._INVALID
_AVAILABILITY = e._AVAILABILITY
_ENUMS = e._ENUMS + (PublicationState, PublicationReason, DispatchDecision,
    PublicationObservationKind, PublicationDispositionKind)
_VALUES = e._VALUES + (PublicationDispatchRequest, PublicationDispatchCoverage,
    PublicationDispatchAssessment, PublicationObservation, PublicationDispositionAssessment,
    _PublishedCheckpoint, _NotSubmittedCheckpoint, _RejectedCheckpoint,
    _UnresolvedCheckpoint, PublicationResult)
_ATOMS = e._ATOMS + (_EvaluationBinding,)
_ATOM_IDS = {id(cls): cls for cls in _ATOMS}
_ENUM_MEMBERS = {id(cls): (cls, tuple(cls)) for cls in _ENUMS}
_FIELD_TYPES = {id(cls): (cls, tuple((f.name, f.type) for f in fields(cls))) for cls in _VALUES}


def _require(value):
    if not value: raise _Malformed()


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
            projected = kind, tuple(visit(v) for v in item)
        else:
            children = []
            for name, annotation in schema[1]:
                try: child = object.__getattribute__(item, name)
                except AttributeError: raise _Malformed() from None
                node = visit(child)
                _require(type(child) is annotation or c._matches(child, annotation))
                children.append((name, node))
            projected = kind, tuple(children)
        active.remove(identity)
        memo[identity] = projected
        return projected
    return visit(value)


def _detach(projection):
    memo = {}

    def detach(node):
        kind, data = node
        if _ATOM_IDS.get(id(kind)) is kind or id(kind) in _ENUM_MEMBERS: return data
        identity = id(node)
        if identity in memo: return memo[identity]
        if kind is tuple:
            value = tuple(detach(child) for child in data)
        else:
            value = object.__new__(kind)
            for name, child in data: object.__setattr__(value, name, detach(child))
        memo[identity] = value
        return value
    return detach(projection)


def _equal(left, right):
    seen = set()

    def compare(a, b):
        if a is b: return True
        kind, data = a
        other, value = b
        if kind is not other: return False
        if kind in (_EvaluationBinding, e._EvaluationBinding) or id(kind) in _ENUM_MEMBERS:
            return data is value
        if _ATOM_IDS.get(id(kind)) is kind: return data == value
        pair = id(a), id(b)
        if pair in seen: return True
        seen.add(pair)
        if len(data) != len(value): return False
        if kind is tuple: return all(compare(x, y) for x, y in zip(data, value))
        return all(name == other_name and compare(x, y)
                   for (name, x), (other_name, y) in zip(data, value))
    return compare(left, right)


def _copy(value): return _detach(_project(value))


def _stable(value, projection):
    try: return _equal(_project(value), projection)
    except _INVALID: return False


def _same(left, right): return _equal(_project(left), _project(right))


def _reference(ref):
    _require(type(ref) is service.EvidenceReference)
    d._reference(ref)


def _source(source):
    """Closed E structure/semantics only. Independent issuance is still required."""
    _require(type(source) is e.PublicationQualificationResult)
    expected = {e.S.QUALIFIED: ('qualified', e._QualifiedPublication),
        e.S.REJECTED: ('rejected', e._RejectedPublication),
        e.S.UNRESOLVED: ('unresolved', e._UnresolvedPublication)}
    name, cls = expected[source.state]
    _require(sum(x is not None for x in (source.qualified, source.rejected, source.unresolved)) == 1)
    payload = object.__getattribute__(source, name)
    _require(type(payload) is cls and (not source.gate_evaluated or source.qualification_attempted))
    if source.state is not e.S.QUALIFIED:
        _require(source.reason is not e.R.QUALIFIED)
        negative = (e.R.INVALID_D_SOURCE, e.R.NOT_RETAINED, e.R.UNQUALIFIED_D_PROVENANCE,
            e.R.CURRENT_AUTHORITY_INELIGIBLE, e.R.PREDECESSOR_MISMATCH, e.R.TEMPORAL_OUTSIDE)
        _require((source.state is e.S.REJECTED) is (source.reason in negative))
        _require(source.state is not e.S.UNRESOLVED or payload.reconciliation_required)
        if payload.source is not None: e._source(payload.source)
        else: _require(source.reason is e.R.INVALID_D_SOURCE)
        return False
    _require(source.reason is e.R.QUALIFIED and source.qualification_attempted and source.gate_evaluated)
    _require(payload.source.state is d.RetentionState.RETAINED
        and type(payload.source.retained) is d._RetainedCandidate)
    _require(payload.source.retained.source.state is c.PreparationState.PREPARED
        and type(payload.source.retained.source.prepared) is c._PreparedCandidate)
    # Inherited handoff is never cleared by a new assessment.
    if (payload.reconciliation_required or payload.source.retained.reconciliation_required
            or payload.source.retained.source.prepared.request.completion.reconciliation_required):
        return True
    e._source(payload.source)
    assessment, gate = payload.assessment, payload.gate
    _require(type(assessment) is e.PublicationAssessment and type(gate) is g.GateResult)
    for ref in (assessment.authority, assessment.implementation, assessment.reference): _reference(ref)
    _require(assessment.validity is V.VALID and assessment.source_provenance is V.VALID)
    _require(type(assessment.request.evaluation) is e._EvaluationBinding)
    _require(_same(assessment.request.source, payload.source) and assessment.inputs is not None)
    _require(_same(gate.inputs, assessment.inputs))
    _require(e._bindings(payload.source, assessment.inputs) is None)
    # GateResult owns its result/inputs consistency check; _revalidate accepts
    # evidence/input roots, not GateResult. Issuance is still verified separately.
    g.GateResult.__post_init__(gate)
    _require(gate.state is g.GateState.SATISFIED and gate.reason is g.GateReason.SATISFIED)
    _require(e._conclusion(gate.inputs, gate) == (e.S.QUALIFIED, e.R.QUALIFIED))
    return False


# Exhaustive fixed correspondence; root-only reasons never become dispatch authority.
_E_TO_F = (
    (e.R.QUALIFIED, None), (e.R.INVALID_D_SOURCE, R.E_REJECTED),
    (e.R.NOT_RETAINED, R.E_REJECTED), (e.R.UPSTREAM_UNRESOLVED, R.E_UNRESOLVED),
    (e.R.INHERITED_RECONCILIATION, R.E_UNRESOLVED),
    (e.R.UNQUALIFIED_D_PROVENANCE, R.E_REJECTED), (e.R.D_PROVENANCE_UNKNOWN, R.E_UNRESOLVED),
    (e.R.CANDIDATE_BINDING_MISMATCH, R.SOURCE_BINDING_MISMATCH),
    (e.R.ORIGINAL_OPERATION_MISMATCH, R.SOURCE_BINDING_MISMATCH),
    (e.R.COMMITTED_TRANSITION_MISMATCH, R.SOURCE_BINDING_MISMATCH),
    (e.R.RETENTION_BINDING_MISMATCH, R.SOURCE_BINDING_MISMATCH),
    (e.R.RETENTION_UNQUALIFIED, R.RETENTION_UNQUALIFIED),
    (e.R.HISTORICAL_EVIDENCE_CONTRADICTION, R.HISTORICAL_EVIDENCE_CONTRADICTION),
    (e.R.CURRENT_AUTHORITY_INELIGIBLE, R.CURRENT_AUTHORITY_INELIGIBLE),
    (e.R.CURRENT_AUTHORITY_UNKNOWN, R.CURRENT_AUTHORITY_UNKNOWN),
    (e.R.PREDECESSOR_MISMATCH, R.PREDECESSOR_MISMATCH), (e.R.PREDECESSOR_UNKNOWN, R.PREDECESSOR_UNKNOWN),
    (e.R.TEMPORAL_OUTSIDE, R.TEMPORAL_OUTSIDE), (e.R.TEMPORAL_UNCERTAIN, R.TEMPORAL_UNCERTAIN),
    (e.R.TIME_UNQUALIFIED, R.TIME_UNQUALIFIED), (e.R.TIME_BINDING_MISMATCH, R.TIME_BINDING_MISMATCH),
    (e.R.PUBLICATION_HISTORY_NON_INITIAL, R.PUBLICATION_HISTORY_NON_INITIAL),
    (e.R.PUBLICATION_HISTORY_UNKNOWN, R.PUBLICATION_HISTORY_UNKNOWN),
    (e.R.MALFORMED_ASSESSMENT, R.DISPATCH_ASSESSMENT_MALFORMED),
    (e.R.UNQUALIFIED_ASSESSMENT, R.DISPATCH_ASSESSMENT_UNQUALIFIED),
    (e.R.ASSESSMENT_BINDING_MISMATCH, R.DISPATCH_ASSESSMENT_UNBOUND),
    (e.R.SOURCE_INSTABILITY, R.SOURCE_INSTABILITY), (e.R.REQUEST_INSTABILITY, R.REQUEST_INSTABILITY),
    (e.R.RESPONSE_INSTABILITY, R.RESPONSE_INSTABILITY), (e.R.DEPENDENCY_INSTABILITY, R.DEPENDENCY_INSTABILITY),
    (e.R.GATE_INSTABILITY, R.GATE_INSTABILITY), (e.R.DEPENDENCY_UNAVAILABLE, R.DISPATCH_QUALIFICATION_UNAVAILABLE),
    (e.R.CANONICAL_GATE_CONTRADICTION, R.CANONICAL_GATE_CONTRADICTION))


def _mapped(reason):
    return next(value for key, value in _E_TO_F if key is reason)


def _assessment(value):
    _require(type(value) is PublicationDispatchAssessment)
    for ref in (value.authority, value.implementation, value.reference): _reference(ref)
    if value.source_provenance is not V.VALID:
        _require(value.inputs is None and value.coverage is None)
        _require(value.decision is (DispatchDecision.INELIGIBLE
            if value.source_provenance is V.INVALID else DispatchDecision.UNKNOWN))
    else:
        _require(type(value.inputs) is g.GateInputs)
        if value.decision is not DispatchDecision.ELIGIBLE: _require(value.coverage is None)
    if value.coverage is not None:
        for ref in (value.coverage.authority, value.coverage.implementation, value.coverage.reference): _reference(ref)


def _coverage(assessment, request, authority, implementation):
    coverage = assessment.coverage
    if coverage is None: return R.DISPATCH_COVERAGE_UNQUALIFIED
    inputs = assessment.inputs
    if (not _same(coverage.request, request) or coverage.authority != authority
            or coverage.implementation != implementation
            or not _same(coverage.candidate, inputs.candidate)
            or coverage.operation != inputs.candidate.operation or inputs.authority is None
            or inputs.time is None or coverage.point != inputs.authority.point
            or coverage.point != inputs.time.point or coverage.interval != inputs.authority.interval
            or coverage.interval != inputs.time.covered_interval):
        return R.DISPATCH_ASSESSMENT_UNBOUND
    if coverage.validity is not V.VALID: return R.DISPATCH_COVERAGE_UNQUALIFIED
    # VALID is the trusted complete assertion of actual-entry scope, not time equality alone.
    return None


def _disposition(assessment, observation, authority, implementation):
    _require(type(assessment) is PublicationDispositionAssessment)
    for ref in (assessment.authority, assessment.implementation, assessment.reference): _reference(ref)
    if assessment.validity is not V.VALID: return R.DISPOSITION_UNQUALIFIED
    if (assessment.authority != authority or assessment.implementation != implementation
            or not _same(assessment.observation, observation)):
        return R.DISPOSITION_UNBOUND
    publication, kind = assessment.publication, assessment.disposition
    if kind is PublicationDispositionKind.PROVEN_NON_DISPATCH:
        if publication is not None: return R.DISPOSITION_CONTRADICTION
        return None
    if publication is None:
        return None if kind is PublicationDispositionKind.UNKNOWN else R.DISPOSITION_MALFORMED
    service.PublicationResult.__post_init__(publication)
    try: service.verify_publication_result(observation.dispatch.inputs.candidate, publication)
    except (ValueError, TypeError, AttributeError): return R.DISPOSITION_UNBOUND
    expected = {PublicationDispositionKind.CONFIRMED: service.ExternalOutcome.CONFIRMED,
        PublicationDispositionKind.DEFINITELY_REJECTED: service.ExternalOutcome.DEFINITELY_REJECTED,
        PublicationDispositionKind.UNKNOWN: service.ExternalOutcome.UNKNOWN}
    if publication.outcome is not expected[kind]: return R.DISPOSITION_CONTRADICTION
    return None


def _issue(state, reason, source=None, dispatch=None, observation=None, qualification=None,
           disposition=None, verified=False, evaluated=False, invoked=False, qualified=False):
    _require(type(state) is S and type(reason) is R)
    _require(not evaluated or verified)
    _require(not qualified or invoked)
    _require(not invoked or verified)
    published = not_submitted = rejected = unresolved = None
    if state is S.PUBLISHED:
        _require(reason is R.PUBLISHED and invoked and qualified and disposition is not None
            and disposition.outcome is service.ExternalOutcome.CONFIRMED
            and disposition.required_gate is o.RequiredGate.ORIGINAL_COMPLETION)
        published = _PublishedCheckpoint(source, dispatch, observation, qualification, disposition)
    elif state is S.DEFINITELY_REJECTED:
        _require(reason is R.EXTERNAL_DEFINITELY_REJECTED and invoked and qualified
            and disposition is not None and disposition.outcome is service.ExternalOutcome.DEFINITELY_REJECTED)
        rejected = _RejectedCheckpoint(source, dispatch, observation, qualification, disposition)
    elif state is S.NOT_SUBMITTED:
        _require(reason in (R.INVALID_E_SOURCE, R.E_REJECTED, R.E_PROVENANCE_INVALID,
            R.CURRENT_AUTHORITY_INELIGIBLE, R.PREDECESSOR_MISMATCH, R.TEMPORAL_OUTSIDE, R.PROVEN_NON_DISPATCH))
        _require(not invoked or (reason is R.PROVEN_NON_DISPATCH and qualified
            and qualification is not None and qualification.validity is V.VALID
            and qualification.disposition is PublicationDispositionKind.PROVEN_NON_DISPATCH))
        not_submitted = _NotSubmittedCheckpoint(source, dispatch, observation, qualification, source is not None)
    else:
        _require(reason not in (R.PUBLISHED, R.EXTERNAL_DEFINITELY_REJECTED, R.INVALID_E_SOURCE,
            R.E_REJECTED, R.E_PROVENANCE_INVALID, R.CURRENT_AUTHORITY_INELIGIBLE,
            R.PREDECESSOR_MISMATCH, R.TEMPORAL_OUTSIDE, R.PROVEN_NON_DISPATCH))
        unresolved = _UnresolvedCheckpoint(source, dispatch, observation, qualification, disposition)
    result = object.__new__(PublicationResult)
    for name, value in (('state', state), ('reason', reason), ('verification_attempted', verified),
        ('gate_evaluated', evaluated), ('publication_invoked', invoked), ('qualification_attempted', qualified),
        ('published', published), ('not_submitted', not_submitted), ('rejected', rejected), ('unresolved', unresolved)):
        object.__setattr__(result, name, value)
    return _copy(result)


def _dependencies():
    """Explicit frozen paths, never discovered from requests or arbitrary globals."""
    module = sys.modules[__name__]
    names = ('_require', '_project', '_detach', '_equal', '_copy', '_stable', '_same', '_reference',
        '_source', '_mapped', '_assessment', '_coverage', '_disposition', '_issue', '_dependencies',
        '_tables', 'e', 'service', 'g', 'o', 'd', 'c', 'p', 'fields', 'FunctionType', 'MethodType',
        'S', 'R', 'V', '_INVALID', '_AVAILABILITY', '_E_TO_F', '_VALUES', '_ATOMS', '_ENUMS',
        'PublicationState', 'PublicationReason', 'DispatchDecision', 'PublicationObservationKind',
        'PublicationDispositionKind', '_PERMISSIONS',
        'PublicationResult', 'PublicationDispatchRequest', 'PublicationDispatchCoverage',
        'PublicationDispatchAssessment', 'PublicationObservation', 'PublicationDispositionAssessment',
        '_EvaluationBinding', '_PublicationEvaluationInterrupted', '_PublishedCheckpoint',
        '_NotSubmittedCheckpoint', '_RejectedCheckpoint', '_UnresolvedCheckpoint')
    extra = ((e, ('_project', '_detach', '_copy', '_equal', '_stable', '_source', '_bindings',
        '_conclusion', '_time_reason', '_require', '_matches', '_EvaluationBinding', '_dependencies',
        '_dispatch_dependencies', '_INVALID', '_AVAILABILITY', '_VALUES', '_ATOMS', '_ENUMS',
        'R', 'S', 's', 'c', 'o', 'cp', 'p', 'd', 'g')),
        (o, ('publication_disposition', '_original', '_finish', 'Disposition', 'RecoveryHandoff')),
        (service.PublicationResult, ('__init__', '__post_init__')),
        (o.Disposition, ('__init__', '__post_init__', 'completion_required', 'delivery_qualification_required')),
        (o.RecoveryHandoff, ('__init__', '__post_init__')),
        (CheckpointPublisher, ('_composition_stable', 'publish_checkpoint')))
    bindings = e._dependencies() + tuple((module, name, getattr(module, name)) for name in names)
    bindings += tuple((owner, name, getattr(owner, name)) for owner, group in extra for name in group)
    constructors = (PublicationDispatchRequest, PublicationDispatchCoverage, PublicationDispatchAssessment,
        PublicationObservation, PublicationDispositionAssessment, _PublishedCheckpoint,
        _NotSubmittedCheckpoint, _RejectedCheckpoint, _UnresolvedCheckpoint, _PublicationEvaluationInterrupted)
    bindings += tuple((cls, '__init__', cls.__init__) for cls in constructors)
    bindings += tuple((PublicationResult, name, getattr(PublicationResult, name)) for name in
        _PERMISSIONS + ('__init__', '__copy__', '__deepcopy__', '__bool__'))
    # In-place function executable replacement is significant even if its name is unchanged.
    executable = tuple((value, '__code__', value.__code__) for _, _, value in bindings if type(value) is FunctionType)
    return bindings + executable


def _tables():
    module = sys.modules[__name__]
    tables = []
    for owner in (e, module):
        for name, keys in (('_ATOM_IDS', tuple(id(cls) for cls in owner._ATOMS)),
            ('_ENUM_MEMBERS', tuple(id(cls) for cls in owner._ENUMS)),
            ('_FIELD_TYPES', tuple(id(cls) for cls in owner._VALUES))):
            mapping = getattr(owner, name)
            _require(type(mapping) is dict)
            tables.append((owner, name, mapping, tuple((key, dict.__getitem__(mapping, key)) for key in keys)))
    return e._dispatch_dependencies() + tuple(tables)


@dataclass(frozen=True, repr=False, init=False)
class CheckpointPublisher:
    _adapter: TrustedPublicationAdapter
    _authority: service.EvidenceReference
    _implementation: service.EvidenceReference
    _verify: object
    _publish: object
    _qualify: object
    _gate: object
    _canonical: object
    _bindings: tuple
    _tables: tuple
    _entry_failure: PublicationResult
    _references: tuple
    _executables: tuple

    def __init__(self, adapter: TrustedPublicationAdapter):
        try:
            _require(type(adapter) is TrustedPublicationAdapter)
            authority, implementation = _copy(adapter.authority), _copy(adapter.implementation)
            _reference(authority); _reference(implementation)
            executables = (adapter.verify, adapter.publish, adapter.qualify)
            _require(all(type(fn) is FunctionType or type(fn) is MethodType for fn in executables))
        except (AttributeError,) + _INVALID:
            raise TypeError('Malformed publication composition') from None
        refs = ((authority.identity, authority.sha256), (implementation.identity, implementation.sha256))
        bindings = _dependencies() + tuple((fn.__func__ if type(fn) is MethodType else fn,
            '__code__', (fn.__func__ if type(fn) is MethodType else fn).__code__) for fn in executables)
        for name, value in (('_adapter', adapter), ('_authority', authority), ('_implementation', implementation),
            ('_verify', executables[0]), ('_publish', executables[1]), ('_qualify', executables[2]),
            ('_executables', tuple((fn, fn.__func__, fn.__self__) if type(fn) is MethodType else
                (fn, fn, None) for fn in executables)), ('_references', refs),
            ('_gate', g.evaluate_publication_gate), ('_canonical', o.publication_disposition),
            ('_bindings', bindings), ('_tables', _tables()),
            ('_entry_failure', _issue(S.UNRESOLVED, R.DEPENDENCY_INSTABILITY))):
            object.__setattr__(self, name, value)

    def _composition_stable(self):
        # No projection, source helper, caller equality, or result factory here.
        # Also used as the initial bootstrap; captured identities are checked first.
        try:
            for owner, name, captured in self._bindings:
                if getattr(owner, name) is not captured: return False
            for owner, name, mapping, entries in self._tables:
                if getattr(owner, name) is not mapping or type(mapping) is not dict: return False
                for key, captured in entries:
                    if dict.get(mapping, key) is not captured: return False
            if self._adapter.verify is not self._verify or self._adapter.publish is not self._publish:
                return False
            if self._adapter.qualify is not self._qualify: return False
            if self._gate is not g.evaluate_publication_gate or self._canonical is not o.publication_disposition:
                return False
            for ref, expected in zip((self._adapter.authority, self._adapter.implementation), self._references):
                if type(ref) is not service.EvidenceReference: return False
                identity, digest = object.__getattribute__(ref, 'identity'), object.__getattribute__(ref, 'sha256')
                if type(identity) is not str or type(digest) is not bytes: return False
                if (identity, digest) != expected: return False
            for fn, executable, receiver in self._executables:
                if type(fn) is MethodType and (fn.__func__ is not executable or fn.__self__ is not receiver): return False
            return True
        except AttributeError:
            return False

    def publish_checkpoint(self, source: e.PublicationQualificationResult) -> PublicationResult:
        # Only exact built-in allocation/identity operations precede the guard.
        # The private construction-time template is never exposed to a caller.
        template = self._entry_failure
        entry_failure = object.__new__(type(template))
        entry_payload = object.__new__(type(template.unresolved))
        for name in ('source', 'dispatch', 'observation', 'qualification', 'disposition'):
            object.__setattr__(entry_payload, name, None)
        object.__setattr__(entry_payload, 'reconciliation_required', True)
        for name in ('state', 'reason', 'verification_attempted', 'gate_evaluated',
                     'publication_invoked', 'qualification_attempted', 'published',
                     'not_submitted', 'rejected'):
            object.__setattr__(entry_failure, name, object.__getattribute__(template, name))
        object.__setattr__(entry_failure, 'unresolved', entry_payload)
        bootstrap = next(value for owner, name, value in self._bindings
                         if owner is type(self) and name == '_composition_stable')
        bootstrap_code = next(value for owner, name, value in self._bindings
                              if owner is bootstrap and name == '__code__')
        if bootstrap.__code__ is not bootstrap_code or not bootstrap(self): return entry_failure
        S, R = PublicationState, PublicationReason
        try:
            _require(type(source) is e.PublicationQualificationResult)
            projection = _project(source)
            saved = _detach(projection)
            inherited = _source(saved)
        except _INVALID:
            if bootstrap.__code__ is not bootstrap_code or not bootstrap(self): return entry_failure
            return _issue(S.NOT_SUBMITTED, R.INVALID_E_SOURCE)
        if bootstrap.__code__ is not bootstrap_code or not bootstrap(self): return entry_failure
        request = response = assessment = inputs = observed_gate = gate = candidate = returned = None
        observation = qualifier_request = confirmation = qualification = disposition = None
        request_projection = response_projection = inputs_projection = gate_projection = None
        candidate_projection = returned_projection = observation_projection = None
        qualifier_projection = confirmation_projection = None
        verified = evaluated = invoked = qualified = False
        failure_source = _copy(saved)
        result_type, unresolved_type = PublicationResult, _UnresolvedCheckpoint

        def unresolved(reason):
            # Sealed failure allocation uses no failed/replaced helper or class
            # initializer. After entry, retain the latest detached evidence floor.
            payload = object.__new__(unresolved_type)
            floor = interrupted.result.unresolved if invoked else None
            for name in ('source', 'dispatch', 'observation', 'qualification', 'disposition'):
                value = (object.__getattribute__(floor, name) if invoked else
                         failure_source if name == 'source' else None)
                object.__setattr__(payload, name, value)
            object.__setattr__(payload, 'reconciliation_required', True)
            result = object.__new__(result_type)
            for name, value in (('state', S.UNRESOLVED), ('reason', reason), ('verification_attempted', verified),
                ('gate_evaluated', evaluated), ('publication_invoked', invoked), ('qualification_attempted', qualified),
                ('published', None), ('not_submitted', None), ('rejected', None), ('unresolved', payload)):
                object.__setattr__(result, name, value)
            return result

        atom_types, enum_types = _ATOMS, _ENUMS

        def unchanged(value, snapshot):
            # Evaluator-local comparison of a captured closed projection. It
            # calls no replaceable projection/validation helper after callbacks.
            # This lets source/request/response priority precede the dependency
            # verdict without executing a replaced dependency to check them.
            seen, active = set(), set()

            def compare(item, node):
                kind, data = node
                if type(item) is not kind: return False
                if any(kind is cls for cls in enum_types): return item is data
                if kind is _EvaluationBinding or kind is e._EvaluationBinding: return item is data
                if any(kind is cls for cls in atom_types): return item == data
                pair = id(item), id(node)
                if id(item) in active: return False
                if pair in seen: return True
                active.add(id(item))
                if kind is tuple:
                    good = len(item) == len(data) and all(compare(x, y) for x, y in zip(item, data))
                else:
                    try: good = all(compare(object.__getattribute__(item, name), child) for name, child in data)
                    except AttributeError: good = False
                active.remove(id(item))
                seen.add(pair)
                return good
            return compare(value, snapshot)

        def instability():
            if not unchanged(source, projection): return R.SOURCE_INSTABILITY
            if request_projection is not None and not unchanged(request, request_projection): return R.REQUEST_INSTABILITY
            if qualifier_projection is not None and not unchanged(qualifier_request, qualifier_projection): return R.REQUEST_INSTABILITY
            if response_projection is not None and not unchanged(response, response_projection): return R.RESPONSE_INSTABILITY
            if confirmation_projection is not None and not unchanged(confirmation, confirmation_projection): return R.RESPONSE_INSTABILITY
            if bootstrap.__code__ is not bootstrap_code or not bootstrap(self): return R.DEPENDENCY_INSTABILITY
            if inputs_projection is not None and not unchanged(inputs, inputs_projection): return R.GATE_INSTABILITY
            if gate_projection is not None and not unchanged(observed_gate, gate_projection): return R.GATE_INSTABILITY
            if candidate_projection is not None and not unchanged(candidate, candidate_projection): return R.EFFECT_EVIDENCE_INSTABILITY
            if returned_projection is not None and not unchanged(returned, returned_projection): return R.EFFECT_EVIDENCE_INSTABILITY
            if observation_projection is not None and not unchanged(observation, observation_projection): return R.EFFECT_EVIDENCE_INSTABILITY
            return None

        def finish(state, reason):
            changed = instability()
            if changed is not None: return unresolved(changed)
            result = _issue(state, reason, saved, assessment, observation, qualification, disposition,
                verified, evaluated, invoked, qualified)
            changed = instability()
            if changed is not None: return unresolved(changed)
            return result

        if saved.state is not e.S.QUALIFIED:
            return finish(S.NOT_SUBMITTED if saved.state is e.S.REJECTED else S.UNRESOLVED,
                R.E_REJECTED if saved.state is e.S.REJECTED else R.E_UNRESOLVED)
        if inherited: return finish(S.UNRESOLVED, R.INHERITED_RECONCILIATION)
        marker = object.__new__(_EvaluationBinding)
        request = PublicationDispatchRequest(_copy(saved), marker)
        request_projection = _project(request)
        changed = instability()
        if changed is not None: return finish(S.UNRESOLVED, changed)
        if d._namespace(saved.qualified.source.retained.source) != self._authority:
            return finish(S.UNRESOLVED, R.DISPATCH_ASSESSMENT_UNBOUND)
        verified = True
        try: response = self._verify(request)
        except _AVAILABILITY: return finish(S.UNRESOLVED, R.DISPATCH_QUALIFICATION_UNAVAILABLE)
        changed = instability()
        if changed is not None: return finish(S.UNRESOLVED, changed)
        try:
            _require(type(response) is PublicationDispatchAssessment)
            response_projection = _project(response)
            assessment = _detach(response_projection)
            _assessment(assessment)
        except _INVALID:
            assessment = None
            return finish(S.UNRESOLVED, R.DISPATCH_ASSESSMENT_MALFORMED)
        changed = instability()
        if changed is not None: return finish(S.UNRESOLVED, changed)
        if assessment.validity is not V.VALID: return finish(S.UNRESOLVED, R.DISPATCH_ASSESSMENT_UNQUALIFIED)
        if (assessment.authority != self._authority or assessment.implementation != self._implementation
                or not _same(assessment.request, request) or assessment.request.evaluation is not marker):
            return finish(S.UNRESOLVED, R.DISPATCH_ASSESSMENT_UNBOUND)
        if assessment.source_provenance is not V.VALID:
            return finish(S.NOT_SUBMITTED if assessment.source_provenance is V.INVALID else S.UNRESOLVED,
                R.E_PROVENANCE_INVALID if assessment.source_provenance is V.INVALID else R.E_PROVENANCE_UNKNOWN)
        problem = e._bindings(saved.qualified.source, assessment.inputs)
        if problem is not None: return finish(S.UNRESOLVED, _mapped(problem))
        try: g._revalidate(assessment.inputs)
        except _INVALID: return finish(S.UNRESOLVED, R.DISPATCH_ASSESSMENT_MALFORMED)
        inputs = _copy(assessment.inputs)
        inputs_projection = _project(inputs)
        changed = instability()
        if changed is not None: return finish(S.UNRESOLVED, changed)
        evaluated = True
        observed_gate = self._gate(inputs)
        changed = instability()
        if changed is not None: return finish(S.UNRESOLVED, changed)
        try:
            _require(type(observed_gate) is g.GateResult)
            gate_projection = _project(observed_gate)
            gate = _detach(gate_projection)
            _require(gate.inputs is not None and _same(gate.inputs, inputs))
            _require((gate.state is g.GateState.SATISFIED) is (gate.reason is g.GateReason.SATISFIED))
        except _INVALID: return finish(S.UNRESOLVED, R.CANONICAL_GATE_CONTRADICTION)
        conclusion_state, conclusion_reason = e._conclusion(inputs, gate)
        expected = (DispatchDecision.ELIGIBLE if conclusion_state is e.S.QUALIFIED else
            DispatchDecision.INELIGIBLE if conclusion_state is e.S.REJECTED else DispatchDecision.UNKNOWN)
        positive = conclusion_state is e.S.QUALIFIED
        if (assessment.decision is not expected or (gate.state is g.GateState.SATISFIED) is not positive):
            return finish(S.UNRESOLVED, R.CANONICAL_GATE_CONTRADICTION)
        if not positive:
            return finish(S.NOT_SUBMITTED if conclusion_state is e.S.REJECTED else S.UNRESOLVED,
                          _mapped(conclusion_reason))
        problem = _coverage(assessment, request, self._authority, self._implementation)
        if problem is not None: return finish(S.UNRESOLVED, problem)
        candidate = _copy(inputs.candidate)
        candidate_projection = _project(candidate)
        fallback = _issue(S.UNRESOLVED, R.EVALUATION_INTERRUPTED, saved, assessment,
            verified=True, evaluated=True, invoked=True)
        interrupted = _PublicationEvaluationInterrupted(fallback)
        changed = instability()
        if changed is not None: return finish(S.UNRESOLVED, changed)
        try:
            invoked = True  # Callable entry may submit; never proof of dispatch or non-dispatch.
            try:
                returned = self._publish(candidate)
                kind = PublicationObservationKind.RETURNED
            except _AVAILABILITY as error:
                kind = (PublicationObservationKind.CAPABILITY_UNAVAILABLE if type(error) is service.CapabilityUnavailable
                    else PublicationObservationKind.TIMEOUT if type(error) is TimeoutError
                    else PublicationObservationKind.EXTERNAL_UNAVAILABLE)
            changed = instability()
            if changed is not None: return finish(S.UNRESOLVED, changed)
            copied_return = None
            if kind is PublicationObservationKind.RETURNED:
                try:
                    _require(type(returned) is service.PublicationResult)
                    returned_projection = _project(returned)
                    copied_return = _detach(returned_projection)
                    service.PublicationResult.__post_init__(copied_return)
                except _INVALID:
                    kind = PublicationObservationKind.MALFORMED_RETURN
                    copied_return = None
                if copied_return is not None:
                    try: service.verify_publication_result(inputs.candidate, copied_return)
                    except _INVALID:
                        kind = PublicationObservationKind.UNBOUND_RETURN
                        copied_return = None
            observation = PublicationObservation(_copy(request), _copy(assessment), kind, copied_return)
            observation_projection = _project(observation)
            qualifier_request = _copy(observation)
            qualifier_projection = _project(qualifier_request)
            changed = instability()
            if changed is not None: return finish(S.UNRESOLVED, changed)
            # Enrich only on the normal, stable path. Emergency handling keeps
            # the last successfully detached snapshot without calling helpers.
            interrupted.result = _issue(S.UNRESOLVED, R.EVALUATION_INTERRUPTED,
                saved, assessment, observation, verified=True, evaluated=True,
                invoked=True, qualified=False)
            changed = instability()
            if changed is not None: return finish(S.UNRESOLVED, changed)
            qualified = True
            object.__setattr__(interrupted.result, 'qualification_attempted', True)
            try: confirmation = self._qualify(qualifier_request)
            except _AVAILABILITY: return finish(S.UNRESOLVED, R.DISPOSITION_QUALIFICATION_UNAVAILABLE)
            changed = instability()
            if changed is not None: return finish(S.UNRESOLVED, changed)
            try:
                _require(type(confirmation) is PublicationDispositionAssessment)
                confirmation_projection = _project(confirmation)
                qualification = _detach(confirmation_projection)
                problem = _disposition(qualification, observation, self._authority, self._implementation)
            except _INVALID:
                qualification = None
                return finish(S.UNRESOLVED, R.DISPOSITION_MALFORMED)
            if problem is not None: return finish(S.UNRESOLVED, problem)
            if qualification.disposition is not PublicationDispositionKind.PROVEN_NON_DISPATCH:
                disposition_candidate = _copy(inputs.candidate)
                disposition_publication = _copy(qualification.publication)
            changed = instability()
            if changed is not None: return finish(S.UNRESOLVED, changed)
            interrupted.result = _issue(S.UNRESOLVED, R.EVALUATION_INTERRUPTED,
                saved, assessment, observation, qualification, verified=True,
                evaluated=True, invoked=True, qualified=True)
            changed = instability()
            if changed is not None: return finish(S.UNRESOLVED, changed)
            if qualification.disposition is PublicationDispositionKind.PROVEN_NON_DISPATCH:
                return finish(S.NOT_SUBMITTED, R.PROVEN_NON_DISPATCH)
            disposition = self._canonical(disposition_candidate, disposition_publication,
                local_commit=o.LocalCommitState.CONFIRMED, qualification=qualification.validity)
            try:
                _require(type(disposition) is o.Disposition)
                g._revalidate(disposition)
                _require(_same(disposition.candidate, inputs.candidate)
                    and disposition.operation == inputs.candidate.operation
                    and disposition.local_commit is o.LocalCommitState.CONFIRMED)
                outcome = {PublicationDispositionKind.CONFIRMED: service.ExternalOutcome.CONFIRMED,
                    PublicationDispositionKind.DEFINITELY_REJECTED: service.ExternalOutcome.DEFINITELY_REJECTED,
                    PublicationDispositionKind.UNKNOWN: service.ExternalOutcome.UNKNOWN}[qualification.disposition]
                _require(disposition.outcome is outcome or
                    (outcome is service.ExternalOutcome.UNKNOWN and disposition.outcome is None))
            except _INVALID: return finish(S.UNRESOLVED, R.CANONICAL_DISPOSITION_CONTRADICTION)
            changed = instability()
            if changed is not None: return finish(S.UNRESOLVED, changed)
            interrupted.result = _issue(S.UNRESOLVED, R.EVALUATION_INTERRUPTED,
                saved, assessment, observation, qualification, disposition,
                verified=True, evaluated=True, invoked=True, qualified=True)
            if qualification.disposition is PublicationDispositionKind.CONFIRMED:
                return finish(S.PUBLISHED, R.PUBLISHED)
            if qualification.disposition is PublicationDispositionKind.DEFINITELY_REJECTED:
                return finish(S.DEFINITELY_REJECTED, R.EXTERNAL_DEFINITELY_REJECTED)
            return finish(S.UNRESOLVED, R.DISPOSITION_UNKNOWN)
        except BaseException as error:
            # The last detached snapshot is a monotonic evidence floor. No
            # dependency call, allocation, retry, recovery or durability claim.
            raise interrupted from error
