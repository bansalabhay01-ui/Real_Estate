"""Visitor list and visitor profile for the sales dashboard, and rescoring after a retrain."""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from ..ai.brief import build_brief, build_followup
from ..analytics import build_analytics
from ..auth import DASHBOARD_ONLY, PASSCODE_HEADER, passcode_ok
from ..db import SessionLocal
from ..models import Visitor
from ..retention import erase_visitors
from ..schemas import AccessOut, AnalyticsOut, BriefOut, ErasedOut, FollowUpIn, FollowUpOut, NudgeOut, RescoreOut, StatsOut, VisitorDetailOut, VisitorOut
from ..scoring.engine import broadcast_snapshot, rescore_all
from ..scoring.nudge import OfferRefused, queue_offer
from ..tracking import dashboard_stats, list_visitors, visitor_detail

router = APIRouter(tags=["visitors"], dependencies=DASHBOARD_ONLY)
erasure = APIRouter(tags=["privacy"])  # visitors can erase their own data, so this one has its own check

Label = Literal["Bot", "Junk", "Review", "Cold", "Warm", "Hot"]


@router.get("/auth/check", response_model=AccessOut)
def check_access() -> AccessOut:
    """Lets the dashboard find out whether its passcode is right."""
    return AccessOut()


def _erase(visitor_id: str) -> bool:
    with SessionLocal() as db:
        return db.get(Visitor, visitor_id) is not None and erase_visitors(db, [visitor_id]) == 1


@erasure.delete("/visitors/{visitor_id}", response_model=ErasedOut)
async def erase_visitor(visitor_id: str, request: Request) -> ErasedOut:
    """Delete a visitor and everything about them (DPDP Act 2023, the right to erasure). The sales team can do this from
    the dashboard, and visitors can do it for themselves by sending their own anonymous ID in X-LeadOps-Visitor."""
    is_themselves = request.headers.get("x-leadops-visitor") == visitor_id
    if not is_themselves and not passcode_ok(request.headers.get(PASSCODE_HEADER)):
        raise HTTPException(status_code=401, detail="Enter the dashboard passcode")
    if not await run_in_threadpool(_erase, visitor_id):
        raise HTTPException(status_code=404, detail="Visitor not found")
    await broadcast_snapshot()
    return ErasedOut()


@router.get("/stats", response_model=StatsOut)
def get_stats() -> StatsOut:
    """Headline numbers for the dashboard, including visitors per label."""
    return dashboard_stats()


@router.get("/analytics", response_model=AnalyticsOut)
def get_analytics(
    days: int = Query(14, ge=1, le=90, description="visitors first seen in the last this many days"),
    simulated: bool = Query(True, description="count the visitors made by Simulate traffic"),
) -> AnalyticsOut:
    """The funnel, what was filtered out, the sales time that saved and traffic per day."""
    return build_analytics(days, simulated)


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


@router.get("/visitors/{visitor_id}/brief", response_model=BriefOut)
def get_brief(visitor_id: str) -> BriefOut:
    """Three plain lines about this visitor and the recommended next step."""
    brief = build_brief(visitor_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Visitor not found")
    return brief


@router.post("/visitors/{visitor_id}/followup", response_model=FollowUpOut)
def draft_followup(visitor_id: str, payload: FollowUpIn) -> FollowUpOut:
    """A WhatsApp or email draft in the buyer's language, to edit and send."""
    draft = build_followup(visitor_id, payload.channel, payload.language)
    if draft is None:
        raise HTTPException(status_code=404, detail="Visitor not found")
    return draft


@router.post("/visitors/{visitor_id}/nudge", response_model=NudgeOut, status_code=201)
def send_offer(visitor_id: str) -> NudgeOut:
    """"Send an offer now": the assistant makes this visitor an offer with their next event batch."""
    try:
        return queue_offer(visitor_id)
    except OfferRefused as refused:
        raise HTTPException(status_code=refused.status, detail=refused.detail) from None


async def _rescore_and_refresh() -> None:
    await run_in_threadpool(rescore_all)
    await broadcast_snapshot()


@router.post("/scoring/rescore", response_model=RescoreOut, tags=["scoring"])
def rescore(background: BackgroundTasks) -> RescoreOut:
    """Reload the model from backend/data/model (after ml/train.py) and relabel every visitor in the background."""
    background.add_task(_rescore_and_refresh)
    return RescoreOut(visitors=dashboard_stats().visitors)
