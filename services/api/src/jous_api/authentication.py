"""Provider-neutral credential verification contract; credentials never become identity."""

from typing import Protocol

from .identity import AccessDenied, VerifiedPrincipal


class CredentialVerifier(Protocol):
    async def verify(self, credential: str) -> VerifiedPrincipal: ...
    async def aclose(self) -> None: ...


class RejectingVerifier:
    async def verify(self, credential: str) -> VerifiedPrincipal:
        raise AccessDenied(401)

    async def aclose(self) -> None:
        pass
