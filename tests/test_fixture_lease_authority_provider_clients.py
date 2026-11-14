"""Offline composition tests; no discovery, credentials or external calls."""
from dataclasses import fields
import importlib
import unittest
from unittest.mock import Mock, patch

import test_fixture_lease_activation as frozen

c = importlib.import_module(frozen.PACKAGE + ".fixture_lease_authority_provider_clients")
e, p = c.e, c.p


class ProviderTests(unittest.TestCase):
    def test_construction_is_inert(self):
        carrier, material = Mock(), Mock()
        with patch("socket.socket", side_effect=AssertionError("NETWORK_FORBIDDEN")):
            client = c.OneShotAWS(carrier=carrier, material=material,
                                   qualification_ref=frozen.ref("qualification"), service="kms")
        self.assertEqual(client.service, "kms")
        carrier.assert_not_called()
        self.assertEqual(carrier.mock_calls, [])
        self.assertEqual(material.mock_calls, [])

    def test_effect_admission_remains_frozen_without_provenance(self):
        self.assertEqual(tuple(field.name for field in fields(p.EffectAdmission)),
            ("snapshot", "approval", "authorization", "absence_history", "clock", "operation",
             "presence", "predecessor_generation", "original_history"))
        self.assertNotIn("provenance", p.EffectAdmission.__annotations__)

    def test_unsupported_algorithm_never_enters_carrier(self):
        carrier = Mock()
        client = c.OneShotAWS(carrier=carrier, material=Mock(), qualification_ref=frozen.ref("q"), service="kms")
        with self.assertRaises(e.EvidenceFailure):
            client.sign(KeyId="arn:aws:kms:test:000000000000:key/key", Message=b"d" * 32,
                        MessageType="DIGEST", SigningAlgorithm="RSASSA_PKCS1_V1_5_SHA_256")
        self.assertEqual(carrier.mock_calls, [])

    def test_uncertain_transport_is_not_retried(self):
        carrier = Mock()
        carrier.invoke_once.side_effect = TimeoutError("credential-bearing error must be redacted")
        client = c.OneShotAWS(carrier=carrier, material=Mock(), qualification_ref=frozen.ref("q"), service="kms")
        with self.assertRaisesRegex(e.EvidenceFailure, "NO_REPLAY") as failure:
            client.sign(KeyId="arn:aws:kms:test:000000000000:key/key", Message=b"d" * 32,
                        MessageType="DIGEST", SigningAlgorithm=e.ALGORITHM)
        self.assertEqual(carrier.invoke_once.call_count, 1)
        self.assertNotIn("credential-bearing", str(failure.exception))

    def test_no_latest_version_or_multipart_surface(self):
        client = c.OneShotAWS(carrier=Mock(), material=Mock(), qualification_ref=frozen.ref("q"), service="s3")
        for version in (None, "", "null"):
            with self.assertRaises(e.EvidenceFailure):
                client.get_object(Bucket="b", Key="key", VersionId=version, ExpectedBucketOwner="000000000000")
        self.assertFalse(hasattr(client, "create_multipart_upload"))
        self.assertFalse(hasattr(client, "upload_file"))
        self.assertFalse(hasattr(client, "delete_object"))

    def test_broker_issuer_cannot_create_independent_authority(self):
        for role in ("GOVERNANCE", "KEY_BINDING", "KEY_STATUS", "VERIFIER_ATTESTATION", "INDEPENDENT_RESULT", "QUAL_APPROVAL"):
            with self.assertRaises(e.EvidenceFailure):
                c.ReceiptIssuer(kms=Mock(), evidence=Mock(), verifier=Mock(), material=Mock(),
                                recipes=Mock(), permitted_roles=(role,))

    def test_configuration_has_no_defaults_or_upload_override(self):
        with self.assertRaises(e.EvidenceFailure):
            c.validate_configuration({})
        self.assertIn("max_single_upload_bytes", c.CONFIG_FIELDS)
        self.assertEqual(e.MAX_SINGLE_UPLOAD_BYTES, 8388608)

    def test_unqualified_inputs_do_not_become_trust_roots(self):
        with self.assertRaises(e.EvidenceFailure):
            c.QualifiedMaterial(evidence=p.EvidenceClient(), verifier=p.EvidenceVerifier(), records=(), roots=())
        material = c.QualifiedMaterial(evidence=p.EvidenceClient(), verifier=p.EvidenceVerifier(),
                                       records=(), roots=(frozen.ref("supplied-T"),))
        with self.assertRaises(e.EvidenceFailure):
            material.view(frozen.ref("missing"))


class BoundarySanitizationTests(unittest.TestCase):
    def assert_chain_free(self, function):
        with self.assertRaises(e.EvidenceFailure) as failed:
            function()
        self.assertNotIn("SENSITIVE", str(failed.exception))
        self.assertIsNone(failed.exception.__context__)
        self.assertIsNone(failed.exception.__cause__)
        self.assertEqual(vars(failed.exception), {})

    def test_aws_and_qualification_carrier_exceptions_are_detached(self):
        for where in ("invoke", "qualification"):
            carrier, material = Mock(), Mock()
            if where == "invoke":
                carrier.invoke_once.side_effect = RuntimeError("SENSITIVE-CREDENTIAL")
            else:
                material.view.side_effect = RuntimeError("SENSITIVE-QUALIFICATION-TRANSPORT")
            client = c.OneShotAWS(carrier=carrier, material=material, qualification_ref=frozen.ref("q"), service="kms")
            self.assert_chain_free(lambda: client.sign(KeyId="arn:aws:kms:test:000000000000:key/key",
                Message=b"d" * 32, MessageType="DIGEST", SigningAlgorithm=e.ALGORITHM))
            self.assertFalse(any("error" in name or "exception" in name for name in vars(client)))

    def test_connection_stream_and_kms_exception_boundaries(self):
        # Construct inert instances to address actual transport boundaries without
        # a configuration fixture ever reading a credential or opening a socket.
        session = c.WriterSession(Mock(), {}, Mock())
        session._begun, session._used = True, True
        session.connection.execute.side_effect = RuntimeError("SENSITIVE-DB-CARRIER")
        self.assert_chain_free(session.commit)
        from test_fixture_lease_authority_evidence import body, ref
        kms = Mock()
        kms.sign.side_effect = RuntimeError("SENSITIVE-KMS-CARRIER")
        self.assert_chain_free(lambda: e.kms_sign(e.producer_bytes(body(), e.BODY_FIELDS), kms))
        custody = Mock()
        custody.resolve.side_effect = RuntimeError("SENSITIVE-CUSTODY-CARRIER")
        client = e.ExactVersionEvidence(s3=Mock(), custody=custody, authority=Mock(), plans=Mock())
        self.assert_chain_free(lambda: client.resolve(e.reference(ref("retained"))))
        client.s3.get_object.side_effect = RuntimeError("SENSITIVE-S3-CARRIER")
        plan = e.CustodyPlan("ns", "inc", "role", "attempt", "bucket", "000000000000",
                            frozen.ref("bucket"), 1000, frozen.ref("retention"), 1024, 8388608)
        self.assert_chain_free(lambda: client._read(frozen.ref("retained"), plan, "key", "version"))

    def test_material_scope_rejects_observer_and_cross_scope_before_session(self):
        from test_fixture_lease_authority_evidence import AdmissionMappingTests, body, ref
        _, _, _, _, view, _, _ = AdmissionMappingTests().source("ADMISSION_PUBLICATION")
        request = {"operation": "ORIGINAL_ATTEMPT_ADMISSION", "operation_role": "CHECKPOINT_PUBLICATION"}
        for name, rule in c.b.request_spec(request):
            if name in request: continue
            request[name] = (b"data" if rule == "BYTES" else view.clock if rule == "TIME"
                else ref(name) if rule == "R" else "value" if rule in ("ID", "TEXT")
                else 0 if rule in ("U", "UTC") else rule[0] if type(rule) is tuple else rule)
        request["logical_role"] = "EXECUTOR"
        for prefix in ("E", "S0", "C0", "P", "Q"):
            request[prefix + "_ref"] = {"identity": prefix, "sha256": c.sha256(request[prefix + "_bytes"]).hexdigest()}
        binding = p.ProviderBinding("broker", "OPERATIONAL", "internal-broker", "carrier", "authority",
            "issuer", "namespace", "OPERATIONAL", frozen.ref("qualification"), frozen.ref("selection"), frozen.ref("adoption"))
        config = {"namespace": request["namespace"], "incarnation_id": request["incarnation_id"],
                  "actor_bindings": {"broker": binding}}
        caller = c.b.Caller(binding.principal, binding.credential_identity, "BROKER", binding)
        signed = body("ENTRY_PUBLICATION")
        signed.update(namespace=request["namespace"], incarnation_id=request["incarnation_id"],
                      request_id=request["request_id"], configuration_ref=request["configuration_ref"])
        signed["predecessor_refs"] = e.required_predecessors(signed)
        record = e.assemble(e.producer_bytes(signed, e.BODY_FIELDS), b"s" * 384, ref("custody"))
        material = dict(namespace=request["namespace"], incarnation_id=request["incarnation_id"],
            request_id=request["request_id"], original_raw=record.raw.hex(), authentication_ref=e.wire_ref(record.reference),
            material_id=record.reference.identity, evidence_identity=record.reference.identity,
            raw_sha256=record.reference.sha256.hex(), subject_ref=signed["subject_ref"],
            receipt_role=signed["receipt_role"], issuer_id=signed["issuer_id"])
        c.validate_material_scope(config, request, caller, material)
        for replacement in (c.b.Caller(binding.principal, binding.credential_identity, "OBSERVER", binding),
                            c.b.Caller("other-principal", binding.credential_identity, "BROKER", binding)):
            with self.assertRaises(e.EvidenceFailure):
                c.validate_material_scope(config, request, replacement, material)
        for field in ("namespace", "incarnation_id", "request_id", "receipt_role", "issuer_id"):
            wrong = dict(material, **{field: "wrong"})
            with self.assertRaises(e.EvidenceFailure):
                c.validate_material_scope(config, request, caller, wrong)
