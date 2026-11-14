"""Fixed CORE.1A broker: permanent admission/claim, one live effect dispatch.

Callable only: no listener, scheduler, credential discovery or recovery loop.
The live continuation is deliberately neither serializable nor reconstructible
from SQL rows or receipts. A restart can observe, never resume an original.
"""
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock

from . import fixture_lease_authority_evidence as e
from . import fixture_lease_authority_providers as p

OPERATIONS = ("ORIGINAL_ATTEMPT_ADMISSION", "DISPATCH_CLAIM", "CHECKPOINT_PUBLICATION",
              "ACTIVATION_CAS", "AUTHORITATIVE_READBACK", "READ_ONLY_RESOLUTION",
              "EVIDENCE_CUSTODY_BINDING")
CATEGORIES = ("OPERATION_STATE", "DECISION", "RECEIPT_REFERENCE", "CUSTODY_LOCATOR",
              "AUTHORITATIVE_READBACK_FACTS")
GROUPS = {
    "Envelope": (("schema_version", 1), ("operation", OPERATIONS), ("request_id", "ID")),
    "Authority": (("namespace", "ID"), ("incarnation_id", "ID"), ("configuration_ref", "R"),
                  ("adoption_ref", "R"), ("expected_fence_epoch", "U")),
    "Caller": (("principal_id", "ID"), ("credential_identity", "ID"),
               ("logical_role", ("EXECUTOR", "CUSTODY", "OBSERVER", "RESULT_VERIFIER")),
               ("authorization_ref", "R")),
    "Freshness": (("current_time", "TIME"), ("time_evidence_ref", "R"), ("qualification_ref", "R")),
    "Lifecycle": (("register_id", "ID"), ("generation", 1), ("activation_id", "ID"),
                  ("K", "ID"), ("J", "ID"), ("host_ref", "R"), ("scope_ref", "R")),
    "Original": (("operation_id", "ID"), ("operation_role", ("CHECKPOINT_PUBLICATION", "ACTIVATION_CAS")),
                 ("input_binding_ref", "R")),
    "Snapshot": tuple((n, "BYTES") for n in ("E_bytes", "S0_bytes", "C0_bytes", "P_bytes"))
                + tuple((n, "R") for n in ("E_ref", "S0_ref", "C0_ref", "P_ref")),
    "Approval": (("Q_bytes", "BYTES"), ("Q_ref", "R")),
    "Absence": (("absence_history_ref", "R"), ("original_history_ref", "R"),
                ("expected_state", "AUTHORITATIVE_ABSENT"), ("expected_generation", 0),
                ("expected_state_version", "U")),
    "Admission": (("admission_id", "ID"), ("admission_evidence_ref", "R")),
    "Claim": (("dispatch_claim_id", "ID"), ("claim_fence_value", "U"), ("claim_commit_evidence_ref", "R")),
    "Payload": (("payload_bytes", "BYTES"), ("payload_sha256", "DIGEST")),
    "Publication": (("publication_operation_id", "ID"), ("publication_decision_ref", "R"),
                    ("publication_receipt_ref", "R")),
    "ObservationScope": (("observation_authorization_ref", "R"), ("observation_scope_ref", "R")),
    "CustodySubject": (("evidence_identity", "ID"), ("raw_sha256", "DIGEST"), ("raw_size", "U"),
                      ("evidence_role", "ID"), ("issuer_id", "ID"), ("subject_context_ref", "R")),
    "CustodyPlan": (("custody_attempt_id", "ID"), ("custody_role", "ID"), ("bucket_resource_ref", "R"),
                   ("object_key", "TEXT"), ("retention_mode", "COMPLIANCE"),
                   ("required_retention_until", "UTC"), ("retention_requirement_ref", "R")),
    "CustodyVersion": (("version_id", "TEXT"), ("observed_retention_until", "UTC"),
                      ("retention_evidence_ref", "R"), ("upload_response_ref", "R"),
                      ("exact_version_readback_ref", "R"), ("custody_authentication_ref", "R")),
}
COMMON = ("Envelope", "Authority", "Caller")
EFFECT_INPUTS = ("Freshness", "Lifecycle", "Original", "Snapshot", "Approval", "Absence")


def request_spec(request):
    e.need(type(request) is dict and request.get("operation") in OPERATIONS, "FIXED_OPERATION_REQUIRED")
    op = request["operation"]
    extra = ()
    if op == "ORIGINAL_ATTEMPT_ADMISSION":
        groups = COMMON + EFFECT_INPUTS
        extra = (("admission_id", "ID"),)
        if request.get("operation_role") == "ACTIVATION_CAS":
            groups += ("Payload", "Publication")
    elif op == "DISPATCH_CLAIM":
        groups = COMMON + ("Freshness", "Lifecycle", "Original", "Admission")
        extra = (("dispatch_claim_id", "ID"), ("broker_principal_id", "ID"), ("expected_fence_value", "U"))
    elif op in ("CHECKPOINT_PUBLICATION", "ACTIVATION_CAS"):
        groups = COMMON + EFFECT_INPUTS + ("Admission", "Claim")
        if op == "ACTIVATION_CAS":
            groups += ("Payload", "Publication")
    elif op == "AUTHORITATIVE_READBACK":
        groups = COMMON + ("Freshness", "Lifecycle", "Original", "Payload", "Publication", "ObservationScope")
        extra = (("activation_decision_ref", "R"), ("activation_receipt_ref", "R"), ("minimum_state_version", "U"))
    elif op == "READ_ONLY_RESOLUTION":
        groups = COMMON + ("ObservationScope",)
        kind = request.get("target_kind")
        e.need(kind in ("OPERATION", "EVIDENCE"), "RESOLUTION_TARGET_KIND")
        extra = (("target_kind", ("OPERATION", "EVIDENCE")), ("permitted_outputs", "OUTPUTS"),
                 ("operation_id" if kind == "OPERATION" else "evidence_identity", "ID"))
    else:
        groups = COMMON + ("Freshness", "CustodySubject", "CustodyPlan")
        phase = request.get("phase")
        e.need(phase in ("RESERVE", "BIND"), "CUSTODY_PHASE")
        extra = (("phase", ("RESERVE", "BIND")),)
        if phase == "RESERVE":
            extra += (("raw_bytes", "BYTES"),)
        else:
            groups += ("CustodyVersion",)
    return tuple(field for group in groups for field in GROUPS[group]) + extra


def validate_request(request):
    specification = request_spec(request)
    e.closed(request, (name for name, _ in specification))
    for name, rule in specification:
        value = request[name]
        if rule == "BYTES":
            e.need(type(value) is bytes and len(value) <= e.MAX_SINGLE_UPLOAD_BYTES, "SIZE_UNSUPPORTED")
        elif rule == "DIGEST":
            e.need(type(value) is bytes and len(value) == 32, "RAW_SHA256_DOMAIN")
        elif rule == "TIME":
            e.need(type(value) is p.a.TimeBinding, "QUALIFIED_TIME_REQUIRED")
            p.s.evaluate_time(value.sample, value.profile, value.current, value.error)
        elif rule == "OUTPUTS":
            e.need(type(value) is tuple and 1 <= len(value) <= 5
                   and len(set(value)) == len(value) and all(v in CATEGORIES for v in value), "CLOSED_OUTPUT_SCOPE")
        else:
            e.schema({name: value}, ((name, rule),))
    for name in ("E", "S0", "C0", "P", "Q"):
        if name + "_bytes" in request:
            e.need(sha256(request[name + "_bytes"]).hexdigest() == request[name + "_ref"]["sha256"],
                   "COMPLETE_INPUT_DIGEST")
    if "payload_bytes" in request:
        e.need(sha256(request["payload_bytes"]).digest() == request["payload_sha256"], "PAYLOAD_DIGEST")
        p.a.decode_canonical(request["payload_bytes"], p.a.ActivationPayload)
    if "raw_bytes" in request:
        e.need(len(request["raw_bytes"]) == request["raw_size"]
               and sha256(request["raw_bytes"]).digest() == request["raw_sha256"], "CUSTODY_RAW_BINDING")
    if "version_id" in request:
        e.need(request["version_id"] != "null", "NULL_VERSION")
        e.need(request["observed_retention_until"] >= request["required_retention_until"], "INSUFFICIENT_RETENTION")
    op = request["operation"]
    roles = {"AUTHORITATIVE_READBACK": ("OBSERVER", "RESULT_VERIFIER"),
             "READ_ONLY_RESOLUTION": ("OBSERVER", "RESULT_VERIFIER", "CUSTODY"),
             "EVIDENCE_CUSTODY_BINDING": ("CUSTODY",)}
    e.need(request["logical_role"] in roles.get(op, ("EXECUTOR",)), "CALLER_OPERATION_ROLE")
    if op in ("CHECKPOINT_PUBLICATION", "ACTIVATION_CAS", "AUTHORITATIVE_READBACK"):
        expected = "CHECKPOINT_PUBLICATION" if op == "CHECKPOINT_PUBLICATION" else "ACTIVATION_CAS"
        e.need(request["operation_role"] == expected, "CROSS_OPERATION_SUBSTITUTION")
    return request


def database_projection(request):
    """Private transport projection, not an evidence/canonical identity format.

    Qualified TimeBinding is verified in the broker; SQL receives its existing
    retained time reference, never a manufactured wall-clock qualification.
    """
    validate_request(request)
    result = {}
    for name, value in request.items():
        if name == "current_time":
            continue
        result[name] = value.hex() if type(value) is bytes else list(value) if type(value) is tuple else value
    return result


@dataclass(frozen=True, repr=False)
class Caller:
    principal: str
    credential_identity: str
    role: str
    binding: p.ProviderBinding


class _Live:
    def __init__(self, owner, request, response):
        self.owner = owner
        self.original = e.capture(request)
        self.request = dict(request)
        self.response = response
        self.admission_receipt = None
        self.claim = e.Once()
        self.effect = e.Once()
        self.bind = e.Once()
        self.invalid = False

    def __reduce__(self):
        raise TypeError("LIVE_CONTINUATION_NOT_SERIALIZABLE")


READBACK_BINDINGS = ("namespace", "incarnation_id", "register_id", "generation", "activation_id", "K", "J",
                     "host_ref", "scope_ref", "operation_id", "operation_role", "input_binding_ref",
                     "payload_sha256", "P_ref", "Q_ref", "C0_ref", "publication_operation_id",
                     "publication_decision_ref", "publication_receipt_ref", "activation_decision_ref",
                     "activation_receipt_ref")
READBACK_FIELDS = ("schema_version", "operation", "request_id") + READBACK_BINDINGS + (
    "disposition", "protected_state", "state_version", "fence_value", "observation_time", "ordering_ref",
    "readback_evidence_ref")


@e.closed_boundary("UNKNOWN_READBACK_EVIDENCE_UNAVAILABLE")
def readback_response(request, native, facts, receipt):
    """Translate actual qualified native facts; never pass through SQL rows."""
    e.need(type(facts) is tuple and len(facts) == 5 and receipt is not None, "READBACK_ACK_REQUIRED")
    request_capture, result_capture, before, after, ack = facts
    e.need(e.capture(request) == request_capture and e.capture(native) == result_capture,
           "READBACK_ACK_MISMATCH")
    p._reference(ack)
    p._reference(receipt)
    e.need(native["disposition"] == "OBSERVED", "READBACK_NOT_ESTABLISHED")
    state, original = native["protected_state"], native["original_decision"]
    binding = original["original_binding"]
    e.need(state["state"] == "ACTIVE" and type(state["generation"]) is int and state["generation"] == 1
           and original["decision"] == "ACTIVATED"
           and e.same(state["lifecycle_binding"], original["lifecycle_binding"]), "READBACK_PROTECTED_STATE")
    actual = {}
    for name in READBACK_BINDINGS:
        if name in ("publication_decision_ref", "activation_decision_ref", "publication_receipt_ref", "activation_receipt_ref"):
            value = native[name]
        elif name == "payload_sha256":
            e.need(original[name] == "\\x" + request[name].hex(), "READBACK_PAYLOAD_IDENTITY")
            value = bytes.fromhex(original[name][2:])
        elif name in ("namespace", "incarnation_id", "operation_id", "operation_role", "input_binding_ref", "publication_operation_id"):
            value = original[name]
        else:
            value = binding[name]
        e.need(e.same(value, request.get(name, value)), "READBACK_ORIGINAL_CONTEXT")
        if name in dict(GROUPS["Lifecycle"]):
            e.need(e.same(value, original["lifecycle_binding"][name]), "READBACK_LIFECYCLE")
        actual[name] = value
    e.need(state["state_version"] >= request["minimum_state_version"], "READBACK_STATE_VERSION")
    p.s.evaluate_time(before.sample, before.profile, before.current, before.error)
    p.s.evaluate_time(after.sample, after.profile, after.current, after.error)
    e.need((before.current.process_id, before.current.domain_id) == (after.current.process_id, after.current.domain_id)
           and before.current.ticks_ns <= after.current.ticks_ns, "READBACK_OBSERVATION_ORDER")
    response = dict(actual, schema_version=request["schema_version"], operation=request["operation"],
                    request_id=request["request_id"], disposition="OBSERVED", protected_state=state["state"],
                    state_version=state["state_version"], fence_value=state["fence_value"], observation_time=after,
                    ordering_ref=ack, readback_evidence_ref=receipt)
    validate_readback_response(response)
    return response


def validate_readback_response(response):
    e.closed(response, READBACK_FIELDS)
    e.need(response["schema_version"] == 1 and response["operation"] == "AUTHORITATIVE_READBACK"
           and response["disposition"] == "OBSERVED" and response["protected_state"] == "ACTIVE"
           and type(response["generation"]) is int and response["generation"] == 1
           and response["operation_role"] == "ACTIVATION_CAS", "READBACK_SUCCESS_SHAPE")
    for name in READBACK_BINDINGS:
        if name.endswith("_ref"):
            e.ref(response[name])
        elif name == "payload_sha256":
            e.need(type(response[name]) is bytes and len(response[name]) == 32, "READBACK_PAYLOAD_DIGEST")
        elif name == "generation":
            e.uint(response[name])
        else:
            e.identifier(response[name])
    for name in ("state_version", "fence_value"):
        e.uint(response[name])
    for name in ("ordering_ref", "readback_evidence_ref"):
        p._reference(response[name])
    clock = response["observation_time"]
    e.need(type(clock) is p.a.TimeBinding, "READBACK_QUALIFIED_OBSERVATION_TIME")
    p.s.evaluate_time(clock.sample, clock.profile, clock.current, clock.error)


class BoundedBroker:
    """One connection/transaction per invocation, no generic SQL or retries.

    sessions supplies only pinned, explicit-credential writer sessions. policy
    verifies actual caller/current external adoption and request qualification
    through the existing independently qualified evidence-verifier seam.
    receipts retains actual raw transaction/acknowledgement evidence and issues
    only role-permitted receipts. It cannot provide independent Q/governance.
    """
    def __init__(self, *, sessions, policy, receipts, principal):
        e.identifier(principal)
        self.sessions, self.policy, self.receipts = sessions, policy, receipts
        self.principal = principal
        self._owner = object()
        self._lock = Lock()
        self._live = {}
        self._entered = set()
        self._acknowledgements = {}
        self._ack_facts = {}

    def _key(self, request):
        return (request["namespace"], request["incarnation_id"],
                request.get("operation_id", request.get("evidence_identity")))

    def _check(self, request, caller):
        validate_request(request)
        e.need(type(caller) is Caller and (caller.principal, caller.credential_identity, caller.role) ==
               (request["principal_id"], request["credential_identity"], request["logical_role"]),
               "AUTHENTICATED_CALLER_MISMATCH")
        p._binding(caller.binding, caller.binding.role, "OPERATIONAL")
        e.need(caller.binding.principal == caller.principal
               and caller.binding.credential_identity == caller.credential_identity, "CARRIER_BINDING")
        self.policy.verify_request(request, caller, self.principal)

    @e.closed_boundary("UNKNOWN_BROKER_OUTCOME_STOP_NO_RETRY", preserve_known=True)
    def _transaction(self, request, caller):
        session = None
        committed = False
        failed = False
        result = None
        try:
            self._check(request, caller)
            session = self.sessions.open(request, caller)
            session.begin(readonly=request["operation"] == "READ_ONLY_RESOLUTION")
            before = self.policy.qualified_observation(request)
            result = session.fixed(request["operation"], database_projection(request))
            # Only the actual COMMIT acknowledgement establishes this boundary.
            # Native return/exception text cannot set the trusted marker.
            session.commit()
            committed = True
            after = self.policy.qualified_observation(request)
            self.policy.verify_commit_bracket(before, after, request, result)
            acknowledgement = self.receipts.record_acknowledgement(request, result, before, after)
            p._reference(acknowledgement)
            self._acknowledgements[request["request_id"]] = acknowledgement
            self._ack_facts[request["request_id"]] = (e.capture(request), e.capture(result), before, after,
                                                     acknowledgement)
            self.policy.verify_response(request, result)
        except BaseException:
            failed = True
        finally:
            if session is not None:
                try:
                    session.close()
                except BaseException:
                    failed = True
        # No carrier object or handler context is retained across this point.
        if failed:
            if committed and request["operation"] not in ("READ_ONLY_RESOLUTION", "AUTHORITATIVE_READBACK"):
                raise e._KnownDecisionGap()
            raise e.EvidenceFailure("UNKNOWN_BROKER_OUTCOME_STOP_NO_RETRY")
        return result

    @e.closed_boundary("UNKNOWN_BROKER_OUTCOME_STOP_NO_RETRY", preserve_known=True)
    def admission(self, request, caller):
        e.need(request.get("operation") == "ORIGINAL_ATTEMPT_ADMISSION", "ADMISSION_ONLY")
        key = self._key(request)
        with self._lock:
            e.need(key not in self._entered, "DUPLICATE_ORIGINAL_NO_RETRY")
            # Permanently consumed locally before any possible remote entry.
            self._entered.add(key)
        result = self._transaction(request, caller)
        with e._known_decision_scope():
            e.need(result["disposition"] == "ADMITTED", "ADMISSION_REJECTED")
            receipt = self.receipts.confirm(request, result)
            continuation = _Live(self._owner, request, result)
            continuation.admission_receipt = receipt
            with self._lock:
                self._live[key] = continuation
            return self._response(request, result, admission_evidence_ref=receipt)

    @e.closed_boundary("UNKNOWN_BROKER_OUTCOME_STOP_NO_RETRY", preserve_known=True)
    def claim(self, request, caller):
        e.need(request.get("operation") == "DISPATCH_CLAIM", "CLAIM_ONLY")
        live = self._continuation(request)
        live.claim.consume()
        live.invalid = True
        e.need(request["broker_principal_id"] == self.principal, "BROKER_IDENTITY")
        self.policy.match_original(live.request, live.response, request)
        e.need(request["admission_evidence_ref"] == e.wire_ref(live.admission_receipt), "EXACT_LIVE_ADMISSION_RECEIPT")
        result = self._transaction(request, caller)
        with e._known_decision_scope():
            e.need(result["disposition"] == "CLAIMED", "CLAIM_REJECTED")
            self.receipts.confirm(request, result)
            result = dict(result, claim_commit_evidence_ref=self._acknowledgements[request["request_id"]])
            live.response = result
            live.invalid = False
            return self._response(request, result)

    @e.closed_boundary("UNKNOWN_BROKER_OUTCOME_STOP_NO_RETRY", preserve_known=True)
    def effect(self, request, caller):
        e.need(request.get("operation") in ("CHECKPOINT_PUBLICATION", "ACTIVATION_CAS"), "EFFECT_ONLY")
        live = self._continuation(request)
        e.need(live.response["disposition"] == "CLAIMED", "ACKNOWLEDGED_CLAIM_REQUIRED")
        self.policy.match_original(live.request, live.response, request)
        e.need(request["claim_commit_evidence_ref"] == e.wire_ref(live.response["claim_commit_evidence_ref"]),
               "EXACT_ACKNOWLEDGED_CLAIM_COMMIT")
        # Irreversible before opening the effect transaction; rollback, lost
        # connection, savepoint or a later rejection cannot reset this latch.
        live.effect.consume()
        live.invalid = True
        result = self._transaction(request, caller)
        with e._known_decision_scope():
            e.need(result["disposition"] in ("CHECKPOINT_PUBLISHED", "ACTIVATED"), "EFFECT_REJECTED")
            receipt = self.receipts.confirm(request, result)
            return self._response(request, result, **{
                "publication_receipt_ref" if request["operation"] == "CHECKPOINT_PUBLICATION" else "activation_receipt_ref": receipt})

    @e.closed_boundary("UNKNOWN_BROKER_OUTCOME_STOP_NO_RETRY")
    def observe(self, request, caller):
        e.need(request.get("operation") in ("AUTHORITATIVE_READBACK", "READ_ONLY_RESOLUTION"), "OBSERVATION_ONLY")
        result = self._transaction(request, caller)
        if request["operation"] == "READ_ONLY_RESOLUTION":
            # No new receipt, history sequence, eligibility or latch.
            return self._response(request, result)
        return self._response(request, result, readback_evidence_ref=self.receipts.confirm(request, result))

    @e.closed_boundary("UNKNOWN_BROKER_OUTCOME_STOP_NO_RETRY", preserve_known=True)
    def custody(self, request, caller):
        e.need(request.get("operation") == "EVIDENCE_CUSTODY_BINDING", "CUSTODY_ONLY")
        key = self._key(request)
        if request["phase"] == "RESERVE":
            with self._lock:
                e.need(key not in self._entered, "CUSTODY_ORIGINAL_ALREADY_ENTERED")
                self._entered.add(key)
            result = self._transaction(request, caller)
            with e._known_decision_scope():
                e.need(result["disposition"] == "CUSTODY_RESERVED", "CUSTODY_RESERVATION_REJECTED")
                receipt = self.receipts.confirm(request, result)
                with self._lock:
                    self._live[key] = _Live(self._owner, request, result)
                return self._response(request, result)
        live = self._continuation(request)
        self.policy.match_custody(live.request, request)
        live.bind.consume()
        live.invalid = True
        result = self._transaction(request, caller)
        with e._known_decision_scope():
            e.need(result["disposition"] == "CUSTODY_BOUND", "CUSTODY_BIND_REJECTED")
            self.receipts.confirm(request, result)
            return self._response(request, result)

    def _response(self, request, result, **evidence):
        if request["operation"] == "AUTHORITATIVE_READBACK":
            facts = self._ack_facts.get(request["request_id"])
            return readback_response(request, result, facts, evidence.get("readback_evidence_ref"))
        response = {name: request[name] for name in ("schema_version", "operation", "request_id", "namespace", "incarnation_id")}
        for name in ("input_binding_ref", "evidence_identity", "raw_sha256", "target_kind"):
            if name in request:
                response[name] = request[name]
        if request.get("operation") == "READ_ONLY_RESOLUTION" and "operation_id" in request:
            response["operation_id"] = request["operation_id"]
        response.update(result)
        response.update(evidence)
        if result["disposition"] in ("CHECKPOINT_PUBLISHED", "ACTIVATED"):
            # Flatten the contract's logical groups. Native SQL projection
            # fields are retained as observations, not exposed as a new schema.
            response.pop("lifecycle_binding", None)
            response.pop("decision_ref", None)
            response.pop("fence_value", None)
            for group in ("Lifecycle", "Original", "Admission", "Claim"):
                response.update({name: request[name] for name, _ in GROUPS[group]})
            for name in ("C0_ref", "P_ref", "Q_ref", "host_ref"):
                response[name] = request[name]
            response["publication_decision_ref" if result["disposition"] == "CHECKPOINT_PUBLISHED" else "activation_decision_ref"] = result["decision_ref"]
            if result["disposition"] == "ACTIVATED":
                response["payload_sha256"] = request["payload_sha256"]
        return response

    def _continuation(self, request):
        with self._lock:
            live = self._live.get(self._key(request))
        e.need(live is not None and live.owner is self._owner and not live.invalid, "STALE_CONTINUATION")
        return live
