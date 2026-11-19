"""Explicit task DTOs and short-transaction authenticated product endpoints."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator
from jous_supply.registry import snapshot
from .dependencies import get_verified_principal
from .execution_settings import BODY_BYTES

router = APIRouter(prefix='/api/projects/{project_id}/tasks')


class SubmitTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str
    task_context: str | None = None
    logical_model_id: str
    route_id: str
    client_request_id: UUID

    @field_validator('prompt','task_context','logical_model_id','route_id',mode='before')
    @classmethod
    def strings(cls,value,info):
        if value is None and info.field_name == 'task_context': return None
        if not isinstance(value,str) or '\x00' in value: raise ValueError('Invalid input')
        limit = 8192 if info.field_name == 'prompt' else 16384 if info.field_name == 'task_context' else 255
        if len(value.encode()) > limit or (info.field_name != 'task_context' and not value.strip()): raise ValueError('Invalid input')
        return value


def coordinator(request: Request): return request.app.state.task_execution


def no_query(request):
    if request.query_params: raise HTTPException(422,'Invalid query')


@router.get('/options')
async def options(project_id: UUID, request: Request, principal=Depends(get_verified_principal), service=Depends(coordinator)):
    no_query(request)
    async with service.store.unit(principal,project_id,execute=True):
        route = snapshot()
        return {'routes':[{k:route[k] for k in ('route_id','logical_model_id','supplier_id','supplier_native_model_id','real_execution_eligible','ineligibility_reason')}],
                'execution_available':False}


@router.post('')
async def submit(project_id: UUID, request: Request, principal=Depends(get_verified_principal), service=Depends(coordinator)):
    no_query(request)
    if request.headers.get('content-type','').split(';')[0].strip().lower() != 'application/json':
        raise HTTPException(415,'JSON required')
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw)+len(chunk)>BODY_BYTES: raise HTTPException(413,'Request too large')
        raw.extend(chunk)
    try: data = SubmitTask.model_validate_json(bytes(raw))
    except ValueError: raise HTTPException(422,'Invalid task input') from None
    try:
        result = await service.submit(principal,project_id,data)
        status = result.http_status
        location = f'/api/projects/{project_id}/tasks/{result["id"]}'
        return JSONResponse(dict(result),status_code=status,headers={'Location':location} if status in (201,202) else {})
    except ValueError: raise HTTPException(422,'Invalid task input') from None


@router.get('')
async def page(project_id: UUID,request: Request,limit: int=Query(20,ge=1,le=50),after: UUID|None=None,
               principal=Depends(get_verified_principal),service=Depends(coordinator)):
    if set(request.query_params)-{'limit','after'}: raise HTTPException(422,'Invalid query')
    return await service.page(principal,project_id,limit,after)


@router.get('/{task_id}')
async def read(project_id: UUID,task_id: UUID,request: Request,principal=Depends(get_verified_principal),service=Depends(coordinator)):
    no_query(request)
    return await service.read(principal,project_id,task_id)
