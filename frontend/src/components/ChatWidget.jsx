import { useEffect, useRef, useState } from "react";
import { Link, matchPath, useLocation } from "react-router";
import { getChatHistory, sendChat } from "../lib/api";
import { formatPrice } from "../lib/format";
import { track, visitorIds } from "../lib/leadops";
import { IconChat, IconClose, IconSend } from "./icons";

const SUGGESTIONS = ["3BHK under 90L in Pune", "Pune mein 90 lakh tak 3BHK chahiye", "2 BHK near a metro"];

// Other parts of the page can open the assistant: window.dispatchEvent(new Event("leadops:open-chat"))
export const openChat = () => window.dispatchEvent(new Event("leadops:open-chat"));

function Message({ message }) {
  const mine = message.role === "user";
  return (
    <li className={`flex flex-col gap-2 ${mine ? "items-end" : "items-start"}`}>
      <p
        className={`max-w-[85%] whitespace-pre-line rounded-lg px-3 py-2 text-sm ${
          mine ? "bg-blueprint text-white" : "bg-concrete text-ink"
        }`}
      >
        {message.text}
      </p>
      {message.listings?.length > 0 && (
        <ul className="flex w-full flex-col gap-1.5">
          {message.listings.map((home) => (
            <li key={home.id}>
              <Link
                to={`/property/${home.id}`}
                className="flex items-baseline justify-between gap-3 rounded-md border border-line px-3 py-2 text-sm hover:border-blueprint"
              >
                <span>
                  <span className="font-semibold">{home.project}</span>
                  <span className="text-muted">
                    {" "}
                    {home.locality}, {home.bhk} BHK
                  </span>
                </span>
                <span className="tabular shrink-0 font-semibold">{formatPrice(home.price_inr)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export default function ChatWidget() {
  const location = useLocation();
  const listingId = matchPath("/property/:id", location.pathname)?.params.id ?? null;
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const historyLoaded = useRef(false);
  const listRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener("leadops:open-chat", show);
    return () => window.removeEventListener("leadops:open-chat", show);
  }, []);

  useEffect(() => {
    if (!open) return;
    track("chat_opened", { listing_id: listingId });
    inputRef.current?.focus();
    if (historyLoaded.current) return;
    historyLoaded.current = true;
    const { visitor_id: visitorId } = visitorIds();
    if (!visitorId) return;
    getChatHistory(visitorId)
      .then((rows) => setMessages((current) => (current.length ? current : rows.map(({ role, text }) => ({ role, text })))))
      .catch(() => {}); // no history is fine
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, sending]);

  async function send(text) {
    const message = text.trim();
    if (!message || sending) return;
    setDraft("");
    setError(null);
    setMessages((current) => [...current, { role: "user", text: message }]);
    setSending(true);
    track("chat_message", { length: message.length, listing_id: listingId });
    try {
      const data = await sendChat(message, listingId);
      setMessages((current) => [...current, { role: "assistant", text: data.reply, listings: data.listings }]);
    } catch {
      setError("The assistant can't be reached right now. Try again in a moment.");
    } finally {
      setSending(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-40 flex items-center gap-2 rounded-full bg-marigold px-5 py-3 font-semibold text-ink shadow-lg shadow-ink/15 hover:bg-[#e09500]"
      >
        <IconChat className="size-5" />
        Ask about homes
      </button>
    );
  }

  return (
    <section
      role="dialog"
      aria-label="Property assistant"
      onKeyDown={(event) => event.key === "Escape" && setOpen(false)}
      className="fixed bottom-4 right-4 z-40 flex h-[min(560px,calc(100dvh-2rem))] w-[min(400px,calc(100vw-2rem))] flex-col overflow-hidden rounded-xl border border-line bg-white shadow-2xl shadow-ink/20"
    >
      <header className="flex items-center justify-between bg-ink px-4 py-3 text-white">
        <div>
          <h2 className="font-wide font-semibold">Property assistant</h2>
          <p className="text-xs text-white/70">Answers from the homes on this site</p>
        </div>
        <button type="button" onClick={() => setOpen(false)} className="rounded p-1 hover:bg-white/10" aria-label="Close the assistant">
          <IconClose className="size-5" />
        </button>
      </header>

      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex flex-col gap-3 text-sm text-ink-soft">
            <p>Tell me what you&apos;re looking for, in English or Hinglish. For example:</p>
            <div className="flex flex-col items-start gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => send(suggestion)}
                  className="rounded-full border border-line px-3 py-1.5 text-left hover:border-blueprint"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <ul className="flex flex-col gap-4">
            {messages.map((message, index) => (
              <Message key={index} message={message} />
            ))}
          </ul>
        )}
        <p aria-live="polite" className="mt-3 text-sm text-muted">
          {sending ? "Finding homes..." : ""}
        </p>
        {error && (
          <p role="alert" className="mt-2 text-sm font-medium text-alert">
            {error}
          </p>
        )}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          send(draft);
        }}
        className="flex gap-2 border-t border-line p-3"
      >
        <label htmlFor="chat-input" className="sr-only">
          Your message
        </label>
        <input
          id="chat-input"
          ref={inputRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          maxLength={1000}
          placeholder="3BHK under 90L in Pune"
          className="min-w-0 flex-1 rounded-md border border-line px-3 py-2 text-base focus:border-blueprint"
        />
        <button
          type="submit"
          disabled={sending || !draft.trim()}
          className="flex items-center gap-1.5 rounded-md bg-ink px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          <IconSend className="size-4" />
          Send
        </button>
      </form>
    </section>
  );
}
