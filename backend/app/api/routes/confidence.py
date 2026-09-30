from __future__ import annotations

import json

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import num, store_dep
from app.schemas.models import ConfidenceMap, RegionConfidence
from app.services.store import DataStore

router = APIRouter(tags=["confidence"])


@router.get("/confidence", response_model=ConfidenceMap)
def confidence(
    date: str | None = Query(
        None, description="Forecast issue (initialisation) date YYYY-MM-DD; default latest"
    ),
    lead: int = Query(3, ge=1, le=10, description="Lead day 1-10"),
    var: str = Query("rain", description="Variable: rain | tmax"),
    store: DataStore = Depends(store_dep),
) -> ConfidenceMap:
    """Region-wise forecast confidence map for one issue date and lead day."""
    date = date or store.latest_date()
    if lead not in store.meta["lead_days"]:
        raise HTTPException(
            404, f"lead day {lead} not in this dataset (available: {store.meta['lead_days']})"
        )
    sl = store.slice(date, lead, var)
    if sl.empty:
        raise HTTPException(404, f"no forecasts for date={date} lead={lead} var={var}")
    sl = sl.sort_values("prob", ascending=False)
    regs = store.regions
    out = []
    for rank, (_, r) in enumerate(sl.iterrows(), 1):
        reg = regs.loc[r["region_id"]]
        reasons = json.loads(r["reasons"]) if isinstance(r["reasons"], str) else []
        out.append(
            RegionConfidence(
                id=r["region_id"],
                name=reg["name"],
                subdivision=reg["subdivision"],
                zone=reg["zone"],
                lat=float(reg["lat"]),
                lon=float(reg["lon"]),
                fc=num(r["fc"]),
                fc_alt=num(r.get("fc_alt")),
                obs=num(r.get("obs")),
                bust_prob=num(r["prob"]),
                baseline_prob=num(r.get("baseline_prob")),
                confidence=num(r["confidence"]),
                risk=r["risk"],
                regime=r.get("regime"),
                bust=num(r.get("bust")),
                rank=rank,
                top_reason=reasons[0]["text"] if reasons else None,
            )
        )
    probs = sl["prob"].to_numpy(dtype=float)
    risk_counts = sl["risk"].value_counts().to_dict()
    return ConfidenceMap(
        source=store.source,
        is_synthetic=bool(store.meta["is_synthetic"]),
        date=date,
        lead=lead,
        variable=var,
        valid_date=sl["valid_date"].iloc[0].strftime("%Y-%m-%d"),
        regions=out,
        error_prone=[o.id for o in out[:10]],
        summary={
            "mean_confidence": num(1 - np.nanmean(probs)),
            "max_bust_prob": num(np.nanmax(probs)),
            "risk_counts": risk_counts,
            "n_regions": len(out),
            "verified": bool(sl["obs"].notna().any()),
            "busts_observed": int(np.nansum(sl["bust"].to_numpy(dtype=float)))
            if sl["bust"].notna().any()
            else None,
        },
    )
