import { useRef, useState } from "react";
import { clearSimulated, rescoreEveryone, runBot, startSimulation } from "../lib/api";
import { LABELS } from "./describe";
import { LabelBadge } from "./Signals";

const KIND_NAMES = {
  "bot/scraper": "Scrapers",
  "bot/slow_scraper": "Slow scrapers",
  "bot/form_bot": "Form bots",
  "bot/click_bot": "Click bots",
  "bot/stealth_form": "Stealth bots",
  "junk/fake_details": "Fake details",
  "junk/broker": "Rival brokers",
  "junk/spam": "Spam",
  "junk/tenant": "Renters",
  "genuine/serious": "Serious buyers",
  "genuine/casual": "Casual browsers",
};
const BOT_KINDS = { stealth: "Stealth bot", naive: "Naive form bot", scraper: "Scraper" };
const FIELDS = [
  ["bots", "Bots", 500],
  ["junk", "Junk leads", 200],
  ["genuine", "Real buyers", 200],
];

function LabelCounts({ labels }) {
  const shown = LABELS.filter((label) => labels?.[label]);
  if (shown.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-sm">
      {shown.map((label) => (
        <li key={label} className="flex items-center gap-1.5">
          <LabelBadge label={label} />
          <span className="tabular font-semibold">{labels[label]}</span>
        </li>
      ))}
    </ul>
  );
}

function Result({ value, total, text }) {
  return (
    <div className="rounded-[16px] border border-line px-4 py-3">
      <p className="tabular text-3xl font-medium tracking-[-0.03em]">
        {value}
        <span className="text-lg font-normal text-muted">/{total}</span>
      </p>
      <p className="mt-0.5 text-sm text-ink-soft">{text}</p>
    </div>
  );
}

function Scoreboard({ board }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <Result value={board.bots_blocked} total={board.bots_total} text="bots blocked" />
        <Result value={board.junk_filtered} total={board.junk_total} text="junk leads filtered" />
        <Result value={board.genuine_kept} total={board.genuine_total} text="real buyers kept" />
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm text-ink-soft">
        <span>Real buyers, sorted by intent:</span>
        <LabelCounts labels={board.genuine_labels} />
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer font-medium text-blueprint">How each kind of visitor was labelled</summary>
        <div className="relative mt-2 overflow-x-auto">
          <table className="w-full min-w-[520px] text-left">
            <thead className="border-b border-line text-muted">
              <tr>
                <th scope="col" className="py-1.5 pr-3 font-medium">Visitor</th>
                {LABELS.map((label) => (
                  <th key={label} scope="col" className="px-2 py-1.5 text-right font-medium">{label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {board.kinds.map((row) => (
                <tr key={row.kind} className="border-b border-line/70 last:border-0">
                  <th scope="row" className="py-1.5 pr-3 font-normal">{KIND_NAMES[row.kind] ?? row.kind}</th>
                  {LABELS.map((label) => (
                    <td key={label} className={`tabular px-2 py-1.5 text-right ${row.labels[label] ? "font-semibold" : "text-muted"}`}>
                      {row.labels[label] ?? 0}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

// The live attack demo: send a burst of labelled traffic or a real bot, and watch the dashboard sort it.
export default function SimulateTraffic({ demo, stats }) {
  const dialogRef = useRef(null);
  const [numbers, setNumbers] = useState({ bots: 200, junk: 30, genuine: 20 });
  const [botKind, setBotKind] = useState("stealth");
  const [problem, setProblem] = useState(null);
  const [clearing, setClearing] = useState(false);
  const [relabelled, setRelabelled] = useState(false);

  const running = Boolean(demo?.running);
  const botRunning = Boolean(demo?.bot_running);
  const percent = demo?.total ? Math.round((demo.sent / demo.total) * 100) : 0;

  async function attempt(work) {
    setProblem(null);
    try {
      await work();
    } catch (error) {
      setProblem(error.message);
    }
  }

  function start(event) {
    event.preventDefault();
    dialogRef.current?.close();
    attempt(() => startSimulation({ ...numbers, seconds: 30 }));
  }

  async function clear() {
    setClearing(true);
    await attempt(clearSimulated);
    setClearing(false);
  }

  // After retraining: load the new model and label everyone again.
  function relabel() {
    attempt(async () => {
      await rescoreEveryone();
      setRelabelled(true);
      setTimeout(() => setRelabelled(false), 4000);
    });
  }

  const buttonOutline = "rounded-full border border-ink px-4 py-2 text-sm font-medium hover:bg-night hover:text-white disabled:border-line disabled:text-muted disabled:hover:bg-transparent";

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={running}
          onClick={() => dialogRef.current?.showModal()}
          className="rounded-full bg-marigold px-5 py-2 text-sm font-medium text-night hover:bg-marigold-deep disabled:opacity-60"
        >
          {running ? "Simulating..." : "Simulate traffic"}
        </button>

        <div className="flex items-center gap-2">
          <label htmlFor="bot-kind" className="sr-only">
            Which bot to run
          </label>
          <select
            id="bot-kind"
            value={botKind}
            disabled={!demo?.bot_available || botRunning}
            onChange={(event) => setBotKind(event.target.value)}
            className="rounded-full border border-line bg-white px-3 py-2 text-sm disabled:text-muted"
          >
            {Object.entries(BOT_KINDS).map(([kind, name]) => (
              <option key={kind} value={kind}>
                {name}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={!demo?.bot_available || botRunning}
            onClick={() => attempt(() => runBot(botKind, window.location.origin))}
            className={buttonOutline}
          >
            {botRunning ? "Bot running..." : "Run a real bot"}
          </button>
        </div>

        {demo?.simulated_visitors > 0 && (
          <button
            type="button"
            disabled={running || clearing}
            onClick={clear}
            className="text-sm font-medium text-blueprint underline underline-offset-2 hover:text-blueprint-deep disabled:text-muted"
          >
            {clearing ? "Clearing..." : `Clear ${demo.simulated_visitors} simulated visitors`}
          </button>
        )}
      </div>

      {demo && !demo.bot_available && (
        <p className="text-xs text-muted">Real bots run only on a laptop with the training packages (ml/requirements.txt) installed.</p>
      )}
      {problem && (
        <p role="alert" className="text-sm font-medium text-alert">
          {problem}
        </p>
      )}
      {demo?.bot_result && (
        <p role="status" className={`text-sm ${demo.bot_result.ok ? "text-ink-soft" : "text-alert"}`}>
          <span className="font-semibold">{BOT_KINDS[demo.bot_result.kind] ?? "Bot"}: </span>
          {demo.bot_result.summary}
        </p>
      )}

      {running && (
        <div className="flex flex-col gap-2">
          <p role="status" className="text-sm">
            Sent <span className="tabular font-semibold">{demo.sent}</span> of <span className="tabular font-semibold">{demo.total}</span> visitors
          </p>
          <div
            role="progressbar"
            aria-label="Simulated visitors sent"
            aria-valuemin={0}
            aria-valuemax={demo.total}
            aria-valuenow={demo.sent}
            className="h-2 rounded-full bg-blueprint-line"
          >
            <div className="h-2 rounded-full bg-blueprint transition-[width] duration-300" style={{ width: `${percent}%` }} />
          </div>
          <LabelCounts labels={demo.labels} />
        </div>
      )}

      {!running && demo?.scoreboard && <Scoreboard board={demo.scoreboard} />}

      {stats && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-3 text-xs text-muted">
          <span>
            Human-check model <span className="font-medium text-ink-soft">{stats.model_version}</span>
            {stats.model_verdicts > 0
              ? `, learned from ${stats.model_verdicts} sales ${stats.model_verdicts === 1 ? "verdict" : "verdicts"}`
              : ""}
          </span>
          <button type="button" onClick={relabel} className="font-medium text-blueprint underline underline-offset-2 hover:text-blueprint-deep">
            {relabelled ? "Relabelling..." : "Relabel everyone"}
          </button>
        </div>
      )}

      <dialog
        ref={dialogRef}
        aria-labelledby="simulate-heading"
        className="m-auto w-[min(420px,calc(100vw-2rem))] rounded-[22px] border border-line bg-white p-6 text-ink backdrop:bg-night/60"
      >
        <form onSubmit={start} className="flex flex-col gap-4">
          <div>
            <h3 id="simulate-heading" className="text-xl font-medium tracking-[-0.02em]">
              Simulate traffic
            </h3>
            <p className="mt-1 text-sm text-muted">The visitors arrive over about 30 seconds and are sorted as they come in.</p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {FIELDS.map(([key, label, max]) => (
              <label key={key} className="flex flex-col gap-1 text-sm font-medium text-ink-soft">
                {label}
                <input
                  type="number"
                  min={0}
                  max={max}
                  required
                  value={numbers[key]}
                  onChange={(event) => setNumbers((current) => ({ ...current, [key]: Number(event.target.value) }))}
                  className="tabular w-full rounded-[10px] border border-line px-2.5 py-1.5 text-base text-ink focus:border-blueprint"
                />
              </label>
            ))}
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => dialogRef.current?.close()} className="rounded-full border border-line px-4 py-2 text-sm hover:bg-concrete">
              Cancel
            </button>
            <button type="submit" className="rounded-full bg-marigold px-5 py-2 text-sm font-medium text-night hover:bg-marigold-deep">
              Start
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
