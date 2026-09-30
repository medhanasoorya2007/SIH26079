"""WeatherBench 2 fetcher: India subset of HRES / GraphCast forecasts and ERA5 truth.

Design goals (driven by a metered connection):

* **Exact byte accounting.** Chunks are fetched raw from the public GCS bucket and
  decoded locally, so every transferred byte is counted in a persistent ledger.
* **Hard cap.** Nothing is requested if it would push the running total past
  ``byte_cap_gb`` (configs/data.yaml).
* **Resumable.** Each (source, variable, init, chunk) is saved as one small ``.npz``
  holding only the India box. Re-running skips everything already on disk, so a
  dropped connection never restarts the download.
* **Usable while downloading.** As soon as all chunks of a month are present, a
  ``monthly/<source>/<var>_<YYYY-MM>.nc`` file is (re)written.

WeatherBench 2 zarr chunks span the whole globe (and, for pressure-level variables,
every level), so the India subset limits what is *kept*, not what is *transferred*.
That is why 850 hPa winds are not fetched: see docs/data.md.
"""

from __future__ import annotations

import argparse
import calendar
import json
import threading
import time
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from ml.config import RAW_DIR, load_config

WB2_DIR = RAW_DIR / "wb2"
UNITS_DIR = WB2_DIR / "units"
MONTHLY_DIR = WB2_DIR / "monthly"
META_DIR = WB2_DIR / "_meta"
LEDGER_PATH = WB2_DIR / "_ledger.json"
GB = 1e9


# --------------------------------------------------------------------------- ledger
class ByteLedger:
    """Thread-safe, persisted running total of transferred bytes."""

    def __init__(self, path: Path, cap_bytes: float):
        self.path = path
        self.cap = cap_bytes
        self._lock = threading.Lock()
        self.data = {"total_bytes": 0, "by_source": {}, "requests": 0}
        if path.exists():
            self.data.update(json.loads(path.read_text()))

    @property
    def total(self) -> int:
        return int(self.data["total_bytes"])

    def add(self, source: str, nbytes: int) -> None:
        with self._lock:
            self.data["total_bytes"] += int(nbytes)
            self.data["requests"] += 1
            bs = self.data["by_source"]
            bs[source] = bs.get(source, 0) + int(nbytes)
            self._flush()

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1))
        tmp.replace(self.path)

    def would_exceed(self, extra: float) -> bool:
        return self.total + extra > self.cap


# ------------------------------------------------------------------ zarr v2 reading
class ChunkStore:
    """Minimal zarr-v2 reader over gcsfs that counts every byte it transfers."""

    def __init__(self, fs, bucket: str, path: str, source: str, ledger: ByteLedger):
        self.fs = fs
        self.root = f"{bucket}/{path}"
        self.source = source
        self.ledger = ledger
        self.meta = self._load_meta(path)
        self._coords: dict[str, np.ndarray] = {}

    # -- metadata (cached on disk after the first fetch)
    def _load_meta(self, path: str) -> dict:
        cache = META_DIR / (path.replace("/", "__") + ".json")
        if cache.exists():
            return json.loads(cache.read_text())
        raw = self._cat(f"{self.root}/.zmetadata")
        meta = json.loads(raw)["metadata"]
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(meta))
        return meta

    def _cat(self, key: str, retries: int = 6) -> bytes:
        delay = 2.0
        for attempt in range(retries):
            try:
                payload = self.fs.cat(key)
                self.ledger.add(self.source, len(payload))
                return payload
            except FileNotFoundError:
                raise
            except Exception as exc:  # network hiccup: back off and retry
                if attempt == retries - 1:
                    raise RuntimeError(f"giving up on {key}: {exc}") from exc
                time.sleep(delay)
                delay = min(delay * 2, 60)
        raise AssertionError("unreachable")

    def array_meta(self, var: str) -> tuple[dict, list[str]]:
        return self.meta[f"{var}/.zarray"], self.meta[f"{var}/.zattrs"]["_ARRAY_DIMENSIONS"]

    def chunk_size_hint(self, var: str, key: str) -> int:
        """Size of one stored chunk (metadata request only; no payload transfer)."""
        return int(self.fs.info(f"{self.root}/{var}/{key}")["size"])

    def read_chunk(self, var: str, idx: tuple[int, ...]) -> np.ndarray:
        import numcodecs

        zarray, _ = self.array_meta(var)
        key = ".".join(str(i) for i in idx)
        raw = self._cat(f"{self.root}/{var}/{key}")
        buf = raw
        if zarray.get("compressor"):
            buf = numcodecs.get_codec(zarray["compressor"]).decode(raw)
        for flt in reversed(zarray.get("filters") or []):
            buf = numcodecs.get_codec(flt).decode(buf)
        arr = np.frombuffer(buf, dtype=np.dtype(zarray["dtype"]))
        arr = arr.reshape(zarray["chunks"], order=zarray.get("order", "C"))
        fill = zarray.get("fill_value")
        if fill is not None and arr.dtype.kind == "f":
            fv = np.nan if fill == "NaN" else float(fill)
            if not np.isnan(fv):
                arr = np.where(arr == fv, np.nan, arr)
        return arr

    def coord(self, name: str) -> np.ndarray:
        """Decoded 1-D coordinate (times as datetime64[ns], timedeltas as hours)."""
        if name in self._coords:
            return self._coords[name]
        cache = META_DIR / (self.root.replace("/", "__") + f"__{name}.npy")
        if cache.exists():
            vals = np.load(cache, allow_pickle=False)
        else:
            zarray, _ = self.array_meta(name)
            n = zarray["shape"][0]
            parts = [self.read_chunk(name, (c,)) for c in range(-(-n // zarray["chunks"][0]))]
            raw = np.concatenate(parts)[:n]
            attrs = self.meta.get(f"{name}/.zattrs", {})
            vals = _decode_cf(raw, attrs)
            np.save(cache, vals, allow_pickle=False)
        self._coords[name] = vals
        return vals


def _decode_cf(raw: np.ndarray, attrs: dict) -> np.ndarray:
    units = attrs.get("units", "")
    if " since " in units:
        from xarray.coding.times import decode_cf_datetime

        return np.asarray(
            decode_cf_datetime(raw, units, attrs.get("calendar", "proleptic_gregorian"))
        ).astype("datetime64[ns]")
    if units in {"nanoseconds", "microseconds", "seconds", "minutes", "hours", "days"}:
        factor = {
            "nanoseconds": 1 / 3.6e12,
            "microseconds": 1 / 3.6e9,
            "seconds": 1 / 3600,
            "minutes": 1 / 60,
            "hours": 1,
            "days": 24,
        }[units]
        return (raw.astype("float64") * factor).round(3)
    return raw


# ------------------------------------------------------------------------- planning
@dataclass(frozen=True)
class Unit:
    """One chunk to fetch: forecast (init date + lead chunk) or ERA5 (time chunk)."""

    source: str
    store_path: str
    var: str
    chunk_idx: tuple[int, ...]
    out_path: Path
    month: str  # YYYY-MM used to group monthly files (init month / valid month)
    init: date | None = None


def _season_inits(year: int, months: list[int]) -> list[date]:
    out = []
    for m in months:
        for d in range(1, calendar.monthrange(year, m)[1] + 1):
            out.append(date(year, m, d))
    return out


def _bbox_index(store: ChunkStore, bbox: dict) -> tuple[np.ndarray, np.ndarray]:
    lat = store.coord("latitude")
    lon = store.coord("longitude")
    li = np.where((lat >= bbox["lat"][0]) & (lat <= bbox["lat"][1]))[0]
    lo = np.where((lon >= bbox["lon"][0]) & (lon <= bbox["lon"][1]))[0]
    return li, lo


class Planner:
    """Turns a download phase from configs/data.yaml into a list of chunk Units."""

    def __init__(self, fs, ledger: ByteLedger):
        self.cfg = load_config("data")["weatherbench2"]
        self.fs = fs
        self.ledger = ledger
        self._stores: dict[str, ChunkStore] = {}

    def store(self, source: str, path: str) -> ChunkStore:
        if path not in self._stores:
            self._stores[path] = ChunkStore(self.fs, self.cfg["bucket"], path, source, self.ledger)
        return self._stores[path]

    def forecast_paths(self, year: int) -> dict[str, str]:
        out = {"hres": self.cfg["stores"]["hres"]["path"]}
        gc = self.cfg["stores"]["graphcast"]["path_by_year"]
        if year in gc:
            out["graphcast"] = gc[year]
        return out

    def plan(self, phase: dict) -> list[Unit]:
        units: list[Unit] = []
        hour = self.cfg["init_hour_utc"]
        valid_dates: set[date] = set()
        for year in phase["seasons"]:
            inits = _season_inits(year, self.cfg["season_months"])
            for source, path in self.forecast_paths(year).items():
                st = self.store(source, path)
                times = st.coord("time")
                leads = st.coord("prediction_timedelta")
                for var in self.cfg["forecast_variables"]:
                    zarray, dims = st.array_meta(var)
                    t_ax, l_ax = dims.index("time"), dims.index("prediction_timedelta")
                    lead_chunks = sorted(
                        {
                            int(np.where(np.isclose(leads, 24 * d))[0][0]) // zarray["chunks"][l_ax]
                            for d in phase["lead_days"]
                        }
                    )
                    for init in inits:
                        t64 = np.datetime64(datetime(init.year, init.month, init.day, hour))
                        ti = np.where(times == t64)[0]
                        if ti.size == 0:
                            continue
                        tchunk = int(ti[0]) // zarray["chunks"][t_ax]
                        for lc in lead_chunks:
                            idx = [0] * len(dims)
                            idx[t_ax], idx[l_ax] = tchunk, lc
                            out = (
                                UNITS_DIR
                                / source
                                / var
                                / str(init.year)
                                / f"{init:%Y%m%d}_c{lc}.npz"
                            )
                            units.append(
                                Unit(source, path, var, tuple(idx), out, f"{init:%Y-%m}", init)
                            )
            for init in inits:
                for d in phase["lead_days"]:
                    # rain day covered by lead day d: (init + d-1 days, init + d days]
                    valid_dates.add(init + timedelta(days=d - 1))
        units += self._era5_units(sorted(valid_dates))
        return units

    def _era5_units(self, valid_dates: list[date]) -> list[Unit]:
        path = self.cfg["stores"]["era5"]["path"]
        st = self.store("era5", path)
        times = st.coord("time")
        units = []
        for var in self.cfg["truth_variables"]:
            zarray, dims = st.array_meta(var)
            t_ax = dims.index("time")
            chunks = set()
            for vd in valid_dates:
                # 24 h accumulation ending at 00 UTC of the day after `vd` == rain on day vd
                t64 = np.datetime64(datetime(vd.year, vd.month, vd.day)) + np.timedelta64(1, "D")
                ti = np.where(times == t64)[0]
                if ti.size:
                    chunks.add(int(ti[0]) // zarray["chunks"][t_ax])
            for c in sorted(chunks):
                idx = [0] * len(dims)
                idx[t_ax] = c
                t0 = times[c * zarray["chunks"][t_ax]]
                month = str(t0)[:7]
                out = UNITS_DIR / "era5" / var / month[:4] / f"t{c}.npz"
                units.append(Unit("era5", path, var, tuple(idx), out, month))
        return units


# ------------------------------------------------------------------------- fetching
def _fetch_unit(planner: Planner, unit: Unit, bbox: dict) -> None:
    st = planner.store(unit.source, unit.store_path)
    arr = st.read_chunk(unit.var, unit.chunk_idx)
    zarray, dims = st.array_meta(unit.var)
    li, lo = _bbox_index(st, bbox)
    # move to (time|lead, lat, lon) and cut the India box
    lat_ax, lon_ax = dims.index("latitude"), dims.index("longitude")
    sub = np.take(np.take(arr, li, axis=lat_ax), lo, axis=lon_ax)
    order = [i for i in range(sub.ndim) if i not in (lat_ax, lon_ax)] + [lat_ax, lon_ax]
    sub = np.transpose(sub, order)
    # squeeze the singleton time axis of forecast chunks
    if "prediction_timedelta" in dims:
        t_ax = dims.index("time")
        sub = np.squeeze(sub, axis=order.index(t_ax))  # forecast chunks hold one init
        l_ax = dims.index("prediction_timedelta")
        start = unit.chunk_idx[l_ax] * zarray["chunks"][l_ax]
        leads = st.coord("prediction_timedelta")[start : start + zarray["chunks"][l_ax]]
        sub = sub[: len(leads)]
        meta = {"lead_hours": leads}
    else:
        t_ax = dims.index("time")
        start = unit.chunk_idx[t_ax] * zarray["chunks"][t_ax]
        times = st.coord("time")[start : start + zarray["chunks"][t_ax]]
        sub = sub[: len(times)]
        meta = {"times": times.astype("datetime64[ns]").astype("int64")}
    unit.out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = unit.out_path.with_suffix(".part.npz")
    np.savez(
        tmp,
        data=sub.astype("float32"),
        lat=st.coord("latitude")[li],
        lon=st.coord("longitude")[lo],
        **meta,
    )
    tmp.replace(unit.out_path)


def assemble_month(source: str, var: str, month: str) -> Path | None:
    """Merge the unit files of one month into ``monthly/<source>/<var>_<month>.nc``."""
    import xarray as xr

    folder = UNITS_DIR / source / var / month[:4]
    if source == "era5":
        files = sorted(folder.glob("t*.npz"))
        pieces = []
        for f in files:
            z = np.load(f)
            t = z["times"].astype("datetime64[ns]")
            pieces.append(
                xr.DataArray(
                    z["data"],
                    dims=("time", "lat", "lon"),
                    coords={"time": t, "lat": z["lat"], "lon": z["lon"]},
                )
            )
        if not pieces:
            return None
        da = xr.concat(pieces, "time").sortby("time")
        da = da.sel(time=da.time.dt.strftime("%Y-%m") == month)
        da = da.isel(time=~da.get_index("time").duplicated())
    else:
        files = sorted(folder.glob(f"{month.replace('-', '')}??_c*.npz"))
        by_init: dict[str, list] = defaultdict(list)
        for f in files:
            by_init[f.name[:8]].append(f)
        inits = []
        for key, fl in sorted(by_init.items()):
            parts = []
            for f in fl:
                z = np.load(f)
                parts.append(
                    xr.DataArray(
                        z["data"],
                        dims=("lead_hour", "lat", "lon"),
                        coords={"lead_hour": z["lead_hours"], "lat": z["lat"], "lon": z["lon"]},
                    )
                )
            one = xr.concat(parts, "lead_hour").sortby("lead_hour")
            inits.append(
                one.expand_dims(init_time=[np.datetime64(f"{key[:4]}-{key[4:6]}-{key[6:]}", "ns")])
            )
        if not inits:
            return None
        da = xr.concat(inits, "init_time", join="outer")
    out = MONTHLY_DIR / source / f"{var}_{month}.nc"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part.nc")
    da.rename(var).to_dataset().to_netcdf(tmp)
    tmp.replace(out)
    return out


def run_phase(phase: dict, dry_run: bool = False) -> bool:
    """Fetch one phase. Returns True if every unit is on disk afterwards."""
    import gcsfs

    cfg = load_config("data")
    wcfg, bbox = cfg["weatherbench2"], cfg["bbox"]
    ledger = ByteLedger(LEDGER_PATH, wcfg["byte_cap_gb"] * GB)
    fs = gcsfs.GCSFileSystem(token="anon")
    planner = Planner(fs, ledger)
    units = planner.plan(phase)
    todo = [u for u in units if not u.out_path.exists()]

    # size estimate from one metadata lookup per (source, var): no payload transferred
    est_by_key: dict[tuple[str, str], int] = {}
    for u in todo:
        k = (u.source, u.var)
        if k not in est_by_key:
            est_by_key[k] = planner.store(u.source, u.store_path).chunk_size_hint(
                u.var, ".".join(map(str, u.chunk_idx))
            )
    est_total = sum(est_by_key[(u.source, u.var)] for u in todo)
    print(
        f"[wb2] phase {phase['name']}: {len(units)} chunks, {len(units) - len(todo)} already on disk, "
        f"{len(todo)} to fetch (~{est_total / GB:.2f} GB). "
        f"Transferred so far: {ledger.total / GB:.3f} GB / cap {wcfg['byte_cap_gb']:.1f} GB",
        flush=True,
    )
    if dry_run:
        return False
    if ledger.would_exceed(est_total):
        print(
            f"[wb2] STOP: phase would take the total to ~{(ledger.total + est_total) / GB:.2f} GB, "
            f"above the {wcfg['byte_cap_gb']} GB cap. Nothing fetched.",
            flush=True,
        )
        return False

    # month-ordered so monthly files complete progressively
    todo.sort(key=lambda u: (u.month, u.source != "era5", u.source, u.var, u.out_path.name))
    remaining_by_month: dict[tuple[str, str, str], int] = defaultdict(int)
    for u in todo:
        remaining_by_month[(u.source, u.var, u.month)] += 1

    failures = 0
    done = 0
    started = time.time()
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=wcfg["workers"]) as pool:
        pending: dict = {}
        it = iter(todo)
        stop = False
        while True:
            while not stop and len(pending) < wcfg["workers"] * 2:
                u = next(it, None)
                if u is None:
                    break
                inflight = sum(est_by_key[(p.source, p.var)] for p in pending.values())
                if ledger.would_exceed(inflight + est_by_key[(u.source, u.var)]):
                    print(f"[wb2] STOP: byte cap of {wcfg['byte_cap_gb']} GB reached.", flush=True)
                    stop = True
                    break
                pending[pool.submit(_fetch_unit, planner, u, bbox)] = u
            if not pending:
                break
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for fut in finished:
                u = pending.pop(fut)
                try:
                    fut.result()
                except Exception as exc:  # keep going; the unit will be retried next run
                    failures += 1
                    print(f"[wb2] FAILED {u.out_path.name} ({u.source}/{u.var}): {exc}", flush=True)
                    continue
                with lock:
                    done += 1
                    key = (u.source, u.var, u.month)
                    remaining_by_month[key] -= 1
                    if remaining_by_month[key] == 0:
                        out = assemble_month(*key)
                        print(
                            f"[wb2] month file ready: {out.relative_to(RAW_DIR.parent)}", flush=True
                        )
                    if done % 50 == 0 or done == len(todo):
                        rate = ledger.total / max(time.time() - started, 1)
                        print(
                            f"[wb2] {done}/{len(todo)} chunks | transferred {ledger.total / GB:.3f} GB "
                            f"| cap {wcfg['byte_cap_gb']:.1f} GB | {rate / 1e6:.2f} MB/s",
                            flush=True,
                        )
    complete = all(u.out_path.exists() for u in units)
    print(
        f"[wb2] phase {phase['name']} {'COMPLETE' if complete else 'INCOMPLETE'}: "
        f"{failures} failures, total transferred {ledger.total / GB:.3f} GB",
        flush=True,
    )
    return complete


def rebuild_monthly() -> None:
    """Re-assemble every monthly file from the unit cache (offline)."""
    for src_dir in UNITS_DIR.glob("*"):
        for var_dir in src_dir.glob("*"):
            months = set()
            for f in var_dir.rglob("*.npz"):
                if src_dir.name == "era5":
                    z = np.load(f)
                    months |= {str(t)[:7] for t in z["times"].astype("datetime64[ns]")}
                else:
                    months.add(f"{f.name[:4]}-{f.name[4:6]}")
            for m in sorted(months):
                assemble_month(src_dir.name, var_dir.name, m)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Fetch the WeatherBench 2 India subset (resumable).")
    ap.add_argument("--phase", help="phase name or 1-based index; default: run phases in order")
    ap.add_argument("--dry-run", action="store_true", help="plan and estimate only")
    ap.add_argument(
        "--rebuild-monthly", action="store_true", help="re-assemble monthly files offline"
    )
    args = ap.parse_args(argv)

    if args.rebuild_monthly:
        rebuild_monthly()
        return
    phases = load_config("data")["weatherbench2"]["phases"]
    if args.phase:
        sel = [p for i, p in enumerate(phases, 1) if args.phase in (p["name"], str(i))]
        if not sel:
            raise SystemExit(f"unknown phase {args.phase}")
        run_phase(sel[0], args.dry_run)
        return
    for p in phases:
        ok = run_phase(p, args.dry_run)
        if not ok:
            print(f"[wb2] stopping after phase {p['name']} (not complete). Re-run to resume.")
            break


if __name__ == "__main__":
    main()
