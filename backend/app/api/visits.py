"""Site visits: requested through the assistant, or booked by the sales team from the dashboard."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from ..ai.assistant import visit_confirmation
from ..realtime import hub
from ..schemas import VisitIn, VisitOut, VisitUpdate
from ..scoring.engine import publish, score_safely
from ..tracking import VisitProblem, list_site_visits, request_visit, update_site_visit
from ..utils import client_ip

router = APIRouter(tags=["visits"])


@router.post("/visits", response_model=VisitOut, status_code=201)
async def create_visit(payload: VisitIn, request: Request) -> VisitOut:
    """Book a site visit. A visitor who hasn't left contact details sends them here, and they become an enquiry."""
    try:
        visit, lead = await run_in_threadpool(request_visit, payload, client_ip(request), request.headers.get("user-agent"))
    except VisitProblem as problem:
        raise HTTPException(status_code=problem.status, detail=problem.detail) from None
    update = await run_in_threadpool(score_safely, visit.visitor_id)
    if lead:
        label = update.visitor.label if update else lead.label
        await hub.broadcast({"type": "lead_created", "lead": lead.model_copy(update={"label": label}).model_dump(mode="json")})
    await publish(None, update)
    await hub.broadcast({"type": "visit_booked", "visit": visit.model_dump(mode="json")})
    return visit.model_copy(update={"confirmation": visit_confirmation(payload.language, visit)})


@router.get("/visits", response_model=list[VisitOut])
def get_visits(
    limit: int = Query(50, ge=1, le=200),
    status: Literal["requested", "confirmed", "done", "cancelled"] | None = Query(None),
) -> list[VisitOut]:
    """Site visits, soonest first."""
    return list_site_visits(limit=limit, status=status)


@router.patch("/visits/{visit_id}", response_model=VisitOut)
async def change_visit(visit_id: int, change: VisitUpdate) -> VisitOut:
    """Confirm, move or cancel a visit. A cancelled visit stops counting towards the visitor's intent."""
    visit = await run_in_threadpool(update_site_visit, visit_id, change)
    if visit is None:
        raise HTTPException(status_code=404, detail="Site visit not found")
    await publish(None, await run_in_threadpool(score_safely, visit.visitor_id))
    await hub.broadcast({"type": "visit_updated", "visit": visit.model_dump(mode="json")})
    return visit
