"""Non-public FastAPI access dependencies; the default trusted-principal seam rejects."""

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .access import AccessService
from .identity import AccessDenied, OrganizationScope, ProjectScope, RequestIdentity, VerifiedPrincipal


async def get_verified_principal() -> VerifiedPrincipal:
    # A future trusted adapter replaces this dependency after separate approval.
    # Never read an identity UUID, role or tenant assertion from request headers.
    raise AccessDenied(401)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.transaction() as session:
        yield session


async def get_access_service(session: AsyncSession = Depends(get_session)) -> AccessService:
    return AccessService(session)


async def get_request_identity(
    principal: VerifiedPrincipal = Depends(get_verified_principal),
    service: AccessService = Depends(get_access_service),
) -> RequestIdentity:
    return await service.resolve(principal)


async def get_organization_scope(
    organization_id: UUID,
    identity: RequestIdentity = Depends(get_request_identity),
    service: AccessService = Depends(get_access_service),
) -> OrganizationScope:
    return await service.organization(identity, organization_id)


async def get_project_scope(
    project_id: UUID,
    organization: OrganizationScope = Depends(get_organization_scope),
    service: AccessService = Depends(get_access_service),
) -> ProjectScope:
    return await service.project(organization, project_id)
