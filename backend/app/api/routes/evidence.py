from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import store_dep
from app.schemas.models import SavedAnalysis, SavedAnalysisIn
from app.services import store as st
from app.services.store import DataStore

router = APIRouter()


@router.get("/metrics", tags=["evidence"])
def metrics(store: DataStore = Depends(store_dep)) -> dict:
    """Held-out verification: BustGuard vs the spread/disagreement baseline (overall, per lead,
    reliability), plus signal descriptions and the frozen bust thresholds."""
    if not store.metrics:
        raise HTTPException(404, "no metrics exported for this source")
    return {
        **store.metrics,
        "signals": store.meta.get("signals", []),
        "label_thresholds": store.meta.get("label_thresholds", {}),
        "top_features": store.meta.get("top_features", {}),
        "operating_point": store.meta.get("operating_point", {}),
    }


@router.get("/replay", tags=["replay"])
def replay_list(store: DataStore = Depends(store_dep)) -> list[dict]:
    """Real bust episodes from the held-out year (auto-detected), newest last."""
    return [
        {
            k: e[k]
            for k in (
                "id",
                "valid_date",
                "title",
                "regime",
                "n_regions",
                "model_warning_days",
                "baseline_warning_days",
                "obs_max",
            )
        }
        for e in store.events
    ]


@router.get("/replay/{event_id}", tags=["replay"])
def replay(event_id: str, store: DataStore = Depends(store_dep)) -> dict:
    """Step through one past bust: bust probability for the affected regions as the event
    approached (Day 10 -> Day 1), model vs baseline, and when each first raised a warning."""
    for e in store.events:
        if e["id"] == event_id:
            names = store.regions["name"].to_dict()
            return {
                **e,
                "region_names": [names.get(r, r) for r in e["regions"]],
                "is_synthetic": bool(store.meta["is_synthetic"]),
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
