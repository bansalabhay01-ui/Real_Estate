"""Removing data: everything about chosen visitors, in the order the foreign keys need."""

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .models import ChatMessage, Event, Feedback, Lead, Score, Visitor, VisitSession

_CHUNK = 500  # databases limit how many values one IN (...) may hold


def erase_visitors(db: Session, visitor_ids: list[str]) -> int:
    """Delete these visitors and everything linked to them. Returns how many visitors were removed."""
    removed = 0
    for start in range(0, len(visitor_ids), _CHUNK):
        chunk = visitor_ids[start : start + _CHUNK]
        for table in (Feedback, Score, ChatMessage, Event, Lead, VisitSession):
            db.execute(delete(table).where(table.visitor_id.in_(chunk)))
        removed += db.execute(delete(Visitor).where(Visitor.id.in_(chunk))).rowcount
    db.commit()
    return removed
