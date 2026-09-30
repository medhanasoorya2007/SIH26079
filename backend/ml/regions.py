"""Verification regions (IMD subdivision representative points)."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from ml.config import load_config


@lru_cache(maxsize=1)
def load_regions() -> pd.DataFrame:
    """Return regions as a DataFrame indexed by ``id``."""
    df = pd.DataFrame(load_config("regions")["regions"])
    if df["id"].duplicated().any():
        raise ValueError(f"duplicate region ids: {df.loc[df['id'].duplicated(), 'id'].tolist()}")
    return df.set_index("id", drop=False)


def nearest_index(values: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Index of the nearest coordinate in ``values`` for every entry of ``targets``."""
    values = np.asarray(values, dtype=float)
    return np.abs(values[None, :] - np.asarray(targets, dtype=float)[:, None]).argmin(axis=1)
