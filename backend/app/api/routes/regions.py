from __future__ import annotations

from fastapi import APIRouter

from app.schemas.models import Region
from ml.regions import load_regions

router = APIRouter(tags=["regions"])


@router.get("/regions", response_model=list[Region])
def regions() -> list[Region]:
    """Verification regions (representative points of the IMD meteorological subdivisions)."""
    df = load_regions()
    return [
        Region(**r)
        for r in df[["id", "name", "subdivision", "zone", "lat", "lon"]].to_dict("records")
    ]
