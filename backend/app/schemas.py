"""Request and response shapes: the shared contracts between the SDK, the frontend and the backend.

docs/CONTRACTS.md explains them for the team. Adding a field is fine; renaming or removing one needs the
whole team's agreement. Live docs for every route: http://localhost:8000/docs
"""

import re
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

from .utils import iso

UTCDateTime = Annotated[datetime, PlainSerializer(iso, return_type=str)]

# IDs made by the SDK (UUIDs) or the server: letters, digits, '-' and '_' only.
ClientId = Annotated[str, Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]

TEST_LABELS = ("genuine", "junk", "bot")  # what a tester link can mark a visit as
LEAD_SOURCES = ("form", "assistant_offer", "chat")  # where an enquiry came from


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
    # Only on test sessions opened through a tester link (?lo_test=genuine&lo_tester=t01). Scoring never reads
    # them; ml/train.py uses them to build the real test set.
    test_label: str | None = None  # genuine / junk / bot
    tester: Annotated[str | None, _clip(40)] = None  # a tester code, not a name

    @field_validator("test_label", mode="before")
    @classmethod
    def _known_test_label(cls, value: Any) -> str | None:
        """An unknown label is dropped rather than rejected, so a mistyped link never loses a batch."""
        label = value.strip().lower() if isinstance(value, str) else None
        return label if label in TEST_LABELS else None


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


class NudgeOut(BaseModel):
    """An offer from the assistant, sent back with an event batch. The SDK hands it to the website (LeadOps.onNudge)."""

    id: str
    kind: str  # floor_plan / emi_plan / site_visit / shortlist
    text: str  # the offer, in the visitor's language
    cta: str  # the words on the accept button
    listing_id: str | None = None
    project: str | None = None
    language: str = "en"
    ask: str = ""  # what accepting means, in words for the sales team: send it as the enquiry's message


class EventsAccepted(BaseModel):
    ok: bool = True
    accepted: int
    nudge: NudgeOut | None = None  # only when the assistant has an offer for this visitor


# ---------------------------------------------------------------- visitors (dashboard)


class ScoreOut(BaseModel):
    """A visitor's latest score from the scoring engine (docs/CONTRACTS.md, section 6)."""

    label: str  # Bot / Junk / Review / Cold / Warm / Hot
    intent_score: int  # 0-100
    human_prob: float  # 0-1, from the ML human check
    visitor_type: str | None = None  # end_buyer / investor / tenant / broker / spam, once known
    reasons: list[str]  # plain-language reasons, most important first
    summary: str  # one line: "Hot: 3 visits over 2 days; ..."
    model_version: str
    scored_at: str  # ISO 8601 UTC


class VerdictOut(BaseModel):
    """The sales team's latest verdict on a visitor."""

    label: str  # genuine / fake / converted
    note: str | None = None
    created_at: UTCDateTime | None = None


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
    label: str | None = None  # Bot / Junk / Review / Cold / Warm / Hot, set by the scoring engine
    test_label: str | None = None  # genuine / junk / bot on test sessions from a tester link
    score: ScoreOut | None = None  # None until the visitor has been scored
    feedback: VerdictOut | None = None  # the sales team's latest verdict


class NextStepOut(BaseModel):
    text: str  # "Call now: asked for a site visit this Saturday."
    urgency: Literal["now", "today", "this_week", "none"]
    action: Literal["call", "offer", "whatsapp", "review", "confirm_visit", "none"]


class BriefOut(BaseModel):
    """What a salesperson needs at a glance."""

    lines: list[str]  # three plain lines: what they want, what they did, what to watch for
    next_step: NextStepOut
    mode: Literal["llm", "template"]


class FollowUpIn(BaseModel):
    channel: Literal["whatsapp", "email"] = "whatsapp"
    language: Literal["auto", "en", "hinglish", "hi", "mr"] = "auto"  # auto: the language the buyer has been using


class FollowUpOut(BaseModel):
    channel: str
    language: str
    subject: str  # for email
    text: str
    mode: Literal["llm", "template"]
    whatsapp_number: str | None = None  # country code and digits
    whatsapp_url: str | None = None  # a wa.me click-to-chat link with the text filled in
    email: str | None = None
    mailto_url: str | None = None


class StatsOut(BaseModel):
    """Headline numbers for the dashboard."""

    visitors: int
    active_now: int  # seen in the last 2 minutes
    leads: int
    chatting_visitors: int  # visitors who talked to the assistant
    labels: dict[str, int] = {}  # visitors per label, e.g. {"Hot": 4, "Bot": 120}
    assistant_leads: int = 0  # enquiries that came from an offer by the assistant
    offers_sent: int = 0  # offers that reached a visitor's browser
    offers_accepted: int = 0
    model_version: str = "fallback"  # the human-check model in use
    model_verdicts: int = 0  # how many sales verdicts that model learned from


class FunnelStep(BaseModel):
    step: str  # visitors / people / contacts / hot
    label: str
    count: int


class DailyTraffic(BaseModel):
    day: date
    kept: int  # people worth the sales team's time: Cold, Warm, Hot and Review
    junk: int
    bots: int


class AnalyticsOut(BaseModel):
    """The analytics page. Everything counts visitors first seen in the chosen period."""

    days: int
    include_simulated: bool
    visitors: int
    funnel: list[FunnelStep]
    labels: dict[str, int]
    enquiries: int
    enquiries_filtered: int  # enquiries from visitors labelled Bot or Junk
    hours_saved: float  # an estimate: enquiries_filtered x minutes_per_enquiry
    minutes_per_enquiry: int
    found_by_assistant: int
    offers_sent: int
    offers_accepted: int
    site_visits: int
    daily: list[DailyTraffic]


class RescoreOut(BaseModel):
    ok: bool = True
    visitors: int  # how many visitors are being rescored


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
    source: str | None = None  # form (the default) / assistant_offer / chat

    @field_validator("source", mode="before")
    @classmethod
    def _known_source(cls, value: Any) -> str | None:
        """An unknown source is dropped rather than rejected, so a site's typo never loses an enquiry."""
        return value if value in LEAD_SOURCES else None


class OtpOut(BaseModel):
    """The phone check that follows an enquiry. It is mocked: no SMS is sent and the site shows demo_code on screen."""

    token: str  # proves the verify request comes from whoever sent this enquiry
    phone: str  # the number with most digits hidden, e.g. "+91 98xxx xx345"
    demo_code: str


class LeadAccepted(BaseModel):
    ok: bool = True
    lead_id: int
    otp: OtpOut | None = None  # only for a number that could receive a code


class OtpCheckIn(BaseModel):
    token: str = Field(min_length=8, max_length=64)
    code: str = Field(min_length=1, max_length=12)


class OtpResult(BaseModel):
    verified: bool
    tries_left: int


class AccessOut(BaseModel):
    ok: bool = True


class ErasedOut(BaseModel):
    ok: bool = True


class LeadCheckOut(BaseModel):
    """One check on an enquiry's details, shown next to it on the dashboard."""

    check: str  # phone / email / name / message / honeypot / fill_time
    ok: bool
    text: str


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
    label: str | None = None  # the visitor's current label
    checks: list[LeadCheckOut] = []
    source: str | None = "form"  # form / assistant_offer / chat
    verdict: str | None = None  # the sales team's latest verdict on this visitor
    phone_verified: bool | None = False  # the buyer entered the OTP


# ---------------------------------------------------------------- site visits -> POST /visits


class VisitIn(BaseModel):
    """A site-visit request. Someone who hasn't left contact details yet sends them here too."""

    visitor_id: ClientId | None = None
    session_id: ClientId | None = None
    listing_id: Annotated[str, Field(min_length=1), _clip(32)]
    day: date
    slot: Literal["morning", "afternoon", "evening"] = "morning"
    source: Literal["assistant", "dashboard"] = "assistant"
    lead_source: Literal["chat", "assistant_offer"] = "chat"  # where new contact details came from
    language: Annotated[str | None, _clip(10)] = None  # the language of the confirmation message
    name: Annotated[str | None, _clip(100)] = None
    phone: Annotated[str | None, _clip(32)] = None
    email: Annotated[str | None, _clip(200)] = None
    consent: bool = False
    honeypot: Annotated[str | None, _clip(500)] = None
    form_fill_ms: int | None = Field(None, ge=0)


class VisitUpdate(BaseModel):
    status: Literal["requested", "confirmed", "done", "cancelled"] | None = None
    day: date | None = None
    slot: Literal["morning", "afternoon", "evening"] | None = None


class VisitOut(BaseModel):
    id: int
    visitor_id: str
    lead_id: int | None
    listing_id: str
    project: str
    locality: str
    city: str
    day: date
    day_text: str  # "Sat 21 Nov"
    slot: str
    status: str
    source: str
    name: str | None = None  # from the visitor's enquiry
    phone: str | None = None
    created_at: UTCDateTime
    confirmation: str | None = None  # a line for the visitor, in their language


# ---------------------------------------------------------------- property assistant -> POST /chat


class ChatIn(BaseModel):
    visitor_id: ClientId | None = None
    session_id: ClientId | None = None
    message: str = Field(min_length=1, max_length=1000)
    listing_id: Annotated[str | None, _clip(32)] = None  # the property page the visitor is on, if any


class EmiOut(BaseModel):
    """An EMI the assistant worked out, with the EMI calculator's formula."""

    listing_id: str
    project: str
    price_inr: int
    down_payment_pct: float
    loan_inr: int
    rate_pct: float
    years: int
    emi_inr: int
    total_interest_inr: int


class ChatAction(BaseModel):
    """Something the chat widget shows under the reply."""

    type: Literal["contact_form", "visit_booked"]
    purpose: Literal["site_visit", "callback"] | None = None  # what a contact_form is for
    listing_id: str | None = None
    project: str | None = None
    need_contact: bool = False  # the form asks for a name and mobile number
    day: date | None = None
    slot: str | None = None
    visit: VisitOut | None = None  # on visit_booked


class ChatOut(BaseModel):
    reply: str
    listings: list[Listing]  # shown as cards under the reply
    extracted: dict[str, Any]  # details found in this message
    profile: dict[str, Any]  # everything known about the buyer so far
    mode: Literal["llm", "template"]
    action: ChatAction | None = None  # a form or a booking to show under the reply
    emi: EmiOut | None = None  # an EMI worked out for this message


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    text: str
    extracted: dict[str, Any]
    listing_ids: list[str]
    mode: str | None
    created_at: UTCDateTime


class NudgeRecordOut(BaseModel):
    """An offer made to this visitor, on their dashboard panel."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    text: str
    trigger: str  # auto / sales
    status: str  # pending / sent / shown / accepted / dismissed
    created_at: UTCDateTime


class VisitorDetailOut(BaseModel):
    visitor: VisitorOut
    user_agent: str | None
    context: dict[str, Any]
    sessions: list[SessionOut]  # newest first
    events: list[EventOut]  # newest first, up to 200
    leads: list[LeadOut]  # newest first
    chat: list[ChatMessageOut]  # oldest first
    site_visits: list[VisitOut] = []  # newest first
    nudges: list[NudgeRecordOut] = []  # offers from the assistant, newest first
    score_detail: dict[str, Any] | None = None  # rules that fired, SHAP factors, intent points (docs/CONTRACTS.md)


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


# ---------------------------------------------------------------- live demo tools (dashboard)


class SimulateIn(BaseModel):
    bots: int = Field(200, ge=0, le=500)
    junk: int = Field(30, ge=0, le=200)
    genuine: int = Field(20, ge=0, le=200)
    seconds: float = Field(30, ge=0, le=120)  # the run is spread over this long, so an audience can watch it
    seed: int | None = None  # the same seed gives the same visitors

    @model_validator(mode="after")
    def _needs_visitors(self) -> "SimulateIn":
        if self.bots + self.junk + self.genuine == 0:
            raise ValueError("Ask for at least one visitor")
        return self


class SimulationStarted(BaseModel):
    ok: bool = True
    run_id: str
    total: int
    seconds: float


class SimulationKindOut(BaseModel):
    kind: str  # e.g. "bot/scraper", "genuine/serious"
    total: int
    labels: dict[str, int]


class ScoreboardOut(BaseModel):
    """How a simulated run was sorted: what each visitor really was against the label it got."""

    run_id: str
    total: int
    seconds: float
    bots_total: int
    bots_blocked: int  # labelled Bot or Junk
    junk_total: int
    junk_filtered: int  # labelled Bot or Junk
    genuine_total: int
    genuine_kept: int  # labelled anything but Bot or Junk
    genuine_labels: dict[str, int]  # e.g. {"Hot": 4, "Warm": 9, "Cold": 7}
    kinds: list[SimulationKindOut]


class DemoStatusOut(BaseModel):
    running: bool
    run_id: str | None = None
    sent: int = 0
    total: int = 0
    labels: dict[str, int] = {}  # visitors of this run per label so far
    scoreboard: ScoreboardOut | None = None  # the latest finished run
    simulated_visitors: int = 0  # visitors the button made that are still in the database
    bot_available: bool = False  # real Playwright bots only run where the backend's laptop has them installed
    bot_running: bool = False


class SimulatedRemoved(BaseModel):
    ok: bool = True
    removed: int


class BotRunIn(BaseModel):
    kind: Literal["naive", "stealth", "scraper"] = "stealth"
    site: Annotated[str, _clip(200)] = "http://localhost:5173"  # the demo site the bot opens
    headed: bool = True  # show the browser window (what an audience wants to see)


class BotRunStarted(BaseModel):
    ok: bool = True
    kind: str
