"""Family ablation (v2 #14): retrain without each feature family, measure test PR-AUC change."""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import average_precision_score

from ml.models.lgbm import BustModel


def family_ablation(
    X: pd.DataFrame,
    y: pd.Series,
    masks: dict[str, pd.Series],
    families: dict[str, str],
    params: dict,
    calibration: str = "isotonic",
) -> list[dict]:
    """``masks``: train / calib / test boolean Series. Returns one row per family."""
    tr, cal, te = (masks[k] & y.notna() for k in ("train", "calib", "test"))

    def pr(cols: list[str]) -> float:
        m = BustModel(params=dict(params), calibration=calibration).fit(
            X.loc[tr, cols], y[tr], X.loc[cal, cols], y[cal]
        )
        return float(average_precision_score(y[te], m.predict_proba(X.loc[te, cols])))

    full_cols = list(X.columns)
    full = pr(full_cols)
    rows = [
        {"family": "none (full model)", "n_features": len(full_cols), "pr_auc": full, "delta": 0.0}
    ]
    ctx_only = [c for c in full_cols if families.get(c, "context") == "context"]
    if ctx_only and len(ctx_only) < len(full_cols):
        score = pr(ctx_only)
        rows.append(
            {
                "family": "ONLY context (location, season, lead, amount, recent error, analogs)",
                "n_features": len(ctx_only),
                "pr_auc": score,
                "delta": score - full,
            }
        )
    for fam in sorted(set(families.get(c, "context") for c in full_cols)):
        cols = [c for c in full_cols if families.get(c, "context") != fam]
        if not cols or len(cols) == len(full_cols):
            continue
        score = pr(cols)
        rows.append(
            {
                "family": fam,
                "n_features": len(full_cols) - len(cols),
                "pr_auc": score,
                "delta": score - full,
            }
        )
    return rows
