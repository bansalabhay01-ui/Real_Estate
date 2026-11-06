"""Numbers that describe one visitor, for the ML model (human check), the rules and the intent score.

The same code builds them for training (ml/train.py, from simulator files) and for live scoring (engine.py, from
the database), so the model sees the same numbers in both places. Both start from a *visitor record*:

    {
      "visitor_id": "...", "user_agent": "...", "context": {...},          # the latest SDK context
      "sessions": [{"session_id": "...", "ip": "...", "events": [...]}],   # oldest first, events as the SDK sends them
      "leads": [{"session_id", "name", "phone", "email", "message", "honeypot", "form_fill_ms", "client_ts", "ip"}],
      "chat": [{"session_id": "...", "text": "...", "ts": 1793697300000}],  # what the visitor wrote to the assistant
      "profile": {...},                                                    # buyer details from chat
      "network": {"ip_visitors": 1, "phone_visitors": 1},                  # counts that need the other visitors
    }

Times are browser milliseconds (each event's "ts"). Unknown values are NaN, which LightGBM treats as missing.

The human check only uses MODEL_FEATURES: *how* someone browses, never *what* they are interested in, so a casual
browser isn't mistaken for a bot and a bot can't pass by opening the EMI calculator.
"""

import math
import re
import statistics
from collections import Counter, defaultdict

from ..listings import get_listing
from ..utils import automation_hints, device_from_ua
from .rules import phone_digits

NAN = float("nan")
DAY_MS = 86_400_000
IST_OFFSET_MS = 19_800_000  # days are counted in Indian time (UTC+5:30)
FAST_PAGE_MS = 2000
IP_WINDOW_MS = DAY_MS  # visitors sharing an IP are counted over the last 24 hours
UTC_ZONES = {"UTC", "Etc/UTC", "Etc/UCT", "UCT", "GMT", "Etc/GMT", "Universal", "Etc/Universal", "Zulu", "Etc/Zulu"}
_PROPERTY_PATH = re.compile(r"^/property/([A-Za-z0-9-]+)")

# The ML model's inputs, in column order, with plain words for explanations.
MODEL_FEATURES: dict[str, str] = {
    "webdriver": "automation flag (navigator.webdriver)",
    "automation_ua": "automation user agent",
    "no_user_agent": "no user agent",
    "browser_languages": "browser languages",
    "timezone_utc": "time zone set to UTC",
    "viewport_matches_screen": "window exactly the size of the screen",
    "hardware_concurrency": "processor cores",
    "touch_mismatch": "phone browser without a touch screen",
    "page_views": "pages opened",
    "duration_s": "time on the site",
    "pages_per_minute": "pages per minute",
    "median_dwell_s": "time per page",
    "fast_pages": "pages left within 2 seconds",
    "scrolls_per_page": "scrolling",
    "activity_coverage": "share of time with mouse or touch activity",
    "mouse_moves_per_min": "mouse movement",
    "mouse_px_per_move": "size of each mouse jump",
    "touches_per_min": "touches",
    "keys": "key presses",
    "trusted_clicks": "real clicks",
    "untrusted_clicks": "scripted clicks",
    "event_gap_cv": "how irregular the timing is",
    "honeypot": "hidden form field",
    "min_fill_s": "time to fill in the form",
    "lead_without_pageviews": "enquiry without browsing",
    "seconds_to_first_lead": "time from arrival to enquiry",
    "ip_visitors": "visitors sharing the IP address",
}


def _num(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return NAN
    return float(value)


def _count(value) -> float:
    number = _num(value)
    return 0.0 if math.isnan(number) else max(0.0, number)


def _size(text) -> tuple[int, int] | None:
    match = re.fullmatch(r"(\d+)x(\d+)", str(text or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _cv(values: list[float]) -> float:
    mean = statistics.fmean(values)
    return statistics.pstdev(values) / mean if mean > 0 else 0.0


def timed_events(session: dict) -> list[dict]:
    """A session's events with a timestamp, in time order (ties keep the order they were sent in)."""
    events = [event for event in session.get("events") or [] if isinstance(event.get("ts"), (int, float))]
    return sorted(events, key=lambda event: event["ts"])


def pages(events: list[dict]) -> list[dict]:
    """One entry per page view: path, start, dwell (ms) and done (False while the page is still open)."""
    found: list[dict] = []
    current = None
    for event in events:
        kind, path = event.get("type"), event.get("path") or ""
        if kind == "page_view":
            if current is not None and current["dwell"] is None:
                current["dwell"], current["done"] = max(0, event["ts"] - current["start"]), True
            current = {"path": path, "start": event["ts"], "dwell": None, "done": False}
            found.append(current)
        elif kind == "page_leave" and current is not None and current["dwell"] is None and current["path"] == path:
            visible = _num((event.get("props") or {}).get("duration_ms"))
            current["dwell"] = visible if not math.isnan(visible) else max(0, event["ts"] - current["start"])
            current["done"] = True
    last = events[-1]["ts"] if events else 0
    for page in found:
        if page["dwell"] is None:  # still open: the time so far
            page["dwell"] = max(0, last - page["start"])
    return found


def visitor_features(record: dict) -> dict[str, float]:
    """Every number for one visitor: MODEL_FEATURES plus the inputs of the rules and the intent score."""
    context = record.get("context") or {}
    agent = record.get("user_agent") or context.get("user_agent")
    leads = record.get("leads") or []
    network = record.get("network") or {}
    f: dict[str, float] = {}

    # ---- the browser
    f["webdriver"] = 1.0 if context.get("webdriver") is True else 0.0
    f["automation_ua"] = 1.0 if "automation_user_agent" in automation_hints(agent, context) else 0.0
    f["no_user_agent"] = 0.0 if agent else 1.0
    f["browser_languages"] = _num(context.get("languages"))
    zone = context.get("timezone")
    f["timezone_utc"] = NAN if not zone else float(zone in UTC_ZONES)
    screen, viewport = _size(context.get("screen")), _size(context.get("viewport"))
    f["viewport_matches_screen"] = float(screen == viewport) if screen and viewport else NAN
    f["hardware_concurrency"] = _num(context.get("hardware_concurrency"))
    touchscreen = device_from_ua(agent) in ("mobile", "tablet")
    f["touch_mismatch"] = 1.0 if touchscreen and context.get("touch_points") == 0 else 0.0

    # ---- how they browse
    counts: Counter = Counter()
    every_page: list[dict] = []
    gaps: list[float] = []
    starts: list[float] = []
    total_ms = 0.0
    listing_ids: list[str] = []
    for session in record.get("sessions") or []:
        events = timed_events(session)
        if not events:
            continue
        starts.append(events[0]["ts"])
        total_ms += events[-1]["ts"] - events[0]["ts"]
        every_page.extend(pages(events))
        moments = [event["ts"] for event in events if event.get("type") != "activity"]  # activity ticks are periodic
        gaps.extend(later - earlier for earlier, later in zip(moments, moments[1:]))
        for event in events:
            kind, props = event.get("type"), event.get("props") or {}
            counts[kind] += 1
            if kind == "activity":
                for key in ("mouse_moves", "mouse_distance", "touches", "keys", "scrolls"):
                    counts["activity_" + key] += _count(props.get(key))
            elif kind == "click":
                counts["untrusted_clicks" if props.get("trusted") is False else "trusted_clicks"] += 1
            elif kind == "property_view" and props.get("listing_id"):
                listing_ids.append(str(props["listing_id"]).upper())

    duration_s = total_ms / 1000
    minutes = duration_s / 60
    page_views = counts["page_view"]
    finished = [page["dwell"] for page in every_page if page["done"]]
    f["sessions"] = float(len(starts))
    f["page_views"] = float(page_views)
    f["duration_s"] = duration_s
    f["pages_per_minute"] = page_views / max(minutes, 0.25) if page_views >= 2 else NAN
    f["median_dwell_s"] = statistics.median(finished) / 1000 if finished else NAN
    f["fast_pages"] = float(sum(1 for dwell in finished if dwell < FAST_PAGE_MS))
    f["scrolls_per_page"] = counts["scroll_depth"] / page_views if page_views else NAN
    expected_ticks = duration_s / 10  # the SDK sends an activity summary every 10 s when anything happened
    f["activity_coverage"] = min(1.0, counts["activity"] / expected_ticks) if expected_ticks >= 1 else NAN
    f["mouse_moves_per_min"] = counts["activity_mouse_moves"] / minutes if duration_s >= 10 else NAN
    moves = counts["activity_mouse_moves"]
    f["mouse_px_per_move"] = counts["activity_mouse_distance"] / moves if moves >= 5 else NAN
    f["touches_per_min"] = counts["activity_touches"] / minutes if duration_s >= 10 else NAN
    f["keys"] = float(counts["activity_keys"])
    f["trusted_clicks"] = float(counts["trusted_clicks"])
    f["untrusted_clicks"] = float(counts["untrusted_clicks"])
    f["event_gap_cv"] = _cv(gaps) if len(gaps) >= 4 else NAN

    # ---- the enquiry form
    fills = [_num(lead.get("form_fill_ms")) for lead in leads if lead.get("form_fill_ms") is not None]
    fills = [fill for fill in fills if not math.isnan(fill)]
    f["leads"] = float(len(leads))
    f["honeypot"] = 1.0 if any(str(lead.get("honeypot") or "").strip() for lead in leads) else 0.0
    f["min_fill_s"] = min(fills) / 1000 if fills else NAN
    f["lead_without_pageviews"] = 1.0 if leads and page_views == 0 else 0.0
    sent = [lead["client_ts"] for lead in leads if isinstance(lead.get("client_ts"), (int, float))]
    f["seconds_to_first_lead"] = max(0.0, (min(sent) - min(starts)) / 1000) if sent and starts else NAN
    f["ip_visitors"] = _num(network.get("ip_visitors"))
    f["phone_visitors"] = _count(network.get("phone_visitors"))

    # ---- what they are interested in (intent score only, never the model)
    property_ms = 0.0
    for page in every_page:
        if match := _PROPERTY_PATH.match(page["path"]):
            property_ms += page["dwell"]
            listing_ids.append(match.group(1).upper())
    viewed = list(dict.fromkeys(listing_ids))
    f["property_views"] = float(len(viewed))
    f["property_time_s"] = property_ms / 1000
    f["emi_used"] = float(counts["emi_used"])
    f["floorplan_downloads"] = float(counts["floorplan_download"])
    f["filters_used"] = float(counts["filter_used"])
    f["chat_messages"] = float(len(record.get("chat") or []))
    f["active_days"] = float(len({(start + IST_OFFSET_MS) // DAY_MS for start in starts}))
    f["visit_span_days"] = (max(starts) - min(starts)) / DAY_MS if len(starts) >= 2 else 0.0

    homes = [home for home in (get_listing(item) for item in viewed) if home is not None]
    if len(homes) >= 2:
        f["city_focus"] = Counter(home.city for home in homes).most_common(1)[0][1] / len(homes)
        prices = [home.price_inr for home in homes]
        f["price_spread"] = max(prices) / min(prices)
    else:
        f["city_focus"] = f["price_spread"] = NAN
    budget = (record.get("profile") or {}).get("budget_max")
    if homes and isinstance(budget, (int, float)) and budget > 0:
        f["budget_fit"] = sum(1 for home in homes if home.price_inr <= budget * 1.15) / len(homes)
    else:
        f["budget_fit"] = NAN
    return f


def model_vector(features: dict) -> list[float]:
    """The model's input row, in MODEL_FEATURES order."""
    return [features.get(name, NAN) for name in MODEL_FEATURES]


# ---------------------------------------------------------------- datasets (training)


def _activity_times(record: dict) -> list[float]:
    times = [event["ts"] for session in record.get("sessions") or [] for event in timed_events(session)]
    times += [lead["client_ts"] for lead in record.get("leads") or [] if isinstance(lead.get("client_ts"), (int, float))]
    return times


def add_network_counts(records: list[dict]) -> None:
    """Fill record["network"] across a whole dataset, the way engine.py counts it live from the database."""
    seen_at: dict[str, list[tuple[float, str]]] = defaultdict(list)  # ip -> [(time, visitor_id)]
    phones: dict[str, set[str]] = defaultdict(set)
    for record in records:
        visitor = record["visitor_id"]
        for session in record.get("sessions") or []:
            events = timed_events(session)
            if session.get("ip") and events:
                seen_at[session["ip"]].append((events[0]["ts"], visitor))
        for lead in record.get("leads") or []:
            if lead.get("ip") and isinstance(lead.get("client_ts"), (int, float)):
                seen_at[lead["ip"]].append((lead["client_ts"], visitor))
            if key := phone_digits(lead.get("phone")):
                phones[key].add(visitor)
    for record in records:
        times = _activity_times(record)
        ips = {s["ip"] for s in record.get("sessions") or [] if s.get("ip")} | {
            lead["ip"] for lead in record.get("leads") or [] if lead.get("ip")
        }
        if ips and times:
            latest = max(times)
            nearby = {visitor for ip in ips for at, visitor in seen_at[ip] if latest - IP_WINDOW_MS <= at <= latest}
            ip_visitors = float(len(nearby | {record["visitor_id"]}))
        else:
            ip_visitors = NAN
        keys = [phone_digits(lead.get("phone")) for lead in record.get("leads") or []]
        phone_visitors = max((len(phones[key]) for key in keys if key), default=0)
        record["network"] = {"ip_visitors": ip_visitors, "phone_visitors": phone_visitors}


def cut_record(record: dict, until_ts: float) -> dict:
    """The visitor as live scoring saw it at time until_ts: later events, enquiries and messages left out."""
    sessions = []
    for session in record.get("sessions") or []:
        events = [event for event in session.get("events") or [] if event.get("ts", 0) <= until_ts]
        if events:
            sessions.append({**session, "events": events})
    leads = [lead for lead in record.get("leads") or [] if (lead.get("client_ts") or 0) <= until_ts]
    chat = [message for message in record.get("chat") or [] if (message.get("ts") or 0) <= until_ts]
    return {**record, "sessions": sessions, "leads": leads, "chat": chat}
