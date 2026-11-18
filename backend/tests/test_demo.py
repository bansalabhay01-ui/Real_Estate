"""The live demo tools: simulated traffic, its scoreboard, clearing it, and the guard rails around real bots."""

import uuid

from app.api import demo as demo_module


def run(client, **numbers):
    body = {"bots": 6, "junk": 4, "genuine": 5, "seconds": 0, "seed": 11, **numbers}
    response = client.post("/demo/simulate", json=body)
    assert response.status_code == 202
    return response.json(), client.get("/demo/status").json()


def test_a_simulated_run_is_sorted_and_scored(client):
    started, status = run(client)
    board = status["scoreboard"]
    assert started["total"] == 15 and not status["running"]
    assert board["run_id"] == started["run_id"]
    assert (board["bots_total"], board["junk_total"], board["genuine_total"]) == (6, 4, 5)
    assert board["bots_blocked"] == 6 and board["junk_filtered"] == 4 and board["genuine_kept"] == 5
    assert sum(kind["total"] for kind in board["kinds"]) == 15
    assert sum(board["genuine_labels"].values()) == 5
    assert status["simulated_visitors"] >= 15


def test_simulated_visitors_are_marked_and_scored_like_real_ones(client):
    run(client, bots=2, junk=0, genuine=2, seed=5)
    visitors = [item for item in client.get("/visitors", params={"limit": 500}).json() if item["id"].startswith("sim-")]
    assert visitors and all(item["label"] and item["score"] for item in visitors)
    assert all(item["site"] in ("leadops-simulator", None) for item in visitors)


def test_clear_removes_only_simulated_visitors(client):
    real_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    body = {"visitor_id": real_id, "session_id": session_id, "site": "tests", "context": {"webdriver": False},
            "events": [{"type": "page_view", "ts": 1, "path": "/"}]}
    assert client.post("/events", json=body).status_code == 200
    run(client, bots=2, junk=2, genuine=2, seed=3)

    removed = client.delete("/demo/simulated").json()
    assert removed["ok"] and removed["removed"] >= 6
    status = client.get("/demo/status").json()
    assert status["simulated_visitors"] == 0 and status["scoreboard"] is None
    assert client.get(f"/visitors/{real_id}").status_code == 200
    assert not [item for item in client.get("/visitors", params={"limit": 500}).json() if item["id"].startswith("sim-")]
    assert not [lead for lead in client.get("/leads", params={"limit": 500}).json() if lead["visitor_id"].startswith("sim-")]


def test_only_one_run_at_a_time(client, monkeypatch):
    monkeypatch.setattr(demo_module, "_run", demo_module.Run(run_id="busy", total=5))
    assert client.post("/demo/simulate", json={"bots": 1, "junk": 0, "genuine": 0, "seconds": 0}).status_code == 409
    assert client.delete("/demo/simulated").status_code == 409
    assert client.get("/demo/status").json()["running"] is True


def test_a_run_needs_visitors_and_sensible_numbers(client):
    assert client.post("/demo/simulate", json={"bots": 0, "junk": 0, "genuine": 0}).status_code == 422
    assert client.post("/demo/simulate", json={"bots": 100_000}).status_code == 422


def test_simulated_traffic_never_calls_the_llm(client, monkeypatch):
    from app.ai import classify as classify_module

    class Forbidden:
        def available(self):
            return True

        def generate_json(self, *args, **kwargs):
            raise AssertionError("simulated traffic must not call the LLM")

    monkeypatch.setattr(classify_module, "llm", Forbidden())
    _, status = run(client, bots=1, junk=3, genuine=3, seed=9)
    assert status["scoreboard"]["total"] == 7


def test_real_bots_need_playwright_and_a_local_site(client, monkeypatch):
    monkeypatch.setattr(demo_module, "bot_available", lambda: False)
    assert client.post("/demo/bot", json={"kind": "stealth"}).status_code == 501

    monkeypatch.setattr(demo_module, "bot_available", lambda: True)
    for site in ("https://example.com", "file:///etc/passwd", "http://8.8.8.8:5173"):
        assert client.post("/demo/bot", json={"kind": "naive", "site": site}).status_code == 422
    assert demo_module._local_site("http://localhost:5173")
    assert demo_module._local_site("http://192.168.1.23:5173")

    monkeypatch.setattr(demo_module, "_bot_running", True)
    assert client.post("/demo/bot", json={"kind": "naive", "site": "http://localhost:5173"}).status_code == 409


def test_a_bot_run_reports_what_happened(client, monkeypatch):
    monkeypatch.setattr(demo_module, "bot_available", lambda: True)
    seen = {}

    def fake_run(payload, api):
        seen.update(kind=payload.kind, api=api, headed=payload.headed)
        return True, "stealth #1: ... -> Bot"

    monkeypatch.setattr(demo_module, "_run_bot", fake_run)
    response = client.post("/demo/bot", json={"kind": "stealth", "site": "http://localhost:5173", "headed": False})
    assert response.status_code == 202 and response.json()["kind"] == "stealth"
    assert seen["kind"] == "stealth" and seen["headed"] is False and seen["api"].startswith("http://127.0.0.1:")
    assert client.get("/demo/status").json()["bot_running"] is False
