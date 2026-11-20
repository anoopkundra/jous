"""Offline V1.3A economics contracts. No network, provider, or database access."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from jous_api.route_economics import (
    ContractError,
    LogicalModelVersion,
    PricingVersion,
    ReasonCode,
    RouteDecision,
    RouteVersion,
    canonical_decimal,
    decide_routes,
    effective_cost,
    evaluate_route,
)


NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def model(*, status="approved", version=1):
    return LogicalModelVersion(
        logical_model_id="jous.text.general.v1",
        version=version,
        display_name="Qwen3-32B reference",
        model_authority_id="qwen3-32b-reference-2026-11-16",
        required_capabilities=("text_generation",),
        context_capacity=32768,
        max_output_allowance=1024,
        status=status,
    )


def route(
    route_id="route-a",
    *,
    enabled=True,
    admission=True,
    token_authority="verified",
    capabilities=("text_generation",),
    context=32768,
    tier="standard",
    route_kind="direct",
    gateway_id=None,
    provider_selection="direct",
    underlying_provider="DeepInfra",
    dynamic_envelope=False,
    dynamic_envelope_id=None,
):
    return RouteVersion(
        route_id=route_id,
        version=1,
        logical_model_id="jous.text.general.v1",
        logical_model_version=1,
        supplier_id="supplier_x",
        supplier_native_model_id="Qwen/Qwen3-32B",
        underlying_provider=underlying_provider,
        route_kind=route_kind,
        gateway_id=gateway_id,
        provider_selection=provider_selection,
        service_tier=tier,
        capabilities=capabilities,
        context_capacity=context,
        operational_enabled=enabled,
        admission_authorized=admission,
        token_authority_status=token_authority,
        route_authority_id="route-authority-v1",
        dynamic_provider_envelope_authorized=dynamic_envelope,
        dynamic_provider_envelope_id=dynamic_envelope_id,
    )


def pricing(
    route_id="route-a",
    *,
    input_price="1",
    output_price="2",
    provider_fee="0",
    gateway_fee=None,
    fee_verified=True,
    provider_fee_applicable=True,
    gateway_fee_applicable=False,
    revoked=False,
    status="approved",
    tier="standard",
    effective_from=NOW - timedelta(days=1),
    valid_until=NOW + timedelta(days=1),
    pricing_id=None,
    evidence_id=None,
):
    return PricingVersion(
        pricing_version_id=pricing_id or f"price-{route_id}",
        route_id=route_id,
        route_version=1,
        service_tier=tier,
        currency="USD",
        input_price_per_1m=Decimal(input_price),
        output_price_per_1m=Decimal(output_price),
        provider_request_fee=None if provider_fee is None else Decimal(provider_fee),
        gateway_request_fee=None if gateway_fee is None else Decimal(gateway_fee),
        fee_basis_verified=fee_verified,
        source_type="manual_review",
        source_evidence_id=evidence_id or f"test-evidence-{route_id}",
        reviewed_at=NOW - timedelta(days=1),
        effective_from=effective_from,
        valid_until=valid_until,
        status=status,
        provider_fee_applicable=provider_fee_applicable,
        gateway_fee_applicable=gateway_fee_applicable,
        revoked=revoked,
    )


def evaluate(r, p=None, *, m=None, at=NOW, input_bound=100, output=20, required=()):
    return evaluate_route(r, m or model(), decision_time=at, input_token_bound=input_bound,
                          output_allowance=output, required_capabilities=required, pricing=p)


class DecimalAndPricingTests(unittest.TestCase):
    def test_exact_decimal_cost_formula_and_fee_components(self):
        cost = effective_cost(1234, 1000, Decimal("0.08"), Decimal("0.28"), Decimal("0.001"))
        self.assertEqual(cost, Decimal("0.00137872"))

    def test_canonical_money_has_no_rounding_or_exponent_notation(self):
        self.assertEqual(canonical_decimal(Decimal("12.340000")), "12.34")
        self.assertEqual(canonical_decimal(Decimal("1E-8")), "0.00000001")
        self.assertEqual(canonical_decimal(Decimal("-0")), "0")
        with self.assertRaises(ContractError):
            effective_cost(1, 1, 0.1, Decimal("0.2"), Decimal("0"))

    def test_source_rates_reject_binary_float_and_excess_precision(self):
        with self.assertRaises(ContractError):
            PricingVersion(
                pricing_version_id="p1", route_id="route-a", route_version=1, service_tier="standard",
                currency="USD", input_price_per_1m=0.1, output_price_per_1m=Decimal("1"),
                provider_request_fee=Decimal("0"), gateway_request_fee=Decimal("0"), fee_basis_verified=True,
                source_type="manual_review", source_evidence_id="evidence-1", reviewed_at=NOW,
                effective_from=NOW, valid_until=NOW + timedelta(days=1), status="approved",
            )
        with self.assertRaises(ContractError):
            PricingVersion(
                pricing_version_id="p1", route_id="route-a", route_version=1, service_tier="standard",
                currency="USD", input_price_per_1m=Decimal("0.0000000000001"), output_price_per_1m=Decimal("1"),
                provider_request_fee=Decimal("0"), gateway_request_fee=Decimal("0"), fee_basis_verified=True,
                source_type="manual_review", source_evidence_id="evidence-1", reviewed_at=NOW,
                effective_from=NOW, valid_until=NOW + timedelta(days=1), status="approved",
            )

    def test_price_interval_is_inclusive_start_exclusive_end(self):
        p = pricing(effective_from=NOW, valid_until=NOW + timedelta(hours=1))
        self.assertTrue(evaluate(route(), p, at=NOW).economic_eligible)
        self.assertIn(ReasonCode.PRICING_EXPIRED, evaluate(route(), p, at=p.valid_until).economic_reason_codes)
        self.assertIn(ReasonCode.PRICING_NOT_EFFECTIVE,
                      evaluate(route(), pricing(effective_from=NOW + timedelta(seconds=1)), at=NOW).economic_reason_codes)

    def test_missing_expired_unverified_and_unknown_fee_are_ineligible(self):
        self.assertIn(ReasonCode.PRICING_MISSING, evaluate(route()).economic_reason_codes)
        expired = pricing(valid_until=NOW)
        self.assertIn(ReasonCode.PRICING_EXPIRED, evaluate(route(), expired).economic_reason_codes)
        pending = pricing(status="pending")
        self.assertIn(ReasonCode.PRICING_UNVERIFIED, evaluate(route(), pending).economic_reason_codes)
        unknown_fee = pricing(provider_fee=None, fee_verified=False)
        self.assertIn(ReasonCode.BILLING_BASIS_UNRESOLVED, evaluate(route(), unknown_fee).economic_reason_codes)

    def test_non_applicable_gateway_fee_is_absent_while_applicable_zero_is_explicit(self):
        direct = pricing(gateway_fee=None, gateway_fee_applicable=False)
        self.assertEqual(direct.total_request_fee, Decimal("0"))
        self.assertTrue(evaluate(route(), direct).economic_eligible)
        unknown = pricing(provider_fee=None, fee_verified=False)
        self.assertIsNone(unknown.total_request_fee)
        self.assertIn(ReasonCode.BILLING_BASIS_UNRESOLVED, evaluate(route(), unknown).economic_reason_codes)
        gateway_zero = pricing(gateway_fee="0", gateway_fee_applicable=True)
        self.assertEqual(gateway_zero.total_request_fee, Decimal("0"))

    def test_revoked_price_is_ineligible_without_rewriting_price_status(self):
        result = evaluate(route(), pricing(revoked=True))
        self.assertFalse(result.economic_eligible)
        self.assertIn(ReasonCode.PRICING_REVOKED, result.economic_reason_codes)

    def test_pricing_version_is_immutable(self):
        p = pricing()
        with self.assertRaises(FrozenInstanceError):
            p.status = "withdrawn"


class RouteEvaluationTests(unittest.TestCase):
    def test_operational_admission_and_economic_eligibility_are_separate(self):
        result = evaluate(route(enabled=False), pricing())
        self.assertFalse(result.operational_eligible)
        self.assertTrue(result.economic_eligible)
        self.assertFalse(result.eligible)
        self.assertIn(ReasonCode.ROUTE_DISABLED, result.operational_reason_codes)
        denied = evaluate(route(admission=False), pricing())
        self.assertIn(ReasonCode.ADMISSION_DENIED, denied.operational_reason_codes)

    def test_unresolved_token_authority_is_denied(self):
        result = evaluate(route(token_authority="unresolved"), pricing())
        self.assertIn(ReasonCode.TOKEN_AUTHORITY_UNRESOLVED, result.operational_reason_codes)
        self.assertFalse(result.eligible)

    def test_capability_and_context_mismatches_are_denied(self):
        self.assertIn(ReasonCode.CAPABILITY_MISMATCH,
                      evaluate(route(capabilities=()), pricing()).operational_reason_codes)
        self.assertIn(ReasonCode.CONTEXT_UNSUPPORTED,
                      evaluate(route(context=100), pricing(), input_bound=90, output=20).operational_reason_codes)
        self.assertIn(ReasonCode.CONTEXT_UNSUPPORTED,
                      evaluate(route(), pricing(), output=1025).operational_reason_codes)

    def test_candidate_model_is_not_selectable(self):
        result = evaluate(route(), pricing(), m=model(status="candidate"))
        self.assertIn(ReasonCode.MODEL_NOT_APPROVED, result.operational_reason_codes)
        self.assertTrue(result.economic_eligible)
        self.assertFalse(result.eligible)

    def test_route_and_price_service_tier_must_match(self):
        result = evaluate(route(tier="flex"), pricing(tier="standard"))
        self.assertIn(ReasonCode.BILLING_BASIS_UNRESOLVED, result.economic_reason_codes)
        self.assertFalse(result.economic_eligible)

    def test_dynamic_gateway_needs_explicit_complete_envelope_authority(self):
        dynamic = route(route_kind="gateway", gateway_id="gateway-x", provider_selection="dynamic",
                        underlying_provider=None)
        result = evaluate(dynamic, pricing())
        self.assertIn(ReasonCode.BILLING_BASIS_UNRESOLVED, result.economic_reason_codes)
        authorized = route(route_kind="gateway", gateway_id="gateway-x", provider_selection="dynamic",
                           underlying_provider=None, dynamic_envelope=True,
                           dynamic_envelope_id="bounded-price-envelope-v1")
        self.assertFalse(evaluate(authorized, pricing(gateway_fee="0", gateway_fee_applicable=True)).economic_eligible)
        self.assertTrue(evaluate(authorized, pricing(gateway_fee="0", gateway_fee_applicable=True,
                                                      evidence_id="bounded-price-envelope-v1")).economic_eligible)


class DecisionTests(unittest.TestCase):
    def decide(self, candidates):
        routes, prices = candidates
        return decide_routes(model(), routes, prices, decision_time=NOW, input_token_bound=100, output_allowance=20)

    def test_exact_cost_ranks_lowest_cost_first(self):
        a, b = route("route-a"), route("route-b")
        p_a = pricing("route-a", input_price="3", output_price="4")
        p_b = pricing("route-b", input_price="1", output_price="1")
        decision = self.decide(([a, b], {"route-a": p_a, "route-b": p_b}))
        self.assertEqual(decision.selected_route_id, "route-b")
        self.assertEqual(decision.candidate_evaluations[0].route_id, "route-a")
        self.assertEqual(next(x.economic_rank for x in decision.candidate_evaluations if x.route_id == "route-b"), 1)

    def test_exact_tie_uses_immutable_route_id_ascending(self):
        decision = self.decide(([route("z-route"), route("a-route")],
                                {"z-route": pricing("z-route"), "a-route": pricing("a-route")}))
        self.assertEqual(decision.selected_route_id, "a-route")
        self.assertIn(ReasonCode.TIE_BREAK_ROUTE_ID, decision.selection_rationale)

    def test_no_eligible_candidate_fails_closed(self):
        decision = self.decide(([route("denied", enabled=False)], {"denied": pricing("denied")}))
        self.assertIsNone(decision.selected_route_id)
        self.assertIsNone(decision.estimated_cost)
        self.assertEqual(decision.selection_rationale, (ReasonCode.NO_ELIGIBLE_ROUTE,))

    def test_decision_is_input_order_independent_and_canonical(self):
        routes = [route("b-route"), route("a-route")]
        prices = {"a-route": pricing("a-route"), "b-route": pricing("b-route")}
        first = self.decide((routes, prices))
        second = self.decide((list(reversed(routes)), prices))
        self.assertEqual(first.canonical_json(), second.canonical_json())
        self.assertEqual(first.sha256, second.sha256)
        self.assertLessEqual(len(first.canonical_json().encode("utf-8")), 65_536)

    def test_persisted_snapshot_hash_covers_exact_utf8_text_bytes(self):
        decision = self.decide(([route()], {"route-a": pricing()}))
        snapshot, digest = decision.snapshot_evidence()
        import hashlib
        self.assertEqual(digest, hashlib.sha256(snapshot.encode("utf-8")).digest())
        self.assertEqual(len(digest), 32)
        self.assertEqual(snapshot, decision.canonical_json())

    def test_direct_construction_normalizes_candidate_order(self):
        decision = self.decide(([route("b-route"), route("a-route")],
                                {"a-route": pricing("a-route"), "b-route": pricing("b-route")}))
        reversed_candidates = tuple(reversed(decision.candidate_evaluations))
        direct = RouteDecision(
            decision_version=decision.decision_version,
            logical_model_id=decision.logical_model_id,
            logical_model_version=decision.logical_model_version,
            selector_version=decision.selector_version,
            decision_time=decision.decision_time,
            selected_route_id=decision.selected_route_id,
            selected_route_version=decision.selected_route_version,
            selected_pricing_version_id=decision.selected_pricing_version_id,
            estimated_cost=decision.estimated_cost,
            currency=decision.currency,
            input_token_bound=decision.input_token_bound,
            output_allowance=decision.output_allowance,
            candidate_evaluations=reversed_candidates,
            selection_rationale=decision.selection_rationale,
        )
        self.assertEqual([item.route_id for item in direct.candidate_evaluations], ["a-route", "b-route"])
        self.assertEqual(direct.canonical_json(), decision.canonical_json())

    def test_factory_and_direct_construction_have_same_canonical_order(self):
        decision = self.decide(([route("b-route"), route("a-route")],
                                {"a-route": pricing("a-route"), "b-route": pricing("b-route")}))
        direct = RouteDecision(
            decision.decision_version, decision.logical_model_id, decision.logical_model_version,
            decision.selector_version, decision.decision_time, decision.selected_route_id,
            decision.selected_route_version, decision.selected_pricing_version_id,
            decision.estimated_cost, decision.currency, decision.input_token_bound,
            decision.output_allowance, tuple(reversed(decision.candidate_evaluations)),
            decision.selection_rationale,
        )
        self.assertEqual(direct.candidate_evaluations, decision.candidate_evaluations)
        self.assertEqual(direct.canonical_json(), decision.canonical_json())

    def test_dataclasses_replace_cannot_reintroduce_order_variance(self):
        decision = self.decide(([route("b-route"), route("a-route")],
                                {"a-route": pricing("a-route"), "b-route": pricing("b-route")}))
        replaced = replace(decision, candidate_evaluations=tuple(reversed(decision.candidate_evaluations)))
        self.assertEqual(replaced.candidate_evaluations, decision.candidate_evaluations)
        self.assertEqual(replaced.canonical_json(), decision.canonical_json())

    def test_duplicate_candidate_identity_is_rejected_not_deduplicated(self):
        decision = self.decide(([route("a-route")], {"a-route": pricing("a-route")}))
        duplicate = decision.candidate_evaluations + decision.candidate_evaluations
        with self.assertRaises(ContractError):
            replace(decision, candidate_evaluations=duplicate)

    def test_decision_remains_immutable_and_serialization_is_stable(self):
        decision = self.decide(([route("a-route")], {"a-route": pricing("a-route")}))
        first = decision.canonical_json()
        self.assertIsInstance(decision.candidate_evaluations, tuple)
        self.assertEqual(first, decision.canonical_json())
        with self.assertRaises(FrozenInstanceError):
            decision.candidate_evaluations = ()

    def test_more_than_64_candidates_is_rejected(self):
        routes = [route(f"route-{index:02d}") for index in range(65)]
        with self.assertRaises(ContractError):
            self.decide((routes, {}))


class HistoricalQwenEvidenceTests(unittest.TestCase):
    """Exact reviewed 2026-11-16 evidence; never current production pricing."""

    HISTORICAL_TEST_EVIDENCE = {
        "hf_deepinfra_standard": ("0.08", "0.28", "standard", "pending"),
        "vercel_catalog": ("0.15", "0.60", "standard", "pending"),
        "vercel_from_quote": ("0.08", "0.28", "standard", "pending"),
        "openrouter_deepinfra_standard": ("0.08", "0.28", "standard", "pending"),
        "openrouter_deepinfra_flex": ("0.064", "0.224", "flex", "pending"),
    }

    def test_historical_rates_are_preserved_as_non_current_unverified_evidence(self):
        expected = self.HISTORICAL_TEST_EVIDENCE
        self.assertEqual(expected["hf_deepinfra_standard"][:2], ("0.08", "0.28"))
        self.assertEqual(expected["vercel_catalog"][:2], ("0.15", "0.60"))
        self.assertEqual(expected["vercel_from_quote"][:2], ("0.08", "0.28"))
        self.assertEqual(expected["openrouter_deepinfra_standard"][:2], ("0.08", "0.28"))
        self.assertEqual(expected["openrouter_deepinfra_flex"][:2], ("0.064", "0.224"))
        for _, _, _, status in expected.values():
            self.assertEqual(status, "pending")

    def test_flex_is_a_distinct_service_tier_and_is_not_substituted_for_standard(self):
        flex_route = route("openrouter-qwen-flex", route_kind="gateway", gateway_id="openrouter",
                           provider_selection="pinned", underlying_provider="DeepInfra", tier="flex")
        standard_pricing = pricing("openrouter-qwen-flex", tier="standard", status="pending")
        result = evaluate(flex_route, standard_pricing)
        self.assertIn(ReasonCode.BILLING_BASIS_UNRESOLVED, result.economic_reason_codes)
        self.assertFalse(result.economic_eligible)

    def test_historical_hf_reference_remains_disabled_and_admission_denied(self):
        hf = route("hf-qwen3-32b-deepinfra-v1", enabled=False, admission=False,
                   token_authority="unresolved", route_kind="gateway", gateway_id="hugging_face",
                   provider_selection="pinned", underlying_provider="DeepInfra")
        result = evaluate(hf, pricing(hf.route_id, status="pending"))
        self.assertFalse(result.operational_eligible)
        self.assertIn(ReasonCode.ADMISSION_DENIED, result.operational_reason_codes)
        self.assertIn(ReasonCode.TOKEN_AUTHORITY_UNRESOLVED, result.operational_reason_codes)


if __name__ == "__main__":
    unittest.main()
