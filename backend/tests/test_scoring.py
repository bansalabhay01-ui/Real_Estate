"""Scoring engine tests: contact checks, rules, features, and features computed live match those from training data."""

import importlib.util
import json
import math
import random
import uuid

import pytest

from app.ai.extract import profile_from_messages
from app.config import REPO_DIR
from app.db import SessionLocal
from app.scoring.engine import load_record
from app.scoring.features import MODEL_FEATURES, add_network_counts, cut_record, model_vector, pages, visitor_features
from app.scoring.rules import BOT, CERTAIN, JUNK, STRONG, check_email, check_message, check_phone, evaluate, is_junk_text

DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"


def codes(signals, layer=None, strength=None):
    return {s.code for s in signals if (layer is None or s.layer == layer) and (strength is None or s.strength == strength)}


# ---------------------------------------------------------------- contact checks


@pytest.mark.parametrize(
    ("number", "kind"),
    [
        ("9822012345", "mobile"), ("+91 98220 12345", "mobile"), ("09822012345", "mobile"), ("919822012345", "mobile"),
        ("+971 501234567", "international"), ("+44 7911 123456", "international"), ("0044 7911 123456", "international"),
        ("9999999999", "fake"), ("9876543210", "fake"), ("1234567890", "fake"), ("0000000000", "fake"),
        ("9898989898", "fake"), ("98765", "invalid"), ("5822012345", "invalid"), ("", "invalid"),
    ],
)  # fmt: skip
def test_phone_check(number, kind):
    assert check_phone(number).kind == kind


@pytest.mark.parametrize(
    ("email", "kind"),
    [
        ("priya.kulkarni12@gmail.com", "ok"), ("hello@startup.in", "ok"), (None, "none"), ("", "none"),
        ("asdf@mailinator.com", "fake"), ("test@test.com", "fake"), ("rahul@example.com", "fake"),
        ("rahul.m@yopmail.com", "disposable"), ("someone@sub.mailinator.com", "disposable"), ("priya@gmail", "invalid"),
    ],
)  # fmt: skip
def test_email_check(email, kind):
    assert check_email(email).kind == kind


def test_placeholder_text_but_not_real_names():
    for junk in ("asdf", "Test", "test user", "aaaa", "qwerty", "n/a", "123", "zxcvb"):
        assert is_junk_text(junk), junk
    for real in ("Priya Kulkarni", "Om", "Ali Khan", "प्रिया शर्मा", "K. Rao", "Harpreet Singh"):
        assert not is_junk_text(real), real


def test_messages():
    assert codes(check_message("Get 10x leads with our SEO services! http://cheap-seo.example")) == {"spam_message"}
    assert "broker_message" in codes(check_message("I am a channel partner. Share your inventory."))
    assert codes(check_message("I saw it on https://99acres.com/x, is it available?")) == {"link_in_message"}
    # A buyer asking whether they pay brokerage is not a broker.
    assert codes(check_message("Is there any brokerage? I want to buy directly.")) == set()
    assert codes(check_message("test")) == {"junk_message"}


# ---------------------------------------------------------------- rules on whole visitors


def browsing(start=1_000_000, pages_open=3, dwell_ms=30_000, *, human=True):
    events, t = [], start
    for n in range(pages_open):
        path = f"/property/PUN-00{n + 1}"
        events.append({"type": "page_view", "ts": t, "path": path, "props": {}})
        if human:
            events.append({"type": "activity", "ts": t + 10_000, "path": path,
                           "props": {"mouse_moves": 80, "mouse_distance": 900, "touches": 0, "keys": 0, "scrolls": 12}})
            events.append({"type": "scroll_depth", "ts": t + 5_000, "path": path, "props": {"percent": 25}})
        t += dwell_ms
        events.append({"type": "page_leave", "ts": t, "path": path, "props": {"duration_ms": dwell_ms}})
        t += 2_000
    return events


def visitor(*, events=None, leads=None, context=None, ua=DESKTOP_UA, chat=None):
    return {
        "visitor_id": str(uuid.uuid4()), "user_agent": ua,
        "context": context or {"webdriver": False, "languages": 2, "timezone": "Asia/Kolkata", "screen": "1920x1080", "viewport": "1920x947"},
        "sessions": [{"session_id": "s1", "ip": "198.18.0.1", "events": events if events is not None else browsing()}],
        "leads": leads or [], "chat": chat or [], "profile": {}, "network": {"ip_visitors": 1, "phone_visitors": 1},
    }  # fmt: skip


def lead(**fields):
    base = {"name": "Priya Kulkarni", "phone": "9822012345", "email": "priya@gmail.com", "message": "Site visit please",
            "honeypot": None, "form_fill_ms": 45_000, "client_ts": 1_200_000}
    return {**base, **fields}


def signals_for(record):
    return evaluate(record, visitor_features(record))


def test_a_genuine_enquiry_fires_nothing():
    assert signals_for(visitor(leads=[lead()])) == []


def test_certain_bot_signals():
    signals = signals_for(visitor(leads=[lead(honeypot="http://promo.example")], context={"webdriver": True}))
    assert {"honeypot", "webdriver"} <= codes(signals, BOT, CERTAIN)
    assert "automation_ua" in codes(signals_for(visitor(ua="python-requests/2.32.3")), BOT, CERTAIN)


def test_autofill_speed_is_not_a_bot_signal_but_instant_is():
    assert codes(signals_for(visitor(leads=[lead(form_fill_ms=1_600)]))) == set()  # browser autofill
    assert codes(signals_for(visitor(leads=[lead(form_fill_ms=400)]))) == {"instant_form"}
    assert codes(signals_for(visitor(leads=[lead(form_fill_ms=0)])), BOT, STRONG) == {"instant_form"}


def test_an_ad_blocked_buyer_is_only_a_strong_signal():
    record = visitor(events=[], leads=[lead()])
    signals = signals_for(record)
    assert codes(signals) == {"no_browsing_enquiry"} and signals[0].strength == STRONG


def test_scraping_and_scripted_clicks():
    fast = browsing(pages_open=10, dwell_ms=600, human=False)
    assert "scraping" in codes(signals_for(visitor(events=fast)), BOT, STRONG)
    clicks = browsing(pages_open=2) + [{"type": "click", "ts": 1_100_000, "path": "/", "props": {"trusted": False}}]
    assert "scripted_clicks" in codes(signals_for(visitor(events=clicks)))
    mixed = clicks + [{"type": "click", "ts": 1_100_500, "path": "/", "props": {"trusted": True}}]
    assert "scripted_clicks" not in codes(signals_for(visitor(events=mixed)))  # a person clicked too


def test_junk_details():
    signals = signals_for(visitor(leads=[lead(name="asdf", phone="9999999999", email="test@test.com")]))
    assert {"junk_name", "fake_phone", "fake_email"} <= codes(signals, JUNK, CERTAIN)
    nri = signals_for(visitor(leads=[lead(phone="+971 501234567")]))
    assert codes(nri) == set()  # NRI buyers' numbers are fine
    assert "disposable_email" in codes(signals_for(visitor(leads=[lead(email="rahul.m@yopmail.com")])), JUNK, STRONG)
    shared = visitor(leads=[lead()])
    shared["network"]["phone_visitors"] = 4
    assert "shared_phone" in codes(signals_for(shared), JUNK, STRONG)


def test_a_broker_in_chat():
    record = visitor(chat=[{"text": "Do you have inventory for my clients in Pune?", "ts": 1_100_000}])
    assert "broker_message" in codes(signals_for(record), JUNK, CERTAIN)


# ---------------------------------------------------------------- features


def test_page_dwell_comes_from_page_leave_or_the_next_page():
    events = [
        {"type": "page_view", "ts": 0, "path": "/"},
        {"type": "page_view", "ts": 4_000, "path": "/property/PUN-001"},  # the first page had no page_leave
        {"type": "page_leave", "ts": 20_000, "path": "/property/PUN-001", "props": {"duration_ms": 12_000}},
        {"type": "page_view", "ts": 21_000, "path": "/property/PUN-002"},
        {"type": "click", "ts": 26_000, "path": "/property/PUN-002", "props": {"trusted": True}},  # still open
    ]
    found = pages(events)
    assert [(p["dwell"], p["done"]) for p in found] == [(4_000, True), (12_000, True), (5_000, False)]


def test_features_and_model_vector():
    record = visitor(leads=[lead()])
    f = visitor_features(record)
    assert f["page_views"] == 3 and f["property_views"] == 3 and f["leads"] == 1
    assert f["median_dwell_s"] == 30 and f["fast_pages"] == 0 and f["min_fill_s"] == 45
    assert f["viewport_matches_screen"] == 0 and f["timezone_utc"] == 0
    assert math.isnan(visitor_features(visitor(events=[]))["median_dwell_s"])  # unknown, not zero
    vector = model_vector(f)
    assert len(vector) == len(MODEL_FEATURES)
    assert "emi_used" not in MODEL_FEATURES and "property_views" not in MODEL_FEATURES  # what, not how


def test_cut_record_keeps_only_what_had_happened():
    record = visitor(leads=[lead(client_ts=1_200_000)])
    early = cut_record(record, 1_040_000)
    assert len(early["sessions"][0]["events"]) < len(record["sessions"][0]["events"]) and early["leads"] == []


def test_network_counts_for_a_dataset():
    first, second, third = visitor(leads=[lead()]), visitor(leads=[lead()]), visitor(leads=[lead(phone="9822099999")])
    third["sessions"][0]["ip"] = "198.18.0.99"
    add_network_counts([first, second, third])
    assert first["network"] == {"ip_visitors": 2.0, "phone_visitors": 2}
    assert third["network"] == {"ip_visitors": 1.0, "phone_visitors": 1}


# ---------------------------------------------------------------- live features == training features


def test_features_from_the_database_match_the_record(client):
    record = visitor(leads=[lead(client_ts=1_150_000)], chat=[{"text": "3BHK under 90L in Pune?", "ts": 1_120_000}])
    record["sessions"].append({"session_id": str(uuid.uuid4()), "ip": record["sessions"][0]["ip"],
                               "events": browsing(start=90_000_000, pages_open=1)})
    record["sessions"][0]["session_id"] = str(uuid.uuid4())
    record["sessions"][0]["ip"] = record["sessions"][1]["ip"] = f"198.19.{random.randint(0, 255)}.{random.randint(1, 254)}"
    record["leads"][0]["phone"] = "9" + str(random.randint(100_000_000, 999_999_999))
    headers = {"User-Agent": DESKTOP_UA, "X-Forwarded-For": record["sessions"][0]["ip"]}

    first, later = record["sessions"]
    for session in (first, later):
        batch = {"visitor_id": record["visitor_id"], "session_id": session["session_id"], "context": record["context"],
                 "events": session["events"]}
        assert client.post("/events", content=json.dumps(batch), headers={**headers, "Content-Type": "text/plain"}).status_code == 200
        if session is first:
            body = {"visitor_id": record["visitor_id"], "session_id": first["session_id"], "message": record["chat"][0]["text"]}
            assert client.post("/chat", json=body, headers=headers).status_code == 200
            enquiry = {key: value for key, value in record["leads"][0].items() if key != "ip"}
            body = {**enquiry, "visitor_id": record["visitor_id"], "session_id": first["session_id"]}
            assert client.post("/leads", json=body, headers=headers).status_code == 201

    record["profile"] = profile_from_messages([message["text"] for message in record["chat"]])
    for item in record["leads"]:
        item["ip"] = first["ip"]
    add_network_counts([record])
    with SessionLocal() as db:
        live = load_record(db, record["visitor_id"])
    expected, actual = visitor_features(record), visitor_features(live)
    assert expected.keys() == actual.keys()
    for name in expected:
        both_nan = math.isnan(expected[name]) and math.isnan(actual[name])
        assert both_nan or expected[name] == pytest.approx(actual[name]), name


# ---------------------------------------------------------------- the simulator


def _simulator():
    spec = importlib.util.spec_from_file_location("simulator", REPO_DIR / "ml" / "simulator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_simulated_genuine_buyers_never_trip_a_certain_signal():
    sim = _simulator()
    rng = random.Random(7)
    records = [sim.make_genuine(rng) for _ in range(150)]
    for item in records:
        item.place(1_793_000_000_000)
    records = [item.record() for item in records]
    add_network_counts(records)
    for record in records:
        record["profile"] = profile_from_messages([message["text"] for message in record["chat"]])
        assert not codes(signals_for(record), strength=CERTAIN), record["kind"]
