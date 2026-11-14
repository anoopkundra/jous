"""CORE.1A exact-byte receipt codec and finite evidence custody.

No constructor performs I/O. Transports, current authority evidence and the
independently qualified native interpreter are explicit composition inputs.
Nothing here selects/adopts a resource or makes KMS authentication trusted time.
Authorities: realization sections 6, 14; codec sections 4--11; ASBQ/APM.
"""
from base64 import b64decode, urlsafe_b64encode
from dataclasses import dataclass, fields, is_dataclass
from contextlib import contextmanager
from hashlib import sha256
import json
import re
from threading import Lock

from . import fixture_lease_authority_providers as p

PROFILE = "JOUS_NON_RFC3161_RECEIPT_BINDING_V1"
ALGORITHM = "RSASSA_PSS_SHA_256"
MAX_SINGLE_UPLOAD_BYTES = 8388608
ROLES = (
    "QUAL_PACKAGE", "QUAL_PREPARATION", "QUAL_CREATION", "QUAL_EXECUTION",
    "QUAL_APPROVAL", "QUAL_OPENING", "ADMISSION_PUBLICATION", "ADMISSION_CAS",
    "ENTRY_PUBLICATION", "ENTRY_CAS", "CLAIM_PUBLICATION", "CLAIM_CAS",
    "RESULT_PUBLICATION", "RESULT_CAS", "READBACK", "CUSTODY_RESERVE",
    "CUSTODY_VERSION", "CUSTODY_BIND", "INDEPENDENT_RESULT",
    "VERIFIER_ATTESTATION", "PROOF_BINDING", "GOVERNANCE", "KEY_BINDING", "KEY_STATUS",
)
REASONS = ("DUPLICATE", "INPUT_CONFLICT", "LIFECYCLE_CONFLICT", "WRONG_PREDECESSOR",
           "ALREADY_ACTIVE", "WRONG_INCARNATION", "UNQUALIFIED", "INVALID_INPUT",
           "STALE_CONTINUATION", "CUSTODY_CONFLICT", "SIZE_UNSUPPORTED")
KINDS = ("PACKAGE", "PREPARATION", "CREATION", "EXECUTION", "APPROVAL", "OPENING",
         "PUBLICATION", "CAS", "READBACK", "CUSTODY", "GOVERNANCE", "KEY")
PURPOSES = ("CREATION", "STORAGE", "HOST", "SCOPE", "ACTOR", "AUTHORIZATION",
            "AUTHORITY", "REPRESENTATION", "SOFTWARE", "GENERATION", "HISTORY",
            "PROTECTED_STATE", "REQUIREMENTS", "CLOCK_PROFILE", "CLOCK_SAMPLE_VALIDATION",
            "CLOCK_PROPAGATION", "INDEPENDENCE", "VALIDITY_STATUS", "PROVENANCE")


class EvidenceFailure(p.ProviderBoundaryFailure):
    """Never establishes effect nonentry or permission to retry."""


def capture(value):
    """Type-sensitive in-memory guard; never serialized, hashed or authority."""
    if type(value) is dict:
        return (dict, tuple((capture(k), capture(v)) for k, v in value.items()))
    if type(value) in (list, tuple):
        return (type(value), tuple(capture(v) for v in value))
    if is_dataclass(value):
        return (type(value), tuple((f.name, capture(getattr(value, f.name))) for f in fields(value)))
    return p.a._capture(value)


def same(left, right):
    """Exact typed native field comparison, independent of mapping iteration.

    This is not a byte codec or canonicalization. Original bytes and complete
    digests are verified separately. JSONB's projection key order grants no
    authority and must not change comparison of the existing Ref fields.
    """
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        left_keys = {capture(key): key for key in left}
        right_keys = {capture(key): key for key in right}
        return (left_keys.keys() == right_keys.keys()
                and all(same(left[left_keys[key]], right[right_keys[key]]) for key in left_keys))
    if type(left) in (tuple, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    if is_dataclass(left):
        return all(same(getattr(left, f.name), getattr(right, f.name)) for f in fields(left))
    return capture(left) == capture(right)


_KNOWN_DECISION_GAP = "KNOWN_DB_DECISION_EVIDENCE_GAP_NO_REPLAY"


class _KnownDecisionGap(EvidenceFailure):
    """Private finite disposition, not a carrier error or a new frozen outcome.

    Only known-commit control flow below creates this marker. Generic
    EvidenceFailure text, including identical text from a carrier, is untrusted.
    There are no transport objects, diagnostic fields or traceback copies here.
    """
    def __init__(self):
        super().__init__(_KNOWN_DECISION_GAP)


@contextmanager
def _known_decision_scope():
    """Use only AFTER a known DB decision; evidence failure cannot undo it."""
    failed = False
    try:
        yield
    except BaseException:
        failed = True
    if failed:
        raise _KnownDecisionGap()


def closed_boundary(code, *, preserve_known=False):
    """Fresh chain-free failures, with opt-in preservation of one closed marker.

    The marker is generated from internal commit state, never by inspecting
    carrier diagnostics. Its object/chain is discarded just like all other
    exceptions. Only a boolean survives the handler, and a NEW exception is
    raised afterward. External-facing transport wrappers do not opt in.
    """
    def decorate(function):
        def invoke(*args, **kwargs):
            known = False
            try:
                return function(*args, **kwargs)
            except _KnownDecisionGap as failure:
                known = (preserve_known and type(failure) is _KnownDecisionGap
                         and type(failure.args) is tuple and len(failure.args) == 1
                         and type(failure.args[0]) is str and failure.args[0] == _KNOWN_DECISION_GAP)
            except BaseException:
                pass
            if known:
                raise _KnownDecisionGap()
            raise EvidenceFailure(code)
        return invoke
    return decorate


def need(condition, code="EVIDENCE_REJECTED"):
    if not condition:
        raise EvidenceFailure(code)


def identifier(value):
    need(type(value) is str, "IDENTIFIER_TYPE")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError:
        raise EvidenceFailure("INVALID_UNICODE") from None
    need(1 <= len(encoded) <= 255 and bool(value.strip()), "IDENTIFIER_DOMAIN")
    return value


def digest(value):
    need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
         "SHA256_DOMAIN")
    return value


def uint(value):
    need(type(value) is int and 0 <= value <= (1 << 63) - 1, "U63_DOMAIN")
    return value


def utc(value):
    need(type(value) is int and -(1 << 63) <= value < (1 << 63), "UTC_DOMAIN")
    return value


def closed(value, names):
    need(type(value) is dict and set(value) == set(names), "CLOSED_SCHEMA")


def ref(value):
    closed(value, ("identity", "sha256"))
    identifier(value["identity"])
    digest(value["sha256"])
    return value


def reference(value):
    ref(value)
    return p.s.EvidenceReference(value["identity"], bytes.fromhex(value["sha256"]))


def wire_ref(value):
    value = p._service_reference(value)
    return {"identity": value.identity, "sha256": value.sha256.hex()}


def b64(value):
    need(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]*", value) is not None,
         "BASE64URL_DOMAIN")
    try:
        decoded = b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, TypeError):
        raise EvidenceFailure("BASE64URL_ENCODING") from None
    need(urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") == value,
         "BASE64URL_NONCANONICAL")
    return decoded


def encode64(value):
    need(type(value) is bytes, "IMMUTABLE_BYTES_REQUIRED")
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def arn(value):
    need(type(value) is str and re.fullmatch(
        r"arn:[A-Za-z0-9-]+:kms:[a-z0-9-]+:[0-9]{12}:key/[A-Za-z0-9-]+", value),
        "FULL_KMS_KEY_ARN_REQUIRED")
    return value


def refs(value):
    need(type(value) is list and len(value) <= 256, "REFERENCE_ARRAY")
    seen = set()
    for item in value:
        ref(item)
        need(item["identity"] not in seen, "DUPLICATE_REFERENCE_ID")
        seen.add(item["identity"])


def obligations(value):
    need(type(value) is list and all(type(x) is str for x in value), "OBLIGATIONS_TYPE")
    need(len(value) == len(set(value)), "DUPLICATE_OBLIGATION")
    # The exact expected tuple is checked against the complete frozen expectation.
    allowed = set(p._COMMON)
    for extra in p._OBLIGATIONS.values():
        allowed.update(extra)
    allowed.update(("EXACT_ROLE_CONTEXT_ISSUER", "TRANSITIVE_STAGE_RESTRICTIONS"))
    need(set(value) <= allowed, "UNKNOWN_OBLIGATION")


def path(value):
    need(type(value) is list and 1 <= len(value) <= 64, "FIELD_PATH")
    for component in value:
        if type(component) is int:
            need(0 <= component <= 4095, "FIELD_INDEX")
        else:
            identifier(component)


def _text(value):
    need(type(value) is str and 1 <= len(value.encode("utf-8")) <= 1024, "TEXT_DOMAIN")


CHECKS = {"ID": identifier, "H": digest, "U": uint, "UTC": utc, "R": ref,
          "ARN": arn, "O": obligations, "PATH": path, "TEXT": _text}


def schema(value, specification):
    closed(value, (name for name, _ in specification))
    for name, rule in specification:
        item = value[name]
        if rule == "?R":
            if item is not None:
                ref(item)
        elif rule in CHECKS:
            CHECKS[rule](item)
        elif type(rule) is tuple:
            need(type(item) is str and item in rule, "FIELD_LITERAL_" + name)
        else:
            need(type(item) is type(rule) and item == rule, "FIELD_LITERAL_" + name)


QF = (("view_type", "ID"), ("view_subject_ref", "R"),
      ("view_provenance_ref", "R"), ("obligations", "O"))
EN = (("admission_ref", "R"), ("operation_id", "ID"),
      ("state", "DURABLY_ENTERED_ORIGINAL"), ("decision_ref", "R"),
      ("state_version", "U"), ("fence_value", "U"))
CL = (("admission_id", "ID"), ("admission_ref", "R"), ("operation_id", "ID"),
      ("operation_role", ("CHECKPOINT_PUBLICATION", "ACTIVATION_CAS")),
      ("input_binding_ref", "R"), ("broker_principal_id", "ID"),
      ("dispatch_claim_id", "ID"), ("claim_decision", "CLAIMED"),
      ("claim_decision_ref", "R"), ("claim_commit_evidence_ref", "R"),
      ("claim_fence_value", "U"))
PB = (("operation", "ID"), ("checkpoint", "R"), ("package", "R"),
      ("approval", "R"), ("host_identity", "ID"),
      ("status", ("CONFIRMED", "REJECTED")), ("decision_ref", "R"),
      ("state_version", "U"), ("claim_ref", "R"))
AC = (("command_id", "ID"), ("payload_sha256", "H"), ("package", "R"),
      ("checkpoint", "R"), ("approval", "R"), ("register_id", "ID"),
      ("generation", 1), ("activation_id", "ID"), ("host_identity", "ID"),
      ("status", ("CONFIRMED", "REJECTED")), ("decision_ref", "R"),
      ("state_version", "U"), ("claim_ref", "R"))
RB = (("original_ref", "R"), ("activation_decision_ref", "R"), ("ordering_ref", "R"),
      ("state", "LINEARIZABLE_CURRENT_AFTER_ORIGINAL"), ("state_version", "U"),
      ("fence_value", "U"), ("result_ref", "R"), ("observation_time_ref", "R"))
CS = (("custody_attempt_id", "ID"), ("evidence_ref", "R"), ("raw_size", "U"),
      ("bucket_resource_ref", "R"), ("object_key", "TEXT"))
CR = CS + (("custody_role", "ID"), ("retention_mode", "COMPLIANCE"),
           ("required_retention_until", "UTC"), ("retention_requirement_ref", "R"),
           ("reservation_decision_ref", "R"), ("state", "RESERVED"))
CV = CS + (("version_id", "TEXT"), ("retention_mode", "COMPLIANCE"),
           ("observed_retention_until", "UTC"), ("retention_requirement_ref", "R"),
           ("upload_response_ref", "R"), ("exact_version_readback_ref", "R"),
           ("retention_evidence_ref", "R"))
CB = CS + (("version_id", "TEXT"), ("custody_role", "ID"),
           ("retention_mode", "COMPLIANCE"), ("observed_retention_until", "UTC"),
           ("retention_evidence_ref", "R"), ("version_observation_ref", "R"),
           ("binding_decision_ref", "R"), ("state", "BOUND"))
IV = (("activation_ref", "R"), ("publication_ref", "R"), ("readback_ref", "R"),
      ("requirements_ref", "R"), ("verification_result_ref", "R"),
      ("independence_ref", "R"), ("obligations", "O"),
      ("verdict", ("ALL_REQUIRED_OBLIGATIONS_PROVED", "REJECTED")))
VA = (("verified_subject_ref", "R"), ("authenticated_binding_ref", "R"),
      ("expectation_ref", "R"), ("interpretation_role", ROLES),
      ("interpretation_type", "ID"), ("obligations", "O"),
      ("verification_result_ref", "R"), ("verdict", ("VERIFIED", "REJECTED")))
PF = (("parent_role", ROLES), ("parent_subject_ref", "R"), ("field_path", "PATH"),
      ("frozen_role", "ID"), ("purpose", PURPOSES), ("leaf_ref", "R"),
      ("interpretation_ref", "R"), ("obligations", "O"))
GV = (("record_kind", ("SELECTION", "QUALIFICATION", "ADOPTION")),
      ("governed_provider_id", "ID"), ("governed_authority_id", "ID"),
      ("governed_incarnation_id", "ID"), ("governed_configuration_ref", "R"),
      ("governed_scope_ref", "R"), ("governance_decision_ref", "R"),
      ("independence_ref", "R"))
KB = (("authorized_key_arn", "ARN"), ("authorized_spki_sha256", "H"),
      ("authorized_algorithm", ALGORITHM), ("authorized_issuer_id", "ID"),
      ("authorized_provider_id", "ID"), ("authorized_authority_id", "ID"),
      ("authorized_namespace", "ID"), ("authorized_incarnation_id", "ID"),
      ("authorized_configuration_ref", "R"), ("permitted_receipt_roles", "ROLES"),
      ("authority_valid_from_us", "UTC"), ("authority_valid_until_us", "UTC"),
      ("supersedes_ref", "?R"), ("lifecycle_authority_ref", "R"),
      ("independent_approval_ref", "R"))
KS = (("observed_key_arn", "ARN"), ("observed_spki_sha256", "H"),
      ("key_binding_ref", "R"), ("lifecycle_state", ("ENABLED", "DISABLED",
       "PENDING_DELETION", "DELETED", "REVOKED", "COMPROMISED")),
      ("status_valid_from_us", "UTC"), ("status_valid_until_us", "UTC"),
      ("status_source_ref", "R"), ("supersession_ref", "?R"), ("status_authority_ref", "R"))
DETAILS = dict(zip(ROLES, (QF,) * 8 + (EN,) * 2 + (CL,) * 2 + (PB, AC, RB, CR, CV, CB,
                                                       IV, VA, PF, GV, KB, KS)))
BODY_FIELDS = ("profile_id", "schema_version", "receipt_role", "receipt_id", "issuer_id",
               "provider_id", "authority_id", "account_id", "region", "namespace",
               "incarnation_id", "configuration_ref", "adoption_ref", "key_binding_ref",
               "key_status_ref", "key_arn", "spki_sha256", "signature_algorithm", "stage",
               "subject_ref", "subject_issuer_id", "subject_kind", "request_id", "request_ref",
               "context", "predecessor_refs", "qualification_ref", "time_ref", "valid_from_us",
               "valid_until_us", "outcome", "rejection_reason", "details")
CONTEXT_FIELDS = ("kind", "register_id", "generation", "activation_id", "K", "J",
                  "host_ref", "scope_ref", "operation_id", "operation_role", "authorization_ref",
                  "input_binding_ref", "E_ref", "S0_ref", "C0_ref", "P_ref", "Q_ref",
                  "payload_ref", "publication_ref", "activation_ref", "request_facts_ref")
ENVELOPE_FIELDS = ("envelope_version", "profile_id", "body", "body_sha256", "signature",
                   "key_arn", "spki_sha256", "signature_algorithm", "key_binding_ref",
                   "key_status_ref", "authority_adoption_ref", "trusted_time_ref", "subject_custody_ref")


def all_refs(value):
    if type(value) is dict:
        if set(value) == {"identity", "sha256"}:
            yield ref(value)
        else:
            for child in value.values():
                yield from all_refs(child)
    elif type(value) in (list, tuple):
        for child in value:
            yield from all_refs(child)


def required_predecessors(body, typed_leaves=()):
    """Codec section 5 order, first exact occurrence; never a hash domain."""
    excluded = [body[name] for name in ("subject_ref", "configuration_ref", "adoption_ref",
                 "key_binding_ref", "key_status_ref", "qualification_ref", "time_ref")]
    candidates = [body["context"][name] for name in CONTEXT_FIELDS
                  if name.endswith("_ref") and body["context"][name] is not None]
    candidates += [body["details"][name] for name, rule in DETAILS[body["receipt_role"]]
                   if rule in ("R", "?R") and body["details"][name] is not None]
    candidates += list(typed_leaves)
    result = []
    seen = {}
    for item in candidates:
        ref(item)
        if item in excluded:
            continue
        need(item["identity"] not in seen or seen[item["identity"]] == item["sha256"], "CONFLICTING_PREDECESSOR_IDENTITY")
        if item["identity"] not in seen:
            result.append(item)
            seen[item["identity"]] = item["sha256"]
    need(len(result) <= 256, "PREDECESSOR_BOUND")
    return result


def frozen_leaves(value, *, skip=None):
    """Same closed traversal as frozen _proofs, excluding live ownership input."""
    if type(value) in (p.s.EvidenceReference, p.a.Reference):
        if skip is None or not same(p._service_reference(value), p._service_reference(skip)):
            yield wire_ref(value)
    elif type(value) is p.a.OpaqueEvidence:
        yield from frozen_leaves(value.reference, skip=skip)
        yield from frozen_leaves(value.qualification, skip=skip)
    elif type(value) is tuple:
        for child in value:
            yield from frozen_leaves(child, skip=skip)
    elif is_dataclass(value):
        for field in fields(value):
            if field.name not in ("request", "snapshot"):
                yield from frozen_leaves(getattr(value, field.name), skip=skip)


def _pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def parse(raw):
    need(type(raw) is bytes and not raw.startswith(b"\xef\xbb\xbf"), "UTF8_NO_BOM")
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_pairs,
                           parse_float=lambda _: need(False, "FLOAT_FORBIDDEN"),
                           parse_constant=lambda _: need(False, "NONFINITE_FORBIDDEN"))
        def unicode_tree(item):
            if type(item) is str:
                item.encode("utf-8", "strict")
            elif type(item) is dict:
                for key, child in item.items():
                    unicode_tree(key)
                    unicode_tree(child)
            elif type(item) is list:
                for child in item:
                    unicode_tree(child)
        unicode_tree(value)
        return value
    except (UnicodeError, ValueError, RecursionError):
        raise EvidenceFailure("JSON_PARSE_FAILURE") from None


def validate_context(value, role):
    closed(value, CONTEXT_FIELDS)
    need(value["kind"] in KINDS, "CONTEXT_KIND")
    kind = value["kind"]
    register = value["register_id"] is not None
    need(register or kind in ("CUSTODY", "GOVERNANCE", "KEY"), "REGISTER_CONTEXT")
    for name in ("register_id", "activation_id", "K", "J"):
        need((value[name] is not None) == register, "REGISTER_PAIR")
        if register:
            identifier(value[name])
    need(type(value["generation"]) is int and value["generation"] == 1 if register
         else value["generation"] is None, "GENERATION_ONE")
    protected = role.startswith(("ADMISSION_", "ENTRY_", "CLAIM_", "RESULT_")) or role == "READBACK"
    if value["operation_id"] is not None:
        identifier(value["operation_id"])
        need(value["operation_role"] in ("CHECKPOINT_PUBLICATION", "ACTIVATION_CAS"), "OPERATION_ROLE")
    else:
        need(not protected and value["operation_role"] is None, "OPERATION_REQUIRED")
    applicable = {
        "host_ref": register, "input_binding_ref": value["operation_id"] is not None,
        "E_ref": kind in ("PACKAGE", "EXECUTION", "APPROVAL", "PUBLICATION", "CAS", "READBACK", "OPENING"),
        "Q_ref": kind in ("EXECUTION", "APPROVAL", "PUBLICATION", "CAS", "READBACK", "OPENING"),
        "payload_ref": kind in ("CAS", "READBACK", "OPENING"),
        "publication_ref": kind in ("CAS", "READBACK", "OPENING"),
        "activation_ref": kind in ("READBACK", "OPENING"),
    }
    applicable.update({name: applicable["E_ref"] for name in ("S0_ref", "C0_ref", "P_ref")})
    for name in ("scope_ref", "authorization_ref", "request_facts_ref"):
        ref(value[name])
    for name, required in applicable.items():
        # Inherited VA/PF contexts preserve their original admission input binding.
        if name == "input_binding_ref" and role in ("VERIFIER_ATTESTATION", "PROOF_BINDING"):
            required = value["operation_id"] is not None
        if required:
            ref(value[name])
        else:
            need(value[name] is None, "INAPPLICABLE_CONTEXT_" + name)
    expected_kind = dict(zip(ROLES[:6], KINDS[:6]))
    expected_kind.update({r: "PUBLICATION" for r in ROLES if r.endswith("_PUBLICATION")})
    expected_kind.update({r: "CAS" for r in ROLES if r.endswith("_CAS")})
    expected_kind.update({"READBACK": "READBACK", "INDEPENDENT_RESULT": "READBACK",
                          "GOVERNANCE": "GOVERNANCE", "KEY_BINDING": "KEY", "KEY_STATUS": "KEY"})
    expected_kind.update({r: "CUSTODY" for r in ("CUSTODY_RESERVE", "CUSTODY_VERSION", "CUSTODY_BIND")})
    if role in expected_kind:
        need(kind == expected_kind[role], "ROLE_CONTEXT")


def validate_body(raw):
    body = parse(raw)
    closed(body, BODY_FIELDS)
    role = body["receipt_role"]
    need(type(role) is str and role in ROLES, "UNKNOWN_RECEIPT_ROLE")
    need(body["profile_id"] == PROFILE and type(body["schema_version"]) is int
         and body["schema_version"] == 1 and body["signature_algorithm"] == ALGORITHM,
         "PROFILE_MISMATCH")
    for name in ("receipt_id", "issuer_id", "provider_id", "authority_id", "region", "namespace",
                 "incarnation_id", "subject_issuer_id", "request_id"):
        identifier(body[name])
    need(type(body["account_id"]) is str and re.fullmatch(r"[0-9]{12}", body["account_id"]), "ACCOUNT_ID")
    arn(body["key_arn"])
    parts = body["key_arn"].split(":")
    need(parts[3:5] == [body["region"], body["account_id"]], "KEY_ACCOUNT_REGION")
    digest(body["spki_sha256"])
    for name in ("configuration_ref", "adoption_ref", "key_binding_ref", "key_status_ref",
                 "subject_ref", "request_ref", "qualification_ref", "time_ref"):
        ref(body[name])
    need(body["subject_kind"] == "OPAQUE_EXTERNAL_EVIDENCE", "OPAQUE_SUBJECT_REQUIRED")
    need(body["stage"] in ("UPSTREAM_ONLY", "Q", "CURRENT", "INDEPENDENT_RESULT_VERIFICATION"), "STAGE")
    expected_stage = {"QUAL_PACKAGE": "UPSTREAM_ONLY", "QUAL_CREATION": "UPSTREAM_ONLY",
                      "QUAL_APPROVAL": "Q", "INDEPENDENT_RESULT": "INDEPENDENT_RESULT_VERIFICATION"}
    if role not in ("VERIFIER_ATTESTATION", "PROOF_BINDING"):
        need(body["stage"] == expected_stage.get(role, "CURRENT"), "ROLE_STAGE")
    validate_context(body["context"], role)
    refs(body["predecessor_refs"])
    need(body["subject_ref"] not in body["predecessor_refs"], "SUBJECT_AS_PREDECESSOR")
    utc(body["valid_from_us"])
    utc(body["valid_until_us"])
    need(body["valid_from_us"] <= body["valid_until_us"], "VALIDITY_INTERVAL")
    need(body["outcome"] in ("ESTABLISHED", "REJECTED"), "OUTCOME")
    need(body["rejection_reason"] == "NONE" if body["outcome"] == "ESTABLISHED"
         else body["rejection_reason"] in REASONS, "REJECTION_REASON")
    specification = DETAILS[role]
    if role == "KEY_BINDING":
        specification = tuple((n, "ID" if r == "ROLES" else r) for n, r in specification
                              if n != "permitted_receipt_roles")
        details = body["details"]
        closed(details, [n for n, _ in KB])
        permitted = details["permitted_receipt_roles"]
        need(type(permitted) is list and 1 <= len(permitted) <= 24 and
             all(type(r) is str and r in ROLES for r in permitted) and len(set(permitted)) == len(permitted),
             "PERMITTED_ROLES")
        schema({n: details[n] for n, _ in specification}, specification)
    else:
        schema(body["details"], specification)
    details = body["details"]
    if role in ROLES[:8]:
        need(details["view_subject_ref"] == body["subject_ref"], "QF_SUBJECT")
        names = ("QualifiedPackageBindings", "QualifiedPreparation", "QualifiedCreation", "QualifiedExecution",
                 "ApprovalView", "QualifiedOpen", "EffectAdmission", "EffectAdmission")
        frozen_roles = ("package", "preparation", "creation", "execution", "approval", "opening",
                        "publication-admission", "cas-admission")
        index = ROLES.index(role)
        need(details["view_type"] == names[index]
             and tuple(details["obligations"]) == p._COMMON + p._OBLIGATIONS[frozen_roles[index]],
             "EXACT_QF_INTERPRETATION_AND_OBLIGATIONS")
    if role in ("CLAIM_PUBLICATION", "CLAIM_CAS"):
        need(details["operation_role"] == ("CHECKPOINT_PUBLICATION" if role.endswith("PUBLICATION") else "ACTIVATION_CAS"),
             "CLAIM_ROLE")
    if role.startswith(("ENTRY_", "CLAIM_")):
        need(details["operation_id"] == body["context"]["operation_id"], "OPERATION_CONTEXT")
    if role == "RESULT_PUBLICATION":
        need(details["operation"] == body["context"]["operation_id"], "PUBLICATION_OPERATION_CONTEXT")
    if role == "RESULT_CAS":
        need(details["command_id"] == body["context"]["K"], "ACTIVATION_COMMAND_CONTEXT")
    if role in ("RESULT_PUBLICATION", "RESULT_CAS"):
        need((details["status"] == "CONFIRMED") == (body["outcome"] == "ESTABLISHED"), "RESULT_OUTCOME")
    if role in ("VERIFIER_ATTESTATION", "INDEPENDENT_RESULT"):
        need((details["verdict"] != "REJECTED") == (body["outcome"] == "ESTABLISHED"), "VERDICT_OUTCOME")
    if role == "PROOF_BINDING":
        need(details["leaf_ref"] == body["subject_ref"], "PROOF_LEAF")
    for start, end in (("authority_valid_from_us", "authority_valid_until_us"),
                       ("status_valid_from_us", "status_valid_until_us")):
        if start in details:
            need(details[start] <= details[end], "DETAIL_VALIDITY")
    if "version_id" in details:
        need(details["version_id"] != "null", "NULL_VERSION")
    if role.startswith("CUSTODY_") and body["outcome"] == "ESTABLISHED":
        need(details["raw_size"] <= MAX_SINGLE_UPLOAD_BYTES, "SIZE_UNSUPPORTED")
    if role in ("CUSTODY_RESERVE", "CUSTODY_BIND"):
        need(details["object_key"] == object_key(body["namespace"], body["incarnation_id"],
             details["custody_role"], details["evidence_ref"]["identity"], 1024), "DETERMINISTIC_CUSTODY_KEY")
    prefix = required_predecessors(body)
    need(body["predecessor_refs"][:len(prefix)] == prefix, "REQUIRED_PREDECESSOR_ORDER")
    return body


def producer_bytes(value, fields):
    closed(value, fields)
    # Producer formatting only. Verification always uses the original bytes.
    ordered = {k: value[k] for k in fields}
    if tuple(fields) == BODY_FIELDS:
        ordered["context"] = {k: value["context"][k] for k in CONTEXT_FIELDS}
        ordered["details"] = {k: value["details"][k] for k, _ in DETAILS[value["receipt_role"]]}
    def order_refs(item):
        if type(item) is dict:
            if set(item) == {"identity", "sha256"}:
                return {"identity": item["identity"], "sha256": item["sha256"]}
            return {k: order_refs(v) for k, v in item.items()}
        if type(item) is list:
            return [order_refs(v) for v in item]
        return item
    return json.dumps(order_refs(ordered), ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def assemble(body_bytes, signature, subject_custody_ref):
    body = validate_body(body_bytes)
    need(type(signature) is bytes and len(signature) == 384, "SIGNATURE_LENGTH")
    if subject_custody_ref is not None:
        ref(subject_custody_ref)
    envelope = dict(envelope_version=1, profile_id=PROFILE, body=encode64(body_bytes),
                    body_sha256=sha256(body_bytes).hexdigest(), signature=encode64(signature),
                    key_arn=body["key_arn"], spki_sha256=body["spki_sha256"],
                    signature_algorithm=ALGORITHM, key_binding_ref=body["key_binding_ref"],
                    key_status_ref=body["key_status_ref"], authority_adoption_ref=body["adoption_ref"],
                    trusted_time_ref=body["time_ref"], subject_custody_ref=subject_custody_ref)
    raw = producer_bytes(envelope, ENVELOPE_FIELDS)
    return p.RetainedEvidence(p.s.EvidenceReference(body["receipt_id"], sha256(raw).digest()), raw)


def envelope(record):
    need(type(record) is p.RetainedEvidence and type(record.raw) is bytes, "RETAINED_RECORD")
    need(sha256(record.raw).digest() == record.reference.sha256, "COMPLETE_ENVELOPE_DIGEST")
    env = parse(record.raw)
    closed(env, ENVELOPE_FIELDS)
    need(type(env["envelope_version"]) is int and env["envelope_version"] == 1
         and env["profile_id"] == PROFILE and env["signature_algorithm"] == ALGORITHM, "ENVELOPE_PROFILE")
    raw = b64(env["body"])
    need(sha256(raw).hexdigest() == env["body_sha256"], "EXACT_BODY_DIGEST")
    body = validate_body(raw)
    need(record.reference.identity == body["receipt_id"], "RECEIPT_IDENTITY")
    need(wire_ref(record.reference) not in tuple(all_refs(body)), "SELF_REFERENTIAL_SIGNED_BODY")
    for external, internal in (("key_arn", "key_arn"), ("spki_sha256", "spki_sha256"),
                               ("key_binding_ref", "key_binding_ref"), ("key_status_ref", "key_status_ref"),
                               ("authority_adoption_ref", "adoption_ref"), ("trusted_time_ref", "time_ref")):
        need(env[external] == body[internal], "DETACHED_BINDING_MISMATCH")
    if env["subject_custody_ref"] is not None:
        ref(env["subject_custody_ref"])
        need(env["subject_custody_ref"] != wire_ref(record.reference), "SELF_CUSTODY_REFERENCE")
    signature = b64(env["signature"])
    need(len(signature) == 384, "SIGNATURE_LENGTH")
    return body, raw, signature, env


def verify_signature(body_bytes, signature, der_spki, expected_hash):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
    from cryptography.exceptions import InvalidSignature
    need(type(der_spki) is bytes and sha256(der_spki).hexdigest() == expected_hash, "SPKI_IDENTITY")
    key = serialization.load_der_public_key(der_spki)
    need(isinstance(key, rsa.RSAPublicKey) and key.key_size == 3072, "RSA_3072_REQUIRED")
    need(key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
         == der_spki, "EXACT_DER_SPKI")
    need(type(signature) is bytes and len(signature) == 384, "SIGNATURE_LENGTH")
    try:
        key.verify(signature, sha256(body_bytes).digest(),
                   padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
                   utils.Prehashed(hashes.SHA256()))
    except InvalidSignature:
        raise EvidenceFailure("BAD_SIGNATURE") from None


@closed_boundary("AUTHENTICATION_UNCONFIRMED_NO_RESIGN")
def kms_sign(body_bytes, kms):
    """Exactly one explicitly supplied, prequalified low-level KMS invocation."""
    body = validate_body(body_bytes)
    try:
        response = kms.sign(KeyId=body["key_arn"], Message=sha256(body_bytes).digest(),
                            MessageType="DIGEST", SigningAlgorithm=ALGORITHM)
    except Exception:
        raise EvidenceFailure("AUTHENTICATION_UNCONFIRMED_NO_RESIGN") from None
    need(response.get("KeyId") == body["key_arn"] and response.get("SigningAlgorithm") == ALGORITHM,
         "KMS_RESPONSE_BINDING")
    signature = response.get("Signature")
    need(type(signature) is bytes and len(signature) == 384, "KMS_SIGNATURE_LENGTH")
    return signature


class Once:
    """An in-memory irreversible latch, never a transferable/recoverable permit."""
    def __init__(self):
        self._lock, self._used = Lock(), False

    def consume(self):
        with self._lock:
            need(not self._used, "STALE_CONTINUATION")
            self._used = True


def object_key(namespace, incarnation, custody_role, identity, qualified_key_limit):
    values = (namespace, incarnation, custody_role, identity)
    for value in values:
        identifier(value)
    key = "evidence/v1/" + "/".join(v.encode("utf-8").hex() for v in values)
    need(type(qualified_key_limit) is int and len(key.encode("utf-8")) <= qualified_key_limit,
         "SIZE_UNSUPPORTED")
    return key


@dataclass(frozen=True, repr=False)
class CustodyPlan:
    namespace: str
    incarnation: str
    role: str
    attempt_id: str
    bucket: str
    bucket_owner: str
    bucket_resource: p.s.EvidenceReference
    retention_until_us: int
    retention_requirement: p.s.EvidenceReference
    key_limit: int
    single_request_capacity: int


class ExactVersionEvidence(p.EvidenceClient):
    """RESERVE -> one upload -> exact VERSION validation -> BIND -> resolution.

    custody is the fixed broker custody handler; authority is an independently
    qualified EvidenceVerifier-backed custody service. Its approved finite
    control-evidence plan must not recurse through this client's own receipts.
    """
    def __init__(self, *, s3, custody, authority, plans):
        self.s3, self.custody, self.authority, self.plans = s3, custody, authority, plans

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def retain(self, record):
        need(type(record) is p.RetainedEvidence and type(record.raw) is bytes, "EXACT_RAW_REQUIRED")
        need(sha256(record.raw).digest() == record.reference.sha256, "RAW_DIGEST")
        need(len(record.raw) <= MAX_SINGLE_UPLOAD_BYTES, "REJECTED_SIZE_UNSUPPORTED")
        plan = self.plans.for_record(record)
        need(type(plan) is CustodyPlan and plan.single_request_capacity >= MAX_SINGLE_UPLOAD_BYTES,
             "PROVIDER_CAPACITY_NOT_QUALIFIED")
        key = object_key(plan.namespace, plan.incarnation, plan.role,
                         record.reference.identity, plan.key_limit)
        # This independently checks adopted resource, scoped caller, current
        # retention authorization and exact subject before entering RESERVE.
        self.authority.check_plan(record, plan, key)
        reservation = self.custody.reserve(record, plan, key)
        self.authority.check_reservation(reservation, record, plan, key)
        latch = Once()
        latch.consume()
        try:
            from datetime import datetime, timedelta, timezone
            until = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=plan.retention_until_us)
            response = self.s3.put_object(
                Bucket=plan.bucket, Key=key, Body=record.raw, ContentLength=len(record.raw),
                ChecksumSHA256=__import__("base64").b64encode(record.reference.sha256).decode("ascii"),
                IfNoneMatch="*", ObjectLockMode="COMPLIANCE", ObjectLockRetainUntilDate=until,
                ExpectedBucketOwner=plan.bucket_owner)
            version = response.get("VersionId")
            need(type(version) is str and version and version != "null", "EXACT_VERSION_REQUIRED")
            observed = self._read(record.reference, plan, key, version)
            need(observed.raw == record.raw, "UPLOAD_BYTES_MISMATCH")
            version_evidence = self.authority.version_observation(record, plan, key, version, response)
            binding = self.custody.bind(reservation, version_evidence)
            self.authority.check_binding(binding, record, plan, key, version)
            need(self.resolve(record.reference).raw == record.raw, "BOUND_RESOLUTION_MISMATCH")
        except Exception:
            # The original reservation stays consumed, including conditional
            # conflicts. No new key, new attempt, upload or recovery is tried.
            raise EvidenceFailure("UNKNOWN_CUSTODY_STOP_NO_RETRY") from None
        return record.reference

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def _read(self, reference_, plan, key, version):
        need(type(version) is str and version and version != "null", "EXACT_VERSION_REQUIRED")
        response = self.s3.get_object(Bucket=plan.bucket, Key=key, VersionId=version,
                                      ExpectedBucketOwner=plan.bucket_owner)
        need(response.get("VersionId") == version and response.get("ObjectLockMode") == "COMPLIANCE",
             "VERSION_RETENTION_MISMATCH")
        stream = response["Body"]
        try:
            raw = stream.read(MAX_SINGLE_UPLOAD_BYTES + 1)
            need(type(raw) is bytes and len(raw) <= MAX_SINGLE_UPLOAD_BYTES, "SIZE_UNSUPPORTED")
            need(stream.read(1) == b"", "INCOMPLETE_VERSION_READ")
        finally:
            stream.close()
        need(sha256(raw).digest() == reference_.sha256, "EXACT_VERSION_DIGEST")
        self.authority.check_version_retention(response, plan, key, version, reference_, len(raw))
        return p.RetainedEvidence(reference_, raw)

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def resolve(self, reference_):
        p._reference(reference_)
        locator = self.custody.resolve(reference_)
        plan, key, version = self.authority.bound_locator(locator, reference_)
        need(key == object_key(plan.namespace, plan.incarnation, plan.role,
                               reference_.identity, plan.key_limit), "LOCATOR_KEY")
        return self._read(reference_, plan, key, version)


class ReceiptVerifier(p.EvidenceVerifier):
    """Cryptographic gate plus the existing independent native-claims boundary.

    trust supplies already independently approved terminal roots, exact key DER,
    lifecycle/status, custody and qualified time. interpreter is the selected
    native EvidenceVerifier (not a callable projected-success decoder). It must
    establish every Appendix A field from original external evidence.
    """
    def __init__(self, *, evidence, trust, interpreter):
        need(isinstance(interpreter, p.EvidenceVerifier), "QUALIFIED_NATIVE_VERIFIER_REQUIRED")
        self.evidence, self.trust, self.interpreter = evidence, trust, interpreter

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def authenticate(self, record, expected_role, expected_context):
        body, raw, signature, env = envelope(record)
        need(body["receipt_role"] == expected_role and body["context"] == expected_context, "EXACT_RECEIPT_ASSOCIATION")
        # validate_receipt closes issuer/roles, independent adoption, incarnation,
        # key usage/spec, complete current interval, status, original subject,
        # predecessor order, root termination and subject/control custody.
        der = self.trust.validate_receipt(record, body, env, self.evidence)
        verify_signature(raw, signature, der, body["spki_sha256"])
        need(body["outcome"] == "ESTABLISHED", "NEGATIVE_RECEIPT_NOT_QUALIFIED")
        return body

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def verify(self, record, expectation):
        before = capture((record, expectation))
        binding_record, role, context = self.trust.binding_for(record, expectation)
        body = self.authenticate(binding_record, role, context)
        if not same(binding_record.reference, record.reference):
            need(body["subject_ref"] == wire_ref(record.reference), "ORIGINAL_SUBJECT_BINDING")
        need(self.evidence.resolve(record.reference).raw == record.raw, "ORIGINAL_RAW_SUBSTITUTION")
        view = self.interpreter.verify(record, expectation)
        need(type(view) is p.AuthenticatedView and same(view.reference, record.reference)
             and same(view.expectation, expectation), "EXACT_FROZEN_VIEW")
        p._strict_view(view.value)
        p.a._time(view.clock, not_before=view.valid_from_us,
                  valid_from=view.valid_from_us, valid_until=view.valid_until_us)
        self.trust.validate_interpretation(body, view, self.evidence, self)
        need(view.provenance != record.reference, "SELF_AUTHENTICATION")
        self.evidence.resolve(view.provenance)
        need(capture((record, expectation)) == before, "INPUT_MUTATION")
        return view


@closed_boundary("UNKNOWN_ADMISSION_PROVENANCE_UNAVAILABLE_NO_REPLAY")
def admission_provenance(*, role, subject, expectation, sources, verifier, designation):
    """ASBQ terminating VA path, then APM source selection BEFORE comparison.

    sources contains completed E0/P0 records, not arbitrary AuthenticatedViews.
    designation is the independently qualified T-authorized exact association
    checker, with the frozen preallocated receipt_id and immutable S/X/D inputs.
    It never uses the final E0 digest to construct an upstream input.
    """
    need(role in ("ADMISSION_PUBLICATION", "ADMISSION_CAS"), "ADMISSION_ROLE")
    # Caller copies are only transport inputs. The qualified original
    # request/result association, under T, determines the entire eligible set.
    records = designation.authoritative_sources(tuple(sources))
    accepted = []
    seen = set()
    for record in records:
        body, _, _, _ = envelope(record)
        # Competing completed E0s under the same designated association remain
        # ambiguous even if one later fails status/authentication checks.
        if designation.matches_upstream(body, subject, expectation, role):
            identity = (record.reference.identity, record.reference.sha256)
            need(identity not in seen, "AMBIGUOUS_E0_SOURCE")
            seen.add(identity)
            need(body["receipt_role"] == "VERIFIER_ATTESTATION", "ASBQ_VA_REQUIRED")
            d = body["details"]
            need(d["verified_subject_ref"] == wire_ref(subject.reference)
                 and d["verification_result_ref"] == body["subject_ref"]
                 and d["interpretation_role"] == role and d["interpretation_type"] == "EffectAdmission"
                 and tuple(d["obligations"]) == expectation.obligations, "ASBQ_EXACT_SUBJECT_CONTEXT")
            verifier.authenticate(record, "VERIFIER_ATTESTATION", body["context"])
            # Checks actual independent D/native claims, T, all U before E0,
            # preallocated ID, exact-version P0 custody, final association and
            # all frozen role/context/obligation/status/time requirements.
            view = designation.qualified_view(record, body, subject, expectation)
            need(type(view) is p.AuthenticatedView and type(view.value) is p.EffectAdmission
                 and same(view.reference, subject.reference)
                 and same(view.expectation, expectation)
                 and same(view.provenance, record.reference), "ASBQ_V0_P0_ASSOCIATION")
            verifier.evidence.resolve(record.reference)
            p.a._time(view.clock, not_before=view.valid_from_us,
                      valid_from=view.valid_from_us, valid_until=view.valid_until_us)
            accepted.append(view)
    need(len(seen) == 1 and len(accepted) == 1, "MISSING_OR_AMBIGUOUS_ADMISSION_PROVENANCE")
    return accepted[0]


def bind_admission_body(body, *, prior_view, role, subject, expectation):
    need(role in ("ADMISSION_PUBLICATION", "ADMISSION_CAS") and body["receipt_role"] == role,
         "ADMISSION_ROLE")
    need(type(prior_view) is p.AuthenticatedView and type(prior_view.value) is p.EffectAdmission
         and same(prior_view.reference, subject.reference)
         and same(prior_view.expectation, expectation), "ROLE_SPECIFIC_PRIOR_V0")
    need(body["subject_ref"] == wire_ref(subject.reference)
         and body["details"]["view_provenance_ref"] == wire_ref(prior_view.provenance),
         "APM_EXACT_IDENTITY_AND_DIGEST")
    # No mutation of EffectAdmission, upstream X/D or the already complete E0.
    updated = dict(body)
    updated["predecessor_refs"] = required_predecessors(body, frozen_leaves(prior_view.value))
    return validate_body(producer_bytes(updated, BODY_FIELDS))


class ReceiptTrust:
    """Use independently authenticated frozen key/governance material.

    material.view resolves and verifies original external records under supplied
    approved T; it must terminate at the independently approved bootstrap, not
    call this receipt's own verifier to approve its key. associations contains
    exact original-record/expectation -> retained binding associations. Neither
    a key ARN nor an SDK GetPublicKey response establishes authority.
    """
    def __init__(self, *, material, spki_records, associations, admission_sources=()):
        self.material, self.spki_records = material, tuple(spki_records)
        self.associations, self.admission_sources = tuple(associations), tuple(admission_sources)

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def binding_for(self, record, expectation):
        matches = [(binding, role, context) for subject, expected, binding, role, context in self.associations
                   if same(subject, record.reference) and same(expected, expectation)]
        need(len(matches) == 1, "MISSING_OR_AMBIGUOUS_RECEIPT_BINDING")
        return matches[0]

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def validate_receipt(self, record, body, env, evidence):
        kb_view = self.material.view(reference(body["key_binding_ref"]))
        ks_view = self.material.view(reference(body["key_status_ref"]))
        adoption_view = self.material.view(reference(body["adoption_ref"]))
        clock_view = self.material.view(reference(body["time_ref"]))
        kb, ks, adoption = kb_view.value, ks_view.value, adoption_view.value
        need(type(kb) is dict and type(ks) is dict and type(adoption) is dict, "QUALIFIED_KEY_GOVERNANCE_CLAIMS")
        # Values here are the independently interpreted existing KB/KS/GV
        # details, not new serialized authority objects.
        closed(kb, (n for n, _ in KB))
        schema(ks, KS)
        schema(adoption, GV)
        need(kb["authorized_algorithm"] == ALGORITHM
             and body["receipt_role"] in kb["permitted_receipt_roles"], "KEY_ROLE_AUTHORITY")
        for actual, approved in (("key_arn", "authorized_key_arn"), ("spki_sha256", "authorized_spki_sha256"),
                                  ("issuer_id", "authorized_issuer_id"), ("provider_id", "authorized_provider_id"),
                                  ("authority_id", "authorized_authority_id"), ("namespace", "authorized_namespace"),
                                  ("incarnation_id", "authorized_incarnation_id"),
                                  ("configuration_ref", "authorized_configuration_ref")):
            need(body[actual] == kb[approved], "KEY_SCOPE_MISMATCH")
        need(ks["observed_key_arn"] == body["key_arn"]
             and ks["observed_spki_sha256"] == body["spki_sha256"]
             and ks["key_binding_ref"] == body["key_binding_ref"]
             and ks["lifecycle_state"] == "ENABLED" and ks["supersession_ref"] is None, "KEY_NOT_CURRENTLY_AUTHORIZED")
        need(adoption["record_kind"] == "ADOPTION"
             and adoption["governed_provider_id"] == body["provider_id"]
             and adoption["governed_authority_id"] == body["authority_id"]
             and adoption["governed_incarnation_id"] == body["incarnation_id"]
             and adoption["governed_configuration_ref"] == body["configuration_ref"]
             and adoption["governed_scope_ref"] == body["context"]["scope_ref"], "ADOPTION_SCOPE")
        lower = max(body["valid_from_us"], kb["authority_valid_from_us"], ks["status_valid_from_us"],
                    kb_view.valid_from_us, ks_view.valid_from_us, adoption_view.valid_from_us)
        upper = min(body["valid_until_us"], kb["authority_valid_until_us"], ks["status_valid_until_us"],
                    kb_view.valid_until_us, ks_view.valid_until_us, adoption_view.valid_until_us)
        p.a._time(clock_view.clock, not_before=lower, valid_from=lower, valid_until=upper)
        for name in ("configuration_ref", "qualification_ref", "request_ref"):
            self.material.view(reference(body[name]))
        for dependency in body["predecessor_refs"]:
            evidence.resolve(reference(dependency))
        subject = evidence.resolve(reference(body["subject_ref"]))
        need(sha256(subject.raw).hexdigest() == body["subject_ref"]["sha256"], "SUBJECT_RAW_DIGEST")
        if env["subject_custody_ref"] is not None:
            custody = self.material.view(reference(env["subject_custody_ref"])).value
            schema(custody, CB)
            need(custody["evidence_ref"] == body["subject_ref"]
                 and custody["raw_size"] == len(subject.raw) and custody["state"] == "BOUND", "SUBJECT_CUSTODY_BINDING")
        else:
            # The independently approved bootstrap/control interpretation must
            # explicitly prove its finite raw-retention arrangement.
            control = self.material.view(reference(body["qualification_ref"]))
            self.validate_control_retention(control, body, subject)
        candidates = [r.raw for r in self.spki_records if sha256(r.raw).hexdigest() == body["spki_sha256"]]
        need(len(candidates) == 1, "UNKNOWN_OR_AMBIGUOUS_PUBLIC_KEY")
        return candidates[0]

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def validate_control_retention(self, control, body, subject):
        # Eligibility is about the ORIGINAL subject, not a retention label.
        # QF admissions/qualifications and ordinary returned decision/results
        # never gain this exception by supplying control-looking metadata.
        need(body["receipt_role"] not in ROLES[:14] + ("INDEPENDENT_RESULT",),
             "ORDINARY_RETURNED_SUBJECT_REQUIRES_BOUND_CUSTODY")
        need(type(subject) is p.RetainedEvidence and type(subject.raw) is bytes
             and same(subject.reference, reference(body["subject_ref"]))
             and sha256(subject.raw).digest() == subject.reference.sha256, "ORIGINAL_CONTROL_SUBJECT")
        original = self.material.evidence.resolve(subject.reference)
        need(type(original) is p.RetainedEvidence and same(original.reference, subject.reference)
             and original.raw == subject.raw, "ORIGINAL_CONTROL_RAW_ASSOCIATION")
        # A completed returned envelope is never an original bootstrap/control
        # subject for this purpose, even if somebody labels it a root/control.
        decoded = None
        try:
            decoded = parse(subject.raw)
        except EvidenceFailure:
            pass
        need(not (type(decoded) is dict and {"envelope_version", "body", "signature"} <= decoded.keys()),
             "RETURNED_ENVELOPE_REQUIRES_BOUND_CUSTODY")
        source = self.material.view(subject.reference)
        need(type(source) is p.AuthenticatedView and same(source.reference, subject.reference)
             and source.expectation.stage == body["stage"], "AUTHENTICATED_ORIGINAL_SUBJECT_REQUIRED")
        p.a._time(source.clock, not_before=source.valid_from_us,
                  valid_from=source.valid_from_us, valid_until=source.valid_until_us)
        # In-memory projection of the existing independently authenticated finite
        # bootstrap/control arrangement. Never inferred from common obligations.
        need(type(control) is p.AuthenticatedView
             and same(control.reference, reference(body["qualification_ref"]))
             and control.expectation.stage == body["stage"], "CONTROL_RETENTION_QUALIFICATION")
        authenticated = self.material.view(reference(body["qualification_ref"]))
        need(type(authenticated) is p.AuthenticatedView and same(authenticated, control),
             "UNAUTHENTICATED_CONTROL_CLASSIFICATION_OR_ASSOCIATION")
        facts = authenticated.value
        need(type(facts) is tuple and len(facts) == 5, "FINITE_CONTROL_ARRANGEMENT_REQUIRED")
        evidence_class, arrangement, subject_ref, context, scope = facts
        need(evidence_class in ("BOOTSTRAP_ROOT", "CONTROL_EVIDENCE")
             and same(subject_ref, subject.reference) and same(context, body["context"])
             and same(scope, (body["namespace"], body["incarnation_id"], body["authority_id"],
                              body["provider_id"], body["configuration_ref"], body["stage"]))
             and "IMMUTABLE_RAW_RETENTION" in control.expectation.obligations,
             "BOOTSTRAP_CONTROL_RETENTION_NOT_ESTABLISHED")
        if evidence_class == "BOOTSTRAP_ROOT":
            # Existing separately supplied approved bootstrap roots, not a new
            # root derived from this receipt or the caller's class string.
            need(any(same(subject.reference, root) for root in self.material.roots)
                 and type(source.value) is p.s.EvidenceReference
                 and same(source.value, subject.reference), "SUBJECT_NOT_APPROVED_BOOTSTRAP_ROOT")
        else:
            # Existing ReceiptRecipes.retain_control_observation representation:
            # actual qualified internal acknowledgement, NOT a returned QF,
            # EffectAdmission, ActivationResult, SQL decision or signed envelope.
            need(type(decoded) is dict and type(source.value) is tuple and len(source.value) == 4,
                 "SUBJECT_NOT_ORIGINAL_CONTROL_OBSERVATION")
            closed(decoded, ("request_facts", "actual_result", "before", "after"))
            request_id, result, before, after = source.value
            need(type(decoded["request_facts"]) is dict
                 and decoded["request_facts"].get("request_id") == request_id
                 and same(decoded["actual_result"], result), "CONTROL_REQUEST_RESULT_ASSOCIATION")
            for name in ("namespace", "incarnation_id", "configuration_ref"):
                need(same(decoded["request_facts"].get(name), body[name]), "CONTROL_SUBJECT_SCOPE")
            def clock_facts(clock):
                need(type(clock) is p.a.TimeBinding, "QUALIFIED_CONTROL_OBSERVATION_TIME")
                p.s.evaluate_time(clock.sample, clock.profile, clock.current, clock.error)
                return dict(sample=wire_ref(clock.sample.sample), profile=wire_ref(clock.profile.profile),
                    validation=wire_ref(clock.sample.validation), error_qualification=wire_ref(clock.error.qualification),
                    process=clock.current.process_id, domain=clock.current.domain_id, ticks_ns=clock.current.ticks_ns,
                    elapsed_ns=clock.error.elapsed_ns, error_ns=clock.error.error_ns)
            need(same(decoded["before"], clock_facts(before)) and same(decoded["after"], clock_facts(after)),
                 "CONTROL_OBSERVATION_BYTES_AND_QUALIFIED_VIEW")
            need((before.current.process_id, before.current.domain_id) == (after.current.process_id, after.current.domain_id)
                 and before.current.ticks_ns <= after.current.ticks_ns, "CONTROL_OBSERVATION_ORDER")
        p._reference(arrangement)
        retained = self.material.view(arrangement)
        need(type(retained) is p.AuthenticatedView and same(retained.reference, arrangement)
             and "IMMUTABLE_RAW_RETENTION" in retained.expectation.obligations
             and same(retained.value, (evidence_class, subject.reference, len(subject.raw), context, scope)),
             "FINITE_CONTROL_RAW_RETENTION_ASSOCIATION")
        p.a._time(retained.clock, not_before=retained.valid_from_us,
                  valid_from=retained.valid_from_us, valid_until=retained.valid_until_us)
        p.a._time(control.clock, not_before=control.valid_from_us,
                  valid_from=control.valid_from_us, valid_until=control.valid_until_us)

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def signed_correspondence(self, body, view):
        # Resolve actual independently interpreted request/decision facts. The
        # constructor association selects a record; it grants no authority.
        # This comparison tuple is private native projection, not wire schema.
        actual = self.material.view(reference(body["context"]["request_facts_ref"]))
        need(type(actual) is p.AuthenticatedView
             and same(actual.reference, reference(body["context"]["request_facts_ref"])),
             "SIGNED_NATIVE_FACTS_REFERENCE")
        # The independent native request/result proof has its own qualified
        # expectation. Its actual interpretation binds the consumer's complete
        # frozen expectation below; it is not another QF of the same subject.
        expected = (body["receipt_role"], body["subject_ref"], view.expectation,
                    body["context"], view.value, body["details"], body["stage"],
                    body["namespace"], body["incarnation_id"], body["configuration_ref"],
                    body["issuer_id"], body["authority_id"], body["provider_id"],
                    (body["request_id"], body["request_ref"], body["valid_from_us"], body["valid_until_us"],
                     body["time_ref"], body["qualification_ref"], body["adoption_ref"]),
                    (view.clock, view.valid_from_us, view.valid_until_us))
        need(same(actual.value, expected), "COMPLETE_SIGNED_NATIVE_CORRESPONDENCE")
        need(body["stage"] == view.expectation.stage, "SIGNED_EXPECTATION_STAGE")
        logical_roles = dict(zip(ROLES[:10], ("package", "preparation", "creation", "execution", "approval", "opening",
            "publication-admission", "cas-admission", "publication-entry", "cas-entry")))
        logical_roles.update(RESULT_PUBLICATION="publication-result", RESULT_CAS="cas-result", READBACK="readback")
        if body["receipt_role"] in logical_roles:
            need(view.expectation.role == logical_roles[body["receipt_role"]], "SIGNED_NATIVE_INTERPRETATION_ROLE")
        need(body["valid_from_us"] <= view.valid_from_us <= view.valid_until_us <= body["valid_until_us"],
             "SIGNED_NATIVE_VALIDITY_BOUNDS")
        p.a._time(actual.clock, not_before=actual.valid_from_us,
                  valid_from=actual.valid_from_us, valid_until=actual.valid_until_us)

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def validate_interpretation(self, body, view, evidence, verifier):
        role, details = body["receipt_role"], body["details"]
        self.signed_correspondence(body, view)
        if role in ROLES[:8]:
            names = ("QualifiedPackageBindings", "QualifiedPreparation", "QualifiedCreation", "QualifiedExecution",
                     "ApprovalView", "QualifiedOpen", "EffectAdmission", "EffectAdmission")
            expected_name = names[ROLES.index(role)]
            need(type(view.value).__name__ == expected_name and details["view_type"] == expected_name,
                 "FROZEN_INTERPRETATION_TYPE")
            need(tuple(details["obligations"]) == view.expectation.obligations, "COMPLETE_OBLIGATION_TUPLE")
        if role in ROLES[:10] + ("RESULT_PUBLICATION", "RESULT_CAS", "READBACK"):
            need(body["predecessor_refs"] == required_predecessors(body, frozen_leaves(view.value, skip=view.reference)),
                 "COMPLETE_FROZEN_REFERENCE_MAPPING")
        need(view.expectation.stage == body["stage"], "INTERPRETATION_STAGE")
        if role in ("ADMISSION_PUBLICATION", "ADMISSION_CAS"):
            matches = [item for item in self.admission_sources if item[0] == role
                       and same(item[1].reference, reference(body["subject_ref"]))]
            need(len(matches) == 1, "MISSING_OR_AMBIGUOUS_ROLE_SPECIFIC_ASBQ_SOURCE")
            _, subject, expectation, sources, designation = matches[0]
            v0 = admission_provenance(role=role, subject=subject, expectation=expectation,
                                      sources=sources, verifier=verifier, designation=designation)
            need(details["view_provenance_ref"] == wire_ref(v0.provenance), "APM_FINAL_P0_IDENTITY_DIGEST")
        # Actual complete typed field, nested proof and context checks remain
        # the independently qualified native interpreter's frozen responsibility.
        p._strict_view(view.value)


class AdmissionDesignation:
    """ASBQ comparison notation only: no new wire field, object or hash domain.

    T, S, X, actual D and expected E0 fields are independently established inputs.
    A designated receipt ID is ordinary preallocated issuance state. `upstream`
    supplies the complete immutable prerequisite closure (record, dependencies).
    No final E0 digest participates in this closure or source-event selection.
    """
    def __init__(self, *, material, trust_ref, subject, request, decision, expectation,
                 role, expected_body, upstream, native_verifier, evidence, association_ref=None):
        need(role in ("ADMISSION_PUBLICATION", "ADMISSION_CAS"), "ADMISSION_ROLE")
        need(isinstance(native_verifier, p.EvidenceVerifier), "INDEPENDENT_NATIVE_VERIFIER")
        self.material, self.trust_ref = material, trust_ref
        self.subject, self.request, self.decision = subject, request, decision
        self.expectation, self.role = expectation, role
        self.expected_body = expected_body
        self.upstream = tuple(upstream)
        self.native_verifier, self.evidence = native_verifier, evidence
        self.association_ref = association_ref
        self._snapshot = capture((subject, request, decision, expectation, expected_body, self.upstream))

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def authoritative_sources(self, copies):
        """Read complete original request/result association via existing verify.

        The tuple below is comparison notation for the independently qualified
        native association, not a receipt, serialization or new evidence class.
        A source list, a copied success flag or a caller's expected_body is not
        evidence of enumeration completeness. The existing independent native
        verifier must establish completeness/current applicability under T.
        """
        need(self.association_ref is not None, "ASBQ_COMPLETENESS_EVIDENCE_REQUIRED")
        association = self.material.view(self.association_ref)
        need(type(association) is p.AuthenticatedView
             and same(association.reference, self.association_ref), "ASBQ_AUTHENTICATED_ASSOCIATION")
        # This is existing qualified native request/result/resolution evidence,
        # with its own independently selected expectation. The target admission
        # expectation is an exact constituent of its interpreted facts below.
        # No new signed association receipt is constructed or required.
        p.a._time(association.clock, not_before=association.valid_from_us,
                  valid_from=association.valid_from_us, valid_until=association.valid_until_us)
        self.material.view(self.trust_ref)
        # Native qualification binds the full event, authorized context/scope,
        # actual decision, established completeness and all completed E0 refs.
        facts = association.value
        need(type(facts) is tuple and len(facts) == 3, "ASBQ_ASSOCIATION_NOT_COMPLETE")
        designation, disposition, completed = facts
        expected = (self.trust_ref, self.subject.reference, self.request.reference,
                    self.decision.reference, self.role, self.expectation,
                    self.expected_body["context"])
        need(same(designation, expected) and disposition == "ESTABLISHED"
             and type(completed) is tuple, "ASBQ_ASSOCIATION_UNKNOWN_OR_INCONSISTENT")
        self.evidence.resolve(association.provenance)
        authoritative = {}
        for ref_ in completed:
            p._reference(ref_)
            key = (ref_.identity, ref_.sha256)
            record = self.evidence.resolve(ref_)
            need(type(record) is p.RetainedEvidence and same(record.reference, ref_)
                 and sha256(record.raw).digest() == ref_.sha256, "ASBQ_COMPLETED_REFERENCE")
            body, _, _, _ = envelope(record)
            need(self.matches_upstream(body, self.subject, self.expectation, self.role),
                 "ASBQ_COMPLETED_ASSOCIATION_MISMATCH")
            if key in authoritative:
                need(authoritative[key].raw == record.raw, "CONFLICTING_COMPLETED_COPY")
            authoritative[key] = record
        supplied = {}
        for record in copies:
            need(type(record) is p.RetainedEvidence, "ASBQ_SOURCE_RECORD")
            key = (record.reference.identity, record.reference.sha256)
            need(key in authoritative and record.raw == authoritative[key].raw,
                 "ASBQ_OMITTED_OR_CONFLICTING_COMPLETED_COPY")
            # Exact raw equality includes signed identifier, context, association
            # and the complete envelope. Only these copies are one logical record.
            supplied[key] = record
        need(set(supplied) == set(authoritative), "ASBQ_INCOMPLETE_CALLER_ENUMERATION")
        need(len(authoritative) == 1, "MISSING_OR_COMPETING_COMPLETED_E0")
        return tuple(authoritative.values())

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def matches_upstream(self, body, subject, expectation, role):
        # Receipt ID is checked after matching the designated actual S/X/D event:
        # another receipt ID does not make a competing E0 invisible.
        if role != self.role or not same(subject.reference, self.subject.reference) or not same(expectation, self.expectation):
            return False
        details = body["details"]
        return (body["receipt_role"] == "VERIFIER_ATTESTATION"
                and details.get("verified_subject_ref") == wire_ref(self.subject.reference)
                and details.get("interpretation_role") == role
                and body["context"] == self.expected_body["context"]
                and body["request_ref"] == wire_ref(self.request.reference)
                and body["subject_ref"] == wire_ref(self.decision.reference))

    @closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def qualified_view(self, record, body, subject, expectation):
        need(capture((self.subject, self.request, self.decision, self.expectation,
                            self.expected_body, self.upstream)) == self._snapshot, "UPSTREAM_INPUT_MUTATION")
        self.material.view(self.trust_ref)
        need(body == self.expected_body, "EXACT_T_AUTHORIZED_DESIGNATION")
        nodes = {(r.reference.identity, r.reference.sha256): (r, tuple(deps)) for r, deps in self.upstream}
        need(len(nodes) == len(self.upstream), "AMBIGUOUS_UPSTREAM_IDENTITY")
        final = (record.reference.identity, record.reference.sha256)
        need(final not in nodes, "FINAL_E0_CANNOT_BE_UPSTREAM")
        visiting, visited = set(), set()
        def visit(key):
            need(key != final and key not in visiting, "RECIPROCAL_HASH_OR_PROVENANCE_CYCLE")
            if key in visited:
                return
            need(key in nodes, "INCOMPLETE_UPSTREAM_CLOSURE")
            raw, dependencies = nodes[key]
            need(self.evidence.resolve(raw.reference).raw == raw.raw
                 and sha256(raw.raw).digest() == raw.reference.sha256, "UPSTREAM_RAW_IDENTITY")
            visiting.add(key)
            for dependency in dependencies:
                visit((dependency.identity, dependency.sha256))
            visiting.remove(key)
            visited.add(key)
        for key in nodes:
            visit(key)
        for required in (self.subject, self.request, self.decision):
            need((required.reference.identity, required.reference.sha256) in visited, "MISSING_S_X_D")
        def required_refs(value):
            if type(value) is dict:
                if set(value) == {"identity", "sha256"}:
                    yield reference(value)
                else:
                    for child in value.values():
                        yield from required_refs(child)
            elif type(value) is list:
                for child in value:
                    yield from required_refs(child)
        roots = {(r.identity, r.sha256) for r in self.material.roots}
        _, _, _, detached = envelope(record)
        for dependency in required_refs((dict(body, subject_custody_ref=detached["subject_custody_ref"]))):
            key = (dependency.identity, dependency.sha256)
            need(key != final and (key in visited or key in roots), "INCOMPLETE_E0_PREREQUISITE_CLOSURE")
        # Actual D is independently interpreted under T. It must bind the
        # complete original request/expectation and real subject facts; equality
        # of receipt labels alone cannot manufacture a qualified EffectAdmission.
        decision = self.material.view(self.decision.reference)
        need(same(decision.expectation, expectation), "ACTUAL_VERIFIER_REQUEST_RESULT_ASSOCIATION")
        view = self.native_verifier.verify(subject, expectation)
        need(type(view) is p.AuthenticatedView and same(view.value, decision.value)
             and same(view.provenance, record.reference), "V0_NATIVE_DECISION_AND_RETAINED_P0")
        return view
