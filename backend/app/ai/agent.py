"""The property assistant as a LangGraph graph, one graph run per chat message:

    understand -> search_properties -> [calc_emi | brochure_search | book_visit | request_call] -> reply -> save_lead_details

  understand         one LLM call (patterns without a key): the buyer details and what the visitor wants
  search_properties  the listings that fit, and which home this turn is about
  calc_emi           the EMI calculator's formula
  brochure_search    passages from the project's brochure
  book_visit         books a site visit, or asks the chat widget for a form with whatever is still missing
  request_call       a call back from the sales team
  reply              the LLM writes from those results only; templates without a key or when a call fails
  save_lead_details  saves the exchange and the buyer details on the visitor

LangGraph only orchestrates. Every LLM call goes through llm_client.py, and the next step comes from structured output
rather than a provider's own tool calling, so Claude, Gemini, Groq and template mode all behave the same. Phone numbers
never pass through the LLM: when contact details are needed the chat widget shows a form.
"""

import logging
import os
import re
from collections import Counter
from datetime import date, timedelta
from functools import lru_cache
from typing import TypedDict

os.environ["LANGSMITH_TRACING"] = "false"  # visitors' conversations never leave for a tracing service

from langgraph.graph import END, START, StateGraph  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from ..db import SessionLocal  # noqa: E402
from ..listings import all_listings, get_listing, monthly_emi  # noqa: E402
from ..models import ChatMessage, Visitor  # noqa: E402
from ..schemas import ChatAction, ChatIn, ChatOut, EmiOut, Listing, VisitorOut  # noqa: E402
from ..tracking import contact_lead_id, get_or_create_visitor, run_in_session, save_site_visit, visitor_out  # noqa: E402
from ..utils import today_ist, utcnow  # noqa: E402
from .assistant import (  # noqa: E402
    SEARCH_KEYS,
    SYSTEM_PROMPT,
    around,
    llm_messages,
    recent_history,
    search_homes,
    template_reply,
    template_turn,
)
from .brochures import Passage  # noqa: E402
from .brochures import search as search_brochures  # noqa: E402
from .extract import extract_details, merge_profile, normalise, read_message  # noqa: E402
from .llm_client import LLMError, llm  # noqa: E402
from .rag import SearchResult  # noqa: E402

log = logging.getLogger("leadops.agent")

GOALS = ("homes", "home_question", "emi", "brochure", "site_visit", "call_me", "small_talk")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DAY_WORDS = ("today", "tomorrow", "day_after", "weekend", *WEEKDAYS)
SLOTS = ("morning", "afternoon", "evening")
DEFAULT_DOWN_PCT, DEFAULT_RATE_PCT, DEFAULT_YEARS = 20.0, 8.5, 20  # the EMI calculator's starting values
STICKY_LANGUAGES = ("hinglish", "hi", "mr")


class Turn(TypedDict, total=False):
    """Everything one chat message passes through the graph."""

    payload: ChatIn
    ip: str | None
    user_agent: str | None
    old_profile: dict
    history: list[ChatMessage]
    shown_ids: list[str]  # the homes the assistant showed last
    current: Listing | None  # the property page the visitor is on
    found: dict
    plan: dict
    profile: dict
    language: str
    result: SearchResult
    home: Listing | None  # the home this turn is about
    emi: EmiOut | None
    passages: list[Passage]
    action: ChatAction | None
    reply: str
    mode: str
    summary: VisitorOut | None


# ---------------------------------------------------------------- understanding a message without an LLM

_VISIT = re.compile(
    r"\bsite[- ]?visit\b|\bvisit (?:the |this |that )?(?:site|home|flat|project|property)\b|\bbook (?:a |the )?(?:site )?visit\b"
    r"|\b(?:want|like|love|need) to (?:visit|see (?:the|this|that) (?:flat|home|site|property))\b|\bvisit (?:on|this|next|tomorrow|today)\b"
    r"|\bdekhne (?:aana|aa|aaunga|aaungi)\b|\bvisit kar(?:na|ni|wa|un)\b|साइट विज़िट|साइट विजिट|साइट व्हिजिट|देखने आना|भेट द्या|भेट द्यायची|पाहायला (?:यायचे|येऊ)"
)
_EMI = re.compile(r"\bemi\b|\bmonthly (?:payment|instal?lment)\b|\bkist\b|ईएमआई|ई\.एम\.आई|हप्ता|किस्त")
_CALL = re.compile(
    r"\bcall me\b|\bcall back\b|\bcallback\b|\btalk to (?:someone|sales|a person|an agent|your team)\b|\bspeak (?:to|with) (?:someone|sales|a person|an agent)\b"
    r"|\bcontact me\b|\bphone kar|\bcall kar|\bbaat kar|फोन कर|कॉल कर|बात कर|संपर्क कर"
)
_BROCHURE = re.compile(
    r"\bpayment (?:plan|schedule)\b|\bbooking amount\b|\bparking\b|\bmaintenance\b|\brera\b|\bapprov|\bspecification|\bspecs\b|\bflooring\b|\bkitchen\b"
    r"|\bbathrooms?\b|\bschools?\b|\bhospitals?\b|\bmetro\b|\bbrochure\b|\bstamp duty\b|\bregistration\b|\bgst\b|\bpossession\b|\bhandover\b|\bamenit"
    r"|\bclubhouse\b|\bgym\b|\bpool\b|\bpower backup\b|\bnearby\b|\bairport\b|पार्किंग|मेंटेनेंस|देखभाल|रेरा|स्कूल|शाळा|अस्पताल|रुग्णालय|दवाखाना|मेट्रो|ब्रोशर|माहितीपत्रक"
    r"|पेमेंट|भुगतान|पजेशन|ताबा|सुविधा"
)
_WANTS_HOMES = re.compile(r"\b(?:show|find|looking|search|need|want|homes?|flats?|apartments?|villas?|dikhao|chahiye|pahije|ghar)\b|घर|चाहिए|हवा|हवे|हवी|दाखवा|दिखाओ")
_PCT = r"(?:%|percent|per cent|प्रतिशत|टक्के)"
_DOWN = re.compile(rf"(\d{{1,2}}(?:\.\d+)?)\s*{_PCT}\s*(?:down|dp|advance|upfront|डाउन)|(?:down ?payment|\bdp\b|डाउन पेमेंट)\D{{0,15}}(\d{{1,2}}(?:\.\d+)?)\s*{_PCT}")
_RATE = re.compile(rf"(?:\bat\b|@|\brate\b|\binterest\b|ब्याज|व्याज)\D{{0,12}}(\d{{1,2}}(?:\.\d+)?)\s*{_PCT}")
_TENURE = re.compile(r"(\d{1,2})\s*(?:years?|yrs?|saal|sal|साल|वर्ष)")
_DAY_PATTERNS = (
    ("day_after", r"\bday after tomorrow\b|\bparso\b|परसों|परवा"),
    ("today", r"\btoday\b|\baaj\b|आज"),
    ("tomorrow", r"\btomorrow\b|\bkal\b|उद्या|कल"),
    ("weekend", r"\bweekend\b|वीकेंड|शनिवार-रविवार"),
    ("saturday", r"\bsat(?:urday)?\b|\bshanivar\b|शनिवार"),
    ("sunday", r"\bsun(?:day)?\b|\bravivar\b|रविवार"),
    ("monday", r"\bmon(?:day)?\b|\bsomvar\b|सोमवार"),
    ("tuesday", r"\btue(?:s|sday)?\b|\bmangalvar\b|मंगलवार|मंगळवार"),
    ("wednesday", r"\bwed(?:nesday)?\b|\bbudhvar\b|बुधवार"),
    ("thursday", r"\bthu(?:rs|rsday)?\b|\bguruvar\b|गुरुवार"),
    ("friday", r"\bfri(?:day)?\b|\bshukravar\b|शुक्रवार"),
)
_SLOT_PATTERNS = (
    ("morning", r"\bmorning\b|\bsubah\b|सुबह|सकाळ"),
    ("afternoon", r"\bafternoon\b|\bdopahar\b|दोपहर|दुपार"),
    ("evening", r"\bevening\b|\bsha+m\b|शाम|संध्याकाळ"),
)
_POSITIONS = {
    0: r"\bfirst\b|\b1st\b|\bpehla\b|\bpehle\b|पहला|पहले|पहिला|पहिले",
    1: r"\bsecond\b|\b2nd\b|\bdoosra\b|\bdusra\b|\bdusre\b|दूसरा|दूसरे|दुसरा|दुसरे",
    2: r"\bthird\b|\b3rd\b|\bteesra\b|\btisra\b|तीसरा|तीसरे|तिसरा|तिसरे",
}
_COMMON_FIRST_WORDS = {"green", "silver", "coral"}  # too ordinary to stand for a project on their own


@lru_cache(maxsize=1)
def _home_names() -> tuple[tuple[re.Pattern, str], ...]:
    firsts = Counter(item.project.split()[0].casefold() for item in all_listings())
    entries = []
    for item in all_listings():
        first = item.project.split()[0].casefold()
        names = {item.project.casefold(), item.id.casefold()}
        if firsts[first] == 1 and first not in _COMMON_FIRST_WORDS:
            names.add(first)
        entries += [(re.compile(rf"(?<!\w){re.escape(name)}(?!\w)"), item.id) for name in names]
    return tuple(entries)


def find_home(text: str) -> str | None:
    """The listing a message names, by project or ID; the first one mentioned wins."""
    hits = [(match.start(), listing_id) for pattern, listing_id in _home_names() if (match := pattern.search(text))]
    return min(hits)[1] if hits else None


def _first_match(patterns, text: str) -> str | None:
    return next((name for name, pattern in patterns if re.search(pattern, text)), None)


def resolve_day(word: str | None, today: date) -> date | None:
    """"saturday" -> the next Saturday. A weekday always means the next one to come, never today."""
    if word == "today":
        return today
    if word == "tomorrow":
        return today + timedelta(days=1)
    if word == "day_after":
        return today + timedelta(days=2)
    word = "saturday" if word == "weekend" else word
    if word in WEEKDAYS:
        return today + timedelta(days=(WEEKDAYS.index(word) - today.weekday()) % 7 or 7)
    return None


def plan_from_patterns(message: str, found: dict, *, on_page: bool) -> dict:
    """What the visitor wants, from keywords in English, Hinglish, Hindi and Marathi."""
    text = normalise(message)
    named = find_home(text)
    asks_for_homes = any(key in found for key in SEARCH_KEYS)
    if _VISIT.search(text):
        goal = "site_visit"
    elif _EMI.search(text):
        goal = "emi"
    elif _CALL.search(text):
        goal = "call_me"
    elif _BROCHURE.search(text) and (named or not asks_for_homes):  # "2 BHK near a metro" is a search, not a brochure question
        goal = "brochure"
    elif asks_for_homes or _WANTS_HOMES.search(text):
        goal = "homes"
    elif on_page or named:
        goal = "home_question"
    else:
        goal = "small_talk"
    down, rate, tenure = _DOWN.search(text), _RATE.search(text), _TENURE.search(text)
    return {
        "goal": goal,
        "home_id": named,
        "home_position": next((position for position, pattern in _POSITIONS.items() if re.search(pattern, text)), None),
        "down_payment_pct": float(down.group(1) or down.group(2)) if down else None,
        "rate_pct": float(rate.group(1)) if rate else None,
        "years": int(tenure.group(1)) if tenure else None,
        "visit_day": _first_match(_DAY_PATTERNS, text),
        "visit_slot": _first_match(_SLOT_PATTERNS, text),
        "search_words": None,
    }


# ---------------------------------------------------------------- understanding a message with the LLM


def _nullable(schema: dict) -> dict:
    return {"anyOf": [schema, {"type": "null"}]}


PLAN_PROPERTIES = {
    "goal": {"type": "string", "enum": list(GOALS)},
    "home_name": _nullable({"type": "string"}),
    "home_position": _nullable({"type": "integer"}),
    "down_payment_pct": _nullable({"type": "number"}),
    "rate_pct": _nullable({"type": "number"}),
    "emi_years": _nullable({"type": "integer"}),
    "visit_day": _nullable({"type": "string", "enum": list(DAY_WORDS)}),
    "visit_slot": _nullable({"type": "string", "enum": list(SLOTS)}),
    "search_words": _nullable({"type": "string"}),
}
PLAN_HELP = """\
Also say what the visitor wants from this message:
- goal: homes (find homes), home_question (about a home's basic facts), emi (a monthly payment), brochure (payment plan, parking, \
maintenance, approvals, specifications, what is nearby, possession), site_visit, call_me (wants a call from the team), small_talk.
- home_name: the project they name, as written. home_position: 1, 2 or 3 for "the first one", "the second one", "the third one".
- down_payment_pct, rate_pct, emi_years: only what they state for an EMI.
- visit_day: today, tomorrow, day_after, weekend or a weekday. visit_slot: morning, afternoon or evening.
- search_words: for a brochure question, a few English words to search the brochure with ("payment plan booking amount")."""


def merge_llm_plan(plan: dict, raw: dict) -> dict:
    """The LLM's reading wins wherever it makes sense; the patterns fill the rest."""
    if not raw:
        return plan
    merged = dict(plan)
    if raw.get("goal") in GOALS:
        merged["goal"] = raw["goal"]
    if isinstance(raw.get("home_name"), str) and (home := find_home(normalise(raw["home_name"]))):
        merged["home_id"] = home
    position = raw.get("home_position")
    if isinstance(position, int) and not isinstance(position, bool) and 1 <= position <= 3:
        merged["home_position"] = position - 1
    for key, target, low, high in (("down_payment_pct", "down_payment_pct", 0, 90), ("rate_pct", "rate_pct", 4, 20), ("emi_years", "years", 1, 35)):
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and low <= value <= high:
            merged[target] = value
    if raw.get("visit_day") in DAY_WORDS:
        merged["visit_day"] = raw["visit_day"]
    if raw.get("visit_slot") in SLOTS:
        merged["visit_slot"] = raw["visit_slot"]
    if isinstance(raw.get("search_words"), str) and raw["search_words"].strip():
        merged["search_words"] = raw["search_words"].strip()[:200]
    return merged


# ---------------------------------------------------------------- the graph's steps


def understand(turn: Turn) -> Turn:
    payload, old_profile = turn["payload"], turn["old_profile"]
    earlier = [row.text for row in turn["history"] if row.role == "user"]
    found, raw = read_message(payload.message, earlier, extra_properties=PLAN_PROPERTIES, extra_help=PLAN_HELP)
    # A short reply such as "3 BHK" or "20 lakh" keeps the language the visitor has been using.
    if found.get("language") == "en" and len(payload.message.split()) <= 5 and old_profile.get("language") in STICKY_LANGUAGES:
        found["language"] = old_profile["language"]
    plan = merge_llm_plan(plan_from_patterns(payload.message, found, on_page=turn.get("current") is not None), raw)
    return {"found": found, "plan": plan, "profile": merge_profile(old_profile, found), "language": found.get("language", "en")}


def search_properties(turn: Turn) -> Turn:
    plan, current = turn["plan"], turn.get("current")
    shown = [home for home in (get_listing(item) for item in turn["shown_ids"]) if home]
    named = get_listing(plan["home_id"]) if plan.get("home_id") else None
    position = plan.get("home_position")
    pointed_at = shown[position] if position is not None and position < len(shown) else None
    target = named or pointed_at
    result = around(target) if target else search_homes(turn["profile"], turn["found"], turn["payload"].message, current)
    best_match = result.listings[0] if result.listings and any(key in turn["profile"] for key in SEARCH_KEYS) else None
    home = target or current or (shown[0] if shown else None) or best_match
    if home is None and plan["goal"] in ("emi", "brochure", "site_visit"):
        result = SearchResult([])  # the reply asks which home they mean: no cards for homes they didn't ask about
    return {"result": result, "home": home}


def choose_tool(turn: Turn) -> str:
    return {"emi": "calc_emi", "brochure": "brochure_search", "site_visit": "book_visit", "call_me": "request_call"}.get(turn["plan"]["goal"], "reply")


def calc_emi(turn: Turn) -> Turn:
    home, plan = turn.get("home"), turn["plan"]
    if home is None:
        return {"emi": None}
    down = plan["down_payment_pct"] if plan.get("down_payment_pct") is not None else DEFAULT_DOWN_PCT
    rate = plan["rate_pct"] if plan.get("rate_pct") is not None else DEFAULT_RATE_PCT
    years = int(plan["years"]) if plan.get("years") else DEFAULT_YEARS
    loan = round(home.price_inr * (1 - down / 100))
    monthly = monthly_emi(loan, rate, years)
    return {"emi": EmiOut(listing_id=home.id, project=home.project, price_inr=home.price_inr, down_payment_pct=down, loan_inr=loan,
                          rate_pct=rate, years=years, emi_inr=round(monthly), total_interest_inr=round(monthly * years * 12 - loan))}  # fmt: skip


def brochure_search(turn: Turn) -> Turn:
    home = turn.get("home")
    if home is None:
        return {"passages": []}
    return {"passages": search_brochures(turn["plan"].get("search_words") or turn["payload"].message, listing_ids=[home.id])}


def book_visit(turn: Turn) -> Turn:
    home, plan, payload = turn.get("home"), turn["plan"], turn["payload"]
    if home is None:
        return {"action": None}
    lead_id = contact_lead_id(payload.visitor_id)
    day = resolve_day(plan.get("visit_day"), today_ist())
    slot = plan.get("visit_slot") or "morning"
    if lead_id and day:
        visit = save_site_visit(payload.visitor_id, lead_id, home.id, day, slot, "assistant")
        return {"action": ChatAction(type="visit_booked", purpose="site_visit", listing_id=home.id, project=home.project, day=day, slot=slot, visit=visit)}
    return {"action": ChatAction(type="contact_form", purpose="site_visit", listing_id=home.id, project=home.project, need_contact=lead_id is None,
                                 day=day, slot=plan.get("visit_slot"))}  # fmt: skip


def request_call(turn: Turn) -> Turn:
    home, payload = turn.get("home"), turn["payload"]
    found = {**turn["found"], "call_requested": True}
    update: Turn = {"found": found, "profile": {**turn["profile"], "call_requested": True}, "action": None}
    if contact_lead_id(payload.visitor_id) is None:
        update["action"] = ChatAction(type="contact_form", purpose="callback", listing_id=home.id if home else None,
                                      project=home.project if home else None, need_contact=True)  # fmt: skip
    return update


def _llm_extras(turn: Turn) -> dict:
    """What the tools found, for the LLM to write from."""
    extras: dict = {"visitor_wants": turn["plan"]["goal"]}
    if emi := turn.get("emi"):
        extras["emi"] = emi.model_dump()
    if passages := turn.get("passages"):
        extras["brochure"] = [{"project": item.project, "section": item.section, "text": item.text} for item in passages]
    action = turn.get("action")
    if turn["plan"]["goal"] in ("site_visit", "call_me"):
        if action and action.type == "visit_booked" and action.visit:
            extras["booking"] = f"Booked: {action.visit.project} on {action.visit.day_text}, {action.visit.slot}. The sales team will confirm."
        elif action:
            extras["booking"] = "The website is showing a form under your reply. Ask the visitor to fill it in; never ask for a number in the chat."
        elif turn["plan"]["goal"] == "call_me":
            extras["booking"] = "The sales team already has the visitor's number and will call them."
        else:
            extras["booking"] = "Not sure which home they mean: ask which one."
    return extras


def reply(turn: Turn) -> Turn:
    payload, profile, result, current = turn["payload"], turn["profile"], turn["result"], turn.get("current")
    if llm.available():
        try:
            messages = llm_messages(payload.message, turn["history"], profile, result, current, _llm_extras(turn))
            return {"reply": llm.generate(SYSTEM_PROMPT, messages), "mode": "llm"}
        except LLMError as exc:
            log.warning("LLM failed, replying from a template instead: %s", exc)
    text = template_turn(turn["plan"]["goal"], turn["language"], profile=profile, result=result, current=current, home=turn.get("home"),
                         emi=turn.get("emi"), passages=turn.get("passages") or [], action=turn.get("action"))  # fmt: skip
    return {"reply": text, "mode": "template"}


def save_lead_details(turn: Turn) -> Turn:
    payload, found = turn["payload"], turn["found"]
    if not payload.visitor_id:
        return {"summary": None}

    def save(db: Session) -> VisitorOut:
        now = utcnow()
        row = get_or_create_visitor(db, payload.visitor_id, ip=turn.get("ip"), user_agent=turn.get("user_agent"))
        db.add_all([
            ChatMessage(visitor_id=row.id, session_id=payload.session_id, role="user", text=payload.message, extracted=found,
                        listing_ids=[], created_at=now),
            ChatMessage(visitor_id=row.id, session_id=payload.session_id, role="assistant", text=turn["reply"], extracted={},
                        listing_ids=[item.id for item in turn["result"].listings], mode=turn["mode"], created_at=now),
        ])  # fmt: skip
        row.profile = merge_profile(dict(row.profile or {}), found)
        row.chat_count += 1
        row.last_seen = now
        db.commit()
        return visitor_out(row)

    return {"summary": run_in_session(save)}


def build_graph():
    graph = StateGraph(Turn)
    for name, step in (("understand", understand), ("search_properties", search_properties), ("calc_emi", calc_emi),
                       ("brochure_search", brochure_search), ("book_visit", book_visit), ("request_call", request_call),
                       ("reply", reply), ("save_lead_details", save_lead_details)):  # fmt: skip
        graph.add_node(name, step)
    graph.add_edge(START, "understand")
    graph.add_edge("understand", "search_properties")
    graph.add_conditional_edges("search_properties", choose_tool, ["calc_emi", "brochure_search", "book_visit", "request_call", "reply"])
    for tool in ("calc_emi", "brochure_search", "book_visit", "request_call"):
        graph.add_edge(tool, "reply")
    graph.add_edge("reply", "save_lead_details")
    graph.add_edge("save_lead_details", END)
    return graph.compile()


AGENT = build_graph()


def _plain_turn(turn: Turn) -> Turn:
    """If the graph itself fails: the patterns, the listing search and a template, so the visitor still gets an answer."""
    payload = turn["payload"]
    found = extract_details(payload.message)
    profile = merge_profile(turn["old_profile"], found)
    result = search_homes(profile, found, payload.message, turn.get("current"))
    done: Turn = {**turn, "found": found, "profile": profile, "result": result, "mode": "template",
                  "reply": template_reply(profile, result, turn.get("current"), found.get("language", "en"))}  # fmt: skip
    return {**done, **save_lead_details(done)}


def handle_chat(payload: ChatIn, ip: str | None, user_agent: str | None) -> tuple[ChatOut, VisitorOut | None]:
    """One chat message: run the graph and return the reply, plus the visitor as it is now."""
    with SessionLocal() as db:
        visitor = db.get(Visitor, payload.visitor_id) if payload.visitor_id else None
        old_profile = dict(visitor.profile or {}) if visitor else {}
        history = recent_history(db, payload.visitor_id) if visitor else []
    shown_ids = next((list(row.listing_ids or []) for row in reversed(history) if row.role == "assistant"), [])
    start: Turn = {"payload": payload, "ip": ip, "user_agent": user_agent, "old_profile": old_profile, "history": history,
                   "shown_ids": shown_ids, "current": get_listing(payload.listing_id) if payload.listing_id else None}  # fmt: skip
    try:
        turn = AGENT.invoke(start)
    except Exception:
        log.exception("The assistant's graph failed, answering from a template")
        turn = _plain_turn(start)
    answer = ChatOut(reply=turn["reply"], listings=turn["result"].listings, extracted=turn["found"], profile=turn["profile"],
                     mode=turn["mode"], action=turn.get("action"), emi=turn.get("emi"))  # fmt: skip
    return answer, turn.get("summary")
