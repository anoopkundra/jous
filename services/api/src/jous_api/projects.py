"""V1.1 project operations over the unchanged identity/RLS foundation."""
from uuid import UUID, uuid4

from sqlalchemy import select

from .access import AccessService
from .identity import AccessDenied, RequestIdentity
from .models import Organization, OrganizationMembership, Project
from .permissions import Action, KNOWN_ROLES, PermissionService


class ProjectService:
    def __init__(self, access: AccessService):
        self.access = access
        self.session = access.session
        self.permissions = PermissionService(access)

    async def organization(self, identity: RequestIdentity):
        await self.access.active_user(identity)
        # Membership RLS already requires an active Organization. Limit two is
        # sufficient to distinguish exactly one from ambiguity; never choose first.
        rows = (await self.session.scalars(select(OrganizationMembership.organization_id).where(
            OrganizationMembership.user_id == identity.user_id,
            OrganizationMembership.status == "active",
            OrganizationMembership.role.in_(KNOWN_ROLES)).limit(2))).all()
        if len(rows) != 1:
            raise AccessDenied(403)
        return await self.access.organization(identity, rows[0])

    async def me(self, identity):
        scope = await self.organization(identity)
        await self.permissions.authorize(scope, Action.READ_ORGANIZATION)
        organization = await self.session.scalar(select(Organization).where(
            Organization.id == scope.organization_id, Organization.status == "active"))
        if organization is None:
            raise AccessDenied()
        return {"user_id": identity.user_id,
                "organization": {"id": organization.id, "name": organization.name}}

    async def list(self, identity, limit: int, after: UUID | None):
        scope = await self.organization(identity)
        await self.permissions.authorize(scope, Action.LIST_PROJECTS)
        statement = select(Project).where(Project.organization_id == scope.organization_id,
                                           Project.status == "active")
        if after is not None:
            statement = statement.where(Project.id > after)
        rows = (await self.session.scalars(statement.order_by(Project.id).limit(limit + 1))).all()
        page = rows[:limit]
        return {"projects": page, "next_cursor": page[-1].id if len(rows) > limit else None}

    async def create(self, identity, data):
        scope = await self.organization(identity)
        await self.permissions.authorize(scope, Action.CREATE_PROJECT)
        project = Project(id=uuid4(), organization_id=scope.organization_id,
                          name=data.name, description=data.description)
        self.session.add(project)
        await self.session.flush()
        # Existing request transaction owns commit/rollback. No nested commit.
        await self.session.refresh(project)
        return project

    async def read(self, identity, project_id):
        organization = await self.organization(identity)
        scope = await self.access.project(organization, project_id)
        await self.permissions.authorize(scope, Action.READ_PROJECT)
        project = await self.session.scalar(select(Project).where(
            Project.id == scope.project_id, Project.organization_id == scope.organization_id,
            Project.status == "active"))
        if project is None:
            raise AccessDenied()
        return project
