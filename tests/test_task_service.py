import unittest
from unittest.mock import AsyncMock,patch
from types import SimpleNamespace
from uuid import uuid4
from jous_api.task_permissions import authorize_project
from jous_api.identity import AccessDenied,RequestIdentity
from jous_api.permissions import permits
from jous_api.task_context import validate_claim
from test_execution_service import Store,data
from jous_api.execution_service import ExecutionService
from jous_supply.contracts import Outcome


class PermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_only_additive_permission(self):
        access=SimpleNamespace(session=SimpleNamespace(scalar=AsyncMock()))
        project=SimpleNamespace(id=uuid4(),organization_id=uuid4())
        identity=RequestIdentity(uuid4())
        with patch('jous_api.task_permissions.ProjectService') as cls:
            cls.return_value.read=AsyncMock(return_value=project)
            for role in ('member','admin',None,'owner'):
                access.session.scalar.return_value=role
                if role=='owner':self.assertIs(await authorize_project(access,identity,project.id,execute=True),project)
                else:
                    with self.assertRaises(AccessDenied):await authorize_project(access,identity,project.id,execute=True)
            await authorize_project(access,identity,project.id)
        self.assertFalse(permits('owner','task.execute'));self.assertTrue(permits('member','project.read'))

    async def test_nested_claim_evidence_tampering(self):
        store=Store();service=ExecutionService(store,SimpleNamespace(execute=AsyncMock(return_value=Outcome('refused'))),admission=lambda route:None)
        await service.submit('mapped',store.project.id,data())
        from copy import deepcopy
        original=vars(next(iter(store.rows.values())))
        for key in ('request_parameters','token_bound_evidence','context_package'):
            values=deepcopy(original);values[key]['extra']='not approved'
            with self.assertRaises(ValueError):validate_claim(values)
        values=deepcopy(original);values['actor_user_id']='spoof'
        with self.assertRaises(ValueError):validate_claim(values)
