// The top of the front page: the header, the hero, the strip of signals LeadOps reads, the problem and the results.
import { useEffect, useState } from "react";
import { Button, Container, Eyebrow, Logo, Marquee, RevealText, Rule, Section, useReducedMotion } from "../components/ui";

export const REPO_URL = "https://github.com/bansalabhay01-ui/Real_Estate";
export const RESULTS_URL = `${REPO_URL}/blob/main/docs/RESULTS.md`;

// Measured results from docs/RESULTS.md. Update them when ml/evaluate.py runs again.
export const RESULTS = { realBotsCaught: 15, realBotsRun: 15, simulatedVisitors: "1,000" };

const SECTIONS = [
  ["How it works", "#how"],
  ["Live sorting", "#watch"],
  ["Dashboard", "#dashboard"],
  ["Privacy", "#privacy"],
  ["FAQ", "#faq"],
];

export function SiteHeader() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const update = () => setScrolled(window.scrollY > 40);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);

  return (
    <header
      data-tone="dark"
      className={`fixed inset-x-0 top-0 z-40 text-white transition-colors duration-300 ${
        scrolled ? "border-b border-white/10 bg-night/95 backdrop-blur-md" : "border-b border-transparent"
      }`}
    >
      <div className="mx-auto flex h-[72px] max-w-[1376px] items-center justify-between gap-4 px-5 sm:px-8">
        <Logo to="/" />
        <nav aria-label="Sections of this page" className="hidden rounded-full border border-white/10 bg-white/[0.04] p-1 md:flex">
          {SECTIONS.map(([text, href]) => (
            <a key={href} href={href} className="rounded-full px-4 py-1.5 text-sm text-white/75 transition-colors hover:bg-white/[0.08] hover:text-white">
              {text}
            </a>
          ))}
        </nav>
        <Button to="/demo" tone="light" size="sm" arrow>
          Try the live demo
        </Button>
      </div>
    </header>
  );
}

const PILL_LABELS = [
  { text: "Bot", dot: "bg-[#ff8f8f]" },
  { text: "Junk", dot: "bg-[#ffc46b]" },
  { text: "Hot", dot: "bg-marigold" },
];

// The pill inside the headline: a scan line sweeps across while a visitor's label flips from Bot to Junk to Hot.
function LabelPill() {
  const reduced = useReducedMotion();
  const [index, setIndex] = useState(PILL_LABELS.length - 1);
  useEffect(() => {
    if (reduced) {
      setIndex(PILL_LABELS.length - 1);
      return undefined;
    }
    const timer = setInterval(() => setIndex((current) => (current + 1) % PILL_LABELS.length), 1800);
    return () => clearInterval(timer);
  }, [reduced]);
  const label = PILL_LABELS[index];

  return (
    <span
      aria-hidden="true"
      className="relative mx-[0.06em] inline-flex h-[0.7em] w-[1.75em] -translate-y-[0.06em] items-center justify-center overflow-hidden rounded-full border border-sky/30 bg-deep-2/80 align-middle shadow-[inset_0_0_28px_rgb(143_192_255/0.2)]"
    >
      <span className="scan-line absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-sky/35 to-transparent" />
      <span key={label.text} className="label-in relative flex items-center gap-[0.16em] font-mono text-[0.27em] font-medium tracking-normal text-white">
        <span className={`size-[0.34em] rounded-full ${label.dot}`} />
        {label.text}
      </span>
    </span>
  );
}

const FACTS = [
  ["1 script tag", "on any website"],
  ["3 checks", "on every visitor"],
  ["4 languages", "in the assistant"],
  [`${RESULTS.realBotsCaught}/${RESULTS.realBotsRun}`, "real bots caught in testing"],
];

export function Hero() {
  return (
    <Section tone="night" rounded={false} className="hero-glow overflow-hidden" aria-labelledby="hero-title">
      <div className="drafting-grid pointer-events-none absolute inset-0" aria-hidden="true" />
      <Container className="relative pb-10 pt-36 sm:pt-44 lg:pt-52">
        <h1 id="hero-title" className="text-display">
          <span className="rise block">Every website visitor,</span>
          <span className="rise block [animation-delay:140ms]">
            sorted <LabelPill /> <span className="text-marigold">in seconds.</span>
          </span>
        </h1>
        <p className="rise text-lede mt-8 max-w-[56ch] text-white/75 [animation-delay:280ms]">
          LeadOps blocks bots, fake numbers and rival brokers on your property website, and shows your sales team which buyers are
          ready, including the ones who never fill in a form.
        </p>
        <div className="rise mt-10 flex flex-wrap gap-3 [animation-delay:400ms]">
          <Button to="/demo" tone="marigold" size="lg" arrow>
            Try the live demo
          </Button>
          <Button href="#watch" tone="outline-dark" size="lg">
            <span className="flex h-3.5 items-end gap-[3px]" aria-hidden="true">
              {[6, 10, 14, 8].map((height, index) => (
                <span key={index} className="w-[3px] rounded-full bg-sky" style={{ height }} />
              ))}
            </span>
            Watch it sort traffic
          </Button>
        </div>

        <Rule className="mt-24 sm:mt-32" />
        <ul className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 lg:grid-cols-4">
          {FACTS.map(([value, text]) => (
            <li key={text} className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-2.5">
              <span className="text-[15px] font-medium">{value}</span>
              <span className="font-mono text-[13px] text-white/60">{text}</span>
            </li>
          ))}
        </ul>
      </Container>
      <div className="glow-band relative h-28 sm:h-40" aria-hidden="true" />
    </Section>
  );
}

const HOW_THEY_BROWSE = [
  "Mouse movement",
  "Scroll depth",
  "Time on each page",
  "Pages per minute",
  "Scripted clicks",
  "Automation flags",
  "Headless browsers",
  "The hidden form field",
];
const WHO_THEY_ARE = [
  "Fake phone numbers",
  "Throwaway emails",
  "Broker pitches",
  "Spam links",
  "EMI calculator use",
  "Floor-plan downloads",
  "Repeat visits",
  "Budget and move-in date",
];

function SignalStrip({ items, reverse, duration }) {
  return (
    <Marquee reverse={reverse} duration={duration}>
      {items.map((item) => (
        <span key={item} className="flex items-center gap-4 px-7 text-[clamp(1.15rem,2vw,1.5rem)] font-medium tracking-[-0.02em] text-white/55">
          <span className="size-1.5 rotate-45 bg-sky/60" aria-hidden="true" />
          {item}
        </span>
      ))}
    </Marquee>
  );
}

// Where masal.ai shows its customers' logos, LeadOps shows what it reads: it has no customers yet.
export function Signals() {
  return (
    <Section tone="night" rounded={false} aria-label="What LeadOps reads on every visit">
      <Container className="pt-10">
        <Eyebrow className="text-white/60">What LeadOps reads on every visit</Eyebrow>
      </Container>
      <div className="mt-8 flex flex-col gap-6 pb-4">
        <SignalStrip items={HOW_THEY_BROWSE} duration={64} />
        <SignalStrip items={WHO_THEY_ARE} duration={72} reverse />
      </div>
    </Section>
  );
}

const PROBLEM =
  "A property website gets thousands of visitors. Many of its enquiries come from bots, fake numbers and rival brokers, " +
  "and the sales team spends its day calling them. Meanwhile the serious buyers study the floor plans, check the EMI and " +
  "leave without a trace. LeadOps watches how every visitor browses, blocks the fakes and puts the real buyers in front of " +
  "your team, with the reasons.";

export function WhyLeadOps() {
  return (
    <Section tone="night" rounded={false} aria-labelledby="why-title" className="pb-40 sm:pb-48">
      <Container className="pt-24 sm:pt-32">
        <Rule />
        <div className="mt-6 grid gap-6 lg:grid-cols-12">
          <h2 id="why-title" className="font-mono text-[13px] font-normal leading-5 text-marigold lg:col-span-4">
            Why LeadOps
          </h2>
          <div className="lg:col-span-8">
            <RevealText text={PROBLEM} className="text-[clamp(1.5rem,2.9vw,2.5rem)] font-medium leading-[1.22] tracking-[-0.03em]" />

            <div className="mt-20">
              <Rule />
              <Eyebrow className="mt-5 text-marigold">Measured in our tests</Eyebrow>
              <dl className="mt-6 grid gap-10 sm:grid-cols-2">
                <div>
                  <dt className="sr-only">Real bots caught</dt>
                  <dd className="tabular text-[clamp(3rem,6vw,5rem)] font-medium leading-none tracking-[-0.05em]">
                    {RESULTS.realBotsCaught}/{RESULTS.realBotsRun}
                  </dd>
                  <dd className="mt-3 max-w-[30ch] text-white/65">real browser bots caught: the team&apos;s own Playwright bots, stealth one included</dd>
                </div>
                <div>
                  <dt className="sr-only">Simulated visitors sorted</dt>
                  <dd className="tabular text-[clamp(3rem,6vw,5rem)] font-medium leading-none tracking-[-0.05em] text-marigold">
                    {RESULTS.simulatedVisitors}
                  </dd>
                  <dd className="mt-3 max-w-[30ch] text-white/65">simulated visitors sorted, with every fake filtered and no real buyer lost</dd>
                </div>
              </dl>
              <p className="mt-10 max-w-[60ch] text-white/75">
                Simulated traffic is the easy test, so the results page keeps it apart from real people.{" "}
                <a href={RESULTS_URL} className="font-medium text-sky underline underline-offset-4 hover:text-white">
                  See how we measured
                </a>
              </p>
            </div>
          </div>
        </div>
      </Container>
    </Section>
  );
}
