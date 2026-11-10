"""Offline provider conformance. Synthetic issuers are NEVER operational trust.

Reuses frozen IL6 synthetic vectors/storage helpers without changing their bytes.
The external test authority authenticates records from an issued registry, not
from caller expectations; its shared fenced history survives adapter replacement.
No production transport, credentials, external store or authority is selected.
"""
from dataclasses import fields, is_dataclass, replace
from hashlib import sha256
from enum import StrEnum
import importlib
import socket
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import test_fixture_lease_activation as frozen

a, s = frozen.a, frozen.v
m = importlib.import_module(frozen.PACKAGE + ".fixture_lease_authority_providers")


def reference(identity, raw):
    return s.EvidenceReference(identity, sha256(raw).digest())


def binding(role, principal=None):
    return m.ProviderBinding(role, "synthetic-" + role, principal or "synthetic-" + role,
        "synthetic-credential-" + role, "synthetic-authority-" + role,
        "synthetic-issuer-" + role, "synthetic-namespace", "SYNTHETIC",
        frozen.ref(role + "-qualification"), frozen.ref(role + "-selection"),
        frozen.ref(role + "-adoption"))


class SyntheticEvidence(m.EvidenceClient):
    def __init__(self):
        self.records = {}
        self.calls = []
        self.fault = None

    def retain(self, record):
        self.calls.append(("retain", record.reference))
        if self.fault == "retain":
            raise OSError("synthetic uncertain retention")
        prior = self.records.setdefault(record.reference.identity, record)
        if prior != record:
            raise a.ActivationRejected("SYNTHETIC_IMMUTABLE_ID_COLLISION")
        return record.reference

    def resolve(self, ref):
        self.calls.append(("resolve", ref))
        record = self.records[ref.identity]
        if self.fault == "corrupt":
            return replace(record, raw=record.raw + b"corrupt")
        return record


class SyntheticVerifier(m.EvidenceVerifier):
    def __init__(self, authority):
        self.authority = authority
        self.fault = None
        self.calls = []
        self.forbidden_upstream = set()

    def verify(self, record, expectation):
        self.calls.append(expectation)
        key = (record.reference, a._capture(expectation.binding), expectation.role,
               a._capture(expectation.context), expectation.stage)
        signed = self.authority.issued[key]
        if expectation.stage == "UPSTREAM_ONLY" and record.reference.identity in self.forbidden_upstream:
            raise a.ActivationRejected("SYNTHETIC_TRANSITIVE_DOWNSTREAM_DEPENDENCY")
        if record != self.authority.store.records[record.reference.identity]:
            raise a.ActivationRejected("SYNTHETIC_AUTHENTICATION_FAILED")
        if expectation.obligations != signed.expectation.obligations:
            raise a.ActivationRejected("SYNTHETIC_OBLIGATIONS_NOT_CERTIFIED")
        if self.fault == "boolean":
            return True
        if self.fault == "binding":
            return replace(signed, expectation=replace(signed.expectation,
                           binding=replace(signed.expectation.binding, issuer="wrong-issuer")))
        if self.fault == "role":
            return replace(signed, expectation=replace(signed.expectation, role="wrong-operation"))
        if self.fault == "context":
            return replace(signed, expectation=replace(signed.expectation, context=("wrong-context",)))
        if self.fault == "digest":
            return replace(signed, reference=frozen.ref("wrong-hash"))
        if self.fault == "revoked":
            raise a.ActivationRejected("SYNTHETIC_REVOKED_OR_UNKNOWN")
        if self.fault == "rotated-without-continuity":
            return replace(signed, expectation=replace(signed.expectation,
                binding=replace(signed.expectation.binding, credential_identity="synthetic-new-unqualified-credential")))
        if self.fault == "stale":
            return replace(signed, valid_until_us=-1)
        if self.fault == "future":
            return replace(signed, valid_from_us=1)
        if self.fault == "bool-time":
            return replace(signed, valid_until_us=True)
        return signed


class SyntheticAuthority(m.QualificationClient, m.ProtectedClient):
    def __init__(self, f):
        self.f = f
        self.store = SyntheticEvidence()
        self.issued = {}
        self.counter = 0
        self.lock = threading.RLock()
        self.history = {}  # external to all composition/adapter instances
        self.consumed = set()
        self.checkpoints = {}
        self.active = {}
        self.tombstones = set()
        self.effects = []
        self.fault = None
        self.bad_value = None
        self.preparation_clock = None
        self.qbinding = binding("qualification")
        self.pbinding = binding("protected")
        self.vbinding = binding("result-verifier")
        self.verifier = SyntheticVerifier(self)
        for participant in (self.qbinding, self.pbinding, self.vbinding, binding("retention")):
            for name in ("qualification", "selection", "adoption"):
                ref = getattr(participant, name)
                self.put(ref, self.proof_bytes(ref))
        for opaque in f.q.bindings.opaque:
            self.put(s.EvidenceReference(opaque.reference.identity,
                                        bytes.fromhex(opaque.reference.sha256)), opaque.raw)
        for ref, raw in ((a.content_reference(f.p), f.snapshot.package),
                         (a.content_reference(f.e), f.snapshot.ceremony),
                         (f.e.initial_state, f.snapshot.state), (f.p.checkpoint, f.snapshot.checkpoint)):
            self.put(s.EvidenceReference(ref.identity, bytes.fromhex(ref.sha256)), raw)
        self.raw = m.RawEvidence(self.store, self.verifier,
                                 binding=binding("retention"), kind="SYNTHETIC")
        self.qualifier = m.QualificationProvider(self, self.raw, binding=self.qbinding,
            verifier_binding=self.vbinding, kind="SYNTHETIC")
        self.protected = self.new_protected()

    def new_protected(self):
        return m.ProtectedAuthorityProvider(self, self.qualifier, self.raw,
                                           binding=self.pbinding, kind="SYNTHETIC")

    def put(self, ref, raw):
        self.store.retain(m.RetainedEvidence(ref, raw))

    def proof_bytes(self, ref):
        if ref.identity in self.store.records:
            return self.store.records[ref.identity].raw
        raw = ("synthetic:" + ref.identity).encode()
        assert sha256(raw).digest() == ref.sha256, ref.identity
        return raw

    def attest(self, ref, value, who, role, context, stage="CURRENT", clock=None):
        clock = clock or self.f.clock
        provenance = frozen.ref("synthetic-retention-and-authentication-provenance")
        self.put(provenance, self.proof_bytes(provenance))
        obligations = m._OBLIGATIONS.get(role, ("EXACT_ROLE_CONTEXT_ISSUER", "TRANSITIVE_STAGE_RESTRICTIONS"))
        expectation = m.EvidenceExpectation(who, binding("retention"), role, context, stage,
                                            m._COMMON + obligations)
        view = m.AuthenticatedView(ref, expectation, value, clock, 0, 1000000, provenance)
        self.issued[(ref, a._capture(who), role, a._capture(context), stage)] = view

    def proofs(self, value, who, context, prefix="view", stage="CURRENT"):
        if type(value) is a.OpaqueEvidence:
            ref = s.EvidenceReference(value.reference.identity, bytes.fromhex(value.reference.sha256))
            self.put(ref, value.raw)
            self.attest(ref, value.reference, who, value.role, context, stage)
            self.proofs(value.qualification, who, context, prefix + ".qualification", stage)
        elif type(value) in (a.Reference, s.EvidenceReference):
            ref = (s.EvidenceReference(value.identity, bytes.fromhex(value.sha256))
                   if type(value) is a.Reference else value)
            self.put(ref, self.proof_bytes(ref))
            self.attest(ref, value, who, prefix, context, stage)
        elif type(value) is tuple:
            for index, item in enumerate(value):
                self.proofs(item, who, context, prefix + "." + str(index), stage)
        elif is_dataclass(value):
            for field in fields(value):
                if field.name not in ("request", "snapshot"):
                    self.proofs(getattr(value, field.name), who, context, prefix + "." + field.name, stage)

    def issue(self, value, who, role, context, stage="CURRENT", clock=None, ref=None):
        with self.lock:
            if ref is None:
                self.counter += 1
                raw = ("synthetic opaque external acceptance %d" % self.counter).encode()
                ref = reference("synthetic-record-%d" % self.counter, raw)
                self.put(ref, raw)
            self.proofs(value, who, context, stage=stage)
            self.attest(ref, value, who, role, context, stage, clock)
            return ref

    def qualify(self, role, context):
        f = self.f
        stage, who, clock = "CURRENT", self.qbinding, f.clock
        if role == "package":
            value, stage = f.q.package(context[0]), "UPSTREAM_ONLY"
        elif role == "preparation":
            value = f.q.preparation(context[0])
            clock = self.preparation_clock or clock
        elif role == "creation":
            value, stage = f.q.creation(*context), "UPSTREAM_ONLY"
        elif role == "execution":
            value = f.q.execution(context[0])
        elif role == "approval":
            value, stage, clock = context[1], "Q", context[2]
        elif role == "opening":
            value = f.q.opening(context[0])
            self.proofs(context[0].independent_result_verification, self.vbinding, context,
                        stage="INDEPENDENT_RESULT_VERIFICATION")
        elif role in ("publication-admission", "cas-admission"):
            who = self.pbinding
            value = m.EffectAdmission(f.snapshot, f.approval, context[-1],
                frozen.ref("fresh-absence"), f.clock,
                "synthetic-publication-operation" if role == "publication-admission" else f.e.activation_command_id,
                "AUTHORITATIVE_ABSENT", 0, "ORIGINAL_UNATTEMPTED_K")
            if f.e.register_id in self.active or f.e.register_id in self.tombstones:
                value = replace(value, presence="ACTIVE_OR_HISTORICAL")
        else:
            raise AssertionError(role)
        if self.bad_value is not None:
            bad_role, change = self.bad_value
            if role == bad_role:
                value = change(value)
        if role in ("opening", "execution"):
            clock = value.fresh_time if role == "opening" else value.clock
        return self.issue(value, who, role, context, stage, clock)

    def enter(self, role, context, admission):
        with self.lock:
            # Namespace+register+generation+K+role fencing, not adapter memory.
            key = (self.pbinding.namespace, self.f.e.register_id, 1, self.f.e.activation_command_id, role)
            if key in self.history:
                raise a.ActivationRejected("SYNTHETIC_PRIOR_OR_UNRESOLVED_ORIGINAL")
            self.history[key] = ("ENTERED", a._capture(context))
            if self.fault == "entry":
                raise OSError("synthetic durable-entry uncertainty")
            operation = "synthetic-publication-operation" if role == "publication" else self.f.e.activation_command_id
            value = m.EnteredOperation(admission, operation, "DURABLY_ENTERED_ORIGINAL")
            if self.bad_value and self.bad_value[0] == role + "-entry":
                value = self.bad_value[1](value)
            return self.issue(value, self.pbinding, role + "-entry", context)

    def consume(self, role, entry):
        with self.lock:
            if entry in self.consumed:
                raise a.ActivationRejected("SYNTHETIC_ENTRY_REPLAY")
            self.consumed.add(entry)
            self.effects.append(role)
            if self.fault == role:
                raise TimeoutError("synthetic possible acceptance UNKNOWN")

    def result_ref(self):
        self.counter += 1
        raw = ("synthetic protected raw response %d" % self.counter).encode()
        ref = reference("synthetic-effect-%d" % self.counter, raw)
        self.put(ref, raw)
        return ref

    def publish_checkpoint(self, snapshot, approval, authorization, entry):
        self.consume("publication", entry)
        ref = self.result_ref()
        result = a.CheckpointResult("synthetic-publication-operation", self.f.p.checkpoint,
            a.content_reference(self.f.p), approval.evidence.reference, self.f.e.host.identity,
            "CONFIRMED", ref)
        if self.bad_value and self.bad_value[0] == "publication-result":
            result = self.bad_value[1](result)
        self.issue(result, self.pbinding, "publication-result", (snapshot, approval, authorization), ref=ref)
        self.checkpoints[self.f.e.register_id] = result
        if self.fault == "after-publication":
            raise TimeoutError("synthetic lost response after durable checkpoint acceptance")
        return ref

    def activate_absent(self, payload, publication, absence_history, authorization, entry):
        self.consume("cas", entry)
        with self.lock:
            if self.f.e.register_id in self.active or self.f.e.register_id in self.tombstones:
                raise a.ActivationRejected("SYNTHETIC_EXPECTED_ABSENT_MISMATCH")
            if self.checkpoints.get(self.f.e.register_id) != publication:
                raise a.ActivationRejected("SYNTHETIC_PROTECTED_CHECKPOINT_NOT_PRESENT")
        ref = self.result_ref()
        result = a.ActivationResult(self.f.e.activation_command_id, sha256(payload).digest(),
            a.content_reference(self.f.p), self.f.p.checkpoint, self.f.approval.evidence.reference,
            self.f.e.register_id, 1, self.f.e.activation_id, self.f.e.host.identity, "CONFIRMED", ref)
        if self.bad_value and self.bad_value[0] == "cas-result":
            result = self.bad_value[1](result)
        self.issue(result, self.pbinding, "cas-result",
                   (payload, publication, absence_history, authorization), ref=ref)
        self.active[self.f.e.register_id] = result
        self.tombstones.add(self.f.e.register_id)
        if self.fault == "after-cas":
            raise TimeoutError("synthetic lost response after durable ABSENT CAS")
        return ref

    def readback(self, result):
        self.effects.append("readback")
        if self.fault == "readback":
            raise TimeoutError("synthetic unknown readback")
        # Authoritative external state is read independently; never echo input.
        stored = self.active.get(result.register_id)
        if stored != result:
            raise a.ActivationRejected("SYNTHETIC_AUTHORITATIVE_READBACK_MISMATCH")
        ref = self.result_ref()
        observed = m.ReadbackView(replace(stored, evidence=ref), stored,
            frozen.ref("synthetic-linearizable-ordering"), "LINEARIZABLE_CURRENT_AFTER_ORIGINAL")
        if self.bad_value and self.bad_value[0] == "readback":
            observed = self.bad_value[1](observed)
        self.issue(observed, self.pbinding, "readback", (result,), ref=ref)
        return ref


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.generator = frozen.fixture()
        self.addCleanup(self.generator.close)
        self.f = next(self.generator)
        # Disposable synthetic preparation ONLY, never an operational register.
        self.receipt = frozen.prepared(self.f)
        self.authority = SyntheticAuthority(self.f)
        self.q = self.authority.qualifier
        self.protected = self.authority.protected
        self.authorization = frozen.ref("execution-authorization")

    def publication(self):
        return self.protected.publish_checkpoint(self.f.snapshot, self.f.approval, self.authorization)

    def cas(self, publication=None):
        publication = publication or self.publication()
        accepted = a.validate_genesis_package(self.f.snapshot, self.q.package(self.f.snapshot))
        payload = a.canonical_bytes(a.activation_payload(accepted, self.f.approval, self.f.clock, self.q))
        return self.protected.activate_absent(payload, publication, frozen.ref("fresh-absence"), self.authorization)

    def test_all_qualification_seams(self):
        self.assertIs(type(self.q.package(self.f.snapshot)), a.QualifiedPackageBindings)
        self.assertIs(type(self.q.preparation(self.f.request)), a.QualifiedPreparation)
        self.assertIs(type(self.q.creation(self.f.request, self.receipt.native_identity,
                        self.receipt.state, self.receipt.database_sha256)), a.QualifiedCreation)
        request = frozen.execution(self.f, self.receipt)
        self.assertEqual(self.q.execution(request).request, request)
        self.assertEqual(self.authority.effects, [])

    def test_distinct_effects_exact_results_and_nonactivation(self):
        publication = self.publication()
        self.assertEqual(self.authority.effects, ["publication"])
        self.assertEqual(self.authority.active, {})
        result = self.cas(publication)
        readback = self.protected.readback(result)
        self.assertEqual(replace(readback, evidence=result.evidence), result)
        self.assertNotEqual(readback.evidence, result.evidence)
        self.assertEqual(self.authority.effects, ["publication", "cas", "readback"])

    def test_defaults_reject_without_io(self):
        for action in (lambda: m.QualificationProvider().package(self.f.snapshot),
                       lambda: m.ProtectedAuthorityProvider().readback(None),
                       lambda: m.RawEvidence().resolve(frozen.ref("missing")),
                       lambda: a.QualificationAdapter().package(self.f.snapshot)):
            with self.assertRaises(a.ActivationRejected):
                action()
        self.assertEqual(self.authority.effects, [])

    def test_synthetic_cannot_masquerade_as_operational(self):
        q = m.QualificationProvider(self.authority, self.authority.raw,
                                   binding=self.authority.qbinding)
        with self.assertRaises(a.ActivationRejected):
            q.package(self.f.snapshot)
        p = m.ProtectedAuthorityProvider(self.authority, self.q, self.authority.raw,
                                        binding=self.authority.pbinding)
        with self.assertRaises(a.ActivationRejected):
            p.publish_checkpoint(self.f.snapshot, self.f.approval, self.authorization)

    def test_arbitrary_callbacks_are_not_clients(self):
        q = m.QualificationProvider(lambda *args: True, self.authority.raw,
                                   binding=self.authority.qbinding, kind="SYNTHETIC")
        with self.assertRaises(a.ActivationRejected):
            q.package(self.f.snapshot)

    def test_raw_retention_resolution_and_immutable_collision(self):
        raw = b"synthetic immutable raw record"
        ref = reference("synthetic-retained", raw)
        self.authority.put(ref, raw)
        self.authority.attest(ref, ref, self.authority.qbinding, "view", ())
        result = self.authority.raw.retain(m.RetainedEvidence(ref, raw), self.authority.qbinding,
                                          "view", (), obligations=("EXACT_ROLE_CONTEXT_ISSUER", "TRANSITIVE_STAGE_RESTRICTIONS"))
        self.assertEqual(result.value, ref)
        self.assertEqual(self.authority.raw.resolve(ref).raw, raw)
        with self.assertRaises(a.ActivationRejected):
            self.authority.raw.retain(m.RetainedEvidence(ref, raw + b"changed"),
                                     self.authority.qbinding, "view", ())
        with self.assertRaises(a.ActivationRejected):
            self.authority.store.retain(m.RetainedEvidence(reference(ref.identity, b"different"), b"different"))

    def test_unresolved_reference_fails_closed(self):
        with self.assertRaises(m.ProviderBoundaryFailure):
            self.authority.raw.resolve(frozen.ref("not-retained"))

    def test_raw_corruption_rejected(self):
        self.authority.store.fault = "corrupt"
        with self.assertRaises(a.ActivationRejected):
            self.q.package(self.f.snapshot)

    def test_missing_nested_raw_not_cached(self):
        self.q.package(self.f.snapshot)
        ref = self.f.approval.evidence.reference
        accepted = a.validate_genesis_package(self.f.snapshot, self.q.package(self.f.snapshot))
        self.q.approval(accepted, self.f.approval, self.f.clock)
        del self.authority.store.records[ref.identity]
        with self.assertRaises(m.ProviderBoundaryFailure):
            self.authority.raw.resolve(ref)

    def test_concurrent_original_has_one_winner(self):
        # Both clients share external history; the adapters themselves have no lock/history.
        def call(_):
            try:
                return self.authority.new_protected().publish_checkpoint(
                    self.f.snapshot, self.f.approval, self.authorization)
            except a.ActivationRejected:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(call, range(2)))
        self.assertEqual(sum(x is not None for x in results), 1)
        self.assertEqual(self.authority.effects, ["publication"])

    def test_uncertain_history_stops_dispatch_and_restart(self):
        self.authority.fault = "entry"
        with self.assertRaises(m.ProviderBoundaryFailure):
            self.publication()
        self.authority.fault = None
        self.protected = self.authority.new_protected()
        with self.assertRaises(a.ActivationRejected):
            self.publication()
        self.assertEqual(self.authority.effects, [])

    def test_unknown_publication_has_no_retry_after_restart(self):
        self.authority.fault = "publication"
        with self.assertRaises(m.ProviderBoundaryFailure):
            self.publication()
        self.authority.fault = None
        self.protected = self.authority.new_protected()
        with self.assertRaises(a.ActivationRejected):
            self.publication()
        self.assertEqual(self.authority.effects, ["publication"])

    def test_unknown_cas_has_no_retry_after_restart(self):
        publication = self.publication()
        self.authority.fault = "cas"
        with self.assertRaises(a.ActivationRejected):
            self.cas(publication)
        self.authority.fault = None
        self.protected = self.authority.new_protected()
        with self.assertRaises(a.ActivationRejected):
            self.cas(publication)
        self.assertEqual(self.authority.effects, ["publication", "cas"])

    def test_unknown_readback_does_not_repeat_effect(self):
        result = self.cas()
        self.authority.fault = "readback"
        with self.assertRaises(m.ProviderBoundaryFailure):
            self.protected.readback(result)
        self.assertEqual(self.authority.effects, ["publication", "cas", "readback"])

    def test_payload_stays_downstream_of_approval(self):
        before = self.f.snapshot.package
        accepted = a.validate_genesis_package(self.f.snapshot, self.q.package(self.f.snapshot))
        payload = a.activation_payload(accepted, self.f.approval, self.f.clock, self.q)
        approval_calls = [x for x in self.authority.verifier.calls if x.role == "approval"]
        self.assertTrue(approval_calls)
        self.assertEqual(approval_calls[-1].context, (self.f.snapshot, self.f.approval, self.f.clock))
        self.assertNotIn(sha256(a.canonical_bytes(payload)).hexdigest().encode(), before)
        self.assertEqual(before, self.f.snapshot.package)

    def test_no_implicit_network_or_managed_effect(self):
        with patch.object(socket, "create_connection", side_effect=AssertionError("NETWORK_FORBIDDEN")):
            self.q.package(self.f.snapshot)
            m.QualificationProvider()
            m.ProtectedAuthorityProvider()
            m.RawEvidence()
        self.assertEqual(self.authority.effects, [])
        self.assertFalse(self.f.request.location.final.exists())

    def test_frozen_executor_consumes_new_providers_without_modification(self):
        request = frozen.execution(self.f, self.receipt)
        result = a.execute_genesis(request, qualification=self.q, protected=self.protected,
                                   attempt=self.receipt.attempt)
        self.assertIsNone(result.cause, repr(result.cause))
        self.assertIs(result.reached, a.Reached.READBACK_CONFIRMED_VERIFICATION_PENDING)
        self.assertTrue(result.recovery_only)
        self.assertEqual(self.authority.effects, ["publication", "cas", "readback"])

    def test_frozen_executor_unknown_keeps_strongest_reached_floor(self):
        self.authority.fault = "cas"
        request = frozen.execution(self.f, self.receipt)
        result = a.execute_genesis(request, qualification=self.q, protected=self.protected,
                                   attempt=self.receipt.attempt)
        self.assertIs(result.reached, a.Reached.CAS_ATTEMPTED)
        self.assertTrue(result.recovery_only)
        self.assertIsInstance(result.cause, m.ProviderBoundaryFailure)
        again = a.execute_genesis(request, qualification=self.q, protected=self.protected,
                                  attempt=self.receipt.attempt)
        self.assertIsNotNone(again.cause)
        self.assertEqual(self.authority.effects, ["publication", "cas"])

    def test_raw_provider_failure_redacts_exception_and_cause(self):
        class SecretFailure(m.EvidenceClient):
            def resolve(self, reference):
                raise RuntimeError("synthetic-secret-material-must-not-escape")
        raw = m.RawEvidence(SecretFailure(), self.authority.verifier,
                            binding=binding("retention"), kind="SYNTHETIC")
        with self.assertRaises(m.ProviderBoundaryFailure) as error:
            raw.resolve(frozen.ref("synthetic-error"))
        self.assertNotIn("secret-material", str(error.exception))
        self.assertIsNone(error.exception.__cause__)
        self.assertIsNone(error.exception.__context__)

    def test_retention_provider_identity_cannot_be_substituted(self):
        self.authority.raw.binding = replace(binding("retention"), principal="synthetic-wrong-store-owner")
        with self.assertRaisesRegex(a.ActivationRejected, "AUTHENTICATED_BINDING_MISMATCH"):
            self.q.package(self.f.snapshot)

    def test_missing_provider_adoption_raw_fails_closed(self):
        del self.authority.store.records[self.authority.qbinding.adoption.identity]
        with self.assertRaises(m.ProviderBoundaryFailure):
            self.q.package(self.f.snapshot)

    def test_transitive_upstream_raw_dependency_rejected(self):
        self.authority.verifier.forbidden_upstream.add(self.f.e.creation_evidence.identity)
        with self.assertRaises(m.ProviderBoundaryFailure):
            self.q.package(self.f.snapshot)
        self.assertEqual(self.authority.effects, [])

    def test_uncertain_raw_retention_never_qualifies(self):
        raw = b"synthetic retained error evidence"
        ref = reference("synthetic-retention-unknown", raw)
        self.authority.store.fault = "retain"
        with self.assertRaises(m.ProviderBoundaryFailure):
            self.authority.raw.retain(m.RetainedEvidence(ref, raw), self.authority.qbinding, "view", ())

    def test_all_adapters_replaced_still_cannot_repeat_original(self):
        self.publication()
        raw = m.RawEvidence(self.authority.store, self.authority.verifier,
                            binding=binding("retention"), kind="SYNTHETIC")
        qualifier = m.QualificationProvider(self.authority, raw, binding=self.authority.qbinding,
            verifier_binding=self.authority.vbinding, kind="SYNTHETIC")
        protected = m.ProtectedAuthorityProvider(self.authority, qualifier, raw,
            binding=self.authority.pbinding, kind="SYNTHETIC")
        with self.assertRaises(m.ProviderBoundaryFailure):
            protected.publish_checkpoint(self.f.snapshot, self.f.approval, self.authorization)
        self.assertEqual(self.authority.effects, ["publication"])

    def test_readback_timeout_does_not_reset_original_cas_admission(self):
        publication = self.publication()
        result = self.cas(publication)
        self.authority.fault = "readback"
        with self.assertRaises(m.ProviderBoundaryFailure):
            self.protected.readback(result)
        self.authority.fault = None
        with self.assertRaises(a.ActivationRejected):
            self.authority.new_protected().activate_absent(
                a.canonical_bytes(a._bound_payload(a._validate_snapshot(self.f.snapshot), self.f.approval)),
                publication, frozen.ref("fresh-absence"), self.authorization)
        self.assertEqual(self.authority.effects, ["publication", "cas", "readback"])

    def test_readback_cannot_echo_caller_instead_of_external_state(self):
        result = self.cas()
        self.authority.active[result.register_id] = replace(result, host_identity="synthetic-different-host")
        with self.assertRaises(m.ProviderBoundaryFailure):
            self.protected.readback(result)
        self.assertEqual(self.authority.effects, ["publication", "cas", "readback"])

    def test_historical_tombstone_is_not_absence(self):
        self.authority.tombstones.add(self.f.e.register_id)
        with self.assertRaises(a.ActivationRejected):
            self.publication()
        self.assertEqual(self.authority.effects, [])

    def test_lost_publication_response_preserves_effect_without_retry(self):
        self.authority.fault = "after-publication"
        with self.assertRaises(m.ProviderBoundaryFailure):
            self.publication()
        self.assertIn(self.f.e.register_id, self.authority.checkpoints)
        self.assertEqual(self.authority.active, {})
        self.authority.fault = None
        with self.assertRaises(a.ActivationRejected):
            self.authority.new_protected().publish_checkpoint(self.f.snapshot, self.f.approval, self.authorization)
        self.assertEqual(self.authority.effects, ["publication"])

    def test_lost_cas_response_preserves_active_history_without_retry(self):
        publication = self.publication()
        self.authority.fault = "after-cas"
        with self.assertRaises(m.ProviderBoundaryFailure):
            self.cas(publication)
        self.assertIn(self.f.e.register_id, self.authority.active)
        self.authority.fault = None
        with self.assertRaises(a.ActivationRejected):
            self.cas(publication)
        self.assertEqual(self.authority.effects, ["publication", "cas"])

    def opening(self, expiry=1000000, fresh=0):
        result = self.cas()
        raw = b"synthetic independent all-obligations result verification"
        verification = a.OpaqueEvidence("INDEPENDENT_RESULT_VERIFICATION",
            a.Reference("synthetic-independent-verification", sha256(raw).hexdigest()), raw,
            frozen.ref("synthetic-independent-verification-qualification"))
        clock = self.f.clock
        if fresh:
            current = replace(clock.current, ticks_ns=fresh * 1000)
            clock = replace(clock, current=current, error=replace(clock.error, elapsed_ns=fresh * 1000))
        approval = replace(self.f.approval, valid_until_us=expiry)
        request = a.OpenRequest(self.f.snapshot, self.f.request.location, self.receipt.native_identity,
            approval, result, verification, clock, self.f.e.actors.opener, self.f.e.actors.issuer)
        return request

    def preparation_at_authenticated_time_two(self, *, valid_from=0, valid_until=3):
        request = self.f.request
        clock = request.clock
        self.authority.preparation_clock = replace(clock,
            current=replace(clock.current, ticks_ns=2000),
            error=replace(clock.error, elapsed_ns=2000))
        self.authority.bad_value = ("preparation", lambda q: replace(q,
            valid_from_us=valid_from, valid_until_us=valid_until))
        self.assertEqual(request.clock.current.ticks_ns, 0)
        return self.q.preparation(request)

    def test_preparation_stale_request_expired_at_authenticated_current_time(self):
        with self.assertRaisesRegex(a.ActivationRejected, "EXPIRED_OR_UNCERTAIN"):
            self.preparation_at_authenticated_time_two(valid_until=1)
        self.assertEqual(self.authority.effects, [])

    def test_preparation_stale_request_valid_at_authenticated_current_time(self):
        q = self.preparation_at_authenticated_time_two(valid_until=3)
        self.assertIs(type(q), a.QualifiedPreparation)
        self.assertEqual(q.request, self.f.request)
        self.assertEqual(q.request.metadata.last_valid_utc, 0)
        self.assertEqual(self.authority.effects, [])

    def test_preparation_authenticated_time_equals_inclusive_valid_until(self):
        self.assertIs(type(self.preparation_at_authenticated_time_two(valid_until=2)),
                      a.QualifiedPreparation)

    def test_preparation_authenticated_time_equals_inclusive_valid_from(self):
        self.assertIs(type(self.preparation_at_authenticated_time_two(valid_from=2)),
                      a.QualifiedPreparation)

    def test_preparation_not_yet_valid_at_authenticated_current_time(self):
        with self.assertRaisesRegex(a.ActivationRejected, "NOT_YET_VALID"):
            self.preparation_at_authenticated_time_two(valid_from=3)

    def test_current_open_requires_independent_verifier(self):
        request = self.opening()
        self.assertIs(type(self.q.opening(request)), a.QualifiedOpen)
        self.q.verifier_binding = replace(self.authority.vbinding, principal=self.f.e.actors.issuer)
        with self.assertRaisesRegex(a.ActivationRejected, "INDEPENDENT_RESULT_VERIFIER_REQUIRED"):
            self.q.opening(request)

    def test_open_q_expiry_request_zero_expiry_one_fresh_two(self):
        request = self.opening(expiry=1)
        fresh = replace(request.clock, current=replace(request.clock.current, ticks_ns=2000),
                        error=replace(request.clock.error, elapsed_ns=2000))
        self.authority.bad_value = ("opening", lambda q: replace(q, fresh_time=fresh))
        with self.assertRaisesRegex(a.ActivationRejected, "EXPIRED_OR_UNCERTAIN"):
            self.q.opening(request)


def install_negative_cases():
    class SyntheticStatus(StrEnum):
        CONFIRMED = "CONFIRMED"
    for fault in ("boolean", "binding", "role", "context", "digest", "revoked", "stale", "future", "bool-time",
                  "rotated-without-continuity"):
        def test(self, fault=fault):
            self.authority.verifier.fault = fault
            with self.assertRaises((a.ActivationRejected, s.TimeRejected, a.protocol.ProtocolRejected)):
                self.q.package(self.f.snapshot)
            self.assertEqual(self.authority.effects, [])
        setattr(ProviderTests, "test_authentication_rejects_" + fault.replace("-", "_"), test)

    cases = [
        ("package", "generation_bool", lambda q: replace(q, claims=replace(q.claims,
            creation=replace(q.claims.creation, generation=True)))),
        ("package", "native_bool", lambda q: replace(q, claims=replace(q.claims,
            creation=replace(q.claims.creation, native_identity=(True, 1))))),
        ("package", "wrong_register", lambda q: replace(q, claims=replace(q.claims,
            creation=replace(q.claims.creation, register_id="wrong")))),
        ("package", "wrong_stage", lambda q: replace(q, claims=replace(q.claims, upstream_dependency_stage="DOWNSTREAM"))),
        ("package", "missing_opaque", lambda q: replace(q, opaque=q.opaque[:-1])),
        ("package", "malformed_claims", lambda q: replace(q, claims=None)),
        ("preparation", "wrong_operation", lambda q: replace(q, action="EXECUTE_ORIGINAL_GENESIS")),
        ("preparation", "unknown_absence", lambda q: replace(q, presence="UNKNOWN")),
        ("preparation", "stale", lambda q: replace(q, valid_until_us=-1)),
        ("preparation", "wrong_process", lambda q: replace(q, process="synthetic-wrong-process")),
        ("creation", "empty_operator", lambda q: replace(q, claims=replace(q.claims, preparation_operator=""))),
        ("publication-admission", "active", lambda q: replace(q, presence="ACTIVE")),
        ("publication-admission", "prior_history", lambda q: replace(q, original_history="UNRESOLVED")),
        ("publication-admission", "zero_bool", lambda q: replace(q, predecessor_generation=False)),
        ("cas-admission", "active", lambda q: replace(q, presence="ACTIVE")),
        ("cas-admission", "predecessor", lambda q: replace(q, predecessor_generation=1)),
        ("cas-admission", "wrong_k", lambda q: replace(q, operation="wrong-attempt")),
        ("cas-admission", "wrong_absence", lambda q: replace(q, absence_history=frozen.ref("wrong-absence"))),
        ("publication-entry", "unresolved", lambda q: replace(q, state="UNRESOLVED")),
        ("publication-entry", "wrong_operation", lambda q: replace(q, operation="wrong")),
        ("cas-entry", "unresolved", lambda q: replace(q, state="UNRESOLVED")),
        ("publication-result", "unknown", lambda r: replace(r, status="UNKNOWN")),
        ("publication-result", "wrong_operation", lambda r: replace(r, operation="wrong")),
        ("publication-result", "wrong_host", lambda r: replace(r, host_identity="wrong")),
        ("cas-result", "unknown", lambda r: replace(r, status="UNKNOWN")),
        ("cas-result", "wrong_register", lambda r: replace(r, register_id="wrong")),
        ("cas-result", "wrong_generation", lambda r: replace(r, generation=2)),
        ("cas-result", "bool_generation", lambda r: replace(r, generation=True)),
        ("cas-result", "status_scalar_subclass", lambda r: replace(r, status=SyntheticStatus.CONFIRMED)),
        ("cas-result", "wrong_activation", lambda r: replace(r, activation_id="wrong")),
        ("cas-result", "wrong_payload", lambda r: replace(r, payload_sha256=b"x" * 32)),
        ("cas-result", "wrong_package", lambda r: replace(r, package=r.checkpoint)),
        ("readback", "wrong_state", lambda r: replace(r, state="EVENTUAL_CACHE")),
        ("readback", "wrong_register", lambda r: replace(r, result=replace(r.result, register_id="wrong"))),
        ("readback", "wrong_original", lambda r: replace(r, original=replace(r.original, command_id="wrong"))),
    ]
    for role, name, change in cases:
        def test(self, role=role, change=change):
            self.authority.bad_value = (role, change)
            with self.assertRaises((a.ActivationRejected, s.TimeRejected, KeyError, AttributeError)):
                if role == "package":
                    self.q.package(self.f.snapshot)
                elif role == "preparation":
                    self.q.preparation(self.f.request)
                elif role == "creation":
                    self.q.creation(self.f.request, self.receipt.native_identity,
                                    self.receipt.state, self.receipt.database_sha256)
                elif role.startswith("publication"):
                    self.publication()
                elif role == "readback":
                    self.protected.readback(self.cas())
                else:
                    self.cas()
            if role.endswith("admission"):
                self.assertNotIn("cas" if role.startswith("cas") else "publication", self.authority.effects)
        setattr(ProviderTests, "test_negative_" + role.replace("-", "_") + "_" + name, test)


install_negative_cases()

if __name__ == "__main__":
    unittest.main()
