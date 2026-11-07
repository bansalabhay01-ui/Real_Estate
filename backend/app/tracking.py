"""Saving what visitors do (events, enquiries) and reading it back for the dashboard."""

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import TypeVar

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import ChatMessage, Event, Lead, Visitor, VisitSession
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
    VisitorDetailOut,
    VisitorOut,
)
from .scoring.rules import lead_checks
from .utils import automation_hints, device_from_ua, utcnow

DETAIL_EVENT_LIMIT = 200
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
    return LeadOut.model_validate(lead).model_copy(update={"label": label, "checks": checks})


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
            score_detail=(visitor.score or {}).get("detail"),
        )


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
