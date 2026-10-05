"""Explicit request-local context. Ordinary GUCs do not authenticate arbitrary SQL."""

from uuid import UUID
from sqlalchemy import text
from .identity import AccessDenied


class DatabaseContext:
    def __init__(self, session):
        self.session = session
        self.initialized = False
        self.user_id = None
        self.organization_id = None

    def require_ready(self):
        if not self.initialized or not self.session.in_transaction():
            raise AccessDenied()

    async def initialize(self):
        if self.initialized or self.session.in_nested_transaction():
            raise AccessDenied()
        await self.session.execute(text(
            "SELECT pg_catalog.set_config('jous.user_id', '', true), "
            "pg_catalog.set_config('jous.organization_id', '', true)"))
        self.initialized = True

    async def bind_user(self, user_id):
        self.require_ready()
        if not isinstance(user_id, UUID) or self.organization_id is not None:
            raise AccessDenied()
        if self.user_id is not None:
            if self.user_id != user_id:
                raise AccessDenied()
            return
        if self.session.in_nested_transaction():
            raise AccessDenied()
        await self.session.execute(text("SELECT pg_catalog.set_config('jous.user_id', :value, true)"),
                                   {"value": str(user_id)})
        self.user_id = user_id

    async def bind_organization(self, organization_id):
        self.require_user(self.user_id)
        if not isinstance(organization_id, UUID):
            raise AccessDenied()
        if self.organization_id is not None:
            if self.organization_id != organization_id:
                raise AccessDenied()
            return
        if self.session.in_nested_transaction():
            raise AccessDenied()
        await self.session.execute(text("SELECT pg_catalog.set_config('jous.organization_id', :value, true)"),
                                   {"value": str(organization_id)})
        self.organization_id = organization_id

    def require_user(self, user_id):
        self.require_ready()
        if not isinstance(user_id, UUID) or self.user_id != user_id:
            raise AccessDenied()

    def require_organization(self, user_id, organization_id):
        self.require_user(user_id)
        if self.organization_id != organization_id:
            raise AccessDenied()

    def clear(self):
        self.initialized = False
        self.user_id = self.organization_id = None
