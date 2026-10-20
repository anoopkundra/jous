"""Initial-publication prerequisite knowledge only; never dispatch permission.

The trusted composer authenticates the COMPLETE assessment, including negative
and unknown findings. Syntax, equality, references and local markers confer no
authority. All current evidence is already acquired; this module owns no I/O,
clock acquisition, publication, permit effect, recovery or runtime wiring.
"""
from dataclasses import dataclass, fields
from enum import StrEnum
from types import FunctionType, MethodType

from . import fixture_lease_candidate_retention as d
from . import fixture_lease_publication_gate as g

s, c, o, cp, p = d.s, d.c, g.outcomes, g.checkpoints, g.p


class PublicationQualificationState(StrEnum):
    QUALIFIED = 'QUALIFIED'
    REJECTED = 'REJECTED'
    UNRESOLVED = 'UNRESOLVED'


class PublicationQualificationReason(StrEnum):
    QUALIFIED = 'QUALIFIED'
    INVALID_D_SOURCE = 'INVALID_D_SOURCE'
    NOT_RETAINED = 'NOT_RETAINED'
    UPSTREAM_UNRESOLVED = 'UPSTREAM_UNRESOLVED'
    INHERITED_RECONCILIATION = 'INHERITED_RECONCILIATION'
    UNQUALIFIED_D_PROVENANCE = 'UNQUALIFIED_D_PROVENANCE'
    D_PROVENANCE_UNKNOWN = 'D_PROVENANCE_UNKNOWN'
    CANDIDATE_BINDING_MISMATCH = 'CANDIDATE_BINDING_MISMATCH'
    ORIGINAL_OPERATION_MISMATCH = 'ORIGINAL_OPERATION_MISMATCH'
    COMMITTED_TRANSITION_MISMATCH = 'COMMITTED_TRANSITION_MISMATCH'
    RETENTION_BINDING_MISMATCH = 'RETENTION_BINDING_MISMATCH'
    RETENTION_UNQUALIFIED = 'RETENTION_UNQUALIFIED'
    HISTORICAL_EVIDENCE_CONTRADICTION = 'HISTORICAL_EVIDENCE_CONTRADICTION'
    CURRENT_AUTHORITY_INELIGIBLE = 'CURRENT_AUTHORITY_INELIGIBLE'
    CURRENT_AUTHORITY_UNKNOWN = 'CURRENT_AUTHORITY_UNKNOWN'
    PREDECESSOR_MISMATCH = 'PREDECESSOR_MISMATCH'
    PREDECESSOR_UNKNOWN = 'PREDECESSOR_UNKNOWN'
    TEMPORAL_OUTSIDE = 'TEMPORAL_OUTSIDE'
    TEMPORAL_UNCERTAIN = 'TEMPORAL_UNCERTAIN'
    TIME_UNQUALIFIED = 'TIME_UNQUALIFIED'
    TIME_BINDING_MISMATCH = 'TIME_BINDING_MISMATCH'
    PUBLICATION_HISTORY_NON_INITIAL = 'PUBLICATION_HISTORY_NON_INITIAL'
    PUBLICATION_HISTORY_UNKNOWN = 'PUBLICATION_HISTORY_UNKNOWN'
    MALFORMED_ASSESSMENT = 'MALFORMED_ASSESSMENT'
    UNQUALIFIED_ASSESSMENT = 'UNQUALIFIED_ASSESSMENT'
    ASSESSMENT_BINDING_MISMATCH = 'ASSESSMENT_BINDING_MISMATCH'
    SOURCE_INSTABILITY = 'SOURCE_INSTABILITY'
    REQUEST_INSTABILITY = 'REQUEST_INSTABILITY'
    RESPONSE_INSTABILITY = 'RESPONSE_INSTABILITY'
    DEPENDENCY_INSTABILITY = 'DEPENDENCY_INSTABILITY'
    GATE_INSTABILITY = 'GATE_INSTABILITY'
    DEPENDENCY_UNAVAILABLE = 'DEPENDENCY_UNAVAILABLE'
    CANONICAL_GATE_CONTRADICTION = 'CANONICAL_GATE_CONTRADICTION'


class _EvaluationBinding:
    """Immutable process-local correlation only, not issuance or permission."""
    __slots__ = ()

    def __new__(cls):
        raise TypeError('Evaluator-local correlation only')

    def __copy__(self):
        raise TypeError('Evaluator-local correlation only')

    def __deepcopy__(self, memo):
        raise TypeError('Evaluator-local correlation only')


@dataclass(frozen=True, repr=False)
class TrustedPublicationQualificationAdapter:
    """Composition-only trust root. qualify is one local read-only assessment.

    No provider/database/network/clock access, waits, discovery, effects, retries
    or fallback. VALID authenticates negative/unknown assessments too. Production
    trust and already-acquired current evidence are separately qualified owners.
    """
    authority: s.EvidenceReference
    implementation: s.EvidenceReference
    qualify: object


@dataclass(frozen=True, repr=False)
class PublicationQualificationRequest:
    source: d.RetentionResult
    evaluation: _EvaluationBinding


@dataclass(frozen=True, repr=False)
class PublicationAssessment:
    """Independent provenance for this entire source/current/evaluation bundle.

    The reference must cover genuine D issuance, exact historical completion and
    retention, all supplied current authority/time/history claims, their scope
    and applicability, and this request. Construction or VALID is not proof.
    """
    request: PublicationQualificationRequest
    authority: s.EvidenceReference
    implementation: s.EvidenceReference
    validity: s.EvidenceValidity
    reference: s.EvidenceReference
    source_provenance: s.EvidenceValidity
    inputs: g.GateInputs | None


@dataclass(frozen=True, repr=False)
class _QualifiedPublication:
    source: d.RetentionResult
    assessment: PublicationAssessment
    gate: g.GateResult
    reconciliation_required: bool


@dataclass(frozen=True, repr=False)
class _RejectedPublication:
    source: d.RetentionResult | None
    assessment: PublicationAssessment | None
    gate: g.GateResult | None
    reconciliation_required: bool


@dataclass(frozen=True, repr=False)
class _UnresolvedPublication:
    source: d.RetentionResult
    assessment: PublicationAssessment | None
    gate: g.GateResult | None
    reconciliation_required: bool


@dataclass(frozen=True, repr=False, init=False)
class PublicationQualificationResult:
    state: PublicationQualificationState
    reason: PublicationQualificationReason
    qualification_attempted: bool
    gate_evaluated: bool
    qualified: _QualifiedPublication | None
    rejected: _RejectedPublication | None
    unresolved: _UnresolvedPublication | None

    def __init__(self, *args, **kwargs):
        raise TypeError('Use PublicationQualifier.qualify_publication')

    def __bool__(self):
        raise TypeError('Prerequisite knowledge is not permission')

    def __copy__(self):
        raise TypeError('Use publication qualification')

    def __deepcopy__(self, memo):
        raise TypeError('Use publication qualification')


_PERMISSIONS = ('publication_permitted', 'cas_permitted', 'publication_retry_permitted',
    'publication_query_permitted', 'publication_disposition_effect_permitted',
    'original_permit_completion_permitted', 'ack_permitted', 'delivery_permitted',
    'redelivery_permitted', 'candidate_retention_permitted', 'permit_acquisition_permitted',
    'permit_renewal_permitted', 'recovery_permitted', 'fence_clearance_permitted',
    'runtime_progression_permitted')
for _name in _PERMISSIONS:
    setattr(PublicationQualificationResult, _name, property(lambda self: False))


class _Malformed(ValueError):
    pass


def _require(condition):
    if not condition:
        raise _Malformed()


_ENUMS = d._ENUMS + (PublicationQualificationState, PublicationQualificationReason,
    g.GateState, g.GateReason, g.CurrentStatus, g.InitialOperationState,
    s.ExternalOutcome, s.TimingBound, o.LocalCommitState, o.Stage, o.RequiredGate, o.Reason)
_VALUES = d._VALUES + (g.LocalCompletionEvidence, g.CurrentAuthorityEvidence,
    g.CurrentTimeEvidence, g.GateInputs, g.GateResult, o.Disposition, o.RecoveryHandoff,
    s.PublicationResult, s.CompletionResult, cp.CommittedHead,
    PublicationQualificationRequest, PublicationAssessment, _QualifiedPublication,
    _RejectedPublication, _UnresolvedPublication, PublicationQualificationResult)
_INVALID = (_Malformed,) + d._INVALID
_AVAILABILITY = d._AVAILABILITY
R, S = PublicationQualificationReason, PublicationQualificationState
_matches = c._matches
_ATOMS = (type(None), str, bytes, int, bool, _EvaluationBinding)
_ATOM_IDS = {id(cls): cls for cls in _ATOMS}
_ENUM_MEMBERS = {id(cls): (cls, tuple(cls)) for cls in _ENUMS}
_FIELD_TYPES = {id(cls): (cls, tuple((f.name, f.type) for f in fields(cls))) for cls in _VALUES}


def _project(value):
    """Closed identity-memoized traversal; no history/STATE budget or duck typing."""
    active, memo = set(), {}

    def visit(item):
        kind = type(item)
        if _ATOM_IDS.get(id(kind)) is kind:
            return kind, item
        enum = _ENUM_MEMBERS.get(id(kind))
        if enum is not None and enum[0] is kind:
            _require(any(item is member for member in enum[1]))
            return kind, item
        schema = _FIELD_TYPES.get(id(kind))
        _require(kind is tuple or (schema is not None and schema[0] is kind))
        identity = id(item)
        _require(identity not in active)
        if identity in memo:
            return memo[identity]
        active.add(identity)
        if kind is tuple:
            projected = kind, tuple(visit(v) for v in item)
        else:
            children = []
            for name, annotation in schema[1]:
                try:
                    child = object.__getattribute__(item, name)
                except AttributeError:
                    raise _Malformed() from None
                node = visit(child)
                _require(type(child) is annotation or _matches(child, annotation))
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
        if _ATOM_IDS.get(id(kind)) is kind or id(kind) in _ENUM_MEMBERS:
            return data
        identity = id(node)
        if identity in memo:
            return memo[identity]
        if kind is tuple:
            value = tuple(detach(child) for child in data)
        else:
            value = object.__new__(kind)
            for name, child in data:
                object.__setattr__(value, name, detach(child))
        memo[identity] = value
        return value
    return detach(projection)


def _copy(value):
    return _detach(_project(value))


def _equal(left, right):
    """Exact equality of OWN projections; memoize DAG pairs, never caller values.

    Integer identity keys avoid foreign class hashing/equality. Only exact
    primitives use value equality; enum members/markers/class tags use identity.
    This preserves comparison semantics without rewalking shared histories.
    """
    seen = set()

    def compare(a, b):
        if a is b:
            return True
        kind, data = a
        other, value = b
        if kind is not other:
            return False
        if kind is _EvaluationBinding or id(kind) in _ENUM_MEMBERS:
            return data is value
        if _ATOM_IDS.get(id(kind)) is kind:
            return data == value
        pair = id(a), id(b)
        if pair in seen:
            return True
        seen.add(pair)
        if len(data) != len(value):
            return False
        if kind is tuple:
            return all(compare(x, y) for x, y in zip(data, value))
        return all(name == other_name and compare(x, y)
                   for (name, x), (other_name, y) in zip(data, value))
    return compare(left, right)


def _stable(value, projection):
    try:
        return _equal(_project(value), projection)
    except _Malformed:
        return False


def _source(value):
    """Necessary D algebra/bindings only; never an issuance assertion."""
    _require(type(value) is d.RetentionResult)
    expected = {d.RetentionState.RETAINED: ('retained', d._RetainedCandidate),
        d.RetentionState.REJECTED: ('rejected', d._RejectedCandidate),
        d.RetentionState.UNRESOLVED: ('unresolved', d._UnresolvedCandidate)}
    name, cls = expected[value.state]
    _require(sum(x is not None for x in (value.retained, value.rejected, value.unresolved)) == 1)
    payload = object.__getattribute__(value, name)
    _require(type(payload) is cls)
    _require(not value.qualification_attempted or value.verification_attempted)
    _require(not value.qualification_attempted or payload.association_invoked)
    _require(not payload.association_invoked or value.verification_attempted)
    _require(payload.association_invoked or payload.disposition is None)
    if payload.source is not None:
        d._source(payload.source)
    if value.state is not d.RetentionState.RETAINED:
        _require(value.reason not in (d.RetentionReason.RETAINED_FIRST_ASSOCIATION,
                                      d.RetentionReason.RETAINED_EXACT_EXISTING))
        if value.state is d.RetentionState.UNRESOLVED:
            _require(payload.reconciliation_required)
        else:
            _require(value.reason in (d.RetentionReason.INVALID_C_SOURCE, d.RetentionReason.NOT_PREPARED,
                d.RetentionReason.UNQUALIFIED_C_PROVENANCE, d.RetentionReason.HISTORICAL_T1_INVALID,
                d.RetentionReason.PROGRESSION_PROHIBITED, d.RetentionReason.ASSOCIATION_CONFLICT,
                d.RetentionReason.PROVEN_PRE_DISPATCH_FAILURE, d.RetentionReason.PROVEN_PRE_DISPATCH_UNAVAILABLE,
                d.RetentionReason.PROVEN_NON_DISPATCH))
            if value.reason is d.RetentionReason.INVALID_C_SOURCE:
                _require(payload.source is None and not value.verification_attempted
                    and not value.qualification_attempted and not payload.association_invoked)
        return
    material = payload.source
    _require(material is not None and material.state is c.PreparationState.PREPARED)
    eligibility = payload.eligibility
    _require(value.verification_attempted and eligibility.validity is s.EvidenceValidity.VALID)
    authority = d._namespace(material)
    d._eligibility(eligibility, material, authority, eligibility.implementation)
    d._retention(payload.retention, material)
    if payload.association_invoked:
        _require(value.reason is d.RetentionReason.RETAINED_FIRST_ASSOCIATION
            and value.qualification_attempted
            and eligibility.history is d.AssociationHistory.ELIGIBLE_FIRST_ASSOCIATION
            and eligibility.progression is d.ProgressionStatus.CLEAR)
        disposition = payload.disposition
        _require(type(disposition) is d.AssociationQualification)
        observation = disposition.observation
        _require(observation.source == material and observation.eligibility == eligibility)
        if observation.returned_candidate is not None:
            s.verify_candidate_association(material.prepared.candidate, observation.returned_candidate)
        d._disposition(disposition, observation, authority, eligibility.implementation)
        _require(disposition.validity is s.EvidenceValidity.VALID
            and disposition.disposition is d.AssociationDisposition.RETAINED
            and disposition.retention == payload.retention)
    else:
        _require(value.reason is d.RetentionReason.RETAINED_EXACT_EXISTING
            and not value.qualification_attempted and payload.disposition is None
            and eligibility.history is d.AssociationHistory.EXACT_EXISTING
            and eligibility.retention == payload.retention)
    _require(payload.reconciliation_required is
             (eligibility.progression is not d.ProgressionStatus.CLEAR))


def _bindings(source, inputs):
    """Compare only closed detached values; do not qualify current assertions."""
    prepared = source.retained.source.prepared
    candidate, snapshot = prepared.candidate, prepared.request.snapshot
    completed = prepared.request.completion.completed
    if inputs.candidate != candidate:
        return R.CANDIDATE_BINDING_MISMATCH
    candidates = tuple(x.candidate for x in (inputs.local, inputs.retention, inputs.authority, inputs.time)
                       if x is not None)
    if any(x != candidate for x in candidates):
        return R.CANDIDATE_BINDING_MISMATCH
    if inputs.prior is not None and inputs.prior.candidate != candidate:
        return R.CANDIDATE_BINDING_MISMATCH
    if any(x.operation != candidate.operation for x in (inputs.retention, inputs.authority) if x is not None):
        return R.ORIGINAL_OPERATION_MISMATCH
    if inputs.prior is not None and inputs.prior.operation != o._operation(candidate, inputs.prior.stage):
        return R.ORIGINAL_OPERATION_MISMATCH
    local = inputs.local
    if local is not None:
        expected = (snapshot.completion, snapshot.events, snapshot.projection, snapshot.context,
            cp.CommittedHead(completed.event_sequence, completed.event_digest, completed.state_digest),
            snapshot.keys, snapshot.definite_expiry)
        if (local.completion, local.events, local.projection, local.context,
                local.head, local.keys, local.definite_expiry) != expected:
            return R.COMMITTED_TRANSITION_MISMATCH
    if inputs.retention is not None and inputs.retention != source.retained.retention:
        # Qualification downgrade is historical contradiction, not new evidence.
        a, b = inputs.retention, source.retained.retention
        if (a.candidate, a.operation, a.reference) != (b.candidate, b.operation, b.reference):
            return R.RETENTION_BINDING_MISMATCH
    authority = inputs.authority
    if authority is not None:
        env = candidate.envelope
        if (authority.permit, authority.principal, authority.activation, authority.host,
                authority.predecessor, authority.representation, authority.representation_authority) != (
                completed.permit, env.principal, env.activation, env.activation.host_identity,
                env.predecessor, env.predecessor.representation, env.predecessor.representation_authority):
            return R.ASSESSMENT_BINDING_MISMATCH
    return None


def _time_reason(candidate, authority, time):
    """Finite diagnostics only. Only the canonical gate can satisfy prerequisites."""
    if time is None or time.qualification is not s.EvidenceValidity.VALID:
        return S.UNRESOLVED, R.TIME_UNQUALIFIED
    fixing = candidate.envelope.fixing
    if fixing is None or time.profile != fixing.profile:
        return S.UNRESOLVED, R.TIME_BINDING_MISMATCH
    try:
        original = s.evaluate_time(fixing.sample, fixing.profile, fixing.point, fixing.propagation).interval
        if (fixing.envelope, fixing.context, fixing.activation, fixing.sample.validation, original) != (
                candidate.envelope.reference, candidate.envelope.context, candidate.envelope.activation,
                candidate.envelope.time_qualification, candidate.envelope.fixing_interval):
            return S.UNRESOLVED, R.TIME_BINDING_MISMATCH
        if original.lower_us != candidate.fixed_utc_us:
            return S.UNRESOLVED, R.TIME_BINDING_MISMATCH
        if time.sample != fixing.sample and (time.fixing_to_refresh is None or not
                s.refresh_consistent(fixing.sample, time.sample, time.profile, time.fixing_to_refresh)):
            return S.UNRESOLVED, R.TIME_BINDING_MISMATCH
        interval = s.evaluate_time(time.sample, time.profile, time.point, time.propagation).interval
    except c._INVALID:
        return S.UNRESOLVED, R.TIME_UNQUALIFIED
    if (time.covered_interval != interval or authority.point != time.point or authority.interval != interval
            or interval.lower_us < candidate.fixed_utc_us):
        return S.UNRESOLVED, R.TIME_BINDING_MISMATCH
    if interval.lower_us < authority.permit.valid_from_us:
        return (S.REJECTED, R.TEMPORAL_OUTSIDE) if interval.upper_us < authority.permit.valid_from_us else (
            S.UNRESOLVED, R.TEMPORAL_UNCERTAIN)
    bound = s.strict_bound(interval, s.StrictDeadline(authority.permit.valid_until_us))
    if bound is s.TimingBound.OUTSIDE:
        return S.REJECTED, R.TEMPORAL_OUTSIDE
    if bound is s.TimingBound.UNCERTAIN:
        return S.UNRESOLVED, R.TEMPORAL_UNCERTAIN
    for applicability, deadline, predicate in (
            (time.authorization_timing, time.authorization_deadline, s.inclusive_bound),
            (time.freshness_timing, time.freshness_deadline, s.strict_bound)):
        if applicability is s.TimingApplicability.UNKNOWN:
            return S.UNRESOLVED, R.TIME_UNQUALIFIED
        if applicability is s.TimingApplicability.REQUIRED:
            bound = predicate(interval, deadline)
            if bound is s.TimingBound.OUTSIDE:
                return S.REJECTED, R.TEMPORAL_OUTSIDE
            if bound is s.TimingBound.UNCERTAIN:
                return S.UNRESOLVED, R.TEMPORAL_UNCERTAIN
    return None


def _conclusion(inputs, gate):
    authority, local, retention = inputs.authority, inputs.local, inputs.retention
    prior = inputs.prior
    if (authority is not None and authority.initial_operation is g.InitialOperationState.UNKNOWN) or (
            prior is not None and (prior.outcome is None or prior.outcome is s.ExternalOutcome.UNKNOWN
                or prior.recovery is not None or prior.prior_recovery is not None)):
        return S.UNRESOLVED, R.PUBLICATION_HISTORY_UNKNOWN
    if prior is not None or (authority is not None and authority.initial_operation is not g.InitialOperationState.INITIAL):
        return S.UNRESOLVED, R.PUBLICATION_HISTORY_NON_INITIAL
    if local is None or local.state is not o.LocalCommitState.CONFIRMED or local.qualification is not s.EvidenceValidity.VALID:
        return S.UNRESOLVED, R.HISTORICAL_EVIDENCE_CONTRADICTION
    if retention is None or retention.qualification is not s.EvidenceValidity.VALID:
        return S.UNRESOLVED, R.RETENTION_UNQUALIFIED
    if authority is None:
        return S.UNRESOLVED, R.CURRENT_AUTHORITY_UNKNOWN
    validity = (authority.permit_validity, authority.activation_validity, authority.host_validity,
                authority.fencing_validity, authority.representation_validity)
    statuses = (authority.activation_status, authority.host_status, authority.fencing_status)
    if any(v is s.EvidenceValidity.UNKNOWN for v in validity) or any(v is g.CurrentStatus.UNKNOWN for v in statuses):
        return S.UNRESOLVED, R.CURRENT_AUTHORITY_UNKNOWN
    if any(v is s.EvidenceValidity.INVALID for v in validity) or any(v is g.CurrentStatus.INELIGIBLE for v in statuses):
        return S.REJECTED, R.CURRENT_AUTHORITY_INELIGIBLE
    if authority.predecessor_validity is s.EvidenceValidity.UNKNOWN:
        return S.UNRESOLVED, R.PREDECESSOR_UNKNOWN
    if authority.predecessor_validity is s.EvidenceValidity.INVALID:
        return S.REJECTED, R.PREDECESSOR_MISMATCH
    timing = _time_reason(inputs.candidate, authority, inputs.time)
    if timing is not None:
        return timing
    if gate.state is g.GateState.SATISFIED and gate.reason is g.GateReason.SATISFIED:
        return S.QUALIFIED, R.QUALIFIED
    return S.UNRESOLVED, R.CANONICAL_GATE_CONTRADICTION


def _issue(state, reason, source=None, assessment=None, gate=None, attempted=False, evaluated=False):
    qualified = rejected = unresolved = None
    if state is S.QUALIFIED:
        _require(reason is R.QUALIFIED and assessment is not None and gate is not None)
        qualified = _QualifiedPublication(source, assessment, gate, False)
    elif state is S.REJECTED:
        upstream = None if source is None else next(v for v in
            (source.retained, source.rejected, source.unresolved) if v is not None)
        rejected = _RejectedPublication(source, assessment, gate,
            upstream is not None and (source.state is d.RetentionState.RETAINED or upstream.reconciliation_required))
    else:
        _require(source is not None)
        unresolved = _UnresolvedPublication(source, assessment, gate, True)
    result = object.__new__(PublicationQualificationResult)
    for name, value in (('state', state), ('reason', reason), ('qualification_attempted', attempted),
            ('gate_evaluated', evaluated), ('qualified', qualified), ('rejected', rejected), ('unresolved', unresolved)):
        object.__setattr__(result, name, value)
    return _copy(result)


def _dependencies():
    """Explicit transitive validation surface, not runtime call-graph discovery.

    Gate -> checkpoint -> completed command/ACK/events/STATE -> conflict codec;
    source -> C snapshot/A admission validators -> acquisition/predecessor checks.
    Constructors, reader methods and retained-disposition validation are included.
    No evaluator, provider, persistence or lifecycle operation is traversed.
    """
    q, r, a, pg, pr, envelope = c.q, c.r, c.a, c.g, c.pr, c.e
    names = ((g, ('evaluate_publication_gate', '_evaluate', '_time_valid', '_revalidate', '_children', '_dataclass_type',
                      'fields', 'GateResult', 's', 'p', 'checkpoints', 'outcomes')),
        (cp, ('validate_candidate', 'construct_candidate', 'decode_checkpoint', 'checkpoint_bytes', 'decode_reference', 'reference_bytes',
              '_command_result_coherent', 'sha256', 'NormalReference', 'NormalCheckpoint', 'CommittedHead', 'p', 'service')),
        (s, ('verify_candidate_association', 'evaluate_time', 'refresh_consistent', 'strict_bound', 'inclusive_bound',
             'valid_from_satisfied', 'floor_us', 'ceil_us', 'require', 'integer', 'identity', '_digest',
             'verify_publication_result', 'verify_completion_result', 'sha256', 'Fraction', 'EvidenceReference',
             'CommandContext', 'OriginalOperation', 'CheckpointCandidate', 'RetainedTimeFixing', 'RetainedAdmissionEnvelope',
             'UtcInterval', 'TimeEvaluation', 'StrictDeadline')),
        (p, ('state_digest', 'state_chunks', 'decode_record', 'encode_record', 'command_bytes', 'ack_bytes',
             'validate_completed_command', 'validate_ack', 'validate_event_chain', 'event_order', 'key_set_digest',
             'command_digest', 'event_digest', 'event_bytes', '_validate_record', 'validate_command', 'validate_primary',
             '_validate_binding', 'validate_references', '_encode', '_decode', '_enum', 'frame', 'parse_frame', '_read_frame',
             'collection', 'u32', 'uint', 'utc', 'identifier', 'digest_value', 'blob', 'require', 'sha256', '_Reader',
             'Reference', 'Parameters', 'CommandPayload', 'AckPayload', 'EventPayload', 'ReservationRow', 'StateProjection',
             'EventType', 'contract')),
        (d, ('_source', '_eligibility', '_retention', '_disposition', '_namespace', '_reference', '_require', 'sha256', 's', 'c', 'g')),
        (o, ('_operation', '_history', '_observe', '_publication_knowledge', '_qualified_outcome', '_knowledge', '_required', 'service')),
        (c, ('_domain', '_bindings', '_snapshot', '_matches', '_need', 'get_args', 'get_origin', 'fields', 'sha256',
             'protocol', 'service', 'checkpoints', 'q', 'contract')),
        (q, ('_validate', '_children', '_own_types', '_project', '_validities', '_check', 'fields', 's', 'r', 'a', 'g')),
        (r, ('_validate', '_children', '_project', '_authority', '_receipt_checks', '_confirmation_checks', '_map_envelope',
             'fields', 'OriginalRecordIndex', 's', 'a', 'e')),
        (envelope, ('_source_validate', '_evaluation', 'a', 's')),
        (a, ('_validate', '_children', '_projection', '_qualification_checks', 'fields', 'sha256', 'g', 's')),
        (pg, ('_kind', '_children', '_revalidate', '_check', '_snapshot', 'fields', 'sha256', 's', 'p', 'c', 'pr')),
        (pr, ('_dataclass_type', '_children', '_revalidate', '_precheck', '_postcheck', 'fields', 'sha256', 's', 'p', 'checkpoints')),
        (p.contract, ('decode_conflict', 'frame_conflict', '_text', '_require', 'ConflictKey', 'ConflictFamily',
                      'sha256_evidence', 'sha256')),
        (p._Reader, ('__init__', 'take', 'count', 'end')),
        (p.contract.ConflictKey, ('__post_init__', 'canonical_bytes')),
        (p.contract.ArtifactBytes, ('evidence_sha256',)))
    bindings = tuple((owner, name, getattr(owner, name)) for owner, group in names for name in group)
    validators = tuple((cls, '__post_init__', cls.__post_init__)
        for cls in _VALUES + (cp.NormalCheckpoint, cp.NormalReference) if hasattr(cls, '__post_init__'))
    constructors = (g.GateResult, cp.NormalReference, cp.NormalCheckpoint, cp.CommittedHead,
        s.EvidenceReference, s.CommandContext, s.OriginalOperation, s.CheckpointCandidate,
        s.RetainedTimeFixing, s.RetainedAdmissionEnvelope, s.UtcInterval, s.TimeEvaluation, s.StrictDeadline,
        p.Reference, p.Parameters, p.CommandPayload, p.AckPayload, p.EventPayload, p.ReservationRow, p.StateProjection,
        r.OriginalRecordIndex, p.contract.ConflictKey)
    return bindings + validators + tuple((cls, '__init__', cls.__init__) for cls in constructors)


def _dispatch_dependencies():
    """Only persistent dispatch tables reached by the frozen E validation path.

    Domains follow the nine reachable protocol record schemas, including
    nullable fields in retained history. Schema entries are closed immutable
    tuples: preserving their identity therefore preserves the complete value.
    Never enumerate a supplied mapping or invoke its equality/lookup hooks.
    """
    enums, schemas = p._ENUMS, p._SCHEMAS
    if type(enums) is not dict or type(schemas) is not dict:
        raise TypeError('Malformed frozen protocol dispatch composition')
    domains = ('Command', 'Operation', 'Phase', 'ArtifactType', 'LeaseStatus',
        'ExecutionState', 'QuarantineReason', 'EventType', 'OutcomeCode')
    records = (p.Reference, p.Parameters, p.CommandPayload, p.EventPayload, p.AckPayload,
        p.MetadataRow, p.ReservationRow, p.ClaimRow, p.CommandRow)
    enum_entries = tuple((key, dict.__getitem__(enums, key)) for key in domains)
    schema_entries = tuple((key, dict.__getitem__(schemas, key)) for key in records)
    for key, value in schema_entries:
        if not (type(value) is tuple and len(value) == 3
                and type(value[0]) is int and type(value[1]) is int and type(value[2]) is tuple
                and all(type(field) is tuple and len(field) == 2
                    and type(field[0]) is str and type(field[1]) is str for field in value[2])):
            raise TypeError('Mutable or malformed frozen protocol schema')
    return ((p, '_ENUMS', enums, enum_entries), (p, '_SCHEMAS', schemas, schema_entries))


@dataclass(frozen=True, repr=False, init=False)
class PublicationQualifier:
    _adapter: TrustedPublicationQualificationAdapter
    _authority: s.EvidenceReference
    _implementation: s.EvidenceReference
    _qualify: object
    _gate: object
    _bindings: tuple
    _dispatch: tuple

    def __init__(self, adapter: TrustedPublicationQualificationAdapter):
        try:
            _require(type(adapter) is TrustedPublicationQualificationAdapter)
            authority = _copy(object.__getattribute__(adapter, 'authority'))
            implementation = _copy(object.__getattribute__(adapter, 'implementation'))
            d._reference(authority); d._reference(implementation)
            qualify = object.__getattribute__(adapter, 'qualify')
            _require(type(qualify) is FunctionType or type(qualify) is MethodType)
        except (AttributeError,) + _INVALID:
            raise TypeError('Malformed publication qualification composition') from None
        for name, value in (('_adapter', adapter), ('_authority', authority), ('_implementation', implementation),
                ('_qualify', qualify), ('_gate', g.evaluate_publication_gate), ('_bindings', _dependencies()),
                ('_dispatch', _dispatch_dependencies())):
            object.__setattr__(self, name, value)

    def _composition_stable(self):
        try:
            return (self._adapter.qualify is self._qualify
                and self._gate is g.evaluate_publication_gate
                and _equal(_project(self._adapter.authority), _project(self._authority))
                and _equal(_project(self._adapter.implementation), _project(self._implementation))
                and all(getattr(owner, name) is captured for owner, name, captured in self._bindings)
                and all(getattr(owner, name) is mapping and type(mapping) is dict
                    and all(dict.get(mapping, key) is captured for key, captured in entries)
                    for owner, name, mapping, entries in self._dispatch))
        except (AttributeError, _Malformed):
            return False

    def qualify_publication(self, source: d.RetentionResult) -> PublicationQualificationResult:
        try:
            _require(type(source) is d.RetentionResult)
            projection = _project(source)
            saved = _detach(projection)
            if not self._composition_stable():
                return _issue(S.UNRESOLVED, R.DEPENDENCY_INSTABILITY, saved)
            _source(saved)
        except _INVALID:
            return _issue(S.REJECTED, R.INVALID_D_SOURCE)
        if saved.state is not d.RetentionState.RETAINED:
            state, reason = ((S.UNRESOLVED, R.UPSTREAM_UNRESOLVED) if saved.state is d.RetentionState.UNRESOLVED
                             else (S.REJECTED, R.NOT_RETAINED))
            return _issue(state, reason, saved)
        if saved.retained.reconciliation_required:
            return _issue(S.UNRESOLVED, R.INHERITED_RECONCILIATION, saved)
        request = response = gate_inputs = gate = assessment = observed_gate = None
        request_projection = response_projection = gate_projection = observed_projection = None
        attempted = evaluated = False

        def instability():
            if not _stable(source, projection): return R.SOURCE_INSTABILITY
            if request_projection is not None and not _stable(request, request_projection): return R.REQUEST_INSTABILITY
            if response_projection is not None and not _stable(response, response_projection): return R.RESPONSE_INSTABILITY
            if not self._composition_stable(): return R.DEPENDENCY_INSTABILITY
            if gate_projection is not None and not _stable(gate_inputs, gate_projection): return R.GATE_INSTABILITY
            if observed_projection is not None and not _stable(observed_gate, observed_projection): return R.GATE_INSTABILITY
            return None

        def finish(state, reason):
            # Final payload allocation precedes the last external graph checks.
            result = _issue(state, reason, saved, assessment, gate, attempted, evaluated)
            changed = instability()
            if changed is not None:
                return _issue(S.UNRESOLVED, changed, saved, attempted=attempted, evaluated=evaluated)
            return result

        if d._namespace(saved.retained.source) != self._authority:
            return finish(S.UNRESOLVED, R.ASSESSMENT_BINDING_MISMATCH)
        marker = object.__new__(_EvaluationBinding)
        request = PublicationQualificationRequest(_copy(saved), marker)
        request_projection = _project(request)
        changed = instability()
        if changed is not None: return finish(S.UNRESOLVED, changed)
        attempted = True
        try:
            response = self._qualify(request)
        except _AVAILABILITY:
            return finish(S.UNRESOLVED, R.DEPENDENCY_UNAVAILABLE)
        changed = instability()
        if changed is not None: return finish(S.UNRESOLVED, changed)
        try:
            _require(type(response) is PublicationAssessment)
            response_projection = _project(response)
            assessment = _detach(response_projection)
            for ref in (assessment.authority, assessment.implementation, assessment.reference): d._reference(ref)
            _require((assessment.source_provenance is s.EvidenceValidity.VALID and assessment.inputs is not None)
                or (assessment.source_provenance is not s.EvidenceValidity.VALID and assessment.inputs is None))
        except _INVALID:
            assessment = None
            return finish(S.UNRESOLVED, R.MALFORMED_ASSESSMENT)
        # Step 7: the ORIGINAL response is re-projected after detachment and
        # validation. finish preserves global instability priority on failure.
        if not _stable(response, response_projection):
            return finish(S.UNRESOLVED, R.RESPONSE_INSTABILITY)
        if not self._composition_stable():
            return finish(S.UNRESOLVED, R.DEPENDENCY_INSTABILITY)
        if assessment.validity is not s.EvidenceValidity.VALID:
            return finish(S.UNRESOLVED, R.UNQUALIFIED_ASSESSMENT)
        if (assessment.request.evaluation is not marker or not _equal(_project(assessment.request), request_projection)
                or assessment.authority != self._authority or assessment.implementation != self._implementation):
            return finish(S.UNRESOLVED, R.ASSESSMENT_BINDING_MISMATCH)
        if assessment.source_provenance is not s.EvidenceValidity.VALID:
            state, reason = ((S.REJECTED, R.UNQUALIFIED_D_PROVENANCE) if assessment.source_provenance is s.EvidenceValidity.INVALID
                             else (S.UNRESOLVED, R.D_PROVENANCE_UNKNOWN))
            return finish(state, reason)
        problem = _bindings(saved, assessment.inputs)
        if problem is not None: return finish(S.UNRESOLVED, problem)
        # Canonical constructors see only closed detached values. They establish
        # shape/semantics, never authentication of the supplied complete claim.
        try:
            g._revalidate(assessment.inputs)
        except c._INVALID:
            return finish(S.UNRESOLVED, R.MALFORMED_ASSESSMENT)
        gate_inputs = _copy(assessment.inputs)
        gate_projection = _project(gate_inputs)
        changed = instability()
        if changed is not None: return finish(S.UNRESOLVED, changed)
        evaluated = True
        observed_gate = self._gate(gate_inputs)
        changed = instability()
        if changed is not None: return finish(S.UNRESOLVED, changed)
        try:
            _require(type(observed_gate) is g.GateResult)
            observed_projection = _project(observed_gate)
            gate = _detach(observed_projection)
            _require(gate.inputs is not None and _equal(_project(gate.inputs), gate_projection))
            _require((gate.state is g.GateState.SATISFIED) is (gate.reason is g.GateReason.SATISFIED))
        except _INVALID:
            gate = None
            return finish(S.UNRESOLVED, R.CANONICAL_GATE_CONTRADICTION)
        if not _stable(observed_gate, observed_projection):
            return finish(S.UNRESOLVED, R.GATE_INSTABILITY)
        state, reason = _conclusion(assessment.inputs, gate)
        if state is not S.QUALIFIED and gate.state is g.GateState.SATISFIED:
            return finish(S.UNRESOLVED, R.CANONICAL_GATE_CONTRADICTION)
        return finish(state, reason)
