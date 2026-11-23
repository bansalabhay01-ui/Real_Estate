"""Small helpers shared across the backend."""

import re
import threading
import time
from collections import deque
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from starlette.requests import HTTPConnection


def utcnow() -> datetime:
    """Current time in UTC without tzinfo. The database stores UTC everywhere (SQLite has no time zones)."""
    return datetime.now(UTC).replace(tzinfo=None)


IST = timezone(timedelta(hours=5, minutes=30))


def today_ist() -> date:
    """Today in India: site visits are booked by the buyer's calendar, not the server's."""
    return datetime.now(IST).date()


def short_day(day: date) -> str:
    """"Sat 21 Nov"."""
    return f"{day:%a} {day.day} {day:%b}"


def iso(value: datetime | None) -> str | None:
    """'2026-11-03T08:15:00.000Z' style, so browsers convert it to local time correctly."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def client_ip(conn: HTTPConnection) -> str | None:
    """The visitor's IP address.

    On Render, Cloudflare sits in front and sets CF-Connecting-IP / True-Client-IP, which a browser can't fake.
    X-Forwarded-For comes next: Render adds to it without clearing what the browser sent, so its first entry can be
    made up, but it is all there is locally (and the simulator sets it on purpose)."""
    for header in ("cf-connecting-ip", "true-client-ip"):
        value = (conn.headers.get(header) or "").strip()
        if value:
            return value[:64]
    forwarded = conn.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]
    return conn.client.host if conn.client else None


class RateLimit:
    """At most `limit` hits per key in any `window_s` seconds. Kept in memory, so it assumes one server process
    (as realtime.py does)."""

    def __init__(self, limit: int, window_s: float) -> None:
        self.limit, self.window_s = limit, window_s
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Count a hit for this key, unless it is over the limit. A limit of 0 means no limit."""
        if self.limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > 10_000:  # forget keys that have gone quiet, so memory stays small
                self._hits = {key: hits for key, hits in self._hits.items() if hits and now - hits[-1] < self.window_s}
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


_TABLET = re.compile(r"iPad|Tablet|Android(?!.*Mobile)", re.IGNORECASE)
_MOBILE = re.compile(r"Mobi|iPhone|Android", re.IGNORECASE)
_AUTOMATION = re.compile(
    r"Headless|PhantomJS|Selenium|Playwright|Puppeteer|python-requests|python-httpx|python-urllib|aiohttp"
    r"|curl/|Wget|Go-http-client|okhttp|Scrapy|bot\b|crawler|spider",
    re.IGNORECASE,
)


def device_from_ua(user_agent: str | None) -> str:
    if not user_agent:
        return "unknown"
    if _TABLET.search(user_agent):
        return "tablet"
    if _MOBILE.search(user_agent):
        return "mobile"
    return "desktop"


def automation_hints(user_agent: str | None, context: dict[str, Any]) -> list[str]:
    """Raw bot signals shown on the dashboard. The Week 2 scoring engine turns signals like these into labels."""
    hints = []
    if context.get("webdriver"):
        hints.append("webdriver")
    if not user_agent:
        hints.append("no_user_agent")
    elif _AUTOMATION.search(user_agent):
        hints.append("automation_user_agent")
    if context.get("languages") == 0:
        hints.append("no_browser_languages")
    return hints
