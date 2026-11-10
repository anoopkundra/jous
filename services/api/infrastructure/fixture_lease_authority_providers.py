"""Explicit IL6 provider composition; no transport, trust root or operational adoption.

Bound to provider contract 3efb8fef034181d8f4a1ae6d3caf2952ee99095c.
The records here are in-memory views of opaque external evidence, NEVER a wire
format, canonical object, permit, register, or local durable-history substitute.
Realization-specific authentication/retention/history clients require separate
selection, qualification and adoption. Every default rejects without I/O.
"""
from dataclasses import dataclass, fields, is_dataclass, replace
from hashlib import sha256

from . import fixture_lease_activation as a

s = a.service
require = a.require


@dataclass(frozen=True, repr=False)
class ProviderBinding:
    role: str
    realization: str
    principal: str
    credential_identity: str
    authority: str
    issuer: str
    namespace: str
    kind: str  # SYNTHETIC or OPERATIONAL; never promoted by this module
    qualification: s.EvidenceReference
    selection: s.EvidenceReference
    adoption: s.EvidenceReference


@dataclass(frozen=True, repr=False)
class RetainedEvidence:
    reference: s.EvidenceReference
    raw: bytes


@dataclass(frozen=True, repr=False)
class EvidenceExpectation:
    binding: ProviderBinding
    retention: ProviderBinding
    role: str
    context: tuple
    stage: str
    obligations: tuple


@dataclass(frozen=True, repr=False)
class AuthenticatedView:
    """Verifier output bound to the COMPLETE raw record and current trust status.

    The trusted verifier must authenticate peer, issuer, actor, scoped rights,
    credential continuity/revocation, selection/adoption, immutable retention and
    EVERY requested obligation (including transitive preimage restrictions).
    Merely constructing this view does not establish those facts.
    """
    reference: s.EvidenceReference
    expectation: EvidenceExpectation
    value: object
    clock: a.TimeBinding
    valid_from_us: int
    valid_until_us: int
    provenance: s.EvidenceReference


class EvidenceClient:
    """Qualified immutable external store. No delete/replace or local fallback.

    retain must preserve complete original bytes and audit/provenance before
    returning. resolve must independently retrieve them, including after restart.
    Failure/uncertainty is an exception, not a reconstructed record.
    """
    def retain(self, record):
        raise a.ActivationRejected("RETENTION_UNAVAILABLE")

    def resolve(self, reference):
        raise a.ActivationRejected("RESOLUTION_UNAVAILABLE")


class EvidenceVerifier:
    """Separately qualified trust boundary, not an arbitrary success callback.

    verify authenticates complete retained raw bytes against the expectation,
    returns their closed typed view, and denies incomplete, revoked, superseded,
    stale, unqualified or unresolved evidence. No local decoder is supplied here.
    verify must also authenticate the returned clock/profile/error and full
    validity interval. It must never use the expectation to manufacture claims.
    """
    def verify(self, record, expectation):
        raise a.ActivationRejected("AUTHENTICATION_UNAVAILABLE")


class QualificationClient:
    """Read-only qualification, except creation may retain actual creation C."""
    def qualify(self, role, context):
        raise a.ActivationRejected("QUALIFICATION_UNAVAILABLE")


class ProtectedClient:
    """Qualified external namespace/history and three DISTINCT protected seams.

    enter durably fences the entire original namespace/register/generation/K/role
    before possible dispatch. It rejects all previous/concurrent/unknown claims,
    even across clients, processes, credentials and restarts. Its receipt covers
    exact bytes/context and qualified original-history/absence, not a local lock.
    Dispatch atomically consumes that exact admission ONCE with the protected
    transition; replay is rejected, never an idempotent resubmission. UNKNOWN
    persistence stops entry. No automatic retry may occur inside any client.
    """
    def enter(self, role, context, admission):
        raise a.ActivationRejected("DURABLE_ADMISSION_UNAVAILABLE")

    def publish_checkpoint(self, snapshot, approval, authorization, entry):
        raise a.ActivationRejected("PUBLICATION_UNAVAILABLE")

    def activate_absent(self, payload, publication, absence_history, authorization, entry):
        raise a.ActivationRejected("ABSENT_CAS_UNAVAILABLE")

    def readback(self, result):
        raise a.ActivationRejected("READBACK_UNAVAILABLE")


@dataclass(frozen=True, repr=False)
class EffectAdmission:
    snapshot: a.PackageSnapshot
    approval: a.ApprovalView
    authorization: s.EvidenceReference
    absence_history: s.EvidenceReference
    clock: a.TimeBinding
    operation: str
    presence: str
    predecessor_generation: int
    original_history: str


@dataclass(frozen=True, repr=False)
class EnteredOperation:
    admission: s.EvidenceReference
    operation: str
    state: str


@dataclass(frozen=True, repr=False)
class ReadbackView:
    result: a.ActivationResult
    original: a.ActivationResult
    ordering: s.EvidenceReference
    state: str


# Fixed obligations are requests for authenticated external proof, not flags a
# constructor or a callback may use to grant itself operational authority.
_COMMON = ("AUTHENTICATED_PEER_ISSUER_ACTOR_RIGHTS", "QUALIFIED_SELECTION_ADOPTION",
           "CURRENT_CREDENTIAL_CONTINUITY_NOT_REVOKED", "IMMUTABLE_RAW_RETENTION",
           "CURRENT_APPLICABILITY_NOT_SUPERSEDED", "QUALIFIED_CLOCK")
_OBLIGATIONS = {
    "package": ("COMPLETE_FROZEN_PACKAGE_CLAIMS", "TRANSITIVE_UPSTREAM_ONLY"),
    "preparation": ("AUTHORIZED_PREPARATION_STORAGE_ACTOR", "CURRENT_ABSENCE_HISTORY"),
    "creation": ("ACTUAL_AUTHORIZED_CREATION_FACTS", "TRANSITIVE_UPSTREAM_ONLY"),
    "execution": ("COMPLETE_EXECUTION_REQUEST", "FRESH_ABSENCE_EXCLUSION_ORIGINAL_K"),
    "approval": ("INDEPENDENT_Q_CURRENT_VALIDITY", "Q_EXCLUDES_DOWNSTREAM_PAYLOAD"),
    "opening": ("CURRENT_PROTECTED_STATE_HISTORY", "INDEPENDENT_RESULT_ALL_OBLIGATIONS",
                "FRESH_OPEN_AND_Q_VALIDITY", "RESTART_DOES_NOT_ESTABLISH_ELIGIBILITY"),
    "publication-admission": ("EXACT_C0_P_Q_K_HOST_AUTHORIZATION", "FRESH_ABSENCE_EXCLUSION_ORIGINAL_K"),
    "cas-admission": ("EXACT_PAYLOAD_CONFIRMED_PUBLICATION", "FRESH_ABSENCE_EXCLUSION_ORIGINAL_K"),
    "publication-entry": ("DURABLE_ORIGINAL_ADMISSION", "NO_REPLAY_ACROSS_RESTART"),
    "cas-entry": ("DURABLE_ORIGINAL_ADMISSION", "NO_REPLAY_ACROSS_RESTART"),
    "publication-result": ("EXACT_ORIGINAL_AUTHENTICATED_ACCEPTANCE", "PROTECTED_C0_NON_ACTIVATING",
                           "DURABLE_HISTORY_AND_RAW_ACCEPTANCE"),
    "cas-result": ("EXACT_ORIGINAL_AUTHENTICATED_ACCEPTANCE", "LINEARIZABLE_ABSENT_ZERO_TO_ONE",
                   "DURABLE_HISTORY_AND_RAW_ACCEPTANCE"),
    "readback": ("INDEPENDENT_AUTHORITATIVE_SOURCE", "LINEARIZABLE_AFTER_ORIGINAL_EFFECT",
                 "CURRENT_PROTECTED_STATE_EXACT_ORIGINAL", "RAW_OBSERVATION_TIME_ORDERING"),
}


def _same(left, right):
    # Type-sensitive equality; bool must never compare as generation/time 0/1.
    return a._capture(left) == a._capture(right)


def _strict_view(value):
    """Frozen numeric validators plus exact declared scalar carrier types."""
    a._external_numbers(value)

    def scalars(item):
        if type(item) is tuple:
            for child in item:
                scalars(child)
        elif is_dataclass(item):
            for field in fields(item):
                child = getattr(item, field.name)
                if field.type in (str, bytes, int, bool):
                    require(type(child) is field.type, "EXTERNAL_SCALAR_TYPE")
                    if field.type is str:
                        try:
                            a.protocol.identifier(child)
                        except a.protocol.ProtocolRejected:
                            raise a.ActivationRejected("EXTERNAL_IDENTIFIER_DOMAIN") from None
                scalars(child)
    scalars(value)


class ProviderBoundaryFailure(a.ActivationRejected):
    """Unconfirmed provider boundary; never proof of nonentry or retry eligibility.

    Client implementations must retain raw dispatch/response/error/time evidence
    in the qualified external history even when they raise. This exception exposes
    no credential-bearing transport message, raw record, request or traceback cause.
    The unchanged IL6 executor retains its strongest reached/recovery-only floor.
    """


def _call(method, *arguments):
    failed = False
    try:
        return a._invoke(method, *arguments)
    except BaseException:
        failed = True
    # Raise outside the handler: no raw exception context or secret-bearing cause.
    if failed:
        raise ProviderBoundaryFailure("PROVIDER_BOUNDARY_UNCONFIRMED_STOP_NO_RETRY")


def _reference(value):
    require(type(value) is s.EvidenceReference, "EVIDENCE_REFERENCE_REQUIRED")
    s.EvidenceReference(value.identity, value.sha256)
    return value


def _service_reference(value):
    if type(value) is a.Reference:
        a._mapping(value)
        return s.EvidenceReference(value.identity, bytes.fromhex(value.sha256))
    return _reference(value)


def _binding(value, role, kind):
    require(type(value) is ProviderBinding and type(value.role) is str and type(value.kind) is str
            and type(kind) is str and value.role == role and value.kind == kind,
            "PROVIDER_ROLE_OR_TRUST_DOMAIN")
    require(kind in ("SYNTHETIC", "OPERATIONAL"), "TRUST_DOMAIN_REQUIRED")
    for name in ("realization", "principal", "credential_identity", "authority", "issuer", "namespace"):
        a.protocol.identifier(getattr(value, name))
    for name in ("qualification", "selection", "adoption"):
        _reference(getattr(value, name))


class RawEvidence:
    """Concrete fail-closed raw resolution/retention and authentication integration."""
    def __init__(self, client=None, verifier=None, *, binding=None, kind="OPERATIONAL"):
        self.client, self.verifier = client, verifier
        self.binding, self.kind = binding, kind

    def _ready(self):
        _binding(self.binding, "retention", self.kind)
        require(isinstance(self.client, EvidenceClient) and isinstance(self.verifier, EvidenceVerifier),
                "QUALIFIED_EVIDENCE_CLIENTS_REQUIRED")

    def resolve(self, reference):
        self._ready()
        reference = _service_reference(reference)
        record = _call(self.client.resolve, reference)
        require(type(record) is RetainedEvidence and _same(record.reference, reference)
                and type(record.raw) is bytes, "RAW_EVIDENCE_REQUIRED")
        require(sha256(record.raw).digest() == reference.sha256, "RAW_EVIDENCE_DIGEST")
        return record

    def authenticate(self, reference, binding, role, context, stage="CURRENT", obligations=()):
        self._ready()
        _binding(binding, binding.role, self.kind)
        require(type(context) is tuple and type(role) is str, "EXACT_EVIDENCE_CONTEXT")
        bindings_before = a._capture((binding, self.binding))
        # Governance identities must remain independently raw-resolvable too;
        # a cached verifier decision cannot replace missing qualification bytes.
        for participant in (binding, self.binding):
            for name in ("qualification", "selection", "adoption"):
                self.resolve(getattr(participant, name))
        require(a._capture((binding, self.binding)) == bindings_before, "PROVIDER_BINDING_MUTATION")
        record = self.resolve(reference)
        expectation = EvidenceExpectation(binding, self.binding, role, context, stage, _COMMON + obligations)
        # These new views aren't canonical objects; frozen capture guards exact
        # in-memory arguments, without inventing a signature/serialization format.
        view = _call(self.verifier.verify, record, expectation)
        require(type(view) is AuthenticatedView and _same(view.reference, record.reference)
                and _same(view.expectation, expectation), "AUTHENTICATED_BINDING_MISMATCH")
        _reference(view.provenance)
        _strict_view(view.value)
        a._time(view.clock, not_before=view.valid_from_us,
                valid_from=view.valid_from_us, valid_until=view.valid_until_us)
        # Unavailable provenance is never replaced by cached claims or logs.
        before = a._capture(view)
        self.resolve(view.provenance)
        require(a._capture(view) == before, "AUTHENTICATED_VIEW_MUTATION")
        return view

    def retain(self, record, binding, role, context, stage="CURRENT", obligations=()):
        self._ready()
        require(type(record) is RetainedEvidence and type(record.raw) is bytes,
                "COMPLETE_RAW_RETENTION_REQUIRED")
        _reference(record.reference)
        require(sha256(record.raw).digest() == record.reference.sha256, "RAW_EVIDENCE_DIGEST")
        receipt = _call(self.client.retain, record)
        require(_same(receipt, record.reference), "RETENTION_REFERENCE_MISMATCH")
        resolved = self.authenticate(receipt, binding, role, context, stage, obligations)
        require(self.resolve(receipt).raw == record.raw, "RETENTION_SUBSTITUTION")
        return resolved


def _proofs(raw, binding, value, context, prefix="view", stage="CURRENT"):
    """Resolve/authenticate every frozen evidence field, including nested claims.

    Exact field paths are the opaque roles supplied to the qualified verifier;
    its stage obligation applies transitively to each raw record's dependencies.
    No opaque bytes are decoded, reserialized or synthesized by this module.
    """
    before = a._capture(value)
    if type(value) is a.OpaqueEvidence:
        record = raw.authenticate(value.reference, binding, value.role, context, stage,
                                  ("EXACT_ROLE_CONTEXT_ISSUER", "TRANSITIVE_STAGE_RESTRICTIONS"))
        require(raw.resolve(value.reference).raw == value.raw, "OPAQUE_RAW_SUBSTITUTION")
        require(_same(record.value, value.reference), "OPAQUE_REFERENCE_BINDING")
        _proofs(raw, binding, value.qualification, context, prefix + ".qualification", stage)
    elif type(value) in (s.EvidenceReference, a.Reference):
        proof = raw.authenticate(value, binding, prefix, context, stage,
                                 ("EXACT_ROLE_CONTEXT_ISSUER", "TRANSITIVE_STAGE_RESTRICTIONS"))
        require(_same(proof.value, value), "PROOF_REFERENCE_BINDING")
    elif type(value) is tuple:
        for index, item in enumerate(value):
            _proofs(raw, binding, item, context, prefix + "." + str(index), stage)
    elif is_dataclass(value):
        # Request input graphs contain ownership resources and local guards;
        # they are bound by the complete authenticated context, never traversed
        # as substitute authority. All returned proof fields are traversed.
        for field in fields(value):
            if field.name not in ("request", "snapshot"):
                _proofs(raw, binding, getattr(value, field.name), context,
                        prefix + "." + field.name, stage)
    require(a._capture(value) == before, "QUALIFIED_VIEW_MUTATION")


class QualificationProvider(a.QualificationAdapter):
    def __init__(self, client=None, evidence=None, *, binding=None, verifier_binding=None,
                 kind="OPERATIONAL"):
        self.client, self.evidence = client, evidence
        self.binding, self.kind = binding, kind
        self.verifier_binding = verifier_binding

    def _qualified_view(self, role, context, cls, stage="CURRENT"):
        _binding(self.binding, "qualification", self.kind)
        require(isinstance(self.client, QualificationClient) and type(self.evidence) is RawEvidence
                and self.evidence.kind == self.kind, "QUALIFIED_PROVIDER_REQUIRED")
        reference = _call(self.client.qualify, role, context)
        view = self.evidence.authenticate(reference, self.binding, role, context, stage,
                                          _OBLIGATIONS[role])
        require(type(view.value) is cls, "FROZEN_TYPED_VIEW_REQUIRED")
        if role in ("execution", "opening"):
            current = view.value.clock if role == "execution" else view.value.fresh_time
            require(_same(current, view.clock), "AUTHENTICATED_CURRENT_TIME_BINDING")
        if role == "approval":
            require(_same(context[2], view.clock), "APPROVAL_OBSERVATION_TIME_BINDING")
        _proofs(self.evidence, self.binding, view.value, context, stage=stage)
        return view

    def _qualified(self, role, context, cls, stage="CURRENT"):
        return self._qualified_view(role, context, cls, stage).value

    def package(self, snapshot):
        a._validate_snapshot(snapshot)
        q = self._qualified("package", (snapshot,), a.QualifiedPackageBindings, "UPSTREAM_ONLY")
        a.validate_genesis_package(snapshot, q)
        return q

    def preparation(self, request):
        require(type(request) is a.PreparationRequest)
        a._initial_metadata(request)
        view = self._qualified_view("preparation", (request,), a.QualifiedPreparation)
        q = view.value
        require(_same(q.request, request) and _same(q.authorization, request.authorization), "PREPARATION_BINDING")
        require((q.action, q.presence, q.original_history) ==
                ("PREPARE_GENESIS", "AUTHORITATIVE_ABSENT", "NO_PRIOR_OR_INFLIGHT_ATTEMPT"))
        for identity in (q.operator, q.process, q.issuer):
            a.protocol.identifier(identity)
        require(q.process == request.clock.current.process_id and
                request.clock.sample.utc.lower_us == request.metadata.last_valid_utc,
                "PREPARATION_CLOCK_PROCESS_BINDING")
        a._time(view.clock, not_before=request.metadata.last_valid_utc,
                valid_from=q.valid_from_us, valid_until=q.valid_until_us)
        return q

    def creation(self, request, native_identity, state, database_sha256):
        require(type(request) is a.PreparationRequest and type(state) is bytes
                and type(database_sha256) is bytes and len(database_sha256) == 32)
        a._native_identity_numbers(native_identity)
        require(a._initial_metadata(request) == state, "CREATION_INITIAL_STATE_BINDING")
        q = self._qualified("creation", (request, native_identity, state, database_sha256),
                            a.QualifiedCreation, "UPSTREAM_ONLY")
        c = q.claims
        require(type(c) is a.CreationClaims and type(q.evidence) is a.OpaqueEvidence)
        require(q.evidence.role == "C" and c.reference == q.evidence.reference)
        require((c.register_id, c.generation, c.activation_id, c.fixed_utc,
                 c.native_identity, c.state, c.dependency_stage) ==
                (request.register_id, 1, request.activation_id,
                 request.metadata.last_valid_utc, native_identity, "PREPARED_NON_AUTHORITATIVE", "UPSTREAM_ONLY"))
        require(c.authorization == request.authorization and
                a.protocol.state_bytes(a.protocol.StateProjection(c.metadata, (), (), ()), request.context) == state)
        require((c.host.identity, c.storage.identity) ==
                (request.location.host_identity, request.location.storage_identity))
        require(c.purpose == "GENESIS_V1" and c.clock.source == request.clock.sample.source and
                (c.clock.profile.identity, c.clock.profile.sha256) ==
                (request.clock.profile.profile.identity, request.clock.profile.profile.sha256.hex()) and
                (c.clock.sample.identity, c.clock.sample.sha256, c.clock.monotonic_domain) ==
                (request.clock.sample.sample.identity, request.clock.sample.sample.sha256.hex(),
                 request.clock.current.domain_id), "CREATION_CLOCK_BINDING")
        return q

    def execution(self, request):
        require(type(request) is a.ExecutionRequest)
        accepted = a.validate_genesis_package(request.snapshot, self.package(request.snapshot))
        a._execution_bindings(request, accepted)
        # Reuse the frozen executor validator, without recursing into this seam.
        q = self._qualified("execution", (request,), a.QualifiedExecution)
        provider = _ExecutionView(q)
        a._qualified_execution(request, accepted, provider)
        self.approval(accepted, request.approval, q.clock)
        return q

    def approval(self, accepted, approval, clock):
        require(type(accepted) is a.ValidatedPackage)
        a.validate_genesis_package(accepted.snapshot, accepted.qualification)
        a._approval(approval, accepted, clock)
        # P/Q/time only; downstream payload is intentionally unavailable here.
        q = self._qualified("approval", (accepted.snapshot, approval, clock), a.ApprovalView, "Q")
        require(_same(q, approval), "APPROVAL_SUBSTITUTION")
        return q

    def opening(self, request):
        require(type(request) is a.OpenRequest)
        accepted = a.validate_genesis_package(request.snapshot, self.package(request.snapshot))
        q = self._qualified("opening", (request,), a.QualifiedOpen)
        require(_same(q.request, request), "OPEN_REQUEST_BINDING")
        e = accepted.evidence
        require((q.opener, q.issuer, q.process, q.state) ==
                (e.actors.opener, e.actors.issuer, e.actors.process, "VERIFIED_CURRENT_NO_UNRESOLVED_OUTCOME"))
        require(q.fresh_time.profile == accepted.qualification.profile, "OPEN_CLOCK_PROFILE")
        self.approval(accepted, request.approval, q.fresh_time)
        payload = a._bound_payload(accepted, request.approval)
        a._activation_result(q.activation, accepted, request.approval.evidence.reference,
                             sha256(a.canonical_bytes(payload)).digest())
        require(type(request.independent_result_verification) is a.OpaqueEvidence and
                request.independent_result_verification.role == "INDEPENDENT_RESULT_VERIFICATION")
        _binding(self.verifier_binding, "result-verifier", self.kind)
        require(self.verifier_binding.namespace == self.binding.namespace and
                self.verifier_binding.principal not in
                (e.actors.genesis_operator, e.actors.preparation_operator, e.actors.issuer,
                 self.binding.principal) and
                self.verifier_binding.credential_identity != self.binding.credential_identity,
                "INDEPENDENT_RESULT_VERIFIER_REQUIRED")
        _proofs(self.evidence, self.verifier_binding, request.independent_result_verification,
                (request,), stage="INDEPENDENT_RESULT_VERIFICATION")
        return q


class _ExecutionView(a.QualificationAdapter):
    """Internal immutable result bridge to the unchanged frozen validator."""
    def __init__(self, value):
        self.value = value

    def execution(self, request):
        return self.value


class ProtectedAuthorityProvider(a.ProtectedGenesis):
    def __init__(self, client=None, qualification=None, evidence=None, *, binding=None, kind="OPERATIONAL"):
        self.client, self.qualification, self.evidence = client, qualification, evidence
        self.binding, self.kind = binding, kind

    def _ready(self):
        _binding(self.binding, "protected", self.kind)
        require(isinstance(self.client, ProtectedClient) and type(self.qualification) is QualificationProvider
                and type(self.evidence) is RawEvidence and self.evidence is self.qualification.evidence
                and self.qualification.kind == self.kind == self.evidence.kind, "PROTECTED_CLIENTS_REQUIRED")

    def _record(self, reference, role, context, cls):
        view = self.evidence.authenticate(reference, self.binding, role, context, "CURRENT", _OBLIGATIONS[role])
        require(type(view.value) is cls, "PROTECTED_TYPED_EVIDENCE_REQUIRED")
        if cls is EffectAdmission:
            require(_same(view.clock, view.value.clock), "AUTHENTICATED_ADMISSION_TIME")
        _proofs(self.evidence, self.binding, view.value, context)
        return view.value

    def _admit(self, role, context):
        self._ready()
        admission_ref = _call(self.qualification.client.qualify, role + "-admission", context)
        admission = self._record(admission_ref, role + "-admission", context, EffectAdmission)
        a._external_numbers(admission)
        require(type(admission.predecessor_generation) is int and admission.predecessor_generation == 0)
        require((admission.presence, admission.original_history) ==
                ("AUTHORITATIVE_ABSENT", "ORIGINAL_UNATTEMPTED_K"), "ABSENCE_OR_ORIGINAL_HISTORY")
        a.protocol.identifier(admission.operation)
        _reference(admission.authorization)
        _reference(admission.absence_history)
        accepted = a.validate_genesis_package(admission.snapshot, self.qualification.package(admission.snapshot))
        self.qualification.approval(accepted, admission.approval, admission.clock)
        a._time(admission.clock, not_before=accepted.evidence.creation_utc_us,
                valid_from=accepted.package.authorization.valid_from_us,
                valid_until=accepted.package.authorization.valid_until_us)
        return admission_ref, admission, accepted

    def _enter(self, role, context, admission_ref, admission):
        reference = _call(self.client.enter, role, context, admission_ref)
        entered = self._record(reference, role + "-entry", context, EnteredOperation)
        require(_same(entered.admission, admission_ref) and entered.operation == admission.operation
                and entered.state == "DURABLY_ENTERED_ORIGINAL", "DURABLE_ORIGINAL_ENTRY_REQUIRED")
        return reference

    def publish_checkpoint(self, snapshot, approval, authorization):
        context = (snapshot, approval, authorization)
        admission_ref, admission, accepted = self._admit("publication", context)
        require(_same((snapshot, approval, authorization),
                      (admission.snapshot, admission.approval, admission.authorization)), "PUBLICATION_ADMISSION_BINDING")
        entry = self._enter("publication", context, admission_ref, admission)
        # From here ANY exception is uncertainty; no catch/retry or success synthesis.
        reference = _call(self.client.publish_checkpoint, snapshot, approval, authorization, entry)
        result = self._record(reference, "publication-result", context, a.CheckpointResult)
        require(result.status == "CONFIRMED" and result.operation == admission.operation)
        require((result.checkpoint, result.package, result.approval, result.host_identity) ==
                (accepted.package.checkpoint, a.content_reference(accepted.package),
                 approval.evidence.reference, accepted.evidence.host.identity), "PUBLICATION_RESULT_BINDING")
        require(_same(result.evidence, reference), "PUBLICATION_RAW_RECEIPT_REQUIRED")
        return result

    def activate_absent(self, payload, publication, absence_history, authorization):
        parsed = a.decode_canonical(payload, a.ActivationPayload)
        context = (payload, publication, absence_history, authorization)
        admission_ref, admission, accepted = self._admit("cas", context)
        require(_same((absence_history, authorization), (admission.absence_history, admission.authorization)))
        require(a.canonical_bytes(a._bound_payload(accepted, admission.approval)) == payload, "CAS_PAYLOAD_BINDING")
        require(admission.operation == parsed.activation_command_id, "CAS_ORIGINAL_K")
        publication_context = (admission.snapshot, admission.approval, authorization)
        proven = self._record(publication.evidence, "publication-result", publication_context, a.CheckpointResult)
        require(_same(proven, publication) and publication.status == "CONFIRMED", "CONFIRMED_PUBLICATION_REQUIRED")
        require((publication.checkpoint, publication.package, publication.approval, publication.host_identity) ==
                (parsed.checkpoint, parsed.package, parsed.approval, parsed.host_identity))
        entry = self._enter("cas", context, admission_ref, admission)
        reference = _call(self.client.activate_absent, payload, publication, absence_history, authorization, entry)
        result = self._record(reference, "cas-result", context, a.ActivationResult)
        a._activation_result(result, accepted, parsed.approval, sha256(payload).digest())
        require(_same(result.evidence, reference), "CAS_RAW_RECEIPT_REQUIRED")
        return result

    def readback(self, result):
        self._ready()
        require(type(result) is a.ActivationResult and result.status == "CONFIRMED")
        a._external_numbers(result)
        # Authenticated source must establish the exact original receipt, not echo
        # a request. Read-only resolution supplies no fresh effect admission.
        context = (result,)
        reference = _call(self.client.readback, result)
        observed = self._record(reference, "readback", context, ReadbackView)
        require(_same(observed.original, result) and
                observed.state == "LINEARIZABLE_CURRENT_AFTER_ORIGINAL", "READBACK_ORDER_OR_ORIGINAL")
        _reference(observed.ordering)
        require(type(observed.result) is a.ActivationResult and
                _same(replace(observed.result, evidence=result.evidence), result), "READBACK_MISMATCH")
        require(_same(observed.result.evidence, reference) and reference != result.evidence,
                "DISTINCT_RAW_READBACK_REQUIRED")
        return observed.result
