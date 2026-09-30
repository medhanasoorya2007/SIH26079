from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import num, store_dep
from app.services.store import RISK_ORDER, DataStore

router = APIRouter(tags=["confidence"])


@router.get("/confidence")
def confidence(
    date: str | None = Query(
        None, description="Issue (initialisation) date YYYY-MM-DD; default latest test date"
    ),
    lead: int = Query(3, ge=1, le=10, description="Lead day 1-10"),
    var: str = Query("rain", description="rain | tmax"),
    store: DataStore = Depends(store_dep),
) -> dict:
    """Region-wise forecast confidence map for one issue date and lead day, ranked by bust
    probability, plus per-lead risk summaries for the Day 1-10 slider."""
    if var not in store.meta["variables"]:
        raise HTTPException(
            404,
            store.meta.get("variables_unavailable", {}).get(var, f"variable {var} not available"),
        )
    date = date or store.latest_date()
    if lead not in store.meta["lead_days"]:
        raise HTTPException(
            404, f"lead day {lead} not in this dataset (available: {store.meta['lead_days']})"
        )
    sl = store.slice(date, lead, var)
    if sl.empty:
        raise HTTPException(404, f"no forecasts for date={date} lead={lead} var={var}")
    sl = sl.sort_values("prob", ascending=False)
    regions = []
    for rank, (_, r) in enumerate(sl.iterrows(), 1):
        reg = store.regions.loc[r["region_id"]]
        s = store.forecast_summary(r)
        regions.append(
            {
                "id": r["region_id"],
                "name": reg["name"],
                "zone": reg["zone"],
                "lat": float(reg["lat"]),
                "lon": float(reg["lon"]),
                "rank": rank,
                **{
                    k: s[k]
                    for k in (
                        "fc",
                        "obs",
                        "bust",
                        "bust_prob",
                        "confidence",
                        "risk",
                        "reliability",
                        "confidently_wrong",
                        "low_spread",
                        "spread",
                        "spread_says",
                        "spread_prob",
                        "lr_prob",
                        "regime",
                        "likely_driver",
                        "valid_date",
                    )
                },
            }
        )
    day = store.day(date, var)
    lead_summary = []
    for L, g in day.groupby("lead_day"):
        lead_summary.append(
            {
                "lead_day": int(L),
                "max_risk": max(g["risk"], key=lambda x: RISK_ORDER.get(x, 0)),
                "n_high": int((g["risk"] == "High").sum()),
                "n_medium": int((g["risk"] == "Medium").sum()),
                "n_cw": int(g["cw"].sum()),
                "max_prob": num(g["prob"].max()),
            }
        )
    probs = sl["prob"].to_numpy(dtype=float)
    return {
        "source": store.source,
        "is_synthetic": bool(store.meta["is_synthetic"]),
        "date": date,
        "lead": lead,
        "variable": var,
        "valid_date": sl["valid_date"].iloc[0].strftime("%Y-%m-%d"),
        "split": str(sl["split"].iloc[0]),
        "regions": regions,
        "error_prone": [r["id"] for r in regions if r["risk"] != "Low"][:10],
        "lead_summary": lead_summary,
        "summary": {
            "mean_bust_prob": num(np.nanmean(probs)),
            "base_rate": store.meta.get("headline", {}).get("base_rate"),
            "risk_counts": {k: int((sl["risk"] == k).sum()) for k in ("Low", "Medium", "High")},
            "n_confidently_wrong": int(sl["cw"].sum()),
            "verified": bool(sl["obs"].notna().any()),
            "busts_observed": int(np.nansum(sl["bust"].to_numpy(dtype=float)))
            if sl["bust"].notna().any()
            else None,
        },
    }
