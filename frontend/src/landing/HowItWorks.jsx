// "How it works": the four steps from adding the script to a salesperson's next call, each with a small app window.
import { useEffect, useRef, useState } from "react";
import { Button, Container, Section, SectionHead, useInView, useReducedMotion } from "../components/ui";

const STEP_MS = 5500;

const STEPS = [
  { title: "Add one script tag", text: "Paste one line into your site. Visitors are asked first, and nothing is recorded until they agree.", tab: "Install" },
  { title: "Visitors browse and chat", text: "The script counts actions and timings, never what people type. The assistant answers in four languages.", tab: "Visitors" },
  { title: "Every visitor is scored", text: "Rules, a machine-learning human check and intent points give each visitor a label and the reasons for it.", tab: "Scores" },
  { title: "Sales gets the ready ones", text: "A live dashboard with a three-line brief, the next step and a WhatsApp draft in the buyer's language.", tab: "Leads" },
];

function Mono({ children, className = "" }) {
  return <span className={`font-mono text-[13px] ${className}`}>{children}</span>;
}

function InstallStep() {
  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm text-muted">Add this to every page of your site:</p>
      <pre className="overflow-x-auto rounded-[12px] bg-night p-4 font-mono text-[13px] leading-6 text-sky">
        {`<script
  src="https://your-leadops-api/sdk/leadops.js"
  data-site="your-site"
  data-consent="required"
  async></script>`}
      </pre>
      <div className="flex flex-col gap-3 rounded-[12px] border border-line p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm">May we record how you use this site? Nothing is recorded unless you agree.</p>
        <span className="flex shrink-0 gap-2" aria-hidden="true">
          <span className="rounded-full bg-night px-3 py-1 text-xs font-medium text-white">Accept</span>
          <span className="rounded-full border border-line px-3 py-1 text-xs font-medium">Decline</span>
        </span>
      </div>
    </div>
  );
}

const EVENTS = [
  ["page_view", "/property/PUN-002"],
  ["scroll_depth", "75%"],
  ["emi_used", "₹86 L over 20 years"],
  ["floorplan_download", "3 BHK"],
  ["activity", "212 mouse moves, 14 key presses"],
];

function VisitorsStep() {
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <div className="flex flex-col gap-2.5">
        <p className="ml-auto max-w-[90%] rounded-[14px] rounded-br-sm bg-blueprint px-3 py-2 text-sm text-white">Pune mein 90 lakh tak 3BHK chahiye</p>
        <div className="max-w-[95%] rounded-[14px] rounded-bl-sm bg-concrete px-3 py-2 text-sm">
          Ye 2 ghar mile (Pune, 3 BHK, ₹90 L tak):
          <ol className="mt-1 list-decimal pl-4 text-ink-soft">
            <li>Aranya Courtyard, Wagholi: ₹86 L</li>
            <li>Indigo Greens, Ravet: ₹89 L</li>
          </ol>
        </div>
      </div>
      <ul className="flex flex-col divide-y divide-line rounded-[12px] border border-line" aria-label="Events the script sends">
        {EVENTS.map(([type, detail]) => (
          <li key={type} className="flex flex-wrap items-baseline justify-between gap-x-3 px-3 py-2">
            <Mono className="text-blueprint">{type}</Mono>
            <span className="text-xs text-muted">{detail}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const POINTS = [
  ["Time on 3 homes", 20],
  ["2 visits over 2 days", 10],
  ["Shared city, BHK and budget", 10],
  ["EMI calculator", 12],
  ["Floor plan", 12],
  ["Kept to similar homes", 10],
  ["Used the filters", 6],
];

function Meter({ name, value, display }) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span>{name}</span>
        <Mono className="text-muted">{display}</Mono>
      </div>
      <div className="mt-1.5 h-1.5 rounded-full bg-blueprint-line">
        <div className="h-full rounded-full bg-blueprint" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function ScoreStep() {
  const intent = POINTS.reduce((sum, [, points]) => sum + points, 0);
  return (
    <div className="grid gap-6 sm:grid-cols-2">
      <div className="flex flex-col gap-4">
        <p className="flex items-center gap-2">
          <span className="rounded-full border border-blueprint/30 bg-blueprint-line px-2.5 py-0.5 text-sm font-semibold">Hot</span>
          <span className="text-sm text-muted">a serious buyer: call first</span>
        </p>
        <Meter name="Human check" value={97} display="97% a person" />
        <Meter name="Intent" value={intent} display={`${intent} / 100`} />
      </div>
      <ul className="flex flex-col gap-1.5 text-sm" aria-label="Intent points">
        {POINTS.map(([name, points]) => (
          <li key={name} className="flex justify-between gap-3 border-b border-dashed border-line pb-1.5">
            <span className="text-ink-soft">{name}</span>
            <Mono>+{points}</Mono>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LeadsStep() {
  return (
    <div className="flex flex-col gap-4">
      <ul className="flex flex-col gap-1.5 text-sm">
        <li>Wants a 3 BHK in Pune under ₹90 L moving within 3 months with a home loan.</li>
        <li className="text-ink-soft">Spent 9 minutes on 3 homes; 3 visits over 2 days; checked the EMI on a ₹86 L home.</li>
        <li className="text-ink-soft">Buying to live in. Has shared contact details.</li>
      </ul>
      <p className="rounded-[12px] border border-blueprint/30 bg-blueprint-line px-3 py-2.5 text-sm">
        <span className="block text-xs font-medium text-ink-soft">Do this now</span>
        <span className="font-semibold">Call now: spent 9 minutes on 3 homes.</span>
      </p>
      <div className="flex flex-wrap gap-2" aria-hidden="true">
        <span className="rounded-full bg-night px-3 py-1.5 text-xs font-medium text-white">Open in WhatsApp</span>
        <span className="rounded-full border border-line px-3 py-1.5 text-xs font-medium">Genuine</span>
        <span className="rounded-full border border-line px-3 py-1.5 text-xs font-medium">Fake</span>
        <span className="rounded-full border border-line px-3 py-1.5 text-xs font-medium">Converted</span>
      </div>
    </div>
  );
}

const PANELS = [InstallStep, VisitorsStep, ScoreStep, LeadsStep];

export default function HowItWorks() {
  const ref = useRef(null);
  const inView = useInView(ref);
  const reduced = useReducedMotion();
  const [step, setStep] = useState(0);
  const [chosen, setChosen] = useState(false); // once someone picks a step, the steps stop moving on their own

  useEffect(() => {
    if (!inView || reduced || chosen) return undefined;
    const timer = setTimeout(() => setStep((current) => (current + 1) % STEPS.length), STEP_MS);
    return () => clearTimeout(timer);
  }, [inView, reduced, chosen, step]);

  const Panel = PANELS[step];
  const running = inView && !reduced && !chosen;

  return (
    <Section tone="paper" id="how" aria-labelledby="how-title" className="scroll-mt-16 pb-40 sm:pb-48">
      <Container className="pt-24 sm:pt-32">
        <SectionHead
          label="How it works"
          titleId="how-title"
          title={
            <>
              Live on any property site <br className="hidden sm:block" />
              in four steps.
            </>
          }
          action={
            <Button to="/demo" tone="blueprint" arrow>
              Try the live demo
            </Button>
          }
        >
          No new website and no call centre. Add one line to the site you already have, and LeadOps scores every visit as it
          happens and hands your team the buyers who are ready, with the reasons.
        </SectionHead>

        <div ref={ref} className="mt-20 lg:px-14">
          <ol className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((item, index) => {
              const active = index === step;
              return (
                <li key={item.title}>
                  <button
                    type="button"
                    aria-current={active ? "step" : undefined}
                    onClick={() => {
                      setStep(index);
                      setChosen(true);
                    }}
                    className={`w-full text-left transition-opacity ${active ? "" : "opacity-50 hover:opacity-80"}`}
                  >
                    <span className="block h-0.5 overflow-hidden rounded-full bg-line">
                      <span
                        key={`${step}-${running}`}
                        className={`block h-full bg-ink ${active && running ? "step-fill" : ""}`}
                        style={{ width: active ? "100%" : "0%", "--step-ms": `${STEP_MS}ms` }}
                      />
                    </span>
                    <span className="mt-4 block font-mono text-[13px] text-blueprint">0{index + 1}</span>
                    <span className="mt-1 block font-medium">{item.title}</span>
                    <span className="mt-1 block text-sm text-muted">{item.text}</span>
                  </button>
                </li>
              );
            })}
          </ol>

          <div className="mt-12 overflow-hidden rounded-[18px] border border-line bg-white shadow-[0_40px_90px_-50px_rgb(14_24_38/0.45)]">
            <div className="flex items-center gap-3 border-b border-line bg-concrete px-4 py-3 text-sm">
              <span className="flex gap-1.5" aria-hidden="true">
                {[0, 1, 2].map((dot) => (
                  <span key={dot} className="size-2.5 rounded-full bg-line" />
                ))}
              </span>
              <span className="text-muted">LeadOps</span>
              <span className="font-medium">{STEPS[step].title}</span>
              <Mono className="ml-auto text-muted">
                {step + 1}/{STEPS.length}
              </Mono>
            </div>
            <div className="grid sm:grid-cols-[160px_1fr]">
              <ul className="hidden flex-col gap-1 border-r border-line bg-concrete/60 p-3 sm:flex" aria-hidden="true">
                {STEPS.map((item, index) => (
                  <li key={item.tab} className={`rounded-lg px-3 py-2 text-sm ${index === step ? "bg-blueprint-line font-medium text-blueprint" : "text-muted"}`}>
                    {item.tab}
                  </li>
                ))}
              </ul>
              <div key={step} className="min-h-[300px] p-5 sm:p-7" aria-live="polite">
                <Panel />
              </div>
            </div>
          </div>
        </div>
      </Container>
    </Section>
  );
}
