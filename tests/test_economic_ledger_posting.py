"""Pure V1.4C supplier-cost posting policy tests."""
from decimal import Decimal
import inspect
import unittest
from uuid import uuid4

from jous_api.economic_ledger_posting import (
    POSTING_PURPOSE, LedgerPostingError, _amount, _ineligible, _journal_entries,
    post_economic_receipt,
)


class EconomicLedgerPostingTests(unittest.TestCase):
    def receipt(self, **changes):
        values = {
            "assessment_status": "COMPUTED", "cost_bearer": "JOUS_BORNE",
            "computed_usage_cost_usd": Decimal("0.000000000000000007"),
            "currency": "USD", "canonical_digest": b"d" * 32,
        }
        values.update(changes)
        return values

    def test_only_computed_positive_jous_borne_receipt_is_eligible(self):
        self.assertIsNone(_ineligible(self.receipt()))
        for status in ("INCOMPLETE_USAGE", "UNAVAILABLE_USAGE", "MISSING_PRICING"):
            with self.subTest(status=status):
                self.assertEqual(_ineligible(self.receipt(assessment_status=status)),
                                 f"ASSESSMENT_{status}")
        self.assertEqual(_ineligible(self.receipt(cost_bearer="CUSTOMER_DIRECT")),
                         "COST_BEARER_CUSTOMER_DIRECT")
        self.assertEqual(_ineligible(self.receipt(cost_bearer="UNKNOWN")), "COST_BEARER_UNKNOWN")
        self.assertEqual(_ineligible(self.receipt(computed_usage_cost_usd=Decimal(0))),
                         "KNOWN_ZERO_COST")
        self.assertEqual(_ineligible(self.receipt(computed_usage_cost_usd=None)), "NULL_COST")

    def test_amount_validation_rejects_float_negative_and_nonfinite(self):
        for value in (0.1, Decimal("-0.1"), Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(value=value), self.assertRaises(LedgerPostingError):
                _amount(value, "amount")
        self.assertEqual(_amount(Decimal("0.000000000000000001"), "amount"),
                         Decimal("0.000000000000000001"))

    def test_provider_only_journal_preserves_subcent_exactly(self):
        org, tx = uuid4(), uuid4()
        accounts = {"provider_inference_expense": uuid4(), "supplier_cost_accrual": uuid4()}
        amount = Decimal("0.000000000000000007")
        entries = _journal_entries({"organization_id": org}, accounts, tx, amount, Decimal(0), amount)
        self.assertEqual([(e["ledger_account_id"], e["direction"], e["amount"]) for e in entries], [
            (accounts["provider_inference_expense"], "DEBIT", amount),
            (accounts["supplier_cost_accrual"], "CREDIT", amount),
        ])
        self.assertEqual(sum(e["amount"] for e in entries if e["direction"] == "DEBIT"),
                         sum(e["amount"] for e in entries if e["direction"] == "CREDIT"))

    def test_provider_plus_gateway_uses_one_accrual_credit(self):
        org, tx = uuid4(), uuid4()
        accounts = {"provider_inference_expense": uuid4(), "gateway_platform_expense": uuid4(),
                    "supplier_cost_accrual": uuid4()}
        provider, gateway, total = Decimal("0.125"), Decimal("0.025"), Decimal("0.150")
        entries = _journal_entries({"organization_id": org}, accounts, tx, provider, gateway, total)
        self.assertEqual(len(entries), 3)
        self.assertEqual([e["direction"] for e in entries], ["DEBIT", "DEBIT", "CREDIT"])
        self.assertEqual(entries[-1]["amount"], total)
        self.assertEqual(entries[1]["ledger_account_id"], accounts["gateway_platform_expense"])

    def test_posting_contract_is_internal_and_receipt_id_only(self):
        self.assertEqual(POSTING_PURPOSE, "COMPUTED_JOUS_COST_V1")
        self.assertEqual(list(inspect.signature(post_economic_receipt).parameters),
                         ["session", "economic_receipt_id"])


if __name__ == "__main__":
    unittest.main()
