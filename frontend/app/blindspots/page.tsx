"use client";

import { CircleCheck, OctagonAlert } from "lucide-react";
import { useState } from "react";
import { useAppState } from "@/components/layout/AppState";
import { BustDial, CwBadge, NeuCard, NeuSegmented, NeuWell, RiskBadge } from "@/components/neu";
import { api } from "@/lib/api";
import { fmtDate, mm } from "@/lib/format";
import { useApi } from "@/lib/useApi";

export default function BlindspotsPage() {
  const { date } = useAppState();
  const [scope, setScope] = useState<"test" | "date">("test");
  const d = scope === "date" ? date : undefined;
  const { data, error, loading } = useApi(scope === "date" && !date ? null : `bs|${d ?? "all"}`, () => api.blindspots(d, 80));
  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl">
          <h1 className="font-display text-3xl font-extrabold tracking-tight text-fg md:text-4xl">Blind spots</h1>
          <p className="mt-2 text-sm text-muted">
            Forecasts the spread would trust (lowest third of lagged-ensemble spread for the regime and month) that Predicta rates HIGH. Confidently-wrong alerts, where similar past cases also busted, are listed first.
          </p>
        </div>
        <NeuSegmented
          label="Period"
          value={scope}
          onChange={setScope}
          options={[
            { value: "test", label: "Whole test period" },
            { value: "date", label: `Issue date ${fmtDate(date, { day: "numeric", month: "short" })}` },
          ]}
        />
      </header>
      {error && <p className="text-sm font-semibold text-risk-high-text">{error.message}</p>}
      {data && (
        <div className="grid gap-4 sm:grid-cols-3">
          <NeuWell shallow>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">Cases</div>
            <div className="font-display text-2xl font-extrabold tabular text-fg">{data.n}</div>
          </NeuWell>
          <NeuWell shallow>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">Confidently wrong</div>
            <div className="font-display text-2xl font-extrabold tabular text-accent-text">{data.n_confidently_wrong}</div>
          </NeuWell>
          <NeuWell shallow>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">Verified busts</div>
            <div className="font-display text-2xl font-extrabold tabular text-fg">
              {data.verified_busts} <span className="text-sm text-muted">of {data.verified}</span>
            </div>
          </NeuWell>
        </div>
      )}
      {loading && !data && <p className="text-sm text-muted">Loading…</p>}
      {data && data.items.length === 0 && <NeuCard compact className="text-sm text-muted">No low-spread, high-risk forecasts {scope === "date" ? "on this issue date" : "in the test period"}.</NeuCard>}
      <ul className="grid gap-5 lg:grid-cols-2">
        {data?.items.map((it, i) => {
          const bust = it.bust === 1;
          return (
            <li key={i}>
              <NeuCard compact interactive className="flex gap-5">
                <BustDial size="md" prob={it.bust_prob} risk={it.risk} label={`Day ${it.lead_day}, ${it.region}`} confidentlyWrong={it.confidently_wrong} />
                <div className="min-w-0 flex-1 space-y-2">
                  <div className="font-display text-base font-bold text-fg">{it.region}</div>
                  <div className="text-xs text-muted">
                    Issued {fmtDate(it.init_date)} · Day {it.lead_day} · valid {fmtDate(it.valid_date)} · {it.regime}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <RiskBadge risk={it.risk} />
                    {it.confidently_wrong && <CwBadge />}
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <NeuWell shallow className="p-2.5">
                      <div className="text-muted">Spread says</div>
                      <div className="font-semibold text-fg">{it.spread_says}</div>
                    </NeuWell>
                    <NeuWell shallow className="p-2.5">
                      <div className="text-muted">Predicta says</div>
                      <div className="font-semibold text-fg">{it.risk.toUpperCase()} risk</div>
                    </NeuWell>
                  </div>
                  <div className="text-xs text-muted">{it.analogs.text}{it.likely_driver ? ` · likely driver: ${it.likely_driver}` : ""}</div>
                  {it.bust !== null && (
                    <div className={`inline-flex items-center gap-1.5 text-xs font-bold ${bust ? "text-risk-high-text" : "text-risk-low-text"}`}>
                      {bust ? <OctagonAlert className="h-3.5 w-3.5" aria-hidden /> : <CircleCheck className="h-3.5 w-3.5" aria-hidden />}
                      {bust ? "Busted" : "Did not bust"}: forecast {mm(it.fc)}, IMD {mm(it.obs)}
                    </div>
                  )}
                </div>
              </NeuCard>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
