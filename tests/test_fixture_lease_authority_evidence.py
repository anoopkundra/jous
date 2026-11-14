"""Unexecuted offline source vectors; synthetic evidence is never adoption."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import importlib
import json
import unittest
from unittest.mock import Mock

import test_fixture_lease_activation as frozen

e = importlib.import_module(frozen.PACKAGE + ".fixture_lease_authority_evidence")
p = e.p


def ref(name="subject"):
    return {"identity": name, "sha256": sha256(name.encode()).hexdigest()}


def body(role="ADMISSION_PUBLICATION"):
    result = {name: "synthetic" for name in e.BODY_FIELDS}
    for name in ("configuration_ref", "adoption_ref", "key_binding_ref", "key_status_ref",
                 "subject_ref", "request_ref", "qualification_ref", "time_ref"):
        result[name] = ref(name)
    result.update(profile_id=e.PROFILE, schema_version=1, receipt_role=role,
        receipt_id="synthetic-receipt", account_id="000000000000", region="synthetic-region",
        key_arn="arn:aws:kms:synthetic-region:000000000000:key/synthetic-key",
        spki_sha256=sha256(b"synthetic-key").hexdigest(), signature_algorithm=e.ALGORITHM,
        stage="CURRENT", subject_kind="OPAQUE_EXTERNAL_EVIDENCE", predecessor_refs=[],
        valid_from_us=0, valid_until_us=1000000, outcome="ESTABLISHED", rejection_reason="NONE")
    kinds = dict(zip(e.ROLES[:6], e.KINDS[:6]))
    kinds.update({r: "PUBLICATION" for r in e.ROLES if r.endswith("_PUBLICATION")})
    kinds.update({r: "CAS" for r in e.ROLES if r.endswith("_CAS")})
    kinds.update({"READBACK": "READBACK", "INDEPENDENT_RESULT": "READBACK", "GOVERNANCE": "GOVERNANCE",
                  "KEY_BINDING": "KEY", "KEY_STATUS": "KEY", "VERIFIER_ATTESTATION": "KEY", "PROOF_BINDING": "KEY"})
    kinds.update({r: "CUSTODY" for r in ("CUSTODY_RESERVE", "CUSTODY_VERSION", "CUSTODY_BIND")})
    kind = kinds[role]
    register = kind not in ("CUSTODY", "KEY", "GOVERNANCE")
    context = {name: None for name in e.CONTEXT_FIELDS}
    context.update(kind=kind, scope_ref=ref("scope"), authorization_ref=ref("authorization"), request_facts_ref=ref("facts"))
    if register:
        context.update(register_id="register", generation=1, activation_id="activation", K="K", J="J", host_ref=ref("host"))
    protected = role.startswith(("ADMISSION_", "ENTRY_", "CLAIM_", "RESULT_")) or role == "READBACK"
    if protected:
        context.update(operation_id="operation", operation_role="ACTIVATION_CAS" if kind in ("CAS", "READBACK") else "CHECKPOINT_PUBLICATION",
                       input_binding_ref=ref("input"))
    if kind in ("PACKAGE", "EXECUTION", "APPROVAL", "PUBLICATION", "CAS", "READBACK", "OPENING"):
        context.update({name: ref(name) for name in ("E_ref", "S0_ref", "C0_ref", "P_ref")})
    if kind in ("EXECUTION", "APPROVAL", "PUBLICATION", "CAS", "READBACK", "OPENING"):
        context["Q_ref"] = ref("Q")
    if kind in ("CAS", "READBACK", "OPENING"):
        context.update(payload_ref=ref("payload"), publication_ref=ref("publication"))
    if kind in ("READBACK", "OPENING"):
        context["activation_ref"] = ref("activation")
    result["context"] = context
    values = {"ID": "synthetic", "H": sha256(b"value").hexdigest(), "U": 1, "UTC": 0,
              "R": ref(), "?R": None, "ARN": result["key_arn"], "O": list(p._COMMON),
              "PATH": ["authorization"], "TEXT": "synthetic-version", "ROLES": [role]}
    details = {}
    for name, rule in e.DETAILS[role]:
        details[name] = deepcopy(values[rule]) if type(rule) is str and rule in values else rule[0] if type(rule) is tuple else rule
    if role in e.ROLES[:8]:
        details["view_subject_ref"] = result["subject_ref"]
        index = e.ROLES.index(role)
        details["view_type"] = ("QualifiedPackageBindings", "QualifiedPreparation", "QualifiedCreation", "QualifiedExecution",
            "ApprovalView", "QualifiedOpen", "EffectAdmission", "EffectAdmission")[index]
        logical = ("package", "preparation", "creation", "execution", "approval", "opening", "publication-admission", "cas-admission")[index]
        details["obligations"] = list(p._COMMON + p._OBLIGATIONS[logical])
    if role.startswith(("ENTRY_", "CLAIM_")):
        details["operation_id"] = context["operation_id"]
    if role.startswith("CLAIM_"):
        details["operation_role"] = context["operation_role"]
    if role == "RESULT_PUBLICATION":
        details["operation"] = context["operation_id"]
    if role == "RESULT_CAS":
        details["command_id"] = context["K"]
    if role == "PROOF_BINDING":
        details["leaf_ref"] = result["subject_ref"]
    if role in ("CUSTODY_RESERVE", "CUSTODY_BIND"):
        details["object_key"] = e.object_key(result["namespace"], result["incarnation_id"],
            details["custody_role"], details["evidence_ref"]["identity"], 1024)
    result["details"] = details
    if role in ("QUAL_PACKAGE", "QUAL_CREATION"):
        result["stage"] = "UPSTREAM_ONLY"
    elif role == "QUAL_APPROVAL":
        result["stage"] = "Q"
    elif role == "INDEPENDENT_RESULT":
        result["stage"] = "INDEPENDENT_RESULT_VERIFICATION"
    result["predecessor_refs"] = e.required_predecessors(result)
    return result


class CodecTests(unittest.TestCase):
    def test_inventory_is_exactly_twenty_four_and_closed(self):
        self.assertEqual(len(e.ROLES), 24)
        self.assertEqual(set(e.DETAILS), set(e.ROLES))
        for role in e.ROLES:
            candidate = body(role)
            raw = e.producer_bytes(candidate, e.BODY_FIELDS)
            self.assertEqual(e.validate_body(raw), candidate)
            for name in e.BODY_FIELDS:
                missing = deepcopy(candidate)
                del missing[name]
                with self.assertRaises(e.EvidenceFailure):
                    e.validate_body(json.dumps(missing).encode())
            candidate["details"]["extension"] = "not authorized"
            with self.assertRaises(e.EvidenceFailure):
                e.validate_body(json.dumps(candidate).encode())

    def test_exact_byte_acceptance_and_no_normalization(self):
        raw = e.producer_bytes(body(), e.BODY_FIELDS)
        altered = b" \t\r\n" + raw + b"\n"
        self.assertEqual(e.validate_body(raw), e.validate_body(altered))
        self.assertNotEqual(sha256(raw).digest(), sha256(altered).digest())
        for invalid in (b"\xef\xbb\xbf" + raw, raw + b"x", raw.replace(b'"schema_version":1', b'"schema_version":1.0'),
                        raw.replace(b'"schema_version":1', b'"schema_version":true'),
                        raw.replace(b'"schema_version":1', b'"schema_version":1e0'),
                        raw.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1')):
            with self.assertRaises(e.EvidenceFailure):
                e.validate_body(invalid)
        for invalid in (b'{"a":1,"\\u0061":2}', b'{"a":"\\ud800"}', b'{"a":NaN}'):
            with self.assertRaises(e.EvidenceFailure):
                e.parse(invalid)

    def test_strict_reference_and_base64_domains(self):
        e.ref(ref())
        for invalid in ({"id": "subject", "sha256": "0" * 64}, {**ref(), "extra": 1},
                        {"identity": "subject", "sha256": "F" * 64}):
            with self.assertRaises(e.EvidenceFailure):
                e.ref(invalid)
        for invalid in ("Zg=", "Zh", "Zg\n", "+/", "A"):
            with self.assertRaises(e.EvidenceFailure):
                e.b64(invalid)
        self.assertEqual(e.b64("Zg"), b"f")

    def test_detached_envelope_hash_and_mutation(self):
        raw = e.producer_bytes(body(), e.BODY_FIELDS)
        record = e.assemble(raw, b"s" * 384, ref("prior-subject-custody"))
        parsed, original, signature, _ = e.envelope(record)
        self.assertEqual(original, raw)
        self.assertEqual(signature, b"s" * 384)
        self.assertEqual(record.reference.sha256, sha256(record.raw).digest())
        mutated = record.raw + b" "
        with self.assertRaises(e.EvidenceFailure):
            e.envelope(p.RetainedEvidence(record.reference, mutated))
        self.assertEqual(parsed["receipt_id"], record.reference.identity)

    def test_rsa_pss_exact_parameters_and_wrong_key(self):
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa, padding, utils
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        raw = b"exact immutable bytes\n"
        der = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        signature = key.sign(sha256(raw).digest(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), utils.Prehashed(hashes.SHA256()))
        e.verify_signature(raw, signature, der, sha256(der).hexdigest())
        for altered in (raw + b" ", raw[:-1]):
            with self.assertRaises(e.EvidenceFailure):
                e.verify_signature(altered, signature, der, sha256(der).hexdigest())
        wrong = rsa.generate_private_key(public_exponent=65537, key_size=3072).public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        with self.assertRaises(e.EvidenceFailure):
            e.verify_signature(raw, signature, wrong, sha256(wrong).hexdigest())
        wrong_salt = key.sign(sha256(raw).digest(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=20), utils.Prehashed(hashes.SHA256()))
        with self.assertRaises(e.EvidenceFailure):
            e.verify_signature(raw, wrong_salt, der, sha256(der).hexdigest())

    def test_kms_digest_one_call_no_resign(self):
        raw = e.producer_bytes(body(), e.BODY_FIELDS)
        kms = Mock()
        kms.sign.return_value = {"KeyId": body()["key_arn"], "SigningAlgorithm": e.ALGORITHM, "Signature": b"s" * 384}
        self.assertEqual(e.kms_sign(raw, kms), b"s" * 384)
        self.assertEqual(kms.sign.call_args.kwargs["Message"], sha256(raw).digest())
        self.assertEqual(kms.sign.call_args.kwargs["MessageType"], "DIGEST")
        kms.sign.side_effect = TimeoutError("not retained")
        with self.assertRaises(e.EvidenceFailure):
            e.kms_sign(raw, kms)
        self.assertEqual(kms.sign.call_count, 2)  # two explicit test invocations, one each


class CustodyTests(unittest.TestCase):
    def client(self, raw):
        reference_ = p.s.EvidenceReference("evidence", sha256(raw).digest())
        plan = e.CustodyPlan("ns", "inc", "custody", "attempt", "bucket", "000000000000",
            frozen.ref("bucket"), 1000000, frozen.ref("retention"), 1024, e.MAX_SINGLE_UPLOAD_BYTES)
        events = []
        s3 = Mock()
        def put(**kwargs):
            events.append("UPLOAD")
            return {"VersionId": "exact-version"}
        def get(**kwargs):
            events.append("VERSION")
            self.assertEqual(kwargs["VersionId"], "exact-version")
            return {"VersionId": "exact-version", "ObjectLockMode": "COMPLIANCE", "Body": BytesIO(raw)}
        s3.put_object.side_effect, s3.get_object.side_effect = put, get
        custody, authority, plans = Mock(), Mock(), Mock()
        plans.for_record.return_value = plan
        custody.reserve.side_effect = lambda *args: events.append("RESERVE") or "reservation"
        custody.bind.side_effect = lambda *args: events.append("BIND") or "binding"
        authority.bound_locator.return_value = (plan, e.object_key("ns", "inc", "custody", "evidence", 1024), "exact-version")
        return e.ExactVersionEvidence(s3=s3, custody=custody, authority=authority, plans=plans), p.RetainedEvidence(reference_, raw), events

    def test_eight_mib_complete_object_accepted_and_same_reference(self):
        client, record, events = self.client(b"x" * e.MAX_SINGLE_UPLOAD_BYTES)
        self.assertEqual(client.retain(record), record.reference)
        self.assertEqual(events, ["RESERVE", "UPLOAD", "VERSION", "BIND", "VERSION"])
        self.assertEqual(client.s3.put_object.call_args.kwargs["IfNoneMatch"], "*")
        self.assertEqual(client.s3.put_object.call_count, 1)

    def test_oversize_before_reservation_and_upload(self):
        client, record, events = self.client(b"x" * (e.MAX_SINGLE_UPLOAD_BYTES + 1))
        with self.assertRaises(e.EvidenceFailure):
            client.retain(record)
        self.assertEqual(events, [])

    def test_uncertain_upload_never_repeated_or_bound(self):
        client, record, events = self.client(b"subject")
        client.s3.put_object.side_effect = TimeoutError()
        with self.assertRaises(e.EvidenceFailure):
            client.retain(record)
        self.assertEqual(client.s3.put_object.call_count, 1)
        client.custody.bind.assert_not_called()

    def test_null_version_and_wrong_bytes_fail_closed(self):
        for version in (None, "", "null"):
            client, record, _ = self.client(b"subject")
            client.s3.put_object.side_effect = None
            client.s3.put_object.return_value = {"VersionId": version}
            with self.assertRaises(e.EvidenceFailure):
                client.retain(record)
            client.custody.bind.assert_not_called()

    def test_zero_bootstrap_sources_not_qualified(self):
        with self.assertRaises(e.EvidenceFailure):
            e.admission_provenance(role="ADMISSION_PUBLICATION", subject=None,
                expectation=None, sources=(), verifier=None, designation=None)

    def test_final_digest_cannot_be_an_upstream_input(self):
        record = p.RetainedEvidence(frozen.ref("final"), b"not a valid upstream closure")
        native = p.EvidenceVerifier()
        designation = e.AdmissionDesignation(material=Mock(), trust_ref=frozen.ref("T"),
            subject=record, request=record, decision=record, expectation=None,
            role="ADMISSION_CAS", expected_body={}, upstream=((record, ()),),
            native_verifier=native, evidence=Mock())
        with self.assertRaises(e.EvidenceFailure):
            designation.qualified_view(record, {}, record, None)


class AdmissionMappingTests(unittest.TestCase):
    """Selection/mapping unit tests; native qualification is a separate boundary.

    The verifier/designation doubles below stand only for already-qualified
    native decisions. They do not certify bootstrap roots or cryptography.
    """
    def source(self, role):
        raw = b"original opaque admission subject"
        subject = p.RetainedEvidence(p.s.EvidenceReference("S", sha256(raw).digest()), raw)
        target = body(role)
        target["subject_ref"] = e.wire_ref(subject.reference)
        target["details"]["view_subject_ref"] = target["subject_ref"]
        va = body("VERIFIER_ATTESTATION")
        va["context"] = deepcopy(target["context"])
        va["details"].update(verified_subject_ref=e.wire_ref(subject.reference),
            verification_result_ref=va["subject_ref"], interpretation_role=role,
            interpretation_type="EffectAdmission", obligations=target["details"]["obligations"])
        va["predecessor_refs"] = e.required_predecessors(va)
        record = e.assemble(e.producer_bytes(va, e.BODY_FIELDS), b"s" * 384, ref("prior-control-custody"))
        logical = "publication-admission" if role == "ADMISSION_PUBLICATION" else "cas-admission"
        expectation = p.EvidenceExpectation(None, None, logical, (), "CURRENT", tuple(target["details"]["obligations"]))
        profile = p.s.QualifiedClockProfile(frozen.ref("profile"), "synthetic-clock", frozen.ref("clock-q"),
                                           1000000, 1000, 1000, 0)
        anchor = p.s.MonotonicPoint("process", "domain", 0)
        sample = p.s.QualifiedSample(frozen.ref("sample"), profile.source, profile.profile,
                                     frozen.ref("validation"), p.s.UtcInterval(0, 0), anchor)
        clock = p.a.TimeBinding(profile, sample, anchor,
            p.s.QualifiedPropagationError(sample.sample, profile.profile, 0, 0, frozen.ref("error")))
        value = p.EffectAdmission(None, None, e.reference(target["context"]["authorization_ref"]), frozen.ref("absence"), clock,
                                 "operation", "AUTHORITATIVE_ABSENT", 0, "ORIGINAL_UNATTEMPTED_K")
        view = p.AuthenticatedView(subject.reference, expectation, value, clock, 0, 1000, record.reference)
        verifier, designation = Mock(), Mock()
        designation.authoritative_sources.side_effect = lambda records: records
        designation.matches_upstream.return_value = True
        designation.qualified_view.side_effect = lambda r, *args: replace(view, provenance=r.reference)
        verifier.authenticate.return_value = va
        verifier.evidence.resolve.return_value = record
        return target, subject, expectation, record, view, verifier, designation

    def test_each_role_uses_prior_p0_then_exact_comparison(self):
        for role in ("ADMISSION_PUBLICATION", "ADMISSION_CAS"):
            target, subject, expectation, record, view, verifier, designation = self.source(role)
            selected = e.admission_provenance(role=role, subject=subject, expectation=expectation,
                sources=(record,), verifier=verifier, designation=designation)
            self.assertEqual(selected.provenance, record.reference)
            target["details"]["view_provenance_ref"] = e.wire_ref(record.reference)
            e.bind_admission_body(target, prior_view=selected, role=role, subject=subject, expectation=expectation)
            target["details"]["view_provenance_ref"] = ref("later-V1-not-prior-P0")
            with self.assertRaises(e.EvidenceFailure):
                e.bind_admission_body(target, prior_view=selected, role=role, subject=subject, expectation=expectation)

    def test_cross_role_substitution_rejects(self):
        _, subject, expectation, record, _, verifier, designation = self.source("ADMISSION_PUBLICATION")
        with self.assertRaises(e.EvidenceFailure):
            e.admission_provenance(role="ADMISSION_CAS", subject=subject, expectation=expectation,
                sources=(record,), verifier=verifier, designation=designation)

    def test_multiple_completed_e0_sources_do_not_choose_first_or_latest(self):
        _, subject, expectation, record, _, verifier, designation = self.source("ADMISSION_PUBLICATION")
        parsed, raw, _, detached = e.envelope(record)
        # A changed signature changes complete envelope identity even if all
        # parsed body claims are the same. No hash-order tie-break is permitted.
        other = e.assemble(raw, b"t" * 384, detached["subject_custody_ref"])
        for sources in ((record, other), (other, record)):
            with self.assertRaises(e.EvidenceFailure):
                e.admission_provenance(role="ADMISSION_PUBLICATION", subject=subject, expectation=expectation,
                    sources=sources, verifier=verifier, designation=designation)


class ConcreteAssociationTests(AdmissionMappingTests):
    """Concrete designation/material/trust logic, local native verifier fixtures.

    Fixture qualification is a controlled independent native boundary; it does
    not claim that synthetic signatures or test roots are operational authority.
    """
    def concrete(self, role="ADMISSION_PUBLICATION", extra=False):
        target, subject, expectation, _, view, verifier, _ = self.source(role)
        clients = importlib.import_module(frozen.PACKAGE + ".fixture_lease_authority_provider_clients")
        def raw_record(name):
            raw = name.encode()
            return p.RetainedEvidence(p.s.EvidenceReference(name, sha256(raw).digest()), raw)
        request, decision, root, association = map(raw_record, ("X", "D", "T", "original-association"))
        va = body("VERIFIER_ATTESTATION")
        va.update(context=deepcopy(target["context"]), subject_ref=e.wire_ref(decision.reference),
                  request_ref=e.wire_ref(request.reference))
        va["details"].update(verified_subject_ref=e.wire_ref(subject.reference),
            verification_result_ref=e.wire_ref(decision.reference), interpretation_role=role,
            interpretation_type="EffectAdmission", obligations=list(expectation.obligations))
        va["predecessor_refs"] = e.required_predecessors(va)
        record = e.assemble(e.producer_bytes(va, e.BODY_FIELDS), b"s" * 384, ref("control-custody"))
        other = e.assemble(e.producer_bytes(va, e.BODY_FIELDS), b"t" * 384, ref("control-custody"))
        completed = (record.reference, other.reference) if extra else (record.reference,)
        records = {r.reference: r for r in (subject, request, decision, root, association, record, other)}
        for wire in tuple(e.all_refs(va)) + (ref("control-custody"),):
            r = raw_record(wire["identity"])
            if e.reference(wire) not in records:
                self.assertEqual(r.reference, e.reference(wire))
                records[r.reference] = r
        class Memory(p.EvidenceClient):
            def retain(self, r):
                records[r.reference] = r
                return r.reference
            def resolve(self, r):
                return records[r]
        memory = Memory()
        views = {}
        class Native(p.EvidenceVerifier):
            def verify(self, r, x):
                result = views[r.reference]
                if not e.same(result.expectation, x):
                    raise e.EvidenceFailure("INDEPENDENT_EXPECTATION_REJECTED")
                return result
        native = Native()
        def qualified(r, value):
            return p.AuthenticatedView(r.reference, expectation, value, view.clock, 0, 1000, root.reference)
        designation_tuple = (root.reference, subject.reference, request.reference, decision.reference,
                             role, expectation, va["context"])
        views[root.reference] = qualified(root, ())
        views[association.reference] = qualified(association, (designation_tuple, "ESTABLISHED", completed))
        views[decision.reference] = qualified(decision, view.value)
        views[subject.reference] = replace(view, provenance=record.reference)
        material = clients.QualifiedMaterial(evidence=memory, verifier=native,
            records=tuple((records[r], v.expectation) for r, v in views.items()), roots=(root.reference,))
        upstream = tuple((r, ()) for r in records.values()
                         if r.reference not in (record.reference, other.reference, association.reference))
        designation = e.AdmissionDesignation(material=material, trust_ref=root.reference, subject=subject,
            request=request, decision=decision, expectation=expectation, role=role, expected_body=va,
            upstream=upstream, native_verifier=native, evidence=memory, association_ref=association.reference)
        verifier.authenticate.return_value = va
        verifier.evidence = memory
        return subject, expectation, record, other, designation, verifier, views, association

    def test_concrete_role_specific_prior_v0_with_exact_copies(self):
        for role in ("ADMISSION_PUBLICATION", "ADMISSION_CAS"):
            subject, x, record, _, d, verifier, _, _ = self.concrete(role)
            copied = p.RetainedEvidence(record.reference, bytes(bytearray(record.raw)))
            result = e.admission_provenance(role=role, subject=subject, expectation=x,
                sources=(record, copied), verifier=verifier, designation=d)
            self.assertEqual(result.provenance, record.reference)
            with self.assertRaises(e.EvidenceFailure):
                e.admission_provenance(role="ADMISSION_CAS" if role.endswith("PUBLICATION") else "ADMISSION_PUBLICATION",
                    subject=subject, expectation=x, sources=(record,), verifier=verifier, designation=d)

    def test_omitted_competing_e0_cannot_produce_v0(self):
        subject, x, record, other, d, verifier, _, _ = self.concrete(extra=True)
        for supplied in ((record,), (other,), (record, other)):
            with self.assertRaises(e.EvidenceFailure):
                e.admission_provenance(role="ADMISSION_PUBLICATION", subject=subject,
                    expectation=x, sources=supplied, verifier=verifier, designation=d)
        verifier.authenticate.assert_not_called()

    def test_missing_unknown_unauthenticated_and_inconsistent_completeness(self):
        for mode in ("missing", "unknown", "inconsistent", "unauthenticated"):
            _, _, record, _, d, _, views, association = self.concrete()
            if mode == "missing":
                d.association_ref = None
            elif mode == "unauthenticated":
                del views[association.reference]
            else:
                prior = views[association.reference]
                designation, _, refs = prior.value
                if mode == "inconsistent":
                    designation = (frozen.ref("wrong-T"),) + designation[1:]
                views[association.reference] = replace(prior,
                    value=(designation, "UNKNOWN" if mode == "unknown" else "ESTABLISHED", refs))
            with self.assertRaises(e.EvidenceFailure):
                d.authoritative_sources((record,))

    def test_conflicting_copies_identifier_digest_and_context_reject(self):
        _, _, record, other, d, _, _, _ = self.concrete()
        parsed, _, _, detached = e.envelope(record)
        changed = deepcopy(parsed)
        changed["context"]["scope_ref"] = ref("other-scope")
        changed["predecessor_refs"] = e.required_predecessors(changed)
        substituted = e.assemble(e.producer_bytes(changed, e.BODY_FIELDS), b"s" * 384,
                                 detached["subject_custody_ref"])
        conflicts = (other, substituted, replace(record, raw=record.raw + b" "),
                     replace(record, reference=frozen.ref("different-completed-reference")))
        for conflict in conflicts:
            with self.assertRaises(e.EvidenceFailure):
                d.authoritative_sources((record, conflict))


class SignedCorrespondenceTests(unittest.TestCase):
    def fixture(self):
        # Native request/result facts are retained and independently qualified;
        # constructor metadata is deliberately insufficient in every test.
        _, _, _, _, prior, _, _ = AdmissionMappingTests().source("ADMISSION_PUBLICATION")
        signed = body()
        value = ("actual-native-interpretation", frozen.ref("actual-obligation"))
        view = replace(prior, value=value)
        expected = (signed["receipt_role"], signed["subject_ref"], view.expectation,
            signed["context"], view.value, signed["details"], signed["stage"], signed["namespace"],
            signed["incarnation_id"], signed["configuration_ref"], signed["issuer_id"],
            signed["authority_id"], signed["provider_id"],
            (signed["request_id"], signed["request_ref"], signed["valid_from_us"], signed["valid_until_us"],
             signed["time_ref"], signed["qualification_ref"], signed["adoption_ref"]),
            (view.clock, view.valid_from_us, view.valid_until_us))
        proof = replace(view, reference=e.reference(signed["context"]["request_facts_ref"]), value=deepcopy(expected))
        class NativeFacts:
            def view(self, reference_):
                if not e.same(reference_, proof.reference):
                    raise e.EvidenceFailure("UNKNOWN_NATIVE_FACTS")
                return proof
        trust = e.ReceiptTrust(material=NativeFacts(), spki_records=(), associations=())
        return signed, view, trust

    def test_complete_signed_native_correspondence(self):
        signed, view, trust = self.fixture()
        trust.signed_correspondence(signed, view)

    def test_role_stage_context_lifecycle_native_obligation_substitution(self):
        for field in ("role", "stage", "context", "lifecycle", "native", "obligation", "reference", "validity", "request"):
            signed, view, trust = self.fixture()
            if field == "role": signed["receipt_role"] = "ADMISSION_CAS"
            elif field == "stage": signed["stage"] = "UPSTREAM_ONLY"
            elif field == "context": signed["context"]["scope_ref"] = ref("other-scope")
            elif field == "lifecycle": signed["context"]["activation_id"] = "other-lifecycle"
            elif field == "native": view = replace(view, value=("unrelated-native-view",))
            elif field == "obligation": signed["details"]["obligations"] = []
            elif field == "reference": signed["details"]["view_provenance_ref"] = ref("V1-is-not-P0")
            elif field == "validity": signed["valid_until_us"] = 999
            else: signed["request_ref"] = ref("unrelated-request")
            with self.assertRaises(e.EvidenceFailure):
                trust.signed_correspondence(signed, view)



class OriginalBootstrapRetentionTests(unittest.TestCase):
    """Existing supplied root + independent native proof, never a relabeled QF.

    The verifier below is an offline selected-verifier double. The actual
    candidate QualifiedMaterial and ReceiptTrust checks are exercised; this is
    source coverage, not operational trust-root/authentication certification.
    """
    def fixture(self, *, role="GOVERNANCE", approved_root=True, label="BOOTSTRAP_ROOT"):
        clients = importlib.import_module(frozen.PACKAGE + ".fixture_lease_authority_provider_clients")
        _, _, _, _, prior, _, _ = AdmissionMappingTests().source("ADMISSION_PUBLICATION")
        signed = body(role)
        raw = b"original externally approved bootstrap authority, not a returned receipt"
        subject = p.RetainedEvidence(p.s.EvidenceReference("supplied-original-root", sha256(raw).digest()), raw)
        signed["subject_ref"] = e.wire_ref(subject.reference)
        if role in e.ROLES[:8]:
            signed["details"]["view_subject_ref"] = signed["subject_ref"]
        signed["predecessor_refs"] = e.required_predecessors(signed)
        def record(name):
            raw = name.encode()
            return p.RetainedEvidence(p.s.EvidenceReference(name, sha256(raw).digest()), raw)
        anchor, provenance = record("independently-supplied-T"), record("independent-native-authentication")
        qualification = p.RetainedEvidence(e.reference(signed["qualification_ref"]), b"qualification_ref")
        arrangement = record("approved-finite-bootstrap-retention")
        scope = (signed["namespace"], signed["incarnation_id"], signed["authority_id"],
                 signed["provider_id"], signed["configuration_ref"], signed["stage"])
        # Existing frozen proof-reference role/representation, not an admission
        # qualification posing as bootstrap/control authority.
        expectation = replace(prior.expectation, role="view.claims.governance_target",
            context=(subject.reference,), obligations=p._COMMON)
        def view(r, value):
            return p.AuthenticatedView(r.reference, expectation, value, prior.clock, 0, 1000, provenance.reference)
        views = {subject.reference: view(subject, subject.reference),
                 qualification.reference: view(qualification,
                     (label, arrangement.reference, subject.reference, deepcopy(signed["context"]), scope)),
                 arrangement.reference: view(arrangement,
                     (label, subject.reference, len(subject.raw), deepcopy(signed["context"]), scope))}
        records = {r.reference: r for r in (subject, anchor, provenance, qualification, arrangement)}
        class Memory(p.EvidenceClient):
            def __init__(self): self.records = records
            def resolve(self, reference_): return self.records[reference_]
        class Native(p.EvidenceVerifier):
            def verify(self, record_, expectation_):
                actual = views[record_.reference]
                if not e.same(actual.expectation, expectation_):
                    raise e.EvidenceFailure("UNAUTHENTICATED_ROOT_ASSOCIATION")
                return actual
        material = clients.QualifiedMaterial(evidence=Memory(), verifier=Native(),
            records=tuple((records[r], v.expectation) for r, v in views.items()),
            roots=(anchor.reference, subject.reference) if approved_root else (anchor.reference,))
        trust = e.ReceiptTrust(material=material, spki_records=(), associations=())
        return signed, subject, views[qualification.reference], trust, views, arrangement

    def test_genuinely_original_approved_bootstrap_subject_accepts_exact_arrangement(self):
        signed, subject, control, trust, _, _ = self.fixture()
        self.assertEqual(signed["receipt_role"], "GOVERNANCE")
        self.assertIn(subject.reference, trust.material.roots)
        self.assertEqual(trust.material.view(subject.reference).value, subject.reference)
        trust.validate_control_retention(control, signed, subject)

    def test_ordinary_admissions_and_results_reject_even_control_looking_metadata(self):
        for role in ("ADMISSION_PUBLICATION", "ADMISSION_CAS", "RESULT_PUBLICATION", "RESULT_CAS",
                     "QUAL_APPROVAL", "INDEPENDENT_RESULT"):
            for label in ("CONTROL_EVIDENCE", "BOOTSTRAP_ROOT"):
                signed, subject, control, trust, _, _ = self.fixture(role=role, label=label)
                # Even stronger-looking metadata/root membership cannot exempt
                # an ordinary returned admission/qualification/result subject.
                with self.assertRaises(e.EvidenceFailure):
                    trust.validate_control_retention(control, signed, subject)

    def test_eligible_subject_wrong_arrangement_rejects(self):
        signed, subject, control, trust, views, arrangement = self.fixture()
        for value in ("generic-retention-success",
                      ("BOOTSTRAP_ROOT", frozen.ref("wrong-subject"), len(subject.raw), signed["context"], control.value[-1]),
                      ("BOOTSTRAP_ROOT", subject.reference, len(subject.raw) + 1, signed["context"], control.value[-1])):
            views[arrangement.reference] = replace(views[arrangement.reference], value=value)
            with self.assertRaises(e.EvidenceFailure):
                trust.validate_control_retention(control, signed, subject)

    def test_unauthenticated_subject_classification_or_association_rejects(self):
        for missing in ("subject", "qualification", "arrangement"):
            signed, subject, control, trust, views, arrangement = self.fixture()
            ref_ = subject.reference if missing == "subject" else control.reference if missing == "qualification" else arrangement.reference
            del views[ref_]
            with self.assertRaises(e.EvidenceFailure):
                # The helper itself must not trust a caller-constructed view.
                trust.validate_control_retention(control, signed, subject)
            with self.assertRaises(e.EvidenceFailure):
                actual = trust.material.view(control.reference)
                trust.validate_control_retention(actual, signed, subject)

    def test_classification_labels_cannot_create_an_approved_root(self):
        signed, subject, control, trust, _, _ = self.fixture(approved_root=False)
        with self.assertRaises(e.EvidenceFailure):
            trust.validate_control_retention(control, signed, subject)
        signed, subject, control, trust, _, _ = self.fixture(label="CONTROL_EVIDENCE")
        # Original external approval bytes are not the native control-ACK
        # representation either. A different label cannot change that fact.
        with self.assertRaises(e.EvidenceFailure):
            trust.validate_control_retention(control, signed, subject)

    def test_immutable_raw_retention_obligation_alone_rejects(self):
        signed, subject, control, trust, _, _ = self.fixture()
        self.assertIn("IMMUTABLE_RAW_RETENTION", control.expectation.obligations)
        with self.assertRaises(e.EvidenceFailure):
            trust.validate_control_retention(replace(control, value=subject.reference), signed, subject)

    def test_returned_envelope_is_not_original_control_even_if_listed_as_root(self):
        signed, subject, control, trust, views, arrangement = self.fixture()
        receipt = e.assemble(e.producer_bytes(body("ADMISSION_PUBLICATION"), e.BODY_FIELDS), b"s" * 384, ref("custody"))
        signed["subject_ref"] = e.wire_ref(receipt.reference)
        material = trust.material
        material.evidence.records[receipt.reference] = receipt
        source = replace(views[subject.reference], reference=receipt.reference, value=receipt.reference,
                         expectation=replace(views[subject.reference].expectation, context=(receipt.reference,)))
        views[receipt.reference] = source
        material.records += ((receipt, source.expectation),)
        material.roots += (receipt.reference,)
        control = replace(control, value=("BOOTSTRAP_ROOT", arrangement.reference, receipt.reference,
                                          signed["context"], control.value[-1]))
        views[control.reference] = control
        views[arrangement.reference] = replace(views[arrangement.reference],
            value=("BOOTSTRAP_ROOT", receipt.reference, len(receipt.raw), signed["context"], control.value[-1]))
        self.assertEqual(material.view(receipt.reference).value, receipt.reference)
        with self.assertRaises(e.EvidenceFailure):
            trust.validate_control_retention(control, signed, receipt)
