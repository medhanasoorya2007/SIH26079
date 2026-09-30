"use client";

import { motion, useReducedMotion } from "framer-motion";
import { CircleCheck, OctagonAlert, ShieldQuestion } from "lucide-react";
import { CwBadge, LeadDaySlider, NeuWell, RiskBadge } from "@/components/neu";
import { fmtDate, mm, pct } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ReplayRegion } from "@/types/api";

/** Two columns per issue day: what the spread said vs what BustGuard said, scrubbed from
 * Day 10 towards the event. The day BustGuard's continuous warning began is highlighted. */
export function ReplayCompare({ region, validDate, step, setStep }: { region: ReplayRegion; validDate: string; step: number; setStep: (n: number) => void }) {
  const reduce = useReducedMotion();
  const steps = region.steps; // Day 10 -> Day 1
  const order = steps.map((_, i) => i + 1); // scrub positions 1..N
  const shown = steps.slice(0, step);
  const firstWarn = region.first_warning.BustGuard;
  const firstSpread = region.first_warning.spread;
  const done = step >= steps.length;
  return (
    <div className="space-y-6">
      <LeadDaySlider
        label={`Scrub towards ${fmtDate(validDate)} (Day ${steps[0]?.lead_day} → Day 1)`}
        value={step}
        onChange={setStep}
        leads={order}
      />
      <div className="grid grid-cols-[4.5rem_1fr_1fr] gap-3 text-[11px] font-bold uppercase tracking-wide text-muted">
        <span>Issued</span>
        <span>Ensemble spread says</span>
        <span>BustGuard says</span>
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
              className={cn("grid grid-cols-[4.5rem_1fr_1fr] items-center gap-3 rounded-panel p-2", warnStart && "shadow-neu-inset-sm ring-2 ring-accent")}
            >
              <span className="text-xs font-semibold tabular text-fg">
                Day {s.lead_day}
                <span className="block font-normal text-muted">{fmtDate(s.init_date, { day: "numeric", month: "short" })}</span>
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
                {warnStart && <span className="w-full font-bold text-accent-text">BustGuard warning begins</span>}
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
              Outcome: IMD observed {mm(region.obs)}; Day-1 forecast {mm(steps[steps.length - 1]?.fc)}: {region.busted_day1 ? "BUST" : "no bust"}
            </span>
          </div>
          <div className="text-xs text-muted">
            BustGuard warning held continuously from {firstWarn ? `Day ${firstWarn}` : "— (no continuous warning)"}; spread from {firstSpread ? `Day ${firstSpread}` : "— (never)"}.
          </div>
        </NeuWell>
      ) : (
        <p className="flex items-center gap-2 text-xs text-muted">
          <ShieldQuestion className="h-4 w-4" aria-hidden /> Outcome hidden until you scrub to Day 1.
        </p>
      )}
    </div>
  );
}
