from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.monitor_schemas import (
    MonitorSchema, 
    MonitorCreateSchema,
    MonitorUpdateSchema
)
from app.services.user_services import get_current_user_from_jwt
from app.db.models.monitor import Monitor
from app.services.monitor_services import (
    create_monitor, 
    update_monitor,
    delete_monitor
)

monitor_router = APIRouter(
    prefix="/monitors",
    tags=["Monitor"]
)


@monitor_router.get("/",response_model=list[MonitorSchema])
async def list_of_user_monitors(
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user_from_jwt),
):
    result = await session.execute(
        select(Monitor).
        where(Monitor.user_id == current_user.id)
    )

    user_monitors = result.scalars().all()
    return user_monitors


@monitor_router.post("/new", response_model=MonitorSchema)
async def create_monitor_for_user(
    monitor_data: MonitorCreateSchema,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user_from_jwt)
): 
    try:
        monitor = await create_monitor(
            session, 
            monitor_data, 
            current_user
        )
    except ValueError as e:
        raise HTTPException(
            status_code=409,
            detail=str(e)
        )

    return monitor


@monitor_router.patch("/{monitor_id}/edit", response_model=MonitorSchema)
async def update_user_monitor(
    monitor_id: int,
    monitor_data: MonitorUpdateSchema,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user_from_jwt)
):
    if not monitor_data:
        raise ValueError("Must provide data to update")
    
    try:
        monitor = await update_monitor(
            session,
            monitor_id,
            monitor_data,
            current_user
        )
    except ValueError as e:
        raise HTTPException(
            status_code=409,
            detail=str(e)
        )

    return monitor


@monitor_router.delete("/{monitor_id}")
async def delete_user_monitor(
    monitor_id: int,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user_from_jwt)
):
    try:
        await delete_monitor(
            session,
            monitor_id,
            current_user
        )
    except ValueError as e:
        raise HTTPException(
            status_code=409,
            detail=str(e)
        )

    return {
        "message": "Monitor deleted",
        "status": status.HTTP_204_NO_CONTENT
    }