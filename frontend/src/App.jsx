import { Link, Route, Routes } from "react-router";
import SiteLayout from "./components/SiteLayout";
import Dashboard from "./pages/Dashboard";
import Home from "./pages/Home";
import Property from "./pages/Property";

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
        <Route path="*" element={<NotFound />} />
      </Route>
      {/* The sales team's view (never tracked). */}
      <Route path="dashboard" element={<Dashboard />} />
    </Routes>
  );
}
