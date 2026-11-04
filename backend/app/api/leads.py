"""Enquiry-form submissions."""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from ..realtime import hub
from ..schemas import LeadAccepted, LeadIn, LeadOut
from ..tracking import get_lead, list_leads, store_lead
from ..utils import client_ip

router = APIRouter(tags=["leads"])


@router.post("/leads", response_model=LeadAccepted, status_code=201)
async def create_lead(payload: LeadIn, request: Request) -> LeadAccepted:
    """Save an enquiry. Bot-looking ones are saved too and get the same answer, so scoring can label them
    and bots get no hint that they were spotted."""
    lead, visitor = await run_in_threadpool(store_lead, payload, client_ip(request), request.headers.get("user-agent"))
    await hub.broadcast({"type": "lead_created", "lead": lead.model_dump(mode="json")})
    await hub.broadcast({"type": "visitor_update", "visitor": visitor.model_dump(mode="json")})
    return LeadAccepted(lead_id=lead.id)


@router.get("/leads", response_model=list[LeadOut])
def get_leads(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)) -> list[LeadOut]:
    """Newest first."""
    return list_leads(limit=limit, offset=offset)


@router.get("/leads/{lead_id}", response_model=LeadOut)
def get_one_lead(lead_id: int) -> LeadOut:
    lead = get_lead(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead
