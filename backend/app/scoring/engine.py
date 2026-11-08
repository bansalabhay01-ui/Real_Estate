"""Scoring a visitor live: load what we know from the database, score it, save it and tell the dashboard.

Every event batch, enquiry and chat message rescores its visitor (rules and the model take milliseconds).
load_record() builds the same *visitor record* the simulator writes (see features.py), so live scoring and
training compute features from the same shape. Scoring never breaks ingestion: any error is logged and skipped.
"""

import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.classify import classify
from ..db import SessionLocal
from ..models import ChatMessage, Event, Lead, Score, Visitor, VisitSession
from ..realtime import hub
from ..schemas import VisitorOut
from ..tracking import visitor_out
from ..utils import utcnow
from .combine import score_record
from .features import NAN
from .model import reload_model
from .rules import phone_digits

log = logging.getLogger("leadops.scoring")

MAX_EVENTS = 3000  # the newest events of one visitor that scoring reads (scrapers can send thousands)
IP_WINDOW = timedelta(hours=24)
HISTORY_INTENT_STEP = 10  # a new row in the scores table when the label changes or intent moves this much


@dataclass
class ScoreUpdate:
    visitor: VisitorOut
    previous_label: str | None

    @property
    def label_changed(self) -> bool:
        return self.visitor.label != self.previous_label


def score_visitor(visitor_id: str) -> ScoreUpdate | None:
    """Score one visitor, save the result on it and, when it changed enough, in the scores table."""
    with SessionLocal() as db:
        record = load_record(db, visitor_id)
        if record is None:
            return None
        visitor = db.get(Visitor, visitor_id)
        result = score_record(record, visitor_type=known_type(visitor.visitor_type))
        previous_label, previous_intent = visitor.label, visitor.intent_score
        now = utcnow()
        saved = result.as_json()
        saved["scored_at"] = now.isoformat(timespec="seconds") + "Z"
        visitor.label, visitor.intent_score = result.label, result.intent_score
        visitor.human_prob, visitor.score, visitor.scored_at = round(result.human.human_prob, 4), saved, now
        if previous_label != result.label or abs((previous_intent or 0) - result.intent_score) >= HISTORY_INTENT_STEP:
            latest_lead = db.scalar(select(Lead.id).where(Lead.visitor_id == visitor_id).order_by(Lead.id.desc()).limit(1))
            db.add(Score(visitor_id=visitor_id, lead_id=latest_lead, label=result.label, human_prob=visitor.human_prob,
                         intent_score=result.intent_score, reasons=result.reasons, model_version=result.human.version,
                         created_at=now))
        db.commit()
        return ScoreUpdate(visitor_out(visitor), previous_label)


def score_safely(visitor_id: str | None) -> ScoreUpdate | None:
    """score_visitor() that never raises: a scoring bug must not lose an event batch or an enquiry."""
    if not visitor_id:
        return None
    try:
        return score_visitor(visitor_id)
    except Exception:
        log.exception("Scoring failed for visitor %s", visitor_id)
        return None


async def publish(visitor: VisitorOut | None, update: ScoreUpdate | None) -> None:
    """Tell the dashboards: the visitor as it is now, and a score_update when its label changed."""
    current = update.visitor if update else visitor
    if current is None:
        return
    await hub.broadcast({"type": "visitor_update", "visitor": current.model_dump(mode="json")})
    if update and update.label_changed and current.score:
        await hub.broadcast({
            "type": "score_update", "visitor_id": current.id, "label": current.label,
            "previous_label": update.previous_label, "intent_score": current.score.intent_score,
            "human_prob": current.score.human_prob, "visitor_type": current.score.visitor_type,
            "reasons": current.score.reasons,
        })  # fmt: skip


def known_type(saved: dict | None) -> dict | None:
    """The saved visitor type without bookkeeping, or None when the messages didn't say."""
    if not saved or not saved.get("type"):
        return None
    return {key: value for key, value in saved.items() if key != "text_hash"}


def classify_visitor(visitor_id: str) -> ScoreUpdate | None:
    """Work out the visitor type from their messages (the LLM, or keywords), save it and rescore.

    Skipped when the messages haven't changed since the last time, so a rescore never pays for another LLM call.
    """
    with SessionLocal() as db:
        visitor = db.get(Visitor, visitor_id)
        if visitor is None:
            return None
        texts = list(db.scalars(select(Lead.message).where(Lead.visitor_id == visitor_id, Lead.message.is_not(None)).order_by(Lead.id)))
        texts += list(db.scalars(
            select(ChatMessage.text).where(ChatMessage.visitor_id == visitor_id, ChatMessage.role == "user").order_by(ChatMessage.id)
        ))  # fmt: skip
        profile = dict(visitor.profile or {})
        saved = visitor.visitor_type or {}
    digest = hashlib.sha1(json.dumps([texts, profile.get("purpose")], ensure_ascii=False).encode()).hexdigest()[:16]
    if saved.get("text_hash") == digest:
        return None
    result = classify(texts, profile)  # may call the LLM: no database session is open
    with SessionLocal() as db:
        visitor = db.get(Visitor, visitor_id)
        visitor.visitor_type = {**(result or {}), "text_hash": digest}
        db.commit()
    return score_safely(visitor_id)


def classify_safely(visitor_id: str | None) -> ScoreUpdate | None:
    if not visitor_id:
        return None
    try:
        return classify_visitor(visitor_id)
    except Exception:
        log.exception("Classifying visitor %s failed", visitor_id)
        return None


async def classify_in_background(visitor_id: str | None) -> None:
    """Run after the response is sent (FastAPI BackgroundTasks), so a slow LLM never delays a visitor."""
    update = await run_in_threadpool(classify_safely, visitor_id)
    if update:
        await publish(None, update)


def rescore_all() -> int:
    """Reload the model from disk (after ml/train.py) and rescore every visitor, most recent first."""
    reload_model()
    with SessionLocal() as db:
        visitor_ids = list(db.scalars(select(Visitor.id).order_by(Visitor.last_seen.desc())))
    for visitor_id in visitor_ids:
        score_safely(visitor_id)
    return len(visitor_ids)


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
