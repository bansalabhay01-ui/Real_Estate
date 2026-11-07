import { useEffect, useState } from "react";
import { Link } from "react-router";
import { PlanMark } from "../components/icons";
import { LABEL_INFO, LABELS } from "../dashboard/describe";
import { IntentMeter, LabelBadge, LeadChecks, shortId, SignalChips } from "../dashboard/Signals";
import { useDashboardFeed, useFilteredVisitors } from "../dashboard/useDashboardFeed";
import VisitorDetail from "../dashboard/VisitorDetail";
import { profilePhrases, timeAgo } from "../lib/format";

const STATUS = {
  connecting: { text: "Connecting...", dot: "bg-white/50" },
  live: { text: "Live", dot: "bg-[#4cc38a]" },
  offline: { text: "Offline, reconnecting...", dot: "bg-[#f07178]" },
};
const HOT_ALERT_MS = 12_000;

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

// One row of filters above the table it scopes: a label (with how many visitors have it) and the sort order.
function VisitorFilters({ filter, onFilter, sort, onSort, stats }) {
  const counts = stats?.labels ?? {};
  const options = [["All", stats?.visitors], ...LABELS.map((label) => [label, counts[label] ?? 0])];
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-2.5">
      <div role="group" aria-label="Show visitors with this label" className="flex flex-wrap gap-1.5">
        {options.map(([name, count]) => {
          const selected = filter === name;
          return (
            <button
              key={name}
              type="button"
              aria-pressed={selected}
              onClick={() => onFilter(name)}
              title={name === "All" ? "Every visitor" : LABEL_INFO[name]}
              className={`rounded-full border px-3 py-1 text-sm ${
                selected ? "border-blueprint bg-blueprint text-white" : "border-line bg-white text-ink hover:bg-concrete"
              }`}
            >
              {name} <span className={`tabular ${selected ? "text-white/80" : "text-muted"}`}>{count ?? "-"}</span>
            </button>
          );
        })}
      </div>
      <label className="flex items-center gap-2 text-sm text-muted">
        Sort
        <select
          value={sort}
          onChange={(event) => onSort(event.target.value)}
          className="rounded border border-line bg-white px-2 py-1 text-ink"
        >
          <option value="recent">Latest activity</option>
          <option value="intent">Highest intent</option>
        </select>
      </label>
    </div>
  );
}

function VisitorsTable({ visitors, filter, loading, failed, updatedAt, selectedId, onSelect, now }) {
  if (failed) {
    return <p className="px-4 py-6 text-sm">These visitors couldn&apos;t load. Check that the API is running.</p>;
  }
  if (loading) return <p className="px-4 py-6 text-sm text-muted">Loading visitors...</p>;
  if (visitors.length === 0 && filter !== "All") {
    return <p className="px-4 py-6 text-sm text-muted">No visitors labelled {filter} yet.</p>;
  }
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
      <table className="w-full min-w-[780px] text-left text-sm">
        <thead className="border-b border-line text-muted">
          <tr>
            <th scope="col" className={th}>Visitor</th>
            <th scope="col" className={th}>Label</th>
            <th scope="col" className={th}>Intent</th>
            <th scope="col" className={th}>Last seen</th>
            <th scope="col" className={th}>Details</th>
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
                <td className={td}>
                  <LabelBadge label={visitor.label} />
                  {visitor.score?.reasons?.[0] && (
                    <div className="mt-1 max-w-[220px] text-xs text-muted">{visitor.score.reasons[0]}</div>
                  )}
                </td>
                <td className={`${td} whitespace-nowrap`}>
                  <IntentMeter value={visitor.score?.intent_score} />
                </td>
                <td className={`${td} whitespace-nowrap`}>
                  {timeAgo(visitor.last_seen, now)}
                  <div className="max-w-[160px] truncate text-xs text-muted">{visitor.last_path ?? ""}</div>
                </td>
                <td className={`${td} min-w-[180px]`}>
                  {profilePhrases(visitor.profile).length > 0 && (
                    <p className="mb-1.5">{profilePhrases(visitor.profile).join(", ")}</p>
                  )}
                  <SignalChips visitor={visitor} />
                </td>
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
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-b border-line text-muted">
          <tr>
            <th scope="col" className={th}>Received</th>
            <th scope="col" className={th}>Label</th>
            <th scope="col" className={th}>Name</th>
            <th scope="col" className={th}>Mobile</th>
            <th scope="col" className={th}>Home</th>
            <th scope="col" className={th}>Visitor</th>
            <th scope="col" className={th}>Checks</th>
          </tr>
        </thead>
        <tbody>
          {leads.map((lead) => (
            <tr key={lead.id} className="border-b border-line/70 align-top last:border-0">
              <td className={`${td} whitespace-nowrap`}>{timeAgo(lead.created_at, now)}</td>
              <td className={td}>
                <LabelBadge label={lead.label} />
              </td>
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

// A short alert when someone turns Hot: the newest one, with how many more arrived at the same time.
function HotAlert({ alerts, onView, onDismiss }) {
  const [latest, ...others] = alerts;
  const latestId = latest?.visitorId;
  useEffect(() => {
    if (!latestId) return undefined;
    const timer = setTimeout(() => onDismiss(latestId), HOT_ALERT_MS);
    return () => clearTimeout(timer);
  }, [latestId, onDismiss]);

  return (
    <div role="status" aria-live="polite" className="fixed bottom-4 right-4 z-20 w-[min(360px,calc(100vw-2rem))]">
      {latest && (
        <div className="rounded-lg border border-blueprint/40 bg-white p-4 shadow-lg">
          <p className="flex flex-wrap items-center gap-2 font-semibold">
            <LabelBadge label="Hot" /> New hot lead: visitor {shortId(latest.visitorId)}
          </p>
          {latest.reason && <p className="mt-1 text-sm text-ink-soft">{latest.reason}</p>}
          {others.length > 0 && (
            <p className="mt-1 text-xs text-muted">
              and {others.length} more just turned Hot (filter by Hot to see them all)
            </p>
          )}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => {
                onView(latest.visitorId);
                onDismiss(latest.visitorId);
              }}
              className="rounded bg-blueprint px-3 py-1.5 text-sm font-semibold text-white hover:bg-blueprint-deep"
            >
              View
            </button>
            <button
              type="button"
              onClick={() => onDismiss(latest.visitorId)}
              className="rounded border border-line px-3 py-1.5 text-sm hover:bg-concrete"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const { visitors, leads, updatedAt, status, stats, hotAlerts, dismissHotAlert } = useDashboardFeed();
  const [selectedId, setSelectedId] = useState(null);
  const [now, setNow] = useState(() => Date.now());
  const [filter, setFilter] = useState("All");
  const [sort, setSort] = useState("recent");
  const shown = useFilteredVisitors(filter, sort, visitors, updatedAt);

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

  const order = sort === "intent" ? "Highest intent first." : "Most recent activity first.";
  const note = shown.capped ? `${order} Showing the first 200.` : `${order} Rows update as people browse.`;

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
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <StatTile label="Visitors" value={stats?.visitors} />
          <StatTile label="Active in the last 2 minutes" value={stats?.active_now} />
          <StatTile label="Enquiries" value={stats?.leads} />
          <StatTile label="Hot right now" value={stats ? (stats.labels?.Hot ?? 0) : undefined} />
          <StatTile
            label="Filtered out: bots and junk"
            value={stats ? (stats.labels?.Bot ?? 0) + (stats.labels?.Junk ?? 0) : undefined}
          />
        </dl>

        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div className="flex min-w-0 flex-col gap-6">
            <Panel id="visitors-heading" title="Visitors" note={note}>
              <VisitorFilters filter={filter} onFilter={setFilter} sort={sort} onSort={setSort} stats={stats} />
              <VisitorsTable
                visitors={shown.visitors}
                filter={filter}
                loading={shown.loading}
                failed={shown.failed}
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
      <HotAlert alerts={hotAlerts} onView={setSelectedId} onDismiss={dismissHotAlert} />
    </div>
  );
}
