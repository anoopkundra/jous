"""Offline IL.4A codec vectors and fail-closed boundaries; no storage access."""
import ast
from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "_il4a_pure"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "services/api/infrastructure")]
sys.modules[PACKAGE] = package
for name in ("fixture_lease_contract", "fixture_lease_protocol"):
    spec = importlib.util.spec_from_file_location(PACKAGE + "." + name,
        ROOT / "services/api/infrastructure" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
p = sys.modules[PACKAGE + ".fixture_lease_protocol"]
c = sys.modules[PACKAGE + ".fixture_lease_contract"]


def h(byte):
    return bytes((byte,)) * 32


def fixtures():
    binding = p.Reference("a", c.ArtifactType.PROVISIONING_REQUEST, h(0x11))
    authorization = p.Reference("z", c.ArtifactType.AUTHORIZATION, h(0x22))
    parameters = p.Parameters("r", None, binding, None, None, (), 100, 90, None)
    command = p.CommandPayload(c.Command.ACQUIRE, "p", "g", 1, "x", "c", "", 0,
        c.Operation.FIXTURE_PROVISIONING, c.Phase.PRE_AUTH,
        c.ArtifactType.PROVISIONING_REQUEST, h(0x11), "s", binding, h(0x33),
        authorization, (), parameters)
    events = []
    prior = p.GENESIS_EVENT_DIGEST
    for sequence, kind in enumerate(p.event_order(c.Command.ACQUIRE), 1):
        event = p.EventPayload(sequence, "c", "r", "g", 1, "x", kind, 0,
            prior, 0, "a", None)
        events.append(event)
        prior = p.event_digest(event)
    ack = p.AckPayload("c", p.command_digest(command), "p", "g", 1, "x", "r", 0,
        "p", c.Operation.FIXTURE_PROVISIONING, c.Phase.PRE_AUTH,
        c.ArtifactType.PROVISIONING_REQUEST, h(0x11), p.key_set_digest(()), h(0x33),
        authorization, (), 0, 0, 100, 90, 1, 3, 3, prior, p.OutcomeCode.SUCCESS)
    metadata = p.MetadataRow(1, 1, "g", 1, "x", h(0x44), h(0x55), h(0x66),
        h(0x77), 0, 0)
    reservation = p.ReservationRow("r", "g", "s", c.Operation.FIXTURE_PROVISIONING,
        c.Phase.PRE_AUTH, c.ArtifactType.PROVISIONING_REQUEST, "a", h(0x11), b"d",
        hashlib.sha256(b"d").digest(), "p", "z", 0, 0, 0, 100, 90, 0,
        c.LeaseStatus.LEASED, 0, p.ExecutionState.NOT_STARTED, None, None, None)
    row = p.CommandRow("c", "p", c.Command.ACQUIRE, p.command_bytes(command),
        p.command_digest(command), 0, "r", p.OutcomeCode.SUCCESS, p.ack_bytes(ack), 3)
    minimal = p.StateProjection(metadata, (), (), ())
    completed = p.StateProjection(metadata, (reservation,), (), (row,))
    context = p.StateContext(p.STATE_2, "g", 1, "x")
    evidence = p.Reference("e", c.ArtifactType.PROVENANCE_EVIDENCE, h(0x88))
    expiry = replace(command, command_kind=c.Command.QUARANTINE, command_id="c-expiry",
        reservation_id="r", approval_record_hash=h(0x99), evidence_references=(evidence,),
        parameters=p.Parameters("r", None, None, None,
            p.QuarantineReason.EXPIRED_UNRECONCILED, (evidence,), None, None, evidence))
    expiry_events = []
    for sequence, kind in enumerate(p.event_order(c.Command.QUARANTINE, definite_expiry=True), 4):
        event = p.EventPayload(sequence, "c-expiry", "r", "g", 1, "x", kind, 101,
            prior, 1, "a", "e")
        expiry_events.append(event)
        prior = p.event_digest(event)
    expiry_ack = replace(ack, command_id="c-expiry", command_payload_sha256=p.command_digest(expiry),
        resulting_revision=1, approval_record_hash=h(0x99), evidence_references=(evidence,),
        issued_at=101, first_event_sequence=4, final_event_sequence=6, final_event_digest=prior)
    primary_a = p.Reference("a-required", c.ArtifactType.RELEASE_EVIDENCE, h(0x11))
    supplementary_z = p.Reference("z-supplementary", c.ArtifactType.PROVENANCE_EVIDENCE, h(0x22))
    primary_z = replace(primary_a, artifact_id="z-required")
    supplementary_a = replace(supplementary_z, artifact_id="a-supplementary")
    primary_first = p.Parameters("r", None, None, None, None,
        (primary_a, supplementary_z), None, None, primary_a)
    supplementary_first = replace(primary_first,
        supporting_refs=(supplementary_a, primary_z), primary_evidence_reference=primary_z)
    vectors = {
        "COMMAND": p.command_bytes(command), "First EVENT": p.event_bytes(events[0]),
        "Subsequent EVENT": p.event_bytes(events[1]), "ACKNOWLEDGED EVENT": p.event_bytes(events[2]),
        "ACK": p.ack_bytes(ack), "Minimal STATE": p.state_bytes(minimal, context),
        "Completed-command STATE": p.state_bytes(completed, context),
        "Expiry COMMAND": p.command_bytes(expiry), "EXPIRED EVENT": p.event_bytes(expiry_events[0]),
        "QUARANTINED EVENT": p.event_bytes(expiry_events[1]),
        "Expiry ACKNOWLEDGED EVENT": p.event_bytes(expiry_events[2]), "Expiry ACK": p.ack_bytes(expiry_ack),
        "Primary sorts first": p.encode_record(primary_first),
        "Supplementary sorts first": p.encode_record(supplementary_first),
        "Empty collection": p.collection(()),
        "One-item collection": p.collection((p.encode_record(primary_a),)),
        "Two-item collection": p.collection(map(p.encode_record, primary_first.supporting_refs)),
    }
    return locals()


EXPECTED = {
    "Empty collection": (4, "df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119"),
    "One-item collection": (98, "007360d0ceeaddda8b91b019b8ec709fd2335ba288373d6120dfaaabdd96cd75"),
    "Two-item collection": (200, "455c96148ed881664979ab0cb518a82b628cd67bf20249e12a0b3724941f23f4"),
    "COMMAND": (609, "f58d835a11128e077af416cda614e8e3ba9947da072ef4ce2e33a87751e07fc5"),
    "First EVENT": (153, "623e6d5a2de819a64b3d6d6f348e69581adcdc2a096b2c666a8a56b631c5ac75"),
    "Subsequent EVENT": (152, "2032dddef8645040803eef9c789a62f722cedb7fd1dd0c1fc2fded959db9d70f"),
    "ACKNOWLEDGED EVENT": (156, "54c6b63a0197ad58ca73c6ea0044c090a7fe3c90c022c7069ad18727538ea47d"),
    "ACK": (528, "71bbc6be226e8e85929bd99a327eb454e0e05c2b6cc706e82a997d300155d720"),
    "Minimal STATE": (269, "e0abb0fee5648d285ae3b3f3f61c133c5ac8f18d4e6493a0ad88d5dce87b5d8a"),
    "Completed-command STATE": (1876, "435d2954bab863c77ee75fd20f72a17be42550057386c62379b9857d3c0652fd"),
    "Expiry COMMAND": (799, "e8bf530487e83ea2800d10e4113820e1ac86a13276169cfadd9ae0389ac96351"),
    "EXPIRED EVENT": (159, "886e5f51e480e7df7c4c98b6ab1b67a7b0c000ee3d2954507c42fd5776c1b30b"),
    "QUARANTINED EVENT": (163, "e0f165fb70e57a28e2ef514f60d61b3175c0defb9131c6e562f8b860260a4206"),
    "Expiry ACKNOWLEDGED EVENT": (164, "a24949136abe475b02473b59fda2e60e04ac2cd6cbab4ec0cd4e92e161d2fc20"),
    "Expiry ACK": (623, "32a8ebc5c69a1aabfc46217a52d5024a7e7537922b3b1899ffaafe5b83035f8e"),
    "Primary sorts first": (362, "683cda653fad6d7d7f2872739e0b4721e180ca83c173718eb11a8c76b32b086e"),
    "Supplementary sorts first": (362, "5d7b5d9c0eb54a470fb84ce7c0ba8eb74947b6667c4c58aa0f03a59d4824f1d8"),
}


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures()

    def reject(self, function, *args, **kwargs):
        with self.assertRaises(p.ProtocolRejected):
            function(*args, **kwargs)

    def test_all_17_published_vectors(self):
        self.assertEqual(len(self.f["vectors"]), 17)
        for name, raw in self.f["vectors"].items():
            with self.subTest(vector=name):
                self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), EXPECTED[name])
                self.assertEqual(raw.hex(), EXPECTED_HEX[name])

    def test_strict_record_roundtrips(self):
        for name, cls in (("command", p.CommandPayload), ("ack", p.AckPayload),
                          ("expiry", p.CommandPayload), ("expiry_ack", p.AckPayload),
                          ("primary_first", p.Parameters), ("supplementary_first", p.Parameters)):
            value = self.f[name]
            self.assertEqual(p.decode_record(p.encode_record(value), cls), value)
        for event in self.f["events"] + self.f["expiry_events"]:
            self.assertEqual(p.decode_record(p.event_bytes(event), p.EventPayload), event)

    def test_cross_vector_dependencies_and_ack_interval(self):
        self.assertEqual(p.GENESIS_EVENT_DIGEST.hex(),
            "4e6abfbfdec0d3d621faea244e0b3c71b2632b092e6423e4f2f352e65a5d7b61")
        self.validate_base()
        f = self.f
        p.validate_ack(f["expiry_ack"], f["expiry"], f["expiry_events"],
            previous_sequence=3, previous_digest=p.event_digest(f["events"][-1]),
            digests=tuple(map(p.event_digest, f["expiry_events"])),
            transition_event_sequence=6, definite_expiry=True, keys=())
        row = f["row"]
        self.assertEqual(row.canonical_payload_bytes, f["vectors"]["COMMAND"])
        self.assertEqual(row.canonical_payload_hash, f["ack"].command_payload_sha256)
        self.assertEqual(row.durable_ack_bytes, f["vectors"]["ACK"])
        self.assertEqual(f["ack"].canonical_key_set_digest,
            hashlib.sha256(f["vectors"]["Empty collection"]).digest())
        command, ack = p.validate_completed_command(f["row"], f["events"],
            previous_sequence=0, previous_digest=p.GENESIS_EVENT_DIGEST,
            digests=tuple(map(p.event_digest, f["events"])), keys=())
        self.assertEqual(command, f["command"])
        self.assertEqual(p.ack_bytes(ack), f["row"].durable_ack_bytes)

    def validate_base(self, ack=None, events=None, digests=None, **changes):
        f = self.f
        defaults = dict(previous_sequence=0, previous_digest=p.GENESIS_EVENT_DIGEST,
            digests=tuple(map(p.event_digest, f["events"])) if digests is None else digests,
            transition_event_sequence=3, keys=())
        defaults.update(changes)
        return p.validate_ack(f["ack"] if ack is None else ack, f["command"],
                              f["events"] if events is None else events, **defaults)

    def test_frame_boundaries_and_malformed_input(self):
        raw = p.frame(1, 17, (b"a" * 65535,))
        self.assertEqual(p.parse_frame(raw, 1, 17, 1), (b"a" * 65535,))
        self.reject(p.frame, 1, 17, (b"a" * 65536,))
        raw = self.f["vectors"]["COMMAND"]
        for corrupt in (raw[:-1], raw + b"x", b"X" + raw[1:],
                        raw[:18] + b"\x03" + raw[19:], raw[:19] + b"\x11" + raw[20:]):
            self.reject(p.decode_record, corrupt, p.CommandPayload)
        fields = list(p.parse_frame(raw, 1, 5, 18))
        for index, value in ((0, b"UNKNOWN"), (1, b"\xff"), (7, b"\x00"), (6, b"\x00")):
            changed = fields.copy()
            changed[index] = value
            self.reject(p.decode_record, p.frame(1, 5, changed), p.CommandPayload)
        self.reject(p.uint, True)
        self.reject(p.utc, False)
        self.reject(p.uint, -1)
        self.reject(p.uint, 1 << 63)
        self.reject(p.u32, 1 << 32)
        self.reject(p.identifier, " ")
        self.reject(p.identifier, "\ud800")

    def test_nullable_marker_and_collection_framing(self):
        params = self.f["primary_first"]
        fields = list(p.parse_frame(p.encode_record(params), 1, 16, 9))
        for value in (b"", b"\x02", b"\x00x", b"\x01"):
            changed = fields.copy()
            changed[1] = value
            self.reject(p.decode_record, p.frame(1, 16, changed), p.Parameters)
        for bad in (b"", b"\x00\x00\x00\x01", p.PREFIX + b"\x01\x0b\x00\x00\x00\x00",
                    p.frame(1, 11, ()), b"\x00\x00\x00\x00x"):
            changed = fields.copy()
            changed[5] = bad
            self.reject(p.decode_record, p.frame(1, 16, changed), p.Parameters)
        correct = fields[5]
        for bad in (b"\x00\x00\x00\x01" + correct[4:],
                    b"\x00\x00\x00\x03" + correct[4:], correct[:-1],
                    p.u32(len(correct)) + correct, p.PREFIX + correct):
            changed = fields.copy()
            changed[5] = bad
            self.reject(p.decode_record, p.frame(1, 16, changed), p.Parameters)

    def test_primary_selection_and_rejection(self):
        for name in ("primary_first", "supplementary_first"):
            params = self.f[name]
            self.assertEqual(p.validate_primary(params, c.Command.RELEASE), params.primary_evidence_reference)
        params = self.f["supplementary_first"]
        primary = params.primary_evidence_reference
        for bad in (replace(params, primary_evidence_reference=None),
                    replace(params, primary_evidence_reference=replace(primary, artifact_id="missing")),
                    replace(params, primary_evidence_reference=params.supporting_refs[0]),
                    replace(params, supporting_refs=(primary, primary)),
                    replace(params, supporting_refs=tuple(reversed(params.supporting_refs))),
                    replace(params, primary_evidence_reference=replace(primary, artifact_sha256=h(0x33)))):
            self.reject(p.validate_primary, bad, c.Command.RELEASE)
        release = replace(self.f["command"], command_kind=c.Command.RELEASE, reservation_id="r",
                          parameters=params, evidence_references=params.supporting_refs)
        p.command_bytes(release)
        swapped = replace(release, parameters=replace(params,
            primary_evidence_reference=params.supporting_refs[0]))
        self.reject(p.command_bytes, swapped)
        self.assertNotEqual(p.command_bytes(release), p.command_bytes(replace(release,
            expected_revision=1)))
        p.validate_evidence(params, c.Command.RELEASE, tuple(reversed(params.supporting_refs)))
        self.reject(p.validate_evidence, params, c.Command.RELEASE,
                    (params.supporting_refs[0], replace(primary,
                        artifact_type=c.ArtifactType.PROVENANCE_EVIDENCE)))
        self.reject(p.validate_evidence, params, c.Command.RELEASE,
                    (params.supporting_refs[0], replace(primary, artifact_sha256=h(0x99))))

    def test_command_applicability(self):
        command = self.f["command"]
        for bad in (replace(command, expected_revision=True), replace(command, expected_revision=1),
                    replace(command, reservation_id="r"), replace(command, issuer_generation=0),
                    replace(command, binding_sha256=h(0x55)),
                    replace(command, authorization_reference=command.binding_reference),
                    replace(command, parameters=replace(command.parameters, proposed_expires_at=None)),
                    replace(command, parameters=replace(command.parameters, execution_state=p.ExecutionState.STARTED))):
            self.reject(p.command_bytes, bad)

    def test_whole_command_over_65535_with_valid_fields(self):
        # Two independently valid nested reference fields can exceed 65535 in total.
        references = tuple(p.Reference(f"e-{index:04d}" + "x" * 180,
            c.ArtifactType.PROVENANCE_EVIDENCE, h(0x88)) for index in range(140))
        command = self.f["command"]
        command = replace(command, evidence_references=references,
            parameters=replace(command.parameters, supporting_refs=references,
                               primary_evidence_reference=references[0]))
        raw = p.command_bytes(command)
        self.assertGreater(len(raw), 65535)
        self.assertEqual(p.decode_record(raw, p.CommandPayload), command)

    def test_event_and_ack_adversaries(self):
        f = self.f
        for field, value in (("event_count", 2), ("first_event_sequence", 2),
                             ("final_event_sequence", 4), ("final_event_digest", h(0)),
                             ("command_payload_sha256", h(0)), ("resulting_revision", 1)):
            self.reject(self.validate_base, ack=replace(f["ack"], **{field: value}))
        self.reject(self.validate_base, transition_event_sequence=1)
        self.reject(self.validate_base, events=(), digests=())
        events = list(f["events"])
        for field, value in (("event_sequence", 4), ("prior_digest", h(0)),
                             ("event_type", p.EventType.RELEASED), ("revision", 1),
                             ("utc_time", 1), ("artifact_id", "wrong")):
            changed = events.copy()
            changed[1] = replace(changed[1], **{field: value})
            self.reject(self.validate_base, events=changed)
        digests = list(map(p.event_digest, events))
        digests[1] = h(0)
        self.reject(self.validate_base, digests=digests)
        self.reject(p.event_order, c.Command.ACQUIRE, definite_expiry=True)
        # Rehash a perfectly contiguous altered chain: order and interval binding
        # still reject; this does not merely fail an old digest comparison.
        altered = []
        prior = p.GENESIS_EVENT_DIGEST
        for event in events:
            kind = p.EventType.RELEASED if event.event_sequence == 3 else event.event_type
            event = replace(event, event_type=kind, prior_digest=prior)
            altered.append(event)
            prior = p.event_digest(event)
        self.reject(self.validate_base, ack=replace(f["ack"], final_event_digest=prior),
                    events=altered, digests=tuple(map(p.event_digest, altered)))

    def test_retained_material_integrity_helpers(self):
        f = self.f
        kwargs = dict(previous_sequence=0, previous_digest=p.GENESIS_EVENT_DIGEST,
                      digests=tuple(map(p.event_digest, f["events"])), keys=())
        for row in (replace(f["row"], authenticated_principal="other"),
                    replace(f["row"], canonical_payload_hash=h(0)),
                    replace(f["row"], durable_ack_bytes=None),
                    replace(f["row"], transition_event_sequence=1),
                    replace(f["row"], expected_revision=1),
                    replace(f["row"], durable_ack_bytes=f["row"].durable_ack_bytes[:-1]),
                    replace(f["row"], canonical_payload_bytes=b"malformed")):
            self.reject(p.validate_completed_command, row, f["events"], **kwargs)

    def test_expiry_order_is_exhaustive_and_atomic_representation(self):
        f = self.f
        self.assertEqual(tuple(event.event_type.value for event in f["expiry_events"]),
                         ("EXPIRED", "QUARANTINED", "ACKNOWLEDGED"))
        for events in (f["expiry_events"][1:], list(reversed(f["expiry_events"]))):
            self.reject(p.validate_ack, f["expiry_ack"], f["expiry"], events,
                previous_sequence=3, previous_digest=p.event_digest(f["events"][-1]),
                digests=tuple(map(p.event_digest, events)), transition_event_sequence=6,
                definite_expiry=True)

    def test_state_roundtrip_streaming_and_integrity(self):
        f = self.f
        for name in ("minimal", "completed"):
            projection = f[name]
            raw = p.state_bytes(projection, f["context"])
            self.assertEqual(p.decode_state(raw, f["context"]), projection)
            self.assertEqual(p.state_digest(projection, f["context"]), hashlib.sha256(raw).digest())
            for size in (1, 7, 1024):
                digest = hashlib.sha256()
                for offset in range(0, len(raw), size):
                    digest.update(raw[offset:offset + size])
                self.assertEqual(digest.digest(), p.state_digest(projection, f["context"]))
            p.verify_state_digest(projection, f["context"], hashlib.sha256(raw).digest())
            self.reject(p.verify_state_digest, projection, f["context"], h(0))
            for bad in (raw[:-1], raw + b"\x00", raw.replace(b"\x03\x00", b"\x03\x02", 1)):
                self.reject(p.decode_state, bad, f["context"])

    def test_state_order_duplicates_context_and_no_fallback(self):
        f = self.f
        for rows in ((f["row"], f["row"]),
                     (replace(f["row"], command_id="z"), f["row"])):
            self.reject(p.state_digest, replace(f["minimal"], commands=rows), f["context"])
        for representation in (p.STATE_1, "STATE_V2", "unknown", "", None):
            context = replace(f["context"], representation=representation)
            self.reject(p.state_digest, f["minimal"], context)
            self.reject(p.decode_state, f["vectors"]["Minimal STATE"], context)
        self.reject(p.state_digest, f["minimal"], replace(f["context"], issuer_generation=2))

    def test_state_claim_keys_and_projected_row_constraints(self):
        f = self.f
        key_a = c.ConflictKey.fixture_set(c.DatabaseTargetScope("g"), "a").canonical_bytes
        key_z = c.ConflictKey.fixture_set(c.DatabaseTargetScope("g"), "z").canonical_bytes
        claim_a = p.ClaimRow(key_a, "r", 0, "a")
        claim_z = replace(claim_a, canonical_key=key_z)
        projection = replace(f["completed"], claims=(claim_a, claim_z))
        p.state_digest(projection, f["context"])
        p.key_set_digest((key_a, key_z))
        for claims in ((claim_z, claim_a), (claim_a, claim_a),
                       (replace(claim_a, canonical_key=b"invalid"),)):
            self.reject(p.state_digest, replace(projection, claims=claims), f["context"])
        self.reject(p.key_set_digest, (key_a, key_a))
        self.reject(p.key_set_digest, (key_z, key_a))
        for reservations in ((f["reservation"], f["reservation"]),
                (replace(f["reservation"], reservation_id="z"), f["reservation"]),
                (replace(f["reservation"], immutable_db_projection_hash=h(0)),),
                (replace(f["reservation"], expired_condition=True),),
                (replace(f["reservation"], lease_status=c.LeaseStatus.QUARANTINED),),
                (replace(f["reservation"], lease_status=c.LeaseStatus.RELEASED),),
                (replace(f["reservation"], acknowledged_at=100),)):
            self.reject(p.state_digest, replace(projection, reservations=reservations), f["context"])
        self.reject(p.state_digest, replace(projection, metadata=replace(f["metadata"],
                    recovery_required=True)), f["context"])
        self.reject(p.state_digest, replace(projection, commands=(replace(f["row"],
                    canonical_payload_hash=h(0)),)), f["context"])

    def test_streaming_one_shot_iterators(self):
        f = self.f
        class Once:
            def __init__(self, values):
                self.values, self.used = values, False
            def __iter__(self):
                if self.used:
                    raise AssertionError("stream read twice")
                self.used = True
                return iter(self.values)
        projection = p.StateProjection(f["metadata"], Once((f["reservation"],)),
                                       Once(()), Once((f["row"],)))
        self.assertEqual(p.state_digest(projection, f["context"]),
                         hashlib.sha256(f["vectors"]["Completed-command STATE"]).digest())

    def test_large_state_4096_4097_4098_streaming(self):
        f = self.f
        for count in (4096, 4097, 4098):
            with self.subTest(count=count):
                def rows():
                    for index in range(count):
                        yield replace(f["row"], command_id=f"c-{index:08d}")
                streaming = replace(f["minimal"], commands=rows())
                digest = p.state_digest(streaming, f["context"])
                materialized = replace(f["minimal"], commands=rows())
                raw = p.state_bytes(materialized, f["context"])
                self.assertEqual(digest, hashlib.sha256(raw).digest())
                self.assertEqual(digest, p.state_digest(replace(f["minimal"], commands=rows()), f["context"]))
                self.assertGreater(len(raw), 65535)

    def test_one_mib_projection_with_framing_overhead(self):
        f = self.f
        large = b"a" * p.MAX_BLOB
        row = replace(f["reservation"], immutable_db_projection=large,
                      immutable_db_projection_hash=hashlib.sha256(large).digest())
        projection = replace(f["minimal"], reservations=(row,))
        raw = p.state_bytes(projection, f["context"])
        self.assertGreater(len(raw), p.MAX_BLOB)
        self.assertEqual(p.state_digest(projection, f["context"]), hashlib.sha256(raw).digest())
        self.assertEqual(p.decode_state(raw, f["context"]), projection)
        self.reject(p.state_digest, replace(projection, reservations=(replace(row,
            immutable_db_projection=large + b"a"),)), f["context"])
        optional_large = replace(f["row"], durable_ack_bytes=large)
        optional_projection = replace(f["minimal"], commands=(optional_large,))
        optional_raw = p.state_bytes(optional_projection, f["context"])
        self.assertEqual(p.decode_state(optional_raw, f["context"]), optional_projection)
        self.assertEqual(p.state_digest(optional_projection, f["context"]),
                         hashlib.sha256(optional_raw).digest())

    def test_numeric_bounds_and_schema_exhaustiveness(self):
        self.assertEqual(p.uint(p.MAX_UINT), b"\x7f" + b"\xff" * 7)
        self.assertEqual(p.utc(-(1 << 63)), b"\x80" + b"\x00" * 7)
        self.assertEqual(p.boolean(False), b"\x00")
        self.assertEqual(p.boolean(True), b"\x01")
        self.reject(p.boolean, 1)
        self.reject(p.utc, -(1 << 63) - 1)
        self.reject(p.utc, 1 << 63)
        for cls, count in ((p.CommandPayload, 18), (p.EventPayload, 12), (p.AckPayload, 26),
                           (p.Parameters, 9), (p.MetadataRow, 11), (p.ReservationRow, 24),
                           (p.ClaimRow, 4), (p.CommandRow, 10)):
            self.assertEqual(len(cls.__dataclass_fields__), count)
        self.reject(p.command_bytes, replace(self.f["command"], evidence_references=(),
            parameters=replace(self.f["command"].parameters,
                proposed_completion_deadline=100)))

    def test_completed_state_rejects_non_success_on_encoding(self):
        f = self.f
        for outcome in (p.OutcomeCode.REPLAY_MISMATCH, p.OutcomeCode.STORAGE_UNKNOWN):
            with self.subTest(outcome=outcome):
                row = replace(f["row"], outcome_code=outcome, durable_ack_bytes=None)
                projection = replace(f["minimal"], commands=(row,))
                self.reject(p.state_bytes, projection, f["context"])
                self.reject(p.state_digest, projection, f["context"])
        for field in ("reservation_id", "durable_ack_bytes", "transition_event_sequence"):
            row = replace(f["row"], **{field: None})
            self.reject(p.state_digest, replace(f["minimal"], commands=(row,)), f["context"])

    def test_completed_state_rejects_non_success_on_decoding(self):
        f = self.f
        fields = p.parse_frame(p.encode_record(f["row"]), 2, 15, 10)
        # Supply externally constructed, correctly framed diagnostic rows. Payload
        # bytes/hash and every other field remain valid; absence of ACK is valid
        # for an IL.3 diagnostic row, but not for this completed STATE collection.
        for outcome in (p.OutcomeCode.REPLAY_MISMATCH, p.OutcomeCode.STORAGE_UNKNOWN):
            with self.subTest(outcome=outcome):
                changed = list(fields)
                changed[7] = outcome.value.encode("utf-8")
                changed[8] = b"\x00"
                row_bytes = p.frame(2, 15, changed)
                state = (p.PREFIX + b"\x02\x08" + p.u32(4) + b"\x02"
                    + p.encode_record(f["metadata"]) + b"\x03\x00\x03\x00\x03\x01"
                    + row_bytes + b"\x00")
                self.reject(p.decode_state, state, f["context"])

    def test_ack_transition_sequence_strict_unsigned_domain(self):
        self.validate_base(transition_event_sequence=3)
        for value in (3.0, True, -1, p.MAX_UINT + 1):
            with self.subTest(sequence=value, value_type=type(value).__name__):
                self.reject(self.validate_base, transition_event_sequence=value)

    def test_ack_adjacent_previous_sequence_strict_unsigned_domain(self):
        # The adjacent input already passes through uint in validate_event_chain.
        # Preserve rejection of numeric equality aliases as well as range errors.
        self.validate_base(previous_sequence=0)
        for value in (0.0, False, -1, p.MAX_UINT + 1):
            with self.subTest(sequence=value, value_type=type(value).__name__):
                self.reject(self.validate_base, previous_sequence=value)

    def test_import_boundary(self):
        tree = ast.parse((ROOT / "services/api/infrastructure/fixture_lease_protocol.py").read_text())
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                imported.append(node.module or "fixture_lease_contract")
        self.assertEqual(set(imported), {"dataclasses", "enum", "hashlib", "typing", "fixture_lease_contract"})


# Exact published hex is appended below, independently of codec output.
EXPECTED_HEX = {
    'COMMAND': '4a4f55532d464958545552452d4c45415345010500000012000000074143515549524500000001700000000167000000080000000000000001000000017800000001630000000000000008000000000000000000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f524551554553540000002011111111111111111111111111111111111111111111111111111111111111110000000173000000594a4f55532d464958545552452d4c4541534501110000000300000001610000001450524f564953494f4e494e475f52455155455354000000201111111111111111111111111111111111111111111111111111111111111111000000203333333333333333333333333333333333333333333333333333333333333333000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e0000002022222222222222222222222222222222222222222222222222222222222222220000000400000000000000b14a4f55532d464958545552452d4c45415345011000000009000000017200000001000000005a014a4f55532d464958545552452d4c4541534501110000000300000001610000001450524f564953494f4e494e475f52455155455354000000201111111111111111111111111111111111111111111111111111111111111111000000010000000001000000000400000000000000090100000000000000640000000901000000000000005a0000000100',
    'First EVENT': '4a4f55532d464958545552452d4c4541534501060000000c00000008000000000000000100000001630000000201720000000167000000080000000000000001000000017800000009524551554553544544000000080000000000000000000000204e6abfbfdec0d3d621faea244e0b3c71b2632b092e6423e4f2f352e65a5d7b610000000800000000000000000000000201610000000100',
    'Subsequent EVENT': '4a4f55532d464958545552452d4c4541534501060000000c00000008000000000000000200000001630000000201720000000167000000080000000000000001000000017800000008524553455256454400000008000000000000000000000020623e6d5a2de819a64b3d6d6f348e69581adcdc2a096b2c666a8a56b631c5ac750000000800000000000000000000000201610000000100',
    'ACKNOWLEDGED EVENT': '4a4f55532d464958545552452d4c4541534501060000000c0000000800000000000000030000000163000000020172000000016700000008000000000000000100000001780000000c41434b4e4f574c4544474544000000080000000000000000000000202032dddef8645040803eef9c789a62f722cedb7fd1dd0c1fc2fded959db9d70f0000000800000000000000000000000201610000000100',
    'ACK': '4a4f55532d464958545552452d4c45415345010a0000001a000000016300000020f58d835a11128e077af416cda614e8e3ba9947da072ef4ce2e33a87751e07fc50000000170000000016700000008000000000000000100000001780000000172000000080000000000000000000000017000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f5245515545535400000020111111111111111111111111111111111111111111111111111111111111111100000020df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119000000203333333333333333333333333333333333333333333333333333333333333333000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e000000202222222222222222222222222222222222222222222222222222222222222222000000040000000000000008000000000000000000000008000000000000000000000008000000000000006400000008000000000000005a0000000800000000000000010000000800000000000000030000000800000000000000030000002054c6b63a0197ad58ca73c6ea0044c090a7fe3c90c022c7069ad18727538ea47d0000000753554343455353',
    'Minimal STATE': '4a4f55532d464958545552452d4c45415345020800000004024a4f55532d464958545552452d4c45415345020c0000000b00000008000000000000000100000008000000000000000100000001670000000800000000000000010000000178000000204444444444444444444444444444444444444444444444444444444444444444000000205555555555555555555555555555555555555555555555555555555555555555000000206666666666666666666666666666666666666666666666666666666666666666000000207777777777777777777777777777777777777777777777777777777777777777000000080000000000000000000000080000000000000000030003000300',
    'Completed-command STATE': '4a4f55532d464958545552452d4c45415345020800000004024a4f55532d464958545552452d4c45415345020c0000000b0000000800000000000000010000000800000000000000010000000167000000080000000000000001000000017800000020444444444444444444444444444444444444444444444444444444444444444400000020555555555555555555555555555555555555555555555555555555555555555500000020666666666666666666666666666666666666666666666666666666666666666600000020777777777777777777777777777777777777777777777777777777777777777700000008000000000000000000000008000000000000000003014a4f55532d464958545552452d4c45415345020d0000001800000001720000000167000000017300000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f52455155455354000000016100000020111111111111111111111111111111111111111111111111111111111111111100000001640000002018ac3e7343f016890c510e93f935261169d9e3f565436429830faf0934f4f8e40000000170000000017a00000008000000000000000000000008000000000000000000000008000000000000000000000008000000000000006400000008000000000000005a000000080000000000000000000000064c45415345440000000800000000000000000000000b4e4f545f5354415254454400000001000000000100000000010000030003014a4f55532d464958545552452d4c45415345020f0000000a000000016300000001700000000741435155495245000002614a4f55532d464958545552452d4c45415345010500000012000000074143515549524500000001700000000167000000080000000000000001000000017800000001630000000000000008000000000000000000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f524551554553540000002011111111111111111111111111111111111111111111111111111111111111110000000173000000594a4f55532d464958545552452d4c4541534501110000000300000001610000001450524f564953494f4e494e475f52455155455354000000201111111111111111111111111111111111111111111111111111111111111111000000203333333333333333333333333333333333333333333333333333333333333333000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e0000002022222222222222222222222222222222222222222222222222222222222222220000000400000000000000b14a4f55532d464958545552452d4c45415345011000000009000000017200000001000000005a014a4f55532d464958545552452d4c4541534501110000000300000001610000001450524f564953494f4e494e475f52455155455354000000201111111111111111111111111111111111111111111111111111111111111111000000010000000001000000000400000000000000090100000000000000640000000901000000000000005a000000010000000020f58d835a11128e077af416cda614e8e3ba9947da072ef4ce2e33a87751e07fc5000000080000000000000000000000020172000000075355434345535300000211014a4f55532d464958545552452d4c45415345010a0000001a000000016300000020f58d835a11128e077af416cda614e8e3ba9947da072ef4ce2e33a87751e07fc50000000170000000016700000008000000000000000100000001780000000172000000080000000000000000000000017000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f5245515545535400000020111111111111111111111111111111111111111111111111111111111111111100000020df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119000000203333333333333333333333333333333333333333333333333333333333333333000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e000000202222222222222222222222222222222222222222222222222222222222222222000000040000000000000008000000000000000000000008000000000000000000000008000000000000006400000008000000000000005a0000000800000000000000010000000800000000000000030000000800000000000000030000002054c6b63a0197ad58ca73c6ea0044c090a7fe3c90c022c7069ad18727538ea47d00000007535543434553530000000901000000000000000300',
    'Expiry COMMAND': '4a4f55532d464958545552452d4c454153450105000000120000000a51554152414e54494e4500000001700000000167000000080000000000000001000000017800000008632d657870697279000000017200000008000000000000000000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f524551554553540000002011111111111111111111111111111111111111111111111111111111111111110000000173000000594a4f55532d464958545552452d4c4541534501110000000300000001610000001450524f564953494f4e494e475f52455155455354000000201111111111111111111111111111111111111111111111111111111111111111000000209999999999999999999999999999999999999999999999999999999999999999000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e0000002022222222222222222222222222222222222222222222222222222222222222220000005c000000014a4f55532d464958545552452d4c4541534501110000000300000001650000001350524f56454e414e43455f45564944454e43450000002088888888888888888888888888888888888888888888888888888888888888880000010c4a4f55532d464958545552452d4c4541534501100000000900000001720000000100000000010000000001000000001501455850495245445f554e5245434f4e43494c45440000005c000000014a4f55532d464958545552452d4c4541534501110000000300000001650000001350524f56454e414e43455f45564944454e43450000002088888888888888888888888888888888888888888888888888888888888888880000000100000000010000000059014a4f55532d464958545552452d4c4541534501110000000300000001650000001350524f56454e414e43455f45564944454e4345000000208888888888888888888888888888888888888888888888888888888888888888',
    'EXPIRED EVENT': '4a4f55532d464958545552452d4c4541534501060000000c00000008000000000000000400000008632d6578706972790000000201720000000167000000080000000000000001000000017800000007455850495245440000000800000000000000650000002054c6b63a0197ad58ca73c6ea0044c090a7fe3c90c022c7069ad18727538ea47d000000080000000000000001000000020161000000020165',
    'QUARANTINED EVENT': '4a4f55532d464958545552452d4c4541534501060000000c00000008000000000000000500000008632d657870697279000000020172000000016700000008000000000000000100000001780000000b51554152414e54494e454400000008000000000000006500000020886e5f51e480e7df7c4c98b6ab1b67a7b0c000ee3d2954507c42fd5776c1b30b000000080000000000000001000000020161000000020165',
    'Expiry ACKNOWLEDGED EVENT': '4a4f55532d464958545552452d4c4541534501060000000c00000008000000000000000600000008632d657870697279000000020172000000016700000008000000000000000100000001780000000c41434b4e4f574c454447454400000008000000000000006500000020e0f165fb70e57a28e2ef514f60d61b3175c0defb9131c6e562f8b860260a4206000000080000000000000001000000020161000000020165',
    'Expiry ACK': '4a4f55532d464958545552452d4c45415345010a0000001a00000008632d65787069727900000020e8bf530487e83ea2800d10e4113820e1ac86a13276169cfadd9ae0389ac963510000000170000000016700000008000000000000000100000001780000000172000000080000000000000001000000017000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f5245515545535400000020111111111111111111111111111111111111111111111111111111111111111100000020df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119000000209999999999999999999999999999999999999999999999999999999999999999000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e0000002022222222222222222222222222222222222222222222222222222222222222220000005c000000014a4f55532d464958545552452d4c4541534501110000000300000001650000001350524f56454e414e43455f45564944454e434500000020888888888888888888888888888888888888888888888888888888888888888800000008000000000000006500000008000000000000000000000008000000000000006400000008000000000000005a00000008000000000000000400000008000000000000000600000008000000000000000300000020a24949136abe475b02473b59fda2e60e04ac2cd6cbab4ec0cd4e92e161d2fc200000000753554343455353',
    'Primary sorts first': '4a4f55532d464958545552452d4c4541534501100000000900000001720000000100000000010000000001000000000100000000c8000000024a4f55532d464958545552452d4c454153450111000000030000000a612d72657175697265640000001052454c454153455f45564944454e43450000002011111111111111111111111111111111111111111111111111111111111111114a4f55532d464958545552452d4c454153450111000000030000000f7a2d737570706c656d656e746172790000001350524f56454e414e43455f45564944454e4345000000202222222222222222222222222222222222222222222222222222222222222222000000010000000001000000005f014a4f55532d464958545552452d4c454153450111000000030000000a612d72657175697265640000001052454c454153455f45564944454e4345000000201111111111111111111111111111111111111111111111111111111111111111',
    'Supplementary sorts first': '4a4f55532d464958545552452d4c4541534501100000000900000001720000000100000000010000000001000000000100000000c8000000024a4f55532d464958545552452d4c454153450111000000030000000f612d737570706c656d656e746172790000001350524f56454e414e43455f45564944454e43450000002022222222222222222222222222222222222222222222222222222222222222224a4f55532d464958545552452d4c454153450111000000030000000a7a2d72657175697265640000001052454c454153455f45564944454e4345000000201111111111111111111111111111111111111111111111111111111111111111000000010000000001000000005f014a4f55532d464958545552452d4c454153450111000000030000000a7a2d72657175697265640000001052454c454153455f45564944454e4345000000201111111111111111111111111111111111111111111111111111111111111111',
    'Empty collection': '00000000',
    'One-item collection': '000000014a4f55532d464958545552452d4c454153450111000000030000000a612d72657175697265640000001052454c454153455f45564944454e4345000000201111111111111111111111111111111111111111111111111111111111111111',
    'Two-item collection': '000000024a4f55532d464958545552452d4c454153450111000000030000000a612d72657175697265640000001052454c454153455f45564944454e43450000002011111111111111111111111111111111111111111111111111111111111111114a4f55532d464958545552452d4c454153450111000000030000000f7a2d737570706c656d656e746172790000001350524f56454e414e43455f45564944454e4345000000202222222222222222222222222222222222222222222222222222222222222222',
}


if __name__ == "__main__":
    unittest.main(verbosity=2)
