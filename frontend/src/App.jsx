import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router";
import SiteLayout from "./components/SiteLayout";
import Dashboard from "./pages/Dashboard";
import Home from "./pages/Home";
import Privacy from "./pages/Privacy";
import Property from "./pages/Property";

// The charts are the heaviest code here, so buyers on the demo site never download them.
const Analytics = lazy(() => import("./pages/Analytics"));

function NotFound() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-16">
      <h1 className="font-wide text-2xl font-semibold">This page doesn&apos;t exist.</h1>
      <Link to="/" className="mt-4 inline-block font-semibold text-blueprint underline underline-offset-2">
        See all homes
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      {/* The demo property site: what buyers see, tracked by the LeadOps script. */}
      <Route element={<SiteLayout />}>
        <Route index element={<Home />} />
        <Route path="property/:id" element={<Property />} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="*" element={<NotFound />} />
      </Route>
      {/* The sales team's views (never tracked). */}
      <Route path="dashboard" element={<Dashboard />} />
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
