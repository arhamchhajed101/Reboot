from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.event_bus import event_bus

router = APIRouter()


@router.websocket("/runs/{run_id}/stream")
async def websocket_run_stream(websocket: WebSocket, run_id: str):
    await event_bus.connect(run_id, websocket)
    try:
        while True:
            # Keep connection alive; incoming messages from client can be ignored/acknowledged
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        await event_bus.disconnect(run_id, websocket)
    except Exception:
        await event_bus.disconnect(run_id, websocket)
