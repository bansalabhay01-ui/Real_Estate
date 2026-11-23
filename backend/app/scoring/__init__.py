"""Scoring engine: turns tracked behaviour into Bot / Junk / Review / Cold / Warm / Hot.

  rules.py        hard rules: honeypot filled, enquiry with no browsing, webdriver, fake contact details, spam
  features.py     per-visitor numbers from events, enquiries and chat (the same for training and live scoring)
  model.py        the LightGBM human check trained by ml/train.py, with SHAP values
  combine.py      rules + ML + intent points -> label and intent score
  explain.py      plain-language reasons
  consistency.py  says versus does: what a visitor tells us against the homes they open
  nudge.py        the smart engagement trigger: offers for serious anonymous visitors
  engine.py       live scoring: load from the database, score, save (every label change also goes in `scores`)
"""
