"""Offline IL6 certification with synthetic authorities and disposable storage.

No synthetic qualifier establishes operational qualification. Native fault tests
exercise fail-closed behavior; these tests do not certify hardware durability.
"""
from dataclasses import replace, fields
from hashlib import sha256
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch

import itertools
import unittest


def parameterize(names, values):
    names = tuple(names.split(","))
    def decorate(function):
        function._parameters = getattr(function, "_parameters", ()) + ((names, tuple(values)),)
        return function
    return decorate


def raises(exception):
    return unittest.TestCase().assertRaises(exception)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "_il6_activation_candidate"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "services/api/infrastructure")]
sys.modules[PACKAGE] = package
contract = importlib.import_module(PACKAGE + ".fixture_lease_contract")
sys.modules["fixture_lease_contract"] = contract
a = importlib.import_module(PACKAGE + ".fixture_lease_activation")
p, s, v = a.protocol, a.store, a.service

PROFILE = (ROOT / "docs/decisions/JOUS.CORE.1A.il6-authority-serialization-profile.md").read_text(encoding="utf-8")
# Exact retained committed bytes, including checkouts with CRLF conversion.
# cat-file reads only local objects: no refs/index mutation or remote operation.
AUTHORITY_BYTES = {role: subprocess.check_output(["git", "cat-file", "blob", blob], cwd=ROOT)
    for role, blob in (
        ("serialization_profile", "63dbed6ae575797da27d6a4ee3be03bb184256c3"),
        ("il6_contract", "ede5e09bf4bdb8461ac92d27da5ec9cb5683f21b"),
        ("genesis_reference_amendment", "d5136bc32ea8f62c04d09e65121edc00c0387d35"),
        ("bootstrap_amendment", "b2af73ae4788e76f4fd591ac267d40230d70026b"),
        ("provisioning_contract", "1d84df662ab0e7245f59842039789a55c1df25c4"))}


def vector(name):
    return re.search(r"### Vector " + name + r"\n\n~~~json\n([^\n]+)\n~~~", PROFILE)[1].encode("ascii")


def support(name):
    raw = re.search(r"### Support " + name + r" \([^\n]+\)\n\n~~~text\n([^\n]+)\n~~~", PROFILE)[1]
    return bytes.fromhex(raw) if name in ("S0", "C0") else raw.encode("ascii")


def ref(name):
    return v.EvidenceReference(name, sha256(("synthetic:" + name).encode()).digest())


@parameterize("name,cls,length,digest", [
    ("E", a.CeremonyEvidence, 4484, "43b0a6aecb7f3206a11b45dc34b179af4bc5f18520f88421f85f25857b86b31b"),
    ("P", a.ActivationPackage, 3128, "1e2096c9295e1835934b347093816995ec4583c7c7188712103d67a020589ba1"),
    ("ActivationPayload", a.ActivationPayload, 703, "42f289d46f332903b99d782e64eae0867365c43cec1fdc44a60d243f7b94cae8"),
])
def test_frozen_exact_vectors(name, cls, length, digest):
    raw = vector(name)
    assert len(raw) == length and sha256(raw).hexdigest() == digest
    record = a.decode_canonical(raw, cls)
    assert a.canonical_bytes(record) == raw
    assert a.content_reference(record).sha256 == digest


def test_existing_state_and_genesis_checkpoint_vectors():
    e = a.decode_canonical(vector("E"), a.CeremonyEvidence)
    projection, context = a.initial_projection(e)
    assert p.state_bytes(projection, context) == support("S0")
    assert a.genesis_checkpoint(e) == support("C0")
    normal = importlib.import_module(PACKAGE + ".fixture_lease_checkpoints")
    with raises(Exception):
        normal.decode_checkpoint(support("C0"))


REJECTIONS = [
    lambda b: b + b"\n",
    lambda b: b"\xef\xbb\xbf" + b,
    lambda b: b.replace(b'"profile_version":1', b'"profile_version":1.0', 1),
    lambda b: b.replace(b'"profile_version":1', b'"profile_version":true', 1),
    lambda b: b.replace(b'"profile_version":1', b'"profile_version":2', 1),
    lambda b: b.replace(b'"register_id":"g"', b'"register_id":"\\u0067"', 1),
    lambda b: b.replace(b'"register_id":"g"', b'"register_id":null', 1),
    lambda b: b'{"extra":0,' + b[1:],
    lambda b: b.replace(b'"register_id":"g"', b'"register_id":"g","register_id":"g"', 1),
    lambda b: b.replace(b'"creation_utc_us":0', b'"creation_utc_us":-0', 1),
    lambda b: b.replace(b'"object_type":"JOUS.CORE.1A.IL6.E","profile_version":1',
                       b'"profile_version":1,"object_type":"JOUS.CORE.1A.IL6.E"', 1),
    lambda b: b.replace(b'"creation_utc_us":0', b'"creation_utc_us":9223372036854775808', 1),
    lambda b: b.replace(b'"register_id":"g"', b'"register_id":"\\ud800"', 1),
]


@parameterize("index", range(13))
def test_frozen_rejection_vectors(index):
    raw = REJECTIONS[index](vector("E"))
    row = re.search(r"\| R%02d \|.*?\| (\d+) \| ([a-f0-9]{64}) \|" % (index + 1), PROFILE)
    assert len(raw) == int(row[1]) and sha256(raw).hexdigest() == row[2]
    with raises(a.ActivationRejected):
        a.decode_canonical(raw, a.CeremonyEvidence)


@parameterize("raw", [b"{}", b"[]", b"null", b"true", b"1", b"NaN", b"\xff"])
def test_malformed_canonical_objects(raw):
    with raises(a.ActivationRejected):
        a.decode_canonical(raw, a.CeremonyEvidence)


@parameterize("cls,name", [(a.CeremonyEvidence, "E"), (a.ActivationPackage, "P"), (a.ActivationPayload, "ActivationPayload")])
@parameterize("suffix", [b" ", b"{}", b"\xff", b"\r\n"])
def test_trailing_bytes_rejected(cls, name, suffix):
    with raises(a.ActivationRejected):
        a.decode_canonical(vector(name) + suffix, cls)


def test_string_primitive_and_no_normalization():
    e = a.decode_canonical(vector("E"), a.CeremonyEvidence)
    value = '"\\\n\x7f\u00e9\U0001f600'
    encoded = json.dumps(a._scalar(value, "ID"), ensure_ascii=True, separators=(",", ":")).encode()
    assert encoded.hex() == "225c225c5c5c6e5c75303037665c75303065395c75643833645c756465303022"
    assert len(encoded) == 32 and sha256(encoded).hexdigest() == "4151067b179bc79ace06b60e393941688adf793cd12bed78dac88361198d7eb5"
    assert a.canonical_bytes(replace(e, register_id="\u00e9")) != a.canonical_bytes(replace(e, register_id="e\u0301"))


@parameterize("change", [
    lambda g: g.upper(), lambda g: g + " ", lambda g: "Genesis" + g[7:], lambda g: g[:-1]])
def test_g_rejections(change):
    e = a.decode_canonical(vector("E"), a.CeremonyEvidence)
    g = a.content_reference(e)
    with raises(a.ActivationRejected):
        a.validate_ceremony_reference(replace(g, identity=change(g.identity)), e)


@parameterize("name,value", [("profile_version", True), ("profile_version", 2),
    ("register_id", ""), ("register_id", " " * 4), ("register_id", "x" * 256),
    ("register_id", "\ud800"), ("creation_utc_us", -(1 << 63) - 1),
    ("event_digest", "A" * 64), ("predecessor_checkpoint_digest", "1" * 64),
    ("issuer_generation", 2), ("purpose", "REPLACEMENT")])
def test_typed_bounds_and_constants(name, value):
    e = a.decode_canonical(vector("E"), a.CeremonyEvidence)
    with raises(a.ActivationRejected):
        a.canonical_bytes(replace(e, **{name: value}))


class SyntheticStorage(a.NativeStorage):
    """Explicit test-only substitute for independently qualified native exclusion
    and directory durability. Actual exclusive create/SQLite/readback/no-overwrite
    operate on disposable files. This substitute NEVER qualifies a real host.
    """
    def __init__(self, fault=None):
        super().__init__()
        self.calls = []
        self.fault = fault

    def acquire(self, location):
        self.calls.append("acquire")
        self.check(location, staging_exists=False)
        self._location, self._lock = location, "synthetic-exclusion"

    def flush_directory(self):
        self.calls.append("flush")
        if self.fault == "flush":
            raise OSError("synthetic flush uncertainty")

    def acquire_existing(self, location, native_identity):
        self.calls.append("acquire_existing")
        self.check_existing(location, native_identity)
        self._location, self._lock = location, "synthetic-exclusion"

    def publish(self, receipt):
        self.calls.append("publish")
        self.check(receipt.request.location, staging_exists=True)
        assert self.readback(receipt.request, receipt.native_identity) == receipt.database_sha256
        if self.fault == "rename":
            raise OSError("synthetic publication uncertainty")
        # Same-inode atomic no-replace namespace publication; only test evidence.
        os.link(receipt.request.location.staging, receipt.request.location.final)
        os.unlink(receipt.request.location.staging)
        self.flush_directory()
        assert self.readback(receipt.request, receipt.native_identity, final=True) == receipt.database_sha256

    def close(self):
        self.calls.append("close")
        self._lock = None


class SyntheticQualification(a.QualificationAdapter):
    def __init__(self, bindings):
        self.bindings = bindings
        self.calls = []
        self.fail = None
        self.request = None

    def package(self, snapshot):
        self.calls.append("package")
        if self.fail == "package":
            raise a.ActivationRejected("synthetic unqualified")
        assert self.request is not None
        request = self.request
        native = request.location.staging if request.location.staging.exists() else request.location.final
        info = native.stat()  # Test qualifier never attests preparation before it exists.
        native_identity = (info.st_dev, info.st_ino)
        accepted = a._validate_snapshot(snapshot)
        e, pack = accepted.evidence, accepted.package
        creation = a.CreationClaims(e.creation_evidence, "GENESIS_V1", e.register_id, e.schema,
            1, e.activation_id, e.host, e.storage, e.scope, e.actors.preparation_operator,
            request.authorization, e.creation_utc_us, e.clock, a.initial_projection(e)[0].metadata,
            native_identity, "PREPARED_NON_AUTHORITATIVE", "UPSTREAM_ONLY")
        storage = a.StorageClaims(e.storage, request.location, native_identity, "synthetic-account",
            ref("effective-access"), e.actors.issuer, e.actors.process, e.host.identity,
            ref("native-continuity"), ref("locking-flush-vfs"), ref("durability"),
            "QUALIFIED_DURABLE_LOCAL", "EXCLUSIVE_IDENTITY_CONTINUITY")
        claims = a.PackageClaims(creation=creation, schema=e.schema, host=e.host,
            host_authentication=ref("host-authentication"), storage=storage, scope=e.scope,
            governance_target=ref("governance-target"), scope_justification=ref("scope-justification"),
            actors=e.actors, actor_role_action_validity=ref("actor-roles"), clock=e.clock,
            authorities=tuple(a.AuthorityClaims(field.name, getattr(e.authorities, field.name),
                "synthetic-v1", ref("adoption:" + field.name), e.scope) for field in fields(e.authorities)),
            representation=e.representation, generation_selection=ref("generation-selection"),
            software=pack.software, host_vfs_compatibility=ref("host-vfs"),
            protected_authorities=pack.protected_authorities, protected_trust_scope=ref("protected-scope"),
            absence="AUTHORITATIVE_ABSENT", linearizable_cas=ref("linearizable-cas"),
            history_tombstones=ref("history-tombstones"), original_command_outcomes=ref("original-outcomes"),
            requirements=pack.requirements, requirement_applicability=ref("requirement-applicability"),
            authorization=pack.authorization, authorization_register_id=e.register_id,
            authorization_activation_id=e.activation_id, authorization_command_id=e.activation_command_id,
            authorization_host=e.host.identity, authorization_operator=e.actors.genesis_operator,
            authorization_action="GENESIS", upstream_dependency_stage="UPSTREAM_ONLY")
        return replace(self.bindings, snapshot=snapshot, claims=claims)

    def approval(self, accepted, approval, clock):
        self.calls.append("approval")
        return approval

    def creation(self, request, native_identity, state, database_sha256):
        self.calls.append("creation")
        e = a.decode_canonical(self.bindings.snapshot.ceremony, a.CeremonyEvidence)
        claims = a.CreationClaims(e.creation_evidence, "GENESIS_V1", e.register_id, e.schema,
            1, e.activation_id, e.host, e.storage, e.scope, e.actors.preparation_operator,
            request.authorization, e.creation_utc_us, e.clock, a.initial_projection(e)[0].metadata,
            native_identity, "PREPARED_NON_AUTHORITATIVE", "UPSTREAM_ONLY")
        return a.QualifiedCreation(a.OpaqueEvidence("C", e.creation_evidence, support("C"),
            ref("C-qualification")), claims, ref("creation-provenance"))

    def preparation(self, request):
        self.calls.append("preparation")
        if self.fail == "preparation":
            raise a.ActivationRejected("synthetic preparation denied")
        e = a.decode_canonical(self.bindings.snapshot.ceremony, a.CeremonyEvidence)
        return a.QualifiedPreparation(request, ref("absence"), ref("storage"), ref("actor"),
            request.authorization, 0, 1000000, ref("preparation-qualification"),
            e.actors.preparation_operator, e.actors.process, e.actors.issuer, "PREPARE_GENESIS",
            "AUTHORITATIVE_ABSENT", "NO_PRIOR_OR_INFLIGHT_ATTEMPT")

    def execution(self, request):
        self.calls.append("execution")
        if self.fail == "execution":
            raise a.ActivationRejected("synthetic execution denied")
        e = a.decode_canonical(request.snapshot.ceremony, a.CeremonyEvidence)
        return a.QualifiedExecution(request, ref("fresh-absence"), ref("storage"), ref("actor"),
            request.authorization, 0, 1000000, ref("execution-qualification"), request.clock,
            e.actors.genesis_operator, e.actors.process, e.actors.issuer, "EXECUTE_ORIGINAL_GENESIS",
            "AUTHORITATIVE_ABSENT", "ORIGINAL_UNATTEMPTED_K")

    def opening(self, request):
        self.calls.append("opening")
        if self.fail == "opening":
            raise a.ActivationRejected("synthetic opening denied")
        return a.QualifiedOpen(request, request.original_result, sha256(request.snapshot.state).digest(),
            0, p.GENESIS_EVENT_DIGEST, ref("current-checkpoint"), ref("history"), ref("storage"),
            ref("actor"), ref("independent-result-verification"), ref("fresh-clock"), ref("open-qualification"),
            request.clock, request.opener, request.issuer, request.clock.current.process_id,
            "VERIFIED_CURRENT_NO_UNRESOLVED_OUTCOME")


class SyntheticProtected(a.ProtectedGenesis):
    def __init__(self, request, fault=None):
        self.calls, self.request, self.fault = [], request, fault

    def publish_checkpoint(self, snapshot, approval, authorization):
        self.calls.append("checkpoint")
        if self.fault == "checkpoint":
            raise OSError("synthetic unknown publication")
        accepted = a._validate_snapshot(snapshot)
        return a.CheckpointResult("synthetic-original-publication", accepted.package.checkpoint,
            a.content_reference(accepted.package), approval.evidence.reference, accepted.evidence.host.identity,
            "CONFIRMED", ref("checkpoint-result"))

    def activate_absent(self, payload, publication, absence, authorization):
        self.calls.append("cas")
        if self.fault == "cas":
            raise OSError("synthetic unknown CAS")
        record = a.decode_canonical(payload, a.ActivationPayload)
        self.result = a.ActivationResult(record.activation_command_id, sha256(payload).digest(), record.package,
            record.checkpoint, record.approval, record.register_id, 1, record.activation_id,
            record.host_identity, "CONFIRMED", ref("activation-result"))
        return self.result

    def readback(self, result):
        self.calls.append("readback")
        if self.fault == "readback":
            raise OSError("synthetic unknown readback")
        return replace(result, evidence=ref("activation-readback"))


def fixture():
    with tempfile.TemporaryDirectory(prefix="jous-synthetic-il6-") as directory:
        e = a.decode_canonical(vector("E"), a.CeremonyEvidence)
        e = replace(e, schema=replace(e.schema, reference=replace(e.schema.reference,
                    sha256=sha256(s.SCHEMA_SQL.encode()).hexdigest())))
        e = replace(e, authorities=replace(e.authorities, **{role:
            replace(getattr(e.authorities, role), sha256=sha256(raw).hexdigest())
            for role, raw in AUTHORITY_BYTES.items()}))
        initial, context = a.initial_projection(e)
        state = p.state_bytes(initial, context)
        e = replace(e, initial_state=replace(e.initial_state, sha256=sha256(state).hexdigest()))
        checkpoint = a.genesis_checkpoint(e)
        pack = a.decode_canonical(vector("P"), a.ActivationPackage)
        pack = replace(pack, ceremony_evidence=a.content_reference(e), initial_state=e.initial_state,
            checkpoint=replace(pack.checkpoint, sha256=sha256(checkpoint).hexdigest()))
        snapshot = a.PackageSnapshot(a.canonical_bytes(e), a.canonical_bytes(pack), state, checkpoint)
        opaque = []
        excluded = {"E.initial_state", "P.initial_state", "P.ceremony_evidence", "P.checkpoint"}
        for root, record in (("E", e), ("P", pack)):
            for role, reference in a._references(record, root):
                if role in excluded:
                    continue
                if role == "E.schema.reference":
                    raw = s.SCHEMA_SQL.encode()
                elif role in ("E.creation_evidence", "P.creation_evidence"):
                    raw = support("C")
                elif role.startswith("E.authorities.") and role.rsplit(".", 1)[1] in AUTHORITY_BYTES:
                    raw = AUTHORITY_BYTES[role.rsplit(".", 1)[1]]
                else:
                    raw = ("synthetic-external:" + reference.identity).encode()
                assert sha256(raw).hexdigest() == reference.sha256
                opaque.append(a.OpaqueEvidence(role, reference, raw, ref("qualification:" + role)))
        er = lambda r: v.EvidenceReference(r.identity, bytes.fromhex(r.sha256))
        profile = v.QualifiedClockProfile(er(e.clock.profile), e.clock.source, er(e.clock.qualification),
                                          1000000000, 1000000, 0, 0)
        sample = v.QualifiedSample(er(e.clock.sample), e.clock.source, profile.profile,
            ref("clock-validation"), v.UtcInterval(0, 0), v.MonotonicPoint(e.actors.process, e.clock.monotonic_domain, 0))
        clock = a.TimeBinding(profile, sample, sample.anchor,
            v.QualifiedPropagationError(sample.sample, profile.profile, 0, 0, ref("propagation")))
        bindings = a.QualifiedPackageBindings(snapshot, tuple(opaque), s.SCHEMA_SQL.encode(), profile,
                                               sample, ref("package-qualification"), None)
        qualifier = SyntheticQualification(bindings)
        parent = Path(directory).resolve()
        info = parent.stat()
        location = a.StorageLocation(parent / "synthetic-final.sqlite", parent / "synthetic-staging.sqlite",
            info.st_dev, info.st_ino, e.host.identity, e.storage.identity, "synthetic-exclusive-issuer")
        md = s.MetadataRow(1, 1, e.register_id, 1, e.activation_id,
            *(getattr(initial.metadata, key) for key in ("fixture_plan_sha256", "bootstrap_amendment_sha256",
                                                      "provisioning_contract_sha256", "design_sha256")),
            0, p.GENESIS_EVENT_DIGEST, sha256(state).digest(), 0, 0)
        request = a.PreparationRequest(e.register_id, e.activation_id, e.activation_command_id,
            e.approval_id, md, context, location, clock, ref("preparation-authorization"))
        qualifier.request = request
        qraw = b"synthetic opaque Q; deliberately not JSON"
        qref = a.Reference(e.approval_id, sha256(qraw).hexdigest())
        approval = a.ApprovalView(a.OpaqueEvidence("Q", qref, qraw, ref("Q-qualification")),
            a.content_reference(pack), pack.checkpoint, e.register_id, 1, e.activation_id, e.host.identity,
            e.activation_command_id, "synthetic-independent-approver", e.actors.genesis_operator,
            e.actors.issuer, ref("independence"), ref("authority"), ref("approval-authorization"),
            ref("not-revoked"), ref("validity-observation"), 0, 1000000, "APPROVED_GENESIS")
        native = SyntheticStorage()
        yield types.SimpleNamespace(e=e, p=pack, snapshot=snapshot, q=qualifier, request=request,
                                    native=native, clock=clock, approval=approval)
        native.close()


def prepared(f):
    result = a.prepare_register(f.request, qualification=f.q, storage=f.native)
    assert result.cause is None, repr(result.cause)
    assert result.reached is a.Reached.PREPARED_NON_AUTHORITATIVE
    return result.receipt


def execution(f, receipt):
    return a.ExecutionRequest(f.snapshot, receipt, f.approval, ref("execution-authorization"), f.clock)


def test_complete_synthetic_phases_and_open(fixture):
    f = fixture
    receipt = prepared(f)
    accepted = a.validate_genesis_package(f.snapshot, f.q.package(f.snapshot))
    assert not f.request.location.final.exists()
    request = execution(f, receipt)
    protected = SyntheticProtected(request)
    result = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
    assert result.cause is None, repr(result.cause)
    assert result.reached is a.Reached.READBACK_CONFIRMED_VERIFICATION_PENDING
    assert result.recovery_only  # Independent verification remains a separate gate.
    assert protected.calls == ["checkpoint", "cas", "readback"]
    assert f.request.location.final.exists() and not f.request.location.staging.exists()
    raw = b"synthetic independent result verification"
    verification = a.OpaqueEvidence("INDEPENDENT_RESULT_VERIFICATION",
        a.Reference("synthetic-verification", sha256(raw).hexdigest()), raw, ref("verification-qualification"))
    opening = a.OpenRequest(f.snapshot, f.request.location, receipt.native_identity, f.approval,
        protected.result, verification, f.clock, f.e.actors.opener, f.e.actors.issuer)
    opened = a.open_authoritative_register(opening, qualification=f.q, storage=f.native)
    assert opened.cause is None, repr(opened.cause)
    assert opened.reached is a.Reached.OPEN_VALIDATED
    assert not hasattr(opened.receipt, "transaction")
    opened.receipt.close()
    assert a.content_reference(accepted.package) == f.approval.package


def test_defaults_and_constructors_do_not_create(fixture):
    f = fixture
    with raises(a.ActivationRejected):
        a.validate_genesis_package(f.snapshot)
    result = a.prepare_register(f.request)
    assert result.reached is a.Reached.REJECTED
    assert not f.request.location.staging.exists() and not f.request.location.final.exists()
    a.NativeStorage()
    a.GenesisAttempt()
    assert not f.request.location.staging.exists()


@parameterize("which", ["staging", "final"])
def test_existing_target_not_overwritten(fixture, which):
    f = fixture
    target = getattr(f.request.location, which)
    target.write_bytes(b"synthetic existing bytes")
    result = a.prepare_register(f.request, qualification=f.q, storage=f.native)
    assert result.cause is not None
    assert target.read_bytes() == b"synthetic existing bytes"


def test_preparation_authority_denial_has_no_effect(fixture):
    f = fixture
    f.q.fail = "preparation"
    result = a.prepare_register(f.request, qualification=f.q, storage=f.native)
    assert result.reached is a.Reached.REJECTED and not f.native.calls
    assert not f.request.location.staging.exists()


@parameterize("field,value", [("register_id", "other"), ("issuer_generation", 2),
    ("activation_id", "other"), ("recovery_required", 1), ("last_event_sequence", 1),
    ("last_event_digest", b"x" * 32), ("state_digest", b"x" * 32)])
def test_bad_initial_metadata_rejected_before_creation(fixture, field, value):
    f = fixture
    request = replace(f.request, metadata=replace(f.request.metadata, **{field: value}))
    result = a.prepare_register(request, qualification=f.q, storage=f.native)
    assert result.reached is a.Reached.REJECTED and not f.native.calls


@parameterize("field,value", [("register_id", "other"), ("activation_id", "other"),
    ("activation_command_id", "other"), ("approval_id", "other")])
def test_package_cross_binding_mismatch(fixture, field, value):
    f = fixture
    bad = replace(f.p, **{field: value})
    with raises(a.ActivationRejected):
        a.validate_genesis_package(replace(f.snapshot, package=a.canonical_bytes(bad)))


@parameterize("fault,expected,calls", [
    ("checkpoint", a.Reached.CHECKPOINT_ATTEMPTED, ["checkpoint"]),
    ("cas", a.Reached.CAS_ATTEMPTED, ["checkpoint", "cas"]),
    ("readback", a.Reached.CAS_CONFIRMED_VERIFICATION_PENDING, ["checkpoint", "cas", "readback"]),
])
def test_uncertainty_preserves_floor_and_prevents_retry(fixture, fault, expected, calls):
    f = fixture
    receipt = prepared(f)
    request = execution(f, receipt)
    protected = SyntheticProtected(request, fault)
    result = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
    assert result.reached is expected and result.recovery_only and isinstance(result.cause, OSError)
    assert protected.calls == calls
    for guard in (receipt.attempt, a.GenesisAttempt()):
        again = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=guard)
        assert again.cause is not None and protected.calls == calls


@parameterize("field,value", [("status", "PENDING"), ("generation", 2),
    ("activation_id", "other"), ("activation_command_id", "other"), ("valid_until_us", -1)])
def test_bad_approval_never_publishes(fixture, field, value):
    f = fixture
    receipt = prepared(f)
    request = replace(execution(f, receipt), approval=replace(f.approval, **{field: value}))
    protected = SyntheticProtected(request)
    result = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
    assert result.reached is a.Reached.REJECTED and not protected.calls
    assert not f.request.location.final.exists()


def test_self_approval_rejected_and_q_never_parsed(fixture):
    f = fixture
    prepared(f)
    accepted = a.validate_genesis_package(f.snapshot, f.q.package(f.snapshot))
    view = f.approval
    original_loads = a.json.loads
    def reject_q(raw, *args, **kwargs):
        assert raw not in (view.evidence.raw, view.evidence.raw.decode()), "Q must remain opaque"
        return original_loads(raw, *args, **kwargs)
    with patch.object(a.json, "loads", reject_q):
        payload = a.activation_payload(accepted, view, f.clock, f.q)
        assert payload.approval.sha256 == sha256(view.evidence.raw).hexdigest()
        with raises(a.ActivationRejected):
            a.activation_payload(accepted, replace(view, approver=view.issuer), f.clock, f.q)
        with patch.object(f.q, "approval", return_value=True):
            with raises(a.ActivationRejected):
                a.activation_payload(accepted, view, f.clock, f.q)


def test_missing_opaque_qualification_rejected(fixture):
    f = fixture
    prepared(f)
    f.q.bindings = replace(f.q.bindings, opaque=f.q.bindings.opaque[:-1])
    with raises(a.ActivationRejected):
        a.validate_genesis_package(f.snapshot, f.q.package(f.snapshot))


def test_wrong_opaque_raw_digest_rejected(fixture):
    f = fixture
    prepared(f)
    first, *rest = f.q.bindings.opaque
    f.q.bindings = replace(f.q.bindings, opaque=(replace(first, raw=b"other"), *rest))
    with raises(a.ActivationRejected):
        a.validate_genesis_package(f.snapshot, f.q.package(f.snapshot))


@parameterize("mutation", ["backward", "domain", "expired", "uncertain"])
def test_clock_fail_closed(fixture, mutation):
    f = fixture
    clock = f.clock
    if mutation == "backward":
        clock = replace(clock, sample=replace(clock.sample,
            anchor=replace(clock.sample.anchor, ticks_ns=1)))
    elif mutation == "domain":
        clock = replace(clock, current=replace(clock.current, domain_id="other"))
    elif mutation == "expired":
        clock = replace(clock, current=replace(clock.current, ticks_ns=2000000000))
    else:
        clock = replace(clock, error=replace(clock.error, error_ns=1))
    request = replace(f.request, clock=clock)
    result = a.prepare_register(request, qualification=f.q, storage=f.native)
    assert result.reached is a.Reached.REJECTED and not f.native.calls


def test_missing_normal_store_does_not_create(fixture):
    path = fixture.request.location.final.parent / "missing" / "register.sqlite"
    with raises(s.StorageRejected):
        s.LeaseStore(path, "synthetic-register")
    assert not path.parent.exists()


def test_import_has_no_storage_or_external_effects():
    spec = importlib.util.spec_from_file_location(PACKAGE + ".activation_import_probe",
        ROOT / "services/api/infrastructure/fixture_lease_activation.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.object(sqlite3, "connect", side_effect=AssertionError("import SQLite")), \
         patch.object(os, "open", side_effect=AssertionError("import native open")):
        spec.loader.exec_module(module)


def test_path_and_parent_mismatch_fail_closed(fixture):
    f = fixture
    bad = replace(f.request, location=replace(f.request.location, parent_inode=-1))
    result = a.prepare_register(bad, qualification=f.q, storage=f.native)
    assert result.cause is not None and not f.request.location.staging.exists()


def test_schema_fault_retains_non_authoritative_remnant(fixture):
    f = fixture
    with patch.object(a.sqlite3, "connect", side_effect=OSError("synthetic initialization crash")):
        result = a.prepare_register(f.request, qualification=f.q, storage=f.native)
    assert result.reached is a.Reached.PREPARATION_ATTEMPTED and result.recovery_only
    assert f.request.location.staging.exists() and not f.request.location.final.exists()
    again = a.prepare_register(f.request, qualification=f.q, storage=f.native)
    assert again.cause is not None


def test_native_unsupported_flush_fails_before_creation(fixture):
    f = fixture
    native = a.NativeStorage()
    try:
        with patch.object(native, "flush_directory", side_effect=OSError("unqualified directory durability")):
            result = a.prepare_register(f.request, qualification=f.q, storage=native)
        assert result.cause is not None and not f.request.location.staging.exists()
    finally:
        try:
            native.close()
        except a.ActivationRejected:
            pass  # Preserve failed native setup; never claim cleanup proved durability.


@parameterize("name,cls", [("E", a.CeremonyEvidence), ("P", a.ActivationPackage),
                           ("ActivationPayload", a.ActivationPayload)])
def test_every_required_top_level_field_is_required(name, cls):
    original = json.loads(vector(name))
    for field in original:
        values = original.copy()
        del values[field]
        with raises(a.ActivationRejected):
            a.decode_canonical(json.dumps(values, separators=(",", ":")).encode(), cls)
        values = original.copy()
        values[field] = None
        with raises(a.ActivationRejected):
            a.decode_canonical(json.dumps(values, separators=(",", ":")).encode(), cls)


@parameterize("name,cls", [("E", a.CeremonyEvidence), ("P", a.ActivationPackage)])
@parameterize("forbidden", ["approval", "activation_payload", "activation_payload_sha256", "self_sha256", "outcome"])
def test_no_downstream_package_or_ceremony_fields(name, cls, forbidden):
    values = json.loads(vector(name))
    values[forbidden] = "forbidden"
    with raises(a.ActivationRejected):
        a.decode_canonical(json.dumps(values, separators=(",", ":")).encode(), cls)


@parameterize("stage", ["create", "schema", "insert", "commit", "close", "flush", "readback"])
def test_preparation_fault_boundaries_retain_fencing_and_remnants(fixture, stage):
    f = fixture
    original_connect = sqlite3.connect

    class FaultConnection:
        def __init__(self, *args, **kwargs):
            self.connection = original_connect(*args, **kwargs)

        def enable_load_extension(self, flag):
            return self.connection.enable_load_extension(flag)

        def execute(self, sql, parameters=()):
            if (stage == "schema" and sql.startswith("CREATE TABLE")) or \
               (stage == "insert" and sql.startswith("INSERT INTO")) or \
               (stage == "commit" and sql == "COMMIT"):
                raise OSError("synthetic " + stage + " uncertainty")
            return self.connection.execute(sql, parameters)

        def close(self):
            self.connection.close()
            if stage == "close":
                raise OSError("synthetic close uncertainty")

    from contextlib import ExitStack
    with ExitStack() as stack:
        if stage in ("schema", "insert", "commit", "close"):
            stack.enter_context(patch.object(a.sqlite3, "connect", FaultConnection))
        elif stage == "create":
            stack.enter_context(patch.object(f.native, "create", side_effect=OSError("synthetic exclusive-create uncertainty")))
        elif stage == "flush":
            f.native.fault = "flush"
        else:
            stack.enter_context(patch.object(f.native, "readback", side_effect=OSError("synthetic readback uncertainty")))
        result = a.prepare_register(f.request, qualification=f.q, storage=f.native)
    assert result.cause is not None and result.recovery_only
    assert result.reached is a.Reached.PREPARATION_ATTEMPTED
    assert not f.request.location.final.exists()
    if stage != "create":
        assert f.request.location.staging.exists()  # No automatic cleanup/reinitialization.


def test_uncertain_rename_cannot_be_retried(fixture):
    f = fixture
    receipt = prepared(f)
    f.native.fault = "rename"
    request = execution(f, receipt)
    protected = SyntheticProtected(request)
    first = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
    assert first.reached is a.Reached.FILE_PUBLICATION_ATTEMPTED and first.recovery_only
    f.native.fault = None
    second = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
    assert second.cause is not None and not protected.calls
    assert f.native.calls.count("publish") == 1


def test_callback_mutation_fences_before_publication(fixture):
    f = fixture
    receipt = prepared(f)
    request = execution(f, receipt)
    protected = SyntheticProtected(request)
    original = f.q.execution
    def mutate(value):
        result = original(value)
        object.__setattr__(value, "authorization", ref("substituted-authorization"))
        return result
    with patch.object(f.q, "execution", mutate):
        result = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
    assert result.cause is not None and not protected.calls
    assert not f.request.location.final.exists()


@parameterize("field,value", [("absence", "UNKNOWN"), ("upstream_dependency_stage", "DEPENDS_ON_Q"),
    ("authorization_operator", "other"), ("authorization_action", "FIXTURE_PROVISIONING")])
def test_qualified_claim_mismatch_rejected(fixture, field, value):
    f = fixture
    prepared(f)
    original = f.q.package
    def mismatch(snapshot):
        qualified = original(snapshot)
        return replace(qualified, claims=replace(qualified.claims, **{field: value}))
    with patch.object(f.q, "package", mismatch):
        with raises(a.ActivationRejected):
            a.validate_genesis_package(f.snapshot, f.q.package(f.snapshot))


@parameterize("field,value", [("operator", "other"), ("process", "other"), ("issuer", "other"),
    ("presence", "UNKNOWN"), ("original_history", "UNCERTAIN"), ("action", "NORMAL_COMMAND")])
def test_execution_qualification_rejection(fixture, field, value):
    f = fixture
    receipt = prepared(f)
    request = execution(f, receipt)
    protected = SyntheticProtected(request)
    original = f.q.execution
    with patch.object(f.q, "execution", lambda request: replace(original(request), **{field: value})):
        result = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
    assert result.reached is a.Reached.REJECTED and not protected.calls
    assert not f.request.location.final.exists()


def activated(f):
    receipt = prepared(f)
    request = execution(f, receipt)
    protected = SyntheticProtected(request)
    result = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
    assert result.cause is None
    raw = b"synthetic independent result verification"
    verification = a.OpaqueEvidence("INDEPENDENT_RESULT_VERIFICATION",
        a.Reference("synthetic-verification", sha256(raw).hexdigest()), raw, ref("verification-qualification"))
    return a.OpenRequest(f.snapshot, f.request.location, receipt.native_identity, f.approval,
        protected.result, verification, f.clock, f.e.actors.opener, f.e.actors.issuer)


@parameterize("fault", ["opener", "issuer", "payload", "recovery", "schema", "pin", "state", "head", "missing", "uncertain", "copied"])
def test_existing_open_rejects_mismatch_without_repair(fixture, fault):
    f = fixture
    request = activated(f)
    path = f.request.location.final
    if fault in ("opener", "issuer"):
        request = replace(request, **{fault: "other"})
    elif fault == "payload":
        request = replace(request, original_result=replace(request.original_result, payload_sha256=b"x" * 32))
    elif fault in ("recovery", "schema", "pin", "state", "head"):
        connection = sqlite3.connect(path)
        try:
            if fault == "schema":
                connection.execute("CREATE TABLE unauthorized (value TEXT)")
            elif fault == "recovery":
                connection.execute("UPDATE REGISTER_METADATA SET recovery_required=1")
            elif fault == "pin":
                connection.execute("UPDATE REGISTER_METADATA SET design_sha256=?", (b"x" * 32,))
            elif fault == "state":
                connection.execute("UPDATE REGISTER_METADATA SET state_digest=?", (b"x" * 32,))
            else:
                connection.execute("UPDATE REGISTER_METADATA SET last_event_sequence=1")
            connection.commit()
        finally:
            connection.close()
    elif fault == "missing":
        request = replace(request, location=replace(request.location, final=path.parent / "missing.sqlite"))
    elif fault == "uncertain":
        f.q.fail = "opening"
    else:
        copy = path.parent / "synthetic-copy.sqlite"
        copy.write_bytes(path.read_bytes())
        request = replace(request, location=replace(request.location, final=copy))
    before = path.read_bytes()
    result = a.open_authoritative_register(request, qualification=f.q, storage=f.native)
    assert result.cause is not None and result.recovery_only
    assert path.read_bytes() == before  # No repair, flag clearing or migration.


def test_handle_requalifies_and_fences_on_later_uncertainty(fixture):
    f = fixture
    request = activated(f)
    opened = a.open_authoritative_register(request, qualification=f.q, storage=f.native)
    assert opened.cause is None
    handle = opened.receipt
    assert handle.read_rows(s.EventRow) == ()
    f.q.fail = "opening"
    with raises(a.ActivationRejected):
        handle.read_rows(s.MetadataRow)
    f.q.fail = None
    with raises(a.ActivationRejected):
        handle.read_rows(s.MetadataRow)
    handle.close()


def test_initial_all_nonmetadata_tables_empty_and_no_runtime_interfaces(fixture):
    f = fixture
    receipt = prepared(f)
    handle = s.LeaseStore(f.request.location.staging, f.e.register_id)
    try:
        for cls in s.SPECS:
            rows = handle.read_rows(cls)
            assert len(rows) == (1 if cls is s.MetadataRow else 0)
    finally:
        handle.close()
    assert receipt.state == f.snapshot.state
    assert not any(name in vars(a) for name in ("main", "app", "router", "supabase", "canary", "provision_fixtures"))


def test_normal_history_open_reuses_frozen_state_event_command_and_claim_validation(fixture):
    f = fixture
    request = activated(f)
    c = contract
    def artifact(name, kind):
        raw, approval = ("synthetic-artifact:" + name).encode(), ("synthetic-approval:" + name).encode()
        return s.ArtifactRow(name, kind, raw, sha256(raw).digest(), approval, sha256(approval).digest(),
            "synthetic-approver", "authorization", c.Operation.FIXTURE_PROVISIONING, c.Phase.PRE_AUTH, None)
    binding = artifact("binding", c.ArtifactType.PROVISIONING_REQUEST)
    authorization = artifact("authorization", c.ArtifactType.AUTHORIZATION)
    reference = lambda row: p.Reference(row.artifact_id, row.artifact_type, row.sha256)
    handle = s.LeaseStore(f.request.location.final, f.e.register_id)
    try:
        with handle.transaction() as writer:
            writer.insert(binding)
            writer.insert(authorization)
        command = p.CommandPayload(c.Command.ACQUIRE, "synthetic-owner", f.e.register_id, 1,
            f.e.activation_id, "synthetic-normal-command", "", 0, c.Operation.FIXTURE_PROVISIONING,
            c.Phase.PRE_AUTH, binding.artifact_type, binding.sha256, "synthetic-fixture-set",
            reference(binding), binding.approval_record_hash, reference(authorization), (),
            p.Parameters("synthetic-reservation", None, reference(binding), None, None, (), 100, 90, None))
        raw = b"synthetic-immutable-database-projection"
        reservation = s.ReservationRow("synthetic-reservation", f.e.register_id, "synthetic-fixture-set",
            c.Operation.FIXTURE_PROVISIONING, c.Phase.PRE_AUTH, binding.artifact_type, binding.artifact_id,
            binding.sha256, raw, sha256(raw).digest(), "synthetic-owner", "authorization", 0, 0, 0,
            100, 90, 0, c.LeaseStatus.LEASED, 0, s.ExecutionState.NOT_STARTED, None, None, None)
        key = c.ConflictKey.fixture_set(c.DatabaseTargetScope(f.e.register_id), "synthetic-fixture-set").canonical_bytes
        claim = s.ClaimRow(key, reservation.reservation_id, 0, binding.artifact_id)
        material = a.commands.PreparedTransition(reservation, (claim,), (), 0, 0)
        a.commands.complete(handle, command, f.request.context, material)
        metadata = handle.read_rows(s.MetadataRow)[0]
        assert metadata.last_event_sequence == 3 and metadata.state_digest != f.request.metadata.state_digest
    finally:
        handle.close()
    original = f.q.opening
    def current(open_request):
        return replace(original(open_request), checkpoint_state_sha256=metadata.state_digest,
            event_sequence=metadata.last_event_sequence, event_digest=metadata.last_event_digest,
            current_checkpoint=ref("synthetic-current-normal-checkpoint"))
    with patch.object(f.q, "opening", current):
        result = a.open_authoritative_register(request, qualification=f.q, storage=f.native)
        assert result.cause is None, repr(result.cause)
        assert len(result.receipt.read_rows(s.EventRow)) == 3
        result.receipt.close()


@parameterize("exists", [False, True])
def test_actual_native_no_replace_primitive_and_identity(fixture, exists):
    f = fixture
    receipt = prepared(f)
    location = f.request.location
    if exists:
        location.final.write_bytes(b"synthetic competing target")
    descriptor = None
    try:
        if os.name != "nt":
            descriptor = os.open(location.final.parent, os.O_RDONLY | os.O_DIRECTORY)
        if exists:
            with raises(a.ActivationRejected):
                a.NativeStorage._no_replace(location, descriptor)
            assert location.final.read_bytes() == b"synthetic competing target"
            assert location.staging.exists()
        else:
            a.NativeStorage._no_replace(location, descriptor)
            assert a.NativeStorage._identity(location.final) == receipt.native_identity
            assert sha256(location.final.read_bytes()).digest() == receipt.database_sha256
            assert not location.staging.exists()
    finally:
        if descriptor is not None:
            os.close(descriptor)


def test_native_exclusive_create_race_preserves_competing_bytes(fixture):
    f = fixture
    original = os.open
    def race(path, flags, *args, **kwargs):
        if Path(path) == f.request.location.staging and flags & os.O_EXCL:
            Path(path).write_bytes(b"synthetic competing creation")
        return original(path, flags, *args, **kwargs)
    with patch.object(a.os, "open", race):
        result = a.prepare_register(f.request, qualification=f.q, storage=f.native)
    assert result.cause is not None
    assert f.request.location.staging.read_bytes() == b"synthetic competing creation"


@parameterize("role", [role for role, _ in a._AUTHORITY_SHA256])
def test_frozen_authority_hash_substitution_rejected(fixture, role):
    f = fixture
    wrong = replace(getattr(f.e.authorities, role), sha256="a" * 64)
    e = replace(f.e, authorities=replace(f.e.authorities, **{role: wrong}))
    with raises(a.ActivationRejected):
        a._validate_snapshot(replace(f.snapshot, ceremony=a.canonical_bytes(e)))


@parameterize("value", [None, True, "unqualified"])
def test_creation_evidence_failure_retains_physical_preparation(fixture, value):
    f = fixture
    with patch.object(f.q, "creation", return_value=value):
        result = a.prepare_register(f.request, qualification=f.q, storage=f.native)
    assert result.cause is not None and result.recovery_only
    assert result.reached is a.Reached.PREPARED_NON_AUTHORITATIVE
    assert f.request.location.staging.exists() and not f.request.location.final.exists()


@parameterize("stage", ["checkpoint", "cas", "readback"])
def test_wrong_protected_result_binding_stops_next_effect(fixture, stage):
    f = fixture
    receipt = prepared(f)
    request = execution(f, receipt)
    protected = SyntheticProtected(request)
    method = {"checkpoint": "publish_checkpoint", "cas": "activate_absent", "readback": "readback"}[stage]
    original = getattr(protected, method)
    def wrong(*args):
        return replace(original(*args), host_identity="wrong-host")
    with patch.object(protected, method, wrong):
        result = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
    assert result.cause is not None and result.recovery_only
    assert protected.calls == {"checkpoint": ["checkpoint"], "cas": ["checkpoint", "cas"],
                              "readback": ["checkpoint", "cas", "readback"]}[stage]


def test_concurrent_original_attempt_has_one_dispatch_winner(fixture):
    import concurrent.futures
    f = fixture
    receipt = prepared(f)
    request = execution(f, receipt)
    protected = SyntheticProtected(request)
    def run():
        return a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run(), range(2)))
    assert sum(result.cause is None for result in results) == 1
    assert protected.calls == ["checkpoint", "cas", "readback"]


def test_constructor_forged_receipt_cannot_supply_new_attempt(fixture):
    f = fixture
    receipt = prepared(f)
    forged = replace(receipt, attempt=a.GenesisAttempt())
    request = execution(f, forged)
    protected = SyntheticProtected(request)
    result = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=forged.attempt)
    assert result.cause is not None and not protected.calls
    assert not f.request.location.final.exists()


def test_public_package_validation_is_pure_and_has_no_callbacks(fixture):
    f = fixture
    prepared(f)
    bindings = f.q.package(f.snapshot)
    with patch.object(os, "open", side_effect=AssertionError("pure native I/O")), \
         patch.object(sqlite3, "connect", side_effect=AssertionError("pure SQLite I/O")), \
         patch.object(f.q, "package", side_effect=AssertionError("pure callback")), \
         patch.object(subprocess, "check_output", side_effect=AssertionError("pure process I/O")):
        assert a.validate_genesis_package(f.snapshot, bindings).snapshot == f.snapshot


@parameterize("suffix", ["-journal", "-wal", "-shm"])
def test_existing_open_rejects_journal_before_sqlite_can_recover(fixture, suffix):
    f = fixture
    request = activated(f)
    journal = Path(str(f.request.location.final) + suffix)
    journal.write_bytes(b"synthetic uncertain journal: preserve")
    before = f.request.location.final.read_bytes()
    with patch.object(sqlite3, "connect", side_effect=AssertionError("must reject before SQLite opens")):
        result = a.open_authoritative_register(request, qualification=f.q, storage=f.native)
    assert isinstance(result.cause, a.ActivationRejected)
    assert journal.read_bytes() == b"synthetic uncertain journal: preserve"
    assert f.request.location.final.read_bytes() == before


def test_restart_existing_open_uses_fresh_sample_and_never_initializes(fixture):
    f = fixture
    request = activated(f)
    f.native.close()
    restarted = SyntheticStorage()
    old = a.open_authoritative_register(request, qualification=f.q, storage=restarted)
    assert old.cause is not None and not restarted.calls
    fresh_sample = replace(f.clock.sample, sample=ref("synthetic-fresh-restart-sample"),
                           validation=ref("synthetic-fresh-restart-validation"))
    fresh_clock = replace(f.clock, sample=fresh_sample,
        error=replace(f.clock.error, sample=fresh_sample.sample, qualification=ref("fresh-restart-error")))
    request = replace(request, clock=fresh_clock)
    try:
        with patch.object(restarted, "create", side_effect=AssertionError("restart genesis")):
            result = a.open_authoritative_register(request, qualification=f.q, storage=restarted)
        assert result.cause is None, repr(result.cause)
        assert restarted.calls == ["acquire_existing"]
        assert result.receipt.read_rows(s.CommandRow) == ()
        result.receipt.close()
    finally:
        restarted.close()


def test_fixed_creation_time_must_match_original_qualified_sample(fixture):
    f = fixture
    clock = replace(f.clock, sample=replace(f.clock.sample, utc=v.UtcInterval(1, 1)))
    result = a.prepare_register(replace(f.request, clock=clock), qualification=f.q, storage=f.native)
    assert result.reached is a.Reached.REJECTED and not f.native.calls
    assert not f.request.location.staging.exists()


def current_clock(clock, utc):
    sample = replace(clock.sample, sample=ref("remediation-fresh-sample:" + str(utc)),
                     validation=ref("remediation-fresh-validation"), utc=v.UtcInterval(utc, utc))
    return replace(clock, sample=sample, current=sample.anchor,
                   error=replace(clock.error, sample=sample.sample))


@parameterize("valid_until,fresh_utc,allowed", [(1, 2, False), (3, 2, True)])
def test_review_stale_request_clock_uses_current_q_validity(fixture, valid_until, fresh_utc, allowed):
    f = fixture
    request = replace(activated(f), approval=replace(f.approval, valid_until_us=valid_until))
    assert request.clock.sample.utc == v.UtcInterval(0, 0)
    original = f.q.opening
    with patch.object(f.q, "opening", lambda request: replace(original(request),
            fresh_time=current_clock(f.clock, fresh_utc))):
        result = a.open_authoritative_register(request, qualification=f.q, storage=f.native)
    if allowed:
        assert result.cause is None and result.reached is a.Reached.OPEN_VALIDATED
        result.receipt.close()
    else:
        try:
            assert result.cause is not None and result.receipt is None
            assert result.reached is a.Reached.REJECTED
        finally:
            if result.receipt is not None:
                result.receipt.close()


def test_review_read_requalification_rejects_expired_approval(fixture):
    f = fixture
    request = replace(activated(f), approval=replace(f.approval, valid_until_us=1))
    opened = a.open_authoritative_register(request, qualification=f.q, storage=f.native)
    assert opened.cause is None
    original = f.q.opening
    try:
        with patch.object(f.q, "opening", lambda request: replace(original(request),
                fresh_time=current_clock(f.clock, 2))):
            with raises(a.ActivationRejected):
                opened.receipt.read_rows(s.MetadataRow)
        with raises(a.ActivationRejected):
            opened.receipt.read_rows(s.MetadataRow)  # Remains fenced after expiry.
    finally:
        opened.receipt.close()


@parameterize("fault", ["missing", "wrong_profile"])
def test_review_fresh_opening_time_remains_required_and_qualified(fixture, fault):
    f = fixture
    request = activated(f)
    original = f.q.opening
    fresh = None if fault == "missing" else replace(current_clock(f.clock, 2),
        profile=replace(f.clock.profile, profile=ref("unapproved-profile")))
    with patch.object(f.q, "opening", lambda request: replace(original(request), fresh_time=fresh)):
        result = a.open_authoritative_register(request, qualification=f.q, storage=f.native)
    assert result.cause is not None and result.receipt is None


@parameterize("generation", [True, 1.0, "1"])
def test_review_approval_generation_requires_exact_integer_before_effect(fixture, generation):
    f = fixture
    receipt = prepared(f)
    request = replace(execution(f, receipt), approval=replace(f.approval, generation=generation))
    protected = SyntheticProtected(request)
    result = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
    assert result.cause is not None and result.reached is a.Reached.REJECTED
    assert protected.calls == [] and not f.request.location.final.exists()


@parameterize("generation", [True, 1.0, "1"])
def test_review_cas_generation_requires_exact_integer_before_readback(fixture, generation):
    f = fixture
    receipt = prepared(f)
    request = execution(f, receipt)
    protected = SyntheticProtected(request)
    original = protected.activate_absent
    with patch.object(protected, "activate_absent", lambda *args: replace(original(*args), generation=generation)):
        result = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
    assert result.cause is not None and result.reached is a.Reached.CAS_ATTEMPTED
    assert protected.calls == ["checkpoint", "cas"]


@parameterize("field,value", [("generation", True), ("generation", 1.0),
                              ("fixed_utc", False), ("fixed_utc", 0.0)])
def test_review_creation_claim_numeric_types(fixture, field, value):
    f = fixture
    original = f.q.creation
    def malformed(*args):
        result = original(*args)
        return replace(result, claims=replace(result.claims, **{field: value}))
    with patch.object(f.q, "creation", malformed):
        result = a.prepare_register(f.request, qualification=f.q, storage=f.native)
    assert result.cause is not None and result.receipt is None


@parameterize("field,value", [("schema_version", True), ("singleton", True),
    ("issuer_generation", True), ("last_valid_utc", False), ("recovery_required", False)])
def test_review_package_metadata_claim_rejects_boolean_integers(fixture, field, value):
    f = fixture
    prepared(f)
    bindings = f.q.package(f.snapshot)
    creation = bindings.claims.creation
    malformed = replace(creation.metadata, **{field: value})
    bindings = replace(bindings, claims=replace(bindings.claims,
        creation=replace(creation, metadata=malformed)))
    with raises(a.ActivationRejected):
        a.validate_genesis_package(f.snapshot, bindings)


@parameterize("identity", [(True, False), (1.0, 0.0)])
def test_review_storage_identity_components_require_exact_integers(fixture, identity):
    f = fixture
    prepared(f)
    bindings = f.q.package(f.snapshot)
    claims = replace(bindings.claims,
        creation=replace(bindings.claims.creation, native_identity=(1, 0)),
        storage=replace(bindings.claims.storage, native_identity=identity))
    with raises(a.ActivationRejected):
        a.validate_genesis_package(f.snapshot, replace(bindings, claims=claims))


@parameterize("field", ["parent_device", "parent_inode"])
def test_review_storage_location_boolean_domain_rejected_before_native_use(fixture, field):
    f = fixture
    location = replace(f.request.location, **{field: True})
    with patch.object(f.native, "_plain", side_effect=AssertionError("numeric rejection must precede native path checks")):
        with raises(a.ActivationRejected):
            f.native.check(location, staging_exists=False)


@parameterize("stage", ["preparation", "execution"])
def test_review_qualification_validity_bounds_reject_boolean(fixture, stage):
    f = fixture
    if stage == "preparation":
        original = f.q.preparation
        with patch.object(f.q, stage, lambda request: replace(original(request), valid_from_us=False)):
            result = a.prepare_register(f.request, qualification=f.q, storage=f.native)
        assert result.reached is a.Reached.REJECTED and not f.native.calls
    else:
        receipt = prepared(f)
        request = execution(f, receipt)
        protected = SyntheticProtected(request)
        original = f.q.execution
        with patch.object(f.q, stage, lambda request: replace(original(request), valid_from_us=False)):
            result = a.execute_genesis(request, qualification=f.q, protected=protected, attempt=receipt.attempt)
        assert result.reached is a.Reached.REJECTED and not protected.calls


def test_review_current_event_sequence_rejects_boolean_zero(fixture):
    f = fixture
    request = activated(f)
    original = f.q.opening
    with patch.object(f.q, "opening", lambda request: replace(original(request), event_sequence=False)):
        result = a.open_authoritative_register(request, qualification=f.q, storage=f.native)
    try:
        assert result.cause is not None and result.receipt is None
    finally:
        if result.receipt is not None:
            result.receipt.close()


class ActivationTests(unittest.TestCase):
    """Standard repository unittest runner; also collectable by pytest."""


def _install_cases():
    for name, function in tuple(globals().items()):
        if not name.startswith("test_") or not callable(function):
            continue
        parameters = getattr(function, "_parameters", ())
        combinations = itertools.product(*(values for _, values in parameters)) if parameters else [()]
        for index, combination in enumerate(combinations):
            arguments = {}
            for (names, _), value in zip(parameters, combination):
                if len(names) == 1:
                    value = (value,)
                arguments.update(zip(names, value))
            def run(self, function=function, arguments=arguments):
                arguments = arguments.copy()
                generator = None
                try:
                    if "fixture" in function.__code__.co_varnames[:function.__code__.co_argcount]:
                        generator = fixture()
                        arguments["fixture"] = next(generator)
                    function(**arguments)
                finally:
                    if generator is not None:
                        generator.close()
            setattr(ActivationTests, name + "_%03d" % index, run)
        del globals()[name]


_install_cases()

if __name__ == "__main__":
    unittest.main()
