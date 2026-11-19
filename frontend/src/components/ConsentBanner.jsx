import { useState } from "react";
import { Link } from "react-router";
import { answerConsent, consentChoice } from "../lib/leadops";

// Asked before anything is recorded (DPDP Act 2023). Saying no is as easy as saying yes, and the site works either way.
export default function ConsentBanner() {
  const [answered, setAnswered] = useState(() => consentChoice() !== null);
  if (answered) return null;

  function answer(granted) {
    answerConsent(granted);
    setAnswered(true);
  }

  const button = "rounded-md border border-ink px-4 py-2 text-sm font-semibold hover:bg-ink hover:text-white";
  return (
    <aside aria-label="Your privacy choice" className="fixed inset-x-0 bottom-0 z-50 border-t border-line bg-white shadow-2xl shadow-ink/20">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-2xl text-sm text-ink-soft">
          May we record how you use this site? It helps our team suggest the right homes and keeps fake enquiries out. Nothing is
          recorded unless you agree.{" "}
          <Link to="/privacy" className="font-medium text-blueprint underline underline-offset-2">
            Read the privacy notice
          </Link>
        </p>
        <div className="flex shrink-0 gap-2">
          <button type="button" onClick={() => answer(true)} className={button}>
            Accept
          </button>
          <button type="button" onClick={() => answer(false)} className={button}>
            Decline
          </button>
        </div>
      </div>
    </aside>
  );
}
