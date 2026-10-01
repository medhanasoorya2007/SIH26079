"use client";

import { ShieldAlert } from "lucide-react";
import { AblationChart, LeadPrChart, ReliabilityChart } from "@/components/charts/Charts";
import { CostLossPanel } from "@/components/charts/CostLossPanel";
import { NeuCard, NeuWell } from "@/components/neu";
import { api } from "@/lib/api";
import { fmtDate, num, pct } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { cn } from "@/lib/utils";
import { BRAND, displayName } from "@/lib/brand";

export default function EvidencePage() {
  const { data: m, error } = useApi("metrics", api.metrics);
  if (error) return <p className="text-sm font-semibold text-risk-high-text">{error.message}</p>;
  if (!m) return <p className="text-sm text-muted">Loading evidence…</p>;
  const methods = Object.keys(m.methods);
  const cw = m.confidently_wrong;
  const ew = m.early_warning;
  return (
    <div className="space-y-10">
      <header className="max-w-3xl">
        <h1 className="font-display text-3xl font-extrabold tracking-tight text-fg md:text-4xl">Evidence</h1>
        <p className="mt-2 text-sm text-muted">
          {BRAND} vs both spread baselines on the fully unseen test years {m.split.test_years.join(" & ")} ({m.test_period.n.toLocaleString("en-IN")} forecasts, {fmtDate(m.test_period.from)} to {fmtDate(m.test_period.to)}). Trained on{" "}
          {m.split.train_years.join(" & ")}, calibrated on {m.split.calibration_years.join(", ")}. Bust = IMD rainfall category missed (heavy observed, not forecast) or off by ≥ 2 classes. Usual bust rate {pct(m.headline.base_rate, 2)}.
        </p>
      </header>

      <section aria-label="Headline metrics" className="grid gap-6 md:grid-cols-3">
        {methods.map((name) => {
          const o = m.overall[name];
          const ci = m.bootstrap?.pr_auc_ci?.[name];
          const model = name === "BustGuard";
          return (
            <NeuCard key={name} compact className={cn(model && "ring-2 ring-accent/40")}>
              <div className={cn("text-sm font-bold", model ? "text-accent-text" : "text-muted")}>{displayName(name)}</div>
              <NeuWell className="mt-4">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">PR-AUC (primary)</div>
                <div className="font-display text-4xl font-extrabold tabular text-fg">{num(o.pr_auc, 3)}</div>
                {ci && (
                  <div className="text-[11px] tabular text-muted">
                    95% CI {num(ci[0], 3)}–{num(ci[1], 3)}
                  </div>
                )}
              </NeuWell>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
                <div>
                  <dt className="text-muted">Busts caught</dt>
                  <dd className="font-display text-lg font-bold tabular text-fg">{pct(o.operating_point.recall)}</dd>
                </div>
                <div>
                  <dt className="text-muted">False-alarm rate</dt>
                  <dd className="font-display text-lg font-bold tabular text-fg">{pct(o.operating_point.far, 1)}</dd>
                </div>
                <div>
                  <dt className="text-muted">CSI</dt>
                  <dd className="font-display text-lg font-bold tabular text-fg">{num(o.operating_point.csi, 3)}</dd>
                </div>
                <div>
                  <dt className="text-muted">Brier skill</dt>
                  <dd className="font-display text-lg font-bold tabular text-fg">{num(o.brier_skill_vs_climatology, 3)}</dd>
                </div>
              </dl>
              <p className="mt-3 text-[11px] text-muted">Operating threshold frozen at {pct(m.operating_far)} false alarms on the calibration year.</p>
            </NeuCard>
          );
        })}
      </section>

      <NeuCard>
        <div className="flex flex-wrap items-start gap-6">
          <span className="grid h-14 w-14 shrink-0 place-items-center rounded-control shadow-neu-inset">
            <ShieldAlert className="h-6 w-6 text-accent-text" aria-hidden />
          </span>
          <div className="min-w-[16rem] flex-1">
            <h2 className="font-display text-xl font-bold text-fg">Confidently wrong: busts the spread said were safe</h2>
            <p className="mt-1 text-sm text-muted">
              {cw.n_low_spread_busts} of {cw.n_busts} test busts ({pct(cw.share_of_busts_with_low_spread)}) happened while the lagged-ensemble spread was in its lowest third for the regime and month. Small sample: read as indicative.
            </p>
            <ul className="mt-5 space-y-3">
              {methods.map((name) => {
                const r = (cw[name] as { recall_low_spread_busts: number | null })?.recall_low_spread_busts ?? 0;
                return (
                  <li key={name} className="grid grid-cols-[12rem_1fr_3.5rem] items-center gap-3 text-sm">
                    <span className={name === "BustGuard" ? "font-bold text-accent-text" : "text-muted"}>{displayName(name)}</span>
                    <span className="h-3.5 overflow-hidden rounded-full shadow-neu-inset-sm">
                      <span className={cn("block h-full rounded-full", name === "BustGuard" ? "bg-accent" : "bg-muted/60")} style={{ width: `${r * 100}%` }} />
                    </span>
                    <span className="text-right font-semibold tabular text-fg">{pct(r)}</span>
                  </li>
                );
              })}
            </ul>
            <p className="mt-4 text-xs text-muted">
              Recall on low-spread busts at each method&apos;s operating threshold. CONFIDENTLY-WRONG ALERTS raised on the test years: {cw.alerts.n_alerts}, of which {cw.alerts.n_alert_busts} verified as busts (precision {pct(cw.alerts.precision)} vs {pct(cw.alerts.base_rate_low_spread, 1)} among all low-spread forecasts).
            </p>
          </div>
        </div>
      </NeuCard>

      <section className="grid gap-8 lg:grid-cols-2">
        <NeuCard compact>
          <LeadPrChart metrics={m} />
        </NeuCard>
        <NeuCard compact>
          <ReliabilityChart reliability={m.reliability} />
        </NeuCard>
        {m.ablation && (
          <NeuCard compact>
            <AblationChart rows={m.ablation} />
            <p className="mt-3 text-[11px] text-muted">
              Honest reading: most skill comes from context (location, season, lead, forecast amount, recent verified error). Physical families (regime, pressure/wind, upstream) add smaller, consistent gains.
            </p>
          </NeuCard>
        )}
        <NeuCard compact>
          <h2 className="mb-3 text-sm font-bold text-fg">Early warning ({ew.n_events} region-days whose Day-1 forecast busted)</h2>
          <div className="space-y-3">
            {methods.map((name) => {
              const e = ew[name] as { mean_days: number | null; share_warned: number | null; share_3plus_days: number | null };
              return (
                <NeuWell key={name} shallow className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className={cn("col-span-3 text-left text-sm font-semibold", name === "BustGuard" ? "text-accent-text" : "text-muted")}>{displayName(name)}</div>
                  <div>
                    <div className="font-display text-xl font-extrabold tabular text-fg">{num(e.mean_days, 1)}</div>
                    <div className="text-muted">mean days of warning</div>
                  </div>
                  <div>
                    <div className="font-display text-xl font-extrabold tabular text-fg">{pct(e.share_warned)}</div>
                    <div className="text-muted">warned at all</div>
                  </div>
                  <div>
                    <div className="font-display text-xl font-extrabold tabular text-fg">{pct(e.share_3plus_days)}</div>
                    <div className="text-muted">≥ 3 days ahead</div>
                  </div>
                </NeuWell>
              );
            })}
          </div>
          <p className="mt-3 text-[11px] text-muted">A warning counts only if every forecast from Day L down to Day 1 was flagged.</p>
        </NeuCard>
      </section>

      <CostLossPanel />

      <NeuCard compact className="text-xs leading-relaxed text-muted">
        <p>{m.spread_note}</p>
        <p className="mt-2">All numbers are computed on the held-out test years and reproduced offline by <code>make headline</code>.</p>
      </NeuCard>
    </div>
  );
}
