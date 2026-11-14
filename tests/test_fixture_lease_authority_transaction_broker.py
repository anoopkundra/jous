"""Source-only bounded broker regression tests; no live DB or DDL execution."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import importlib
import unittest
from unittest.mock import Mock

import test_fixture_lease_activation as frozen

b = importlib.import_module(frozen.PACKAGE + ".fixture_lease_authority_transaction_broker")
e = b.e


class SimulatedBroker(b.BoundedBroker):
    """Only transport-free latch tests; not operational qualification."""
    def __init__(self):
        receipts = Mock()
        receipts.confirm.side_effect = lambda request, result: frozen.ref(request["request_id"])
        super().__init__(sessions=Mock(), policy=Mock(), receipts=receipts, principal="broker")
        self.calls, self.fault = [], None

    def _transaction(self, request, caller):
        self.calls.append(request["operation"])
        if self.fault:
            raise self.fault
        self._acknowledgements[request["request_id"]] = frozen.ref("actual-test-ack")
        return {"disposition": {"ORIGINAL_ATTEMPT_ADMISSION": "ADMITTED", "DISPATCH_CLAIM": "CLAIMED",
            "CHECKPOINT_PUBLICATION": "CHECKPOINT_PUBLISHED", "ACTIVATION_CAS": "ACTIVATED"}[request["operation"]]}

    def _response(self, request, result, **evidence):
        # This fake isolates latch sequencing; it deliberately does not model
        # a qualified SQL response or certify the real response translator.
        return dict(result, **evidence)


def request(operation):
    return dict(schema_version=1, namespace="ns", incarnation_id="inc", operation_id="original", request_id="fixed-request",
                operation=operation, broker_principal_id="broker",
                admission_evidence_ref=e.wire_ref(frozen.ref("fixed-request")),
                claim_commit_evidence_ref=e.wire_ref(frozen.ref("actual-test-ack")))


class BrokerTests(unittest.TestCase):
    def admitted_claim(self):
        broker = SimulatedBroker()
        broker.admission(request("ORIGINAL_ATTEMPT_ADMISSION"), None)
        broker.claim(request("DISPATCH_CLAIM"), None)
        return broker

    def test_claim_is_separate_before_one_effect(self):
        broker = self.admitted_claim()
        broker.effect(request("CHECKPOINT_PUBLICATION"), None)
        self.assertEqual(broker.calls, ["ORIGINAL_ATTEMPT_ADMISSION", "DISPATCH_CLAIM", "CHECKPOINT_PUBLICATION"])
        with self.assertRaises(e.EvidenceFailure):
            broker.effect(request("CHECKPOINT_PUBLICATION"), None)
        self.assertEqual(len(broker.calls), 3)

    def test_effect_failure_consumes_latch(self):
        broker = self.admitted_claim()
        broker.fault = e.EvidenceFailure("UNKNOWN")
        with self.assertRaises(e.EvidenceFailure):
            broker.effect(request("CHECKPOINT_PUBLICATION"), None)
        broker.fault = None
        with self.assertRaises(e.EvidenceFailure):
            broker.effect(request("CHECKPOINT_PUBLICATION"), None)
        self.assertEqual(broker.calls.count("CHECKPOINT_PUBLICATION"), 1)

    def test_claim_failure_and_restart_do_not_reconstruct_dispatch(self):
        broker = SimulatedBroker()
        broker.admission(request("ORIGINAL_ATTEMPT_ADMISSION"), None)
        broker.fault = e.EvidenceFailure("UNKNOWN")
        with self.assertRaises(e.EvidenceFailure):
            broker.claim(request("DISPATCH_CLAIM"), None)
        with self.assertRaises(e.EvidenceFailure):
            broker.effect(request("CHECKPOINT_PUBLICATION"), None)
        replacement = SimulatedBroker()
        with self.assertRaises(e.EvidenceFailure):
            replacement.effect(request("CHECKPOINT_PUBLICATION"), None)

    def test_concurrent_workers_enter_effect_at_most_once(self):
        broker = self.admitted_claim()
        def invoke(_):
            try:
                broker.effect(request("CHECKPOINT_PUBLICATION"), None)
                return True
            except e.EvidenceFailure:
                return False
        with ThreadPoolExecutor(max_workers=8) as workers:
            self.assertEqual(sum(workers.map(invoke, range(16))), 1)
        self.assertEqual(broker.calls.count("CHECKPOINT_PUBLICATION"), 1)

    def test_unknown_admission_cannot_be_repeated_locally(self):
        broker = SimulatedBroker()
        broker.fault = e.EvidenceFailure("UNKNOWN")
        with self.assertRaises(e.EvidenceFailure):
            broker.admission(request("ORIGINAL_ATTEMPT_ADMISSION"), None)
        broker.fault = None
        with self.assertRaises(e.EvidenceFailure):
            broker.admission(request("ORIGINAL_ATTEMPT_ADMISSION"), None)
        self.assertEqual(len(broker.calls), 1)

    def test_closed_request_discriminator_and_schema(self):
        for value in ({}, {"operation": "REPLAY"}, {"operation": "READ_ONLY_RESOLUTION", "target_kind": "ARBITRARY"}):
            with self.assertRaises(e.EvidenceFailure):
                b.validate_request(value)
        self.assertEqual(len(b.OPERATIONS), 7)
        self.assertEqual(len(b.CATEGORIES), 5)

    def test_sql_contains_disjoint_fks_and_no_restore_eligibility_api(self):
        # Artifact checks only; these do not substitute for later qualified
        # PostgreSQL constraint, privilege, concurrency and fault certification.
        sql = (Path(__file__).resolve().parents[1] / "services/api/infrastructure/fixture_lease_authority_schema.sql").read_text()
        for table in ("incarnation", "slot", "lifecycle", "admission", "claim", "publication", "activation", "history", "material", "locator"):
            self.assertIn("CREATE TABLE jous_authority." + table, sql)
        self.assertIn("previous_sequence=sequence-1", sql)
        self.assertIn("NOLOGIN NOINHERIT", sql)
        self.assertIn("REVOKE ALL ON ALL FUNCTIONS", sql)
        self.assertNotIn("ON CONFLICT DO UPDATE", sql)
        self.assertNotIn("CREATE OR REPLACE", sql)


class ConcreteReadbackTests(unittest.TestCase):
    def fixture(self):
        from copy import deepcopy
        from test_fixture_lease_authority_evidence import AdmissionMappingTests, ref
        _, _, _, _, view, _, _ = AdmissionMappingTests().source("ADMISSION_CAS")
        request = {name: ref(name) if name.endswith("_ref") else "value" for name in b.READBACK_BINDINGS}
        request.update(schema_version=1, operation="AUTHORITATIVE_READBACK", request_id="observation",
            generation=1, operation_role="ACTIVATION_CAS", payload_sha256=b"p" * 32, minimum_state_version=2)
        lifecycle = {name: request[name] for name, _ in b.GROUPS["Lifecycle"]}
        original = {name: request[name] for name in ("namespace", "incarnation_id", "operation_id",
            "operation_role", "input_binding_ref", "publication_operation_id")}
        original.update(original_binding=deepcopy(request), lifecycle_binding=deepcopy(lifecycle), decision="ACTIVATED",
                        payload_sha256="\\x" + request["payload_sha256"].hex())
        native = {name: request[name] for name in ("publication_decision_ref", "activation_decision_ref",
                                                  "publication_receipt_ref", "activation_receipt_ref")}
        native.update(disposition="OBSERVED", original_decision=original,
                      protected_state=dict(state="ACTIVE", generation=1, state_version=2, fence_value=3,
                                           lifecycle_binding=deepcopy(lifecycle)))
        clock = view.clock
        facts = (e.capture(request), e.capture(native), clock, clock, frozen.ref("qualified-actual-ack"))
        return request, native, facts

    def test_concrete_policy_then_exact_external_success_shape(self):
        clients = importlib.import_module(frozen.PACKAGE + ".fixture_lease_authority_provider_clients")
        request, native, facts = self.fixture()
        # No config/connection construction; this validator reads native facts.
        policy = object.__new__(clients.BrokerPolicy)
        policy.verify_response(request, native)
        response = b.readback_response(request, native, facts, frozen.ref("readback-receipt"))
        self.assertEqual(set(response), set(b.READBACK_FIELDS))
        self.assertEqual(response["protected_state"], "ACTIVE")
        self.assertEqual(response["state_version"], 2)
        self.assertEqual(response["fence_value"], 3)
        self.assertIs(response["observation_time"], facts[3])
        self.assertEqual(response["ordering_ref"], facts[4])
        self.assertNotIn("original_decision", response)
        b.validate_readback_response(response)

    def test_native_jsonb_ref_key_order_does_not_replace_reference_identity(self):
        request, native, facts = self.fixture()
        for name in ("publication_decision_ref", "activation_decision_ref", "publication_receipt_ref", "activation_receipt_ref"):
            native[name] = dict(reversed(tuple(native[name].items())))
        native["original_decision"]["input_binding_ref"] = dict(reversed(tuple(request["input_binding_ref"].items())))
        rebound = (facts[0], e.capture(native)) + facts[2:]
        response = b.readback_response(request, native, rebound, frozen.ref("readback"))
        self.assertEqual(response["input_binding_ref"], request["input_binding_ref"])
        response["input_binding_ref"] = dict(response["input_binding_ref"], sha256="0" * 64)
        self.assertFalse(e.same(response["input_binding_ref"], request["input_binding_ref"]))

    def test_missing_original_or_result_binding_rejects(self):
        for field in ("P_ref", "Q_ref", "C0_ref", "host_ref", "activation_decision_ref", "publication_decision_ref"):
            request, native, facts = self.fixture()
            if field in native:
                del native[field]
            else:
                del native["original_decision"]["original_binding"][field]
            rebound = (facts[0], e.capture(native)) + facts[2:]
            with self.assertRaises(e.EvidenceFailure):
                b.readback_response(request, native, rebound, frozen.ref("readback"))

    def test_acknowledgement_mismatch_and_native_projection_are_not_authority(self):
        request, native, facts = self.fixture()
        native["protected_state"]["fence_value"] = 99
        with self.assertRaises(e.EvidenceFailure):
            b.readback_response(request, native, facts, frozen.ref("readback"))
        request, native, facts = self.fixture()
        request["activation_decision_ref"] = e.wire_ref(frozen.ref("unrelated-decision"))
        rebound = (e.capture(request),) + facts[1:]
        with self.assertRaises(e.EvidenceFailure):
            b.readback_response(request, native, rebound, frozen.ref("readback"))
        with self.assertRaises(e.EvidenceFailure):
            b.validate_readback_response(native)

    def test_final_external_response_is_closed_and_requires_time_ordering(self):
        for field in ("observation_time", "ordering_ref", "payload_sha256", "input_binding_ref", "protected_state"):
            request, native, facts = self.fixture()
            response = b.readback_response(request, native, facts, frozen.ref("readback"))
            del response[field]
            with self.assertRaises(e.EvidenceFailure):
                b.validate_readback_response(response)


class MaterialSqlSourceTests(unittest.TestCase):
    def test_observer_has_no_append_grant_and_internal_parent_checks_exist(self):
        sql = (Path(__file__).resolve().parents[1] /
               "services/api/infrastructure/fixture_lease_authority_schema.sql").read_text()
        declaration = "CREATE FUNCTION jous_authority.append_material(r jsonb,m jsonb)"
        function = sql.split(declaration, 1)[1].split("END $$;", 1)[0]
        grant = "GRANT EXECUTE ON FUNCTION jous_authority.append_material(jsonb,jsonb) TO jous_broker,jous_custody;"
        self.assertIn(grant, sql)
        self.assertNotIn("append_material(jsonb,jsonb) TO jous_broker,jous_custody,jous_observer", sql)
        for required in ("pg_has_role(session_user,'jous_observer','MEMBER')",
                         "MATERIAL_CUSTODY_SCOPE", "MATERIAL_BROKER_SCOPE", "MATERIAL_CALLER_SCOPE",
                         "MATERIAL_SIGNED_SCOPE", "MATERIAL_ROLE", "MATERIAL_DECISION_PARENT",
                         "MATERIAL_READBACK_PARENT", "INTO STRICT h", "parent_request->>'principal_id'",
                         "parent_request->>'credential_identity'", "parent_request->'authorization_ref'"):
            self.assertIn(required, function)
        self.assertEqual(function.count("INSERT INTO"), 1)
        self.assertIn("INSERT INTO jous_authority.material", function)
        for protected in ("admission", "claim", "activation", "publication", "slot", "history"):
            self.assertNotIn("INSERT INTO jous_authority." + protected, function)
            self.assertNotIn("UPDATE jous_authority." + protected, function)
        self.assertNotIn("DELETE FROM", function)
        # Artifact assertions are not PostgreSQL execution/certification.


class PublicBrokerDispositionTests(unittest.TestCase):
    """Real public broker/transaction path over deterministic offline sessions.

    No SQL/provider code is executed. These fixtures stand for already-qualified
    sessions and clocks, and do not override _transaction or public handlers.
    """
    def scenario(self, *, prepared=True):
        from test_fixture_lease_authority_evidence import AdmissionMappingTests, ref
        _, _, _, _, prior, _, _ = AdmissionMappingTests().source("ADMISSION_PUBLICATION")
        class CarrierFailure(RuntimeError): pass
        class State:
            mode = None
            def __init__(self):
                self.fixed_calls, self.commit_calls, self.acknowledged_commits = [], [], []
            def fail(self, stage):
                if self.mode == stage:
                    try:
                        raise ValueError("SECRET-CREDENTIAL-INNER")
                    except ValueError:
                        raise CarrierFailure("SECRET-SQL-PROVIDER-TSA-DIAGNOSTIC")
        state = State()
        def make(operation, identity):
            request_ = dict(operation=operation, operation_role="CHECKPOINT_PUBLICATION")
            for name, rule in b.request_spec(request_):
                if name in request_: continue
                request_[name] = (b"original-" + name.encode() if rule == "BYTES" else prior.clock if rule == "TIME"
                    else ref(name) if rule == "R" else "value" if rule in ("ID", "TEXT")
                    else 0 if rule in ("U", "UTC") else rule[0] if type(rule) is tuple else rule)
            request_.update(namespace="ns", incarnation_id="inc", operation_id="original", request_id=identity,
                            logical_role="EXECUTOR", principal_id="executor", credential_identity="scoped-carrier")
            for prefix in ("E", "S0", "C0", "P", "Q"):
                if prefix + "_bytes" in request_:
                    request_[prefix + "_ref"] = dict(identity=prefix,
                        sha256=b.sha256(request_[prefix + "_bytes"]).hexdigest())
            return request_
        class Policy:
            def verify_request(self, request_, caller, broker_principal):
                e.need((request_["namespace"], request_["incarnation_id"], broker_principal) == ("ns", "inc", "broker"))
            def qualified_observation(self, request_):
                if request_["operation"] == "CHECKPOINT_PUBLICATION" and state.acknowledged_commits.count("CHECKPOINT_PUBLICATION"):
                    state.fail("post-commit-time")
                return prior.clock
            def verify_commit_bracket(self, before, after, request_, result):
                e.need(before is prior.clock and after is prior.clock)
            def verify_response(self, request_, result):
                e.need(result["disposition"] == {"ORIGINAL_ATTEMPT_ADMISSION": "ADMITTED",
                    "DISPATCH_CLAIM": "CLAIMED", "CHECKPOINT_PUBLICATION": "CHECKPOINT_PUBLISHED"}[request_["operation"]])
            def match_original(self, admitted, result, request_):
                for name in ("namespace", "incarnation_id", "operation_id", "operation_role", "input_binding_ref", "admission_id"):
                    e.need(e.same(admitted[name], request_[name]), "EXACT_FIXTURE_ORIGINAL_BINDING")
        class Session:
            def __init__(self, request_): self.request = request_
            def begin(self, *, readonly): e.need(readonly is False)
            def fixed(self, operation, projection):
                state.fixed_calls.append(operation)
                if operation == "CHECKPOINT_PUBLICATION":
                    state.fail("before-commit")
                    if state.mode == "forged-known-text":
                        raise e.EvidenceFailure("KNOWN_DB_DECISION_EVIDENCE_GAP_NO_REPLAY")
                    if state.mode == "forged-known-marker":
                        raise e._KnownDecisionGap()
                common = dict(operation_id=projection["operation_id"], admission_id=projection["admission_id"])
                if operation == "ORIGINAL_ATTEMPT_ADMISSION":
                    return dict(common, disposition="ADMITTED", input_binding_ref=projection["input_binding_ref"],
                                state_version=0, fence_value=0, admission_decision_ref=ref("actual-admission"))
                if operation == "DISPATCH_CLAIM":
                    return dict(common, disposition="CLAIMED", dispatch_claim_id=projection["dispatch_claim_id"],
                                broker_principal_id="broker", claim_fence_value=1, claim_decision_ref=ref("actual-claim"))
                return dict(common, disposition="CHECKPOINT_PUBLISHED", dispatch_claim_id=projection["dispatch_claim_id"],
                            input_binding_ref=projection["input_binding_ref"], lifecycle_binding={},
                            state_version=1, fence_value=1, decision_ref=ref("actual-publication"))
            def commit(self):
                state.commit_calls.append(self.request["operation"])
                if self.request["operation"] == "CHECKPOINT_PUBLICATION": state.fail("ambiguous-commit")
                state.acknowledged_commits.append(self.request["operation"])
            def close(self):
                if self.request["operation"] == "CHECKPOINT_PUBLICATION": state.fail("close-after-commit")
        class Sessions:
            def open(self, request_, caller): return Session(request_)
        class Receipts:
            def record_acknowledgement(self, request_, result, before, after):
                if request_["operation"] == "CHECKPOINT_PUBLICATION": state.fail("acknowledgement")
                return frozen.ref("ack-" + request_["request_id"])
            def confirm(self, request_, result):
                # The default external transport wrapper must sanitize even a
                # known-looking carrier failure; the public broker's already
                # established commit state supplies the known disposition.
                @e.closed_boundary("UNKNOWN_BOUNDARY_FAILURE_NO_REPLAY")
                def retain():
                    if request_["operation"] == "CHECKPOINT_PUBLICATION": state.fail("receipt-retention")
                    return frozen.ref("receipt-" + request_["request_id"])
                return retain()
        binding = b.p.ProviderBinding("executor", "offline-qualified-session", "executor", "scoped-carrier",
            "authority", "issuer", "ns", "OPERATIONAL", frozen.ref("q"), frozen.ref("s"), frozen.ref("a"))
        caller = b.Caller(binding.principal, binding.credential_identity, "EXECUTOR", binding)
        broker = b.BoundedBroker(sessions=Sessions(), policy=Policy(), receipts=Receipts(), principal="broker")
        if not prepared:
            return broker, caller, make, state, CarrierFailure
        admitted = broker.admission(make("ORIGINAL_ATTEMPT_ADMISSION", "admit"), caller)
        claim_request = make("DISPATCH_CLAIM", "claim")
        claim_request.update(broker_principal_id="broker", admission_id=admitted["admission_id"],
                             admission_evidence_ref=e.wire_ref(admitted["admission_evidence_ref"]))
        claimed = broker.claim(claim_request, caller)
        effect = make("CHECKPOINT_PUBLICATION", "effect")
        effect.update(admission_id=admitted["admission_id"], admission_evidence_ref=e.wire_ref(admitted["admission_evidence_ref"]),
                      dispatch_claim_id=claimed["dispatch_claim_id"], claim_fence_value=claimed["claim_fence_value"],
                      claim_commit_evidence_ref=e.wire_ref(claimed["claim_commit_evidence_ref"]))
        return broker, caller, effect, state, CarrierFailure

    def assert_sanitized(self, failure, broker, carrier_type):
        self.assertNotIsInstance(failure, carrier_type)
        self.assertIsNone(failure.__context__)
        self.assertIsNone(failure.__cause__)
        self.assertNotIn("SECRET", str(failure))
        self.assertEqual(vars(failure), {})
        self.assertTrue(all(type(arg) is str for arg in failure.args))
        # Internal retained broker state has no error/exception slot or object.
        self.assertFalse(any(isinstance(value, BaseException) for value in vars(broker).values()))
        self.assertFalse(any("error" in name or "exception" in name for name in vars(broker)))
        for live in broker._live.values():
            self.assertFalse(any(isinstance(value, BaseException) for value in vars(live).values()))

    def test_known_commit_evidence_failure_survives_public_wrappers_without_carrier_chain(self):
        for stage in ("post-commit-time", "acknowledgement", "receipt-retention", "close-after-commit"):
            broker, caller, request_, state, carrier_type = self.scenario()
            state.mode = stage
            with self.assertRaises(e.EvidenceFailure) as failed:
                broker.effect(request_, caller)
            self.assertEqual(str(failed.exception), "KNOWN_DB_DECISION_EVIDENCE_GAP_NO_REPLAY")
            self.assertEqual(state.acknowledged_commits.count("CHECKPOINT_PUBLICATION"), 1)
            self.assert_sanitized(failed.exception, broker, carrier_type)
            with self.assertRaises(e.EvidenceFailure): broker.effect(request_, caller)
            self.assertEqual(state.fixed_calls.count("CHECKPOINT_PUBLICATION"), 1)
            self.assertEqual(state.commit_calls.count("CHECKPOINT_PUBLICATION"), 1)

    def test_ambiguous_commit_and_untrusted_known_looking_errors_stay_unknown(self):
        for stage in ("before-commit", "ambiguous-commit", "forged-known-text", "forged-known-marker"):
            broker, caller, request_, state, carrier_type = self.scenario()
            state.mode = stage
            with self.assertRaises(e.EvidenceFailure) as failed:
                broker.effect(request_, caller)
            self.assertEqual(str(failed.exception), "UNKNOWN_BROKER_OUTCOME_STOP_NO_RETRY")
            self.assertEqual(state.acknowledged_commits.count("CHECKPOINT_PUBLICATION"), 0)
            self.assert_sanitized(failed.exception, broker, carrier_type)
            with self.assertRaises(e.EvidenceFailure): broker.effect(request_, caller)
            self.assertEqual(state.fixed_calls.count("CHECKPOINT_PUBLICATION"), 1)


    def test_public_protected_adapter_preserves_known_broker_failure(self):
        clients = importlib.import_module(frozen.PACKAGE + ".fixture_lease_authority_provider_clients")
        broker, caller, make, state, carrier_type = self.scenario(prepared=False)
        context = ("snapshot-fixture", "approval-fixture", "authorization-fixture")
        admit = make("ORIGINAL_ATTEMPT_ADMISSION", "admit")
        admission = e.reference(admit["qualification_ref"])
        claim = make("DISPATCH_CLAIM", "claim")
        claim["broker_principal_id"] = "broker"
        effect = make("CHECKPOINT_PUBLICATION", "effect")
        entries = tuple((request_["operation"], context, admission, request_, frozen.ref("proof-" + request_["request_id"]))
                        for request_ in (admit, claim, effect))
        class Raw:
            def authenticate(self, proof, binding, role, context_, stage, obligations):
                # Existing independently qualified frozen proof seam, reduced
                # here to the exact reference needed by this adapter fixture.
                class Proven: value = proof
                return Proven()
        client = clients.ProtectedClient(broker=broker, caller=caller, plans=clients.RequestPlans(entries),
                                                 raw=Raw(), binding=caller.binding)
        entry = client.enter("publication", context, admission)
        state.mode = "receipt-retention"
        with self.assertRaises(e.EvidenceFailure) as failed:
            client.publish_checkpoint(*context, entry)
        self.assertEqual(str(failed.exception), "KNOWN_DB_DECISION_EVIDENCE_GAP_NO_REPLAY")
        self.assert_sanitized(failed.exception, broker, carrier_type)
        with self.assertRaises(e.EvidenceFailure): client.publish_checkpoint(*context, entry)
        self.assertEqual(state.fixed_calls.count("CHECKPOINT_PUBLICATION"), 1)
