from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import store_dep
from app.services.store import DataStore, region_pathway, risk_windows

router = APIRouter(tags=["region"])


@router.get("/region/{region_id}")
def region(
    region_id: str,
    date: str | None = Query(None, description="Issue date YYYY-MM-DD; default latest test date"),
    var: str = Query("rain"),
    store: DataStore = Depends(store_dep),
) -> dict:
    """Day 1-10 bust probabilities for one subdivision with, per lead: risk level, reliability,
    family contributions (% of the bust-raising SHAP), plain-English reasons, pathway chain,
    analog cases ("N of M similar past cases busted"), confidently-wrong flag and what the
    spread baseline says. Also the risk window (lead days at MEDIUM or above)."""
    if region_id not in store.regions.index:
        raise HTTPException(404, f"unknown region {region_id}")
    date = date or store.latest_date()
    rows = store.region_rows(date, region_id, var)
    if rows.empty:
        raise HTTPException(404, f"no forecasts for {region_id} on {date}")
    reg = store.regions.loc[region_id]
    leads = []
    for _, r in rows.iterrows():
        s = store.forecast_summary(r)
        s["reasons"] = store.reasons(r)
        s["pathway"] = region_pathway(store, r)
        s["analogs"] = store.analogs(r)
        leads.append(s)
    return {
        "source": store.source,
        "is_synthetic": bool(store.meta["is_synthetic"]),
        "region": {
            k: (float(reg[k]) if k in ("lat", "lon") else reg[k])
            for k in ("id", "name", "zone", "lat", "lon")
        },
        "date": date,
        "variable": var,
        "risk_window": risk_windows(rows),
        "any_confidently_wrong": bool(rows["cw"].any()),
        "leads": leads,
    }
