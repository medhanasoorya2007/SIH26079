"""v2 evaluation: BustGuard vs both spread baselines on the held-out test years.

Every number is computed on the TEST years (configs/model.yaml split). Thresholds used for
alerts/CSI/early warning/confidently-wrong are frozen on the CALIBRATION block first.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd

from ml.eval.ablation import family_ablation
from ml.eval.costloss import relative_value, value_curve
from ml.eval.early_warning import event_lead_times, summarize
from ml.eval.metrics import (
    bootstrap_pr_auc,
    operating_point,
    reliability,
    score_block,
    threshold_at_far,
    to_jsonable,
)
from ml.eval.scorecard import regime_lead_scorecard
from ml.models.confidently_wrong import ConfidentlyWrong

MODEL = "BustGuard"


def method_columns(label: str, baselines: dict, df: pd.DataFrame) -> dict[str, str]:
    cols = {MODEL: f"prob_{label}"}
    for key, spec in baselines.items():
        c = f"{key}_prob_{label}"
        if c in df:
            cols[spec["name"]] = c
    return cols


def evaluate_label(
    df: pd.DataFrame, label: str, cfg: dict, analog_rate: pd.Series, ablation_inputs: dict | None
) -> tuple[dict, dict]:
    """Returns (report dict, frozen artefacts {thresholds, cw}) for one bust definition."""
    ecfg = cfg["eval"]
    y = f"bust_{label}"
    methods = method_columns(label, cfg["baselines"], df)
    free = df["holdout_event"].fillna("") == ""
    cal = (df["split"] == "calib") & free & df[y].notna()
    tr = (df["split"] == "train") & free
    te = (df["split"] == "test") & df[y].notna()
    for c in methods.values():
        te &= df[c].notna()
    d = df[te]

    far = ecfg["operating_far"]
    thr = {m: threshold_at_far(df.loc[cal, y], df.loc[cal, c], far) for m, c in methods.items()}
    risk = {
        "medium": threshold_at_far(
            df.loc[cal, y], df.loc[cal, methods[MODEL]], cfg["risk_levels"]["medium_far"]
        ),
        "high": threshold_at_far(
            df.loc[cal, y], df.loc[cal, methods[MODEL]], cfg["risk_levels"]["high_far"]
        ),
    }

    rep: dict = {
        "methods": methods,
        "primary_metric": "pr_auc",
        "operating_far": far,
        "thresholds": thr,
        "risk_thresholds": risk,
    }
    rep["overall"] = {
        m: {
            **score_block(d[y], d[c], ecfg["false_alarm_rates"]),
            "operating_point": operating_point(d[y], d[c], thr[m]),
        }
        for m, c in methods.items()
    }
    rep["per_lead"] = {
        int(lead): {
            m: {
                **score_block(g[y], g[c], ecfg["false_alarm_rates"]),
                "operating_point": operating_point(g[y], g[c], thr[m]),
            }
            for m, c in methods.items()
        }
        for lead, g in d.groupby("lead_day")
    }
    rep["bootstrap"] = bootstrap_pr_auc(
        d[y], {m: d[c].to_numpy() for m, c in methods.items()}, d["init_date"].to_numpy()
    )
    rep["reliability"] = {
        m: reliability(d[y], d[c], ecfg["reliability_bins"]) for m, c in methods.items()
    }
    rep["reliability_calibration_block"] = reliability(
        df.loc[cal, y], df.loc[cal, methods[MODEL]], ecfg["reliability_bins"]
    )

    # ---- confidently wrong (headline): busts that the spread says are safe
    ccfg = cfg["confidently_wrong"]
    cw = ConfidentlyWrong(
        spread_col=ccfg["spread_column"],
        quantile=ccfg["quantile"],
        group_by=tuple(ccfg["group_by"]),
        min_group_size=ccfg["min_group_size"],
        analog_min_rate=ccfg["analog_min_rate"],
    ).fit(df[tr])
    low = cw.low_spread(d)
    has_spread = d[ccfg["spread_column"]].notna().to_numpy()
    busts = d[y].to_numpy() == 1
    lowrep = {
        "n_low_spread": int(low.sum()),
        "n_low_spread_busts": int((low & busts).sum()),
        "n_busts": int(busts.sum()),
        "share_of_busts_with_low_spread": float((low & busts).sum() / max(busts.sum(), 1)),
    }
    for m, c in methods.items():
        p = d[c].to_numpy(dtype=float)
        lowrep[m] = {
            "recall_low_spread_busts": float((p[low & busts] >= thr[m]).mean())
            if (low & busts).any()
            else None,
            "recall_other_busts": float((p[~low & busts & has_spread] >= thr[m]).mean())
            if (~low & busts & has_spread).any()
            else None,
        }
    alerts = cw.alerts(
        d, d[methods[MODEL]].to_numpy(), risk["high"], analog_rate.loc[d.index].to_numpy()
    )
    lowrep["alerts"] = {
        "n_alerts": int(alerts.sum()),
        "n_alert_busts": int((alerts & busts).sum()),
        "precision": float((alerts & busts).sum() / alerts.sum()) if alerts.any() else None,
        "base_rate_low_spread": float(busts[low].mean()) if low.any() else None,
        "share_low_spread_busts_alerted": float(
            (alerts & busts & low).sum() / max((low & busts).sum(), 1)
        ),
    }
    rep["confidently_wrong"] = lowrep

    rep["scorecard"] = regime_lead_scorecard(
        d, y, methods, MODEL, min_busts=ecfg["scorecard_min_busts"]
    )
    ev = event_lead_times(d.assign(bust=d[y]), methods, thr, bust_col="bust")
    rep["early_warning"] = summarize(ev, list(methods))

    users = cfg["costloss"]["users"]
    rep["costloss"] = {
        "curves": {m: value_curve(d[y], d[c]) for m, c in methods.items()},
        "users": {
            k: {
                **u,
                "value": {m: relative_value(d[y], d[c], u["alpha"]) for m, c in methods.items()},
            }
            for k, u in users.items()
        },
        "base_rate": float(d[y].mean()),
    }
    if ablation_inputs is not None:
        rep["ablation"] = family_ablation(**ablation_inputs)
    rep["test_period"] = {
        "from": str(pd.to_datetime(d["init_date"]).min().date()),
        "to": str(pd.to_datetime(d["init_date"]).max().date()),
        "n": int(len(d)),
    }
    return to_jsonable(rep), {"thresholds": thr, "risk": risk, "cw": cw}


def build_report(
    df: pd.DataFrame, labels: list[str], cfg: dict, analog_rates: dict, ablation: dict | None
) -> tuple[dict, dict]:
    out = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "split": cfg["split"],
        "labels": {},
    }
    frozen = {}
    for lab in labels:
        out["labels"][lab], frozen[lab] = evaluate_label(
            df, lab, cfg, analog_rates[lab], ablation if lab == labels[0] else None
        )
    return out, frozen


# ----------------------------------------------------------------------------- markdown
def _f(x, pct=False, nd=3):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{x:.1%}" if pct else f"{x:.{nd}f}"


def markdown(report: dict, title: str, banner: str, notes: list[str], changelog: list[str]) -> str:
    L = [f"# BustGuard results: {title}", ""]
    if banner:
        L += [f"> **{banner}**", ""]
    sp = report["split"]
    L += [
        f"Split by year: train {sp['train_years']}, calibration {sp['calibration_years']}, **test {sp['test_years']} (fully unseen)**. "
        f"Generated {report['generated_utc']}. Every number below is computed on the test years; thresholds were frozen on the calibration year.",
        "",
    ]
    L += [f"- {n}" for n in notes] + [""]
    for label, r in report["labels"].items():
        names = list(r["methods"])
        ov = r["overall"]
        n0 = ov[names[0]]
        L += [
            f"## Bust definition `{label}`",
            "",
            f"Test forecasts: {n0['n']:,}; busts: {n0['n_busts']:,} (base rate {n0['base_rate']:.2%}).",
            "",
        ]
        L += ["| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        L.append(
            "| **PR-AUC (primary)** | "
            + " | ".join(f"**{_f(ov[m]['pr_auc'])}**" for m in names)
            + " |"
        )
        bs = r.get("bootstrap", {}).get("pr_auc_ci", {})
        if bs:
            L.append(
                "| PR-AUC 95% CI (bootstrap over issue dates) | "
                + " | ".join(f"{_f(bs[m][0])}-{_f(bs[m][1])}" for m in names)
                + " |"
            )
        L.append("| ROC-AUC | " + " | ".join(_f(ov[m]["roc_auc"]) for m in names) + " |")
        L.append(
            "| Brier score (lower is better) | "
            + " | ".join(_f(ov[m]["brier"], nd=5) for m in names)
            + " |"
        )
        L.append(
            "| Brier skill vs climatology | "
            + " | ".join(_f(ov[m]["brier_skill_vs_climatology"]) for m in names)
            + " |"
        )
        for fk in ov[names[0]]["recall_at_far"]:
            L.append(
                f"| Busts caught at {float(fk):.0%} false-alarm rate (ROC) | "
                + " | ".join(_f(ov[m]["recall_at_far"][fk]["recall"], pct=True) for m in names)
                + " |"
            )
        op = {m: ov[m]["operating_point"] for m in names}
        L.append(
            f"| Operating point (threshold frozen at {r['operating_far']:.0%} FAR on calibration): recall / realised FAR | "
            + " | ".join(f"{_f(op[m]['recall'], True)} / {_f(op[m]['far'], True)}" for m in names)
            + " |"
        )
        L.append(
            "| Precision at operating point | "
            + " | ".join(_f(op[m]["precision"], True) for m in names)
            + " |"
        )
        L.append("| CSI at operating point | " + " | ".join(_f(op[m]["csi"]) for m in names) + " |")
        cw = r["confidently_wrong"]
        L += ["", "### Confidently wrong: busts the spread said were safe (headline)", ""]
        L += [
            f"{cw['n_low_spread_busts']} of {cw['n_busts']} test busts ({cw['share_of_busts_with_low_spread']:.0%}) happened when the lagged-ensemble spread was in its lowest third for the regime and month.",
            "",
        ]
        L += ["| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        L.append(
            "| Recall on **low-spread** busts | "
            + " | ".join(_f(cw[m]["recall_low_spread_busts"], True) for m in names)
            + " |"
        )
        L.append(
            "| Recall on other busts | "
            + " | ".join(_f(cw[m]["recall_other_busts"], True) for m in names)
            + " |"
        )
        a = cw["alerts"]
        L += [
            "",
            f"CONFIDENTLY-WRONG ALERTS on the test years: {a['n_alerts']} raised, {a['n_alert_busts']} verified as busts (precision {_f(a['precision'], True)} vs {_f(a['base_rate_low_spread'], True)} bust rate among all low-spread forecasts).",
            "",
        ]
        L += [
            "### Per lead day (PR-AUC)",
            "",
            "| Lead | busts | " + " | ".join(names) + " |",
            "|---|---|" + "---|" * len(names),
        ]
        for lead, per in sorted(r["per_lead"].items(), key=lambda kv: int(kv[0])):
            L.append(
                f"| Day {lead} | {per[names[0]]['n_busts']} | "
                + " | ".join(_f(per[m]["pr_auc"]) for m in names)
                + " |"
            )
        ew = r["early_warning"]
        L += [
            "",
            f"### Early warning ({ew['n_events']} events: region-days whose Day-1 forecast busted)",
            "",
            "| | mean warning lead (days) | warned at all | warned >= 3 days ahead |",
            "|---|---|---|---|",
        ]
        for m in names:
            e = ew[m]
            L.append(
                f"| {m} | {_f(e['mean_days'], nd=2)} | {_f(e['share_warned'], True)} | {_f(e['share_3plus_days'], True)} |"
            )
        cl = r["costloss"]["users"]
        L += [
            "",
            "### Cost-loss value (relative economic value; illustrative user cost/loss ratios)",
            "",
            "| User (C/L) | " + " | ".join(names) + " |",
            "|---|" + "---|" * len(names),
        ]
        for u in cl.values():
            L.append(
                f"| {u['label']} ({u['alpha']}) | "
                + " | ".join(_f(u["value"][m]) for m in names)
                + " |"
            )
        if r.get("ablation"):
            L += [
                "",
                "### Ablation: drop one feature family, retrain, test PR-AUC",
                "",
                "| Dropped family | features | PR-AUC | change |",
                "|---|---|---|---|",
            ]
            for a in r["ablation"]:
                L.append(
                    f"| {a['family']} | {a['n_features']} | {_f(a['pr_auc'])} | {a['delta']:+.3f} |"
                )
        sc = r["scorecard"]
        cells = [c for c in sc["cells"] if c["improvement"] is not None]
        if cells:
            L += [
                "",
                f"### Regime x lead: PR-AUC improvement of BustGuard over the best baseline (cells with >= {sc['min_busts']} busts)",
                "",
            ]
            leads = sc["leads"]
            L += [
                "| Regime | " + " | ".join(f"D{d}" for d in leads) + " |",
                "|---|" + "---|" * len(leads),
            ]
            for reg in sc["regimes"]:
                row = []
                for lead in leads:
                    c = next(
                        (c for c in sc["cells"] if c["regime"] == reg and c["lead_day"] == lead),
                        None,
                    )
                    row.append(
                        f"{c['improvement']:+.2f}" if c and c["improvement"] is not None else "·"
                    )
                L.append(f"| {reg} | " + " | ".join(row) + " |")
        L += [
            "",
            "Reliability (test, BustGuard):",
            "",
            "| forecast bin | mean forecast | observed | n |",
            "|---|---|---|---|",
        ]
        for b in r["reliability"][MODEL]:
            L.append(
                f"| {b['bin_lo']:.1f}-{b['bin_hi']:.1f} | {b['mean_prob']:.3f} | {b['obs_freq']:.3f} | {b['count']:,} |"
            )
        L += [""]
    if changelog:
        L += ["## Changelog", ""] + [f"- {c}" for c in changelog] + [""]
    return "\n".join(L) + "\n"
