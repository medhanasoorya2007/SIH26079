"""Early-warning lead time (v2 #14).

A bust *event* is a (region, valid day) whose Day-1 forecast busted, i.e. even the last
forecast before the day was wrong. For each method the warning lead time is the largest L
such that the forecasts for that day issued at leads 1..L were ALL flagged (p >= the
method's frozen operating threshold): the warning had stood continuously since Day L.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def event_lead_times(
    df: pd.DataFrame,
    prob_cols: dict[str, str],
    thresholds: dict[str, float],
    bust_col: str = "bust",
) -> pd.DataFrame:
    d1 = df[(df["lead_day"] == 1) & (df[bust_col] == 1)][["region_id", "valid_date"]]
    if d1.empty:
        return pd.DataFrame(columns=["region_id", "valid_date", *prob_cols])
    sub = df.merge(d1, on=["region_id", "valid_date"]).sort_values("lead_day")
    rows = []
    for (rid, vd), g in sub.groupby(["region_id", "valid_date"]):
        rec = {"region_id": rid, "valid_date": vd}
        leads = g["lead_day"].to_numpy()
        for name, col in prob_cols.items():
            flagged = g[col].to_numpy(dtype=float) >= thresholds[name]
            lead = 0
            for L, f in zip(leads, flagged, strict=True):
                if int(L) - 1 != lead or not f:
                    break
                lead = int(L)
            rec[name] = lead
        rows.append(rec)
    return pd.DataFrame(rows)


def summarize(ev: pd.DataFrame, names: list[str]) -> dict:
    out = {"n_events": int(len(ev))}
    for n in names:
        v = ev[n].to_numpy(dtype=float) if len(ev) else np.array([])
        out[n] = {
            "mean_days": float(v.mean()) if len(v) else None,
            "median_days": float(np.median(v)) if len(v) else None,
            "share_warned": float((v >= 1).mean()) if len(v) else None,
            "share_3plus_days": float((v >= 3).mean()) if len(v) else None,
            "histogram": {str(k): int((v == k).sum()) for k in range(0, 11)},
        }
    return out
