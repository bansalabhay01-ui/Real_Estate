import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import ChatWidget from "./ChatWidget";
import { PlanMark } from "./icons";

const navClass = ({ isActive }) =>
  `rounded px-1 py-0.5 ${isActive ? "text-ink underline decoration-marigold decoration-2 underline-offset-8" : "text-ink-soft hover:text-ink"}`;

export default function SiteLayout() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0); // braces matter: scrollTo returns a Promise in newer browsers, and React would treat it as a cleanup
  }, [pathname]);

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
          <Link to="/" className="flex items-center gap-2.5">
            <PlanMark />
            <span className="whitespace-nowrap font-extra-wide text-lg font-bold">LeadOps Realty</span>
            <span className="rounded-full border border-line px-2 text-xs font-medium text-muted">Demo</span>
          </Link>
          <nav aria-label="Main" className="flex items-center gap-5 text-sm font-medium">
            <NavLink to="/" end className={navClass}>
              Homes
            </NavLink>
            <NavLink to="/dashboard" className={navClass}>
              Sales dashboard
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-line bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-6 text-sm text-muted">
          <p>LeadOps Realty is a demo site for the LeadOps project. All homes and prices are fictional.</p>
          <p>
            Visits here are tracked by the LeadOps script.{" "}
            <Link to="/dashboard" className="font-medium text-blueprint underline underline-offset-2">
              Open the sales dashboard
            </Link>{" "}
            to watch your own visit arrive.
          </p>
        </div>
      </footer>

      <ChatWidget />
    </div>
  );
}
