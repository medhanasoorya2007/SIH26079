"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import type { DateEntry, Meta } from "@/types/api";

interface AppState {
  meta?: Meta;
  dates: DateEntry[];
  date?: string;
  setDate: (d: string) => void;
  variable: string;
  setVariable: (v: string) => void;
  lead: number;
  setLead: (l: number) => void;
  error?: string;
}

const Ctx = createContext<AppState | null>(null);

/** Issue date / variable / lead shared by every page (the header shows the issue date). */
export function AppStateProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta>();
  const [dates, setDates] = useState<DateEntry[]>([]);
  const [date, setDate] = useState<string>();
  const [variable, setVariable] = useState("rain");
  const [lead, setLead] = useState(3);
  const [error, setError] = useState<string>();

  useEffect(() => {
    Promise.all([api.meta(), api.dates()])
      .then(([m, d]) => {
        setMeta(m);
        setDates(d.dates);
        const params = new URLSearchParams(window.location.search);
        const qd = params.get("date");
        setDate(qd && d.dates.some((x) => x.date === qd) ? qd : m.latest_date);
        const ql = Number(params.get("lead"));
        if (ql && m.lead_days.includes(ql)) setLead(ql);
      })
      .catch((e: Error) => setError(`Cannot reach the Predicta API (${e.message}). Start it with \`make api\`.`));
  }, []);

  const value = useMemo(() => ({ meta, dates, date, setDate, variable, setVariable, lead, setLead, error }), [meta, dates, date, variable, lead, error]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppState(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAppState outside AppStateProvider");
  return v;
}
