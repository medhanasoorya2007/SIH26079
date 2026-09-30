"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { NeuButton, NeuSelect } from "@/components/neu";
import { fmtDate } from "@/lib/format";
import { useAppState } from "./AppState";

const SPLIT_LABEL: Record<string, string> = { test: "Test years (unseen)", calib: "Calibration year", train: "Replay-event windows" };

/** Issue-date picker: grouped by split, with previous/next buttons. */
export function DatePicker({ compact }: { compact?: boolean }) {
  const { dates, date, setDate } = useAppState();
  if (!date || !dates.length) return <div className="h-11 w-48 rounded-control shadow-neu-inset-sm" aria-hidden />;
  const i = dates.findIndex((d) => d.date === date);
  const groups = ["test", "calib", "train"].map((s) => ({ s, items: dates.filter((d) => d.split === s) })).filter((g) => g.items.length);
  return (
    <div className="flex items-center gap-2">
      {!compact && (
        <NeuButton size="icon" aria-label="Previous issue date" disabled={i <= 0} onClick={() => setDate(dates[i - 1].date)}>
          <ChevronLeft className="h-4 w-4" aria-hidden />
        </NeuButton>
      )}
      <label className="sr-only" htmlFor="issue-date">
        Forecast issue date
      </label>
      <NeuSelect id="issue-date" value={date} onChange={(e) => setDate(e.target.value)} className="w-auto min-w-[11rem] font-semibold tabular">
        {groups.map((g) => (
          <optgroup key={g.s} label={SPLIT_LABEL[g.s] ?? g.s}>
            {g.items.map((d) => (
              <option key={d.date} value={d.date}>
                {fmtDate(d.date)}
              </option>
            ))}
          </optgroup>
        ))}
      </NeuSelect>
      {!compact && (
        <NeuButton size="icon" aria-label="Next issue date" disabled={i >= dates.length - 1} onClick={() => setDate(dates[i + 1].date)}>
          <ChevronRight className="h-4 w-4" aria-hidden />
        </NeuButton>
      )}
    </div>
  );
}
