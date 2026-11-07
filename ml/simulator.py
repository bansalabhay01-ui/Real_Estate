"""Synthetic LeadOps traffic: labelled bot, junk and genuine visitors (Python standard library only).

Writes one visitor per line (JSONL) for training, and can also send the visitors to a running backend so they show
up live on the dashboard. Events have the same shape the tracking SDK sends (docs/CONTRACTS.md), and every line is
a *visitor record* (backend/app/scoring/features.py), so training and live scoring read the same thing.

    python ml/simulator.py                                    # 200 bot, 100 junk, 200 genuine -> ml/data/sessions.jsonl
    python ml/simulator.py --bots 20 --junk 10 --genuine 20 --out ml/data/small.jsonl
    python ml/simulator.py --send http://localhost:8000 --bots 5 --junk 3 --genuine 4
    python ml/simulator.py --send http://localhost:8000 --report --seed 7   # send, then print how each kind was labelled

Labels and kinds:
    bot      scraper (opens many pages in seconds), slow_scraper (a few seconds per page and no mouse at all),
             form_bot (enquiry with little or no browsing, often fills the honeypot), click_bot (scripted clicks
             at fixed intervals), stealth_form (hides webdriver, copies a real browser, fakes mouse moves and typing)
    junk     fake_details (real browsing, fake phone/email), broker (rival broker fishing for inventory),
             spam (promotional message)
    genuine  serious (focused search, EMI, floor plan, enquiry; often comes back on later days), casual (a short
             look, rarely an enquiry). Some genuine buyers are NRIs (foreign time zone and number), use browser
             autofill (a 1-3 second form), a privacy browser (UTC time zone) or an ad blocker (no tracking at all).

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
DAY_MS = 86_400_000

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
BROKER_CHAT = ["Do you have inventory for my clients in {city}?", "What is the commission structure for channel partners?"]
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
STEALTH_MESSAGES = ["Interested, please call me.", "Please share the price list.", "Need more details about this project."]
CHAT_MESSAGES = {
    "en": ["{bhk}BHK under {budget}L in {city}?", "Is it ready to move?", "Need a home loan, moving in 3 months"],
    "hinglish": ["{city} mein {budget} lakh tak {bhk}BHK chahiye", "Possession kab tak milega?", "Loan chahiye, 6 mahine mein shift karna hai"],
}
NRI_ZONES = ["Asia/Dubai", "America/New_York", "Europe/London", "Asia/Singapore", "America/Los_Angeles", "Australia/Sydney"]

# IP addresses come from ranges reserved for documentation and testing (RFC 5737, RFC 2544), never real people's.
BOT_IPS = [f"192.0.2.{n}" for n in (7, 8, 9, 23, 41)]  # a few addresses reused heavily by bots
SHARED_IPS = [f"203.0.113.{n}" for n in range(10, 18)]  # college, office and mobile-network addresses many people share


def own_ip(rng: random.Random) -> str:
    """One person's own connection."""
    return f"198.{rng.choice([18, 19])}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


def human_ip(rng: random.Random) -> str:
    """30% of people browse from an address shared with many others (college, office, mobile network)."""
    return rng.choice(SHARED_IPS) if rng.random() < 0.3 else own_ip(rng)


def proxy_ip(rng: random.Random) -> str:
    """Rotating proxies, which stealth bots use so no address repeats."""
    return f"198.51.100.{rng.randint(1, 254)}"


class Visitor:
    """One browser: a label, its context and one or more visits."""

    def __init__(self, rng: random.Random, label: str, kind: str, *, user_agent: str, context: dict, mobile: bool = False):
        self.rng, self.label, self.kind = rng, label, kind
        self.visitor_id = str(uuid.uuid4())
        self.user_agent, self.context, self.mobile = user_agent, context, mobile
        self.visits: list[Visit] = []

    def visit(self, ip: str) -> "Visit":
        visit = Visit(self, ip)
        self.visits.append(visit)
        return visit

    def place(self, end_ms: int) -> None:
        """Put the visits in real time: the last one ends at end_ms, earlier ones hours or days before it."""
        target = end_ms
        for visit in reversed(self.visits):
            visit.events.sort(key=lambda event: event["ts"])
            last = max([visit.clock, *(event["ts"] for event in visit.events)])
            offset = target - last
            for event in visit.events:
                event["ts"] += offset
            for lead in visit.leads:
                lead["client_ts"] += offset
            for message in visit.chat:
                message["ts"] += offset
            target = offset - int(self.rng.uniform(0.3, 3.0) * DAY_MS)  # the visit before ended earlier

    def record(self) -> dict:
        return {
            "label": self.label, "kind": self.kind, "visitor_id": self.visitor_id, "user_agent": self.user_agent,
            "context": self.context,
            "sessions": [{"session_id": v.session_id, "ip": v.ip, "events": v.events} for v in self.visits if v.events],
            "leads": [lead for v in self.visits for lead in v.leads],
            "chat": [message for v in self.visits for message in v.chat],
        }  # fmt: skip


class Visit:
    """One visit (session), built event by event on its own millisecond clock that starts at 0."""

    def __init__(self, visitor: Visitor, ip: str):
        self.visitor, self.rng, self.ip = visitor, visitor.rng, ip
        self.session_id = str(uuid.uuid4())
        self.clock = 0
        self.events: list[dict] = []
        self.leads: list[dict] = []
        self.chat: list[dict] = []

    def add(self, type_: str, path: str, props: dict | None = None, ts: int | None = None) -> None:
        self.events.append({"type": type_, "ts": self.clock if ts is None else ts, "path": path,
                            "url": f"http://localhost:5173{path}", "title": "LeadOps Realty (demo)", "props": props or {}})

    def wait(self, low_s: float, high_s: float) -> None:
        self.clock += int(self.rng.uniform(low_s, high_s) * 1000)

    def activity(self, path: str, ts: int, interval_ms: int, *, keys: int = 0, synthetic: bool = False) -> None:
        """The SDK's 10-second activity summary."""
        rng = self.rng
        if synthetic:  # a script faking a person: a few big mouse jumps, one click, a wheel turn
            moves = rng.randint(4, 12)
            props = {"mouse_moves": moves, "mouse_distance": int(moves * rng.uniform(60, 220)), "clicks": 1,
                     "touches": 0, "scrolls": rng.randint(1, 3)}
        elif self.visitor.mobile:
            props = {"mouse_moves": 0, "mouse_distance": 0, "clicks": 0,
                     "touches": max(1, int(rng.lognormvariate(2.0, 0.6))), "scrolls": rng.randint(3, 60)}
        else:
            moves = min(900, max(5, int(rng.lognormvariate(4.3, 0.7))))
            props = {"mouse_moves": moves, "mouse_distance": int(moves * rng.uniform(4, 22)),
                     "clicks": rng.choice([0, 0, 0, 1, 1, 2]), "touches": 0, "scrolls": int(rng.expovariate(1 / 12))}
        self.add("activity", path, {"interval_ms": interval_ms, **props, "keys": keys}, ts=ts)

    def human_page(self, path: str, dwell_s: float, extra=None) -> None:
        """A person on a page: scrolls step by step, moves the mouse or touches, now and then pauses."""
        start, dwell, max_scroll = self.clock, int(dwell_s * 1000), 0
        self.add("page_view", path, {"referrer": None})
        if extra:  # custom events (EMI, floor plan, ...) part-way through the visit
            self.clock = start + int(dwell * 0.6)
            extra(path)
            dwell = max(dwell, self.clock - start + 2000)  # stay until whatever happened on the page is done
        for mark in (25, 50, 75, 100):  # people scroll deeper step by step, and often stop early
            if self.rng.random() > 0.8:
                break
            self.add("scroll_depth", path, {"percent": mark}, ts=start + int(dwell * mark / 130))
            max_scroll = mark
        idle = 0.15  # share of 10-second windows with nothing at all (reading, thinking)
        for tick in range(start + 10_000, start + dwell + 1, 10_000):
            if self.rng.random() > idle:
                self.activity(path, tick, 10_000)
        if dwell % 10_000 > 1000:  # the SDK also sends what happened since the last summary when the page changes
            self.activity(path, start + dwell, dwell % 10_000)
        self.clock = start + dwell
        self.add("page_leave", path, {"duration_ms": dwell, "max_scroll_pct": max_scroll, "reason": "navigate"})

    def robot_page(self, path: str, dwell_s: float, *, scroll: bool = False, synthetic: bool = False) -> None:
        """A script on a page: no mouse or touch at all (or fake moves), at most one scroll straight to the bottom."""
        start, dwell, max_scroll = self.clock, max(50, int(dwell_s * 1000)), 0
        self.add("page_view", path, {"referrer": None})
        if scroll:
            for step, mark in enumerate((25, 50, 75, 100)):
                self.add("scroll_depth", path, {"percent": mark}, ts=start + 300 + step * 5)
            max_scroll = 100
        if synthetic:
            for tick in range(start + 10_000, start + dwell + 1, 10_000):
                self.activity(path, tick, 10_000, synthetic=True)
            if dwell % 10_000 > 500:
                self.activity(path, start + dwell, dwell % 10_000, synthetic=True)
        self.clock = start + dwell
        self.add("page_leave", path, {"duration_ms": dwell, "max_scroll_pct": max_scroll, "reason": "navigate"})

    def submit(self, path: str | None, listing_id: str, *, name: str, phone_number: str, email: str | None,
               message: str, fill_ms: int, keys: int = 0, honeypot: str | None = None, direct: bool = False,
               hands: str = "human") -> None:
        """Send the enquiry form. direct=True posts it to the API without the site (no visitor ID, no events).
        hands: "human" (real mouse or touch while typing), "script" (fake moves and typing) or "none" (a script
        that fills the fields in directly)."""
        start = self.clock
        self.clock += fill_ms
        if not direct and path and hands != "none":  # typing shows up in the 10-second activity summaries
            ticks = max(1, fill_ms // 10_000)
            for tick in range(ticks):
                share = keys // ticks + (keys % ticks if tick == ticks - 1 else 0)
                self.activity(path, start + min(fill_ms, (tick + 1) * 10_000), min(fill_ms, 10_000), keys=share,
                              synthetic=hands == "script")
        self.leads.append({
            "visitor_id": None if direct else self.visitor.visitor_id, "session_id": None if direct else self.session_id,
            "listing_id": listing_id, "name": name, "phone": phone_number, "email": email, "message": message or None,
            "consent": True, "honeypot": honeypot, "form_fill_ms": fill_ms, "client_ts": self.clock, "ip": self.ip,
        })  # fmt: skip
        if not direct and path:
            self.add("enquiry_submitted", path, {"listing_id": listing_id})

    def say(self, text: str) -> None:
        """A message to the property assistant."""
        self.wait(5, 25)
        self.chat.append({"session_id": self.session_id, "text": text, "ts": self.clock})
        self.add("chat_message", self.events[-1]["path"] if self.events else "/", {"length": len(text)})


# ---------------------------------------------------------------- building blocks


def human_context(rng: random.Random, mobile: bool, *, nri: bool = False, privacy: bool = False) -> dict:
    if mobile:
        width, height = rng.choice([(390, 844), (412, 915), (360, 800), (393, 873)])
        viewport = (width, height - rng.randint(90, 170))  # the address bar takes some height
    else:
        width, height = rng.choice([(1920, 1080), (1366, 768), (1536, 864), (1440, 900), (2560, 1440)])
        viewport = (width - rng.choice([0, 0, 0, 15, 17]), height - rng.randint(110, 200))  # tabs, toolbar, taskbar
    context = {
        "user_agent": None, "language": rng.choice(["en-US", "en-GB"]) if nri else "en-IN",
        "languages": rng.choice([1, 2, 2, 3, 3, 4]), "timezone": rng.choice(NRI_ZONES) if nri else "Asia/Kolkata",
        "screen": f"{width}x{height}", "viewport": f"{viewport[0]}x{viewport[1]}",
        "pixel_ratio": 3 if mobile else rng.choice([1, 1.25, 1.5, 2]), "touch_points": 5 if mobile else 0,
        "hardware_concurrency": rng.choice([6, 8]) if mobile else rng.choice([4, 8, 12, 16]), "webdriver": False,
        "referrer": rng.choice([None, "https://www.google.com/", "https://www.instagram.com/"]), "utm": {},
    }  # fmt: skip
    if privacy:  # fingerprinting protection (Firefox, Tor Browser): UTC, 2 cores, a window-sized screen
        context.update(timezone="UTC", hardware_concurrency=2, languages=1, screen=context["viewport"])
    elif not mobile and rng.random() < 0.05:  # full-screen browsing (F11) or a kiosk: the window fills the screen
        context["viewport"] = context["screen"]
    return context


def bot_context(rng: random.Random) -> dict:
    """A headless browser with its default settings."""
    size = rng.choice(["800x600", "1280x720"])
    return {"user_agent": None, "language": "en-US", "languages": rng.choice([0, 1]),
            "timezone": rng.choice(["UTC", "UTC", "America/New_York", "Asia/Kolkata"]), "screen": size, "viewport": size,
            "pixel_ratio": 1, "touch_points": 0, "hardware_concurrency": rng.choice([1, 2, 4]),
            "webdriver": rng.random() < 0.7, "referrer": None, "utm": {}}


def stealth_context(rng: random.Random) -> dict:
    """A bot copying a real Indian desktop browser; it often keeps Playwright's window-equals-screen default."""
    context = human_context(rng, False)
    if rng.random() < 0.5:
        context["viewport"] = context["screen"]
    context.update(languages=2, hardware_concurrency=rng.choice([4, 8]))
    return context


def digits(rng: random.Random, count: int) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(count))


def phone(rng: random.Random) -> str:
    return str(rng.choice([6, 7, 8, 9])) + digits(rng, 9)


def intl_phone(rng: random.Random) -> str:
    """An NRI buyer's number: UAE, US, UK or Singapore."""
    return rng.choice([
        lambda: "+971 5" + digits(rng, 8),
        lambda: "+1 " + str(rng.randint(2, 9)) + digits(rng, 9),
        lambda: "+44 7" + digits(rng, 9),
        lambda: "+65 " + rng.choice("89") + digits(rng, 7),
    ])()  # fmt: skip


def person(rng: random.Random) -> tuple[str, str]:
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    return f"{first} {last}", f"{first.lower()}.{last.lower()}{rng.randint(1, 99)}@{rng.choice(EMAIL_DOMAINS)}"


def typed_keys(rng: random.Random, *texts: str | None) -> int:
    """Key presses to type these fields, plus a few corrections."""
    return sum(len(text or "") for text in texts) + rng.randint(0, 12)


def pick_search(rng: random.Random) -> tuple[str, int, int]:
    """A genuine buyer's search: a city, a BHK and a budget that fits at least one home there."""
    home = rng.choice(LISTINGS)
    return home["city"], home["bhk"], int(home["price_inr"] * rng.uniform(1.0, 1.15))


def homes_for(city: str, bhk: int, budget: int) -> list[dict]:
    matches = [h for h in LISTINGS if h["city"] == city and abs(h["bhk"] - bhk) <= 1 and h["price_inr"] <= budget * 1.1]
    return matches or [h for h in LISTINGS if h["city"] == city]


def view_props(home: dict) -> dict:
    return {"listing_id": home["id"], "city": home["city"], "bhk": home["bhk"], "price_inr": home["price_inr"]}


# ---------------------------------------------------------------- bots


def make_bot(rng: random.Random) -> Visitor:
    kind = rng.choices(["scraper", "slow_scraper", "form_bot", "click_bot", "stealth_form"], weights=[4, 2, 3, 1, 3])[0]
    if kind == "stealth_form":
        return make_stealth_bot(rng)
    if kind == "slow_scraper":  # rate-limited to look human: a few seconds per page, but never a mouse move
        ua = rng.choice(UA_DESKTOP) if rng.random() < 0.7 else rng.choice(UA_BOT)
        context = stealth_context(rng) if rng.random() < 0.5 else bot_context(rng)
        visitor = Visitor(rng, "bot", kind, user_agent=ua, context=context)
        visit = visitor.visit(rng.choice(BOT_IPS) if rng.random() < 0.5 else proxy_ip(rng))
        scroll = rng.random() < 0.5
        for home in rng.sample(LISTINGS, rng.randint(10, 18)):
            visit.robot_page(f"/property/{home['id']}", rng.uniform(2.5, 6.0), scroll=scroll)
            visit.wait(0.3, 0.6)
        return visitor

    ua = rng.choice(UA_BOT) if rng.random() < 0.6 else rng.choice(UA_DESKTOP)  # some bots copy a real browser's UA
    visitor = Visitor(rng, "bot", kind, user_agent=ua, context=bot_context(rng))
    visit = visitor.visit(rng.choice(BOT_IPS) if rng.random() < 0.6 else proxy_ip(rng))
    if kind == "scraper":
        visit.robot_page("/", rng.uniform(0.2, 1.0))
        scroll = rng.random() < 0.3
        for home in rng.sample(LISTINGS, rng.randint(8, 18)):
            visit.wait(0.1, 0.8)
            visit.robot_page(f"/property/{home['id']}", rng.uniform(0.2, 1.2), scroll=scroll)
    elif kind == "form_bot":
        home = rng.choice(LISTINGS)
        direct = rng.random() < 0.4  # skips the site: calls the API with no visitor ID at all
        path = None if direct else f"/property/{home['id']}"
        if path:
            visit.robot_page(path, rng.uniform(0.3, 1.5))
        visit.submit(path, home["id"], name=rng.choice(JUNK_NAMES + [person(rng)[0]]),
                     phone_number=rng.choice(FAKE_PHONES + [phone(rng)]), email=rng.choice(JUNK_EMAILS),
                     message=rng.choice(SPAM_MESSAGES + [""]), fill_ms=rng.randint(0, 1500),
                     honeypot="http://promo.example" if rng.random() < 0.7 else None, direct=direct, hands="none")
    else:  # click_bot: the same scripted click every few seconds
        interval = rng.uniform(2, 4)
        for home in rng.sample(LISTINGS, rng.randint(3, 6)):
            path, start = f"/property/{home['id']}", visit.clock
            visit.add("page_view", path)
            visit.clock += int(interval * 1000)
            visit.add("click", path, {"tag": "button", "trusted": False, "text": "Download floor plan"})
            visit.clock += int(interval * 1000)
            visit.add("page_leave", path, {"duration_ms": visit.clock - start, "max_scroll_pct": 0, "reason": "navigate"})
    return visitor


def make_stealth_bot(rng: random.Random) -> Visitor:
    """Hides webdriver, copies a real browser, moves the mouse and types: only its behaviour gives it away."""
    visitor = Visitor(rng, "bot", "stealth_form", user_agent=rng.choice(UA_DESKTOP), context=stealth_context(rng))
    visit = visitor.visit(proxy_ip(rng) if rng.random() < 0.7 else rng.choice(BOT_IPS))
    homes = rng.sample(LISTINGS, rng.randint(1, 3))
    for home in homes:
        visit.robot_page(f"/property/{home['id']}", rng.uniform(5, 15), scroll=rng.random() < 0.6, synthetic=True)
        visit.wait(0.8, 1.6)
    if rng.random() < 0.5:  # believable details
        name, email = person(rng)
        number, message = phone(rng), rng.choice(STEALTH_MESSAGES)
    else:
        name = rng.choice(JUNK_NAMES + [person(rng)[0]])
        number, email = rng.choice(FAKE_PHONES + [phone(rng)]), rng.choice(JUNK_EMAILS + [person(rng)[1]])
        message = rng.choice(SPAM_MESSAGES + STEALTH_MESSAGES)
    path = f"/property/{homes[-1]['id']}"
    visit.submit(path, homes[-1]["id"], name=name, phone_number=number, email=email, message=message,
                 fill_ms=rng.randint(2_000, 8_000), keys=len(name) + len(number) + len(email or ""), hands="script")
    return visitor


# ---------------------------------------------------------------- junk


def make_junk(rng: random.Random) -> Visitor:
    kind = rng.choices(["fake_details", "broker", "spam"], weights=[5, 3, 2])[0]
    mobile = rng.random() < 0.6
    ua = rng.choice(UA_MOBILE if mobile else UA_DESKTOP)
    visitor = Visitor(rng, "junk", kind, user_agent=ua, context=human_context(rng, mobile), mobile=mobile)
    home = rng.choice(LISTINGS)
    path = f"/property/{home['id']}"
    if kind == "broker":  # looks at many homes across cities, often comes back, then fishes for inventory
        for number in range(2 if rng.random() < 0.3 else 1):
            visit = visitor.visit(human_ip(rng))
            for other in rng.sample(LISTINGS, rng.randint(6, 12)):
                visit.human_page(f"/property/{other['id']}", rng.uniform(5, 20))
                visit.wait(1, 4)
            if number == 0 and rng.random() < 0.4:
                visit.say(rng.choice(BROKER_CHAT).format(city=home["city"]))
        name, email = person(rng)
        message = rng.choice(BROKER_MESSAGES)
        visit.human_page(path, rng.uniform(10, 30))
        visit.submit(path, home["id"], name=name, phone_number=phone(rng), email=email, message=message,
                     fill_ms=rng.randint(15_000, 60_000), keys=typed_keys(rng, name, email, message))
    elif kind == "spam":
        visit = visitor.visit(human_ip(rng))
        visit.human_page(path, rng.uniform(3, 10))
        message = rng.choice(SPAM_MESSAGES)
        visit.submit(path, home["id"], name=person(rng)[0], phone_number=phone(rng), email=rng.choice(JUNK_EMAILS),
                     message=message, fill_ms=rng.randint(4_000, 15_000), keys=typed_keys(rng, message))
    else:  # fake_details: a person, but not a real enquiry
        visit = visitor.visit(human_ip(rng))
        visit.human_page("/", rng.uniform(4, 15))
        visit.human_page(path, rng.uniform(8, 30))
        visit.submit(path, home["id"], name=rng.choice(JUNK_NAMES), phone_number=rng.choice(FAKE_PHONES),
                     email=rng.choice(JUNK_EMAILS), message="", fill_ms=rng.randint(5_000, 20_000), keys=rng.randint(8, 30))
    return visitor


# ---------------------------------------------------------------- genuine buyers


def make_genuine(rng: random.Random) -> Visitor:
    kind = rng.choices(["serious", "casual"], weights=[3, 2])[0]
    mobile, nri, privacy = rng.random() < 0.6, rng.random() < 0.08, rng.random() < 0.03
    ua = rng.choice(UA_MOBILE if mobile else UA_DESKTOP)
    visitor = Visitor(rng, "genuine", kind, user_agent=ua, context=human_context(rng, mobile, nri=nri, privacy=privacy),
                      mobile=mobile)
    city, bhk, budget = pick_search(rng)
    homes = homes_for(city, bhk, budget)
    ip = human_ip(rng)

    def contact() -> tuple[str, str, str | None]:
        name, email = person(rng)
        return name, intl_phone(rng) if nri else phone(rng), email if rng.random() < 0.7 else None

    def enquire(visit: Visit, home: dict, *, message: str) -> None:
        name, number, email = contact()
        visit.wait(5, 20)
        path = f"/property/{home['id']}"
        if rng.random() < 0.25:  # browser autofill: name, phone and email in one tap
            visit.submit(path, home["id"], name=name, phone_number=number, email=email, message=message,
                         fill_ms=rng.randint(1_200, 3_000), keys=rng.randint(0, 2))
        else:
            visit.submit(path, home["id"], name=name, phone_number=number, email=email, message=message,
                         fill_ms=rng.randint(20_000, 120_000), keys=typed_keys(rng, name, number, email, message))

    if rng.random() < 0.03:  # an ad blocker hides the tracking script: only the enquiry arrives
        visit = visitor.visit(ip)
        visit.clock = int(rng.uniform(60, 600) * 1000)
        name, number, email = contact()
        visit.submit(None, homes[0]["id"], name=name, phone_number=number, email=email,
                     message=rng.choice(GENUINE_MESSAGES), fill_ms=rng.randint(20_000, 90_000), direct=True)
        return visitor

    def use_filters(path: str) -> None:
        visit.add("filter_used", path, {"city": city, "bhk": bhk, "max_price": None})

    visit = visitor.visit(ip)
    visit.human_page("/", rng.uniform(10, 40), extra=use_filters)

    if kind == "casual":
        for home in rng.sample(homes, min(len(homes), rng.randint(1, 2))):
            visit.wait(1, 5)
            visit.human_page(f"/property/{home['id']}", rng.uniform(8, 45),
                             extra=lambda path, home=home: visit.add("property_view", path, view_props(home)))
        if rng.random() < 0.15:  # comes back once for another look
            visit = visitor.visit(ip if rng.random() < 0.5 else human_ip(rng))
            home = rng.choice(homes)
            visit.human_page(f"/property/{home['id']}", rng.uniform(10, 60),
                             extra=lambda path: visit.add("property_view", path, view_props(home)))
        if rng.random() < 0.1:
            enquire(visit, homes[0], message="")
        return visitor

    def on_property(path: str, home: dict, emi_chance: float, plan_chance: float) -> None:
        visit.add("property_view", path, view_props(home))
        if rng.random() < emi_chance:
            visit.wait(5, 20)
            visit.add("emi_used", path, {"listing_id": home["id"], "price_inr": home["price_inr"],
                                         "down_payment_pct": rng.choice([10, 20, 25, 30]), "rate_pct": rng.choice([8.25, 8.5, 8.75, 9.0]),
                                         "years": rng.choice([15, 20, 25]), "emi": int(home["price_inr"] * 0.0068)})
        if rng.random() < plan_chance:
            visit.wait(2, 10)
            visit.add("click", path, {"tag": "button", "trusted": True, "text": "Download floor plan"})
            visit.add("floorplan_download", path, {"listing_id": home["id"], "bhk": home["bhk"]})

    shortlist = rng.sample(homes, min(len(homes), rng.randint(2, 4)))
    for home in shortlist:
        visit.wait(2, 8)
        visit.human_page(f"/property/{home['id']}", rng.uniform(40, 180),
                         extra=lambda path, home=home: on_property(path, home, 0.7, 0.6))
    if rng.random() < 0.4:
        templates = CHAT_MESSAGES[rng.choice(["en", "hinglish"])]
        visit.say(templates[0].format(bhk=bhk, budget=budget // 100_000, city=city))
        visit.say(rng.choice(templates[1:]))

    if rng.random() < 0.55:  # comes back on later days to look at the shortlist again
        for _ in range(rng.randint(1, 3)):
            visit = visitor.visit(ip if rng.random() < 0.5 else human_ip(rng))
            for home in rng.sample(shortlist, min(len(shortlist), rng.randint(1, 2))):
                visit.wait(1, 6)
                visit.human_page(f"/property/{home['id']}", rng.uniform(30, 150),
                                 extra=lambda path, home=home: on_property(path, home, 0.4, 0.2))
    if rng.random() < 0.75:
        enquire(visit, shortlist[-1], message=rng.choice(GENUINE_MESSAGES))
    return visitor


# ---------------------------------------------------------------- output


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


def send(visitor: Visitor, api: str, *, include_chat: bool) -> None:
    context = {**visitor.context, "user_agent": visitor.user_agent}
    for visit in visitor.visits:
        for start in range(0, len(visit.events), 50):
            batch = {"visitor_id": visitor.visitor_id, "session_id": visit.session_id, "site": SITE,
                     "sdk_version": "simulator", "sent_at": int(time.time() * 1000), "context": context,
                     "events": visit.events[start : start + 50]}
            post(f"{api}/events", batch, user_agent=visitor.user_agent, ip=visit.ip, as_text=True)
        if include_chat:
            for message in visit.chat:
                post(f"{api}/chat", {"visitor_id": visitor.visitor_id, "session_id": visit.session_id, "message": message["text"]},
                     user_agent=visitor.user_agent, ip=visit.ip)
        for lead in visit.leads:
            payload = {key: value for key, value in lead.items() if key != "ip"}
            post(f"{api}/leads", payload, user_agent=visitor.user_agent, ip=lead["ip"])


def get_json(url: str):
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.loads(response.read())


def report(visitors: list[Visitor], api: str) -> None:
    """How the backend labelled each kind of simulated visitor: the quick end-to-end check."""
    labels: dict[str, str | None] = {}
    for offset in range(0, 100_000, 500):
        page = get_json(f"{api}/visitors?limit=500&offset={offset}")
        labels.update({item["id"]: item.get("label") for item in page})
        if len(page) < 500:
            break
    by_contact: dict[tuple, str] = {}  # enquiries posted straight to the API get a visitor ID from the backend
    for offset in range(0, 100_000, 500):
        page = get_json(f"{api}/leads?limit=500&offset={offset}")
        by_contact.update({(item["name"], item["phone"]): item["visitor_id"] for item in page})
        if len(page) < 500:
            break

    names = ["Bot", "Junk", "Review", "Cold", "Warm", "Hot"]
    table: dict[str, dict[str, int]] = {}
    for visitor in visitors:
        visitor_id = visitor.visitor_id
        if not any(visit.events for visit in visitor.visits):
            first = next((lead for visit in visitor.visits for lead in visit.leads), None)
            visitor_id = by_contact.get((first["name"], first["phone"])) if first else None
        label = labels.get(visitor_id) or "-"
        row = table.setdefault(f"{visitor.label}/{visitor.kind}", {})
        row[label] = row.get(label, 0) + 1

    print("\nHow the backend labelled them:")
    print(f"  {'':22}" + "".join(f"{name:>8}" for name in [*names, '-']))
    for kind in sorted(table):
        print(f"  {kind:22}" + "".join(f"{table[kind].get(name, 0):>8}" for name in [*names, "-"]))

    def share(prefix: str, good: set[str]) -> str:
        rows = [row for kind, row in table.items() if kind.startswith(prefix)]
        total = sum(sum(row.values()) for row in rows)
        hits = sum(count for row in rows for name, count in row.items() if name in good)
        return f"{hits}/{total}"

    print(f"  Bots filtered out (Bot or Junk): {share('bot', {'Bot', 'Junk'})}; junk filtered out: "
          f"{share('junk', {'Bot', 'Junk'})}; genuine buyers kept (not Bot or Junk): "
          f"{share('genuine', {'Review', 'Cold', 'Warm', 'Hot'})}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate labelled bot / junk / genuine visitors for LeadOps.")
    parser.add_argument("--bots", type=int, default=200)
    parser.add_argument("--junk", type=int, default=100)
    parser.add_argument("--genuine", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42, help="same seed, same visitors")
    parser.add_argument("--out", default=str(ROOT / "ml" / "data" / "sessions.jsonl"), help="JSONL file to write")
    parser.add_argument("--send", metavar="API_URL", help="also send the visitors to a running backend, e.g. http://localhost:8000")
    parser.add_argument("--chat", action="store_true", help="with --send, also send chat messages (may call the backend's LLM)")
    parser.add_argument("--report", action="store_true", help="with --send, print how the backend labelled each kind")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    makers = [make_bot] * args.bots + [make_junk] * args.junk + [make_genuine] * args.genuine
    rng.shuffle(makers)
    visitors = [maker(rng) for maker in makers]

    now_ms = int(time.time() * 1000)
    for visitor in visitors:
        # Sent visitors end within the last minute (they look live); file-only ones spread over a week.
        spread = 60_000 if args.send else 7 * DAY_MS
        visitor.place(now_ms - rng.randint(0, spread))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as file:
        for visitor in visitors:
            file.write(json.dumps(visitor.record(), ensure_ascii=False) + "\n")
    counts = {label: sum(v.label == label for v in visitors) for label in ("bot", "junk", "genuine")}
    print(f"Wrote {len(visitors)} visitors to {out} ({counts['bot']} bot, {counts['junk']} junk, {counts['genuine']} genuine)")

    if args.send:
        # On Windows, "localhost" tries IPv6 first and waits about 2 seconds per request before falling back to
        # IPv4, where uvicorn listens. 127.0.0.1 goes straight there.
        api = args.send.rstrip("/").replace("://localhost", "://127.0.0.1")
        try:
            for visitor in visitors:
                send(visitor, api, include_chat=args.chat)
        except (urllib.error.URLError, TimeoutError) as error:
            print(f"Couldn't send to {api}: {error}. Is the backend running? (cd backend; uvicorn app.main:app)", file=sys.stderr)
            return 1
        print(f"Sent them to {api}. Watch them on the dashboard: http://localhost:5173/dashboard")
        if args.report:
            report(visitors, api)
    return 0


if __name__ == "__main__":
    sys.exit(main())
