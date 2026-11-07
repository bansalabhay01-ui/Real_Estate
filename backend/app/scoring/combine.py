"""One decision per visitor: rules + the ML human check + intent points -> label, intent score and reasons.

The label, in this order (LEADOPS_PLAN.md, Week 2 Part 3):
  1. Bot     a certain bot signal, two strong ones, one strong one with human_prob under the review cut-off,
             or human_prob under the bot cut-off (with enough to go on)
  2. Junk    a certain junk signal, two strong ones, or a confident visitor type of broker / spam / tenant;
             but with intent 70+ it becomes Review, so a real buyer is never silently thrown away
  3. Review  one strong signal alone, or human_prob under the review cut-off, for visitors worth a look
             (an enquiry, or intent 40+); unsure anonymous browsers stay Cold
  4. Cold under 40, Warm 40-70, Hot over 70 on the intent score
"""

import math
from dataclasses import dataclass, field

from ..listings import format_price
from .explain import human_factors, reasons_for, summary_line
from .features import visitor_features
from .model import HumanCheck, HumanModel, current_model
from .rules import BOT, CERTAIN, JUNK, STRONG, Signal, evaluate

NOT_BUYERS = {"broker", "spam", "tenant"}  # visitor types that aren't buyers (Part 6 classifies them)
CONFIDENT = 0.7


@dataclass
class IntentPoint:
    signal: str
    points: int
    detail: str


@dataclass
class ScoreResult:
    label: str
    intent_score: int
    human: HumanCheck
    signals: list[Signal]
    points: list[IntentPoint]
    reasons: list[str]
    summary: str
    thresholds: dict
    features: dict = field(repr=False)
    visitor_type: dict | None = None

    def as_json(self) -> dict:
        """What engine.py saves on the visitor: the summary the API returns, plus the full breakdown."""
        return {
            "label": self.label,
            "intent_score": self.intent_score,
            "human_prob": round(self.human.human_prob, 4),
            "visitor_type": (self.visitor_type or {}).get("type"),
            "reasons": self.reasons,
            "summary": self.summary,
            "model_version": self.human.version,
            "detail": {
                "signals": [{"code": s.code, "layer": s.layer, "strength": s.strength, "reason": s.reason} for s in self.signals],
                "human": {"prob": round(self.human.human_prob, 4), "source": self.human.source,
                          "factors": human_factors(self.human, self.features)},
                "intent": {"score": self.intent_score,
                           "points": [{"signal": p.signal, "points": p.points, "detail": p.detail} for p in self.points]},
                "visitor_type": self.visitor_type,
                "thresholds": self.thresholds,
            },
        }  # fmt: skip


def _known(value) -> float | None:
    return None if value is None or (isinstance(value, float) and math.isnan(value)) else value


def _duration(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} seconds"
    minutes = round(seconds / 60)
    return f"{minutes} minutes" if minutes < 90 else f"{seconds / 3600:.1f} hours"


def _last_props(record: dict, event_type: str) -> dict:
    found: dict = {}
    for session in record.get("sessions") or []:
        for event in session.get("events") or []:
            if event.get("type") == event_type:
                found = event.get("props") or {}
    return found


def _budget_phrase(profile: dict) -> str | None:
    low, high = profile.get("budget_min"), profile.get("budget_max")
    if low and high:
        return f"{format_price(low)} to {format_price(high)}"
    if high:
        return f"under {format_price(high)}"
    if low:
        return f"above {format_price(low)}"
    return None


def intent_points(record: dict, f: dict, signals: list[Signal]) -> list[IntentPoint]:
    """Points for buying signals, out of 100 (the plan's table). Easy to explain, and Week 3 can re-weight them."""
    points: list[IntentPoint] = []

    def add(signal: str, value: float, detail: str) -> None:
        if value >= 1:
            points.append(IntentPoint(signal, int(round(value)), detail))

    homes = int(f["property_views"])
    if homes:
        add("property_time", min(20.0, f["property_time_s"] / 180 * 20),
            f"Spent {_duration(f['property_time_s'])} on {homes} home{'s' if homes > 1 else ''}")
    if f["sessions"] >= 2:
        days, visits = int(f["active_days"]), int(f["sessions"])
        add("repeat_visits", 15 if days >= 3 else 10 if days == 2 else 6,
            f"{visits} visits over {days} days" if days >= 2 else f"{visits} visits in one day")

    profile = record.get("profile") or {}
    told, value = [], 0
    if place := profile.get("locality") or profile.get("city"):
        value, told = value + 3, [*told, place]
    if profile.get("bhk"):
        value, told = value + 3, [*told, f"{profile['bhk']} BHK"]
    if budget := _budget_phrase(profile):
        value, told = value + 4, [*told, budget]
    months = profile.get("timeline_months")
    if isinstance(months, (int, float)) and months <= 6:
        value, told = value + 5, [*told, f"moving within {months} month{'s' if months != 1 else ''}"]
    add("shared_details", value, "Told the assistant: " + ", ".join(told))

    if f["emi_used"]:
        price = _last_props(record, "emi_used").get("price_inr")
        add("emi", 12, f"Checked the EMI on a {format_price(price)} home" if isinstance(price, int) else "Used the EMI calculator")
    if f["floorplan_downloads"]:
        bhk = _last_props(record, "floorplan_download").get("bhk")
        add("floor_plan", 12, f"Downloaded the {bhk} BHK floor plan" if bhk else "Downloaded a floor plan")
    flagged = any(s.layer == JUNK for s in signals) or any(s.layer == BOT and s.strength == CERTAIN for s in signals)
    if f["leads"] and not flagged:
        add("enquiry", 10, "Sent an enquiry with valid contact details")
    focus, city_focus, spread = 0, _known(f["city_focus"]), _known(f["price_spread"])
    if city_focus is not None:
        focus += 6 if city_focus == 1 else 3 if city_focus >= 0.75 else 0
    if spread is not None and spread <= 1.5:
        focus += 4
    add("focused_search", focus, "Looked at homes in one city and price range" if focus >= 10 else "Kept to a few similar homes")
    if f["filters_used"]:
        add("filters", 6, "Searched with the filters")
    return points


def decide(f: dict, signals: list[Signal], human: HumanCheck, intent: int, thresholds: dict,
           visitor_type: dict | None = None) -> str:
    p = human.human_prob
    bot_certain = [s for s in signals if s.layer == BOT and s.strength == CERTAIN]
    bot_strong = [s for s in signals if s.layer == BOT and s.strength == STRONG]
    junk_certain = [s for s in signals if s.layer == JUNK and s.strength == CERTAIN]
    junk_strong = [s for s in signals if s.layer == JUNK and s.strength == STRONG]
    not_a_buyer = bool(visitor_type) and visitor_type.get("type") in NOT_BUYERS
    confident_type = not_a_buyer and (visitor_type.get("confidence") or 0) >= CONFIDENT
    # The model alone only calls Bot when it has something to go on: a fresh visitor with one page view is unknown.
    enough = f["leads"] > 0 or f["page_views"] >= 3 or f["duration_s"] >= 20

    if bot_certain or len(bot_strong) >= 2 or (bot_strong and p < thresholds["review"]) or (enough and p < thresholds["bot"]):
        return "Bot"
    if junk_certain or len(junk_strong) >= 2 or confident_type:
        return "Review" if intent >= 70 else "Junk"
    worth_a_look = f["leads"] > 0 or intent >= 40
    if worth_a_look and (bot_strong or junk_strong or not_a_buyer or p < thresholds["review"]):
        return "Review"
    return "Hot" if intent > 70 else "Warm" if intent >= 40 else "Cold"


def score_record(record: dict, *, model: HumanModel | None = None, visitor_type: dict | None = None) -> ScoreResult:
    """Score one visitor record (features.py). model: the saved model by default, or one being trained."""
    model = model or current_model()
    f = visitor_features(record)
    signals = evaluate(record, f)
    human = model.predict(f)
    points = intent_points(record, f, signals)
    intent = min(100, sum(point.points for point in points))
    label = decide(f, signals, human, intent, model.thresholds, visitor_type)
    reasons = reasons_for(label, signals=signals, check=human, features=f, points=points, intent=intent,
                          visitor_type=visitor_type)
    return ScoreResult(label=label, intent_score=intent, human=human, signals=signals, points=points, reasons=reasons,
                       summary=summary_line(label, reasons), thresholds=dict(model.thresholds), features=f,
                       visitor_type=visitor_type)
