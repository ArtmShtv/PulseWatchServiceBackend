import asyncio
from contextlib import suppress

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.services.auth_services import ws_authenticate_user
from app.ws.events import EventType, build_event
from app.ws.manager import manager

HEARTBEAT_SECONDS = 25

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    user_id = await ws_authenticate_user(token)
    if user_id is None:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws.accept()
    await manager.connect(user_id, ws)
    await ws.send_text(build_event(EventType.CONNECTED))

    heartbeat = asyncio.create_task(_heartbeat(ws))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat.cancel()
        manager.disconnect(user_id, ws)


async def _heartbeat(ws: WebSocket) -> None:
    with suppress(Exception):
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await ws.send_text(build_event(EventType.PING))