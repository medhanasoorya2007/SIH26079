"use client";

import { useEffect, useState } from "react";
import { NeuCard, NeuSegmented } from "@/components/neu";
import { ReplayCompare } from "@/components/replay/ReplayCompare";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { cn } from "@/lib/utils";

export default function ReplayPage() {
  const list = useApi("replay-list", api.replayList);
  const [eventId, setEventId] = useState<string>();
  useEffect(() => {
    if (!eventId && list.data?.length) setEventId(list.data[list.data.length - 1].id);
  }, [list.data, eventId]);
  const ev = useApi(eventId ? `ev|${eventId}` : null, () => api.replay(eventId!));
  const [day, setDay] = useState<string>();
  const [regionId, setRegionId] = useState<string>();
  const [step, setStep] = useState(1);

  useEffect(() => {
    const e = ev.data;
    if (!e) return;
    const peak = e.peak?.valid_date && e.days.some((d) => d.valid_date === e.peak.valid_date) ? e.peak.valid_date : e.days[0]?.valid_date;
    setDay(peak);
    const d = e.days.find((x) => x.valid_date === peak);
    const busted = d?.regions.find((r) => r.busted_day1) ?? d?.regions[0];
    setRegionId(busted?.region_id);
    setStep(1);
  }, [ev.data]);

  const dayData = ev.data?.days.find((d) => d.valid_date === day);
  const region = dayData?.regions.find((r) => r.region_id === regionId) ?? dayData?.regions[0];

  return (
    <div className="space-y-8">
      <header className="max-w-3xl">
        <h1 className="font-display text-3xl font-extrabold tracking-tight text-fg md:text-4xl">Replay</h1>
        <p className="mt-2 text-sm text-muted">
          Real past events with verified forecast and IMD coverage (docs/replay_events.md). Their windows were excluded from training and calibration. &ldquo;Spread&rdquo; is the lagged-ensemble spread of recent HRES runs.
        </p>
      </header>
      {list.error && <p className="text-sm font-semibold text-risk-high-text">{list.error.message}</p>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {list.data?.map((e) => (
          <button
            key={e.id}
            type="button"
            onClick={() => setEventId(e.id)}
            aria-pressed={e.id === eventId}
            className={cn(
              "focus-ring rounded-panel bg-bg p-5 text-left transition-all duration-ui ease-out",
              e.id === eventId ? "shadow-neu-inset" : "shadow-neu hover:-translate-y-0.5 hover:shadow-neu-hover",
            )}
          >
            <div className="font-display text-sm font-bold text-fg">{e.title}</div>
            <div className="mt-1 text-xs text-muted">
              {fmtDate(e.window[0], { day: "numeric", month: "short" })} – {fmtDate(e.window[1])} · {e.split === "test" ? "test year" : "held out from training"}
            </div>
            {e.peak?.imd_mm !== undefined && (
              <div className="mt-2 text-xs tabular text-muted">
                Peak IMD {e.peak.imd_mm} mm ({e.peak.region}), HRES Day 1 {e.peak.hres_day1_mm} mm
              </div>
            )}
          </button>
        ))}
      </div>

      {ev.data && dayData && region && (
        <NeuCard className="space-y-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="font-display text-xl font-bold text-fg">{ev.data.title}</h2>
              <p className="text-xs text-muted">Valid day and subdivision</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <NeuSegmented
                label="Valid day"
                value={day ?? ""}
                onChange={(v) => {
                  setDay(v);
                  setStep(1);
                }}
                options={ev.data.days.map((d) => ({ value: d.valid_date, label: fmtDate(d.valid_date, { day: "numeric", month: "short" }) }))}
                className="flex-wrap"
              />
            </div>
          </div>
          {dayData.regions.length > 1 && (
            <NeuSegmented
              label="Subdivision"
              value={region.region_id}
              onChange={(v) => {
                setRegionId(v);
                setStep(1);
              }}
              options={dayData.regions.map((r) => ({ value: r.region_id, label: r.region }))}
              className="flex-wrap"
            />
          )}
          <ReplayCompare region={region} validDate={dayData.valid_date} step={Math.min(step, region.steps.length)} setStep={setStep} />
        </NeuCard>
      )}
    </div>
  );
}
