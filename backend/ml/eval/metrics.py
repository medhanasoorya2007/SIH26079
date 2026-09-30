"""Verification metrics for bust probabilities.

The headline comparison is *recall at a fixed false-alarm rate*: if an operational desk
tolerates, say, 10% false alarms among non-bust forecasts, how many real busts does
each method catch?
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score, roc_curve


def _clean(y, s):
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    ok = ~(np.isnan(y) | np.isnan(s))
    return y[ok].astype(int), s[ok]


def recall_at_far(y, score, far: float) -> dict:
    """Highest recall (hit rate) achievable with false-alarm rate <= ``far``.

    False-alarm rate here is POFD = FP / (FP + TN), i.e. the share of non-bust forecasts
    that get flagged. Returns recall, the realised FAR and the score threshold.
    """
    y, s = _clean(y, score)
    if y.min(initial=1) == y.max(initial=0):
        return {"recall": np.nan, "far": np.nan, "threshold": np.nan}
    fpr, tpr, thr = roc_curve(y, s)
    ok = np.where(fpr <= far + 1e-12)[0]
    i = ok[np.argmax(tpr[ok])]
    return {"recall": float(tpr[i]), "far": float(fpr[i]), "threshold": float(thr[i])}


def reliability(y, p, bins: int = 10) -> list[dict]:
    """Reliability-diagram points: mean forecast probability vs observed frequency."""
    y, p = _clean(y, p)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    out = []
    for b in range(bins):
        m = idx == b
        if m.sum() == 0:
            continue
        out.append(
            {
                "bin_lo": float(edges[b]),
                "bin_hi": float(edges[b + 1]),
                "mean_prob": float(p[m].mean()),
                "obs_freq": float(y[m].mean()),
                "count": int(m.sum()),
            }
        )
    return out


def score_block(y, prob, far_levels=(0.05, 0.1, 0.2)) -> dict:
    """All scalar metrics for one set of probabilities."""
    y_, p_ = _clean(y, prob)
    n_pos = int(y_.sum())
    res = {
        "n": int(len(y_)),
        "n_busts": n_pos,
        "base_rate": float(y_.mean()) if len(y_) else np.nan,
    }
    if 0 < n_pos < len(y_):
        res.update(
            roc_auc=float(roc_auc_score(y_, p_)),
            pr_auc=float(average_precision_score(y_, p_)),
            brier=float(brier_score_loss(y_, np.clip(p_, 0, 1))),
        )
        clim = y_.mean()
        res["brier_skill_vs_climatology"] = float(1 - res["brier"] / (clim * (1 - clim)))
    else:
        res.update(roc_auc=np.nan, pr_auc=np.nan, brier=np.nan, brier_skill_vs_climatology=np.nan)
    res["recall_at_far"] = {f"{f:.2f}": recall_at_far(y_, p_, f) for f in far_levels}
    return res


def compare(
    df: pd.DataFrame, y_col: str, methods: dict[str, str], far_levels, bins: int = 10
) -> dict:
    """Overall + per-lead metrics for several probability columns on the same rows."""
    ok = df[y_col].notna()
    for c in methods.values():
        ok &= df[c].notna()
    d = df[ok]
    out = {"overall": {}, "per_lead": {}, "reliability": {}}
    for name, col in methods.items():
        out["overall"][name] = score_block(d[y_col], d[col], far_levels)
        out["reliability"][name] = reliability(d[y_col], d[col], bins)
    for lead, g in d.groupby("lead_day"):
        out["per_lead"][int(lead)] = {
            name: score_block(g[y_col], g[col], far_levels) for name, col in methods.items()
        }
    return out


def to_jsonable(obj):
    """Replace NaN/inf with None recursively (for JSON output)."""
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, float | np.floating):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    return obj
