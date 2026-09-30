"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import HTTPException, Query

from app.services.store import DataStore, available_sources, get_store, num  # noqa: F401


def store_dep(
    source: str | None = Query(
        None, description="wb2 | open_meteo | synthetic (default: best available)"
    ),
) -> DataStore:
    try:
        return get_store(source)
    except KeyError as exc:
        raise HTTPException(
            404, f"source {source!r} not available; have {list(available_sources())}"
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
