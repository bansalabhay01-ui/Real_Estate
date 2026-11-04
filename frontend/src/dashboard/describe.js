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

// An enquiry filled in faster than a person can type is a strong bot signal.
export const FAST_FILL_MS = 3000;
