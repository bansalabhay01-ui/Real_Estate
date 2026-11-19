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
