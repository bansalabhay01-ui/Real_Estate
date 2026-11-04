"""Synthetic LeadOps traffic: labelled bot, junk and genuine sessions (Python standard library only).

Writes one session per line (JSONL) for training, and can also send the sessions to a running backend so they
show up live on the dashboard. Events have the same shape the tracking SDK sends (docs/CONTRACTS.md).

    python ml/simulator.py                                    # 200 bot, 100 junk, 200 genuine -> ml/data/sessions.jsonl
    python ml/simulator.py --bots 20 --junk 10 --genuine 20 --out ml/data/small.jsonl
    python ml/simulator.py --send http://localhost:8000 --bots 5 --junk 3 --genuine 4

Labels and kinds:
    bot      scraper (opens many pages in seconds), form_bot (enquiry with no browsing, often fills the
             honeypot), click_bot (scripted clicks at fixed intervals)
    junk     fake_details (real browsing, fake phone/email), broker (rival broker fishing for inventory),
             spam (promotional message)
    genuine  serious (focused search, EMI, floor plan, enquiry), casual (a short look, rarely an enquiry)

Chat messages are saved in the file but only sent with --chat, because the backend may call a paid LLM.
"""

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LISTINGS = json.loads((ROOT / "backend" / "data" / "listings.json").read_text(encoding="utf-8"))
SITE = "leadops-realty-demo"

UA_DESKTOP = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
]
UA_MOBILE = [
    "Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; RMX3741) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
]
UA_BOT = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/141.0.0.0 Safari/537.36",
    "python-requests/2.32.3",
    "Mozilla/5.0 (compatible; Scrapy/2.13; +https://scrapy.org)",
]

FIRST_NAMES = ["Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Sneha", "Arjun", "Kavya", "Rahul", "Isha", "Karthik",
               "Meera", "Siddharth", "Pooja", "Nikhil", "Divya", "Imran", "Fatima", "Harpreet", "Joseph", "Lakshmi"]
LAST_NAMES = ["Sharma", "Patel", "Iyer", "Reddy", "Nair", "Kulkarni", "Deshpande", "Gupta", "Singh", "Khan",
              "Fernandes", "Das", "Mehta", "Joshi", "Rao", "Menon"]
EMAIL_DOMAINS = ["gmail.com", "outlook.com", "yahoo.co.in", "rediffmail.com"]
FAKE_PHONES = ["9999999999", "1234567890", "0000000000", "9876543210", "1111111111", "98765"]
JUNK_NAMES = ["asdf", "test", "abc", "xyz", "qwerty", "aaa"]
JUNK_EMAILS = ["test@test.com", "abc@abc.com", "asdf@mailinator.com", "x@yopmail.com", "fake@guerrillamail.com"]
BROKER_MESSAGES = [
    "I am a channel partner with 50+ clients. Share your inventory and commission structure.",
    "Broker here. Do you have resale units? Need best price for my buyers, what is the brokerage?",
]
SPAM_MESSAGES = [
    "Get 10x leads with our SEO services! Visit http://cheap-seo.example now",
    "Earn money from home, call now http://quick-cash.example",
]
GENUINE_MESSAGES = [
    "Please call me after 6 pm. Is the price negotiable?",
    "Interested in a site visit this weekend.",
    "Looking to move in within 3 months. Need a home loan too.",
    "",
]
CHAT_MESSAGES = {
    "en": ["{bhk}BHK under {budget}L in {city}?", "Is it ready to move?", "Need a home loan, moving in 3 months"],
    "hinglish": ["{city} mein {budget} lakh tak {bhk}BHK chahiye", "Possession kab tak milega?", "Loan chahiye, 6 mahine mein shift karna hai"],
}


class Session:
    """One simulated visit, built up event by event on a millisecond clock that starts at 0."""

    def __init__(self, rng: random.Random, label: str, kind: str, mobile: bool, user_agent: str, ip: str, context: dict):
        self.rng, self.label, self.kind = rng, label, kind
        self.visitor_id, self.session_id = str(uuid.uuid4()), str(uuid.uuid4())
        self.mobile, self.user_agent, self.ip, self.context = mobile, user_agent, ip, context
        self.clock = 0
        self.events: list[dict] = []
        self.lead: dict | None = None
        self.chat: list[str] = []

    def add(self, type_: str, path: str, props: dict | None = None, ts: int | None = None) -> None:
        self.events.append({"type": type_, "ts": self.clock if ts is None else ts, "path": path,
                            "url": f"http://localhost:5173{path}", "title": "LeadOps Realty (demo)", "props": props or {}})

    def wait(self, low_s: float, high_s: float) -> None:
        self.clock += int(self.rng.uniform(low_s, high_s) * 1000)

    def browse(self, path: str, dwell_s: float, *, human: bool, extra=None) -> None:
        """A page view, what happens on the page, then leaving it."""
        start, dwell, max_scroll = self.clock, int(dwell_s * 1000), 0
        self.add("page_view", path, {"referrer": None})
        if human:
            if extra:  # custom events (EMI, floor plan, ...) part-way through the visit
                self.clock = start + int(dwell * 0.6)
                extra(path)
                dwell = max(dwell, self.clock - start + 2000)  # stay until whatever happened on the page is done
            for mark in (25, 50, 75, 100):  # people scroll deeper step by step, and often stop early
                if self.rng.random() > 0.8:
                    break
                self.add("scroll_depth", path, {"percent": mark}, ts=start + int(dwell * mark / 130))
                max_scroll = mark
            ticks = list(range(start + 10_000, start + dwell + 1, 10_000)) or [start + max(dwell - 500, 1)]
            for tick in ticks:  # the SDK sends an activity summary every 10 s
                moves = 0 if self.mobile else self.rng.randint(15, 180)
                self.add("activity", path, {"interval_ms": 10_000, "mouse_moves": moves, "mouse_distance": moves * self.rng.randint(8, 30),
                                            "clicks": self.rng.randint(0, 2), "touches": self.rng.randint(2, 15) if self.mobile else 0,
                                            "keys": 0, "scrolls": self.rng.randint(2, 25)}, ts=tick)
        self.clock = start + dwell
        self.add("page_leave", path, {"duration_ms": dwell, "max_scroll_pct": max_scroll, "reason": "navigate"})

    def record(self) -> dict:
        return {"label": self.label, "kind": self.kind, "visitor_id": self.visitor_id, "session_id": self.session_id,
                "ip": self.ip, "user_agent": self.user_agent, "context": self.context, "events": self.events,
                "lead": self.lead, "chat": self.chat}


# ---------------------------------------------------------------- building blocks


def human_context(rng: random.Random, mobile: bool) -> dict:
    screen = rng.choice(["390x844", "412x915", "360x800"]) if mobile else rng.choice(["1920x1080", "1366x768", "1536x864", "1440x900"])
    return {"user_agent": None, "language": "en-IN", "languages": rng.randint(2, 4), "timezone": "Asia/Kolkata",
            "screen": screen, "viewport": screen, "pixel_ratio": 3 if mobile else 1, "touch_points": 5 if mobile else 0,
            "hardware_concurrency": rng.choice([4, 8, 12, 16]), "webdriver": False, "referrer": rng.choice([None, "https://www.google.com/"]), "utm": {}}


def bot_context(rng: random.Random) -> dict:
    return {"user_agent": None, "language": "en-US", "languages": rng.choice([0, 1]), "timezone": rng.choice(["UTC", "America/New_York"]),
            "screen": "800x600", "viewport": "800x600", "pixel_ratio": 1, "touch_points": 0,
            "hardware_concurrency": rng.choice([1, 2]), "webdriver": rng.random() < 0.7, "referrer": None, "utm": {}}


def human_ip(rng: random.Random) -> str:
    # Documentation ranges (RFC 5737): realistic-looking, never real people's addresses.
    return f"{rng.choice(['198.51.100', '203.0.113'])}.{rng.randint(1, 254)}"


BOT_IPS = [f"192.0.2.{n}" for n in (7, 8, 9, 23, 41)]  # a few addresses, reused heavily: a classic bot signal


def phone(rng: random.Random) -> str:
    return str(rng.choice([6, 7, 8, 9])) + "".join(str(rng.randint(0, 9)) for _ in range(9))


def person(rng: random.Random) -> tuple[str, str]:
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    return f"{first} {last}", f"{first.lower()}.{last.lower()}{rng.randint(1, 99)}@{rng.choice(EMAIL_DOMAINS)}"


def lead(session: Session, listing_id: str | None, *, name: str, phone_number: str, email: str | None,
         message: str, fill_ms: int, honeypot: str | None = None, with_ids: bool = True) -> None:
    session.lead = {"visitor_id": session.visitor_id if with_ids else None, "session_id": session.session_id if with_ids else None,
                    "listing_id": listing_id, "name": name, "phone": phone_number, "email": email, "message": message or None,
                    "consent": True, "honeypot": honeypot, "form_fill_ms": fill_ms, "client_ts": session.clock}


def pick_search(rng: random.Random) -> tuple[str, int, int]:
    """A genuine buyer's search: a city, a BHK and a budget that fits at least one home there."""
    home = rng.choice(LISTINGS)
    return home["city"], home["bhk"], int(home["price_inr"] * rng.uniform(1.0, 1.15))


def homes_for(city: str, bhk: int, budget: int) -> list[dict]:
    matches = [h for h in LISTINGS if h["city"] == city and abs(h["bhk"] - bhk) <= 1 and h["price_inr"] <= budget * 1.1]
    return matches or [h for h in LISTINGS if h["city"] == city]


# ---------------------------------------------------------------- session kinds


def make_bot(rng: random.Random) -> Session:
    kind = rng.choices(["scraper", "form_bot", "click_bot"], weights=[5, 3, 2])[0]
    ua = rng.choice(UA_BOT) if rng.random() < 0.6 else rng.choice(UA_DESKTOP)  # some bots copy a real browser's UA
    s = Session(rng, "bot", kind, False, ua, rng.choice(BOT_IPS), bot_context(rng))
    if kind == "scraper":
        s.browse("/", rng.uniform(0.2, 1.0), human=False)
        for home in rng.sample(LISTINGS, rng.randint(8, 18)):
            s.wait(0.1, 0.8)
            s.browse(f"/property/{home['id']}", rng.uniform(0.2, 1.2), human=False)
    elif kind == "form_bot":
        home = rng.choice(LISTINGS)
        posted_directly = rng.random() < 0.4  # skips the site: calls the API with no visitor ID at all
        if not posted_directly:
            s.browse(f"/property/{home['id']}", rng.uniform(0.3, 1.5), human=False)
        name = rng.choice(JUNK_NAMES + [person(rng)[0]])
        lead(s, home["id"], name=name, phone_number=rng.choice(FAKE_PHONES + [phone(rng)]), email=rng.choice(JUNK_EMAILS),
             message=rng.choice(SPAM_MESSAGES + [""]), fill_ms=rng.randint(0, 1500),
             honeypot="http://promo.example" if rng.random() < 0.7 else None, with_ids=not posted_directly)
    else:  # click_bot: the same scripted click every few seconds
        interval = rng.uniform(2, 4)
        for home in rng.sample(LISTINGS, rng.randint(3, 6)):
            path = f"/property/{home['id']}"
            s.add("page_view", path)
            s.clock += int(interval * 1000)
            s.add("click", path, {"tag": "button", "trusted": False, "text": "Download floor plan"})
            s.clock += int(interval * 1000)
    return s


def make_junk(rng: random.Random) -> Session:
    kind = rng.choices(["fake_details", "broker", "spam"], weights=[5, 3, 2])[0]
    mobile = rng.random() < 0.6
    s = Session(rng, "junk", kind, mobile, rng.choice(UA_MOBILE if mobile else UA_DESKTOP), human_ip(rng), human_context(rng, mobile))
    home = rng.choice(LISTINGS)
    if kind == "broker":  # looks at many homes across cities, then fishes for inventory
        for other in rng.sample(LISTINGS, rng.randint(6, 12)):
            s.browse(f"/property/{other['id']}", rng.uniform(5, 20), human=True)
            s.wait(1, 4)
        name, email = person(rng)
        lead(s, home["id"], name=name, phone_number=phone(rng), email=email, message=rng.choice(BROKER_MESSAGES), fill_ms=rng.randint(15_000, 60_000))
    elif kind == "spam":
        s.browse(f"/property/{home['id']}", rng.uniform(3, 10), human=True)
        lead(s, home["id"], name=person(rng)[0], phone_number=phone(rng), email=rng.choice(JUNK_EMAILS),
             message=rng.choice(SPAM_MESSAGES), fill_ms=rng.randint(4_000, 15_000))
    else:  # fake_details: a person, but not a real enquiry
        s.browse("/", rng.uniform(4, 15), human=True)
        s.browse(f"/property/{home['id']}", rng.uniform(8, 30), human=True)
        lead(s, home["id"], name=rng.choice(JUNK_NAMES), phone_number=rng.choice(FAKE_PHONES), email=rng.choice(JUNK_EMAILS),
             message="", fill_ms=rng.randint(5_000, 20_000))
    return s


def make_genuine(rng: random.Random) -> Session:
    kind = rng.choices(["serious", "casual"], weights=[3, 2])[0]
    mobile = rng.random() < 0.6
    s = Session(rng, "genuine", kind, mobile, rng.choice(UA_MOBILE if mobile else UA_DESKTOP), human_ip(rng), human_context(rng, mobile))
    city, bhk, budget = pick_search(rng)
    homes = homes_for(city, bhk, budget)

    def use_filters(path: str) -> None:
        s.add("filter_used", path, {"city": city, "bhk": bhk, "max_price": None})

    s.browse("/", rng.uniform(10, 40), human=True, extra=use_filters)
    if kind == "casual":
        for home in rng.sample(homes, min(len(homes), rng.randint(1, 2))):
            s.wait(1, 5)
            s.browse(f"/property/{home['id']}", rng.uniform(8, 45), human=True,
                     extra=lambda path, home=home: s.add("property_view", path, {"listing_id": home["id"], "city": home["city"], "bhk": home["bhk"], "price_inr": home["price_inr"]}))
        if rng.random() < 0.1:
            name, email = person(rng)
            lead(s, homes[0]["id"], name=name, phone_number=phone(rng), email=email, message="", fill_ms=rng.randint(20_000, 70_000))
        return s

    chosen = None
    for home in rng.sample(homes, min(len(homes), rng.randint(2, 4))):
        chosen = home
        s.wait(2, 8)

        def on_property(path: str, home=home) -> None:
            s.add("property_view", path, {"listing_id": home["id"], "city": home["city"], "bhk": home["bhk"], "price_inr": home["price_inr"]})
            if rng.random() < 0.7:
                s.wait(5, 20)
                s.add("emi_used", path, {"listing_id": home["id"], "price_inr": home["price_inr"], "down_payment_pct": rng.choice([10, 20, 25, 30]),
                                         "rate_pct": rng.choice([8.25, 8.5, 8.75, 9.0]), "years": rng.choice([15, 20, 25]), "emi": int(home["price_inr"] * 0.0068)})
            if rng.random() < 0.6:
                s.wait(2, 10)
                s.add("click", path, {"tag": "button", "trusted": True, "text": "Download floor plan"})
                s.add("floorplan_download", path, {"listing_id": home["id"], "bhk": home["bhk"]})

        s.browse(f"/property/{home['id']}", rng.uniform(40, 180), human=True, extra=on_property)

    if rng.random() < 0.4:
        style = rng.choice(["en", "hinglish"])
        templates = CHAT_MESSAGES[style]
        s.chat = [templates[0].format(bhk=bhk, budget=budget // 100_000, city=city), rng.choice(templates[1:])]
    if rng.random() < 0.75:
        name, email = person(rng)
        s.wait(5, 20)
        lead(s, chosen["id"], name=name, phone_number=phone(rng), email=email if rng.random() < 0.7 else None,
             message=rng.choice(GENUINE_MESSAGES), fill_ms=rng.randint(25_000, 120_000))
    return s


# ---------------------------------------------------------------- output


def place_in_time(session: Session, end_ms: int) -> None:
    """Put events in time order and turn the 0-based clock into real timestamps that end at end_ms."""
    session.events.sort(key=lambda event: event["ts"])
    offset = end_ms - max([session.clock, *(event["ts"] for event in session.events)])
    for event in session.events:
        event["ts"] += offset
    if session.lead:
        session.lead["client_ts"] += offset


def post(url: str, payload: dict, *, user_agent: str, ip: str, as_text: bool = False) -> None:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "text/plain" if as_text else "application/json",  # the SDK sends events as text/plain
            "User-Agent": user_agent,
            "X-Forwarded-For": ip,  # the backend reads the client IP from this header, as it does behind a proxy
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def send(session: Session, api: str, *, include_chat: bool) -> None:
    context = {**session.context, "user_agent": session.user_agent}
    for start in range(0, len(session.events), 50):
        batch = {"visitor_id": session.visitor_id, "session_id": session.session_id, "site": SITE, "sdk_version": "simulator",
                 "sent_at": int(time.time() * 1000), "context": context, "events": session.events[start : start + 50]}
        post(f"{api}/events", batch, user_agent=session.user_agent, ip=session.ip, as_text=True)
    if include_chat:
        for message in session.chat:
            post(f"{api}/chat", {"visitor_id": session.visitor_id, "session_id": session.session_id, "message": message},
                 user_agent=session.user_agent, ip=session.ip)
    if session.lead:
        post(f"{api}/leads", session.lead, user_agent=session.user_agent, ip=session.ip)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate labelled bot / junk / genuine sessions for LeadOps.")
    parser.add_argument("--bots", type=int, default=200)
    parser.add_argument("--junk", type=int, default=100)
    parser.add_argument("--genuine", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42, help="same seed, same sessions")
    parser.add_argument("--out", default=str(ROOT / "ml" / "data" / "sessions.jsonl"), help="JSONL file to write")
    parser.add_argument("--send", metavar="API_URL", help="also send the sessions to a running backend, e.g. http://localhost:8000")
    parser.add_argument("--chat", action="store_true", help="with --send, also send chat messages (may call the backend's LLM)")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    makers = [make_bot] * args.bots + [make_junk] * args.junk + [make_genuine] * args.genuine
    rng.shuffle(makers)
    sessions = [maker(rng) for maker in makers]

    now_ms = int(time.time() * 1000)
    for session in sessions:
        # Sent sessions end within the last minute (they look live); file-only sessions spread over a week.
        spread = 60_000 if args.send else 7 * 24 * 3600 * 1000
        place_in_time(session, now_ms - rng.randint(0, spread))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as file:
        for session in sessions:
            file.write(json.dumps(session.record(), ensure_ascii=False) + "\n")
    counts = {label: sum(s.label == label for s in sessions) for label in ("bot", "junk", "genuine")}
    print(f"Wrote {len(sessions)} sessions to {out} ({counts['bot']} bot, {counts['junk']} junk, {counts['genuine']} genuine)")

    if args.send:
        api = args.send.rstrip("/")
        try:
            for session in sessions:
                send(session, api, include_chat=args.chat)
        except (urllib.error.URLError, TimeoutError) as error:
            print(f"Couldn't send to {api}: {error}. Is the backend running? (cd backend; uvicorn app.main:app)", file=sys.stderr)
            return 1
        print(f"Sent them to {api}. Watch them on the dashboard: http://localhost:5173/dashboard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
