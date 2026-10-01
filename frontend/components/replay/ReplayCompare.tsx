"use client";

import { motion, useReducedMotion } from "framer-motion";
import { CircleCheck, OctagonAlert, ShieldQuestion } from "lucide-react";
import { CwBadge, LeadDaySlider, NeuWell, RiskBadge } from "@/components/neu";
import { fmtDate, mm, pct } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ReplayRegion } from "@/types/api";
import { BRAND } from "@/lib/brand";

/** Two columns per issue day: what the spread said vs what Predicta said, scrubbed from
 * Day 10 towards the event. The day Predicta's continuous warning began is highlighted. */
export function ReplayCompare({ region, validDate, step, setStep }: { region: ReplayRegion; validDate: string; step: number; setStep: (n: number) => void }) {
  const reduce = useReducedMotion();
  // forecasts for this valid day in time order: oldest issue (longest lead) first
  const chrono = [...region.steps].sort((a, b) => a.init_date.localeCompare(b.init_date));
  const positions = chrono.map((_, i) => i + 1);
  // `step` = slider position; show forecasts issued from the oldest up to that position
  const pos = Math.min(Math.max(1, step), chrono.length);
  const shown = chrono.slice(0, pos);
  const firstWarn = region.first_warning.BustGuard;
  const firstSpread = region.first_warning.spread;
  const done = pos >= chrono.length; // outcome revealed once the last forecast is reached
  const ahead = (lead: number) => `${lead} day${lead === 1 ? "" : "s"} ahead`;
  const issued = (iso?: string) => fmtDate(iso, { day: "numeric", month: "short" });
  const byLead = (lead: number) => chrono.find((c) => c.lead_day === lead);
  const dots = chrono.map((s, i) => ({
    lead_day: i + 1,
    max_risk: s.model_risk,
    n_high: s.model_risk === "High" ? 1 : 0,
    n_medium: s.model_risk === "Medium" ? 1 : 0,
    n_cw: s.confidently_wrong ? 1 : 0,
    max_prob: s.model_prob ?? 0,
  }));
  return (
    <div className="space-y-6">
      <LeadDaySlider
        label={`Forecasts for ${fmtDate(validDate)}, in the order they were issued; dots = ${BRAND} risk`}
        value={pos}
        onChange={setStep}
        leads={positions}
        summary={dots}
        formatValue={(v) => `${issued(chrono[v - 1]?.init_date)} · ${ahead(chrono[v - 1]?.lead_day ?? 0)}`}
        formatTick={(v) => issued(chrono[v - 1]?.init_date)}
      />
      <div className="grid grid-cols-[6rem_1fr_1fr] gap-3 text-[11px] font-bold uppercase tracking-wide text-muted">
        <span>Issued · lead</span>
        <span>Ensemble spread says</span>
        <span>{BRAND} says</span>
      </div>
      <ol className="space-y-3">
        {shown.map((s) => {
          const warnStart = s.lead_day === firstWarn && firstWarn > 0;
          return (
            <motion.li
              key={s.lead_day}
              initial={{ opacity: 0, y: reduce ? 0 : 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: reduce ? 0 : 0.3 }}
              className={cn("grid grid-cols-[6rem_1fr_1fr] items-center gap-3 rounded-panel p-2", warnStart && "shadow-neu-inset-sm ring-2 ring-accent")}
            >
              <span className="text-xs font-semibold tabular text-fg">
                Issued {issued(s.init_date)}
                <span className="block font-normal text-muted">{ahead(s.lead_day)}</span>
              </span>
              <NeuWell shallow className="p-3 text-xs">
                <div className={cn("font-semibold", s.spread_flag ? "text-risk-medium-text" : "text-fg")}>
                  {s.spread_says === "uncertain" ? "Uncertain: low confidence" : s.spread_says === "confident" ? "Confident: trust forecast" : "No spread available"}
                </div>
                <div className="tabular text-muted">bust prob. {pct(s.spread_prob, 1)}</div>
              </NeuWell>
              <NeuWell shallow className="flex flex-wrap items-center gap-2 p-3 text-xs">
                <RiskBadge risk={s.model_risk} />
                <span className="font-semibold tabular text-fg">{pct(s.model_prob, 1)}</span>
                {s.confidently_wrong && <CwBadge compact />}
                {warnStart && <span className="w-full font-bold text-accent-text">{BRAND} warning begins</span>}
              </NeuWell>
            </motion.li>
          );
        })}
      </ol>
      {done ? (
        <NeuWell className="space-y-2 text-sm">
          <div className="flex items-center gap-2 font-bold">
            {region.busted_day1 ? <OctagonAlert className="h-4 w-4 text-risk-high-text" aria-hidden /> : <CircleCheck className="h-4 w-4 text-risk-low-text" aria-hidden />}
            <span className={region.busted_day1 ? "text-risk-high-text" : "text-risk-low-text"}>
              Outcome: IMD observed {mm(region.obs)}; forecast issued {issued(byLead(1)?.init_date)} {mm(byLead(1)?.fc)}: {region.busted_day1 ? "BUST" : "no bust"}
            </span>
          </div>
          <div className="text-xs text-muted">
            {BRAND} warning held continuously from {firstWarn ? `${issued(byLead(firstWarn)?.init_date)} (${ahead(firstWarn)})` : "— (no continuous warning)"}; spread from {firstSpread ? `${issued(byLead(firstSpread)?.init_date)} (${ahead(firstSpread)})` : "— (never)"}.
          </div>
        </NeuWell>
      ) : (
        <p className="flex items-center gap-2 text-xs text-muted">
          <ShieldQuestion className="h-4 w-4" aria-hidden /> Outcome hidden until you reach the last forecast (1 day ahead).
        </p>
      )}
    </div>
  );
}
