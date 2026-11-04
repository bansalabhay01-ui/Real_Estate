"""POST /events: behaviour events from the tracking SDK (sdk/leadops.js)."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from ..realtime import hub
from ..schemas import EventBatchIn, EventsAccepted
from ..tracking import store_event_batch
from ..utils import client_ip

router = APIRouter(tags=["events"])

MAX_BATCH_BYTES = 256 * 1024


@router.post("/events", response_model=EventsAccepted)
async def ingest_events(request: Request) -> EventsAccepted:
    """Store a batch of events. The body is an EventBatchIn as JSON (see docs/CONTRACTS.md).

    The SDK sends the JSON as text/plain, so browsers skip the CORS preflight and navigator.sendBeacon works
    when the page closes. That's why the body is parsed here rather than by FastAPI.
    """
    if int(request.headers.get("content-length") or 0) > MAX_BATCH_BYTES:
        raise HTTPException(status_code=413, detail="Batch too large")
    body = await request.body()
    if len(body) > MAX_BATCH_BYTES:
        raise HTTPException(status_code=413, detail="Batch too large")
    try:
        batch = EventBatchIn.model_validate_json(body)
    except ValidationError as exc:
        detail = exc.errors(include_url=False, include_context=False, include_input=False)
        raise HTTPException(status_code=422, detail=detail) from None

    visitor = await run_in_threadpool(store_event_batch, batch, client_ip(request), request.headers.get("user-agent"))
    await hub.broadcast({"type": "visitor_update", "visitor": visitor.model_dump(mode="json")})
    return EventsAccepted(accepted=len(batch.events))
