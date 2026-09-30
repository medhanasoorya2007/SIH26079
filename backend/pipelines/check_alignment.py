"""Empirical check of the IMD date convention against HRES Day-1 rain.

The HRES Day-1 window is 00-24 UTC of the rain day. IMD daily grids end at 03 UTC (08:30 IST);
whether IMD's date labels the start or the end of its window decides the offset. We pick
the offset that maximises the correlation between HRES Day-1 and IMD subdivision rain.

    uv run python -m pipelines.check_alignment
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.data.wb2_table import TP, _open, imd_truth
from ml.subdivisions import grid_weights, load_partition, region_centroids, subdivision_table


def main() -> None:
    from ml.data import imd

    part = load_partition()
    years = [y for y in range(2016, 2026) if imd.year_path(y).exists()]
    tp = _open("hres", TP, years)
    if tp is None:
        raise SystemExit("need HRES monthly files overlapping IMD years")
    sub_ids = [s for s in subdivision_table().index if s in region_centroids().index]
    k_idx = [list(subdivision_table().index).index(s) for s in sub_ids]
    W = grid_weights(part, tp["lat"].values, tp["lon"].values)[k_idx]
    x = (tp.sel(lead_hour=24.0) * 1000).transpose("init_time", "lat", "lon").values
    fc = pd.DataFrame(
        x.reshape(len(x), -1) @ W.T,
        index=pd.DatetimeIndex(tp["init_time"].values).normalize(),
        columns=sub_ids,
    )
    truth = imd_truth(years, part)[sub_ids]
    print(f"HRES Day-1 vs IMD, {len(fc)} runs, years {years}")
    best = None
    for off in (-1, 0, 1):
        ob = truth.reindex(fc.index + pd.Timedelta(days=off))
        a, b = fc.to_numpy().ravel(), ob.to_numpy().ravel()
        ok = np.isfinite(a) & np.isfinite(b)
        r = np.corrcoef(a[ok], b[ok])[0, 1]
        print(f"  IMD date = rain day {off:+d}: r = {r:.3f} (n={ok.sum():,})")
        best = max(best or (r, off), (r, off))
    print(f"best offset: {best[1]:+d}  -> set imd.day_offset in configs/data.yaml")


if __name__ == "__main__":
    main()
