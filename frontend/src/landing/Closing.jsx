// The end of the front page: the business model, the FAQ, the closing call to action and the footer.
import { useId, useState } from "react";
import { Link } from "react-router";
import { IconCheck, IconMinus, IconPlus } from "../components/icons";
import { Button, Container, Eyebrow, Logo, Section, SectionHead } from "../components/ui";
import { REPO_URL, RESULTS, RESULTS_URL } from "./Hero";

const MODELS = [
  {
    name: "Per qualified lead",
    text: "Pay only for visitors LeadOps marks Warm or Hot who leave a real phone number. Bots and junk cost nothing.",
  },
  {
    name: "Monthly plan",
    text: "One flat fee a month for each website, for teams that would rather know their bill in advance.",
  },
];
const INCLUDED = [
  "Bot and junk filtering, with reasons",
  "The live sales dashboard",
  "The property assistant in 4 languages",
  "Smart offers for silent buyers",
  "WhatsApp and email follow-up drafts",
  "Consent, erasure and data expiry (DPDP)",
];

export function BusinessModel() {
  return (
    <Section tone="paper" aria-labelledby="model-title" className="pb-36 sm:pb-44">
      <Container className="pt-24 sm:pt-32">
        <SectionHead
          label="Business model"
          titleId="model-title"
          title={
            <>
              Pay for buyers, <br className="hidden sm:block" />
              not for traffic.
            </>
          }
        >
          One script tag for any builder&apos;s or broker&apos;s website. Prices will be set with our first pilot customers; the two
          ways to pay are already clear.
        </SectionHead>
        <div className="mt-16 grid gap-4 lg:grid-cols-2">
          {MODELS.map((model, index) => (
            <article
              key={model.name}
              data-tone={index === 0 ? "dark" : undefined}
              className={`rounded-[22px] p-6 sm:p-8 ${index === 0 ? "bg-blueprint text-white" : "border border-line bg-white"}`}
            >
              <h3 className="text-title">{model.name}</h3>
              <p className={`mt-3 max-w-[44ch] ${index === 0 ? "text-white/80" : "text-muted"}`}>{model.text}</p>
            </article>
          ))}
        </div>
        <div className="mt-4 rounded-[22px] border border-line p-6 sm:p-8">
          <h3 className="font-medium">Both include</h3>
          <ul className="mt-4 grid gap-x-8 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
            {INCLUDED.map((item) => (
              <li key={item} className="flex gap-2.5 text-ink-soft">
                <IconCheck className="mt-1 size-4 shrink-0 text-blueprint" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </Container>
    </Section>
  );
}

const QUESTIONS = [
  [
    "Will it slow my website down?",
    "No. The script is one small file that loads after the page. It sends a short batch of counts every few seconds and never gets in the way of a click.",
  ],
  [
    "Does it read what visitors type?",
    "No. It counts key presses and mouse movement and measures timings, but it never reads what anyone types or fills in.",
  ],
  [
    "How accurate is it?",
    `It caught ${RESULTS.realBotsCaught} of ${RESULTS.realBotsRun} real browser bots in our tests, and sorted ${RESULTS.simulatedVisitors} simulated visitors without losing a real buyer. Simulated traffic is the easy test, so the results page keeps real people apart. Anything uncertain goes to Review, so a real buyer is never thrown away without a person looking.`,
  ],
  [
    "Can a clever bot fool it?",
    "Hiding the automation flag isn't enough. The model looks at how the mouse moves, how long pages are read and how the form is filled, and anything unsure goes to Review for a person to check.",
  ],
  [
    "Which languages does the assistant speak?",
    "English, Hinglish, Hindi and Marathi. It replies in the language the visitor uses, and keeps it for short replies like \"3 BHK\".",
  ],
  [
    "What if the AI service is down, or we have no API key?",
    "Everything keeps working. The assistant, the briefs and the follow-ups fall back to templates and keyword rules, so scoring and the dashboard never stop.",
  ],
  [
    "Where is the data kept?",
    "In your own database. Nothing is shared or sold, the dashboard needs a passcode, and personal data expires after 180 days.",
  ],
];

function Question({ question, answer, open, onToggle }) {
  const id = useId();
  return (
    <li className="border-b border-line">
      <h3>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={id}
          onClick={onToggle}
          className="flex w-full items-center justify-between gap-6 py-6 text-left text-lg font-medium sm:text-xl"
        >
          {question}
          <span className={`grid size-9 shrink-0 place-items-center rounded-full ${open ? "bg-blueprint text-white" : "border border-line bg-white"}`}>
            {open ? <IconMinus className="size-4" /> : <IconPlus className="size-4" />}
          </span>
        </button>
      </h3>
      <p id={id} hidden={!open} className="-mt-2 max-w-[62ch] pb-6 text-muted">
        {answer}
      </p>
    </li>
  );
}

export function Faq() {
  const [open, setOpen] = useState(0);
  return (
    <Section tone="concrete" id="faq" aria-labelledby="faq-title" className="scroll-mt-16 pb-36 sm:pb-44">
      <Container className="grid gap-12 pt-24 sm:pt-32 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <Eyebrow className="text-muted">FAQ</Eyebrow>
          <h2 id="faq-title" className="text-section mt-4">
            Common questions
          </h2>
          <p className="mt-6 text-muted">
            Still curious?{" "}
            <Link to="/demo" className="font-medium text-blueprint underline underline-offset-4">
              Try the live demo
            </Link>{" "}
            and watch yourself arrive on the dashboard.
          </p>
        </div>
        <ul className="border-t border-line lg:col-span-7">
          {QUESTIONS.map(([question, answer], index) => (
            <Question key={question} question={question} answer={answer} open={open === index} onToggle={() => setOpen(open === index ? null : index)} />
          ))}
        </ul>
      </Container>
    </Section>
  );
}

// A funnel drawn as ruled bars, narrowing from every visitor to the few hot leads at the bottom.
function Funnel() {
  const bars = 11;
  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col items-center gap-2.5" aria-hidden="true">
      {Array.from({ length: bars }, (_, index) => {
        const last = index === bars - 1;
        return (
          <span
            key={index}
            className={`block h-2.5 rounded-full sm:h-3 ${last ? "bg-marigold" : "bg-ink"}`}
            style={{ width: `${100 - index * 8.6}%`, opacity: last ? 1 : 0.92 - index * 0.05 }}
          />
        );
      })}
    </div>
  );
}

export function FinalCall() {
  return (
    <Section tone="paper" aria-labelledby="final-title" className="pb-40 sm:pb-48">
      <Container className="pt-20 text-center sm:pt-28">
        <Funnel />
        <h2 id="final-title" className="text-display mx-auto mt-20 max-w-[14ch]">
          Find the real buyers in your traffic.
        </h2>
        <p className="text-lede mx-auto mt-6 max-w-[46ch] text-muted">
          Open the demo property site, browse like a buyer, and watch yourself appear on the sales dashboard.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <Button to="/demo" tone="blueprint" size="lg" arrow>
            Try the live demo
          </Button>
          <Button to="/dashboard" tone="outline" size="lg">
            Open the dashboard
          </Button>
        </div>
        <p className="mt-8 text-sm text-muted">The demo homes, prices and people are fictional.</p>
      </Container>
    </Section>
  );
}

const FOOTER_LINKS = [
  {
    title: "Product",
    links: [
      ["How it works", "#how"],
      ["Live sorting", "#watch"],
      ["Dashboard preview", "#dashboard"],
      ["FAQ", "#faq"],
    ],
  },
  {
    title: "Try it",
    links: [
      ["Demo property site", "/demo"],
      ["Sales dashboard", "/dashboard"],
      ["Analytics", "/dashboard/analytics"],
      ["Privacy notice", "/privacy"],
    ],
  },
  {
    title: "Project",
    links: [
      ["Source code", REPO_URL],
      ["How we measured", RESULTS_URL],
    ],
  },
];

function FooterLink({ href, children }) {
  const className = "text-white/70 transition-colors hover:text-white";
  if (href.startsWith("/")) {
    return (
      <Link to={href} className={className}>
        {children}
      </Link>
    );
  }
  return (
    <a href={href} className={className}>
      {children}
    </a>
  );
}

export function Footer() {
  return (
    <footer data-tone="dark" className="relative -mt-10 overflow-hidden rounded-t-[40px] bg-night text-white">
      <Container className="grid gap-12 pt-20 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <Logo to="/" />
          <p className="mt-5 max-w-[36ch] text-white/70">
            Scores every visitor on a property website, blocks bots and junk, and shows the sales team which buyers are ready.
          </p>
        </div>
        <nav aria-label="Footer" className="grid grid-cols-2 gap-8 sm:grid-cols-3 lg:col-span-8">
          {FOOTER_LINKS.map((group) => (
            <div key={group.title}>
              <p className="font-mono text-[13px] text-white/55">{group.title}</p>
              <ul className="mt-4 flex flex-col gap-2.5">
                {group.links.map(([text, href]) => (
                  <li key={text}>
                    <FooterLink href={href}>{text}</FooterLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </Container>
      <p
        aria-hidden="true"
        className="mt-16 select-none pb-[0.16em] text-center text-[clamp(5rem,21vw,19rem)] font-bold leading-[0.8] tracking-[-0.07em] text-white/[0.06]"
      >
        Lead<span className="text-marigold/[0.22]">Ops</span>
      </p>
      <Container className="flex flex-col gap-2 border-t border-white/10 py-6 text-sm text-white/60 sm:flex-row sm:justify-between">
        <p>© 2026 LeadOps, built by a team of three for a national hackathon.</p>
        <p>The demo homes and prices are fictional.</p>
      </Container>
    </footer>
  );
}
