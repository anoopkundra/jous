"""Read-only identity and tenant access queries; no CRUD or administration."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .identity import AccessDenied, OrganizationScope, ProjectScope, RequestIdentity, VerifiedPrincipal
from .models import Organization, OrganizationMembership, Project, User


class AccessService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve(self, principal: VerifiedPrincipal) -> RequestIdentity:
        user_id = await self.session.scalar(select(User.id).where(
            User.auth_issuer == principal.issuer, User.auth_subject == principal.subject,
            User.status == "active"))
        if user_id is None:
            raise AccessDenied(401)
        return RequestIdentity(user_id)

    async def active_user(self, identity: RequestIdentity) -> RequestIdentity:
        user_id = await self.session.scalar(select(User.id).where(
            User.id == identity.user_id, User.status == "active"))
        if user_id is None:
            raise AccessDenied(401)
        return RequestIdentity(user_id)

    @staticmethod
    def organization_query(identity: RequestIdentity, organization_id: UUID):
        # Only the known base role is supported. No owner/admin privileges exist.
        return select(Organization.id).join(
            OrganizationMembership, OrganizationMembership.organization_id == Organization.id
        ).join(User, User.id == OrganizationMembership.user_id).where(
            User.id == identity.user_id, User.status == "active",
            Organization.id == organization_id, Organization.status == "active",
            OrganizationMembership.status == "active", OrganizationMembership.role == "member")

    async def organization(self, identity: RequestIdentity, organization_id: UUID) -> OrganizationScope:
        result = await self.session.scalar(self.organization_query(identity, organization_id))
        if result is None:
            raise AccessDenied()
        return OrganizationScope(identity.user_id, result)

    async def project(self, organization: OrganizationScope, project_id: UUID) -> ProjectScope:
        # Recheck the full access relationship, even if the supplied scope is stale.
        # Project ID alone never selects a row; Organization ownership is mandatory.
        statement = self.organization_query(
            RequestIdentity(organization.user_id), organization.organization_id
        ).with_only_columns(Project.id).join(
            Project, Project.organization_id == Organization.id
        ).where(Project.id == project_id, Project.organization_id == organization.organization_id,
                Project.status == "active")
        result = await self.session.scalar(statement)
        if result is None:
            raise AccessDenied()
        return ProjectScope(organization.user_id, organization.organization_id, result)
