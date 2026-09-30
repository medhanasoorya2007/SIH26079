"""Cost-loss relative economic value of bust probabilities (v2 #14).

A user pays cost C to protect against a bust that would otherwise cost L; alpha = C/L.
Acting when p >= alpha, the relative value V = (E_clim - E_fc) / (E_clim - E_perfect)
(Richardson 2000): 1 = perfect information, 0 = no better than climatology, < 0 = worse.
The user presets in configs/model.yaml are illustrative cost/loss ratios, not measurements.
"""

from __future__ import annotations

import numpy as np

from ml.eval.metrics import _clean


def relative_value(y, p, alpha: float) -> float:
    y_, p_ = _clean(y, p)
    n = len(y_)
    if n == 0:
        return float("nan")
    s = y_.mean()
    act = p_ >= alpha
    e_fc = (alpha * act.sum() + ((~act) & (y_ == 1)).sum()) / n
    e_clim = min(alpha, s)
    e_perf = alpha * s
    den = e_clim - e_perf
    return float((e_clim - e_fc) / den) if den > 0 else float("nan")


def value_curve(y, p, alphas=None) -> list[dict]:
    alphas = np.round(np.geomspace(0.002, 0.8, 40), 4) if alphas is None else alphas
    return [{"alpha": float(a), "value": relative_value(y, p, a)} for a in alphas]
