import { IconAlert, IconChat, IconEnquiry } from "../components/icons";
import { formatDuration } from "../lib/format";
import { FAST_FILL_MS, HINT_LABELS } from "./describe";

// Text stays ink; the coloured icon carries the meaning, and every chip has a label (never colour alone).
const TONES = { alert: "text-alert", amber: "text-amber", blue: "text-blueprint" };
const ICONS = { alert: IconAlert, amber: IconEnquiry, blue: IconChat };

export function Chip({ tone, children }) {
  const Icon = ICONS[tone];
  return (
    <li className="inline-flex items-center gap-1 rounded-full border border-line bg-white px-2 py-0.5 text-xs font-medium text-ink">
      <Icon className={`size-3.5 shrink-0 ${TONES[tone]}`} />
      {children}
    </li>
  );
}

export function shortId(id) {
  return id.startsWith("nosdk-") ? `no-sdk ${id.slice(6, 12)}` : id.slice(0, 8);
}

export function SignalChips({ visitor }) {
  const chips = visitor.automation_hints.map((hint) => ({ key: hint, tone: "alert", text: HINT_LABELS[hint] ?? hint }));
  if (visitor.lead_count > 0 && visitor.page_views === 0) {
    chips.push({ key: "no-browsing", tone: "alert", text: "Enquiry without browsing" });
  }
  if (visitor.lead_count > 0) {
    chips.push({ key: "lead", tone: "amber", text: visitor.lead_count === 1 ? "Enquiry" : `${visitor.lead_count} enquiries` });
  }
  if (visitor.chat_count > 0) chips.push({ key: "chat", tone: "blue", text: "Chatted" });

  if (chips.length === 0) return <span className="text-muted">None yet</span>;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {chips.map((chip) => (
        <Chip key={chip.key} tone={chip.tone}>
          {chip.text}
        </Chip>
      ))}
    </ul>
  );
}

// Bot checks on one enquiry: the hidden honeypot field and how fast the form was filled in.
export function LeadChecks({ lead }) {
  const fill = lead.form_fill_ms;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {lead.honeypot && <Chip tone="alert">Hidden field filled in</Chip>}
      {!fill ? (
        <Chip tone="alert">Sent without typing</Chip>
      ) : fill < FAST_FILL_MS ? (
        <Chip tone="alert">Filled in {formatDuration(fill)}</Chip>
      ) : (
        <li className="text-xs text-muted">Filled in {formatDuration(fill)}</li>
      )}
    </ul>
  );
}
