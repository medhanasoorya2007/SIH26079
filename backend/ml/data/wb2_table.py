"""Build the raw training table from WeatherBench 2 forecasts + IMD rain truth (v2, real data).

One row = one HRES 00 UTC run x IMD subdivision x lead day (rain).

Conventions
-----------
* Lead day d of a 00 UTC run covers (init + d-1 days, init + d days]; its rain is HRES
  ``total_precipitation_24hr`` at lead 24*d h. ``valid_date`` = init + d-1 days.
* Truth = IMD 0.25 deg gridded rainfall, subdivision area-mean (cos-lat weighted). The IMD
  day is aligned with ``imd.day_offset`` (configs/data.yaml), chosen empirically by
  ``pipelines.check_alignment`` (see docs/data.md). ERA5 is never used as rain truth.
* Forecast fields are mapped to subdivisions by sending every IMD cell to its nearest
  1.5 deg model cell (``ml.subdivisions.grid_weights``).
* Context (what a forecaster has at issue time): HRES MSLP (valid-day mean), geostrophic
  vorticity and wind from the MSLP field, rain/MSLP in an upstream box, and ERA5 analysis
  total column water vapour at the initialisation time.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from ml.config import load_config
from ml.data.weatherbench2 import MONTHLY_DIR
from ml.subdivisions import (
    grid_weights,
    imd_area_means,
    load_partition,
    region_centroids,
    subdivision_table,
)

TP, MSLP, TCWV = "total_precipitation_24hr", "mean_sea_level_pressure", "total_column_water_vapour"
OMEGA, RHO = 7.292e-5, 1.2
BOXES = {  # (lat_min, lat_max, lon_min, lon_max)
    "bob": (12.0, 24.0, 82.0, 95.0),  # Bay of Bengal: monsoon lows/depressions form and track
    "arb": (10.0, 24.0, 66.0, 74.0),  # eastern Arabian Sea: offshore trough / vortices
    "nw": (26.0, 34.0, 68.0, 78.0),  # NW India heat low / western disturbances
    "core": (18.0, 28.0, 69.0, 88.0),  # monsoon core zone (active / break)
}
# upstream box relative to the subdivision centre: monsoon systems travel west-north-west,
# so "upstream" is to the east-south-east (deg)
UPSTREAM = {"dlat": (-3.0, 0.5), "dlon": (2.0, 6.5)}


def _open(source: str, var: str, years: list[int] | None = None) -> xr.DataArray | None:
    files = sorted((MONTHLY_DIR / source).glob(f"{var}_*.nc"))
    if years:
        files = [f for f in files if int(f.stem.rsplit("_", 1)[1][:4]) in years]
    if not files:
        return None
    dim = "time" if source == "era5" else "init_time"
    parts = []
    for f in files:  # close each file immediately (the downloader may replace it)
        with xr.open_dataset(f) as ds:
            parts.append(ds[var].load())
    da = xr.concat(parts, dim=dim, join="outer").sortby(dim)
    return da.isel({dim: ~da.get_index(dim).duplicated()})


def _box_weights(lat: np.ndarray, lon: np.ndarray, boxes: list[tuple]) -> np.ndarray:
    """Row-normalised cos-lat weights (n_boxes, n_lat*n_lon) for lat/lon boxes."""
    glat, glon = np.meshgrid(lat, lon, indexing="ij")
    W = np.zeros((len(boxes), glat.size))
    for k, (a, b, c, d) in enumerate(boxes):
        m = (glat >= a) & (glat <= b) & (glon >= c) & (glon <= d)
        W[k] = (m * np.cos(np.deg2rad(glat))).ravel()
    s = W.sum(1, keepdims=True)
    return np.divide(W, s, out=np.zeros_like(W), where=s > 0)


def _geostrophic(p_hpa: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(vorticity 1e-5 s^-1, u_g m/s, v_g m/s) from MSLP[..., lat, lon] on a regular grid."""
    p = p_hpa * 100.0
    dy = 111_195.0 * float(np.abs(np.diff(lat)).mean())
    coslat = np.cos(np.deg2rad(lat))[:, None]
    dx = dy * coslat
    f = (2 * OMEGA * np.sin(np.deg2rad(lat)))[:, None]
    f = np.where(np.abs(lat)[:, None] >= 8.0, f, np.nan)
    dpdy = np.gradient(p, axis=-2) / dy
    dpdx = np.gradient(p, axis=-1) / dx
    lap = np.gradient(dpdy, axis=-2) / dy + np.gradient(dpdx, axis=-1) / dx
    return lap / (RHO * f) * 1e5, -dpdy / (RHO * f), dpdx / (RHO * f)


def _window_mean(da: xr.DataArray, d: int) -> xr.DataArray | None:
    hours = da["lead_hour"].values
    sel = hours[(hours > 24 * (d - 1)) & (hours <= 24 * d)]
    if not len(sel):
        return None
    out = da.sel(lead_hour=sel).mean("lead_hour")
    return out if bool(out.notnull().any()) else None


def available_lead_days(tp: xr.DataArray) -> list[int]:
    hours = set(tp["lead_hour"].values.tolist())
    return [
        d
        for d in range(1, 11)
        if float(24 * d) in hours and bool(tp.sel(lead_hour=float(24 * d)).notnull().any())
    ]


def imd_truth(years: list[int], part: dict) -> pd.DataFrame:
    """IMD area-mean rain per subdivision, indexed by IMD date (columns = subdivision ids)."""
    from ml.data import imd

    frames = []
    for y in years:
        if not imd.year_path(y).exists():
            continue
        dates, rain = imd.load_year(y)
        frames.append(
            pd.DataFrame(
                imd_area_means(rain, part["assign"], part["lat"]),
                index=dates,
                columns=subdivision_table().index,
            )
        )
    if not frames:
        raise SystemExit("no IMD rainfall files: run `make fetch SOURCE=imd`")
    return pd.concat(frames).sort_index()


def build(years: list[int] | None = None) -> pd.DataFrame:
    cfg = load_config("data")
    years = years or sorted({y for p in cfg["weatherbench2"]["phases"] for y in p["seasons"]})
    offset = int(cfg["imd"].get("day_offset", 0))
    part = load_partition()
    subs = subdivision_table()
    cents = region_centroids()
    sub_ids = [s for s in subs.index if s in cents.index]
    k_idx = [list(subs.index).index(s) for s in sub_ids]

    tp = _open("hres", TP, years)
    if tp is None:
        raise SystemExit("no HRES monthly files: run `make fetch`")
    tp = tp * 1000.0
    mslp = _open("hres", MSLP, years)
    mslp = mslp / 100.0 if mslp is not None else None
    tcwv = _open("era5", TCWV, years)
    lat, lon = tp["lat"].values, tp["lon"].values
    W = grid_weights(part, lat, lon)[k_idx]  # (n_sub, n_cell)
    Wb = _box_weights(lat, lon, list(BOXES.values()))  # (n_box, n_cell)
    up_boxes = [
        (
            c.lat + UPSTREAM["dlat"][0],
            c.lat + UPSTREAM["dlat"][1],
            c.lon + UPSTREAM["dlon"][0],
            c.lon + UPSTREAM["dlon"][1],
        )
        for _, c in cents.loc[sub_ids].iterrows()
    ]
    Wu = _box_weights(lat, lon, up_boxes)  # (n_sub, n_cell)
    in_sub = W > 0

    inits = pd.DatetimeIndex(tp["init_time"].values).normalize()
    n_i, n_s = len(inits), len(sub_ids)
    truth = imd_truth(years, part)[sub_ids]
    frames = []
    for d in available_lead_days(tp):
        x = (
            tp.sel(lead_hour=float(24 * d))
            .transpose("init_time", "lat", "lon")
            .values.reshape(n_i, -1)
        )
        x = np.where(np.isfinite(x), x, np.nan)
        fc = x @ W.T
        rec: dict[str, np.ndarray] = {"fc": fc}
        rec["ctx_fc_sub_std"] = np.sqrt(np.clip((x**2) @ W.T - fc**2, 0, None))
        rec["ctx_fc_sub_max"] = np.stack(
            [np.nanmax(np.where(in_sub[k], x, -np.inf), axis=1) for k in range(n_s)], 1
        )
        rec["ctx_up_fc"] = x @ Wu.T
        box = x @ Wb.T
        rec["ctx_core_fc"] = np.repeat(box[:, [3]], n_s, 1)
        if mslp is not None:
            pm = _window_mean(mslp.reindex(init_time=tp["init_time"]), d)
            if pm is not None:
                p = pm.transpose("init_time", "lat", "lon").values
                vort, ug, vg = _geostrophic(p, lat)
                pf = p.reshape(n_i, -1)
                rec["ctx_mslp"] = pf @ W.T
                rec["ctx_geo_vort"] = np.nan_to_num(vort.reshape(n_i, -1)) @ W.T
                rec["ctx_geo_u"] = np.nan_to_num(ug.reshape(n_i, -1)) @ W.T
                rec["ctx_geo_v"] = np.nan_to_num(vg.reshape(n_i, -1)) @ W.T
                rec["ctx_up_mslp"] = pf @ Wu.T
                la, lo = np.meshgrid(lat, lon, indexing="ij")
                for name, (a, b, c, e) in BOXES.items():
                    m = ((la >= a) & (la <= b) & (lo >= c) & (lo <= e)).ravel()
                    if name in ("bob", "arb"):
                        rec[f"ctx_{name}_min_mslp"] = np.repeat(
                            np.nanmin(pf[:, m], 1)[:, None], n_s, 1
                        )
                    elif name == "nw":
                        rec["ctx_nw_mslp"] = np.repeat(np.nanmean(pf[:, m], 1)[:, None], n_s, 1)
        if tcwv is not None:
            tw = (
                tcwv.reindex(time=tp["init_time"].values)
                .transpose("time", "lat", "lon")
                .values.reshape(n_i, -1)
            )
            rec["ctx_tcwv"] = tw @ W.T
            rec["ctx_up_tcwv"] = tw @ Wu.T
        valid = inits + pd.Timedelta(days=d - 1)
        rec["obs"] = truth.reindex(valid + pd.Timedelta(days=offset)).to_numpy()
        df = pd.DataFrame({k: np.asarray(v, dtype="float32").reshape(-1) for k, v in rec.items()})
        df["init_date"] = np.repeat(inits, n_s)
        df["region_id"] = np.tile(sub_ids, n_i)
        df["lead_day"] = d
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["variable"] = "rain"
    out["valid_date"] = out["init_date"] + pd.to_timedelta(out["lead_day"] - 1, unit="D")
    meta = cents.loc[sub_ids, ["lat", "lon"]].join(subs[["zone"]])
    out = out.merge(meta, left_on="region_id", right_index=True)
    out["source"], out["is_synthetic"] = "wb2", False
    out["fc_alt"] = np.nan  # GraphCast disagreement is out of v2 scope
    return out.dropna(subset=["fc"]).reset_index(drop=True)
