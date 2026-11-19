"""The dashboard passcode: the dashboard shows names and phone numbers, so a deployed one must not be open to everyone.

Set DASHBOARD_PASSCODE to switch it on. The dashboard's routes then need the passcode in the X-LeadOps-Passcode header,
and its WebSocket in the `passcode` query parameter. Without the setting (local development) nothing changes. What
visitors use (events, enquiries, chat, listings, the SDK) never needs it.
"""

import secrets

from fastapi import Depends, HTTPException, Request

from .config import settings

PASSCODE_HEADER = "x-leadops-passcode"


def current_passcode() -> str:
    return settings.dashboard_passcode


def passcode_ok(given: str | None) -> bool:
    expected = current_passcode()
    return not expected or secrets.compare_digest((given or "").encode(), expected.encode())


def require_dashboard(request: Request) -> None:
    if not passcode_ok(request.headers.get(PASSCODE_HEADER)):
        raise HTTPException(status_code=401, detail="Enter the dashboard passcode")


DASHBOARD_ONLY = [Depends(require_dashboard)]
