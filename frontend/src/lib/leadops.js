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
  script.dataset.excludePaths = "/dashboard"; // the sales team using the dashboard aren't visitors
  document.head.appendChild(script);
}

// Custom events. Calls made before the script has loaded are queued and sent once it has.
export function track(name, props = {}) {
  if (window.LeadOps) window.LeadOps.track(name, props);
  else (window.__leadopsQueue ||= []).push(["track", name, props]);
}

// The anonymous visitor and session IDs, sent with enquiries and chat so the backend can link them.
export function visitorIds() {
  return window.LeadOps ? window.LeadOps.ids() : { visitor_id: null, session_id: null };
}
