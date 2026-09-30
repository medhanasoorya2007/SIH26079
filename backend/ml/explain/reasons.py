"""Turn TreeSHAP contributions into plain-English meteorological reasons.

For each forecast, the features that pushed the bust probability UP the most are
translated with the templates each signal declares (``Signal.explanations``). Templates
may be a string, or a {"high": ..., "low": ...} pair chosen by comparing the value with
the training median. Several features that map to the same sentence are merged.
"""

from __future__ import annotations

import math

import pandas as pd

ANALOG_TEMPLATES = {
    "sig_analog_bust_rate": "In the most similar past forecasts, {value:.0%} turned out to be busts.",
    "sig_analog_mae": "The most similar past forecasts were off by {value:.0f} {unit} on average.",
}

UNITS = {"rain": "mm", "tmax": "degC"}


def _fmt(template: str, value: float, row: pd.Series, region_name: str) -> str:
    unit = UNITS.get(str(row.get("variable", "rain")), "")
    try:
        return template.format(
            value=value, row=row, region=region_name, unit=unit, lead=row.get("lead_day")
        )
    except (ValueError, KeyError, IndexError):  # a bad template must never break the API
        return template


def top_reasons(
    contrib_row: pd.Series,
    feature_row: pd.Series,
    templates: dict,
    medians: dict,
    region_name: str,
    n: int = 3,
) -> list[dict]:
    """Top-``n`` bust-increasing reasons for one forecast."""
    c = contrib_row.drop(labels=["_bias"], errors="ignore")
    c = c[c > 0].sort_values(ascending=False)
    reasons: list[dict] = []
    seen: set[str] = set()
    for feat, val in c.items():
        tpl = templates.get(feat)
        if tpl is None:
            continue
        x = feature_row.get(feat)
        if x is None or (isinstance(x, float) and math.isnan(x)):
            continue
        if isinstance(tpl, dict):
            tpl = tpl["high"] if x >= medians.get(feat, 0.0) else tpl["low"]
        text = _fmt(tpl, float(x), feature_row, region_name)
        if text in seen:
            continue
        seen.add(text)
        reasons.append(
            {"feature": feat, "text": text, "contribution": round(float(val), 4), "value": float(x)}
        )
        if len(reasons) >= n:
            break
    return reasons
