import { formatFeature } from "./describe";
import { Chip, IntentMeter, LabelBadge } from "./Signals";

const MAX_ITEM_POINTS = 20; // the largest single intent item (time on property pages), so bars compare across visitors

function Block({ title, aside, children }) {
  return (
    <div className="rounded-md border border-line p-3">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold">{title}</h4>
        {aside && <p className="text-xs text-muted">{aside}</p>}
      </div>
      {children}
    </div>
  );
}

function LegendKey({ className, children }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-2.5 w-3 rounded-sm ${className}`} aria-hidden="true" />
      {children}
    </span>
  );
}

// SHAP values as diverging bars from a zero line: towards a bot to the right (alert), towards a person to the left
// (blueprint). Each row also states its direction and the visitor's value in text, so colour is never the only cue.
function HumanFactors({ factors }) {
  if (!factors?.length) return <p className="text-xs text-muted">No behaviour factors yet.</p>;
  const largest = Math.max(0.5, ...factors.map((factor) => Math.abs(factor.contribution)));
  return (
    <div>
      <p className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <LegendKey className="bg-blueprint">Towards a person</LegendKey>
        <LegendKey className="bg-alert">Towards a bot</LegendKey>
      </p>
      <ul className="flex flex-col gap-1.5">
        {factors.map((factor) => {
          const towardsBot = factor.towards === "bot";
          const width = (Math.abs(factor.contribution) / largest) * 50; // percent of the whole track
          const signed = `${factor.contribution > 0 ? "+" : ""}${factor.contribution.toFixed(2)}`;
          const explanation = `${factor.label}: ${formatFeature(factor.feature, factor.value)}. Pushes towards ${
            towardsBot ? "a bot" : "a person"
          } (${signed} log-odds).`;
          return (
            <li
              key={factor.feature}
              tabIndex={0}
              title={explanation}
              aria-label={explanation}
              className="grid grid-cols-[minmax(0,1fr)_112px] items-center gap-3 rounded px-1 py-0.5 text-xs hover:bg-concrete focus-visible:bg-concrete"
            >
              <span className="min-w-0">
                <span className="text-ink">{factor.label}</span>{" "}
                <span className="text-muted">{formatFeature(factor.feature, factor.value)}</span>
              </span>
              <span className="relative block h-3" aria-hidden="true">
                <span className="absolute inset-y-0 left-1/2 w-px bg-line" />
                <span
                  className={`absolute top-0 h-3 ${towardsBot ? "left-1/2 rounded-r bg-alert" : "right-1/2 rounded-l bg-blueprint"}`}
                  style={{ width: `${width}%` }}
                />
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function IntentPoints({ points }) {
  if (!points?.length) return <p className="text-xs text-muted">No buying signals yet.</p>;
  const sorted = [...points].sort((a, b) => b.points - a.points);
  return (
    <ul className="flex flex-col gap-1.5">
      {sorted.map((point) => (
        <li key={point.signal} className="grid grid-cols-[minmax(0,1fr)_112px] items-center gap-3 px-1 text-xs">
          <span className="min-w-0 text-ink">{point.detail}</span>
          <span className="flex items-center gap-1.5" title={`${point.points} points`}>
            <span className="block h-2 rounded-r bg-blueprint" style={{ width: `${(point.points / MAX_ITEM_POINTS) * 80}px` }} />
            <span className="tabular font-semibold">+{point.points}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

function SignalList({ signals }) {
  if (!signals.length) return null;
  return (
    <ul className="mb-2 flex flex-wrap gap-1.5">
      {signals.map((signal) => (
        <Chip key={signal.code} tone="alert">
          {signal.reason}
        </Chip>
      ))}
    </ul>
  );
}

const TYPE_NAMES = { end_buyer: "End buyer", investor: "Investor", tenant: "Tenant", broker: "Broker", spam: "Spam" };

export default function ScoreBreakdown({ score, detail, hasEnquiry }) {
  if (!score || !detail) {
    return <p className="text-sm text-muted">Not scored yet. Scoring starts with the visitor&apos;s first page view.</p>;
  }
  const human = detail.human ?? {};
  const botSignals = (detail.signals ?? []).filter((signal) => signal.layer === "bot");
  const junkSignals = (detail.signals ?? []).filter((signal) => signal.layer === "junk");
  const visitorType = detail.visitor_type;
  const source = human.source === "model" ? `model ${score.model_version}` : "fallback formula (no trained model)";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <LabelBadge label={score.label} />
        <span className="flex items-center gap-2">
          <span className="text-muted">Intent</span>
          <IntentMeter value={score.intent_score} />
        </span>
        <span>
          <span className="text-muted">Human </span>
          <span className="tabular font-semibold">{Math.round(score.human_prob * 100)}%</span>
        </span>
      </div>
      <ul className="list-disc pl-5 text-sm">
        {score.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>

      <Block title="Human check" aside={source}>
        <p className="mb-2 text-xs text-ink-soft">
          {Math.round(score.human_prob * 100)}% likely to be a person, judged by how they browse. Bot below{" "}
          {Math.round((detail.thresholds?.bot ?? 0.2) * 100)}%, a look below {Math.round((detail.thresholds?.review ?? 0.5) * 100)}%.
        </p>
        <SignalList signals={botSignals} />
        <HumanFactors factors={human.factors} />
      </Block>

      <Block title="Contact details">
        <SignalList signals={junkSignals} />
        {visitorType?.type && (
          <p className="mb-1 text-xs">
            <span className="text-muted">Visitor type: </span>
            <span className="font-semibold">{TYPE_NAMES[visitorType.type] ?? visitorType.type}</span>
            {visitorType.reason ? <span className="text-ink-soft">. {visitorType.reason}</span> : null}
          </p>
        )}
        {junkSignals.length === 0 && (
          <p className="text-xs text-muted">
            {hasEnquiry ? "The enquiry's details look real." : "No enquiry yet, so there are no contact details to check."}
          </p>
        )}
      </Block>

      <Block title="Intent" aside={`${score.intent_score} of 100 points`}>
        <IntentPoints points={detail.intent?.points} />
      </Block>
    </div>
  );
}
