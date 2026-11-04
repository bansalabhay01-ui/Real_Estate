"""Visitor list and visitor profile for the sales dashboard."""

from fastapi import APIRouter, HTTPException, Query

from ..schemas import StatsOut, VisitorDetailOut, VisitorOut
from ..tracking import dashboard_stats, list_visitors, visitor_detail

router = APIRouter(tags=["visitors"])


@router.get("/stats", response_model=StatsOut)
def get_stats() -> StatsOut:
    """Headline numbers for the dashboard."""
    return dashboard_stats()


@router.get("/visitors", response_model=list[VisitorOut])
def get_visitors(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)) -> list[VisitorOut]:
    """Most recently active first."""
    return list_visitors(limit=limit, offset=offset)


@router.get("/visitors/{visitor_id}", response_model=VisitorDetailOut)
def get_visitor(visitor_id: str) -> VisitorDetailOut:
    """Sessions, recent events, enquiries and chat for one visitor."""
    detail = visitor_detail(visitor_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Visitor not found")
    return detail
