import { API_URL } from "./config";
import { visitorIds } from "./leadops";

const PASSCODE_KEY = "leadops_dashboard_passcode";

// The dashboard's passcode lasts as long as this browser tab, and is only ever sent to the LeadOps API.
export function dashboardPasscode() {
  try {
    return window.sessionStorage.getItem(PASSCODE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function rememberPasscode(code) {
  try {
    window.sessionStorage.setItem(PASSCODE_KEY, code);
  } catch {
    // storage blocked: the dashboard asks again next time
  }
}

async function request(path, { method = "GET", body, headers = {} } = {}) {
  const passcode = dashboardPasscode();
  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(passcode ? { "X-LeadOps-Passcode": passcode } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    const text = typeof problem?.detail === "string" ? problem.detail : `${method} ${path} failed with status ${response.status}`;
    throw Object.assign(new Error(text), { status: response.status });
  }
  return response.json();
}

let listingsRequest = null;
export function getListings() {
  listingsRequest ||= request("/listings").catch((error) => {
    listingsRequest = null; // let the next call try again
    throw error;
  });
  return listingsRequest;
}

export const getListing = (id) => request(`/listings/${encodeURIComponent(id)}`);

export const sendLead = (fields) => request("/leads", { method: "POST", body: { ...visitorIds(), ...fields } });

export const sendChat = (message, listingId) =>
  request("/chat", { method: "POST", body: { ...visitorIds(), message, listing_id: listingId ?? null } });

export const getChatHistory = (visitorId) => request(`/chat/${encodeURIComponent(visitorId)}`);

export const bookVisit = (fields) => request("/visits", { method: "POST", body: { ...visitorIds(), ...fields } });
export const getVisits = () => request("/visits?limit=100");
export const updateVisit = (id, change) => request(`/visits/${id}`, { method: "PATCH", body: change });

export const getVisitor = (id) => request(`/visitors/${encodeURIComponent(id)}`);

// { label: "Hot" | undefined, sort: "recent" | "intent", limit }
export function getVisitors({ label, sort = "recent", limit = 200 } = {}) {
  const params = new URLSearchParams({ sort, limit: String(limit) });
  if (label) params.set("label", label);
  return request(`/visitors?${params}`);
}

export const getStats = () => request("/stats");
export const getBrief = (visitorId) => request(`/visitors/${encodeURIComponent(visitorId)}/brief`);
export const draftFollowUp = (visitorId, fields) => request(`/visitors/${encodeURIComponent(visitorId)}/followup`, { method: "POST", body: fields });
export const sendVerdict = (fields) => request("/feedback", { method: "POST", body: fields });
export const sendOffer = (visitorId) => request(`/visitors/${encodeURIComponent(visitorId)}/nudge`, { method: "POST" });

// The live demo tools on the dashboard.
export const rescoreEveryone = () => request("/scoring/rescore", { method: "POST" });

// Privacy and the phone check.
export const getHealth = () => request("/health");
export const verifyPhone = (leadId, token, code) => request(`/leads/${leadId}/verify`, { method: "POST", body: { token, code } });
export const eraseVisitor = (visitorId) => request(`/visitors/${encodeURIComponent(visitorId)}`, { method: "DELETE" });
export const eraseMyData = (visitorId) =>
  request(`/visitors/${encodeURIComponent(visitorId)}`, { method: "DELETE", headers: { "X-LeadOps-Visitor": visitorId } });

// False only when the API says the passcode is missing or wrong.
export async function hasDashboardAccess() {
  try {
    await request("/auth/check");
    return true;
  } catch (error) {
    return error.status !== 401;
  }
}

export const getDemoStatus = () => request("/demo/status");
export const startSimulation = (numbers) => request("/demo/simulate", { method: "POST", body: numbers });
export const clearSimulated = () => request("/demo/simulated", { method: "DELETE" });
export const runBot = (kind, site) => request("/demo/bot", { method: "POST", body: { kind, site } });
