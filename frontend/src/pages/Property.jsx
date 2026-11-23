import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import EmiCalculator from "../components/EmiCalculator";
import EnquiryForm from "../components/EnquiryForm";
import FloorPlan from "../components/FloorPlan";
import { IconBack, IconDownload } from "../components/icons";
import StatusBadge from "../components/StatusBadge";
import { Button, Eyebrow, Rule } from "../components/ui";
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
    <div className="flex flex-col gap-0.5">
      <dt className="font-mono text-[12px] text-muted">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

function Part({ id, title, children }) {
  return (
    <section aria-labelledby={id}>
      <Rule />
      <h2 id={id} className="text-title mt-5">
        {title}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
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
      <div className="mx-auto max-w-[1224px] px-5 pb-32 pt-16 sm:px-8">
        <h1 className="text-title">We couldn&apos;t find home {id}.</h1>
        <p className="mt-2 text-muted">It may have been sold or taken off the site.</p>
        <Link to="/demo" className="mt-6 inline-block font-semibold text-blueprint underline underline-offset-2">
          See all homes
        </Link>
      </div>
    );
  }
  if (state === "loading" || !listing) {
    return <p className="mx-auto max-w-[1224px] px-5 pb-32 pt-16 text-muted sm:px-8">Loading the home...</p>;
  }

  const filename = `${listing.project} ${listing.bhk}BHK floor plan.svg`.replace(/[^\w .-]/g, "");

  return (
    <article className="mx-auto max-w-[1224px] px-5 pb-36 pt-8 sm:px-8">
      <Link
        to="/demo"
        className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-3.5 py-1.5 text-sm font-medium text-ink-soft hover:text-ink"
      >
        <IconBack />
        All homes
      </Link>

      <div className="mt-8 grid gap-12 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="flex flex-col gap-14">
          <header>
            <Eyebrow className="text-muted">
              {listing.locality}, {listing.city}
            </Eyebrow>
            <h1 className="text-section mt-3">{listing.project}</h1>
            <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-3">
              <p className="tabular text-3xl font-medium tracking-[-0.03em]">{formatPrice(listing.price_inr)}</p>
              <StatusBadge listing={listing} className="border border-line" />
              <Button href="#enquiry" tone="marigold" size="sm" className="lg:hidden">
                Send an enquiry
              </Button>
            </div>
            <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-5 rounded-[20px] border border-line bg-white p-6 sm:grid-cols-3">
              <Fact label="Bedrooms" value={`${listing.bhk} BHK`} />
              <Fact label="Area" value={formatArea(listing.area_sqft)} />
              <Fact label="Type" value={listing.property_type} />
              {listing.floor && <Fact label="Floor" value={listing.floor} />}
              {listing.facing && <Fact label="Facing" value={listing.facing} />}
              <Fact label="Possession" value={listing.possession} />
            </dl>
          </header>

          <section aria-labelledby="plan-heading">
            <Rule />
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
              <h2 id="plan-heading" className="text-title">
                Floor plan
              </h2>
              <Button
                tone="outline"
                size="sm"
                onClick={() => {
                  downloadSvg(planRef.current, filename);
                  track("floorplan_download", { listing_id: listing.id, bhk: listing.bhk });
                }}
              >
                <IconDownload />
                Download floor plan
              </Button>
            </div>
            <div className="mt-5 overflow-hidden rounded-[22px] bg-blueprint">
              <FloorPlan ref={planRef} bhk={listing.bhk} area={listing.area_sqft} className="block w-full" />
            </div>
            <p className="mt-3 text-sm text-muted">Indicative layout. Room sizes are approximate.</p>
          </section>

          <Part id="highlights-heading" title="Why people pick it">
            <ul className="flex flex-col gap-2 text-ink-soft">
              {listing.highlights.map((highlight) => (
                <li key={highlight} className="flex gap-2.5">
                  <span className="mt-2.5 size-1.5 shrink-0 rotate-45 bg-blueprint" aria-hidden="true" />
                  {highlight}
                </li>
              ))}
            </ul>
          </Part>

          <Part id="amenities-heading" title="Amenities">
            <ul className="flex flex-wrap gap-2">
              {listing.amenities.map((amenity) => (
                <li key={amenity} className="rounded-full border border-line bg-white px-3.5 py-1.5 text-sm">
                  {amenity}
                </li>
              ))}
            </ul>
          </Part>

          <Part id="about-heading" title="About this home">
            <p className="max-w-prose text-ink-soft">{listing.description}</p>
          </Part>
        </div>

        <aside className="flex flex-col gap-5 lg:sticky lg:top-24 lg:self-start">
          <EmiCalculator listing={listing} />
          <EnquiryForm key={listing.id} listing={listing} />
        </aside>
      </div>
    </article>
  );
}
