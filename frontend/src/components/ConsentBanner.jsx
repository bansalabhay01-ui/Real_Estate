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

  const button = "rounded-full px-5 py-2 text-sm font-medium transition-colors";
  return (
    <aside
      aria-label="Your privacy choice"
      data-tone="dark"
      className="fixed inset-x-3 bottom-3 z-50 rounded-[20px] border border-white/10 bg-night/95 text-white shadow-2xl shadow-ink/40 backdrop-blur-md sm:inset-x-auto sm:left-5 sm:bottom-5 sm:max-w-xl"
    >
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-white/80">
          May we record how you use this site? It helps our team suggest the right homes and keeps fake enquiries out. Nothing is
          recorded unless you agree.{" "}
          <Link to="/privacy" className="font-medium text-sky underline underline-offset-4 hover:text-white">
            Read the privacy notice
          </Link>
        </p>
        <div className="flex shrink-0 gap-2">
          <button type="button" onClick={() => answer(true)} className={`${button} bg-white text-night hover:bg-white/90`}>
            Accept
          </button>
          <button type="button" onClick={() => answer(false)} className={`${button} border border-white/20 hover:bg-white/10`}>
            Decline
          </button>
        </div>
      </div>
    </aside>
  );
}
