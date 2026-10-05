"""Non-public FastAPI identity, scope and central permission dependencies."""

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .access import AccessService
from .identity import AccessDenied, OrganizationScope, ProjectScope, RequestIdentity, VerifiedPrincipal
from .permissions import PermissionService


async def get_verified_principal(request: Request) -> VerifiedPrincipal:
    # Headers convey only an untrusted credential, never a trusted User/tenant/role.
    values = request.headers.getlist("authorization")
    if len(values) != 1:
        raise AccessDenied(401)
    value = values[0]
    if not value.isascii() or len(value) > 8199:
        raise AccessDenied(401)
    parts = value.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1] or any(c.isspace() for c in parts[1]):
        raise AccessDenied(401)
    return await request.app.state.credential_verifier.verify(parts[1])


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.transaction() as session:
        yield session


async def get_access_service(session: AsyncSession = Depends(get_session)) -> AccessService:
    return AccessService(session)


async def get_permission_service(service: AccessService = Depends(get_access_service)) -> PermissionService:
    return PermissionService(service)


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
