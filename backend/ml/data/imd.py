"""IMD 0.25 deg gridded daily rainfall (Pai et al. 2014) = BustGuard's rain truth (v2).

The IMD server (imdpune.gov.in) is slow (~50-100 kB/s) and drops connections, so this
module downloads the yearly binary files itself: streamed, retried, size-checked, and
written where ``imdlib.open_data`` expects them (data/raw/imd/rain/<year>.grd). Bytes
are added to the same transfer ledger as WeatherBench 2 so the byte cap covers both.

IMD's rain day runs 03 UTC -> 03 UTC (08:30 IST). BustGuard forecast rain days run
00 -> 00 UTC; the 3-hour offset is documented in docs/data.md.
"""

from __future__ import annotations

import calendar
import time

import numpy as np
import pandas as pd
import requests

from ml.config import RAW_DIR, load_config
from ml.data.weatherbench2 import GB, WB2_DIR, ByteLedger

IMD_DIR = RAW_DIR / "imd"
URL = "https://imdpune.gov.in/cmpg/Griddata/rainfall.php"
NLAT, NLON = 129, 135  # 6.5N-38.5N, 66.5E-100E at 0.25 deg
LATS = 6.5 + 0.25 * np.arange(NLAT)
LONS = 66.5 + 0.25 * np.arange(NLON)


def expected_bytes(year: int) -> int:
    return NLAT * NLON * (366 if calendar.isleap(year) else 365) * 4


def year_path(year: int):
    return IMD_DIR / "rain" / f"{year}.grd"


def fetch_year(year: int, ledger: ByteLedger, retries: int = 8) -> None:
    out = year_path(year)
    if out.exists() and out.stat().st_size == expected_bytes(year):
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_suffix(".part")
    for attempt in range(1, retries + 1):
        got = 0
        try:
            with requests.post(URL, data={"rain": str(year)}, stream=True, timeout=(60, 300)) as r:
                r.raise_for_status()
                with part.open("wb") as fh:
                    for block in r.iter_content(1 << 16):
                        fh.write(block)
                        got += len(block)
            ledger.add("imd", got)
            if got == expected_bytes(year):
                part.replace(out)
                print(
                    f"[imd] {year}: {got / 1e6:.1f} MB ok | ledger {ledger.total / GB:.3f} GB",
                    flush=True,
                )
                return
            print(
                f"[imd] {year}: truncated ({got} of {expected_bytes(year)} bytes), retry {attempt}",
                flush=True,
            )
        except requests.RequestException as exc:
            ledger.add("imd", got)
            print(
                f"[imd] {year}: {type(exc).__name__} after {got / 1e6:.1f} MB, retry {attempt}",
                flush=True,
            )
        time.sleep(min(30 * attempt, 180))
    raise RuntimeError(f"IMD {year} failed after {retries} attempts (server {URL})")


def fetch(years: list[int] | None = None) -> None:
    cfg = load_config("data")
    years = years or cfg["imd"]["years"]
    ledger = ByteLedger(WB2_DIR / "_ledger_imd.json", cfg["weatherbench2"]["byte_cap_gb"] * GB)
    need = sum(
        expected_bytes(y)
        for y in years
        if not (year_path(y).exists() and year_path(y).stat().st_size == expected_bytes(y))
    )
    if ledger.would_exceed(need):
        raise SystemExit(f"[imd] STOP: {need / GB:.2f} GB would exceed the byte cap")
    for y in years:
        fetch_year(y, ledger)


def load_year(year: int) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """(dates, rain[day, lat, lon]) with NaN outside India / missing (-999)."""
    raw = np.fromfile(year_path(year), dtype="<f4")
    days = raw.size // (NLAT * NLON)
    arr = raw.reshape(days, NLAT, NLON)
    arr = np.where(arr <= -998, np.nan, arr).astype("float32")
    dates = pd.date_range(f"{year}-01-01", periods=days, freq="D")
    return dates, arr


def land_mask(year: int) -> np.ndarray:
    """Cells with valid IMD data (India land mask)."""
    _, arr = load_year(year)
    return np.isfinite(arr).any(axis=0)
