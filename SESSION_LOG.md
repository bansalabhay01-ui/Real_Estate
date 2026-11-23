# Session Log

A short diary of LeadOps work sessions, newest first. Claude saves each session by itself: whenever a piece of work is finished, and at the start of the next session if the last one wasn't saved. Each save updates this file, commits, and pushes to GitHub.

## Current status
_Last updated: 2026-11-23_

- **Phase:** built and live. Everything in `LEADOPS_PLAN.md` that can be built is built, Weeks 1 to 4, and since 23 Nov it runs at https://leadops-henna.vercel.app (backend https://leadops-api-pudl.onrender.com, database on Neon). What's left needs the team: real test sessions, one check with a real LLM key, the demo video and rehearsals. Deadline about 30 Nov 2026.
- **Done:** the Week 1 foundation (demo property site, tracking SDK, FastAPI backend, a basic property assistant in English, Hinglish and Hindi, the live sales dashboard, the traffic simulator, the shared contracts draft), all of Week 2 ("Week 2 Build Plan" in `LEADOPS_PLAN.md`: tester links, simulator v2, features and rules, the LightGBM human check with SHAP, intent points, labels and reasons, dashboard v1, three real Playwright bots, LLM extraction and visitor type) and all of Week 3: the dashboard's Simulate traffic button with a live scoreboard and Run a real bot; the assistant as a LangGraph agent with brochure answers, EMIs, site visits and Marathi; the smart engagement trigger that turns serious anonymous visitors into leads; the lead brief with a next step, follow-up drafts in the buyer's language, one-click site visits and sales verdicts; the says-versus-does checks and retraining that learns from sales verdicts; consent before tracking, data retention and erasure, a mocked OTP and a dashboard passcode. All of Week 4: the analytics page, everything needed to deploy (`docs/DEPLOY.md`), the measured results (`docs/RESULTS.md`), the architecture and demo script, a README with screenshots, and the pitch deck (`docs/LeadOps_pitch.pptx`). A pre-deploy code and security review (23 Nov): dead code removed, a chat rate limit, a daily LLM call cap and safer IP, masking and link handling. A masal.ai-style redesign (23 Nov): a LeadOps front page at `/`, the property site at `/demo`, and the property site, dashboard and analytics restyled in LeadOps' own colours; the README screenshots and the pitch deck's two app screenshots are refreshed. 262 tests pass. Deployed (23 Nov): the site and dashboard on Vercel, the backend on Render and the database on Neon (both in Singapore), all on free plans, and checked end to end on the live servers.
- **Next (only the team can do these):** 30 to 50 real test sessions through tester links, which now work on the live site (`https://leadops-henna.vercel.app/demo?lo_test=genuine&lo_tester=t01`), then `ml/evaluate.py` on the database that holds them and the Impact slide; one check with a real LLM key (added in Render's Environment tab); the 3-minute demo video and at least five rehearsals (`docs/DEMO_SCRIPT.md`).
- **Blocked:** the LLM features haven't been tried with a real API key (the user hasn't approved spending it); template mode and the keyword rules work, and Claude's request shape matches the API reference.
- **Code:** https://github.com/bansalabhay01-ui/Real_Estate (branch `main`)

---

## 2026-11-23 · bansalabhay01-ui · Deployed LeadOps on Vercel, Render and Neon

**Done**
- The user decided to deploy with the dashboard WebSocket's passcode left in its URL (the open question in the entry below), so the WebSocket contract is unchanged.
- The user found the services' websites hard, so Claude deployed with their command-line tools after the user approved the plan and signed in to each once in Chrome (`neonctl` 9.9.3 and Vercel CLI 66.6.0 through `npx`, Render CLI 2.38.0 from its GitHub release, checksum verified):
  - **Neon:** project `leadops`, Singapore (`aws-ap-southeast-1`), Postgres 18. The backend uses the direct (unpooled) connection string.
  - **Render:** web service `leadops-api`, Singapore, free plan, built from the public GitHub repo with `render.yaml`'s build and start commands, health check `/health`, Python 3.14.6, `CORS_ORIGINS=*`, `RETENTION_DAYS=180`, a new random `DASHBOARD_PASSCODE` and no LLM key (template answers): https://leadops-api-pudl.onrender.com
  - **Vercel:** project `leadops`, deployed from `frontend/` with `VITE_API_URL` set for production: https://leadops-henna.vercel.app
- New `frontend/.gitignore` (approved): keeps Vercel's `.vercel/` link folder out of git.
- `README.md`: a "Live demo" table. `docs/DEPLOY.md`: "The live deployment", "Putting a change live" and a note on the Render CLI in Git Bash.
- Checked on the live servers: 18/18 API checks (`/health` with the LightGBM model, the passcode on the dashboard routes and the WebSocket, browser access from the Vercel site, the tracking script, the assistant's brochure answer, a 250-visitor Simulate traffic run with 200/200 bots blocked, 30/30 junk filtered and 20/20 buyers kept, analytics, Clear) and 4/4 in headless Chrome (front page, the demo site's homes, the dashboard reaching Live with the passcode, analytics). The test chat visitor and the simulated visitors were erased.

**Next**
- Real test sessions on the live site, then `ml/evaluate.py`; one check with a real LLM key; the demo video and rehearsals.
- Optional: connect GitHub to Render and Vercel so that pushes deploy by themselves.

**Notes**
- Neither service redeploys when `main` changes: `docs/DEPLOY.md` ("Putting a change live") has the steps.
- The dashboard passcode is kept only in Render (`leadops-api`, Environment). It was shown to the user once and isn't in the repo.
- The first Render deploy never went live: run from Git Bash, the CLI's `--health-check-path /health` became `C:/Program Files/Git/health`. Claude fixed the path, cancelled that deploy and redeployed. Set `MSYS_NO_PATHCONV=1` before using the Render CLI in Git Bash.
- `vercel link` also wrote `frontend/.env.local`, holding a short-lived Vercel token. Git ignores it, and `.env` files are blocked for Claude, so it is still there; it can be deleted.
- On Render's free instance a 250-visitor Simulate traffic run took 42 seconds rather than 30. The free plan also sleeps after about 15 minutes, so open `/health` before presenting.
- The Neon, Render and Vercel command-line tools stay signed in on this laptop for later redeploys.

---

## 2026-11-23 · bansalabhay01-ui · Pre-deploy review, then a masal.ai-style redesign

**Done**
- **Redesign, Part 5 (documents):** new screenshots in `docs/screenshots/` (taken from a throwaway backend filled by Simulate traffic, one real stealth bot and a buyer chat), plus `front.png` for the front page; the README gallery, links and run steps, `docs/DEMO_SCRIPT.md` (opens on the front page), the `docs/DEPLOY.md` checklist, `docs/ARCHITECTURE.md` and `CLAUDE.md` describe the new addresses. `docs/LeadOps_pitch.pptx`: only its two app screenshots (slides 5 and 6) were swapped, at the same pixel sizes; the deck's text and layout are unchanged, its alt text still matches, and it passes the pptx validator.
- **Redesign, Part 4 (dashboard and analytics):** a shared dark sales header with a pill menu (Dashboard, Analytics, Demo site), `SalesHeader` in `frontend/src/dashboard/PasscodeGate.jsx`; light working area with rounded cards and tables, pill filters, buttons and selects, mono section labels in the visitor panel, the passcode screen on the drafting-grid background; the chart colours stay as they were (checked for colour blindness). Pages no longer reset the tab title to the property site's on the way out. The old `font-wide` classes are gone. No feature changes. Checked on a throwaway backend with a passcode: 10/10 (wrong passcode refused, right one opens the live dashboard, Simulate traffic fills the table, a visitor's panel and brief open, a verdict saves, analytics loads, no errors, no sideways scroll at 1440 or 390 px).
- **Redesign, Part 3 (the property site at `/demo`):** the homes page gets a dark drafting-grid hero with the self-drawing floor plan, pill filters and rounded listing cards; the property page, EMI calculator, enquiry form and phone check, assistant, offer card, privacy page and not-found page get the new look (no feature changes); the consent banner is a floating dark card; the footer links back to the front page. Everything the bots rely on is unchanged (Accept, the form labels, the hidden field, Send enquiry, Enquiry sent, the price element). `ml/bots/run_bots.py` opens `/demo?lo_test=...`, the simulator's home path is `/demo` (paths aren't model features), and the README tester links point at `/demo`. Checked on a throwaway backend (no LLM key, temporary database) and a second copy of the site: the three real bots were all labelled Bot (the stealth bot by the model alone), and a buyer's path passed on desktop and phone (consent, property page, the assistant's answer, enquiry, OTP), with no sideways scroll or page errors; 262 backend tests pass.
- **Redesign, Part 2 (the LeadOps front page at `/`):** `frontend/src/pages/Landing.jsx` with sections in `frontend/src/landing/`: `Hero.jsx` (fixed header with a pill menu, the headline "Every website visitor, sorted in seconds" with a pill that flips Bot, Junk, Hot; a strip of the signals LeadOps reads instead of customer logos; the problem paragraph that lights up on scroll; measured results 15/15 real bots and 1,000 simulated visitors, labelled as such), `LiveSort.jsx` (a live feed and three example visitors, using the scoring engine's own reason sentences), `HowItWorks.jsx` (four steps with an app window), `DashboardPreview.jsx`, `Features.jsx` (smart offers, the assistant in 4 languages, says versus does, the feedback loop, WhatsApp drafts and privacy) and `Closing.jsx` (business model in words with no prices, FAQ, funnel call to action, footer). No customer logos, testimonials or made-up numbers. The property site's homes page moved to `/demo` (links updated); old `/?lo_test=` tester links forward there. The dashboard now loads separately. Checked: build, no sideways scroll or console errors at 1440 and 390 px, and a headless Edge run (tracking intercepted, nothing written to the database) passed 8/8: the front page sends nothing, tracking starts on `/demo`, an old tester link still marks the visit, reduced motion stops the animations.
- **Redesign, Part 1 (design basics):** the user asked for the website in the style of https://masal.ai and a front page modelled on theirs. Plan approved with the recommended choices (`LEADOPS_PLAN.md`). Geist and Geist Mono replace Archivo (Noto Sans Devanagari stays). New colour tokens in `frontend/src/index.css` (night `#07101c`, deep `#0b2140`, sky, paper, concrete, blueprint, marigold), type utilities (`text-display`, `text-section`, `text-title`, `text-lede`), dimension-line rules, the drafting grid and glow, and the marquee, scan and row animations, all off with reduced motion. `frontend/src/components/ui.jsx`: buttons, labels, sections, logo, marquee and a paragraph that lights up on scroll. SDK 1.4.0: a `data-exclude-paths` entry ending in `$` skips only that exact path, so the front page at `/` is never tracked; activity is filed under the page it happened on.
- Read every line of the backend, AI, scoring, `ml/`, SDK and frontend, and ran ruff, vulture, bandit, pip-audit and npm audit. No known-vulnerable packages (71 Python, all npm) and no secrets in the code or the git history.
- **Security fixes:**
  - LLM cost: `LLM_DAILY_LIMIT` (default 1000 calls in any 24 hours, 0 = no limit) in `ai/llm_client.py`. Past it every caller falls back to its template, so the demo keeps working. Added to `backend/.env.example`.
  - `POST /chat` allows 30 messages a minute per IP address and then returns 429 (`utils.RateLimit`, in memory). The chat widget explains the 429. Enquiries and events have no limit, on purpose: labelling spam is the product.
  - Visitor IP (`utils.client_ip`): Render adds to `X-Forwarded-For` without clearing what the browser sent, so the first entry could be faked. Cloudflare's `CF-Connecting-IP` / `True-Client-IP` now come first. `X-Real-IP` is no longer trusted.
  - `ai/privacy.py` masks phone numbers in any format before text reaches an LLM: dashes, brackets, landlines, Devanagari digits. Budgets and sizes are left alone.
  - The follow-up `mailto:` link encodes the address (backend and `LeadBrief.jsx`), so a fake email like `a@b.in?bcc=x@y.in` can't add recipients.
  - The SDK (1.3.1) drops a clicked link's query string and fragment, and keeps only the scheme of `mailto:`/`tel:` links. Enquiry forms send `page_url` without the query string.
  - `frontend/vercel.json` sends `X-Frame-Options: DENY`, `nosniff`, a referrer policy and a permissions policy.
- **Other fixes:** a lead brief no longer fails with a 500 if the visitor is erased during the LLM call. `ml/bots/run_bots.py` sends `DASHBOARD_PASSCODE` when it reads a bot's label. The cache-key SHA-1 calls are marked `usedforsecurity=False`.
- **Removed:** the unused `db.get_db`, the unused `_MAX_BEFORE` / `_MAX_AFTER` patterns in `ai/extract.py`, an unused import in `ml/train.py` and an unneeded export in `Filters.jsx`. Out-of-date comments in `scoring/__init__.py`, `ai/rag.py` and `scoring/explain.py` were rewritten.
- Checked: 262 tests pass (10 new: Cloudflare IP, the chat limit, the LLM cap, the masking), the frontend builds, and a live server run passed (no LLM key, throwaway database, passcode on).

**Next**
- The user decides on the dashboard WebSocket passcode (below), then the deploy.

**Notes**
- Left as it is, for the user to decide: the dashboard WebSocket sends its passcode as `?passcode=` in the URL, which uvicorn writes to Render's logs. Moving it to a header-like channel changes the WebSocket contract in `docs/CONTRACTS.md`, so it needs the team's OK.
- The remaining bandit warnings are false alarms: random numbers for simulation, the bot runner's fixed command line, and URLs that come from the developer's own command line.
- After deploying, check that the dashboard shows each visitor's real IP. If every IP looks the same, Render isn't passing on Cloudflare's header.

---

## 2026-11-18 · bansalabhay01-ui · Week 3 build and Week 4

**Done**
- The user said to complete the project from the plan and push after each task, which lifts the 16 Nov pause on saving. The plan's recommended decisions apply: ask for consent before tracking, Marathi as the regional language, and the contract additions as listed. No real LLM key is used.
- **Part 1, Simulate traffic and Run a real bot:**
  - `backend/app/api/demo.py`: `POST /demo/simulate` makes visitors with `ml/simulator.py` (new `make_visitors()`) and feeds them through the real ingestion code, spread over about 30 seconds, ending with a scoreboard (`simulation_started` / `_progress` / `_done` on the WebSocket). `GET /demo/status`, `DELETE /demo/simulated` (visitors with `sim-` IDs only) and `POST /demo/bot` (runs a Playwright bot on the backend's laptop, local sites only).
  - `backend/app/retention.py`: `erase_visitors()` removes a visitor and everything linked to it. `classify_visitor(use_llm=False)`: simulated traffic never calls an LLM.
  - Dashboard: a "Live demo" panel (`frontend/src/dashboard/SimulateTraffic.jsx`) with the dialog, a progress bar, label counts as they arrive, the scoreboard, a breakdown by kind of visitor, Clear and Run a real bot. Simulated rows get a "Simulated" chip.
  - Checked: 118 tests pass and the frontend builds. A headless Edge check passed 12/12 (a 60-visitor run through the button: 40/40 bots blocked, 10/10 junk filtered, 10/10 buyers kept; Clear; no sideways scroll at phone width; no page errors). The stealth bot launched through `POST /demo/bot` was labelled `Bot` by the ML model alone.
- **Part 2, assistant v2:**
  - `backend/app/ai/agent.py`: the assistant is a LangGraph graph: understand, search_properties, one of calc_emi / brochure_search / book_visit / request_call, reply, save_lead_details. One structured LLM call understands the message (patterns without a key), so a message still makes two LLM calls while the visitor waits. If the graph itself fails, a plain template answer still goes out. `LANGSMITH_TRACING` is forced off, so conversations never leave for a tracing service.
  - `backend/data/brochures/`: 18 fictional brochures. `backend/app/ai/brochures.py`: BM25 keyword search, with Hindi, Hinglish and Marathi words mapped to the brochures' English words.
  - Site visits: the `site_visits` table, `POST / GET / PATCH /visits` (`backend/app/api/visits.py`), 15 intent points, `visit_booked` and `visit_updated` on the WebSocket, and a Site visits panel on the dashboard. Contact details are collected in a form in the chat (`frontend/src/components/ContactCapture.jsx`), never as chat text. `Lead.source` records where an enquiry came from.
  - Languages: Marathi joins English, Hinglish and Hindi in detection, patterns (including Devanagari digits), replies and the form. A short reply keeps the conversation's language.
  - Checked: 160 tests pass (with fake LLMs for the LLM paths) and the frontend builds. A headless Edge check passed 13/13: a payment-plan answer from the brochure, an EMI with 30% down, a Saturday-morning visit booked through the form, a Marathi reply, the visit confirmed from the dashboard with its intent points, no sideways scroll at phone width, no page errors.
- **Part 3, smart engagement trigger:**
  - `backend/app/scoring/nudge.py` decides after each event batch: looks human (0.8+), intent 40+, no contact details, not chatting, at least a minute on this visit, on a property page; once per visit and twice a day at most. The offer (floor plan, EMI plan, site visit or shortlist) comes from templates in the visitor's language. A new `nudges` table keeps each offer and what became of it.
  - It travels back in the `/events` response as `nudge`. SDK 1.2 hands it to `LeadOps.onNudge(fn)`. The demo site shows an offer card above the assistant button; accepting opens the assistant with the contact form and sends an enquiry with `source: "assistant_offer"`.
  - Dashboard: a "Found by the assistant" tile and alert, offers in the visitor's timeline, and **Send an offer now** for anonymous Warm or Hot visitors (`POST /visitors/{id}/nudge`).
  - Checked: 175 tests pass and the frontend builds. A headless Edge check passed 12/12: the offer appeared for a serious anonymous visitor, accepting it created a lead marked as found by the assistant, a hand-sent offer arrived with the next batch, no sideways scroll at phone width, no page errors. The check found one bug, now fixed: the visitor panel didn't refresh after sending an offer.
- **Part 4, lead brief, follow-ups and verdicts:**
  - `backend/app/ai/brief.py`: `GET /visitors/{id}/brief` gives three plain lines and a next step from rules (call now, send an offer, WhatsApp today, check first, confirm the visit, or nothing). `POST /visitors/{id}/followup` drafts a WhatsApp or email message in English, Hinglish, Hindi or Marathi, with a `wa.me` link. With a key the LLM writes both, only when a salesperson asks; a brief is kept until the score changes. The LLM never sees a name, number or email: drafts use a `{name}` placeholder that the backend fills in.
  - Sales verdicts count at once: Fake makes a visitor `Junk`; Genuine and Converted overrule the rules and the model, leaving the intent score to decide. The latest verdict is kept on the visitor and shown as a chip and in the enquiries table.
  - Dashboard: `frontend/src/dashboard/LeadBrief.jsx` opens the visitor panel with the brief, the next step, an editable follow-up draft (Copy, Open in WhatsApp, Open in email), one-click site-visit booking, Send an offer now and the verdict buttons.
  - Checked: 204 tests pass and the frontend builds. A headless Edge check passed 15/15. It found one bug, now fixed: screen-reader labels inside wide tables made the whole page scroll sideways on phones.
- **Part 5, consistency check and learning from verdicts:**
  - `backend/app/scoring/consistency.py` compares what a visitor says with what they do: budget, city and BHK against the homes they opened (three homes at least), and "to live in" against "investment". It shows under "Why this label" and in the brief, and never changes the label.
  - `ml/train.py` reads the sales verdicts. Genuine and Converted join the training data at five times the weight. Fake counts as a bot only when nothing else explains it: a broker or a made-up number is a person with bad details, and shouldn't teach the human check. It reports how the model that was running did on those visitors, saves the counts in `model_info.json` and, with 20 or more verdicts, prints suggested intent points for the team to review.
  - Dashboard: the model version, how many verdicts it learned from, and a **Relabel everyone** button.
  - Checked: 216 tests pass and the frontend builds. A headless Edge check passed 7/7. A real training run on throwaway data learned from 17 of 22 marked visitors, wrote to a scratch folder and left the committed model unchanged.
- **Part 6, privacy and OTP:**
  - Consent: SDK 1.3 supports `data-consent="required"`: nothing is sent or stored until `LeadOps.consent(true)`. The demo site asks with a banner (Accept and Decline carry equal weight) and has a privacy notice at `/privacy` with a Delete my data button.
  - `backend/app/retention.py`: a clean-up at startup and then daily (`RETENTION_DAYS`, default 180) deletes old browsing and chat, removes visitors who never enquired and strips personal details from old enquiries. `DELETE /visitors/{id}` erases a visitor, from the dashboard or by the visitor themselves.
  - OTP (mocked): after an enquiry the form asks for a 6-digit code, shown on screen and labelled as a demo. `POST /leads/{id}/verify` adds a "Phone verified by OTP" check and 5 intent points.
  - `backend/app/auth.py`: with `DASHBOARD_PASSCODE` set, the dashboard's routes and WebSocket need the passcode and the dashboard asks for it. Unset, nothing changes.
  - The Playwright bots accept the banner, as a real stealth bot would.
  - Checked: 240 tests pass and the frontend builds. A headless Edge check passed 24/24: nothing sent or stored before the answer, held events sent on Accept, nothing sent after Decline, the OTP, Delete my data, the passcode and erasing from the dashboard. All three real bots were still labelled `Bot`, the stealth bot by the ML model alone.
- **Week 4 plan:** "Week 4 Build Plan" at the end of `LEADOPS_PLAN.md`, including what only the team can do.
- **Week 4 Part 1, analytics page:** `/dashboard/analytics` (`frontend/src/pages/Analytics.jsx`, `backend/app/analytics.py`, `GET /analytics`): the share of enquiries filtered out, estimated sales hours saved (6 minutes per filtered enquiry, stated on the page), buyers found by the assistant, site visits, the funnel from visitor to Hot lead, visitors by label and a Recharts chart of visitors per day with a table view. The period and simulated traffic can be filtered. The charts load only on this page, so buyers on the demo site never download them. Checked: 247 tests pass, the frontend builds and a headless Edge check passed 10/10.
- **Week 4 Part 2, ready to deploy:** `render.yaml`, `frontend/vercel.json` and `docs/DEPLOY.md` (Neon, Render and Vercel, step by step). `psycopg[binary]` joins `backend/requirements.txt`. Browser input is now safe for Postgres: NUL characters are removed and numbers too big for their column are dropped or capped. `TEST_DATABASE_URL` runs the tests against Postgres. Checked on a real PostgreSQL 18 server: all 248 tests pass, and the 250-visitor Simulate traffic run blocked 200/200 bots, filtered 30/30 junk leads and kept 20/20 buyers in 9 seconds, peaking at 268 MB of memory (Render's free plan has 512 MB). The deploy itself needs the team's own accounts.
- **Week 4 Part 3, final metrics:** `ml/evaluate.py` scores everyone with the saved model, leaves sales verdicts out and writes `docs/RESULTS.md`, keeping real people, real bots and simulated traffic apart, with 95% confidence intervals. Measured: **real people, no sessions yet**, so nothing is claimed; **real bots, 15 of 15 caught** (three bots the team wrote, five runs each, 95% CI 80% to 100%); **simulated traffic, 600 of 600 fake visitors filtered and 400 of 400 buyers kept** on a new random sample, which the report marks as the easiest test. Checked: 252 tests pass.
- **Week 4 Part 4, documents:** `docs/ARCHITECTURE.md`, `docs/DEMO_SCRIPT.md` (a 3-minute run sheet, a backup plan and answers to likely questions) and a README with screenshots from the running app (`docs/screenshots/`) and the measured results. The demo's buyer path was walked in a real browser: the assistant answers from the brochure, the visit books, and the path earned 56 intent points (Warm). A person's rehearsal still has to confirm the label, because a scripted browser is labelled Bot.
- **Week 4 Part 5, pitch deck:** `docs/LeadOps_pitch.pptx`, 12 slides: problem, solution, scoring, the assistant, live demo, architecture, impact, privacy, business model, roadmap and close, with speaker notes. The problem figures are cited on the slides and in the notes: automated traffic was 51% of all web traffic in 2024 (Imperva Bad Bot Report 2025); about 12% of marketing spend leaks to invalid traffic (mFilterIt, Dec 2025, as reported by Storyboard18); India's real estate market reaches US$1 trillion by 2030 (IBEF); DPDP Act penalties reach ₹250 crore. No reliable figure was found for the share of Indian real estate leads that are junk, so the deck doesn't claim one. The Impact slide says "Next" for real people until they are measured. Checked: the deck passes the file validator and was opened and rendered in PowerPoint.

**Next (only the team can do these)**
- 30 to 50 real test sessions, then `ml/evaluate.py` and the Impact slide.
- The deploy with the team's own accounts (`docs/DEPLOY.md`).
- One check with a real LLM key.
- The 3-minute demo video and at least five rehearsals (`docs/DEMO_SCRIPT.md`).

**Notes**
- Teammates: run `pip install -r requirements.txt` in `backend/` again for `langgraph`.
- `rag.py` now matches whole-word starts: "emi" used to match "premium".

---

## 2026-11-08 · bansalabhay01-ui · Part 6 saved, Week 3 plan

**Done**
- Saved the previous session, which had ended before its save: checked Week 2 Part 6 (results in the entry below), committed it and pushed. GitHub sign-in works again, so Parts 4, 5 and 6 are now on GitHub.
- Wrote the Week 3 build plan ("Week 3 Build Plan" at the end of `LEADOPS_PLAN.md`), six parts: Simulate traffic and Run a real bot; assistant v2 (LangGraph agent, brochures, EMI, site visits, a regional language); the smart engagement trigger; the lead brief, follow-ups and sales verdicts; the consistency check and learning from verdicts; privacy (consent, retention, erasure), a mocked OTP and a dashboard passcode. It lists the contract additions, new files and packages, changes from the main plan, four decisions, team actions and the checks.
- pip dry runs on Python 3.14 (Windows): `langgraph` 1.2.20 adds 20 packages, all ready-made wheels; `chromadb` 1.5.9 adds 57 (onnxruntime, gRPC, a Kubernetes client, OpenTelemetry), so the plan uses BM25 over Markdown brochures instead.

**Next**
- The user's go-ahead and the four decisions (consent before tracking, the regional language, the contracts, one real LLM check), then Week 3 Part 1.

**Notes**
- Claude's request shape checked against the current API reference: structured outputs in `output_config.format`, effort in `output_config.effort`, `fallbacks: "default"` with the `server-side-fallback-2026-07-01` beta, and no `temperature`.
- `git push` works with the saved credentials; run without a terminal, Git Credential Manager prints a harmless "Cannot prompt" line first.
- Rough LLM cost per chat message (up to three calls): about $0.03 on Claude Opus 5.5, under a tenth of a cent on Claude Haiku 5.5.

---

## 2026-11-06 · bansalabhay01-ui · Week 2 plan and Parts 1-6 (tester link, features and rules, model and labels, dashboard, bots, LLM extraction and visitor type)

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
- **Part 3, model and labels:**
  - `ml/train.py` trains the LightGBM human check on 2,000 simulated visitors, whole and cut short, tunes the cut-offs (they can only get more careful than 0.2 / 0.5) and measures the whole engine on unseen simulated visitors and on the real test set (tester-link visitors in the database). It saves `backend/data/model/bot_model.txt` and `model_info.json`, now committed (model `lgbm-20261106-a53bb8`).
  - `scoring/model.py` gives `human_prob` plus SHAP values from LightGBM's `pred_contrib`, with a hand-made fallback formula if the model is missing. `scoring/combine.py` holds the intent points (out of 100) and the label order from the plan. `scoring/explain.py` writes the plain-language reasons and summary line. `scoring/engine.py` rescores a visitor after every event batch, enquiry and chat message, saves the score on the visitor, keeps label changes in `scores` and sends `score_update`.
  - API: `VisitorOut.score`, `VisitorDetailOut.score_detail`, `LeadOut.label` and `checks`, `GET /visitors?label=&sort=intent`, `/stats` labels, `POST /scoring/rescore`, `/health` model version. `docs/CONTRACTS.md` (section 6) and the README ("Scoring") updated.
  - Database: new nullable columns on `visitors` (`label`, `intent_score`, `human_prob`, `score`, `scored_at`, `visitor_type`). `db.init_db()` now adds new columns to existing databases at startup, so nobody has to delete theirs.
  - `python ml/simulator.py --send URL --report` prints how the backend labelled each kind.
  - Checked: 87 tests pass and the frontend builds. Through the live API, 500 fresh simulated visitors (seed 7) were sorted in 34 s: 200/200 bots and 100/100 junk filtered out, 200/200 genuine buyers kept (4 in Review). The existing dashboard shows the labels.
- **Part 4, dashboard v1:**
  - Visitors table: label badges (an icon per label so meaning never rests on colour; Cold/Warm/Hot show 1-3 strength bars), the top reason, an intent meter, filter buttons with live counts from `/stats` and a sort by highest intent. A filtered or sorted list is fetched from the API and kept current with live updates. Columns trimmed to fit beside the side panel.
  - Visitor panel: new "Why this label" (`frontend/src/dashboard/ScoreBreakdown.jsx`): reasons, the human check with SHAP factors as diverging bars (blueprint = towards a person, alert red = towards a bot; the pair passed the colour-blind validator), contact-detail checks and the intent points.
  - Enquiries table: label column and the backend's checks. A "new hot lead" alert with View and Dismiss. Stat tiles: Visitors, Active now, Enquiries, Hot right now, Filtered out.
  - The model now has monotone constraints (`ml/train.py`), so a bot signal can only push towards "bot" and SHAP bars read sensibly; importance is spread across behaviour features. Retrained as `lgbm-20261107-49dc13`; simulated results unchanged.
  - Checked: 87 tests pass, the frontend builds, and a headless Edge check passed 10/10 (badges, Hot filter rows = Hot count, intent sort, Hot alert, score panel, enquiry labels, no sideways scroll at phone width, no page errors). Screenshots looked right at desktop and phone width.
- **Part 5, Playwright bots:** `ml/bots/run_bots.py` with three bots (naive form bot, stealth form bot, scraper) that drive the installed Edge or Chrome; `--headed` for the live demo, `--api` prints each bot's label. Every run uses a `lo_test=bot` tester link, so the bots join the real test set. Checked: 9 runs (3 of each), all labelled Bot. The naive bot and the scraper were caught by the rules (honeypot, webdriver, headless user agent); the stealth bot by the ML model alone ("under 1% likely to be a person; the mouse jumped about 63-99 pixels at a time"). `ml/train.py`'s real-test-set report works: 9/9 tester bots caught. README: "Playwright bots".
- **Part 6, LLM extraction and visitor type** (built on 2026-11-07, checked and saved on 2026-11-08):
  - `llm_client.generate_json()`: a JSON object that follows a schema. Claude returns it as a structured output (`output_config.format`); Gemini and Groq use their JSON mode with the schema in the prompt. Any failure, including JSON that doesn't parse or an answer that was cut off, raises `LLMError`.
  - `ai/extract.py`: `smart_extract()` runs the patterns, then, with a key, the LLM reads the message with the visitor's last four messages ("same budget but in Bengaluru", "80-85 lakh ke beech"). Every LLM value is checked first (`clean_details`: a known city or locality, BHK 1-6, budgets ₹5 L-₹100 Cr, move-in within 5 years), and a budget pair never mixes the two extractors. New buyer detail `purpose` (`own_use` / `investment`), found by the patterns too; the assistant asks it last.
  - `ai/classify.py`: end buyer, investor, tenant, broker or spam, with a confidence and a one-line reason, from the enquiry messages and chat: the LLM on masked text, or keyword rules without a key or when the call fails. `scoring/engine.py` runs it after the response is sent (a FastAPI background task) for every chat message and every enquiry with a message, skips it when the messages haven't changed, saves it on the visitor and rescores. A confident (0.7+) broker, spammer or tenant becomes Junk (Review with intent 70+).
  - Simulator: a new junk kind, `tenant` (wants to rent), and an investor message among genuine buyers. Retrained as `lgbm-20261107-c41e90`; `ml/train.py` gives simulated visitors the keyword visitor type, as the backend does without a key.
  - Dashboard: "Purpose" in the buyer details (the visitor type already showed in "Why this label"). `docs/CONTRACTS.md` and the README ("The LLM") updated.
  - Checked: 110 tests pass and the frontend builds. Through the live API (template mode, throwaway database), 500 fresh simulated visitors (seed 7): 200/200 bots and 100/100 junk filtered out, including 18/18 tenants that only the visitor type catches; 200/200 genuine buyers kept (4 in Review). In chat, the assistant asks the purpose question and saves "for my family to live in" as `own_use`; a Hinglish rent question is classified as a tenant. Claude's structured-output and refusal-fallback request shape matches the Claude API reference.

**Next**
- Week 3: write the build plan and wait for the go-ahead.

**Notes**
- With an LLM key, each chat message now makes up to three LLM calls: detail extraction and the reply while the visitor waits, then the visitor type in the background.
- The user said "continue" without answering the plan's two decisions, so the plan's recommendations apply: the contract additions as planned (written into `docs/CONTRACTS.md` as each part lands) and same-Wi-Fi testing.
- Teammates: run `pip install -r requirements.txt` in `backend/` again for the new packages, and `pip install -r ml/requirements.txt` (from the repo root, into the same venv) to train or run the bots.
- Simulated results are near perfect (AUC 1.0) because the simulator is easy to separate; the real test set is the honest number. Two simulator quirks were fixed so the model leans on behaviour: shared IPs (now 30% of people, and bots often use proxies) and full-screen windows (5% of desktop users).
- Problems hit: LightGBM's model file lists tree sizes in bytes, so Windows line endings broke loading (the trainer now writes `\n`, the loader normalises). On Windows, `localhost` costs about 2 s per request from Python (IPv6 first), so the simulator now sends to `127.0.0.1`. The simulator's console output is plain ASCII, because Windows pipes use the old code page.
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
