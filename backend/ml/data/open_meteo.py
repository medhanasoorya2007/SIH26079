"""Open-Meteo quick-start track: past forecasts by lead day (1-7) from several models,
plus ERA5-based 'observed' values from the Historical Weather API.

Verified availability (2026-09): the Previous Runs API serves ``*_previous_dayN`` for
N = 1..7 only; with the latest run (N=0) that is lead days 1-8 (no 9-10), ECMWF IFS from ~2024-03, GFS/JMA from 2021; it has no
ensemble-member history. Everything is cached in data/raw/open_meteo as gzipped JSON,
so the build step and the demo run offline.

Free-tier limits are weighted by locations x variables/10 x days/14; the fetcher
throttles itself to ``max_weighted_calls_per_hour`` (configs/data.yaml).
"""

from __future__ import annotations

import gzip
import json
import math
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from ml.config import RAW_DIR, load_config
from ml.regions import load_regions

OM_DIR = RAW_DIR / "open_meteo"
VAR_MAP = {"rain": "precipitation", "tmax": "temperature_2m"}


class _Throttle:
    def __init__(self, per_hour: float):
        self.per_hour = per_hour
        self.window: list[tuple[float, float]] = []

    def wait(self, weight: float) -> None:
        while True:
            now = time.time()
            self.window = [(t, w) for t, w in self.window if now - t < 3600]
            if sum(w for _, w in self.window) + weight <= self.per_hour:
                self.window.append((now, weight))
                return
            time.sleep(30)


def _col(var: str, n: int) -> str:
    """Hourly column for the run issued n days before the valid day (n=0: latest run)."""
    return var if n == 0 else f"{var}_previous_day{n}"


def _weight(n_vars: int, start: str, end: str) -> float:
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    return max(1.0, n_vars / 10) * max(1.0, days / 14)


def _get(url: str, params: dict, cache: Path, throttle: _Throttle, weight: float) -> dict:
    if cache.exists():
        with gzip.open(cache, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    for attempt in range(6):
        throttle.wait(weight)
        r = requests.get(url, params=params, timeout=120)
        if r.status_code == 429:
            print("[open-meteo] rate limited; sleeping 10 min", flush=True)
            time.sleep(600)
            continue
        if r.status_code >= 500:
            time.sleep(2**attempt)
            continue
        data = r.json()
        if data.get("error"):
            raise RuntimeError(f"Open-Meteo error for {params}: {data.get('reason')}")
        cache.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(cache, "wt", encoding="utf-8") as fh:
            json.dump(data, fh)
        return data
    raise RuntimeError(f"Open-Meteo request failed repeatedly: {params}")


def fetch(dry_run: bool = False) -> None:
    """Download previous-run forecasts and ERA5 truth for every region and period."""
    cfg = load_config("data")["open_meteo"]
    regions = load_regions()
    throttle = _Throttle(cfg["max_weighted_calls_per_hour"])
    hourly = [_col(VAR_MAP[v], n) for v in ("rain", "tmax") for n in cfg["previous_days"]]
    total_w = 0.0
    jobs = []
    for start, end in cfg["periods"]:
        start, end = str(start), str(end)
        for rid, reg in regions.iterrows():
            for model in cfg["models"]:
                p = {
                    "latitude": reg.lat,
                    "longitude": reg.lon,
                    "hourly": ",".join(hourly),
                    "start_date": start,
                    "end_date": end,
                    "models": model,
                    "timezone": cfg["timezone"],
                }
                jobs.append(
                    (
                        cfg["previous_runs_url"],
                        p,
                        OM_DIR / "fc" / model / f"{rid}_{start}.json.gz",
                        _weight(len(hourly), start, end),
                    )
                )
            p = {
                "latitude": reg.lat,
                "longitude": reg.lon,
                "daily": "precipitation_sum,temperature_2m_max",
                "start_date": start,
                "end_date": end,
                "timezone": cfg["timezone"],
            }
            jobs.append(
                (
                    cfg["archive_url"],
                    p,
                    OM_DIR / "obs" / f"{rid}_{start}.json.gz",
                    _weight(2, start, end),
                )
            )
    todo = [j for j in jobs if not j[2].exists()]
    total_w = sum(j[3] for j in todo)
    print(
        f"[open-meteo] {len(jobs)} requests, {len(todo)} to fetch, ~{total_w:,.0f} weighted API calls "
        f"(~{math.ceil(total_w / cfg['max_weighted_calls_per_hour'])} h at the configured rate)"
    )
    if dry_run:
        return
    for i, (url, params, cache, w) in enumerate(todo, 1):
        _get(url, params, cache, throttle, w)
        if i % 25 == 0:
            print(f"[open-meteo] {i}/{len(todo)} requests done", flush=True)


def _load(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def build_table() -> pd.DataFrame:
    """Daily IST aggregates -> raw training table (fc = ECMWF, fc_alt = 2nd model)."""
    cfg = load_config("data")["open_meteo"]
    regions = load_regions()
    primary, alt = cfg["models"][0], cfg["models"][1]
    rows = []
    for start, _ in cfg["periods"]:
        start = str(start)
        for rid in regions.index:
            obs_path = OM_DIR / "obs" / f"{rid}_{start}.json.gz"
            if not obs_path.exists():
                continue
            ob = _load(obs_path)["daily"]
            obs = pd.DataFrame(
                {
                    "valid_date": pd.to_datetime(ob["time"]),
                    "rain": ob["precipitation_sum"],
                    "tmax": ob["temperature_2m_max"],
                }
            )
            per_model = {}
            for model in cfg["models"]:
                fp = OM_DIR / "fc" / model / f"{rid}_{start}.json.gz"
                if not fp.exists():
                    continue
                h = pd.DataFrame(_load(fp)["hourly"])
                h["valid_date"] = pd.to_datetime(h["time"]).dt.normalize()
                agg = {}
                for n in cfg["previous_days"]:
                    g = h.groupby("valid_date")
                    agg[("rain", n)] = g[_col("precipitation", n)].sum(min_count=20)
                    agg[("tmax", n)] = g[_col("temperature_2m", n)].max()
                per_model[model] = agg
            if primary not in per_model:
                continue
            for (var, n), s in per_model[primary].items():
                d = n + 1  # run issued n days before the valid day -> lead day n+1
                df = s.rename("fc").reset_index()
                if alt in per_model:
                    df = df.merge(
                        per_model[alt][(var, n)].rename("fc_alt").reset_index(),
                        on="valid_date",
                        how="left",
                    )
                others = [per_model[m][(var, n)].rename(m) for m in per_model]
                spread = pd.concat(others, axis=1).std(axis=1).rename("ctx_mm_spread").reset_index()
                df = df.merge(spread, on="valid_date", how="left").merge(
                    obs[["valid_date", var]].rename(columns={var: "obs"}),
                    on="valid_date",
                    how="left",
                )
                df["init_date"] = df["valid_date"] - pd.to_timedelta(n, unit="D")
                df["lead_day"], df["variable"], df["region_id"] = d, var, rid
                rows.append(df)
    if not rows:
        raise SystemExit("no Open-Meteo data cached: run `make fetch SOURCE=open_meteo` first")
    out = pd.concat(rows, ignore_index=True).dropna(subset=["fc"])
    out = out.merge(regions[["lat", "lon", "zone"]], left_on="region_id", right_index=True)
    out["source"], out["is_synthetic"] = "open_meteo", False
    return out.replace([np.inf, -np.inf], np.nan)
