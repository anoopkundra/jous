"""Deterministic normalization of immutable V1.2 execution usage evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID, uuid5
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .usage_event_models import usage_events


NORMALIZER_VERSION = "jous.execution-usage.v1"
SOURCE_TYPE = "execution_usage"
SOURCE_REVISION = "execution-row-v1"
USAGE_FIELDS = ("input_tokens", "output_tokens", "total_tokens",
                "cached_input_tokens", "reasoning_tokens")
_NAMESPACE = UUID("9a5d4e8b-e62c-52dc-b507-c3028f9beefa")


class UsageNormalizationError(ValueError):
    """Persisted execution evidence does not satisfy its declared contract."""


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise UsageNormalizationError("Usage evidence timestamp must be timezone aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class NormalizedUsageEvent:
    usage_event_id: UUID
    organization_id: UUID
    project_id: UUID
    actor_user_id: UUID
    task_id: UUID
    dispatch_claim_id: UUID
    execution_id: UUID
    route_decision_id: UUID | None
    logical_model_id: str
    logical_model_version: int | None
    route_id: str | None
    route_version: int | None
    supplier_id: str
    underlying_provider: str
    reported_provider_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cached_input_tokens: int | None
    reasoning_tokens: int | None
    usage_status: str
    source_type: str
    source_reference: str
    source_revision: str
    observed_at: datetime
    normalizer_version: str
    canonical_payload: str
    evidence_sha256: bytes
    supersedes_usage_event_id: UUID | None


def normalize_execution(task, execution, *, route_decision=None,
                        normalizer_version: str = NORMALIZER_VERSION,
                        supersedes_usage_event_id: UUID | None = None) -> NormalizedUsageEvent:
    """Normalize only persisted execution evidence; never derive missing counts."""
    if execution.task_id != task.id or execution.dispatch_claim_id != task.dispatch_claim_id:
        raise UsageNormalizationError("Execution is not bound to task claim")
    if (execution.organization_id, execution.project_id, execution.actor_user_id) != (
            task.organization_id, task.project_id, task.actor_user_id):
        raise UsageNormalizationError("Execution tenant binding differs from task")
    if route_decision is not None and (
            route_decision.task_id != task.id
            or route_decision.dispatch_claim_id != task.dispatch_claim_id
            or (route_decision.organization_id, route_decision.project_id,
                route_decision.actor_user_id) !=
               (task.organization_id, task.project_id, task.actor_user_id)):
        raise UsageNormalizationError("Route decision is not bound to task claim")

    status = execution.usage_status
    source_usage = execution.usage
    if status not in {"available", "partial", "unavailable"}:
        raise UsageNormalizationError("Unsupported source usage status")
    if status == "unavailable":
        if source_usage is not None:
            raise UsageNormalizationError("Unavailable usage must not contain counts")
        usage = {name: None for name in USAGE_FIELDS}
    else:
        if not isinstance(source_usage, dict) or not source_usage or set(source_usage) - set(USAGE_FIELDS):
            raise UsageNormalizationError("Unsupported source usage shape")
        if any(type(value) is not int or value < 0 for value in source_usage.values()):
            raise UsageNormalizationError("Usage dimensions must be nonnegative integers")
        usage = {name: source_usage.get(name) for name in USAGE_FIELDS}
        if status == "available":
            required = ("input_tokens", "output_tokens", "total_tokens")
            if any(usage[name] is None for name in required):
                raise UsageNormalizationError("Available usage is incomplete")
        elif not any(value is not None for value in usage.values()):
            raise UsageNormalizationError("Partial usage must retain evidence")

    params = task.request_parameters
    route_id = params.get("route_id") if isinstance(params, dict) else None
    observed = execution.response_received_at or execution.request_started_at or execution.recorded_at
    observed_text = _iso(observed)
    decision_id = route_decision.task_id if route_decision is not None else None
    logical_version = route_decision.logical_model_version if route_decision is not None else None
    selected_route = route_decision.selected_route_id if route_decision is not None else route_id
    route_version = route_decision.selected_route_version if route_decision is not None else None
    if route_decision is not None and (task.logical_model_id != route_decision.logical_model_id
                                      or route_id != route_decision.selected_route_id):
        raise UsageNormalizationError("Route decision identity differs from task")

    # Execution rows are immutable and terminal/unique per task. This explicit
    # source revision is therefore stable and can also be checked in SQL; the
    # canonical event digest binds the selected source values.
    source_revision = SOURCE_REVISION
    identity = f"{execution.id}:{normalizer_version}:{source_revision}"
    event_id = uuid5(_NAMESPACE, identity)
    payload = {
        "schema_version": "jous.usage-event.v1",
        "usage_event_id": str(event_id),
        "organization_id": str(task.organization_id),
        "project_id": str(task.project_id),
        "actor_user_id": str(task.actor_user_id),
        "task_id": str(task.id),
        "dispatch_claim_id": str(task.dispatch_claim_id),
        "execution_id": str(execution.id),
        "route_decision_id": str(decision_id) if decision_id else None,
        "logical_model_id": task.logical_model_id,
        "logical_model_version": logical_version,
        "route_id": selected_route,
        "route_version": route_version,
        "supplier_id": task.supplier_id,
        "underlying_provider": task.underlying_provider,
        "reported_provider_id": execution.reported_provider_id,
        **usage,
        "usage_status": status.upper(),
        "source_type": SOURCE_TYPE,
        "source_reference": str(execution.id),
        "source_revision": source_revision,
        "observed_at": observed_text,
        "normalizer_version": normalizer_version,
        "supersedes_usage_event_id": (str(supersedes_usage_event_id)
                                       if supersedes_usage_event_id else None),
    }
    encoded = canonical_json(payload)
    return NormalizedUsageEvent(
        usage_event_id=event_id, organization_id=task.organization_id,
        project_id=task.project_id, actor_user_id=task.actor_user_id,
        task_id=task.id, dispatch_claim_id=task.dispatch_claim_id,
        execution_id=execution.id, route_decision_id=decision_id,
        logical_model_id=task.logical_model_id, logical_model_version=logical_version,
        route_id=selected_route, route_version=route_version,
        supplier_id=task.supplier_id, underlying_provider=task.underlying_provider,
        reported_provider_id=execution.reported_provider_id,
        **usage, usage_status=status.upper(), source_type=SOURCE_TYPE,
        source_reference=str(execution.id), source_revision=source_revision,
        observed_at=observed, normalizer_version=normalizer_version,
        canonical_payload=encoded,
        evidence_sha256=hashlib.sha256(encoded.encode("utf-8")).digest(),
        supersedes_usage_event_id=supersedes_usage_event_id,
    )


async def persist_usage_event(session, event: NormalizedUsageEvent):
    """Insert idempotently; a source-identity collision must be byte-equivalent."""
    values = {name: getattr(event, name) for name in usage_events.c.keys()
              if name != "recorded_at"}
    result = await session.execute(insert(usage_events).values(**values)
        .on_conflict_do_nothing(constraint="uq_usage_events_source_identity")
        .returning(usage_events.c.usage_event_id))
    inserted = result.scalar_one_or_none()
    if inserted is not None:
        return event.usage_event_id
    existing = await session.execute(select(usage_events.c.usage_event_id,
        usage_events.c.evidence_sha256).where(
            usage_events.c.execution_id == event.execution_id,
            usage_events.c.normalizer_version == event.normalizer_version,
            usage_events.c.source_revision == event.source_revision))
    row = existing.one_or_none()
    if row is None or row.usage_event_id != event.usage_event_id or bytes(row.evidence_sha256) != event.evidence_sha256:
        raise UsageNormalizationError("UsageEvent source identity collision")
    return event.usage_event_id
