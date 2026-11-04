// "Ready to move" or "Possession Jun 2027": a white chip so it reads on top of a blueprint.
export default function StatusBadge({ listing, className = "" }) {
  const ready = listing.status === "Ready to move";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full bg-white px-2.5 py-0.5 text-xs font-semibold text-ink ${className}`}
    >
      <span className={`size-2 rounded-full ${ready ? "bg-ok" : "bg-amber"}`} aria-hidden="true" />
      {ready ? "Ready to move" : `Possession ${listing.possession}`}
    </span>
  );
}
