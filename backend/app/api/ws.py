"""WebSocket feed for the sales dashboard: a snapshot on connect, then live updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from ..realtime import hub
from ..tracking import list_leads, list_visitors

router = APIRouter(tags=["dashboard"])


@router.websocket("/ws/dashboard")
async def dashboard_feed(ws: WebSocket) -> None:
    await ws.accept()
    try:
        visitors = await run_in_threadpool(list_visitors, 50)
        leads = await run_in_threadpool(list_leads, 20)
        await ws.send_json(
            {
                "type": "snapshot",
                "visitors": [visitor.model_dump(mode="json") for visitor in visitors],
                "leads": [lead.model_dump(mode="json") for lead in leads],
            }
        )
        hub.add(ws)
        while True:
            await ws.receive_text()  # the dashboard never sends anything; this waits until it disconnects
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(ws)
