"""Synthetic IL.2 tests; imports inspect source but never acquire operational facts."""
import ast
from dataclasses import FrozenInstanceError, replace
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
for name in ('fixture_lease_contract', 'fixture_lease_service'):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'services/api/infrastructure' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
s = sys.modules['fixture_lease_service']
c = sys.modules['fixture_lease_contract']


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.ref = s.EvidenceReference('synthetic', b'x' * 32)
        self.profile = s.QualifiedClockProfile(self.ref, 'synthetic-source', self.ref,
                                             10000000, 20000, 10000, 0)
        self.anchor = s.MonotonicPoint('synthetic-process', 'synthetic-domain', 100)
        self.sample = s.QualifiedSample(self.ref, 'synthetic-source', self.ref, self.ref,
                                       s.UtcInterval(1000, 1002), self.anchor)

    def error(self, elapsed=0, error=0):
        return s.QualifiedPropagationError(self.ref, self.ref, elapsed, error, self.ref)

    def evaluate(self, elapsed=0, error=0):
        return s.evaluate_time(self.sample, self.profile,
                               replace(self.anchor, ticks_ns=100 + elapsed), self.error(elapsed, error))

    def test_every_rejecting_default(self):
        default = s.RejectingCapabilities()
        methods = {'authenticate': 1, 'verify': 3, 'observe': 1, 'obtain': 2,
                   'complete': 2, 'reconcile': 2, 'read': 1, 'publish': 3,
                   'qualify': 2, 'measure': 0}
        for name, count in methods.items():
            with self.subTest(name=name), self.assertRaises(s.CapabilityUnavailable):
                getattr(default, name)(*([None] * count))

    def test_absence_is_positive_evidence(self):
        absent = s.ActivationObservation(s.AuthorityPresence.AUTHORITATIVE_ABSENT, self.ref, None)
        self.assertEqual(absent.evidence, self.ref)
        for presence in ('UNKNOWN', 'UNAVAILABLE', 'STALE', 'LOOKUP_FAILED', None, False):
            with self.subTest(presence=presence), self.assertRaises(s.TimeRejected):
                s.ActivationObservation(presence, self.ref, None)
        with self.assertRaises(s.TimeRejected):
            s.ActivationObservation(s.AuthorityPresence.AUTHORITATIVE_ABSENT, None, None)

    def test_inclusive_matrix(self):
        deadline = s.InclusiveDeadline(10)
        for lower, upper, result in [(1, 9, 'SATISFIED'), (10, 10, 'SATISFIED'),
                                     (11, 12, 'OUTSIDE'), (9, 11, 'UNCERTAIN')]:
            self.assertEqual(s.inclusive_bound(s.UtcInterval(lower, upper), deadline).value, result)

    def test_strict_matrix(self):
        deadline = s.StrictDeadline(10)
        for lower, upper, result in [(1, 9, 'SATISFIED'), (10, 10, 'OUTSIDE'),
                                     (11, 12, 'OUTSIDE'), (9, 10, 'UNCERTAIN')]:
            self.assertEqual(s.strict_bound(s.UtcInterval(lower, upper), deadline).value, result)

    def test_deadline_types_not_interchangeable(self):
        for fn, deadline in [(s.strict_bound, s.InclusiveDeadline(10)),
                             (s.inclusive_bound, s.StrictDeadline(10))]:
            with self.assertRaises(s.TimeRejected): fn(s.UtcInterval(1, 2), deadline)

    def test_valid_from(self):
        for lower, upper, result in [(9, 11, False), (10, 11, True), (11, 12, True)]:
            self.assertIs(s.valid_from_satisfied(s.UtcInterval(lower, upper), 10), result)

    def test_zero_elapsed(self):
        self.assertEqual(self.evaluate(), s.TimeEvaluation(s.UtcInterval(1000, 1002), 2, 0))

    def test_positive_elapsed_error_growth_and_outward_rounding(self):
        value = self.evaluate(1501, 502)
        self.assertEqual(value.interval, s.UtcInterval(1000, 1005))
        self.assertEqual(value.sample_age_upper_us, 3)
        self.assertEqual(value.command_uncertainty_us, 5)
        self.assertEqual(value, self.evaluate(1501, 502))

    def test_lower_rounds_down(self):
        self.assertEqual(self.evaluate(0, 1).interval, s.UtcInterval(999, 1003))

    def test_negative_elapsed(self):
        with self.assertRaises(s.TimeRejected):
            s.evaluate_time(self.sample, self.profile, replace(self.anchor, ticks_ns=99), self.error())

    def test_reversed_interval(self):
        with self.assertRaises(s.TimeRejected): s.UtcInterval(2, 1)

    def test_invalid_numeric_values(self):
        for bad in (True, False, 1.0, '1', None, 1 << 63):
            for make in (lambda: s.UtcInterval(bad, bad), lambda: s.StrictDeadline(bad),
                         lambda: replace(self.anchor, ticks_ns=bad),
                         lambda: self.error(error=bad)):
                with self.subTest(bad=bad), self.assertRaises(s.TimeRejected): make()
        with self.assertRaises(s.TimeRejected): self.error(error=-1)
        with self.assertRaises(s.TimeRejected): replace(self.profile, max_sample_age_us=-1)

    def test_overflow_rejected(self):
        sample = replace(self.sample, utc=s.UtcInterval((1 << 63)-1, (1 << 63)-1))
        with self.assertRaises(s.TimeRejected):
            s.evaluate_time(sample, self.profile, replace(self.anchor, ticks_ns=1100), self.error(1000))

    def test_qualification_limits(self):
        for profile in (replace(self.profile, max_elapsed_ns=0),
                        replace(self.profile, max_sample_age_us=0),
                        replace(self.profile, max_command_uncertainty_us=1)):
            with self.assertRaises(s.TimeRejected):
                s.evaluate_time(self.sample, profile, replace(self.anchor, ticks_ns=1100), self.error(1000))

    def test_error_evidence_binding(self):
        for error in (self.error(1), replace(self.error(), sample=s.EvidenceReference('other', b'y'*32)),
                      replace(self.error(), profile=s.EvidenceReference('other', b'y'*32))):
            with self.assertRaises(s.TimeRejected):
                s.evaluate_time(self.sample, self.profile, self.anchor, error)

    def test_restart_and_domain_rejected(self):
        for point in (replace(self.anchor, process_id='restarted'),
                      replace(self.anchor, domain_id='other-domain')):
            with self.assertRaises(s.TimeRejected):
                s.evaluate_time(self.sample, self.profile, point, self.error())

    def test_raw_evidence_not_qualified_sample(self):
        with self.assertRaises(s.TimeRejected):
            s.evaluate_time(s.RawTimeEvidence('synthetic-source', self.ref), self.profile,
                            self.anchor, self.error())

    def test_source_profile_mismatch(self):
        for sample in (replace(self.sample, source='other'),
                       replace(self.sample, profile=s.EvidenceReference('other', b'y'*32))):
            with self.assertRaises(s.TimeRejected):
                s.evaluate_time(sample, self.profile, self.anchor, self.error())

    def test_refresh_independent_and_no_narrowing(self):
        new = replace(self.sample, sample=s.EvidenceReference('fresh', b'y'*32),
                      anchor=replace(self.anchor, ticks_ns=1100), utc=s.UtcInterval(1000, 1005))
        self.assertTrue(s.refresh_consistent(self.sample, new, self.profile, self.error(1000)))
        self.assertEqual(new.utc, s.UtcInterval(1000, 1005))
        contradictory = replace(new, utc=s.UtcInterval(2000, 2001))
        self.assertFalse(s.refresh_consistent(self.sample, contradictory, self.profile, self.error(1000)))
        with self.assertRaises(s.TimeRejected):
            s.refresh_consistent(self.sample, self.sample, self.profile, self.error())

    def test_immutable_values(self):
        for value in (self.sample, self.profile, self.ref, self.anchor, self.error(), self.evaluate()):
            with self.assertRaises(FrozenInstanceError): value.unapproved = True

    def test_timing_is_not_permission_or_availability(self):
        value = self.evaluate()
        self.assertFalse(hasattr(value, 'authorized'))
        self.assertFalse(hasattr(value, 'available'))
        self.assertTrue(c.claims_remain_blocking(c.LeaseStatus.EXPIRED))
        self.assertTrue(c.claims_remain_blocking(c.LeaseStatus.QUARANTINED))

    def test_supporting_capability_values(self):
        context = s.CommandContext('synthetic-command', b'x'*32, c.Command.ACQUIRE,
                                   c.Operation.FIXTURE_PROVISIONING, c.Phase.PRE_AUTH, 0, self.ref)
        actor = s.AuthenticatedRequester('synthetic-requester', self.ref)
        artifact = c.ArtifactBytes(c.ArtifactType.PROVISIONING_REQUEST, b'synthetic')
        approval = s.VerifiedApproval('synthetic-reviewer', actor.principal, context, artifact, self.ref)
        activation = s.ActivationIdentity('synthetic-register', 1, 'synthetic-activation',
                                          'synthetic-host', self.ref)
        observation = s.ActivationObservation(s.AuthorityPresence.AUTHORITATIVE_PRESENT,
                                              self.ref, activation)
        permit = s.CommandPermit(context, activation, 1, 2, self.ref)
        self.assertEqual(observation.activation, permit.activation)
        self.assertEqual(approval.context, permit.context)
        with self.assertRaises(s.TimeRejected): replace(approval, approver=actor.principal)
        with self.assertRaises(s.TimeRejected): replace(context, reservation_revision=True)
        with self.assertRaises(s.TimeRejected): replace(permit, valid_until_us=0)
        with self.assertRaises(s.TimeRejected): replace(activation, generation=0)
        with self.assertRaises(s.TimeRejected): replace(observation, activation=None)

    def test_import_boundary(self):
        tree = ast.parse((ROOT / 'services/api/infrastructure/fixture_lease_service.py').read_text())
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imports, {'dataclasses', 'enum', 'fractions', 'typing', 'fixture_lease_contract'})
        self.assertFalse(any(isinstance(node, ast.Import) for node in ast.walk(tree)))
        forbidden = {'open', 'eval', 'exec', '__import__'}
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                             and node.func.id in forbidden for node in ast.walk(tree)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
