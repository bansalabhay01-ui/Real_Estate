import { useEffect, useState } from "react";
import { getStats } from "../lib/api";
import { WS_URL } from "../lib/config";

const MAX_VISITORS = 500;

// Live dashboard data: a snapshot when the WebSocket connects, then visitor and enquiry updates.
// Reconnects on its own (1 s, 2 s, 4 s ... up to 10 s) and gets a fresh snapshot each time.
export function useDashboardFeed() {
  const [visitors, setVisitors] = useState([]); // most recent activity first
  const [leads, setLeads] = useState([]); // newest first
  const [updatedAt, setUpdatedAt] = useState({}); // visitor id -> when it last changed
  const [status, setStatus] = useState("connecting"); // connecting | live | offline
  const [stats, setStats] = useState(null);

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

  return { visitors, leads, updatedAt, status, stats };
}
