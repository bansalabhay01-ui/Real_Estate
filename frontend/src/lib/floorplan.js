// Simple, believable floor plans drawn from a home's BHK and area (the demo site has no photos).
// Rooms tile a grid exactly: [name, x, y, width, height] in grid units. Room sizes are scaled so the
// plan's total area matches the listing's area.
const LAYOUTS = {
  1: {
    width: 12,
    height: 8,
    rooms: [
      ["Living / dining", 0, 0, 7, 6],
      ["Kitchen", 7, 0, 5, 3],
      ["Bedroom", 7, 3, 5, 5],
      ["Balcony", 0, 6, 4, 2],
      ["Bath", 4, 6, 3, 2],
    ],
  },
  2: {
    width: 12,
    height: 8,
    rooms: [
      ["Bedroom 1", 0, 0, 4, 4],
      ["Bedroom 2", 0, 4, 4, 4],
      ["Living / dining", 4, 0, 5, 8],
      ["Kitchen", 9, 0, 3, 3],
      ["Bath", 9, 3, 3, 2],
      ["Balcony", 9, 5, 3, 3],
    ],
  },
  3: {
    width: 12,
    height: 8,
    rooms: [
      ["Bedroom 1", 0, 0, 4, 4],
      ["Bedroom 2", 0, 4, 4, 4],
      ["Living / dining", 4, 0, 5, 5],
      ["Kitchen", 9, 0, 3, 3],
      ["Bedroom 3", 9, 3, 3, 5],
      ["Bath", 4, 5, 2, 1.5],
      ["Bath", 4, 6.5, 2, 1.5],
      ["Balcony", 6, 5, 3, 3],
    ],
  },
  4: {
    width: 14,
    height: 8,
    rooms: [
      ["Bedroom 1", 0, 0, 4, 4],
      ["Bedroom 2", 0, 4, 4, 4],
      ["Living / dining", 4, 0, 6, 5],
      ["Kitchen", 10, 0, 4, 3],
      ["Bedroom 3", 10, 3, 4, 5],
      ["Bedroom 4", 4, 5, 3, 3],
      ["Bath", 7, 5, 3, 1.5],
      ["Bath", 7, 6.5, 3, 1.5],
    ],
  },
};

function feet(value) {
  const whole = Math.floor(value);
  const inches = Math.round((value - whole) * 12);
  return inches === 12 ? `${whole + 1}'0"` : `${whole}'${inches}"`;
}

export function floorPlan(bhk, areaSqft) {
  const layout = LAYOUTS[Math.min(Math.max(bhk, 1), 4)];
  const feetPerUnit = Math.sqrt(areaSqft / (layout.width * layout.height));
  return {
    width: layout.width,
    height: layout.height,
    rooms: layout.rooms.map(([name, x, y, w, h]) => ({
      name,
      x,
      y,
      w,
      h,
      size: `${feet(w * feetPerUnit)} × ${feet(h * feetPerUnit)}`,
    })),
  };
}
