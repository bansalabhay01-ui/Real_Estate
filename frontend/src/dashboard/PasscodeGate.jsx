import { useEffect, useState } from "react";
import { hasDashboardAccess, rememberPasscode } from "../lib/api";

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
    <main className="flex min-h-dvh items-center justify-center bg-ink px-4">
      <form onSubmit={open} className="flex w-full max-w-sm flex-col gap-3 rounded-lg bg-white p-6">
        <h1 className="font-wide text-xl font-semibold">Sales dashboard</h1>
        <p className="text-sm text-muted">This page shows buyers&apos; names and phone numbers, so it needs the team&apos;s passcode.</p>
        <label className="flex flex-col gap-1 text-sm font-medium text-ink-soft">
          Passcode
          <input
            required
            autoFocus
            type="password"
            autoComplete="current-password"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            className="rounded-md border border-line px-3 py-2 text-base text-ink focus:border-blueprint"
          />
        </label>
        {state === "wrong" && (
          <p role="alert" className="text-sm font-medium text-alert">
            That passcode isn&apos;t right.
          </p>
        )}
        <button type="submit" disabled={state === "checking"} className="rounded-md bg-marigold px-4 py-2 font-semibold text-ink hover:bg-[#e09500] disabled:opacity-60">
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
