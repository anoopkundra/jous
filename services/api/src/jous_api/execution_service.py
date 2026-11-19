"""Single dispatch ownership; no retries, no recovery redispatch, no I/O in DB scope."""
import time
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from dataclasses import asdict
from fastapi import HTTPException
from jous_supply.contracts import ExecutionRequest, Outcome, RouteUnavailable
from jous_supply.registry import resolve, require_real_eligibility, catalog_digest
from jous_supply.token_budget import count, BRANCH
from .task_context import assemble, bounded
from .task_service import dto, request_hash, SubmissionResult


class OperationBudget:
    """Monotonic total budget; wall clock can only shorten it, never extend it."""
    def __init__(self, clock, monotonic):
        self.wall_end=clock()+timedelta(seconds=40)
        self.monotonic_end=monotonic()+40
        self.last=40.0

    def remaining(self, clock, monotonic):
        self.last=min(self.last,(self.wall_end-clock()).total_seconds(),self.monotonic_end-monotonic())
        return self.last


class ExecutionService:
    def __init__(self, store, adapter, *, admission=require_real_eligibility, clock=lambda: datetime.now(timezone.utc), counter=count, monotonic=time.monotonic):
        # Alternate collaborators are dependency-injected in offline tests only.
        # Product composition always uses these defaults and the denied HF adapter.
        self.monotonic = monotonic
        self.store, self.adapter, self.admission, self.clock, self.counter = store, adapter, admission, clock, counter

    async def submit(self, principal, project_id, data):
        operation_end = OperationBudget(self.clock,self.monotonic)
        try:
            async with asyncio.timeout(40):
                return await self._submit(principal, project_id, data, operation_end)
        except TimeoutError:
            raise HTTPException(503,'Task outcome unavailable') from None

    def remaining(self, operation_end):
        remaining = operation_end.remaining(self.clock,self.monotonic)
        if remaining <= 0: raise HTTPException(503,'Task outcome unavailable')
        return remaining

    async def _submit(self, principal, project_id, data, operation_end):
        self.remaining(operation_end)
        digest = request_hash(data)
        inserted = False
        try:
            async with self.store.unit(principal, project_id, execute=True) as unit:
                old = await unit.existing(data.client_request_id)
                if old is not None:
                    if old.request_sha256 != digest: raise HTTPException(409,'Request key already used')
                    return SubmissionResult(dto(old, await unit.outcome(old), now=self.clock()),200)
                package, context_hash, system, user = assemble(unit.project, data.prompt, data.task_context, actor_id=unit.actor, captured_at=self.clock(), request_id=data.client_request_id)
                route = resolve(data.logical_model_id, data.route_id)
                n, evidence, manifest_hash = self.counter(system,user)
                self.admission(route)  # Real HF denial is BEFORE durable claim.
                parameters = {'schema_version':1,'route_id':route.route_id,'catalog_digest':catalog_digest(),
                    'route_snapshot':asdict(route),'limits':{'context_capacity':32768,'output_allowance':1024,'safety_margin':3277},
                    'execution':{'stream':False,'max_tokens':1024,'temperature':0.7,'enable_thinking':False}}
                bounded(parameters,8192); bounded(evidence,8192)
                now = self.clock()
                values = dict(id=uuid4(),organization_id=unit.project.organization_id, project_id=project_id,
                    actor_user_id=unit.actor,client_request_id=data.client_request_id,request_sha256=digest,
                    prompt=data.prompt,context_package=package,context_sha256=context_hash,
                    logical_model_id=route.logical_model_id,supplier_id=route.supplier_id,
                    supplier_native_model_id=route.supplier_native_model_id,underlying_provider=route.underlying_provider,
                    admission_version=route.admission_version,request_parameters=parameters,tokenizer_manifest_sha256=manifest_hash,
                    template_branch=BRANCH,token_bound_method='LOCAL_PROVISIONAL',token_bound_evidence=evidence,
                    input_token_upper_bound=n,output_allowance=1024,safety_margin=3277,dispatch_claim_id=uuid4(),
                    dispatch_deadline_at=min(now+timedelta(seconds=39),operation_end.wall_end))
                self.remaining(operation_end)
                task, inserted = await unit.claim(values)
                if task is None: raise HTTPException(503,'Task unavailable')
                if task.request_sha256 != digest: raise HTTPException(409,'Request key already used')
                task_id = task.id
            # Only successful exit (including confirmed COMMIT) grants local
            # dispatch ownership. Any exception above exits without supplier I/O.
        except RouteUnavailable:
            raise HTTPException(503,'Execution unavailable') from None
        if not inserted:
            return SubmissionResult(await self.read(principal,project_id,task_id),200)
        try:
            async with self.store.unit(principal,project_id,execute=True) as unit:
                task = await unit.task(task_id)
                if unit.actor != task.actor_user_id: raise HTTPException(403,'Task unavailable')
                if await unit.outcome(task) is not None:
                    return SubmissionResult(dto(task, await unit.outcome(task), now=self.clock()),200)
                self.admission(resolve(task.logical_model_id, task.request_parameters['route_id']))
                if self.clock() >= task.dispatch_deadline_at: raise RouteUnavailable()
                remaining = self.remaining(operation_end)
                # Five seconds is reserved for authorized finalization and readback.
                # Do not start with less than one second of supplier budget.
                if remaining < 6: raise RouteUnavailable()
                supplier_end = self.monotonic() + min(20,remaining-5)
                deadline = min(task.dispatch_deadline_at, self.clock()+timedelta(seconds=min(20,remaining-5)))
        except RouteUnavailable:
            return SubmissionResult(await self._finalize(principal,project_id,task_id,Outcome('known_error',error_code='not_dispatched'),operation_end),201)
        # No store/session/connection scope exists across supplier I/O.
        remaining = self.remaining(operation_end)
        supplier_timeout = min(20,remaining-5,supplier_end-self.monotonic())
        if supplier_timeout < 1:
            return SubmissionResult(await self._finalize(principal,project_id,task_id,Outcome('known_error',error_code='not_dispatched'),operation_end),201)
        # The wall deadline is evidence only. Runtime authority is the fixed,
        # decreasing monotonic allowance, never reconstructed from this timestamp.
        deadline = min(deadline, self.clock()+timedelta(seconds=supplier_timeout))
        dispatch_started = self.clock()
        try:
            async with asyncio.timeout(supplier_timeout):
                outcome = await self.adapter.execute(ExecutionRequest(system,user,deadline))
        except TimeoutError:
            outcome = Outcome('unknown',error_code='provider_timeout',request_started_at=dispatch_started)
        except Exception:
            # Unknown adapter outcome is NEVER inferred to be non-execution.
            outcome = Outcome('unknown',error_code='transport_ambiguous',request_started_at=dispatch_started)
        result = await self._finalize(principal,project_id,task_id,outcome,operation_end)
        return SubmissionResult(result,202 if result['status']=='claimed' else 201)

    async def _finalize(self,principal,project_id,task_id,outcome,operation_end):
        self.remaining(operation_end)
        async with self.store.unit(principal,project_id,execute=True) as unit:
            task = await unit.task(task_id)
            if unit.actor != task.actor_user_id: raise HTTPException(403,'Task unavailable')
            self.remaining(operation_end)
            await unit.finalize(task,outcome)
        self.remaining(operation_end)
        # Never return an in-memory supplier result, even when INSERT flushed.
        return await self.read(principal,project_id,task_id)

    async def read(self,principal,project_id,task_id):
        async with self.store.unit(principal,project_id) as unit:
            task = await unit.task(task_id)
            return dto(task,await unit.outcome(task),now=self.clock())

    async def page(self,principal,project_id,limit,after):
        async with self.store.unit(principal,project_id) as unit:
            return await unit.page(limit,after)
