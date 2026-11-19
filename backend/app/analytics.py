"""The numbers for the analytics page: the funnel, what was filtered out, and the sales time that saved."""

from collections import Counter
from datetime import timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Lead, Nudge, SiteVisit, Visitor
from .schemas import AnalyticsOut, DailyTraffic, FunnelStep
from .utils import IST, today_ist, utcnow

MINUTES_PER_FAKE_ENQUIRY = 6  # a stated assumption: a call attempt, a retry and the notes afterwards
FILTERED = ("Bot", "Junk")
SIMULATED_PREFIX = "sim-"


def _in_scope(column, include_simulated: bool):
    return [] if include_simulated else [column.not_like(f"{SIMULATED_PREFIX}%")]


def _count(db: Session, query) -> int:
    return db.scalar(query) or 0


def build_analytics(days: int, include_simulated: bool) -> AnalyticsOut:
    """Everything is about visitors first seen in the last `days` days (Indian dates), so the numbers always agree."""
    today = today_ist()
    first_day = today - timedelta(days=days - 1)
    since = (utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days + 1))
    with SessionLocal() as db:
        rows = db.execute(
            select(Visitor.id, Visitor.label, Visitor.lead_count, Visitor.first_seen).where(Visitor.first_seen >= since, *_in_scope(Visitor.id, include_simulated))
        ).all()
        rows = [row for row in rows if row.first_seen.replace(tzinfo=timezone.utc).astimezone(IST).date() >= first_day]
        ids = [row.id for row in rows]

        enquiries = enquiries_filtered = found_by_assistant = site_visits = offers_sent = offers_accepted = 0
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            enquiries += _count(db, select(func.count()).select_from(Lead).where(Lead.visitor_id.in_(chunk)))
            enquiries_filtered += _count(db, select(func.count()).select_from(Lead).join(Visitor, Visitor.id == Lead.visitor_id)
                                         .where(Lead.visitor_id.in_(chunk), Visitor.label.in_(FILTERED)))  # fmt: skip
            found_by_assistant += _count(db, select(func.count()).select_from(Lead).where(Lead.visitor_id.in_(chunk), Lead.source == "assistant_offer"))
            site_visits += _count(db, select(func.count()).select_from(SiteVisit).where(SiteVisit.visitor_id.in_(chunk), SiteVisit.status != "cancelled"))
            offers_sent += _count(db, select(func.count()).select_from(Nudge).where(Nudge.visitor_id.in_(chunk), Nudge.status != "pending"))
            offers_accepted += _count(db, select(func.count()).select_from(Nudge).where(Nudge.visitor_id.in_(chunk), Nudge.status == "accepted"))

    labels = Counter(row.label for row in rows if row.label)
    people = sum(1 for row in rows if row.label != "Bot")
    contacts = sum(1 for row in rows if row.lead_count > 0 and row.label not in FILTERED)
    hot = sum(1 for row in rows if row.lead_count > 0 and row.label == "Hot")

    by_day: dict = {first_day + timedelta(days=offset): Counter() for offset in range(days)}
    for row in rows:
        day = row.first_seen.replace(tzinfo=timezone.utc).astimezone(IST).date()
        if day in by_day:
            by_day[day]["bots" if row.label == "Bot" else "junk" if row.label == "Junk" else "kept"] += 1

    return AnalyticsOut(
        days=days,
        include_simulated=include_simulated,
        visitors=len(rows),
        funnel=[
            FunnelStep(step="visitors", label="All visitors", count=len(rows)),
            FunnelStep(step="people", label="Real people", count=people),
            FunnelStep(step="contacts", label="Real contacts", count=contacts),
            FunnelStep(step="hot", label="Hot leads", count=hot),
        ],
        labels=dict(labels),
        enquiries=enquiries,
        enquiries_filtered=enquiries_filtered,
        hours_saved=round(enquiries_filtered * MINUTES_PER_FAKE_ENQUIRY / 60, 1),
        minutes_per_enquiry=MINUTES_PER_FAKE_ENQUIRY,
        found_by_assistant=found_by_assistant,
        offers_sent=offers_sent,
        offers_accepted=offers_accepted,
        site_visits=site_visits,
        daily=[DailyTraffic(day=day, kept=counts["kept"], junk=counts["junk"], bots=counts["bots"]) for day, counts in by_day.items()],
    )
