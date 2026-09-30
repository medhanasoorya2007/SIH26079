"use client";

import { useEffect, useState } from "react";
import { MapTray } from "@/components/console/MapTray";
import { RegionDrawer } from "@/components/console/RegionDrawer";
import { RegionRankList } from "@/components/console/RegionRankList";
import { useAppState } from "@/components/layout/AppState";
import { LeadDaySlider, NeuCard, NeuSegmented, NeuWell } from "@/components/neu";
import { api } from "@/lib/api";
import { fmtDate, pct } from "@/lib/format";
import { useApi } from "@/lib/useApi";

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: string }) {
  return (
    <NeuWell shallow className="px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className={`font-display text-xl font-extrabold tabular ${tone ?? "text-fg"}`}>{value}</div>
    </NeuWell>
  );
}

export default function ConsolePage() {
  const { meta, date, variable, setVariable, lead, setLead } = useAppState();
  const [selected, setSelected] = useState<string>();
  const geo = useApi("geo", api.geo);
  const conf = useApi(meta && date ? `${date}|${lead}|${variable}` : null, () => api.confidence(date, lead, variable));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setSelected(undefined);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const c = conf.data;
  const tmaxNote = meta?.variables_unavailable?.tmax;
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-extrabold tracking-tight text-fg md:text-4xl">Forecast console</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Where and when an ECMWF HRES rainfall forecast is likely to bust (IMD category rule), issued {fmtDate(date)}.
          </p>
        </div>
        {c && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Valid" value={fmtDate(c.valid_date, { day: "numeric", month: "short" })} />
            <Stat label="High risk" value={c.summary.risk_counts.High} tone="text-risk-high-text" />
            <Stat label="Confidently wrong" value={c.summary.n_confidently_wrong} tone="text-accent-text" />
            <Stat label="Busts observed" value={c.summary.busts_observed ?? "–"} />
          </div>
        )}
      </div>

      <div className="grid gap-8 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <MapTray
            className="h-[420px] md:h-[620px]"
            geo={geo.data}
            regions={c?.regions}
            thresholds={meta?.risk_thresholds}
            selected={selected}
            onSelect={setSelected}
          />
          {conf.error && <p className="mt-4 text-sm font-semibold text-risk-high-text">{conf.error.message}</p>}
        </div>

        <aside className="space-y-8 lg:col-span-4" aria-label="Controls and ranked regions">
          <NeuCard compact className="space-y-6">
            {meta && <LeadDaySlider value={lead} onChange={setLead} leads={meta.lead_days} summary={c?.lead_summary} />}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-sm font-semibold text-muted">Variable</span>
              <NeuSegmented
                label="Forecast variable"
                value={variable}
                onChange={setVariable}
                options={[
                  { value: "rain", label: "Rain" },
                  { value: "tmax", label: "Tmax", disabled: !meta?.variables.includes("tmax"), title: tmaxNote },
                ]}
              />
            </div>
            {tmaxNote && !meta?.variables.includes("tmax") && <p className="text-[11px] leading-relaxed text-muted">{tmaxNote}</p>}
            {meta && (
              <p className="text-[11px] leading-relaxed text-muted">
                Usual bust rate {pct(meta.headline.base_rate, 1)}. HIGH = flagged at the {pct(0.1)} false-alarm operating point frozen on the calibration year.
              </p>
            )}
          </NeuCard>

          <NeuCard compact>
            <div className="mb-4 flex items-baseline justify-between">
              <h2 className="text-base font-bold text-fg">Error-prone regions</h2>
              <span className="text-xs text-muted">Day {lead}</span>
            </div>
            <div className="max-h-[560px] overflow-y-auto rounded-panel p-2 shadow-neu-inset-sm">
              {c ? <RegionRankList regions={c.regions} selected={selected} onSelect={setSelected} lead={lead} /> : <p className="p-3 text-sm text-muted">Loading…</p>}
            </div>
          </NeuCard>
        </aside>
      </div>

      <RegionDrawer regionId={selected} date={date} variable={variable} lead={lead} setLead={setLead} meta={meta} onClose={() => setSelected(undefined)} />
    </div>
  );
}
