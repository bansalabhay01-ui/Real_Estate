import { Link } from "react-router";
import { formatArea, formatPrice } from "../lib/format";
import FloorPlan from "./FloorPlan";
import StatusBadge from "./StatusBadge";

export default function ListingCard({ listing }) {
  return (
    <Link
      to={`/property/${listing.id}`}
      data-lo-track="listing_card"
      className="group flex flex-col overflow-hidden rounded-lg border border-line bg-white transition-colors hover:border-blueprint"
    >
      <div className="relative bg-blueprint">
        <FloorPlan bhk={listing.bhk} area={listing.area_sqft} compact className="block aspect-[16/10] w-full" />
        <StatusBadge listing={listing} className="absolute left-3 top-3" />
      </div>
      <div className="flex flex-1 flex-col gap-1 p-4">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="font-wide text-lg font-semibold group-hover:text-blueprint">{listing.project}</h3>
          <p className="tabular shrink-0 text-lg font-semibold">{formatPrice(listing.price_inr)}</p>
        </div>
        <p className="text-sm text-muted">
          {listing.locality}, {listing.city}
        </p>
        <p className="mt-auto flex gap-4 pt-3 text-sm text-ink-soft">
          <span>
            {listing.bhk} BHK {listing.property_type.toLowerCase()}
          </span>
          <span className="tabular">{formatArea(listing.area_sqft)}</span>
        </p>
      </div>
    </Link>
  );
}
