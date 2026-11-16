"""Offline product-service tests. No database or external authentication calls."""
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from jous_api.access import AccessService
from jous_api.identity import AccessDenied, OrganizationScope, RequestIdentity, ProjectScope
from jous_api.models import Project
from jous_api.product_api import CreateProject
from jous_api.projects import ProjectService


class ProjectServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.identity = RequestIdentity(uuid4())
        self.scope = OrganizationScope(self.identity.user_id, uuid4())
        self.session = AsyncMock()
        self.session.add = Mock()
        self.session.scalars.return_value = SimpleNamespace(all=lambda: [self.scope.organization_id])
        self.session.scalar.return_value = "member"
        self.access = AsyncMock(spec=AccessService)
        self.access.session = self.session
        self.access.organization.return_value = self.scope
        self.access.organization_query = AccessService.organization_query
        self.service = ProjectService(self.access)

    async def test_zero_and_multiple_memberships_never_choose_first(self):
        for ids in ([], [uuid4(), uuid4()]):
            self.session.scalars.return_value = SimpleNamespace(all=lambda: ids)
            with self.assertRaises(AccessDenied):
                await self.service.organization(self.identity)
        self.access.organization.assert_not_awaited()

    async def test_membership_query_is_own_active_recognized_and_bounded(self):
        self.assertEqual(await self.service.organization(self.identity), self.scope)
        query = self.session.scalars.call_args.args[0]
        sql, params = str(query), query.compile().params
        self.assertIn("organization_memberships.user_id =", sql)
        self.assertIn("organization_memberships.status =", sql)
        self.assertIn("organization_memberships.role IN", sql)
        self.assertIn(self.identity.user_id, params.values())
        self.assertIn("active", params.values())
        self.assertIn(2, params.values())
        self.access.active_user.assert_awaited_once_with(self.identity)

    async def test_inactive_user_and_revoked_organization_deny(self):
        self.access.active_user.side_effect = AccessDenied(401)
        with self.assertRaises(AccessDenied): await self.service.organization(self.identity)
        self.access.active_user.side_effect = None
        self.access.organization.side_effect = AccessDenied()
        with self.assertRaises(AccessDenied): await self.service.organization(self.identity)

    async def test_create_assigns_organization_and_transaction_ownership(self):
        value = await self.service.create(self.identity, CreateProject(name="  My First Project  "))
        self.assertEqual(value.name, "My First Project")
        self.assertEqual(value.organization_id, self.scope.organization_id)
        self.assertIsNotNone(value.id)
        self.session.add.assert_called_once_with(value)
        self.session.flush.assert_awaited_once()
        self.session.refresh.assert_awaited_once_with(value)
        self.session.commit.assert_not_awaited()

    async def test_create_checks_persisted_permission(self):
        self.session.scalar.return_value = "admin"
        with self.assertRaises(AccessDenied):
            await self.service.create(self.identity, CreateProject(name="Project"))
        self.session.add.assert_not_called()

    async def test_list_scopes_query_and_paginates(self):
        rows = [SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())]
        self.session.scalars.side_effect = [SimpleNamespace(all=lambda: [self.scope.organization_id]),
                                           SimpleNamespace(all=lambda: rows)]
        after = uuid4()
        result = await self.service.list(self.identity, 1, after)
        self.assertEqual(result, {"projects": rows[:1], "next_cursor": rows[0].id})
        query = self.session.scalars.call_args.args[0]
        self.assertIn(self.scope.organization_id, query.compile().params.values())
        self.assertIn(after, query.compile().params.values())
        self.assertIn("projects.status =", str(query))

    async def test_read_checks_scope_and_rechecks_project_permission(self):
        project_id = uuid4()
        self.access.project.return_value = ProjectScope(self.identity.user_id, self.scope.organization_id, project_id)
        project = Project(id=project_id, organization_id=self.scope.organization_id, name="Project")
        self.session.scalar.side_effect = ["member", project]
        self.assertIs(await self.service.read(self.identity, project_id), project)
        self.assertEqual(self.access.project.await_count, 2)
        self.assertIn(self.scope.organization_id, self.session.scalar.call_args.args[0].compile().params.values())

    async def test_cross_organization_and_unknown_project_same_denial(self):
        self.access.project.side_effect = AccessDenied()
        for project_id in (uuid4(), uuid4()):
            with self.assertRaises(AccessDenied) as error:
                await self.service.read(self.identity, project_id)
            self.assertEqual(error.exception.status_code, 404)

    def test_input_normalization_and_limits(self):
        self.assertEqual(CreateProject(name=" My First Project ").name, "My First Project")
        for data in ({"name": " "}, {"name": "x\n"}, {"name": "x" * 256}, {"name": 3},
                     {"name": "OK", "description": "x" * 2001}, {"name": "OK", "organization_id": str(uuid4())},
                     {"name": "OK", "status": "active"}):
            with self.subTest(data_type=list(data)), self.assertRaises(ValueError): CreateProject(**data)
