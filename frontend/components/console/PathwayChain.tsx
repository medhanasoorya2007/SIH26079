import { Fragment } from "react";
import type { PathwayStep } from "@/types/api";

/** 3-5 extruded steps joined by inset connectors (only families the model flagged). */
export function PathwayChain({ steps, regime }: { steps: PathwayStep[] | null; regime: string }) {
  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-bold text-fg">Pathway</h3>
        <span className="text-[11px] text-muted">{regime} template</span>
      </div>
      {!steps ? (
        <p className="text-xs text-muted">No physical pathway stands out: the risk is associated mainly with location, season and forecast amount.</p>
      ) : (
        <ol className="flex flex-wrap items-center gap-y-3" aria-label="Pathway associated with the bust risk">
          {steps.map((s, i) => (
            <Fragment key={i}>
              {i > 0 && <li aria-hidden className="mx-1 h-2 w-6 rounded-full shadow-neu-inset-sm" />}
              <li className={`rounded-full bg-bg px-3.5 py-2 text-xs font-semibold shadow-neu-sm ${s.family === "outcome" ? "text-risk-high-text" : "text-fg"}`}>{s.text}</li>
            </Fragment>
          ))}
        </ol>
      )}
    </div>
  );
}
