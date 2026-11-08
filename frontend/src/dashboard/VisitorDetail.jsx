import { useEffect, useState } from "react";
import { IconClose } from "../components/icons";
import { getVisitor } from "../lib/api";
import { formatClock, formatDateTime, formatPrice } from "../lib/format";
import { describeEvent } from "./describe";
import ScoreBreakdown from "./ScoreBreakdown";
import { LabelBadge, LeadChecks, shortId, SignalChips } from "./Signals";

const TIMELINE_LIMIT = 60;
const LANGUAGES = { en: "English", hinglish: "Hinglish", hi: "Hindi" };

function Section({ title, children }) {
  return (
    <section className="border-t border-line pt-4">
      <h3 className="mb-2 text-sm font-semibold text-ink-soft">{title}</h3>
      {children}
    </section>
  );
}

function Row({ label, children }) {
  return (
    <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-3 py-0.5">
      <dt className="text-muted">{label}</dt>
      <dd className="break-words">{children}</dd>
    </div>
  );
}

function budget(profile) {
  const { budget_min: low, budget_max: high } = profile;
  if (low && high) return `${formatPrice(low)} to ${formatPrice(high)}`;
  if (high) return `Under ${formatPrice(high)}`;
  if (low) return `Above ${formatPrice(low)}`;
  return null;
}

function BuyerDetails({ profile }) {
  const unknown = <span className="text-muted">Not shared yet</span>;
  const loan = profile.loan_needed === true ? "Needs a loan" : profile.loan_needed === false ? "No loan needed" : null;
  const purpose = { own_use: "To live in", investment: "An investment" }[profile.purpose] ?? null;
  return (
    <dl className="text-sm">
      <Row label="Location">{[profile.locality, profile.city].filter(Boolean).join(", ") || unknown}</Row>
      <Row label="Bedrooms">{profile.bhk ? `${profile.bhk} BHK` : unknown}</Row>
      <Row label="Budget">{budget(profile) ?? unknown}</Row>
      <Row label="Move-in">{profile.timeline_months ? `Within ${profile.timeline_months} months` : unknown}</Row>
      <Row label="Home loan">{loan ?? unknown}</Row>
      <Row label="Purpose">{purpose ?? unknown}</Row>
      <Row label="Language">{LANGUAGES[profile.language] ?? unknown}</Row>
    </dl>
  );
}

const panelClass = "self-start rounded-lg border border-line bg-white p-5 xl:sticky xl:top-6";

export default function VisitorDetail({ visitorId, version, onClose }) {
  const [detail, setDetail] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!visitorId) return undefined;
    let cancelled = false;
    setFailed(false);
    getVisitor(visitorId)
      .then((data) => !cancelled && setDetail(data))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [visitorId, version]);

  if (!visitorId) {
    return (
      <aside className={`${panelClass} border-dashed text-sm text-muted`}>
        Select a visitor to see their pages, chat and enquiries in the order they happened.
      </aside>
    );
  }
  if (failed) {
    return (
      <aside role="alert" className={`${panelClass} text-sm`}>
        This visitor couldn&apos;t load. Check that the API is running, then select the visitor again.
      </aside>
    );
  }
  if (!detail || detail.visitor.id !== visitorId) {
    return <aside className={`${panelClass} text-sm text-muted`}>Loading the visitor...</aside>;
  }

  const { visitor, events, leads, chat, context, user_agent: userAgent, score_detail: scoreDetail } = detail;
  return (
    <aside
      aria-labelledby="visitor-heading"
      className={`${panelClass} flex flex-col gap-4 xl:max-h-[calc(100dvh-3rem)] xl:overflow-y-auto`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="visitor-heading" className="flex flex-wrap items-center gap-2 font-wide text-lg font-semibold">
            Visitor {shortId(visitor.id)} <LabelBadge label={visitor.label} />
          </h2>
          <p className="text-sm text-muted">
            First seen {formatDateTime(visitor.first_seen)}. {visitor.session_count}{" "}
            {visitor.session_count === 1 ? "visit" : "visits"} on {visitor.device}.
          </p>
        </div>
        <button type="button" onClick={onClose} className="rounded p-1 hover:bg-concrete" aria-label="Close visitor details">
          <IconClose className="size-5" />
        </button>
      </div>

      <Section title="Why this label">
        <ScoreBreakdown score={visitor.score} detail={scoreDetail} hasEnquiry={leads.length > 0} />
      </Section>

      <Section title="Signals">
        <SignalChips visitor={visitor} />
      </Section>

      <Section title="Buyer details from chat">
        <BuyerDetails profile={visitor.profile} />
      </Section>

      {leads.length > 0 && (
        <Section title="Enquiries">
          <ul className="flex flex-col gap-3 text-sm">
            {leads.map((lead) => (
              <li key={lead.id} className="rounded-md border border-line p-3">
                <p className="font-semibold">
                  {lead.name}, {lead.phone}
                </p>
                <p className="text-muted">
                  {lead.listing_id ? `About ${lead.listing_id}, ` : ""}
                  {formatDateTime(lead.created_at)}
                  {lead.email ? `, ${lead.email}` : ""}
                </p>
                {lead.message && <p className="mt-1 text-ink-soft">{lead.message}</p>}
                <div className="mt-2">
                  <LeadChecks lead={lead} />
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {chat.length > 0 && (
        <Section title="Conversation">
          <ol className="flex flex-col gap-2 text-sm">
            {chat.map((message) => (
              <li key={message.id} className={message.role === "user" ? "text-ink" : "text-ink-soft"}>
                <span className="font-semibold">{message.role === "user" ? "Visitor" : "Assistant"}: </span>
                <span className="whitespace-pre-line">{message.text}</span>
              </li>
            ))}
          </ol>
        </Section>
      )}

      <Section title="Activity, newest first">
        {events.length === 0 ? (
          <p className="text-sm text-muted">No browsing recorded for this visitor.</p>
        ) : (
          <ol className="flex flex-col gap-1.5 text-sm">
            {events.slice(0, TIMELINE_LIMIT).map((event) => (
              <li key={event.id} className="grid grid-cols-[72px_minmax(0,1fr)] gap-2">
                <time className="tabular text-muted" dateTime={event.received_at}>
                  {formatClock(event.received_at)}
                </time>
                <span className="break-words">{describeEvent(event)}</span>
              </li>
            ))}
          </ol>
        )}
        {events.length > TIMELINE_LIMIT && (
          <p className="mt-2 text-xs text-muted">
            Showing the latest {TIMELINE_LIMIT} of {events.length} events.
          </p>
        )}
      </Section>

      <Section title="Browser">
        <dl className="text-sm">
          <Row label="IP address">{visitor.last_ip ?? "Unknown"}</Row>
          <Row label="Site">{visitor.site ?? "Unknown"}</Row>
          <Row label="Screen">{context.screen ?? "Unknown"}</Row>
          <Row label="Time zone">{context.timezone ?? "Unknown"}</Row>
          <Row label="Automated">{context.webdriver ? "Yes (webdriver is on)" : "No sign of it"}</Row>
          <Row label="User agent">
            <span className="text-xs text-ink-soft">{userAgent ?? "None sent"}</span>
          </Row>
        </dl>
      </Section>
    </aside>
  );
}
