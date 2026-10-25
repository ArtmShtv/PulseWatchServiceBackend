from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidMonitorDataError,
    MonitorAlreadyExistsError,
    MonitorNotFoundError,
)
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.monitor_schemas import (
    MonitorCreateSchema,
    MonitorSchema,
    MonitorUpdateSchema,
)
from app.services.auth_services import get_current_user_from_jwt
from app.services.monitor_services import (
    create_monitor,
    delete_monitor,
    get_user_monitor,
    list_user_monitors,
    update_monitor,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user_from_jwt)]

monitor_router = APIRouter(
    prefix="/monitors",
    tags=["Monitor"],
)

_NOT_FOUND = {404: {"description": "Monitor not found"}}
_CONFLICT = {409: {"description": "Monitor with this URL and method already exists"}}


def _not_found(e: MonitorNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


def _conflict(e: MonitorAlreadyExistsError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


def _invalid(e: InvalidMonitorDataError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))


@monitor_router.get("/", response_model=list[MonitorSchema])
async def list_monitors(session: SessionDep, current_user: CurrentUser):
    return await list_user_monitors(session, current_user)


@monitor_router.post(
    "/",
    response_model=MonitorSchema,
    status_code=status.HTTP_201_CREATED,
    responses=_CONFLICT,
)
async def create_user_monitor(
    monitor_data: MonitorCreateSchema,
    session: SessionDep,
    current_user: CurrentUser,
):
    try:
        return await create_monitor(session, monitor_data, current_user)
    except MonitorAlreadyExistsError as e:
        raise _conflict(e) from None


@monitor_router.get("/{monitor_id}", response_model=MonitorSchema, responses=_NOT_FOUND)
async def get_monitor(monitor_id: int, session: SessionDep, current_user: CurrentUser):
    try:
        return await get_user_monitor(session, monitor_id, current_user)
    except MonitorNotFoundError as e:
        raise _not_found(e) from None


@monitor_router.patch(
    "/{monitor_id}",
    response_model=MonitorSchema,
    responses=_NOT_FOUND | _CONFLICT,
)
async def update_user_monitor(
    monitor_id: int,
    monitor_data: MonitorUpdateSchema,
    session: SessionDep,
    current_user: CurrentUser,
):
    try:
        return await update_monitor(session, monitor_id, monitor_data, current_user)
    except MonitorNotFoundError as e:
        raise _not_found(e) from None
    except MonitorAlreadyExistsError as e:
        raise _conflict(e) from None
    except InvalidMonitorDataError as e:
        raise _invalid(e) from None


@monitor_router.delete(
    "/{monitor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=_NOT_FOUND,
)
async def delete_user_monitor(
    monitor_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    try:
        await delete_monitor(session, monitor_id, current_user)
    except MonitorNotFoundError as e:
        raise _not_found(e) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
