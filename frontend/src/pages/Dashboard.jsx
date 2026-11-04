import { useEffect, useState } from "react";
import { Link } from "react-router";
import { PlanMark } from "../components/icons";
import { LeadChecks, shortId, SignalChips } from "../dashboard/Signals";
import { useDashboardFeed } from "../dashboard/useDashboardFeed";
import VisitorDetail from "../dashboard/VisitorDetail";
import { profilePhrases, timeAgo } from "../lib/format";

const STATUS = {
  connecting: { text: "Connecting...", dot: "bg-white/50" },
  live: { text: "Live", dot: "bg-[#4cc38a]" },
  offline: { text: "Offline, reconnecting...", dot: "bg-[#f07178]" },
};

function StatTile({ label, value }) {
  return (
    <div className="rounded-lg border border-line bg-white px-4 py-3">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="tabular mt-1 text-3xl font-semibold">{value ?? "-"}</dd>
    </div>
  );
}

function Panel({ id, title, note, children }) {
  return (
    <section aria-labelledby={id} className="min-w-0 rounded-lg border border-line bg-white">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-4 py-3">
        <h2 id={id} className="font-wide text-lg font-semibold">
          {title}
        </h2>
        {note && <p className="text-sm text-muted">{note}</p>}
      </div>
      {children}
    </section>
  );
}

const th = "px-3 py-2 font-medium first:pl-4 last:pr-4";
const td = "px-3 py-2.5 first:pl-4 last:pr-4";

function VisitorsTable({ visitors, updatedAt, selectedId, onSelect, now }) {
  if (visitors.length === 0) {
    return (
      <div className="px-4 py-10 text-center text-sm">
        <p className="font-medium">No visitors yet.</p>
        <p className="mt-1 text-muted">
          Open the{" "}
          <Link to="/" className="font-medium text-blueprint underline underline-offset-2">
            demo site
          </Link>{" "}
          in another tab, or send simulated traffic with{" "}
          <code className="rounded bg-concrete px-1">python ml/simulator.py --send http://localhost:8000</code>
        </p>
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] text-left text-sm">
        <thead className="border-b border-line text-muted">
          <tr>
            <th scope="col" className={th}>Visitor</th>
            <th scope="col" className={th}>Last seen</th>
            <th scope="col" className={`${th} text-right`}>Pages</th>
            <th scope="col" className={`${th} text-right`}>Events</th>
            <th scope="col" className={th}>Buyer details</th>
            <th scope="col" className={th}>Signals</th>
            <th scope="col" className={th}>Label</th>
          </tr>
        </thead>
        <tbody>
          {visitors.map((visitor) => {
            const changed = updatedAt[visitor.id];
            const selected = visitor.id === selectedId;
            return (
              <tr
                key={`${visitor.id}-${changed ?? 0}`} // a new key replays the highlight on every update
                onClick={() => onSelect(visitor.id)}
                className={`cursor-pointer border-b border-line/70 align-top last:border-0 ${
                  selected ? "bg-blueprint-line" : "hover:bg-concrete"
                } ${changed && !selected ? "row-flash" : ""}`}
              >
                <td className={td}>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(visitor.id);
                    }}
                    className="font-semibold text-blueprint hover:underline"
                  >
                    {shortId(visitor.id)}
                  </button>
                  <div className="max-w-[150px] truncate text-xs text-muted" title={visitor.site ?? undefined}>
                    {visitor.device}
                    {visitor.site ? `, ${visitor.site}` : ""}
                  </div>
                </td>
                <td className={`${td} whitespace-nowrap`}>
                  {timeAgo(visitor.last_seen, now)}
                  <div className="max-w-[180px] truncate text-xs text-muted">{visitor.last_path ?? ""}</div>
                </td>
                <td className={`${td} tabular text-right`}>{visitor.page_views}</td>
                <td className={`${td} tabular text-right`}>{visitor.event_count}</td>
                <td className={`${td} min-w-[140px]`}>
                  {profilePhrases(visitor.profile).join(", ") || <span className="text-muted">None yet</span>}
                </td>
                <td className={td}>
                  <SignalChips visitor={visitor} />
                </td>
                <td className={`${td} whitespace-nowrap text-muted`}>{visitor.label ?? "Not scored"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function LeadsTable({ leads, onSelect, now }) {
  if (leads.length === 0) {
    return <p className="px-4 py-6 text-sm text-muted">No enquiries yet. They appear here the moment a form is sent.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="border-b border-line text-muted">
          <tr>
            <th scope="col" className={th}>Received</th>
            <th scope="col" className={th}>Name</th>
            <th scope="col" className={th}>Mobile</th>
            <th scope="col" className={th}>Home</th>
            <th scope="col" className={th}>Visitor</th>
            <th scope="col" className={th}>Bot checks</th>
          </tr>
        </thead>
        <tbody>
          {leads.map((lead) => (
            <tr key={lead.id} className="border-b border-line/70 align-top last:border-0">
              <td className={`${td} whitespace-nowrap`}>{timeAgo(lead.created_at, now)}</td>
              <td className={`${td} font-medium`}>{lead.name}</td>
              <td className={`${td} tabular`}>{lead.phone}</td>
              <td className={td}>{lead.listing_id ?? "-"}</td>
              <td className={td}>
                <button
                  type="button"
                  onClick={() => onSelect(lead.visitor_id)}
                  className="font-semibold text-blueprint hover:underline"
                >
                  {shortId(lead.visitor_id)}
                </button>
              </td>
              <td className={td}>
                <LeadChecks lead={lead} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Dashboard() {
  const { visitors, leads, updatedAt, status, stats } = useDashboardFeed();
  const [selectedId, setSelectedId] = useState(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 15_000); // keeps "2 min ago" current
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    document.title = "Sales dashboard | LeadOps";
    return () => {
      document.title = "LeadOps Realty (demo)";
    };
  }, []);

  return (
    <div className="min-h-dvh">
      <header className="bg-ink text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <PlanMark />
            <span className="font-extra-wide text-lg font-bold">LeadOps</span>
            <span className="text-white/70">Sales dashboard</span>
          </div>
          <div className="flex items-center gap-5 text-sm">
            <span className="flex items-center gap-2" role="status">
              <span className={`size-2.5 rounded-full ${STATUS[status].dot}`} aria-hidden="true" />
              {STATUS[status].text}
            </span>
            <Link to="/" className="font-medium text-white/80 underline-offset-4 hover:text-white hover:underline">
              Open the demo site
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile label="Visitors" value={stats?.visitors} />
          <StatTile label="Active in the last 2 minutes" value={stats?.active_now} />
          <StatTile label="Enquiries" value={stats?.leads} />
          <StatTile label="Talked to the assistant" value={stats?.chatting_visitors} />
        </dl>

        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div className="flex min-w-0 flex-col gap-6">
            <Panel id="visitors-heading" title="Visitors" note="Most recent activity first. Rows update as people browse.">
              <VisitorsTable
                visitors={visitors}
                updatedAt={updatedAt}
                selectedId={selectedId}
                onSelect={setSelectedId}
                now={now}
              />
            </Panel>
            <Panel id="leads-heading" title="Enquiries" note="Newest first">
              <LeadsTable leads={leads} onSelect={setSelectedId} now={now} />
            </Panel>
          </div>
          <VisitorDetail
            visitorId={selectedId}
            version={selectedId ? updatedAt[selectedId] : 0}
            onClose={() => setSelectedId(null)}
          />
        </div>
      </main>
    </div>
  );
}
