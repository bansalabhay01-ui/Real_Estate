"""The smart engagement trigger: how LeadOps catches genuine buyers who would otherwise leave without a trace.

After each event batch this decides whether an anonymous visitor should get an offer from the assistant ("Want this
3 BHK floor plan on WhatsApp?"). The offer travels back in the /events response; the SDK hands it to the website, which
shows it. Offers come from templates in the visitor's language, so they are instant and free. Every offer is saved with
what became of it, so we can report how many offers turned into leads. A salesperson can also send one by hand.
"""

import logging
import re
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..listings import format_price, get_listing
from ..models import ChatMessage, Nudge, Visitor, VisitSession
from ..schemas import EventBatchIn, Listing, NudgeOut
from ..utils import utcnow

log = logging.getLogger("leadops.nudge")

MIN_HUMAN_PROB = 0.8  # only people who clearly look human get an offer
MIN_INTENT = 40  # Warm or better
MIN_VISIT = timedelta(seconds=60)
QUIET_CHAT = timedelta(seconds=120)  # someone talking to the assistant doesn't need it to interrupt them
MAX_A_DAY = 2
_PROPERTY_PATH = re.compile(r"^/property/([A-Za-z0-9-]+)")
_RANK = {"pending": 0, "sent": 1, "shown": 2, "accepted": 3, "dismissed": 3}
_OUTCOMES = {"nudge_shown": "shown", "nudge_accepted": "accepted", "nudge_dismissed": "dismissed"}

OFFERS = {
    "floor_plan": {
        "en": ("Want the {bhk} BHK floor plan of {project} on WhatsApp?", "Send it to me"),
        "hinglish": ("{project} ka {bhk} BHK floor plan WhatsApp par chahiye?", "Haan, bhej dijiye"),
        "hi": ("क्या आपको {project} का {bhk} BHK फ्लोर प्लान व्हाट्सऐप पर चाहिए?", "हां, भेज दीजिए"),
        "mr": ("{project} चा {bhk} BHK फ्लोर प्लॅन व्हॉट्सअ‍ॅपवर हवा आहे का?", "हो, पाठवा"),
    },
    "emi_plan": {
        "en": ("Want a personal EMI plan for {project} ({price}) on WhatsApp?", "Send my EMI plan"),
        "hinglish": ("{project} ({price}) ka personal EMI plan WhatsApp par chahiye?", "Haan, EMI plan bhejiye"),
        "hi": ("क्या आपको {project} ({price}) का पर्सनल EMI प्लान व्हाट्सऐप पर चाहिए?", "हां, EMI प्लान भेजिए"),
        "mr": ("{project} ({price}) चा तुमच्यासाठी EMI प्लॅन व्हॉट्सअ‍ॅपवर हवा आहे का?", "हो, EMI प्लॅन पाठवा"),
    },
    "site_visit": {
        "en": ("Welcome back! Shall I set up a site visit to {project} this weekend?", "Book a visit"),
        "hinglish": ("Wapas aane ka shukriya! Kya {project} ki site visit is weekend set kar doon?", "Visit book karein"),
        "hi": ("फिर से स्वागत है! क्या इस वीकेंड {project} की साइट विज़िट तय कर दूं?", "विज़िट बुक करें"),
        "mr": ("पुन्हा स्वागत आहे! या वीकेंडला {project} ची साइट व्हिजिट ठरवू का?", "व्हिजिट बुक करा"),
    },
    "shortlist": {
        "en": ("Comparing homes? I can send you a shortlist of three that fit, on WhatsApp.", "Send my shortlist"),
        "hinglish": ("Ghar compare kar rahe hain? Main aapko 3 best options ki list WhatsApp par bhej sakta hoon.", "List bhejiye"),
        "hi": ("घर की तुलना कर रहे हैं? मैं आपको 3 बेहतर विकल्पों की सूची व्हाट्सऐप पर भेज सकता हूं।", "सूची भेजिए"),
        "mr": ("घरांची तुलना करत आहात? मी तुम्हाला 3 चांगल्या घरांची यादी व्हॉट्सअ‍ॅपवर पाठवू शकतो.", "यादी पाठवा"),
    },
}


def _intent_signals(visitor: Visitor) -> set[str]:
    points = (((visitor.score or {}).get("detail") or {}).get("intent") or {}).get("points") or []
    return {point.get("signal") for point in points}


def choose_kind(visitor: Visitor, home: Listing | None) -> str:
    """The floor plan if they haven't got it, an EMI plan if they used the calculator, a visit if they came back."""
    if home is None:
        return "shortlist"
    signals = _intent_signals(visitor)
    if "floor_plan" not in signals:
        return "floor_plan"
    if "emi" in signals:
        return "emi_plan"
    return "site_visit" if visitor.session_count >= 2 else "shortlist"


def _language(visitor: Visitor) -> str:
    spoken = (visitor.profile or {}).get("language")
    if spoken in ("hinglish", "hi", "mr"):
        return spoken
    browser = str((visitor.context or {}).get("language") or "").lower()
    return "hi" if browser.startswith("hi") else "mr" if browser.startswith("mr") else "en"


def _ask(kind: str, home: Listing | None) -> str:
    """What the buyer asked for, in words for the sales team."""
    if home is None or kind == "shortlist":
        return "Asked for a shortlist of homes on WhatsApp"
    return {
        "floor_plan": f"Asked for the {home.bhk} BHK floor plan of {home.project} on WhatsApp",
        "emi_plan": f"Asked for an EMI plan for {home.project} on WhatsApp",
        "site_visit": f"Asked for a site visit to {home.project}",
    }[kind]


def _to_out(row: Nudge) -> NudgeOut:
    home = get_listing(row.listing_id) if row.listing_id else None
    return NudgeOut(id=row.id, kind=row.kind, text=row.text, cta=row.cta, listing_id=row.listing_id, project=home.project if home else None,
                    language=row.language, ask=_ask(row.kind, home))  # fmt: skip


def _create(db: Session, visitor: Visitor, home: Listing | None, session_id: str | None, trigger: str, status: str) -> Nudge:
    kind, language = choose_kind(visitor, home), _language(visitor)
    template, cta = OFFERS[kind][language]
    values = {"project": home.project, "bhk": home.bhk, "price": format_price(home.price_inr)} if home else {}
    now = utcnow()
    row = Nudge(id=uuid.uuid4().hex[:16], visitor_id=visitor.id, session_id=session_id, kind=kind, listing_id=home.id if home else None,
                language=language, text=template.format(**values), cta=cta, trigger=trigger, status=status, created_at=now,
                sent_at=now if status == "sent" else None)  # fmt: skip
    db.add(row)
    return row


def _home_on(path: str | None) -> Listing | None:
    match = _PROPERTY_PATH.match(path or "")
    return get_listing(match.group(1)) if match else None


def _note_outcomes(db: Session, batch: EventBatchIn) -> None:
    """The website reports what the visitor did with an offer as ordinary events."""
    for event in batch.events:
        status = _OUTCOMES.get(event.type)
        if status and (row := db.get(Nudge, str(event.props.get("nudge_id") or ""))) and row.visitor_id == batch.visitor_id:
            if _RANK[status] >= _RANK.get(row.status, 0):
                row.status = status


def _deserves_an_offer(db: Session, visitor: Visitor, session_id: str) -> bool:
    now = utcnow()
    if visitor.lead_count > 0 or visitor.label not in ("Warm", "Hot"):
        return False
    if (visitor.human_prob or 0) < MIN_HUMAN_PROB or (visitor.intent_score or 0) < MIN_INTENT:
        return False
    session = db.get(VisitSession, session_id)
    if session is None or now - session.started_at < MIN_VISIT:
        return False
    last_chat = db.scalar(select(func.max(ChatMessage.created_at)).where(ChatMessage.visitor_id == visitor.id))
    if last_chat is not None and now - last_chat < QUIET_CHAT:
        return False
    if db.scalar(select(func.count()).select_from(Nudge).where(Nudge.visitor_id == visitor.id, Nudge.session_id == session_id)):
        return False  # once per visit
    today = now - timedelta(days=1)
    return (db.scalar(select(func.count()).select_from(Nudge).where(Nudge.visitor_id == visitor.id, Nudge.created_at >= today)) or 0) < MAX_A_DAY


def _next_offer(batch: EventBatchIn) -> NudgeOut | None:
    with SessionLocal() as db:
        _note_outcomes(db, batch)
        visitor = db.get(Visitor, batch.visitor_id)
        if visitor is None:
            db.commit()
            return None
        waiting = db.scalars(select(Nudge).where(Nudge.visitor_id == visitor.id, Nudge.status == "pending").order_by(Nudge.created_at)).first()
        if waiting is not None:  # a salesperson pressed "Send an offer now"
            waiting.status, waiting.session_id, waiting.sent_at = "sent", batch.session_id, utcnow()
            db.commit()
            return _to_out(waiting)
        path = next((event.path for event in reversed(batch.events) if event.path), visitor.last_path)
        home = _home_on(path)
        if home is None or not _deserves_an_offer(db, visitor, batch.session_id):
            db.commit()
            return None
        row = _create(db, visitor, home, batch.session_id, "auto", "sent")
        db.commit()
        return _to_out(row)


def next_offer(batch: EventBatchIn) -> NudgeOut | None:
    """The offer to send back with this event batch, if any. Never raises: an offer must not cost an event batch."""
    try:
        return _next_offer(batch)
    except Exception:
        log.exception("Deciding on an offer for visitor %s failed", batch.visitor_id)
        return None


class OfferRefused(Exception):
    """Why this visitor can't be sent an offer: the status code and a sentence for the salesperson."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def queue_offer(visitor_id: str) -> NudgeOut:
    """"Send an offer now" on the dashboard: it reaches the visitor's browser with their next event batch."""
    with SessionLocal() as db:
        visitor = db.get(Visitor, visitor_id)
        if visitor is None:
            raise OfferRefused(404, "Visitor not found")
        if visitor.lead_count > 0:
            raise OfferRefused(409, "This visitor has already shared contact details")
        if visitor.label in ("Bot", "Junk"):
            raise OfferRefused(409, f"This visitor is labelled {visitor.label}")
        waiting = db.scalars(select(Nudge).where(Nudge.visitor_id == visitor_id, Nudge.status == "pending")).first()
        if waiting is not None:
            return _to_out(waiting)
        row = _create(db, visitor, _home_on(visitor.last_path), None, "sales", "pending")
        db.commit()
        return _to_out(row)
