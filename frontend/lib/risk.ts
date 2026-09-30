import type { Risk } from "@/types/api";

/** Risk semantics: the ONLY colours besides the accent. Text uses darkened, AA-contrast tones. */
export const RISK_LABEL: Record<Risk | "CW", string> = {
  Low: "LOW",
  Medium: "MEDIUM",
  High: "HIGH",
  CW: "CONFIDENTLY WRONG",
};

export const RISK_FILL: Record<Risk, string> = {
  Low: "var(--risk-low)",
  Medium: "var(--risk-medium)",
  High: "var(--risk-high)",
};

export const RISK_TEXT_CLASS: Record<Risk, string> = {
  Low: "text-risk-low-text",
  Medium: "text-risk-medium-text",
  High: "text-risk-high-text",
};

/** Concrete hex values (MapLibre and SVG gradients cannot read CSS variables). Keep in sync
 * with app/globals.css. */
export const HEX = {
  low: "#2f9e8f",
  medium: "#c98a1b",
  high: "#d1493b",
  accent: "#6c63ff",
  basemap: "#e7ebf1",
  outline: "rgba(61,72,82,0.35)",
  grid: "#cbd2dc",
  muted: "#5a6270",
  fg: "#3d4852",
};

function mix(a: string, b: string, t: number): string {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return "#" + pa.map((v, i) => Math.round(v + (pb[i] - v) * t).toString(16).padStart(2, "0")).join("");
}

/** Sequential 5-step map scale: low -> medium -> high. */
export const MAP_SCALE = [HEX.low, mix(HEX.low, HEX.medium, 0.5), HEX.medium, mix(HEX.medium, HEX.high, 0.5), HEX.high];

/** Step index 0..4 from the bust probability and the frozen operating thresholds. */
export function mapStep(p: number, thr: { medium: number; high: number }): number {
  if (p >= thr.high) return 4;
  if (p >= (thr.medium + thr.high) / 2) return 3;
  if (p >= thr.medium) return 2;
  if (p >= thr.medium / 2) return 1;
  return 0;
}

export const MAP_LEGEND: { step: number; label: string; risk: Risk }[] = [
  { step: 0, label: "Low", risk: "Low" },
  { step: 1, label: "Low (upper)", risk: "Low" },
  { step: 2, label: "Medium", risk: "Medium" },
  { step: 3, label: "Medium (upper)", risk: "Medium" },
  { step: 4, label: "High", risk: "High" },
];
