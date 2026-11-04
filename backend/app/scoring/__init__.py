"""Scoring engine (Week 2, Member B): turns tracked behaviour into Bot / Junk / Cold / Warm / Hot / Review.

Planned modules (see LEADOPS_PLAN.md):
  rules.py     hard rules: honeypot filled, enquiry with no browsing, webdriver, too many hits from one IP
  features.py  per-visitor features from events, leads and chat
  model.py     LightGBM model trained by ml/train.py
  combine.py   rules + ML + LLM signals -> label and intent score
  explain.py   SHAP values -> plain-language reasons
Results go in the `scores` table (app.models.Score).
"""
