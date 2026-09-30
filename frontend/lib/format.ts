export const pct = (x: number | null | undefined, digits = 0) =>
  x === null || x === undefined || Number.isNaN(x) ? "–" : `${(x * 100).toFixed(digits)}%`;

export const mm = (x: number | null | undefined) =>
  x === null || x === undefined || Number.isNaN(x) ? "–" : `${x.toFixed(0)} mm`;

export const num = (x: number | null | undefined, digits = 2) =>
  x === null || x === undefined || Number.isNaN(x) ? "–" : x.toFixed(digits);

export function fmtDate(iso: string | undefined, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }) {
  if (!iso) return "–";
  const d = new Date(iso + "T00:00:00Z");
  return d.toLocaleDateString("en-IN", { ...opts, timeZone: "UTC" });
}

export const times = (p: number | null | undefined, base: number | null | undefined) =>
  p === null || p === undefined || !base ? "–" : `${(p / base).toFixed(1)}×`;
