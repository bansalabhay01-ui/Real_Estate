"""Measure LeadOps and write docs/RESULTS.md: real people, real bots and simulated traffic, always kept apart.

    backend\\.venv\\Scripts\\python ml/evaluate.py          # Mac/Linux: backend/.venv/bin/python ml/evaluate.py

Real people and real bots are the visitors in your database who came through a tester link (README, "Collecting real
test sessions"). The score is worked out afresh with the saved model, and sales verdicts are left out of it, so a label a
salesperson corrected by hand can't flatter the result. A group with no sessions says so: nothing here is estimated.
Each share comes with a 95% confidence interval (Wilson), because a test set of a few dozen people is small.
"""

import argparse
import math
import random
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "ml"))

from app.ai.classify import classify  # noqa: E402
from app.ai.extract import profile_from_messages  # noqa: E402
from app.scoring.combine import score_record  # noqa: E402
from app.scoring.features import add_network_counts  # noqa: E402
from app.scoring.model import HumanModel, load_model  # noqa: E402

LABELS = ["Bot", "Junk", "Review", "Cold", "Warm", "Hot"]
FILTERED = {"Bot", "Junk"}
BOT_NAMES = {"bot-naive": "Naive form bot", "bot-stealth": "Stealth bot", "bot-scraper": "Scraper"}
KIND_NAMES = {
    "bot/scraper": "Scrapers", "bot/slow_scraper": "Slow scrapers", "bot/form_bot": "Form bots", "bot/click_bot": "Click bots",
    "bot/stealth_form": "Stealth bots", "junk/fake_details": "Fake details", "junk/broker": "Rival brokers", "junk/spam": "Spam",
    "junk/tenant": "Renters", "genuine/serious": "Serious buyers", "genuine/casual": "Casual browsers",
}  # fmt: skip


def wilson(hits: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """The 95% confidence interval of a share: honest about how little a small sample can show."""
    if total == 0:
        return 0.0, 0.0
    share = hits / total
    middle = share + z * z / (2 * total)
    spread = z * math.sqrt(share * (1 - share) / total + z * z / (4 * total * total))
    bottom = 1 + z * z / total
    return max(0.0, (middle - spread) / bottom), min(1.0, (middle + spread) / bottom)


def share_text(hits: int, total: int) -> str:
    if total == 0:
        return "no sessions yet"
    low, high = wilson(hits, total)
    return f"**{hits}/{total}** ({hits / total:.1%}; 95% CI {low:.0%} to {high:.0%})"


def tester_rows(model: HumanModel) -> list[dict]:
    """Everyone who came through a tester link, scored afresh without any sales verdict."""
    from app.config import settings

    if settings.database_url.startswith("sqlite:///") and not Path(settings.database_url.removeprefix("sqlite:///")).exists():
        return []
    from sqlalchemy import select

    from app.db import SessionLocal, init_db
    from app.models import Visitor
    from app.scoring.engine import known_type, load_record

    init_db()
    rows = []
    with SessionLocal() as db:
        for visitor_id, context, saved_type in db.execute(select(Visitor.id, Visitor.context, Visitor.visitor_type)).all():
            truth = (context or {}).get("test_label")
            if truth:
                label = score_record(load_record(db, visitor_id), model=model, visitor_type=known_type(saved_type)).label
                rows.append({"truth": truth, "tester": (context or {}).get("tester") or "", "label": label})
    return rows


def simulated_rows(model: HumanModel, visitors: int, seed: int) -> list[dict]:
    """A new random sample of simulated visitors, scored the way the backend scores without an LLM key."""
    import simulator

    rng = random.Random(seed)
    made = simulator.make_visitors(int(visitors * 0.4), int(visitors * 0.2), visitors - int(visitors * 0.4) - int(visitors * 0.2), rng)
    now = int(time.time() * 1000)
    for visitor in made:
        visitor.place(now - rng.randint(0, 7 * simulator.DAY_MS))
    records = [visitor.record() for visitor in made]
    add_network_counts(records)
    rows = []
    for record in records:
        record["profile"] = profile_from_messages([message["text"] for message in record.get("chat") or []])
        texts = [lead.get("message") or "" for lead in record.get("leads") or []] + [message["text"] for message in record.get("chat") or []]
        kind = classify(texts, record["profile"], use_llm=False)
        rows.append({"truth": record["label"], "kind": f"{record['label']}/{record['kind']}", "label": score_record(record, model=model, visitor_type=kind).label})
    return rows


def table(rows: list[tuple[str, Counter]]) -> list[str]:
    lines = ["| Visitor | Total | " + " | ".join(LABELS) + " |", "|---|---:|" + "---:|" * len(LABELS)]
    for name, counts in rows:
        lines.append(f"| {name} | {sum(counts.values())} | " + " | ".join(str(counts.get(label, 0)) for label in LABELS) + " |")
    return lines


def headline(rows: list[dict]) -> list[str]:
    fake = [row for row in rows if row["truth"] in ("bot", "junk")]
    genuine = [row for row in rows if row["truth"] == "genuine"]
    caught = sum(row["label"] in FILTERED for row in fake)
    wrongly = sum(row["label"] in FILTERED for row in genuine)
    lines = [
        f"- **Fake visitors filtered out (recall):** {share_text(caught, len(fake))}",
        f"- **Genuine buyers kept:** {share_text(len(genuine) - wrongly, len(genuine))}",
    ]
    if caught + wrongly:
        lines.append(f"- **Of everything filtered out, truly fake (precision):** {share_text(caught, caught + wrongly)}")
    return lines


def report(model: HumanModel, testers: list[dict], simulated: list[dict], seed: int) -> str:
    bots = [row for row in testers if row["truth"] == "bot"]
    people = [row for row in testers if row["truth"] != "bot"]
    lines = [
        "# LeadOps results",
        "",
        f"Measured on {datetime.now(UTC):%d %b %Y} with the model `{model.version}` by `ml/evaluate.py`. Run it again after collecting more",
        "sessions; it rewrites this file. Scores leave out sales verdicts, and the three groups are never added together.",
        "",
        "## 1. Real people",
        "",
    ]
    if people:
        groups = [(name, Counter(row["label"] for row in people if row["truth"] == truth)) for name, truth in (("Genuine buyers", "genuine"), ("Playing junk on purpose", "junk"))]
        lines += [f"{len(people)} sessions from people browsing through tester links.", "", *headline(people), "", *table([group for group in groups if sum(group[1].values())])]
    else:
        lines += ["**No sessions collected yet.** This is the number that matters most, and it needs people, so nothing is claimed here.",
                  'Follow "Collecting real test sessions" in the README (target: 30 to 50 sessions), then run this script again.']  # fmt: skip
    lines += ["", "## 2. Real bots", ""]
    if bots:
        kinds = sorted({row["tester"] for row in bots})
        caught = sum(row["label"] in FILTERED for row in bots)
        lines += ["Playwright bots driving a real browser against the demo site (`ml/bots/run_bots.py`). The team wrote these three bots, so this shows the",
                  "engine works on real browsers. It does not show that every bot in the wild would be caught.", "",
                  f"- **Bots filtered out:** {share_text(caught, len(bots))}", "",
                  *table([(BOT_NAMES.get(kind, kind), Counter(row["label"] for row in bots if row["tester"] == kind)) for kind in kinds])]  # fmt: skip
    else:
        lines += ["**No bot runs in this database yet.** Run `python ml/bots/run_bots.py --count 5 --api http://localhost:8000`."]
    kinds = sorted({row["kind"] for row in simulated})
    lines += [
        "", "## 3. Simulated traffic", "",
        f"{len(simulated)} visitors from `ml/simulator.py`: a new random sample (seed {seed}), not the visitors the model trained on. The model did learn from the",
        "same simulator, so these numbers are the easiest of the three and are not evidence of real-world accuracy.", "",
        *headline(simulated), "",
        *table([(KIND_NAMES.get(kind, kind), Counter(row["label"] for row in simulated if row["kind"] == kind)) for kind in kinds]), "",
    ]  # fmt: skip
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure LeadOps on real people, real bots and simulated traffic.")
    parser.add_argument("--simulated", type=int, default=1000, help="how many fresh simulated visitors to score")
    parser.add_argument("--seed", type=int, default=2026, help="the same seed gives the same simulated visitors")
    parser.add_argument("--out", default=str(ROOT / "docs" / "RESULTS.md"), help="the report to write")
    args = parser.parse_args()

    model = load_model()
    testers = tester_rows(model)
    simulated = simulated_rows(model, args.simulated, args.seed)
    Path(args.out).write_text(report(model, testers, simulated, args.seed), encoding="utf-8", newline="\n")
    print(f"Real people: {sum(row['truth'] != 'bot' for row in testers)} sessions; real bots: {sum(row['truth'] == 'bot' for row in testers)} runs; simulated: {len(simulated)} visitors")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
