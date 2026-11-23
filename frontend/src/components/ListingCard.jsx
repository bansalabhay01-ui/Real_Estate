import { Link } from "react-router";
import { formatArea, formatPrice } from "../lib/format";
import FloorPlan from "./FloorPlan";
import StatusBadge from "./StatusBadge";

export default function ListingCard({ listing }) {
  return (
    <Link
      to={`/property/${listing.id}`}
      data-lo-track="listing_card"
      className="group flex w-full flex-col rounded-[22px] border border-line bg-white p-2 transition-colors hover:border-blueprint/50"
    >
      <div className="relative overflow-hidden rounded-[16px] bg-blueprint">
        <FloorPlan bhk={listing.bhk} area={listing.area_sqft} compact className="block aspect-[16/10] w-full" />
        <StatusBadge listing={listing} className="absolute left-3 top-3" />
      </div>
      <div className="flex flex-1 flex-col gap-1 px-3 pb-3 pt-4">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-lg font-medium tracking-[-0.02em] group-hover:text-blueprint">{listing.project}</h3>
          <p className="tabular shrink-0 text-lg font-medium">{formatPrice(listing.price_inr)}</p>
        </div>
        <p className="text-sm text-muted">
          {listing.locality}, {listing.city}
        </p>
        <p className="mt-auto flex gap-4 pt-4 text-sm text-ink-soft">
          <span>
            {listing.bhk} BHK {listing.property_type.toLowerCase()}
          </span>
          <span className="tabular">{formatArea(listing.area_sqft)}</span>
        </p>
      </div>
    </Link>
  );
}
