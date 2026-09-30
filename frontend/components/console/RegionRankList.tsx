"use client";

import { BustDial, CwBadge, RiskBadge } from "@/components/neu";
import { cn } from "@/lib/utils";
import type { RegionConfidence } from "@/types/api";

/** Ranked error-prone regions. Mirrors the map, so every subdivision is keyboard-selectable. */
export function RegionRankList({
  regions,
  selected,
  onSelect,
  lead,
}: {
  regions: RegionConfidence[];
  selected?: string;
  onSelect: (id: string) => void;
  lead: number;
}) {
  return (
    <ol aria-label={`Subdivisions ranked by bust probability, Day ${lead}`} className="space-y-3">
      {regions.map((r) => (
        <li key={r.id}>
          <button
            type="button"
            onClick={() => onSelect(r.id)}
            aria-current={r.id === selected ? "true" : undefined}
            className={cn(
              "focus-ring flex w-full items-center gap-3 rounded-panel bg-bg p-3 text-left transition-all duration-ui ease-out",
              r.id === selected ? "shadow-neu-inset" : "shadow-neu-sm hover:-translate-y-0.5 hover:shadow-neu-hover",
            )}
          >
            <span className="w-6 text-center text-xs font-bold tabular text-muted">{r.rank}</span>
            <BustDial size="sm" prob={r.bust_prob} risk={r.risk} label={`Day ${lead}, ${r.name}`} confidentlyWrong={r.confidently_wrong} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold text-fg">{r.name}</span>
              <span className="mt-1 flex flex-wrap items-center gap-1.5">
                <RiskBadge risk={r.risk} />
                {r.confidently_wrong && <CwBadge compact />}
              </span>
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}
