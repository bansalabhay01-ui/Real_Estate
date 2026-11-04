# LeadOps

GenAI lead qualification for real estate websites. LeadOps scores every visitor, blocks bots and junk leads, finds genuine buyers (anonymous ones too) and explains each decision so sales can follow up fast. A team of 3 is building it for a national-level hackathon; the deadline is about 30 Nov 2026.

The full plan, features and timeline are in `LEADOPS_PLAN.md`. Read it before any large change.

## Every session
- At the start, read the **Current status** block at the top of `SESSION_LOG.md`.
- At the end, the user runs `/wrap-up` to add a session entry and refresh that status.
- `PROMPTS.md` is filled automatically by a hook (`.claude/hooks/log-prompt.mjs`). Never edit or reformat it.

## Stack
- **Frontend:** React (Vite) + Tailwind + shadcn/ui + Recharts. One app: demo site at `/`, sales dashboard at `/dashboard`.
- **SDK:** plain-JS `sdk/leadops.js`, served by the backend at `/sdk/leadops.js`.
- **Backend:** FastAPI + SQLAlchemy + WebSockets. SQLite in development; Postgres (Neon/Supabase) in production through `DATABASE_URL`.
- **GenAI:** LangChain/LangGraph agent; RAG over the listings, plus ChromaDB for brochures later.
- **ML:** scikit-learn / LightGBM + SHAP.
- **Deploy:** Vercel (frontend) + Render (backend).

## Folder map
This folder is the repo root. Shared JSON shapes are in `docs/CONTRACTS.md` (code: `backend/app/schemas.py`).
- `frontend/`: demo site, dashboard, chat widget
- `sdk/`: embeddable tracking script and `demo.html`
- `backend/app/api/`: routes
- `backend/app/scoring/`: rules, features, model, combine, explain
- `backend/app/ai/`: llm_client, rag, extract, assistant, prompts
- `backend/data/`: listings, brochures
- `ml/`: simulator, Playwright bots, training
- `docs/`: shared contracts, architecture, pitch

## Commands
Windows paths shown; on Mac/Linux use `.venv/bin/python`.
- Backend, from `backend/`: `.venv\Scripts\python -m uvicorn app.main:app --reload` (http://localhost:8000, docs at `/docs`)
- Backend tests, from `backend/`: `.venv\Scripts\python -m pytest` (temporary database, template mode, no LLM calls)
- Frontend, from `frontend/`: `npm run dev` (http://localhost:5173, dashboard at `/dashboard`); `npm run build` checks it compiles
- Simulator, from the repo root: `python ml/simulator.py` (writes `ml/data/sessions.jsonl`); add `--send http://localhost:8000` to post to a running backend
- First-time setup: `python -m venv .venv` and `.venv\Scripts\python -m pip install -r requirements.txt` in `backend/`; `npm install` in `frontend/`

When checking the app, run the backend with `LLM_PROVIDER=none` and a throwaway `DATABASE_URL`, so the user's
LLM key isn't spent and their local database stays clean.

## Rules
- Secrets live in `backend/.env`, which git ignores. Never read, print or commit it. Put new settings in `backend/.env.example` and ask the user to copy them across.
- Every LLM call goes through `backend/app/ai/llm_client.py`, so the provider (Claude, Gemini, Groq) can be switched by changing the key.
- The demo must never break: if there's no API key or an LLM call fails, fall back to template answers.
- The shared contracts in `docs/CONTRACTS.md` (event JSON, lead JSON, API routes, WebSocket messages) are agreed by all three members. Don't change them without asking.
- Mask phone numbers and emails before any text reaches an LLM (DPDP Act 2023).
- Teammates may use Windows, Mac or Linux, so keep scripts cross-platform (Python or Node, not PowerShell-only or bash-only).

## Team
- **A, Frontend:** demo site, SDK, chat widget, smart-trigger UI, dashboard, live feed, charts
- **B, Backend + ML:** FastAPI, DB, event ingestion, rules, features, simulator, Playwright bots, ML + SHAP, WebSocket, feedback loop
- **C, GenAI:** LLM wrapper, RAG, agent, multilingual, extraction, visitor-type classification, consistency check, explanations, follow-ups
