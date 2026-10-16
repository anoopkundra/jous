"""Increment A: read-only current qualification, never writer permission.

The trusted composition root selects the single read/qualification dependency
and its supported deterministic model interpretations outside request evidence.
The callback authenticates retention provenance AND current facts. Its proof
must cover the complete response, including continuity throughout the finite
model elapsed scope; an instantaneous read or echoed VALID bits cannot do so.
Neither callback shape nor constructors authenticate a provider. Python is not
a sandbox against a compromised composer or privileged mutation of internals.

No model formula, clock measurement, future writer point, coverage, provider,
credential, persistence or effect other than one qualification read is selected.
Increment B must capture its own point and evaluate these scoped inputs afresh.
"""
from dataclasses import dataclass, fields
from enum import StrEnum
from types import FunctionType, MethodType

from . import fixture_lease_admission_retention as r

s, a, g = r.s, r.a, r.a.g


class QualificationState(StrEnum):
    QUALIFIED = 'QUALIFIED'
    REJECTED = 'REJECTED'
    UNRESOLVED = 'UNRESOLVED'


class QualificationReason(StrEnum):
    QUALIFIED = 'QUALIFIED'
    SOURCE = 'SOURCE'
    DEPENDENCY = 'DEPENDENCY'
    UNAVAILABLE = 'UNAVAILABLE'
    RESPONSE = 'RESPONSE'
    MUTATED = 'MUTATED'
    BINDING = 'BINDING'
    INVALID = 'INVALID'
    UNKNOWN = 'UNKNOWN'
    MODEL = 'MODEL'
    SCOPE = 'SCOPE'
    DOMAIN = 'DOMAIN'
    PROVENANCE = 'PROVENANCE'
    TIME = 'TIME'
    APPLICABILITY = 'APPLICABILITY'


class ErrorConventions(StrEnum):
    # Identifies accounting/rounding, not a drift formula or production model.
    DESIGN7_NS_OUTWARD = 'DESIGN7_NS_OUTWARD_SAMPLE_PLUS_SUBSEQUENT_ERROR'


@dataclass(frozen=True, repr=False)
class ModelSupport:
    """Trusted composition's locally supported interpretation, not request code.

    interpretation identifies independently approved deterministic semantics;
    qualification identifies their implementation/accounting qualification.
    Composer must actually support that exact interpretation without I/O later.
    This declaration alone does not qualify applicability to a current sample.
    """
    model: s.EvidenceReference
    interpretation: s.EvidenceReference
    qualification: s.EvidenceReference
    profile: s.EvidenceReference
    source: str
    max_elapsed_ns: int
    conventions: ErrorConventions

    def __post_init__(self):
        _children(self)
        for value in (self.model, self.interpretation, self.qualification, self.profile):
            s.require(type(value) is s.EvidenceReference)
        s.identity(self.source)
        s.integer(self.max_elapsed_ns, 1)
        s.require(type(self.conventions) is ErrorConventions)


@dataclass(frozen=True, repr=False)
class PropagationModelBinding:
    """Qualified model applicability, NOT a future point-specific error.

    Scope uses elapsed nanoseconds from sample.anchor, inclusive endpoints.
    Current observation must be at its lower endpoint; upper must be later.
    All current facts in CurrentQualification must have independently justified
    continuity throughout this scope. It never extends any deadline. Later
    consumers still evaluate age, error, uncertainty and deadlines at their point.
    Missing process/domain provenance is representable but cannot qualify.
    """
    support: ModelSupport
    sample: s.EvidenceReference
    process_id: str | None
    domain_id: str | None
    min_elapsed_ns: int
    max_elapsed_ns: int
    applicability: s.EvidenceValidity
    qualification: s.EvidenceReference

    def __post_init__(self):
        _children(self)
        s.require(type(self.support) is ModelSupport and type(self.sample) is s.EvidenceReference)
        for value in (self.process_id, self.domain_id):
            if value is not None: s.identity(value)
        s.integer(self.min_elapsed_ns, 0)
        s.integer(self.max_elapsed_ns, 0)
        s.require(type(self.applicability) is s.EvidenceValidity)
        s.require(type(self.qualification) is s.EvidenceReference)


@dataclass(frozen=True, repr=False)
class CurrentQualification:
    """Untrusted response except when returned by the composed qualifier.

    authority/qualification must resolve authenticated proof of this whole graph:
    original protected retention, exact original permit, current eligibility,
    single-flight, no invalidating closure/supersession/competing operation,
    host/fencing/predecessor, authorization/revocation, approval applicability,
    sample/profile/model provenance and observation freshness. Continuity is
    warranted over model.min_elapsed_ns..max_elapsed_ns, not just at time.point.
    It must NOT equate the outstanding original permit with an unrelated gap.
    """
    source: r.RetentionResult
    authority: s.EvidenceReference
    qualification: s.EvidenceReference
    continuity: s.EvidenceValidity
    single_flight: s.EvidenceValidity
    activation: s.EvidenceValidity
    host: s.EvidenceValidity
    fencing: s.EvidenceValidity
    predecessor: s.EvidenceValidity
    provenance: s.EvidenceValidity
    process_domain: s.EvidenceValidity
    freshness: s.EvidenceValidity
    authorization: g.AuthorizationEvidence
    approval: g.ApprovalEvidence
    time: g.TimeEvidence
    model: PropagationModelBinding
    fixing_to_refresh: s.QualifiedPropagationError | None = None

    def __post_init__(self):
        _children(self)
        s.require(type(self.source) is r.RetentionResult)
        s.require(type(self.authority) is s.EvidenceReference and type(self.qualification) is s.EvidenceReference)
        s.require(all(type(v) is s.EvidenceValidity for v in _validities(self)))
        s.require(type(self.authorization) is g.AuthorizationEvidence and type(self.approval) is g.ApprovalEvidence)
        s.require(type(self.time) is g.TimeEvidence and type(self.model) is PropagationModelBinding)
        s.require(self.fixing_to_refresh is None or type(self.fixing_to_refresh) is s.QualifiedPropagationError)


@dataclass(frozen=True, repr=False)
class TrustedQualificationAdapter:
    """Read-only composition dependency; never selected through request data.

    qualify(source) is one logical authenticated observation AND qualification.
    No artificial second callback. All effects are prohibited except reads.
    supported_models are preselected local implementations, not an executable
    registry supplied in the callback response. No fallback or lazy resolution.
    """
    authority: s.EvidenceReference
    supported_models: tuple[ModelSupport, ...]
    qualify: object

    def __post_init__(self):
        s.require(type(self) is TrustedQualificationAdapter)
        s.require(type(self.authority) is s.EvidenceReference)
        r._validate(self.authority)
        s.require(type(self.supported_models) is tuple and 0 < len(self.supported_models) <= 64)
        for model in self.supported_models:
            s.require(type(model) is ModelSupport)
            _validate(model)
        s.require(len({_project(model) for model in self.supported_models}) == len(self.supported_models))
        s.require(type(self.qualify) is FunctionType or type(self.qualify) is MethodType)


def _own_types():
    return (ModelSupport, PropagationModelBinding, CurrentQualification,
            r.RetentionResult, QualifiedAdmissionInputs, AdmissionQualificationResult)


def _children(value):
    kind = type(value)
    s.require(any(kind is t for t in _own_types()))
    for field in fields(kind):
        child = object.__getattribute__(value, field.name)
        if kind is CurrentQualification and field.name == 'source':
            # Response source semantics come from exact equality to the saved,
            # fully validated source. Close its graph here without decoding the
            # same large canonical history again in every response constructor.
            s.require(type(child) is r.RetentionResult)
            _project(child)
        else:
            _validate(child)


def _validate(value):
    kind = type(value)
    if any(kind is t for t in (QualificationState, QualificationReason, ErrorConventions)): return
    if any(kind is t for t in _own_types()):
        # Classification/traversal before any lower semantic equality or hooks.
        if kind is r.RetentionResult: _project(value)
        kind.__post_init__(value)
    else:
        r._validate(value)


def _project(value):
    kind = type(value)
    if any(kind is t for t in (QualificationState, QualificationReason, ErrorConventions)): return kind, value
    if any(kind is t for t in _own_types()):
        return kind, tuple((f.name, _project(object.__getattribute__(value, f.name))) for f in fields(kind))
    return r._project(value)


def _copy(value): return a._copy_projection(_project(value))


def _unchanged(value, projection):
    try: return _project(value) == projection
    except a._REJECTIONS: return False


def _validities(q):
    return (q.continuity, q.single_flight, q.activation, q.host, q.fencing,
            q.predecessor, q.provenance, q.process_domain, q.freshness)


def _check(q, source, authority, models):
    """Pure semantic checks after closed validation. Returns finite knowledge."""
    reject, unresolved = QualificationState.REJECTED, QualificationState.UNRESOLVED
    if _project(q.source) != _project(source) or q.authority != authority:
        return reject, QualificationReason.BINDING, None
    bundle = source.prepared.material.source.attempt.bundle
    original_time = source.prepared.material.source.qualification.time
    auth, approval, time, model = q.authorization, q.approval, q.time, q.model
    # Current qualification may change validity, never original scope/bounds.
    if (auth.context, auth.principal, auth.activation, auth.reference, auth.valid_from_us, auth.deadline) != (
            bundle.authorization.context, bundle.authorization.principal, bundle.authorization.activation,
            bundle.authorization.reference, bundle.authorization.valid_from_us, bundle.authorization.deadline):
        return reject, QualificationReason.BINDING, None
    if (approval.applicability, approval.verified, approval.reference, approval.valid_from_us, approval.deadline) != (
            bundle.approval.applicability, bundle.approval.verified, bundle.approval.reference,
            bundle.approval.valid_from_us, bundle.approval.deadline):
        if approval.applicability is s.ApprovalApplicability.UNKNOWN:
            return unresolved, QualificationReason.APPLICABILITY, None
        return reject, QualificationReason.BINDING, None
    if any(v is s.TimingApplicability.UNKNOWN for v in
           (time.freshness_applicability, time.lease_applicability)):
        return unresolved, QualificationReason.APPLICABILITY, None
    if (time.profile != original_time.profile or
            (time.freshness_applicability, time.freshness_deadline, time.lease_applicability, time.lease_deadline) !=
            (original_time.freshness_applicability, original_time.freshness_deadline,
             original_time.lease_applicability, original_time.lease_deadline)):
        return reject, QualificationReason.BINDING, None
    support = model.support
    if not any(_project(support) == _project(v) for v in models):
        return reject, QualificationReason.MODEL, None
    if (support.profile != time.profile.profile or support.source != time.sample.source or
            support.max_elapsed_ns > time.profile.max_elapsed_ns or
            model.sample != time.sample.sample):
        return reject, QualificationReason.MODEL, None
    if model.process_id is None or model.domain_id is None:
        return unresolved, QualificationReason.PROVENANCE, None
    domain = (time.sample.anchor.process_id, time.sample.anchor.domain_id)
    if ((model.process_id, model.domain_id) != domain or
            (time.point.process_id, time.point.domain_id) != domain or
            domain != (original_time.point.process_id, original_time.point.domain_id)):
        return reject, QualificationReason.DOMAIN, None
    elapsed = time.point.ticks_ns - time.sample.anchor.ticks_ns
    if (elapsed < 0 or model.min_elapsed_ns != elapsed or model.max_elapsed_ns <= elapsed or
            model.max_elapsed_ns > min(time.profile.max_elapsed_ns, support.max_elapsed_ns) or
            s.ceil_us(model.max_elapsed_ns) > time.profile.max_sample_age_us or
            time.sample.anchor.ticks_ns + model.max_elapsed_ns > (1 << 63) - 1 or
            time.point.ticks_ns < original_time.point.ticks_ns):
        return reject, QualificationReason.SCOPE, None
    validities = _validities(q) + (auth.validity, approval.validity, model.applicability)
    if any(v is s.EvidenceValidity.INVALID for v in validities):
        return reject, QualificationReason.INVALID, None
    if any(v is s.EvidenceValidity.UNKNOWN for v in validities):
        return unresolved, QualificationReason.UNKNOWN, None
    try:
        if time.sample != original_time.sample:
            s.require(q.fixing_to_refresh is not None and s.refresh_consistent(
                original_time.sample, time.sample, time.profile, q.fixing_to_refresh))
        else:
            s.require(q.fixing_to_refresh is None)
        evaluation = s.evaluate_time(time.sample, time.profile, time.point, time.propagation)
        interval = evaluation.interval
        permit = source.prepared.material.source.qualification.permit
        s.require(s.valid_from_satisfied(interval, permit.valid_from_us))
        s.require(s.strict_bound(interval, s.StrictDeadline(permit.valid_until_us)) is s.TimingBound.SATISFIED)
        s.require(s.valid_from_satisfied(interval, auth.valid_from_us))
        s.require(s.inclusive_bound(interval, auth.deadline) is s.TimingBound.SATISFIED)
        if approval.applicability is s.ApprovalApplicability.REQUIRED:
            s.require(s.valid_from_satisfied(interval, approval.valid_from_us))
            s.require(s.inclusive_bound(interval, approval.deadline) is s.TimingBound.SATISFIED)
        for applicability, deadline in ((time.freshness_applicability, time.freshness_deadline),
                                        (time.lease_applicability, time.lease_deadline)):
            s.require(applicability is not s.TimingApplicability.UNKNOWN)
            s.require((applicability is s.TimingApplicability.REQUIRED) == (deadline is not None))
            if deadline is not None:
                s.require(s.strict_bound(interval, deadline) is s.TimingBound.SATISFIED)
        s.require(interval.lower_us >= source.envelope.fixed_utc_us)
    except s.TimeRejected:
        return reject, QualificationReason.TIME, None
    return QualificationState.QUALIFIED, QualificationReason.QUALIFIED, evaluation


class _KnowledgeOnly:
    """No truthiness-to-authority conversion; copying is not issuance."""
    def __bool__(self): raise TypeError('Inspect qualification state explicitly')
    def __copy__(self): raise TypeError('Knowledge must be evaluated')
    def __deepcopy__(self, memo): raise TypeError('Knowledge must be evaluated')

    @property
    def current_permit_consumable(self): return False
    @property
    def admission_coverage_confirmed(self): return False
    @property
    def begin_permitted(self): return False
    @property
    def transaction_owned(self): return False
    @property
    def sql_permitted(self): return False
    @property
    def writer_admission_permitted(self): return False
    @property
    def local_mutation_permitted(self): return False
    @property
    def commit_permitted(self): return False
    @property
    def local_commit_confirmed(self): return False
    @property
    def candidate_construction_permitted(self): return False
    @property
    def candidate_retention_permitted(self): return False
    @property
    def publication_permitted(self): return False
    @property
    def completion_permitted(self): return False
    @property
    def ack_construction_permitted(self): return False
    @property
    def ack_delivery_permitted(self): return False
    @property
    def active_permitted(self): return False
    @property
    def retry_permitted(self): return False
    @property
    def reacquisition_permitted(self): return False
    @property
    def renewal_permitted(self): return False
    @property
    def cancellation_permitted(self): return False
    @property
    def fence_clearance_permitted(self): return False
    @property
    def recovery_execution_permitted(self): return False
    @property
    def runtime_activation_permitted(self): return False


@dataclass(frozen=True, repr=False, init=False)
class QualifiedAdmissionInputs(_KnowledgeOnly):
    """Detached evaluator-issued knowledge; no future point or executable code."""
    observation: CurrentQualification
    evaluation: s.TimeEvaluation
    support: ModelSupport

    def __init__(self, *args, **kwargs): raise TypeError('Use current qualification')

    def __post_init__(self):
        s.require(type(self) is QualifiedAdmissionInputs)
        s.require(type(self.observation) is CurrentQualification and type(self.evaluation) is s.TimeEvaluation)
        s.require(type(self.support) is ModelSupport)
        _validate(self.observation); r._validate(self.evaluation); _validate(self.support)
        q = self.observation
        _validate(q.source)
        state, reason, evaluation = _check(q, q.source, r._authority(q.source.prepared), (self.support,))
        s.require(state is QualificationState.QUALIFIED and reason is QualificationReason.QUALIFIED)
        s.require(evaluation == self.evaluation)


@dataclass(frozen=True, repr=False, init=False)
class AdmissionQualificationResult(_KnowledgeOnly):
    state: QualificationState
    reason: QualificationReason
    source: r.RetentionResult | None
    attempted: bool
    inputs: QualifiedAdmissionInputs | None

    def __init__(self, *args, **kwargs): raise TypeError('Use current qualification')

    def __post_init__(self):
        s.require(type(self) is AdmissionQualificationResult)
        s.require(type(self.state) is QualificationState and type(self.reason) is QualificationReason)
        s.require(type(self.attempted) is bool)
        if self.state is QualificationState.QUALIFIED:
            s.require(self.reason is QualificationReason.QUALIFIED and self.attempted)
            s.require(type(self.inputs) is QualifiedAdmissionInputs)
            _validate(self.inputs)
            s.require(_project(self.source) == _project(self.inputs.observation.source))
        else:
            if self.source is not None: _validate(self.source)
            s.require(self.inputs is None and self.reason is not QualificationReason.QUALIFIED)
            if self.reason is QualificationReason.SOURCE:
                s.require(self.state is QualificationState.REJECTED and not self.attempted and self.source is None)
            else:
                s.require(self.source is not None and self.source.state is r.RetentionState.RETAINED)
                s.require(self.attempted is (self.reason is not QualificationReason.DEPENDENCY))
                unresolved = (QualificationReason.DEPENDENCY, QualificationReason.UNAVAILABLE,
                    QualificationReason.UNKNOWN, QualificationReason.PROVENANCE, QualificationReason.APPLICABILITY)
                s.require(self.state is (QualificationState.UNRESOLVED if self.reason in unresolved
                                        else QualificationState.REJECTED))


def _assemble(kind, **values):
    # Internal assembly after evaluator checks, not a public issuance API.
    # __post_init__ remains the complete independent revalidation contract.
    # Re-decoding unchanged retained history in every intermediate assembly
    # provides no additional qualification; exact detached projections suffice.
    s.require(kind is QualifiedAdmissionInputs or kind is AdmissionQualificationResult)
    result = object.__new__(kind)
    for name, value in values.items(): object.__setattr__(result, name, value)
    return result


def _result(state, reason, source=None, attempted=False, inputs=None):
    return _assemble(AdmissionQualificationResult, state=state, reason=reason,
                     source=source, attempted=attempted, inputs=inputs)


def qualify_admission_inputs(source, adapter=None):
    """Validate/detach -> one composed qualification read -> check/detach -> stop.

    Only explicitly classified availability errors are mapped. Programming
    defects propagate; no raw external diagnostic enters a result. Rejection
    never asserts closure/absence/cancellation of the original permit.
    """
    rejected, unresolved = QualificationState.REJECTED, QualificationState.UNRESOLVED
    try:
        s.require(type(source) is r.RetentionResult)
        original = _project(source)
        saved = a._copy_projection(original)
        _validate(saved)
        s.require(saved.state is r.RetentionState.RETAINED)
        s.require(_unchanged(source, original))
    except a._REJECTIONS:
        return _result(rejected, QualificationReason.SOURCE)
    if type(adapter) is not TrustedQualificationAdapter:
        return _result(unresolved, QualificationReason.DEPENDENCY, saved)
    try:
        TrustedQualificationAdapter.__post_init__(adapter)
        s.require(adapter.authority == r._authority(saved.prepared))
    except a._REJECTIONS:
        return _result(unresolved, QualificationReason.DEPENDENCY, saved)
    # Snapshot all bindings AND callback before invocation, never reread adapter.
    qualify = adapter.qualify
    authority = _copy(adapter.authority)
    models = tuple(_copy(v) for v in adapter.supported_models)
    request = _copy(saved)
    try:
        response = qualify(request)
    except (s.CapabilityUnavailable, a.ExternalAvailabilityFailure, TimeoutError):
        mutated = not _unchanged(source, original) or not _unchanged(request, original)
        return _result(rejected if mutated else unresolved,
                       QualificationReason.MUTATED if mutated else QualificationReason.UNAVAILABLE, saved, True)
    if not _unchanged(source, original) or not _unchanged(request, original):
        return _result(rejected, QualificationReason.MUTATED, saved, True)
    try:
        s.require(type(response) is CurrentQualification)
        _validate(response)
        state, reason, evaluation = _check(response, saved, authority, models)
    except a._REJECTIONS:
        return _result(rejected, QualificationReason.RESPONSE, saved, True)
    if state is not QualificationState.QUALIFIED:
        return _result(state, reason, saved, True)
    detached = _copy(response)
    _validate(detached)
    state, reason, detached_evaluation = _check(detached, saved, authority, models)
    s.require(state is QualificationState.QUALIFIED and detached_evaluation == evaluation)
    inputs = _assemble(QualifiedAdmissionInputs, observation=detached,
                       evaluation=_copy(evaluation), support=_copy(detached.model.support))
    return _result(state, reason, saved, True, inputs)
