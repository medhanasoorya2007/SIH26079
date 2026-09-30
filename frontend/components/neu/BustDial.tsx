"use client";

import { motion, useReducedMotion } from "framer-motion";
import { RISK_FILL, RISK_LABEL } from "@/lib/risk";
import { cn } from "@/lib/utils";
import type { Risk } from "@/types/api";

interface BustDialProps {
  prob: number;
  risk: Risk;
  /** observed bust frequency of forecasts with similar probability (calibration year) */
  reliability?: number | null;
  size?: "sm" | "md" | "lg";
  /** context for screen readers, e.g. "Day 5, Konkan & Goa" */
  label: string;
  confidentlyWrong?: boolean;
}

const SIZES = { sm: 56, md: 136, lg: 176 };

/** Extruded outer ring -> inset track -> risk-coloured arc -> bust % in the centre. */
export function BustDial({ prob, risk, reliability, size = "md", label, confidentlyWrong }: BustDialProps) {
  const reduce = useReducedMotion();
  const px = SIZES[size];
  const stroke = size === "sm" ? 5 : 10;
  const inset = size === "sm" ? 5 : 12;
  const r = px / 2 - inset - stroke / 2 - (size === "sm" ? 1 : 4);
  const c = 2 * Math.PI * r;
  const shown = Math.max(0, Math.min(1, prob));
  const pctText = (prob * 100).toFixed(prob < 0.1 ? 1 : 0);
  const aria = `Bust probability ${pctText}%, ${RISK_LABEL[risk].toLowerCase()} risk${confidentlyWrong ? ", confidently wrong" : ""}, ${label}`;
  return (
    <div
      role="img"
      aria-label={aria}
      className={cn("relative grid shrink-0 place-items-center rounded-full bg-bg shadow-neu", confidentlyWrong && "animate-cw-pulse")}
      style={{ width: px, height: px }}
    >
      <div className="absolute rounded-full shadow-neu-inset-deep" style={{ inset }} />
      <svg width={px} height={px} className="absolute -rotate-90" aria-hidden>
        <motion.circle
          cx={px / 2}
          cy={px / 2}
          r={r}
          fill="none"
          stroke={RISK_FILL[risk]}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - shown) }}
          transition={{ duration: reduce ? 0 : 0.5, ease: "easeOut" }}
        />
      </svg>
      <div className="relative text-center leading-none" aria-hidden>
        <div className={cn("font-display font-extrabold tabular text-fg", size === "sm" ? "text-sm" : size === "md" ? "text-3xl" : "text-4xl")}>
          {pctText}
          <span className={size === "sm" ? "text-[10px]" : "text-base"}>%</span>
        </div>
        {size !== "sm" && (
          <div className="mt-1.5 px-3 text-[11px] font-medium text-muted">
            {reliability !== null && reliability !== undefined ? `busted ${(reliability * 100).toFixed(0)}% of the time` : "bust probability"}
          </div>
        )}
      </div>
    </div>
  );
}
