import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { openChat } from "../components/ChatWidget";
import Filters from "../components/Filters";
import FloorPlan from "../components/FloorPlan";
import ListingCard from "../components/ListingCard";
import { Button, Eyebrow, Rule } from "../components/ui";
import { getListings } from "../lib/api";
import { API_URL } from "../lib/config";
import { formatArea, formatPrice } from "../lib/format";
import { track } from "../lib/leadops";

const FEATURED_ID = "PUN-002";
const NO_FILTERS = { city: "", bhk: 0, maxPrice: 0 };

function Hero({ featured }) {
  return (
    <section data-tone="dark" className="hero-glow relative overflow-hidden text-white">
      <div className="drafting-grid pointer-events-none absolute inset-0" aria-hidden="true" />
      <div className="relative mx-auto grid max-w-[1224px] items-center gap-12 px-5 pb-28 pt-16 sm:px-8 md:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] md:pb-36 md:pt-24">
        <div>
          <Eyebrow className="text-white/60">Homes in Pune, Bengaluru, Hyderabad, Mumbai and Noida</Eyebrow>
          <h1 className="text-section mt-5">See the layout before you visit.</h1>
          <p className="text-lede mt-6 max-w-md text-white/75">Every home comes with its floor plan, its price and an EMI estimate.</p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Button href="#homes" tone="marigold" size="lg">
              Browse homes
            </Button>
            <Button onClick={openChat} tone="outline-dark" size="lg">
              Ask the assistant
            </Button>
          </div>
        </div>

        <figure>
          <div className="overflow-hidden rounded-[22px] border border-white/10 bg-blueprint shadow-[0_40px_90px_-40px_rgb(0_0_0/0.8)]">
            <FloorPlan
              bhk={featured?.bhk ?? 3}
              area={featured?.area_sqft ?? 1180}
              animate
              className="block w-full"
              title={featured ? `Floor plan of ${featured.project}` : "Floor plan of a 3 BHK home"}
            />
          </div>
          {featured && (
            <figcaption className="mt-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-sm">
              <span>
                <span className="font-medium">{featured.project}</span>
                <span className="text-white/65">
                  , {featured.locality}, {featured.city}. {featured.bhk} BHK, {formatArea(featured.area_sqft)},{" "}
                  {formatPrice(featured.price_inr)}
                </span>
              </span>
              <Link to={`/property/${featured.id}`} className="font-medium text-sky underline underline-offset-4 hover:text-white">
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
    document.title = "LeadOps Realty (demo)";
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

      <section
        id="homes"
        aria-labelledby="homes-heading"
        className="relative -mt-8 scroll-mt-16 rounded-t-[28px] bg-concrete pb-28 sm:-mt-10 sm:rounded-t-[40px]"
      >
        <div className="mx-auto max-w-[1224px] px-5 pt-14 sm:px-8 sm:pt-20">
          <Rule />
          <div className="mt-6 flex flex-wrap items-end justify-between gap-3">
            <h2 id="homes-heading" className="text-section">
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

          <div className="mt-8">
            <Filters filters={filters} onChange={changeFilters} />
          </div>

          {failed && (
            <p role="alert" className="mt-8 rounded-[14px] border border-alert/40 bg-white p-4 text-ink">
              The homes couldn&apos;t load. Check that the LeadOps API is running at {API_URL}, then reload this page.
            </p>
          )}
          {!listings && !failed && <p className="mt-8 text-muted">Loading homes...</p>}
          {listings && visible.length === 0 && (
            <div className="mt-8 rounded-[18px] border border-line bg-white p-6">
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
        </div>
      </section>
    </>
  );
}
