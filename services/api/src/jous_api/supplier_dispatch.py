"""Server-owned route/funding resolution at the provider dispatch boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from jous_supply.contracts import ResolvedSupplierCredential, RouteUnavailable
from jous_supply.registry import resolve


class DispatchAuthorityError(ValueError):
    """Persisted dispatch authority is absent, contradictory, or unsupported."""


@dataclass(frozen=True)
class DispatchPlan:
    route: Any
    funding_authority: Mapping[str, Any] | None
    legacy: bool


class SupplierCredentialResolver(Protocol):
    async def resolve(self, authority: Mapping[str, Any]) -> ResolvedSupplierCredential: ...


class RejectingCredentialResolver:
    """Product default: no live secret source is configured or activated."""
    async def resolve(self, authority: Mapping[str, Any]) -> ResolvedSupplierCredential:
        raise RouteUnavailable("Supplier credential authority is unavailable")


def plan_dispatch(task: Any, decision: Mapping[str, Any] | None,
                  authority: Mapping[str, Any] | None = None) -> DispatchPlan:
    """Resolve a dispatch only from a persisted decision, retaining legacy null behavior."""
    params = task.request_parameters
    requested_route_id = params.get("route_id") if isinstance(params, dict) else None
    if decision is None:
        if authority is not None:
            raise DispatchAuthorityError("Legacy task cannot be assigned funding authority")
        try:
            route = resolve(task.logical_model_id, requested_route_id)
        except Exception:
            raise DispatchAuthorityError("Legacy route is unsupported") from None
        if route.real_execution_eligible:
            raise DispatchAuthorityError("An enabled route requires a persisted RouteDecision")
        return DispatchPlan(route=route, funding_authority=None, legacy=True)

    expected = (task.id, task.organization_id, task.project_id, task.actor_user_id,
                task.dispatch_claim_id, task.logical_model_id)
    actual = (decision.get("task_id"), decision.get("organization_id"), decision.get("project_id"),
              decision.get("actor_user_id"), decision.get("dispatch_claim_id"),
              decision.get("logical_model_id"))
    if actual != expected:
        raise DispatchAuthorityError("Persisted RouteDecision source binding mismatch")
    if (not decision.get("pricing_version_id") or
            decision.get("pricing_authority_id") != decision.get("pricing_version_id") or
            decision.get("pricing_route_id") != decision.get("selected_route_id") or
            decision.get("pricing_route_version") != decision.get("selected_route_version") or
            decision.get("pricing_status") != "approved" or decision.get("pricing_is_revoked") is not False):
        raise DispatchAuthorityError("Persisted RouteDecision pricing binding is unavailable")
    if decision.get("selected_route_id") is None or decision.get("selected_route_version") != 1:
        raise DispatchAuthorityError("Persisted RouteDecision selected an unsupported route version")
    try:
        route = resolve(task.logical_model_id, decision["selected_route_id"])
    except Exception:
        raise DispatchAuthorityError("Persisted RouteDecision selected an unsupported route") from None
    if route.logical_model_id != decision.get("logical_model_id"):
        raise DispatchAuthorityError("Persisted RouteDecision route is not compatible with its logical model")

    binding = tuple(decision.get(name) for name in (
        "funding_authority_id", "funding_authority_version", "funding_authority_digest"))
    if all(value is None for value in binding):
        if authority is not None:
            raise DispatchAuthorityError("Unbound funding authority was supplied")
        if route.real_execution_eligible:
            raise DispatchAuthorityError("Enabled route requires a bound funding authority")
        return DispatchPlan(route=route, funding_authority=None, legacy=False)
    if any(value is None for value in binding) or authority is None:
        raise DispatchAuthorityError("Persisted funding authority binding is incomplete")
    if (authority.get("funding_authority_id"), authority.get("authority_version"),
            bytes(authority.get("authority_digest") or b"")) != (
            binding[0], binding[1], bytes(binding[2])):
        raise DispatchAuthorityError("Funding authority identity/version/digest mismatch")
    if (authority.get("route_id") != route.route_id or authority.get("route_version") != 1 or
            authority.get("supplier_id") != route.supplier_id):
        raise DispatchAuthorityError("Funding authority does not match selected supplier route")
    if (authority.get("scope") == "ORGANIZATION" and
            authority.get("organization_id") != task.organization_id):
        raise DispatchAuthorityError("Funding authority belongs to another organization")
    if authority.get("scope") not in {"JOUS_GLOBAL", "ORGANIZATION"}:
        raise DispatchAuthorityError("Funding authority scope is invalid")
    ref = authority.get("credential_authority_ref")
    if not isinstance(ref, str) or not ref.strip():
        raise DispatchAuthorityError("Bound funding authority has no dispatch credential reference")
    return DispatchPlan(route=route, funding_authority=authority, legacy=False)


def require_credential_match(plan: DispatchPlan,
                             credential: ResolvedSupplierCredential) -> None:
    authority = plan.funding_authority
    if authority is None:
        raise DispatchAuthorityError("Credential supplied without funding authority")
    if (credential.credential_authority_ref != authority.get("credential_authority_ref") or
            credential.supplier_id != plan.route.supplier_id or
            credential.underlying_provider != plan.route.underlying_provider):
        raise DispatchAuthorityError("Resolved credential does not match authorized supplier account")
