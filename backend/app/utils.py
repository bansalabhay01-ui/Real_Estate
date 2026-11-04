"""Small helpers shared across the backend."""

import re
from datetime import UTC, datetime
from typing import Any

from starlette.requests import HTTPConnection


def utcnow() -> datetime:
    """Current time in UTC without tzinfo. The database stores UTC everywhere (SQLite has no time zones)."""
    return datetime.now(UTC).replace(tzinfo=None)


def iso(value: datetime | None) -> str | None:
    """'2026-11-03T08:15:00.000Z' style, so browsers convert it to local time correctly."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def client_ip(conn: HTTPConnection) -> str | None:
    """The visitor's IP address. Behind a proxy (Render, Vercel) the first X-Forwarded-For entry is the client."""
    forwarded = conn.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]
    real_ip = conn.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()[:64]
    return conn.client.host if conn.client else None


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
