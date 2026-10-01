"use client";

import { useState } from "react";
import { NeuCard, NeuSegmented } from "@/components/neu";
import { api } from "@/lib/api";
import { num } from "@/lib/format";
import { HEX } from "@/lib/risk";
import { useApi } from "@/lib/useApi";
import { BRAND, displayName } from "@/lib/brand";

type Mode = "gain" | "model";

/** Map a value to the risk scale: large gain/skill = teal (reliable), none = red. */
function colour(v: number, lo: number, hi: number) {
  const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo || 1)));
  const stops = [HEX.high, HEX.medium, HEX.low];
  const seg = t < 0.5 ? 0 : 1;
  const u = t < 0.5 ? t / 0.5 : (t - 0.5) / 0.5;
  const a = stops[seg];
  const b = stops[seg + 1];
  const mix = [1, 3, 5].map((i) => Math.round(parseInt(a.slice(i, i + 2), 16) + (parseInt(b.slice(i, i + 2), 16) - parseInt(a.slice(i, i + 2), 16)) * u));
  return `rgb(${mix.join(",")})`;
}

export default function ScorecardPage() {
  const { data, error } = useApi("scorecard", api.scorecard);
  const [mode, setMode] = useState<Mode>("gain");
  if (error) return <p className="text-sm font-semibold text-risk-high-text">{error.message}</p>;
  if (!data) return <p className="text-sm text-muted">Loading scorecard…</p>;
  const cell = (reg: string, lead: number) => data.cells.find((c) => c.regime === reg && c.lead_day === lead);
  const value = (c?: (typeof data.cells)[number]) => (!c || c.improvement === null || !c.pr_auc ? null : mode === "gain" ? c.improvement : c.pr_auc.BustGuard);
  const vals = data.cells.map(value).filter((v): v is number => v !== null);
  const lo = mode === "gain" ? 0 : Math.min(...vals);
  const hi = Math.max(...vals);
  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl">
          <h1 className="font-display text-3xl font-extrabold tracking-tight text-fg md:text-4xl">Regime scorecard</h1>
          <p className="mt-2 text-sm text-muted">
            Test years, by weather regime and lead day. Cells need at least {data.min_busts} busts; others are marked &ldquo;·&rdquo;. Regimes are diagnosed from the forecast; Day 9–10 regimes use rain only (no MSLP beyond Day 8).
          </p>
        </div>
        <NeuSegmented
          label="Heatmap value"
          value={mode}
          onChange={setMode}
          options={[
            { value: "gain", label: "Gain over best baseline" },
            { value: "model", label: `${BRAND} PR-AUC` },
          ]}
        />
      </header>
      <NeuCard>
        <div className="overflow-x-auto rounded-panel p-3 shadow-neu-inset-deep">
          <table className="w-full border-separate border-spacing-1.5 text-xs">
            <caption className="sr-only">{mode === "gain" ? `PR-AUC gain of ${BRAND} over the best spread baseline` : `${BRAND} PR-AUC`} by regime and lead day</caption>
            <thead>
              <tr>
                <th scope="col" className="px-2 py-1 text-left font-semibold text-muted">
                  Regime
                </th>
                {data.leads.map((l) => (
                  <th key={l} scope="col" className="px-1 py-1 font-semibold tabular text-muted">
                    D{l}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.regimes.map((reg) => (
                <tr key={reg}>
                  <th scope="row" className="whitespace-nowrap px-2 text-left font-semibold text-fg">
                    {reg}
                  </th>
                  {data.leads.map((l) => {
                    const c = cell(reg, l);
                    const v = value(c);
                    return (
                      <td
                        key={l}
                        title={c ? `${c.n_busts} busts / ${c.n} forecasts${c.pr_auc ? ` · PR-AUC ${Object.entries(c.pr_auc).map(([k, x]) => `${displayName(k)} ${x.toFixed(3)}`).join(", ")}` : ""}` : "no data"}
                        className="h-11 min-w-[3.25rem] rounded-control text-center font-bold tabular"
                        style={v === null ? { boxShadow: "var(--shadow-inset-sm)", color: "var(--muted)" } : { background: colour(v, lo, hi), color: "#fff", opacity: 0.9 }}
                      >
                        {v === null ? "·" : (mode === "gain" ? "+" : "") + num(v, 2)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-3 text-[11px] font-semibold text-muted">
          <span>{mode === "gain" ? "gain" : "PR-AUC"}:</span>
          <span className="h-3 w-32 rounded-full" style={{ background: `linear-gradient(90deg, ${HEX.high}, ${HEX.medium}, ${HEX.low})` }} aria-hidden />
          <span className="tabular">
            {num(lo, 2)} → {num(hi, 2)}
          </span>
          <span>· teal = strongest, red = weakest</span>
        </div>
      </NeuCard>
    </div>
  );
}
