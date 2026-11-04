import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import EmiCalculator from "../components/EmiCalculator";
import EnquiryForm from "../components/EnquiryForm";
import FloorPlan from "../components/FloorPlan";
import { IconBack, IconDownload } from "../components/icons";
import StatusBadge from "../components/StatusBadge";
import { getListing } from "../lib/api";
import { formatArea, formatPrice } from "../lib/format";
import { track } from "../lib/leadops";

function downloadSvg(svg, filename) {
  const blob = new Blob([new XMLSerializer().serializeToString(svg)], { type: "image/svg+xml" });
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Fact({ label, value }) {
  return (
    <div className="flex flex-col">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="font-semibold">{value}</dd>
    </div>
  );
}

export default function Property() {
  const { id } = useParams();
  const [listing, setListing] = useState(null);
  const [state, setState] = useState("loading"); // loading | ready | missing
  const planRef = useRef(null);
  const trackedId = useRef(null);

  useEffect(() => {
    setState("loading");
    getListing(id)
      .then((home) => {
        setListing(home);
        setState("ready");
        document.title = `${home.project}, ${home.locality} | LeadOps Realty`;
        if (trackedId.current !== home.id) {
          trackedId.current = home.id;
          track("property_view", { listing_id: home.id, city: home.city, bhk: home.bhk, price_inr: home.price_inr });
        }
      })
      .catch(() => setState("missing"));
    return () => {
      document.title = "LeadOps Realty (demo)";
    };
  }, [id]);

  if (state === "missing") {
    return (
      <div className="mx-auto max-w-6xl px-4 py-16">
        <h1 className="font-wide text-2xl font-semibold">We couldn&apos;t find home {id}.</h1>
        <p className="mt-2 text-muted">It may have been sold or taken off the site.</p>
        <Link to="/" className="mt-6 inline-block font-semibold text-blueprint underline underline-offset-2">
          See all homes
        </Link>
      </div>
    );
  }
  if (state === "loading" || !listing) {
    return <p className="mx-auto max-w-6xl px-4 py-16 text-muted">Loading the home...</p>;
  }

  const filename = `${listing.project} ${listing.bhk}BHK floor plan.svg`.replace(/[^\w .-]/g, "");

  return (
    <article className="mx-auto max-w-6xl px-4 py-8">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft hover:text-ink">
        <IconBack />
        All homes
      </Link>

      <div className="mt-6 grid gap-10 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex flex-col gap-10">
          <header>
            <h1 className="font-extra-wide text-4xl font-bold tracking-tight sm:text-5xl">{listing.project}</h1>
            <p className="mt-2 text-lg text-ink-soft">
              {listing.locality}, {listing.city}
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-3">
              <p className="tabular text-3xl font-semibold">{formatPrice(listing.price_inr)}</p>
              <StatusBadge listing={listing} className="border border-line" />
              <a
                href="#enquiry"
                className="rounded-md bg-marigold px-4 py-2 text-sm font-semibold text-ink hover:bg-[#e09500] lg:hidden"
              >
                Send an enquiry
              </a>
            </div>
            <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 rounded-lg border border-line bg-white p-5 sm:grid-cols-3">
              <Fact label="Bedrooms" value={`${listing.bhk} BHK`} />
              <Fact label="Area" value={formatArea(listing.area_sqft)} />
              <Fact label="Type" value={listing.property_type} />
              {listing.floor && <Fact label="Floor" value={listing.floor} />}
              {listing.facing && <Fact label="Facing" value={listing.facing} />}
              <Fact label="Possession" value={listing.possession} />
            </dl>
          </header>

          <section aria-labelledby="plan-heading">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="plan-heading" className="font-wide text-xl font-semibold">
                Floor plan
              </h2>
              <button
                type="button"
                onClick={() => {
                  downloadSvg(planRef.current, filename);
                  track("floorplan_download", { listing_id: listing.id, bhk: listing.bhk });
                }}
                className="inline-flex items-center gap-2 rounded-md border border-ink px-3 py-2 text-sm font-semibold hover:bg-ink hover:text-white"
              >
                <IconDownload />
                Download floor plan
              </button>
            </div>
            <div className="mt-4 overflow-hidden rounded-lg bg-blueprint">
              <FloorPlan ref={planRef} bhk={listing.bhk} area={listing.area_sqft} className="block w-full" />
            </div>
            <p className="mt-2 text-sm text-muted">Indicative layout. Room sizes are approximate.</p>
          </section>

          <section aria-labelledby="highlights-heading">
            <h2 id="highlights-heading" className="font-wide text-xl font-semibold">
              Why people pick it
            </h2>
            <ul className="mt-3 list-disc space-y-1.5 pl-5 text-ink-soft">
              {listing.highlights.map((highlight) => (
                <li key={highlight}>{highlight}</li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="amenities-heading">
            <h2 id="amenities-heading" className="font-wide text-xl font-semibold">
              Amenities
            </h2>
            <ul className="mt-3 flex flex-wrap gap-2">
              {listing.amenities.map((amenity) => (
                <li key={amenity} className="rounded-full border border-line bg-white px-3 py-1 text-sm">
                  {amenity}
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="about-heading">
            <h2 id="about-heading" className="font-wide text-xl font-semibold">
              About this home
            </h2>
            <p className="mt-3 max-w-prose text-ink-soft">{listing.description}</p>
          </section>
        </div>

        <aside className="flex flex-col gap-6 lg:sticky lg:top-6 lg:self-start">
          <EmiCalculator listing={listing} />
          <EnquiryForm key={listing.id} listing={listing} />
        </aside>
      </div>
    </article>
  );
}
