import { useEffect } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import ChatWidget from "./ChatWidget";
import ConsentBanner from "./ConsentBanner";
import { PlanMark } from "./icons";
import { Container } from "./ui";

const navClass = ({ isActive }) =>
  `rounded-full px-3.5 py-1.5 transition-colors ${isActive ? "bg-night text-white" : "text-ink-soft hover:bg-concrete hover:text-ink"}`;

// The demo property site: a builder's website with the LeadOps script on it.
export default function SiteLayout() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0); // braces matter: scrollTo returns a Promise in newer browsers, and React would treat it as a cleanup
  }, [pathname]);

  return (
    <div className="flex min-h-dvh flex-col bg-concrete">
      <header className="sticky top-0 z-30 border-b border-line/80 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1224px] items-center justify-between gap-3 px-5 sm:px-8">
          <Link to="/demo" className="flex items-center gap-2.5">
            <PlanMark />
            <span className="whitespace-nowrap text-[17px] font-semibold tracking-[-0.02em]">LeadOps Realty</span>
            <span className="hidden rounded-full border border-line px-2 text-xs text-muted sm:inline">Demo</span>
          </Link>
          <nav aria-label="Main" className="flex items-center gap-1 whitespace-nowrap rounded-full border border-line bg-white p-1 text-sm font-medium">
            <NavLink to="/demo" end className={navClass}>
              Homes
            </NavLink>
            <NavLink to="/dashboard" className={navClass}>
              <span className="sm:hidden">Dashboard</span>
              <span className="hidden sm:inline">Sales dashboard</span>
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer data-tone="dark" className="relative z-10 -mt-8 rounded-t-[28px] bg-night text-white sm:-mt-10 sm:rounded-t-[40px]">
        <Container className="flex flex-col gap-6 py-12 text-sm sm:flex-row sm:items-end sm:justify-between">
          <div className="max-w-md">
            <p className="flex items-center gap-2.5 font-semibold">
              <PlanMark className="size-6" />
              LeadOps Realty
            </p>
            <p className="mt-3 text-white/70">
              A demo site for the LeadOps project: every home and price here is fictional. If you agree, your visit is tracked by
              the LeadOps script, and you can watch it arrive on the sales dashboard.
            </p>
          </div>
          <ul className="flex flex-wrap gap-x-6 gap-y-2 text-white/75">
            <li>
              <Link to="/" reloadDocument className="hover:text-white">
                How LeadOps works
              </Link>
            </li>
            <li>
              <Link to="/dashboard" className="hover:text-white">
                Sales dashboard
              </Link>
            </li>
            <li>
              <Link to="/privacy" className="hover:text-white">
                Privacy notice
              </Link>
            </li>
          </ul>
        </Container>
      </footer>

      <ChatWidget />
      <ConsentBanner />
    </div>
  );
}
