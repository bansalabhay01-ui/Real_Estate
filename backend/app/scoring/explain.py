"""Plain-language reasons: the rules that fired, the ML model's strongest factors and the biggest intent points.

These are template sentences. Week 3 adds an LLM-written summary on top (every LLM call goes through llm_client.py).
"""

import math

from .features import MODEL_FEATURES
from .model import HumanCheck
from .rules import BOT, CERTAIN, JUNK, STRONG, Signal

MAX_REASONS = 5


def known(value) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value


def bot_factor_text(name: str, value: float | None) -> str | None:
    """Why this feature made the visitor look like a bot. None when there's nothing worth saying."""
    if value is None:
        return None
    plural = "" if value == 1 else "s"
    match name:
        case "activity_coverage":
            return "No mouse, touch or keyboard activity at all" if value == 0 else (
                f"Mouse or touch activity in only {value:.0%} of the visit" if value < 0.5 else None)
        case "mouse_px_per_move":
            return f"The mouse jumped about {value:.0f} pixels at a time; people move in small steps" if value > 35 else None
        case "median_dwell_s":
            return f"Spent only {value:.1f} seconds per page" if value < 5 else None
        case "fast_pages":
            return f"Left {value:.0f} page{plural} within 2 seconds" if value >= 2 else None
        case "pages_per_minute":
            return f"Opened {value:.0f} pages a minute" if value >= 6 else None
        case "viewport_matches_screen":
            return "The window is exactly the size of the screen, a headless-browser default" if value == 1 else None
        case "timezone_utc":
            return "The browser's time zone is UTC, as on servers" if value == 1 else None
        case "browser_languages":
            return "The browser lists no languages" if value == 0 else None
        case "hardware_concurrency":
            return f"The device reports only {value:.0f} processor core{plural}" if value <= 2 else None
        case "ip_visitors":
            return f"{value:.0f} visitors came from the same IP address within a day" if value >= 3 else None
        case "min_fill_s":
            return f"Filled in the enquiry form in {value:.1f} seconds" if value < 10 else None
        case "seconds_to_first_lead":
            return f"Sent an enquiry {value:.0f} seconds after arriving" if value < 60 else None
        case "event_gap_cv":
            return "Its actions came at machine-regular intervals" if value < 0.5 else None
        case "scrolls_per_page":
            return "Never scrolled" if value == 0 else None
        case "untrusted_clicks":
            return f"Made {value:.0f} scripted click{plural}" if value >= 1 else None
        case "touch_mismatch":
            return "A phone browser without a touch screen" if value == 1 else None
        case "duration_s":
            return f"The whole visit took {value:.0f} seconds" if value < 20 else None
        case "page_views":
            return f"Opened {value:.0f} pages" if value >= 8 else None
    return None  # the rules already explain webdriver, user agent, honeypot and no-browsing enquiries


def bot_reasons_from_model(check: HumanCheck, features: dict, limit: int = 3) -> list[str]:
    found = []
    for name, contribution in sorted(check.contributions.items(), key=lambda item: -item[1]):
        if contribution <= 0.1:
            break
        if text := bot_factor_text(name, known(features.get(name))):
            found.append(text)
        if len(found) == limit:
            break
    return found


def human_factors(check: HumanCheck, features: dict, limit: int = 8) -> list[dict]:
    """The model's strongest factors either way, for the dashboard's human-check panel."""
    strongest = sorted(check.contributions.items(), key=lambda item: -abs(item[1]))[:limit]
    return [
        {
            "feature": name,
            "label": MODEL_FEATURES.get(name, name.replace("_", " ")),
            "value": known(features.get(name)),
            "contribution": round(value, 3),
            "towards": "bot" if value > 0 else "human",
        }
        for name, value in strongest
    ]


def _lower_first(text: str) -> str:
    """"Checked the EMI" -> "checked the EMI", but "EMI checked" stays as it is."""
    return text[0].lower() + text[1:] if len(text) > 1 and text[1].islower() else text


def _by_strength(signals: list[Signal]) -> list[str]:
    return [s.reason for s in signals if s.strength == CERTAIN] + [s.reason for s in signals if s.strength == STRONG]


def reasons_for(label: str, *, signals: list[Signal], check: HumanCheck, features: dict, points: list,
                intent: int, visitor_type: dict | None = None) -> list[str]:
    """Up to five reasons for this label, the most important first."""
    bot = [s for s in signals if s.layer == BOT]
    junk = [s for s in signals if s.layer == JUNK]
    buying = [point.detail for point in sorted(points, key=lambda point: -point.points)]
    type_reason = [visitor_type["reason"]] if visitor_type and visitor_type.get("reason") else []
    unsure = f"Only {check.human_prob:.0%} likely to be a person, judging by how it browses"

    if label == "Bot":
        found = _by_strength(bot) or [unsure]
        found += bot_reasons_from_model(check, features)
    elif label == "Junk":
        found = _by_strength(junk) + type_reason
    elif label == "Review":
        found = _by_strength([s for s in signals if s.strength == STRONG or s.layer == JUNK]) + type_reason
        if check.human_prob < 0.5:
            found.append(unsure)
            found += bot_reasons_from_model(check, features, limit=2)
        if buying:
            found.append(("Strong buying signals: " if intent >= 70 else "Buying signals: ") + _lower_first(buying[0]))
            found += buying[1:2]
    else:
        found = buying[:4] or ["Only a quick look so far"]
    unique = list(dict.fromkeys(found))  # keep the order, drop repeats
    return unique[:MAX_REASONS]


def summary_line(label: str, reasons: list[str]) -> str:
    """"Hot: 3 visits over 2 days; checked the EMI on a ₹85 L home; ..." (the LLM writes a better one in Week 3)."""
    if not reasons:
        return label
    parts = [reasons[0]] + [_lower_first(reason) for reason in reasons[1:3]]
    return f"{label}: " + "; ".join(part.rstrip(".") for part in parts)
