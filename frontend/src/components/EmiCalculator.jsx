import { useEffect, useId, useRef, useState } from "react";
import { track } from "../lib/leadops";
import { emi, formatPrice, formatRupees } from "../lib/format";

function Slider({ label, value, display, min, max, step, onChange }) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <label htmlFor={id} className="font-medium text-ink-soft">
          {label}
        </label>
        <span className="tabular font-semibold">{display}</span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={onChange}
        className="w-full accent-blueprint"
      />
    </div>
  );
}

export default function EmiCalculator({ listing }) {
  const [downPct, setDownPct] = useState(20);
  const [rate, setRate] = useState(8.5);
  const [years, setYears] = useState(20);
  const touched = useRef(false);

  const loan = listing.price_inr * (1 - downPct / 100);
  const monthly = emi(loan, rate, years);
  const totalInterest = monthly * years * 12 - loan;

  // Using the calculator is a strong intent signal: record the settings once the visitor stops adjusting.
  useEffect(() => {
    if (!touched.current) return undefined;
    const timer = setTimeout(() => {
      track("emi_used", {
        listing_id: listing.id,
        price_inr: listing.price_inr,
        down_payment_pct: downPct,
        rate_pct: rate,
        years,
        emi: Math.round(monthly),
      });
    }, 1200);
    return () => clearTimeout(timer);
  }, [downPct, rate, years, listing.id, listing.price_inr, monthly]);

  const change = (setter) => (event) => {
    touched.current = true;
    setter(Number(event.target.value));
  };

  return (
    <section aria-labelledby="emi-heading" className="rounded-lg border border-line bg-white p-5">
      <h2 id="emi-heading" className="font-wide text-lg font-semibold">
        EMI estimate
      </h2>
      <p className="mt-3">
        <span className="tabular text-3xl font-semibold">{formatRupees(monthly)}</span>
        <span className="text-muted"> a month</span>
      </p>
      <p className="mt-1 text-sm text-muted">
        Loan of {formatRupees(loan)}, with {formatRupees(totalInterest)} interest in total.
      </p>
      <div className="mt-5 flex flex-col gap-4">
        <Slider
          label="Down payment"
          value={downPct}
          display={`${downPct}% (${formatPrice((listing.price_inr * downPct) / 100)})`}
          min={10}
          max={50}
          step={5}
          onChange={change(setDownPct)}
        />
        <Slider
          label="Interest rate"
          value={rate}
          display={`${rate.toFixed(2)}%`}
          min={7}
          max={12}
          step={0.05}
          onChange={change(setRate)}
        />
        <Slider
          label="Loan tenure"
          value={years}
          display={`${years} years`}
          min={5}
          max={30}
          step={1}
          onChange={change(setYears)}
        />
      </div>
      <p className="mt-4 text-xs text-muted">An estimate only. Your bank&apos;s rate and fees decide the final EMI.</p>
    </section>
  );
}
