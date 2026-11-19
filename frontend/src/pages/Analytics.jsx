import { useEffect, useState } from "react";
import { Link } from "react-router";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PlanMark } from "../components/icons";
import { LABEL_INFO, LABELS } from "../dashboard/describe";
import PasscodeGate from "../dashboard/PasscodeGate";
import { LabelBadge } from "../dashboard/Signals";
import { getAnalytics } from "../lib/api";

const PERIODS = [7, 14, 30];
// Checked with the colour-blind validator in this order. Amber is lighter than 3:1 on white, so the table repeats every value.
const SERIES = [
  { key: "kept", name: "People worth a call", color: "#1d4f91" },
  { key: "junk", name: "Junk leads", color: "#d9920f" },
  { key: "bots", name: "Bots", color: "#b4232a" },
];
const STACK = SERIES.map((series) => series.key);
const AXIS_TEXT = { fontSize: 12, fill: "#5b6773" };

const dayName = (day) => new Date(`${day}T12:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
const percent = (part, whole) => (whole ? Math.round((part / whole) * 100) : 0);

function Tile({ label, value, note }) {
  return (
    <div className="rounded-lg border border-line bg-white px-4 py-3">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="mt-1 text-3xl font-semibold">{value}</dd>
      <dd className="mt-1 text-xs text-muted">{note}</dd>
    </div>
  );
}

function Card({ id, title, note, children }) {
  return (
    <section aria-labelledby={id} className="min-w-0 rounded-lg border border-line bg-white p-4">
      <h2 id={id} className="font-wide text-lg font-semibold">
        {title}
      </h2>
      {note && <p className="mt-0.5 text-sm text-muted">{note}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

// A name, a bar and a figure per row, the bars on one baseline so they compare exactly.
function BarList({ rows, largest }) {
  return (
    <ul className="flex flex-col gap-3">
      {rows.map((row) => (
        <li key={row.key}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span>{row.name}</span>
            <span className="tabular font-semibold">{row.count.toLocaleString("en-IN")}</span>
          </div>
          <div className="mt-1 h-2 rounded-full bg-blueprint-line" aria-hidden="true">
            <div className="h-2 rounded-full bg-blueprint" style={{ width: `${largest ? Math.max(row.count ? 1 : 0, (row.count / largest) * 100) : 0}%` }} />
          </div>
          {row.note && <p className="mt-1 text-xs text-muted">{row.note}</p>}
        </li>
      ))}
    </ul>
  );
}

// One stacked segment. Only the top of the column is rounded; the white stroke is the 2px gap between segments.
function segment(key) {
  return function Segment({ x, y, width, height, fill, payload }) {
    if (!height || height <= 0) return null;
    const hasMoreAbove = STACK.slice(STACK.indexOf(key) + 1).some((name) => payload[name] > 0);
    const r = hasMoreAbove ? 0 : Math.min(4, width / 2, height);
    const shape = `M${x},${y + height}V${y + r}Q${x},${y} ${x + r},${y}H${x + width - r}Q${x + width},${y} ${x + width},${y + r}V${y + height}Z`;
    return <path d={shape} fill={fill} stroke="#ffffff" strokeWidth={2} />;
  };
}

function DayTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-md border border-line bg-white px-3 py-2 text-sm shadow-lg">
      <p className="mb-1 text-xs text-muted">{label}</p>
      <ul className="flex flex-col gap-0.5">
        {[...SERIES].reverse().map((series) => (
          <li key={series.key} className="flex items-center gap-2">
            <span className="inline-block h-0.5 w-3 rounded" style={{ background: series.color }} aria-hidden="true" />
            <span className="tabular font-semibold">{row[series.key]}</span>
            <span className="text-ink-soft">{series.name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DailyChart({ daily }) {
  const rows = daily.map((day) => ({ ...day, label: dayName(day.day) }));
  const total = (key) => rows.reduce((sum, row) => sum + row[key], 0);
  const summary = `Visitors per day: ${total("kept")} people worth a call, ${total("junk")} junk leads and ${total("bots")} bots over ${rows.length} days.`;
  return (
    <>
      <ul className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-soft">
        {SERIES.map((series) => (
          <li key={series.key} className="flex items-center gap-1.5">
            <span className="inline-block size-2.5 rounded-sm" style={{ background: series.color }} aria-hidden="true" />
            {series.name}
          </li>
        ))}
      </ul>
      <div role="img" aria-label={summary} className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: -18 }} barCategoryGap="30%">
            <CartesianGrid vertical={false} stroke="#e8ebee" />
            <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: "#d9dee3" }} tick={AXIS_TEXT} minTickGap={18} />
            <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={AXIS_TEXT} />
            <Tooltip content={<DayTooltip />} cursor={{ fill: "#f3f5f6" }} isAnimationActive={false} />
            {SERIES.map((series) => (
              <Bar key={series.key} dataKey={series.key} name={series.name} stackId="day" fill={series.color} maxBarSize={24} shape={segment(series.key)} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-medium text-blueprint">Show these numbers as a table</summary>
        <div className="relative mt-2 max-h-72 overflow-auto">
          <table className="w-full text-left">
            <thead className="border-b border-line text-muted">
              <tr>
                <th scope="col" className="py-1.5 pr-3 font-medium">Day</th>
                {SERIES.map((series) => (
                  <th key={series.key} scope="col" className="px-2 py-1.5 text-right font-medium">{series.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.day} className="border-b border-line/70 last:border-0">
                  <th scope="row" className="py-1.5 pr-3 font-normal">{row.label}</th>
                  {SERIES.map((series) => (
                    <td key={series.key} className="tabular px-2 py-1.5 text-right">{row[series.key]}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}

function Report({ data }) {
  const [visitors, people, contacts, hot] = data.funnel;
  const funnel = [
    { key: visitors.step, name: visitors.label, count: visitors.count },
    { key: people.step, name: people.label, count: people.count, note: `${percent(people.count, visitors.count)}% of all visitors` },
    { key: contacts.step, name: contacts.label, count: contacts.count, note: `${percent(contacts.count, people.count)}% of real people left real details` },
    { key: hot.step, name: hot.label, count: hot.count, note: `${percent(hot.count, contacts.count)}% of real contacts are Hot` },
  ];
  const labelRows = LABELS.map((label) => ({ key: label, name: <LabelBadge label={label} />, count: data.labels[label] ?? 0, note: LABEL_INFO[label] }));
  const largestLabel = Math.max(...labelRows.map((row) => row.count), 0);

  return (
    <>
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile
          label="Enquiries filtered out"
          value={`${percent(data.enquiries_filtered, data.enquiries)}%`}
          note={`${data.enquiries_filtered} of ${data.enquiries} came from bots or junk leads`}
        />
        <Tile label="Sales hours saved (estimate)" value={data.hours_saved} note={`Assumes ${data.minutes_per_enquiry} minutes for each filtered enquiry`} />
        <Tile label="Found by the assistant" value={data.found_by_assistant} note={`${data.offers_accepted} of ${data.offers_sent} offers accepted`} />
        <Tile label="Site visits requested" value={data.site_visits} note="Booked through the assistant or by sales" />
      </dl>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card id="funnel-heading" title="From visitor to hot lead" note="Each step narrows the one before.">
          <BarList rows={funnel} largest={visitors.count} />
        </Card>
        <Card id="labels-heading" title="Visitors by label" note="How LeadOps sorted everyone in this period.">
          <BarList rows={labelRows} largest={largestLabel} />
        </Card>
      </div>

      <div className="mt-6">
        <Card id="daily-heading" title="Visitors per day" note="By the day each visitor first arrived.">
          <DailyChart daily={data.daily} />
        </Card>
      </div>
    </>
  );
}

function AnalyticsPage() {
  const [days, setDays] = useState(14);
  const [simulated, setSimulated] = useState(true);
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading"); // loading | ready | failed

  useEffect(() => {
    document.title = "Analytics | LeadOps";
    return () => {
      document.title = "LeadOps Realty (demo)";
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    getAnalytics({ days, simulated }).then(
      (answer) => {
        if (cancelled) return;
        setData(answer);
        setState("ready");
      },
      () => !cancelled && setState("failed"),
    );
    return () => {
      cancelled = true;
    };
  }, [days, simulated]);

  const link = "font-medium text-white/80 underline-offset-4 hover:text-white hover:underline";
  return (
    <div className="min-h-dvh">
      <header className="bg-ink text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <PlanMark />
            <span className="font-extra-wide text-lg font-bold">LeadOps</span>
            <span className="text-white/70">Analytics</span>
          </div>
          <nav aria-label="Sales tools" className="flex items-center gap-5 text-sm">
            <Link to="/dashboard" className={link}>
              Sales dashboard
            </Link>
            <Link to="/" className={link}>
              Open the demo site
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <div className="mb-5 flex flex-wrap items-center gap-x-6 gap-y-3">
          <div role="group" aria-label="Period" className="flex gap-1.5">
            {PERIODS.map((period) => (
              <button
                key={period}
                type="button"
                aria-pressed={days === period}
                onClick={() => setDays(period)}
                className={`rounded-full border px-3 py-1 text-sm ${days === period ? "border-blueprint bg-blueprint text-white" : "border-line bg-white hover:bg-concrete"}`}
              >
                Last {period} days
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={simulated} onChange={(event) => setSimulated(event.target.checked)} className="accent-blueprint" />
            Include simulated traffic
          </label>
        </div>

        {state === "failed" && !data && <p className="text-sm">The analytics couldn&apos;t load. Check that the API is running.</p>}
        {data && data.visitors === 0 && (
          <p className="rounded-lg border border-line bg-white px-4 py-10 text-center text-sm text-muted">
            No visitors in this period yet. Press Simulate traffic on the{" "}
            <Link to="/dashboard" className="font-medium text-blueprint underline underline-offset-2">
              sales dashboard
            </Link>
            .
          </p>
        )}
        {data && data.visitors > 0 && (
          <div className={`transition-opacity ${state === "loading" ? "opacity-60" : ""}`}>
            <Report data={data} />
          </div>
        )}
      </main>
    </div>
  );
}

export default function Analytics() {
  return (
    <PasscodeGate>
      <AnalyticsPage />
    </PasscodeGate>
  );
}
