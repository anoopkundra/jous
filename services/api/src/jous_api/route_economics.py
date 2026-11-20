"""Pure Jous-owned V1.3A route and pricing authority contracts.

This module has no provider, database, network, or credential dependencies.
It is intentionally non-dispatching; adapter admission remains a separate gate.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from enum import StrEnum
import hashlib
import json
import re
from typing import Mapping, Sequence


USD = "USD"
MONEY_SCALE = 12
MAX_CANDIDATES = 64
MAX_DECISION_BYTES = 65_536
MAX_TOKEN_COUNT = 2_147_483_647
RATE_DENOMINATOR = Decimal("1000000")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+_-]{0,254}$")


class ContractError(ValueError):
    """Invalid or unbounded server-owned routing evidence."""


class ReasonCode(StrEnum):
    ROUTE_DISABLED = "ROUTE_DISABLED"
    ADMISSION_DENIED = "ADMISSION_DENIED"
    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    CONTEXT_UNSUPPORTED = "CONTEXT_UNSUPPORTED"
    TOKEN_AUTHORITY_UNRESOLVED = "TOKEN_AUTHORITY_UNRESOLVED"
    PRICING_MISSING = "PRICING_MISSING"
    PRICING_EXPIRED = "PRICING_EXPIRED"
    PRICING_NOT_EFFECTIVE = "PRICING_NOT_EFFECTIVE"
    PRICING_UNVERIFIED = "PRICING_UNVERIFIED"
    PRICING_REVOKED = "PRICING_REVOKED"
    BILLING_BASIS_UNRESOLVED = "BILLING_BASIS_UNRESOLVED"
    CURRENCY_UNSUPPORTED = "CURRENCY_UNSUPPORTED"
    LOGICAL_MODEL_MISMATCH = "LOGICAL_MODEL_MISMATCH"
    MODEL_NOT_APPROVED = "MODEL_NOT_APPROVED"
    ELIGIBLE = "ELIGIBLE"
    LOWEST_EFFECTIVE_COST = "LOWEST_EFFECTIVE_COST"
    TIE_BREAK_ROUTE_ID = "TIE_BREAK_ROUTE_ID"
    NO_ELIGIBLE_ROUTE = "NO_ELIGIBLE_ROUTE"


def _identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ContractError(f"Invalid {field}")
    return value


def _aware(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ContractError(f"Invalid {field}")
    return value.astimezone(timezone.utc)


def _decimal(
    value: Decimal | str | int,
    field: str,
    *,
    max_scale: int | None = MONEY_SCALE,
    max_precision: int = 30,
    max_integer_digits: int | None = 8,
) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ContractError(f"{field} must not use binary floating point")
    if not isinstance(value, (Decimal, str, int)):
        raise ContractError(f"Invalid {field}")
    try:
        result = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError):
        raise ContractError(f"Invalid {field}") from None
    if not result.is_finite() or result < 0:
        raise ContractError(f"Invalid {field}")
    if result == 0:
        return result
    decimal_tuple = result.as_tuple()
    digits = decimal_tuple.digits
    trailing_zeroes = 0
    for digit in reversed(digits):
        if digit != 0:
            break
        trailing_zeroes += 1
    significant_digits = max(1, len(digits) - trailing_zeroes)
    scale = max(0, -decimal_tuple.exponent - trailing_zeroes)
    if max_scale is not None and scale > max_scale:
        raise ContractError(f"{field} exceeds supported decimal scale")
    if significant_digits > max_precision:
        raise ContractError(f"{field} exceeds supported precision")
    if max_integer_digits is not None and result != 0 and result.adjusted() >= max_integer_digits:
        raise ContractError(f"{field} exceeds supported integer range")
    return result


def canonical_decimal(value: Decimal | str | int) -> str:
    """Serialize an exact nonnegative decimal without rounding or exponent form."""
    amount = _decimal(value, "amount", max_scale=None, max_precision=50, max_integer_digits=None)
    if amount == 0:
        return "0"
    if amount.as_tuple().exponent < -50 or amount.adjusted() > 49:
        raise ContractError("Amount exceeds canonical serialization bounds")
    rendered = format(amount, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _capabilities(values: Sequence[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ContractError(f"Invalid {field}")
    result = tuple(values)
    if len(result) > 32 or any(not _identifier(v, field) for v in result) or len(set(result)) != len(result):
        raise ContractError(f"Invalid {field}")
    return tuple(sorted(result))


@dataclass(frozen=True)
class LogicalModelVersion:
    logical_model_id: str
    version: int
    display_name: str
    model_authority_id: str
    modality: str = "text_generation"
    required_capabilities: tuple[str, ...] = ("text_generation",)
    context_capacity: int = 32_768
    max_output_allowance: int = 1_024
    status: str = "candidate"

    def __post_init__(self):
        _identifier(self.logical_model_id, "logical model id")
        _identifier(self.model_authority_id, "model authority id")
        if type(self.version) is not int or not 1 <= self.version <= MAX_TOKEN_COUNT:
            raise ContractError("Invalid logical model version")
        if not isinstance(self.display_name, str) or not self.display_name.strip() or len(self.display_name) > 128:
            raise ContractError("Invalid display name")
        if self.modality != "text_generation" or self.status not in {"candidate", "approved", "retired"}:
            raise ContractError("Unsupported logical model status or modality")
        if type(self.context_capacity) is not int or not 1 <= self.context_capacity <= MAX_TOKEN_COUNT:
            raise ContractError("Invalid model context capacity")
        if type(self.max_output_allowance) is not int or not 1 <= self.max_output_allowance <= self.context_capacity:
            raise ContractError("Invalid model output allowance")
        object.__setattr__(self, "required_capabilities", _capabilities(self.required_capabilities, "model capability"))


@dataclass(frozen=True)
class RouteVersion:
    route_id: str
    version: int
    logical_model_id: str
    logical_model_version: int
    supplier_id: str
    supplier_native_model_id: str
    underlying_provider: str | None
    route_kind: str
    gateway_id: str | None
    provider_selection: str
    service_tier: str
    capabilities: tuple[str, ...]
    context_capacity: int
    operational_enabled: bool
    admission_authorized: bool
    token_authority_status: str
    route_authority_id: str
    dynamic_provider_envelope_authorized: bool = False
    dynamic_provider_envelope_id: str | None = None

    def __post_init__(self):
        for field in ("route_id", "logical_model_id", "supplier_id", "supplier_native_model_id", "service_tier", "route_authority_id"):
            _identifier(getattr(self, field), field)
        if self.underlying_provider is not None:
            _identifier(self.underlying_provider, "underlying provider")
        if self.gateway_id is not None:
            _identifier(self.gateway_id, "gateway id")
        if (type(self.version) is not int or not 1 <= self.version <= MAX_TOKEN_COUNT
                or type(self.logical_model_version) is not int
                or not 1 <= self.logical_model_version <= MAX_TOKEN_COUNT):
            raise ContractError("Invalid route version")
        if self.route_kind not in {"direct", "gateway"}:
            raise ContractError("Invalid route kind")
        if self.route_kind == "direct" and (
            self.gateway_id is not None or self.provider_selection != "direct" or not self.underlying_provider
        ):
            raise ContractError("Invalid direct route policy")
        if self.route_kind == "gateway" and (self.gateway_id is None or self.provider_selection not in {"pinned", "dynamic"}):
            raise ContractError("Invalid gateway route policy")
        if self.provider_selection == "pinned" and not self.underlying_provider:
            raise ContractError("Pinned route requires an underlying provider")
        if self.provider_selection == "dynamic" and self.dynamic_provider_envelope_authorized and not self.dynamic_provider_envelope_id:
            raise ContractError("Authorized dynamic route requires envelope evidence")
        if self.token_authority_status not in {"verified", "unresolved"}:
            raise ContractError("Invalid token authority status")
        if type(self.operational_enabled) is not bool or type(self.admission_authorized) is not bool:
            raise ContractError("Invalid route eligibility flags")
        if type(self.context_capacity) is not int or not 1 <= self.context_capacity <= MAX_TOKEN_COUNT:
            raise ContractError("Invalid route context capacity")
        object.__setattr__(self, "capabilities", _capabilities(self.capabilities, "route capability"))


@dataclass(frozen=True)
class PricingVersion:
    pricing_version_id: str
    route_id: str
    route_version: int
    service_tier: str
    currency: str
    input_price_per_1m: Decimal | str | int
    output_price_per_1m: Decimal | str | int
    provider_request_fee: Decimal | str | int | None
    gateway_request_fee: Decimal | str | int | None
    fee_basis_verified: bool
    source_type: str
    source_evidence_id: str
    reviewed_at: datetime
    effective_from: datetime
    valid_until: datetime
    status: str
    billing_basis: str = "input_output_tokens_plus_request_fees_v1"
    provider_fee_applicable: bool = True
    gateway_fee_applicable: bool = True
    revoked: bool = False

    def __post_init__(self):
        for field in ("pricing_version_id", "route_id", "service_tier", "source_evidence_id"):
            _identifier(getattr(self, field), field)
        if type(self.route_version) is not int or not 1 <= self.route_version <= MAX_TOKEN_COUNT:
            raise ContractError("Invalid pricing route version")
        object.__setattr__(self, "input_price_per_1m", _decimal(self.input_price_per_1m, "input price"))
        object.__setattr__(self, "output_price_per_1m", _decimal(self.output_price_per_1m, "output price"))
        for field in ("provider_request_fee", "gateway_request_fee"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, _decimal(value, field))
        for applicable_field, amount_field in (
            ("provider_fee_applicable", "provider_request_fee"),
            ("gateway_fee_applicable", "gateway_request_fee"),
        ):
            applicable = getattr(self, applicable_field)
            amount = getattr(self, amount_field)
            if type(applicable) is not bool or (not applicable and amount is not None):
                raise ContractError("Non-applicable fees must be absent; applicable unresolved fees remain explicit")
        if self.currency != USD:
            raise ContractError("V1.3A supports USD only")
        if self.source_type not in {"provider_published", "gateway_published", "invoice_review", "manual_review"}:
            raise ContractError("Invalid pricing source type")
        if self.status not in {"pending", "approved"}:
            raise ContractError("Invalid pricing status")
        if self.billing_basis != "input_output_tokens_plus_request_fees_v1":
            raise ContractError("Unsupported billing basis")
        if type(self.revoked) is not bool:
            raise ContractError("Invalid revocation status")
        if type(self.fee_basis_verified) is not bool:
            raise ContractError("Invalid fee-basis status")
        for field in ("reviewed_at", "effective_from", "valid_until"):
            object.__setattr__(self, field, _aware(getattr(self, field), field))
        if self.valid_until <= self.effective_from:
            raise ContractError("Pricing validity interval must be nonempty")

    @property
    def total_request_fee(self) -> Decimal | None:
        if (not self.fee_basis_verified or self.revoked or
                (self.provider_fee_applicable and self.provider_request_fee is None) or
                (self.gateway_fee_applicable and self.gateway_request_fee is None)):
            return None
        with localcontext() as context:
            context.prec = 50
            return (self.provider_request_fee if self.provider_fee_applicable else Decimal(0)) + \
                   (self.gateway_request_fee if self.gateway_fee_applicable else Decimal(0))


@dataclass(frozen=True)
class RouteEvaluation:
    route_id: str
    route_version: int
    pricing_version_id: str | None
    operational_eligible: bool
    economic_eligible: bool
    eligible: bool
    estimated_cost: Decimal | None
    currency: str
    operational_reason_codes: tuple[str, ...]
    economic_reason_codes: tuple[str, ...]
    economic_rank: int | None = None

    def __post_init__(self):
        _identifier(self.route_id, "route id")
        if type(self.route_version) is not int or not 1 <= self.route_version <= MAX_TOKEN_COUNT:
            raise ContractError("Invalid route evaluation version")
        if self.pricing_version_id is not None:
            _identifier(self.pricing_version_id, "pricing version id")
        for field in ("operational_eligible", "economic_eligible", "eligible"):
            if type(getattr(self, field)) is not bool:
                raise ContractError("Invalid route eligibility result")
        if self.eligible != (self.operational_eligible and self.economic_eligible):
            raise ContractError("Overall eligibility must require both gates")
        if self.estimated_cost is not None:
            object.__setattr__(
                self,
                "estimated_cost",
                _decimal(self.estimated_cost, "estimated cost", max_scale=None, max_precision=50,
                         max_integer_digits=None),
            )
        if self.currency != USD:
            raise ContractError("V1.3A supports USD only")
        for field in ("operational_reason_codes", "economic_reason_codes"):
            codes = tuple(getattr(self, field))
            if len(codes) > len(ReasonCode) or any(code not in {item.value for item in ReasonCode} for code in codes):
                raise ContractError("Invalid route reason code")
            if len(set(codes)) != len(codes):
                raise ContractError("Duplicate route reason code")
            object.__setattr__(self, field, codes)
        if self.economic_eligible != (self.estimated_cost is not None and self.pricing_version_id is not None):
            raise ContractError("Economic eligibility requires a price and exact estimate")
        if self.economic_rank is not None and (type(self.economic_rank) is not int or not 1 <= self.economic_rank <= MAX_CANDIDATES):
            raise ContractError("Invalid economic rank")

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return self.operational_reason_codes + self.economic_reason_codes


@dataclass(frozen=True)
class RouteDecision:
    decision_version: str
    logical_model_id: str
    logical_model_version: int
    selector_version: str
    decision_time: datetime
    selected_route_id: str | None
    selected_route_version: int | None
    selected_pricing_version_id: str | None
    estimated_cost: Decimal | None
    currency: str
    input_token_bound: int
    output_allowance: int
    candidate_evaluations: tuple[RouteEvaluation, ...]
    selection_rationale: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "decision_time", _aware(self.decision_time, "decision time"))
        candidates = tuple(self.candidate_evaluations)
        if any(not isinstance(item, RouteEvaluation) for item in candidates):
            raise ContractError("Invalid candidate evaluation")
        if len({(item.route_id, item.route_version) for item in candidates}) != len(candidates):
            raise ContractError("Duplicate candidate evaluation")
        object.__setattr__(
            self,
            "candidate_evaluations",
            tuple(sorted(candidates, key=lambda item: (item.route_id, item.route_version))),
        )
        object.__setattr__(self, "selection_rationale", tuple(self.selection_rationale))
        _identifier(self.logical_model_id, "logical model id")
        _identifier(self.decision_version, "decision version")
        _identifier(self.selector_version, "selector version")
        if type(self.logical_model_version) is not int or not 1 <= self.logical_model_version <= MAX_TOKEN_COUNT:
            raise ContractError("Invalid decision model version")
        if type(self.input_token_bound) is not int or not 0 <= self.input_token_bound <= MAX_TOKEN_COUNT:
            raise ContractError("Invalid decision input token bound")
        if type(self.output_allowance) is not int or not 0 <= self.output_allowance <= MAX_TOKEN_COUNT:
            raise ContractError("Invalid decision output allowance")
        if self.currency != USD:
            raise ContractError("V1.3A supports USD only")
        if len(self.candidate_evaluations) > MAX_CANDIDATES:
            raise ContractError("Candidate evidence exceeds limit")
        allowed_rationale = {
            ReasonCode.NO_ELIGIBLE_ROUTE.value,
            ReasonCode.LOWEST_EFFECTIVE_COST.value,
            ReasonCode.TIE_BREAK_ROUTE_ID.value,
            ReasonCode.ELIGIBLE.value,
        }
        if len(self.selection_rationale) > 4 or any(code not in allowed_rationale for code in self.selection_rationale):
            raise ContractError("Invalid selection rationale")
        if self.estimated_cost is not None:
            object.__setattr__(
                self,
                "estimated_cost",
                _decimal(self.estimated_cost, "estimated cost", max_scale=None, max_precision=50,
                         max_integer_digits=None),
            )
        if self.selected_route_id is None:
            if any(value is not None for value in (self.selected_route_version, self.selected_pricing_version_id, self.estimated_cost)):
                raise ContractError("Unselected decision cannot carry selected-route evidence")
        else:
            _identifier(self.selected_route_id, "selected route id")
            _identifier(self.selected_pricing_version_id, "selected pricing version id")
            if (type(self.selected_route_version) is not int or
                    not 1 <= self.selected_route_version <= MAX_TOKEN_COUNT or self.estimated_cost is None):
                raise ContractError("Selected decision requires complete route evidence")
            selected = [item for item in self.candidate_evaluations if item.route_id == self.selected_route_id and item.route_version == self.selected_route_version]
            if (
                len(selected) != 1
                or not selected[0].eligible
                or selected[0].economic_rank != 1
                or selected[0].pricing_version_id != self.selected_pricing_version_id
                or selected[0].estimated_cost != self.estimated_cost
            ):
                raise ContractError("Selected route must be the first eligible candidate")
            tied = [
                item for item in self.candidate_evaluations
                if item.eligible and item.estimated_cost == self.estimated_cost
            ]
            if self.selection_rationale != (
                ReasonCode.LOWEST_EFFECTIVE_COST.value,
                *((ReasonCode.TIE_BREAK_ROUTE_ID.value,) if len(tied) > 1 else ()),
                ReasonCode.ELIGIBLE.value,
            ):
                raise ContractError("Invalid selected-route rationale")
        if self.selected_route_id is None and self.selection_rationale != (ReasonCode.NO_ELIGIBLE_ROUTE.value,):
            raise ContractError("No-route decision requires fail-closed rationale")

    def canonical_json(self) -> str:
        """Return bounded, order-stable JSON suitable for a later persisted digest."""
        payload = {
            "decision_version": self.decision_version,
            "logical_model_id": self.logical_model_id,
            "logical_model_version": self.logical_model_version,
            "selector_version": self.selector_version,
            "decision_time": _iso(self.decision_time),
            "selected": None if self.selected_route_id is None else {
                "route_id": self.selected_route_id,
                "route_version": self.selected_route_version,
                "pricing_version_id": self.selected_pricing_version_id,
                "estimated_cost": canonical_decimal(self.estimated_cost),
                "currency": self.currency,
            },
            "input_token_bound": self.input_token_bound,
            "output_allowance": self.output_allowance,
            "candidate_evaluations": [_evaluation_payload(e) for e in self.candidate_evaluations],
            "selection_rationale": list(self.selection_rationale),
        }
        result = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if len(result.encode("utf-8")) > MAX_DECISION_BYTES:
            raise ContractError("Canonical decision exceeds size limit")
        return result

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def snapshot_evidence(self) -> tuple[str, bytes]:
        """Return exact persisted UTF-8 TEXT and SHA-256 digest bytes."""
        snapshot = self.canonical_json()
        encoded = snapshot.encode("utf-8")
        if not 1 <= len(encoded) <= MAX_DECISION_BYTES:
            raise ContractError("Decision snapshot exceeds persistence bound")
        return snapshot, hashlib.sha256(encoded).digest()


def _iso(value: datetime) -> str:
    return _aware(value, "timestamp").isoformat(timespec="microseconds").replace("+00:00", "Z")


def _evaluation_payload(value: RouteEvaluation) -> dict:
    return {
        "route_id": value.route_id,
        "route_version": value.route_version,
        "pricing_version_id": value.pricing_version_id,
        "operational_eligible": value.operational_eligible,
        "economic_eligible": value.economic_eligible,
        "eligible": value.eligible,
        "estimated_cost": None if value.estimated_cost is None else canonical_decimal(value.estimated_cost),
        "currency": value.currency,
        "operational_reason_codes": list(value.operational_reason_codes),
        "economic_reason_codes": list(value.economic_reason_codes),
        "economic_rank": value.economic_rank,
    }


def effective_cost(
    input_token_bound: int,
    output_allowance: int,
    input_price_per_1m: Decimal | str | int,
    output_price_per_1m: Decimal | str | int,
    verified_request_attributable_route_fee: Decimal | str | int,
) -> Decimal:
    """Exact USD maximum supplier/route estimate; no customer or ledger economics."""
    for value, name in ((input_token_bound, "input token bound"), (output_allowance, "output allowance")):
        if type(value) is not int or not 0 <= value <= MAX_TOKEN_COUNT:
            raise ContractError(f"Invalid {name}")
    input_rate = _decimal(input_price_per_1m, "input price")
    output_rate = _decimal(output_price_per_1m, "output price")
    fee = _decimal(verified_request_attributable_route_fee, "request fee")
    with localcontext() as context:
        context.prec = 50
        return (Decimal(input_token_bound) * input_rate + Decimal(output_allowance) * output_rate) / RATE_DENOMINATOR + fee


def evaluate_route(
    route: RouteVersion,
    model: LogicalModelVersion,
    *,
    decision_time: datetime,
    input_token_bound: int,
    output_allowance: int,
    required_capabilities: Sequence[str] = (),
    pricing: PricingVersion | None = None,
) -> RouteEvaluation:
    at = _aware(decision_time, "decision time")
    for value, name in ((input_token_bound, "input token bound"), (output_allowance, "output allowance")):
        if type(value) is not int or not 0 <= value <= MAX_TOKEN_COUNT:
            raise ContractError(f"Invalid {name}")

    operational: list[str] = []
    economic: list[str] = []
    if model.status != "approved":
        operational.append(ReasonCode.MODEL_NOT_APPROVED.value)
    if route.logical_model_id != model.logical_model_id or route.logical_model_version != model.version:
        operational.append(ReasonCode.LOGICAL_MODEL_MISMATCH.value)
    if not route.operational_enabled:
        operational.append(ReasonCode.ROUTE_DISABLED.value)
    if not route.admission_authorized:
        operational.append(ReasonCode.ADMISSION_DENIED.value)
    if route.token_authority_status != "verified":
        operational.append(ReasonCode.TOKEN_AUTHORITY_UNRESOLVED.value)
    needed = set(model.required_capabilities) | set(_capabilities(required_capabilities, "required capability"))
    if not needed.issubset(route.capabilities):
        operational.append(ReasonCode.CAPABILITY_MISMATCH.value)
    if output_allowance > model.max_output_allowance or input_token_bound + output_allowance > min(model.context_capacity, route.context_capacity):
        operational.append(ReasonCode.CONTEXT_UNSUPPORTED.value)

    estimate: Decimal | None = None
    if pricing is None:
        economic.append(ReasonCode.PRICING_MISSING.value)
    else:
        if pricing.route_id != route.route_id or pricing.route_version != route.version or pricing.service_tier != route.service_tier:
            economic.append(ReasonCode.BILLING_BASIS_UNRESOLVED.value)
        if pricing.currency != USD:
            economic.append(ReasonCode.CURRENCY_UNSUPPORTED.value)
        if pricing.status != "approved":
            economic.append(ReasonCode.PRICING_UNVERIFIED.value)
        if pricing.revoked:
            economic.append(ReasonCode.PRICING_REVOKED.value)
        if at < pricing.effective_from:
            economic.append(ReasonCode.PRICING_NOT_EFFECTIVE.value)
        elif at >= pricing.valid_until:
            economic.append(ReasonCode.PRICING_EXPIRED.value)
        fee = pricing.total_request_fee
        if fee is None and ReasonCode.PRICING_REVOKED.value not in economic:
            economic.append(ReasonCode.BILLING_BASIS_UNRESOLVED.value)
        if route.provider_selection == "dynamic" and (
            not route.dynamic_provider_envelope_authorized
            or pricing.source_evidence_id != route.dynamic_provider_envelope_id
        ):
            economic.append(ReasonCode.BILLING_BASIS_UNRESOLVED.value)
        if not economic:
            estimate = effective_cost(input_token_bound, output_allowance, pricing.input_price_per_1m,
                                      pricing.output_price_per_1m, fee)

    operational_eligible = not operational
    economic_eligible = not economic
    eligible = operational_eligible and economic_eligible
    if eligible:
        operational.append(ReasonCode.ELIGIBLE.value)
    return RouteEvaluation(
        route_id=route.route_id,
        route_version=route.version,
        pricing_version_id=None if pricing is None else pricing.pricing_version_id,
        operational_eligible=operational_eligible,
        economic_eligible=economic_eligible,
        eligible=eligible,
        estimated_cost=estimate,
        currency=USD,
        operational_reason_codes=tuple(operational),
        economic_reason_codes=tuple(economic),
    )


def decide_routes(
    model: LogicalModelVersion,
    routes: Sequence[RouteVersion],
    pricing_by_route: Mapping[str, PricingVersion],
    *,
    decision_time: datetime,
    input_token_bound: int,
    output_allowance: int,
    selector_version: str = "economic-cost-v0",
    required_capabilities: Sequence[str] = (),
) -> RouteDecision:
    """Evaluate the bounded server-owned candidate set and choose deterministically."""
    if len(routes) > MAX_CANDIDATES:
        raise ContractError("Candidate evidence exceeds limit")
    for value, name in ((input_token_bound, "input token bound"), (output_allowance, "output allowance")):
        if type(value) is not int or not 0 <= value <= MAX_TOKEN_COUNT:
            raise ContractError(f"Invalid {name}")
    _identifier(selector_version, "selector version")
    _aware(decision_time, "decision time")
    ids = [(route.route_id, route.version) for route in routes]
    if len(set(ids)) != len(ids):
        raise ContractError("Duplicate route version")
    if len({route.route_id for route in routes}) != len(routes):
        raise ContractError("At most one route version per immutable route ID may be evaluated")

    evaluations = [
        evaluate_route(route, model, decision_time=decision_time, input_token_bound=input_token_bound,
                       output_allowance=output_allowance, required_capabilities=required_capabilities,
                       pricing=pricing_by_route.get(route.route_id))
        for route in routes
    ]
    eligible = sorted((item for item in evaluations if item.eligible),
                      key=lambda item: (item.estimated_cost, item.route_id))
    ranked = { (item.route_id, item.route_version): replace(item, economic_rank=index)
               for index, item in enumerate(eligible, start=1) }
    stable_evaluations = tuple(sorted((ranked.get((item.route_id, item.route_version), item) for item in evaluations),
                                      key=lambda item: (item.route_id, item.route_version)))

    selected = eligible[0] if eligible else None
    rationale: list[str] = []
    if selected is None:
        rationale.append(ReasonCode.NO_ELIGIBLE_ROUTE.value)
    else:
        rationale.append(ReasonCode.LOWEST_EFFECTIVE_COST.value)
        tied = [item for item in eligible if item.estimated_cost == selected.estimated_cost]
        if len(tied) > 1:
            rationale.append(ReasonCode.TIE_BREAK_ROUTE_ID.value)
        rationale.append(ReasonCode.ELIGIBLE.value)
    pricing = None if selected is None else pricing_by_route[selected.route_id]
    return RouteDecision(
        decision_version="route-decision-v1",
        logical_model_id=model.logical_model_id,
        logical_model_version=model.version,
        selector_version=selector_version,
        decision_time=_aware(decision_time, "decision time"),
        selected_route_id=None if selected is None else selected.route_id,
        selected_route_version=None if selected is None else selected.route_version,
        selected_pricing_version_id=None if pricing is None else pricing.pricing_version_id,
        estimated_cost=None if selected is None else selected.estimated_cost,
        currency=USD,
        input_token_bound=input_token_bound,
        output_allowance=output_allowance,
        candidate_evaluations=stable_evaluations,
        selection_rationale=tuple(rationale),
    )
