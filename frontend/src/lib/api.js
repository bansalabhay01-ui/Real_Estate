import { API_URL } from "./config";
import { visitorIds } from "./leadops";

async function request(path, { method = "GET", body } = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new Error(`${method} ${path} failed with status ${response.status}`);
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

export const getVisitor = (id) => request(`/visitors/${encodeURIComponent(id)}`);

// { label: "Hot" | undefined, sort: "recent" | "intent", limit }
export function getVisitors({ label, sort = "recent", limit = 200 } = {}) {
  const params = new URLSearchParams({ sort, limit: String(limit) });
  if (label) params.set("label", label);
  return request(`/visitors?${params}`);
}

export const getStats = () => request("/stats");
