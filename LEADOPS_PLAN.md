# LeadOps — Find the Genuine Buyers Among Your Website Visitors

## Context
- The `real_estate` folder is empty, so this is a new build. The team has 3 members, 1 month and a Python + React stack, and is aiming at a national-level hackathon.
- **Problem:** Real estate websites get thousands of visitors, but:
  1. many form "leads" are bots, spam, fake numbers or rival brokers, and
  2. most serious buyers browse and leave without ever filling in a form.

  Sales teams waste hours on junk and never hear about the real buyers.
- **Goal:** LeadOps scores every visitor, filters out the fakes, spots serious buyers (anonymous ones too), explains each decision, and helps sales follow up quickly.
- **Tagline idea:** "Every visitor scored. Every bot blocked. Every genuine buyer found."

> **Pitch tip:** find 2–3 real, citable figures on how many real estate leads are junk (property portals, broker surveys, news articles) and put them on your first slide. Judges reward a problem backed by numbers.

---

## The Core Idea: a 3-Layer "Genuineness Score"

| Layer | Question | Signals |
|---|---|---|
| **1. Human check** | Real person, or a bot or scraper? | Mouse/scroll/touch patterns, time between actions, typing rhythm, hidden honeypot field, form submitted without any browsing first, `navigator.webdriver` or other headless-browser hints, scraping pattern (opens every listing within seconds), too many hits from one IP |
| **2. Authenticity check** | Are the details real, and is this really a buyer? | Indian mobile format (10 digits, starting with 6–9), fake patterns (`9999999999`, `1234567890`), disposable-email blocklist, duplicate leads, OTP (mocked in the demo). The LLM flags junk text ("asdf", "test") and sorts the visitor into **end-buyer / investor / tenant / broker / spam** |
| **3. Intent check** | How serious are they? | Time on property pages, repeat visits, EMI calculator use, floor-plan downloads, consistent budget/location, plus chat answers (budget, BHK, location, timeline, loan needed) |

**How the layers combine (easy to explain to judges):**
- A hard rule fails (honeypot filled, no browsing before submitting), or the ML model's probability that the visitor is human is low → `Bot`
- Fake details, spam, or not a buyer (e.g. a rival broker) → `Junk`
- Otherwise the Intent score (0–100) decides: `Cold` (<40) · `Warm` (40–70) · `Hot` (>70)
- Low-confidence cases go to a `Review` bucket, so a real buyer is never silently thrown away.

Every lead gets an AI-written reason, for example:
> "Hot: 3 visits in 2 days, used the EMI calculator for ₹85L, downloaded the 3BHK floor plan, told the assistant they want to move within 3 months."

---

## Features

### Must-have (the MVP that wins the demo)
1. **Demo real estate website**: 15–20 listings, property pages, EMI calculator, floor-plan download, and an enquiry form with a hidden honeypot field.
2. **Tracking SDK**: one `<script>` tag that sends behaviour events and gives each visitor an anonymous ID, so repeat visits are linked. Show it working on a second, plain HTML page to prove it is plug-and-play.
3. **AI property assistant (RAG + agent)**: answers questions from the listings and brochures, asks qualifying questions naturally, and saves the answers as structured JSON.
4. **Smart engagement trigger**: when an anonymous visitor looks human and shows high intent but hasn't left contact details, the assistant pops up with a relevant offer ("Want this 3BHK floor plan on WhatsApp?"). This is how LeadOps catches genuine buyers who would otherwise leave without a trace.
5. **Multilingual**: English + Hindi/Hinglish (+1 regional language).
6. **Scoring engine**: rules + ML + LLM produce the label, as described above.
7. **Explainable AI**: SHAP shows which factors drove the ML score, and the LLM turns them into plain-language reasons and a 3-line summary.
8. **Sales dashboard**: live lead feed (WebSocket), filters by label, and a lead profile showing the activity timeline, chat transcript, score breakdown and recommended next action.
9. **AI follow-up generator**: a WhatsApp or email draft in the buyer's language, plus a one-click "Book site visit".

### Should-have (adds "wow")
10. **Live attack demo**: a "Simulate Traffic" button (200 bots + 30 junk + 20 real buyers), plus a real Playwright bot filling in the enquiry form. The audience watches LeadOps sort them live. This is your strongest demo moment.
11. **Consistency check (LLM)**: flags contradictions, e.g. someone says "budget ₹2 Cr" but only looks at ₹40L flats.
12. **Sales feedback loop**: salespeople mark leads as "genuine / fake / converted", and these marks become new training labels ("the model learns from your sales team").
13. **Privacy-first (DPDP Act 2023)**: consent banner, phone and email masked before anything reaches the LLM, data-retention setting.
14. **Analytics page**: funnel (visitors → humans → real contacts → hot leads), share of junk filtered, estimated sales hours saved.

### Stretch (only if time is left)
- AI voice-call qualifier in Indian languages (e.g. using Bhashini APIs).
- WhatsApp bot through the Twilio sandbox.
- Spotting the same lead arriving from several property portals.

---

## Architecture

```
[Demo site (React) + leadops.js SDK] --events--> [FastAPI backend] --> [PostgreSQL]
          | chat widget                               | WebSocket
          v                                           v
[AI assistant: LangGraph agent + RAG]        [Sales dashboard (React)]
  tools: search_properties, calc_emi,
         book_visit, save_lead_details
                     |
              [Scoring engine]
   rules + ML (LightGBM + SHAP) + LLM signals -> label + reasons
```

### Tech stack
- **Frontend:** React (Vite) + Tailwind + shadcn/ui + Recharts, in one app with two route groups: `/` (demo site) and `/dashboard`.
- **SDK:** a small plain-JS file, served by the backend at `/sdk/leadops.js`.
- **Backend:** FastAPI, SQLAlchemy, PostgreSQL (SQLite while developing), WebSockets.
- **GenAI:** LangChain/LangGraph for the agent (Week 2). Retrieval starts as structured search over the listings; ChromaDB is added for brochures (PDFs), with the index rebuilt at startup. Keep the LLM behind one wrapper (`llm_client.py`) so you can switch providers (Claude, Gemini, Groq) depending on which free tier or credits you have.
- **ML:** scikit-learn / LightGBM + SHAP.
- **Deploy:** Vercel (frontend) + Render (backend) + Neon/Supabase (Postgres).

### Data strategy (your answer when a judge asks "isn't your data fake?")
- **Train** on simulator data: realistic bot, junk and genuine sessions.
- **Test on real data:** 30–50 sessions from classmates and friends browsing as real buyers, plus real Playwright/Selenium bots run against the site.
- Report precision/recall on that **real** test set, and explain that the model keeps improving through the sales feedback loop.

### Repo layout
```
leadops/
  frontend/          # React: demo site + dashboard + chat widget
  sdk/leadops.js     # embeddable tracking script
  backend/
    app/api/         # events, leads, chat, feedback, websocket routes
    app/models.py    # Visitor, Session, Event, Lead, ChatMessage, Score, Feedback
    app/scoring/     # rules.py, features.py, model.py, combine.py, explain.py
    app/ai/          # llm_client.py, rag.py, extract.py, assistant.py, prompts/ (+ agent.py in Week 2)
    data/            # listings.json, brochures/, disposable_domains.txt
  ml/
    simulator.py     # synthetic bot/junk/genuine sessions
    bots/            # real Playwright bots for testing and the live demo
    train.py         # train, evaluate, save model + SHAP explainer
  docs/              # architecture diagram, PPT, demo script
```

---

## Team Split
| Member | Owns |
|---|---|
| **A — Frontend** | Demo site, SDK, chat widget, smart-trigger UI, dashboard, live feed, analytics charts |
| **B — Backend + ML** | FastAPI, DB, event ingestion, rules, features, simulator, Playwright bots, ML + SHAP, WebSocket, feedback loop |
| **C — GenAI** | LLM wrapper, RAG, LangGraph agent, multilingual, JSON extraction, visitor-type classification, consistency check, explanations, follow-ups |

Everyone: collecting real test sessions, pitch deck, demo video, README.

---

## 4-Week Timeline

**Week 1 — Foundation**
- **Day 1:** agree on the shared contracts (event JSON, lead JSON, API routes) and don't change them, so all three of you can work in parallel.
- Listings and demo site pages; the SDK sends events to `POST /events`; DB schema.
- Basic RAG chatbot over the listings.
- Simulator v1.

**Week 2 — Intelligence**
- Rules engine, feature engineering, LightGBM + SHAP.
- Write the Playwright bots and collect real human sessions from classmates.
- Chatbot qualifying flow, JSON extraction, visitor-type classification.
- Dashboard v1: lead list with scores.

**Week 3 — Integration + Wow**
- Combined score and explanations; smart engagement trigger.
- Live dashboard, lead profile, follow-up generator, feedback buttons.
- Hindi/Hinglish, consistency check, DPDP consent and PII masking.
- "Simulate Traffic" button.

**Week 4 — Polish + Pitch**
- Deploy, build the analytics page, fix bugs.
- Final metrics on the real test set.
- PPT (problem → solution → live demo → architecture → impact → business model → roadmap), a 3-minute demo video, and a README with screenshots.
- Rehearse at least 5 times. Render's free tier sleeps when idle, so wake the backend before you present, and keep a local setup and the recorded video as backups.

---

## What Makes It "National Level" (mapped to typical judging criteria)
| Criterion | What LeadOps shows |
|---|---|
| Innovation | 3-layer scoring, smart engagement for anonymous visitors, visitor-type detection |
| Technical depth | RAG + LangGraph agent, LightGBM + SHAP, real-time WebSocket pipeline, embeddable SDK |
| Impact | Measured results: share of junk filtered, precision/recall on a real test set, sales hours saved |
| India relevance | Hindi and regional languages, Indian phone validation, WhatsApp follow-up, DPDP Act compliance |
| Feasibility & business | One script tag for any builder's or broker's site; subscription or pay-per-qualified-lead pricing |
| Demo | A live bot attack, sorted in real time |

---

## What I'll Do Once Approved
**Step 1 (right after approval):** save this plan as `LEADOPS_PLAN.md` in the `real_estate` folder, then stop so you can read it there. Step 2 starts only when you say go.

**Step 2:** scaffold the `leadops/` monorepo in this folder for Week 1, then install the dependencies and run the checks below myself.

- **Frontend:** Vite + React + Tailwind. Demo site: a home page with filters and listing cards, and a property page with the EMI calculator, floor-plan download and an enquiry form with a hidden honeypot. Plus the chat widget and a first `/dashboard` that lists visitors live.
- **Backend:** FastAPI + SQLAlchemy, using SQLite by default (`DATABASE_URL` switches to Postgres). Routes: `POST /events`, listings, leads, visitors, chat, feedback, and a dashboard WebSocket.
- **Listings:** about 18 fictional listings across Pune, Bengaluru, Hyderabad, Mumbai and Noida in `backend/data/listings.json`. The site reads them through the API, so the site and the chatbot always use the same data.
- **SDK v1 (`sdk/leadops.js`):** anonymous visitor ID, sessions, page views (including in-app navigation), clicks, scroll depth, time on page, mouse/touch activity counts and `navigator.webdriver`. `LeadOps.track()` records custom events (EMI used, floor plan downloaded, enquiry sent). `sdk/demo.html` shows the same script working on a plain HTML page.
- **Data captured from day 1 for Week 2 scoring:** honeypot value, time taken to fill the form, client timestamps, and IP address (works behind a proxy).
- **LLM wrapper (`llm_client.py`):** picks the provider from whichever key is in `backend/.env` (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY` or `GROQ_API_KEY`); `LLM_MODEL` overrides the model. The Claude default is `claude-opus-5-5` (best quality); set `LLM_MODEL=claude-haiku-5-5` for a much lower cost. With no key, or if an LLM call fails, the chatbot answers from the search results using templates, so the demo never breaks.
- **Basic RAG chatbot:** structured search (city, BHK, budget) plus keyword matching over the listings. For questions like "3BHK under 90L" this is more accurate than vector search and needs no heavy install. Budget, BHK and location are picked out with simple patterns that also handle Hinglish ("Pune mein 90 lakh tak 3BHK"); Member C upgrades this to LLM JSON extraction in Week 2.
- **`ml/simulator.py`:** uses only the Python standard library. Writes labelled bot/junk/genuine sessions to JSONL for training, and can also send them to the running backend.
- **`docs/CONTRACTS.md`:** a draft of the Day 1 shared contracts (event JSON, lead JSON, API routes, WebSocket messages) for the team to review.
- **README** with setup steps and the team task split.

**Setup notes:** Python 3.14.6, Node 24.14, npm 11.9 and git 2.55 are already installed. This folder is inside OneDrive, so `node_modules` and `.venv` (thousands of files) will sync to the cloud. It works, but installs are faster if you pause OneDrive syncing or move the project to a folder like `C:\dev\leadops`.
## Verification
- `uvicorn app.main:app` starts the backend; `npm run dev` serves the site and dashboard.
- Browse the demo site → events are saved in the DB → the visitor appears on the dashboard within seconds.
- Open `sdk/demo.html` → that visitor appears too, which proves the script works on any site.
- Ask the assistant "3BHK under 90L in Pune?" → it answers from the listings (in template mode if no API key is set) and records the budget, BHK and location.
- Submit the enquiry form → the lead is saved with its honeypot value and form-fill time.
- `python ml/simulator.py` writes a labelled JSONL file; with its send option, the simulated visitors appear on the dashboard.
- By Week 3: run the simulator and a Playwright bot → bots land in `Bot`/`Junk` and real buyers in `Warm`/`Hot`, each with reasons; `ml/train.py` prints precision/recall on the real test set.

---

## Week 2 Build Plan (draft for review)
Week 2 runs 6–13 Nov. Nothing below is built until you say go.

**Goal:** every visitor on the dashboard gets a label (`Bot` / `Junk` / `Cold` / `Warm` / `Hot` / `Review`), an intent score and the reasons behind them, updated live, and we can measure how well that works on real bots and real people.

**What "done" looks like:** send simulated traffic and watch the dashboard sort it as it arrives; a real Playwright bot fills in the enquiry form and lands in `Bot` with the reason shown; a classmate browsing normally climbs from `Cold` to `Hot` as they use the EMI calculator, the floor plan and the assistant.

The work comes in six parts. Each part ends with the tests passing and a quick check, then I save and push it, so the demo keeps working even if a later part slips. The owner is in brackets.

### Part 1: Tester link for real sessions (A, B)
Real sessions take calendar time to collect (classmates need a free half hour), so this ships first.
- Opening the site through a link such as `/?lo_test=genuine&lo_tester=t01` (a tester code, not a name) marks that browser as a test session: `genuine`, `junk` or `bot`. The SDK remembers it in the browser, so repeat visits count too, and sends it with every batch. `?lo_test=off` clears it.
- Scoring never reads the test label; only `ml/train.py` does, to build the real test set.
- A short guide for testers in the README: browse like a real buyer for 5–10 minutes, use the assistant if you like, and send an enquiry with a made-up number (10 digits starting 6–9) and a made-up email, so the test set holds no real personal data. Two or three people play junk on purpose (broker messages, fake numbers).
- Target: 30–50 human sessions by 21 Nov (end of Week 3), plus the bot sessions from Part 5.

### Part 2: Simulator v2, features and rules (B)
- **`ml/simulator.py` v2:** serious buyers come back 2–4 times over a few days; new "stealth" bots hide `webdriver` and copy a real browser; slow scrapers; shared IPs. Its activity numbers (mouse moves, scrolls, time per page) are checked against the first real sessions, so the model doesn't learn simulator quirks.
- **`scoring/features.py`:** about 30 numbers per visitor: pages per minute, time on property pages, mouse and touch activity, scripted clicks, form-fill time, repeat visits, visitors sharing the IP, EMI and floor-plan use, details shared in chat, phone and email checks. The same code builds them for training (from the simulator file) and for live scoring (from the database), so the model sees the same numbers in both places.
- **`scoring/rules.py`**, two kinds of rules:
  - *Certain* signals decide on their own. Bot: the hidden honeypot filled, `navigator.webdriver`, an automation user agent (`HeadlessChrome`, `python-requests`, `Scrapy`). Junk: a fake number (`9999999999`, `1234567890`, too short), a test name ("asdf", "test"), a spam message (links, promotions) or a broker pitch ("channel partner", "share your inventory").
  - *Strong* signals have innocent explanations, so one alone sends the visitor to `Review` at most; two together, or one plus a low ML score, make it `Bot` or `Junk`. Bot side: a form sent in under 1 second (browser autofill can fill it in 1–2), only scripted clicks, 8+ homes opened with under 2 seconds on each, an enquiry with no page views (an ad blocker can hide our script). Junk side: a disposable email domain (`backend/data/disposable_domains.txt`), the same phone from 3+ visitors.
  - Not a rule at all: lots of visitors from one IP. Colleges, offices and mobile networks put many people behind one address, so this only feeds the ML model.
  - International numbers (NRI buyers) are allowed; only clearly fake numbers count as junk.

### Part 3: Model, intent score, label and reasons (B, C)
- **`ml/train.py`** trains a LightGBM model that answers "is this visitor a bot?". It trains on whole simulated visits and on their first few minutes, because live scoring sees a visit while it is still happening. It prints precision and recall on held-out simulated visits and on the real test set (tester-link visitors in the database), and saves the model and its metrics to `backend/data/model/` (small, committed to git, so nobody has to train before running the backend).
- **`scoring/model.py`** loads the model and returns `human_prob` (0–1) plus a SHAP value per feature. Without a model file the rules still run and a simple formula stands in, so the demo never breaks.
- **Intent score** (`scoring/combine.py`), points out of 100: time on property pages (up to 20), repeat visits (up to 15), details shared with the assistant (up to 15: city, BHK, budget, moving within 6 months), EMI calculator (12), floor-plan download (12), a valid enquiry (10), a focused search, i.e. homes in one city and budget (up to 10), filters used (6). Points keep it easy to explain; Week 3's sales feedback can re-weight them.
- **Label** (`scoring/combine.py`), in this order:
  1. `Bot`: a certain bot signal, two strong ones, one strong one with `human_prob` under 0.5, or `human_prob` under 0.2.
  2. `Junk`: a certain junk signal, two strong ones, or a confident visitor type of broker / spam / tenant (Part 6). With intent 70+ it becomes `Review` instead.
  3. `Review`: one strong signal alone, or `human_prob` 0.2–0.5. Only for visitors worth a look (an enquiry, or intent 40+); unsure anonymous browsers stay `Cold`.
  4. Otherwise the intent score decides: `Cold` under 40, `Warm` 40–70, `Hot` over 70.

  The 0.2 / 0.5 cut-offs are starting values; `ml/train.py` tunes them and saves them with the model.
- **Reasons** (`scoring/explain.py`): the rules that fired, the top SHAP factors and the biggest intent points, in plain words: "Opened 14 homes in 9 seconds", "Checked the EMI on a ₹85 L home", "3 visits in 2 days". The LLM-written summary comes in Week 3.
- **`scoring/engine.py`** rescores a visitor after every event batch, enquiry and chat message (rules and model take milliseconds), saves the latest score on the visitor, keeps every label change in the existing `scores` table, and sends `score_update` to the dashboard. `POST /scoring/rescore` relabels everyone after a retrain.
- **Database:** visitors get a few columns for the latest score. A small startup step adds new columns to existing databases, so nobody has to delete theirs.

### Part 4: Dashboard v1 with scores (A)
- Visitors table: a label badge (text and icon, never colour alone), the intent score with a small bar, filter tabs with counts (All · Hot · Warm · Cold · Review · Junk · Bot), and sorting by latest activity or highest intent.
- Visitor panel: "Why this label" with the reasons, then three short blocks: human check (the probability and the top SHAP factors as bars), authenticity (phone, email, name and message checks, plus the visitor type) and intent (where the points came from).
- Enquiries table: the visitor's label next to each enquiry. The honeypot and fill-time checks move to the backend, so the dashboard and the scoring always agree.
- A short alert when someone turns `Hot`, and a "Test: genuine" chip on tester sessions.

### Part 5: Playwright bots (B)
`ml/bots/run_bots.py` runs three bots. They drive the Edge or Chrome already installed; `--headed` shows the browser, which is what the live demo uses.
- **Naive form bot:** fills in every field, the hidden one too, and submits in under a second. The certain rules should catch it.
- **Stealth form bot:** hides `webdriver`, uses a normal user agent, moves the mouse, scrolls, types with pauses and skips the hidden field. Only its behaviour gives it away, so it is the real test of the ML model.
- **Scraper:** opens every listing in a few seconds and copies the prices.
- Every bot run opens the site through a `lo_test=bot` link, so its visits join the real test set.
- `python ml/simulator.py --send http://localhost:8000 --report` prints how many of each kind got each label: our quick end-to-end check.

### Part 6: Assistant: LLM extraction and visitor type (C)
- **`llm_client.generate_json()`:** asks Claude, Gemini or Groq for JSON that fits a schema, and checks it. Any failure raises `LLMError`, so callers fall back as usual.
- **`ai/extract.py`:** with a key set, the LLM reads the message plus the last few turns ("same budget but in Bengaluru", "80-85 lakh ke beech", "teen BHK") and returns the same keys as now. The pattern extractor still runs first and fills gaps, and every value is checked (a known city, a sensible budget, BHK 1–6) before it is saved. This adds one short LLM call per chat message.
- **`ai/classify.py`:** sorts the visitor into end-buyer / investor / tenant / broker / spam from their enquiry message and chat, with a confidence and a one-line reason. It runs in the background after an enquiry or chat message, then the visitor is rescored. Without a key, keyword rules do it ("channel partner", "my clients", "rental yield", a link in the message).
- **Qualifying flow:** the assistant also asks whether the home is for their own use or an investment (new profile key `purpose`).
- **Privacy:** phone numbers and emails are masked as now, and names never reach the LLM (name checks are rule-based).

### Contract additions (need the team's OK)
Nothing is renamed or removed and every new field is optional, so nothing that works today breaks. `docs/CONTRACTS.md` is updated in the same commit.

| Where | Addition |
|---|---|
| Event batch `context` | `test_label` (`genuine` / `junk` / `bot`) and `tester`, only on tester-link visits |
| `VisitorOut` | `label` is now filled in; new `score`: `{label, intent_score, human_prob, visitor_type, reasons, model_version, scored_at}`; new `test_label` |
| `VisitorDetailOut` | new `score_detail`: the rules that fired, SHAP factors, intent points |
| `LeadOut` | new `label` (the visitor's) and `checks` (phone, email, name, honeypot, fill time) |
| `GET /visitors` | optional `?label=Hot` and `?sort=intent` |
| `GET /stats` | new `labels`: visitors per label |
| `POST /scoring/rescore` | new route: relabel every visitor after a retrain |
| WebSocket | `score_update` as already planned, plus `human_prob`, `visitor_type` and `previous_label` |
| Buyer details (`profile`) | new key `purpose`: `own_use` / `investment` |

### New files
| File | What it's for |
|---|---|
| `backend/app/scoring/rules.py`, `features.py`, `model.py`, `combine.py`, `explain.py` | the scoring engine (already named in this plan) |
| `backend/app/scoring/engine.py` | runs scoring when something happens, saves it and tells the dashboard |
| `backend/app/ai/classify.py` | visitor type: end-buyer / investor / tenant / broker / spam |
| `backend/data/disposable_domains.txt` | throwaway email domains (mailinator, yopmail, ...) |
| `backend/data/model/` | the trained model and its metrics, written by `ml/train.py` |
| `backend/tests/test_scoring.py` | tests for the rules, features, labels and reasons |
| `ml/train.py` | trains and evaluates the model |
| `ml/bots/run_bots.py` | the three Playwright bots |
| `ml/requirements.txt` | packages needed only for training and the bots |
| `frontend/src/dashboard/ScoreBreakdown.jsx` | the "Why this label" panel |

### New packages
All of them have ready-made builds for Python 3.14 on Windows (checked on 6 Nov with a pip dry run).
- Backend (`backend/requirements.txt`): `lightgbm` 4.7 and `numpy`, plus `scipy`, which LightGBM needs.
- Training and bots (`ml/requirements.txt`, installed into the same `backend/.venv`): `scikit-learn` 1.9 and `playwright` 1.64. On Mac or Linux, `python -m playwright install chromium` downloads a browser once.
- Not needed: the `shap` package. LightGBM computes SHAP values itself (`pred_contrib`, the same TreeSHAP method), so the server stays light. They are still SHAP values, and the pitch can say so.

### Changes from the main plan
- **The LangGraph agent moves to the start of Week 3.** This week's GenAI work (extraction, visitor type) feeds scoring now, and rebuilding the working assistant as a graph fits better next to the smart trigger and follow-ups it will drive. LangGraph 1.2 installs fine on Python 3.14. It will only orchestrate the steps; every LLM call still goes through `llm_client.py`.
- **SHAP values come from LightGBM itself** (see New packages).
- **Many visitors from one IP is not a rule**, and **a fast form, a missing SDK or a disposable email alone never make a visitor `Bot` or `Junk`** (Part 2), so real buyers aren't thrown away.
- **Tenants count as `Junk`** ("wants to rent, not buy") unless they also show strong buying signals.
- **The mocked OTP check** waits for Week 3, next to the DPDP consent work.

### Decisions for you
1. **Contracts:** are the additions above OK, or should the team see them first?
2. **How classmates reach the site:**
   - **Same Wi-Fi (recommended):** everyone in one room opens the site from one laptop that runs the backend and the frontend. No accounts or deploys; I add the steps to the README. Only people in the room can take part.
   - **Deploy early:** Render + Vercel + Neon now instead of in Week 4, so friends can test from home. It means setting up three accounts, and it pulls Week 4 work forward.

### Verification (end of Week 2)
- `python ml/simulator.py`, then `backend\.venv\Scripts\python ml/train.py`: prints precision and recall on held-out simulated visits and saves the model.
- `python -m pytest` in `backend/`: the 36 existing tests and the new scoring tests pass, with no LLM calls.
- Backend running with `LLM_PROVIDER=none` and a throwaway database, then `python ml/simulator.py --send http://localhost:8000 --report`: nearly all bots land in `Bot`, junk in `Junk`, serious buyers in `Warm`/`Hot` and casual ones in `Cold`. Simulated data is expected to score high; the real test set is the number that counts.
- The three Playwright bots: naive and scraper → `Bot`; stealth → `Bot` or `Review`, with behaviour reasons.
- Browsing the demo site in a normal browser: starts `Cold` and climbs to `Warm`/`Hot` with the EMI calculator, floor plan, assistant and enquiry, with reasons that match.
- Without the model file and without an LLM key, labels still appear.
- `npm run build` passes; the filters and the score panel work, including at phone width.
