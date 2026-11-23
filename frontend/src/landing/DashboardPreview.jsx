// "Every lead lands on one live screen": a preview of the sales dashboard and the path from visitor to hot lead.
import { useRef } from "react";
import { Button, Container, Eyebrow, Rule, Section } from "../components/ui";
import { DarkLabel, latestRows, tally, useArrivals } from "./LiveSort";

const INTENT = { Bot: null, Junk: null, Cold: 22, Warm: 54, Hot: 80, Review: 41 };

function Preview() {
  const ref = useRef(null);
  const { arrived, animate } = useArrivals(ref);
  const rows = latestRows(arrived);
  const counts = tally(arrived);
  return (
    <figure ref={ref} className="overflow-hidden rounded-[18px] border border-white/10 bg-night-2 shadow-[0_40px_90px_-40px_rgb(0_0_0/0.8)]">
      <div className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
        <span className="flex gap-1.5" aria-hidden="true">
          {[0, 1, 2].map((dot) => (
            <span key={dot} className="size-2.5 rounded-full bg-white/15" />
          ))}
        </span>
        <span className="mx-auto flex gap-1 rounded-full bg-white/[0.05] p-1 text-xs" aria-hidden="true">
          <span className="rounded-full bg-white/10 px-3 py-1 font-medium">Visitors</span>
          <span className="px-3 py-1 text-white/60">Enquiries</span>
          <span className="hidden px-3 py-1 text-white/60 sm:inline">Site visits</span>
        </span>
        <span className="inline-flex items-center gap-1.5 text-xs text-white/70">
          <span className="size-1.5 rounded-full bg-[#4cc38a] motion-safe:animate-pulse" aria-hidden="true" />
          Live
        </span>
      </div>
      <dl className="grid grid-cols-3 gap-3 p-4">
        {[
          ["Visitors today", 240 + arrived],
          ["Hot right now", 3 + counts.hot],
          ["Filtered out", 170 + counts.bots + counts.junk],
        ].map(([name, value]) => (
          <div key={name} className="flex flex-col-reverse gap-1 rounded-[12px] border border-white/10 bg-white/[0.04] p-3">
            <dt className="text-xs text-white/60">{name}</dt>
            <dd className="tabular text-xl font-medium">{value}</dd>
          </div>
        ))}
      </dl>
      <table className="w-full text-left text-sm">
        <thead className="font-mono text-[11px] text-white/55">
          <tr>
            <th scope="col" className="px-4 pb-2 font-normal">
              Visitor
            </th>
            <th scope="col" className="px-2 pb-2 font-normal">
              Label
            </th>
            <th scope="col" className="px-2 pb-2 font-normal">
              Intent
            </th>
            <th scope="col" className="hidden px-4 pb-2 font-normal md:table-cell">
              Why
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.key} className={`border-t border-white/[0.06] ${index === 0 && animate ? "row-in" : ""}`}>
              <td className="px-4 py-2.5 font-mono text-xs text-white/60">{row.id}</td>
              <td className="px-2 py-2.5">
                <DarkLabel label={row.label} />
              </td>
              <td className="tabular px-2 py-2.5 text-white/85">{INTENT[row.label] ?? "-"}</td>
              <td className="hidden max-w-[240px] truncate px-4 py-2.5 text-white/70 md:table-cell">{row.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
const STAGES = [
  { name: "All visitors", note: "everyone who opened the site", items: ["Scraper: 14 pages in 20 seconds", "Buyer from Pune: 3 homes", "Form bot: no browsing at all"] },
  { name: "Real people", note: "bots are gone", items: ["Buyer from Pune: 3 homes", "Broker: 11 homes in 4 cities"] },
  { name: "Real contacts", note: "fake details and brokers are gone", items: ["Buyer from Pune: number checked by OTP"] },
  { name: "Hot leads", note: "worth a call today", items: ["Buyer from Pune: intent 80"] },
];

export default function DashboardPreview() {
  return (
    <Section tone="night" id="dashboard" aria-labelledby="dashboard-title" className="scroll-mt-16 overflow-hidden pb-40 sm:pb-48">
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_50%_40%_at_75%_35%,rgb(29_79_145/0.35),transparent_70%)]"
        aria-hidden="true"
      />
      <Container className="relative pt-24 sm:pt-32">
        <div className="grid items-center gap-14 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <Eyebrow className="text-white/60">Sales dashboard</Eyebrow>
            <h2 id="dashboard-title" className="text-section mt-4">
              Every lead lands on one live screen.
            </h2>
            <p className="text-lede mt-6 max-w-[46ch] text-white/70">
              Visitors appear the moment they arrive and change label as they browse. Filter by Hot, open anyone for their
              timeline, conversation and score, and mark them Genuine, Fake or Converted so the model learns.
            </p>
            <Button to="/dashboard" tone="light" className="mt-8" arrow>
              Open the dashboard
            </Button>
          </div>
          <div className="lg:col-span-7">
            <Preview />
            <p className="mt-3 font-mono text-xs text-white/60">An illustration, with visitors from the demo&apos;s simulated traffic.</p>
          </div>
        </div>

        <div className="mt-28">
          <Rule />
          <div className="mt-6 grid gap-5 lg:grid-cols-12">
            <Eyebrow className="text-white/60 lg:col-span-3">From visitor to hot lead</Eyebrow>
            <h3 className="text-title lg:col-span-9">Bots drop out first, then fake details and brokers. What&apos;s left is worth a call.</h3>
          </div>
          <ol className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {STAGES.map((stage, index) => (
              <li key={stage.name} className="flex flex-col rounded-[18px] border border-white/10 bg-white/[0.03] p-4">
                <p className="flex items-baseline justify-between gap-2">
                  <span className="font-medium">{stage.name}</span>
                  <span className="font-mono text-xs text-white/55">0{index + 1}</span>
                </p>
                <p className="text-sm text-white/60">{stage.note}</p>
                <ul className="mt-4 flex flex-col gap-2">
                  {stage.items.map((item) => (
                    <li
                      key={item}
                      className={`rounded-[10px] border px-3 py-2 text-sm ${
                        item.startsWith("Buyer") ? "border-marigold/40 bg-marigold/10 text-white" : "border-white/10 bg-white/[0.04] text-white/70"
                      }`}
                    >
                      {item}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </div>
      </Container>
    </Section>
  );
}
