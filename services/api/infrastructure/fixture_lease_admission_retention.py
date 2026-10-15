"""One original-record envelope retention effect, never writer admission.

Trusted application composition selects this adapter outside request evidence.
Its verifier independently qualifies original protected permit provenance and
retention authority; its qualifier independently confirms durable immutable
retention and the section 5 original-record lookup/index association. Callback
shape and constructors are not authentication. Production providers, durable
history/single-flight enforcement and authentication remain separately gated.

No new permit, operation key, canonical envelope codec or local journal exists.
The only effect is retain(material), once. Confirmation fixes no new time and
does not establish current permit consumability or actual admission coverage.
"""
from dataclasses import dataclass, fields
from enum import StrEnum
from types import FunctionType, MethodType

from . import fixture_lease_admission_envelope as e
from . import fixture_lease_permit_acquisition as a
from . import fixture_lease_service as s


class RetentionState(StrEnum):
    RETAINED = 'QUALIFIED_ORIGINAL_ENVELOPE_RETENTION'
    FAIL_CLOSED = 'PRE_DISPATCH_FAILURE'
    HANDOFF = 'UNRESOLVED_HANDOFF'


class RetentionReason(StrEnum):
    RETAINED = 'RETAINED'
    MALFORMED = 'MALFORMED'
    NOT_PREPARED = 'NOT_PREPARED'
    UPSTREAM_UNRESOLVED = 'UPSTREAM_UNRESOLVED'
    AUTHORITY_UNAVAILABLE = 'AUTHORITY_UNAVAILABLE'
    UNQUALIFIED_AUTHORITY = 'UNQUALIFIED_AUTHORITY'
    MUTATED = 'MUTATED'
    RETENTION_UNAVAILABLE = 'RETENTION_UNAVAILABLE'
    MALFORMED_RECEIPT = 'MALFORMED_RECEIPT'
    QUALIFICATION_UNAVAILABLE = 'QUALIFICATION_UNAVAILABLE'
    UNQUALIFIED_CONFIRMATION = 'UNQUALIFIED_CONFIRMATION'


@dataclass(frozen=True, repr=False)
class OriginalRecordIndex:
    """Untrusted claim of the protected original-record lookup association.

    Context includes exact command_id and canonical digest; activation includes
    register/generation/activation/host and predecessor. Principal is separate.
    A qualified response must prove this association and its retained history
    lifetime, not merely echo these matching fields or a provider-native ID.
    """
    context: s.CommandContext
    principal: str
    activation: s.ActivationIdentity
    permit: s.EvidenceReference
    envelope: s.EvidenceReference

    def __post_init__(self):
        _children(self)
        s.require(type(self.context) is s.CommandContext and type(self.activation) is s.ActivationIdentity)
        s.identity(self.principal)
        s.require(type(self.permit) is s.EvidenceReference and type(self.envelope) is s.EvidenceReference)


@dataclass(frozen=True, repr=False)
class RetentionAuthorization:
    """Claim accepted only from the composed pre-dispatch verifier invocation."""
    prepared: e.PreparationResult
    permit: s.EvidenceReference
    authority: s.EvidenceReference
    validity: s.EvidenceValidity
    reference: s.EvidenceReference

    def __post_init__(self):
        _children(self)
        s.require(type(self.prepared) is e.PreparationResult and self.prepared.state is e.PreparationState.PREPARED)
        s.require(all(type(v) is s.EvidenceReference for v in (self.permit, self.authority, self.reference)))
        s.require(type(self.validity) is s.EvidenceValidity)


@dataclass(frozen=True, repr=False)
class RetentionReceipt:
    """Unqualified transport observation; not a competing retained envelope.

    reference is externally issued for the exact immutable prepared evidence.
    No constructor or returned boolean proves its existence or durability.
    """
    material: e.PreparedEnvelopeMaterial
    reference: s.EvidenceReference
    index: OriginalRecordIndex

    def __post_init__(self):
        _children(self)
        s.require(type(self.material) is e.PreparedEnvelopeMaterial)
        s.require(type(self.reference) is s.EvidenceReference and type(self.index) is OriginalRecordIndex)


@dataclass(frozen=True, repr=False)
class RetentionConfirmation:
    """Qualifier response: original association, durable retention AND lookup.

    Three validity claims cannot self-certify. They are accepted only from the
    separately composed independent qualifier, bound to the exact receipt and
    prepared graph. Its reference must resolve authenticated proof of immutable
    retained evidence and required original-record indexing/history lifetime.
    """
    receipt: RetentionReceipt
    authority: s.EvidenceReference
    validity: s.EvidenceValidity
    durable: s.EvidenceValidity
    indexed: s.EvidenceValidity
    reference: s.EvidenceReference

    def __post_init__(self):
        _children(self)
        s.require(type(self.receipt) is RetentionReceipt)
        s.require(type(self.authority) is s.EvidenceReference and type(self.reference) is s.EvidenceReference)
        s.require(all(type(v) is s.EvidenceValidity for v in (self.validity, self.durable, self.indexed)))


@dataclass(frozen=True, repr=False)
class TrustedRetentionAdapter:
    """Composition dependency; never selectable through request evidence.

    verify(prepared) qualifies original permit/authority/material provenance.
    retain(material) performs the sole effect against that original record.
    qualify(prepared, receipt) independently proves retention and index facts.
    Verification/qualification are reads, not fallback retention or acquisition.
    Exact function/method checks enforce shape only; names confer no authority.
    A compromised composition root is outside the untrusted request boundary.
    """
    authority: s.EvidenceReference
    verify: object
    retain: object
    qualify: object

    def __post_init__(self):
        s.require(type(self) is TrustedRetentionAdapter)
        s.require(type(self.authority) is s.EvidenceReference)
        a._validate(self.authority)
        for name in ('verify', 'retain', 'qualify'):
            kind = type(object.__getattribute__(self, name))
            s.require(kind is FunctionType or kind is MethodType)


def _children(value):
    kind = type(value)
    s.require(any(kind is approved for approved in (OriginalRecordIndex, RetentionAuthorization,
        RetentionReceipt, RetentionConfirmation, e.PreparationResult, e.PreparedEnvelopeMaterial,
        s.RetainedAdmissionEnvelope, s.RetainedTimeFixing)))
    for f in fields(kind): _validate(object.__getattribute__(value, f.name))


def _validate(value):
    """Closed exact classes before traversal, equality, hashing or validation."""
    kind = type(value)
    if kind is a.AcquisitionResult: e._source_validate(value)
    elif any(kind is t for t in (e.PreparationState, e.PreparationReason, RetentionState, RetentionReason)): return
    elif kind is e.PreparationResult or kind is e.PreparedEnvelopeMaterial:
        # Frozen preparation validators already establish the complete closed
        # graph before semantic comparisons; do not duplicate their traversal.
        kind.__post_init__(value)
    elif kind is s.RetainedAdmissionEnvelope or kind is s.RetainedTimeFixing:
        _children(value)
        kind.__post_init__(value)
    elif any(kind is t for t in (OriginalRecordIndex, RetentionAuthorization, RetentionReceipt, RetentionConfirmation)):
        kind.__post_init__(value)
    else: a._validate(value)


def _project(value):
    """Closed structural projection, including full bytes and concrete types.

    After callbacks, exact equality to the already semantically validated
    projection revalidates every bound field without re-running expensive pure
    codecs on an unchanged graph. Changed graphs reject rather than normalize.
    """
    kind = type(value)
    if value is None or any(kind is t for t in (bytes, str, int, bool)):
        a.g._revalidate(value)
        return kind, value
    if kind is tuple:
        s.require(len(value) <= a.g.p.MAX_FIELD // (len(a.g.p.PREFIX) + 6 + 12 + 2 + 32))
        return kind, tuple(_project(item) for item in value)
    enums = (e.PreparationState, e.PreparationReason, RetentionState, RetentionReason,
        a.AcquisitionState, a.AcquisitionReason, a.g.GateState, a.g.GateReason,
        a.g.CommandHistory, a.g.GapKnowledge, s.ApprovalApplicability, s.EvidenceValidity,
        s.TimingApplicability, a.g.c.Command, a.g.c.Operation, a.g.c.Phase, a.g.c.ArtifactType,
        a.g.p.ExecutionState, a.g.p.QuarantineReason, a.g.pr.PredecessorProfile,
        a.g.pr.CurrentStatus, a.g.pr.HostStatus, a.g.pr.FencingStatus,
        a.g.pr.ResolutionState, a.g.pr.ResolutionReason)
    if any(kind is t for t in enums): return kind, value
    own = (OriginalRecordIndex, RetentionAuthorization, RetentionReceipt, RetentionConfirmation,
           e.PreparationResult, e.PreparedEnvelopeMaterial, a.AcquisitionResult,
           a.AcquisitionInput, a.PermitQualification, a.g.GateResult, s.CommandPermit,
           s.RetainedAdmissionEnvelope, s.RetainedTimeFixing)
    if not any(kind is t for t in own): a.g._kind(value)
    return kind, tuple((f.name, _project(object.__getattribute__(value, f.name))) for f in fields(kind))


def _copy(value): return a._copy_projection(_project(value))


def _unchanged(value, projection):
    try:
        return _project(value) == projection
    except a._REJECTIONS: return False


def _authority(prepared): return prepared.material.source.attempt.bundle.predecessor.context.requested.authority


def _receipt_checks(receipt, prepared):
    s.require(_project(receipt.material) == _project(prepared.material))
    material = prepared.material
    bundle = material.source.attempt.bundle
    expected = OriginalRecordIndex(bundle.context, bundle.requester.principal, bundle.activation,
                                   material.source.qualification.permit.evidence, receipt.reference)
    s.require(receipt.index == expected)


def _confirmation_checks(confirmation, prepared):
    s.require(all(v is s.EvidenceValidity.VALID for v in
                  (confirmation.validity, confirmation.durable, confirmation.indexed)))
    s.require(confirmation.authority == _authority(prepared))
    _receipt_checks(confirmation.receipt, prepared)


def _map_envelope(prepared, reference):
    """Only after independent qualified confirmation; no new codec or UTC."""
    material = prepared.material
    bundle = material.source.attempt.bundle
    time = material.source.qualification.time
    fixing = s.RetainedTimeFixing(reference, bundle.context, bundle.activation,
                                time.sample, time.profile, time.point, time.propagation)
    return s.RetainedAdmissionEnvelope(reference, bundle.canonical_command, bundle.context,
        bundle.requester.principal, material.source.qualification.permit.evidence, bundle.activation,
        bundle.predecessor.observation.predecessor, bundle.approval.applicability, bundle.approval.reference,
        material.fixed_utc_us, material.evaluation.interval, material.sample_validation, fixing)


@dataclass(frozen=True, repr=False, init=False)
class RetentionResult:
    """Qualified retention knowledge or unresolved evidence, never admission."""
    state: RetentionState
    reason: RetentionReason
    prepared: e.PreparationResult | None
    dispatched: bool
    confirmation: RetentionConfirmation | None
    envelope: s.RetainedAdmissionEnvelope | None

    def __init__(self, *args, **kwargs): raise TypeError('Use original-record retention')

    def __post_init__(self):
        s.require(type(self) is RetentionResult and type(self.state) is RetentionState)
        s.require(type(self.reason) is RetentionReason and type(self.dispatched) is bool)
        if self.prepared is not None:
            s.require(type(self.prepared) is e.PreparationResult); _validate(self.prepared)
        if self.state is RetentionState.RETAINED:
            s.require(self.reason is RetentionReason.RETAINED and self.dispatched)
            s.require(self.prepared is not None and self.prepared.state is e.PreparationState.PREPARED)
            s.require(type(self.confirmation) is RetentionConfirmation and type(self.envelope) is s.RetainedAdmissionEnvelope)
            _validate(self.confirmation); _validate(self.envelope)
            _confirmation_checks(self.confirmation, self.prepared)
            s.require(self.envelope == _map_envelope(self.prepared, self.confirmation.receipt.reference))
        else:
            s.require(self.confirmation is None and self.envelope is None and self.reason is not RetentionReason.RETAINED)
            if self.state is RetentionState.HANDOFF:
                s.require(self.prepared is not None)
                if not self.dispatched:
                    s.require(self.reason is RetentionReason.UPSTREAM_UNRESOLVED
                              and self.prepared.state is e.PreparationState.HANDOFF)
                else:
                    s.require(self.prepared.state is e.PreparationState.PREPARED)
                    s.require(self.reason in (RetentionReason.MUTATED, RetentionReason.RETENTION_UNAVAILABLE,
                        RetentionReason.MALFORMED_RECEIPT, RetentionReason.QUALIFICATION_UNAVAILABLE,
                        RetentionReason.UNQUALIFIED_CONFIRMATION))
            else:
                s.require(not self.dispatched and self.reason in (RetentionReason.MALFORMED,
                    RetentionReason.NOT_PREPARED, RetentionReason.AUTHORITY_UNAVAILABLE,
                    RetentionReason.UNQUALIFIED_AUTHORITY, RetentionReason.MUTATED))

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


def _result(state, reason, prepared=None, dispatched=False, confirmation=None, envelope=None):
    result = object.__new__(RetentionResult)
    for name, value in (('state', state), ('reason', reason), ('prepared', prepared), ('dispatched', dispatched),
                        ('confirmation', confirmation), ('envelope', envelope)):
        object.__setattr__(result, name, value)
    RetentionResult.__post_init__(result)
    return result


_EXTERNAL_FAILURES = (s.CapabilityUnavailable, a.ExternalAvailabilityFailure, TimeoutError)


def retain_original_envelope(prepared, adapter=None):
    """Closed validation -> authority verification -> one retain -> qualification.

    Only adapter-classified external availability failures/timeouts are bounded;
    unexpected RuntimeError/AssertionError remain distinguishable. No provider
    diagnostic is returned. Post-dispatch uncertainty never means non-retention.
    """
    fail, handoff = RetentionState.FAIL_CLOSED, RetentionState.HANDOFF
    try:
        s.require(type(prepared) is e.PreparationResult); _validate(prepared)
    except a._REJECTIONS: return _result(fail, RetentionReason.MALFORMED)
    projection = _project(prepared)
    saved = _copy(prepared)
    _validate(saved)
    if saved.state is e.PreparationState.HANDOFF:
        return _result(handoff, RetentionReason.UPSTREAM_UNRESOLVED, saved)
    if saved.state is not e.PreparationState.PREPARED:
        return _result(fail, RetentionReason.NOT_PREPARED, saved)
    if type(adapter) is not TrustedRetentionAdapter:
        return _result(fail, RetentionReason.AUTHORITY_UNAVAILABLE, saved)
    try:
        TrustedRetentionAdapter.__post_init__(adapter)
        s.require(adapter.authority == _authority(saved))
    except (s.TimeRejected, AttributeError): return _result(fail, RetentionReason.AUTHORITY_UNAVAILABLE, saved)
    verify, retain, qualify = adapter.verify, adapter.retain, adapter.qualify
    authority = _copy(adapter.authority)
    try:
        authorization = verify(prepared)
    except _EXTERNAL_FAILURES:
        return _result(fail, RetentionReason.MUTATED if not _unchanged(prepared, projection)
                       else RetentionReason.AUTHORITY_UNAVAILABLE, saved)
    if not _unchanged(prepared, projection): return _result(fail, RetentionReason.MUTATED, saved)
    try:
        s.require(type(authorization) is RetentionAuthorization); _validate(authorization)
        s.require(authorization.validity is s.EvidenceValidity.VALID and authorization.authority == authority)
        s.require(authorization.permit == saved.material.source.qualification.permit.evidence)
        s.require(_project(authorization.prepared) == projection)
    except a._REJECTIONS: return _result(fail, RetentionReason.UNQUALIFIED_AUTHORITY, saved)
    try:
        receipt = retain(prepared.material)
    except _EXTERNAL_FAILURES:
        return _result(handoff, RetentionReason.MUTATED if not _unchanged(prepared, projection)
                       else RetentionReason.RETENTION_UNAVAILABLE, saved, True)
    if not _unchanged(prepared, projection): return _result(handoff, RetentionReason.MUTATED, saved, True)
    try:
        s.require(type(receipt) is RetentionReceipt); _validate(receipt)
        _receipt_checks(receipt, saved)
    except a._REJECTIONS: return _result(handoff, RetentionReason.MALFORMED_RECEIPT, saved, True)
    receipt_projection = _project(receipt)
    try:
        confirmation = qualify(prepared, receipt)
    except _EXTERNAL_FAILURES:
        changed = not _unchanged(prepared, projection) or not _unchanged(receipt, receipt_projection)
        return _result(handoff, RetentionReason.MUTATED if changed else RetentionReason.QUALIFICATION_UNAVAILABLE, saved, True)
    if not _unchanged(prepared, projection) or not _unchanged(receipt, receipt_projection):
        return _result(handoff, RetentionReason.MUTATED, saved, True)
    try:
        s.require(type(confirmation) is RetentionConfirmation); _validate(confirmation)
        _confirmation_checks(confirmation, saved)
        s.require(_project(confirmation.receipt) == receipt_projection)
    except a._REJECTIONS: return _result(handoff, RetentionReason.UNQUALIFIED_CONFIRMATION, saved, True)
    qualified = _copy(confirmation)
    _validate(qualified)
    envelope = _map_envelope(saved, qualified.receipt.reference)
    return _result(RetentionState.RETAINED, RetentionReason.RETAINED, saved, True, qualified, envelope)
