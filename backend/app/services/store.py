"""In-memory store over the exported v2 bundle (fully offline at serve time).

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
from ml.explain.serve import breakdown_from_pct, family_sentence, pathway, render_reasons
from ml.regions import load_regions

ORDER = [("wb2", "wb2"), ("open_meteo", "open_meteo"), ("synthetic", "SYNTHETIC")]
REQUIRED = ("serving.parquet", "meta.json")
RISK_ORDER = {"Low": 0, "Medium": 1, "High": 2}


def _schema_ok(folder: Path) -> bool:
    try:
        return json.loads((folder / "meta.json").read_text()).get("schema_version", 1) >= 2
    except (OSError, ValueError):
        return False


def available_sources() -> dict[str, Path]:
    out = {}
    for name, tagname in ORDER:
        for d in (ARTIFACTS_DIR / tagname, SAMPLE_DIR / tagname):
            if all((d / f).exists() for f in REQUIRED) and _schema_ok(d):
                out[name] = d
                break
    return out


def default_source() -> str:
    env = os.environ.get("BUSTGUARD_SOURCE")
    avail = available_sources()
    if env:
        if env not in avail:
            raise RuntimeError(f"BUSTGUARD_SOURCE={env} has no exported v2 artifacts")
        return env
    if not avail:
        raise RuntimeError("no exported artifacts found: run `make pipeline` (or `make synthetic`)")
    return next(iter(avail))


def num(x) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(f) else round(f, 4)


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
        cat = folder / "catalog.parquet"
        self.catalog = pd.read_parquet(cat).set_index("row") if cat.exists() else pd.DataFrame()
        self._by_slice = self.df.groupby(["init_str", "lead_day", "variable"]).indices
        self._by_region = self.df.groupby(["init_str", "region_id", "variable"]).indices
        self._by_date = self.df.groupby(["init_str", "variable"]).indices
        self.regions = load_regions()
        self.features = self.meta.get("model_features", [])
        self.medians = self.meta.get("feature_medians", {})
        self.fam_cols = [c for c in self.df.columns if c.startswith("fam_")]

    # ------------------------------------------------------------------ lookups
    @property
    def label(self) -> str:
        return self.meta["default_label"]

    def report(self) -> dict:
        return self.metrics.get("labels", {}).get(self.label, {})

    def latest_date(self) -> str:
        dates = self.meta.get("test_init_dates") or self.meta["init_dates"]
        return dates[-1]

    def slice(self, date: str, lead: int, variable: str) -> pd.DataFrame:
        idx = self._by_slice.get((date, lead, variable))
        return self.df.iloc[idx] if idx is not None else self.df.iloc[:0]

    def day(self, date: str, variable: str) -> pd.DataFrame:
        idx = self._by_date.get((date, variable))
        return self.df.iloc[idx] if idx is not None else self.df.iloc[:0]

    def region_rows(self, date: str, region_id: str, variable: str) -> pd.DataFrame:
        idx = self._by_region.get((date, region_id, variable))
        return self.df.iloc[idx].sort_values("lead_day") if idx is not None else self.df.iloc[:0]

    def region_name(self, rid: str) -> str:
        return str(self.regions.loc[rid, "name"]) if rid in self.regions.index else rid

    # ------------------------------------------------------------ explanations
    def families(self, r) -> list[dict]:
        return breakdown_from_pct({c[4:]: r[c] for c in self.fam_cols})

    def reasons(self, r) -> list[dict]:
        items = []
        for k in range(5):
            f = f"r{k}_f"
            if f not in r or r[f] < 0 or r[f] >= len(self.features):
                continue
            items.append((self.features[int(r[f])], float(r[f"r{k}_v"]), float(r[f"r{k}_c"])))
        return render_reasons(
            items, self.medians, self.region_name(r["region_id"]), r["variable"], int(r["lead_day"])
        )

    def analogs(self, r, k: int = 5) -> dict:
        cases = []
        for j in range(k):
            rid = int(r.get(f"an{j}", -1))
            if rid < 0 or rid not in self.catalog.index:
                continue
            c = self.catalog.loc[rid]
            cases.append(
                {
                    "init_date": pd.Timestamp(c["init_date"]).strftime("%Y-%m-%d"),
                    "valid_date": pd.Timestamp(c["valid_date"]).strftime("%Y-%m-%d"),
                    "region_id": c["region_id"],
                    "region": self.region_name(c["region_id"]),
                    "lead_day": int(c["lead_day"]),
                    "fc": num(c["fc"]),
                    "obs": num(c["obs"]),
                    "bust": num(c["bust"]),
                    "regime": c["regime"],
                }
            )
        n, nb = int(r.get("an_n", 0)), int(r.get("an_bust", 0))
        return {
            "n_total": n,
            "n_bust": nb,
            "text": f"{nb} of {n} similar past cases busted"
            if n
            else "No verified similar past cases yet",
            "cases": cases,
        }

    def forecast_summary(self, r) -> dict:
        fam = self.families(r)
        driver = next((f for f in fam if f["direction"] == "raises"), None)
        return {
            "lead_day": int(r["lead_day"]),
            "init_date": r["init_str"],
            "valid_date": r["valid_date"].strftime("%Y-%m-%d"),
            "fc": num(r["fc"]),
            "obs": num(r["obs"]),
            "abs_error": num(r["abs_error"]),
            "bust": num(r["bust"]),
            "bust_prob": num(r["prob"]),
            "confidence": num(1 - r["prob"]),
            "risk": r["risk"],
            "reliability": {
                "observed_bust_rate": num(r["reliability_obs"]),
                "n": int(r["reliability_n"]),
            },
            "confidently_wrong": bool(r["cw"]),
            "low_spread": bool(r["low_spread"]),
            "spread": num(r["spread"]),
            "spread_says": r["spread_says"],
            "spread_prob": num(r["spread_prob"]),
            "lr_prob": num(r["lr_prob"]),
            "regime": r["regime"],
            "likely_driver": driver["label"] if driver else None,
            "families": fam,
            "family_sentence": family_sentence(
                [
                    {**f, "direction": "raises" if f["direction"] == "raises" else "lowers"}
                    for f in fam
                ]
            ),
        }


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


def region_pathway(store: DataStore, r) -> list[dict] | None:
    fam = store.families(r)
    return pathway(
        r["regime"],
        [{**f, "direction": "raises" if f["direction"] == "raises" else "lowers"} for f in fam],
        store.region_name(r["region_id"]),
    )


def risk_windows(rows: pd.DataFrame, min_level: str = "Medium") -> list[dict]:
    """Contiguous lead-day ranges at or above ``min_level``."""
    out, cur = [], None
    for r in rows.sort_values("lead_day").itertuples():
        hot = RISK_ORDER.get(r.risk, 0) >= RISK_ORDER[min_level]
        if hot and cur is None:
            cur = {"from_lead": int(r.lead_day), "to_lead": int(r.lead_day), "max_risk": r.risk}
        elif hot:
            cur["to_lead"] = int(r.lead_day)
            if RISK_ORDER[r.risk] > RISK_ORDER[cur["max_risk"]]:
                cur["max_risk"] = r.risk
        elif cur is not None:
            out.append(cur)
            cur = None
    if cur is not None:
        out.append(cur)
    return out


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
