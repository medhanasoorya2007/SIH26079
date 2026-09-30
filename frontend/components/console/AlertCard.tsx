import { CalendarRange, History, Lightbulb } from "lucide-react";
import { BustDial, CwBadge, NeuWell, RiskBadge } from "@/components/neu";
import { fmtDate, mm, times } from "@/lib/format";
import type { LeadDetail, RiskWindow } from "@/types/api";

function windowText(w: RiskWindow[]) {
  if (!w.length) return "No lead day at MEDIUM or above";
  return w.map((x) => (x.from_lead === x.to_lead ? `Day ${x.from_lead}` : `Day ${x.from_lead}–${x.to_lead}`) + ` (${x.max_risk.toUpperCase()})`).join(", ");
}

/** Alert card: region, Day N, variable -> dial -> likely driver -> risk window -> analogs -> CW. */
export function AlertCard({
  region,
  lead,
  variable,
  riskWindow,
  baseRate,
}: {
  region: string;
  lead: LeadDetail;
  variable: string;
  riskWindow: RiskWindow[];
  baseRate?: number;
}) {
  const verified = lead.obs !== null && lead.bust !== null;
  return (
    <section aria-label={`Alert for ${region}, Day ${lead.lead_day}`} className="space-y-5">
      <header>
        <div className="text-xs font-semibold uppercase tracking-wide text-muted">
          Day {lead.lead_day} · {variable === "rain" ? "Rainfall" : "Tmax"} · valid {fmtDate(lead.valid_date)}
        </div>
        <h2 className="mt-1 font-display text-2xl font-extrabold text-fg">{region}</h2>
      </header>
      <div className="flex flex-wrap items-center gap-6">
        <BustDial size="lg" prob={lead.bust_prob} risk={lead.risk} reliability={lead.reliability.observed_bust_rate} label={`Day ${lead.lead_day}, ${region}`} confidentlyWrong={lead.confidently_wrong} />
        <div className="min-w-[12rem] flex-1 space-y-2">
          <div className="flex flex-wrap gap-2">
            <RiskBadge risk={lead.risk} />
            {lead.confidently_wrong && <CwBadge />}
          </div>
          <p className="text-sm text-fg">
            <span className="font-display text-lg font-bold tabular">{times(lead.bust_prob, baseRate)}</span> the usual bust rate
          </p>
          <p className="text-xs text-muted">
            Spread says <span className="font-semibold text-fg">{lead.spread_says}</span>
            {lead.spread !== null && <> (lagged spread {mm(lead.spread)})</>}
          </p>
          <p className="text-xs text-muted">Regime: {lead.regime}</p>
        </div>
      </div>
      <NeuWell shallow className="space-y-3 text-sm">
        <p className="flex gap-2">
          <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-accent-text" aria-hidden />
          <span>
            <span className="font-semibold">Likely driver: {lead.likely_driver ?? "none"}. </span>
            {lead.family_sentence}
          </span>
        </p>
        <p className="flex gap-2">
          <CalendarRange className="mt-0.5 h-4 w-4 shrink-0 text-accent-text" aria-hidden />
          <span>
            <span className="font-semibold">Risk window: </span>
            {windowText(riskWindow)}
          </span>
        </p>
        <p className="flex gap-2">
          <History className="mt-0.5 h-4 w-4 shrink-0 text-accent-text" aria-hidden />
          <span className="font-semibold">{lead.analogs.text}</span>
        </p>
      </NeuWell>
      {verified && (
        <p className="text-xs text-muted">
          Verified outcome (IMD): observed <span className="font-semibold tabular text-fg">{mm(lead.obs)}</span> vs forecast{" "}
          <span className="font-semibold tabular text-fg">{mm(lead.fc)}</span>:{" "}
          <span className={lead.bust === 1 ? "font-bold text-risk-high-text" : "font-bold text-risk-low-text"}>{lead.bust === 1 ? "BUST" : "no bust"}</span>
        </p>
      )}
    </section>
  );
}
