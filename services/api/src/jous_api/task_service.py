"""Append-only task storage. Each unit owns one short authorized transaction."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4
import hashlib
from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from .access import AccessService
from .task_permissions import authorize_project
from .task_models import Task, Execution
from .task_context import canonical, bounded, validate_claim
from .usage_events import normalize_execution, persist_usage_event
from sqlalchemy import text
from types import SimpleNamespace


def request_hash(data):
    # Exactly the normalized client request, not a mutable project snapshot.
    return hashlib.sha256(canonical({'schema_version':'jous.task.request.v1','prompt': data.prompt, 'task_context': data.task_context,
        'logical_model_id': data.logical_model_id, 'route_id': data.route_id})).digest()


class TaskDetailDTO(dict):
    """Explicit safe detail projection; never ORM serialization."""


class TaskSummaryDTO(dict):
    """Bounded list projection; no response/context/usage payload."""


class SubmissionResult(dict):
    def __init__(self, value, status):
        super().__init__(value)
        self.http_status = status


def dto(task, outcome=None, *, now=None):
    now = now or datetime.now(timezone.utc)
    status = outcome.status if outcome else ('unknown' if now >= task.dispatch_deadline_at else 'claimed')
    return TaskDetailDTO({'id': str(task.id), 'project_id': str(task.project_id), 'prompt': task.prompt,
        'logical_model_id': task.logical_model_id, 'supplier': task.supplier_id,
        'native_model': task.supplier_native_model_id, 'status': status,
        'created_at': task.created_at.isoformat(), 'execution': None if outcome is None else {
            'id': str(outcome.id), 'status': outcome.status, 'response_text': outcome.response_text,
            'reported_model_id': outcome.reported_model_id, 'reported_provider_id': outcome.reported_provider_id,
            'finish_reason': outcome.finish_reason, 'usage': outcome.usage, 'usage_status': outcome.usage_status,
            'error_code': outcome.error_code, 'recorded_at': outcome.recorded_at.isoformat()}})


class SQLTaskStore:
    def __init__(self, database): self.database = database

    @asynccontextmanager
    async def unit(self, principal, project_id, *, execute=False):
        async with self.database.scoped_transaction() as session:
            access = AccessService(session)
            identity = await access.resolve(principal)
            project = await authorize_project(access, identity, project_id, execute=execute)
            yield SQLUnit(session, project, identity.user_id)


class SQLUnit:
    def __init__(self, session, project, actor):
        self.session, self.project, self.actor = session, project, actor

    def scope(self):
        return (Task.organization_id == self.project.organization_id, Task.project_id == self.project.id)

    async def existing(self, key):
        return await self.session.scalar(select(Task).where(*self.scope(), Task.actor_user_id == self.actor,
                                                            Task.client_request_id == key))

    async def task(self, task_id):
        task = await self.session.scalar(select(Task).where(*self.scope(), Task.id == task_id))
        if task is None: raise HTTPException(404, 'Task unavailable')
        return task

    async def outcome(self, task):
        return await self.session.scalar(select(Execution).where(Execution.task_id == task.id,
            Execution.organization_id == self.project.organization_id, Execution.project_id == self.project.id))

    async def dispatch_context(self, task):
        """Read the exact persisted decision and bound non-secret authority in the auth transaction."""
        result = await self.session.execute(text("""SELECT
            d.task_id,d.organization_id,d.project_id,d.actor_user_id,d.dispatch_claim_id,
            d.logical_model_id,d.logical_model_version,d.selected_route_id,d.selected_route_version,
            d.pricing_version_id,d.funding_authority_id,d.funding_authority_version,d.funding_authority_digest,
            p.pricing_version_id AS pricing_authority_id,p.route_id AS pricing_route_id,
            p.route_version AS pricing_route_version,p.pricing_status,
            EXISTS (SELECT 1 FROM public.route_pricing_revocations x
                    WHERE x.pricing_version_id=d.pricing_version_id) AS pricing_is_revoked,
            a.scope AS authority_scope,a.organization_id AS authority_organization_id,
            a.supplier_id AS authority_supplier_id,a.route_id AS authority_route_id,
            a.route_version AS authority_route_version,a.credential_authority_ref,
            a.authority_digest AS authority_digest
          FROM public.route_decisions d
          LEFT JOIN public.supplier_funding_authorities a
            ON a.funding_authority_id=d.funding_authority_id
           AND a.authority_version=d.funding_authority_version
          LEFT JOIN public.route_pricing_versions p
            ON p.pricing_version_id=d.pricing_version_id AND p.route_id=d.selected_route_id
           AND p.route_version=d.selected_route_version AND p.service_tier=d.service_tier
           AND p.currency=d.currency AND p.billing_basis=d.billing_basis
         WHERE d.task_id=:task_id"""), {"task_id": task.id})
        row = result.mappings().one_or_none()
        if row is None:
            return None, None
        decision = {name: row[name] for name in (
            "task_id","organization_id","project_id","actor_user_id","dispatch_claim_id",
            "logical_model_id","logical_model_version","selected_route_id","selected_route_version",
            "pricing_version_id","funding_authority_id","funding_authority_version","funding_authority_digest")}
        decision.update({name: row[name] for name in (
            "pricing_authority_id","pricing_route_id","pricing_route_version","pricing_status","pricing_is_revoked")})
        authority = None
        if row["funding_authority_id"] is not None:
            authority = {
                "funding_authority_id": row["funding_authority_id"],
                "authority_version": row["funding_authority_version"],
                "authority_digest": row["authority_digest"],
                "scope": row["authority_scope"],
                "organization_id": row["authority_organization_id"],
                "supplier_id": row["authority_supplier_id"],
                "route_id": row["authority_route_id"],
                "route_version": row["authority_route_version"],
                "credential_authority_ref": row["credential_authority_ref"],
            }
        return decision, authority

    async def claim(self, values):
        validate_claim(values)
        for name, maximum in [('context_package',32768),('request_parameters',8192),('token_bound_evidence',8192)]:
            bounded(values[name], maximum)
        result = await self.session.scalar(insert(Task).values(**values).on_conflict_do_nothing(
            constraint='uq_tasks_request').returning(Task.id))
        if result is None:
            return await self.existing(values['client_request_id']), False
        return await self.task(result), True

    async def finalize(self, task, outcome):
        from dataclasses import asdict
        values = asdict(outcome)
        if values['usage'] is not None: bounded(values['usage'],8192)
        if outcome.request_started_at is not None and not task.created_at <= outcome.request_started_at < task.dispatch_deadline_at:
            raise ValueError('Invalid dispatch timestamp')
        row = Execution(id=uuid4(), task_id=task.id, organization_id=task.organization_id,
            project_id=task.project_id, actor_user_id=self.actor, dispatch_claim_id=task.dispatch_claim_id, **values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        decision_row = (await self.session.execute(text("""SELECT task_id,organization_id,project_id,
            actor_user_id,dispatch_claim_id,logical_model_id,logical_model_version,
            selected_route_id,selected_route_version FROM public.route_decisions WHERE task_id=:task_id"""),
            {"task_id": task.id})).mappings().one_or_none()
        decision = SimpleNamespace(**decision_row) if decision_row is not None else None
        dispatch_route = None
        if decision is not None:
            from jous_supply.registry import resolve
            dispatch_route = resolve(task.logical_model_id, decision.selected_route_id)
        event = normalize_execution(task, row, route_decision=decision, dispatch_route=dispatch_route)
        await persist_usage_event(self.session, event)
        return row

    async def page(self, limit, after):
        stmt = select(Task).where(*self.scope())
        if after:
            anchor = await self.task(after)
            stmt = stmt.where(tuple_(Task.created_at,Task.id) > tuple_(anchor.created_at,anchor.id))
        rows = (await self.session.scalars(stmt.order_by(Task.created_at,Task.id).limit(limit+1))).all()
        result = []
        for t in rows[:limit]:
            outcome = await self.outcome(t)
            result.append(TaskSummaryDTO(id=str(t.id),project_id=str(t.project_id),prompt_preview=t.prompt[:256],
                status=outcome.status if outcome else ('unknown' if datetime.now(timezone.utc)>=t.dispatch_deadline_at else 'claimed'),
                created_at=t.created_at.isoformat()))
        return {'tasks':result,'next_cursor': str(rows[limit-1].id) if len(rows)>limit else None}
