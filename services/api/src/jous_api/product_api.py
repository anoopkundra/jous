"""Four bounded product endpoints; no onboarding or tenant selectors."""
from datetime import datetime
import unicodedata
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .dependencies import get_access_service, get_request_identity
from .projects import ProjectService

router = APIRouter(prefix="/api")


class CreateProject(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        if not isinstance(value, str):
            raise ValueError("Project name required")
        if any(unicodedata.category(c).startswith("C") for c in value):
            raise ValueError("Project name contains control characters")
        value = value.strip()
        if not value:
            raise ValueError("Project name required")
        return value

    @field_validator("description")
    @classmethod
    def plain_description(cls, value):
        if value is not None and any(unicodedata.category(c).startswith("C")
                                     and c not in "\n\r\t" for c in value):
            raise ValueError("Invalid description")
        return value


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectPage(BaseModel):
    projects: list[ProjectResponse]
    next_cursor: UUID | None


class OrganizationResponse(BaseModel):
    id: UUID
    name: str


class MeResponse(BaseModel):
    user_id: UUID
    organization: OrganizationResponse


async def bounded_json(request: Request):
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(415, "JSON required")
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 16384:
            raise HTTPException(413, "Request too large")
        raw.extend(chunk)
    try:
        return CreateProject.model_validate_json(bytes(raw))
    except ValueError:
        # No Pydantic input echo: descriptions can contain private project text.
        raise HTTPException(422, "Invalid project input") from None


def service(access=Depends(get_access_service)):
    return ProjectService(access)


@router.get("/me", response_model=MeResponse)
async def me(identity=Depends(get_request_identity), projects=Depends(service)):
    return await projects.me(identity)


@router.get("/projects", response_model=ProjectPage)
async def list_projects(request: Request, limit: int = Query(50, ge=1, le=100),
                        after: UUID | None = None, identity=Depends(get_request_identity),
                        projects=Depends(service)):
    if set(request.query_params) - {"limit", "after"}:
        raise HTTPException(422, "Invalid query")
    return await projects.list(identity, limit, after)


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(request: Request, identity=Depends(get_request_identity),
                         projects=Depends(service)):
    if request.query_params:
        raise HTTPException(422, "Invalid query")
    return await projects.create(identity, await bounded_json(request))


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def read_project(project_id: UUID, request: Request, identity=Depends(get_request_identity),
                       projects=Depends(service)):
    if request.query_params:
        raise HTTPException(422, "Invalid query")
    return await projects.read(identity, project_id)
