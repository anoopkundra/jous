"""Deterministic IL.1 tests; no database, network, clock or operational adapters."""
import ast
from dataclasses import FrozenInstanceError, replace
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'services/api/infrastructure/fixture_lease_contract.py'
spec = importlib.util.spec_from_file_location('fixture_lease_contract', MODULE)
c = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = c
spec.loader.exec_module(c)


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.scope = c.DatabaseTargetScope('synthetic-target')
        self.provider = c.ProviderAllocationScope('synthetic-provider')
        self.ids = tuple(UUID(int=value) for value in range(1, 9))
        self.keys = (c.ConflictKey.fixture_set(self.scope, 'synthetic-set'),) + tuple(
            c.ConflictKey.db_uuid(self.scope, value) for value in self.ids)
        self.request = c.ArtifactBytes(c.ArtifactType.PROVISIONING_REQUEST, b'synthetic-request')
        self.binding = c.Binding(c.Operation.FIXTURE_PROVISIONING, c.Phase.PRE_AUTH, self.request)
        self.reservation = c.ReservationValue('reservation', 'synthetic-set', 'operator',
            self.binding, c.LeaseStatus.LEASED, 100, 90, 0, self.ids, b'synthetic-values', self.keys)

    def rejected(self, function, *args):
        with self.assertRaises(c.ContractRejected):
            function(*args)

    def test_closed_domains(self):
        expected = {
            c.Operation: {'FIXTURE_PROVISIONING', 'CANARY', 'FIXTURE_MAINTENANCE', 'FIXTURE_RETIREMENT'},
            c.LeaseStatus: {'LEASED', 'EXPIRED', 'QUARANTINED', 'RELEASED'},
            c.Phase: {'PRE_AUTH_PROVISIONING_REQUEST', 'AUTH_IDENTITIES_BOUND', 'NOT_APPLICABLE'},
            c.IssuerMode: {'RECOVERY_ONLY', 'ACTIVE'},
            c.ArtifactType: {'PROVISIONING_REQUEST', 'FIXTURE_MANIFEST', 'PROVENANCE_EVIDENCE',
                             'RELEASE_EVIDENCE', 'RECOVERY_EVIDENCE', 'AUTHORIZATION'},
            c.Command: {'ACQUIRE', 'ADVANCE', 'RECORD_EXECUTION', 'QUARANTINE', 'RELEASE', 'RECOVER'},
        }
        for enum, values in expected.items():
            self.assertEqual({value.value for value in enum}, values)
            for value in values:
                self.assertEqual(enum(value).value, value)
            with self.assertRaises(ValueError):
                enum('UNSUPPORTED')
        self.assertEqual([value.value for value in c.ConflictFamily], [1, 2, 3, 4])

    def test_frozen_values(self):
        for value in (self.scope, self.provider, self.keys[0], self.request, self.binding, self.reservation):
            name = next(iter(value.__dataclass_fields__))
            with self.assertRaises(FrozenInstanceError):
                setattr(value, name, None)

    def test_exact_published_frame_vector(self):
        key = c.ConflictKey.fixture_set(c.DatabaseTargetScope('db'), 'set')
        self.assertEqual(key.canonical_bytes,
            b'JOUS-FIXTURE-LEASE\x01\x01\x00\x00\x00\x02'
            b'\x00\x00\x00\x02db\x00\x00\x00\x03set')

    def test_all_families_roundtrip(self):
        keys = (*self.keys, c.ConflictKey.logical_actor(self.provider, 'actor'),
                c.ConflictKey.issuer_subject('synthetic-issuer', 'subject'))
        for key in keys:
            self.assertEqual(c.decode_conflict(key.canonical_bytes), key)

    def test_deterministic_value_identity(self):
        first = c.ConflictKey.db_uuid(self.scope, self.ids[0])
        second = c.ConflictKey.db_uuid(c.DatabaseTargetScope('synthetic-target'), UUID(int=1))
        self.assertEqual(first, second)
        self.assertEqual(first.canonical_bytes, second.canonical_bytes)

    def test_delimiter_ambiguity(self):
        a = c.ConflictKey.issuer_subject('a|b', 'c')
        b = c.ConflictKey.issuer_subject('a', 'b|c')
        self.assertNotEqual(a.canonical_bytes, b.canonical_bytes)

    def test_family_separation(self):
        keys = [c.ConflictKey(family, (b'a', b'0123456789abcdef')) for family in c.ConflictFamily]
        self.assertEqual(len({key.canonical_bytes for key in keys}), 4)

    def test_uuid_table_independence(self):
        key = c.ConflictKey.db_uuid(self.scope, self.ids[0])
        self.assertEqual(key.fields, (b'synthetic-target', self.ids[0].bytes))
        with self.assertRaises(TypeError):
            c.ConflictKey.db_uuid(self.scope, self.ids[0], 'users')

    def test_target_scope_separation(self):
        self.assertNotEqual(c.ConflictKey.db_uuid(self.scope, self.ids[0]),
            c.ConflictKey.db_uuid(c.DatabaseTargetScope('other'), self.ids[0]))

    def test_scope_type_separation(self):
        self.rejected(c.ConflictKey.logical_actor, self.scope, 'actor')
        self.rejected(c.ConflictKey.fixture_set, self.provider, 'set')

    def test_provider_scope_separation(self):
        self.assertNotEqual(c.ConflictKey.logical_actor(self.provider, 'actor'),
            c.ConflictKey.logical_actor(c.ProviderAllocationScope('other'), 'actor'))

    def test_exact_issuer_subject_bytes(self):
        original = c.ConflictKey.issuer_subject('ISSUER', ' subject ')
        for other in (c.ConflictKey.issuer_subject('issuer', ' subject '),
                      c.ConflictKey.issuer_subject('ISSUER', 'subject')):
            self.assertNotEqual(original, other)
        self.assertNotEqual(c.ConflictKey.issuer_subject('issuer', '\u00e9'),
                            c.ConflictKey.issuer_subject('issuer', 'e\u0301'))

    def test_no_database_scope_in_pair_key(self):
        self.assertEqual(c.ConflictKey.issuer_subject('issuer', 'subject').fields,
                         (b'issuer', b'subject'))

    def test_scope_bounds_and_malformed_text(self):
        for cls in (c.DatabaseTargetScope, c.ProviderAllocationScope):
            for value in ('', '  ', '\ud800', 'a' * 256, '\u00e9' * 128, 1, b'bytes'):
                self.rejected(cls, value)
            self.assertEqual(cls(' x ').value, ' x ')
            cls('x' * 255)

    def test_canonical_uuid_text(self):
        value = '00000000-0000-0000-0000-00000000000a'
        self.assertEqual(c.canonical_uuid(value).bytes, UUID(value).bytes)
        for invalid in (value.upper(), value.replace('-', ''), '{'+value+'}', 'bad', 1):
            self.rejected(c.canonical_uuid, invalid)

    def test_encoder_rejects_bad_shapes(self):
        for family, fields in ((1, (b'a', b'b')), (c.ConflictFamily.FIXTURE_SET, [b'a', b'b']),
                (c.ConflictFamily.FIXTURE_SET, (b'a',)),
                (c.ConflictFamily.FIXTURE_SET, (b'a', b'b', b'c')),
                (c.ConflictFamily.FIXTURE_SET, (b'a', bytearray(b'b'))),
                (c.ConflictFamily.FIXTURE_SET, (b'a', b'\xff')),
                (c.ConflictFamily.ISSUER_SUBJECT, (b'a', b'b' * 65536)),
                (c.ConflictFamily.DB_UUID, (b'a', b'b' * 15))):
            self.rejected(c.frame_conflict, family, fields)

    def test_decoder_rejects_all_truncations(self):
        raw = self.keys[0].canonical_bytes
        for length in range(len(raw)):
            self.rejected(c.decode_conflict, raw[:length])

    def test_decoder_rejects_noncanonical_frames(self):
        raw = self.keys[0].canonical_bytes
        n = len(c.PREFIX)
        for bad in (raw+b'extra', b'X'+raw[1:], raw[:n]+b'\x02'+raw[n+1:],
                    raw[:n+1]+b'\x09'+raw[n+2:], raw[:n+2]+b'\0\0\0\3'+raw[n+6:],
                    raw[:n+6]+b'\0\0\0\0'+raw[n+10:], bytearray(raw)):
            self.rejected(c.decode_conflict, bad)

    def test_exact_duplicate_set_deduplication(self):
        self.assertEqual(c.canonical_conflict_set(self.keys+self.keys),
                         c.canonical_conflict_set(tuple(reversed(self.keys))))
        self.assertEqual(len(c.canonical_conflict_set(self.keys)), 9)

    def test_digest_collision_cannot_replace_full_identity(self):
        # Identity/equality never invokes digest helpers, even if they collide.
        original = c.sha256_evidence
        try:
            c.sha256_evidence = lambda raw: b'0' * 32
            a = c.ConflictKey.issuer_subject('issuer', 'a')
            b = c.ConflictKey.issuer_subject('issuer', 'b')
            self.assertNotEqual(a, b)
            self.assertEqual(len(c.canonical_conflict_set((a, b))), 2)
        finally:
            c.sha256_evidence = original

    def test_sha256_known_vector(self):
        self.assertEqual(c.sha256_evidence(b'abc').hex(),
                         'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
        self.rejected(c.sha256_evidence, 'abc')

    def test_artifact_bounds_and_immutability(self):
        for raw in (b'', bytearray(b'a'), 'a', b'a' * (1024*1024+1)):
            self.rejected(c.ArtifactBytes, c.ArtifactType.AUTHORIZATION, raw)
        self.rejected(c.ArtifactBytes, 'AUTHORIZATION', b'a')
        self.assertEqual(self.request.evidence_sha256, hashlib.sha256(self.request.exact_bytes).digest())

    def test_binding_hash_types_never_substitute(self):
        manifest = c.ArtifactBytes(c.ArtifactType.FIXTURE_MANIFEST, self.request.exact_bytes)
        canary = c.Binding(c.Operation.CANARY, c.Phase.NOT_APPLICABLE, manifest)
        self.assertEqual(canary.fixture_manifest_sha256, self.binding.provisioning_request_sha256)
        self.rejected(c.Binding, c.Operation.CANARY, c.Phase.NOT_APPLICABLE, self.request)
        self.rejected(c.Binding, c.Operation.FIXTURE_PROVISIONING, c.Phase.PRE_AUTH, manifest)
        with self.assertRaises(c.ContractRejected):
            _ = self.binding.fixture_manifest_sha256
        with self.assertRaises(c.ContractRejected):
            _ = canary.provisioning_request_sha256

    def test_invalid_phase_and_disabled_operations(self):
        for operation in (c.Operation.FIXTURE_MAINTENANCE, c.Operation.FIXTURE_RETIREMENT):
            self.rejected(c.Binding, operation, c.Phase.NOT_APPLICABLE, self.request)
        self.rejected(c.Binding, c.Operation.CANARY, c.Phase.PRE_AUTH, self.request)
        self.rejected(c.Binding, 'FIXTURE_PROVISIONING', c.Phase.PRE_AUTH, self.request)

    def test_phase_matrix(self):
        for operation in c.Operation:
            for before in c.Phase:
                for after in c.Phase:
                    self.assertEqual(c.phase_advance_allowed(operation, before, after),
                        operation is c.Operation.FIXTURE_PROVISIONING and
                        before is c.Phase.PRE_AUTH and after is c.Phase.AUTH_IDENTITIES_BOUND)

    def bound_next(self):
        binding = c.Binding(c.Operation.FIXTURE_PROVISIONING, c.Phase.AUTH_IDENTITIES_BOUND,
                           c.ArtifactBytes(c.ArtifactType.PROVISIONING_REQUEST, b'bound-request'))
        pairs = (c.ConflictKey.issuer_subject('issuer', 'a'), c.ConflictKey.issuer_subject('issuer', 'b'))
        return replace(self.reservation, binding=binding, revision=1, claims=self.keys+pairs)

    def test_forward_transition_retains_keys(self):
        self.assertTrue(c.structurally_permitted_transition(self.reservation, self.bound_next(), c.Command.ADVANCE))

    def test_phase_downgrade(self):
        before = self.bound_next()
        after = replace(self.reservation, revision=2)
        self.assertFalse(c.structurally_permitted_transition(before, after, c.Command.ADVANCE))

    def test_operation_conversion(self):
        binding = c.Binding(c.Operation.CANARY, c.Phase.NOT_APPLICABLE,
                           c.ArtifactBytes(c.ArtifactType.FIXTURE_MANIFEST, b'manifest'))
        self.assertFalse(c.structurally_permitted_transition(self.reservation,
            replace(self.reservation, binding=binding, revision=1), c.Command.ADVANCE))

    def test_immutable_transition_fields(self):
        for kwargs in ({'owner':'other'}, {'reservation_id':'other'}, {'fixture_set_id':'other'},
                       {'expires_at':101}, {'completion_deadline':89},
                       {'immutable_database_projection':b'changed'},
                       {'database_ids':tuple(reversed(self.ids))}):
            after = replace(self.bound_next(), **kwargs)
            self.assertFalse(c.structurally_permitted_transition(self.reservation, after, c.Command.ADVANCE))

    def test_missing_old_claim_and_unrelated_added_claim(self):
        after = self.bound_next()
        for claims in (after.claims[1:], after.claims+(c.ConflictKey.fixture_set(self.scope, 'other'),)):
            self.assertFalse(c.structurally_permitted_transition(self.reservation,
                replace(after, claims=claims), c.Command.ADVANCE))

    def test_revision_and_unleased_advance(self):
        for before in (replace(self.reservation, status=c.LeaseStatus.EXPIRED),
                       replace(self.reservation, status=c.LeaseStatus.QUARANTINED)):
            self.assertFalse(c.structurally_permitted_transition(before, self.bound_next(), c.Command.ADVANCE))
        self.assertFalse(c.structurally_permitted_transition(self.reservation,
            replace(self.bound_next(), revision=2), c.Command.ADVANCE))

    def test_expired_and_quarantined_claims_block(self):
        for status in (c.LeaseStatus.LEASED, c.LeaseStatus.EXPIRED, c.LeaseStatus.QUARANTINED):
            self.assertTrue(c.claims_remain_blocking(status))
            with self.assertRaises(c.ContractRejected):
                replace(self.reservation, status=status, claims=())
        self.assertFalse(c.claims_remain_blocking(c.LeaseStatus.RELEASED))

    def test_expiry_never_implicitly_releases(self):
        expired = replace(self.reservation, status=c.LeaseStatus.EXPIRED)
        released = replace(expired, status=c.LeaseStatus.RELEASED, claims=(), revision=1)
        for command in c.Command:
            self.assertFalse(c.structurally_permitted_transition(expired, released, command))

    def test_release_shape_needs_typed_evidence(self):
        released = replace(self.reservation, status=c.LeaseStatus.RELEASED, claims=(), revision=1)
        evidence = c.ArtifactBytes(c.ArtifactType.RELEASE_EVIDENCE, b'structure-only')
        self.assertTrue(c.structurally_permitted_transition(self.reservation, released, c.Command.RELEASE, evidence))
        self.assertFalse(c.structurally_permitted_transition(self.reservation, released, c.Command.RELEASE, self.request))
        self.assertFalse(c.structurally_permitted_transition(self.reservation, released, c.Command.RELEASE, True))

    def test_recovery_and_no_released_takeover(self):
        before = replace(self.reservation, status=c.LeaseStatus.QUARANTINED)
        released = replace(before, status=c.LeaseStatus.RELEASED, claims=(), revision=1)
        evidence = c.ArtifactBytes(c.ArtifactType.RECOVERY_EVIDENCE, b'structure-only')
        self.assertTrue(c.structurally_permitted_transition(before, released, c.Command.RECOVER, evidence))
        self.assertFalse(c.structurally_permitted_transition(self.reservation, released, c.Command.RECOVER, evidence))
        self.assertFalse(c.structurally_permitted_transition(released,
            replace(self.reservation, revision=2), c.Command.ACQUIRE))

    def test_quarantined_release_rejected_recovery_and_evidence_separated(self):
        before = replace(self.reservation, status=c.LeaseStatus.QUARANTINED)
        released = replace(before, status=c.LeaseStatus.RELEASED, claims=(), revision=1)
        release = c.ArtifactBytes(c.ArtifactType.RELEASE_EVIDENCE, b'structure-only')
        recovery = c.ArtifactBytes(c.ArtifactType.RECOVERY_EVIDENCE, b'structure-only')
        self.assertFalse(c.structurally_permitted_transition(before, released, c.Command.RELEASE, release))
        self.assertTrue(c.structurally_permitted_transition(before, released, c.Command.RECOVER, recovery))
        self.assertFalse(c.structurally_permitted_transition(before, released, c.Command.RECOVER, release))
        self.assertFalse(c.structurally_permitted_transition(before, released, c.Command.RELEASE, recovery))

    def test_ordinary_release_preserved_for_leased_and_expired(self):
        release = c.ArtifactBytes(c.ArtifactType.RELEASE_EVIDENCE, b'structure-only')
        recovery = c.ArtifactBytes(c.ArtifactType.RECOVERY_EVIDENCE, b'structure-only')
        for status in (c.LeaseStatus.LEASED, c.LeaseStatus.EXPIRED):
            before = replace(self.reservation, status=status)
            released = replace(before, status=c.LeaseStatus.RELEASED, claims=(), revision=1)
            self.assertTrue(c.structurally_permitted_transition(before, released, c.Command.RELEASE, release))
            self.assertFalse(c.structurally_permitted_transition(before, released, c.Command.RELEASE, recovery))

    def test_quarantine_retains_exact_keys(self):
        after = replace(self.reservation, status=c.LeaseStatus.QUARANTINED, revision=1)
        self.assertTrue(c.structurally_permitted_transition(self.reservation, after, c.Command.QUARANTINE))
        self.assertFalse(c.structurally_permitted_transition(self.reservation,
            replace(after, claims=self.keys[1:]), c.Command.QUARANTINE))

    def test_invalid_reservation_ranges(self):
        for kwargs in ({'revision':True}, {'revision':-1}, {'revision':1<<64},
                       {'expires_at':1<<63}, {'expires_at':True}, {'expires_at':90},
                       {'database_ids':self.ids[:-1]}, {'database_ids':self.ids[:-1]+(self.ids[0],)},
                       {'claims':list(self.keys)}, {'immutable_database_projection':bytearray(b'a')}):
            with self.assertRaises(c.ContractRejected):
                replace(self.reservation, **kwargs)

    def test_standard_library_pure_import_boundary(self):
        tree = ast.parse(MODULE.read_text(encoding='utf-8'))
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imports, {'dataclasses', 'enum', 'hashlib', 'uuid'})
        self.assertFalse(any(isinstance(node, ast.Import) for node in ast.walk(tree)))
        forbidden = {'open', 'exec', 'eval', '__import__', 'compile', 'input'}
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                             and node.func.id in forbidden for node in ast.walk(tree)))


if __name__ == '__main__':
    unittest.main()
