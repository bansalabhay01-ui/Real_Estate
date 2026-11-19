"""Privacy: erasure, the retention clean-up, the mocked OTP and the dashboard passcode."""

import random
import uuid
from datetime import timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

from app import auth
from app.db import SessionLocal
from app.models import ChatMessage, Event, Feedback, Lead, Nudge, Score, SiteVisit, Visitor, VisitSession
from app.retention import ERASED_NAME, purge_old
from app.utils import utcnow

CONTEXT = {"webdriver": False, "languages": 2, "timezone": "Asia/Kolkata"}


def phone() -> str:
    return "98" + str(random.randint(10_000_000, 99_999_999))


def visitor_with_everything(client, *, message="Please call me about this home."):
    visitor_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    batch = {"visitor_id": visitor_id, "session_id": session_id, "context": CONTEXT, "events": [{"type": "page_view", "ts": 1, "path": "/property/PUN-002"}]}
    assert client.post("/events", json=batch).status_code == 200
    client.post("/chat", json={"visitor_id": visitor_id, "session_id": session_id, "message": "3BHK under 90L in Pune"})
    body = {"visitor_id": visitor_id, "session_id": session_id, "listing_id": "PUN-002", "name": "Asha Rao", "phone": phone(), "email": "asha.rao@gmail.com",
            "message": message, "consent": True, "form_fill_ms": 30_000}  # fmt: skip
    lead = client.post("/leads", json=body).json()
    client.post("/feedback", json={"visitor_id": visitor_id, "label": "genuine", "note": "Spoke to Asha"})
    return visitor_id, session_id, lead


def rows_about(visitor_id):
    with SessionLocal() as db:
        return {table.__name__: db.query(table).filter(table.visitor_id == visitor_id).count()
                for table in (Event, VisitSession, ChatMessage, Lead, Score, Feedback, SiteVisit, Nudge)}  # fmt: skip


# ---------------------------------------------------------------- erasure


def test_a_visitor_can_erase_their_own_data(client):
    visitor_id, _, _ = visitor_with_everything(client)
    assert rows_about(visitor_id)["Lead"] == 1
    response = client.delete(f"/visitors/{visitor_id}", headers={"X-LeadOps-Visitor": visitor_id})
    assert response.status_code == 200 and response.json() == {"ok": True}
    assert client.get(f"/visitors/{visitor_id}").status_code == 404
    assert set(rows_about(visitor_id).values()) == {0}
    assert client.delete(f"/visitors/{visitor_id}", headers={"X-LeadOps-Visitor": visitor_id}).status_code == 404


def test_erasing_tells_open_dashboards(client):
    visitor_id, _, _ = visitor_with_everything(client)
    with client.websocket_connect("/ws/dashboard") as ws:
        assert ws.receive_json()["type"] == "snapshot"
        client.delete(f"/visitors/{visitor_id}")
        assert ws.receive_json()["type"] == "snapshot"


# ---------------------------------------------------------------- the retention clean-up


def make_old(visitor_id, days):
    long_ago = utcnow() - timedelta(days=days)
    with SessionLocal() as db:
        db.query(Event).filter(Event.visitor_id == visitor_id).update({Event.received_at: long_ago})
        db.query(ChatMessage).filter(ChatMessage.visitor_id == visitor_id).update({ChatMessage.created_at: long_ago})
        db.query(VisitSession).filter(VisitSession.visitor_id == visitor_id).update({VisitSession.last_seen: long_ago})
        db.query(Lead).filter(Lead.visitor_id == visitor_id).update({Lead.created_at: long_ago})
        db.query(Feedback).filter(Feedback.visitor_id == visitor_id).update({Feedback.created_at: long_ago})
        db.query(Visitor).filter(Visitor.id == visitor_id).update({Visitor.last_seen: long_ago})
        db.commit()


def test_old_enquiries_lose_every_personal_detail(client):
    visitor_id, _, _ = visitor_with_everything(client)
    make_old(visitor_id, 200)
    removed = purge_old(180)
    assert removed["enquiries"] >= 1 and removed["events"] >= 1 and removed["chat"] >= 2
    counts = rows_about(visitor_id)
    assert counts["Event"] == 0 and counts["ChatMessage"] == 0 and counts["VisitSession"] == 0 and counts["Lead"] == 1
    with SessionLocal() as db:
        lead = db.query(Lead).filter(Lead.visitor_id == visitor_id).one()
        assert (lead.name, lead.phone, lead.email, lead.message, lead.ip) == (ERASED_NAME, "deleted", None, None, None)
        visitor = db.get(Visitor, visitor_id)
        assert visitor.profile == {} and visitor.last_ip is None and visitor.feedback_note is None
        assert db.query(Feedback).filter(Feedback.visitor_id == visitor_id).one().note is None


def test_old_visitors_who_never_enquired_are_removed(client):
    visitor_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    client.post("/events", json={"visitor_id": visitor_id, "session_id": session_id, "context": CONTEXT, "events": [{"type": "page_view", "ts": 1, "path": "/"}]})
    make_old(visitor_id, 200)
    assert purge_old(180)["visitors"] >= 1
    assert client.get(f"/visitors/{visitor_id}").status_code == 404


def test_recent_data_is_left_alone(client):
    visitor_id, _, _ = visitor_with_everything(client)
    make_old(visitor_id, 30)
    purge_old(180)
    detail = client.get(f"/visitors/{visitor_id}").json()
    assert detail["leads"][0]["name"] == "Asha Rao" and detail["events"] and detail["chat"]


# ---------------------------------------------------------------- the mocked OTP


def enquiry(client, number=None):
    visitor_id = str(uuid.uuid4())
    body = {"visitor_id": visitor_id, "name": "Asha Rao", "phone": number or phone(), "consent": True, "form_fill_ms": 30_000}
    return visitor_id, client.post("/leads", json=body).json()


def test_a_right_code_verifies_the_phone(client):
    visitor_id, lead = enquiry(client, "9823012345")
    otp = lead["otp"]
    assert otp["phone"] == "+91 98xxx xx345" and len(otp["demo_code"]) == 6
    answer = client.post(f"/leads/{lead['lead_id']}/verify", json={"token": otp["token"], "code": otp["demo_code"]}).json()
    assert answer == {"verified": True, "tries_left": 0}
    detail = client.get(f"/visitors/{visitor_id}").json()
    assert detail["leads"][0]["phone_verified"] is True
    assert {"check": "otp", "ok": True, "text": "Phone verified by OTP"} in detail["leads"][0]["checks"]
    points = {point["signal"]: point["points"] for point in detail["score_detail"]["intent"]["points"]}
    assert points["phone_verified"] == 5


def test_wrong_codes_run_out(client):
    _, lead = enquiry(client)
    url, token = f"/leads/{lead['lead_id']}/verify", lead["otp"]["token"]
    answers = [client.post(url, json={"token": token, "code": "000000"}).json() for _ in range(5)]
    assert [answer["tries_left"] for answer in answers] == [4, 3, 2, 1, 0] and not any(answer["verified"] for answer in answers)
    assert client.post(url, json={"token": token, "code": lead["otp"]["demo_code"]}).status_code == 429


def test_a_code_needs_the_enquirys_token(client):
    _, lead = enquiry(client)
    assert client.post(f"/leads/{lead['lead_id']}/verify", json={"token": "x" * 32, "code": lead["otp"]["demo_code"]}).status_code == 403
    assert client.post("/leads/99999999/verify", json={"token": "x" * 32, "code": "123456"}).status_code == 403


def test_a_fake_number_gets_no_otp(client):
    assert enquiry(client, "9999999999")[1]["otp"] is None


def test_the_code_is_never_shown_on_the_dashboard(client):
    visitor_id, lead = enquiry(client)
    detail = client.get(f"/visitors/{visitor_id}").text
    assert lead["otp"]["demo_code"] not in detail and lead["otp"]["token"] not in detail


# ---------------------------------------------------------------- the dashboard passcode

LOCKED = [("GET", "/stats"), ("GET", "/visitors"), ("GET", "/leads"), ("GET", "/visits"), ("GET", "/feedback"), ("GET", "/demo/status"),
          ("GET", "/auth/check"), ("POST", "/scoring/rescore"), ("GET", "/visitors/someone"), ("GET", "/visitors/someone/brief")]  # fmt: skip


@pytest.fixture
def locked(monkeypatch):
    monkeypatch.setattr(auth, "current_passcode", lambda: "open-sesame")


@pytest.mark.parametrize(("method", "path"), LOCKED)
def test_dashboard_routes_need_the_passcode(client, locked, method, path):
    assert client.request(method, path).status_code == 401
    assert client.request(method, path, headers={"X-LeadOps-Passcode": "wrong"}).status_code == 401
    assert client.request(method, path, headers={"X-LeadOps-Passcode": "open-sesame"}).status_code != 401


def test_what_visitors_use_stays_open(client, locked):
    visitor_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    batch = {"visitor_id": visitor_id, "session_id": session_id, "context": CONTEXT, "events": [{"type": "page_view", "ts": 1, "path": "/"}]}
    assert client.post("/events", json=batch).status_code == 200
    assert client.post("/chat", json={"visitor_id": visitor_id, "message": "hello"}).status_code == 200
    assert client.get("/listings").status_code == 200
    assert client.post("/leads", json={"visitor_id": visitor_id, "name": "Asha Rao", "phone": phone(), "consent": True}).status_code == 201
    assert client.get("/health").json()["dashboard_locked"] is True


def test_only_the_visitor_or_sales_can_erase_when_locked(client, locked):
    visitor_id, _ = enquiry(client)
    assert client.delete(f"/visitors/{visitor_id}").status_code == 401
    assert client.delete(f"/visitors/{visitor_id}", headers={"X-LeadOps-Visitor": "someone-else"}).status_code == 401
    assert client.delete(f"/visitors/{visitor_id}", headers={"X-LeadOps-Visitor": visitor_id}).status_code == 200


def test_the_live_feed_needs_the_passcode(client, locked):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/dashboard"):
            pass
    with client.websocket_connect("/ws/dashboard?passcode=open-sesame") as ws:
        assert ws.receive_json()["type"] == "snapshot"


def test_without_a_passcode_nothing_changes(client):
    assert client.get("/auth/check").json() == {"ok": True} and client.get("/health").json()["dashboard_locked"] is False
