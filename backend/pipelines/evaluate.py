"""Evaluate BustGuard vs both baselines on the held-out test years (v2).

    uv run python -m pipelines.evaluate --source wb2

Writes artifacts/<SOURCE>/metrics.json, frozen thresholds + confidently-wrong detector
(frozen.joblib, used by export/API), and docs/results.md (real data) or
docs/results_synthetic.md.
"""

from __future__ import annotations

import argparse
import json

import joblib
import pandas as pd

from ml.config import REPO_DIR, load_config
from ml.eval.report import build_report, markdown
from pipelines.common import artifact_dir, banner, table_path

TITLES = {
    "synthetic": "SYNTHETIC demo data (pipeline check only)",
    "wb2": "ECMWF HRES vs IMD gridded rainfall, IMD subdivisions, JJAS",
    "open_meteo": "Open-Meteo previous runs (ECMWF IFS, Day 1-8)",
}
CHANGELOG = [
    "v2: bust = IMD rainfall-category bust (>= 2 classes apart, or observed >= Heavy while forecast < Heavy); v1 p95 label kept as option.",
    "v2: regions = 34 IMD meteorological subdivisions (area means); rain truth = IMD 0.25 deg gridded rainfall (ERA5 only for atmospheric state).",
    "v2: split train 2018-19 / calibration 2020 / test 2021-22; replay-event windows excluded from fitting; features restricted to issue-time information.",
    "v2: baselines = lagged-ensemble spread (per-lead isotonic) and logistic regression (spread + lead day).",
    "v2: new feature families, grouped SHAP explanations, confidently-wrong alerts, pathways, analog cases, regime x lead scorecard, early-warning lead time, cost-loss value, ablation.",
]


def run(source: str, ablation: bool | None = None) -> dict:
    cfg = load_config("model")
    adir = artifact_dir(source)
    summary = json.loads((adir / "train_summary.json").read_text())
    meta = json.loads((adir / "dataset_meta.json").read_text())
    table = pd.read_parquet(table_path(source))
    preds = pd.read_parquet(adir / "predictions_raw.parquet")
    keys = ["init_date", "region_id", "variable", "lead_day"]
    df = table.merge(preds.drop(columns=["split"]), on=keys, how="left")
    labels = summary["labels"]
    analog = {
        lab: pd.read_parquet(adir / f"analog_features_{lab}.parquet")[
            "sig_analog_bust_rate"
        ].set_axis(df.index)
        for lab in labels
    }

    abl = None
    do_ablation = cfg["eval"]["ablation"] if ablation is None else ablation
    if do_ablation:
        lab = labels[0]
        af = pd.read_parquet(adir / f"analog_features_{lab}.parquet").set_axis(df.index)
        feats = summary[lab]["features"]
        X = df[[f for f in feats if f in df]].join(af[[c for c in af if c in feats]])
        free = df["holdout_event"].fillna("") == ""
        abl = {
            "X": X,
            "y": df[f"bust_{lab}"],
            "masks": {
                "train": (df["split"] == "train") & free,
                "calib": (df["split"] == "calib") & free,
                "test": df["split"] == "test",
            },
            "families": meta["families"],
            "params": summary[lab]["params"],
            "calibration": cfg["calibration"]["method"],
        }
        print("[eval] ablation: retraining without each feature family ...", flush=True)

    report, frozen = build_report(df, labels, cfg, analog, abl)
    report.update(
        source=source,
        is_synthetic=source == "synthetic",
        default_label=summary["default"],
        families=meta["families"],
    )
    (adir / "metrics.json").write_text(json.dumps(report, indent=1))
    joblib.dump(frozen, adir / "frozen.joblib")

    notes = [
        "Rain truth: IMD 0.25 deg gridded rainfall, subdivision area means. Forecast: ECMWF HRES (WeatherBench 2, 1.5 deg), 00 UTC runs.",
        "Spread = lagged-ensemble spread (std of the last three HRES runs for the same valid day), a proxy: the 50-member ECMWF ensemble was not downloaded. No spread exists for Day 10.",
        "Primary metric: PR-AUC (busts are rare). False-alarm rate = share of non-bust forecasts flagged.",
    ]
    name = "results.md" if source == "wb2" else f"results_{source}.md"
    out = REPO_DIR / "docs" / name
    out.write_text(
        markdown(
            report, TITLES[source], banner(source), notes, CHANGELOG if source == "wb2" else []
        ),
        encoding="utf-8",
    )
    print(f"[eval] wrote {out}")
    for lab, r in report["labels"].items():
        for m, s in r["overall"].items():
            print(
                f"[eval] {lab:13s} {m:30s} PR-AUC {s['pr_auc']:.3f}  ROC {s['roc_auc']:.3f}  recall@op {s['operating_point']['recall']:.1%} (FAR {s['operating_point']['far']:.1%})"
            )
        cw = r["confidently_wrong"]
        print(
            f"[eval] {lab:13s} low-spread busts {cw['n_low_spread_busts']}/{cw['n_busts']}: "
            + ", ".join(f"{m} {cw[m]['recall_low_spread_busts'] or 0:.1%}" for m in r["methods"])
        )
    return report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="wb2", choices=["synthetic", "wb2", "open_meteo"])
    ap.add_argument("--no-ablation", action="store_true")
    args = ap.parse_args(argv)
    if banner(args.source):
        print(banner(args.source))
    run(args.source, ablation=False if args.no_ablation else None)


if __name__ == "__main__":
    main()
