"""In-memory lifecycle tests. No SQL, provider sockets or operational admission."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
import unittest
from unittest.mock import AsyncMock
from fastapi import HTTPException
from jous_api.identity import AccessDenied
from jous_api.task_api import SubmitTask
from jous_api.task_context import validate_claim
from jous_api.execution_service import ExecutionService, OperationBudget
from jous_supply.contracts import Outcome
from jous_supply.registry import HF_ROUTE
from jous_supply.token_budget import count


class Store:
    def __init__(self):
        self.project=SimpleNamespace(id=uuid4(),organization_id=uuid4(),name='My First Project',description='Context')
        self.actor=uuid4(); self.rows={}; self.outcomes={}; self.depth=0; self.calls=0
        self.decision=None; self.funding_authority=None
        self.denied=set(); self.uncertain=False; self.fail_finalize=False
        self.lock=asyncio.Lock()

    @asynccontextmanager
    async def unit(self,principal,project_id,*,execute=False):
        async with self.lock:
            self.calls+=1
            if project_id!=self.project.id or principal!='mapped' or self.calls in self.denied:
                raise AccessDenied()
            self.depth+=1
            try:
                yield self
                if self.uncertain and self.rows: raise RuntimeError('Commit outcome uncertain')
            finally:self.depth-=1

    async def existing(self,key):
        return next((t for t in self.rows.values() if t.client_request_id==key and t.actor_user_id==self.actor),None)
    async def claim(self,values):
        validate_claim(values)
        old=await self.existing(values['client_request_id'])
        if old:return old,False
        row=SimpleNamespace(**values,created_at=datetime.now(timezone.utc));self.rows[row.id]=row
        return row,True
    async def task(self,key):
        if key not in self.rows:raise HTTPException(404)
        return self.rows[key]
    async def outcome(self,task):return self.outcomes.get(task.id)
    async def dispatch_context(self,task):
        if callable(self.decision): return self.decision(task),self.funding_authority
        return self.decision,self.funding_authority
    async def finalize(self,task,outcome):
        if self.fail_finalize:raise RuntimeError('Finalization unavailable')
        if task.id in self.outcomes:raise RuntimeError('Duplicate terminal outcome')
        from dataclasses import asdict
        row=SimpleNamespace(**asdict(outcome),id=uuid4(),recorded_at=datetime.now(timezone.utc))
        self.outcomes[task.id]=row;return row


def data(**changes):
    return SubmitTask.model_validate(dict(prompt='Summarize this project',task_context=None,
        logical_model_id=HF_ROUTE.logical_model_id,route_id=HF_ROUTE.route_id,client_request_id=uuid4(),**changes))


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store=Store()
        async def execute(request):
            self.assertEqual(self.store.depth,0)
            return Outcome('succeeded',response_text='Actual mock result',usage={'input_tokens':7},usage_status='partial')
        self.adapter=SimpleNamespace(execute=AsyncMock(side_effect=execute))
        self.service=ExecutionService(self.store,self.adapter,admission=lambda route:None)

    async def test_success_returns_persisted_result_without_db_during_io(self):
        result=await self.service.submit('mapped',self.store.project.id,data())
        self.assertEqual(result['execution']['response_text'],'Actual mock result')
        self.assertEqual(len(self.store.rows),1);self.assertEqual(len(self.store.outcomes),1)
        self.assertNotIn('organization_id',result);self.assertNotIn('provider_response_id',result['execution'])

    async def test_real_route_denied_before_claim(self):
        self.service=ExecutionService(self.store,self.adapter)
        with self.assertRaises(HTTPException) as e:await self.service.submit('mapped',self.store.project.id,data())
        self.assertEqual(e.exception.status_code,503);self.assertFalse(self.store.rows)
        self.adapter.execute.assert_not_awaited()

    async def test_duplicate_same_key_never_redispatches(self):
        request=data();a=await self.service.submit('mapped',self.store.project.id,request)
        b=await self.service.submit('mapped',self.store.project.id,request)
        self.assertEqual(a,b);self.adapter.execute.assert_awaited_once()

    async def test_different_request_same_key_conflicts(self):
        request=data();await self.service.submit('mapped',self.store.project.id,request)
        request.prompt='Different request'
        with self.assertRaises(HTTPException) as e:await self.service.submit('mapped',self.store.project.id,request)
        self.assertEqual(e.exception.status_code,409);self.adapter.execute.assert_awaited_once()

    async def test_concurrent_duplicate_one_dispatch(self):
        request=data()
        await asyncio.gather(*(self.service.submit('mapped',self.store.project.id,request) for _ in range(2)))
        self.adapter.execute.assert_awaited_once()

    async def test_uncertain_commit_never_dispatches(self):
        self.store.uncertain=True
        with self.assertRaises(RuntimeError):await self.service.submit('mapped',self.store.project.id,data())
        self.adapter.execute.assert_not_awaited()

    async def test_revocation_each_phase(self):
        for phase in (1,2,3):
            self.setUp();self.store.denied={phase}
            with self.assertRaises(AccessDenied):await self.service.submit('mapped',self.store.project.id,data())
            self.assertEqual(self.adapter.execute.await_count,1 if phase==3 else 0)
            self.assertFalse(self.store.outcomes)

    async def test_finalization_failure_not_redispatched(self):
        request=data();self.store.fail_finalize=True
        with self.assertRaises(RuntimeError):await self.service.submit('mapped',self.store.project.id,request)
        result=await self.service.submit('mapped',self.store.project.id,request)
        self.assertEqual(result['status'],'claimed');self.adapter.execute.assert_awaited_once()

    async def test_timeout_and_lost_response_never_retry(self):
        for error in (TimeoutError(),OSError()):
            self.setUp();self.adapter.execute.side_effect=error;request=data()
            result=await self.service.submit('mapped',self.store.project.id,request)
            self.assertEqual(result['status'],'unknown')
            await self.service.submit('mapped',self.store.project.id,request)
            self.adapter.execute.assert_awaited_once()

    async def test_crash_after_claim_derived_unknown(self):
        self.adapter.execute.side_effect=asyncio.CancelledError()
        request=data()
        with self.assertRaises(asyncio.CancelledError):await self.service.submit('mapped',self.store.project.id,request)
        task=next(iter(self.store.rows.values()));task.dispatch_deadline_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        result=await self.service.submit('mapped',self.store.project.id,request)
        self.assertEqual(result['status'],'unknown');self.assertIsNone(result['execution'])
        self.adapter.execute.assert_awaited_once()

    async def test_cross_project_and_unknown_identity(self):
        for principal,project in [('mapped',uuid4()),('unknown',self.store.project.id)]:
            with self.assertRaises(AccessDenied):await self.service.submit(principal,project,data())
        self.adapter.execute.assert_not_awaited()

    async def test_deadline_hierarchy_and_finalization_reserve(self):
        now=datetime.now(timezone.utc);ticks=[now]
        self.service.clock=lambda:ticks[0];self.service.monotonic=lambda:0
        original=self.store.task
        async def preflight(key):
            task=await original(key)
            if self.store.calls==2:ticks[0]=now+timedelta(seconds=25)
            return task
        self.store.task=preflight
        async def execute(request):
            self.assertEqual(request.deadline,now+timedelta(seconds=35))
            ticks[0]=request.deadline
            raise TimeoutError()
        self.adapter.execute.side_effect=execute
        result=await self.service.submit('mapped',self.store.project.id,data())
        self.assertEqual(result['status'],'unknown');self.assertEqual(len(self.store.outcomes),1)
        budget=OperationBudget(lambda:now,lambda:0)
        self.assertEqual(self.service.remaining(budget),5)

    async def test_late_preflight_prevents_dispatch(self):
        now=datetime.now(timezone.utc);ticks=[now];self.service.clock=lambda:ticks[0];self.service.monotonic=lambda:0
        original=self.store.task
        async def late(key):
            task=await original(key)
            if self.store.calls==2:ticks[0]=now+timedelta(seconds=35)
            return task
        self.store.task=late
        result=await self.service.submit('mapped',self.store.project.id,data())
        self.assertEqual(result['execution']['error_code'],'not_dispatched');self.adapter.execute.assert_not_awaited()

    async def test_full_initial_supplier_budget_never_exceeds_twenty(self):
        now=datetime.now(timezone.utc);self.service.clock=lambda:now;self.service.monotonic=lambda:0
        async def execute(request):
            self.assertEqual((request.deadline-now).total_seconds(),20)
            return Outcome('succeeded',response_text='Result')
        self.adapter.execute.side_effect=execute
        await self.service.submit('mapped',self.store.project.id,data())

    async def test_persisted_decision_and_funding_authority_drive_fake_dispatch(self):
        from jous_supply.contracts import ResolvedSupplierCredential
        authority_id=uuid4(); digest=b'a'*32
        self.store.funding_authority={"funding_authority_id":authority_id,"authority_version":1,
            "authority_digest":digest,"scope":"JOUS_GLOBAL","organization_id":None,
            "supplier_id":HF_ROUTE.supplier_id,"route_id":HF_ROUTE.route_id,"route_version":1,
            "credential_authority_ref":"ACCOUNT_A","cost_bearer":"JOUS_BORNE"}
        def decision(task):
            return {"task_id":task.id,"organization_id":task.organization_id,"project_id":task.project_id,
                "actor_user_id":task.actor_user_id,"dispatch_claim_id":task.dispatch_claim_id,
                "logical_model_id":task.logical_model_id,"selected_route_id":HF_ROUTE.route_id,
                "selected_route_version":1,"pricing_version_id":"price-v1","pricing_authority_id":"price-v1",
                "pricing_route_id":HF_ROUTE.route_id,"pricing_route_version":1,"pricing_status":"approved",
                "pricing_is_revoked":False,"funding_authority_id":authority_id,"funding_authority_version":1,
                "funding_authority_digest":digest}
        self.store.decision=decision
        credential=ResolvedSupplierCredential("ACCOUNT_A",HF_ROUTE.supplier_id,HF_ROUTE.underlying_provider,"fake-secret-v1")
        resolver=SimpleNamespace(resolve=AsyncMock(return_value=credential))
        async def dispatch(request,received):
            self.assertEqual(self.store.depth,0)
            self.assertEqual(request.route_id,HF_ROUTE.route_id)
            self.assertIs(received,credential)
            return Outcome('succeeded',response_text='mock',credential_authority_ref=received.credential_authority_ref)
        self.adapter.execute.side_effect=dispatch
        self.service=ExecutionService(self.store,self.adapter,credential_resolver=resolver,admission=lambda route:None)
        result=await self.service.submit('mapped',self.store.project.id,data())
        self.adapter.execute.assert_awaited_once()
        self.assertEqual(resolver.resolve.await_count,1)
        execution=next(iter(self.store.outcomes.values()))
        self.assertEqual(execution.credential_authority_ref,'ACCOUNT_A')
        self.assertEqual(result['execution']['status'],'succeeded')

    async def test_funding_resolver_mismatch_fails_before_adapter(self):
        from jous_supply.contracts import ResolvedSupplierCredential
        authority_id=uuid4(); digest=b'b'*32
        self.store.funding_authority={"funding_authority_id":authority_id,"authority_version":1,
            "authority_digest":digest,"scope":"JOUS_GLOBAL","organization_id":None,
            "supplier_id":HF_ROUTE.supplier_id,"route_id":HF_ROUTE.route_id,"route_version":1,
            "credential_authority_ref":"ACCOUNT_A","cost_bearer":"JOUS_BORNE"}
        def decision(task):
            return {"task_id":task.id,"organization_id":task.organization_id,"project_id":task.project_id,
                "actor_user_id":task.actor_user_id,"dispatch_claim_id":task.dispatch_claim_id,
                "logical_model_id":task.logical_model_id,"selected_route_id":HF_ROUTE.route_id,
                "selected_route_version":1,"pricing_version_id":"price-v1","pricing_authority_id":"price-v1",
                "pricing_route_id":HF_ROUTE.route_id,"pricing_route_version":1,"pricing_status":"approved",
                "pricing_is_revoked":False,"funding_authority_id":authority_id,"funding_authority_version":1,
                "funding_authority_digest":digest}
        self.store.decision=decision
        resolver=SimpleNamespace(resolve=AsyncMock(return_value=ResolvedSupplierCredential(
            "ACCOUNT_B",HF_ROUTE.supplier_id,HF_ROUTE.underlying_provider,"fake-secret-v2")))
        self.service=ExecutionService(self.store,self.adapter,credential_resolver=resolver,admission=lambda route:None)
        result=await self.service.submit('mapped',self.store.project.id,data())
        self.adapter.execute.assert_not_awaited()
        self.assertEqual(result['execution']['error_code'],'not_dispatched')
        self.assertIsNone(result['execution'].get('credential_authority_ref'))

    async def test_adapter_provenance_mismatch_does_not_persist_execution(self):
        from jous_supply.contracts import ResolvedSupplierCredential
        authority_id=uuid4(); digest=b'c'*32
        self.store.funding_authority={"funding_authority_id":authority_id,"authority_version":1,
            "authority_digest":digest,"scope":"JOUS_GLOBAL","organization_id":None,
            "supplier_id":HF_ROUTE.supplier_id,"route_id":HF_ROUTE.route_id,"route_version":1,
            "credential_authority_ref":"ACCOUNT_A","cost_bearer":"JOUS_BORNE"}
        def decision(task):
            return {"task_id":task.id,"organization_id":task.organization_id,"project_id":task.project_id,
                "actor_user_id":task.actor_user_id,"dispatch_claim_id":task.dispatch_claim_id,
                "logical_model_id":task.logical_model_id,"selected_route_id":HF_ROUTE.route_id,
                "selected_route_version":1,"pricing_version_id":"price-v1","pricing_authority_id":"price-v1",
                "pricing_route_id":HF_ROUTE.route_id,"pricing_route_version":1,"pricing_status":"approved",
                "pricing_is_revoked":False,"funding_authority_id":authority_id,"funding_authority_version":1,
                "funding_authority_digest":digest}
        self.store.decision=decision
        resolver=SimpleNamespace(resolve=AsyncMock(return_value=ResolvedSupplierCredential(
            "ACCOUNT_A",HF_ROUTE.supplier_id,HF_ROUTE.underlying_provider,"fake-secret-v1")))
        self.adapter.execute.side_effect=None
        self.adapter.execute.return_value=Outcome('succeeded',response_text='mock',credential_authority_ref='ACCOUNT_B')
        self.service=ExecutionService(self.store,self.adapter,credential_resolver=resolver,admission=lambda route:None)
        with self.assertRaises(HTTPException):
            await self.service.submit('mapped',self.store.project.id,data())
        self.assertEqual(self.adapter.execute.await_count,1)
        self.assertFalse(self.store.outcomes)

    async def test_dispatch_wall_rollback_cannot_extend_monotonic_supplier_allowance(self):
        from unittest.mock import patch
        now=datetime.now(timezone.utc)
        wall=[now];mono=[0.0];after_preflight=[False];post_clock_calls=[0]
        def clock():
            stamp=wall[0]
            if after_preflight[0]:
                post_clock_calls[0]+=1
                # Roll back after the final evidence deadline was formed, before
                # the actual timeout is entered. The old datetime subtraction
                # would authorize 20 seconds here instead of the reserved 10.
                if post_clock_calls[0]==3:wall[0]=now-timedelta(seconds=100)
            return stamp
        self.service.clock=clock;self.service.monotonic=lambda:mono[0]
        original_task=self.store.task
        async def preflight(key):
            task=await original_task(key)
            if self.store.calls==2:wall[0]=now+timedelta(seconds=25);mono[0]=25
            return task
        self.store.task=preflight
        original_unit=self.store.unit
        @asynccontextmanager
        async def unit(*args,**kwargs):
            async with original_unit(*args,**kwargs) as value:
                is_preflight=self.store.calls==2
                yield value
            if is_preflight:after_preflight[0]=True
        self.store.unit=unit
        allowances=[];real_timeout=asyncio.timeout
        def observed_timeout(seconds):
            allowances.append(seconds)
            return real_timeout(seconds) # Actual asyncio timeout, not a fake timer.
        async def execute(request):
            self.assertEqual(self.store.depth,0)
            self.assertLess(clock(),now) # Actual dispatch sees wall-clock rollback.
            self.assertGreater((request.deadline-clock()).total_seconds(),20)
            self.assertEqual(allowances,[40,10])
            self.assertLessEqual(allowances[-1],20)
            self.assertLessEqual(allowances[-1],40-mono[0]-5)
            mono[0]+=allowances[-1] # Deterministic supplier timeout, no sleep.
            raise TimeoutError()
        self.adapter.execute.side_effect=execute
        with patch('jous_api.execution_service.asyncio.timeout',side_effect=observed_timeout):
            result=await self.service.submit('mapped',self.store.project.id,data())
        self.adapter.execute.assert_awaited_once()
        self.assertEqual(allowances,[40,10])
        self.assertEqual(result['status'],'unknown')
        self.assertEqual(40-mono[0],5) # Finalization/readback reserve protected.
        self.assertEqual(len(self.store.outcomes),1)


class SQLStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_unit_lookup_claim_conflict_retrieval_and_terminal_insert(self):
        from unittest.mock import MagicMock,patch
        from sqlalchemy.dialects.postgresql import dialect
        from jous_api.task_service import SQLUnit
        from jous_api.task_models import Task
        store=Store();service=ExecutionService(store,SimpleNamespace(execute=AsyncMock(return_value=Outcome('succeeded',response_text='x'))),admission=lambda route:None)
        await service.submit('mapped',store.project.id,data())
        task=next(iter(store.rows.values()));values={k:v for k,v in vars(task).items() if k!='created_at'}
        empty_decision=SimpleNamespace(mappings=lambda:SimpleNamespace(one_or_none=lambda:None))
        inserted_event=SimpleNamespace(scalar_one_or_none=lambda:uuid4())
        async def refresh(row):row.recorded_at=datetime.now(timezone.utc)
        session=SimpleNamespace(scalar=AsyncMock(),add=MagicMock(),flush=AsyncMock(),
            refresh=AsyncMock(side_effect=refresh),execute=AsyncMock(side_effect=[empty_decision,inserted_event]))
        unit=SQLUnit(session,store.project,store.actor)
        session.scalar.return_value=task
        await unit.existing(task.client_request_id)
        stmt=session.scalar.call_args.args[0];compiled=stmt.compile(dialect=dialect())
        for column in ('organization_id','project_id','actor_user_id','client_request_id'):self.assertIn(column,str(compiled))
        self.assertIn(task.client_request_id,compiled.params.values())
        session.scalar.side_effect=[task.id,task]
        claimed,creator=await unit.claim(values);self.assertIs(claimed,task);self.assertTrue(creator)
        sql=str(session.scalar.call_args_list[-2].args[0].compile(dialect=dialect()))
        self.assertIn('INSERT INTO public.tasks',sql);self.assertIn('ON CONFLICT ON CONSTRAINT uq_tasks_request DO NOTHING',sql)
        session.scalar.side_effect=[None,task]
        self.assertEqual(await unit.claim(values),(task,False))
        session.scalar.side_effect=None;session.scalar.return_value=None
        with self.assertRaises(HTTPException):await unit.task(uuid4())
        await unit.finalize(task,Outcome('known_error',error_code='not_dispatched'))
        row=session.add.call_args.args[0]
        self.assertEqual(row.task_id,task.id);self.assertEqual(row.dispatch_claim_id,task.dispatch_claim_id)
        self.assertEqual(row.actor_user_id,store.actor);session.flush.assert_awaited_once();session.refresh.assert_awaited_once()
        self.assertIn('public.route_decisions',str(session.execute.call_args_list[0].args[0]))
        self.assertIn('usage_events',str(session.execute.call_args_list[1].args[0]))
        self.assertFalse(any(name in SQLUnit.__dict__ for name in ('update','delete','retry')))

    async def test_summary_pages_exact_progression_and_large_detail_exclusion(self):
        from jous_api.task_service import SQLUnit,dto
        from unittest.mock import MagicMock
        from sqlalchemy.dialects.postgresql import dialect
        now=datetime.now(timezone.utc);project=SimpleNamespace(id=uuid4(),organization_id=uuid4())
        rows=[SimpleNamespace(id=uuid4(),project_id=project.id,created_at=now+timedelta(seconds=i),dispatch_deadline_at=now+timedelta(seconds=40),prompt='p'*8192,logical_model_id='m',supplier_id='s',supplier_native_model_id='n') for i in range(5)]
        outcome=SimpleNamespace(id=uuid4(),status='succeeded',response_text='x'*65536,reported_model_id=None,reported_provider_id=None,finish_reason=None,usage=None,usage_status='unavailable',error_code=None,recorded_at=now)
        session=SimpleNamespace(scalars=AsyncMock(),scalar=AsyncMock(return_value=outcome))
        unit=SQLUnit(session,project,uuid4());seen=[]
        for offset in (0,2,4):
            session.scalars.return_value=SimpleNamespace(all=lambda:rows[offset:offset+3])
            if offset:unit.task=AsyncMock(return_value=rows[offset-1])
            page=await unit.page(2,rows[offset-1].id if offset else None)
            seen.extend(t['id'] for t in page['tasks'])
            self.assertEqual(page['next_cursor'],str(rows[offset+1].id) if offset<4 else None)
            self.assertTrue(all(set(t)=={'id','project_id','prompt_preview','status','created_at'} for t in page['tasks']))
            self.assertLess(len(str(page)),2000)
            sql=str(session.scalars.call_args.args[0].compile(dialect=dialect()))
            self.assertIn('ORDER BY public.tasks.created_at, public.tasks.id',sql)
            if offset:self.assertIn('(public.tasks.created_at, public.tasks.id) >',sql)
        self.assertEqual(seen,[str(r.id) for r in rows]);self.assertEqual(len(dto(rows[0],outcome)['execution']['response_text']),65536)

    async def test_store_transaction_exit_precedes_next_unit(self):
        from unittest.mock import patch
        from jous_api.task_service import SQLTaskStore
        events=[];session=object();project=SimpleNamespace(id=uuid4())
        @asynccontextmanager
        async def transaction():
            events.append('begin');yield session;events.append('commit-release')
        access=SimpleNamespace(resolve=AsyncMock(return_value=SimpleNamespace(user_id=uuid4())))
        with patch('jous_api.task_service.AccessService',return_value=access),patch('jous_api.task_service.authorize_project',AsyncMock(return_value=project)):
            store=SQLTaskStore(SimpleNamespace(scoped_transaction=transaction))
            for _ in range(2):
                async with store.unit('principal',project.id,execute=True):events.append('work')
        self.assertEqual(events,['begin','work','commit-release']*2)

    async def test_task_deadlines_do_not_change_foundation_auth_budget(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        bridge=(root/'apps/web/src/lib/task-api.ts').read_text()
        self.assertIn('},45000)',bridge)
        service=(root/'services/api/src/jous_api/execution_service.py').read_text()
        self.assertIn('asyncio.timeout(40)',service);self.assertIn('min(20,remaining-5)',service)
        import subprocess
        for path in ('apps/web/src/lib/security.ts','apps/web/src/lib/supabase/server.ts','apps/web/src/lib/supabase/session.ts'):
            self.assertEqual((root/path).read_text(),subprocess.check_output(['git','show','HEAD:'+path],cwd=root).decode().replace('\r\n','\n'))

    async def test_monotonic_budget_cannot_increase_after_wall_clock_rollback(self):
        now=datetime.now(timezone.utc);wall=[now];mono=[0.0]
        budget=OperationBudget(lambda:wall[0],lambda:mono[0])
        self.assertEqual(budget.remaining(lambda:wall[0],lambda:mono[0]),40)
        wall[0]-=timedelta(seconds=100);mono[0]=10
        self.assertEqual(budget.remaining(lambda:wall[0],lambda:mono[0]),30)
        wall[0]=now+timedelta(seconds=38);mono[0]=11
        self.assertEqual(budget.remaining(lambda:wall[0],lambda:mono[0]),2)
        wall[0]=now;mono[0]=12
        self.assertEqual(budget.remaining(lambda:wall[0],lambda:mono[0]),2)
