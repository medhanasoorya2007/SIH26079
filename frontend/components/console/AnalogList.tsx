import { CircleCheck, OctagonAlert } from "lucide-react";
import { fmtDate, mm } from "@/lib/format";
import type { Analogs } from "@/types/api";

/** "N of M similar past cases busted" + the closest cases as compact inset wells. */
export function AnalogList({ analogs }: { analogs: Analogs }) {
  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-bold text-fg">Similar past cases</h3>
        <span className="text-xs font-semibold tabular text-muted">{analogs.text}</span>
      </div>
      {analogs.cases.length === 0 ? (
        <p className="text-xs text-muted">No verified analog cases before this issue date.</p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2">
          {analogs.cases.map((c, i) => {
            const bust = c.bust === 1;
            return (
              <li key={i} className="rounded-panel bg-bg p-3 text-xs shadow-neu-inset-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold tabular text-fg">{fmtDate(c.valid_date)}</span>
                  <span className={`inline-flex items-center gap-1 font-bold ${bust ? "text-risk-high-text" : "text-risk-low-text"}`}>
                    {bust ? <OctagonAlert className="h-3.5 w-3.5" aria-hidden /> : <CircleCheck className="h-3.5 w-3.5" aria-hidden />}
                    {bust ? "Bust" : "No bust"}
                  </span>
                </div>
                <div className="mt-1 truncate text-muted">
                  {c.region} · Day {c.lead_day} · {c.regime}
                </div>
                <div className="mt-1 tabular text-muted">
                  forecast {mm(c.fc)} · observed {mm(c.obs)}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
