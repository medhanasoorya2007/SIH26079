"""Regime x lead-day scorecard (v2 #14): where does BustGuard beat the spread baselines?"""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import average_precision_score


def regime_lead_scorecard(
    df: pd.DataFrame,
    y_col: str,
    methods: dict[str, str],
    model: str,
    regime_col: str = "sig_regime_label",
    min_busts: int = 8,
) -> dict:
    """PR-AUC per (regime, lead) for every method and model-minus-best-baseline improvement.
    Cells with fewer than ``min_busts`` busts are reported with values = None."""
    cells = []
    baselines = [m for m in methods if m != model]
    for (reg, lead), g in df.groupby([regime_col, "lead_day"]):
        g = g[g[y_col].notna()]
        nb = int(g[y_col].sum())
        cell = {"regime": str(reg), "lead_day": int(lead), "n": int(len(g)), "n_busts": nb}
        if nb >= min_busts and nb < len(g):
            scores = {m: float(average_precision_score(g[y_col], g[c])) for m, c in methods.items()}
            cell["pr_auc"] = scores
            cell["base_rate"] = float(g[y_col].mean())
            cell["improvement"] = (
                scores[model] - max(scores[b] for b in baselines) if baselines else None
            )
        else:
            cell["pr_auc"], cell["improvement"], cell["base_rate"] = (
                None,
                None,
                float(g[y_col].mean()) if len(g) else None,
            )
        cells.append(cell)
    regimes = sorted({c["regime"] for c in cells})
    leads = sorted({c["lead_day"] for c in cells})
    return {"regimes": regimes, "leads": leads, "cells": cells, "min_busts": min_busts}
