"""WebSocket route — subscribe to a run's event stream."""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.event_bus import EventBus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["streaming"])


@router.websocket("/ws/runs/{run_id}")
async def stream_run(websocket: WebSocket, run_id: str) -> None:
    """Forward ordered WSEvents for ``run_id`` until ``done`` or client disconnect."""
    bus: EventBus = websocket.app.state.event_bus
    await websocket.accept()
    try:
        async for event in bus.subscribe(run_id):
            await websocket.send_json(event)
            if event["type"] == "done":
                break
    except WebSocketDisconnect:
        logger.debug("client disconnected run_id=%s", run_id)
    except Exception:
        logger.exception("websocket stream error run_id=%s", run_id)
        await websocket.close(code=1011)
    else:
        await websocket.close()
