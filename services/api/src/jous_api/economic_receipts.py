"""Deterministic derivation and idempotent persistence of V1.4C receipts.

Only persisted UsageEvent, RouteDecision, selected pricing-version evidence,
and an immutable route-bound supplier funding authority determine a receipt.
Missing authority remains UNKNOWN. This module never posts ledger rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from typing import Any, Mapping
from uuid import UUID, uuid5

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .economic_models import economic_receipts
from .usage_event_models import usage_events

ECONOMIC_POLICY_VERSION = "jous.economic-assessment.v1"
CALCULATION_VERSION = "jous.token-cost.v1"
TREATMENT_POLICY_VERSION = "jous.cost-bearer.v1"
TREATMENT_POLICY = {
    "schema_version": TREATMENT_POLICY_VERSION,
    "authority": "route_decision_bound_immutable_supplier_funding_authority",
    "known_bearer_requires_matching_immutable_execution_credential_authority_ref": True,
    "dispatch_evidence_source": "public.executions.credential_authority_ref",
    "missing_authority": "UNKNOWN",
    "jous_runtime_context_is_authority": False,
    "processor_may_assert_bearer": False,
}
TREATMENT_POLICY_DIGEST = hashlib.sha256(
    json.dumps(TREATMENT_POLICY, sort_keys=True, separators=(",", ":"),
               ensure_ascii=False).encode("utf-8")
).digest()
_RECEIPT_NAMESPACE = UUID("1372254d-1172-5e30-a54a-2cc7453eb54c")
_MONEY_QUANTUM = Decimal("0.000000000000000001")
_RATE_DENOMINATOR = Decimal(1_000_000)
_PRICING_FIELDS = (
    "pricing_version_id", "route_id", "route_version", "service_tier", "currency",
    "billing_basis", "input_price_per_1m", "output_price_per_1m",
    "provider_fee_applicable", "provider_request_fee_usd", "gateway_fee_applicable",
    "gateway_request_fee_usd", "fee_basis_verified", "source_type", "source_evidence_id",
    "reviewed_at", "effective_from", "valid_until",
)
_ROUTE_DECISION_SQL = text("""SELECT task_id,organization_id,project_id,actor_user_id,
 dispatch_claim_id,pricing_version_id,funding_authority_id,funding_authority_version,
 funding_authority_digest,selected_route_id,selected_route_version
 FROM public.route_decisions WHERE task_id=:decision_id""")
_FUNDING_AUTHORITY_SQL = text("""SELECT funding_authority_id,authority_version,scope,organization_id,
 supplier_id,route_id,route_version,credential_authority_ref,account_owner,cost_bearer,
 evidence_type,evidence_reference,effective_at,canonical_evidence,authority_digest
 FROM public.supplier_funding_authorities
 WHERE funding_authority_id=:funding_authority_id AND authority_version=:authority_version""")
_PRICING_SQL = text("""SELECT pricing_version_id,route_id,route_version,service_tier,currency,
 billing_basis,input_price_per_1m,output_price_per_1m,provider_fee_applicable,
 provider_request_fee_usd,gateway_fee_applicable,gateway_request_fee_usd,
 fee_basis_verified,source_type,source_evidence_id,reviewed_at,effective_from,
 valid_until,pricing_status FROM public.route_pricing_versions
 WHERE pricing_version_id=:pricing_version_id""")
_EXECUTION_SQL = text("""SELECT id,task_id,organization_id,project_id,actor_user_id,dispatch_claim_id,
 request_started_at,credential_authority_ref FROM public.executions WHERE id=:execution_id""")
_ASSESSMENT_KEY_SQL = text("""SELECT pg_catalog.sha256(pg_catalog.convert_to(
 pg_catalog.jsonb_build_object('schema_version','jous.economic-assessment.v1',
 'usage_event_id',CAST(:usage_event_id AS uuid),
 'economic_policy_version',CAST(:economic_policy_version AS text),
 'treatment_policy_digest',pg_catalog.encode(CAST(:treatment_policy_digest AS bytea),'hex'),
 'calculation_version',CAST(:calculation_version AS text),
 'pricing_version_id',CAST(:pricing_version_id AS varchar),
 'funding_authority_digest',CASE WHEN CAST(:funding_authority_digest AS bytea) IS NULL THEN NULL
   ELSE pg_catalog.encode(CAST(:funding_authority_digest AS bytea),'hex') END)::text,'UTF8'))""")


class EconomicReceiptDerivationError(ValueError):
    """Persisted source/pricing evidence is invalid or internally inconsistent."""


@dataclass(frozen=True)
class EconomicReceiptCandidate:
    economic_receipt_id: UUID
    assessment_key: bytes
    organization_id: UUID
    project_id: UUID
    actor_user_id: UUID
    task_id: UUID
    dispatch_claim_id: UUID
    execution_id: UUID
    usage_event_id: UUID
    route_decision_id: UUID | None
    pricing_version_id: str | None
    funding_authority_id: UUID | None
    funding_authority_version: int | None
    funding_authority_digest: bytes | None
    economic_policy_version: str
    treatment_policy_digest: bytes
    calculation_version: str
    assessment_status: str
    cost_bearer: str
    currency: str
    provider_usage_cost_usd: Decimal | None
    provider_request_fee_usd: Decimal | None
    gateway_request_fee_usd: Decimal | None
    computed_usage_cost_usd: Decimal | None
    pricing_snapshot_canonical: str | None
    pricing_snapshot_sha256: bytes | None
    source_usage_digest: bytes
    observed_at: datetime
    execution_credential_authority_ref: str | None

    def insert_values(self) -> dict[str, Any]:
        """Columns allowed to the processor; DB triggers own assessment/digest fields."""
        return {name: getattr(self, name) for name in (
            "economic_receipt_id", "organization_id", "project_id", "actor_user_id", "task_id",
            "dispatch_claim_id", "execution_id", "usage_event_id", "route_decision_id",
            "pricing_version_id", "funding_authority_id", "funding_authority_version",
            "funding_authority_digest", "economic_policy_version", "treatment_policy_digest",
            "calculation_version", "assessment_status", "cost_bearer", "currency",
            "provider_usage_cost_usd", "provider_request_fee_usd", "gateway_request_fee_usd",
            "computed_usage_cost_usd", "pricing_snapshot_canonical", "pricing_snapshot_sha256",
            "source_usage_digest", "observed_at")}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def _utc_text(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise EconomicReceiptDerivationError("Pricing timestamp is not timezone aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (Decimal, int, str)):
        raise EconomicReceiptDerivationError(f"Invalid exact decimal evidence: {field}")
    try:
        result = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError):
        raise EconomicReceiptDerivationError(f"Invalid exact decimal evidence: {field}") from None
    if not result.is_finite() or result < 0:
        raise EconomicReceiptDerivationError(f"Invalid exact decimal evidence: {field}")
    return result


def _numeric_50_18(value: Decimal, field: str) -> Decimal:
    """Accept exact NUMERIC(50,18) values; never round/overstate economics."""
    try:
        with localcontext() as context:
            context.prec = 100
            quantized = value.quantize(_MONEY_QUANTUM)
    except InvalidOperation:
        raise EconomicReceiptDerivationError(f"Amount exceeds NUMERIC(50,18): {field}") from None
    if quantized != value or (quantized != 0 and quantized.adjusted() >= 32):
        raise EconomicReceiptDerivationError(f"Amount is not exactly representable as NUMERIC(50,18): {field}")
    return quantized


def _pricing_snapshot(pricing: Mapping[str, Any]) -> tuple[str, bytes]:
    payload: dict[str, Any] = {"schema_version": "jous.route-pricing.v1"}
    for name in _PRICING_FIELDS:
        value = pricing[name]
        if name in {"input_price_per_1m", "output_price_per_1m",
                    "provider_request_fee_usd", "gateway_request_fee_usd"}:
            payload[name] = None if value is None else format(_decimal(value, name), "f")
        elif name in {"reviewed_at", "effective_from", "valid_until"}:
            payload[name] = _utc_text(value)
        else:
            payload[name] = value
    canonical = _canonical_json(payload)
    return canonical, hashlib.sha256(canonical.encode("utf-8")).digest()


def _identity_uuid(assessment_key: bytes) -> UUID:
    return uuid5(_RECEIPT_NAMESPACE, assessment_key.hex())


def derive_economic_receipt_candidate(
    usage: Mapping[str, Any], route_decision: Mapping[str, Any] | None,
    pricing: Mapping[str, Any] | None, assessment_key: bytes,
    funding_authority: Mapping[str, Any] | None = None,
    execution_evidence: Mapping[str, Any] | None = None,
) -> EconomicReceiptCandidate:
    """Pure assessment mapping; tenant/source facts come only from UsageEvent."""
    required = ("usage_event_id", "organization_id", "project_id", "actor_user_id", "task_id",
                "dispatch_claim_id", "execution_id", "route_decision_id", "usage_status",
                "supplier_id", "input_tokens", "output_tokens", "evidence_sha256", "observed_at")
    if any(name not in usage for name in required):
        raise EconomicReceiptDerivationError("UsageEvent source projection is incomplete")
    source_digest = bytes(usage["evidence_sha256"] or b"")
    if len(source_digest) != 32:
        raise EconomicReceiptDerivationError("UsageEvent digest is invalid")
    observed_at = usage["observed_at"]
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise EconomicReceiptDerivationError("UsageEvent observed_at is invalid")
    if len(assessment_key) != 32:
        raise EconomicReceiptDerivationError("Assessment key is invalid")
    if execution_evidence is None:
        raise EconomicReceiptDerivationError("Immutable Execution dispatch evidence is required")
    if (execution_evidence.get("id") != usage["execution_id"] or
            execution_evidence.get("task_id") != usage["task_id"] or
            execution_evidence.get("organization_id") != usage["organization_id"] or
            execution_evidence.get("project_id") != usage["project_id"] or
            execution_evidence.get("actor_user_id") != usage["actor_user_id"] or
            execution_evidence.get("dispatch_claim_id") != usage["dispatch_claim_id"]):
        raise EconomicReceiptDerivationError("Execution source binding mismatch")
    execution_ref = execution_evidence.get("credential_authority_ref")
    request_started_at = execution_evidence.get("request_started_at")
    if execution_ref is not None and (not isinstance(execution_ref, str) or not execution_ref.strip()):
        raise EconomicReceiptDerivationError("Execution credential authority reference is invalid")
    if execution_ref is not None and request_started_at is None:
        raise EconomicReceiptDerivationError("Execution credential authority has no dispatch timestamp")

    decision_id = usage["route_decision_id"]
    pricing_id = None
    funding_authority_id = funding_authority_version = funding_authority_digest = None
    cost_bearer = "UNKNOWN"
    if decision_id is None:
        if route_decision is not None:
            raise EconomicReceiptDerivationError("Legacy UsageEvent cannot be assigned a RouteDecision")
        if funding_authority is not None:
            raise EconomicReceiptDerivationError("Legacy UsageEvent cannot be assigned funding authority")
        if execution_ref is not None:
            raise EconomicReceiptDerivationError("Legacy execution has contradictory funding dispatch evidence")
    else:
        if route_decision is None:
            raise EconomicReceiptDerivationError("Persisted RouteDecision is unavailable")
        expected_binding = (usage["organization_id"], usage["project_id"], usage["actor_user_id"],
                            usage["task_id"], usage["dispatch_claim_id"])
        actual_binding = (route_decision["organization_id"], route_decision["project_id"],
                          route_decision["actor_user_id"], route_decision["task_id"],
                          route_decision["dispatch_claim_id"])
        if actual_binding != expected_binding or route_decision["task_id"] != decision_id:
            raise EconomicReceiptDerivationError("RouteDecision source binding mismatch")
        pricing_id = route_decision["pricing_version_id"]
        authority_tuple = tuple(route_decision.get(name) for name in (
            "funding_authority_id", "funding_authority_version", "funding_authority_digest"))
        if all(value is None for value in authority_tuple):
            if funding_authority is not None:
                raise EconomicReceiptDerivationError("Unbound funding authority was supplied")
            if execution_ref is not None:
                raise EconomicReceiptDerivationError("Execution credential evidence has no bound authority")
        elif any(value is None for value in authority_tuple):
            raise EconomicReceiptDerivationError("RouteDecision funding authority binding is incomplete")
        else:
            if funding_authority is None:
                raise EconomicReceiptDerivationError("Persisted funding authority is unavailable")
            funding_authority_id, funding_authority_version, funding_authority_digest = authority_tuple
            digest = bytes(funding_authority_digest)
            if len(digest) != 32 or bytes(funding_authority.get("authority_digest", b"")) != digest:
                raise EconomicReceiptDerivationError("Funding authority digest mismatch")
            if (funding_authority.get("funding_authority_id") != funding_authority_id or
                    funding_authority.get("authority_version") != funding_authority_version):
                raise EconomicReceiptDerivationError("Funding authority identity/version mismatch")
            scope = funding_authority.get("scope")
            authority_org = funding_authority.get("organization_id")
            if scope == "ORGANIZATION" and authority_org != usage["organization_id"]:
                raise EconomicReceiptDerivationError("Funding authority belongs to another organization")
            if scope not in {"ORGANIZATION", "JOUS_GLOBAL"}:
                raise EconomicReceiptDerivationError("Funding authority scope is invalid")
            if (funding_authority.get("route_id") != route_decision.get("selected_route_id") or
                    funding_authority.get("route_version") != route_decision.get("selected_route_version")):
                raise EconomicReceiptDerivationError("Funding authority route mismatch")
            if funding_authority.get("supplier_id") != usage.get("supplier_id"):
                raise EconomicReceiptDerivationError("Funding authority supplier mismatch")
            canonical = funding_authority.get("canonical_evidence")
            if not isinstance(canonical, str) or hashlib.sha256(canonical.encode("utf-8")).digest() != digest:
                raise EconomicReceiptDerivationError("Funding authority canonical evidence is invalid")
            effective_at = funding_authority.get("effective_at")
            expected_evidence = {
                "schema_version": "jous.supplier-funding-authority.v1",
                "funding_authority_id": str(funding_authority_id),
                "authority_version": funding_authority_version,
                "scope": scope,
                "organization_id": None if authority_org is None else str(authority_org),
                "supplier_id": funding_authority.get("supplier_id"),
                "route_id": funding_authority.get("route_id"),
                "route_version": funding_authority.get("route_version"),
                "credential_authority_ref": funding_authority.get("credential_authority_ref"),
                "account_owner": funding_authority.get("account_owner"),
                "cost_bearer": funding_authority.get("cost_bearer"),
                "evidence_type": funding_authority.get("evidence_type"),
                "evidence_reference": funding_authority.get("evidence_reference"),
                "effective_at": _utc_text(effective_at),
            }
            try:
                if json.loads(canonical) != expected_evidence:
                    raise EconomicReceiptDerivationError("Funding authority snapshot does not match its fields")
            except (TypeError, ValueError, json.JSONDecodeError):
                raise EconomicReceiptDerivationError("Funding authority canonical evidence is malformed") from None
            authority_bearer = funding_authority.get("cost_bearer")
            if authority_bearer not in {"JOUS_BORNE", "CUSTOMER_DIRECT", "UNKNOWN"}:
                raise EconomicReceiptDerivationError("Funding authority bearer is invalid")
            if authority_bearer == "CUSTOMER_DIRECT" and not (
                    scope == "ORGANIZATION" and funding_authority.get("account_owner") == "CUSTOMER"):
                raise EconomicReceiptDerivationError("Customer-direct authority lacks customer ownership")
            expected_ref = funding_authority.get("credential_authority_ref")
            if execution_ref is None:
                if request_started_at is not None:
                    raise EconomicReceiptDerivationError("Dispatched execution lacks actual credential authority evidence")
                cost_bearer = "UNKNOWN"
            elif execution_ref != expected_ref:
                raise EconomicReceiptDerivationError("Execution credential authority contradicts funding decision")
            else:
                cost_bearer = authority_bearer

    status = str(usage["usage_status"]).upper()
    provider_usage = provider_fee = gateway_fee = total = None
    snapshot_text = None
    snapshot_digest = None
    assessment_status: str
    if status == "UNAVAILABLE":
        if any(usage[name] is not None for name in ("input_tokens", "output_tokens")):
            raise EconomicReceiptDerivationError("Unavailable UsageEvent contains fabricated counts")
        assessment_status = "UNAVAILABLE_USAGE"
    elif status == "PARTIAL":
        for name in ("input_tokens", "output_tokens"):
            value = usage[name]
            if value is not None and (type(value) is not int or value < 0):
                raise EconomicReceiptDerivationError("Partial token evidence is invalid")
        assessment_status = "INCOMPLETE_USAGE"
    elif status == "AVAILABLE":
        tokens = [usage[name] for name in ("input_tokens", "output_tokens")]
        if any(type(value) is not int or value < 0 for value in tokens):
            raise EconomicReceiptDerivationError("Available usage lacks valid required token evidence")
        if route_decision is None or pricing_id is None or pricing is None:
            assessment_status = "MISSING_PRICING"
        else:
            if pricing.get("pricing_version_id") != pricing_id:
                raise EconomicReceiptDerivationError("Pricing version differs from persisted RouteDecision")
            if (pricing.get("pricing_status") != "approved" or pricing.get("currency") != "USD"
                    or pricing.get("fee_basis_verified") is not True):
                assessment_status = "MISSING_PRICING"
            else:
                provider_applicable = pricing.get("provider_fee_applicable")
                gateway_applicable = pricing.get("gateway_fee_applicable")
                provider_raw = pricing.get("provider_request_fee_usd")
                gateway_raw = pricing.get("gateway_request_fee_usd")
                input_rate = pricing.get("input_price_per_1m")
                output_rate = pricing.get("output_price_per_1m")
                if (type(provider_applicable) is not bool or type(gateway_applicable) is not bool
                        or input_rate is None or output_rate is None
                        or (provider_applicable and provider_raw is None)
                        or (not provider_applicable and provider_raw is not None)
                        or (gateway_applicable and gateway_raw is None)
                        or (not gateway_applicable and gateway_raw is not None)):
                    assessment_status = "MISSING_PRICING"
                else:
                    with localcontext() as context:
                        context.prec = 100
                        input_cost = Decimal(tokens[0]) * _decimal(input_rate, "input price") / _RATE_DENOMINATOR
                        output_cost = Decimal(tokens[1]) * _decimal(output_rate, "output price") / _RATE_DENOMINATOR
                        provider_usage = _numeric_50_18(input_cost + output_cost, "provider usage")
                        provider_fee = (_numeric_50_18(_decimal(provider_raw, "provider fee"), "provider fee")
                                        if provider_applicable else Decimal(0).quantize(_MONEY_QUANTUM))
                        gateway_fee = (_numeric_50_18(_decimal(gateway_raw, "gateway fee"), "gateway fee")
                                       if gateway_applicable else Decimal(0).quantize(_MONEY_QUANTUM))
                        total = _numeric_50_18(provider_usage + provider_fee + gateway_fee, "computed cost")
                    assessment_status = "COMPUTED"
                    snapshot_text, snapshot_digest = _pricing_snapshot(pricing)
    else:
        raise EconomicReceiptDerivationError("Unsupported persisted UsageEvent status")

    if assessment_status != "COMPUTED":
        provider_usage = provider_fee = gateway_fee = total = None
    return EconomicReceiptCandidate(
        economic_receipt_id=_identity_uuid(assessment_key), assessment_key=assessment_key,
        organization_id=usage["organization_id"], project_id=usage["project_id"],
        actor_user_id=usage["actor_user_id"], task_id=usage["task_id"],
        dispatch_claim_id=usage["dispatch_claim_id"], execution_id=usage["execution_id"],
        usage_event_id=usage["usage_event_id"], route_decision_id=decision_id,
        pricing_version_id=pricing_id, economic_policy_version=ECONOMIC_POLICY_VERSION,
        treatment_policy_digest=TREATMENT_POLICY_DIGEST, calculation_version=CALCULATION_VERSION,
        assessment_status=assessment_status, cost_bearer=cost_bearer, currency="USD",
        funding_authority_id=funding_authority_id,
        funding_authority_version=funding_authority_version,
        funding_authority_digest=None if funding_authority_digest is None else bytes(funding_authority_digest),
        provider_usage_cost_usd=provider_usage, provider_request_fee_usd=provider_fee,
        gateway_request_fee_usd=gateway_fee, computed_usage_cost_usd=total,
        pricing_snapshot_canonical=snapshot_text, pricing_snapshot_sha256=snapshot_digest,
        source_usage_digest=source_digest, observed_at=observed_at.astimezone(timezone.utc),
        execution_credential_authority_ref=execution_ref)


async def _load_candidate(session: AsyncSession, usage_event_id: UUID) -> EconomicReceiptCandidate:
    usage_stmt = select(*(usage_events.c[name] for name in (
        "usage_event_id", "organization_id", "project_id", "actor_user_id", "task_id",
        "dispatch_claim_id", "execution_id", "route_decision_id", "supplier_id", "input_tokens", "output_tokens",
        "usage_status", "evidence_sha256", "observed_at"))).where(
            usage_events.c.usage_event_id == usage_event_id)
    usage_row = (await session.execute(usage_stmt)).mappings().one_or_none()
    if usage_row is None:
        raise EconomicReceiptDerivationError("UsageEvent source was not found")
    usage = dict(usage_row)
    execution_row = (await session.execute(_EXECUTION_SQL,
        {"execution_id": usage["execution_id"]})).mappings().one_or_none()
    if execution_row is None:
        raise EconomicReceiptDerivationError("Immutable Execution source was not found")
    execution = dict(execution_row)
    decision = None
    pricing = None
    funding_authority = None
    if usage["route_decision_id"] is not None:
        decision_row = (await session.execute(_ROUTE_DECISION_SQL,
            {"decision_id": usage["route_decision_id"]})).mappings().one_or_none()
        if decision_row is None:
            raise EconomicReceiptDerivationError("UsageEvent RouteDecision was not found")
        decision = dict(decision_row)
        if decision["funding_authority_id"] is not None:
            authority_row = (await session.execute(_FUNDING_AUTHORITY_SQL, {
                "funding_authority_id": decision["funding_authority_id"],
                "authority_version": decision["funding_authority_version"],
            })).mappings().one_or_none()
            if authority_row is None:
                raise EconomicReceiptDerivationError("Bound funding authority was not found")
            funding_authority = dict(authority_row)
        pricing_row = (await session.execute(_PRICING_SQL,
            {"pricing_version_id": decision["pricing_version_id"]})).mappings().one_or_none()
        pricing = None if pricing_row is None else dict(pricing_row)
    key = (await session.execute(_ASSESSMENT_KEY_SQL, {
        "usage_event_id": usage["usage_event_id"],
        "economic_policy_version": ECONOMIC_POLICY_VERSION,
        "treatment_policy_digest": TREATMENT_POLICY_DIGEST,
        "calculation_version": CALCULATION_VERSION,
        "pricing_version_id": None if decision is None else decision["pricing_version_id"],
        "funding_authority_digest": None if decision is None else decision["funding_authority_digest"],
    })).scalar_one()
    return derive_economic_receipt_candidate(usage, decision, pricing, bytes(key), funding_authority, execution)


async def derive_and_persist_economic_receipt(
    session: AsyncSession, usage_event_id: UUID,
) -> Mapping[str, Any]:
    """Persist one immutable receipt; deterministic replay returns the same row."""
    if not isinstance(usage_event_id, UUID):
        raise EconomicReceiptDerivationError("usage_event_id must be a UUID")
    async with session.begin():
        candidate = await _load_candidate(session, usage_event_id)
        result = await session.execute(insert(economic_receipts).values(**candidate.insert_values())
            .on_conflict_do_nothing(constraint="uq_economic_receipts_assessment_key")
            .returning(economic_receipts))
        row = result.mappings().one_or_none()
        if row is not None:
            if bytes(row["assessment_key"]) != candidate.assessment_key:
                raise EconomicReceiptDerivationError("Database assessment identity differs from candidate")
            return dict(row)
        existing = (await session.execute(select(economic_receipts).where(
            economic_receipts.c.assessment_key == candidate.assessment_key))).mappings().one_or_none()
        if existing is None:
            raise EconomicReceiptDerivationError("Assessment-key collision could not be resolved")
        _verify_existing_assessment(existing, candidate)
        return dict(existing)


def _verify_existing_assessment(existing: Mapping[str, Any], candidate: EconomicReceiptCandidate) -> None:
    """Fail closed if a uniqueness conflict is not the exact deterministic receipt."""
    if bytes(existing.get("assessment_key", b"")) != candidate.assessment_key:
        raise EconomicReceiptDerivationError("Existing assessment key collision")
    for name, value in candidate.insert_values().items():
        if existing.get(name) != value:
            raise EconomicReceiptDerivationError(
                "Existing assessment conflicts with deterministic source evidence")
