"""Additive product permission; frozen Action/ROLE_ACTIONS remain unchanged."""
from sqlalchemy import select
from .identity import AccessDenied
from .models import OrganizationMembership
from .projects import ProjectService

TASK_EXECUTE = 'task.execute'


async def authorize_project(access, identity, project_id, *, execute=False):
    project = await ProjectService(access).read(identity, project_id)
    if execute:
        role = await access.session.scalar(select(OrganizationMembership.role).where(
            OrganizationMembership.organization_id == project.organization_id,
            OrganizationMembership.user_id == identity.user_id,
            OrganizationMembership.status == 'active'))
        if role != 'owner': raise AccessDenied(403)
    return project
