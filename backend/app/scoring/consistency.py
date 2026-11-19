"""Says versus does: does what a visitor tells us match the homes they actually open?

A mismatch never changes a label, because real buyers do explore: someone who says "under ₹50 L" may be testing what
₹1.2 Cr buys. It is a question for the sales call, shown under "Why this label" and in the lead brief.
"""

import re
import statistics

from ..ai.extract import extract_details
from ..listings import format_price, get_listing
from ..schemas import Listing

MIN_HOMES = 3  # fewer homes than this say too little about what someone is really looking for
MAX_MESSAGES = 20
_PROPERTY_PATH = re.compile(r"^/property/([A-Za-z0-9-]+)")


def viewed_homes(record: dict) -> list[Listing]:
    """Each home this visitor opened, once."""
    seen: list[str] = []
    for session in record.get("sessions") or []:
        for event in session.get("events") or []:
            if event.get("type") == "property_view" and (event.get("props") or {}).get("listing_id"):
                seen.append(str(event["props"]["listing_id"]).upper())
            elif event.get("type") == "page_view" and (match := _PROPERTY_PATH.match(event.get("path") or "")):
                seen.append(match.group(1).upper())
    return [home for home in (get_listing(item) for item in dict.fromkeys(seen)) if home]


def _budget(profile: dict, homes: list[Listing]) -> dict | None:
    high, low = profile.get("budget_max"), profile.get("budget_min")
    if not (high or low) or len(homes) < MIN_HOMES:
        return None
    prices = [home.price_inr for home in homes]
    typical = round(statistics.median(prices))
    if high and min(prices) > high * 1.15 and typical > high * 1.4:
        return {"check": "budget", "ok": False, "text": f"Says under {format_price(high)} but opened homes around {format_price(typical)}"}
    if low and max(prices) < low * 0.85 and typical < low * 0.6:
        return {"check": "budget", "ok": False, "text": f"Says above {format_price(low)} but opened homes around {format_price(typical)}"}
    return {"check": "budget", "ok": True, "text": "The homes they opened fit the budget they gave"}


def _city(profile: dict, homes: list[Listing]) -> dict | None:
    city = profile.get("city")
    if not city or len(homes) < MIN_HOMES:
        return None
    cities = sorted({home.city for home in homes})
    if city in cities:
        return {"check": "city", "ok": True, "text": f"Opened homes in {city}, the city they named"}
    return {"check": "city", "ok": False, "text": f"Says {city} but opened homes only in {', '.join(cities)}"}


def _bhk(profile: dict, homes: list[Listing]) -> dict | None:
    bhk = profile.get("bhk")
    if not bhk or len(homes) < MIN_HOMES:
        return None
    sizes = sorted({home.bhk for home in homes})
    if bhk in sizes:
        return {"check": "bhk", "ok": True, "text": f"Opened {bhk} BHK homes, as they said"}
    return {"check": "bhk", "ok": False, "text": f"Asked for a {bhk} BHK but opened only {', '.join(f'{size} BHK' for size in sizes)} homes"}


def _purpose(record: dict) -> dict | None:
    texts = [lead.get("message") or "" for lead in record.get("leads") or []]
    texts += [message.get("text") or "" for message in record.get("chat") or []]
    stated = {extract_details(text).get("purpose") for text in texts[-MAX_MESSAGES:] if text.strip()} - {None}
    if len(stated) == 2:
        return {"check": "purpose", "ok": False, "text": "Says the home is both to live in and an investment"}
    return None


def consistency_checks(record: dict) -> list[dict]:
    """[{"check": "budget", "ok": false, "text": "..."}] for whatever can be compared; mismatches come first."""
    profile, homes = record.get("profile") or {}, viewed_homes(record)
    checks = [_budget(profile, homes), _city(profile, homes), _bhk(profile, homes), _purpose(record)]
    return sorted((check for check in checks if check), key=lambda check: check["ok"])
