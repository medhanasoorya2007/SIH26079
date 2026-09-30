from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import num, store_dep
from app.schemas.models import SavedAnalysis, SavedAnalysisIn
from app.services import store as st
from app.services.store import DataStore

router = APIRouter()


@router.get("/metrics", tags=["evidence"])
def metrics(store: DataStore = Depends(store_dep)) -> dict:
    """Held-out test verification of BustGuard vs BOTH spread baselines: PR-AUC (primary),
    ROC-AUC, Brier, recall at fixed false-alarm rates, CSI, reliability, confidently-wrong
    (low-spread) recall, early warning, cost-loss, ablation, bootstrap CIs."""
    rep = store.report()
    if not rep:
        raise HTTPException(404, "no metrics exported for this source")
    return {
        "label": store.label,
        "label_definition": store.meta.get("label_definition"),
        "split": store.meta.get("split"),
        "headline": store.meta.get("headline"),
        "spread_note": store.meta.get("spread_note"),
        "is_synthetic": bool(store.meta["is_synthetic"]),
        **{
            k: rep.get(k)
            for k in (
                "methods",
                "overall",
                "per_lead",
                "reliability",
                "reliability_calibration_block",
                "confidently_wrong",
                "early_warning",
                "ablation",
                "bootstrap",
                "thresholds",
                "risk_thresholds",
                "test_period",
                "operating_far",
            )
        },
        "families": store.metrics.get("families"),
        "signals": store.meta.get("signals", []),
    }


@router.get("/scorecard", tags=["evidence"])
def scorecard(store: DataStore = Depends(store_dep)) -> dict:
    """Regime x lead-day heatmap: PR-AUC of every method and BustGuard's improvement over the
    best baseline (test years; cells with too few busts are null)."""
    rep = store.report()
    if "scorecard" not in rep:
        raise HTTPException(404, "no scorecard exported")
    return {**rep["scorecard"], "methods": rep["methods"]}


@router.get("/costloss", tags=["evidence"])
def costloss(
    user: str = Query("disaster_manager", description="disaster_manager | power_utility | farmer"),
    store: DataStore = Depends(store_dep),
) -> dict:
    """Relative economic value curves (test years) and the value for a user preset
    (illustrative cost/loss ratio; see configs/model.yaml)."""
    cl = store.report().get("costloss")
    if not cl:
        raise HTTPException(404, "no cost-loss analysis exported")
    if user not in cl["users"]:
        raise HTTPException(404, f"unknown user {user}; choose from {list(cl['users'])}")
    return {
        "user": user,
        "preset": cl["users"][user],
        "users": {
            k: {kk: v[kk] for kk in ("label", "alpha", "action")} for k, v in cl["users"].items()
        },
        "curves": cl["curves"],
        "base_rate": cl["base_rate"],
    }


@router.get("/blindspots", tags=["evidence"])
def blindspots(
    date: str | None = Query(None, description="Issue date; omit for the whole test period"),
    var: str = Query("rain"),
    limit: int = Query(50, ge=1, le=500),
    store: DataStore = Depends(store_dep),
) -> dict:
    """Low-spread, high-risk forecasts: cases where the spread says 'trust the forecast' but
    BustGuard rates the bust risk HIGH. CONFIDENTLY-WRONG alerts (analogs agree) come first."""
    df = (
        store.day(date, var)
        if date
        else store.df[(store.df["split"] == "test") & (store.df["variable"] == var)]
    )
    sel = (
        df[df["low_spread"] & (df["risk"] == "High")]
        .sort_values(["cw", "prob"], ascending=[False, False])
        .head(limit)
    )
    items = []
    for _, r in sel.iterrows():
        s = store.forecast_summary(r)
        items.append(
            {
                "region_id": r["region_id"],
                "region": store.region_name(r["region_id"]),
                **{
                    k: s[k]
                    for k in (
                        "init_date",
                        "valid_date",
                        "lead_day",
                        "bust_prob",
                        "risk",
                        "confidently_wrong",
                        "spread",
                        "spread_says",
                        "regime",
                        "likely_driver",
                        "fc",
                        "obs",
                        "bust",
                    )
                },
                "analogs": store.analogs(r, 0),
            }
        )
    verified = sel["bust"].notna()
    return {
        "date": date,
        "n": int(len(sel)),
        "n_confidently_wrong": int(sel["cw"].sum()),
        "verified_busts": int((sel.loc[verified, "bust"] == 1).sum()),
        "verified": int(verified.sum()),
        "items": items,
        "note": "Low spread = lowest third of lagged-ensemble spread for the regime and month (training-year thresholds).",
    }


@router.get("/replay", tags=["replay"])
def replay_list(store: DataStore = Depends(store_dep)) -> list[dict]:
    """Real past events with verified data coverage (docs/replay_events.md); their windows
    were excluded from training and calibration."""
    out = []
    for e in store.events:
        peak = e.get("peak") or {}
        out.append(
            {k: e.get(k) for k in ("id", "title", "window", "split", "region_names")}
            | {"peak": peak, "n_days": len(e.get("days", []))}
        )
    return out


@router.get("/replay/{event_id}", tags=["replay"])
def replay(event_id: str, store: DataStore = Depends(store_dep)) -> dict:
    """Day-by-day: what the spread said vs what BustGuard said as each valid day approached
    (Day 10 -> Day 1), and the lead at which each first raised a continuous warning."""
    for e in store.events:
        if e["id"] == event_id:
            return {
                **e,
                "is_synthetic": bool(store.meta["is_synthetic"]),
                "operating_point": store.meta.get("operating_point"),
            }
    raise HTTPException(404, f"unknown event {event_id}")


@router.get("/saved", response_model=list[SavedAnalysis], tags=["saved"])
def saved_list() -> list[dict]:
    """Saved analyses (traceability of reviewed high-risk forecasts)."""
    return st.list_saved()


@router.post("/saved", response_model=SavedAnalysis, status_code=201, tags=["saved"])
def saved_add(item: SavedAnalysisIn) -> dict:
    return st.add_saved(item.model_dump())


@router.delete("/saved/{item_id}", status_code=204, tags=["saved"])
def saved_delete(item_id: str) -> None:
    if not st.delete_saved(item_id):
        raise HTTPException(404, "not found")


__all__ = ["router", "num"]
