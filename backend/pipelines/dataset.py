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
from ml.features.base import SignalContext, compute_signals, feature_columns
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
    test_years = set(load_config("model")["split"]["test_years"])
    years = pd.to_datetime(df["init_date"]).dt.year
    return pd.Series(np.where(years.isin(test_years), "test", "train"), index=df.index)


def build_table(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = raw.sort_values(["init_date", "lead_day", "region_id", "variable"]).reset_index(drop=True)
    df["split"] = assign_split(df)
    fit_mask = df["split"] == "train"
    df = add_errors(df)
    labels = make_labels(df, fit_mask)
    df = df.join(labels.labels)
    df, signals = compute_signals(df, SignalContext(fit_mask=fit_mask))
    meta = {
        "signals": [{"name": s.name, "description": s.description} for s in signals],
        "features": feature_columns(df, signals),
        "label_thresholds": labels.thresholds,
        "default_label": load_config("labels")["default"],
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
    tr = table[table["split"] == "train"]
    te = table[table["split"] == "test"]
    print(
        f"[dataset] {args.source}: {len(table):,} rows ({len(tr):,} train / {len(te):,} test), "
        f"{len(meta['features'])} features from {len(meta['signals'])} signals, "
        f"bust rate train {tr['bust'].mean():.3f} / test {te['bust'].mean():.3f}"
    )
    print(f"[dataset] wrote {table_path(args.source)}")


if __name__ == "__main__":
    main()
