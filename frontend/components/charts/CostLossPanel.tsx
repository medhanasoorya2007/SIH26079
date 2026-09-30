"use client";

import { useState } from "react";
import { NeuCard, NeuSegmented, NeuWell } from "@/components/neu";
import { api } from "@/lib/api";
import { num } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { CostLossChart } from "./Charts";

const USERS = [
  { value: "disaster_manager", label: "Disaster manager" },
  { value: "power_utility", label: "Power utility" },
  { value: "farmer", label: "Farmer" },
];

/** Cost-loss value with a user toggle (illustrative cost/loss ratios from configs/model.yaml). */
export function CostLossPanel() {
  const [user, setUser] = useState("disaster_manager");
  const { data, error } = useApi(`cl|${user}`, () => api.costloss(user));
  return (
    <NeuCard>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="font-display text-xl font-bold text-fg">Cost-loss value</h2>
          <p className="text-xs text-muted">Should this user act on a bust warning? Ratios are illustrative assumptions, not measurements.</p>
        </div>
        <NeuSegmented label="User type" value={user} onChange={setUser} options={USERS} />
      </div>
      {error && <p className="text-sm text-risk-high-text">{error.message}</p>}
      {data && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <CostLossChart curves={data.curves} alpha={data.preset.alpha} userLabel={`${data.preset.label} (C/L ${data.preset.alpha})`} />
          </div>
          <div className="space-y-3">
            <NeuWell shallow className="text-sm">
              <div className="font-semibold text-fg">{data.preset.label}</div>
              <div className="text-xs text-muted">Action: {data.preset.action}</div>
              <div className="mt-1 text-xs text-muted">Cost/loss ratio {data.preset.alpha}</div>
            </NeuWell>
            {Object.entries(data.preset.value).map(([m, v]) => (
              <NeuWell key={m} shallow className="flex items-center justify-between py-3 text-sm">
                <span className={m === "BustGuard" ? "font-bold text-accent-text" : "text-muted"}>{m}</span>
                <span className="font-display text-lg font-extrabold tabular text-fg">{num(v)}</span>
              </NeuWell>
            ))}
          </div>
        </div>
      )}
    </NeuCard>
  );
}
