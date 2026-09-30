"""Export everything the API serves, offline (v2).

    uv run python -m pipelines.export --source wb2 [--sample]

Only out-of-sample forecasts are exported: calibration + test years and replay-event windows
(which were excluded from fitting). ``--sample`` copies the compact bundle to
data/sample/<SOURCE>/ (committed, < 20 MB) so the dashboard and `make demo` run offline.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd

from ml.config import SAMPLE_DIR, load_config
from ml.explain.grouped_shap import (
    FAMILY_LABELS,
    family_contributions,
)
from ml.features.base import FAMILIES
from ml.models.lgbm import BustModel
from ml.regions import load_regions
from pipelines.common import artifact_dir, banner, table_path, tag

MODEL = "BustGuard"
BUNDLE = ["serving.parquet", "catalog.parquet", "replay_events.json", "meta.json", "metrics.json"]


def risk_levels(p: np.ndarray, thr: dict) -> np.ndarray:
    return np.select([p >= thr["high"], p >= thr["medium"]], ["High", "Medium"], "Low").astype(
        object
    )


def reliability_lookup(p: np.ndarray, bins: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Observed bust frequency (calibration block) of the reliability bin each prob falls in."""
    obs = np.full(len(p), np.nan)
    n = np.zeros(len(p), dtype=int)
    for b in bins:
        m = (p >= b["bin_lo"]) & ((p < b["bin_hi"]) | (b["bin_hi"] >= 1.0))
        obs[m], n[m] = b["obs_freq"], b["count"]
    return obs, n


def _warning_lead(rows: list[dict], key: str) -> int:
    lead = 0
    for r in sorted(rows, key=lambda r: r["lead_day"]):
        if r["lead_day"] - 1 != lead or not r[key]:
            break
        lead = r["lead_day"]
    return lead


def _n(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(f) else round(f, 4)


def build_replay(serv: pd.DataFrame, coverage: list[dict], names: dict) -> list[dict]:
    """Replay payloads for events that passed the coverage check (docs/replay_events.md)."""
    events = []
    for ev in coverage:
        if not ev.get("usable"):
            continue
        lo, hi = (pd.Timestamp(x) for x in ev["window"])
        sub = serv[
            (serv["valid_date"] >= lo)
            & (serv["valid_date"] <= hi)
            & serv["region_id"].isin(ev["regions"])
        ]
        if sub.empty:
            continue
        days = []
        for vd, g in sub.groupby("valid_date"):
            regions = []
            for rid, h in g.groupby("region_id"):
                steps = [
                    {
                        "lead_day": int(r.lead_day),
                        "init_date": pd.Timestamp(r.init_date).strftime("%Y-%m-%d"),
                        "fc": _n(r.fc),
                        "obs": _n(r.obs),
                        "bust": _n(r.bust),
                        "model_prob": _n(r.prob),
                        "model_risk": r.risk,
                        "model_flag": bool(r.risk == "High"),
                        "spread": _n(r.spread),
                        "spread_prob": _n(r.spread_prob),
                        "spread_says": r.spread_says,
                        "spread_flag": bool(r.spread_says == "uncertain"),
                        "confidently_wrong": bool(r.cw),
                    }
                    for r in h.sort_values("lead_day", ascending=False).itertuples()
                ]
                regions.append(
                    {
                        "region_id": rid,
                        "region": names.get(rid, rid),
                        "obs": _n(h["obs"].iloc[0]),
                        "busted_day1": bool((h.loc[h["lead_day"] == 1, "bust"] == 1).any()),
                        "first_warning": {
                            MODEL: _warning_lead(steps, "model_flag"),
                            "spread": _warning_lead(steps, "spread_flag"),
                        },
                        "steps": steps,
                    }
                )
            days.append({"valid_date": pd.Timestamp(vd).strftime("%Y-%m-%d"), "regions": regions})
        events.append(
            {
                **{k: ev.get(k) for k in ("id", "title", "window", "regions", "split")},
                "peak": ev.get("peak") or {},
                "days": days,
                "region_names": [names.get(r, r) for r in ev["regions"]],
            }
        )
    return events


def export(source: str, write_sample: bool = False) -> None:
    adir = artifact_dir(source)
    summary = json.loads((adir / "train_summary.json").read_text())
    metrics = json.loads((adir / "metrics.json").read_text())
    ds_meta = json.loads((adir / "dataset_meta.json").read_text())
    mcfg = load_config("model")
    label = summary["default"]
    frozen = joblib.load(adir / "frozen.joblib")[label]
    rep = metrics["labels"][label]
    table = pd.read_parquet(table_path(source))
    preds = pd.read_parquet(adir / "predictions_raw.parquet")
    keys = ["init_date", "region_id", "variable", "lead_day"]
    df = table.merge(preds.drop(columns=["split"]), on=keys, how="left")
    keep = (df["split"].isin(["calib", "test"]) | (df["holdout_event"].fillna("") != "")).to_numpy()
    kpos = np.where(keep)[0]
    d = df.loc[keep]

    model = BustModel.load(adir / f"model_{label}.joblib")
    af = pd.read_parquet(adir / f"analog_features_{label}.parquet").set_axis(df.index)
    X = (
        df[[f for f in model.features if f in df]]
        .join(af[[c for c in af if c in model.features]])
        .loc[keep, model.features]
    )
    print(f"[export] explaining {len(X):,} out-of-sample forecasts ...", flush=True)
    C = model.contributions(X).drop(columns=["_bias"]).to_numpy()
    fams = {f: ds_meta["families"].get(f, "context") for f in model.features}
    sums, pct, fam_names = family_contributions(C, model.features, fams)
    regions = load_regions()
    rname = regions["name"].to_dict()
    # compact explanation: top-K bust-raising features (index, value, contribution)
    K = 5
    top = np.argsort(-C, axis=1)[:, :K]
    top_c = np.take_along_axis(C, top, 1)
    top_v = np.take_along_axis(X.to_numpy(dtype=float), top, 1)

    prob = d[f"prob_{label}"].to_numpy()
    nan = np.full(len(d), np.nan)
    spread_name = mcfg["baselines"]["spread_iso"]["name"]
    spread_prob = (
        d[f"spread_iso_prob_{label}"].to_numpy() if f"spread_iso_prob_{label}" in d else nan
    )
    lr_prob = d[f"spread_lr_prob_{label}"].to_numpy() if f"spread_lr_prob_{label}" in d else nan
    spread = d["sig_spread"].to_numpy(dtype=float)
    spread_thr = frozen["thresholds"].get(spread_name, np.inf)
    spread_says = np.where(
        ~np.isfinite(spread),
        "no spread",
        np.where(spread_prob >= spread_thr, "uncertain", "confident"),
    )
    cw = frozen["cw"]
    analog_rate = af.loc[keep, "sig_analog_bust_rate"].to_numpy()
    low = cw.low_spread(d)
    alert = cw.alerts(d, prob, frozen["risk"]["high"], analog_rate)
    rel_obs, rel_n = reliability_lookup(prob, rep["reliability_calibration_block"])

    # analogs: "N of M similar past cases busted" + a catalogue of the cases themselves
    an = np.load(adir / "analogs.npz")
    ids = an["ids"][kpos]
    lab = df[f"bust_{label}"].to_numpy(dtype=float)
    valid = ids >= 0
    an_n = valid.sum(1)
    an_bust = (valid & (lab[np.where(valid, ids, 0)] == 1)).sum(1)
    cat_ids = np.unique(ids[:, :5][ids[:, :5] >= 0])
    catalog = df.iloc[cat_ids][
        [
            "init_date",
            "valid_date",
            "lead_day",
            "region_id",
            "fc",
            "obs",
            f"bust_{label}",
            "sig_regime_label",
        ]
    ].rename(columns={f"bust_{label}": "bust", "sig_regime_label": "regime"})
    catalog.insert(0, "row", cat_ids.astype(np.int32))

    regimes = d["sig_regime_label"].fillna("Normal").tolist()
    col = lambda c: d[c].to_numpy(dtype="float32") if c in d else nan.astype("float32")  # noqa: E731
    serv = pd.DataFrame(
        {
            "row": kpos.astype(np.int32),
            "init_date": d["init_date"].to_numpy(),
            "valid_date": d["valid_date"].to_numpy(),
            "lead_day": d["lead_day"].astype(np.int8).to_numpy(),
            "region_id": d["region_id"].to_numpy(),
            "variable": d["variable"].to_numpy(),
            "split": d["split"].to_numpy(),
            "holdout_event": d["holdout_event"].fillna("").to_numpy(),
            "fc": col("fc"),
            "obs": col("obs"),
            "abs_error": col("abs_error"),
            "bust": d[f"bust_{label}"].to_numpy(dtype="float32"),
            "prob": prob.astype("float32"),
            "spread_prob": spread_prob.astype("float32"),
            "lr_prob": lr_prob.astype("float32"),
            "spread": spread.astype("float32"),
            "spread_says": spread_says,
            "low_spread": low,
            "cw": alert,
            "risk": risk_levels(prob, frozen["risk"]),
            "reliability_obs": rel_obs.astype("float32"),
            "reliability_n": rel_n.astype(np.int32),
            "regime": regimes,
            "jump": col("sig_jump_abs"),
            "tcwv_anom": col("sig_tcwv_anom"),
            "an_n": an_n.astype(np.int8),
            "an_bust": an_bust.astype(np.int8),
        }
    )
    for j, f in enumerate(fam_names):
        serv[f"fam_{f}"] = np.round(pct[:, j], 1).astype("float32")
    for k in range(K):
        serv[f"r{k}_f"] = top[:, k].astype(np.int8)
        serv[f"r{k}_v"] = top_v[:, k].astype("float32")
        serv[f"r{k}_c"] = np.round(top_c[:, k], 4).astype("float32")
    for k in range(5):
        serv[f"an{k}"] = ids[:, k].astype(np.int32)
    serv.to_parquet(adir / "serving.parquet", index=False, compression="zstd")
    catalog.to_parquet(adir / "catalog.parquet", index=False, compression="zstd")

    cov_path = adir / "events_coverage.json"
    coverage = json.loads(cov_path.read_text()) if cov_path.exists() else []
    serv_ts = serv.assign(
        init_date=pd.to_datetime(serv["init_date"]), valid_date=pd.to_datetime(serv["valid_date"])
    )
    events = build_replay(serv_ts, coverage, rname)
    (adir / "replay_events.json").write_text(json.dumps(events, indent=1))

    ov = rep["overall"]
    cwrep = rep["confidently_wrong"]
    methods = list(rep["methods"])
    meta = {
        "schema_version": 2,
        "source": source,
        "source_tag": tag(source),
        "is_synthetic": source == "synthetic",
        "banner": banner(source),
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "default_label": label,
        "label_definition": load_config("labels")["definitions"][label],
        "variables": sorted(serv["variable"].unique().tolist()),
        "variables_unavailable": {
            "tmax": "No Tmax forecasts in this build (HRES 2 m temperature was not downloaded). The Tmax bust rule is implemented and tested."
        },
        "lead_days": sorted(int(x) for x in serv["lead_day"].unique()),
        "init_dates": sorted({str(x)[:10] for x in serv["init_date"]}),
        "test_init_dates": sorted(
            {str(x)[:10] for x in serv.loc[serv["split"] == "test", "init_date"]}
        ),
        "split": mcfg["split"],
        "families": list(FAMILIES),
        "family_labels": FAMILY_LABELS,
        "families_present": fam_names,
        "risk_thresholds": frozen["risk"],
        "operating_point": {
            "false_alarm_rate": rep["operating_far"],
            "thresholds": frozen["thresholds"],
        },
        "methods": methods,
        "method_columns": {
            MODEL: "prob",
            spread_name: "spread_prob",
            **{m: "lr_prob" for m in methods if m not in (MODEL, spread_name)},
        },
        "spread_note": "Spread = lagged-ensemble spread (std of the last three HRES runs for the same valid day): a proxy, not the 50-member ECMWF ensemble. No spread on Day 10.",
        "headline": {
            "test_years": mcfg["split"]["test_years"],
            "base_rate": ov[MODEL]["base_rate"],
            "pr_auc": {m: ov[m]["pr_auc"] for m in methods},
            "pr_auc_ci": rep.get("bootstrap", {}).get("pr_auc_ci"),
            "recall_at_operating_point": {m: ov[m]["operating_point"]["recall"] for m in methods},
            "far_at_operating_point": {m: ov[m]["operating_point"]["far"] for m in methods},
            "n_low_spread_busts": cwrep["n_low_spread_busts"],
            "recall_low_spread_busts": {m: cwrep[m]["recall_low_spread_busts"] for m in methods},
            "cw_alerts": cwrep["alerts"],
        },
        "top_features": summary[label]["top_features"],
        "model_features": model.features,
        "feature_medians": model.feature_medians,
        "feature_families": fams,
        "signals": ds_meta["signals"],
        "n_forecasts": int(len(serv)),
    }
    (adir / "meta.json").write_text(json.dumps(meta, indent=1, default=str))
    print(
        f"[export] {len(serv):,} forecasts, {len(catalog):,} analog cases, {len(events)} replay events -> {adir}"
    )

    if write_sample:
        dst = SAMPLE_DIR / tag(source)
        dst.mkdir(parents=True, exist_ok=True)
        for f in BUNDLE:
            shutil.copy2(adir / f, dst / f)
        size = sum(p.stat().st_size for p in dst.iterdir()) / 1e6
        print(f"[export] sample bundle -> {dst} ({size:.1f} MB)")
        if size > 20:
            raise SystemExit("[export] sample bundle exceeds 20 MB: not suitable for git")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="wb2", choices=["synthetic", "wb2", "open_meteo"])
    ap.add_argument("--sample", action="store_true", help="also write the committed demo sample")
    args = ap.parse_args(argv)
    if banner(args.source):
        print(banner(args.source))
    export(args.source, args.sample)


if __name__ == "__main__":
    main()
