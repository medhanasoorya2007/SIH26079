from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import num, store_dep
from app.schemas.models import LeadDetail, Reason, Region, RegionDetail
from app.services.store import DataStore

router = APIRouter(tags=["region"])


@router.get("/region/{region_id}", response_model=RegionDetail)
def region(
    region_id: str,
    date: str | None = Query(None, description="Issue date YYYY-MM-DD; default latest"),
    var: str = Query("rain"),
    analogs: int = Query(5, ge=0, le=5),
    store: DataStore = Depends(store_dep),
) -> RegionDetail:
    """Day 1-10 bust probabilities, plain-English reasons and analog cases for one region."""
    if region_id not in store.regions.index:
        raise HTTPException(404, f"unknown region {region_id}")
    date = date or store.latest_date()
    rows = store.region_rows(date, region_id, var)
    if rows.empty:
        raise HTTPException(404, f"no forecasts for {region_id} on {date}")
    reg = store.regions.loc[region_id]
    leads = []
    for pos, r in rows.iterrows():
        reasons = json.loads(r["reasons"]) if isinstance(r["reasons"], str) else []
        leads.append(
            LeadDetail(
                lead_day=int(r["lead_day"]),
                valid_date=r["valid_date"].strftime("%Y-%m-%d"),
                fc=num(r["fc"]),
                fc_alt=num(r.get("fc_alt")),
                obs=num(r.get("obs")),
                abs_error=num(r.get("abs_error")),
                bust=num(r.get("bust")),
                bust_prob=num(r["prob"]),
                baseline_prob=num(r.get("baseline_prob")),
                confidence=num(r["confidence"]),
                risk=r["risk"],
                regime=r.get("regime"),
                disagreement=num(r.get("disagreement")),
                jump=num(r.get("jump")),
                reasons=[Reason(**x) for x in reasons],
                analogs=store.analogs(int(pos), analogs) if analogs else [],
            )
        )
    return RegionDetail(
        source=store.source,
        is_synthetic=bool(store.meta["is_synthetic"]),
        region=Region(**reg[["id", "name", "subdivision", "zone", "lat", "lon"]].to_dict()),
        date=date,
        variable=var,
        leads=leads,
    )
