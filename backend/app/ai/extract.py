"""Pick buyer details out of a chat message: patterns first (English, Hinglish and basic Hindi), then the LLM.

    "3BHK under 90L in Pune?"            -> {"city": "Pune", "bhk": 3, "budget_max": 9000000, ...}
    "Pune mein 90 lakh tak 3BHK chahiye" -> the same

smart_extract() runs the patterns and, when an LLM key is set, lets the LLM read the message with the last few
turns ("same budget but in Bengaluru", "80-85 lakh ke beech", "teen BHK"). Every LLM value is checked before it is
used, and any LLM failure falls back to the patterns. Output keys (all optional): city, locality, bhk, budget_min,
budget_max (INR), timeline_months, loan_needed, purpose ("own_use" / "investment"), language ("en", "hinglish", "hi").
"""

import logging
import math
import re

from ..listings import locality_index
from .llm_client import LLMError, llm
from .privacy import mask_pii

log = logging.getLogger("leadops.extract")

LAKH = 100_000
CRORE = 10_000_000
MIN_BUDGET, MAX_BUDGET = 5 * LAKH, 100 * CRORE  # amounts outside this range aren't home budgets

_CITY_ALIASES = {
    "Pune": ["pune", "poona", "pcmc", "पुणे"],
    "Bengaluru": ["bengaluru", "bangalore", "blr", "बेंगलुरु", "बेंगलुरू", "बैंगलोर"],
    "Hyderabad": ["hyderabad", "hyd", "secunderabad", "हैदराबाद"],
    "Mumbai": ["mumbai", "bombay", "navi mumbai", "mmr", "मुंबई"],
    "Noida": ["noida", "greater noida", "नोएडा"],
}
CITY_LOOKUP = {alias: city for city, aliases in _CITY_ALIASES.items() for alias in aliases}

# Other names people use for localities in the listings (the listings' own locality names match too).
LOCALITY_ALIASES = {
    "thane": "Thane West",
    "hinjewadi": "Hinjewadi Phase 1",
    "hinjawadi": "Hinjewadi Phase 1",
    "e city": "Electronic City",
    "ecity": "Electronic City",
    "e-city": "Electronic City",
    "sarjapur": "Sarjapur Road",
    "greater noida west": "Noida Extension",
}

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5,
}  # fmt: skip
_BHK = re.compile(
    r"(?<![\w.])([1-6]|one|two|three|four|five|ek|do|teen|chaa?r|paanch)\s*-?\s*"
    r"(?:bhk|b\.h\.k\.?|bed(?:room)?s?|br|बीएचके|बेडरूम)(?![a-z])"
)
_SECTOR = re.compile(r"\bsec(?:tor)?[\s-]*(\d{1,3})\b")

_NUM = r"(\d+(?:\.\d+)?)"
_UNIT = r"(lakhs?|lacs?|lkh|lk|l|crores?|crs?|karod|karor|लाख|करोड़|करोड)"
_AMOUNT = re.compile(rf"(?:₹|rs\.?|inr)?\s*{_NUM}\s*{_UNIT}(?![a-z])")
_RANGE = re.compile(rf"{_NUM}\s*{_UNIT}?\s*(?:-|to|se|and)\s*{_NUM}\s*{_UNIT}(?![a-z])")
# Full rupee amounts: "₹85,00,000", "rs 8500000", or Indian digit grouping "85,00,000".
_RUPEES = re.compile(r"(?:₹|rs\.?|inr|rupees)\s*(\d{1,3}(?:,\d{2,3})+|\d{6,9})(?![\d,])|(?<![\d,])(\d{1,2}(?:,\d{2})+,\d{3})(?![\d,])")

_MIN_BEFORE = re.compile(r"(above|over|more than|min(?:imum)?|at ?least|starting(?: from)?|from|>)\s*$")
_MAX_BEFORE = re.compile(r"(under|below|upto|up to|within|max(?:imum)?|less than|not more than|budget|around|about|approx(?:imately)?|<)\s*(?:is|of)?\s*$")
_MIN_AFTER = re.compile(r"^\s*(se (?:upar|zyada|jyada|adhik)|or more|plus|\+|से ज़्यादा|से ऊपर)")
_MAX_AFTER = re.compile(r"^\s*(tak|tk|ke andar|ke under|se kam|or less|max|तक|से कम)")

_MONTHS = re.compile(r"(\d{1,2})\s*(?:months?|mnths?|mahine|mahino|mahina|महीने|महीनों|महीना)")
_YEARS = re.compile(r"(\d|a|one|ek)\s*(?:years?|yrs?|saal|sal|साल)(?![a-z])")
_SOON = re.compile(r"\b(?:immediately|asap|urgent(?:ly)?|right away|right now|turant|jaldi)\b|तुरंत|जल्दी")
_NEXT_MONTH = re.compile(r"\bnext month\b|agle mahine|अगले महीने")
_NEXT_YEAR = re.compile(r"\bnext year\b|agle saal|अगले साल")
_LOAN_WORDS = re.compile(r"\b(?:emi|loan|tenure|interest)\b|लोन")

_NO_LOAN = re.compile(
    r"\b(?:no loan|without (?:a |any )?loan|(?:don'?t|do not|won'?t) need (?:a |any )?loan|fully? (?:cash|payment)"
    r"|cash (?:buyer|payment|down)|self[- ]funded|loan nahi[n]?|loan ki zarurat nahi)\b|लोन नहीं"
)
_LOAN = re.compile(r"\b(?:home loan|housing loan|loan|emi|finance|financing|mortgage)\b|लोन")

_INVESTMENT = re.compile(
    r"\b(?:invest(?:ment|ing)?|rental (?:income|yield)|roi|appreciation|resale value|rent (?:it )?out)\b"
    r"|investment ke liye|nivesh|निवेश"
)
_OWN_USE = re.compile(
    r"\b(?:own use|self use|end use|to live in|for (?:my|our) family|live there|stay there|khud ke liye|apne liye"
    r"|rehne ke liye)\b|रहने के लिए|अपने लिए|खुद के लिए"
)

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_HINGLISH_WORDS = {
    "mein", "mujhe", "chahiye", "tak", "hai", "kya", "ka", "ki", "ke", "se", "aur", "nahi", "ghar", "lena",
    "kitna", "kitne", "wala", "wali", "hoga", "batao", "dikhao", "accha", "acha", "bhi", "koi", "kuch", "hum",
}  # fmt: skip


def extract_details(message: str) -> dict:
    """Buyer details found in one message. Keys are only present when found (language is always set)."""
    text = _normalise(message)
    details: dict = {}

    locality = _find_locality(text)
    if locality:
        details["locality"] = locality
        details["city"] = locality_index()[locality.casefold()].city
    elif city := _find_first(text, CITY_LOOKUP):
        details["city"] = city

    if bhk := _find_bhk(text):
        details["bhk"] = bhk
    details.update(_find_budget(text))
    if (months := _find_timeline(text)) is not None:
        details["timeline_months"] = months
    if (loan := _find_loan(text)) is not None:
        details["loan_needed"] = loan
    if _INVESTMENT.search(text):
        details["purpose"] = "investment"
    elif _OWN_USE.search(text):
        details["purpose"] = "own_use"
    details["language"] = detect_language(message)
    return details


# ---------------------------------------------------------------- LLM extraction

CITIES = list(_CITY_ALIASES)
PURPOSES = ("own_use", "investment")
LANGUAGES = ("en", "hinglish", "hi")

EXTRACTION_SYSTEM = """\
You read one message from a visitor on an Indian real estate website and pick out the home-buying details it states.

Use null for anything the latest message doesn't say. Earlier messages are only context, for replies such as \
"same budget, but in Bengaluru".
- city: Pune, Bengaluru, Hyderabad, Mumbai or Noida (Bangalore is Bengaluru, Bombay is Mumbai).
- locality: a neighbourhood the visitor names, as written.
- bhk: the number of bedrooms.
- budget_min / budget_max: rupees as whole numbers (90 lakh = 9000000, 1.2 crore = 12000000). "Under 90L" is \
budget_max only; "80 to 90 lakh" sets both.
- timeline_months: when they want to move in, in months ("immediately" = 1, "next year" = 12).
- loan_needed: true if they need a home loan, false if they say they don't.
- purpose: "own_use" to live in, "investment" to invest or rent out.
- language: "en" (English), "hinglish" (Hindi in Roman script) or "hi" (Hindi in Devanagari).
"[phone]" and "[email]" are details hidden for privacy."""


def _nullable(schema: dict) -> dict:
    return {"anyOf": [schema, {"type": "null"}]}


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "city": _nullable({"type": "string", "enum": CITIES}),
        "locality": _nullable({"type": "string"}),
        "bhk": _nullable({"type": "integer"}),
        "budget_min": _nullable({"type": "integer"}),
        "budget_max": _nullable({"type": "integer"}),
        "timeline_months": _nullable({"type": "integer"}),
        "loan_needed": _nullable({"type": "boolean"}),
        "purpose": _nullable({"type": "string", "enum": list(PURPOSES)}),
        "language": {"type": "string", "enum": list(LANGUAGES)},
    },
    "required": ["city", "locality", "bhk", "budget_min", "budget_max", "timeline_months", "loan_needed", "purpose", "language"],
    "additionalProperties": False,
}


def _whole(value) -> int | None:
    """An integer that isn't a bool (JSON true would otherwise pass as 1), NaN or a fraction."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return int(value) if value == int(value) else None


def clean_details(raw: dict) -> dict:
    """Only the values that make sense: a known city or listing locality, BHK 1-6, budgets between 5 L and 100 Cr,
    a move-in within 5 years, and the allowed words for purpose and language."""
    found: dict = {}
    if isinstance(raw.get("city"), str):
        name = raw["city"].strip().casefold()
        city = CITY_LOOKUP.get(name) or next((item for item in CITIES if item.casefold() == name), None)
        if city:
            found["city"] = city
    if isinstance(raw.get("locality"), str) and raw["locality"].strip():
        if locality := _find_locality(_normalise(raw["locality"])):
            found["locality"] = locality
            found["city"] = locality_index()[locality.casefold()].city  # the locality decides the city
    if (bhk := _whole(raw.get("bhk"))) is not None and 1 <= bhk <= 6:
        found["bhk"] = bhk
    budgets = {key: _whole(raw.get(key)) for key in ("budget_min", "budget_max")}
    budgets = {key: value for key, value in budgets.items() if value is not None and MIN_BUDGET <= value <= MAX_BUDGET}
    if len(budgets) == 2 and budgets["budget_min"] > budgets["budget_max"]:
        budgets = {"budget_min": budgets["budget_max"], "budget_max": budgets["budget_min"]}
    found.update(budgets)
    if (months := _whole(raw.get("timeline_months"))) is not None and 0 <= months <= 60:
        found["timeline_months"] = months
    if isinstance(raw.get("loan_needed"), bool):
        found["loan_needed"] = raw["loan_needed"]
    if raw.get("purpose") in PURPOSES:
        found["purpose"] = raw["purpose"]
    if raw.get("language") in LANGUAGES:
        found["language"] = raw["language"]
    return found


def extract_with_llm(message: str, history: list[str]) -> dict:
    """The details the LLM finds in this message, checked. Phones and emails are masked first; raises LLMError."""
    earlier = "\n".join(f"- {mask_pii(text)}" for text in history[-4:])
    content = (f"<earlier_messages>\n{earlier}\n</earlier_messages>\n\n" if earlier else "") + (
        f"<latest_message>\n{mask_pii(message)}\n</latest_message>"
    )
    raw = llm.generate_json(EXTRACTION_SYSTEM, [{"role": "user", "content": content}], EXTRACTION_SCHEMA, max_tokens=512)
    return clean_details(raw)


def smart_extract(message: str, history: list[str] | None = None) -> dict:
    """The patterns' details, improved by the LLM when a key is set. history: the visitor's earlier messages."""
    found = extract_details(message)
    if not llm.available():
        return found
    try:
        from_llm = extract_with_llm(message, history or [])
    except LLMError as exc:
        log.warning("LLM extraction failed, using the patterns only: %s", exc)
        return found
    merged = {**found, **from_llm}  # the LLM wins where it found something; a null never erases a pattern's find
    if "budget_min" in from_llm or "budget_max" in from_llm:  # never mix one extractor's minimum with the other's maximum
        for key in ("budget_min", "budget_max"):
            merged.pop(key, None)
            if key in from_llm:
                merged[key] = from_llm[key]
    if _DEVANAGARI.search(message):
        merged["language"] = "hi"
    return merged


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


def profile_from_messages(messages: list[str]) -> dict:
    """Buyer details from a whole conversation, oldest message first (as the assistant builds them live)."""
    profile: dict = {}
    for message in messages:
        profile = merge_profile(profile, extract_details(message))
    return profile


def detect_language(message: str) -> str:
    if _DEVANAGARI.search(message):
        return "hi"
    words = set(re.findall(r"[a-z]+", message.casefold()))
    return "hinglish" if len(words & _HINGLISH_WORDS) >= 2 else "en"


def _normalise(message: str) -> str:
    text = message.casefold().replace("–", "-").replace("—", "-").replace("₹", " ₹")
    return re.sub(r"\s+", " ", text).strip()


def _find_first(text: str, lookup: dict[str, str]) -> str | None:
    """Value of the alias that appears first in the text (the longer alias wins at the same spot)."""
    best: tuple[tuple[int, int], str] | None = None
    for alias, value in lookup.items():
        pattern = rf"(?<!\w){re.escape(alias)}(?!\w)" if alias.isascii() else re.escape(alias)
        match = re.search(pattern, text)
        if match:
            rank = (match.start(), -len(alias))
            if best is None or rank < best[0]:
                best = (rank, value)
    return best[1] if best else None


def _find_locality(text: str) -> str | None:
    index = locality_index()
    lookup = {name: listing.locality for name, listing in index.items()}
    lookup.update({alias.casefold(): name for alias, name in LOCALITY_ALIASES.items()})
    if found := _find_first(text, lookup):
        return found
    for match in _SECTOR.finditer(text):  # "sec 150", "sector-150"
        name = f"sector {int(match.group(1))}"
        if name in index:
            return index[name].locality
    return None


def _find_bhk(text: str) -> int | None:
    match = _BHK.search(text)
    if not match:
        return None
    word = match.group(1)
    return int(word) if word.isdigit() else _WORD_NUMBERS.get(word.replace("chaar", "char"))


def _to_inr(number: str, unit: str | None) -> int:
    value = float(number)
    if unit and (unit.startswith(("c", "k")) or unit.startswith("कर")):
        return round(value * CRORE)
    return round(value * LAKH)


def _find_budget(text: str) -> dict:
    found: dict = {}
    taken: list[tuple[int, int]] = []

    # A range: "between 60 and 80 lakh", "80-90L", "80 lakh se 1 crore".
    for match in _RANGE.finditer(text):
        low_unit = match.group(2) or match.group(4)
        low, high = _to_inr(match.group(1), low_unit), _to_inr(match.group(3), match.group(4))
        if MIN_BUDGET <= min(low, high) and max(low, high) <= MAX_BUDGET and low != high:
            found["budget_min"], found["budget_max"] = min(low, high), max(low, high)
            taken.append(match.span())
            break

    # Single amounts: "under 90L", "1.2 cr tak", "above 1 crore", "₹85,00,000".
    amounts = [(m.span(), _to_inr(m.group(1), m.group(2))) for m in _AMOUNT.finditer(text)]
    amounts += [(m.span(), int((m.group(1) or m.group(2)).replace(",", ""))) for m in _RUPEES.finditer(text)]
    for (start, end), value in sorted(amounts):
        if any(start < t_end and end > t_start for t_start, t_end in taken):
            continue  # already part of the range
        if not MIN_BUDGET <= value <= MAX_BUDGET:
            continue
        before, after = text[max(0, start - 25) : start], text[end : end + 20]
        if _MIN_BEFORE.search(before) or _MIN_AFTER.search(after):
            found["budget_min"] = value
        else:  # "under", "tak", "budget 90L", or a bare amount: treat it as the upper limit
            found["budget_max"] = value
    return found


def _find_timeline(text: str) -> int | None:
    if _SOON.search(text):
        return 1
    if _NEXT_MONTH.search(text):
        return 1
    if match := _MONTHS.search(text):
        return int(match.group(1))
    if _NEXT_YEAR.search(text):
        return 12
    # "2 years" is a move-in plan, unless the message is about a loan ("EMI for 20 years").
    if (match := _YEARS.search(text)) and not _LOAN_WORDS.search(text):
        word = match.group(1)
        years = int(word) if word.isdigit() else 1
        if 1 <= years <= 5:
            return years * 12
    return None


def _find_loan(text: str) -> bool | None:
    if _NO_LOAN.search(text):
        return False
    if _LOAN.search(text):
        return True
    return None
