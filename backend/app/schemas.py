"""Request and response shapes: the shared contracts between the SDK, the frontend and the backend.

docs/CONTRACTS.md explains them for the team. Adding a field is fine; renaming or removing one needs the
whole team's agreement. Live docs for every route: http://localhost:8000/docs
"""

import re
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

from .utils import iso

UTCDateTime = Annotated[datetime, PlainSerializer(iso, return_type=str)]

# IDs made by the SDK (UUIDs) or the server: letters, digits, '-' and '_' only.
ClientId = Annotated[str, Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


def _clip(limit: int) -> AfterValidator:
    """Cut long text instead of rejecting the whole request (a long page title shouldn't drop a batch)."""
    return AfterValidator(lambda value: value[:limit] if isinstance(value, str) else value)


# ---------------------------------------------------------------- listings


class Listing(BaseModel):
    id: str
    title: str
    project: str
    city: str
    locality: str
    bhk: int
    property_type: str  # Apartment / Villa
    price_inr: int
    area_sqft: int
    status: str  # Ready to move / Under construction
    possession: str  # "Ready", or a month such as "Jun 2027"
    floor: str | None = None
    facing: str | None = None
    amenities: list[str] = []
    highlights: list[str] = []
    tags: list[str] = []
    description: str


# ---------------------------------------------------------------- tracking SDK -> POST /events


class ClientContext(BaseModel):
    """Browser details the SDK sends with every batch. Extra fields are kept as they are."""

    model_config = ConfigDict(extra="allow")

    user_agent: Annotated[str | None, _clip(500)] = None
    language: Annotated[str | None, _clip(35)] = None
    languages: int | None = None  # how many languages the browser lists (0 is a headless-browser hint)
    timezone: Annotated[str | None, _clip(64)] = None
    screen: Annotated[str | None, _clip(20)] = None  # "1920x1080"
    viewport: Annotated[str | None, _clip(20)] = None
    pixel_ratio: float | None = None
    touch_points: int | None = None
    hardware_concurrency: int | None = None
    webdriver: bool | None = None  # true when an automation tool drives the browser
    referrer: Annotated[str | None, _clip(500)] = None
    utm: dict[str, str] | None = None


_EVENT_TYPE_JUNK = re.compile(r"[^a-z0-9_.:-]+")


class EventIn(BaseModel):
    type: str = Field(min_length=1, max_length=80)
    ts: int | None = None  # browser clock, ms since epoch
    path: Annotated[str | None, _clip(500)] = None
    url: Annotated[str | None, _clip(2000)] = None
    title: Annotated[str | None, _clip(300)] = None
    props: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _normalise_type(cls, value: str) -> str:
        """'EMI Used' becomes 'emi_used', so custom event names from any site group together."""
        return _EVENT_TYPE_JUNK.sub("_", value.strip().lower()).strip("_")[:50] or "custom"


class EventBatchIn(BaseModel):
    visitor_id: ClientId
    session_id: ClientId
    site: Annotated[str | None, _clip(100)] = None
    sdk_version: Annotated[str | None, _clip(20)] = None
    sent_at: int | None = None  # browser clock when the batch was sent, ms since epoch
    context: ClientContext = Field(default_factory=ClientContext)
    events: list[EventIn] = Field(min_length=1, max_length=100)


class EventsAccepted(BaseModel):
    ok: bool = True
    accepted: int


# ---------------------------------------------------------------- visitors (dashboard)


class VisitorOut(BaseModel):
    id: str
    site: str | None
    first_seen: UTCDateTime
    last_seen: UTCDateTime
    session_count: int
    page_views: int
    event_count: int
    lead_count: int
    chat_count: int
    last_path: str | None
    last_ip: str | None
    device: str  # desktop / mobile / tablet / unknown
    automation_hints: list[str]  # raw bot signals, e.g. "webdriver"
    profile: dict[str, Any]  # buyer details from chat
    label: str | None = None  # Bot / Junk / Cold / Warm / Hot / Review, set by the scoring engine (Week 2)


class StatsOut(BaseModel):
    """Headline numbers for the dashboard."""

    visitors: int
    active_now: int  # seen in the last 2 minutes
    leads: int
    chatting_visitors: int  # visitors who talked to the assistant


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    started_at: UTCDateTime
    last_seen: UTCDateTime
    landing_path: str | None
    referrer: str | None
    utm: dict[str, Any]
    page_views: int
    event_count: int
    ip: str | None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    type: str
    path: str | None
    title: str | None
    props: dict[str, Any]
    client_ts: int | None
    received_at: UTCDateTime


# ---------------------------------------------------------------- enquiry form -> POST /leads


class LeadIn(BaseModel):
    """The enquiry form. honeypot and form_fill_ms feed the Week 2 bot checks."""

    visitor_id: ClientId | None = None
    session_id: ClientId | None = None
    listing_id: Annotated[str | None, _clip(32)] = None
    name: Annotated[str, Field(min_length=1), _clip(100)]
    phone: Annotated[str, Field(min_length=1), _clip(32)]
    email: Annotated[str | None, _clip(200)] = None
    message: Annotated[str | None, _clip(2000)] = None
    consent: bool = False  # "I agree to be contacted" (DPDP Act 2023)
    honeypot: Annotated[str | None, _clip(500)] = None  # value of the hidden field; people leave it empty
    form_fill_ms: int | None = Field(None, ge=0)  # first touch of the form until submit
    client_ts: int | None = None
    page_url: Annotated[str | None, _clip(2000)] = None


class LeadAccepted(BaseModel):
    ok: bool = True
    lead_id: int


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visitor_id: str
    session_id: str | None
    listing_id: str | None
    name: str
    phone: str
    email: str | None
    message: str | None
    consent: bool
    honeypot: str | None
    form_fill_ms: int | None
    page_url: str | None
    ip: str | None
    status: str
    created_at: UTCDateTime


# ---------------------------------------------------------------- property assistant -> POST /chat


class ChatIn(BaseModel):
    visitor_id: ClientId | None = None
    session_id: ClientId | None = None
    message: str = Field(min_length=1, max_length=1000)
    listing_id: Annotated[str | None, _clip(32)] = None  # the property page the visitor is on, if any


class ChatOut(BaseModel):
    reply: str
    listings: list[Listing]  # shown as cards under the reply
    extracted: dict[str, Any]  # details found in this message
    profile: dict[str, Any]  # everything known about the buyer so far
    mode: Literal["llm", "template"]


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    text: str
    extracted: dict[str, Any]
    listing_ids: list[str]
    mode: str | None
    created_at: UTCDateTime


class VisitorDetailOut(BaseModel):
    visitor: VisitorOut
    user_agent: str | None
    context: dict[str, Any]
    sessions: list[SessionOut]  # newest first
    events: list[EventOut]  # newest first, up to 200
    leads: list[LeadOut]  # newest first
    chat: list[ChatMessageOut]  # oldest first


# ---------------------------------------------------------------- sales feedback -> POST /feedback


class FeedbackIn(BaseModel):
    visitor_id: ClientId | None = None
    lead_id: int | None = None
    label: Literal["genuine", "fake", "converted"]
    note: Annotated[str | None, _clip(1000)] = None

    @model_validator(mode="after")
    def _needs_a_target(self) -> "FeedbackIn":
        if self.visitor_id is None and self.lead_id is None:
            raise ValueError("Give a visitor_id or a lead_id")
        return self


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visitor_id: str | None
    lead_id: int | None
    label: str
    note: str | None
    created_at: UTCDateTime
