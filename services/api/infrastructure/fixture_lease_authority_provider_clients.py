"""Explicit operational realization behind unchanged frozen provider seams.

Inert composition only until separately adopted, qualified capabilities are
supplied and a caller invokes a fixed operation. No default discovery, startup
hook, connection pool, credential refresh, retry, host/register or recovery API.
"""
from dataclasses import dataclass
from copy import deepcopy
from hashlib import sha256
from threading import Lock

from . import fixture_lease_authority_providers as p
from . import fixture_lease_authority_evidence as e
from . import fixture_lease_authority_transaction_broker as b

FUNCTIONS = {
    "ORIGINAL_ATTEMPT_ADMISSION": "SELECT jous_authority.original_attempt_admission(%s::jsonb)",
    "DISPATCH_CLAIM": "SELECT jous_authority.dispatch_claim(%s::jsonb)",
    "CHECKPOINT_PUBLICATION": "SELECT jous_authority.checkpoint_publication(%s::jsonb)",
    "ACTIVATION_CAS": "SELECT jous_authority.activation_cas(%s::jsonb)",
    "AUTHORITATIVE_READBACK": "SELECT jous_authority.authoritative_readback(%s::jsonb)",
    "READ_ONLY_RESOLUTION": "SELECT jous_authority.read_only_resolution(%s::jsonb)",
    "EVIDENCE_CUSTODY_BINDING": "SELECT jous_authority.custody_binding(%s::jsonb)",
}
CONFIG_FIELDS = (
    "account_id", "region", "db_resource_id", "writer_endpoint", "bucket_resource_ref",
    "namespace", "incarnation_id", "fence_epoch", "engine_build", "parameter_ref",
    "schema_sha256", "functions_sha256", "dependency_lock_sha256", "configuration_ref",
    "selection_ref", "qualification_ref", "adoption_ref", "recovery_policy_ref",
    "database", "schema", "session_profile_ref", "tls_peer_name", "tls_roots_ref",
    "network_ref", "timeout_ms", "retention_profile_ref", "locator_policy_ref",
    "max_single_upload_bytes", "single_request_capacity", "key_size_capacity",
    "tsa_service_ref", "tsa_policy_oid", "tsa_signer_policy_ref", "tsa_status_policy_ref",
    "subscriber_entitlement_ref", "clock_profile_ref", "continuity_policy_ref",
    "actor_bindings", "credential_references")


def validate_configuration(config):
    e.closed(config, CONFIG_FIELDS)
    for name in CONFIG_FIELDS:
        if name.endswith("_ref"):
            e.ref(config[name])
        elif name.endswith("_sha256"):
            e.digest(config[name])
    for name in ("region", "db_resource_id", "writer_endpoint", "namespace", "incarnation_id",
                 "engine_build", "database", "schema", "tls_peer_name", "tsa_policy_oid"):
        e.identifier(config[name])
    e.need(type(config["account_id"]) is str and len(config["account_id"]) == 12
           and config["account_id"].isascii() and config["account_id"].isdigit(), "ACCOUNT_ID")
    e.uint(config["fence_epoch"])
    e.need(type(config["max_single_upload_bytes"]) is int
           and config["max_single_upload_bytes"] == e.MAX_SINGLE_UPLOAD_BYTES, "FROZEN_UPLOAD_BOUND")
    e.need(type(config["single_request_capacity"]) is int
           and config["single_request_capacity"] >= e.MAX_SINGLE_UPLOAD_BYTES, "CAPACITY_QUALIFICATION_FAILED")
    e.need(type(config["key_size_capacity"]) is int and config["key_size_capacity"] > 0, "KEY_CAPACITY")
    e.need(type(config["timeout_ms"]) is int and 0 < config["timeout_ms"] <= (1 << 31) - 1, "BOUNDED_TIMEOUT")
    e.need(config["schema"] == "jous_authority" and config["writer_endpoint"] == config["tls_peer_name"], "FIXED_WRITER_PROFILE")
    actors = config["actor_bindings"]
    e.closed(actors, ("executor", "approver", "verifier", "custodian", "recovery", "broker", "signer", "status"))
    for value in actors.values():
        p._binding(value, value.role, "OPERATIONAL")
    # R4 incompatibility is effective separation, not just different labels.
    incompatible = ("executor", "approver", "verifier", "custodian", "recovery")
    for index, role in enumerate(incompatible):
        for other in incompatible[index + 1:]:
            left, right = actors[role], actors[other]
            e.need(left.principal != right.principal and left.credential_identity != right.credential_identity,
                   "INCOMPATIBLE_AUTHORITY_COLLAPSE")
    e.need(type(config["credential_references"]) is tuple, "EXPLICIT_CREDENTIAL_REFERENCES")
    for value in config["credential_references"]:
        p._reference(value)
    return config


class QualifiedMaterial:
    """Existing verifier + complete retained roots/records, not success flags.

    Each item is (original retained record, exact frozen expectation). The
    supplied verifier is the independently selected native verifier. Every use
    re-resolves original bytes and current status; no cached view grants rights.
    Terminal bootstrap references are supplied independently, never inferred
    from the records they authorize.
    """
    def __init__(self, *, evidence, verifier, records, roots):
        e.need(isinstance(evidence, p.EvidenceClient) and isinstance(verifier, p.EvidenceVerifier), "FROZEN_EVIDENCE_SEAMS")
        e.need(type(roots) is tuple and len(roots) > 0, "EXPLICIT_APPROVED_BOOTSTRAP_REQUIRED")
        self.evidence, self.verifier = evidence, verifier
        self.records, self.roots = tuple(records), roots

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def view(self, reference_):
        matches = [(r, x) for r, x in self.records if e.same(r.reference, reference_)]
        e.need(len(matches) == 1, "MISSING_OR_AMBIGUOUS_AUTHORITY_MATERIAL")
        record, expectation = matches[0]
        actual = self.evidence.resolve(reference_)
        e.need(actual.raw == record.raw and sha256(actual.raw).digest() == reference_.sha256, "AUTHORITY_RAW_IDENTITY")
        for root in self.roots:
            self.evidence.resolve(root)
        view = self.verifier.verify(actual, expectation)
        e.need(type(view) is p.AuthenticatedView and e.same(view.reference, reference_)
               and e.same(view.expectation, expectation), "AUTHORITY_INTERPRETATION_BINDING")
        p.a._time(view.clock, not_before=view.valid_from_us,
                  valid_from=view.valid_from_us, valid_until=view.valid_until_us)
        self.evidence.resolve(view.provenance)
        return view


def validate_material_scope(config, request, caller, material):
    """Only scoped internal broker/custody carriers can append bookkeeping.

    Observation identities remain read-only, including readback receipt storage:
    that storage uses a separately supplied internal broker carrier, never the
    observer's database credentials. Nothing here enters admission or effects.
    """
    b.validate_request(request)
    custody = request["operation"] == "EVIDENCE_CUSTODY_BINDING"
    internal = config["actor_bindings"]["custodian" if custody else "broker"]
    p._binding(internal, internal.role, "OPERATIONAL")
    e.need(type(caller) is b.Caller and e.same(caller.binding, internal)
           and caller.principal == internal.principal
           and caller.credential_identity == internal.credential_identity
           and caller.role not in ("OBSERVER", "RESULT_VERIFIER"), "MATERIAL_INTERNAL_CALLER_SCOPE")
    e.need((request["namespace"], request["incarnation_id"]) ==
           (config["namespace"], config["incarnation_id"])
           and material["namespace"] == request["namespace"]
           and material["incarnation_id"] == request["incarnation_id"]
           and material["request_id"] == request["request_id"], "MATERIAL_RESOURCE_SCOPE")
    record = p.RetainedEvidence(e.reference(material["authentication_ref"]), bytes.fromhex(material["original_raw"]))
    body, _, _, _ = e.envelope(record)
    suffix = "PUBLICATION" if request.get("operation_role") == "CHECKPOINT_PUBLICATION" else "CAS"
    roles = {"ORIGINAL_ATTEMPT_ADMISSION": "ENTRY_" + suffix, "DISPATCH_CLAIM": "CLAIM_" + suffix,
             "CHECKPOINT_PUBLICATION": "RESULT_PUBLICATION", "ACTIVATION_CAS": "RESULT_CAS",
             "AUTHORITATIVE_READBACK": "READBACK", "EVIDENCE_CUSTODY_BINDING":
                 "CUSTODY_RESERVE" if request.get("phase") == "RESERVE" else "CUSTODY_BIND"}
    e.need(body["receipt_role"] == roles.get(request["operation"]) == material["receipt_role"]
           and body["request_id"] == request["request_id"]
           and body["namespace"] == request["namespace"] and body["incarnation_id"] == request["incarnation_id"]
           and body["configuration_ref"] == request["configuration_ref"]
           and body["subject_ref"] == material["subject_ref"] and body["issuer_id"] == material["issuer_id"]
           and record.reference.identity == material["material_id"] == material["evidence_identity"]
           and record.reference.sha256.hex() == material["raw_sha256"], "MATERIAL_SIGNED_SCOPE")


class WriterSessions:
    def __init__(self, *, config, carrier, material):
        self.config = dict(validate_configuration(config))
        self.carrier, self.material = carrier, material
        self._fingerprint = e.capture(config)

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def open(self, request, caller):
        e.need(e.capture(self.config) == self._fingerprint, "CONFIGURATION_MUTATION")
        for name in ("selection_ref", "qualification_ref", "adoption_ref", "continuity_policy_ref"):
            self.material.view(e.reference(self.config[name]))
        # The scoped carrier is the only source of a connection. It is required
        # to use verify-full, the approved CA/peer, explicit credentials and no
        # pool/proxy reconnect/replay. It exposes no printable secret fields.
        connection = self.carrier.connect_writer(self.config, caller)
        return WriterSession(connection, self.config, self.material)

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def append_material(self, request, caller, material):
        """Internal post-COMMIT bookkeeping, not an eighth protected operation."""
        validate_material_scope(self.config, request, caller, material)
        session = self.open(request, caller)
        try:
            session.begin(readonly=False)
            session.append_material(request, material)
            session.commit()
        except Exception:
            raise e.EvidenceFailure("KNOWN_DECISION_MATERIAL_GAP_NO_REPLAY") from None
        finally:
            session.close()


class WriterSession:
    def __init__(self, connection, config, material):
        self.connection, self.config, self.material = connection, config, material
        self._used = False
        self._begun = False

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def begin(self, *, readonly):
        from psycopg import Connection
        e.need(isinstance(self.connection, Connection) and not self._begun, "ONE_EXPLICIT_SESSION")
        info = self.connection.info
        e.need(info.host == self.config["writer_endpoint"] and info.dbname == self.config["database"]
               and self.connection.pgconn.ssl_in_use, "PINNED_TLS_WRITER_REQUIRED")
        # Verify the actual transport certificate/resource/build externally; a
        # copied DB-local adoption row or endpoint string is not sufficient.
        self.material.view(e.reference(self.config["network_ref"]))
        self.connection.autocommit = True
        self.connection.execute("BEGIN READ ONLY" if readonly else "BEGIN")
        self.connection.execute("SELECT set_config('statement_timeout', %s, true)", (str(self.config["timeout_ms"]),))
        self.connection.execute("SELECT set_config('lock_timeout', %s, true)", (str(self.config["timeout_ms"]),))
        self.connection.execute("SELECT set_config('idle_in_transaction_session_timeout', %s, true)",
                                (str(self.config["timeout_ms"]),))
        values = self.connection.execute("SELECT current_setting('fsync'),current_setting('full_page_writes'),"
            "current_setting('synchronous_commit'),pg_is_in_recovery()").fetchone()
        e.need(values == ("on", "on", "on", False), "DURABLE_PRIMARY_SESSION_REQUIRED")
        self._begun = True

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def fixed(self, operation, projection):
        from psycopg.types.json import Jsonb
        e.need(self._begun and not self._used and operation in FUNCTIONS, "FIXED_ONE_INVOCATION")
        self._used = True
        result = self.connection.execute(FUNCTIONS[operation], (Jsonb(projection),)).fetchone()
        e.need(type(result) is tuple and len(result) == 1 and type(result[0]) is dict, "DATABASE_RESPONSE_SHAPE")
        return result[0]

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def commit(self):
        e.need(self._begun and self._used, "NO_EMPTY_OR_REPEATED_COMMIT")
        self.connection.execute("COMMIT")
        self._begun = False

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def append_material(self, request, material):
        from psycopg.types.json import Jsonb
        e.need(self._begun and not self._used, "ONE_APPEND_ONLY_MATERIAL_INVOCATION")
        self._used = True
        self.connection.execute("SELECT jous_authority.append_material(%s::jsonb,%s::jsonb)",
                                (Jsonb(b.database_projection(request)), Jsonb(material))).fetchone()

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def close(self):
        # Closing a failed session is not an effect retry or outcome assertion.
        try:
            self.connection.close()
        except Exception:
            pass


class OneShotAWS:
    """Fixed low-level calls through a qualified no-replay credential carrier.

    The carrier owns explicit secure signing/TLS transport. No SDK convenience
    client, credential refresh, transfer manager, redirect or retry middleware
    is constructed here. Its selected botocore build/protocol behavior is part
    of the independently qualified configuration, not inferred from this type.
    """
    def __init__(self, *, carrier, material, qualification_ref, service):
        e.need(service in ("s3", "kms"), "FIXED_AWS_SERVICE")
        self.carrier, self.material, self.qualification_ref = carrier, material, qualification_ref
        self.service = service

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def _call(self, operation, request):
        self.material.view(self.qualification_ref)
        try:
            return self.carrier.invoke_once(self.service, operation, request)
        except Exception:
            raise e.EvidenceFailure("AWS_BOUNDARY_UNCONFIRMED_NO_REPLAY") from None

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def put_object(self, **request):
        e.need(self.service == "s3", "S3_ONLY")
        e.closed(request, ("Bucket", "Key", "Body", "ContentLength", "ChecksumSHA256", "IfNoneMatch",
                           "ObjectLockMode", "ObjectLockRetainUntilDate", "ExpectedBucketOwner"))
        e.need(type(request["Body"]) is bytes and len(request["Body"]) <= e.MAX_SINGLE_UPLOAD_BYTES
               and request["ContentLength"] == len(request["Body"])
               and request["IfNoneMatch"] == "*" and request["ObjectLockMode"] == "COMPLIANCE", "SINGLE_CONDITIONAL_COMPLIANCE_PUT")
        return self._call("PutObject", request)

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def get_object(self, **request):
        e.need(self.service == "s3", "S3_ONLY")
        e.closed(request, ("Bucket", "Key", "VersionId", "ExpectedBucketOwner"))
        e.need(type(request["VersionId"]) is str and request["VersionId"] not in ("", "null"), "EXACT_VERSION_ONLY")
        return self._call("GetObject", request)

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def sign(self, **request):
        e.need(self.service == "kms", "KMS_ONLY")
        e.closed(request, ("KeyId", "Message", "MessageType", "SigningAlgorithm"))
        e.arn(request["KeyId"])
        e.need(request["MessageType"] == "DIGEST" and request["SigningAlgorithm"] == e.ALGORITHM
               and type(request["Message"]) is bytes and len(request["Message"]) == 32, "EXACT_KMS_PROFILE")
        return self._call("Sign", request)


class QualificationClient(p.QualificationClient):
    """Consume actual independently produced qualification; never issue Q."""
    def __init__(self, *, raw, binding, source):
        self.raw, self.binding, self.source = raw, binding, source

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def qualify(self, role, context):
        e.need(role in p._OBLIGATIONS and role in ("package", "preparation", "creation", "execution",
               "approval", "opening", "publication-admission", "cas-admission"), "FIXED_QUALIFICATION_ROLE")
        before = e.capture(context)
        # source is the selected independent QualificationClient, not a broker
        # signing capability or a callback manufacturing requested success.
        e.need(isinstance(self.source, p.QualificationClient) and self.source is not self, "INDEPENDENT_QUALIFICATION_CLIENT")
        reference_ = self.source.qualify(role, context)
        stage = "UPSTREAM_ONLY" if role in ("package", "creation") else "Q" if role == "approval" else "CURRENT"
        view = self.raw.authenticate(reference_, self.binding, role, context, stage, p._OBLIGATIONS[role])
        e.need(e.capture(context) == before and e.same(view.reference, reference_), "QUALIFICATION_CONTEXT_MUTATION")
        return reference_


class ProtectedClient(p.ProtectedClient):
    """Exact fixed broker translation; no success type is synthesized here.

    plans is immutable preallocated request material authenticated by raw at each
    use. Requests bind complete frozen arguments, fresh qualification, original
    operation and request identities. No IDs are generated after uncertainty.
    """
    def __init__(self, *, broker, caller, plans, raw, binding):
        e.need(type(broker) is b.BoundedBroker and type(caller) is b.Caller, "BOUNDED_BROKER_REQUIRED")
        self.broker, self.caller, self.plans, self.raw, self.binding = broker, caller, plans, raw, binding
        self._entries = {}
        self._lock = Lock()

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def _request(self, operation, context, anchor):
        request, material_ref = self.plans.request(operation, context, anchor)
        b.validate_request(request)
        e.need(request["operation"] == operation, "FIXED_OPERATION_TRANSLATION")
        view = self.raw.authenticate(material_ref, self.binding, "view.authorization", context,
                                      "CURRENT", ("EXACT_ROLE_CONTEXT_ISSUER", "TRANSITIVE_STAGE_RESTRICTIONS"))
        # A frozen nested proof returns its original Ref, never a newly invented
        # dictionary interpretation. The broker independently compares the full
        # logical input binding and current qualification before DB entry.
        e.need(e.same(view.value, material_ref), "AUTHENTICATED_REQUEST_FACTS_REQUIRED")
        return dict(request)

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY", preserve_known=True)
    def enter(self, role, context, admission):
        e.need(role in ("publication", "cas"), "PROTECTED_ROLE")
        req = self._request("ORIGINAL_ATTEMPT_ADMISSION", context, admission)
        e.need(req["qualification_ref"] == e.wire_ref(admission), "ORIGINAL_APM_QUALIFIED_ADMISSION")
        response = self.broker.admission(req, self.caller)
        entry = response["admission_evidence_ref"]
        with self._lock:
            e.need(entry not in self._entries, "DUPLICATE_ENTRY")
            self._entries[entry] = (role, e.capture(context), req, admission, response)
        return entry

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY", preserve_known=True)
    def _effect(self, operation, role, context, entry):
        with self._lock:
            prior = self._entries.pop(entry, None)
        e.need(prior is not None and prior[:2] == (role, e.capture(context)), "LIVE_ENTRY_CONTEXT_REQUIRED")
        claim = self._request("DISPATCH_CLAIM", context, prior[3])
        claim.update(admission_evidence_ref=e.wire_ref(entry), admission_id=prior[2]["admission_id"],
                     expected_fence_value=prior[4]["fence_value"])
        claimed = self.broker.claim(claim, self.caller)
        request = self._request(operation, context, prior[3])
        request.update(admission_evidence_ref=e.wire_ref(entry), admission_id=prior[2]["admission_id"],
                       dispatch_claim_id=claimed["dispatch_claim_id"], claim_fence_value=claimed["claim_fence_value"],
                       claim_commit_evidence_ref=e.wire_ref(claimed["claim_commit_evidence_ref"]))
        response = self.broker.effect(request, self.caller)
        return response["publication_receipt_ref" if operation == "CHECKPOINT_PUBLICATION" else "activation_receipt_ref"]

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY", preserve_known=True)
    def publish_checkpoint(self, snapshot, approval, authorization, entry):
        return self._effect("CHECKPOINT_PUBLICATION", "publication", (snapshot, approval, authorization), entry)

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY", preserve_known=True)
    def activate_absent(self, payload, publication, absence_history, authorization, entry):
        return self._effect("ACTIVATION_CAS", "cas", (payload, publication, absence_history, authorization), entry)

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def readback(self, result):
        e.need(type(result) is p.a.ActivationResult and result.status == "CONFIRMED", "CONFIRMED_ORIGINAL_REQUIRED")
        response = self.broker.observe(self._request("AUTHORITATIVE_READBACK", (result,), result.evidence), self.caller)
        return response["readback_evidence_ref"]


class RequestPlans:
    """Preallocated immutable call material; no synthesized IDs or effects."""
    def __init__(self, entries):
        # Entries: fixed operation, original frozen context, anchor Ref,
        # complete logical request, existing independently verifiable facts Ref.
        self.entries = tuple(entries)
        self._before = e.capture(self.entries)

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def request(self, operation, context, anchor):
        e.need(e.capture(self.entries) == self._before, "REQUEST_PLAN_MUTATION")
        found = [(r, proof) for op, original, ref, r, proof in self.entries
                 if op == operation and e.same(context, original) and e.same(ref, anchor)]
        e.need(len(found) == 1, "MISSING_OR_AMBIGUOUS_FIXED_REQUEST")
        return found[0]


class BrokerPolicy:
    """All comparisons consume independent original evidence, never flags.

    Native control/input-binding records are interpreted by QualifiedMaterial's
    existing independently qualified EvidenceVerifier. Logical field tuples are
    in-memory comparisons of realization sections 5/7, not a new wire schema,
    canonical object, receipt role or provider method.
    """
    def __init__(self, *, config, material, clock):
        self.config = dict(validate_configuration(config))
        self.material, self.clock = material, clock
        self._before = e.capture(self.config)

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def _proved(self, reference_, expected):
        view = self.material.view(p._service_reference(reference_))
        e.need(e.same(view.value, expected), "INDEPENDENT_NATIVE_FACT_COMPARISON")
        return view

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def verify_request(self, request, caller, broker_principal):
        b.validate_request(request)
        e.need(e.capture(self.config) == self._before, "CONFIGURATION_MUTATION")
        for name, configured in (("namespace", "namespace"), ("incarnation_id", "incarnation_id"),
                                  ("configuration_ref", "configuration_ref"), ("adoption_ref", "adoption_ref"),
                                  ("expected_fence_epoch", "fence_epoch")):
            e.need(e.same(request[name], self.config[configured]), "WRONG_INCARNATION")
        actors = self.config["actor_bindings"]
        e.need(broker_principal == actors["broker"].principal, "ACTUAL_BROKER_PRINCIPAL")
        e.need(any(e.same(caller.binding, actor) for actor in actors.values()), "UNADOPTED_CALLER")
        resource_facts = tuple((name, self.config[name]) for name in (
            "account_id", "region", "db_resource_id", "writer_endpoint", "engine_build", "parameter_ref",
            "schema_sha256", "functions_sha256", "dependency_lock_sha256", "configuration_ref",
            "namespace", "incarnation_id", "fence_epoch"))
        self._proved(e.reference(self.config["adoption_ref"]), resource_facts)
        # Externally supplied current continuity proves the actual writer, not
        # a restored copy's internal adoption row. No automatic re-adoption.
        self._proved(e.reference(self.config["continuity_policy_ref"]), resource_facts)
        if "current_time" in request:
            current = self.clock.current()
            e.need((request["current_time"].current.process_id, request["current_time"].current.domain_id) ==
                   (current.current.process_id, current.current.domain_id)
                   and request["current_time"].current.ticks_ns <= current.current.ticks_ns,
                   "CURRENT_QUALIFIED_TIME")
            self.material.view(e.reference(request["time_evidence_ref"]))
            qualification = self.material.view(e.reference(request["qualification_ref"]))
            p.a._time(current, not_before=qualification.valid_from_us,
                      valid_from=qualification.valid_from_us, valid_until=qualification.valid_until_us)
        self.material.view(e.reference(request["authorization_ref"]))
        if "input_binding_ref" in request:
            # Exact immutable input binding, in the contract's prescribed group
            # order; no hashes/serialization are created for this comparison.
            source = self.material.view(e.reference(request["input_binding_ref"]))
            expected = source.value
            e.need(type(expected) is tuple and all(type(pair) is tuple and len(pair) == 2 for pair in expected),
                   "COMPLETE_ORIGINAL_INPUT_FACTS")
            names = [name for name, _ in expected]
            e.need(len(names) == len(set(names)), "AMBIGUOUS_INPUT_FACTS")
            required_groups = ("Authority", "Lifecycle", "Original", "Snapshot", "Approval")
            required_names = [name for group in required_groups for name, _ in b.GROUPS[group]
                              if name != "input_binding_ref"]
            required_names += ["authorization_ref", "expected_state", "expected_generation"]
            if request["operation_role"] == "ACTIVATION_CAS":
                required_names += [name for group in ("Payload", "Publication") for name, _ in b.GROUPS[group]]
            e.need(names == required_names, "EXACT_INPUT_BINDING_COVERAGE")
            for name, value in expected:
                if name in request:
                    e.need(e.same(value, request[name]), "IMMUTABLE_ORIGINAL_INPUT_MISMATCH")
            if "Snapshot" in required_groups and "E_bytes" in request:
                snapshot = p.a.PackageSnapshot(request["E_bytes"], request["P_bytes"], request["S0_bytes"], request["C0_bytes"])
                accepted = p.a._validate_snapshot(snapshot)
                ceremony = accepted.evidence
                e.need((ceremony.register_id, ceremony.issuer_generation, ceremony.activation_id,
                         ceremony.activation_command_id, ceremony.approval_id) ==
                       (request["register_id"], request["generation"], request["activation_id"], request["K"], request["J"]),
                       "EXACT_FROZEN_LIFECYCLE")
        if request["operation"] in ("AUTHORITATIVE_READBACK", "READ_ONLY_RESOLUTION"):
            self.material.view(e.reference(request["observation_authorization_ref"]))
            self.material.view(e.reference(request["observation_scope_ref"]))
        if request["operation"] == "EVIDENCE_CUSTODY_BINDING" and request["phase"] == "BIND":
            version = self.material.view(e.reference(request["custody_authentication_ref"])).value
            e.schema(version, e.CV)
            e.need(version["evidence_ref"] == {"identity": request["evidence_identity"], "sha256": request["raw_sha256"].hex()},
                   "EXACT_CUSTODY_SUBJECT")
            for name in ("custody_attempt_id", "raw_size", "bucket_resource_ref", "object_key", "version_id",
                         "retention_mode", "observed_retention_until", "retention_requirement_ref", "upload_response_ref",
                         "exact_version_readback_ref", "retention_evidence_ref"):
                e.need(e.same(version[name], request[name]), "AUTHENTICATED_VERSION_BINDING")

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def qualified_observation(self, request):
        current = self.clock.current()
        p.s.evaluate_time(current.sample, current.profile, current.current, current.error)
        return current

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def verify_commit_bracket(self, before, after, request, result):
        left = p.s.evaluate_time(before.sample, before.profile, before.current, before.error)
        right = p.s.evaluate_time(after.sample, after.profile, after.current, after.error)
        e.need((before.current.process_id, before.current.domain_id) ==
               (after.current.process_id, after.current.domain_id)
               and before.current.ticks_ns <= after.current.ticks_ns
               and left.interval.lower_us <= right.interval.upper_us, "QUALIFIED_COMMIT_COMPLETION_ORDER")

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def verify_response(self, request, result):
        e.need(type(result) is dict and type(result.get("disposition")) is str, "DATABASE_RESPONSE")
        disposition = result["disposition"]
        if disposition == "REJECTED":
            e.closed(result, ("disposition", "reason", "prior_decision_ref"))
            e.need(result["reason"] in e.REASONS, "CLOSED_REJECTION_REASON")
            if result["prior_decision_ref"] is not None:
                e.ref(result["prior_decision_ref"])
            return
        fields = {
            "ADMITTED": ("operation_id", "admission_id", "input_binding_ref", "state_version", "fence_value", "admission_decision_ref"),
            "CLAIMED": ("operation_id", "admission_id", "dispatch_claim_id", "broker_principal_id", "claim_fence_value", "claim_decision_ref"),
            "CHECKPOINT_PUBLISHED": ("operation_id", "admission_id", "dispatch_claim_id", "state_version", "fence_value", "decision_ref", "lifecycle_binding", "input_binding_ref"),
            "ACTIVATED": ("operation_id", "admission_id", "dispatch_claim_id", "state_version", "fence_value", "decision_ref", "lifecycle_binding", "input_binding_ref"),
            "OBSERVED": ("protected_state", "original_decision", "publication_decision_ref",
                         "activation_decision_ref", "publication_receipt_ref", "activation_receipt_ref"),
            "RESOLVED": ("outputs",),
            "CUSTODY_RESERVED": ("reservation_decision_ref", "custody_attempt_id", "evidence_identity", "object_key"),
            "CUSTODY_BOUND": ("locator", "binding_decision_ref", "custody_authentication_ref"),
        }
        e.need(disposition in fields, "UNKNOWN_DATABASE_DISPOSITION")
        e.closed(result, ("disposition",) + fields[disposition])
        for name in ("operation_id", "admission_id", "dispatch_claim_id", "input_binding_ref", "custody_attempt_id", "evidence_identity", "object_key"):
            if name in result:
                e.need(e.same(result[name], request[name]), "DATABASE_RESPONSE_ORIGINAL_BINDING")
        for name in ("state_version", "fence_value", "claim_fence_value"):
            if name in result:
                e.uint(result[name])
        if disposition == "RESOLVED":
            e.closed(result["outputs"], request["permitted_outputs"])
        if disposition == "OBSERVED":
            for field in ("publication_decision_ref", "activation_decision_ref", "publication_receipt_ref", "activation_receipt_ref"):
                e.ref(result[field])
                e.need(result[field] == request[field], "READBACK_RETAINED_DECISION_BINDING")
            state, original = result["protected_state"], result["original_decision"]
            e.need(state["state"] == "ACTIVE" and type(state["generation"]) is int and state["generation"] == 1
                   and original["decision"] == "ACTIVATED" and original["operation_id"] == request["operation_id"]
                   and original["payload_sha256"] == "\\x" + request["payload_sha256"].hex(), "AUTHORITATIVE_READBACK_FACTS")

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def match_original(self, admitted, acknowledged, request):
        for name in ("namespace", "incarnation_id", "operation_id", "admission_id", "operation_role",
                     "input_binding_ref", "register_id", "generation", "activation_id", "K", "J", "host_ref", "scope_ref"):
            e.need(e.same(admitted[name], request[name]), "LIVE_ORIGINAL_BINDING")
        if acknowledged["disposition"] == "CLAIMED":
            for name in ("dispatch_claim_id", "claim_fence_value"):
                e.need(e.same(acknowledged[name], request[name]), "LIVE_CLAIM_BINDING")

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def match_custody(self, reserved, request):
        for group in ("Authority", "CustodySubject", "CustodyPlan"):
            for name, _ in b.GROUPS[group]:
                e.need(e.same(reserved[name], request[name]), "LIVE_CUSTODY_BINDING")


class ReceiptIssuer:
    """Only actual issuer-owned results; governance/independent Q are excluded."""
    BROKER_ROLES = ("ENTRY_PUBLICATION", "ENTRY_CAS", "CLAIM_PUBLICATION", "CLAIM_CAS",
                    "RESULT_PUBLICATION", "RESULT_CAS", "READBACK")

    def __init__(self, *, kms, evidence, verifier, material, recipes, permitted_roles, material_sink=None):
        e.need(type(permitted_roles) is tuple and permitted_roles
               and set(permitted_roles) <= set(self.BROKER_ROLES + ("CUSTODY_RESERVE", "CUSTODY_VERSION", "CUSTODY_BIND")),
               "ISSUER_ROLE_SEPARATION")
        self.kms, self.evidence, self.verifier, self.material = kms, evidence, verifier, material
        self.recipes, self.permitted_roles = recipes, permitted_roles
        self.material_sink = material_sink
        self._issued = set()
        self._lock = Lock()

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def record_acknowledgement(self, request, result, before, after):
        return self.recipes.retain_control_observation(request, result, before, after)

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def confirm(self, request, result):
        body, subject_custody = self.recipes.actual_decision_body(request, result)
        e.need(body["receipt_role"] in self.permitted_roles, "ISSUER_CANNOT_MANUFACTURE_OTHER_AUTHORITY")
        raw = e.producer_bytes(body, e.BODY_FIELDS)
        e.validate_body(raw)
        # Independently authenticate all native facts, not a projected request.
        self.recipes.validate_actual_decision(body, request, result, self.material)
        identity = body["receipt_id"]
        with self._lock:
            e.need(identity not in self._issued, "NO_RESIGN_OR_RECEIPT_REISSUE")
            self._issued.add(identity)
        signature = e.kms_sign(raw, self.kms)
        record = e.assemble(raw, signature, subject_custody)
        e.need(self.evidence.retain(record) == record.reference, "RECEIPT_RETENTION_REFERENCE")
        self.verifier.authenticate(record, body["receipt_role"], body["context"])
        e.need(self.material_sink is not None, "POST_COMMIT_MATERIAL_RETENTION_REQUIRED")
        custody = request["operation"] == "EVIDENCE_CUSTODY_BINDING"
        readback = request["operation"] == "AUTHORITATIVE_READBACK"
        sequence = (0 if request.get("phase") == "RESERVE" else 1) if custody else {
            "ORIGINAL_ATTEMPT_ADMISSION": 0, "DISPATCH_CLAIM": 1,
            "CHECKPOINT_PUBLICATION": 2, "ACTIVATION_CAS": 2, "AUTHORITATIVE_READBACK": None}[request["operation"]]
        row = dict(namespace=request["namespace"], incarnation_id=request["incarnation_id"],
            material_id=body["receipt_id"], evidence_identity=record.reference.identity,
            parent_kind="READBACK" if readback else "DECISION",
            subject_kind=None if readback else "CUSTODY" if custody else "OPERATION",
            subject_id=None if readback else request["evidence_identity"] if custody else request["operation_id"],
            sequence=sequence, activation_operation_id=request["operation_id"] if readback else None,
            request_id=request["request_id"], receipt_role=body["receipt_role"], original_raw=record.raw.hex(),
            raw_sha256=record.reference.sha256.hex(), issuer_id=body["issuer_id"],
            authentication_ref=e.wire_ref(record.reference), subject_ref=body["subject_ref"])
        self.material_sink(request, row)
        self.recipes.completed(request, record)
        return record.reference


class ReceiptRecipes:
    """Closed body construction from actual established decisions.

    templates supply independently approved issuer/root/context material and
    preallocated receipt IDs. They do not supply a decision. Raw control
    observations use the already-authorized finite bookkeeping arrangement,
    whose EvidenceClient must not recursively require these returned receipts.
    """
    def __init__(self, *, templates, controls, control_expectations, control_verifier):
        e.need(isinstance(controls, p.EvidenceClient) and isinstance(control_verifier, p.EvidenceVerifier),
               "QUALIFIED_FINITE_CONTROL_EVIDENCE_REQUIRED")
        self.templates, self.controls = tuple(templates), controls
        self.control_expectations, self.control_verifier = tuple(control_expectations), control_verifier
        self._before = e.capture((self.templates, self.control_expectations))
        self._acks = {}
        self._observations = {}
        self._completed = {}

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def completed(self, request, record):
        key = (request["namespace"], request["incarnation_id"], request.get("operation_id", request.get("evidence_identity")),
               request["operation"], request.get("phase"))
        e.need(key not in self._completed, "NO_RECEIPT_REISSUANCE_FOR_COMPLETED_EVENT")
        self._completed[key] = record.reference

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def retain_control_observation(self, request, result, before, after):
        import json
        def clock_facts(clock):
            return dict(sample=e.wire_ref(clock.sample.sample), profile=e.wire_ref(clock.profile.profile),
                validation=e.wire_ref(clock.sample.validation), error_qualification=e.wire_ref(clock.error.qualification),
                process=clock.current.process_id, domain=clock.current.domain_id, ticks_ns=clock.current.ticks_ns,
                elapsed_ns=clock.error.elapsed_ns, error_ns=clock.error.error_ns)
        # Actual native bookkeeping, not a 25th signed receipt or a replacement
        # for original request bytes. Byte fields are represented only by their
        # actual complete digests/lengths; no credential value is recorded.
        request_facts = {name: ({"sha256": sha256(value).hexdigest(), "size": len(value)}
                                if type(value) is bytes else value)
                         for name, value in b.database_projection(request).items()}
        for name, value in request.items():
            if type(value) is bytes:
                request_facts[name] = {"sha256": sha256(value).hexdigest(), "size": len(value)}
        raw = json.dumps(dict(request_facts=request_facts, actual_result=result,
                              before=clock_facts(before), after=clock_facts(after)),
                         ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        record = p.RetainedEvidence(p.s.EvidenceReference(sha256(raw).hexdigest(), sha256(raw).digest()), raw)
        e.need(self.controls.retain(record) == record.reference
               and self.controls.resolve(record.reference).raw == raw, "FINITE_CONTROL_RETENTION")
        matches = [expectation for identity, expectation in self.control_expectations if identity == request["request_id"]]
        e.need(len(matches) == 1, "CONTROL_EXPECTATION_ASSOCIATION")
        observed = self.control_verifier.verify(record, matches[0])
        e.need(type(observed) is p.AuthenticatedView and e.same(observed.reference, record.reference)
               and e.same(observed.expectation, matches[0]), "QUALIFIED_CONTROL_ACKNOWLEDGEMENT")
        p.a._time(observed.clock, not_before=observed.valid_from_us,
                  valid_from=observed.valid_from_us, valid_until=observed.valid_until_us)
        e.need(e.same(observed.value, (request["request_id"], result, before, after)), "ACTUAL_COMMIT_OBSERVATION_FACTS")
        self._acks[request["request_id"]] = record.reference
        self._observations[request["request_id"]] = (before, after)
        return record.reference

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def actual_decision_body(self, request, result):
        e.need(e.capture((self.templates, self.control_expectations)) == self._before, "RECEIPT_TEMPLATE_MUTATION")
        found = [(body, custody) for identity, body, custody in self.templates if identity == request["request_id"]]
        e.need(len(found) == 1, "RECEIPT_TEMPLATE_ASSOCIATION")
        body, custody = deepcopy(found[0])
        op = request["operation"]
        role = request.get("operation_role")
        suffix = "PUBLICATION" if role == "CHECKPOINT_PUBLICATION" else "CAS"
        expected = {"ORIGINAL_ATTEMPT_ADMISSION": "ENTRY_" + suffix,
                    "DISPATCH_CLAIM": "CLAIM_" + suffix,
                    "CHECKPOINT_PUBLICATION": "RESULT_PUBLICATION", "ACTIVATION_CAS": "RESULT_CAS",
                    "AUTHORITATIVE_READBACK": "READBACK", "EVIDENCE_CUSTODY_BINDING":
                        "CUSTODY_RESERVE" if request.get("phase") == "RESERVE" else "CUSTODY_BIND"}[op]
        e.need(body["receipt_role"] == expected and body["request_id"] == request["request_id"], "ACTUAL_RECEIPT_ROLE_REQUEST")
        expected_disposition = {"ORIGINAL_ATTEMPT_ADMISSION": "ADMITTED", "DISPATCH_CLAIM": "CLAIMED",
            "CHECKPOINT_PUBLICATION": "CHECKPOINT_PUBLISHED", "ACTIVATION_CAS": "ACTIVATED",
            "AUTHORITATIVE_READBACK": "OBSERVED", "EVIDENCE_CUSTODY_BINDING":
                "CUSTODY_RESERVED" if request.get("phase") == "RESERVE" else "CUSTODY_BOUND"}[op]
        e.need(result["disposition"] == expected_disposition, "NO_PROJECTED_POSITIVE_DECISION")
        details = body["details"]
        acknowledgement = self._acks.get(request["request_id"])
        e.need(acknowledgement is not None, "DEFINITE_RETAINED_COMMIT_OBSERVATION_REQUIRED")
        if op == "ORIGINAL_ATTEMPT_ADMISSION":
            body["subject_ref"] = result["admission_decision_ref"]
            details.update(admission_ref=request["qualification_ref"], operation_id=result["operation_id"], state="DURABLY_ENTERED_ORIGINAL",
                           decision_ref=result["admission_decision_ref"], state_version=result["state_version"],
                           fence_value=result["fence_value"])
        elif op == "DISPATCH_CLAIM":
            body["subject_ref"] = result["claim_decision_ref"]
            details.update({name: request[name] for name in ("admission_id", "operation_id", "operation_role", "input_binding_ref")})
            details.update(admission_ref=request["admission_evidence_ref"], broker_principal_id=result["broker_principal_id"],
                dispatch_claim_id=result["dispatch_claim_id"], claim_decision="CLAIMED",
                claim_decision_ref=result["claim_decision_ref"], claim_commit_evidence_ref=e.wire_ref(acknowledgement),
                claim_fence_value=result["claim_fence_value"])
        elif op in ("CHECKPOINT_PUBLICATION", "ACTIVATION_CAS"):
            body["subject_ref"] = result["decision_ref"]
            details.update(checkpoint=request["C0_ref"], package=request["P_ref"], approval=request["Q_ref"],
                decision_ref=result["decision_ref"], state_version=result["state_version"], status="CONFIRMED")
            claim_key = (request["namespace"], request["incarnation_id"], request["operation_id"], "DISPATCH_CLAIM", None)
            e.need(claim_key in self._completed, "RETAINED_ORIGINAL_CLAIM_RECEIPT_REQUIRED")
            details["claim_ref"] = e.wire_ref(self._completed[claim_key])
            snapshot = p.a.PackageSnapshot(request["E_bytes"], request["P_bytes"], request["S0_bytes"], request["C0_bytes"])
            details["host_identity"] = p.a._validate_snapshot(snapshot).evidence.host.identity
            if op == "CHECKPOINT_PUBLICATION":
                details["operation"] = request["operation_id"]
            else:
                details.update(command_id=request["K"], payload_sha256=request["payload_sha256"].hex(),
                    register_id=request["register_id"], generation=1, activation_id=request["activation_id"])
        elif op == "AUTHORITATIVE_READBACK":
            body["subject_ref"] = e.wire_ref(acknowledgement)
            details.update(original_ref=request["activation_receipt_ref"], activation_decision_ref=request["activation_decision_ref"],
                state="LINEARIZABLE_CURRENT_AFTER_ORIGINAL", state_version=result["protected_state"]["state_version"],
                fence_value=result["protected_state"]["fence_value"], ordering_ref=e.wire_ref(acknowledgement),
                result_ref=e.wire_ref(acknowledgement), observation_time_ref=e.wire_ref(acknowledgement))
        else:
            decision_name = "reservation_decision_ref" if request["phase"] == "RESERVE" else "binding_decision_ref"
            body["subject_ref"] = result[decision_name]
            details.update(custody_attempt_id=request["custody_attempt_id"],
                evidence_ref={"identity": request["evidence_identity"], "sha256": request["raw_sha256"].hex()},
                raw_size=request["raw_size"], bucket_resource_ref=request["bucket_resource_ref"],
                object_key=request["object_key"], custody_role=request["custody_role"], retention_mode="COMPLIANCE")
            if request["phase"] == "RESERVE":
                details.update(required_retention_until=request["required_retention_until"],
                    retention_requirement_ref=request["retention_requirement_ref"], reservation_decision_ref=result[decision_name], state="RESERVED")
            else:
                details.update(version_id=request["version_id"], observed_retention_until=request["observed_retention_until"],
                    retention_evidence_ref=request["retention_evidence_ref"], version_observation_ref=request["custody_authentication_ref"],
                    binding_decision_ref=result[decision_name], state="BOUND")
        body["outcome"], body["rejection_reason"] = "ESTABLISHED", "NONE"
        # These issuer-owned EN/CL/PB/AC/RB/CR/CB interpretations introduce no
        # additional frozen leaves beyond their Context/details expansions.
        # Never carry stale/future placeholder references out of a template.
        body["predecessor_refs"] = e.required_predecessors(body)
        return body, custody

    @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
    def validate_actual_decision(self, body, request, result, material):
        e.validate_body(e.producer_bytes(body, e.BODY_FIELDS))
        # The native decision and separately retained acknowledgement must both
        # resolve/authenticate. Broker issuance never supplies independent Q or
        # result verification, and cannot make missing evidence authoritative.
        self.controls.resolve(self._acks[request["request_id"]])
        material.view(e.reference(body["subject_ref"]))
        material.view(e.reference(body["request_ref"]))
        for field in ("configuration_ref", "adoption_ref", "key_binding_ref", "key_status_ref", "qualification_ref", "time_ref"):
            material.view(e.reference(body[field]))
