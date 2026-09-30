"""Evaluate model vs baseline on the held-out year; write metrics.json and docs/results*.md.

uv run python -m pipelines.evaluate --source synthetic
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

from ml.config import REPO_DIR, load_config
from ml.eval.report import evaluate, markdown
from pipelines.common import artifact_dir, banner, table_path

TITLES = {
    "synthetic": "SYNTHETIC demo data (pipeline check only)",
    "wb2": "WeatherBench 2 (ECMWF HRES vs ERA5, JJAS)",
    "open_meteo": "Open-Meteo previous runs (ECMWF IFS, Day 1-7)",
}


def run(source: str) -> dict:
    cfg = load_config("model")
    adir = artifact_dir(source)
    summary = json.loads((adir / "train_summary.json").read_text())
    table = pd.read_parquet(table_path(source))
    preds = pd.read_parquet(adir / "predictions_raw.parquet")
    df = table.merge(
        preds.drop(columns=["split"]),
        on=["init_date", "region_id", "variable", "lead_day"],
        how="left",
    )
    report = evaluate(
        df,
        summary["labels"],
        cfg["eval"]["false_alarm_rates"],
        cfg["eval"]["reliability_bins"],
        cfg["baseline"]["name"],
    )
    report["source"] = source
    report["is_synthetic"] = source == "synthetic"
    report["baseline"] = cfg["baseline"]
    report["default_label"] = summary["default"]
    (adir / "metrics.json").write_text(json.dumps(report, indent=1))

    notes = [
        f"Baseline: **{cfg['baseline']['name']}** (`{cfg['baseline']['score_column']}`), mapped to probabilities with a lead-day-specific isotonic fit on the training years.",
        "Training years use leave-one-year-out calibration; test year never seen during training or calibration.",
        "False-alarm rate = share of non-bust forecasts that get flagged (POFD).",
    ]
    name = "results.md" if source == "wb2" else f"results_{source}.md"
    out = REPO_DIR / "docs" / name
    out.write_text(markdown(report, TITLES[source], banner(source), notes), encoding="utf-8")
    print(f"[eval] wrote {out} and {adir / 'metrics.json'}")
    for label, r in report["labels"].items():
        for m, s in r["overall"].items():
            rec = s["recall_at_far"].get("0.10", {}).get("recall")
            print(
                f"[eval] {label:14s} {m:40s} AUC {s['roc_auc']:.3f}  PR-AUC {s['pr_auc']:.3f}  recall@10%FAR {rec:.1%}"
            )
    return report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="synthetic", choices=["synthetic", "wb2", "open_meteo"])
    args = ap.parse_args(argv)
    if banner(args.source):
        print(banner(args.source))
    run(args.source)


if __name__ == "__main__":
    main()
