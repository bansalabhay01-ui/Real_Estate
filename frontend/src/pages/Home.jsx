import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { openChat } from "../components/ChatWidget";
import Filters from "../components/Filters";
import FloorPlan from "../components/FloorPlan";
import ListingCard from "../components/ListingCard";
import { getListings } from "../lib/api";
import { API_URL } from "../lib/config";
import { formatArea, formatPrice } from "../lib/format";
import { track } from "../lib/leadops";

const FEATURED_ID = "PUN-002";
const NO_FILTERS = { city: "", bhk: 0, maxPrice: 0 };

function Hero({ featured }) {
  return (
    <section className="border-b border-line bg-white">
      <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-12 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] md:py-16">
        <div>
          <h1 className="font-extra-wide text-4xl font-bold tracking-tight sm:text-5xl">See the layout before you visit.</h1>
          <p className="mt-5 max-w-md text-lg text-ink-soft">
            Homes in Pune, Bengaluru, Hyderabad, Mumbai and Noida, each with its floor plan, price and an EMI estimate.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="#homes" className="rounded-md bg-marigold px-5 py-3 font-semibold text-ink hover:bg-[#e09500]">
              Browse homes
            </a>
            <button
              type="button"
              onClick={openChat}
              className="rounded-md border border-ink px-5 py-3 font-semibold text-ink hover:bg-ink hover:text-white"
            >
              Ask the assistant
            </button>
          </div>
        </div>

        <figure>
          <div className="overflow-hidden rounded-lg bg-blueprint">
            <FloorPlan
              bhk={featured?.bhk ?? 3}
              area={featured?.area_sqft ?? 1180}
              animate
              className="block w-full"
              title={featured ? `Floor plan of ${featured.project}` : "Floor plan of a 3 BHK home"}
            />
          </div>
          {featured && (
            <figcaption className="mt-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-sm">
              <span>
                <span className="font-semibold">{featured.project}</span>
                <span className="text-muted">
                  , {featured.locality}, {featured.city}. {featured.bhk} BHK, {formatArea(featured.area_sqft)},{" "}
                  {formatPrice(featured.price_inr)}
                </span>
              </span>
              <Link to={`/property/${featured.id}`} className="font-semibold text-blueprint underline underline-offset-2">
                View this home
              </Link>
            </figcaption>
          )}
        </figure>
      </div>
    </section>
  );
}

export default function Home() {
  const [listings, setListings] = useState(null);
  const [failed, setFailed] = useState(false);
  const [filters, setFilters] = useState(NO_FILTERS);
  const filtersTouched = useRef(false);

  useEffect(() => {
    getListings()
      .then(setListings)
      .catch(() => setFailed(true));
  }, []);

  // Record how visitors narrow their search (once they stop changing filters).
  useEffect(() => {
    if (!filtersTouched.current) return undefined;
    const timer = setTimeout(() => {
      track("filter_used", { city: filters.city || null, bhk: filters.bhk || null, max_price: filters.maxPrice || null });
    }, 800);
    return () => clearTimeout(timer);
  }, [filters]);

  const visible = useMemo(
    () =>
      (listings ?? []).filter(
        (home) =>
          (!filters.city || home.city === filters.city) &&
          (!filters.bhk || home.bhk === filters.bhk) &&
          (!filters.maxPrice || home.price_inr <= filters.maxPrice),
      ),
    [listings, filters],
  );
  const featured = listings?.find((home) => home.id === FEATURED_ID) ?? listings?.[0];
  const filtered = Boolean(filters.city || filters.bhk || filters.maxPrice); // a bare 0 would render as "0"

  const changeFilters = (next) => {
    filtersTouched.current = true;
    setFilters(next);
  };

  return (
    <>
      <Hero featured={featured} />

      <section id="homes" aria-labelledby="homes-heading" className="mx-auto max-w-6xl scroll-mt-4 px-4 py-10">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 id="homes-heading" className="font-wide text-2xl font-semibold">
            Homes for sale
          </h2>
          {listings && (
            <p className="text-sm text-muted">
              {visible.length === listings.length ? `${listings.length} homes` : `${visible.length} of ${listings.length} homes`}
              {filtered && (
                <button
                  type="button"
                  onClick={() => changeFilters(NO_FILTERS)}
                  className="ml-3 font-medium text-blueprint underline underline-offset-2"
                >
                  Clear filters
                </button>
              )}
            </p>
          )}
        </div>

        <div className="mt-6">
          <Filters filters={filters} onChange={changeFilters} />
        </div>

        {failed && (
          <p role="alert" className="mt-8 rounded-md border border-alert/40 bg-white p-4 text-ink">
            The homes couldn&apos;t load. Check that the LeadOps API is running at {API_URL}, then reload this page.
          </p>
        )}
        {!listings && !failed && <p className="mt-8 text-muted">Loading homes...</p>}
        {listings && visible.length === 0 && (
          <div className="mt-8 rounded-md border border-line bg-white p-6">
            <p className="font-medium">No homes match these filters.</p>
            <p className="mt-1 text-sm text-muted">Try a higher budget, another city or any number of bedrooms.</p>
          </div>
        )}
        <ul className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((listing) => (
            <li key={listing.id} className="flex">
              <ListingCard listing={listing} />
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
