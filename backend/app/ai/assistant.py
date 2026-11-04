"""The property assistant: pull out buyer details -> find listings -> reply.

Replies come from the LLM when a key is set (llm_client.py) and from templates otherwise. Any LLM failure
also falls back to a template, so the demo never breaks. Buyer details are saved on the visitor as JSON
(visitor.profile) for the dashboard and, from Week 2, for scoring.
"""

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..listings import filter_listings, format_price, get_listing
from ..models import ChatMessage, Visitor
from ..schemas import ChatIn, ChatMessageOut, ChatOut, Listing, VisitorOut
from ..tracking import get_or_create_visitor, run_in_session, visitor_out
from ..utils import utcnow
from .extract import extract_details
from .llm_client import LLMError, llm
from .privacy import mask_pii
from .rag import SearchResult, find_listings

log = logging.getLogger("leadops.assistant")

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "assistant_system.md").read_text(encoding="utf-8")
HISTORY_MESSAGES = 8  # earlier messages sent to the LLM for context
SEARCH_KEYS = ("city", "locality", "bhk", "budget_min", "budget_max")

# Qualifying questions, asked one at a time, in this order, for whatever is still unknown.
QUESTIONS = {
    "city": "Which city are you looking in? We have homes in Pune, Bengaluru, Hyderabad, Mumbai and Noida.",
    "bhk": "How many bedrooms do you need: 1, 2, 3 or 4 BHK?",
    "budget": "What budget do you have in mind? For example, under ₹90 L or up to ₹1.5 Cr.",
    "timeline": "When are you planning to move in: right away, within 6 months, or later?",
    "loan": "Will you need a home loan? Each property page has an EMI calculator.",
}


def handle_chat(payload: ChatIn, ip: str | None, user_agent: str | None) -> tuple[ChatOut, VisitorOut | None]:
    found = extract_details(payload.message)

    # 1. What we already know (a short database read).
    with SessionLocal() as db:
        visitor = db.get(Visitor, payload.visitor_id) if payload.visitor_id else None
        old_profile = dict(visitor.profile or {}) if visitor else {}
        history = _recent_history(db, payload.visitor_id) if visitor else []

    # 2. Find homes and write the reply (may call the LLM, so no database session is held open).
    profile = merge_profile(old_profile, found)
    current = get_listing(payload.listing_id) if payload.listing_id else None
    result = _search(profile, found, payload.message, current)
    reply, mode = _reply(payload.message, history, profile, result, current)

    # 3. Save the exchange and the updated buyer details.
    summary = None
    if payload.visitor_id:

        def save(db: Session) -> VisitorOut:
            now = utcnow()
            row = get_or_create_visitor(db, payload.visitor_id, ip=ip, user_agent=user_agent)
            db.add_all(
                [
                    ChatMessage(
                        visitor_id=row.id, session_id=payload.session_id, role="user", text=payload.message,
                        extracted=found, listing_ids=[], created_at=now,
                    ),
                    ChatMessage(
                        visitor_id=row.id, session_id=payload.session_id, role="assistant", text=reply,
                        extracted={}, listing_ids=[item.id for item in result.listings], mode=mode, created_at=now,
                    ),
                ]
            )  # fmt: skip
            row.profile = merge_profile(dict(row.profile or {}), found)
            row.chat_count += 1
            row.last_seen = now
            db.commit()
            return visitor_out(row)

        summary = run_in_session(save)

    return ChatOut(reply=reply, listings=result.listings, extracted=found, profile=profile, mode=mode), summary


def chat_history(visitor_id: str, limit: int = 50) -> list[ChatMessageOut]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(ChatMessage).where(ChatMessage.visitor_id == visitor_id).order_by(ChatMessage.id.desc()).limit(limit)
        )
        return [ChatMessageOut.model_validate(row) for row in reversed(list(rows))]


def merge_profile(profile: dict, found: dict) -> dict:
    """Newest details win. A new budget replaces the old one; a new city drops a locality from another city."""
    merged = dict(profile)
    if "budget_min" in found or "budget_max" in found:
        merged.pop("budget_min", None)
        merged.pop("budget_max", None)
    if "city" in found and "locality" not in found and found["city"] != profile.get("city"):
        merged.pop("locality", None)
    merged.update(found)
    return merged


def missing_details(profile: dict) -> list[str]:
    known = {
        "city": "city" in profile,
        "bhk": "bhk" in profile,
        "budget": "budget_max" in profile or "budget_min" in profile,
        "timeline": "timeline_months" in profile,
        "loan": "loan_needed" in profile,
    }
    return [key for key in QUESTIONS if not known[key]]


def _recent_history(db: Session, visitor_id: str) -> list[ChatMessage]:
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.visitor_id == visitor_id)
        .order_by(ChatMessage.id.desc())
        .limit(HISTORY_MESSAGES)
    )
    return list(reversed(list(rows)))


def _search(profile: dict, found: dict, message: str, current: Listing | None) -> SearchResult:
    if current and not any(key in found for key in SEARCH_KEYS):
        # A question on a property page about that property ("is it ready to move?"): lead with it,
        # then up to two similar homes in the same city.
        similar = [
            item
            for item in filter_listings(city=current.city)
            if item.id != current.id and abs(item.bhk - current.bhk) <= 1
        ]
        similar.sort(key=lambda item: abs(item.price_inr - current.price_inr))
        return SearchResult([current, *similar[:2]])
    return find_listings(profile, message)


def _reply(
    message: str, history: list[ChatMessage], profile: dict, result: SearchResult, current: Listing | None
) -> tuple[str, str]:
    if llm.available():
        try:
            return llm.generate(SYSTEM_PROMPT, _llm_messages(message, history, profile, result, current)), "llm"
        except LLMError as exc:
            log.warning("LLM failed, replying from a template instead: %s", exc)
    return template_reply(profile, result, current), "template"


# ---------------------------------------------------------------- LLM mode


def _listing_facts(item: Listing) -> dict:
    return {
        "id": item.id,
        "project": item.project,
        "locality": item.locality,
        "city": item.city,
        "bhk": item.bhk,
        "type": item.property_type,
        "area_sqft": item.area_sqft,
        "price": format_price(item.price_inr),
        "status": item.status,
        "possession": item.possession,
        "amenities": item.amenities,
        "highlights": item.highlights,
    }


def _search_note(result: SearchResult) -> str:
    if not result.listings:
        return "No listings match. Say so and ask what they could change (budget, area or BHK)."
    if result.exact:
        return "These match everything the visitor asked for."
    return "No exact match. Loosened: " + ", ".join(result.relaxed) + "."


def _llm_messages(
    message: str, history: list[ChatMessage], profile: dict, result: SearchResult, current: Listing | None
) -> list[dict[str, str]]:
    messages = [{"role": row.role, "content": mask_pii(row.text)} for row in history]
    while messages and messages[0]["role"] != "user":  # a conversation must start with the visitor
        messages.pop(0)
    context = {
        "listings": [_listing_facts(item) for item in result.listings],
        "search_note": _search_note(result),
        "known_details": {key: value for key, value in profile.items() if key != "language"},
        "still_unknown": missing_details(profile),
        "current_page_listing": current.id if current else None,
    }
    content = (
        f"<context>\n{json.dumps(context, ensure_ascii=False, indent=1)}\n</context>\n\n"
        f"<visitor_message>\n{mask_pii(message)}\n</visitor_message>"
    )
    messages.append({"role": "user", "content": content})
    return messages


# ---------------------------------------------------------------- template mode (no key, or the LLM failed)


def _criteria_phrase(profile: dict) -> str:
    parts = []
    place = ", ".join(value for value in (profile.get("locality"), profile.get("city")) if value)
    if place:
        parts.append(f"in {place}")
    if profile.get("bhk"):
        parts.append(f"{profile['bhk']} BHK")
    low, high = profile.get("budget_min"), profile.get("budget_max")
    if low and high:
        parts.append(f"{format_price(low)} to {format_price(high)}")
    elif high:
        parts.append(f"under {format_price(high)}")
    elif low:
        parts.append(f"above {format_price(low)}")
    return (" " + ", ".join(parts)) if parts else ""


def _listing_line(item: Listing) -> str:
    status = item.status if item.status != "Under construction" else f"possession {item.possession}"
    return (
        f"{item.project}, {item.locality}: {item.bhk} BHK {item.property_type.lower()}, "
        f"{item.area_sqft:,} sq ft, {format_price(item.price_inr)} ({status.lower()})"
    )


def template_reply(profile: dict, result: SearchResult, current: Listing | None) -> str:
    lines: list[str] = []
    homes = result.listings
    if homes and current and homes[0].id == current.id:
        lines.append(f"About this home: {_listing_line(current)}.")
        if len(homes) > 1:
            lines.append("Similar homes nearby:")
            lines += [f"{number}. {_listing_line(item)}" for number, item in enumerate(homes[1:], start=1)]
    elif homes:
        noun = "home" if len(homes) == 1 else "homes"
        if result.exact:
            lines.append(f"Here {'is' if len(homes) == 1 else 'are'} {len(homes)} {noun}{_criteria_phrase(profile)}:")
        else:
            lines.append(
                f"I couldn't find an exact match{_criteria_phrase(profile)}, so here are the closest options "
                f"(I loosened the {' and '.join(result.relaxed)}):"
            )
        lines += [f"{number}. {_listing_line(item)}" for number, item in enumerate(homes, start=1)]
    elif any(key in profile for key in SEARCH_KEYS):
        lines.append(f"I couldn't find a home{_criteria_phrase(profile)} yet.")
    else:
        lines.append("Hi! I can help you find a home in Pune, Bengaluru, Hyderabad, Mumbai or Noida.")

    missing = missing_details(profile)
    if missing:
        lines.append(QUESTIONS[missing[0]])
    else:
        lines.append("Would you like a site visit? Send an enquiry from the property page and our team will call you.")
    return "\n".join(lines)
