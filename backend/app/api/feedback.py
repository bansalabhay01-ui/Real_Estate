"""Sales feedback on leads and visitors (genuine / fake / converted). These become training labels in Week 3."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..db import SessionLocal
from ..models import Feedback, Lead, Visitor
from ..schemas import FeedbackIn, FeedbackOut

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=FeedbackOut, status_code=201)
def add_feedback(payload: FeedbackIn) -> FeedbackOut:
    with SessionLocal() as db:
        visitor_id = payload.visitor_id
        if payload.lead_id is not None:
            lead = db.get(Lead, payload.lead_id)
            if lead is None:
                raise HTTPException(status_code=404, detail="Lead not found")
            visitor_id = visitor_id or lead.visitor_id
        if visitor_id is not None and db.get(Visitor, visitor_id) is None:
            raise HTTPException(status_code=404, detail="Visitor not found")
        row = Feedback(visitor_id=visitor_id, lead_id=payload.lead_id, label=payload.label, note=payload.note)
        db.add(row)
        db.commit()
        return FeedbackOut.model_validate(row)


@router.get("/feedback", response_model=list[FeedbackOut])
def list_feedback(limit: int = Query(100, ge=1, le=1000)) -> list[FeedbackOut]:
    """Newest first."""
    with SessionLocal() as db:
        rows = db.scalars(select(Feedback).order_by(Feedback.id.desc()).limit(limit))
        return [FeedbackOut.model_validate(row) for row in rows]
