"""Pure pre-retention material preparation from evaluator-issued acquisition data.

This boundary revalidates already-qualified source knowledge; it authenticates
no provider or request-side qualification claims. It accepts only the frozen
AcquisitionResult, never a bare PermitQualification or a VALID label. There is
no callback/composition seam here. Privileged fabrication of evaluator internals
is not authentication. Later retention must independently qualify its authority.

RetainedAdmissionEnvelope and RetainedTimeFixing require an externally issued
envelope reference. They MUST NOT be constructed here. The material below keeps
their required source fields without inventing that reference or a wire codec.
Future admission-point coverage remains a separate downstream requirement.
"""
from dataclasses import dataclass, fields
from enum import StrEnum

from . import fixture_lease_permit_acquisition as a
from . import fixture_lease_service as s


class PreparationState(StrEnum):
    PREPARED = 'PREPARED_ADMISSION_ENVELOPE_MATERIAL'
    FAIL_CLOSED = 'FAIL_CLOSED'
    HANDOFF = 'UNRESOLVED_ACQUISITION_HANDOFF'


class PreparationReason(StrEnum):
    PREPARED = 'PREPARED'
    MALFORMED = 'MALFORMED'
    SOURCE_NOT_QUALIFIED = 'SOURCE_NOT_QUALIFIED'
    SOURCE_UNRESOLVED = 'SOURCE_UNRESOLVED'
    SOURCE_CHANGED = 'SOURCE_CHANGED'


def _source_validate(source):
    """Closed exact type checks before source traversal or frozen semantics."""
    s.require(type(source) is a.AcquisitionResult)
    s.require(type(object.__getattribute__(source, 'state')) is a.AcquisitionState)
    s.require(type(object.__getattribute__(source, 'reason')) is a.AcquisitionReason)
    s.require(type(object.__getattribute__(source, 'acquisition_attempted')) is bool)
    for name, allowed in (('attempt', a.AcquisitionInput), ('qualification', a.PermitQualification)):
        value = object.__getattribute__(source, name)
        s.require(value is None or type(value) is allowed)
        if value is not None: a._validate(value)
    a.AcquisitionResult.__post_init__(source)


def _source_projection(source):
    # Only after _source_validate: no foreign class/enum/equality inspection.
    return a.AcquisitionResult, tuple((f.name,
        (type(value), value) if f.name in ('state', 'reason') else a._projection(value))
        for f in fields(a.AcquisitionResult)
        for value in (object.__getattribute__(source, f.name),))


def _evaluation(source):
    time = source.qualification.time
    return s.evaluate_time(time.sample, time.profile, time.point, time.propagation)


@dataclass(frozen=True, repr=False, init=False)
class PreparedEnvelopeMaterial:
    """Detached pre-retention data, not retained evidence or durable confirmation.

    source retains the full exact command/prerequisite/predecessor/permit graph,
    including applicable approval and opaque immutable permit evidence bytes.
    It also retains the original observation's sample/profile/point/propagation.
    The two qualification references below are intentionally distinct roles;
    equality of their bytes, if present, cannot interchange their meanings.
    No retained-envelope identity or future admission coverage is supplied.
    """
    source: a.AcquisitionResult
    fixed_utc_us: int
    evaluation: s.TimeEvaluation
    sample_validation: s.EvidenceReference
    acquisition_qualification: s.EvidenceReference

    def __init__(self, *args, **kwargs):
        raise TypeError('Use preparation to obtain detached material')

    def __post_init__(self):
        s.require(type(self) is PreparedEnvelopeMaterial)
        _source_validate(self.source)
        s.require(self.source.state is a.AcquisitionState.QUALIFIED)
        s.integer(self.fixed_utc_us)
        for value, kind in ((self.evaluation, s.TimeEvaluation), (self.sample_validation, s.EvidenceReference),
                            (self.acquisition_qualification, s.EvidenceReference)):
            s.require(type(value) is kind)
            a._validate(value)
        evaluated = _evaluation(self.source)
        s.require(self.evaluation == evaluated and self.fixed_utc_us == evaluated.interval.lower_us)
        s.require(self.sample_validation == self.source.qualification.time.sample.validation)
        s.require(self.acquisition_qualification == self.source.qualification.reference)


@dataclass(frozen=True, repr=False, init=False)
class PreparationResult:
    """Knowledge only: malformed data never establishes permit absence/closure."""
    state: PreparationState
    reason: PreparationReason
    material: PreparedEnvelopeMaterial | None
    source: a.AcquisitionResult | None

    def __init__(self, *args, **kwargs):
        raise TypeError('Use pure envelope preparation')

    def __post_init__(self):
        s.require(type(self) is PreparationResult and type(self.state) is PreparationState)
        s.require(type(self.reason) is PreparationReason)
        if self.source is not None: _source_validate(self.source)
        if self.state is PreparationState.PREPARED:
            s.require(self.reason is PreparationReason.PREPARED and self.source is None)
            s.require(type(self.material) is PreparedEnvelopeMaterial)
            PreparedEnvelopeMaterial.__post_init__(self.material)
        else:
            s.require(self.material is None)
            if self.state is PreparationState.HANDOFF:
                s.require(self.reason is PreparationReason.SOURCE_UNRESOLVED and self.source is not None)
                s.require(self.source.state is a.AcquisitionState.UNRESOLVED_HANDOFF)
            elif self.reason is PreparationReason.SOURCE_NOT_QUALIFIED:
                s.require(self.source is not None and self.source.state is a.AcquisitionState.PRE_DISPATCH_FAILURE)
            else:
                s.require(self.reason in (PreparationReason.MALFORMED, PreparationReason.SOURCE_CHANGED)
                          and self.source is None)

    @property
    def external_retention_permitted(self): return False
    @property
    def durability_confirmed(self): return False
    @property
    def envelope_retained(self): return False
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
    def fence_clearance_permitted(self): return False
    @property
    def recovery_execution_permitted(self): return False
    @property
    def runtime_activation_permitted(self): return False


def _result(state, reason, material=None, source=None):
    result = object.__new__(PreparationResult)
    for name, value in (('state', state), ('reason', reason), ('material', material), ('source', source)):
        object.__setattr__(result, name, value)
    PreparationResult.__post_init__(result)
    return result


def prepare_admission_envelope(source):
    """Fix lower-bound UTC without acquiring time, identities or capabilities.

    Detach the complete closed graph, then revalidate the copy. No external
    operation or provider exception boundary exists. Only frozen input-domain
    rejections are bounded; internal AssertionError/RuntimeError propagate.
    """
    try:
        _source_validate(source)
        projection = _source_projection(source)
        detached = a._copy_projection(projection)
        _source_validate(detached)
        s.require(_source_projection(detached) == projection)
        _source_validate(source)
        if _source_projection(source) != projection:
            return _result(PreparationState.FAIL_CLOSED, PreparationReason.SOURCE_CHANGED)
    except a._REJECTIONS:
        return _result(PreparationState.FAIL_CLOSED, PreparationReason.MALFORMED)
    if detached.state is a.AcquisitionState.UNRESOLVED_HANDOFF:
        return _result(PreparationState.HANDOFF, PreparationReason.SOURCE_UNRESOLVED, source=detached)
    if detached.state is not a.AcquisitionState.QUALIFIED:
        return _result(PreparationState.FAIL_CLOSED, PreparationReason.SOURCE_NOT_QUALIFIED, source=detached)
    evaluated = _evaluation(detached)
    material = object.__new__(PreparedEnvelopeMaterial)
    for name, value in (('source', detached), ('fixed_utc_us', evaluated.interval.lower_us),
                        ('evaluation', evaluated), ('sample_validation', detached.qualification.time.sample.validation),
                        ('acquisition_qualification', detached.qualification.reference)):
        object.__setattr__(material, name, value)
    PreparedEnvelopeMaterial.__post_init__(material)
    return _result(PreparationState.PREPARED, PreparationReason.PREPARED, material=material)
