"""Keeping personal data no longer than needed (DPDP Act 2023): erasure on request, and a daily clean-up.

After RETENTION_DAYS (default 180, because buying a home can take months) browsing events, sessions and chat are deleted,
visitors who never enquired are removed entirely, and older enquiries lose every personal detail but stay as counts.
"""

import asyncio
import logging
from datetime import timedelta

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .models import ChatMessage, Event, Feedback, Lead, Nudge, Score, SiteVisit, Visitor, VisitSession
from .utils import utcnow

log = logging.getLogger("leadops.retention")

_CHUNK = 500  # databases limit how many values one IN (...) may hold
_DAY_SECONDS = 86_400
ERASED_NAME, ERASED_PHONE = "Deleted", "deleted"


def erase_visitors(db: Session, visitor_ids: list[str]) -> int:
    """Delete these visitors and everything linked to them. Returns how many visitors were removed."""
    removed = 0
    for start in range(0, len(visitor_ids), _CHUNK):
        chunk = visitor_ids[start : start + _CHUNK]
        for table in (Feedback, Score, SiteVisit, Nudge, ChatMessage, Event, Lead, VisitSession):
            db.execute(delete(table).where(table.visitor_id.in_(chunk)))
        removed += db.execute(delete(Visitor).where(Visitor.id.in_(chunk))).rowcount
    db.commit()
    return removed


def purge_old(days: int) -> dict[str, int]:
    """Remove what has passed the retention period. Returns how many rows of each kind went."""
    cutoff = utcnow() - timedelta(days=days)
    with SessionLocal() as db:
        with_enquiries = select(Lead.visitor_id)
        forgotten = list(db.scalars(select(Visitor.id).where(Visitor.last_seen < cutoff, Visitor.id.not_in(with_enquiries))))
        visitors = erase_visitors(db, forgotten)

        events = db.execute(delete(Event).where(Event.received_at < cutoff)).rowcount
        chat = db.execute(delete(ChatMessage).where(ChatMessage.created_at < cutoff)).rowcount
        still_used = select(Event.session_id)
        sessions = db.execute(delete(VisitSession).where(VisitSession.last_seen < cutoff, VisitSession.id.not_in(still_used))).rowcount
        enquiries = db.execute(
            update(Lead).where(Lead.created_at < cutoff, Lead.name != ERASED_NAME).values(
                name=ERASED_NAME, phone=ERASED_PHONE, email=None, message=None, honeypot=None, page_url=None, ip=None, user_agent=None,
                otp_code=None, otp_token=None,
            )
        ).rowcount  # fmt: skip
        db.execute(update(Feedback).where(Feedback.created_at < cutoff).values(note=None))
        db.execute(update(Visitor).where(Visitor.last_seen < cutoff).values(
            profile={}, context={}, last_ip=None, user_agent=None, feedback_note=None, brief=None,
        ))  # fmt: skip
        db.commit()
    return {"visitors": visitors, "events": events, "chat": chat, "sessions": sessions, "enquiries": enquiries}


async def retention_loop() -> None:
    """Runs at startup and then once a day. RETENTION_DAYS=0 switches it off."""
    while settings.retention_days > 0:
        try:
            removed = await run_in_threadpool(purge_old, settings.retention_days)
            if any(removed.values()):
                log.info("Removed data past the retention period: %s", removed)
        except Exception:
            log.exception("The retention clean-up failed")
        await asyncio.sleep(_DAY_SECONDS)
