// Shared pieces of the LeadOps look: buttons, labels, sections and the few animations the pages use.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { IconArrowUpRight, PlanMark } from "./icons";

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

// Whether the visitor asked their system for less motion. Animations that run on a timer check this first.
export function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia?.(REDUCED_MOTION).matches ?? false);
  useEffect(() => {
    const media = window.matchMedia?.(REDUCED_MOTION);
    if (!media) return undefined;
    const update = () => setReduced(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return reduced;
}

// True while the element is on screen. With once, it stays true after the first time.
export function useInView(ref, { once = false } = {}) {
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") {
      setInView(true);
      return undefined;
    }
    const observer = new IntersectionObserver(([entry]) => {
      setInView(entry.isIntersecting);
      if (entry.isIntersecting && once) observer.disconnect();
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [ref, once]);
  return inView;
}

const BUTTON_TONES = {
  marigold: "bg-marigold text-night hover:bg-marigold-deep",
  light: "bg-white text-night hover:bg-white/90",
  blueprint: "bg-blueprint text-white shadow-[0_14px_32px_-14px_rgb(29_79_145/0.9)] hover:bg-blueprint-deep",
  ink: "bg-night text-white hover:bg-night-2",
  "outline-dark": "border border-white/15 bg-white/[0.06] text-white hover:bg-white/[0.12]",
  outline: "border border-line bg-white text-ink hover:bg-concrete",
};
const BUTTON_SIZES = { sm: "h-9 px-4 text-sm", md: "h-11 px-5 text-[15px]", lg: "h-12 px-6 text-base" };

// A pill button. `to` is a page in this app (`reload` opens it with a full page load), `href` any other link,
// and without either it is a <button>.
export function Button({ to, href, tone = "blueprint", size = "md", arrow = false, reload = false, className = "", children, ...rest }) {
  const classes = `inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium transition-colors disabled:opacity-60 ${BUTTON_TONES[tone]} ${BUTTON_SIZES[size]} ${className}`;
  const content = (
    <>
      {children}
      {arrow && <IconArrowUpRight className="size-4" />}
    </>
  );
  if (to) {
    return (
      <Link to={to} reloadDocument={reload} className={classes} {...rest}>
        {content}
      </Link>
    );
  }
  if (href) {
    return (
      <a href={href} className={classes} {...rest}>
        {content}
      </a>
    );
  }
  return (
    <button type="button" className={classes} {...rest}>
      {content}
    </button>
  );
}

// The small mono label that names a section, written in sentence case.
export function Eyebrow({ children, className = "" }) {
  return <p className={`font-mono text-[13px] leading-5 ${className}`}>{children}</p>;
}

// A dimension line, as on a drawing: a hairline with a tick at each end. It takes the colour of the text around it.
export function Rule({ className = "" }) {
  return <div className={`dim-rule ${className}`} aria-hidden="true" />;
}

export function Container({ className = "", children }) {
  return <div className={`mx-auto w-full max-w-[1224px] px-5 sm:px-8 ${className}`}>{children}</div>;
}

const SECTION_TONES = {
  night: "bg-night text-white",
  deep: "bg-deep text-white",
  paper: "bg-paper text-ink",
  concrete: "bg-concrete text-ink",
};

// A full-width band of the page. `rounded` gives it rounded top corners that overlap the band above.
export function Section({ tone = "paper", rounded = true, className = "", children, ...rest }) {
  const dark = tone === "night" || tone === "deep";
  return (
    <section
      data-tone={dark ? "dark" : "light"}
      className={`relative ${SECTION_TONES[tone]} ${rounded ? "-mt-8 rounded-t-[28px] sm:-mt-10 sm:rounded-t-[40px]" : ""} ${className}`}
      {...rest}
    >
      {children}
    </section>
  );
}

// The opening of a section: a dimension line, the label on the left and the heading on the right.
export function SectionHead({ label, title, titleId, children, action }) {
  return (
    <header>
      <Rule />
      <div className="mt-6 grid gap-5 lg:grid-cols-12">
        <Eyebrow className="opacity-60 lg:col-span-3">{label}</Eyebrow>
        <div className="lg:col-span-9">
          <h2 id={titleId} className="text-section max-w-[18ch]">
            {title}
          </h2>
          {(children || action) && (
            <div className="mt-6 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
              {children && <div className="text-lede max-w-[58ch] opacity-70">{children}</div>}
              {action && <div className="shrink-0">{action}</div>}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

// The LeadOps mark and name. `to` makes it a link.
export function Logo({ to, reload = false, className = "" }) {
  const mark = (
    <>
      <PlanMark className="size-8" />
      <span className="text-[19px] font-semibold tracking-[-0.02em]">LeadOps</span>
    </>
  );
  if (!to) return <span className={`inline-flex items-center gap-2.5 ${className}`}>{mark}</span>;
  return (
    <Link to={to} reloadDocument={reload} className={`inline-flex items-center gap-2.5 ${className}`}>
      {mark}
    </Link>
  );
}

// A strip that scrolls sideways on its own and pauses under the mouse. With reduced motion it stands still.
export function Marquee({ children, reverse = false, duration = 48 }) {
  return (
    <div className="marquee relative overflow-hidden [mask-image:linear-gradient(to_right,transparent,#000_8%,#000_92%,transparent)]">
      <div className="marquee-track flex w-max" data-reverse={reverse} style={{ "--marquee-duration": `${duration}s` }}>
        <div className="flex shrink-0 items-center">{children}</div>
        <div className="flex shrink-0 items-center" aria-hidden="true">
          {children}
        </div>
      </div>
    </div>
  );
}

// A paragraph whose words light up as it scrolls through the screen. Every word is always in the text, so screen
// readers and reduced motion get the whole paragraph at once.
export function RevealText({ text, className = "" }) {
  const ref = useRef(null);
  const reduced = useReducedMotion();
  const words = useMemo(() => text.split(" "), [text]);
  const [lit, setLit] = useState(0);

  useEffect(() => {
    if (reduced) return undefined;
    let frame = 0;
    const measure = () => {
      frame = 0;
      const box = ref.current?.getBoundingClientRect();
      if (!box) return;
      const view = window.innerHeight;
      const progress = (view * 0.85 - box.top) / (box.height + view * 0.25);
      setLit(Math.round(Math.min(1, Math.max(0, progress)) * words.length));
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      cancelAnimationFrame(frame);
    };
  }, [reduced, words.length]);

  return (
    <p ref={ref} className={className}>
      {words.map((word, index) => (
        <span key={index} className={`transition-opacity duration-300 ${reduced || index < lit ? "opacity-100" : "opacity-25"}`}>
          {index < words.length - 1 ? `${word} ` : word}
        </span>
      ))}
    </p>
  );
}
