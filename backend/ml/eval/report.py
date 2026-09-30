"""Model-vs-baseline evaluation report (JSON for the API + Markdown for docs/results.md)."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from ml.eval.metrics import compare, to_jsonable


def evaluate(
    df: pd.DataFrame, labels: list[str], far_levels, bins: int, baseline_name: str
) -> dict:
    """Metrics on the held-out split for every trained label definition."""
    test = df[df["split"] == "test"]
    out = {"generated_utc": datetime.now(UTC).isoformat(timespec="seconds"), "labels": {}}
    for label in labels:
        methods = {"BustGuard": f"prob_{label}"}
        if f"baseline_prob_{label}" in test:
            methods[baseline_name] = f"baseline_prob_{label}"
        out["labels"][label] = compare(test, f"bust_{label}", methods, far_levels, bins)
        out["labels"][label]["methods"] = methods
    out["test_period"] = {
        "from": str(pd.to_datetime(test["init_date"]).min().date()) if len(test) else None,
        "to": str(pd.to_datetime(test["init_date"]).max().date()) if len(test) else None,
    }
    return to_jsonable(out)


def _f(x, pct=False):
    if x is None:
        return "n/a"
    return f"{x:.1%}" if pct else f"{x:.3f}"


def markdown(report: dict, source_title: str, banner: str, notes: list[str]) -> str:
    lines = [f"# BustGuard results: {source_title}", ""]
    if banner:
        lines += [f"> **{banner}**", ""]
    tp = report["test_period"]
    lines += [
        f"Held-out test period (initialisations): **{tp['from']} to {tp['to']}**. Generated {report['generated_utc']}.",
        "",
    ]
    for n in notes:
        lines.append(f"- {n}")
    lines.append("")
    for label, r in report["labels"].items():
        names = list(r["methods"].keys())
        lines += [f"## Bust definition: `{label}`", ""]
        ov = r["overall"]
        lines += ["| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        n0 = ov[names[0]]
        lines.append(
            f"| Test forecasts / busts | {n0['n']:,} / {n0['n_busts']:,} (base rate {n0['base_rate']:.1%}) |"
            + " |" * (len(names) - 1)
        )
        for key, title in [
            ("roc_auc", "ROC-AUC"),
            ("pr_auc", "PR-AUC"),
            ("brier", "Brier score (lower = better)"),
            ("brier_skill_vs_climatology", "Brier skill vs climatology"),
        ]:
            lines.append(f"| {title} | " + " | ".join(_f(ov[m][key]) for m in names) + " |")
        for far, _ in ov[names[0]]["recall_at_far"].items():
            lines.append(
                f"| Busts caught at {float(far):.0%} false-alarm rate | "
                + " | ".join(_f(ov[m]["recall_at_far"][far]["recall"], pct=True) for m in names)
                + " |"
            )
        lines += ["", "**Per lead day** (ROC-AUC; busts caught at 10% false-alarm rate):", ""]
        lines += [
            "| Lead day | n busts | "
            + " | ".join(f"{m} AUC | {m} recall@10%" for m in names)
            + " |"
        ]
        lines += ["|---|---|" + "---|---|" * len(names)]
        for lead, per in sorted(r["per_lead"].items(), key=lambda kv: int(kv[0])):
            cells = []
            for m in names:
                cells += [
                    _f(per[m]["roc_auc"]),
                    _f(per[m]["recall_at_far"].get("0.10", {}).get("recall"), pct=True),
                ]
            lines.append(f"| Day {lead} | {per[names[0]]['n_busts']} | " + " | ".join(cells) + " |")
        lines += [""]
        rel = r["reliability"][names[0]]
        lines += [
            "Reliability of BustGuard probabilities (test):",
            "",
            "| Forecast prob. bin | mean forecast | observed frequency | n |",
            "|---|---|---|---|",
        ]
        for b in rel:
            lines.append(
                f"| {b['bin_lo']:.1f}-{b['bin_hi']:.1f} | {b['mean_prob']:.3f} | {b['obs_freq']:.3f} | {b['count']:,} |"
            )
        lines += [""]
    return "\n".join(lines) + "\n"
