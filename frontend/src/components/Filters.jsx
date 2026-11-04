export const CITIES = ["Pune", "Bengaluru", "Hyderabad", "Mumbai", "Noida"];
const BEDROOMS = [1, 2, 3, 4];
const BUDGETS = [
  [7_500_000, "Under ₹75 L"],
  [10_000_000, "Under ₹1 Cr"],
  [15_000_000, "Under ₹1.5 Cr"],
  [20_000_000, "Under ₹2 Cr"],
];

function Choice({ pressed, onClick, children }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={`rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors ${
        pressed ? "border-ink bg-ink text-white" : "border-line bg-white text-ink hover:border-ink"
      }`}
    >
      {children}
    </button>
  );
}

// filters: { city: "" | name, bhk: 0 | n, maxPrice: 0 | inr }
export default function Filters({ filters, onChange }) {
  const set = (key, value) => onChange({ ...filters, [key]: value });
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-end lg:gap-8">
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-semibold text-ink-soft">City</legend>
        <div className="flex flex-wrap gap-2">
          <Choice pressed={!filters.city} onClick={() => set("city", "")}>
            All cities
          </Choice>
          {CITIES.map((city) => (
            <Choice key={city} pressed={filters.city === city} onClick={() => set("city", city)}>
              {city}
            </Choice>
          ))}
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-semibold text-ink-soft">Bedrooms</legend>
        <div className="flex flex-wrap gap-2">
          <Choice pressed={!filters.bhk} onClick={() => set("bhk", 0)}>
            Any
          </Choice>
          {BEDROOMS.map((bhk) => (
            <Choice key={bhk} pressed={filters.bhk === bhk} onClick={() => set("bhk", bhk)}>
              {bhk} BHK
            </Choice>
          ))}
        </div>
      </fieldset>

      <label className="flex flex-col gap-2 text-sm font-semibold text-ink-soft">
        Budget
        <select
          value={filters.maxPrice}
          onChange={(event) => set("maxPrice", Number(event.target.value))}
          className="rounded-md border border-line bg-white px-3 py-2 text-sm font-medium text-ink"
        >
          <option value={0}>Any budget</option>
          {BUDGETS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
