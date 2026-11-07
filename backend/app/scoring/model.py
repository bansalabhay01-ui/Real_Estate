"""The ML human check: a LightGBM model answers "is this visitor a bot?", and SHAP values say why.

ml/train.py trains it on simulator data and saves it to backend/data/model/. The SHAP values come from LightGBM
itself (predict(pred_contrib=True), the TreeSHAP method), so the server needs no extra package. Without a model
file, or if it can't be read, a simple hand-made formula stands in, so scoring never stops.
"""

import json
import logging
import math
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..config import BACKEND_DIR

log = logging.getLogger("leadops.scoring")

MODEL_DIR = BACKEND_DIR / "data" / "model"
MODEL_FILE_NAME, INFO_FILE_NAME = "bot_model.txt", "model_info.json"
# human_prob below "bot" makes a visitor a Bot on the model's word alone; below "review" it needs a look.
DEFAULT_THRESHOLDS = {"bot": 0.2, "review": 0.5}


@dataclass
class HumanCheck:
    human_prob: float  # 0-1: how likely this is a real person
    contributions: dict[str, float]  # feature -> SHAP value in log-odds; positive pushes towards "bot"
    source: str  # "model" or "fallback"
    version: str


def _sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-max(-50.0, min(50.0, value))))


class HumanModel:
    def __init__(self, booster=None, info: dict | None = None):
        self.booster = booster
        self.info = info or {}
        self.version = self.info.get("version") or ("unversioned" if booster is not None else "fallback")
        self.thresholds = {**DEFAULT_THRESHOLDS, **(self.info.get("thresholds") or {})}
        self._features = booster.feature_name() if booster is not None else []
        self._lock = threading.Lock()  # one prediction at a time: requests are scored in worker threads

    def predict(self, features: dict) -> HumanCheck:
        if self.booster is not None:
            try:
                return self._lightgbm(features)
            except Exception as exc:  # a model problem must never stop scoring
                log.warning("The scoring model failed, using the fallback formula: %s", exc)
        return self._fallback(features)

    def _lightgbm(self, features: dict) -> HumanCheck:
        import numpy as np

        # The model's own column order, so a model trained before a feature was added still lines up.
        row = np.array([[features.get(name, math.nan) for name in self._features]], dtype=float)
        with self._lock:
            values = self.booster.predict(row, pred_contrib=True, num_threads=1)[0]
        raw = float(values.sum())  # SHAP values plus the expected value add up to the model's raw score
        contributions = {name: float(value) for name, value in zip(self._features, values[:-1]) if value != 0}
        return HumanCheck(1 - _sigmoid(raw), contributions, "model", self.version)

    @staticmethod
    def _fallback(features: dict) -> HumanCheck:
        """A hand-made score from the clearest behaviour cues, used only when there is no trained model."""
        parts: dict[str, float] = {}

        def push(name: str, amount: float) -> None:
            parts[name] = parts.get(name, 0.0) + amount

        def known(name: str) -> float | None:
            value = features.get(name, math.nan)
            return None if value is None or math.isnan(value) else value

        if (coverage := known("activity_coverage")) is not None:
            push("activity_coverage", 2.5 if coverage == 0 else -1.5 if coverage >= 0.5 else 0.0)
        if (jump := known("mouse_px_per_move")) is not None:
            push("mouse_px_per_move", 2.0 if jump > 50 else -1.0 if jump < 30 else 0.0)
        if (dwell := known("median_dwell_s")) is not None:
            push("median_dwell_s", 1.5 if dwell < 2 else -1.0 if dwell > 10 else 0.0)
        if features.get("fast_pages", 0) >= 3:
            push("fast_pages", 1.5)
        if known("viewport_matches_screen") == 1:
            push("viewport_matches_screen", 0.7)
        if known("timezone_utc") == 1:
            push("timezone_utc", 0.5)
        if known("browser_languages") == 0:
            push("browser_languages", 1.0)
        if (shared := known("ip_visitors")) is not None and shared >= 5:
            push("ip_visitors", 0.8)
        if (fill := known("min_fill_s")) is not None and fill < 3:
            push("min_fill_s", 0.8)
        raw = -1.0 + sum(parts.values())  # -1.0: a visitor we know nothing about is more likely a person
        return HumanCheck(1 - _sigmoid(raw), {k: v for k, v in parts.items() if v}, "fallback", "fallback")


def load_model(directory: Path = MODEL_DIR) -> HumanModel:
    model_file, info_file = directory / MODEL_FILE_NAME, directory / INFO_FILE_NAME
    if not model_file.exists():
        log.info("No scoring model at %s: using the fallback formula (train one with ml/train.py)", model_file)
        return HumanModel()
    try:
        import lightgbm

        # The file lists each tree's size in bytes, so Windows line endings (from git or an editor) would break it.
        text = model_file.read_bytes().decode("utf-8").replace("\r\n", "\n")
        booster = lightgbm.Booster(model_str=text)
        info = json.loads(info_file.read_text(encoding="utf-8")) if info_file.exists() else {}
        return HumanModel(booster, info)
    except Exception as exc:
        log.warning("Couldn't load the scoring model, using the fallback formula: %s", exc)
        return HumanModel()


@lru_cache(maxsize=1)
def current_model() -> HumanModel:
    return load_model()


def reload_model() -> HumanModel:
    """Pick up a freshly trained model (POST /scoring/rescore does this)."""
    current_model.cache_clear()
    return current_model()
