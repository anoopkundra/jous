"""V1.4B normalization contract tests; never invoke a provider or database."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
import unittest

from jous_api.usage_events import (
    NORMALIZER_VERSION, UsageNormalizationError, normalize_execution,
)


class UsageNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 20, 12, 30, tzinfo=timezone.utc)
        self.task = SimpleNamespace(
            id=uuid4(), organization_id=uuid4(), project_id=uuid4(), actor_user_id=uuid4(),
            dispatch_claim_id=uuid4(), logical_model_id="jous.text.general.v1",
            supplier_id="supplier-a", underlying_provider="provider-a",
            request_parameters={"route_id": "route-a"})
        self.execution = SimpleNamespace(
            id=uuid4(), task_id=self.task.id, organization_id=self.task.organization_id,
            project_id=self.task.project_id, actor_user_id=self.task.actor_user_id,
            dispatch_claim_id=self.task.dispatch_claim_id, status="succeeded",
            usage={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            usage_status="available", reported_provider_id="provider-a-reported",
            request_started_at=self.now, response_received_at=self.now,
            recorded_at=self.now)

    def test_available_preserves_only_source_dimensions_and_is_deterministic(self):
        first = normalize_execution(self.task, self.execution)
        second = normalize_execution(self.task, self.execution)
        self.assertEqual(first, second)
        self.assertEqual(first.normalizer_version, NORMALIZER_VERSION)
        self.assertEqual((first.input_tokens, first.output_tokens, first.total_tokens), (11, 7, 18))
        self.assertIsNone(first.cached_input_tokens)
        self.assertIsNone(first.reasoning_tokens)
        self.assertEqual(first.evidence_sha256.hex(), __import__("hashlib").sha256(
            first.canonical_payload.encode("utf-8")).hexdigest())

    def test_partial_does_not_infer_total_or_optional_zeroes(self):
        self.execution.usage_status = "partial"
        self.execution.usage = {"input_tokens": 11}
        event = normalize_execution(self.task, self.execution)
        self.assertEqual(event.input_tokens, 11)
        self.assertIsNone(event.output_tokens)
        self.assertIsNone(event.total_tokens)
        self.assertIsNone(event.cached_input_tokens)

    def test_unavailable_is_all_null_and_distinct_from_zero(self):
        self.execution.usage_status = "unavailable"
        self.execution.usage = None
        absent = normalize_execution(self.task, self.execution)
        self.execution.usage_status = "partial"
        self.execution.usage = {"input_tokens": 0}
        zero = normalize_execution(self.task, self.execution)
        self.assertIsNone(absent.input_tokens)
        self.assertEqual(zero.input_tokens, 0)
        self.assertNotEqual(absent.evidence_sha256, zero.evidence_sha256)

    def test_failure_refusal_unknown_and_not_dispatched_keep_source_status(self):
        for status, usage_status, usage, error in (
            ("known_error", "partial", {"input_tokens": 2}, "supplier_rejected"),
            ("refused", "available", {"input_tokens": 2, "output_tokens": 1,
                                        "total_tokens": 3}, None),
            ("unknown", "unavailable", None, "provider_timeout"),
            ("known_error", "unavailable", None, "not_dispatched"),
        ):
            with self.subTest(status=status, error=error):
                self.execution.status = status
                self.execution.usage_status = usage_status
                self.execution.usage = usage
                self.execution.error_code = error
                event = normalize_execution(self.task, self.execution)
                self.assertEqual(event.usage_status, usage_status.upper())

    def test_available_requires_contract_fields_and_preserves_reported_total(self):
        self.execution.usage = {"input_tokens": 5, "output_tokens": 4}
        with self.assertRaises(UsageNormalizationError):
            normalize_execution(self.task, self.execution)
        self.execution.usage = {"input_tokens": 5, "output_tokens": 4, "total_tokens": 8}
        event = normalize_execution(self.task, self.execution)
        self.assertEqual(event.total_tokens, 8)

    def test_invalid_and_unknown_source_dimensions_fail_closed(self):
        for usage in ({"input_tokens": -1}, {"input_tokens": True},
                      {"input_tokens": 2.0}, {"new_token_kind": 2}, {}):
            with self.subTest(usage=usage):
                self.execution.usage_status = "partial"
                self.execution.usage = usage
                with self.assertRaises(UsageNormalizationError):
                    normalize_execution(self.task, self.execution)

    def test_route_decision_is_optional_but_exactly_bound_when_present(self):
        legacy = normalize_execution(self.task, self.execution)
        self.assertIsNone(legacy.route_decision_id)
        decision = SimpleNamespace(task_id=self.task.id,
            organization_id=self.task.organization_id, project_id=self.task.project_id,
            actor_user_id=self.task.actor_user_id, dispatch_claim_id=self.task.dispatch_claim_id,
            logical_model_id=self.task.logical_model_id, logical_model_version=2,
            selected_route_id="route-a", selected_route_version=1)
        dispatch_route = SimpleNamespace(route_id="route-a", supplier_id=self.task.supplier_id,
            underlying_provider=self.task.underlying_provider)
        bound = normalize_execution(self.task, self.execution, route_decision=decision,
                                    dispatch_route=dispatch_route)
        self.assertEqual(bound.route_decision_id, self.task.id)
        self.assertEqual((bound.logical_model_version, bound.route_version), (2, 1))
        decision.dispatch_claim_id = uuid4()
        with self.assertRaises(UsageNormalizationError):
            normalize_execution(self.task, self.execution, route_decision=decision,
                                dispatch_route=dispatch_route)

    def test_execution_tenant_project_actor_claim_and_identity_are_bound(self):
        for field, value in (
            ("organization_id", uuid4()), ("project_id", uuid4()),
            ("actor_user_id", uuid4()), ("dispatch_claim_id", uuid4()),
            ("task_id", uuid4()),
        ):
            with self.subTest(field=field):
                original = getattr(self.execution, field)
                setattr(self.execution, field, value)
                with self.assertRaises(UsageNormalizationError):
                    normalize_execution(self.task, self.execution)
                setattr(self.execution, field, original)

    def test_route_decision_tenant_project_actor_claim_model_and_route_are_bound(self):
        decision = SimpleNamespace(task_id=self.task.id,
            organization_id=self.task.organization_id, project_id=self.task.project_id,
            actor_user_id=self.task.actor_user_id, dispatch_claim_id=self.task.dispatch_claim_id,
            logical_model_id=self.task.logical_model_id, logical_model_version=2,
            selected_route_id="route-a", selected_route_version=3)
        for field, value in (
            ("organization_id", uuid4()), ("project_id", uuid4()),
            ("actor_user_id", uuid4()), ("dispatch_claim_id", uuid4()),
            ("task_id", uuid4()), ("logical_model_id", "jous.other.v1"),
            ("selected_route_id", "other-route"),
        ):
            with self.subTest(field=field):
                original = getattr(decision, field)
                setattr(decision, field, value)
                with self.assertRaises(UsageNormalizationError):
                    normalize_execution(self.task, self.execution, route_decision=decision)
                setattr(decision, field, original)

    def test_corrected_normalization_is_new_event_linked_to_predecessor(self):
        old = normalize_execution(self.task, self.execution)
        new = normalize_execution(self.task, self.execution,
            normalizer_version="jous.execution-usage.v2",
            supersedes_usage_event_id=old.usage_event_id)
        self.assertNotEqual(old.usage_event_id, new.usage_event_id)
        self.assertEqual(new.supersedes_usage_event_id, old.usage_event_id)
        self.assertNotEqual(old.canonical_payload, new.canonical_payload)

    def test_canonical_payload_is_locale_independent_and_has_explicit_nulls(self):
        self.execution.usage_status = "partial"
        self.execution.usage = {"input_tokens": 0}
        event = normalize_execution(self.task, self.execution)
        self.assertIn('"output_tokens":null', event.canonical_payload)
        self.assertIn('"input_tokens":0', event.canonical_payload)
        self.assertNotIn("e+", event.canonical_payload.lower())
