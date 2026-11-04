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
