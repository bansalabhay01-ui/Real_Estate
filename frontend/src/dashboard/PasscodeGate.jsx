import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router";
import { PlanMark } from "../components/icons";
import { hasDashboardAccess, rememberPasscode } from "../lib/api";

const toolLink = ({ isActive }) =>
  `rounded-full px-3.5 py-1.5 transition-colors ${isActive ? "bg-white/[0.12] text-white" : "text-white/70 hover:text-white"}`;

// The sales team's header, shared by the dashboard and the analytics page. `children` sits at the right (the live status).
export function SalesHeader({ title, children }) {
  return (
    <header data-tone="dark" className="bg-night text-white">
      <div className="mx-auto flex max-w-[1376px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link to="/" className="flex items-center gap-2.5">
          <PlanMark />
          <span className="text-lg font-semibold tracking-[-0.02em]">LeadOps</span>
          <span className="text-white/60">{title}</span>
        </Link>
        <nav aria-label="Sales tools" className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] p-1 text-sm">
          <NavLink to="/dashboard" end className={toolLink}>
            Dashboard
          </NavLink>
          <NavLink to="/dashboard/analytics" className={toolLink}>
            Analytics
          </NavLink>
          <NavLink to="/demo" className={toolLink}>
            Demo site
          </NavLink>
        </nav>
        {children}
      </div>
    </header>
  );
}

// Shown when the backend has a DASHBOARD_PASSCODE and this tab doesn't know it yet.
function PasscodeForm({ onOpen }) {
  const [code, setCode] = useState("");
  const [state, setState] = useState("idle"); // idle | checking | wrong

  async function open(event) {
    event.preventDefault();
    setState("checking");
    rememberPasscode(code.trim());
    if (await hasDashboardAccess()) onOpen();
    else setState("wrong");
  }

  return (
    <main className="hero-glow relative flex min-h-dvh items-center justify-center px-4">
      <div className="drafting-grid pointer-events-none absolute inset-0" aria-hidden="true" />
      <form onSubmit={open} className="relative flex w-full max-w-sm flex-col gap-4 rounded-[22px] bg-white p-7">
        <p className="flex items-center gap-2.5">
          <PlanMark />
          <span className="text-lg font-semibold tracking-[-0.02em]">LeadOps</span>
        </p>
        <h1 className="text-2xl font-medium tracking-[-0.03em]">Sales dashboard</h1>
        <p className="text-sm text-muted">This page shows buyers&apos; names and phone numbers, so it needs the team&apos;s passcode.</p>
        <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-soft">
          Passcode
          <input
            required
            autoFocus
            type="password"
            autoComplete="current-password"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            className="rounded-[12px] border border-line px-3.5 py-2.5 text-base text-ink focus:border-blueprint"
          />
        </label>
        {state === "wrong" && (
          <p role="alert" className="text-sm font-medium text-alert">
            That passcode isn&apos;t right.
          </p>
        )}
        <button
          type="submit"
          disabled={state === "checking"}
          className="rounded-full bg-marigold px-5 py-3 font-medium text-night hover:bg-marigold-deep disabled:opacity-60"
        >
          {state === "checking" ? "Checking..." : "Open the dashboard"}
        </button>
      </form>
    </main>
  );
}

// Everything the sales team sees goes through here.
export default function PasscodeGate({ children }) {
  const [access, setAccess] = useState("checking"); // checking | open | locked

  useEffect(() => {
    hasDashboardAccess().then((allowed) => setAccess(allowed ? "open" : "locked"));
  }, []);

  if (access === "checking") return <p className="p-8 text-sm text-muted">Opening the dashboard...</p>;
  if (access === "locked") return <PasscodeForm onOpen={() => setAccess("open")} />;
  return children;
}
