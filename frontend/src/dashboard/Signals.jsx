import { IconAlert, IconBan, IconBot, IconChat, IconEnquiry, IconEye, IconStrength, IconTest } from "../components/icons";
import { HINT_LABELS, LABEL_INFO } from "./describe";

// Text stays ink; the coloured icon carries the meaning, and every chip has a label (never colour alone).
const TONES = { alert: "text-alert", amber: "text-amber", blue: "text-blueprint", test: "text-muted" };
const ICONS = { alert: IconAlert, amber: IconEnquiry, blue: IconChat, test: IconTest };

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

const LABEL_ICONS = {
  Bot: (props) => <IconBot {...props} />,
  Junk: (props) => <IconBan {...props} />,
  Review: (props) => <IconEye {...props} />,
  Cold: (props) => <IconStrength level={1} {...props} />,
  Warm: (props) => <IconStrength level={2} {...props} />,
  Hot: (props) => <IconStrength level={3} {...props} />,
};
const LABEL_TONES = {
  Bot: "text-alert",
  Junk: "text-alert",
  Review: "text-amber",
  Cold: "text-blueprint",
  Warm: "text-blueprint",
  Hot: "text-blueprint",
};

// The scoring engine's label: an icon that keeps the meaning without colour, plus the word itself.
export function LabelBadge({ label }) {
  if (!label) return <span className="text-xs text-muted">Not scored</span>;
  const Icon = LABEL_ICONS[label];
  const hot = label === "Hot";
  return (
    <span
      title={LABEL_INFO[label]}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-semibold text-ink ${
        hot ? "border-blueprint/40 bg-blueprint-line" : "border-line bg-white"
      }`}
    >
      {Icon && <Icon className={`size-3.5 shrink-0 ${LABEL_TONES[label]}`} />}
      {label}
    </span>
  );
}

// Intent out of 100: the number, then a thin single-hue bar on a lighter track of the same blue.
export function IntentMeter({ value }) {
  if (value == null) return <span className="text-muted">-</span>;
  return (
    <span className="flex items-center gap-2">
      <span className="tabular w-7 text-right font-semibold">{value}</span>
      <span className="block h-1.5 w-16 shrink-0 rounded-full bg-blueprint-line" aria-hidden="true">
        <span className="block h-1.5 rounded-full bg-blueprint" style={{ width: `${Math.min(100, value)}%` }} />
      </span>
      <span className="sr-only">out of 100</span>
    </span>
  );
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
  if (visitor.test_label) chips.push({ key: "test", tone: "test", text: `Test: ${visitor.test_label}` });

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

// The backend's checks on one enquiry: failed ones as alert chips, otherwise a quiet "all passed".
export function LeadChecks({ lead }) {
  const checks = lead.checks ?? [];
  const failed = checks.filter((check) => !check.ok);
  const fill = checks.find((check) => check.check === "fill_time" && check.ok);
  return (
    <ul className="flex flex-wrap gap-1.5">
      {failed.map((check) => (
        <Chip key={check.check} tone="alert">
          {check.text}
        </Chip>
      ))}
      {failed.length === 0 && (
        <li className="text-xs text-muted">
          {checks.length ? "All checks passed" : "Not checked"}
          {fill ? `. ${fill.text}` : ""}
        </li>
      )}
    </ul>
  );
}
