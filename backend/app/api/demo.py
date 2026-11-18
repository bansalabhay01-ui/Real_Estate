"""The live demo tools on the dashboard: Simulate traffic, clear simulated visitors and run a real bot.

Simulate traffic makes visitors with ml/simulator.py and feeds them through the same code as the real API (store,
visitor type, score, dashboard updates), spread over about half a minute so an audience can watch them being sorted.
Because the simulator knows what each visitor really is, the run ends with a scoreboard. Simulated visitors get IDs
starting with "sim-", which is how Clear finds them; real and tester visitors are never touched. They never call an
LLM: chat messages aren't sent and the visitor type comes from the keyword rules.
"""

import asyncio
import importlib.util
import ipaddress
import logging
import random
import subprocess
import sys
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from urllib.parse import urlsplit

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select

from ..config import REPO_DIR
from ..db import SessionLocal
from ..models import Visitor
from ..realtime import hub
from ..retention import erase_visitors
from ..schemas import (
    BotRunIn,
    BotRunStarted,
    DemoStatusOut,
    EventBatchIn,
    LeadIn,
    ScoreboardOut,
    SimulatedRemoved,
    SimulateIn,
    SimulationKindOut,
    SimulationStarted,
)
from ..scoring.engine import ScoreUpdate, broadcast_snapshot, classify_safely, publish, score_safely
from ..tracking import store_event_batch, store_lead

log = logging.getLogger("leadops.demo")
router = APIRouter(prefix="/demo", tags=["demo"])

SIM_PREFIX = "sim-"
BATCH_SIZE = 50
PROGRESS_EVERY_S = 0.4
LATEST_END_MS = 60_000  # simulated visits end within the last minute, so they look live
BOT_SCRIPT = REPO_DIR / "ml" / "bots" / "run_bots.py"
BOT_TIMEOUT_S = 240
FILTERED = {"Bot", "Junk"}


@dataclass
class Run:
    run_id: str
    total: int
    sent: int = 0
    labels: Counter = field(default_factory=Counter)


_run: Run | None = None  # the run in progress (one at a time)
_scoreboard: ScoreboardOut | None = None  # the latest finished run
_bot_running = False


@lru_cache(maxsize=1)
def _simulator():
    """ml/simulator.py (standard library only), or None where the ml folder isn't deployed."""
    path = REPO_DIR / "ml" / "simulator.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("leadops_simulator", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _replay(simulated) -> tuple[str, ScoreUpdate | None, list]:
    """Send one simulated visitor through the real ingestion code. Blocking: runs in a worker thread."""
    visitor_id = SIM_PREFIX + simulated.visitor_id
    context = {**simulated.context, "user_agent": simulated.user_agent}
    leads, summary = [], None
    for visit in simulated.visits:
        for start in range(0, len(visit.events), BATCH_SIZE):
            batch = EventBatchIn.model_validate({
                "visitor_id": visitor_id, "session_id": visit.session_id, "site": "leadops-simulator",
                "sdk_version": "simulator", "sent_at": int(time.time() * 1000), "context": context,
                "events": visit.events[start : start + BATCH_SIZE],
            })  # fmt: skip
            summary = store_event_batch(batch, visit.ip, simulated.user_agent)
        for lead in visit.leads:
            fields = {key: value for key, value in lead.items() if key != "ip"}
            payload = LeadIn.model_validate({**fields, "visitor_id": visitor_id})
            saved, summary = store_lead(payload, lead["ip"], simulated.user_agent)
            leads.append(saved)
    has_message = any(lead.message for lead in leads)
    update = classify_safely(visitor_id, use_llm=False) if has_message else score_safely(visitor_id)
    return visitor_id, update or (summary and ScoreUpdate(summary, None)), leads


async def _send(simulated) -> tuple[str, str | None]:
    visitor_id, update, leads = await run_in_threadpool(_replay, simulated)
    label = update.visitor.label if update else None
    for lead in leads:
        await hub.broadcast({"type": "lead_created", "lead": lead.model_copy(update={"label": label}).model_dump(mode="json")})
    await publish(None, update)
    return visitor_id, label


def _scoreboard_for(run: Run, truth: dict[str, tuple[str, str]], seconds: float) -> ScoreboardOut:
    """What each visitor really was against the label it has now."""
    ids = list(truth)
    with SessionLocal() as db:
        labels = dict(db.execute(select(Visitor.id, Visitor.label).where(Visitor.id.in_(ids))).all())
    by_kind: dict[str, Counter] = {}
    groups: dict[str, Counter] = {"bot": Counter(), "junk": Counter(), "genuine": Counter()}
    for visitor_id, (group, kind) in truth.items():
        label = labels.get(visitor_id) or "Not scored"
        by_kind.setdefault(f"{group}/{kind}", Counter())[label] += 1
        groups[group][label] += 1

    def filtered(counts: Counter) -> int:
        return sum(count for label, count in counts.items() if label in FILTERED)

    return ScoreboardOut(
        run_id=run.run_id, total=run.total, seconds=round(seconds, 1),
        bots_total=sum(groups["bot"].values()), bots_blocked=filtered(groups["bot"]),
        junk_total=sum(groups["junk"].values()), junk_filtered=filtered(groups["junk"]),
        genuine_total=sum(groups["genuine"].values()),
        genuine_kept=sum(groups["genuine"].values()) - filtered(groups["genuine"]),
        genuine_labels=dict(groups["genuine"]),
        kinds=[SimulationKindOut(kind=kind, total=sum(counts.values()), labels=dict(counts)) for kind, counts in sorted(by_kind.items())],
    )  # fmt: skip


async def _simulate(run: Run, visitors: list, seconds: float) -> None:
    global _run, _scoreboard
    started = time.monotonic()
    pace = seconds / max(1, run.total)
    truth: dict[str, tuple[str, str]] = {}
    last_progress = 0.0
    try:
        await hub.broadcast({"type": "simulation_started", "run_id": run.run_id, "total": run.total})
        for number, simulated in enumerate(visitors, start=1):
            visitor_id, label = await _send(simulated)
            truth[visitor_id] = (simulated.label, simulated.kind)
            run.sent = number
            run.labels[label or "Not scored"] += 1
            now = time.monotonic()
            if now - last_progress >= PROGRESS_EVERY_S or number == run.total:
                last_progress = now
                await hub.broadcast({"type": "simulation_progress", "run_id": run.run_id, "sent": run.sent, "total": run.total,
                                     "labels": dict(run.labels)})
            wait = started + pace * number - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
        _scoreboard = await run_in_threadpool(_scoreboard_for, run, truth, time.monotonic() - started)
    except Exception:
        log.exception("The simulated run failed")
    finally:
        _run = None
        finished = _scoreboard if _scoreboard and _scoreboard.run_id == run.run_id else None
        await hub.broadcast({"type": "simulation_done", "run_id": run.run_id,
                             "scoreboard": finished.model_dump(mode="json") if finished else None})


@router.post("/simulate", response_model=SimulationStarted, status_code=202)
async def simulate(payload: SimulateIn, background: BackgroundTasks) -> SimulationStarted:
    """Send simulated traffic (by default 200 bots, 30 junk leads and 20 real buyers) and sort it live."""
    global _run
    if _run is not None:
        raise HTTPException(status_code=409, detail="A simulated run is already going")
    simulator = _simulator()
    if simulator is None:
        raise HTTPException(status_code=501, detail="Simulated traffic needs the ml/ folder next to the backend")
    rng = random.Random(payload.seed)
    visitors = simulator.make_visitors(payload.bots, payload.junk, payload.genuine, rng)
    now_ms = int(time.time() * 1000)
    for visitor in visitors:
        visitor.place(now_ms - rng.randint(0, LATEST_END_MS))
    _run = Run(run_id=uuid.uuid4().hex[:12], total=len(visitors))
    background.add_task(_simulate, _run, visitors, payload.seconds)
    return SimulationStarted(run_id=_run.run_id, total=_run.total, seconds=payload.seconds)


def _simulated_count() -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(Visitor).where(Visitor.id.like(f"{SIM_PREFIX}%"))) or 0


def _erase_simulated() -> int:
    with SessionLocal() as db:
        ids = list(db.scalars(select(Visitor.id).where(Visitor.id.like(f"{SIM_PREFIX}%"))))
        return erase_visitors(db, ids)


@router.delete("/simulated", response_model=SimulatedRemoved)
async def clear_simulated() -> SimulatedRemoved:
    """Remove the visitors the button made, so a rehearsal can start clean. Real visitors are never touched."""
    global _scoreboard
    if _run is not None:
        raise HTTPException(status_code=409, detail="Wait for the simulated run to finish")
    removed = await run_in_threadpool(_erase_simulated)
    _scoreboard = None
    await broadcast_snapshot()
    return SimulatedRemoved(removed=removed)


def bot_available() -> bool:
    """Real bots need Playwright, which only the training setup (ml/requirements.txt) installs."""
    return BOT_SCRIPT.is_file() and importlib.util.find_spec("playwright") is not None


@router.get("/status", response_model=DemoStatusOut)
def status() -> DemoStatusOut:
    """Where the demo tools stand, for a dashboard that has just opened."""
    run = _run
    return DemoStatusOut(
        running=run is not None, run_id=run.run_id if run else None, sent=run.sent if run else 0,
        total=run.total if run else 0, labels=dict(run.labels) if run else {}, scoreboard=_scoreboard,
        simulated_visitors=_simulated_count(), bot_available=bot_available(), bot_running=_bot_running,
    )  # fmt: skip


def _local_site(url: str) -> bool:
    """Bots only ever open this laptop or a device on its own network."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def _run_bot(payload: BotRunIn, api: str) -> tuple[bool, str]:
    command = [sys.executable, str(BOT_SCRIPT), "--kind", payload.kind, "--site", payload.site.rstrip("/"), "--api", api]
    if payload.headed:
        command += ["--headed", "--slow-mo", "120"]
    try:
        done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=BOT_TIMEOUT_S, cwd=REPO_DIR)  # fmt: skip
    except subprocess.TimeoutExpired:
        return False, "The bot didn't finish in time."
    lines = [line for line in (done.stdout + "\n" + done.stderr).splitlines() if line.strip()]
    return done.returncode == 0, lines[-1] if lines else "The bot ended without saying anything."


async def _bot_job(payload: BotRunIn, api: str) -> None:
    global _bot_running
    try:
        ok, summary = await run_in_threadpool(_run_bot, payload, api)
    except Exception:
        log.exception("Running the bot failed")
        ok, summary = False, "The bot couldn't start."
    _bot_running = False
    await hub.broadcast({"type": "bot_finished", "kind": payload.kind, "ok": ok, "summary": summary})


@router.post("/bot", response_model=BotRunStarted, status_code=202)
async def run_bot(payload: BotRunIn, request: Request, background: BackgroundTasks) -> BotRunStarted:
    """Run one real Playwright bot on the laptop that runs this backend, against the demo site."""
    global _bot_running
    if not bot_available():
        raise HTTPException(status_code=501, detail="Real bots only run on a laptop with ml/requirements.txt installed")
    if not _local_site(payload.site):
        raise HTTPException(status_code=422, detail="Bots only open a site on this laptop or its own network")
    if _bot_running:
        raise HTTPException(status_code=409, detail="A bot is already running")
    _bot_running = True
    port = (request.scope.get("server") or ("127.0.0.1", 8000))[1]
    await hub.broadcast({"type": "bot_started", "kind": payload.kind})
    background.add_task(_bot_job, payload, f"http://127.0.0.1:{port}")
    return BotRunStarted(kind=payload.kind)
