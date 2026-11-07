"""Visitor list and visitor profile for the sales dashboard, and rescoring after a retrain."""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from ..realtime import hub
from ..schemas import RescoreOut, StatsOut, VisitorDetailOut, VisitorOut
from ..scoring.engine import rescore_all
from ..tracking import dashboard_stats, list_leads, list_visitors, visitor_detail

router = APIRouter(tags=["visitors"])

Label = Literal["Bot", "Junk", "Review", "Cold", "Warm", "Hot"]


@router.get("/stats", response_model=StatsOut)
def get_stats() -> StatsOut:
    """Headline numbers for the dashboard, including visitors per label."""
    return dashboard_stats()


@router.get("/visitors", response_model=list[VisitorOut])
def get_visitors(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    label: Label | None = Query(None, description="only visitors with this label"),
    sort: Literal["recent", "intent"] = Query("recent", description="recent: latest activity first; intent: highest first"),
) -> list[VisitorOut]:
    return list_visitors(limit=limit, offset=offset, label=label, sort=sort)


@router.get("/visitors/{visitor_id}", response_model=VisitorDetailOut)
def get_visitor(visitor_id: str) -> VisitorDetailOut:
    """Sessions, recent events, enquiries, chat and the score breakdown for one visitor."""
    detail = visitor_detail(visitor_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Visitor not found")
    return detail


async def _rescore_and_refresh() -> None:
    await run_in_threadpool(rescore_all)
    visitors, leads = await run_in_threadpool(list_visitors, 50), await run_in_threadpool(list_leads, 20)  # as on connect
    await hub.broadcast({  # dashboards replace their lists, as when they connect
        "type": "snapshot",
        "visitors": [visitor.model_dump(mode="json") for visitor in visitors],
        "leads": [lead.model_dump(mode="json") for lead in leads],
    })  # fmt: skip


@router.post("/scoring/rescore", response_model=RescoreOut, tags=["scoring"])
def rescore(background: BackgroundTasks) -> RescoreOut:
    """Reload the model from backend/data/model (after ml/train.py) and relabel every visitor in the background."""
    background.add_task(_rescore_and_refresh)
    return RescoreOut(visitors=dashboard_stats().visitors)
