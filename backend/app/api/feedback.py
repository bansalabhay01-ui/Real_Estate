"""Sales verdicts on leads and visitors (genuine / fake / converted). A verdict counts at once, and ml/train.py learns from it."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from ..db import SessionLocal
from ..models import Feedback, Lead, Visitor
from ..schemas import FeedbackIn, FeedbackOut
from ..scoring.engine import publish, score_safely
from ..utils import utcnow

router = APIRouter(tags=["feedback"])


def _save(payload: FeedbackIn) -> FeedbackOut:
    with SessionLocal() as db:
        visitor_id = payload.visitor_id
        if payload.lead_id is not None:
            lead = db.get(Lead, payload.lead_id)
            if lead is None:
                raise HTTPException(status_code=404, detail="Lead not found")
            visitor_id = visitor_id or lead.visitor_id
        visitor = db.get(Visitor, visitor_id) if visitor_id is not None else None
        if visitor is None:
            raise HTTPException(status_code=404, detail="Visitor not found")
        now = utcnow()
        row = Feedback(visitor_id=visitor_id, lead_id=payload.lead_id, label=payload.label, note=payload.note, created_at=now)
        db.add(row)
        visitor.feedback_label, visitor.feedback_note, visitor.feedback_at = payload.label, payload.note, now
        db.commit()
        return FeedbackOut.model_validate(row)


@router.post("/feedback", response_model=FeedbackOut, status_code=201)
async def add_feedback(payload: FeedbackIn) -> FeedbackOut:
    """Save a verdict and relabel the visitor: Fake makes them Junk, Genuine and Converted overrule the rules and the model."""
    saved = await run_in_threadpool(_save, payload)
    await publish(None, await run_in_threadpool(score_safely, saved.visitor_id))
    return saved


@router.get("/feedback", response_model=list[FeedbackOut])
def list_feedback(limit: int = Query(100, ge=1, le=1000)) -> list[FeedbackOut]:
    """Newest first."""
    with SessionLocal() as db:
        rows = db.scalars(select(Feedback).order_by(Feedback.id.desc()).limit(limit))
        return [FeedbackOut.model_validate(row) for row in rows]
