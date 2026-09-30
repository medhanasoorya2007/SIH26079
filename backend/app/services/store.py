"""In-memory store over the exported artifacts (fully offline at serve time).

Source resolution (first that exists wins, unless BUSTGUARD_SOURCE or ?source= is given):
    artifacts/wb2 -> sample/wb2 -> artifacts/open_meteo -> sample/open_meteo
    -> artifacts/SYNTHETIC -> sample/SYNTHETIC
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from ml.config import ARTIFACTS_DIR, SAMPLE_DIR
from ml.regions import load_regions

ORDER = [("wb2", "wb2"), ("open_meteo", "open_meteo"), ("synthetic", "SYNTHETIC")]
FILES = ("serving.parquet", "meta.json")


def _candidates(tagname: str) -> list[Path]:
    return [ARTIFACTS_DIR / tagname, SAMPLE_DIR / tagname]


def available_sources() -> dict[str, Path]:
    out = {}
    for name, tagname in ORDER:
        for d in _candidates(tagname):
            if all((d / f).exists() for f in FILES):
                out[name] = d
                break
    return out


def default_source() -> str:
    env = os.environ.get("BUSTGUARD_SOURCE")
    avail = available_sources()
    if env:
        if env not in avail:
            raise RuntimeError(f"BUSTGUARD_SOURCE={env} has no exported artifacts")
        return env
    if not avail:
        raise RuntimeError("no exported artifacts found: run `make synthetic` or `make pipeline`")
    return next(iter(avail))


class DataStore:
    def __init__(self, source: str, folder: Path):
        self.source = source
        self.folder = folder
        self.meta = json.loads((folder / "meta.json").read_text())
        self.metrics = (
            json.loads((folder / "metrics.json").read_text())
            if (folder / "metrics.json").exists()
            else {}
        )
        ev = folder / "replay_events.json"
        self.events = json.loads(ev.read_text()) if ev.exists() else []
        df = pd.read_parquet(folder / "serving.parquet")
        df["init_date"] = pd.to_datetime(df["init_date"])
        df["valid_date"] = pd.to_datetime(df["valid_date"])
        df["init_str"] = df["init_date"].dt.strftime("%Y-%m-%d")
        self.df = df.reset_index(drop=True)
        an = folder / "serving_analogs.npz"
        self.analog_ids = np.load(an)["ids"] if an.exists() else None
        self.analog_dist = np.load(an)["dist"] if an.exists() else None
        self._by_slice = self.df.groupby(["init_str", "lead_day", "variable"]).indices
        self._by_region = self.df.groupby(["init_str", "region_id", "variable"]).indices
        self.regions = load_regions()

    # ------------------------------------------------------------------ helpers
    def latest_date(self) -> str:
        dates = self.meta.get("test_init_dates") or self.meta["init_dates"]
        return dates[-1]

    def slice(self, date: str, lead: int, variable: str) -> pd.DataFrame:
        idx = self._by_slice.get((date, lead, variable))
        return self.df.iloc[idx] if idx is not None else self.df.iloc[:0]

    def region_rows(self, date: str, region_id: str, variable: str) -> pd.DataFrame:
        idx = self._by_region.get((date, region_id, variable))
        return self.df.iloc[idx].sort_values("lead_day") if idx is not None else self.df.iloc[:0]

    def analogs(self, pos: int, k: int = 5) -> list[dict]:
        if self.analog_ids is None:
            return []
        out = []
        for j, d in zip(self.analog_ids[pos][:k], self.analog_dist[pos][:k], strict=False):
            if j < 0 or j >= len(self.df):
                continue
            r = self.df.iloc[int(j)]
            out.append(
                {
                    "init_date": r["init_str"],
                    "valid_date": r["valid_date"].strftime("%Y-%m-%d"),
                    "region_id": r["region_id"],
                    "region_name": str(self.regions.loc[r["region_id"], "name"])
                    if r["region_id"] in self.regions.index
                    else r["region_id"],
                    "lead_day": int(r["lead_day"]),
                    "fc": _num(r["fc"]),
                    "obs": _num(r["obs"]),
                    "abs_error": _num(r["abs_error"]),
                    "bust": _num(r["bust"]),
                    "regime": r.get("regime"),
                    "distance": _num(d),
                }
            )
        return out


def _num(x) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(f) else round(f, 4)


_lock = threading.Lock()


@lru_cache(maxsize=4)
def _load(source: str, folder: str) -> DataStore:
    return DataStore(source, Path(folder))


def get_store(source: str | None = None) -> DataStore:
    with _lock:
        src = source or default_source()
        avail = available_sources()
        if src not in avail:
            raise KeyError(src)
        return _load(src, str(avail[src]))


# ---------------------------------------------------------------- saved analyses
def _saved_path() -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACTS_DIR / "saved_analyses.json"


def list_saved() -> list[dict]:
    p = _saved_path()
    return json.loads(p.read_text()) if p.exists() else []


def add_saved(item: dict) -> dict:
    with _lock:
        items = list_saved()
        item = {
            **item,
            "id": uuid.uuid4().hex[:10],
            "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        items.insert(0, item)
        _saved_path().write_text(json.dumps(items, indent=1))
        return item


def delete_saved(item_id: str) -> bool:
    with _lock:
        items = list_saved()
        keep = [i for i in items if i["id"] != item_id]
        _saved_path().write_text(json.dumps(keep, indent=1))
        return len(keep) != len(items)
