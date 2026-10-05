"""Action matrix and persistence-backed revalidation; no mutation workflows."""

import unittest
from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from jous_api.access import AccessService
from jous_api.identity import AccessDenied, OrganizationScope, ProjectScope
from jous_api.permissions import Action, PermissionService, permits


class PermissionTests(unittest.IsolatedAsyncioTestCase):
    def test_complete_role_action_matrix_and_deferred_denial(self):
        member = {Action.READ_ORGANIZATION, Action.LIST_PROJECTS, Action.READ_PROJECT,
                  Action.CREATE_PROJECT, Action.UPDATE_PROJECT, Action.READ_OWN_MEMBERSHIP}
        for action in Action:
            self.assertEqual(permits("member", action), action in member)
            self.assertTrue(permits("owner", action))
            for role in ("admin", "unknown", "", None):
                self.assertFalse(permits(role, action))
        for action in ("membership.invite", "membership.add", "membership.remove", "membership.change_role",
                       "organization.delete", "project.delete", "billing.administer", "ownership.transfer",
                       "ownership.recover", "ledger.write", "unknown"):
            for role in ("member", "owner"):
                self.assertFalse(permits(role, action))

    async def test_persistence_role_and_scoped_project_revalidation(self):
        user, organization, project = uuid4(), uuid4(), uuid4()
        scope = ProjectScope(user, organization, project)
        session = AsyncMock()
        session.scalar.side_effect = [organization, project, "owner"]
        service = PermissionService(AccessService(session))
        self.assertEqual(await service.authorize(scope, Action.ARCHIVE_PROJECT), scope)
        statement = session.scalar.call_args.args[0].compile(dialect=postgresql.dialect())
        self.assertIn("organization_memberships.role", str(statement))
        self.assertIn(user, statement.params.values())
        self.assertIn(organization, statement.params.values())
        for results in ([None], [organization, None], [organization, project, "member"],
                        [organization, project, "admin"], [organization, project, None]):
            session.scalar.side_effect = results
            with self.assertRaises(AccessDenied):
                await service.authorize(scope, Action.ARCHIVE_PROJECT)

    async def test_project_actions_require_project_scope_unknown_action_denies_without_query(self):
        access = AsyncMock()
        service = PermissionService(access)
        scope = OrganizationScope(uuid4(), uuid4())
        for action in (Action.READ_PROJECT, Action.UPDATE_PROJECT, Action.ARCHIVE_PROJECT, "billing.administer"):
            with self.assertRaises(AccessDenied):
                await service.authorize(scope, action)
        access.organization.assert_not_called()

    async def test_own_membership_is_bound_to_scope_user(self):
        session = AsyncMock()
        user, organization = uuid4(), uuid4()
        session.scalar.side_effect = [organization, "member"]
        await PermissionService(AccessService(session)).authorize(
            OrganizationScope(user, organization), Action.READ_OWN_MEMBERSHIP)
        sql = session.scalar.call_args.args[0].compile(dialect=postgresql.dialect())
        self.assertIn(user, sql.params.values())

    async def test_inactive_or_cross_tenant_relationship_denies_every_action(self):
        session = AsyncMock()
        session.scalar.return_value = None
        scope = ProjectScope(uuid4(), uuid4(), uuid4())
        service = PermissionService(AccessService(session))
        for action in Action:
            with self.assertRaises(AccessDenied):
                await service.authorize(scope, action)
        statement = session.scalar.call_args.args[0].compile(dialect=postgresql.dialect())
        for predicate in ("users.id =", "users.status =", "organizations.id =",
                          "organizations.status =", "organization_memberships.status ="):
            self.assertIn(predicate, str(statement))
        self.assertIn("active", statement.params.values())
