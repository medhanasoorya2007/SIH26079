"""Train BustGuard and its baselines with a strict year-based split (v2).

    uv run python -m pipelines.train --source wb2

* train years       -> LightGBM, feature scalers (analogs), climatologies (in the dataset step)
* calibration years -> isotonic calibrator of the model; baselines are fitted on train+calibration
* test years        -> untouched here; scored by pipelines.evaluate
Replay-event windows are excluded from every fit.
"""

from __future__ import annotations

import argparse
import json

import joblib
import numpy as np
import pandas as pd

from ml.config import load_config
from ml.models.analogs_knn import analog_features, causal_analogs
from ml.models.baseline_spread import build_baselines
from ml.models.lgbm import BustModel
from pipelines.common import artifact_dir, banner, table_path

MIN_POSITIVES = 50


def fit_masks(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    free = df["holdout_event"].fillna("") == ""
    return (df["split"] == "train") & free, (df["split"] == "calib") & free


def train(source: str, labels: list[str] | None = None) -> dict:
    cfg = load_config("model")
    adir = artifact_dir(source)
    df = pd.read_parquet(table_path(source))
    meta = json.loads((adir / "dataset_meta.json").read_text())
    base_features = [f for f in meta["features"] if f in df]
    tr, cal = fit_masks(df)
    lag = int(meta.get("verification_lag_days", cfg["issue_time"]["verification_lag_days"]))

    default = meta["default_label"]
    if labels is None:
        labels = [default]
        for extra in ("p95_error",):
            if (
                f"bust_{extra}" in df
                and extra != default
                and df.loc[tr, f"bust_{extra}"].sum() >= MIN_POSITIVES
            ):
                labels.append(extra)

    acfg = cfg["analogs"]
    analog_feats = [f for f in acfg["features"] if f in df]
    print(
        f"[train] causal analog search over {len(analog_feats)} pattern features, k={acfg['k']}",
        flush=True,
    )
    pool = df["holdout_event"].fillna("") == ""
    ids, dist = causal_analogs(df, analog_feats, acfg["k"], lag, f"bust_{default}", pool, tr)
    np.savez_compressed(adir / "analogs.npz", ids=ids, dist=dist)

    preds = df[["init_date", "region_id", "variable", "lead_day", "split"]].copy()
    preds["in_sample"] = (
        tr.to_numpy()
    )  # probabilities on these rows are in-sample: never displayed as evidence
    summary = {"split": cfg["split"], "n_train": int(tr.sum()), "n_calib": int(cal.sum())}
    for label in labels:
        ycol = f"bust_{label}"
        af = analog_features(df, ids, ycol)
        X = df[base_features].join(af)
        feats = list(X.columns)
        ytr, ycal = tr & df[ycol].notna(), cal & df[ycol].notna()
        if df.loc[ytr, ycol].sum() < MIN_POSITIVES:
            print(
                f"[train] skip {label}: only {int(df.loc[ytr, ycol].sum())} positives in training years"
            )
            continue
        model = BustModel(
            params=dict(cfg["lightgbm"]), calibration=cfg["calibration"]["method"], label=label
        )
        model.fit(X.loc[ytr, feats], df.loc[ytr, ycol], X.loc[ycal, feats], df.loc[ycal, ycol])
        preds[f"prob_{label}"] = model.predict_proba(X[feats])
        model.save(adir / f"model_{label}.joblib")
        af.to_parquet(adir / f"analog_features_{label}.parquet")

        fit_bl = (tr | cal) & df[ycol].notna()
        baselines = build_baselines(cfg["baselines"], df[fit_bl], df.loc[fit_bl, ycol])
        for key, bl in baselines.items():
            preds[f"{key}_prob_{label}"] = bl.predict_proba(df)
        joblib.dump(baselines, adir / f"baselines_{label}.joblib")

        from sklearn.metrics import average_precision_score

        cal_pr = (
            average_precision_score(df.loc[ycal, ycol], preds.loc[ycal, f"prob_{label}"])
            if df.loc[ycal, ycol].nunique() == 2
            else float("nan")
        )
        summary[label] = {
            "n_train_busts": int(df.loc[ytr, ycol].sum()),
            "n_calib_busts": int(df.loc[ycal, ycol].sum()),
            "calibration_pr_auc": float(cal_pr),
            "features": feats,
            "top_features": model.importance().head(12).round(1).to_dict(),
            "baselines": {k: b.name for k, b in baselines.items()},
        }
        print(
            f"[train] {label}: {int(ytr.sum()):,} train rows ({summary[label]['n_train_busts']} busts), calibration PR-AUC {cal_pr:.3f}"
        )
        print("        top features:", ", ".join(model.importance().head(6).index))

    trained = [lab for lab in labels if lab in summary]
    preds.to_parquet(adir / "predictions_raw.parquet", index=False)
    (adir / "train_summary.json").write_text(
        json.dumps({"labels": trained, "default": default, **summary}, indent=1)
    )
    return summary


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="wb2", choices=["synthetic", "wb2", "open_meteo"])
    ap.add_argument("--labels", nargs="*", help="bust definitions to train (default: auto)")
    args = ap.parse_args(argv)
    if banner(args.source):
        print(banner(args.source))
    train(args.source, args.labels)


if __name__ == "__main__":
    main()
