"""Train the ML human check: a LightGBM model that answers "is this visitor a bot?".

    python ml/simulator.py --bots 800 --junk 400 --genuine 800     # training data (more data, a steadier model)
    backend\\.venv\\Scripts\\python ml/train.py                       # Mac/Linux: backend/.venv/bin/python ml/train.py

What it does:
  1. Trains on simulated visitors, whole and cut short, because live scoring sees a visit while it's still happening.
  2. Checks the model on a quarter of the visitors it never saw, and tunes the Bot / Review cut-offs. Tuning can only
     make them more careful than the plan's starting values (0.2 and 0.5), never more aggressive.
  3. Saves backend/data/model/bot_model.txt and model_info.json (the backend loads them; commit both).
  4. Measures the whole scoring engine (rules + model) on the real test set: visitors in the database who came
     through a tester link (README, "Collecting real test sessions"). Simulated scores run high; this is the number
     that counts.
Needs backend/requirements.txt and ml/requirements.txt in the backend's virtual environment.
"""

import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.metrics import precision_score, recall_score, roc_auc_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

from app.ai.classify import classify  # noqa: E402
from app.ai.extract import profile_from_messages  # noqa: E402
from app.scoring.combine import score_record  # noqa: E402
from app.scoring.features import MODEL_FEATURES, add_network_counts, cut_record, model_vector, visitor_features  # noqa: E402
from app.scoring.model import DEFAULT_THRESHOLDS, INFO_FILE_NAME, MODEL_DIR, MODEL_FILE_NAME, HumanModel  # noqa: E402

LABELS = ["Bot", "Junk", "Review", "Cold", "Warm", "Hot"]
# Monotone constraints keep the model's logic sensible and its SHAP explanations intuitive: a bot signal can only
# ever push towards "bot" (+1), a human one only towards "person" (-1). Features that cut both ways stay free (0):
# lots of pages can be a scraper or a broker, and a scroll straight to the bottom is a script, not a person.
MONOTONE = {
    "webdriver": 1, "automation_ua": 1, "no_user_agent": 1, "timezone_utc": 1, "viewport_matches_screen": 1,
    "touch_mismatch": 1, "pages_per_minute": 1, "fast_pages": 1, "mouse_px_per_move": 1, "untrusted_clicks": 1,
    "honeypot": 1, "lead_without_pageviews": 1, "ip_visitors": 1,
    "browser_languages": -1, "hardware_concurrency": -1, "duration_s": -1, "median_dwell_s": -1,
    "activity_coverage": -1, "mouse_moves_per_min": -1, "touches_per_min": -1, "trusted_clicks": -1,
    "event_gap_cv": -1, "min_fill_s": -1, "seconds_to_first_lead": -1,
}  # fmt: skip
PARAMS = {
    "objective": "binary", "learning_rate": 0.05, "num_leaves": 15, "min_data_in_leaf": 10, "feature_fraction": 0.8,
    "bagging_fraction": 0.8, "bagging_freq": 1, "lambda_l2": 1.0, "seed": 7, "deterministic": True,
    "force_row_wise": True, "num_threads": 1, "verbosity": -1,
}  # fmt: skip


def load_records(path: Path) -> list[dict]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    add_network_counts(records)
    for record in records:
        record["profile"] = profile_from_messages([message["text"] for message in record.get("chat") or []])
    return records


def activity_span(record: dict) -> tuple[float, float] | None:
    times = [event["ts"] for session in record.get("sessions") or [] for event in session.get("events") or []]
    times += [lead["client_ts"] for lead in record.get("leads") or [] if lead.get("client_ts") is not None]
    return (min(times), max(times)) if times else None


def rows_for(records: list[dict], rng: random.Random, cuts: int) -> tuple[list[list[float]], list[int]]:
    """Each visitor whole, plus `cuts` versions cut off part-way (what live scoring sees mid-visit)."""
    x, y = [], []
    for record in records:
        versions = [record]
        span = activity_span(record)
        if span and span[1] - span[0] > 3000:
            versions += [cut_record(record, rng.uniform(span[0] + 1000, span[1])) for _ in range(cuts)]
        for version in versions:
            x.append(model_vector(visitor_features(version)))
            y.append(1 if record["label"] == "bot" else 0)
    return x, y


def visitor_type(record: dict) -> dict | None:
    """The keyword visitor type from a simulated visitor's messages, as the backend works it out without a key."""
    texts = [lead.get("message") or "" for lead in record.get("leads") or []]
    texts += [message["text"] for message in record.get("chat") or []]
    return classify(texts, record.get("profile") or {}, use_llm=False)


def safe_cut(human_probs: list[float], limit: float, ceiling: float) -> float:
    """The highest cut-off (at most `ceiling`) that puts no more than `limit` of real people below it."""
    for cut in np.arange(ceiling, 0.0, -0.01):
        if np.mean(np.array(human_probs) < cut) <= limit:
            return round(float(cut), 2)
    return 0.01


def confusion(rows: list[tuple[str, str]]) -> dict[str, dict[str, int]]:
    table: dict[str, Counter] = {}
    for truth, label in rows:
        table.setdefault(truth, Counter())[label] += 1
    return {truth: {label: counts[label] for label in LABELS if counts[label]} for truth, counts in sorted(table.items())}


def print_confusion(title: str, table: dict) -> None:
    print(f"\n{title}")
    print(f"  {'':22}" + "".join(f"{label:>8}" for label in LABELS))
    for truth, counts in table.items():
        print(f"  {truth:22}" + "".join(f"{counts.get(label, 0):>8}" for label in LABELS))


def headline(rows: list[tuple[str, str]]) -> dict:
    """The numbers for the pitch: bots and junk filtered out, genuine buyers kept."""
    def share(truth_prefix: str, good: set[str]) -> float | None:
        picked = [label for truth, label in rows if truth.startswith(truth_prefix)]
        return round(sum(label in good for label in picked) / len(picked), 3) if picked else None

    return {
        "bots_caught": share("bot", {"Bot"}),
        "bots_filtered": share("bot", {"Bot", "Junk"}),
        "junk_filtered": share("junk", {"Bot", "Junk"}),
        "genuine_kept": share("genuine", {"Cold", "Warm", "Hot", "Review"}),
        "genuine_in_review": share("genuine", {"Review"}),
    }


def real_test_set(model: HumanModel) -> list[tuple[str, str]] | None:
    """Score the tester-link visitors in the database (DATABASE_URL) with the new model."""
    from app.config import settings

    if settings.database_url.startswith("sqlite:///"):
        if not Path(settings.database_url.removeprefix("sqlite:///")).exists():
            return None
    from app.db import SessionLocal, init_db
    from app.models import Visitor
    from app.scoring.engine import known_type, load_record
    from sqlalchemy import select

    init_db()  # adds any new columns, as the backend does at startup
    rows = []
    with SessionLocal() as db:
        for visitor_id, context, saved_type in db.execute(select(Visitor.id, Visitor.context, Visitor.visitor_type)).all():
            truth = (context or {}).get("test_label")
            if truth:
                record = load_record(db, visitor_id)
                label = score_record(record, model=model, visitor_type=known_type(saved_type)).label
                rows.append((f"{truth} (tester)", label))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Train LeadOps' ML human check (LightGBM).")
    parser.add_argument("--data", default=str(ROOT / "ml" / "data" / "sessions.jsonl"), help="simulator output (JSONL)")
    parser.add_argument("--cuts", type=int, default=3, help="cut-short copies of each training visitor")
    parser.add_argument("--out", default=str(MODEL_DIR), help="where to save the model")
    args = parser.parse_args()

    data = Path(args.data)
    if not data.exists():
        print(f"No training data at {data}. Make some first: python ml/simulator.py --bots 800 --junk 400 --genuine 800")
        return 1
    records = load_records(data)
    kinds = [f"{r['label']}/{r['kind']}" for r in records]
    train, test = train_test_split(records, test_size=0.25, random_state=7, stratify=kinds)
    rng = random.Random(7)
    x_train, y_train = rows_for(train, rng, args.cuts)
    x_test, y_test = rows_for(test, rng, args.cuts)
    print(f"Training on {len(train)} visitors ({len(x_train)} rows with the cut-short copies); "
          f"checking on {len(test)} unseen visitors ({len(x_test)} rows)")

    features = list(MODEL_FEATURES)
    PARAMS["monotone_constraints"] = [MONOTONE.get(name, 0) for name in features]
    train_set = lgb.Dataset(np.array(x_train, dtype=float), label=y_train, feature_name=features, free_raw_data=False)
    test_set = lgb.Dataset(np.array(x_test, dtype=float), label=y_test, reference=train_set)
    booster = lgb.train(PARAMS, train_set, num_boost_round=400, valid_sets=[test_set],
                        callbacks=[lgb.early_stopping(30, verbose=False)])
    print(f"Trained {booster.best_iteration} trees")

    bot_prob = booster.predict(np.array(x_test, dtype=float), num_iteration=booster.best_iteration)
    human_prob = 1 - bot_prob
    people = [p for p, label in zip(human_prob, y_test) if label == 0]
    thresholds = {"bot": safe_cut(people, 0.005, DEFAULT_THRESHOLDS["bot"]),
                  "review": safe_cut(people, 0.03, DEFAULT_THRESHOLDS["review"])}
    thresholds["review"] = max(thresholds["review"], thresholds["bot"])
    predicted = [int(p < thresholds["review"]) for p in human_prob]
    model_metrics = {
        "auc": round(float(roc_auc_score(y_test, bot_prob)), 4),
        "bot_precision": round(float(precision_score(y_test, predicted, zero_division=0)), 4),
        "bot_recall": round(float(recall_score(y_test, predicted, zero_division=0)), 4),
    }
    print(f"Model alone on unseen visitors (whole and cut short): AUC {model_metrics['auc']}, "
          f"bot precision {model_metrics['bot_precision']}, recall {model_metrics['bot_recall']} "
          f"at human_prob < {thresholds['review']}")
    print(f"Cut-offs: Bot below {thresholds['bot']}, Review below {thresholds['review']}")

    model_text = booster.model_to_string(num_iteration=booster.best_iteration)
    version = f"lgbm-{datetime.now(UTC):%Y%m%d}-{hashlib.sha1(model_text.encode()).hexdigest()[:6]}"
    contributions = booster.predict(np.array(x_test, dtype=float), pred_contrib=True, num_iteration=booster.best_iteration)
    importance = dict(sorted(zip(features, np.abs(contributions[:, :-1]).mean(axis=0).round(4).tolist()), key=lambda kv: -kv[1]))
    info = {"version": version, "thresholds": thresholds, "features": features}
    model = HumanModel(lgb.Booster(model_str=model_text), info)

    # The whole engine (rules + model + intent) on unseen simulated visitors, whole visits only.
    pipeline = [(f"{r['label']}/{r['kind']}", score_record(r, model=model, visitor_type=visitor_type(r)).label) for r in test]
    print_confusion("Whole engine on unseen simulated visitors:", confusion(pipeline))
    simulated = headline(pipeline)
    print("  " + ", ".join(f"{name.replace('_', ' ')} {value:.1%}" for name, value in simulated.items() if value is not None))

    real = real_test_set(model)
    if real:
        print_confusion(f"Whole engine on the REAL test set ({len(real)} tester visitors):", confusion(real))
        real_headline = headline(real)
        print("  " + ", ".join(f"{name.replace('_', ' ')} {value:.1%}" for name, value in real_headline.items() if value is not None))
    else:
        real_headline = None
        print("\nNo real test set yet: no tester-link visitors in the database (README, 'Collecting real test sessions').")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / MODEL_FILE_NAME).write_text(model_text, encoding="utf-8", newline="\n")  # LightGBM counts bytes: keep \n
    info.update({
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "lightgbm": lgb.__version__, "trees": booster.best_iteration, "params": PARAMS,
        "data": {"file": data.name, "visitors": len(records), "by_label": dict(Counter(r["label"] for r in records)),
                 "train_rows": len(x_train), "test_rows": len(x_test)},
        "metrics": {"model_on_unseen_simulated": model_metrics, "engine_on_unseen_simulated": simulated,
                    "engine_on_real_test_set": real_headline, "real_test_set_size": len(real or [])},
        "importance": importance,
    })  # fmt: skip
    (out / INFO_FILE_NAME).write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"\nSaved {version} to {out}. Restart the backend (or POST /scoring/rescore) to use it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
