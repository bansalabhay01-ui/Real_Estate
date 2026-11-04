"""Database tables.

Visitor -> VisitSession -> Event hold what the tracking SDK sends, Lead holds enquiry-form submissions and
ChatMessage holds assistant conversations. Score (Week 2 scoring engine) and Feedback (Week 3 sales feedback
loop) exist now so the schema doesn't change under the team later.
"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .utils import utcnow


class Visitor(Base):
    """One browser, identified by the anonymous ID the SDK keeps in localStorage."""

    __tablename__ = "visitors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    site: Mapped[str | None] = mapped_column(String(100))
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    last_ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    last_path: Mapped[str | None] = mapped_column(String(500))
    # Latest browser details from the SDK: webdriver flag, screen, time zone, languages, ...
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    # Buyer details gathered in chat: city, locality, bhk, budget_min/max, timeline_months, loan_needed, language.
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    session_count: Mapped[int] = mapped_column(Integer, default=0)
    page_views: Mapped[int] = mapped_column(Integer, default=0)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    lead_count: Mapped[int] = mapped_column(Integer, default=0)
    chat_count: Mapped[int] = mapped_column(Integer, default=0)  # messages the visitor sent to the assistant

    sessions: Mapped[list["VisitSession"]] = relationship(back_populates="visitor")

    @classmethod
    def new(cls, visitor_id: str, **fields) -> "Visitor":
        """A visitor with every counter at zero (column defaults only apply once the row is saved)."""
        now = utcnow()
        values = {
            "first_seen": now,
            "last_seen": now,
            "context": {},
            "profile": {},
            "session_count": 0,
            "page_views": 0,
            "event_count": 0,
            "lead_count": 0,
            "chat_count": 0,
        }
        values.update(fields)
        return cls(id=visitor_id, **values)


class VisitSession(Base):
    """One visit: activity from the same browser with no gap longer than 30 minutes (decided by the SDK)."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    visitor_id: Mapped[str] = mapped_column(ForeignKey("visitors.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    referrer: Mapped[str | None] = mapped_column(String(500))
    landing_path: Mapped[str | None] = mapped_column(String(500))
    utm: Mapped[dict] = mapped_column(JSON, default=dict)
    page_views: Mapped[int] = mapped_column(Integer, default=0)
    event_count: Mapped[int] = mapped_column(Integer, default=0)

    visitor: Mapped[Visitor] = relationship(back_populates="sessions")


class Event(Base):
    """One thing a visitor did: page view, click, scroll milestone, activity summary or custom event."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visitor_id: Mapped[str] = mapped_column(ForeignKey("visitors.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    type: Mapped[str] = mapped_column(String(50), index=True)
    path: Mapped[str | None] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(300))
    props: Mapped[dict] = mapped_column(JSON, default=dict)
    client_ts: Mapped[int | None] = mapped_column(BigInteger)  # browser clock, ms since epoch
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Lead(Base):
    """An enquiry-form submission. Stored even when it looks like a bot, so scoring can label it."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visitor_id: Mapped[str] = mapped_column(ForeignKey("visitors.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(64))
    listing_id: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(200))
    message: Mapped[str | None] = mapped_column(Text)
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    honeypot: Mapped[str | None] = mapped_column(Text)  # the hidden field: people leave it empty, bots fill it
    form_fill_ms: Mapped[int | None] = mapped_column(Integer)  # first touch of the form until submit
    page_url: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    client_ts: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ChatMessage(Base):
    """One message in a conversation with the property assistant."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visitor_id: Mapped[str] = mapped_column(ForeignKey("visitors.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(10))  # "user" or "assistant"
    text: Mapped[str] = mapped_column(Text)
    extracted: Mapped[dict] = mapped_column(JSON, default=dict)  # details found in a user message
    listing_ids: Mapped[list] = mapped_column(JSON, default=list)  # listings an assistant reply showed
    mode: Mapped[str | None] = mapped_column(String(10))  # "llm" or "template" for assistant replies
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Score(Base):
    """Output of the scoring engine (Week 2): one row per scoring run."""

    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visitor_id: Mapped[str] = mapped_column(ForeignKey("visitors.id"), index=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"))
    label: Mapped[str] = mapped_column(String(10))  # Bot / Junk / Cold / Warm / Hot / Review
    human_prob: Mapped[float | None] = mapped_column(Float)
    intent_score: Mapped[int | None] = mapped_column(Integer)  # 0-100
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    model_version: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Feedback(Base):
    """A salesperson's verdict on a lead or visitor; becomes training labels (Week 3)."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visitor_id: Mapped[str | None] = mapped_column(ForeignKey("visitors.id"), index=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"))
    label: Mapped[str] = mapped_column(String(20))  # genuine / fake / converted
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
