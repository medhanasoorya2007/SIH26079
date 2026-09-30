"""Config-driven bust labels (see configs/labels.yaml and docs/bust_definition.md).

Every definition returns a 0/1 Series (NaN where the forecast is not yet verified or the
definition does not apply to the variable). Thresholds that are learned from data (the
percentile rule) are fitted on training rows only and returned so they can be frozen,
reported and reused at serve time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ml.config import load_config


@dataclass
class LabelResult:
    labels: pd.DataFrame  # columns: bust_<name> for every definition + `bust` (default)
    thresholds: dict = field(default_factory=dict)  # learned thresholds per definition


def add_errors(df: pd.DataFrame) -> pd.DataFrame:
    """Add signed and absolute forecast error (forecast minus truth)."""
    out = df.copy()
    out["error"] = out["fc"] - out["obs"]
    out["abs_error"] = out["error"].abs()
    return out


def _percentile_error(df: pd.DataFrame, spec: dict, fit_mask: pd.Series) -> tuple[pd.Series, dict]:
    by = spec.get("group_by", ["variable", "lead_day"])
    q = spec.get("percentile", 95) / 100.0
    fit = df.loc[fit_mask & df["abs_error"].notna()]
    thr = fit.groupby(by)["abs_error"].quantile(q)
    floor = spec.get("min_abs_error", {})
    thr_df = thr.rename("thr").reset_index()
    if "variable" in thr_df:  # floor: never call a 3 mm miss in a dry region a bust
        thr_df["thr"] = np.maximum(thr_df["thr"], thr_df["variable"].map(floor).fillna(0.0))
    merged = df[by].merge(thr_df, on=by, how="left")
    merged.index = df.index
    lab = (df["abs_error"] > merged["thr"]).astype(float)
    lab[df["abs_error"].isna() | merged["thr"].isna()] = np.nan
    thresholds = {
        "|".join(str(k) for k in (key if isinstance(key, tuple) else (key,))): float(v)
        for key, v in thr_df.set_index(by)["thr"].items()
    }
    return lab, {"group_by": by, "percentile": spec.get("percentile", 95), "values": thresholds}


def _category_flip(df: pd.DataFrame, spec: dict) -> tuple[pd.Series, dict]:
    thr = np.asarray(spec["thresholds"], dtype=float)
    fc_c = np.digitize(df["fc"].to_numpy(dtype=float), thr)
    ob_c = np.digitize(df["obs"].to_numpy(dtype=float), thr)
    count = spec.get("count", "both")
    if count == "misses":
        flip = ob_c > fc_c
    elif count == "false_alarms":
        flip = fc_c > ob_c
    else:
        flip = fc_c != ob_c
    lab = pd.Series(flip.astype(float), index=df.index)
    lab[(df["variable"] != spec["variable"]) | df["obs"].isna()] = np.nan
    return lab, {"thresholds": thr.tolist(), "count": count}


def _absolute_error(df: pd.DataFrame, spec: dict) -> tuple[pd.Series, dict]:
    lab = (df["abs_error"] >= spec["threshold"]).astype(float)
    lab[(df["variable"] != spec["variable"]) | df["abs_error"].isna()] = np.nan
    return lab, {"threshold": spec["threshold"]}


def make_labels(df: pd.DataFrame, fit_mask: pd.Series, config: dict | None = None) -> LabelResult:
    """Compute every configured bust definition. ``df`` must contain error columns."""
    cfg = config or load_config("labels")
    if "abs_error" not in df:
        df = add_errors(df)
    labels: dict[str, pd.Series] = {}
    thresholds: dict[str, dict] = {}
    pending_any = {}
    for name, spec in cfg["definitions"].items():
        kind = spec["kind"]
        if kind == "percentile_error":
            labels[name], thresholds[name] = _percentile_error(df, spec, fit_mask)
        elif kind == "category_flip":
            labels[name], thresholds[name] = _category_flip(df, spec)
        elif kind == "absolute_error":
            labels[name], thresholds[name] = _absolute_error(df, spec)
        elif kind == "any_of":
            pending_any[name] = spec
        else:
            raise ValueError(f"unknown bust kind {kind!r} for {name}")
    for name, spec in pending_any.items():
        parts = pd.concat([labels[p] for p in spec["of"]], axis=1)
        lab = parts.max(axis=1, skipna=True)
        lab[parts.isna().all(axis=1)] = np.nan
        labels[name] = lab
        thresholds[name] = {"any_of": spec["of"]}
    out = pd.DataFrame({f"bust_{k}": v for k, v in labels.items()}, index=df.index)
    out["bust"] = out[f"bust_{cfg['default']}"]
    return LabelResult(out, thresholds)
