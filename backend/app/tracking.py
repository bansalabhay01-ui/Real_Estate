"""Saving what visitors do (events, enquiries) and reading it back for the dashboard."""

import time
import uuid
from collections.abc import Callable
from datetime import date, timedelta
from typing import TypeVar

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import SessionLocal
from .listings import get_listing
from .models import ChatMessage, Event, Lead, SiteVisit, Visitor, VisitSession
from .schemas import (
    ChatMessageOut,
    EventBatchIn,
    EventOut,
    LeadCheckOut,
    LeadIn,
    LeadOut,
    ScoreOut,
    SessionOut,
    StatsOut,
    VisitIn,
    VisitOut,
    VisitorDetailOut,
    VisitorOut,
    VisitUpdate,
)
from .scoring.rules import check_phone, lead_checks
from .utils import automation_hints, device_from_ua, short_day, today_ist, utcnow

DETAIL_EVENT_LIMIT = 200
MAX_VISIT_DAYS = 60  # how far ahead a site visit can be booked
T = TypeVar("T")


def run_in_session(work: Callable[[Session], T]) -> T:
    """Run work(db) in a fresh session. Retries once if two first requests from a new visitor race to create it."""
    for attempt in range(2):
        with SessionLocal() as db:
            try:
                return work(db)
            except IntegrityError:
                db.rollback()
                if attempt == 1:
                    raise
    raise AssertionError("unreachable")


def score_out(saved: dict | None) -> ScoreOut | None:
    """The saved score without its full breakdown (that comes with GET /visitors/{id} as score_detail)."""
    if not saved:
        return None
    try:
        return ScoreOut.model_validate({key: value for key, value in saved.items() if key != "detail"})
    except ValidationError:  # saved by an older version: rescoring fixes it
        return None


def lead_out(lead: Lead, label: str | None = None) -> LeadOut:
    fields = {"phone": lead.phone, "email": lead.email, "name": lead.name, "message": lead.message,
              "honeypot": lead.honeypot, "form_fill_ms": lead.form_fill_ms}
    checks = [LeadCheckOut(**check) for check in lead_checks(fields)]
    return LeadOut.model_validate(lead).model_copy(update={"label": label, "checks": checks, "source": lead.source or "form"})


def visitor_out(visitor: Visitor) -> VisitorOut:
    return VisitorOut(
        id=visitor.id,
        site=visitor.site,
        first_seen=visitor.first_seen,
        last_seen=visitor.last_seen,
        session_count=visitor.session_count,
        page_views=visitor.page_views,
        event_count=visitor.event_count,
        lead_count=visitor.lead_count,
        chat_count=visitor.chat_count,
        last_path=visitor.last_path,
        last_ip=visitor.last_ip,
        device=device_from_ua(visitor.user_agent),
        automation_hints=automation_hints(visitor.user_agent, visitor.context or {}),
        profile=visitor.profile or {},
        label=visitor.label,
        test_label=(visitor.context or {}).get("test_label"),
        score=score_out(visitor.score),
    )


def get_or_create_visitor(
    db: Session, visitor_id: str, *, site: str | None = None, ip: str | None = None, user_agent: str | None = None
) -> Visitor:
    visitor = db.get(Visitor, visitor_id)
    if visitor is None:
        visitor = Visitor.new(visitor_id, site=site, last_ip=ip, user_agent=user_agent)
        db.add(visitor)
        db.flush()  # insert it now: rows added next (events, leads, chat) point to it
    return visitor


def store_event_batch(batch: EventBatchIn, ip: str | None, user_agent: str | None) -> VisitorOut:
    def work(db: Session) -> VisitorOut:
        now = utcnow()
        visitor = get_or_create_visitor(db, batch.visitor_id, site=batch.site, ip=ip, user_agent=user_agent)
        session = db.get(VisitSession, batch.session_id)
        if session is None:
            session = VisitSession(
                id=batch.session_id,
                visitor_id=visitor.id,
                started_at=now,
                last_seen=now,
                ip=ip,
                user_agent=user_agent,
                referrer=batch.context.referrer,
                landing_path=batch.events[0].path,
                utm=batch.context.utm or {},
                page_views=0,
                event_count=0,
            )
            db.add(session)
            db.flush()  # insert it before the events that point to it
            visitor.session_count += 1

        db.add_all(
            Event(
                visitor_id=visitor.id,
                session_id=session.id,
                type=item.type,
                path=item.path,
                url=item.url,
                title=item.title,
                props=item.props,
                client_ts=item.ts,
                received_at=now,
            )
            for item in batch.events
        )
        page_views = sum(1 for item in batch.events if item.type == "page_view")
        session.last_seen = now
        session.page_views += page_views
        session.event_count += len(batch.events)
        visitor.last_seen = now
        visitor.page_views += page_views
        visitor.event_count += len(batch.events)
        visitor.site = batch.site or visitor.site
        visitor.last_ip = ip or visitor.last_ip
        visitor.user_agent = user_agent or visitor.user_agent
        visitor.context = batch.context.model_dump(exclude_none=True)
        last_path = next((item.path for item in reversed(batch.events) if item.path), None)
        if last_path:
            visitor.last_path = last_path
        db.commit()
        return visitor_out(visitor)

    return run_in_session(work)


def store_lead(payload: LeadIn, ip: str | None, user_agent: str | None) -> tuple[LeadOut, VisitorOut]:
    # A form posted without the SDK (for example by a bot calling the API directly) gets a visitor record of
    # its own: an enquiry with no browsing at all is itself a strong bot signal.
    visitor_id = payload.visitor_id or f"nosdk-{uuid.uuid4().hex}"

    def work(db: Session) -> tuple[LeadOut, VisitorOut]:
        now = utcnow()
        visitor = get_or_create_visitor(db, visitor_id, ip=ip, user_agent=user_agent)
        lead = Lead(
            visitor_id=visitor.id,
            session_id=payload.session_id,
            listing_id=payload.listing_id,
            name=payload.name,
            phone=payload.phone,
            email=payload.email or None,
            message=payload.message or None,
            consent=payload.consent,
            honeypot=payload.honeypot or None,
            form_fill_ms=payload.form_fill_ms,
            page_url=payload.page_url,
            ip=ip,
            user_agent=user_agent,
            client_ts=payload.client_ts,
            status="new",
            source=payload.source or "form",
            created_at=now,
        )
        db.add(lead)
        visitor.lead_count += 1
        visitor.last_seen = now
        visitor.last_ip = ip or visitor.last_ip
        db.commit()
        return lead_out(lead, visitor.label), visitor_out(visitor)

    return run_in_session(work)


def list_visitors(limit: int = 50, offset: int = 0, *, label: str | None = None, sort: str = "recent") -> list[VisitorOut]:
    """sort: "recent" (latest activity first) or "intent" (highest intent score first)."""
    query = select(Visitor)
    if label:
        query = query.where(Visitor.label == label)
    if sort == "intent":
        query = query.order_by(Visitor.intent_score.desc().nulls_last(), Visitor.last_seen.desc())
    else:
        query = query.order_by(Visitor.last_seen.desc())
    with SessionLocal() as db:
        return [visitor_out(row) for row in db.scalars(query.limit(limit).offset(offset))]


def visitor_detail(visitor_id: str) -> VisitorDetailOut | None:
    with SessionLocal() as db:
        visitor = db.get(Visitor, visitor_id)
        if visitor is None:
            return None
        sessions = db.scalars(
            select(VisitSession).where(VisitSession.visitor_id == visitor_id).order_by(VisitSession.started_at.desc())
        )
        events = db.scalars(
            select(Event).where(Event.visitor_id == visitor_id).order_by(Event.id.desc()).limit(DETAIL_EVENT_LIMIT)
        )
        leads = db.scalars(select(Lead).where(Lead.visitor_id == visitor_id).order_by(Lead.id.desc()))
        chat = db.scalars(select(ChatMessage).where(ChatMessage.visitor_id == visitor_id).order_by(ChatMessage.id))
        return VisitorDetailOut(
            visitor=visitor_out(visitor),
            user_agent=visitor.user_agent,
            context=visitor.context or {},
            sessions=[SessionOut.model_validate(row) for row in sessions],
            events=[EventOut.model_validate(row) for row in events],
            leads=[lead_out(row, visitor.label) for row in leads],
            chat=[ChatMessageOut.model_validate(row) for row in chat],
            site_visits=_visits_of(db, visitor_id),
            score_detail=(visitor.score or {}).get("detail"),
        )


# ---------------------------------------------------------------- site visits


class VisitProblem(Exception):
    """A site-visit request that can't be booked: the status code and a sentence for the visitor."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def visit_out(visit: SiteVisit, lead: Lead | None) -> VisitOut:
    home = get_listing(visit.listing_id)
    return VisitOut(
        id=visit.id, visitor_id=visit.visitor_id, lead_id=visit.lead_id, listing_id=visit.listing_id,
        project=home.project if home else visit.listing_id, locality=home.locality if home else "", city=home.city if home else "",
        day=visit.day, day_text=short_day(visit.day), slot=visit.slot, status=visit.status, source=visit.source,
        name=lead.name if lead else None, phone=lead.phone if lead else None, created_at=visit.created_at,
    )  # fmt: skip


def _visits_of(db: Session, visitor_id: str) -> list[VisitOut]:
    rows = db.scalars(select(SiteVisit).where(SiteVisit.visitor_id == visitor_id).order_by(SiteVisit.id.desc())).all()
    return [visit_out(row, db.get(Lead, row.lead_id) if row.lead_id else None) for row in rows]


def contact_lead_id(visitor_id: str | None) -> int | None:
    """The visitor's latest enquiry with a real-looking number, if they have left one."""
    if not visitor_id:
        return None
    with SessionLocal() as db:
        leads = db.scalars(select(Lead).where(Lead.visitor_id == visitor_id).order_by(Lead.id.desc())).all()
        return next((lead.id for lead in leads if check_phone(lead.phone).kind in ("mobile", "international")), None)


def save_site_visit(visitor_id: str, lead_id: int | None, listing_id: str, day: date, slot: str, source: str) -> VisitOut:
    """Book a visit. Asking again for the same home and day changes the slot instead of booking twice."""

    def work(db: Session) -> VisitOut:
        visit = db.scalar(select(SiteVisit).where(
            SiteVisit.visitor_id == visitor_id, SiteVisit.listing_id == listing_id, SiteVisit.day == day, SiteVisit.status != "cancelled",
        ))  # fmt: skip
        if visit is None:
            visit = SiteVisit(visitor_id=visitor_id, lead_id=lead_id, listing_id=listing_id, day=day, slot=slot, status="requested",
                              source=source, created_at=utcnow())  # fmt: skip
            db.add(visit)
        else:
            visit.slot = slot
        visitor = db.get(Visitor, visitor_id)
        if visitor is not None:
            visitor.last_seen = utcnow()
        db.commit()
        return visit_out(visit, db.get(Lead, visit.lead_id) if visit.lead_id else None)

    return run_in_session(work)


def request_visit(payload: VisitIn, ip: str | None, user_agent: str | None) -> tuple[VisitOut, LeadOut | None]:
    """A visit from the chat widget or the dashboard. New contact details become an enquiry first."""
    home = get_listing(payload.listing_id)
    if home is None:
        raise VisitProblem(404, "We couldn't find that home")
    today = today_ist()
    if not today <= payload.day <= today + timedelta(days=MAX_VISIT_DAYS):
        raise VisitProblem(422, f"Pick a day in the next {MAX_VISIT_DAYS} days")
    lead_id = contact_lead_id(payload.visitor_id)
    new_lead = None
    visitor_id = payload.visitor_id
    if lead_id is None:
        if not (payload.name or "").strip() or not (payload.phone or "").strip():
            raise VisitProblem(422, "We need your name and mobile number to book the visit")
        if not payload.consent:
            raise VisitProblem(422, "Please agree to be contacted about this visit")
        details = LeadIn(
            visitor_id=payload.visitor_id, session_id=payload.session_id, listing_id=home.id, name=payload.name.strip(),
            phone=payload.phone.strip(), email=payload.email, message=f"Asked for a site visit to {home.project}", consent=True,
            honeypot=payload.honeypot, form_fill_ms=payload.form_fill_ms, client_ts=int(time.time() * 1000), source="chat",
        )  # fmt: skip
        new_lead, _ = store_lead(details, ip, user_agent)
        visitor_id, lead_id = new_lead.visitor_id, new_lead.id
    return save_site_visit(visitor_id, lead_id, home.id, payload.day, payload.slot, payload.source), new_lead


def list_site_visits(limit: int = 50, status: str | None = None) -> list[VisitOut]:
    query = select(SiteVisit).order_by(SiteVisit.day, SiteVisit.id.desc())
    if status:
        query = query.where(SiteVisit.status == status)
    with SessionLocal() as db:
        return [visit_out(row, db.get(Lead, row.lead_id) if row.lead_id else None) for row in db.scalars(query.limit(limit))]


def update_site_visit(visit_id: int, change: VisitUpdate) -> VisitOut | None:
    with SessionLocal() as db:
        visit = db.get(SiteVisit, visit_id)
        if visit is None:
            return None
        for key, value in change.model_dump(exclude_none=True).items():
            setattr(visit, key, value)
        db.commit()
        return visit_out(visit, db.get(Lead, visit.lead_id) if visit.lead_id else None)


def dashboard_stats(active_minutes: int = 2) -> StatsOut:
    cutoff = utcnow() - timedelta(minutes=active_minutes)
    with SessionLocal() as db:
        count = select(func.count()).select_from(Visitor)
        return StatsOut(
            visitors=db.scalar(count) or 0,
            active_now=db.scalar(count.where(Visitor.last_seen >= cutoff)) or 0,
            leads=db.scalar(select(func.count()).select_from(Lead)) or 0,
            chatting_visitors=db.scalar(count.where(Visitor.chat_count > 0)) or 0,
            labels=dict(
                db.execute(
                    select(Visitor.label, func.count()).where(Visitor.label.is_not(None)).group_by(Visitor.label)
                ).all()
            ),
        )


def list_leads(limit: int = 50, offset: int = 0) -> list[LeadOut]:
    with SessionLocal() as db:
        rows = db.execute(
            select(Lead, Visitor.label).join(Visitor, Visitor.id == Lead.visitor_id).order_by(Lead.id.desc()).limit(limit).offset(offset)
        ).all()
        return [lead_out(lead, label) for lead, label in rows]


def get_lead(lead_id: int) -> LeadOut | None:
    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        if lead is None:
            return None
        return lead_out(lead, db.scalar(select(Visitor.label).where(Visitor.id == lead.visitor_id)))
