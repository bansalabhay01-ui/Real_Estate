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

## 3. Assistant: frontend -> `POST /chat`

Request: `{"visitor_id": "...", "session_id": "...", "message": "3BHK under 90L in Pune?", "listing_id": null}`
(`listing_id` is the property page the visitor is on, if any).

```json
{
  "reply": "Here are 2 homes in Pune, 3 BHK, under ₹90 L: ...",
  "listings": [{"id": "PUN-003", "project": "Indigo Greens", "...": "..."}],
  "extracted": {"city": "Pune", "bhk": 3, "budget_max": 9000000, "language": "en"},
  "profile": {"city": "Pune", "bhk": 3, "budget_max": 9000000, "language": "en"},
  "mode": "template"
}
```

- **extracted**: details found in this message; **profile**: everything known so far (saved on the visitor).
- Buyer detail keys: `city`, `locality`, `bhk`, `budget_min`, `budget_max` (INR), `timeline_months`,
  `loan_needed` (true/false), `language` (`en` / `hinglish` / `hi`). Week 2's LLM extraction keeps these keys.
- **mode**: `llm` when an LLM wrote the reply, `template` without a key or when the LLM call failed.

## 4. Routes

| Method and path | Purpose | Owner |
|---|---|---|
| `POST /events` | SDK event batches | B |
| `GET /visitors?limit=&offset=` | visitors, most recent activity first | B |
| `GET /visitors/{id}` | one visitor: sessions, events (newest first, up to 200), enquiries, chat | B |
| `GET /stats` | `{visitors, active_now, leads, chatting_visitors}` for the dashboard | B |
| `GET /listings?city=&bhk=&min_price=&max_price=&q=` | listings | B |
| `GET /listings/{id}` | one listing | B |
| `POST /leads`, `GET /leads`, `GET /leads/{id}` | enquiries | B |
| `POST /chat`, `GET /chat/{visitor_id}` | the assistant and a visitor's conversation | C |
| `POST /feedback`, `GET /feedback` | sales verdicts: `genuine` / `fake` / `converted` | B |
| `WS /ws/dashboard` | live dashboard feed | B |
| `GET /sdk/leadops.js` | the tracking script | A |
| `GET /health` | `{status, llm, listings}` | B |

## 5. Dashboard WebSocket: `WS /ws/dashboard`

Server to browser only. On connect:

```json
{"type": "snapshot", "visitors": [VisitorOut, ...], "leads": [LeadOut, ...]}
```

Then, as things happen:

```json
{"type": "visitor_update", "visitor": VisitorOut}
{"type": "lead_created", "lead": LeadOut}
```

`VisitorOut` fields: `id`, `site`, `first_seen`, `last_seen`, `session_count`, `page_views`, `event_count`,
`lead_count`, `chat_count`, `last_path`, `last_ip`, `device`, `automation_hints`, `profile`, `label`,
`test_label` (`genuine` / `junk` / `bot` on test sessions, otherwise `null`).
`automation_hints` lists raw signals (`webdriver`, `automation_user_agent`, `no_browser_languages`,
`no_user_agent`); it is not a verdict.

Planned for Week 2: `{"type": "score_update", "visitor_id": "...", "label": "Hot", "intent_score": 82, "reasons": [...]}`.

## 6. Labels (Week 2, to agree)

`label` is one of `Bot`, `Junk`, `Cold`, `Warm`, `Hot`, `Review` (see `LEADOPS_PLAN.md`). The `scores` table already
has `label`, `human_prob` (0-1), `intent_score` (0-100), `reasons` (list of strings) and `model_version`.
