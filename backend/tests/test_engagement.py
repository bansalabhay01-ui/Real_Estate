"""After the score: the smart engagement trigger (and, as they arrive, the lead brief, verdicts and consistency checks)."""

import json
import random
import uuid
from datetime import timedelta

import pytest

from app.db import SessionLocal
from app.models import Nudge, Visitor, VisitSession
from app.scoring import nudge as nudge_module
from app.utils import utcnow

CONTEXT = {"webdriver": False, "languages": 3, "timezone": "Asia/Kolkata", "screen": "1920x1080", "viewport": "1536x730",
           "hardware_concurrency": 8, "language": "en-IN"}  # fmt: skip
HEADERS = {"Content-Type": "text/plain", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"}


def post(client, visitor_id, session_id, events, context=None):
    batch = {"visitor_id": visitor_id, "session_id": session_id, "context": context or CONTEXT, "events": events}
    response = client.post("/events", content=json.dumps(batch), headers=HEADERS)
    assert response.status_code == 200
    return response.json()


def browsing(start, homes=("PUN-002", "PUN-003"), *, emi=True, floor_plan=False):
    """A person looking closely at a few homes: long pages, small mouse moves, scrolling."""
    events, t = [], start
    for home in homes:
        path = f"/property/{home}"
        events.append({"type": "page_view", "ts": t, "path": path, "props": {}})
        events.append({"type": "property_view", "ts": t + 500, "path": path, "props": {"listing_id": home}})
        for tick in range(1, 13):
            events.append({"type": "activity", "ts": t + tick * 10_000, "path": path,
                           "props": {"interval_ms": 10_000, "mouse_moves": random.randint(60, 140), "mouse_distance": random.randint(700, 1500),
                                     "clicks": 1, "touches": 0, "keys": 0, "scrolls": random.randint(5, 20)}})  # fmt: skip
        events.append({"type": "scroll_depth", "ts": t + 15_000, "path": path, "props": {"percent": 50}})
        t += 125_000
        events.append({"type": "page_leave", "ts": t, "path": path, "props": {"duration_ms": 125_000, "max_scroll_pct": 75}})
        t += random.randint(2_000, 6_000)
    if emi:
        events.append({"type": "emi_used", "ts": t, "path": f"/property/{homes[0]}",
                       "props": {"listing_id": homes[0], "price_inr": 8_600_000, "emi": 59_706}})  # fmt: skip
    if floor_plan:
        events.append({"type": "floorplan_download", "ts": t + 1000, "path": f"/property/{homes[0]}", "props": {"listing_id": homes[0], "bhk": 3}})
    return events


def age_the_visit(session_id, seconds=300):
    with SessionLocal() as db:
        db.get(VisitSession, session_id).started_at = utcnow() - timedelta(seconds=seconds)
        db.commit()


def serious_visitor(client, *, floor_plan=False):
    """A visitor who has browsed long enough, ready for the next batch."""
    visitor_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    answer = post(client, visitor_id, session_id, browsing(1_790_000_000_000, floor_plan=floor_plan))
    assert "nudge" not in answer  # the visit is still too young
    age_the_visit(session_id)
    return visitor_id, session_id


def still_here(start=1_790_001_000_000, path="/property/PUN-002"):
    return [{"type": "activity", "ts": start, "path": path, "props": {"interval_ms": 10_000, "mouse_moves": 90, "mouse_distance": 1000, "clicks": 0,
                                                                      "touches": 0, "keys": 0, "scrolls": 8}}]  # fmt: skip


# ---------------------------------------------------------------- the trigger


def test_a_serious_anonymous_visitor_gets_one_offer(client):
    visitor_id, session_id = serious_visitor(client)
    visitor = client.get(f"/visitors/{visitor_id}").json()["visitor"]
    assert visitor["label"] in ("Warm", "Hot") and visitor["score"]["human_prob"] >= 0.8

    offer = post(client, visitor_id, session_id, still_here())["nudge"]
    assert offer["kind"] == "floor_plan" and offer["listing_id"] == "PUN-002" and offer["project"] == "Aranya Courtyard"
    assert "3 BHK floor plan of Aranya Courtyard" in offer["text"] and offer["cta"] and "floor plan" in offer["ask"]
    assert "nudge" not in post(client, visitor_id, session_id, still_here(1_790_001_010_000))  # once per visit


def test_the_offer_fits_what_they_have_done(client):
    visitor_id, session_id = serious_visitor(client, floor_plan=True)
    offer = post(client, visitor_id, session_id, still_here())["nudge"]
    assert offer["kind"] == "emi_plan" and "₹86 L" in offer["text"]


def test_a_returning_visitor_is_offered_a_site_visit():
    row = Visitor.new("v" * 12, session_count=3, score={"detail": {"intent": {"points": [{"signal": "floor_plan"}]}}})
    from app.listings import get_listing

    assert nudge_module.choose_kind(row, get_listing("PUN-002")) == "site_visit"
    assert nudge_module.choose_kind(row, None) == "shortlist"


def test_the_offer_speaks_the_visitors_language(client):
    visitor_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    post(client, visitor_id, session_id, browsing(1_790_000_000_000), {**CONTEXT, "language": "hi-IN"})
    age_the_visit(session_id)
    offer = post(client, visitor_id, session_id, still_here(), {**CONTEXT, "language": "hi-IN"})["nudge"]
    assert offer["language"] == "hi" and "फ्लोर प्लान" in offer["text"]


@pytest.mark.parametrize("why", ["left_details", "chatting", "too_young", "not_on_a_home", "automated"])
def test_who_does_not_get_an_offer(client, why):
    visitor_id, session_id = serious_visitor(client)
    events, context = still_here(), CONTEXT
    if why == "left_details":
        body = {"visitor_id": visitor_id, "session_id": session_id, "name": "Priya Kulkarni", "phone": "98" + str(random.randint(10_000_000, 99_999_999)),
                "consent": True, "form_fill_ms": 30_000}  # fmt: skip
        assert client.post("/leads", json=body).status_code == 201
    elif why == "chatting":
        assert client.post("/chat", json={"visitor_id": visitor_id, "session_id": session_id, "message": "hello"}).status_code == 200
    elif why == "too_young":
        age_the_visit(session_id, seconds=10)
    elif why == "not_on_a_home":
        events = still_here(path="/")
    else:
        context = {**CONTEXT, "webdriver": True}
    assert "nudge" not in post(client, visitor_id, session_id, events, context)


def test_at_most_two_offers_a_day(client):
    visitor_id, session_id = serious_visitor(client)
    assert post(client, visitor_id, session_id, still_here())["nudge"]
    for number in (2, 3):
        next_session = str(uuid.uuid4())
        post(client, visitor_id, next_session, still_here(1_790_002_000_000 + number))
        age_the_visit(next_session)
        answer = post(client, visitor_id, next_session, still_here(1_790_003_000_000 + number))
        assert ("nudge" in answer) == (number == 2)


def test_what_became_of_an_offer_is_saved(client):
    visitor_id, session_id = serious_visitor(client)
    offer = post(client, visitor_id, session_id, still_here())["nudge"]
    before = client.get("/stats").json()
    for kind in ("nudge_shown", "nudge_accepted"):
        post(client, visitor_id, session_id, [{"type": kind, "ts": 1_790_001_020_000, "path": "/property/PUN-002", "props": {"nudge_id": offer["id"], "kind": offer["kind"]}}])
    with SessionLocal() as db:
        assert db.get(Nudge, offer["id"]).status == "accepted"

    body = {"visitor_id": visitor_id, "session_id": session_id, "listing_id": "PUN-002", "name": "Asha Rao", "consent": True, "form_fill_ms": 14_000,
            "phone": "97" + str(random.randint(10_000_000, 99_999_999)), "message": offer["ask"], "source": "assistant_offer"}  # fmt: skip
    assert client.post("/leads", json=body).status_code == 201
    after = client.get("/stats").json()
    assert after["assistant_leads"] == before["assistant_leads"] + 1 and after["offers_accepted"] == before["offers_accepted"] + 1
    detail = client.get(f"/visitors/{visitor_id}").json()
    assert detail["leads"][0]["source"] == "assistant_offer" and detail["nudges"][0]["status"] == "accepted"


def test_someone_elses_offer_cannot_be_changed(client):
    visitor_id, session_id = serious_visitor(client)
    offer = post(client, visitor_id, session_id, still_here())["nudge"]
    post(client, str(uuid.uuid4()), str(uuid.uuid4()), [{"type": "nudge_dismissed", "ts": 1, "path": "/", "props": {"nudge_id": offer["id"]}}])
    with SessionLocal() as db:
        assert db.get(Nudge, offer["id"]).status == "sent"


def test_a_bad_offer_decision_never_costs_an_event_batch(client, monkeypatch):
    monkeypatch.setattr(nudge_module, "_next_offer", lambda batch: 1 / 0)
    visitor_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    assert post(client, visitor_id, session_id, still_here()) == {"ok": True, "accepted": 1}


# ---------------------------------------------------------------- an offer sent by hand


def test_sales_can_send_an_offer_by_hand(client):
    visitor_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    post(client, visitor_id, session_id, still_here())  # far too early for an automatic offer
    response = client.post(f"/visitors/{visitor_id}/nudge")
    assert response.status_code == 201
    queued = response.json()
    assert client.post(f"/visitors/{visitor_id}/nudge").json()["id"] == queued["id"]  # pressing twice queues one offer

    delivered = post(client, visitor_id, session_id, still_here(1_790_001_030_000))["nudge"]
    assert delivered["id"] == queued["id"]
    assert client.get(f"/visitors/{visitor_id}").json()["nudges"][0]["trigger"] == "sales"
    assert "nudge" not in post(client, visitor_id, session_id, still_here(1_790_001_040_000))


def test_offers_by_hand_have_limits(client):
    assert client.post("/visitors/nobody-here/nudge").status_code == 404
    bot_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    post(client, bot_id, session_id, still_here(), {**CONTEXT, "webdriver": True})
    assert client.post(f"/visitors/{bot_id}/nudge").status_code == 409

    known_id = str(uuid.uuid4())
    body = {"visitor_id": known_id, "name": "Asha Rao", "phone": "96" + str(random.randint(10_000_000, 99_999_999)), "consent": True}
    client.post("/leads", json=body)
    assert client.post(f"/visitors/{known_id}/nudge").status_code == 409


# ---------------------------------------------------------------- the lead brief and the next step

from app.ai import brief as brief_module  # noqa: E402
from app.ai.brief import next_step  # noqa: E402
from app.ai.llm_client import LLMError  # noqa: E402


def enquiring_visitor(client, *, name="Priya Kulkarni", email="priya.k@gmail.com", phone=None):
    visitor_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    post(client, visitor_id, session_id, browsing(1_790_000_000_000, floor_plan=True))
    number = phone or "98" + str(random.randint(10_000_000, 99_999_999))
    body = {"visitor_id": visitor_id, "session_id": session_id, "listing_id": "PUN-002", "name": name, "phone": number, "email": email,
            "consent": True, "form_fill_ms": 40_000, "message": "Please share the details."}  # fmt: skip
    assert client.post("/leads", json=body).status_code == 201
    return visitor_id, number


@pytest.mark.parametrize(
    ("label", "details", "action", "urgency"),
    [
        ("Hot", {"has_contact": True}, "call", "now"),
        ("Hot", {"has_contact": False}, "offer", "now"),
        ("Warm", {"has_contact": True}, "whatsapp", "today"),
        ("Warm", {"has_contact": False}, "offer", "today"),
        ("Cold", {"has_contact": True}, "whatsapp", "this_week"),
        ("Cold", {"has_contact": False}, "none", "none"),
        ("Review", {"has_contact": True}, "review", "today"),
        ("Bot", {"has_contact": True}, "none", "none"),
        ("Junk", {"has_contact": True}, "none", "none"),
        ("Hot", {"has_contact": True, "visit": "Aranya Courtyard on Sat 21 Nov, morning"}, "confirm_visit", "now"),
        ("Warm", {"has_contact": True, "call_requested": True}, "call", "now"),
        ("Hot", {"has_contact": True, "verdict": "converted"}, "none", "none"),
        ("Hot", {"has_contact": True, "verdict": "fake"}, "none", "none"),
    ],
)
def test_the_next_step(label, details, action, urgency):
    fields = {"verdict": None, "visit": None, "reason": "Checked the EMI on a ₹86 L home", **details}
    step = next_step(label, **fields)
    assert (step.action, step.urgency) == (action, urgency)


def test_a_brief_has_three_plain_lines_and_a_next_step(client):
    visitor_id, _ = enquiring_visitor(client)
    brief = client.get(f"/visitors/{visitor_id}/brief").json()
    assert len(brief["lines"]) == 3 and brief["mode"] == "template"
    assert "Aranya Courtyard" in brief["lines"][0] and "Has shared contact details" in brief["lines"][2]
    assert brief["next_step"]["action"] in ("call", "whatsapp")
    assert client.get("/visitors/nobody-here/brief").status_code == 404


class FakeWriter:
    def __init__(self, answer=None, error=None):
        self.answer, self.error, self.sent = answer, error, []

    def available(self):
        return True

    def generate_json(self, system, messages, schema, **kwargs):
        self.sent.append(system + messages[0]["content"])
        if self.error:
            raise self.error
        return self.answer


def test_the_llm_brief_is_kept_until_the_score_changes(client, monkeypatch):
    visitor_id, _ = enquiring_visitor(client)
    fake = FakeWriter({"lines": ["Wants a 3 BHK.", "Checked the EMI.", "Ask about the loan."]})
    monkeypatch.setattr(brief_module, "llm", fake)
    assert client.get(f"/visitors/{visitor_id}/brief").json()["mode"] == "llm"
    assert client.get(f"/visitors/{visitor_id}/brief").json()["lines"][0] == "Wants a 3 BHK."
    assert len(fake.sent) == 1
    client.post("/feedback", json={"visitor_id": visitor_id, "label": "genuine"})
    client.get(f"/visitors/{visitor_id}/brief")
    assert len(fake.sent) == 2


def test_a_bad_llm_brief_falls_back(client, monkeypatch):
    visitor_id, _ = enquiring_visitor(client)
    for fake in (FakeWriter({"lines": ["Only one line."]}), FakeWriter(error=LLMError("timeout"))):
        monkeypatch.setattr(brief_module, "llm", fake)
        assert client.get(f"/visitors/{visitor_id}/brief").json()["mode"] == "template"


# ---------------------------------------------------------------- follow-up drafts


def test_a_whatsapp_draft_is_ready_to_send(client):
    visitor_id, number = enquiring_visitor(client)
    draft = client.post(f"/visitors/{visitor_id}/followup", json={"channel": "whatsapp"}).json()
    assert draft["text"].startswith("Hi Priya,") and "Aranya Courtyard" in draft["text"] and "₹59,706" in draft["text"]
    assert draft["whatsapp_number"] == "91" + number and draft["whatsapp_url"].startswith(f"https://wa.me/91{number}?text=Hi%20Priya")
    assert draft["mode"] == "template"


def test_an_email_draft_has_a_subject(client):
    visitor_id, _ = enquiring_visitor(client)
    draft = client.post(f"/visitors/{visitor_id}/followup", json={"channel": "email"}).json()
    assert "Aranya Courtyard" in draft["subject"] and draft["text"].endswith("LeadOps Realty sales team")
    assert draft["mailto_url"].startswith("mailto:priya.k@gmail.com?subject=")


@pytest.mark.parametrize(("language", "greeting"), [("hinglish", "Namaste Priya"), ("hi", "नमस्ते Priya"), ("mr", "नमस्कार Priya")])
def test_drafts_in_the_buyers_language(client, language, greeting):
    visitor_id, _ = enquiring_visitor(client)
    assert client.post(f"/visitors/{visitor_id}/followup", json={"language": language}).json()["text"].startswith(greeting)


def test_a_draft_follows_the_language_they_chatted_in(client):
    visitor_id, _ = enquiring_visitor(client)
    client.post("/chat", json={"visitor_id": visitor_id, "message": "पुण्यात 90 लाखांपर्यंत 3BHK हवा आहे"})
    draft = client.post(f"/visitors/{visitor_id}/followup", json={}).json()
    assert draft["language"] == "mr" and draft["text"].startswith("नमस्कार Priya")


def test_names_and_numbers_never_reach_the_llm(client, monkeypatch):
    visitor_id, number = enquiring_visitor(client, name="Sunita Rangarajan", email="sunita.r@gmail.com")
    fake = FakeWriter({"subject": "Your home", "text": "Hi {name}, thanks for looking at Aranya Courtyard. Can you visit on Saturday?"})
    monkeypatch.setattr(brief_module, "llm", fake)
    draft = client.post(f"/visitors/{visitor_id}/followup", json={"channel": "email"}).json()
    assert draft["mode"] == "llm" and draft["text"].startswith("Hi Sunita,")
    fake.answer = {"lines": ["One.", "Two.", "Three."]}
    client.get(f"/visitors/{visitor_id}/brief")
    assert len(fake.sent) == 2
    for sent in fake.sent:
        assert "Sunita" not in sent and "Rangarajan" not in sent and number not in sent and "sunita.r" not in sent


def test_a_draft_without_the_placeholder_uses_the_template(client, monkeypatch):
    visitor_id, _ = enquiring_visitor(client)
    monkeypatch.setattr(brief_module, "llm", FakeWriter({"subject": "Hi", "text": "Dear customer, please call us."}))
    assert client.post(f"/visitors/{visitor_id}/followup", json={}).json()["mode"] == "template"


def test_a_draft_for_someone_without_a_number(client):
    visitor_id, _ = serious_visitor(client)
    draft = client.post(f"/visitors/{visitor_id}/followup", json={}).json()
    assert draft["text"].startswith("Hi there,") and draft["whatsapp_url"] is None and draft["mailto_url"] is None
    assert client.post("/visitors/nobody-here/followup", json={}).status_code == 404


# ---------------------------------------------------------------- sales verdicts


def visitor_now(client, visitor_id):
    return client.get(f"/visitors/{visitor_id}").json()["visitor"]


def test_fake_makes_a_visitor_junk_at_once(client):
    visitor_id, _ = enquiring_visitor(client)
    assert client.post("/feedback", json={"visitor_id": visitor_id, "label": "fake", "note": "Wrong number"}).status_code == 201
    visitor = visitor_now(client, visitor_id)
    assert visitor["label"] == "Junk" and visitor["score"]["reasons"][0] == "Marked fake by the sales team"
    assert visitor["feedback"]["label"] == "fake" and visitor["feedback"]["note"] == "Wrong number"
    assert client.get(f"/visitors/{visitor_id}/brief").json()["next_step"]["action"] == "none"


def test_genuine_overrules_the_rules_and_the_model(client):
    visitor_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    post(client, visitor_id, session_id, still_here(), {**CONTEXT, "webdriver": True})
    assert visitor_now(client, visitor_id)["label"] == "Bot"
    client.post("/feedback", json={"visitor_id": visitor_id, "label": "genuine"})
    visitor = visitor_now(client, visitor_id)
    assert visitor["label"] == "Cold" and visitor["score"]["reasons"][0] == "Confirmed genuine by the sales team"


def test_a_verdict_on_an_enquiry_reaches_its_visitor(client):
    visitor_id, _ = enquiring_visitor(client)
    lead_id = client.get(f"/visitors/{visitor_id}").json()["leads"][0]["id"]
    client.post("/feedback", json={"lead_id": lead_id, "label": "converted"})
    assert visitor_now(client, visitor_id)["feedback"]["label"] == "converted"
    assert client.get(f"/leads/{lead_id}").json()["verdict"] == "converted"
    assert client.get(f"/visitors/{visitor_id}/brief").json()["next_step"]["text"].startswith("Nothing to do")


def test_the_latest_verdict_wins(client):
    visitor_id, _ = enquiring_visitor(client)
    client.post("/feedback", json={"visitor_id": visitor_id, "label": "fake"})
    client.post("/feedback", json={"visitor_id": visitor_id, "label": "genuine"})
    assert visitor_now(client, visitor_id)["label"] != "Junk"


# ---------------------------------------------------------------- says versus does

from app.scoring.consistency import consistency_checks  # noqa: E402


def looked_at(*homes):
    return [{"events": [{"type": "property_view", "ts": index, "path": f"/property/{home}", "props": {"listing_id": home}} for index, home in enumerate(homes)]}]


def by_check(record):
    return {item["check"]: item for item in consistency_checks(record)}


def test_a_budget_that_doesnt_match_the_homes_opened():
    found = by_check({"profile": {"budget_max": 5_000_000}, "sessions": looked_at("MUM-001", "BLR-001", "NOI-001")})
    assert found["budget"]["ok"] is False and "Says under ₹50 L" in found["budget"]["text"] and "₹1.6" in found["budget"]["text"]
    found = by_check({"profile": {"budget_min": 25_000_000}, "sessions": looked_at("MUM-004", "NOI-003", "PUN-004")})
    assert found["budget"]["ok"] is False and "Says above ₹2.5 Cr" in found["budget"]["text"]


def test_a_budget_that_fits():
    found = by_check({"profile": {"budget_max": 9_000_000}, "sessions": looked_at("PUN-002", "PUN-003", "PUN-004")})
    assert found["budget"]["ok"] is True


def test_city_and_bhk_mismatches():
    found = by_check({"profile": {"city": "Pune", "bhk": 4}, "sessions": looked_at("MUM-001", "MUM-002", "NOI-003")})
    assert found["city"] == {"check": "city", "ok": False, "text": "Says Pune but opened homes only in Mumbai, Noida"}
    assert found["bhk"]["ok"] is False and "2 BHK" in found["bhk"]["text"]


def test_two_homes_are_too_few_to_judge():
    assert consistency_checks({"profile": {"city": "Pune", "budget_max": 5_000_000, "bhk": 4}, "sessions": looked_at("MUM-001", "MUM-002")}) == []


def test_saying_both_to_live_in_and_to_invest():
    chat = [{"text": "It is for my family to live in"}, {"text": "What rental yield can I expect from this investment?"}]
    assert by_check({"profile": {}, "sessions": [], "chat": chat})["purpose"]["ok"] is False
    assert "purpose" not in by_check({"profile": {}, "sessions": [], "chat": chat[:1]})


def test_mismatches_come_first():
    checks = consistency_checks({"profile": {"city": "Mumbai", "bhk": 4}, "sessions": looked_at("MUM-001", "MUM-002", "MUM-004")})
    assert [item["ok"] for item in checks] == [False, True]


def test_a_mismatch_shows_but_never_changes_the_label(client):
    visitor_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    post(client, visitor_id, session_id, browsing(1_790_000_000_000, homes=("MUM-001", "BLR-001", "NOI-001"), emi=False))
    before = client.get(f"/visitors/{visitor_id}").json()["visitor"]["label"]
    client.post("/chat", json={"visitor_id": visitor_id, "session_id": session_id, "message": "I need something under 50 lakh"})
    detail = client.get(f"/visitors/{visitor_id}").json()
    budget = next(item for item in detail["score_detail"]["consistency"] if item["check"] == "budget")
    assert budget["ok"] is False and detail["visitor"]["label"] == before
    assert "Ask about this" in client.get(f"/visitors/{visitor_id}/brief").json()["lines"][2]


# ---------------------------------------------------------------- learning from the sales team


@pytest.fixture(scope="module")
def trainer():
    pytest.importorskip("sklearn")
    pytest.importorskip("lightgbm")
    import importlib.util

    from app.config import REPO_DIR

    spec = importlib.util.spec_from_file_location("leadops_train", REPO_DIR / "ml" / "train.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def judged(verdict, **extra):
    good_lead = {"name": "Priya Kulkarni", "phone": "9822012345", "email": "priya.k@gmail.com", "message": "Please call me", "form_fill_ms": 40_000, "client_ts": 2}
    return {"visitor_id": str(uuid.uuid4()), "user_agent": HEADERS["User-Agent"], "context": CONTEXT, "verdict": verdict, "kind": "sales_verdict",
            "label": "bot" if verdict == "fake" else "genuine", "sessions": [{"session_id": "s", "ip": "198.18.0.9", "events": browsing(1_000_000)}],
            "leads": [good_lead], "chat": [], "profile": {}, "network": {"ip_visitors": 1, "phone_visitors": 1}, **extra}  # fmt: skip


def test_good_verdicts_teach_the_model_what_people_look_like(trainer):
    records = [judged("genuine"), judged("converted")]
    assert trainer.trainable_verdicts(records) == records


def test_a_fake_lead_with_believable_details_counts_as_a_bot(trainer):
    fake = judged("fake")
    assert trainer.trainable_verdicts([fake]) == [fake]


def test_a_person_with_bad_details_does_not_teach_the_human_check(trainer):
    made_up_number = judged("fake", leads=[{"name": "Priya Kulkarni", "phone": "9999999999", "message": "", "form_fill_ms": 40_000, "client_ts": 2}])
    broker = judged("fake", saved_type={"type": "broker", "confidence": 0.9})
    assert trainer.trainable_verdicts([made_up_number, broker]) == []


def test_verdicts_are_reported_without_the_verdict_deciding(trainer):
    from app.scoring.model import load_model

    rows = trainer.verdict_rows([judged("genuine"), judged("fake")], load_model())
    assert rows[0][0] == "genuine (sales verdict)" and rows[1][0] == "junk (sales verdict)"
    assert rows[1][1] != "Junk"  # believable details: the engine alone has no reason to call it junk


def test_intent_points_are_suggested_only_with_enough_verdicts(trainer):
    from app.scoring.model import load_model

    model = load_model()
    few = [judged("genuine"), judged("fake")]
    assert trainer.suggested_intent_points(few, model) is None
    many = [judged("genuine") for _ in range(12)] + [judged("fake", sessions=[]) for _ in range(10)]
    suggested = trainer.suggested_intent_points(many, model)
    assert suggested["property_time"]["suggested"] > suggested["property_time"]["now"]  # good leads spent far longer on homes
    assert suggested["filters"]["suggested"] == suggested["filters"]["now"]  # nobody used the filters: no evidence either way
