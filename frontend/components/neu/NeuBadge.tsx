import { CircleCheck, OctagonAlert, ShieldAlert, TriangleAlert } from "lucide-react";
import type { HTMLAttributes } from "react";
import { RISK_LABEL, RISK_TEXT_CLASS } from "@/lib/risk";
import { cn } from "@/lib/utils";
import type { Risk } from "@/types/api";

export function NeuBadge({ className, ...p }: HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("inline-flex items-center gap-1.5 rounded-full bg-bg px-3 py-1 text-xs font-bold tracking-wide shadow-neu-inset-sm", className)} {...p} />;
}

export const RISK_ICON = { Low: CircleCheck, Medium: TriangleAlert, High: OctagonAlert } as const;

/** Risk level: icon + text label + colour (never colour alone). */
export function RiskBadge({ risk, className }: { risk: Risk; className?: string }) {
  const Icon = RISK_ICON[risk];
  return (
    <NeuBadge className={cn(RISK_TEXT_CLASS[risk], className)}>
      <Icon aria-hidden className="h-3.5 w-3.5" />
      {RISK_LABEL[risk]}
    </NeuBadge>
  );
}

/** CONFIDENTLY WRONG: spread says trust, BustGuard says bust. Pulsing inset ring + icon + text. */
export function CwBadge({ className, compact }: { className?: string; compact?: boolean }) {
  return (
    <NeuBadge
      className={cn("animate-cw-pulse text-accent-text", className)}
      title="The spread says trust this forecast, but BustGuard rates the bust risk HIGH and similar past cases agree"
    >
      <ShieldAlert aria-hidden className="h-3.5 w-3.5" />
      {compact ? (
        <>
          <span aria-hidden>CW</span>
          <span className="sr-only">confidently wrong</span>
        </>
      ) : (
        RISK_LABEL.CW
      )}
    </NeuBadge>
  );
}
