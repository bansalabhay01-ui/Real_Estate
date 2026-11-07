import { formatDuration, formatPrice, formatRupees } from "../lib/format";

// Plain-language names for the raw bot signals the API reports.
export const HINT_LABELS = {
  webdriver: "Automated browser",
  automation_user_agent: "Bot-like user agent",
  no_browser_languages: "No browser languages",
  no_user_agent: "No user agent",
};

// One line per event for the visitor timeline.
export function describeEvent(event) {
  const p = event.props ?? {};
  switch (event.type) {
    case "page_view":
      return `Opened ${event.path}`;
    case "page_leave":
      return `Left ${event.path} after ${formatDuration(p.duration_ms ?? 0)}, scrolled ${p.max_scroll_pct ?? 0}%`;
    case "scroll_depth":
      return `Scrolled ${p.percent}% down ${event.path}`;
    case "click": {
      const what = p.text ? `"${p.text}"` : p.track || p.tag || "something";
      return `Clicked ${what}${p.trusted === false ? " (a scripted click)" : ""}`;
    }
    case "activity":
      return `${p.mouse_moves ?? 0} mouse moves, ${p.clicks ?? 0} clicks, ${p.keys ?? 0} key presses, ${p.touches ?? 0} touches`;
    case "property_view":
      return `Viewed home ${p.listing_id}`;
    case "emi_used":
      return `Checked the EMI on ${p.listing_id}: ${formatRupees(p.emi ?? 0)} a month over ${p.years} years`;
    case "floorplan_download":
      return `Downloaded the floor plan of ${p.listing_id}`;
    case "enquiry_submitted":
      return `Sent an enquiry about ${p.listing_id}`;
    case "chat_opened":
      return "Opened the assistant";
    case "chat_message":
      return "Wrote to the assistant";
    case "filter_used": {
      const parts = [p.city, p.bhk && `${p.bhk} BHK`, p.max_price && `under ${formatPrice(p.max_price)}`].filter(Boolean);
      return parts.length ? `Filtered homes: ${parts.join(", ")}` : "Cleared the filters";
    }
    default:
      return event.type.replaceAll("_", " ");
  }
}

// What each label means, for the badge's tooltip and the filter row.
export const LABEL_INFO = {
  Hot: "Serious buyer: call first (intent over 70)",
  Warm: "Interested: follow up (intent 40 to 70)",
  Cold: "Just looking so far (intent under 40)",
  Review: "Needs a person to look: mixed or uncertain signals",
  Junk: "Filtered out: fake details, spam, a broker or not a buyer",
  Bot: "Filtered out: automated traffic",
};
export const LABELS = ["Hot", "Warm", "Cold", "Review", "Junk", "Bot"];

const seconds = (value) => (value < 60 ? `${value.toFixed(value < 10 ? 1 : 0)} s` : `${Math.round(value / 60)} min`);
const yesNo = (value) => (value ? "yes" : "no");
const FEATURE_FORMATS = {
  activity_coverage: (value) => `${Math.round(value * 100)}%`,
  mouse_px_per_move: (value) => `${Math.round(value)} px`,
  mouse_moves_per_min: (value) => `${Math.round(value)} a minute`,
  touches_per_min: (value) => `${Math.round(value)} a minute`,
  pages_per_minute: (value) => `${value.toFixed(1)} a minute`,
  median_dwell_s: seconds,
  duration_s: seconds,
  min_fill_s: seconds,
  seconds_to_first_lead: seconds,
  event_gap_cv: (value) => value.toFixed(2),
  scrolls_per_page: (value) => value.toFixed(1),
  webdriver: yesNo,
  automation_ua: yesNo,
  no_user_agent: yesNo,
  timezone_utc: yesNo,
  viewport_matches_screen: yesNo,
  touch_mismatch: yesNo,
  honeypot: yesNo,
  lead_without_pageviews: yesNo,
};

// A model feature's value for this visitor, in words: "62%", "139 px", "4.2 s", "yes".
export function formatFeature(name, value) {
  if (value === null || value === undefined) return "unknown";
  const format = FEATURE_FORMATS[name];
  if (format) return format(value);
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
