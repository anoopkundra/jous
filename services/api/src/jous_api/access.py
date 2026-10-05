"""Read-only identity and tenant access queries; no CRUD or administration."""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .identity import AccessDenied, OrganizationScope, ProjectScope, RequestIdentity, VerifiedPrincipal
from .models import Organization, OrganizationMembership, Project, User
from .permissions import KNOWN_ROLES


class AccessService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.context = session.info.get("jous_context")
        if self.context is None:
            raise AccessDenied()

    async def resolve(self, principal: VerifiedPrincipal) -> RequestIdentity:
        self.context.require_ready()
        if self.context.user_id is not None:
            raise AccessDenied(401)
        user_id = await self.session.scalar(text(
            "SELECT jous_security.resolve_user(:issuer, :subject)"),
            {"issuer": principal.issuer, "subject": principal.subject})
        if user_id is None:
            raise AccessDenied(401)
        await self.context.bind_user(user_id)
        return RequestIdentity(user_id)

    async def active_user(self, identity: RequestIdentity) -> RequestIdentity:
        self.context.require_user(identity.user_id)
        user_id = await self.session.scalar(select(User.id).where(
            User.id == identity.user_id, User.status == "active"))
        if user_id is None:
            raise AccessDenied(401)
        return RequestIdentity(user_id)

    @staticmethod
    def organization_query(identity: RequestIdentity, organization_id: UUID):
        # Known active memberships grant base access, not action-specific privileges.
        return select(Organization.id).join(
            OrganizationMembership, OrganizationMembership.organization_id == Organization.id
        ).join(User, User.id == OrganizationMembership.user_id).where(
            User.id == identity.user_id, User.status == "active",
            Organization.id == organization_id, Organization.status == "active",
            OrganizationMembership.status == "active", OrganizationMembership.role.in_(KNOWN_ROLES))

    async def organization(self, identity: RequestIdentity, organization_id: UUID) -> OrganizationScope:
        self.context.require_user(identity.user_id)
        if self.context.organization_id is None:
            # Membership RLS checks active Organization through the narrow status helper.
            eligible = await self.session.scalar(select(OrganizationMembership.organization_id).where(
                OrganizationMembership.user_id == identity.user_id,
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.status == "active", OrganizationMembership.role.in_(KNOWN_ROLES)))
            if eligible != organization_id:
                raise AccessDenied()
            await self.context.bind_organization(organization_id)
        self.context.require_organization(identity.user_id, organization_id)
        result = await self.session.scalar(self.organization_query(identity, organization_id))
        if result is None:
            raise AccessDenied()
        return OrganizationScope(identity.user_id, result)

    async def project(self, organization: OrganizationScope, project_id: UUID) -> ProjectScope:
        self.context.require_organization(organization.user_id, organization.organization_id)
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
