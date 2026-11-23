// "Watch LeadOps sort a bot attack": a live feed of visitors getting their labels, and three visitors explained.
// The visitors come from the demo's simulated traffic, and every reason is a sentence the scoring engine really
// writes (backend/app/scoring/rules.py, explain.py, combine.py and ai/classify.py).
import { useEffect, useRef, useState } from "react";
import { IconCheck, IconMinus, IconPlus } from "../components/icons";
import { Container, Eyebrow, Section, SectionHead, useInView, useReducedMotion } from "../components/ui";

// Label colours for dark surfaces. The word is always shown too, so colour is never the only cue.
export const LABEL_STYLE = {
  Bot: { dot: "bg-[#ff8f8f]", text: "text-[#ffb3b3]" },
  Junk: { dot: "bg-[#ffc46b]", text: "text-[#ffd699]" },
  Review: { dot: "bg-[#ffc46b]", text: "text-[#ffd699]" },
  Cold: { dot: "bg-sky/60", text: "text-sky" },
  Warm: { dot: "bg-sky", text: "text-sky" },
  Hot: { dot: "bg-marigold", text: "text-marigold" },
};

export function DarkLabel({ label }) {
  const style = LABEL_STYLE[label];
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.06] px-2.5 py-0.5 text-xs font-medium ${style.text}`}>
      <span className={`size-1.5 rounded-full ${style.dot}`} aria-hidden="true" />
      {label}
    </span>
  );
}

export const FEED = [
  { id: "sim 3f9a1c", label: "Bot", reason: "Opened 14 pages, spending under 2 seconds on each" },
  { id: "sim 8b20de", label: "Cold", reason: "Spent 2 minutes on 1 home" },
  { id: "sim 51c7aa", label: "Junk", reason: "The phone number can't be real: the same digit over and over" },
  { id: "sim e04b93", label: "Bot", reason: "Filled in the hidden form field that only bots can see" },
  { id: "sim 7d16f2", label: "Hot", reason: "3 visits over 2 days" },
  { id: "sim c2a8e5", label: "Junk", reason: "The message is a broker's pitch (\"my clients\")" },
  { id: "sim 94fe03", label: "Bot", reason: "The mouse jumped about 140 pixels at a time; people move in small steps" },
  { id: "sim 0ab6c1", label: "Warm", reason: "Checked the EMI on a ₹86 L home" },
  { id: "sim 6e35b8", label: "Bot", reason: "The browser is driven by automation software (navigator.webdriver)" },
  { id: "sim f17d2a", label: "Junk", reason: "Wants to rent, not buy" },
];
export const SHOWN_ROWS = 6;

// How many visitors have "arrived": it grows every 1.5 seconds while the feed is on screen.
export function useArrivals(ref) {
  const inView = useInView(ref);
  const reduced = useReducedMotion();
  const [arrived, setArrived] = useState(SHOWN_ROWS);
  useEffect(() => {
    if (!inView || reduced) return undefined;
    const timer = setInterval(() => setArrived((count) => count + 1), 1500);
    return () => clearInterval(timer);
  }, [inView, reduced]);
  return { arrived, animate: !reduced };
}

// The newest visitors first.
export function latestRows(arrived) {
  return Array.from({ length: SHOWN_ROWS }, (_, offset) => {
    const number = arrived - 1 - offset;
    return { ...FEED[number % FEED.length], key: number };
  });
}

// What happened to the visitors who have arrived so far.
export function tally(arrived) {
  const counts = { bots: 0, junk: 0, people: 0, hot: 0 };
  for (let number = 0; number < arrived; number += 1) {
    const { label } = FEED[number % FEED.length];
    if (label === "Bot") counts.bots += 1;
    else if (label === "Junk") counts.junk += 1;
    else counts.people += 1;
    if (label === "Hot") counts.hot += 1;
  }
  return counts;
}

function WindowDots() {
  return (
    <span className="flex gap-1.5" aria-hidden="true">
      {[0, 1, 2].map((dot) => (
        <span key={dot} className="size-2.5 rounded-full bg-white/15" />
      ))}
    </span>
  );
}

function LiveFeed() {
  const ref = useRef(null);
  const { arrived, animate } = useArrivals(ref);
  const counts = tally(arrived);
  return (
    <figure ref={ref} className="overflow-hidden rounded-[18px] border border-white/10 bg-night/70 shadow-[0_40px_90px_-40px_rgb(0_0_0/0.8)]">
      <div className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
        <WindowDots />
        <p className="text-sm text-white/70">Sales dashboard</p>
        <p className="ml-auto inline-flex items-center gap-1.5 text-xs text-white/70">
          <span className="size-1.5 rounded-full bg-[#4cc38a] motion-safe:animate-pulse" aria-hidden="true" />
          Live
        </p>
      </div>
      <ol className="divide-y divide-white/[0.06]" aria-label="Visitors as they arrive, newest first">
        {latestRows(arrived).map((row, index) => (
          <li
            key={row.key}
            className={`grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 px-4 py-3 sm:grid-cols-[92px_1fr_auto] ${index === 0 && animate ? "row-in" : ""}`}
          >
            <span className="font-mono text-xs text-white/55 sm:order-none">{row.id}</span>
            <span className="order-3 col-span-2 text-sm leading-5 text-white/85 sm:order-none sm:col-span-1 sm:truncate">{row.reason}</span>
            <DarkLabel label={row.label} />
          </li>
        ))}
      </ol>
      <dl className="grid grid-cols-3 border-t border-white/10 text-center">
        {[
          ["Bots blocked", counts.bots],
          ["Junk filtered", counts.junk],
          ["People kept", counts.people],
        ].map(([name, value]) => (
          <div key={name} className="flex flex-col-reverse gap-0.5 border-white/10 px-2 py-3 [&:not(:last-child)]:border-r">
            <dt className="font-mono text-[11px] text-white/60 sm:text-xs">{name}</dt>
            <dd className="tabular text-lg font-medium">{value}</dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}

const EXAMPLES = [
  {
    title: "Stealth bot",
    note: "Hid its automation flag and typed like a person",
    label: "Bot",
    reasons: [
      "The mouse jumped about 140 pixels at a time; people move in small steps",
      "Mouse or touch activity in only 20% of the visit",
      "Filled in the enquiry form in 3.1 seconds",
    ],
  },
  {
    title: "Rival broker",
    note: "A real person, fishing for your inventory",
    label: "Junk",
    reasons: ["The message is a broker's pitch (\"share your inventory\")", "Writes like a broker looking for inventory or commission"],
  },
  {
    title: "Serious buyer",
    note: "Never filled in a form until the assistant offered the floor plan",
    label: "Hot",
    reasons: ["Spent 9 minutes on 3 homes", "3 visits over 2 days", "Checked the EMI on a ₹86 L home", "Downloaded the 3 BHK floor plan"],
  },
];

function Examples() {
  const [open, setOpen] = useState(0);
  return (
    <ul className="mt-8 flex flex-col gap-3">
      {EXAMPLES.map((example, index) => {
        const expanded = open === index;
        return (
          <li
            key={example.title}
            className={`rounded-[14px] border transition-colors ${expanded ? "border-white/20 bg-white/[0.08]" : "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"}`}
          >
            <button
              type="button"
              aria-expanded={expanded}
              aria-controls={`example-${index}`}
              onClick={() => setOpen(expanded ? null : index)}
              className="flex w-full items-center gap-4 rounded-[14px] px-4 py-4 text-left"
            >
              <span className={`grid size-10 shrink-0 place-items-center rounded-full ${expanded ? "bg-white text-night" : "bg-white/10 text-white"}`}>
                {expanded ? <IconMinus className="size-4" /> : <IconPlus className="size-4" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{example.title}</span>
                <span className="block text-sm text-white/65">{example.note}</span>
              </span>
              <DarkLabel label={example.label} />
            </button>
            <ul id={`example-${index}`} hidden={!expanded} className="flex flex-col gap-2 px-4 pb-5 pl-[4.5rem] text-sm text-white/80">
              {example.reasons.map((reason) => (
                <li key={reason} className="flex gap-2">
                  <IconCheck className={`mt-0.5 size-4 shrink-0 ${LABEL_STYLE[example.label].text}`} />
                  {reason}
                </li>
              ))}
            </ul>
          </li>
        );
      })}
    </ul>
  );
}

const STATS = [
  ["3 checks", "human, authenticity and intent"],
  ["27 signals", "read by the machine-learning human check"],
  ["4 languages", "English, Hinglish, Hindi and Marathi"],
  ["0 numbers", "ever sent to the AI: phones and emails are hidden"],
];
const ABILITIES = [
  "Explains every label in plain words",
  "Catches bots by how they move, not only by flags",
  "Spots fake numbers and throwaway emails",
  "Sorts out brokers, renters and spam",
  "Never reads what people type",
  "Learns from your sales team's verdicts",
  "Keeps working without an AI key",
];

export default function LiveSort() {
  return (
    <Section tone="deep" id="watch" aria-labelledby="watch-title" className="scroll-mt-16 overflow-hidden pb-40 sm:pb-48">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_45%_at_25%_55%,rgb(29_79_145/0.45),transparent_70%)]"
        aria-hidden="true"
      />
      <Container className="relative pt-24 sm:pt-32">
        <SectionHead
          label="Live sorting"
          titleId="watch-title"
          title={
            <>
              Watch LeadOps sort <br className="hidden sm:block" />a bot attack.
            </>
          }
        />
        <div className="mt-16 grid items-start gap-12 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <LiveFeed />
            <p className="mt-3 font-mono text-xs text-white/60">An illustration, with visitors from the demo&apos;s simulated traffic.</p>
          </div>
          <div className="lg:col-span-6 lg:pl-4">
            <Eyebrow className="text-white/60">Every label comes with reasons</Eyebrow>
            <h3 className="text-title mt-3">Three visitors, three verdicts.</h3>
            <p className="mt-3 max-w-[52ch] text-white/70">
              The reasons are the ones the dashboard shows a salesperson, word for word. Open a visitor to read them.
            </p>
            <Examples />
          </div>
        </div>

        <dl className="mt-20 grid overflow-hidden rounded-[18px] border border-white/10 sm:grid-cols-2 lg:grid-cols-4">
          {STATS.map(([value, text]) => (
            <div key={value} className="flex flex-col gap-2 border-white/10 p-6 [&:not(:last-child)]:border-b sm:[&:nth-child(odd)]:border-r lg:border-b-0 lg:[&:not(:last-child)]:border-r">
              <dt className="text-[clamp(1.8rem,3vw,2.5rem)] font-medium leading-none tracking-[-0.04em]">{value}</dt>
              <dd className="text-sm text-white/65">{text}</dd>
            </div>
          ))}
        </dl>
        <ul className="mx-auto mt-10 flex max-w-[960px] flex-wrap justify-center gap-2.5" aria-label="What it can do">
          {ABILITIES.map((ability) => (
            <li key={ability} className="rounded-full border border-white/15 bg-white/[0.04] px-4 py-2 text-sm text-white/85">
              {ability}
            </li>
          ))}
        </ul>
      </Container>
    </Section>
  );
}
