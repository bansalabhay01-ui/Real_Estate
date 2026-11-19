"""The assistant as an agent: understanding, EMI, brochures, site visits, languages and every fallback."""

import random
import uuid
from datetime import date, timedelta

import pytest

from app.ai import agent as agent_module
from app.ai import extract as extract_module
from app.ai.agent import AGENT, find_home, plan_from_patterns, resolve_day
from app.ai.brochures import search
from app.ai.extract import detect_language, extract_details
from app.ai.llm_client import LLMError
from app.listings import format_rupees, monthly_emi
from app.utils import today_ist

LAKH = 100_000


def ids() -> tuple[str, str]:
    return str(uuid.uuid4()), str(uuid.uuid4())


def say(client, message, visitor_id=None, session_id=None, listing_id=None):
    body = {"visitor_id": visitor_id, "session_id": session_id, "message": message, "listing_id": listing_id}
    response = client.post("/chat", json=body)
    assert response.status_code == 200
    return response.json()


def phone() -> str:
    return "9" + str(random.randint(100_000_000, 999_999_999))


def enquire(client, visitor_id, session_id, listing_id="PUN-002"):
    body = {"visitor_id": visitor_id, "session_id": session_id, "listing_id": listing_id, "name": "Priya Kulkarni", "phone": phone(),
            "consent": True, "form_fill_ms": 30_000, "message": "Please call me."}
    assert client.post("/leads", json=body).status_code == 201


# ---------------------------------------------------------------- the graph


def test_the_graph_has_every_step_of_the_plan():
    nodes = set(AGENT.get_graph().nodes)
    assert {"understand", "search_properties", "calc_emi", "brochure_search", "book_visit", "request_call", "reply", "save_lead_details"} <= nodes


@pytest.mark.parametrize(
    ("message", "goal"),
    [
        ("3BHK under 90L in Pune", "homes"),
        ("2 BHK near a metro", "homes"),
        ("What's the payment plan at Aranya Courtyard?", "brochure"),
        ("parking kitni hai?", "brochure"),
        ("EMI for this with 30% down", "emi"),
        ("Book a site visit on Saturday morning", "site_visit"),
        ("Please call me back", "call_me"),
        ("hello there", "small_talk"),
    ],
)
def test_what_the_visitor_wants(message, goal):
    assert plan_from_patterns(message, extract_details(message), on_page=False)["goal"] == goal


def test_details_of_a_request_are_read():
    plan = plan_from_patterns("EMI with 30% down at 8.75% for 15 years", {}, on_page=True)
    assert (plan["down_payment_pct"], plan["rate_pct"], plan["years"]) == (30, 8.75, 15)
    plan = plan_from_patterns("शनिवारी सकाळी साइट व्हिजिट करायची आहे", {}, on_page=True)
    assert plan["goal"] == "site_visit" and plan["visit_day"] == "saturday" and plan["visit_slot"] == "morning"
    assert find_home("what about aranya?") == "PUN-002" and find_home("a green park nearby") is None


def test_days_are_the_next_one_to_come():
    wednesday = date(2026, 11, 18)
    assert resolve_day("saturday", wednesday) == date(2026, 11, 21)
    assert resolve_day("weekend", wednesday) == date(2026, 11, 21)
    assert resolve_day("wednesday", wednesday) == date(2026, 11, 25)  # a weekday is never today
    assert resolve_day("tomorrow", wednesday) == date(2026, 11, 19)
    assert resolve_day(None, wednesday) is None


# ---------------------------------------------------------------- EMI


def test_the_assistant_works_out_an_emi_like_the_calculator(client):
    data = say(client, "What's the EMI at Aranya Courtyard with 30% down?")
    emi = data["emi"]
    loan = round(8_600_000 * 0.7)
    assert emi["listing_id"] == "PUN-002" and emi["loan_inr"] == loan and (emi["rate_pct"], emi["years"]) == (8.5, 20)
    assert emi["emi_inr"] == round(monthly_emi(loan, 8.5, 20))
    assert format_rupees(emi["emi_inr"]) in data["reply"] and data["mode"] == "template"


def test_an_emi_needs_to_know_which_home(client):
    data = say(client, "what is the emi?")
    assert data["emi"] is None and "Which home" in data["reply"]


def test_an_emi_on_a_property_page_is_for_that_home(client):
    assert say(client, "EMI for 15 years?", listing_id="BLR-002")["emi"]["listing_id"] == "BLR-002"


def test_the_second_one_means_the_second_home_shown(client):
    visitor_id, session_id = ids()
    shown = say(client, "3BHK under 90L in Pune", visitor_id, session_id)["listings"]
    data = say(client, "emi for the second one", visitor_id, session_id)
    assert data["emi"]["listing_id"] == shown[1]["id"]


# ---------------------------------------------------------------- brochures


def test_brochure_search_finds_the_right_section():
    assert search("payment plan", listing_ids=["PUN-002"])[0].section == "Payment plan"
    assert search("when is possession", listing_ids=["HYD-003"])[0].section == "Possession and handover"
    assert search("पार्किंग", listing_ids=["BLR-004"])[0].section == "Parking"
    assert search("शाळा आणि दवाखाना", listing_ids=["NOI-001"])[0].section.startswith("Schools")
    assert search("xyzzy", listing_ids=["PUN-001"]) == []
    assert {item.listing_id for item in search("parking", listing_ids=["MUM-001"], limit=5)} == {"MUM-001"}


def test_the_assistant_answers_from_the_brochure(client):
    data = say(client, "What's the payment plan at Aranya Courtyard?")
    assert "Aranya Courtyard brochure (Payment plan)" in data["reply"] and "on booking" in data["reply"]


def test_a_brochure_question_on_a_property_page(client):
    data = say(client, "how much is the maintenance?", listing_id="MUM-002")
    assert "Seawind Residency brochure (Maintenance and society)" in data["reply"]


def test_a_brochure_question_without_a_home_asks_which(client):
    assert "Which home" in say(client, "Is there parking?")["reply"]


# ---------------------------------------------------------------- site visits


def next_saturday() -> str:
    return resolve_day("saturday", today_ist()).isoformat()


def test_a_visit_without_contact_details_asks_for_them(client):
    visitor_id, session_id = ids()
    data = say(client, "Book a site visit to Aranya Courtyard on Saturday morning", visitor_id, session_id)
    action = data["action"]
    assert action["type"] == "contact_form" and action["need_contact"] is True and action["purpose"] == "site_visit"
    assert action["listing_id"] == "PUN-002" and action["day"] == next_saturday() and action["slot"] == "morning"
    assert client.get("/visits").status_code == 200
    assert not client.get(f"/visitors/{visitor_id}").json()["site_visits"]


def test_the_form_books_the_visit_and_saves_an_enquiry(client):
    visitor_id, session_id = ids()
    say(client, "site visit please at Indigo Greens", visitor_id, session_id)
    body = {"visitor_id": visitor_id, "session_id": session_id, "listing_id": "PUN-003", "day": next_saturday(), "slot": "evening",
            "name": "Rohan Patil", "phone": phone(), "consent": True, "form_fill_ms": 12_000, "language": "hinglish"}
    response = client.post("/visits", json=body)
    assert response.status_code == 201
    visit = response.json()
    assert visit["project"] == "Indigo Greens" and visit["status"] == "requested" and visit["name"] == "Rohan Patil"
    assert visit["confirmation"].startswith("Ho gaya") and "shaam" in visit["confirmation"]

    detail = client.get(f"/visitors/{visitor_id}").json()
    assert detail["leads"][0]["source"] == "chat" and detail["site_visits"][0]["id"] == visit["id"]
    points = {point["signal"]: point for point in detail["score_detail"]["intent"]["points"]}
    assert points["site_visit"]["points"] == 15 and "Indigo Greens" in points["site_visit"]["detail"]


def test_a_visitor_with_an_enquiry_is_booked_at_once(client):
    visitor_id, session_id = ids()
    enquire(client, visitor_id, session_id)
    data = say(client, "Book a site visit on Sunday evening", visitor_id, session_id, listing_id="PUN-002")
    assert data["action"]["type"] == "visit_booked"
    assert data["action"]["visit"]["slot"] == "evening" and "Sun" in data["action"]["visit"]["day_text"]
    assert "Aranya Courtyard" in data["reply"]
    assert len(client.get(f"/visitors/{visitor_id}").json()["site_visits"]) == 1

    say(client, "Book a site visit on Sunday morning", visitor_id, session_id, listing_id="PUN-002")  # the same day changes the slot
    visits = client.get(f"/visitors/{visitor_id}").json()["site_visits"]
    assert len(visits) == 1 and visits[0]["slot"] == "morning"


def test_a_known_visitor_without_a_day_gets_a_day_picker(client):
    visitor_id, session_id = ids()
    enquire(client, visitor_id, session_id)
    action = say(client, "I want a site visit", visitor_id, session_id, listing_id="PUN-002")["action"]
    assert action["type"] == "contact_form" and action["need_contact"] is False and action["day"] is None


def test_a_visit_needs_real_details(client):
    base = {"listing_id": "PUN-002", "day": next_saturday(), "visitor_id": str(uuid.uuid4())}
    assert client.post("/visits", json=base).status_code == 422
    assert client.post("/visits", json={**base, "name": "Asha", "phone": phone()}).status_code == 422  # no consent
    assert client.post("/visits", json={**base, "listing_id": "NOPE-9"}).status_code == 404
    past = (today_ist() - timedelta(days=1)).isoformat()
    assert client.post("/visits", json={**base, "day": past, "name": "Asha", "phone": phone(), "consent": True}).status_code == 422


def test_cancelling_a_visit_takes_its_points_away(client):
    visitor_id, session_id = ids()
    enquire(client, visitor_id, session_id)
    visit = say(client, "Book a site visit on Saturday", visitor_id, session_id, listing_id="PUN-002")["action"]["visit"]
    assert client.patch(f"/visits/{visit['id']}", json={"status": "confirmed"}).json()["status"] == "confirmed"
    assert any(row["id"] == visit["id"] for row in client.get("/visits", params={"status": "confirmed"}).json())
    assert client.patch(f"/visits/{visit['id']}", json={"status": "cancelled"}).status_code == 200
    points = client.get(f"/visitors/{visitor_id}").json()["score_detail"]["intent"]["points"]
    assert "site_visit" not in {point["signal"] for point in points}
    assert client.patch("/visits/999999", json={"status": "done"}).status_code == 404


def test_a_call_back(client):
    visitor_id, session_id = ids()
    assert say(client, "please call me", visitor_id, session_id)["action"]["purpose"] == "callback"
    enquire(client, visitor_id, session_id)
    data = say(client, "please call me", visitor_id, session_id)
    assert data["action"] is None and "number you shared" in data["reply"]


# ---------------------------------------------------------------- languages


@pytest.mark.parametrize(
    ("message", "language"),
    [
        ("3BHK under 90L in Pune", "en"),
        ("Pune mein 90 lakh tak 3BHK chahiye", "hinglish"),
        ("मुझे पुणे में 90 लाख तक 3BHK चाहिए", "hi"),
        ("पुण्यात 90 लाखांपर्यंत 3BHK हवा आहे", "mr"),
        ("mala pune madhe ghar pahije", "mr"),
    ],
)
def test_languages_are_told_apart(message, language):
    assert detect_language(message) == language


def test_marathi_details_are_understood():
    found = extract_details("मला मुंबईत १.५ कोटीपर्यंत तीन बीएचके घर हवे आहे, ६ महिन्यांत, गृहकर्ज नको, गुंतवणुकीसाठी")
    assert found["city"] == "Mumbai" and found["bhk"] == 3 and found["budget_max"] == 15_000_000
    assert found["timeline_months"] == 6 and found["purpose"] == "investment" and found["language"] == "mr"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Pune mein 90 lakh tak 3BHK chahiye", "ghar mile"),
        ("मुझे पुणे में 90 लाख तक 3BHK चाहिए", "घर मिले"),
        ("पुण्यात 90 लाखांपर्यंत 3BHK हवा आहे", "घरे मिळाली"),
    ],
)
def test_template_replies_use_the_visitors_language(client, message, expected):
    data = say(client, message)
    assert expected in data["reply"] and "Indigo Greens" in data["reply"]


def test_a_short_reply_keeps_the_conversations_language(client):
    visitor_id, session_id = ids()
    say(client, "पुण्यात घर हवे आहे", visitor_id, session_id)
    data = say(client, "3 BHK", visitor_id, session_id)
    assert data["profile"]["language"] == "mr" and "बजेट" in data["reply"]


def test_emi_and_brochure_replies_in_hinglish(client):
    data = say(client, "Aranya Courtyard ka EMI kitna hoga 30% down par?")
    assert "mahina aayegi" in data["reply"]
    assert "brochure ke hisaab se" in say(client, "Aranya Courtyard mein parking kitni hai bhai kya bataoge?")["reply"]


# ---------------------------------------------------------------- with an LLM, and when things fail


class FakeLLM:
    """Stands in for the LLM: answers the understanding call and records what it was sent."""

    def __init__(self, plan=None, understand_error=None, reply_error=None):
        self.plan, self.understand_error, self.reply_error = plan or {}, understand_error, reply_error
        self.seen: list = []

    def available(self):
        return True

    def generate_json(self, system, messages, schema, **kwargs):
        self.seen.append(("json", messages[0]["content"], schema))
        if self.understand_error:
            raise self.understand_error
        return {"city": None, "locality": None, "bhk": None, "budget_min": None, "budget_max": None, "timeline_months": None,
                "loan_needed": None, "purpose": None, "language": "en", "goal": "small_talk", "home_name": None, "home_position": None,
                "down_payment_pct": None, "rate_pct": None, "emi_years": None, "visit_day": None, "visit_slot": None,
                "search_words": None, **self.plan}  # fmt: skip

    def generate(self, system, messages, **kwargs):
        self.seen.append(("text", messages[-1]["content"]))
        if self.reply_error:
            raise self.reply_error
        return "A reply from the LLM."


def use_llm(monkeypatch, fake):
    monkeypatch.setattr(agent_module, "llm", fake)
    monkeypatch.setattr(extract_module, "llm", fake)
    return fake


def test_one_llm_call_understands_and_one_replies(client, monkeypatch):
    fake = use_llm(monkeypatch, FakeLLM({"goal": "emi", "home_name": "Aranya Courtyard", "down_payment_pct": 25, "emi_years": 15}))
    data = say(client, "kitna padega har mahine agar quarter down du? call 9822012345")
    assert data["mode"] == "llm" and data["reply"] == "A reply from the LLM."
    assert data["emi"]["down_payment_pct"] == 25 and data["emi"]["years"] == 15 and data["emi"]["listing_id"] == "PUN-002"
    assert [kind for kind, *_ in fake.seen] == ["json", "text"]
    assert all("9822012345" not in sent[1] for sent in fake.seen) and "[phone]" in fake.seen[0][1]
    assert '"emi"' in fake.seen[1][1] and '"visitor_wants": "emi"' in fake.seen[1][1]


def test_the_llms_answers_are_checked(client, monkeypatch):
    use_llm(monkeypatch, FakeLLM({"goal": "launch_rockets", "down_payment_pct": 400, "rate_pct": -2, "home_name": "No Such Tower", "home_position": 9}))
    data = say(client, "EMI for Aranya Courtyard")
    assert data["emi"]["down_payment_pct"] == 20 and data["emi"]["rate_pct"] == 8.5 and data["emi"]["listing_id"] == "PUN-002"


def test_brochure_passages_reach_the_llm(client, monkeypatch):
    fake = use_llm(monkeypatch, FakeLLM({"goal": "brochure", "search_words": "payment plan booking amount"}))
    say(client, "bhugtan kaise karna hoga?", listing_id="PUN-002")
    assert '"brochure"' in fake.seen[1][1] and "Payment plan" in fake.seen[1][1]


def test_llm_failures_fall_back_to_patterns_and_templates(client, monkeypatch):
    use_llm(monkeypatch, FakeLLM(understand_error=LLMError("timeout"), reply_error=LLMError("rate limit")))
    data = say(client, "What's the EMI at Aranya Courtyard with 30% down?")
    assert data["mode"] == "template" and data["emi"]["down_payment_pct"] == 30


def test_a_broken_graph_still_answers(client, monkeypatch):
    class Broken:
        def invoke(self, state):
            raise RuntimeError("the graph broke")

    monkeypatch.setattr(agent_module, "AGENT", Broken())
    visitor_id, session_id = ids()
    data = say(client, "3BHK under 90L in Pune", visitor_id, session_id)
    assert data["mode"] == "template" and data["listings"]
    assert client.get(f"/visitors/{visitor_id}").json()["visitor"]["profile"]["bhk"] == 3
