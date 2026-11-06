"""Scoring a visitor live: load what we know from the database, score it, save it and tell the dashboard.

load_record() builds the same *visitor record* the simulator writes (see features.py), so live scoring and
training compute features from the same shape.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ChatMessage, Event, Lead, Visitor, VisitSession
from .features import NAN
from .rules import phone_digits

MAX_EVENTS = 3000  # the newest events of one visitor that scoring reads (scrapers can send thousands)
IP_WINDOW = timedelta(hours=24)


def _ms(value: datetime | None) -> int | None:
    """A database time (UTC, no tzinfo) as milliseconds since 1970, like the browser timestamps."""
    if value is None:
        return None
    return int((value - datetime(1970, 1, 1)).total_seconds() * 1000)


def load_record(db: Session, visitor_id: str) -> dict | None:
    """Everything scoring needs about one visitor, as a visitor record (features.py)."""
    visitor = db.get(Visitor, visitor_id)
    if visitor is None:
        return None
    sessions = db.scalars(
        select(VisitSession).where(VisitSession.visitor_id == visitor_id).order_by(VisitSession.started_at)
    ).all()
    newest = db.scalars(
        select(Event).where(Event.visitor_id == visitor_id).order_by(Event.id.desc()).limit(MAX_EVENTS)
    ).all()
    by_session: dict[str, list[dict]] = defaultdict(list)
    for event in reversed(newest):  # oldest first, in the order they were sent
        by_session[event.session_id].append({
            "type": event.type,
            "ts": event.client_ts if event.client_ts is not None else _ms(event.received_at),
            "path": event.path,
            "props": event.props or {},
        })  # fmt: skip
    leads = db.scalars(select(Lead).where(Lead.visitor_id == visitor_id).order_by(Lead.id)).all()
    chat = db.scalars(
        select(ChatMessage).where(ChatMessage.visitor_id == visitor_id, ChatMessage.role == "user").order_by(ChatMessage.id)
    ).all()
    record = {
        "visitor_id": visitor.id,
        "user_agent": visitor.user_agent,
        "context": visitor.context or {},
        "sessions": [{"session_id": row.id, "ip": row.ip, "events": by_session.get(row.id, [])} for row in sessions],
        "leads": [
            {
                "session_id": lead.session_id, "listing_id": lead.listing_id, "name": lead.name, "phone": lead.phone,
                "email": lead.email, "message": lead.message, "consent": lead.consent, "honeypot": lead.honeypot,
                "form_fill_ms": lead.form_fill_ms, "ip": lead.ip,
                "client_ts": lead.client_ts if lead.client_ts is not None else _ms(lead.created_at),
            }
            for lead in leads
        ],  # fmt: skip
        "chat": [{"session_id": row.session_id, "text": row.text, "ts": _ms(row.created_at)} for row in chat],
        "profile": visitor.profile or {},
    }
    record["network"] = network_counts(db, record, anchor=visitor.last_seen)
    return record


def network_counts(db: Session, record: dict, *, anchor: datetime) -> dict:
    """Visitors sharing this visitor's IPs over the 24 hours before its last activity, and visitors who sent the
    same phone number. features.add_network_counts() counts the same way for training data."""
    ips = {s["ip"] for s in record["sessions"] if s["ip"]} | {lead["ip"] for lead in record["leads"] if lead["ip"]}
    ip_visitors = NAN
    if ips:
        since = anchor - IP_WINDOW
        from_sessions = select(VisitSession.visitor_id).where(
            VisitSession.ip.in_(ips), VisitSession.last_seen >= since, VisitSession.started_at <= anchor
        )
        from_leads = select(Lead.visitor_id).where(Lead.ip.in_(ips), Lead.created_at >= since, Lead.created_at <= anchor)
        visitors = set(db.scalars(from_sessions)) | set(db.scalars(from_leads)) | {record["visitor_id"]}
        ip_visitors = float(len(visitors))

    phone_visitors = 0
    for key in {phone_digits(lead["phone"]) for lead in record["leads"]} - {""}:
        # Narrow the search with the last four digits, then compare the numbers digit by digit in Python.
        rows = db.execute(select(Lead.visitor_id, Lead.phone).where(Lead.phone.like(f"%{key[-4:]}%"))).all()
        same = {visitor for visitor, phone in rows if phone_digits(phone) == key}
        phone_visitors = max(phone_visitors, len(same))
    return {"ip_visitors": ip_visitors, "phone_visitors": phone_visitors}
