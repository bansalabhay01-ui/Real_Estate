# LeadOps shared contracts (draft for Day 1 review)

These are the shapes the SDK, frontend, backend, simulator and scoring code agree on, so all three of us can
work in parallel. The code version lives in `backend/app/schemas.py`; live docs for every route are at
http://localhost:8000/docs when the backend runs.

**Rules**
- Adding an optional field is fine at any time. Renaming, removing or changing the meaning of a field needs the
  whole team's agreement, and this file is updated in the same commit.
- IDs from the SDK are UUIDs. Any ID is 8-64 characters of letters, digits, `-` and `_`.
- Browser times (`ts`, `sent_at`, `client_ts`) are milliseconds since 1970 (`Date.now()`). Server times are
  ISO 8601 in UTC with a `Z`, e.g. `2026-11-03T08:15:00.000Z`.
- Money is whole rupees (INR) as integers: `9000000` is ₹90 L.
- Too-long text is cut, not rejected, so one long page title never loses a batch of events.

## 1. Event batch: SDK -> `POST /events`

Sent as JSON with `Content-Type: text/plain` (no CORS preflight, and `navigator.sendBeacon` can send it when a
page closes). Up to 100 events per batch, 256 KB at most.

```json
{
  "visitor_id": "4d1c8c1e-7f0a-4c55-9a41-0f3c2b7a9e10",
  "session_id": "b0e3f2a4-5c6d-4e7f-8a9b-1c2d3e4f5a6b",
  "site": "leadops-realty-demo",
  "sdk_version": "1.0.0",
  "sent_at": 1793697300000,
  "context": {
    "user_agent": "Mozilla/5.0 ...",
    "language": "en-IN",
    "languages": 3,
    "timezone": "Asia/Kolkata",
    "screen": "1920x1080",
    "viewport": "1536x730",
    "pixel_ratio": 1.25,
    "touch_points": 0,
    "hardware_concurrency": 8,
    "webdriver": false,
    "referrer": "https://www.google.com/",
    "utm": {"utm_source": "instagram"}
  },
  "events": [
    {"type": "page_view", "ts": 1793697299000, "path": "/property/PUN-002", "url": "http://localhost:5173/property/PUN-002",
     "title": "Aranya Courtyard, Wagholi | LeadOps Realty", "props": {"referrer": "/"}}
  ]
}
```

Response: `{"ok": true, "accepted": 1}`. A bad batch gets `422` with the validation errors.

When the assistant has an offer for this visitor (the smart engagement trigger), the response also has `nudge`:

```json
{"ok": true, "accepted": 12, "nudge": {"id": "9f2c41d07ab34e11", "kind": "floor_plan", "listing_id": "PUN-002",
  "project": "Aranya Courtyard", "language": "en", "text": "Want the 3 BHK floor plan of Aranya Courtyard on WhatsApp?",
  "cta": "Send it to me", "ask": "Asked for the 3 BHK floor plan of Aranya Courtyard on WhatsApp"}}
```

`kind` is `floor_plan`, `emi_plan`, `site_visit` or `shortlist`. SDK 1.2 hands it to the site's `LeadOps.onNudge(fn)`
handler; a site without a handler shows nothing. The site reports what happened with the events below and sends an
accepted offer as an enquiry with `source: "assistant_offer"` and `ask` as its message.

- **visitor_id**: kept in `localStorage`, so it links repeat visits from the same browser.
- **session_id**: a new one after 30 minutes without activity.
- **context.webdriver**: `true` when Selenium, Playwright or Puppeteer drives the browser.
- **context.languages**: how many languages the browser lists; headless browsers often list none.
- **context.test_label** / **context.tester** (optional): only on test sessions opened through a tester link,
  e.g. `?lo_test=genuine&lo_tester=t01`. `test_label` is `genuine`, `junk` or `bot` (anything else is dropped);
  `tester` is a code, not a name (up to 40 characters). Scoring never reads them; `ml/train.py` uses them to
  build the real test set. `?lo_test=off` clears them from the browser.
- The server adds the IP address (first `X-Forwarded-For` entry behind a proxy) and the `User-Agent` header.

### Event types

| type | sent when | props |
|---|---|---|
| `page_view` | a page opens, including in-app navigation | `referrer` (previous path, or `document.referrer` on the first page) |
| `page_leave` | the visitor navigates away or closes the page | `duration_ms` (time the page was visible), `max_scroll_pct`, `reason` (`navigate` / `close`) |
| `scroll_depth` | first time the visitor scrolls past 25 / 50 / 75 / 100 % | `percent` |
| `click` | a click on a link, button or `[data-lo-track]` element | `tag`, `text`, `track`, `id`, `href`, `trusted` (`false` = clicked by a script) |
| `activity` | every 10 s, if anything happened | `interval_ms`, `mouse_moves`, `mouse_distance`, `clicks`, `touches`, `keys` (a count, never the keys), `scrolls` |
| `property_view` | a property page loads (demo site) | `listing_id`, `city`, `bhk`, `price_inr` |
| `emi_used` | the EMI calculator settles after a change | `listing_id`, `price_inr`, `down_payment_pct`, `rate_pct`, `years`, `emi` |
| `floorplan_download` | the floor plan is downloaded | `listing_id`, `bhk` |
| `filter_used` | the home-page filters settle after a change | `city`, `bhk`, `max_price` |
| `enquiry_submitted` | the enquiry form is sent | `listing_id` |
| `chat_opened` / `chat_message` | the assistant is opened / sent a message | `listing_id`, `length` |
| `nudge_shown` / `nudge_accepted` / `nudge_dismissed` | the visitor saw / accepted / turned down an offer | `nudge_id`, `kind`, `listing_id` |

Custom events from any site: `LeadOps.track("name", {...})`. Names are lower-cased and spaces become `_`.

## 2. Enquiry: frontend -> `POST /leads`

```json
{
  "visitor_id": "4d1c8c1e-...", "session_id": "b0e3f2a4-...", "listing_id": "PUN-002",
  "name": "Priya Kulkarni", "phone": "9822012345", "email": "priya@example.com",
  "message": "Interested in a site visit this weekend.", "consent": true,
  "honeypot": "", "form_fill_ms": 48210, "client_ts": 1793697310000,
  "page_url": "http://localhost:5173/property/PUN-002"
}
```

Response `201`: `{"ok": true, "lead_id": 12}`.

- **honeypot**: the value of a field hidden from people. Real people leave it empty; form bots fill it.
- **form_fill_ms**: from the first touch of the form to submit. `0` means the form was sent without typing.
- **Never reject bot-looking enquiries.** Save them and answer as usual, so scoring can label them and bots
  get no hint. An enquiry without a `visitor_id` (an API call with no browsing) gets a `nosdk-...` visitor.
- **source** (optional): where the enquiry came from: `form` (the default), `assistant_offer` or `chat`. An unknown
  value is dropped, never rejected. `LeadOut` always has it.
- `LeadOut` (in `GET /leads` and the WebSocket) adds `label` (the visitor's current label, or `null`) and
  `checks`: `[{"check": "phone", "ok": false, "text": "Phone: the same digit over and over"}, ...]` for `phone`,
  `email`, `name`, `message`, `honeypot` and `fill_time` (only the ones that apply), and `verdict` (the sales team's
  latest verdict on this visitor, or `null`).

## 3. Assistant: frontend -> `POST /chat`

Request: `{"visitor_id": "...", "session_id": "...", "message": "3BHK under 90L in Pune?", "listing_id": null}`
(`listing_id` is the property page the visitor is on, if any).

```json
{
  "reply": "Here are 2 homes in Pune, 3 BHK, under ₹90 L: ...",
  "listings": [{"id": "PUN-003", "project": "Indigo Greens", "...": "..."}],
  "extracted": {"city": "Pune", "bhk": 3, "budget_max": 9000000, "language": "en"},
  "profile": {"city": "Pune", "bhk": 3, "budget_max": 9000000, "language": "en"},
  "mode": "template",
  "action": null,
  "emi": null
}
```

- **extracted**: details found in this message; **profile**: everything known so far (saved on the visitor).
- Buyer detail keys: `city`, `locality`, `bhk`, `budget_min`, `budget_max` (INR), `timeline_months`,
  `loan_needed` (true/false), `purpose` (`own_use` / `investment`), `language` (`en` / `hinglish` / `hi` / `mr`). With
  an LLM key, the LLM extraction fills the same keys; every value is checked before it is saved. `call_requested`
  (true) appears when the visitor asks for a call back.
- **mode**: `llm` when an LLM wrote the reply, `template` without a key or when the LLM call failed.
- **emi** (optional): an EMI worked out for this message, with the EMI calculator's formula: `{listing_id, project,
  price_inr, down_payment_pct, loan_inr, rate_pct, years, emi_inr, total_interest_inr}`.
- **action** (optional): what the chat widget shows under the reply. `{"type": "contact_form", "purpose": "site_visit" /
  "callback", "listing_id", "project", "need_contact", "day", "slot"}` asks for what is missing in a form, so phone
  numbers are never typed into the chat; `{"type": "visit_booked", "visit": VisitOut, ...}` confirms a booking.

### Site visits: `POST /visits`

Request: `{"visitor_id", "session_id", "listing_id": "PUN-002", "day": "2026-11-21", "slot": "morning", "language": "en"}`.
`slot` is `morning`, `afternoon` or `evening`; `source` is `assistant` (the default) or `dashboard`. A visitor who hasn't
left contact details also sends `name`, `phone`, `consent: true` (plus `honeypot` and `form_fill_ms`), which become an
enquiry with `source: "chat"`. Asking again for the same home and day changes the slot.

Response `201`, a `VisitOut`: `{id, visitor_id, lead_id, listing_id, project, locality, city, day, day_text: "Sat 21 Nov",
slot, status, source, name, phone, created_at, confirmation}`. `status` is `requested`, `confirmed`, `done` or
`cancelled`. `confirmation` is a sentence for the visitor in their language. `422` when details are missing or the day
is outside the next 60 days, `404` for an unknown home.

## 4. Routes

| Method and path | Purpose | Owner |
|---|---|---|
| `POST /events` | SDK event batches | B |
| `GET /visitors?limit=&offset=&label=&sort=` | visitors, most recent activity first; `label=Hot` filters, `sort=intent` puts the highest intent first | B |
| `GET /visitors/{id}` | one visitor: sessions, events (newest first, up to 200), enquiries, chat, site visits, offers (`nudges`), `score_detail` | B |
| `POST /visitors/{id}/nudge` | "Send an offer now": queue an offer that reaches the browser with the visitor's next event batch. `201` with the offer; `409` if they already shared contact details or are labelled Bot or Junk | B |
| `GET /visitors/{id}/brief` | `{lines: [three strings], next_step: {text, urgency: "now" / "today" / "this_week" / "none", action: "call" / "offer" / "whatsapp" / "review" / "confirm_visit" / "none"}, mode: "llm" / "template"}` | C |
| `POST /visitors/{id}/followup` | `{channel: "whatsapp" / "email", language: "auto" / "en" / "hinglish" / "hi" / "mr"}` returns a draft: `{channel, language, subject, text, mode, whatsapp_number, whatsapp_url, email, mailto_url}` | C |
| `GET /stats` | `{visitors, active_now, leads, chatting_visitors, labels, assistant_leads, offers_sent, offers_accepted}` for the dashboard; `labels` counts visitors per label, e.g. `{"Hot": 4, "Bot": 120}` | B |
| `POST /scoring/rescore` | reload the model (after `ml/train.py`) and relabel every visitor in the background: `{"ok": true, "visitors": 512}` | B |
| `GET /listings?city=&bhk=&min_price=&max_price=&q=` | listings | B |
| `GET /listings/{id}` | one listing | B |
| `POST /leads`, `GET /leads`, `GET /leads/{id}` | enquiries | B |
| `POST /chat`, `GET /chat/{visitor_id}` | the assistant and a visitor's conversation | C |
| `POST /visits`, `GET /visits?status=&limit=`, `PATCH /visits/{id}` | site visits, soonest first; `PATCH` takes `{status, day, slot}` | B |
| `POST /feedback`, `GET /feedback` | sales verdicts: `genuine` / `fake` / `converted`. A verdict relabels the visitor at once (section 6) | B |
| `WS /ws/dashboard` | live dashboard feed | B |
| `POST /demo/simulate` | `{bots, junk, genuine, seconds, seed}` (defaults 200 / 30 / 20 over 30 s): send simulated traffic through the real ingestion code. `202 {"ok": true, "run_id": "...", "total": 250, "seconds": 30}`, `409` while a run is going | B |
| `GET /demo/status` | `{running, run_id, sent, total, labels, scoreboard, simulated_visitors, bot_available, bot_running}` | B |
| `DELETE /demo/simulated` | remove the visitors the button made (IDs starting `sim-`): `{"ok": true, "removed": 250}` | B |
| `POST /demo/bot` | `{kind: "naive" / "stealth" / "scraper", site, headed}`: run one real Playwright bot on the backend's laptop. `501` where Playwright isn't installed, `422` for a site outside this laptop's network | B |
| `GET /sdk/leadops.js` | the tracking script | A |
| `GET /health` | `{status, llm, listings, model}`; `model` is the scoring model's version, or `fallback` | B |

## 5. Dashboard WebSocket: `WS /ws/dashboard`

Server to browser only. On connect:

```json
{"type": "snapshot", "visitors": [VisitorOut, ...], "leads": [LeadOut, ...]}
```

Then, as things happen:

```json
{"type": "visitor_update", "visitor": VisitorOut}
{"type": "lead_created", "lead": LeadOut}
{"type": "score_update", "visitor_id": "...", "label": "Hot", "previous_label": "Warm", "intent_score": 82,
 "human_prob": 0.99, "visitor_type": null, "reasons": ["3 visits over 2 days", "..."]}
```

Site visits add `{"type": "visit_booked", "visit": VisitOut}` and `{"type": "visit_updated", "visit": VisitOut}`.

The live demo tools add:

```json
{"type": "simulation_started", "run_id": "...", "total": 250}
{"type": "simulation_progress", "run_id": "...", "sent": 120, "total": 250, "labels": {"Bot": 96, "Junk": 14, "Warm": 6}}
{"type": "simulation_done", "run_id": "...", "scoreboard": {"run_id": "...", "total": 250, "seconds": 31.2,
  "bots_total": 200, "bots_blocked": 200, "junk_total": 30, "junk_filtered": 30, "genuine_total": 20, "genuine_kept": 20,
  "genuine_labels": {"Hot": 4, "Warm": 9, "Cold": 7}, "kinds": [{"kind": "bot/scraper", "total": 61, "labels": {"Bot": 61}}]}}
{"type": "bot_started", "kind": "stealth"}
{"type": "bot_finished", "kind": "stealth", "ok": true, "summary": "stealth #1: ... -> Bot: ..."}
```

Every event batch, enquiry and chat message rescores its visitor, so each `visitor_update` carries the latest
score. `score_update` follows only when the label changed (use it for "new Hot lead" alerts). After
`POST /scoring/rescore` the server sends a fresh `snapshot`.

`VisitorOut` fields: `id`, `site`, `first_seen`, `last_seen`, `session_count`, `page_views`, `event_count`,
`lead_count`, `chat_count`, `last_path`, `last_ip`, `device`, `automation_hints`, `profile`, `label`,
`test_label` (`genuine` / `junk` / `bot` on test sessions, otherwise `null`), `score` (section 6, `null` until
scored) and `feedback` (the sales team's latest verdict: `{label, note, created_at}`, otherwise `null`).
`automation_hints` lists raw signals (`webdriver`, `automation_user_agent`, `no_browser_languages`, `no_user_agent`);
it is not a verdict.

## 6. Scores and labels

`label` is one of `Bot`, `Junk`, `Review`, `Cold`, `Warm`, `Hot` (the rules are in `LEADOPS_PLAN.md`, Week 2
Build Plan, and `backend/app/scoring/combine.py`). A sales verdict overrules them: `fake` makes the visitor `Junk`;
`genuine` and `converted` leave only the intent score to decide (`Cold`, `Warm` or `Hot`).

`VisitorOut.score`:

```json
{
  "label": "Hot", "intent_score": 82, "human_prob": 0.998, "visitor_type": null,
  "reasons": ["Checked the EMI on a ₹85 L home", "Downloaded the 3 BHK floor plan", "2 visits over 2 days"],
  "summary": "Hot: Checked the EMI on a ₹85 L home; downloaded the 3 BHK floor plan; 2 visits over 2 days",
  "model_version": "lgbm-20261106-a53bb8", "scored_at": "2026-11-06T15:04:05Z"
}
```

- **human_prob**: 0-1 from the ML human check (LightGBM), `model_version` says which model (`fallback` when no
  model file is loaded). **intent_score**: 0-100 points for buying signals. **reasons**: up to five, most
  important first. **visitor_type**: `end_buyer` / `investor` / `tenant` / `broker` / `spam` once the visitor's
  enquiry messages and chat have been classified (in the background, by the LLM or keyword rules), otherwise
  `null`. A confident (0.7+) broker, spam or tenant is `Junk`, or `Review` with intent 70+.

Intent points: time on property pages (up to 20), repeat visits (up to 15), details shared with the assistant (up to
15), EMI calculator (12), floor plan (12), a valid enquiry (10), a focused search (up to 10), filters (6) and a requested
site visit (15), capped at 100. `VisitorDetailOut` also lists the visitor's `site_visits`.

`VisitorDetailOut.score_detail` (only in `GET /visitors/{id}`):

```json
{
  "signals": [{"code": "honeypot", "layer": "bot", "strength": "certain", "reason": "Filled in the hidden form field..."}],
  "human": {"prob": 0.004, "source": "model",
            "factors": [{"feature": "mouse_px_per_move", "label": "size of each mouse jump", "value": 138.8,
                         "contribution": 2.1, "towards": "bot"}]},
  "intent": {"score": 82, "points": [{"signal": "emi", "points": 12, "detail": "Checked the EMI on a ₹85 L home"}]},
  "visitor_type": {"type": "investor", "confidence": 0.7, "reason": "Buying as an investment", "source": "keywords"},
  "thresholds": {"bot": 0.2, "review": 0.5}
}
```

`factors` are SHAP values from the model (log-odds, positive pushes towards "bot"), the eight strongest. The
`scores` table keeps every label change: `label`, `human_prob`, `intent_score`, `reasons`, `model_version`.
