"""Verification regions = IMD meteorological subdivisions (v2).

``load_regions()`` returns one row per subdivision that has IMD grid cells, with a label
point (lat/lon) from the map geometry. Kept under this name so older call sites work.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd


@lru_cache(maxsize=1)
def load_regions() -> pd.DataFrame:
    """DataFrame indexed by subdivision id: id, name, subdivision, zone, lat, lon."""
    from ml.subdivisions import region_centroids, subdivision_table

    subs = subdivision_table()
    cents = region_centroids()
    df = subs.loc[[s for s in subs.index if s in cents.index]].copy()
    df["subdivision"] = df["name"]
    df = df.join(cents[["lat", "lon"]])
    return df[["id", "name", "subdivision", "zone", "lat", "lon"]]


def nearest_index(values: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Index of the nearest coordinate in ``values`` for every entry of ``targets``."""
    values = np.asarray(values, dtype=float)
    return np.abs(values[None, :] - np.asarray(targets, dtype=float)[:, None]).argmin(axis=1)
