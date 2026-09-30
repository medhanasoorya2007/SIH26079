"""Export everything the API serves (offline): predictions + reasons + analogs + replay events.

    uv run python -m pipelines.export --source wb2 [--sample]

``--sample`` also writes a compact copy to data/sample/<SOURCE>/ (committed to git, < 20 MB)
so the dashboard runs straight after cloning, without downloads or training.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from ml.config import SAMPLE_DIR, load_config
from ml.explain.reasons import ANALOG_TEMPLATES, reasons_batch
from ml.features.base import REGISTRY, discover
from ml.models.lgbm import BustModel
from ml.regions import load_regions
from pipelines.common import artifact_dir, banner, table_path, tag

KEEP = [
    "init_date",
    "valid_date",
    "lead_day",
    "region_id",
    "variable",
    "split",
    "fc",
    "fc_alt",
    "obs",
    "error",
    "abs_error",
    "sig_regime_label",
    "sig_disagreement_abs",
    "sig_jump_abs",
    "sig_mslp_anom",
    "sig_geo_vorticity",
]


def risk_level(p: np.ndarray) -> np.ndarray:
    levels = load_config("model")["risk_levels"]
    out = np.empty(len(p), dtype=object)
    lo = -np.inf
    for lvl in levels:
        m = (p > lo) & (p <= lvl["max"]) if np.isfinite(lo) else p <= lvl["max"]
        out[m] = lvl["name"]
        lo = lvl["max"]
    return out


def _templates() -> dict:
    discover()
    t = dict(ANALOG_TEMPLATES)
    for cls in REGISTRY.values():
        t.update(cls.explanations)
    return t


def compute_reasons(df: pd.DataFrame, model: BustModel, X: pd.DataFrame, n: int = 3) -> list[str]:
    """JSON list of top-n reasons per row (TreeSHAP, bust-increasing features only)."""
    contrib = model.contributions(X).drop(columns=["_bias"]).to_numpy()
    names = load_regions()["name"].to_dict()
    batch = reasons_batch(
        contrib,
        X[model.features].to_numpy(dtype=float),
        model.features,
        _templates(),
        model.feature_medians,
        [names.get(r, r) for r in df["region_id"]],
        df["variable"].tolist(),
        df["lead_day"].tolist(),
        n,
    )
    return [json.dumps(r) for r in batch]


def _warning_lead(per_lead: list[dict], flag_key: str, n_hit: int) -> int:
    """Warning lead time: largest L such that at least half of the affected regions were
    flagged at EVERY lead day from 1 to L (i.e. the warning stood continuously since Day L)."""
    need = max(1, n_hit // 2)
    lead = 0
    for r in sorted(per_lead, key=lambda r: r["lead_day"]):
        if r["lead_day"] != lead + 1 or not r.get(flag_key) or r[flag_key] < need:
            break
        lead = r["lead_day"]
    return lead


def detect_replay_events(
    serv: pd.DataFrame, thr_model: float, thr_base: float | None, max_events: int = 6
) -> list[dict]:
    """Real bust episodes in the held-out year: many regions busting at short lead."""
    regions = load_regions()
    test = serv[(serv["split"] == "test") & serv["bust"].notna()]
    short = test[(test["lead_day"] <= 2) & (test["bust"] == 1)]
    if short.empty:
        return []
    counts = short.groupby("valid_date")["region_id"].nunique().sort_values(ascending=False)
    chosen: list[pd.Timestamp] = []
    for vd, c in counts.items():
        if c < 2 or len(chosen) >= max_events:
            break
        if all(abs((vd - x).days) > 4 for x in chosen):
            chosen.append(vd)
    events = []
    for vd in sorted(chosen):
        hit = sorted(short.loc[short["valid_date"] == vd, "region_id"].unique())
        rows = test[(test["valid_date"] == vd) & test["region_id"].isin(hit)]
        per_lead = []
        for lead, g in rows.groupby("lead_day"):
            per_lead.append(
                {
                    "lead_day": int(lead),
                    "init_date": str(g["init_date"].iloc[0].date()),
                    "model_prob": float(g["prob"].mean()),
                    "baseline_prob": float(g["baseline_prob"].mean())
                    if "baseline_prob" in g and g["baseline_prob"].notna().any()
                    else None,
                    "model_flagged": int((g["prob"] >= thr_model).sum()),
                    "baseline_flagged": int((g["baseline_prob"] >= thr_base).sum())
                    if thr_base is not None and "baseline_prob" in g
                    else None,
                    "n_regions": int(g["region_id"].nunique()),
                    "fc_mean": float(g["fc"].mean()),
                    "obs_mean": float(g["obs"].mean()),
                }
            )
        per_lead.sort(key=lambda r: -r["lead_day"])

        subdiv = regions.loc[hit, "subdivision"].value_counts().index[:2].tolist()
        regime = rows.loc[rows["lead_day"] == rows["lead_day"].min(), "regime"].mode()
        events.append(
            {
                "id": f"{vd:%Y%m%d}-{hit[0]}",
                "valid_date": str(vd.date()),
                "title": f"{' · '.join(subdiv)}: {vd:%d %b %Y}",
                "regime": str(regime.iloc[0]) if len(regime) else "Normal",
                "regions": hit,
                "n_regions": len(hit),
                "obs_max": float(rows["obs"].max()),
                "per_lead": per_lead,
                "model_warning_days": _warning_lead(per_lead, "model_flagged", len(hit)),
                "baseline_warning_days": _warning_lead(per_lead, "baseline_flagged", len(hit)),
                "model_threshold": thr_model,
                "baseline_threshold": thr_base,
            }
        )
    return events


def export(source: str, write_sample: bool = False) -> None:
    adir = artifact_dir(source)
    summary = json.loads((adir / "train_summary.json").read_text())
    metrics = json.loads((adir / "metrics.json").read_text())
    ds_meta = json.loads((adir / "dataset_meta.json").read_text())
    label = summary["default"]
    table = pd.read_parquet(table_path(source))
    preds = pd.read_parquet(adir / "predictions_raw.parquet")
    keys = ["init_date", "region_id", "variable", "lead_day"]
    df = table.merge(preds.drop(columns=["split"]), on=keys, how="left")

    model = BustModel.load(adir / f"model_{label}.joblib")
    af = pd.read_parquet(adir / f"analog_features_{label}.parquet")
    X = df[[f for f in model.features if f in df]].join(af[[c for c in af if c in model.features]])
    print(f"[export] computing top-3 reasons for {len(df):,} forecasts ...", flush=True)
    reasons = compute_reasons(df, model, X)

    serv = df[[c for c in KEEP if c in df]].copy()
    serv["bust"] = df[f"bust_{label}"]
    for lab in summary["labels"]:
        serv[f"bust_{lab}"] = df[f"bust_{lab}"]
        serv[f"prob_{lab}"] = df[f"prob_{lab}"]
    serv["prob"] = df[f"prob_{label}"]
    if f"baseline_prob_{label}" in df:
        serv["baseline_prob"] = df[f"baseline_prob_{label}"]
    serv["confidence"] = 1.0 - serv["prob"]
    serv["risk"] = risk_level(serv["prob"].to_numpy())
    serv["reasons"] = reasons
    serv["is_synthetic"] = source == "synthetic"
    serv = serv.rename(
        columns={
            "sig_regime_label": "regime",
            "sig_disagreement_abs": "disagreement",
            "sig_jump_abs": "jump",
            "sig_mslp_anom": "mslp_anom",
            "sig_geo_vorticity": "geo_vorticity",
        }
    )
    for c in serv.select_dtypes("float64"):
        serv[c] = serv[c].astype("float32")
    serv.to_parquet(adir / "serving.parquet", index=False)

    an = np.load(adir / "analogs.npz")
    np.savez_compressed(
        adir / "serving_analogs.npz",
        ids=an["ids"][:, :5].astype(np.int32),
        dist=an["dist"][:, :5].astype(np.float32),
    )

    far = metrics["labels"][label]["overall"]
    thr_model = far["BustGuard"]["recall_at_far"]["0.10"]["threshold"]
    bname = load_config("model")["baseline"]["name"]
    thr_base = far.get(bname, {}).get("recall_at_far", {}).get("0.10", {}).get("threshold")
    events = detect_replay_events(serv, thr_model, thr_base)
    (adir / "replay_events.json").write_text(json.dumps(events, indent=1))

    meta = {
        "source": source,
        "source_tag": tag(source),
        "is_synthetic": source == "synthetic",
        "banner": banner(source),
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "default_label": label,
        "labels": summary["labels"],
        "label_thresholds": ds_meta["label_thresholds"],
        "signals": ds_meta["signals"],
        "variables": sorted(serv["variable"].unique().tolist()),
        "lead_days": sorted(int(x) for x in serv["lead_day"].unique()),
        "init_dates": sorted({str(d.date()) for d in pd.to_datetime(serv["init_date"])}),
        "test_init_dates": sorted(
            {str(d.date()) for d in pd.to_datetime(serv.loc[serv["split"] == "test", "init_date"])}
        ),
        "risk_levels": load_config("model")["risk_levels"],
        "baseline_name": bname,
        "operating_point": {
            "false_alarm_rate": 0.10,
            "model_threshold": thr_model,
            "baseline_threshold": thr_base,
        },
        "top_features": summary[label]["top_features"],
    }
    (adir / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"[export] {len(serv):,} forecasts, {len(events)} replay events -> {adir}")

    if write_sample:
        dst = SAMPLE_DIR / tag(source)
        dst.mkdir(parents=True, exist_ok=True)
        for f in [
            "serving.parquet",
            "serving_analogs.npz",
            "replay_events.json",
            "meta.json",
            "metrics.json",
        ]:
            shutil.copy2(adir / f, dst / f)
        size = sum(p.stat().st_size for p in dst.iterdir()) / 1e6
        print(f"[export] sample written to {dst} ({size:.1f} MB)")
        if size > 20:
            print("[export] WARNING: sample exceeds 20 MB; do not commit it as is.")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="synthetic", choices=["synthetic", "wb2", "open_meteo"])
    ap.add_argument("--sample", action="store_true", help="also write the committed demo sample")
    args = ap.parse_args(argv)
    if banner(args.source):
        print(banner(args.source))
    export(args.source, args.sample)


if __name__ == "__main__":
    main()
