"""Deterministic posting of eligible immutable Jous supplier-cost receipts."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from .economic_models import ledger_accounts, ledger_entries, ledger_transactions


POSTING_PURPOSE = "COMPUTED_JOUS_COST_V1"
_ELIGIBLE_STATUS = "COMPUTED"
_ELIGIBLE_BEARER = "JOUS_BORNE"


class LedgerPostingError(ValueError):
    """Persisted receipt or posting evidence is invalid or contradictory."""


class LedgerAccountUnavailable(LedgerPostingError):
    """A required immutable chart account is absent or inconsistent."""


@dataclass(frozen=True)
class LedgerPostingResult:
    status: str
    reason: str | None = None
    ledger_transaction_id: UUID | None = None
    entry_count: int = 0
    created: bool = False


_RECEIPT_SQL = text("""SELECT r.*,
  EXISTS (SELECT 1 FROM public.economic_receipts successor
          WHERE successor.supersedes_receipt_id=r.economic_receipt_id) AS has_successor
  FROM public.economic_receipts r WHERE r.economic_receipt_id=:receipt_id""")
_DISPATCH_PROVENANCE_SQL = text("""SELECT
  e.credential_authority_ref AS execution_authority_ref,
  d.funding_authority_id, d.funding_authority_version, d.funding_authority_digest,
  a.authority_digest, a.credential_authority_ref AS authority_ref, a.cost_bearer
 FROM public.economic_receipts r
 JOIN public.executions e ON e.id=r.execution_id AND e.task_id=r.task_id
   AND e.organization_id=r.organization_id AND e.project_id=r.project_id
   AND e.actor_user_id=r.actor_user_id AND e.dispatch_claim_id=r.dispatch_claim_id
 JOIN public.route_decisions d ON d.task_id=r.route_decision_id
   AND d.task_id=r.task_id AND d.organization_id=r.organization_id
   AND d.project_id=r.project_id AND d.actor_user_id=r.actor_user_id
   AND d.dispatch_claim_id=r.dispatch_claim_id
 JOIN public.supplier_funding_authorities a
   ON a.funding_authority_id=d.funding_authority_id
   AND a.authority_version=d.funding_authority_version
 WHERE r.economic_receipt_id=:receipt_id""")
_EXISTING_SQL = text("""SELECT t.ledger_transaction_id,t.organization_id,t.economic_receipt_id,
  t.posting_purpose,t.currency,t.source_digest,count(e.line_number)::integer AS entry_count
 FROM public.ledger_transactions t LEFT JOIN public.ledger_entries e
   ON e.ledger_transaction_id=t.ledger_transaction_id AND e.organization_id=t.organization_id
 WHERE t.economic_receipt_id=:receipt_id AND t.posting_purpose=:posting_purpose
 GROUP BY t.ledger_transaction_id,t.organization_id,t.economic_receipt_id,
   t.posting_purpose,t.currency,t.source_digest""")


def _amount(value: Any, name: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (Decimal, int)):
        raise LedgerPostingError(f"Receipt amount is not exact Decimal evidence: {name}")
    result = value if isinstance(value, Decimal) else Decimal(value)
    if not result.is_finite() or result < 0:
        raise LedgerPostingError(f"Receipt amount is invalid: {name}")
    return result


def _ineligible(receipt: Mapping[str, Any]) -> str | None:
    if receipt["assessment_status"] != _ELIGIBLE_STATUS:
        return f"ASSESSMENT_{receipt['assessment_status']}"
    if receipt["cost_bearer"] != _ELIGIBLE_BEARER:
        return f"COST_BEARER_{receipt['cost_bearer']}"
    amount = receipt["computed_usage_cost_usd"]
    if amount is None:
        return "NULL_COST"
    amount = _amount(amount, "computed_usage_cost_usd")
    if amount == 0:
        return "KNOWN_ZERO_COST"
    if receipt["currency"] != "USD":
        raise LedgerPostingError("Receipt currency is not USD")
    if receipt["canonical_digest"] is None or len(bytes(receipt["canonical_digest"])) != 32:
        raise LedgerPostingError("Receipt canonical source digest is invalid")
    return None


async def _account_ids(session: AsyncSession, provider_amount: Decimal,
                       gateway_amount: Decimal) -> dict[str, UUID]:
    needed = {"supplier_cost_accrual"}
    if provider_amount > 0:
        needed.add("provider_inference_expense")
    if gateway_amount > 0:
        needed.add("gateway_platform_expense")
    rows = (await session.execute(select(
        ledger_accounts.c.ledger_account_id, ledger_accounts.c.account_code,
        ledger_accounts.c.economic_classification, ledger_accounts.c.normal_side,
        ledger_accounts.c.currency, ledger_accounts.c.postable, ledger_accounts.c.account_version,
    ).where(ledger_accounts.c.account_code.in_(needed)))).mappings().all()
    expected = {
        "provider_inference_expense": ("PROVIDER_INFERENCE_EXPENSE", "DEBIT"),
        "gateway_platform_expense": ("GATEWAY_PLATFORM_EXPENSE", "DEBIT"),
        "supplier_cost_accrual": ("SUPPLIER_COST_ACCRUAL", "CREDIT"),
    }
    found: dict[str, UUID] = {}
    for row in rows:
        code = row["account_code"]
        if (code not in needed or row["economic_classification"] != expected[code][0]
                or row["normal_side"] != expected[code][1] or row["currency"] != "USD"
                or row["postable"] is not True or row["account_version"] <= 0):
            raise LedgerAccountUnavailable("Server chart account is inconsistent")
        found[code] = row["ledger_account_id"]
    if set(found) != needed:
        raise LedgerAccountUnavailable("Required server chart account is missing")
    return found


async def _existing(session: AsyncSession, receipt_id: UUID) -> LedgerPostingResult | None:
    row = (await session.execute(_EXISTING_SQL, {
        "receipt_id": receipt_id, "posting_purpose": POSTING_PURPOSE,
    })).mappings().one_or_none()
    if row is None:
        return None
    if (row["economic_receipt_id"] != receipt_id or row["posting_purpose"] != POSTING_PURPOSE
            or row["currency"] != "USD" or row["entry_count"] < 2
            or len(bytes(row["source_digest"] or b"")) != 32):
        raise LedgerPostingError("Existing posting conflicts with immutable receipt identity")
    return LedgerPostingResult("POSTED", ledger_transaction_id=row["ledger_transaction_id"],
                               entry_count=row["entry_count"], created=False)


def _journal_entries(receipt: Mapping[str, Any], accounts: Mapping[str, UUID],
                    tx_id: UUID, provider_amount: Decimal,
                    gateway_fee: Decimal, total: Decimal) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    line = 1
    if provider_amount > 0:
        entries.append({"ledger_transaction_id": tx_id, "organization_id": receipt["organization_id"],
            "line_number": line, "ledger_account_id": accounts["provider_inference_expense"],
            "currency": "USD", "direction": "DEBIT", "amount": provider_amount})
        line += 1
    if gateway_fee > 0:
        entries.append({"ledger_transaction_id": tx_id, "organization_id": receipt["organization_id"],
            "line_number": line, "ledger_account_id": accounts["gateway_platform_expense"],
            "currency": "USD", "direction": "DEBIT", "amount": gateway_fee})
        line += 1
    entries.append({"ledger_transaction_id": tx_id, "organization_id": receipt["organization_id"],
        "line_number": line, "ledger_account_id": accounts["supplier_cost_accrual"],
        "currency": "USD", "direction": "CREDIT", "amount": total})
    return entries


async def post_economic_receipt(session: AsyncSession,
                                economic_receipt_id: UUID) -> LedgerPostingResult:
    """Post the one approved Jous supplier-cost journal for a receipt ID only.

    The immutable header is inserted last; PostgreSQL's deferred triggers and
    uniqueness constraints are the final authority for balance and replay.
    """
    if not isinstance(economic_receipt_id, UUID):
        raise LedgerPostingError("economic_receipt_id must be a UUID")
    try:
        async with session.begin():
            receipt_row = (await session.execute(_RECEIPT_SQL,
                {"receipt_id": economic_receipt_id})).mappings().one_or_none()
            if receipt_row is None:
                raise LedgerPostingError("Economic receipt was not found")
            receipt = dict(receipt_row)
            ineligible = _ineligible(receipt)
            if ineligible is not None:
                return LedgerPostingResult("INELIGIBLE", reason=ineligible)

            # A committed historical posting remains the replay result even if a
            # later assessment has since superseded its receipt.
            already = await _existing(session, economic_receipt_id)
            if already is not None:
                return already
            if receipt["supersedes_receipt_id"] is not None:
                return LedgerPostingResult("INELIGIBLE", reason="RECEIPT_IS_SUPERSESSION")
            if receipt["has_successor"]:
                return LedgerPostingResult("INELIGIBLE", reason="RECEIPT_SUPERSEDED")

            provenance = (await session.execute(_DISPATCH_PROVENANCE_SQL,
                {"receipt_id": economic_receipt_id})).mappings().one_or_none()
            if (provenance is None or provenance["cost_bearer"] != _ELIGIBLE_BEARER
                    or provenance["funding_authority_id"] != receipt["funding_authority_id"]
                    or provenance["funding_authority_version"] != receipt["funding_authority_version"]
                    or bytes(provenance["funding_authority_digest"] or b"") !=
                       bytes(receipt["funding_authority_digest"] or b"")
                    or bytes(provenance["authority_digest"] or b"") !=
                       bytes(receipt["funding_authority_digest"] or b"")
                    or provenance["execution_authority_ref"] is None
                    or provenance["execution_authority_ref"] != provenance["authority_ref"]):
                raise LedgerPostingError("Receipt funding or dispatch provenance is contradictory")

            provider_usage = _amount(receipt["provider_usage_cost_usd"], "provider_usage_cost_usd")
            provider_fee = _amount(receipt["provider_request_fee_usd"], "provider_request_fee_usd")
            gateway_fee = _amount(receipt["gateway_request_fee_usd"], "gateway_request_fee_usd")
            total = _amount(receipt["computed_usage_cost_usd"], "computed_usage_cost_usd")
            provider_amount = provider_usage + provider_fee
            if provider_amount + gateway_fee != total or total <= 0:
                raise LedgerPostingError("Receipt component totals are inconsistent")
            accounts = await _account_ids(session, provider_amount, gateway_fee)

            tx_id = uuid4()
            entries = _journal_entries(receipt, accounts, tx_id, provider_amount, gateway_fee, total)
            await session.execute(insert(ledger_entries), entries)
            await session.execute(insert(ledger_transactions).values(
                ledger_transaction_id=tx_id,
                organization_id=receipt["organization_id"],
                economic_receipt_id=economic_receipt_id,
                posting_purpose=POSTING_PURPOSE,
                currency="USD",
                source_digest=bytes(receipt["canonical_digest"]),
            ))
            return LedgerPostingResult("POSTED", ledger_transaction_id=tx_id,
                                       entry_count=len(entries), created=True)
    except IntegrityError:
        # Concurrent identical posts can race before the deterministic unique
        # header wins. Recover only if that authoritative posting now exists.
        async with session.begin():
            existing = await _existing(session, economic_receipt_id)
            if existing is not None:
                return existing
        raise
