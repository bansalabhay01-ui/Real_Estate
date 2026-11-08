"""Visitor type: end buyer, investor, tenant, broker or spam, from what the visitor wrote (enquiries and chat).

With an LLM key, the LLM reads the visitor's messages (phones and emails masked) and returns a type, a confidence
and a one-line reason. Without a key, or if the call fails, keyword rules do the same job. Names never reach the LLM:
only the messages and the buyer details are sent. A confident broker, spam or tenant makes the visitor Junk
(scoring/combine.py); investors and end buyers are scored on intent like everyone else.
"""

import logging
import re

from ..scoring.rules import check_message
from .llm_client import LLMError, llm
from .privacy import mask_pii

log = logging.getLogger("leadops.classify")

TYPES = ("end_buyer", "investor", "tenant", "broker", "spam")
REASONS = {
    "end_buyer": "Buying a home to live in",
    "investor": "Buying as an investment",
    "tenant": "Wants to rent, not buy",
    "broker": "Writes like a broker looking for inventory or commission",
    "spam": "The messages advertise something else",
}
MAX_TEXTS = 10

_INVESTOR = re.compile(
    r"\b(?:invest(?:ment|ing|or)?|rental (?:income|yield)|roi|appreciation|resale value|capital gains?|rent (?:it )?out)\b"
    r"|निवेश",
    re.IGNORECASE,
)
_TENANT = re.compile(
    r"\b(?:on rent|for rent|rental basis|monthly rent|rent per month|rent of|lease|leasing|paying guest|pg|tenant|"
    r"rent pe|rent par|kiraye|kiraya|kiraaye)\b|किराए|किराये",
    re.IGNORECASE,
)
_BUYER = re.compile(
    r"\b(?:to live|live in|for (?:my|our) family|move in|shift|site visit|home loan|possession|ready to move)\b"
    r"|rehne|shift karna",
    re.IGNORECASE,
)

CLASSIFY_SYSTEM = """\
You sort visitors of an Indian real estate sales website by what they wrote to the sales team or the website's \
assistant. Types:
- end_buyer: wants to buy a home to live in.
- investor: wants to buy, for rental income, resale or appreciation.
- tenant: wants to rent a home, not buy one.
- broker: a broker, agent or channel partner fishing for inventory, prices or commission for their own clients. A \
buyer asking whether *they* must pay brokerage is not a broker.
- spam: advertising or anything unrelated to buying a home.
- unknown: not enough to tell.
confidence is 0 to 1. reason is one short sentence in English that doesn't quote names or numbers from the messages.
"[phone]" and "[email]" are details hidden for privacy."""

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": [*TYPES, "unknown"]},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["type", "confidence", "reason"],
    "additionalProperties": False,
}


def with_keywords(texts: list[str], profile: dict) -> dict | None:
    """The keyword version: spam and broker phrases (shared with rules.py), then rent, investment and buying words."""
    joined = "\n".join(texts)
    codes = {signal.code for text in texts for signal in check_message(text)}
    if "spam_message" in codes:
        kind, confidence = "spam", 0.9
    elif "broker_message" in codes:
        kind, confidence = "broker", 0.9
    elif _INVESTOR.search(joined) or profile.get("purpose") == "investment":
        kind, confidence = "investor", 0.7
    elif _TENANT.search(joined):
        kind, confidence = "tenant", 0.8
    elif _BUYER.search(joined) or profile.get("purpose") == "own_use" or profile.get("bhk") or profile.get("budget_max"):
        kind, confidence = "end_buyer", 0.6
    else:
        return None
    return {"type": kind, "confidence": confidence, "reason": REASONS[kind], "source": "keywords"}


def with_llm(texts: list[str], profile: dict) -> dict | None:
    """The LLM version: raises LLMError if the call fails or the answer makes no sense."""
    known = {key: value for key, value in profile.items() if key != "language"}
    lines = "\n".join(f"- {mask_pii(text)[:600]}" for text in texts)
    content = f"<buyer_details>{known}</buyer_details>\n\n<messages>\n{lines}\n</messages>"
    raw = llm.generate_json(CLASSIFY_SYSTEM, [{"role": "user", "content": content}], CLASSIFY_SCHEMA, max_tokens=256)
    kind = raw.get("type")
    if kind == "unknown":
        return None
    if kind not in TYPES:
        raise LLMError(f"unexpected visitor type {kind!r}")
    confidence = raw.get("confidence")
    confidence = min(1.0, max(0.0, float(confidence))) if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) else 0.5
    reason = str(raw.get("reason") or REASONS[kind]).strip()[:140] or REASONS[kind]
    return {"type": kind, "confidence": round(confidence, 2), "reason": reason, "source": "llm"}


def classify(texts: list[str], profile: dict | None = None, *, use_llm: bool = True) -> dict | None:
    """{"type", "confidence", "reason", "source"} for a visitor's messages, or None when there's nothing to go on."""
    texts = [text.strip() for text in texts if text and text.strip()][-MAX_TEXTS:]
    profile = profile or {}
    if not texts:
        return None
    if use_llm and llm.available():
        try:
            return with_llm(texts, profile)
        except LLMError as exc:
            log.warning("LLM classification failed, using keywords: %s", exc)
    return with_keywords(texts, profile)
