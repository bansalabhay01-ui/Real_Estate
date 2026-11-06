"""Hard rules: checks on contact details, and the bot and junk signals that can decide a label.

Every signal has a strength (LEADOPS_PLAN.md, Week 2 Part 2):
  certain  decides on its own. Bot: hidden honeypot filled, navigator.webdriver, an automation user agent.
           Junk: a fake phone number, a placeholder name or email, a spam or broker message.
  strong   has an innocent explanation (browser autofill, an ad blocker, a throwaway email to avoid spam
           calls), so one alone sends a visitor to Review at most. Two together, or one plus a low ML score,
           decide (combine.py).
Lots of visitors from one IP is deliberately not a rule: colleges, offices and mobile networks share addresses,
so it only feeds the ML model.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from ..config import BACKEND_DIR

CERTAIN, STRONG = "certain", "strong"
BOT, JUNK = "bot", "junk"

FAST_FORM_MS = 1000  # faster than any person; browser autofill still takes 1-2 seconds
SCRAPE_PAGES = 8  # this many pages with under 2 seconds on each looks like a scraper
SHARED_PHONE_VISITORS = 3  # the same number from this many browsers (one person on phone + laptop is 2)


@dataclass(frozen=True)
class Signal:
    code: str  # e.g. "honeypot", "fake_phone"
    layer: str  # "bot" or "junk"
    strength: str  # "certain" or "strong"
    reason: str  # plain words for the sales team


# ---------------------------------------------------------------- contact checks


@dataclass(frozen=True)
class Check:
    kind: str  # phone: mobile / international / invalid / fake; email: ok / none / invalid / disposable / fake
    reason: str = ""


_KNOWN_FAKE_NUMBERS = {"9876543210", "9123456789", "9988776655", "9000000000", "8888888888", "7777777777"}


def phone_digits(raw: str | None) -> str:
    """The number as digits only, with the country code or leading 0 removed for Indian numbers."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        return digits[1:]
    return digits


def check_phone(raw: str | None) -> Check:
    text = (raw or "").strip()
    digits = re.sub(r"\D", "", text)
    if not digits:
        return Check("invalid", "no digits at all")
    if len(digits) >= 5 and len(set(digits)) == 1:
        return Check("fake", "the same digit over and over")
    dialled_abroad = digits.startswith("00") and len(digits) > 10 and digits[2] != "0"  # 00 + country code
    international = (text.startswith("+") and not digits.startswith("91")) or dialled_abroad
    if international:  # NRI buyers: any plausible international number is fine
        digits = digits.removeprefix("00")
        return Check("international") if 8 <= len(digits) <= 15 else Check("invalid", "not a valid phone number")
    number = phone_digits(text)
    if len(number) < 10:
        return Check("invalid", f"too short ({len(number)} digits)")
    if len(number) > 10:
        # Likely an international number typed without the +. We can't be sure it's fake, so let it through.
        return Check("international") if len(number) <= 15 else Check("invalid", "too long")
    if number in "01234567890" or number in "98765432109" or number in _KNOWN_FAKE_NUMBERS:
        return Check("fake", "a well-known placeholder number")
    if number == number[:2] * 5:
        return Check("fake", "a repeating pattern")
    if not re.fullmatch(r"[6-9]\d{9}", number):
        return Check("invalid", "not a valid Indian mobile number (they start with 6 to 9)")
    return Check("mobile")


JUNK_WORDS = {
    "asdf", "asd", "sdf", "qwe", "qwerty", "zxc", "test", "testing", "tester", "abc", "abcd", "xyz", "xxx", "zzz",
    "aaa", "none", "null", "nil", "dummy", "fake", "sample", "demo", "hello", "hii", "user", "name", "admin",
    "lorem", "ipsum", "bot", "spam", "nothing", "noname", "unknown", "anonymous",
}  # fmt: skip
_JUNK_WHOLE = {"n/a", "na", "-", ".", "..", "...", "?"}
# Narrower than JUNK_WORDS: "hello@..." or "admin@..." can be a real address.
_JUNK_EMAIL_LOCALS = {"test", "testing", "asdf", "abc", "abcd", "xyz", "qwerty", "fake", "dummy", "sample", "spam",
                      "noemail", "nomail", "none", "null", "na", "xxx", "aaa"}  # fmt: skip
_KEYBOARD_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
_PLACEHOLDER_DOMAINS = {"test.com", "test.in", "example.com", "example.in", "example.org", "abc.com", "xyz.com",
                        "asdf.com", "fake.com", "domain.com", "sample.com", "dummy.com"}  # fmt: skip
_EMAIL = re.compile(r"^[\w.+-]+@([\w-]+(?:\.[\w-]+)+)$")


def _junk_word(word: str) -> bool:
    if word in JUNK_WORDS:
        return True
    if len(word) >= 2 and len(set(word)) == 1:  # "aaaa"
        return True
    return len(word) >= 4 and any(word in row for row in _KEYBOARD_ROWS)  # "asdfg", "qwer"


def is_junk_text(text: str | None) -> bool:
    """A placeholder like "test", "asdf", "aaaa" or "123" rather than a real name or message."""
    value = (text or "").strip().casefold()
    if not value:
        return False
    if value in _JUNK_WHOLE:
        return True
    words = re.findall(r"[a-z]+|[ऀ-ॿ]+", value)
    if not words:
        return True  # no letters at all
    return all(_junk_word(word) for word in words)


@lru_cache(maxsize=1)
def disposable_domains() -> frozenset[str]:
    path = BACKEND_DIR / "data" / "disposable_domains.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip().lower() for line in lines if line.strip() and not line.startswith("#"))


def check_email(raw: str | None) -> Check:
    text = (raw or "").strip().casefold()
    if not text:
        return Check("none")
    match = _EMAIL.match(text)
    if not match:
        return Check("invalid", "not a valid email address")
    local, domain = text.split("@", 1)[0], match.group(1)
    letters = re.sub(r"[^a-z]", "", local)
    placeholder_local = letters in _JUNK_EMAIL_LOCALS or (len(letters) >= 3 and len(set(letters)) == 1)
    if domain in _PLACEHOLDER_DOMAINS or placeholder_local:
        return Check("fake", f"a placeholder address ({text})")
    if domain in disposable_domains() or any(domain.endswith("." + d) for d in disposable_domains()):
        return Check("disposable", f"a throwaway email domain ({domain})")
    return Check("ok")


_URL = re.compile(r"https?://|www\.|\b[\w-]+\.(?:com|in|net|org|xyz|info|biz|example)/", re.IGNORECASE)
_PROMO = re.compile(
    r"\b(?:seo|backlinks?|digital marketing|marketing services|earn (?:money|from home)|work from home|casino|"
    r"crypto|bitcoin|forex|guaranteed returns?|click here|limited offer|buy followers|10x leads|lottery)\b",
    re.IGNORECASE,
)
_BROKER = re.compile(
    r"\b(?:channel partners?|cp registration|my clients?|my buyers|for my client|(?:share|send) (?:your|the|full|all)"
    r" inventory|inventory list|brokerage (?:structure|percentage|sharing|kitna)|commission (?:structure|percentage|"
    r"sharing)|i am an? (?:broker|agent|channel partner)|broker here|we are (?:a )?(?:real estate )?(?:consultants?|"
    r"agency|brokers))\b",
    re.IGNORECASE,
)


def check_message(text: str | None) -> list[Signal]:
    """Junk signals in an enquiry message or a chat message."""
    message = (text or "").strip()
    if not message:
        return []
    signals = []
    if _PROMO.search(message):
        signals.append(Signal("spam_message", JUNK, CERTAIN, "The message is an advert (SEO, earn money, offers)"))
    elif _URL.search(message):
        signals.append(Signal("link_in_message", JUNK, STRONG, "The message contains a link"))
    if match := _BROKER.search(message):
        signals.append(Signal("broker_message", JUNK, CERTAIN, f'The message is a broker\'s pitch ("{match.group(0)}")'))
    if is_junk_text(message):
        signals.append(Signal("junk_message", JUNK, CERTAIN, "The message is a placeholder, not a question"))
    return signals


# ---------------------------------------------------------------- the rules


def _seconds(ms: float) -> str:
    return f"{ms / 1000:.1f} seconds" if ms < 10_000 else f"{round(ms / 1000)} seconds"


def evaluate(record: dict, features: dict) -> list[Signal]:
    """Every bot and junk signal that fires for this visitor (record and features: see features.py)."""
    signals: list[Signal] = []
    add = signals.append
    leads = record.get("leads") or []

    # ---- bot: certain
    if features.get("honeypot"):
        add(Signal("honeypot", BOT, CERTAIN, "Filled in the hidden form field that only bots can see"))
    if features.get("webdriver"):
        add(Signal("webdriver", BOT, CERTAIN, "The browser is driven by automation software (navigator.webdriver)"))
    if features.get("automation_ua"):
        add(Signal("automation_ua", BOT, CERTAIN, f"The user agent belongs to an automation tool ({_ua_name(record)})"))
    if features.get("no_user_agent"):
        add(Signal("no_user_agent", BOT, CERTAIN, "Sent no user agent, which every real browser does"))

    # ---- bot: strong
    fills = [lead.get("form_fill_ms") for lead in leads if lead.get("form_fill_ms") is not None]
    if fills and min(fills) < FAST_FORM_MS:
        fastest = min(fills)
        detail = "without typing anything" if fastest == 0 else f"{_seconds(fastest)} after first touching it"
        add(Signal("instant_form", BOT, STRONG, f"Sent the enquiry form {detail}"))
    if features.get("untrusted_clicks", 0) >= 1 and features.get("trusted_clicks", 0) == 0:
        count = int(features["untrusted_clicks"])
        add(Signal("scripted_clicks", BOT, STRONG, f"{count} click{'s were' if count > 1 else ' was'} made by a script, none by a person"))
    if features.get("fast_pages", 0) >= SCRAPE_PAGES:
        add(Signal("scraping", BOT, STRONG, f"Opened {int(features['fast_pages'])} pages, spending under 2 seconds on each"))
    if leads and features.get("page_views", 0) == 0:
        add(Signal("no_browsing_enquiry", BOT, STRONG,
                   "Sent an enquiry without loading a single page (posted straight to the API, or the script was blocked)"))

    # ---- junk: contact details and messages
    for lead in leads:
        phone = check_phone(lead.get("phone"))
        if phone.kind in ("fake", "invalid"):
            add(Signal("fake_phone", JUNK, CERTAIN, f"The phone number can't be real: {phone.reason}"))
        if is_junk_text(lead.get("name")):
            add(Signal("junk_name", JUNK, CERTAIN, f'The name is a placeholder ("{(lead.get("name") or "").strip()[:20]}")'))
        email = check_email(lead.get("email"))
        if email.kind == "fake":
            add(Signal("fake_email", JUNK, CERTAIN, f"The email is {email.reason}"))
        elif email.kind == "disposable":
            add(Signal("disposable_email", JUNK, STRONG, f"Uses {email.reason}"))
        elif email.kind == "invalid":
            add(Signal("invalid_email", JUNK, STRONG, "The email address isn't valid"))
        signals.extend(check_message(lead.get("message")))
    for message in record.get("chat") or []:
        signals.extend(s for s in check_message(message.get("text")) if s.code in ("spam_message", "broker_message"))
    shared = (record.get("network") or {}).get("phone_visitors", 0)
    if leads and shared >= SHARED_PHONE_VISITORS:
        add(Signal("shared_phone", JUNK, STRONG, f"The same phone number came from {shared} different visitors"))

    return _dedupe(signals)


def _ua_name(record: dict) -> str:
    agent = record.get("user_agent") or ""
    for token in ("HeadlessChrome", "PhantomJS", "Selenium", "Playwright", "Puppeteer", "python-requests",
                  "python-httpx", "python-urllib", "aiohttp", "curl", "Wget", "Go-http-client", "okhttp", "Scrapy"):
        if token.casefold() in agent.casefold():
            return token
    return "a bot or crawler"


def _dedupe(signals: list[Signal]) -> list[Signal]:
    """One signal per code (the first one), so two enquiries with the same fake number count once."""
    seen: set[str] = set()
    unique = []
    for signal in signals:
        if signal.code not in seen:
            seen.add(signal.code)
            unique.append(signal)
    return unique
