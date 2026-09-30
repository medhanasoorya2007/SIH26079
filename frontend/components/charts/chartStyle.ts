import { HEX } from "@/lib/risk";

/** Chart conventions: model = accent solid; baselines = muted dashed (distinct dash patterns). */
export const MODEL = "BustGuard";
export const DASHES = ["6 4", "2 4", "10 3 2 3"];

export function seriesStyle(name: string, i: number) {
  return name === MODEL ? { stroke: HEX.accent, strokeWidth: 3, strokeDasharray: undefined } : { stroke: HEX.muted, strokeWidth: 2, strokeDasharray: DASHES[i % DASHES.length] };
}

export const axis = { stroke: HEX.grid, tick: { fill: HEX.muted, fontSize: 11 }, tickLine: false };
export const grid = { stroke: HEX.grid, strokeDasharray: "3 3", vertical: false };
export const tooltipStyle = {
  contentStyle: { background: "#e0e5ec", border: "none", borderRadius: 16, boxShadow: "5px 5px 10px rgba(163,177,198,0.6), -5px -5px 10px rgba(255,255,255,0.5)", fontSize: 12, color: HEX.fg },
  labelStyle: { color: HEX.fg, fontWeight: 600 },
};
