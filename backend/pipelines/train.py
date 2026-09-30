"""Train the bust model(s) and the spread/disagreement baseline.

    uv run python -m pipelines.train --source synthetic

Time-based split (configs/model.yaml): training years -> fit, latest year -> held out.
One model per bust definition listed in ``--labels`` (default: the default definition
plus ``category_flip`` when it has enough positives).
"""

from __future__ import annotations

import argparse
import json

import joblib
import numpy as np
import pandas as pd

from ml.config import load_config
from ml.models.analogs_knn import analog_features, cross_fitted_analogs
from ml.models.baseline_spread import SpreadBaseline
from ml.models.lgbm import BustModel
from pipelines.common import artifact_dir, banner, table_path

MIN_POSITIVES = 200


def train(source: str, labels: list[str] | None = None) -> dict:
    cfg = load_config("model")
    adir = artifact_dir(source)
    df = pd.read_parquet(table_path(source))
    meta = json.loads((adir / "dataset_meta.json").read_text())
    base_features = [f for f in meta["features"] if f in df]
    year = pd.to_datetime(df["init_date"]).dt.year
    train_mask = df["split"] == "train"

    default = meta["default_label"]
    if labels is None:
        labels = [default]
        if (
            "bust_category_flip" in df
            and df.loc[train_mask, "bust_category_flip"].sum() >= MIN_POSITIVES
        ):
            labels.append("category_flip")

    acfg = cfg["analogs"]
    analog_feats = [f if f in df else f"sig_{f}" for f in acfg["features"]]
    analog_feats = [f for f in analog_feats if f in df or f in {"fc", "lead_day"}]
    print(f"[train] analog search over {len(analog_feats)} pattern features, k={acfg['k']}")
    ids, dist = cross_fitted_analogs(df, analog_feats, acfg["k"], year, train_mask)
    np.savez_compressed(adir / "analogs.npz", ids=ids, dist=dist)

    preds = df[["init_date", "region_id", "variable", "lead_day", "split"]].copy()
    summary = {}
    for label in labels:
        ycol = f"bust_{label}"
        af = analog_features(df, ids, ycol)
        feats = base_features + list(af.columns)
        X = df[base_features].join(af)
        fit_rows = train_mask & df[ycol].notna()
        model = BustModel(
            params=dict(cfg["lightgbm"]), calibration=cfg["calibration"]["method"], label=label
        )
        model.fit(X.loc[fit_rows, feats], df.loc[fit_rows, ycol], groups=year[fit_rows])

        prob = model.predict_proba(X[feats])
        # training years: show honest out-of-fold probabilities, never in-sample fits
        oof = model.calibrate(np.nan_to_num(model.oof_raw, nan=np.nanmedian(model.oof_raw)))
        prob[np.where(fit_rows)[0]] = oof
        preds[f"prob_{label}"] = prob

        bcol = cfg["baseline"]["score_column"]
        if bcol in df and df.loc[fit_rows, bcol].notna().any():
            baseline = SpreadBaseline(bcol, cfg["baseline"]["name"]).fit(
                df[fit_rows], df.loc[fit_rows, ycol]
            )
            preds[f"baseline_prob_{label}"] = baseline.predict_proba(df)
            preds[f"baseline_raw_{label}"] = baseline.raw(df)
            joblib.dump(baseline, adir / f"baseline_{label}.joblib")
        model.save(adir / f"model_{label}.joblib")
        af.to_parquet(adir / f"analog_features_{label}.parquet")

        test = ~train_mask & df[ycol].notna()
        from sklearn.metrics import roc_auc_score

        auc = (
            roc_auc_score(df.loc[test, ycol], prob[test.to_numpy()])
            if df.loc[test, ycol].nunique() == 2
            else float("nan")
        )
        summary[label] = {
            "n_train": int(fit_rows.sum()),
            "n_test": int(test.sum()),
            "test_roc_auc": float(auc),
            "top_features": model.importance().head(10).round(1).to_dict(),
        }
        print(f"[train] {label}: {fit_rows.sum():,} train rows, test ROC-AUC {auc:.3f}")
        print("        top features:", ", ".join(model.importance().head(6).index))

    preds.to_parquet(adir / "predictions_raw.parquet", index=False)
    (adir / "train_summary.json").write_text(
        json.dumps({"labels": labels, "default": default, **summary}, indent=1)
    )
    return summary


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="synthetic", choices=["synthetic", "wb2", "open_meteo"])
    ap.add_argument("--labels", nargs="*", help="bust definitions to train (default: auto)")
    args = ap.parse_args(argv)
    if banner(args.source):
        print(banner(args.source))
    train(args.source, args.labels)


if __name__ == "__main__":
    main()
