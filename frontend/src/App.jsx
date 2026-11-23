import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router";
import SiteLayout from "./components/SiteLayout";
import Home from "./pages/Home";
import Landing from "./pages/Landing";
import Privacy from "./pages/Privacy";
import Property from "./pages/Property";

// The sales team's pages load only when they are opened, so the front page and the property site stay light.
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Analytics = lazy(() => import("./pages/Analytics"));

function NotFound() {
  return (
    <div className="mx-auto max-w-[1224px] px-5 pb-36 pt-16 sm:px-8">
      <h1 className="text-title">This page doesn&apos;t exist.</h1>
      <Link to="/demo" className="mt-4 inline-block font-semibold text-blueprint underline underline-offset-2">
        See all homes
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      {/* The LeadOps front page (not tracked). */}
      <Route index element={<Landing />} />
      {/* The demo property site: what buyers see, tracked by the LeadOps script. */}
      <Route element={<SiteLayout />}>
        <Route path="demo" element={<Home />} />
        <Route path="property/:id" element={<Property />} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="*" element={<NotFound />} />
      </Route>
      {/* The sales team's views (never tracked). */}
      <Route
        path="dashboard"
        element={
          <Suspense fallback={<p className="p-8 text-sm text-muted">Opening the dashboard...</p>}>
            <Dashboard />
          </Suspense>
        }
      />
      <Route
        path="dashboard/analytics"
        element={
          <Suspense fallback={<p className="p-8 text-sm text-muted">Opening the analytics...</p>}>
            <Analytics />
          </Suspense>
        }
      />
    </Routes>
  );
}
