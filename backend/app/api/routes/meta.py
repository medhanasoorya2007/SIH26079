from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import store_dep
from app.services.store import DataStore, available_sources
from ml.subdivisions import GEOJSON_PATH

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "sources": list(available_sources())}


@router.get("/sources")
def sources() -> dict:
    return {name: str(path) for name, path in available_sources().items()}


@router.get("/meta")
def meta(store: DataStore = Depends(store_dep)) -> dict:
    """Dataset/model metadata: source, synthetic flag, dates, lead days, families, thresholds,
    headline test metrics."""
    return {**store.meta, "latest_date": store.latest_date()}


@router.get("/dates")
def dates(store: DataStore = Depends(store_dep)) -> dict:
    """Issue dates with out-of-sample forecasts, grouped by split."""
    d = store.df.groupby("init_str")["split"].first()
    return {"latest": store.latest_date(), "dates": [{"date": k, "split": v} for k, v in d.items()]}


@router.get("/geo/subdivisions")
def geo() -> dict:
    """Subdivision polygons derived from the IMD gridded-rainfall land mask (GeoJSON)."""
    if not GEOJSON_PATH.exists():
        raise HTTPException(404, "geometry not built: run the dataset step")
    return json.loads(GEOJSON_PATH.read_text())
