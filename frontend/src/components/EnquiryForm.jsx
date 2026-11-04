import { useId, useRef, useState } from "react";
import { sendLead } from "../lib/api";
import { track } from "../lib/leadops";
import { IconCheck } from "./icons";

const inputClass =
  "w-full rounded-md border border-line bg-white px-3 py-2 text-base text-ink placeholder:text-muted focus:border-blueprint";

function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1 text-sm font-medium text-ink-soft">
      {label}
      {children}
    </label>
  );
}

export default function EnquiryForm({ listing }) {
  const [fields, setFields] = useState({
    name: "",
    phone: "",
    email: "",
    message: `I'm interested in ${listing.project}. Please call me.`,
    consent: false,
    website: "", // the honeypot
  });
  const [status, setStatus] = useState("idle"); // idle | sending | sent | error
  const startedAt = useRef(null); // first touch of the form, for the fill-time signal
  const headingId = useId();

  const update = (key) => (event) => {
    startedAt.current ??= Date.now();
    const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
    setFields((current) => ({ ...current, [key]: value }));
  };

  async function submit(event) {
    event.preventDefault();
    setStatus("sending");
    try {
      await sendLead({
        listing_id: listing.id,
        name: fields.name.trim(),
        phone: fields.phone.trim(),
        email: fields.email.trim() || null,
        message: fields.message.trim() || null,
        consent: fields.consent,
        honeypot: fields.website,
        form_fill_ms: startedAt.current ? Date.now() - startedAt.current : 0,
        client_ts: Date.now(),
        page_url: window.location.href,
      });
      track("enquiry_submitted", { listing_id: listing.id });
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  }

  if (status === "sent") {
    return (
      <section aria-live="polite" className="rounded-lg border border-line bg-white p-5">
        <p className="flex items-center gap-2 font-wide text-lg font-semibold">
          <IconCheck className="size-5 text-ok" />
          Enquiry sent
        </p>
        <p className="mt-2 text-ink-soft">
          Thanks, {fields.name.trim()}. Our sales team will call you on {fields.phone.trim()} about {listing.project}.
        </p>
      </section>
    );
  }

  return (
    <section id="enquiry" aria-labelledby={headingId} className="rounded-lg border border-line bg-white p-5">
      <h2 id={headingId} className="font-wide text-lg font-semibold">
        Talk to the sales team
      </h2>
      <p className="mt-1 text-sm text-muted">We&apos;ll call you back, usually within a day.</p>

      <form onSubmit={submit} className="relative mt-4 flex flex-col gap-3">
        <Field label="Your name">
          <input required autoComplete="name" value={fields.name} onChange={update("name")} className={inputClass} />
        </Field>
        <Field label="Mobile number">
          <input
            required
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            pattern="[0-9+ \-]{10,15}"
            title="A 10-digit mobile number"
            value={fields.phone}
            onChange={update("phone")}
            className={inputClass}
          />
        </Field>
        <Field label="Email (optional)">
          <input type="email" autoComplete="email" value={fields.email} onChange={update("email")} className={inputClass} />
        </Field>
        <Field label="Message">
          <textarea rows={3} value={fields.message} onChange={update("message")} className={inputClass} />
        </Field>

        {/* Honeypot: hidden from people and screen readers. Form bots fill in every field they find. */}
        <div aria-hidden="true" className="absolute -left-[9999px] top-0 h-px w-px overflow-hidden">
          <label>
            Website
            <input type="text" name="website" tabIndex={-1} autoComplete="off" value={fields.website} onChange={update("website")} />
          </label>
        </div>

        <label className="flex items-start gap-2 text-sm text-ink-soft">
          <input required type="checkbox" checked={fields.consent} onChange={update("consent")} className="mt-1 accent-blueprint" />
          You can call or WhatsApp me about this home.
        </label>

        {status === "error" && (
          <p role="alert" className="text-sm font-medium text-alert">
            The enquiry didn&apos;t go through. Check your connection and send it again.
          </p>
        )}
        <button
          type="submit"
          disabled={status === "sending"}
          className="mt-1 rounded-md bg-marigold px-4 py-2.5 font-semibold text-ink transition-colors hover:bg-[#e09500] disabled:opacity-60"
        >
          {status === "sending" ? "Sending..." : "Send enquiry"}
        </button>
      </form>
    </section>
  );
}
