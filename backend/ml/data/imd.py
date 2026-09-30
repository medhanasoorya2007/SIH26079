"""IMD 0.25 deg gridded daily rainfall (via imdlib) as independent ground truth.

IMD's day runs 03 UTC to 03 UTC; ERA5/forecast 'rain days' in BustGuard run 00 UTC to 00 UTC.
The 3-hour offset is small for daily totals and documented in docs/data.md. Yearly files
(~25 MB each) are cached in data/raw/imd; nothing is downloaded at serve time.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.config import RAW_DIR, load_config
from ml.regions import load_regions, nearest_index

IMD_DIR = RAW_DIR / "imd"


def fetch(years: list[int] | None = None) -> None:
    import imdlib as imd

    cfg = load_config("data")["imd"]
    years = years or cfg["years"]
    IMD_DIR.mkdir(parents=True, exist_ok=True)
    for y in years:
        imd.get_data(cfg["variable"], y, y, fn_format="yearwise", file_dir=str(IMD_DIR))


def point_truth(years: list[int] | None = None) -> pd.DataFrame:
    """Daily IMD rainfall at each region point (nearest 0.25 deg cell)."""
    import imdlib as imd

    cfg = load_config("data")["imd"]
    years = years or cfg["years"]
    regions = load_regions()
    frames = []
    for y in years:
        ds = imd.open_data(
            cfg["variable"], y, y, fn_format="yearwise", file_dir=str(IMD_DIR)
        ).get_xarray()
        da = ds[cfg["variable"]].where(ds[cfg["variable"]] > -998)
        li = nearest_index(da["lat"].values, regions["lat"].values)
        lo = nearest_index(da["lon"].values, regions["lon"].values)
        vals = da.values[:, li, lo]  # (time, region)
        frames.append(
            pd.DataFrame(
                {
                    "valid_date": np.repeat(pd.to_datetime(da["time"].values), len(regions)),
                    "region_id": np.tile(regions.index.values, len(da["time"])),
                    "obs_imd": vals.reshape(-1),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)
