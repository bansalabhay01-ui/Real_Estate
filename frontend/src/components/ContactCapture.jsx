import { useId, useMemo, useRef, useState } from "react";
import { bookVisit, sendLead } from "../lib/api";

const WORDS = {
  en: {
    name: "Your name",
    mobile: "Mobile number",
    day: "Day",
    time: "Time",
    consent: "You can call or WhatsApp me about this.",
    book: "Book the visit",
    send: "Send",
    sending: "Sending...",
    failed: "That didn't go through. Check your details and try again.",
    thanks: "Thanks! The sales team will contact you soon.",
    slots: { morning: "Morning", afternoon: "Afternoon", evening: "Evening" },
  },
  hinglish: {
    name: "Aapka naam",
    mobile: "Mobile number",
    day: "Din",
    time: "Samay",
    consent: "Aap is baare mein mujhe call ya WhatsApp kar sakte hain.",
    book: "Visit book karein",
    send: "Bhejein",
    sending: "Bhej rahe hain...",
    failed: "Ye nahi ho paya. Apni details dekh kar dobara koshish kijiye.",
    thanks: "Dhanyavaad! Sales team jaldi aapse sampark karegi.",
    slots: { morning: "Subah", afternoon: "Dopahar", evening: "Shaam" },
  },
  hi: {
    name: "आपका नाम",
    mobile: "मोबाइल नंबर",
    day: "दिन",
    time: "समय",
    consent: "आप इस बारे में मुझे कॉल या व्हाट्सऐप कर सकते हैं।",
    book: "विज़िट बुक करें",
    send: "भेजें",
    sending: "भेज रहे हैं...",
    failed: "यह नहीं हो पाया। अपनी जानकारी देखकर फिर कोशिश कीजिए।",
    thanks: "धन्यवाद! सेल्स टीम जल्द ही आपसे संपर्क करेगी।",
    slots: { morning: "सुबह", afternoon: "दोपहर", evening: "शाम" },
  },
  mr: {
    name: "तुमचे नाव",
    mobile: "मोबाइल नंबर",
    day: "दिवस",
    time: "वेळ",
    consent: "तुम्ही याबद्दल मला कॉल किंवा व्हॉट्सअ‍ॅप करू शकता.",
    book: "व्हिजिट बुक करा",
    send: "पाठवा",
    sending: "पाठवत आहे...",
    failed: "हे झाले नाही. तुमची माहिती तपासून पुन्हा प्रयत्न करा.",
    thanks: "धन्यवाद! सेल्स टीम लवकरच तुमच्याशी संपर्क करेल.",
    slots: { morning: "सकाळी", afternoon: "दुपारी", evening: "संध्याकाळी" },
  },
};

const fieldClass = "w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-base text-ink focus:border-blueprint";

function isoDay(day) {
  const month = String(day.getMonth() + 1).padStart(2, "0");
  return `${day.getFullYear()}-${month}-${String(day.getDate()).padStart(2, "0")}`;
}

// The next ten days, plus the day the visitor asked for if it is further away.
function dayChoices(asked) {
  const days = Array.from({ length: 10 }, (_, index) => {
    const day = new Date();
    day.setDate(day.getDate() + index + 1);
    return day;
  });
  const choices = days.map((day) => ({
    value: isoDay(day),
    saturday: day.getDay() === 6,
    text: day.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" }),
  }));
  if (asked && !choices.some((choice) => choice.value === asked)) {
    const day = new Date(`${asked}T12:00:00`);
    choices.unshift({ value: asked, saturday: false, text: day.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" }) });
  }
  return choices;
}

// The small form in the assistant: a phone number is never typed into the chat itself, so it never reaches the LLM.
// action: { purpose: "site_visit" | "callback" | "offer", listing_id, need_contact, day, slot, offer }
export default function ContactCapture({ action, language = "en", onDone }) {
  const words = WORDS[language] ?? WORDS.en;
  const forVisit = action.purpose === "site_visit";
  const choices = useMemo(() => (forVisit ? dayChoices(action.day) : []), [forVisit, action.day]);
  const [fields, setFields] = useState({
    name: "",
    phone: "",
    consent: false,
    website: "", // the honeypot
    day: action.day ?? (choices.find((choice) => choice.saturday) ?? choices[0])?.value ?? "",
    slot: action.slot ?? "morning",
  });
  const [status, setStatus] = useState("idle"); // idle | sending | error
  const [problem, setProblem] = useState(null);
  const startedAt = useRef(null);
  const id = useId();

  const update = (key) => (event) => {
    startedAt.current ??= Date.now();
    const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
    setFields((current) => ({ ...current, [key]: value }));
  };

  async function submit(event) {
    event.preventDefault();
    setStatus("sending");
    setProblem(null);
    const contact = {
      name: fields.name.trim(),
      phone: fields.phone.trim(),
      consent: fields.consent,
      honeypot: fields.website,
      form_fill_ms: startedAt.current ? Date.now() - startedAt.current : 0,
    };
    try {
      if (forVisit) {
        const visit = await bookVisit({
          listing_id: action.listing_id,
          day: fields.day,
          slot: fields.slot,
          language,
          ...(action.need_contact ? contact : {}),
        });
        onDone(visit.confirmation);
      } else {
        await sendLead({
          ...contact,
          listing_id: action.listing_id ?? null,
          message: action.message ?? "Asked for a call back",
          source: action.purpose === "offer" ? "assistant_offer" : "chat",
          client_ts: Date.now(),
          page_url: window.location.href,
        });
        onDone(action.thanks ?? words.thanks);
      }
    } catch (error) {
      setStatus("error");
      setProblem(error.status === 422 && error.message.length < 90 ? error.message : words.failed);
    }
  }

  return (
    <form onSubmit={submit} className="relative flex w-full flex-col gap-2.5 rounded-md border border-line bg-white p-3 text-sm">
      {forVisit && (
        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1 font-medium text-ink-soft">
            {words.day}
            <select value={fields.day} onChange={update("day")} className={fieldClass}>
              {choices.map((choice) => (
                <option key={choice.value} value={choice.value}>
                  {choice.text}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 font-medium text-ink-soft">
            {words.time}
            <select value={fields.slot} onChange={update("slot")} className={fieldClass}>
              {Object.entries(words.slots).map(([value, text]) => (
                <option key={value} value={value}>
                  {text}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {action.need_contact && (
        <>
          <label className="flex flex-col gap-1 font-medium text-ink-soft">
            {words.name}
            <input required autoComplete="name" value={fields.name} onChange={update("name")} className={fieldClass} />
          </label>
          <label className="flex flex-col gap-1 font-medium text-ink-soft">
            {words.mobile}
            <input
              required
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              pattern="[0-9+ \-]{10,15}"
              title="A 10-digit mobile number"
              value={fields.phone}
              onChange={update("phone")}
              className={fieldClass}
            />
          </label>
          {/* Honeypot: hidden from people and screen readers. */}
          <div aria-hidden="true" className="absolute -left-[9999px] top-0 h-px w-px overflow-hidden">
            <label htmlFor={`${id}-website`}>Website</label>
            <input id={`${id}-website`} type="text" name="website" tabIndex={-1} autoComplete="off" value={fields.website} onChange={update("website")} />
          </div>
          <label className="flex items-start gap-2 text-ink-soft">
            <input required type="checkbox" checked={fields.consent} onChange={update("consent")} className="mt-1 accent-blueprint" />
            {words.consent}
          </label>
        </>
      )}

      {problem && (
        <p role="alert" className="font-medium text-alert">
          {problem}
        </p>
      )}
      <button
        type="submit"
        disabled={status === "sending"}
        className="rounded-md bg-marigold px-3 py-2 font-semibold text-ink hover:bg-[#e09500] disabled:opacity-60"
      >
        {status === "sending" ? words.sending : (action.cta ?? (forVisit ? words.book : words.send))}
      </button>
    </form>
  );
}
