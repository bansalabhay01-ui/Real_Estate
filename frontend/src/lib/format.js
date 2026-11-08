const LAKH = 100_000;
const CRORE = 10_000_000;

// 8600000 -> "₹86 L", 14500000 -> "₹1.45 Cr"
export function formatPrice(inr) {
  const [value, unit] = inr >= CRORE ? [inr / CRORE, "Cr"] : [inr / LAKH, "L"];
  return `₹${Number(value.toFixed(2))} ${unit}`;
}

const rupees = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
export const formatRupees = (amount) => rupees.format(Math.round(amount)); // ₹1,66,622

export const formatArea = (sqft) => `${sqft.toLocaleString("en-IN")} sq ft`;

// Monthly EMI: P × r × (1 + r)^n / ((1 + r)^n − 1), with r the monthly rate and n the number of months.
export function emi(principal, annualRatePct, years) {
  const monthlyRate = annualRatePct / 12 / 100;
  const months = years * 12;
  if (principal <= 0 || months <= 0) return 0;
  if (monthlyRate === 0) return principal / months;
  const growth = (1 + monthlyRate) ** months;
  return (principal * monthlyRate * growth) / (growth - 1);
}

export function timeAgo(iso, now = Date.now()) {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds} s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export const formatClock = (iso) =>
  new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export const formatDateTime = (iso) =>
  new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export function formatDuration(ms) {
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.round(ms / 60_000)} min`;
}

// What a buyer has told the assistant, as short phrases: ["Wagholi, Pune", "3 BHK", "under ₹90 L", ...]
export function profilePhrases(profile = {}) {
  const phrases = [];
  const place = [profile.locality, profile.city].filter(Boolean).join(", ");
  if (place) phrases.push(place);
  if (profile.bhk) phrases.push(`${profile.bhk} BHK`);
  const { budget_min: low, budget_max: high } = profile;
  if (low && high) phrases.push(`${formatPrice(low)} to ${formatPrice(high)}`);
  else if (high) phrases.push(`under ${formatPrice(high)}`);
  else if (low) phrases.push(`above ${formatPrice(low)}`);
  if (profile.timeline_months) phrases.push(`moving in ${profile.timeline_months} mo`);
  if (profile.loan_needed === true) phrases.push("needs a loan");
  if (profile.loan_needed === false) phrases.push("no loan");
  if (profile.purpose === "own_use") phrases.push("to live in");
  if (profile.purpose === "investment") phrases.push("as an investment");
  return phrases;
}
