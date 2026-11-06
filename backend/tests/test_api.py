"""API tests in template mode on a throwaway database."""

import json
import uuid


def new_ids() -> tuple[str, str]:
    return str(uuid.uuid4()), str(uuid.uuid4())


def send_events(client, visitor_id, session_id, events, *, context=None):
    """Post a batch the way the SDK does: JSON in a text/plain body."""
    batch = {
        "visitor_id": visitor_id,
        "session_id": session_id,
        "site": "tests",
        "sdk_version": "test",
        "context": context or {"webdriver": False, "languages": 2},
        "events": events,
    }
    return client.post("/events", content=json.dumps(batch), headers={"Content-Type": "text/plain"})


def test_health(client):
    data = client.get("/health").json()
    assert data == {"status": "ok", "llm": "template", "listings": 18}


def test_listings_and_filters(client):
    homes = client.get("/listings", params={"city": "Pune", "bhk": 3, "max_price": 9_000_000}).json()
    assert {home["id"] for home in homes} == {"PUN-002", "PUN-003"}
    assert {home["id"] for home in client.get("/listings", params={"q": "villa"}).json()} == {"BLR-004"}
    assert client.get("/listings/pun-001").json()["project"] == "Saffron Heights"
    assert client.get("/listings/NOPE-1").status_code == 404


def test_events_build_a_visitor(client):
    visitor_id, session_id = new_ids()
    events = [
        {"type": "page_view", "ts": 1, "path": "/", "title": "Home"},
        {"type": "Click", "ts": 2, "path": "/", "props": {"text": "View"}},
        {"type": "page_view", "ts": 3, "path": "/property/PUN-002"},
    ]
    response = send_events(client, visitor_id, session_id, events)
    assert response.status_code == 200 and response.json() == {"ok": True, "accepted": 3}

    detail = client.get(f"/visitors/{visitor_id}").json()
    assert detail["visitor"]["page_views"] == 2
    assert detail["visitor"]["session_count"] == 1
    assert detail["visitor"]["last_path"] == "/property/PUN-002"
    assert detail["sessions"][0]["landing_path"] == "/"
    assert [event["type"] for event in detail["events"]] == ["page_view", "click", "page_view"]  # newest first
    assert detail["visitor"]["last_seen"].endswith("Z")
    assert visitor_id in {visitor["id"] for visitor in client.get("/visitors").json()}


def test_bad_batches_are_rejected(client):
    visitor_id, session_id = new_ids()
    assert client.post("/events", content="not json", headers={"Content-Type": "text/plain"}).status_code == 422
    assert send_events(client, "bad id!", session_id, [{"type": "page_view"}]).status_code == 422
    assert send_events(client, visitor_id, session_id, []).status_code == 422


def test_a_long_title_is_cut_not_rejected(client):
    visitor_id, session_id = new_ids()
    response = send_events(client, visitor_id, session_id, [{"type": "page_view", "title": "x" * 5000}])
    assert response.status_code == 200
    assert len(client.get(f"/visitors/{visitor_id}").json()["events"][0]["title"]) == 300


def test_automation_hints(client):
    visitor_id, session_id = new_ids()
    send_events(client, visitor_id, session_id, [{"type": "page_view", "path": "/"}], context={"webdriver": True, "languages": 0})
    hints = client.get(f"/visitors/{visitor_id}").json()["visitor"]["automation_hints"]
    assert "webdriver" in hints and "no_browser_languages" in hints


def test_tester_links_label_test_sessions(client):
    visitor_id, session_id = new_ids()
    context = {"webdriver": False, "languages": 2, "test_label": "Genuine", "tester": "t01"}
    assert send_events(client, visitor_id, session_id, [{"type": "page_view", "path": "/"}], context=context).status_code == 200
    detail = client.get(f"/visitors/{visitor_id}").json()
    assert detail["visitor"]["test_label"] == "genuine"
    assert detail["context"]["tester"] == "t01"

    # A mistyped label is dropped, never rejected: the batch still counts.
    other_id, other_session = new_ids()
    response = send_events(client, other_id, other_session, [{"type": "page_view"}], context={"test_label": "maybe"})
    assert response.status_code == 200
    assert client.get(f"/visitors/{other_id}").json()["visitor"]["test_label"] is None


def test_lead_keeps_honeypot_timing_and_ip(client):
    visitor_id, session_id = new_ids()
    send_events(client, visitor_id, session_id, [{"type": "page_view", "path": "/property/PUN-002"}])
    response = client.post(
        "/leads",
        json={
            "visitor_id": visitor_id,
            "session_id": session_id,
            "listing_id": "PUN-002",
            "name": "Asha",
            "phone": "9876543210",
            "email": "asha@example.com",
            "honeypot": "http://spam.example",
            "form_fill_ms": 1200,
            "consent": True,
        },
        headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"},
    )
    assert response.status_code == 201
    lead = client.get(f"/leads/{response.json()['lead_id']}").json()
    assert lead["honeypot"] == "http://spam.example"
    assert lead["form_fill_ms"] == 1200
    assert lead["ip"] == "203.0.113.7"  # the client, not the proxy
    assert client.get(f"/visitors/{visitor_id}").json()["visitor"]["lead_count"] == 1


def test_lead_without_the_sdk_gets_its_own_visitor(client):
    response = client.post("/leads", json={"name": "Bot", "phone": "9999999999"})
    lead = client.get(f"/leads/{response.json()['lead_id']}").json()
    assert lead["visitor_id"].startswith("nosdk-")
    visitor = client.get(f"/visitors/{lead['visitor_id']}").json()["visitor"]
    assert visitor["event_count"] == 0 and visitor["lead_count"] == 1


def test_chat_answers_from_listings_and_remembers_details(client):
    visitor_id, session_id = new_ids()
    data = client.post("/chat", json={"visitor_id": visitor_id, "session_id": session_id, "message": "3BHK under 90L in Pune?"}).json()
    assert data["mode"] == "template"
    assert [home["id"] for home in data["listings"]] == ["PUN-003", "PUN-002"]  # closest to the budget first
    assert "Indigo Greens" in data["reply"] and "Aranya Courtyard" in data["reply"]
    assert data["profile"] == {"city": "Pune", "bhk": 3, "budget_max": 9_000_000, "language": "en"}
    assert "When are you planning to move in" in data["reply"]  # next qualifying question

    data = client.post("/chat", json={"visitor_id": visitor_id, "session_id": session_id, "message": "within 3 months"}).json()
    assert data["profile"]["timeline_months"] == 3 and data["profile"]["city"] == "Pune"
    assert client.get(f"/visitors/{visitor_id}").json()["visitor"]["profile"]["timeline_months"] == 3
    history = client.get(f"/chat/{visitor_id}").json()
    assert [message["role"] for message in history] == ["user", "assistant", "user", "assistant"]


def test_chat_loosens_filters_when_nothing_matches(client):
    data = client.post("/chat", json={"message": "1 bhk in Pune under 40 lakh"}).json()
    assert data["listings"] and all(home["city"] == "Pune" for home in data["listings"])
    assert "couldn't find an exact match" in data["reply"]


def test_chat_on_a_property_page_talks_about_that_property(client):
    data = client.post("/chat", json={"message": "is it ready to move?", "listing_id": "PUN-003"}).json()
    assert data["listings"][0]["id"] == "PUN-003"
    assert data["reply"].startswith("About this home: Indigo Greens")


def test_feedback(client):
    visitor_id, session_id = new_ids()
    send_events(client, visitor_id, session_id, [{"type": "page_view", "path": "/"}])
    assert client.post("/feedback", json={"visitor_id": visitor_id, "label": "genuine"}).status_code == 201
    assert client.post("/feedback", json={"label": "fake"}).status_code == 422
    assert client.post("/feedback", json={"visitor_id": visitor_id, "label": "maybe"}).status_code == 422
    assert client.get("/feedback").json()[0]["label"] == "genuine"


def test_dashboard_websocket_snapshot_then_live_updates(client):
    with client.websocket_connect("/ws/dashboard") as ws:
        assert ws.receive_json()["type"] == "snapshot"
        visitor_id, session_id = new_ids()
        send_events(client, visitor_id, session_id, [{"type": "page_view", "path": "/"}])
        message = ws.receive_json()
        assert message["type"] == "visitor_update" and message["visitor"]["id"] == visitor_id


def test_stats_count_visitors_and_leads(client):
    before = client.get("/stats").json()
    visitor_id, session_id = new_ids()
    send_events(client, visitor_id, session_id, [{"type": "page_view", "path": "/"}])
    client.post("/leads", json={"visitor_id": visitor_id, "name": "Ravi", "phone": "9876501234"})
    after = client.get("/stats").json()
    assert after["visitors"] == before["visitors"] + 1
    assert after["leads"] == before["leads"] + 1
    assert after["active_now"] >= 1


def test_sdk_is_served(client):
    response = client.get("/sdk/leadops.js")
    assert response.status_code == 200 and "LeadOps" in response.text
