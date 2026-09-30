"""Build the training table: raw forecasts/obs -> split -> bust labels -> signals.

uv run python -m pipelines.dataset --source synthetic
uv run python -m pipelines.dataset --source wb2
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from ml.config import ensure_dirs, load_config
from ml.features.base import SignalContext, compute_signals, feature_columns, feature_families
from ml.labels.bust import add_errors, make_labels
from pipelines.common import artifact_dir, banner, raw_path, table_path


def build_raw(source: str) -> pd.DataFrame:
    if source == "synthetic":
        from ml.data.synthetic import generate

        return generate()
    if source == "wb2":
        from ml.data.wb2_table import build

        return build()
    if source == "open_meteo":
        from ml.data.open_meteo import build_table

        return build_table()
    raise SystemExit(f"unknown source {source}")


def assign_split(df: pd.DataFrame) -> pd.Series:
    """'train' | 'calib' | 'test' | 'unused' by initialisation year (configs/model.yaml)."""
    sp = load_config("model")["split"]
    years = pd.to_datetime(df["init_date"]).dt.year
    out = np.full(len(df), "unused", dtype=object)
    out[years.isin(sp["train_years"]).to_numpy()] = "train"
    out[years.isin(sp["calibration_years"]).to_numpy()] = "calib"
    out[years.isin(sp["test_years"]).to_numpy()] = "test"
    return pd.Series(out, index=df.index)


def holdout_events(df: pd.DataFrame) -> pd.Series:
    """Replay-event id for rows whose valid date falls in an event window, else ''."""
    ev = load_config("replay_events")["events"]
    vd = pd.to_datetime(df["valid_date"])
    out = pd.Series("", index=df.index, dtype=object)
    for e in ev:
        lo, hi = (pd.Timestamp(str(x)) for x in e["window"])
        out[(vd >= lo) & (vd <= hi)] = e["id"]
    return out


def build_table(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = raw.sort_values(["init_date", "lead_day", "region_id", "variable"]).reset_index(drop=True)
    df["split"] = assign_split(df)
    df["holdout_event"] = holdout_events(df)
    # climatologies, scalers and label thresholds see training years only (never events)
    fit_mask = (df["split"] == "train") & (df["holdout_event"] == "")
    df = add_errors(df)
    labels = make_labels(df, fit_mask)
    df = df.join(labels.labels)
    lag = int(load_config("model")["issue_time"]["verification_lag_days"])
    df, signals = compute_signals(df, SignalContext(fit_mask=fit_mask, verification_lag_days=lag))
    meta = {
        "signals": [{"name": s.name, "description": s.description} for s in signals],
        "features": feature_columns(df, signals),
        "families": feature_families(df, signals),
        "label_thresholds": labels.thresholds,
        "default_label": load_config("labels")["default"],
        "split": load_config("model")["split"],
        "verification_lag_days": lag,
    }
    return df, meta


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="synthetic", choices=["synthetic", "wb2", "open_meteo"])
    ap.add_argument("--reuse-raw", action="store_true", help="skip rebuilding the raw table")
    args = ap.parse_args(argv)
    ensure_dirs()
    if banner(args.source):
        print(banner(args.source))
    rp = raw_path(args.source)
    if args.reuse_raw and rp.exists():
        raw = pd.read_parquet(rp)
    else:
        raw = build_raw(args.source)
        raw.to_parquet(rp, index=False)
    table, meta = build_table(raw)
    table.to_parquet(table_path(args.source), index=False)
    (artifact_dir(args.source) / "dataset_meta.json").write_text(
        json.dumps(meta, indent=1, default=str)
    )
    counts = table.groupby("split")["bust"].agg(["size", "mean", "sum"])
    print(
        f"[dataset] {args.source}: {len(table):,} rows, {len(meta['features'])} features "
        f"from {len(meta['signals'])} signals; holdout-event rows: {(table['holdout_event'] != '').sum():,}"
    )
    print(counts.rename(columns={"size": "rows", "mean": "bust_rate", "sum": "busts"}).to_string())
    print(f"[dataset] wrote {table_path(args.source)}")


if __name__ == "__main__":
    main()
