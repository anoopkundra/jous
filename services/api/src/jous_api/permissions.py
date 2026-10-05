"""Central action policy. Roles are read only from active internal memberships."""

from enum import StrEnum
from types import MappingProxyType

from .identity import AccessDenied, OrganizationScope, ProjectScope, RequestIdentity
from .models import OrganizationMembership


class Action(StrEnum):
    READ_ORGANIZATION = "organization.read"
    UPDATE_ORGANIZATION_NAME = "organization.update_name"
    LIST_PROJECTS = "project.list"
    CREATE_PROJECT = "project.create"
    READ_PROJECT = "project.read"
    UPDATE_PROJECT = "project.update"
    ARCHIVE_PROJECT = "project.archive"
    READ_OWN_MEMBERSHIP = "membership.read_own"


MEMBER_ACTIONS = frozenset({Action.READ_ORGANIZATION, Action.LIST_PROJECTS,
    Action.CREATE_PROJECT, Action.READ_PROJECT, Action.UPDATE_PROJECT, Action.READ_OWN_MEMBERSHIP})
ROLE_ACTIONS = MappingProxyType({"member": MEMBER_ACTIONS, "owner": MEMBER_ACTIONS | {
    Action.UPDATE_ORGANIZATION_NAME, Action.ARCHIVE_PROJECT}})
KNOWN_ROLES = tuple(ROLE_ACTIONS)
PROJECT_ACTIONS = frozenset({Action.READ_PROJECT, Action.UPDATE_PROJECT, Action.ARCHIVE_PROJECT})


def permits(role: str, action: str) -> bool:
    return isinstance(role, str) and isinstance(action, str) and action in ROLE_ACTIONS.get(role, ())


class PermissionService:
    def __init__(self, access):
        self.access = access

    async def authorize(self, scope: OrganizationScope | ProjectScope, action: str):
        if (not isinstance(action, str) or action not in set(Action)
                or (action in PROJECT_ACTIONS and not isinstance(scope, ProjectScope))):
            raise AccessDenied()
        # Revalidate the exact active relationship; immutable scopes are not capabilities.
        identity = RequestIdentity(scope.user_id)
        organization = await self.access.organization(identity, scope.organization_id)
        if isinstance(scope, ProjectScope):
            await self.access.project(organization, scope.project_id)
        statement = self.access.organization_query(identity, scope.organization_id).with_only_columns(
            OrganizationMembership.role)
        role = await self.access.session.scalar(statement)
        if not permits(role, action):
            raise AccessDenied()
        return scope
