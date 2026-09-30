"use client";

import { RISK_FILL } from "@/lib/risk";
import { cn } from "@/lib/utils";
import type { LeadDetail } from "@/types/api";

/** Day 1-10 bust probability for one region; bars sit in inset wells. Click to change day. */
export function LeadStrip({ leads, value, onChange }: { leads: LeadDetail[]; value: number; onChange: (l: number) => void }) {
  const max = Math.max(0.05, ...leads.map((l) => l.bust_prob));
  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-bold text-fg">Bust probability, Day 1–10</h3>
        <span className="text-[11px] text-muted">select a day</span>
      </div>
      <div className="flex items-end gap-2" role="group" aria-label="Bust probability by lead day">
        {leads.map((l) => (
          <button
            key={l.lead_day}
            type="button"
            onClick={() => onChange(l.lead_day)}
            aria-pressed={l.lead_day === value}
            aria-label={`Day ${l.lead_day}: ${(l.bust_prob * 100).toFixed(1)}% ${l.risk} risk${l.confidently_wrong ? ", confidently wrong" : ""}`}
            className={cn(
              "focus-ring flex min-w-0 flex-1 flex-col items-center gap-1.5 rounded-control p-1.5 transition-all duration-ui",
              l.lead_day === value ? "shadow-neu-inset-sm" : "hover:-translate-y-px",
            )}
          >
            <span className="flex h-24 w-full items-end overflow-hidden rounded-control shadow-neu-inset-sm">
              <span className="w-full rounded-t-[6px] transition-all duration-dial" style={{ height: `${(l.bust_prob / max) * 100}%`, background: RISK_FILL[l.risk] }} />
            </span>
            <span className={cn("text-[11px] font-semibold tabular", l.lead_day === value ? "text-accent-text" : "text-muted")}>
              {l.lead_day}
              {l.confidently_wrong && <span className="text-accent-text"> ◆</span>}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
