import { useEffect, useState } from "react";
import { dayChoices } from "../components/ContactCapture";
import { bookVisit, draftFollowUp, getBrief, sendOffer, sendVerdict } from "../lib/api";
import { OFFER_NAMES } from "./describe";

const URGENCY = {
  now: { text: "Do this now", tone: "border-blueprint bg-blueprint-line" },
  today: { text: "Today", tone: "border-amber/50 bg-[#fdf3e1]" },
  this_week: { text: "This week", tone: "border-line bg-concrete" },
  none: { text: "No rush", tone: "border-line bg-concrete" },
};
const VERDICTS = [
  ["genuine", "Genuine"],
  ["fake", "Fake"],
  ["converted", "Converted"],
];
const LANGUAGES = [
  ["auto", "Buyer's language"],
  ["en", "English"],
  ["hinglish", "Hinglish"],
  ["hi", "Hindi"],
  ["mr", "Marathi"],
];
const OFFER_STATUS = { pending: "waiting for their next page activity", sent: "sent", shown: "shown", accepted: "accepted", dismissed: "turned down" };
const SLOTS = [
  ["morning", "Morning"],
  ["afternoon", "Afternoon"],
  ["evening", "Evening"],
];

const smallButton = "rounded-md border border-line bg-white px-2.5 py-1.5 text-sm font-medium hover:bg-concrete disabled:text-muted";
const mainButton = "rounded-md bg-ink px-3 py-1.5 text-sm font-semibold text-white hover:bg-ink-soft disabled:opacity-60";

function Problem({ children }) {
  return children ? (
    <p role="alert" className="mt-1.5 text-sm text-alert">
      {children}
    </p>
  ) : null;
}

// Pick a channel and language, edit the draft, then send it from WhatsApp or email.
function FollowUp({ visitorId }) {
  const [channel, setChannel] = useState("whatsapp");
  const [language, setLanguage] = useState("auto");
  const [draft, setDraft] = useState(null);
  const [text, setText] = useState("");
  const [state, setState] = useState("loading"); // loading | ready | failed
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    draftFollowUp(visitorId, { channel, language }).then(
      (data) => {
        if (cancelled) return;
        setDraft(data);
        setText(data.text);
        setState("ready");
      },
      () => !cancelled && setState("failed"),
    );
    return () => {
      cancelled = true;
    };
  }, [visitorId, channel, language]);

  async function copy() {
    await navigator.clipboard?.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  const whatsapp = draft?.whatsapp_number ? `https://wa.me/${draft.whatsapp_number}?text=${encodeURIComponent(text)}` : null;
  const email = draft?.email ? `mailto:${draft.email}?subject=${encodeURIComponent(draft.subject)}&body=${encodeURIComponent(text)}` : null;
  return (
    <div className="mt-2 flex flex-col gap-2 rounded-md border border-line p-3">
      <div className="flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Send by" className="flex overflow-hidden rounded-md border border-line text-sm">
          {[["whatsapp", "WhatsApp"], ["email", "Email"]].map(([value, name]) => (
            <button
              key={value}
              type="button"
              aria-pressed={channel === value}
              onClick={() => setChannel(value)}
              className={`px-2.5 py-1 ${channel === value ? "bg-blueprint text-white" : "bg-white hover:bg-concrete"}`}
            >
              {name}
            </button>
          ))}
        </div>
        <label className="sr-only" htmlFor="followup-language">
          Language of the message
        </label>
        <select
          id="followup-language"
          value={language}
          onChange={(event) => setLanguage(event.target.value)}
          className="rounded-md border border-line bg-white px-2 py-1 text-sm"
        >
          {LANGUAGES.map(([value, name]) => (
            <option key={value} value={value}>
              {name}
            </option>
          ))}
        </select>
      </div>

      {state === "failed" ? (
        <Problem>The draft couldn&apos;t be written. Try again.</Problem>
      ) : (
        <>
          <label className="sr-only" htmlFor="followup-text">
            The message
          </label>
          <textarea
            id="followup-text"
            rows={6}
            value={state === "loading" ? "Writing a draft..." : text}
            readOnly={state === "loading"}
            onChange={(event) => setText(event.target.value)}
            className="w-full rounded-md border border-line px-2.5 py-2 text-sm focus:border-blueprint"
          />
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={state !== "ready"} onClick={copy} className={smallButton}>
              {copied ? "Copied" : "Copy"}
            </button>
            {channel === "whatsapp" && whatsapp && (
              <a href={whatsapp} target="_blank" rel="noreferrer" className={mainButton}>
                Open in WhatsApp
              </a>
            )}
            {channel === "email" && email && (
              <a href={email} className={mainButton}>
                Open in email
              </a>
            )}
          </div>
          {channel === "whatsapp" && draft && !whatsapp && <p className="text-xs text-muted">No valid mobile number yet, so copy the message instead.</p>}
          {channel === "email" && draft && !email && <p className="text-xs text-muted">This buyer hasn&apos;t shared an email address.</p>}
        </>
      )}
    </div>
  );
}

function BookVisit({ visitorId, listingId, onBooked }) {
  const [choices] = useState(() => dayChoices(null));
  const [day, setDay] = useState(() => (choices.find((choice) => choice.saturday) ?? choices[0]).value);
  const [slot, setSlot] = useState("morning");
  const [state, setState] = useState("idle"); // idle | sending
  const [problem, setProblem] = useState(null);

  async function book() {
    setState("sending");
    setProblem(null);
    try {
      await bookVisit({ visitor_id: visitorId, session_id: null, listing_id: listingId, day, slot, source: "dashboard" });
      onBooked();
    } catch (error) {
      setProblem(error.message);
    }
    setState("idle");
  }

  return (
    <div className="mt-2 rounded-md border border-line p-3">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs font-medium text-ink-soft">
          Day
          <select value={day} onChange={(event) => setDay(event.target.value)} className="rounded-md border border-line bg-white px-2 py-1 text-sm">
            {choices.map((choice) => (
              <option key={choice.value} value={choice.value}>
                {choice.text}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-ink-soft">
          Time
          <select value={slot} onChange={(event) => setSlot(event.target.value)} className="rounded-md border border-line bg-white px-2 py-1 text-sm">
            {SLOTS.map(([value, name]) => (
              <option key={value} value={value}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" disabled={state === "sending"} onClick={book} className={mainButton}>
          {state === "sending" ? "Booking..." : "Book the visit"}
        </button>
      </div>
      <Problem>{problem}</Problem>
    </div>
  );
}

export function VerdictButtons({ visitorId, leadId, current, onSaved }) {
  const [problem, setProblem] = useState(null);
  const [note, setNote] = useState("");

  async function save(label) {
    setProblem(null);
    try {
      await sendVerdict({ visitor_id: visitorId, lead_id: leadId ?? null, label, note: note.trim() || null });
      setNote("");
      onSaved?.();
    } catch {
      setProblem("That verdict couldn't be saved. Try again.");
    }
  }

  return (
    <div>
      <div role="group" aria-label="Sales verdict" className="flex flex-wrap items-center gap-1.5">
        {VERDICTS.map(([value, name]) => (
          <button
            key={value}
            type="button"
            aria-pressed={current === value}
            onClick={() => save(value)}
            className={`rounded-full border px-3 py-1 text-sm ${
              current === value ? "border-blueprint bg-blueprint text-white" : "border-line bg-white hover:bg-concrete"
            }`}
          >
            {name}
          </button>
        ))}
      </div>
      <label className="sr-only" htmlFor={`verdict-note-${leadId ?? visitorId}`}>
        A note about this verdict
      </label>
      <input
        id={`verdict-note-${leadId ?? visitorId}`}
        value={note}
        onChange={(event) => setNote(event.target.value)}
        maxLength={300}
        placeholder="Add a note (optional)"
        className="mt-2 w-full rounded-md border border-line px-2.5 py-1.5 text-sm focus:border-blueprint"
      />
      <Problem>{problem}</Problem>
    </div>
  );
}

// Anonymous Warm or Hot visitors can be sent the assistant's offer by hand.
function OfferControl({ visitor, nudges, onSent }) {
  const [state, setState] = useState("idle"); // idle | sending | failed
  const latest = nudges[0];
  const canSend = visitor.lead_count === 0 && ["Warm", "Hot"].includes(visitor.label) && latest?.status !== "pending";
  if (!canSend && !latest) return null;

  function send() {
    setState("sending");
    sendOffer(visitor.id).then(
      () => {
        setState("idle");
        onSent();
      },
      () => setState("failed"),
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm">
      {latest && (
        <p>
          Offer: {OFFER_NAMES[latest.kind] ?? "an offer"} <span className="text-muted">({OFFER_STATUS[latest.status] ?? latest.status})</span>
        </p>
      )}
      {canSend && (
        <button type="button" disabled={state === "sending"} onClick={send} className={smallButton}>
          {state === "sending" ? "Sending..." : "Send an offer now"}
        </button>
      )}
      {state === "failed" && <Problem>The offer couldn&apos;t be sent. Try again.</Problem>}
    </div>
  );
}

// The top of a lead's panel: what to know, what to do next, and the tools to do it.
export default function LeadBrief({ detail, onChanged }) {
  const { visitor, leads, nudges = [], site_visits: visits = [] } = detail;
  const [brief, setBrief] = useState(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(null); // followup | visit | null
  const score = visitor.score?.intent_score;
  const verdict = visitor.feedback?.label;

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    getBrief(visitor.id).then(
      (data) => !cancelled && setBrief(data),
      () => !cancelled && setFailed(true),
    );
    return () => {
      cancelled = true;
    };
  }, [visitor.id, visitor.label, score, verdict, visits.length, leads.length]);

  const hasContact = leads.some((lead) => lead.checks?.some((check) => check.check === "phone" && check.ok));
  const filteredOut = ["Bot", "Junk"].includes(visitor.label);
  const listingId = leads.find((lead) => lead.listing_id)?.listing_id ?? visits[0]?.listing_id ?? visitor.last_path?.match(/^\/property\/([A-Za-z0-9-]+)/)?.[1];
  const step = brief?.next_step;
  const urgency = URGENCY[step?.urgency] ?? URGENCY.none;
  const toggle = (name) => setOpen((current) => (current === name ? null : name));

  return (
    <section aria-label="Lead brief" className="flex flex-col gap-3">
      {failed && <Problem>The brief couldn&apos;t load.</Problem>}
      {brief && (
        <>
          <ul className="flex flex-col gap-1 text-sm">
            {brief.lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className={`rounded-md border px-3 py-2 text-sm ${urgency.tone}`}>
            <span className="block text-xs font-semibold text-ink-soft">{urgency.text}</span>
            <span className="font-semibold">{step.text}</span>
          </p>
        </>
      )}

      {!filteredOut && (
        <div>
          <div className="flex flex-wrap gap-2">
            <button type="button" aria-expanded={open === "followup"} onClick={() => toggle("followup")} className={smallButton}>
              Draft a follow-up
            </button>
            {hasContact && listingId && (
              <button type="button" aria-expanded={open === "visit"} onClick={() => toggle("visit")} className={smallButton}>
                Book a site visit
              </button>
            )}
          </div>
          {open === "followup" && <FollowUp visitorId={visitor.id} />}
          {open === "visit" && (
            <BookVisit
              visitorId={visitor.id}
              listingId={listingId}
              onBooked={() => {
                setOpen(null);
                onChanged();
              }}
            />
          )}
        </div>
      )}

      <OfferControl visitor={visitor} nudges={nudges} onSent={onChanged} />

      <div>
        <h3 className="mb-1.5 text-sm font-semibold text-ink-soft">Your verdict</h3>
        <VerdictButtons visitorId={visitor.id} current={verdict} onSaved={onChanged} />
        {visitor.feedback?.note && <p className="mt-1.5 text-xs text-muted">Note: {visitor.feedback.note}</p>}
      </div>
    </section>
  );
}
