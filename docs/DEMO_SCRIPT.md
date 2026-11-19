# LeadOps demo script

A 3-minute run sheet for two people: one **speaks** and one **drives** the laptop. Rehearse it at least five times with a timer.

## Set up, 15 minutes before

1. **Run everything on the presenting laptop.** The demo then doesn't depend on the venue's internet, and the real bot can run.
   Follow "Run it" in the README. Install the bot's packages once, from the repo root:
   `backend\.venv\Scripts\python -m pip install -r ml/requirements.txt` (Mac/Linux: `backend/.venv/bin/python`).
2. **Start the backend on a clean database,** so old rehearsals don't show. From `backend/`:
   - Windows PowerShell: `$env:DATABASE_URL="sqlite:///./demo_day.db"; .venv\Scripts\python -m uvicorn app.main:app`
   - Mac or Linux: `DATABASE_URL=sqlite:///./demo_day.db .venv/bin/python -m uvicorn app.main:app`
3. **Open two browser windows.**
   - Window A, a **private** window at http://localhost:5173. This is the buyer.
   - Window B, a normal window at http://localhost:5173/dashboard. This is the sales team.
4. **Run the real bot now, before you go on stage.** In window B, choose **Stealth bot** and press **Run a real bot**. A browser
   window opens and the bot works for under a minute. Wait for its result line to appear under the buttons.
5. **Prepare the room.** Zoom both windows to 125%, turn off notifications and plug in the charger.
6. **Keep the recorded demo video open** in another tab.

## The three minutes

| Time | The driver does | The speaker says |
|---|---|---|
| **0:00 to 0:20** | Shows the demo site's home page in window A. | "More than half of all web traffic is now automated. For a property developer, that means fake enquiries, sales teams calling numbers that don't exist, and real buyers who leave without a word. LeadOps finds the real buyers and explains why." |
| **0:20 to 1:10** | Window A. Press **Accept**. Open **Aranya Courtyard**. Move the **Down payment** slider. Press **Download floor plan**. Press **Ask about homes** and send the three messages below. Fill in the form with a made-up name and number, tick the box and press **Book the visit**. | "I'm a buyer. LeadOps asked for my consent first. I check the EMI, download the floor plan and ask a question. The answer comes from the project's own brochure, and the assistant also speaks Hinglish, Hindi and Marathi." |
| **1:10 to 1:35** | Window B. Click the top row under Visitors. Point to the three-line brief and the next-step box. Press **Draft a follow-up**. | "Sales sees this within seconds: what this buyer wants, what to do next, and a follow-up ready to send on WhatsApp." |
| **1:35 to 1:55** | Press the **Bot** filter and click the stealth bot's row, the one marked **Test: bot**. Point to the brief. | "Before this talk we launched a real browser bot at the site. It hides its automation flags, moves the mouse, types with pauses and sends a believable enquiry. LeadOps still caught it, and it says why: the mouse jumps in big steps that people don't make." |
| **1:55 to 2:35** | Press the **All** filter. Press **Simulate traffic**, then **Start**. Wait for the scoreboard. | "Now 250 simulated visitors arrive in 30 seconds: 200 bots, 30 junk leads and 20 real buyers, all through the real scoring engine. Each one goes through hard rules, a machine-learning human check and a buying intent score. These visitors are simulated, so this is a stress test, not a claim about real-world accuracy." |
| **2:35 to 3:00** | Press **Analytics**. Point to the first tile and the funnel. | "This is the business result: the share of enquiries filtered out, and the sales hours saved, estimated at six minutes for each fake enquiry. One script tag, every visitor scored, every decision explained. That's LeadOps." |

**The three messages for the assistant**

1. `What's the payment plan?`
2. `We want a 3 BHK in Pune under 90 lakh, for our own use, buying in 3 months`
3. `Book a site visit on Saturday morning`

The buyer should end up **Warm**. Check this in rehearsal, because the label depends on how you actually browse.

Use a made-up phone number that starts with 6 to 9, never a real one. Numbers like 9999999999 are flagged as fake.

## Backup plan

| If this happens | Do this |
|---|---|
| **Run a real bot** is greyed out or the window doesn't open | Skip it. Say what the bot does in one sentence, and that the engine caught all 15 runs of the team's three bots (`docs/RESULTS.md`). |
| The buyer doesn't appear on the dashboard | Refresh window B. If it's still missing, check that window A's privacy banner was accepted. |
| The buyer shows **Review** or **Cold** instead of Warm | Say that LeadOps is careful with short visits. After Simulate traffic, open a **Hot** visitor instead. |
| The assistant's LLM is slow or fails | Carry on. It falls back to template answers by itself. |
| Simulate traffic is still running at 2:35 | Keep talking over the live counts, then move to Analytics. |
| The laptop's local setup fails | Open the deployed site, if the team has set one up (`docs/DEPLOY.md`). |
| Nothing works | Play the recorded demo video and narrate it. |

## Questions judges may ask

**How accurate is it on real people?** Quote section 1 of `docs/RESULTS.md`. Until the team has collected real sessions, say plainly
that this test is the next step. Never quote the simulated numbers as real-world accuracy.

**Could it block a real buyer?** A likely junk visitor with high intent goes to Review for a person to check, and a salesperson's
verdict always overrules the engine.

**How do you handle privacy?** Tracking waits for consent. Phone numbers and emails are masked before any text reaches an LLM.
Personal data is removed after 180 days by default, and a visitor can be erased on request.

**What if the LLM goes down?** The assistant falls back to templates, so the site keeps working.

**Is the phone check real?** Not yet. The OTP is mocked for the demo, and a real SMS provider can replace it.

**How would a developer adopt it?** By adding one script tag to their website. The sales team then works from the dashboard.
