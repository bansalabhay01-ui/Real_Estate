"""ml/evaluate.py reports what was measured and nothing else: the groups stay apart and an empty group says so."""

import importlib.util
import sys

import pytest

from app.config import REPO_DIR


@pytest.fixture(scope="module")
def evaluate():
    sys.path.insert(0, str(REPO_DIR / "ml"))
    spec = importlib.util.spec_from_file_location("leadops_evaluate", REPO_DIR / "ml" / "evaluate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeModel:
    version = "lgbm-test"


def rows(truth, label, count, **extra):
    return [{"truth": truth, "label": label, **extra} for _ in range(count)]


SIMULATED = rows("bot", "Bot", 3, kind="bot/scraper") + rows("genuine", "Warm", 2, kind="genuine/serious")


def test_a_small_sample_gets_a_wide_interval(evaluate):
    low, high = evaluate.wilson(15, 15)
    assert low == pytest.approx(0.796, abs=0.001) and high == 1.0
    assert evaluate.wilson(0, 0) == (0.0, 0.0)
    assert "95% CI 80% to 100%" in evaluate.share_text(15, 15)
    assert evaluate.share_text(0, 0) == "no sessions yet"


def test_groups_without_sessions_claim_nothing(evaluate):
    text = evaluate.report(FakeModel, [], SIMULATED, 2026)
    people = text.split("## 1. Real people")[1].split("## 2. Real bots")[0]
    bots = text.split("## 2. Real bots")[1].split("## 3. Simulated traffic")[0]
    assert "No sessions collected yet" in people and "%" not in people
    assert "No bot runs in this database yet" in bots and "%" not in bots
    assert "not evidence of real-world accuracy" in text


def test_real_people_bots_and_simulated_visitors_stay_apart(evaluate):
    testers = (
        rows("genuine", "Hot", 8, tester="t01") + rows("genuine", "Junk", 2, tester="t02") + rows("junk", "Junk", 4, tester="t03")
        + rows("bot", "Bot", 5, tester="bot-stealth") + rows("bot", "Warm", 1, tester="bot-stealth")
    )  # fmt: skip
    text = evaluate.report(FakeModel, testers, SIMULATED, 2026)
    people = text.split("## 1. Real people")[1].split("## 2. Real bots")[0]
    bots = text.split("## 2. Real bots")[1].split("## 3. Simulated traffic")[0]
    simulated = text.split("## 3. Simulated traffic")[1]

    assert "14 sessions" in people
    assert "**4/4**" in people  # junk testers filtered out; the six bot runs are not counted here
    assert "**8/10**" in people  # genuine testers kept
    assert "**4/6**" in people  # of the six filtered out, four were really junk
    assert "**5/6**" in bots
    assert "Stealth bot" in bots
    assert "**3/3**" in simulated and "**2/2**" in simulated


def test_the_simulated_sample_is_scored_by_the_real_engine(evaluate):
    from app.scoring.model import load_model

    measured = evaluate.simulated_rows(load_model(), 30, seed=5)
    assert len(measured) == 30
    assert {row["truth"] for row in measured} == {"bot", "junk", "genuine"}
    assert all(row["label"] in evaluate.LABELS for row in measured)
