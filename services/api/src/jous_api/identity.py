"""Trusted, provider-neutral identity values. No credential verification is implemented."""

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class VerifiedPrincipal:
    issuer: str = field(repr=False)
    subject: str = field(repr=False)

    def __post_init__(self):
        for value in (self.issuer, self.subject):
            if not isinstance(value, str) or not value.strip() or len(value) > 255:
                raise ValueError("Invalid verified principal")


@dataclass(frozen=True)
class RequestIdentity:
    user_id: UUID


class IdentityResolver(Protocol):
    async def resolve(self, principal: VerifiedPrincipal) -> RequestIdentity: ...


@dataclass(frozen=True)
class OrganizationScope:
    user_id: UUID
    organization_id: UUID


@dataclass(frozen=True)
class ProjectScope:
    user_id: UUID
    organization_id: UUID
    project_id: UUID


class AccessDenied(Exception):
    """Bounded failure without object identifiers, credentials or existence details."""

    def __init__(self, status_code: int = 404):
        super().__init__("Access unavailable")
        self.status_code = status_code
