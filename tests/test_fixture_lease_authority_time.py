"""Unexecuted RFC3161/monotonic source tests; no TSA/OS-time authority."""
from fractions import Fraction
import importlib
import unittest
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import test_fixture_lease_activation as frozen

t = importlib.import_module(frozen.PACKAGE + ".fixture_lease_authority_time")
e, p = t.e, t.p


class TimeTests(unittest.TestCase):
    def test_conservative_interval_uses_entire_elapsed(self):
        interval = t.conservative_interval(1000000, 100, 9000000, 1000)
        self.assertEqual((interval.lower_us, interval.upper_us), (999900, 1009101))
        self.assertGreater(interval.upper_us, 1000000 + 4500)

    def test_submicroseconds_round_outward(self):
        interval = t.conservative_interval(Fraction(1, 2), 0, 1, 0)
        self.assertEqual((interval.lower_us, interval.upper_us), (0, 1))
        with self.assertRaises(e.EvidenceFailure):
            t.conservative_interval(0, False, 1, 0)

    def test_no_current_without_new_startup_sample(self):
        bridge = t.Rfc3161Bridge(policy=Mock(), profile=Mock(), authority=Mock(), evidence=Mock(),
                                 transport=Mock(), monotonic=Mock(), entropy=Mock())
        with self.assertRaises(e.EvidenceFailure):
            bridge.current()
        bridge.transport.assert_not_called()

    def test_restart_invalidates_anchor(self):
        profile = p.s.QualifiedClockProfile(frozen.ref("profile"), "synthetic-tsa", frozen.ref("qualification"),
                                           1000000, 1000, 1000, 0)
        anchor = p.s.MonotonicPoint("original-process", "domain", 0)
        sample = p.s.QualifiedSample(frozen.ref("sample"), profile.source, profile.profile,
                                     frozen.ref("validation"), p.s.UtcInterval(0, 0), anchor)
        monotonic = Mock()
        monotonic.observe.return_value = p.s.MonotonicPoint("replacement-process", "domain", 0)
        bridge = t.Rfc3161Bridge(policy=Mock(), profile=profile, authority=Mock(), evidence=Mock(),
                                 transport=Mock(), monotonic=monotonic, entropy=Mock())
        bridge._publish(sample, bridge._epoch)
        with self.assertRaises(e.EvidenceFailure):
            bridge.current()
        bridge.authority.propagation.assert_not_called()

    def test_frozen_propagation_limits_are_used(self):
        profile = p.s.QualifiedClockProfile(frozen.ref("profile"), "synthetic-tsa", frozen.ref("qualification"),
                                           1000000, 1000, 1000, 0)
        anchor = p.s.MonotonicPoint("process", "domain", 0)
        sample = p.s.QualifiedSample(frozen.ref("sample"), profile.source, profile.profile,
                                     frozen.ref("validation"), p.s.UtcInterval(0, 0), anchor)
        monotonic, authority = Mock(), Mock()
        monotonic.observe.return_value = p.s.MonotonicPoint("process", "domain", 1000)
        authority.propagation.return_value = p.s.QualifiedPropagationError(sample.sample, profile.profile,
            1000, 1, frozen.ref("error"))
        bridge = t.Rfc3161Bridge(policy=Mock(), profile=profile, authority=authority, evidence=Mock(),
                                 transport=Mock(), monotonic=monotonic, entropy=Mock())
        bridge._publish(sample, bridge._epoch)
        binding = bridge.current()
        self.assertEqual(binding.error.elapsed_ns, 1000)
        bridge.invalidate()
        with self.assertRaises(e.EvidenceFailure):
            bridge.current()

    def test_request_nonce_policy_imprint_and_der(self):
        from asn1crypto import tsp
        policy = t.TsaPolicy(frozen.ref("DigiCert-Europe"), "1.2.3.4", "0" * 64, (), 1000000,
            ("sha256_rsa",), frozen.ref("entitlement"), frozen.ref("approved-bootstrap"), (), frozen.ref("q"))
        raw = t.request_der(context_bytes=b"exact request context", nonce=b"n" * 16, policy=policy)
        parsed = tsp.TimeStampReq.load(raw, strict=True)
        self.assertEqual(parsed["nonce"].native, int.from_bytes(b"n" * 16, "big"))
        self.assertEqual(parsed["req_policy"].native, policy.policy_oid)
        self.assertEqual(parsed["message_imprint"]["hashed_message"].native, t.sha256(b"exact request context").digest())
        with self.assertRaises(e.EvidenceFailure):
            t.request_der(context_bytes=b"context", nonce=b"\x00" * 16, policy=policy)

    def test_malformed_response_cannot_be_trusted_time(self):
        policy = t.TsaPolicy(frozen.ref("DigiCert-Europe"), "1.2.3.4", "0" * 64, (), 1000000,
            ("sha256_rsa",), frozen.ref("entitlement"), frozen.ref("approved-bootstrap"), (), frozen.ref("q"))
        request = t.request_der(context_bytes=b"context", nonce=b"n" * 16, policy=policy)
        with self.assertRaises(e.EvidenceFailure):
            t.validate_response(request_raw=request, response_raw=b"malformed", context_bytes=b"context",
                                policy=policy, authority=Mock())


class AtomicTimeTests(unittest.TestCase):
    def fixture(self):
        profile = p.s.QualifiedClockProfile(frozen.ref("profile"), "synthetic-clock", frozen.ref("q"),
                                          1000000, 1000, 1000, 0)
        anchor = p.s.MonotonicPoint("A", "domain-A", 0)
        sample = p.s.QualifiedSample(frozen.ref("sample-A"), profile.source, profile.profile,
                                    frozen.ref("validation-A"), p.s.UtcInterval(0, 0), anchor)
        authority, monotonic = Mock(), Mock()
        monotonic.observe.return_value = p.s.MonotonicPoint("A", "domain-A", 1000)
        bridge = t.Rfc3161Bridge(policy=Mock(), profile=profile, authority=authority, evidence=Mock(),
                                transport=Mock(), monotonic=monotonic, entropy=Mock())
        bridge._publish(sample, bridge._epoch)
        return bridge, sample

    def test_refresh_current_cannot_mix_a_b(self):
        bridge, sample = self.fixture()
        entered, release = Event(), Event()
        def propagation(actual, profile, current):
            self.assertIs(actual, sample)
            self.assertEqual(current.process_id, "A")
            entered.set()
            self.assertTrue(release.wait(5))
            return p.s.QualifiedPropagationError(actual.sample, profile.profile, 1000, 0, frozen.ref("error-A"))
        bridge.authority.propagation.side_effect = propagation
        with ThreadPoolExecutor(max_workers=1) as worker:
            pending = worker.submit(bridge.current)
            self.assertTrue(entered.wait(5))
            b_anchor = p.s.MonotonicPoint("B", "domain-B", 0)
            sample_b = p.s.QualifiedSample(frozen.ref("sample-B"), bridge.profile.source, bridge.profile.profile,
                                          frozen.ref("validation-B"), p.s.UtcInterval(0, 0), b_anchor)
            bridge._publish(sample_b, bridge._epoch)
            release.set()
            with self.assertRaises(e.EvidenceFailure):
                pending.result(timeout=5)
        self.assertIs(bridge._state[0], sample_b)

    def test_invalidation_current_cannot_return_stale_snapshot(self):
        bridge, sample = self.fixture()
        entered, release = Event(), Event()
        def propagation(actual, profile, current):
            entered.set()
            self.assertTrue(release.wait(5))
            return p.s.QualifiedPropagationError(actual.sample, profile.profile, 1000, 0, frozen.ref("error"))
        bridge.authority.propagation.side_effect = propagation
        with ThreadPoolExecutor(max_workers=1) as worker:
            pending = worker.submit(bridge.current)
            self.assertTrue(entered.wait(5))
            bridge.invalidate()
            release.set()
            with self.assertRaises(e.EvidenceFailure):
                pending.result(timeout=5)
        self.assertIsNone(bridge._state)

    def test_invalidation_during_actual_refresh_cannot_republish(self):
        bridge, _ = self.fixture()
        entered, release = Event(), Event()
        raw = b"sample-context"
        context = p.RetainedEvidence(p.s.EvidenceReference("context", t.sha256(raw).digest()), raw)
        def transport(request):
            entered.set()
            self.assertTrue(release.wait(5))
            return b"controlled-validation-double-not-CMS"
        bridge.transport.timestamp.side_effect = transport
        bridge.monotonic.observe.return_value = p.s.MonotonicPoint("A", "domain-A", 1000)
        bridge.authority.response_record.return_value = p.RetainedEvidence(frozen.ref("response"), b"response")
        bridge.authority.elapsed_errors.return_value = (0, 0)
        bridge.authority.retain_validation.return_value = frozen.ref("validation")
        with patch.object(t, "request_der", return_value=b"controlled-request"), \
             patch.object(t, "validate_response", return_value=(0, 0)):
            with ThreadPoolExecutor(max_workers=1) as worker:
                pending = worker.submit(bridge.sample, request_id="refresh", context_record=context)
                self.assertTrue(entered.wait(5))
                bridge.invalidate()
                release.set()
                with self.assertRaises(e.EvidenceFailure):
                    pending.result(timeout=5)
        self.assertIsNone(bridge._state)
        self.assertEqual(bridge.transport.timestamp.call_count, 1)
        with self.assertRaises(e.EvidenceFailure):
            bridge.sample(request_id="refresh", context_record=context)
        self.assertEqual(bridge.transport.timestamp.call_count, 1)

    def test_current_returns_exact_combination_validated(self):
        bridge, sample = self.fixture()
        current = bridge.monotonic.observe.return_value
        error = p.s.QualifiedPropagationError(sample.sample, bridge.profile.profile, 1000, 0, frozen.ref("error"))
        bridge.authority.propagation.return_value = error
        actual = bridge.current()
        self.assertIs(actual.sample, sample)
        self.assertIs(actual.current, current)
        self.assertIs(actual.error, error)

    def test_tsa_transport_exception_has_no_carrier_chain(self):
        bridge, _ = self.fixture()
        bridge.authority.authorize_sample.side_effect = RuntimeError("SENSITIVE-TSA-CARRIER")
        raw = b"context"
        context = p.RetainedEvidence(p.s.EvidenceReference("context", t.sha256(raw).digest()), raw)
        with self.assertRaises(e.EvidenceFailure) as failed:
            bridge.sample(request_id="one", context_record=context)
        self.assertNotIn("SENSITIVE", str(failed.exception))
        self.assertIsNone(failed.exception.__context__)
        self.assertIsNone(failed.exception.__cause__)
        self.assertEqual(vars(failed.exception), {})

# A real independently generated positive CMS fixture is intentionally deferred
# to the test-realization gate. Synthetic validation doubles test synchronization
# only and never bypass production CMS/path/policy/status validation.
