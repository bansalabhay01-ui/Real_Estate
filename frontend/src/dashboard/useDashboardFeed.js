import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getDemoStatus, getStats, getVisitors, getVisits } from "../lib/api";
import { WS_URL } from "../lib/config";

const MAX_VISITORS = 500;
const FILTERED_LIMIT = 200;
const LIVE_STATS_MS = 1200; // how often the headline numbers refresh while simulated traffic pours in

// Live dashboard data: a snapshot when the WebSocket connects, then visitor, enquiry and score updates.
// Reconnects on its own (1 s, 2 s, 4 s ... up to 10 s) and gets a fresh snapshot each time.
export function useDashboardFeed() {
  const [visitors, setVisitors] = useState([]); // most recent activity first
  const [leads, setLeads] = useState([]); // newest first
  const [updatedAt, setUpdatedAt] = useState({}); // visitor id -> when it last changed
  const [status, setStatus] = useState("connecting"); // connecting | live | offline
  const [stats, setStats] = useState(null);
  const [hotAlerts, setHotAlerts] = useState([]); // visitors who just turned Hot, newest first
  const [demo, setDemo] = useState(null); // the live demo tools: simulated run, scoreboard, real bot
  const [visits, setVisits] = useState([]); // site visits, soonest first
  const statsLoadedAt = useRef(0);

  const loadStats = useCallback(() => {
    statsLoadedAt.current = Date.now();
    return getStats()
      .then(setStats)
      .catch(() => {});
  }, []);
  const loadVisits = useCallback(
    () =>
      getVisits()
        .then(setVisits)
        .catch(() => {}),
    [],
  );
  const refreshDemo = useCallback(
    () =>
      getDemoStatus()
        .then((data) => setDemo((current) => ({ ...current, ...data })))
        .catch(() => {}),
    [],
  );

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
        refreshDemo();
        loadVisits();
      };
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "snapshot") {
          setVisitors(message.visitors);
          setLeads(message.leads);
          loadStats();
          refreshDemo();
        } else if (message.type === "visitor_update") {
          const visitor = message.visitor;
          setVisitors((current) => [visitor, ...current.filter((item) => item.id !== visitor.id)].slice(0, MAX_VISITORS));
          setUpdatedAt((current) => ({ ...current, [visitor.id]: Date.now() }));
        } else if (message.type === "lead_created") {
          setLeads((current) => [message.lead, ...current.filter((item) => item.id !== message.lead.id)]);
          if (message.lead.source === "assistant_offer") {
            const alert = { visitorId: message.lead.visitor_id, reason: message.lead.message ?? "", at: Date.now(), found: true };
            setHotAlerts((current) => [alert, ...current.filter((item) => item.visitorId !== alert.visitorId)].slice(0, 20));
          }
        } else if (message.type === "score_update") {
          setLeads((current) =>
            current.map((lead) => (lead.visitor_id === message.visitor_id ? { ...lead, label: message.label } : lead)),
          );
          if (message.label === "Hot" && message.previous_label !== "Hot") {
            const alert = { visitorId: message.visitor_id, reason: message.reasons?.[0] ?? "", at: Date.now() };
            setHotAlerts((current) => [alert, ...current.filter((item) => item.visitorId !== alert.visitorId)].slice(0, 20));
          }
        } else if (message.type === "visit_booked" || message.type === "visit_updated") {
          loadVisits();
        } else if (message.type === "simulation_started") {
          setDemo((current) => ({ ...current, running: true, sent: 0, total: message.total, labels: {}, scoreboard: null }));
        } else if (message.type === "simulation_progress") {
          setDemo((current) => ({ ...current, running: true, sent: message.sent, total: message.total, labels: message.labels }));
          if (Date.now() - statsLoadedAt.current > LIVE_STATS_MS) loadStats();
        } else if (message.type === "simulation_done") {
          setDemo((current) => ({ ...current, running: false, scoreboard: message.scoreboard }));
          loadStats();
          refreshDemo();
        } else if (message.type === "bot_started") {
          setDemo((current) => ({ ...current, bot_running: true, bot_result: null }));
        } else if (message.type === "bot_finished") {
          setDemo((current) => ({ ...current, bot_running: false, bot_result: message }));
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
  }, [loadStats, loadVisits, refreshDemo]);

  // Headline numbers come from the API (the list only holds recent visitors).
  useEffect(() => {
    loadStats();
    const timer = setInterval(loadStats, 5000);
    return () => clearInterval(timer);
  }, [loadStats]);

  const dismissHotAlert = useCallback(
    (visitorId) => setHotAlerts((current) => current.filter((item) => item.visitorId !== visitorId)),
    [],
  );

  return { visitors, leads, updatedAt, status, stats, hotAlerts, dismissHotAlert, demo, visits };
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
