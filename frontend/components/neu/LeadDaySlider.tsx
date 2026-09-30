"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useRef, type KeyboardEvent, type PointerEvent } from "react";
import { RISK_FILL, RISK_LABEL } from "@/lib/risk";
import { cn } from "@/lib/utils";
import type { LeadSummary } from "@/types/api";

/** Day 1-10 slider: inset track, extruded thumb, a tiny risk dot per day. Arrow keys supported. */
export function LeadDaySlider({
  value,
  onChange,
  leads,
  summary,
  label = "Forecast lead day",
}: {
  value: number;
  onChange: (lead: number) => void;
  leads: number[];
  summary?: LeadSummary[];
  label?: string;
}) {
  const reduce = useReducedMotion();
  const track = useRef<HTMLDivElement>(null);
  const idx = Math.max(0, leads.indexOf(value));
  const frac = leads.length > 1 ? idx / (leads.length - 1) : 0;
  const info = (l: number) => summary?.find((s) => s.lead_day === l);

  const fromPointer = (e: PointerEvent) => {
    const r = track.current?.getBoundingClientRect();
    if (!r || !leads.length) return;
    const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    onChange(leads[Math.round(f * (leads.length - 1))]);
  };
  const onKey = (e: KeyboardEvent) => {
    const step: Record<string, number> = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 };
    if (e.key in step) {
      e.preventDefault();
      onChange(leads[Math.min(leads.length - 1, Math.max(0, idx + step[e.key]))]);
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      onChange(leads[e.key === "Home" ? 0 : leads.length - 1]);
    }
  };
  const cur = info(value);
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-sm font-semibold text-muted">{label}</span>
        <span className="font-display text-2xl font-extrabold tabular text-fg">Day {value}</span>
      </div>
      <div
        role="slider"
        tabIndex={0}
        aria-label={label}
        aria-valuemin={leads[0]}
        aria-valuemax={leads[leads.length - 1]}
        aria-valuenow={value}
        aria-valuetext={`Day ${value}${cur ? `, highest risk ${RISK_LABEL[cur.max_risk].toLowerCase()}, ${cur.n_high} high-risk regions` : ""}`}
        onKeyDown={onKey}
        onPointerDown={(e) => {
          (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
          fromPointer(e);
        }}
        onPointerMove={(e) => {
          if (e.buttons === 1) fromPointer(e);
        }}
        className="focus-ring cursor-pointer touch-none select-none rounded-panel px-4 pb-2 pt-5"
      >
        <div ref={track} className="relative h-3 rounded-full bg-bg shadow-neu-inset-sm">
          <div className="absolute inset-y-0 left-0 rounded-full bg-accent/60" style={{ width: `${frac * 100}%` }} />
          <motion.div
            className="absolute top-1/2 h-9 w-9 -translate-x-1/2 -translate-y-1/2 rounded-full bg-bg shadow-neu-sm"
            animate={{ left: `${frac * 100}%` }}
            transition={{ duration: reduce ? 0 : 0.3, ease: "easeOut" }}
          >
            <span className="absolute inset-[11px] rounded-full bg-accent" />
          </motion.div>
        </div>
        <div className="mt-5 flex justify-between">
          {leads.map((l) => {
            const s = info(l);
            return (
              <span key={l} className={cn("flex w-6 flex-col items-center gap-1 text-[11px] font-semibold tabular", l === value ? "text-accent-text" : "text-muted")}>
                <span
                  aria-hidden
                  className="h-2 w-2 rounded-full"
                  style={{ background: s ? RISK_FILL[s.max_risk] : "var(--grid)" }}
                  title={s ? `${RISK_LABEL[s.max_risk]}: ${s.n_high} high, ${s.n_medium} medium${s.n_cw ? `, ${s.n_cw} confidently wrong` : ""}` : undefined}
                />
                {l}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
