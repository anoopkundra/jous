"""Pure V1.4C receipt derivation tests; no database/network access."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import inspect
import json
import unittest
from uuid import uuid4

from jous_api.economic_receipts import (
    CALCULATION_VERSION,
    ECONOMIC_POLICY_VERSION,
    TREATMENT_POLICY_DIGEST,
    TREATMENT_POLICY_VERSION,
    EconomicReceiptDerivationError,
    _numeric_50_18,
    _pricing_snapshot,
    _verify_existing_assessment,
    derive_economic_receipt_candidate,
    derive_and_persist_economic_receipt,
)


class EconomicReceiptDerivationTests(unittest.TestCase):
    def setUp(self):
        self.usage = {
            "usage_event_id": uuid4(), "organization_id": uuid4(), "project_id": uuid4(),
            "actor_user_id": uuid4(), "task_id": uuid4(), "dispatch_claim_id": uuid4(),
            "execution_id": uuid4(), "route_decision_id": None, "route_id": "route-a",
            "supplier_id": "supplier-a",
            "route_version": 1, "usage_status": "AVAILABLE", "input_tokens": 11,
            "output_tokens": 7, "total_tokens": 18, "source_type": "execution_usage",
            "source_revision": "execution-row-v1", "normalizer_version": "jous.execution-usage.v1",
            "evidence_sha256": hashlib.sha256(b"usage-source").digest(),
            "observed_at": datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc),
        }
        self.execution = {
            "id": self.usage["execution_id"], "task_id": self.usage["task_id"],
            "organization_id": self.usage["organization_id"], "project_id": self.usage["project_id"],
            "actor_user_id": self.usage["actor_user_id"],
            "dispatch_claim_id": self.usage["dispatch_claim_id"],
            "request_started_at": None, "credential_authority_ref": None,
        }
        self.decision = {
            "task_id": self.usage["task_id"],
            "organization_id": self.usage["organization_id"], "project_id": self.usage["project_id"],
            "actor_user_id": self.usage["actor_user_id"], "dispatch_claim_id": self.usage["dispatch_claim_id"],
            "pricing_version_id": "price-v1", "selected_route_id": "route-a", "selected_route_version": 1,
            "service_tier": "standard", "currency": "USD", "billing_basis": "input_output_tokens",
            "funding_authority_id": None, "funding_authority_version": None,
            "funding_authority_digest": None,
        }
        self.usage["route_decision_id"] = self.usage["task_id"]
        self.pricing = {
            "pricing_version_id": "price-v1", "route_id": "route-a", "route_version": 1,
            "service_tier": "standard", "currency": "USD", "billing_basis": "input_output_tokens",
            "input_price_per_1m": Decimal("1.000000000000"),
            "output_price_per_1m": Decimal("2.000000000000"),
            "provider_fee_applicable": True, "provider_request_fee_usd": Decimal("0.000000000000"),
            "gateway_fee_applicable": False, "gateway_request_fee_usd": None,
            "fee_basis_verified": True, "source_type": "manual_review", "source_evidence_id": "ev-1",
            "reviewed_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "effective_from": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "valid_until": datetime(2027, 1, 1, tzinfo=timezone.utc), "pricing_status": "approved",
        }
        self.key = hashlib.sha256(b"assessment-key").digest()

    def derive(self, usage=None, decision="default", pricing="default", funding_authority=None,
               execution="default"):
        return derive_economic_receipt_candidate(
            self.usage if usage is None else usage,
            self.decision if decision == "default" else decision,
            self.pricing if pricing == "default" else pricing,
            self.key,
            funding_authority,
            self.execution if execution == "default" else execution,
        )

    def authority(self, *, bearer="JOUS_BORNE", scope="JOUS_GLOBAL", owner="JOUS", organization_id=None):
        authority_id = uuid4()
        effective_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        payload = {
            "schema_version": "jous.supplier-funding-authority.v1",
            "funding_authority_id": str(authority_id), "authority_version": 1,
            "scope": scope, "organization_id": None if organization_id is None else str(organization_id),
            "supplier_id": "supplier-a", "route_id": "route-a", "route_version": 1,
            "credential_authority_ref": "opaque-test-account-ref", "account_owner": owner,
            "cost_bearer": bearer, "evidence_type": "controlled_fixture",
            "evidence_reference": "fixture:funding-authority-1",
            "effective_at": "2026-01-01T00:00:00.000000Z",
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).digest()
        return {"funding_authority_id": authority_id, "authority_version": 1, "scope": scope,
            "organization_id": organization_id, "supplier_id": "supplier-a", "route_id": "route-a",
            "route_version": 1, "credential_authority_ref": "opaque-test-account-ref",
            "account_owner": owner, "cost_bearer": bearer, "evidence_type": "controlled_fixture",
            "evidence_reference": "fixture:funding-authority-1", "effective_at": effective_at,
            "canonical_evidence": canonical, "authority_digest": digest}

    def bind_authority(self, authority):
        return {**self.decision, "funding_authority_id": authority["funding_authority_id"],
            "funding_authority_version": authority["authority_version"],
            "funding_authority_digest": authority["authority_digest"]}

    def test_stable_policy_identity_and_receipt_id(self):
        first, second = self.derive(), self.derive()
        self.assertEqual(first.assessment_key, second.assessment_key)
        self.assertEqual(first.economic_receipt_id, second.economic_receipt_id)
        self.assertEqual(first.economic_policy_version, "jous.economic-assessment.v1")
        self.assertEqual(first.calculation_version, "jous.token-cost.v1")
        self.assertEqual(TREATMENT_POLICY_VERSION, "jous.cost-bearer.v1")
        self.assertEqual(len(TREATMENT_POLICY_DIGEST), 32)
        self.assertEqual(first.cost_bearer, "UNKNOWN")

    def test_available_input_output_and_fee_math(self):
        result = self.derive()
        self.assertEqual(result.assessment_status, "COMPUTED")
        self.assertEqual(result.provider_usage_cost_usd, Decimal("0.000025000000000000"))
        self.assertEqual(result.provider_request_fee_usd, Decimal("0E-18"))
        self.assertEqual(result.gateway_request_fee_usd, Decimal("0E-18"))
        self.assertEqual(result.computed_usage_cost_usd, Decimal("0.000025000000000000"))
        self.assertEqual(result.cost_bearer, "UNKNOWN")

    def test_component_only_math_and_combined_fees(self):
        usage = {**self.usage, "input_tokens": 0, "output_tokens": 3}
        pricing = {**self.pricing, "input_price_per_1m": Decimal("0"),
                   "output_price_per_1m": Decimal("4"),
                   "provider_request_fee_usd": Decimal("0.000000000003"),
                   "gateway_fee_applicable": True, "gateway_request_fee_usd": Decimal("0.000000000004")}
        result = self.derive(usage, pricing=pricing)
        self.assertEqual(result.provider_usage_cost_usd, Decimal("0.000012000000000000"))
        self.assertEqual(result.provider_request_fee_usd, Decimal("3E-12"))
        self.assertEqual(result.gateway_request_fee_usd, Decimal("4E-12"))
        self.assertEqual(result.computed_usage_cost_usd, Decimal("0.000012000007000000"))

    def test_input_only_and_output_only_pricing(self):
        input_only = self.derive({**self.usage, "output_tokens": 0}, pricing=self.pricing)
        output_only = self.derive({**self.usage, "input_tokens": 0}, pricing=self.pricing)
        self.assertEqual(input_only.provider_usage_cost_usd, Decimal("0.000011000000000000"))
        self.assertEqual(output_only.provider_usage_cost_usd, Decimal("0.000014000000000000"))

    def test_exact_zero_and_zero_tokens_are_known_not_missing(self):
        usage = {**self.usage, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        pricing = {**self.pricing, "input_price_per_1m": Decimal("0"),
                   "output_price_per_1m": Decimal("0"), "provider_request_fee_usd": Decimal("0")}
        result = self.derive(usage, pricing=pricing)
        self.assertEqual(result.assessment_status, "COMPUTED")
        self.assertEqual(result.computed_usage_cost_usd, Decimal("0E-18"))
        partial = self.derive({**usage, "usage_status": "PARTIAL", "input_tokens": None})
        self.assertEqual(partial.assessment_status, "INCOMPLETE_USAGE")
        self.assertIsNone(partial.computed_usage_cost_usd)

    def test_usage_and_pricing_status_mapping(self):
        partial = {**self.usage, "usage_status": "PARTIAL", "output_tokens": None, "total_tokens": None}
        self.assertEqual(self.derive(partial).assessment_status, "INCOMPLETE_USAGE")
        unavailable = {**self.usage, "usage_status": "UNAVAILABLE", "input_tokens": None,
                       "output_tokens": None, "total_tokens": None}
        self.assertEqual(self.derive(unavailable).assessment_status, "UNAVAILABLE_USAGE")
        self.assertEqual(self.derive(pricing=None).assessment_status, "MISSING_PRICING")
        legacy = {**self.usage, "route_decision_id": None}
        self.assertEqual(self.derive(legacy, decision=None, pricing=None).assessment_status, "MISSING_PRICING")
        for bad in (
            {**self.pricing, "provider_request_fee_usd": None},
            {**self.pricing, "fee_basis_verified": False},
            {**self.pricing, "pricing_status": "revoked"},
        ):
            self.assertEqual(self.derive(pricing=bad).assessment_status, "MISSING_PRICING")

    def test_missing_dimensions_are_not_zero_and_available_requires_values(self):
        partial = {**self.usage, "usage_status": "PARTIAL", "input_tokens": None}
        self.assertIsNone(self.derive(partial).provider_usage_cost_usd)
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive({**self.usage, "input_tokens": None})
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive({**self.usage, "usage_status": "UNAVAILABLE", "input_tokens": 0})

    def test_decimal_precision_is_exact_and_never_rounded(self):
        self.assertEqual(_numeric_50_18(Decimal("1.2300000000000000000"), "test"),
                         Decimal("1.230000000000000000"))
        with self.assertRaises(EconomicReceiptDerivationError):
            _numeric_50_18(Decimal("0.0000000000000000001"), "test")
        with self.assertRaises(EconomicReceiptDerivationError):
            _numeric_50_18(Decimal("1E32"), "test")
        pricing = {**self.pricing, "input_price_per_1m": Decimal("0.000000000001"),
                   "output_price_per_1m": Decimal("0"), "provider_request_fee_usd": Decimal("0")}
        self.assertEqual(self.derive(pricing=pricing).provider_usage_cost_usd,
                         Decimal("0.000000000000000011"))
        too_precise = {**pricing, "input_price_per_1m": Decimal("0.0000000000001")}
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(pricing=too_precise)

    def test_numeric_50_18_boundary_is_exact_for_route_pricing_types(self):
        # V1.3 rates are NUMERIC(20,12), usage counts are BIGINT, and
        # multiplying then scaling by 10^-6 cannot exceed scale 18.
        tokens = 2**63 - 1
        rate = Decimal("99999999.999999999999")
        with localcontext() as context:
            context.prec = 100
            expected = Decimal(tokens) * rate / Decimal(1_000_000)
        self.assertEqual(_numeric_50_18(expected, "boundary"), expected)
        self.assertEqual(expected.as_tuple().exponent, -18)

    def test_snapshot_is_deterministic_and_null_distinct_from_zero(self):
        one, one_hash = _pricing_snapshot(self.pricing)
        two, two_hash = _pricing_snapshot(dict(reversed(list(self.pricing.items()))))
        self.assertEqual((one, one_hash), (two, two_hash))
        null_pricing = {**self.pricing, "gateway_request_fee_usd": None}
        zero_pricing = {**self.pricing, "gateway_request_fee_usd": Decimal("0")}
        self.assertNotEqual(_pricing_snapshot(null_pricing)[0], _pricing_snapshot(zero_pricing)[0])
        changed_price = {**self.pricing, "input_price_per_1m": Decimal("3")}
        self.assertNotEqual(_pricing_snapshot(self.pricing)[1], _pricing_snapshot(changed_price)[1])
        self.assertEqual(one_hash, hashlib.sha256(one.encode("utf-8")).digest())

    def test_source_binding_and_exact_pricing_binding_fail_closed(self):
        forged = {**self.decision, "organization_id": uuid4()}
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(decision=forged)
        forged_route = {**self.decision, "task_id": uuid4()}
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(decision=forged_route)
        forged_price_id = {**self.pricing, "pricing_version_id": "other"}
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(pricing=forged_price_id)
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive({**self.usage, "evidence_sha256": b"bad"})
        self.assertNotIn("route_id", self.derive().insert_values())

    def test_replay_collision_mismatch_fails_closed(self):
        candidate = self.derive()
        existing = {**candidate.insert_values(), "assessment_key": candidate.assessment_key}
        _verify_existing_assessment(existing, candidate)
        mismatch = {**existing, "computed_usage_cost_usd": Decimal("1")}
        with self.assertRaises(EconomicReceiptDerivationError):
            _verify_existing_assessment(mismatch, candidate)
        self.assertEqual(tuple(inspect.signature(derive_and_persist_economic_receipt).parameters),
                         ("session", "usage_event_id"))

    def test_bearer_is_derived_only_from_bound_immutable_authority(self):
        jous = self.authority()
        actual = {**self.execution, "request_started_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
                  "credential_authority_ref": jous["credential_authority_ref"]}
        jous_candidate = self.derive(decision=self.bind_authority(jous), funding_authority=jous, execution=actual)
        self.assertEqual(jous_candidate.cost_bearer, "JOUS_BORNE")
        self.assertEqual(jous_candidate.funding_authority_id, jous["funding_authority_id"])
        self.assertEqual(jous_candidate.funding_authority_version, 1)
        self.assertEqual(jous_candidate.funding_authority_digest, jous["authority_digest"])

        customer = self.authority(bearer="CUSTOMER_DIRECT", scope="ORGANIZATION", owner="CUSTOMER",
                                  organization_id=self.usage["organization_id"])
        customer_actual = {**actual, "credential_authority_ref": customer["credential_authority_ref"]}
        customer_candidate = self.derive(decision=self.bind_authority(customer), funding_authority=customer,
                                         execution=customer_actual)
        self.assertEqual(customer_candidate.cost_bearer, "CUSTOMER_DIRECT")

        self.assertEqual(self.derive().cost_bearer, "UNKNOWN")
        self.assertIsNone(self.derive().funding_authority_digest)

    def test_funding_authority_scope_route_digest_and_version_are_verified(self):
        authority = self.authority(scope="ORGANIZATION", owner="CUSTOMER",
                                   bearer="CUSTOMER_DIRECT", organization_id=uuid4())
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(decision=self.bind_authority(authority), funding_authority=authority)

    def test_funding_authority_supplier_must_match_immutable_usage_source(self):
        authority = self.authority()
        actual = {**self.execution, "request_started_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
                  "credential_authority_ref": authority["credential_authority_ref"]}
        self.assertEqual(self.derive(decision=self.bind_authority(authority),
                                     funding_authority=authority, execution=actual).cost_bearer, "JOUS_BORNE")
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive({**self.usage, "supplier_id": "different-supplier"},
                        decision=self.bind_authority(authority), funding_authority=authority)

        authority = self.authority()
        decision = self.bind_authority(authority)
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(decision={**decision, "selected_route_id": "route-other"}, funding_authority=authority)
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(decision={**decision, "funding_authority_version": 2}, funding_authority=authority)
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(decision={**decision, "funding_authority_digest": b"x" * 32}, funding_authority=authority)
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(decision=decision, funding_authority={**authority, "cost_bearer": "UNKNOWN"})

    def test_authority_is_never_caller_selectable_for_legacy_or_unbound_route(self):
        authority = self.authority()
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(funding_authority=authority)
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(usage={**self.usage, "route_decision_id": None}, decision=None,
                        pricing=None, funding_authority=authority)

    def test_known_bearer_requires_matching_execution_credential_evidence(self):
        authority = self.authority()
        decision = self.bind_authority(authority)
        dispatched = {**self.execution, "request_started_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
                      "credential_authority_ref": "account-B"}
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(decision=decision, funding_authority=authority, execution=dispatched)
        dispatched["credential_authority_ref"] = None
        with self.assertRaises(EconomicReceiptDerivationError):
            self.derive(decision=decision, funding_authority=authority, execution=dispatched)
        not_dispatched = {**self.execution, "request_started_at": None, "credential_authority_ref": None}
        candidate = self.derive(decision=decision, funding_authority=authority, execution=not_dispatched)
        self.assertEqual(candidate.cost_bearer, "UNKNOWN")

    def test_receipt_derivation_module_has_no_network_or_ledger_surface(self):
        from jous_api import economic_receipts
        self.assertFalse(hasattr(economic_receipts, "ledger_transactions"))
        self.assertFalse(hasattr(economic_receipts, "ledger_entries"))
        self.assertEqual(ECONOMIC_POLICY_VERSION, "jous.economic-assessment.v1")


if __name__ == "__main__":
    unittest.main()
