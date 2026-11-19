import { useEffect, useState } from "react";
import { eraseMyData, getHealth } from "../lib/api";
import { answerConsent, consentChoice, visitorIds } from "../lib/leadops";

function Part({ title, children }) {
  return (
    <section>
      <h2 className="font-wide text-xl font-semibold">{title}</h2>
      <div className="mt-2 flex flex-col gap-2 text-ink-soft">{children}</div>
    </section>
  );
}

export default function Privacy() {
  const [days, setDays] = useState(null);
  const [choice, setChoice] = useState(() => consentChoice());
  const [erased, setErased] = useState("idle"); // idle | erasing | done | nothing | failed

  useEffect(() => {
    document.title = "Privacy notice | LeadOps Realty";
    getHealth()
      .then((health) => setDays(health.retention_days))
      .catch(() => {});
    return () => {
      document.title = "LeadOps Realty (demo)";
    };
  }, []);

  function change(granted) {
    answerConsent(granted);
    setChoice(granted ? "granted" : "denied");
  }

  async function erase() {
    const { visitor_id: visitorId } = visitorIds();
    setErased("erasing");
    try {
      if (visitorId) await eraseMyData(visitorId);
      change(false);
      setErased(visitorId ? "done" : "nothing");
    } catch (error) {
      if (error.status === 404) {
        change(false);
        setErased("nothing");
      } else {
        setErased("failed");
      }
    }
  }

  const status = { granted: "You have agreed to tracking.", denied: "You have declined tracking." }[choice] ?? "You haven't chosen yet.";
  const button = "rounded-md border border-ink px-4 py-2 text-sm font-semibold hover:bg-ink hover:text-white disabled:border-line disabled:text-muted disabled:hover:bg-transparent";

  return (
    <article className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10">
      <header>
        <h1 className="font-extra-wide text-4xl font-bold tracking-tight">Privacy notice</h1>
        <p className="mt-2 text-ink-soft">LeadOps Realty is a demo site. This notice shows how a real site using LeadOps treats your data under India&apos;s DPDP Act 2023.</p>
      </header>

      <Part title="What we record, if you agree">
        <ul className="list-disc space-y-1 pl-5">
          <li>The pages and homes you open, how long you stay, and whether you use the EMI calculator or floor plans.</li>
          <li>Counts of mouse moves, scrolls, touches and key presses. We never record what you type into a form.</li>
          <li>Your browser type, screen size, time zone and IP address.</li>
          <li>An anonymous ID in your browser, so a return visit is linked to the first one.</li>
          <li>What you tell the assistant, and the details you send in an enquiry.</li>
        </ul>
      </Part>

      <Part title="Why">
        <p>To suggest homes that fit, to let our sales team follow up with people who are really interested, and to keep out bots and fake enquiries.</p>
        <p>Phone numbers and email addresses are hidden before any text reaches an AI service, and your name is never sent to one.</p>
      </Part>

      <Part title="How long we keep it">
        <p>
          {days ? `Browsing and chat are deleted after ${days} days.` : "Browsing and chat are deleted automatically after a set period."} Enquiries older than that lose
          your name, number, email and message.
        </p>
      </Part>

      <Part title="Your choices">
        <p role="status">{status}</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={choice === "granted"} onClick={() => change(true)} className={button}>
            Accept tracking
          </button>
          <button type="button" disabled={choice === "denied"} onClick={() => change(false)} className={button}>
            Decline tracking
          </button>
        </div>
      </Part>

      <Part title="Delete your data">
        <p>This removes everything linked to this browser: your visits, conversation and enquiries. It also turns tracking off.</p>
        <div>
          <button type="button" disabled={erased === "erasing"} onClick={erase} className={button}>
            {erased === "erasing" ? "Deleting..." : "Delete my data"}
          </button>
        </div>
        <p role="status" className="font-medium text-ink">
          {erased === "done" && "Your data has been deleted."}
          {erased === "nothing" && "We hold no data linked to this browser."}
        </p>
        {erased === "failed" && (
          <p role="alert" className="font-medium text-alert">
            That didn&apos;t work. Check your connection and try again.
          </p>
        )}
      </Part>
    </article>
  );
}
