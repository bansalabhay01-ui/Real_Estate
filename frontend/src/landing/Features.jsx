// What else LeadOps does: offers for silent buyers, the assistant, says-versus-does checks, learning from sales,
// follow-ups in the buyer's language and privacy. Every message shown is one the app really produces.
import FloorPlan from "../components/FloorPlan";
import { Container, Eyebrow, Section, SectionHead } from "../components/ui";

function Card({ label, title, children, visual, className = "" }) {
  return (
    <article className={`flex flex-col rounded-[22px] border border-line bg-white p-5 sm:p-7 ${className}`}>
      <Eyebrow className="text-blueprint">{label}</Eyebrow>
      <h3 className="text-title mt-3">{title}</h3>
      <p className="mt-2 max-w-[52ch] text-muted">{children}</p>
      <div className="mt-6 flex-1 overflow-hidden rounded-[16px] bg-concrete">{visual}</div>
    </article>
  );
}

function OfferVisual() {
  return (
    <div className="relative h-full min-h-[300px] p-5">
      <div className="max-w-[300px] overflow-hidden rounded-[12px] border border-line bg-white" aria-hidden="true">
        <FloorPlan bhk={3} area={1180} compact className="block aspect-[16/10] w-full" />
        <div className="flex flex-col gap-1.5 p-3">
          <span className="text-sm font-medium">Aranya Courtyard</span>
          <span className="text-xs text-muted">Wagholi, Pune: 3 BHK, ₹86 L</span>
        </div>
      </div>
      <div className="absolute bottom-5 right-5 w-[min(300px,calc(100%-2.5rem))] rounded-[16px] border border-line bg-white p-4 shadow-[0_24px_50px_-24px_rgb(14_24_38/0.5)]">
        <p className="text-xs font-medium text-blueprint">Property assistant</p>
        <p className="mt-1.5 text-sm">Want the 3 BHK floor plan of Aranya Courtyard on WhatsApp?</p>
        <p className="mt-3 flex gap-2" aria-hidden="true">
          <span className="rounded-full bg-marigold px-3 py-1.5 text-xs font-medium text-night">Send it to me</span>
          <span className="rounded-full border border-line px-3 py-1.5 text-xs font-medium">No thanks</span>
        </p>
      </div>
    </div>
  );
}

const LANGUAGES = [
  ["English", "3BHK under 90L in Pune"],
  ["Hinglish", "Pune mein 90 lakh tak 3BHK chahiye"],
  ["Hindi", "पुणे में 90 लाख तक 3BHK चाहिए"],
  ["Marathi", "पुण्यात 90 लाखांपर्यंत 3BHK हवा आहे"],
];

function LanguagesVisual() {
  return (
    <ul className="flex flex-col gap-3 p-5">
      {LANGUAGES.map(([language, message]) => (
        <li key={language} className="flex flex-col items-end gap-1">
          <span className="font-mono text-[11px] text-muted">{language}</span>
          <span lang={language === "Hindi" ? "hi" : language === "Marathi" ? "mr" : "en"} className="max-w-[92%] rounded-[14px] rounded-br-sm bg-blueprint px-3 py-2 text-sm text-white">
            {message}
          </span>
        </li>
      ))}
    </ul>
  );
}

function ConsistencyVisual() {
  return (
    <div className="flex flex-col gap-3 p-5">
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-[12px] border border-line bg-white p-3">
          <span className="block text-xs text-muted">Told the assistant</span>
          <span className="mt-1 block font-medium">Under ₹50 L</span>
        </div>
        <div className="rounded-[12px] border border-line bg-white p-3">
          <span className="block text-xs text-muted">Opened</span>
          <span className="mt-1 block font-medium">Homes around ₹1.45 Cr</span>
        </div>
      </div>
      <p className="rounded-[12px] border border-amber/30 bg-[#fdf3e1] px-3 py-2.5 text-sm">
        <span className="block text-xs font-medium text-amber">Ask about this on the call</span>
        Says under ₹50 L but opened homes around ₹1.45 Cr
      </p>
    </div>
  );
}

function LearningVisual() {
  return (
    <div className="flex h-full flex-col justify-center gap-4 p-5">
      <p className="flex flex-wrap gap-2" aria-hidden="true">
        <span className="rounded-full bg-night px-3.5 py-1.5 text-sm font-medium text-white">Genuine</span>
        <span className="rounded-full border border-line bg-white px-3.5 py-1.5 text-sm font-medium">Fake</span>
        <span className="rounded-full border border-line bg-white px-3.5 py-1.5 text-sm font-medium">Converted</span>
      </p>
      <p className="text-sm text-ink-soft">
        A verdict counts at once: <span className="font-medium text-ink">Fake</span> makes a visitor Junk, and{" "}
        <span className="font-medium text-ink">Genuine</span> overrules the rules and the model. The next training run learns from every one.
      </p>
    </div>
  );
}

export function Features() {
  return (
    <Section tone="paper" aria-labelledby="features-title" className="pb-40 sm:pb-48">
      <Container className="pt-24 sm:pt-32">
        <SectionHead
          label="Built in"
          titleId="features-title"
          title={
            <>
              Catch the buyers <br className="hidden sm:block" />
              who never fill a form.
            </>
          }
        >
          Most serious buyers browse, compare and leave without a trace. LeadOps notices them while they&apos;re still on the page.
        </SectionHead>
        <div className="mt-16 grid gap-4 lg:grid-cols-12">
          <Card className="lg:col-span-7" label="Smart offers" title="An offer at the right moment." visual={<OfferVisual />}>
            When a visitor looks human, shows real intent and hasn&apos;t left a number, the assistant offers something useful.
            Saying yes turns them into a lead.
          </Card>
          <Card className="lg:col-span-5" label="Property assistant" title="Answers in four languages." visual={<LanguagesVisual />}>
            Prices, EMIs, payment plans and site visits, from your listings and brochures. Numbers go through a form, never through the AI.
          </Card>
          <Card className="lg:col-span-5" label="Says versus does" title="Spots what doesn't add up." visual={<ConsistencyVisual />}>
            When what someone says doesn&apos;t match the homes they open, the brief says so, as a question for the call. It never
            changes a label on its own.
          </Card>
          <Card className="lg:col-span-7" label="Feedback loop" title="Learns from your sales team." visual={<LearningVisual />}>
            Salespeople mark leads Genuine, Fake or Converted from the dashboard, so the model keeps up with the buyers your team
            actually meets.
          </Card>
        </div>
      </Container>
    </Section>
  );
}

function Phone({ children }) {
  return (
    <div className="mx-auto w-[min(290px,100%)] rounded-[38px] border-[7px] border-night bg-night shadow-[0_40px_80px_-30px_rgb(0_0_0/0.6)]" aria-hidden="true">
      <div className="overflow-hidden rounded-[31px] bg-[#eef1f4]">{children}</div>
    </div>
  );
}

const GLOW_CARD =
  "relative overflow-hidden rounded-[22px] p-5 text-white sm:p-8 " +
  "bg-[radial-gradient(ellipse_70%_60%_at_15%_10%,rgb(242_162_12/0.35),transparent_60%),linear-gradient(140deg,var(--color-deep-2),var(--color-night))]";

export function FollowUp() {
  return (
    <Section tone="concrete" aria-labelledby="followup-title" className="pb-40 sm:pb-48">
      <Container className="pt-24 sm:pt-32">
        <SectionHead
          label="Follow-up and privacy"
          titleId="followup-title"
          title={
            <>
              Follow up in the buyer&apos;s <br className="hidden sm:block" />
              own language.
            </>
          }
        >
          One click drafts a WhatsApp message or an email in English, Hinglish, Hindi or Marathi. The AI writes it with a
          placeholder and the buyer&apos;s name goes in afterwards, so the AI never sees it.
        </SectionHead>
        <div className="mt-16 grid gap-4 lg:grid-cols-2">
          <article data-tone="dark" className={GLOW_CARD}>
            <Eyebrow className="text-marigold">WhatsApp drafts</Eyebrow>
            <h3 className="text-title mt-3">Ready to edit and send.</h3>
            <p className="mt-2 max-w-[44ch] text-white/75">Written from what the buyer looked at, in the language they used with the assistant.</p>
            <div className="mt-8">
              <Phone>
                <div className="bg-deep px-4 pb-3 pt-6 text-white">
                  <p className="text-sm font-medium">LeadOps Realty</p>
                  <p className="text-[11px] text-white/70">Draft for Priya</p>
                </div>
                <div className="flex min-h-[260px] flex-col justify-end gap-2 p-3">
                  <p className="ml-auto max-w-[88%] rounded-[12px] rounded-br-sm bg-white px-3 py-2 text-[13px] leading-5 text-ink shadow-sm">
                    Namaste Priya, main LeadOps Realty ki sales team se hoon. Aapne Aranya Courtyard, Wagholi dekha tha: 3 BHK, ₹86 L.
                    Kya Sat 28 Nov ko site visit theek rahegi?
                  </p>
                  <p className="ml-auto font-mono text-[10px] text-muted">Hinglish draft</p>
                </div>
              </Phone>
            </div>
          </article>
          <article id="privacy" data-tone="dark" className={`${GLOW_CARD} scroll-mt-24`}>
            <Eyebrow className="text-marigold">Privacy</Eyebrow>
            <h3 className="text-title mt-3">Built for the DPDP Act 2023.</h3>
            <p className="mt-2 max-w-[44ch] text-white/75">
              Visitors are asked before anything is recorded. Phone numbers and emails are hidden before any text reaches the AI,
              personal data expires after 180 days, and anyone can delete theirs.
            </p>
            <div className="mt-8">
              <Phone>
                <div className="flex min-h-[318px] flex-col justify-between gap-4 p-4 pt-8 text-ink">
                  <div className="flex flex-col gap-1.5">
                    <p className="font-mono text-[11px] text-muted">What the visitor wrote</p>
                    <p className="rounded-[10px] bg-white px-3 py-2 text-[13px]">Call me on 98765 43210 after 6 pm</p>
                    <p className="mt-2 font-mono text-[11px] text-muted">What the AI sees</p>
                    <p className="rounded-[10px] bg-white px-3 py-2 text-[13px]">Call me on [phone] after 6 pm</p>
                  </div>
                  <div className="rounded-[12px] bg-white p-3 text-[12px] leading-5 shadow-sm">
                    May we record how you use this site? Nothing is recorded unless you agree.
                    <span className="mt-2 flex gap-1.5">
                      <span className="rounded-full bg-night px-2.5 py-1 font-medium text-white">Accept</span>
                      <span className="rounded-full border border-line px-2.5 py-1 font-medium">Decline</span>
                    </span>
                  </div>
                </div>
              </Phone>
            </div>
          </article>
        </div>
      </Container>
    </Section>
  );
}
