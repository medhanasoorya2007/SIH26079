from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import store_dep
from app.services.store import DataStore, available_sources

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "sources": list(available_sources())}


@router.get("/sources")
def sources() -> dict:
    return {name: str(path) for name, path in available_sources().items()}


@router.get("/meta")
def meta(store: DataStore = Depends(store_dep)) -> dict:
    """Dataset/model metadata: source, synthetic flag, dates, lead days, signals, thresholds."""
    return {**store.meta, "latest_date": store.latest_date()}
