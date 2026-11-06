"""Pick buyer details out of a chat message with simple patterns: English, Hinglish and basic Hindi.

    "3BHK under 90L in Pune?"            -> {"city": "Pune", "bhk": 3, "budget_max": 9000000, ...}
    "Pune mein 90 lakh tak 3BHK chahiye" -> the same

Member C upgrades this to LLM JSON extraction in Week 2. Keep these output keys (all optional):
city, locality, bhk, budget_min, budget_max (INR), timeline_months, loan_needed, language ("en", "hinglish", "hi").
"""

import re

from ..listings import locality_index

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
    details["language"] = detect_language(message)
    return details


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
