import type {
  Blindspots,
  ConfidenceMap,
  CostLoss,
  DateEntry,
  Meta,
  Metrics,
  Region,
  RegionDetail,
  ReplayEvent,
  ReplayEventSummary,
  Scorecard,
} from "@/types/api";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function get<T>(path: string, params?: Record<string, string | number | undefined | null>): Promise<T> {
  const url = new URL(API_BASE + path);
  Object.entries(params ?? {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  });
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* keep status text */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  meta: () => get<Meta>("/meta"),
  dates: () => get<{ latest: string; dates: DateEntry[] }>("/dates"),
  regions: () => get<Region[]>("/regions"),
  geo: () => get<GeoJSON.FeatureCollection>("/geo/subdivisions"),
  confidence: (date: string | undefined, lead: number, variable: string) =>
    get<ConfidenceMap>("/confidence", { date, lead, var: variable }),
  region: (id: string, date: string | undefined, variable: string) =>
    get<RegionDetail>(`/region/${encodeURIComponent(id)}`, { date, var: variable }),
  metrics: () => get<Metrics>("/metrics"),
  scorecard: () => get<Scorecard>("/scorecard"),
  costloss: (user: string) => get<CostLoss>("/costloss", { user }),
  blindspots: (date?: string, limit = 60) => get<Blindspots>("/blindspots", { date, limit }),
  replayList: () => get<ReplayEventSummary[]>("/replay"),
  replay: (id: string) => get<ReplayEvent>(`/replay/${encodeURIComponent(id)}`),
  saveAnalysis: async (body: { title: string; note?: string; date: string; lead: number; variable: string; region_id?: string }) => {
    const res = await fetch(`${API_BASE}/saved`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new ApiError(res.status, res.statusText);
    return res.json();
  },
};
