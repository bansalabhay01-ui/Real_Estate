import { API_URL } from "./config";

// Loads the LeadOps tracking script: the same one any website adds with a single <script> tag.
export function loadTracker() {
  if (document.getElementById("leadops-sdk")) return;
  const script = document.createElement("script");
  script.id = "leadops-sdk";
  script.src = `${API_URL}/sdk/leadops.js`;
  script.async = true;
  script.dataset.api = API_URL;
  script.dataset.site = "leadops-realty-demo";
  // The sales team using the dashboard aren't visitors, and the LeadOps front page ("/" exactly) isn't the property site.
  script.dataset.excludePaths = "/dashboard,/$";
  script.dataset.consent = "required"; // nothing is sent until the visitor accepts the banner
  document.head.appendChild(script);
}

// The visitor's answer to the consent banner: "granted", "denied" or null when they haven't been asked yet.
export function consentChoice() {
  try {
    return window.localStorage.getItem("leadops_consent");
  } catch {
    return null;
  }
}

export function answerConsent(granted) {
  if (window.LeadOps) window.LeadOps.consent(granted);
  else (window.__leadopsQueue ||= []).push(["consent", granted]);
}

// Custom events. Calls made before the script has loaded are queued and sent once it has.
export function track(name, props = {}) {
  if (window.LeadOps) window.LeadOps.track(name, props);
  else (window.__leadopsQueue ||= []).push(["track", name, props]);
}

// Offers from the assistant for serious anonymous visitors (the smart engagement trigger).
export function onNudge(handler) {
  if (window.LeadOps) window.LeadOps.onNudge(handler);
  else (window.__leadopsQueue ||= []).push(["onNudge", handler]);
}

// The anonymous visitor and session IDs, sent with enquiries and chat so the backend can link them.
export function visitorIds() {
  return window.LeadOps ? window.LeadOps.ids() : { visitor_id: null, session_id: null };
}
