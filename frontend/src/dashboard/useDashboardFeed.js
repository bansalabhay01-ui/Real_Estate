import { useCallback, useEffect, useMemo, useState } from "react";
import { getStats, getVisitors } from "../lib/api";
import { WS_URL } from "../lib/config";

const MAX_VISITORS = 500;
const FILTERED_LIMIT = 200;

// Live dashboard data: a snapshot when the WebSocket connects, then visitor, enquiry and score updates.
// Reconnects on its own (1 s, 2 s, 4 s ... up to 10 s) and gets a fresh snapshot each time.
export function useDashboardFeed() {
  const [visitors, setVisitors] = useState([]); // most recent activity first
  const [leads, setLeads] = useState([]); // newest first
  const [updatedAt, setUpdatedAt] = useState({}); // visitor id -> when it last changed
  const [status, setStatus] = useState("connecting"); // connecting | live | offline
  const [stats, setStats] = useState(null);
  const [hotAlerts, setHotAlerts] = useState([]); // visitors who just turned Hot, newest first

  useEffect(() => {
    let socket;
    let retryTimer;
    let attempts = 0;
    let stopped = false;

    function connect() {
      socket = new WebSocket(`${WS_URL}/ws/dashboard`);
      socket.onopen = () => {
        attempts = 0;
        setStatus("live");
      };
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "snapshot") {
          setVisitors(message.visitors);
          setLeads(message.leads);
        } else if (message.type === "visitor_update") {
          const visitor = message.visitor;
          setVisitors((current) => [visitor, ...current.filter((item) => item.id !== visitor.id)].slice(0, MAX_VISITORS));
          setUpdatedAt((current) => ({ ...current, [visitor.id]: Date.now() }));
        } else if (message.type === "lead_created") {
          setLeads((current) => [message.lead, ...current.filter((item) => item.id !== message.lead.id)]);
        } else if (message.type === "score_update") {
          setLeads((current) =>
            current.map((lead) => (lead.visitor_id === message.visitor_id ? { ...lead, label: message.label } : lead)),
          );
          if (message.label === "Hot" && message.previous_label !== "Hot") {
            const alert = { visitorId: message.visitor_id, reason: message.reasons?.[0] ?? "", at: Date.now() };
            setHotAlerts((current) => [alert, ...current.filter((item) => item.visitorId !== alert.visitorId)].slice(0, 20));
          }
        }
      };
      socket.onclose = () => {
        if (stopped) return;
        setStatus("offline");
        attempts += 1;
        retryTimer = setTimeout(connect, Math.min(1000 * 2 ** (attempts - 1), 10_000));
      };
      socket.onerror = () => socket.close();
    }

    connect();
    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      socket?.close();
    };
  }, []);

  // Headline numbers come from the API (the list only holds recent visitors).
  useEffect(() => {
    let cancelled = false;
    const load = () =>
      getStats()
        .then((data) => !cancelled && setStats(data))
        .catch(() => {});
    load();
    const timer = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const dismissHotAlert = useCallback(
    (visitorId) => setHotAlerts((current) => current.filter((item) => item.visitorId !== visitorId)),
    [],
  );

  return { visitors, leads, updatedAt, status, stats, hotAlerts, dismissHotAlert };
}

const byRecent = (a, b) => Date.parse(b.last_seen) - Date.parse(a.last_seen);
const byIntent = (a, b) => (b.score?.intent_score ?? -1) - (a.score?.intent_score ?? -1) || byRecent(a, b);

// The visitors table for a label filter and a sort order. "All, latest first" is the live list itself; anything
// else is fetched from the API (so it covers every visitor, not just recent ones) and then kept current with the
// live updates: a visitor that changed after the fetch is added, moved or dropped as its label now says.
export function useFilteredVisitors(filter, sort, live, updatedAt) {
  const usesLive = filter === "All" && sort === "recent";
  const key = `${filter}|${sort}`;
  const [fetched, setFetched] = useState({ key: null, at: 0, items: [], failed: false });

  useEffect(() => {
    if (usesLive) return undefined;
    let cancelled = false;
    const at = Date.now();
    getVisitors({ label: filter === "All" ? undefined : filter, sort, limit: FILTERED_LIMIT })
      .then((items) => !cancelled && setFetched({ key, at, items, failed: false }))
      .catch(() => !cancelled && setFetched({ key, at, items: [], failed: true }));
    return () => {
      cancelled = true;
    };
  }, [key, usesLive, filter, sort]);

  return useMemo(() => {
    if (usesLive) return { visitors: live, loading: false, failed: false, capped: false };
    if (fetched.key !== key) return { visitors: [], loading: true, failed: false, capped: false };
    const byId = new Map(fetched.items.map((visitor) => [visitor.id, visitor]));
    for (const visitor of live) {
      if ((updatedAt[visitor.id] ?? 0) <= fetched.at) continue; // unchanged since the fetch
      if (filter === "All" || visitor.label === filter) byId.set(visitor.id, visitor);
      else byId.delete(visitor.id);
    }
    const visitors = [...byId.values()].sort(sort === "intent" ? byIntent : byRecent);
    return { visitors, loading: false, failed: fetched.failed, capped: fetched.items.length >= FILTERED_LIMIT };
  }, [usesLive, live, fetched, key, filter, sort, updatedAt]);
}
