"""The analytics page's numbers."""

import random
import uuid
from datetime import timedelta

from app import analytics as analytics_module
from app.db import SessionLocal
from app.models import Visitor
from app.utils import today_ist, utcnow

HUMAN = {"webdriver": False, "languages": 3, "timezone": "Asia/Kolkata"}


def visit(client, context=None, path="/property/PUN-002"):
    visitor_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    batch = {"visitor_id": visitor_id, "session_id": session_id, "context": context or HUMAN, "events": [{"type": "page_view", "ts": 1, "path": path}]}
    assert client.post("/events", json=batch).status_code == 200
    return visitor_id, session_id


def enquire(client, visitor_id, session_id, *, phone=None, source=None):
    body = {"visitor_id": visitor_id, "session_id": session_id, "listing_id": "PUN-002", "name": "Asha Rao", "consent": True, "form_fill_ms": 30_000,
            "phone": phone or "98" + str(random.randint(10_000_000, 99_999_999)), "source": source}  # fmt: skip
    assert client.post("/leads", json=body).status_code == 201


def numbers(client, **params):
    return client.get("/analytics", params={"days": 14, **params}).json()


def step(data, name):
    return next(item["count"] for item in data["funnel"] if item["step"] == name)


def test_the_funnel_narrows_step_by_step(client):
    before = numbers(client)
    visit(client, {**HUMAN, "webdriver": True})  # a bot
    junk_id, junk_session = visit(client)
    enquire(client, junk_id, junk_session, phone="9999999999")  # a person with a fake number
    real_id, real_session = visit(client)
    enquire(client, real_id, real_session)  # a real contact
    visit(client)  # a person who only looked
    after = numbers(client)
    assert after["visitors"] == before["visitors"] + 4
    assert step(after, "people") == step(before, "people") + 3
    assert step(after, "contacts") == step(before, "contacts") + 1
    assert after["enquiries"] == before["enquiries"] + 2 and after["enquiries_filtered"] == before["enquiries_filtered"] + 1
    counts = [item["count"] for item in after["funnel"]]
    assert counts == sorted(counts, reverse=True)


def test_hours_saved_states_its_assumption(client):
    junk_id, junk_session = visit(client)
    enquire(client, junk_id, junk_session, phone="9999999999")
    data = numbers(client)
    assert data["minutes_per_enquiry"] == analytics_module.MINUTES_PER_FAKE_ENQUIRY
    assert data["hours_saved"] == round(data["enquiries_filtered"] * data["minutes_per_enquiry"] / 60, 1)


def test_every_day_of_the_period_is_listed_and_adds_up(client):
    visit(client)
    data = numbers(client, days=7)
    assert len(data["daily"]) == 7 and data["daily"][-1]["day"] == today_ist().isoformat()
    assert sum(day["kept"] + day["junk"] + day["bots"] for day in data["daily"]) == data["visitors"]


def test_older_visitors_fall_outside_the_period(client):
    visitor_id, _ = visit(client)
    with SessionLocal() as db:
        db.get(Visitor, visitor_id).first_seen = utcnow() - timedelta(days=30)
        db.commit()
    assert numbers(client, days=14)["visitors"] < numbers(client, days=60)["visitors"]


def test_simulated_traffic_can_be_left_out(client):
    client.post("/demo/simulate", json={"bots": 3, "junk": 2, "genuine": 2, "seconds": 0, "seed": 8})
    assert numbers(client, simulated=True)["visitors"] == numbers(client, simulated=False)["visitors"] + client.get("/demo/status").json()["simulated_visitors"]
    client.delete("/demo/simulated")


def test_offers_and_visits_are_counted(client):
    before = numbers(client)
    visitor_id, session_id = visit(client)
    enquire(client, visitor_id, session_id, source="assistant_offer")
    assert numbers(client)["found_by_assistant"] == before["found_by_assistant"] + 1


def test_the_period_is_limited(client):
    assert client.get("/analytics", params={"days": 0}).status_code == 422
    assert client.get("/analytics", params={"days": 365}).status_code == 422
