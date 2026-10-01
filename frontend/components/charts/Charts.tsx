"use client";

import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { NeuWell } from "@/components/neu";
import { HEX } from "@/lib/risk";
import type { Metrics, ReliabilityBin } from "@/types/api";
import { axis, grid, MODEL, seriesStyle, tooltipStyle } from "./chartStyle";
import { displayName } from "@/lib/brand";

export function ChartWell({ title, caption, children, height = 280 }: { title: string; caption?: string; children: React.ReactNode; height?: number }) {
  return (
    <figure>
      <figcaption className="mb-3">
        <div className="text-sm font-bold text-fg">{title}</div>
        {caption && <div className="text-[11px] text-muted">{caption}</div>}
      </figcaption>
      <NeuWell className="p-3" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          {children as React.ReactElement}
        </ResponsiveContainer>
      </NeuWell>
    </figure>
  );
}

const legendStyle = { fontSize: 11, color: HEX.muted };

/** PR-AUC per lead day: model vs both baselines. */
export function LeadPrChart({ metrics }: { metrics: Metrics }) {
  const methods = Object.keys(metrics.methods);
  const rows = Object.entries(metrics.per_lead)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([lead, per]) => ({ lead: `D${lead}`, ...Object.fromEntries(methods.map((m) => [m, per[m]?.pr_auc ?? null])) }));
  return (
    <ChartWell title="PR-AUC by lead day (test years)" caption="Higher is better. Busts are rare, so PR-AUC is the primary metric.">
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
        <CartesianGrid {...grid} />
        <XAxis dataKey="lead" {...axis} />
        <YAxis {...axis} domain={[0, "auto"]} />
        <Tooltip {...tooltipStyle} formatter={(v: number) => v?.toFixed(3)} />
        <Legend wrapperStyle={legendStyle} />
        {methods.map((m, i) => (
          <Line key={m} type="monotone" dataKey={m} name={displayName(m)} dot={false} isAnimationActive={false} {...seriesStyle(m, i)} />
        ))}
      </LineChart>
    </ChartWell>
  );
}

/** Reliability diagram: mean forecast probability vs observed bust frequency. */
export function ReliabilityChart({ reliability }: { reliability: Record<string, ReliabilityBin[]> }) {
  const methods = Object.keys(reliability);
  const maxP = Math.max(0.05, ...methods.flatMap((m) => reliability[m].map((b) => Math.max(b.mean_prob, b.obs_freq))));
  const top = Math.min(1, Math.ceil(maxP * 10) / 10);
  return (
    <ChartWell title="Reliability diagram (test years)" caption="Points on the diagonal = calibrated probabilities. Point size is not shown; bins with few forecasts are noisy.">
      <LineChart margin={{ top: 8, right: 12, bottom: 12, left: -8 }}>
        <CartesianGrid {...grid} vertical />
        <XAxis type="number" dataKey="mean_prob" domain={[0, top]} {...axis} label={{ value: "forecast probability", position: "insideBottom", offset: -6, fill: HEX.muted, fontSize: 11 }} />
        <YAxis type="number" domain={[0, top]} {...axis} />
        <Tooltip {...tooltipStyle} formatter={(v: number) => v?.toFixed(3)} />
        <Legend wrapperStyle={legendStyle} verticalAlign="top" />
        <ReferenceLine segment={[{ x: 0, y: 0 }, { x: top, y: top }]} stroke={HEX.grid} strokeWidth={1.5} />
        {methods.map((m, i) => (
          <Line key={m} data={reliability[m]} dataKey="obs_freq" name={displayName(m)} type="linear" isAnimationActive={false} dot={{ r: m === MODEL ? 4 : 3, fill: seriesStyle(m, i).stroke }} {...seriesStyle(m, i)} />
        ))}
      </LineChart>
    </ChartWell>
  );
}

/** Ablation: change in test PR-AUC when a family is dropped (or only context is kept). */
export function AblationChart({ rows }: { rows: NonNullable<Metrics["ablation"]> }) {
  const data = rows.filter((r) => r.family !== "none (full model)").map((r) => ({ name: r.family.startsWith("ONLY") ? "context only" : `– ${r.family}`, delta: r.delta }));
  return (
    <ChartWell title="Ablation: PR-AUC change (test years)" caption="Retrained without each feature family. Negative = the family helps." height={300}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 24 }}>
        <CartesianGrid {...grid} horizontal={false} vertical />
        <XAxis type="number" {...axis} tickFormatter={(v: number) => v.toFixed(2)} />
        <YAxis type="category" dataKey="name" width={96} {...axis} />
        <Tooltip {...tooltipStyle} formatter={(v: number) => v.toFixed(3)} />
        <ReferenceLine x={0} stroke={HEX.muted} />
        <Bar dataKey="delta" isAnimationActive={false} radius={[4, 4, 4, 4]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.delta < 0 ? HEX.accent : HEX.grid} />
          ))}
        </Bar>
      </BarChart>
    </ChartWell>
  );
}

/** Cost-loss relative economic value curves with the chosen user's cost/loss ratio marked. */
export function CostLossChart({ curves, alpha, userLabel }: { curves: Record<string, { alpha: number; value: number | null }[]>; alpha: number; userLabel: string }) {
  const methods = Object.keys(curves);
  const rows = curves[methods[0]].map((p, k) => ({ alpha: p.alpha, ...Object.fromEntries(methods.map((m) => [m, curves[m][k]?.value !== null ? Math.max(-0.5, curves[m][k].value as number) : null])) }));
  const at = rows.reduce((best, r) => (Math.abs(r.alpha - alpha) < Math.abs(best.alpha - alpha) ? r : best), rows[0]);
  return (
    <ChartWell title="Relative economic value" caption={`Value of acting on bust warnings (1 = perfect, 0 = no better than climatology). Marker: ${userLabel}.`}>
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 12, left: -8 }}>
        <CartesianGrid {...grid} />
        <XAxis dataKey="alpha" type="number" scale="log" domain={["dataMin", "dataMax"]} {...axis} tickFormatter={(v: number) => v.toString()} label={{ value: "cost / loss ratio", position: "insideBottom", offset: -6, fill: HEX.muted, fontSize: 11 }} />
        <YAxis domain={[-0.5, 1]} {...axis} />
        <Tooltip {...tooltipStyle} formatter={(v: number) => v?.toFixed(2)} labelFormatter={(v: number) => `C/L = ${v}`} />
        <Legend wrapperStyle={legendStyle} verticalAlign="top" />
        <ReferenceLine y={0} stroke={HEX.muted} />
        <ReferenceLine x={at.alpha} stroke={HEX.accent} strokeDasharray="3 3" />
        {methods.map((m, i) => (
          <Line key={m} dataKey={m} name={displayName(m)} type="monotone" dot={false} isAnimationActive={false} connectNulls {...seriesStyle(m, i)} />
        ))}
        <ReferenceDot x={at.alpha} y={(at as Record<string, number>)[MODEL] ?? 0} r={5} fill={HEX.accent} stroke="none" />
      </LineChart>
    </ChartWell>
  );
}
