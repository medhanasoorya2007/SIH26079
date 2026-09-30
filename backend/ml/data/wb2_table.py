"""Build the raw training table from the WeatherBench 2 monthly files (real data).

Conventions
-----------
* Lead day d of a 00 UTC run covers the 24 h window (init + d-1 days, init + d days].
  Its rain is ``total_precipitation_24hr`` at lead 24*d h; truth is ERA5
  ``total_precipitation_24hr`` stamped at init + d days 00 UTC (same window).
* ``valid_date`` = init + d-1 days (the rain day).
* Context fields come from the HRES forecast itself (what a forecaster sees at issue time):
  valid-day mean MSLP, geostrophic vorticity from the MSLP Laplacian, box minima/means.
* Only lead days present in the downloaded chunks are emitted (e.g. 1-7 and 10).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from ml.data.weatherbench2 import MONTHLY_DIR
from ml.regions import load_regions, nearest_index

TP, MSLP = "total_precipitation_24hr", "mean_sea_level_pressure"
OMEGA, RHO = 7.292e-5, 1.2

BOXES = {  # (lat_min, lat_max, lon_min, lon_max)
    "bob": (12.0, 24.0, 82.0, 95.0),  # Bay of Bengal + east coast: depressions form/track here
    "arb": (10.0, 24.0, 66.0, 74.0),  # Arabian Sea (east part inside the India box)
    "nw": (26.0, 34.0, 68.0, 78.0),  # NW India heat low / western disturbances
    "core": (18.0, 28.0, 69.0, 88.0),  # monsoon core zone (active / break)
}


def _open(source: str, var: str, years: list[int] | None = None) -> xr.DataArray | None:
    files = sorted((MONTHLY_DIR / source).glob(f"{var}_*.nc"))
    if years:
        files = [f for f in files if int(f.stem.rsplit("_", 1)[1][:4]) in years]
    if not files:
        return None
    dim = "time" if source == "era5" else "init_time"
    parts = []
    for f in files:  # close each file immediately: the downloader may replace it on Windows
        with xr.open_dataset(f) as ds:
            parts.append(ds[var].load())
    da = xr.concat(parts, dim=dim, join="outer").sortby(dim)
    return da.isel({dim: ~da.get_index(dim).duplicated()})


def _box(da: xr.DataArray, name: str) -> xr.DataArray:
    la0, la1, lo0, lo1 = BOXES[name]
    return da.sel(lat=slice(la0, la1), lon=slice(lo0, lo1))


def geostrophic_vorticity(mslp_hpa: xr.DataArray) -> xr.DataArray:
    """zeta_g = lap(p) / (rho f) in 1e-5 s^-1 (NaN within 8 deg of the equator)."""
    p = mslp_hpa * 100.0
    lat = np.deg2rad(p["lat"])
    dy = 111_195.0 * float(np.abs(np.diff(p["lat"].values)).mean())
    dx = dy * np.cos(lat)
    d2y = (p.shift(lat=-1) - 2 * p + p.shift(lat=1)) / dy**2
    d2x = (p.shift(lon=-1) - 2 * p + p.shift(lon=1)) / dx**2
    f = 2 * OMEGA * np.sin(lat)
    zeta = (d2x + d2y) / (RHO * f) * 1e5
    return zeta.where(np.abs(p["lat"]) >= 8.0)


def _window_mean(da: xr.DataArray, d: int) -> xr.DataArray:
    """Mean over the 6-hourly leads inside day d's window that were downloaded."""
    hours = da["lead_hour"].values
    sel = hours[(hours > 24 * (d - 1)) & (hours <= 24 * d)]
    return da.sel(lead_hour=sel).mean("lead_hour") if len(sel) else da.isel(lead_hour=0) * np.nan


def available_lead_days(tp: xr.DataArray) -> list[int]:
    hours = set(tp["lead_hour"].values.tolist())
    days = [d for d in range(1, 11) if float(24 * d) in hours]
    return [d for d in days if bool(tp.sel(lead_hour=float(24 * d)).notnull().any())]


def build(years: list[int] | None = None) -> pd.DataFrame:
    regions = load_regions()
    hres_tp, hres_p = _open("hres", TP, years), _open("hres", MSLP, years)
    gc_tp = _open("graphcast", TP, years)
    era = _open("era5", TP, years)
    if hres_tp is None or era is None:
        raise SystemExit("no WeatherBench 2 monthly files: run `make fetch` first")

    hres_tp = hres_tp * 1000.0  # m -> mm
    era = (era * 1000.0).clip(min=0.0)
    hres_p = hres_p / 100.0 if hres_p is not None else None  # Pa -> hPa
    lat, lon = hres_tp["lat"].values, hres_tp["lon"].values
    li = nearest_index(lat, regions["lat"].values)
    lo = nearest_index(lon, regions["lon"].values)
    inits = pd.DatetimeIndex(hres_tp["init_time"].values)
    n_r = len(regions)
    frames = []
    for d in available_lead_days(hres_tp):
        fc = hres_tp.sel(lead_hour=float(24 * d)).transpose("init_time", "lat", "lon")
        grid = fc.values  # (init, lat, lon)
        # 3x3 neighbourhood statistics around each region's cell
        pad = np.pad(grid, ((0, 0), (1, 1), (1, 1)), mode="edge")
        neigh = np.stack([pad[:, li + a, lo + b] for a in (0, 1, 2) for b in (0, 1, 2)], axis=-1)
        rec = {
            "fc": grid[:, li, lo],
            "ctx_fc_neigh_mean": neigh.mean(-1),
            "ctx_fc_neigh_std": neigh.std(-1),
            "ctx_fc_neigh_max": neigh.max(-1),
            "ctx_core_fc": np.repeat(_box(fc, "core").mean(("lat", "lon")).values[:, None], n_r, 1),
        }
        if gc_tp is not None and float(24 * d) in gc_tp["lead_hour"].values:
            g = (gc_tp.sel(lead_hour=float(24 * d)) * 1000.0).reindex(init_time=fc["init_time"])
            rec["fc_alt"] = g.transpose("init_time", "lat", "lon").values[:, li, lo]
        if hres_p is not None:
            pm = _window_mean(hres_p.reindex(init_time=fc["init_time"]), d).transpose(
                "init_time", "lat", "lon"
            )
            vort = geostrophic_vorticity(pm).transpose("init_time", "lat", "lon")
            rec["ctx_mslp"] = pm.values[:, li, lo]
            rec["ctx_geo_vort"] = vort.values[:, li, lo]
            for name, col, how in [
                ("bob", "ctx_bob_min_mslp", "min"),
                ("arb", "ctx_arb_min_mslp", "min"),
                ("nw", "ctx_nw_mslp", "mean"),
            ]:
                v = getattr(_box(pm, name), how)(("lat", "lon")).values
                rec[col] = np.repeat(v[:, None], n_r, 1)
        # truth: ERA5 24 h total ending at init + d days 00 UTC
        t_end = inits + pd.Timedelta(days=d)
        ob = era.reindex(time=t_end.values).transpose("time", "lat", "lon").values
        rec["obs"] = ob[:, li, lo]
        df = pd.DataFrame({k: np.asarray(v).reshape(-1) for k, v in rec.items()})
        df["init_date"] = np.repeat(inits.normalize(), n_r)
        df["region_id"] = np.tile(regions.index.values, len(inits))
        df["lead_day"] = d
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["variable"] = "rain"
    out["valid_date"] = out["init_date"] + pd.to_timedelta(out["lead_day"] - 1, unit="D")
    out = out.merge(regions[["lat", "lon", "zone"]], left_on="region_id", right_index=True)
    out["source"], out["is_synthetic"] = "wb2", False
    if "fc_alt" not in out:
        out["fc_alt"] = np.nan
    return out.dropna(subset=["fc"]).reset_index(drop=True)
