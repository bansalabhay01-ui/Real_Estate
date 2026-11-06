# Session Log

A short diary of LeadOps work sessions, newest first. Claude saves each session by itself: whenever a piece of work is finished, and at the start of the next session if the last one wasn't saved. Each save updates this file, commits, and pushes to GitHub.

## Current status
_Last updated: 2026-11-06_

- **Phase:** Week 2 (Intelligence, 6–13 Nov) in progress: Parts 1 and 2 of 6 done. Deadline about 30 Nov 2026.
- **Done:** the Week 1 foundation (demo property site, tracking SDK, FastAPI backend, a basic property assistant in English, Hinglish and Hindi, the live sales dashboard, the traffic simulator, the shared contracts draft) and the Week 2 build plan ("Week 2 Build Plan" at the end of `LEADOPS_PLAN.md`). Week 2 Part 1: tester links that label real test sessions, and same-Wi-Fi testing. Part 2: simulator v2, the shared visitor features and the bot/junk rules. 77 tests pass. Roughly 38% of the whole plan.
- **Next:** Week 2 Part 3: the LightGBM model, intent score, labels and reasons. Classmates can start test sessions now (README, "Collecting real test sessions").
- **Blocked:** nothing. The assistant's LLM replies haven't been tried with a real API key yet (template replies work).
- **Code:** https://github.com/bansalabhay01-ui/Real_Estate (branch `main`)

---

## 2026-11-06 · bansalabhay01-ui · Week 2 plan, Parts 1-2 (tester link, features and rules)

**Done**
- Wrote the Week 2 build plan as a new section at the end of `LEADOPS_PLAN.md`. It has six parts: tester link for real sessions, simulator v2 + features + rules, LightGBM model + intent score + labels + reasons, dashboard v1 with scores, Playwright bots, and LLM extraction + visitor type. It also lists the contract additions, new files, new packages, changes from the main plan and the checks.
- A pip dry run confirmed that LightGBM 4.7, scikit-learn 1.9, Playwright 1.64, LangGraph 1.2 and SHAP 0.54 all have ready-made Windows builds for Python 3.14.
- Ran `claude doctor`: Claude Code 2.1.319, native install, no issues.
- **Part 1, tester link:** `sdk/leadops.js` (now 1.1.0) reads `?lo_test=genuine|junk|bot&lo_tester=CODE`, remembers it in the browser and sends it as `context.test_label` / `context.tester`; `?lo_test=off` clears it. The backend keeps it and shows it as `VisitorOut.test_label` (an unknown label is dropped, never rejected). The dashboard shows a "Test" chip. `docs/CONTRACTS.md` and the README ("Collecting real test sessions": tester guide and same-Wi-Fi steps) are updated.
- The site now looks for the API on port 8000 of the machine that serves the page, unless `VITE_API_URL` is set, so classmates' phones on the same Wi-Fi need no settings.
- Installed the Week 2 packages: `lightgbm` 4.7.0, `numpy` 2.5.4 and `scipy` 1.18.1 in `backend/requirements.txt`; `scikit-learn` 1.9.1 and `playwright` 1.64.1 in the new `ml/requirements.txt`.
- Checked: 37 tests pass, the frontend builds, and a headless Edge check of the tester link passed 10/10.
- **Part 2, features and rules:**
  - `backend/app/scoring/features.py`: 41 numbers per visitor from one *visitor record* shape, which the simulator writes and `scoring/engine.py` (`load_record`) builds from the database, so training and live scoring see the same numbers. Only the 27 "how they browse" features go to the ML model.
  - `backend/app/scoring/rules.py`: phone, email, name and message checks, plus the certain/strong bot and junk signals. NRI numbers are allowed; browser-autofill speed (1-3 s) isn't a signal.
  - `backend/data/disposable_domains.txt`: 54 throwaway email domains.
  - `ml/simulator.py` v2 writes visitor records (several visits per visitor) and adds stealth bots, slow scrapers, repeat visits, NRI buyers, autofill, privacy browsers, ad blockers and shared IPs.
  - `merge_profile` moved from `ai/assistant.py` to `ai/extract.py`, next to the new `profile_from_messages`.
  - New `backend/tests/test_scoring.py`: 40 tests, including live-vs-training feature parity and "simulated genuine buyers never trip a certain signal". 77 tests pass.

**Next**
- Part 3: the LightGBM model, intent score, labels and reasons.

**Notes**
- The user said "continue" without answering the plan's two decisions, so the plan's recommendations apply: the contract additions as planned (written into `docs/CONTRACTS.md` as each part lands) and same-Wi-Fi testing.
- Teammates: run `pip install -r requirements.txt` in `backend/` again for the new packages, and `pip install -r ml/requirements.txt` (from the repo root, into the same venv) to train or run the bots.
- Plan decisions: SHAP values come from LightGBM's own `pred_contrib` (no `shap` package on the server). The LangGraph agent moves to the start of Week 3. Many visitors from one IP, a fast form, a missing SDK or a disposable email never make a visitor `Bot` or `Junk` on their own. International (NRI) phone numbers are allowed.
- Found while planning: the enquiry form's timer starts at the first change, so browser autofill can make a real buyer look fast. The floor-plan download's scripted `link.click()` happens on a detached link, so the SDK never records it as a scripted click.
- Edge and Chrome are installed on this laptop, so the Playwright bots need no browser download here.
- When Claude Code runs in VS Code's terminal, VS Code's automatic venv activation line can end up in the Claude prompt. It is harmless; nothing runs.

---

## 2026-11-04 · bansalabhay01-ui · Progress check and GitHub

**Done**
- Progress check against `LEADOPS_PLAN.md`: about 30% done and on schedule (Week 1 finished on day 6 of about 31). Tests and the frontend build re-run: passing.
- First commit, then connected GitHub (`origin`: https://github.com/bansalabhay01-ui/Real_Estate), on top of GitHub's "Initial commit". Our README replaced GitHub's one-line placeholder.
- Sessions are now saved by Claude without being asked: the routine is in `CLAUDE.md` ("Sessions"), the steps are in `.claude/commands/wrap-up.md` (log, commit, push), and a SessionStart hook in `.claude/settings.json` lists unsaved files when a session starts.

**Next**
- Week 2 work (see Current status).

**Notes**
- The start-of-session check ignores `PROMPTS.md` (it changes with every message); it is committed with the next save.

---

## 2026-11-03 · bansalabhay01-ui · Week 1 foundation built

**Done**
- Step 2 of the plan (finished on 2026-11-04):
  - `frontend/`: React demo property site (filters, EMI calculator, floor-plan download, enquiry form with a hidden honeypot, chat widget) and the live sales dashboard at `/dashboard`.
  - `sdk/leadops.js`, the tracking script, plus `sdk/demo.html`, a plain page that shows it working on another site.
  - `backend/`: FastAPI with SQLite (events, visitors, listings, enquiries, chat, feedback, stats, dashboard WebSocket), the property assistant in `backend/app/ai/`, 18 fictional listings and 36 tests.
  - `ml/simulator.py` (labelled bot / junk / genuine traffic), `docs/CONTRACTS.md` and `README.md`.
- Checked end to end in headless Edge: 19/19, covering every item on the plan's verification list; no sideways scrolling at phone width.
- Fixed bugs the checks found: events saved before their visitor existed (foreign key error), a layout crash because `scrollTo` returns a Promise in new browsers, a stray "0" next to "18 homes", and a header too wide for phones.

**Next**
- Team review of `docs/CONTRACTS.md`, then Week 2.

**Notes**
- Newer packages than expected: anthropic 2.4 (Claude API version 2026-10-21, which rejects `temperature`), React Router 8, Vite 8. Their APIs were checked; backend versions are pinned in `requirements.txt`.
- Claude defaults: `claude-opus-5-5` at low effort for quick chat replies, with Anthropic's server-side refusal fallback on.
- Decided: JavaScript rather than TypeScript; drawn floor plans instead of photos; shadcn/ui and Recharts not installed yet. Added `GET /stats` and a visitor detail panel to the dashboard.
- New optional settings in `backend/.env.example`: `LLM_PROVIDER` and `CORS_ORIGINS` (the defaults work).

---

## 2026-11-03 · bansalabhay01-ui · Project setup

**Done**
- Started git on branch `main`. Nothing is committed yet.
- Created `.gitignore`, `backend/.env` + `backend/.env.example`, `CLAUDE.md`, `.claude/settings.json`, `SESSION_LOG.md`, `PROMPTS.md`, the prompt-logging hook (`.claude/hooks/log-prompt.mjs`) and the `/wrap-up` command (`.claude/commands/wrap-up.md`).
- Kept `real_estate/` as the repo root: the plan's `leadops/` folder is this folder.

**Next**
- Optional: paste an LLM API key into `backend/.env` (the demo works without one).
- Restart Claude Code, or open `/hooks` once, so prompt logging starts.
- Say go for Step 2: scaffold the repo.

**Notes**
- Skipped for now: `.gitattributes` and `DECISIONS.md`.
