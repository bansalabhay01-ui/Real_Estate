import { forwardRef, useId } from "react";
import { floorPlan } from "../lib/floorplan";

const UNIT = 30; // SVG pixels per grid unit
const COLORS = { paper: "#1d4f91", line: "#e6effa", label: "#d4e3f6", grid: "#2b5f9f" };

// A blueprint-style floor plan. compact = card thumbnail (no labels); animate = the walls draw themselves.
const FloorPlan = forwardRef(function FloorPlan({ bhk, area, compact = false, animate = false, title, className = "" }, ref) {
  const plan = floorPlan(bhk, area);
  const gridId = `plan-grid-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`; // safe inside url(#...)
  const pad = compact ? 14 : 24;
  const width = plan.width * UNIT + pad * 2;
  const height = plan.height * UNIT + pad * 2;
  const rect = (x, y, w, h) => `M${x * UNIT} ${y * UNIT}h${w * UNIT}v${h * UNIT}h${-w * UNIT}Z`;

  return (
    <svg
      ref={ref}
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={title ?? `Floor plan of a ${bhk} BHK, ${area} sq ft`}
      className={`${animate ? "plan-animate" : ""} ${className}`}
      fontFamily="Archivo, Arial, sans-serif"
    >
      <defs>
        <pattern id={gridId} width={UNIT / 2} height={UNIT / 2} patternUnits="userSpaceOnUse">
          <path d={`M${UNIT / 2} 0V${UNIT / 2}H0`} fill="none" stroke={COLORS.grid} strokeWidth="0.6" />
        </pattern>
      </defs>
      <rect width={width} height={height} fill={COLORS.paper} />
      <rect width={width} height={height} fill={`url(#${gridId})`} />

      <g transform={`translate(${pad} ${pad})`} fill="none" stroke={COLORS.line}>
        {plan.rooms.map((room, index) => (
          <path
            key={index}
            className="plan-wall"
            pathLength="1"
            d={rect(room.x, room.y, room.w, room.h)}
            strokeWidth="1.6"
            style={animate ? { animationDelay: `${0.15 + index * 0.1}s` } : undefined}
          />
        ))}
        <path className="plan-wall" pathLength="1" d={rect(0, 0, plan.width, plan.height)} strokeWidth="4" />
      </g>

      {!compact && (
        <g transform={`translate(${pad} ${pad})`} textAnchor="middle" fill={COLORS.label}>
          {plan.rooms.map((room, index) => {
            const cx = (room.x + room.w / 2) * UNIT;
            const cy = (room.y + room.h / 2) * UNIT;
            const roomy = room.w >= 3 && room.h >= 2;
            return (
              <g key={index} className="plan-label">
                <text x={cx} y={roomy ? cy - 2 : cy + 4} fontSize={room.w >= 3 ? 12 : 10} fontWeight="600">
                  {room.name}
                </text>
                {roomy && (
                  <text x={cx} y={cy + 14} fontSize="10" opacity="0.8">
                    {room.size}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      )}
    </svg>
  );
});

export default FloorPlan;
