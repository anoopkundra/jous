from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4
import unittest
from unittest.mock import AsyncMock
from test_product_api import call
from jous_api.config import Settings
from jous_api.identity import AccessDenied,VerifiedPrincipal
from jous_api.product_app import create_product_app
from jous_api.task_api import SubmitTask
from jous_api.task_service import SubmissionResult


class TaskApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app=create_product_app(Settings(environment='test'));self.project=uuid4();self.base=f'/api/projects/{self.project}/tasks'
        async def verify(token):
            if token in ('invalid','expired'):raise AccessDenied(401)
            return VerifiedPrincipal('fixture',token)
        self.app.state.credential_verifier=SimpleNamespace(verify=verify)
        @asynccontextmanager
        async def unit(principal,project,*,execute=False):
            if principal.subject in ('unknown','inactive','zero','inactive-membership','multiple'):raise AccessDenied(403)
            yield None
        self.service=SimpleNamespace(store=SimpleNamespace(unit=unit),submit=AsyncMock(return_value=SubmissionResult({'id':str(uuid4())},201)),
            page=AsyncMock(return_value={'tasks':[],'next_cursor':None}),read=AsyncMock(return_value={'id':str(uuid4())}))
        self.app.state.task_execution=self.service
        self.body={'prompt':'Task','logical_model_id':'jous.text.general.v1','route_id':'hf-qwen3-32b-deepinfra-v1','client_request_id':str(uuid4())}
    async def test_authentication_and_unavailable_options(self):
        for token in (None,'invalid','expired'):
            self.assertEqual((await call(self.app,self.base+'/options',token=token))[0],401)
        for token in ('unknown','inactive','zero','inactive-membership','multiple'):
            self.assertEqual((await call(self.app,self.base+'/options',token=token))[0],403)
        status,value,_=await call(self.app,self.base+'/options')
        self.assertEqual(status,200);self.assertFalse(value['execution_available'])
        self.assertFalse(value['routes'][0]['real_execution_eligible'])
    async def test_bounded_body_unknown_fields_and_spoofing(self):
        for extra in ({'organization_id':str(uuid4())},{'actor_user_id':str(uuid4())},{'endpoint':'https://evil.invalid'},{'real_execution_eligible':True}):
            self.assertEqual((await call(self.app,self.base,'POST',body={**self.body,**extra}))[0],422)
        for value in ['', 'é'*4097]:
            self.assertEqual((await call(self.app,self.base,'POST',body={**self.body,'prompt':value}))[0],422)
        self.assertEqual((await call(self.app,self.base,'POST',body=b'x'*65537))[0],413)
        self.service.submit.assert_not_awaited()
    async def test_submission_read_page_and_pagination_bounds(self):
        self.assertEqual((await call(self.app,self.base,'POST',body=self.body))[0],201)
        principal,project,data=self.service.submit.call_args.args
        self.assertEqual(project,self.project);self.assertFalse(hasattr(data,'organization_id'))
        for query in ('limit=0','limit=51','organization_id=spoof','after=bad'):
            self.assertEqual((await call(self.app,self.base,query=query))[0],422)
        self.assertEqual((await call(self.app,self.base))[0],200)
        self.assertEqual((await call(self.app,self.base+'/'+str(uuid4())))[0],200)

    async def test_actual_coordinator_submission_and_recovery(self):
        from test_execution_service import Store
        from jous_api.execution_service import ExecutionService
        from jous_supply.contracts import Outcome
        store=Store();self.project=store.project.id;self.base=f'/api/projects/{self.project}/tasks'
        adapter=SimpleNamespace(execute=AsyncMock(return_value=Outcome('succeeded',response_text='Persisted')))
        # Real coordinator; only persistence/identity and supplier are fixtures.
        service=ExecutionService(store,adapter,admission=lambda route:None)
        self.app.state.task_execution=service
        self.app.state.credential_verifier=SimpleNamespace(verify=AsyncMock(return_value='mapped'))
        status,value,headers=await call(self.app,self.base,'POST',body=self.body)
        self.assertEqual(status,201);self.assertEqual(value['execution']['response_text'],'Persisted')
        self.assertEqual(headers[b'location'].decode(),self.base+'/'+value['id'])
        again,_,_=await call(self.app,self.base,'POST',body=self.body)
        self.assertEqual(again,200);adapter.execute.assert_awaited_once()
        # A durable claim recovered with no outcome is 200, never redispatched.
        store.outcomes.clear()
        status,value,_=await call(self.app,self.base,'POST',body=self.body)
        self.assertEqual(status,200);self.assertEqual(value['status'],'claimed');adapter.execute.assert_awaited_once()

    async def test_pending_submission_contract_and_options_owner_requirement(self):
        for status in (201,202,200):
            key=str(uuid4());self.service.submit.return_value=SubmissionResult({'id':key},status)
            actual,_,headers=await call(self.app,self.base,'POST',body=self.body)
            self.assertEqual(actual,status)
            self.assertEqual(headers.get(b'location'),(self.base+'/'+key).encode() if status in (201,202) else None)
        from test_execution_service import Store
        from jous_api.execution_service import ExecutionService
        store=Store();self.app.state.task_execution=ExecutionService(store,None)
        self.app.state.credential_verifier=SimpleNamespace(verify=AsyncMock(return_value='mapped'))
        self.assertEqual((await call(self.app,f'/api/projects/{store.project.id}/tasks/options'))[0],200)
        @asynccontextmanager
        async def denied(principal,project,*,execute=False):
            self.assertTrue(execute);raise AccessDenied(403);yield
        store.unit=denied
        self.assertEqual((await call(self.app,f'/api/projects/{store.project.id}/tasks/options'))[0],403)

    async def test_options_through_actual_sql_store_owner_member_and_revoked(self):
        from unittest.mock import patch
        from jous_api.task_service import SQLTaskStore
        from jous_api.execution_service import ExecutionService
        from jous_api.identity import RequestIdentity
        session=SimpleNamespace(scalar=AsyncMock(return_value='owner'))
        @asynccontextmanager
        async def transaction():yield session
        access=SimpleNamespace(resolve=AsyncMock(return_value=RequestIdentity(uuid4())),session=session)
        project=SimpleNamespace(id=self.project,organization_id=uuid4())
        self.app.state.task_execution=ExecutionService(SQLTaskStore(SimpleNamespace(scoped_transaction=transaction)),None)
        with patch('jous_api.task_service.AccessService',return_value=access),patch('jous_api.task_permissions.ProjectService') as cls:
            cls.return_value.read=AsyncMock(return_value=project)
            self.assertEqual((await call(self.app,self.base+'/options'))[0],200)
            session.scalar.return_value='member'
            self.assertEqual((await call(self.app,self.base+'/options'))[0],403)
            access.resolve.side_effect=AccessDenied(403)
            self.assertEqual((await call(self.app,self.base+'/options'))[0],403)
