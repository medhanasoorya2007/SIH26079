"""Family-level explanations (v2 #9).

Per forecast, TreeSHAP contributions (log-odds) are summed within each feature family and
turned into a share of the bust-raising signal. Sentences always say "associated with",
never "caused by": SHAP describes what the model relied on, not physical causation.
"""

from __future__ import annotations

import numpy as np

from ml.features.base import FAMILIES

FAMILY_LABELS = {
    "disagreement": "Model disagreement",
    "spread": "Spread",
    "drift": "Run-to-run drift",
    "pressure_wind": "Pressure / wind",
    "moisture": "Moisture",
    "upstream": "Upstream systems",
    "regime": "Weather regime",
    "context": "Context",
}
FAMILY_PHRASES = {
    "disagreement": "disagreement between independent models",
    "spread": "large spread between successive forecast runs",
    "drift": "run-to-run drift in the forecast",
    "pressure_wind": "the forecast pressure and low-level wind pattern",
    "moisture": "anomalous moisture at issue time",
    "upstream": "systems upstream of the region",
    "regime": "the current weather regime",
    "context": "lead time, location, season and forecast intensity",
}


def family_matrix(features: list[str], families: dict[str, str]) -> tuple[np.ndarray, list[str]]:
    """One-hot (n_features, n_families) matrix for summing contributions per family."""
    fams = [f for f in FAMILIES if f in set(families.values())]
    M = np.zeros((len(features), len(fams)))
    for i, feat in enumerate(features):
        M[i, fams.index(families.get(feat, "context"))] = 1.0
    return M, fams


def family_contributions(
    contrib: np.ndarray, features: list[str], families: dict[str, str]
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """(signed sums, % share of positive contributions) per family; arrays (n, n_families)."""
    M, fams = family_matrix(features, families)
    sums = contrib @ M
    pos = np.clip(sums, 0, None)
    tot = pos.sum(1, keepdims=True)
    pct = np.divide(pos, tot, out=np.zeros_like(pos), where=tot > 0) * 100.0
    return sums, pct, fams


def family_breakdown(sums_row: np.ndarray, pct_row: np.ndarray, fams: list[str]) -> list[dict]:
    """Sorted list for the API/UI (bust-raising families first)."""
    out = [
        {
            "family": f,
            "label": FAMILY_LABELS[f],
            "shap": round(float(s), 4),
            "pct": round(float(p), 1),
            "direction": "raises" if s > 0 else "lowers",
        }
        for f, s, p in zip(fams, sums_row, pct_row, strict=True)
    ]
    return sorted(out, key=lambda d: (-d["pct"], d["shap"]))


def family_sentence(breakdown: list[dict], min_pct: float = 10.0, n: int = 2) -> str:
    top = [b for b in breakdown if b["direction"] == "raises" and b["pct"] >= min_pct][:n]
    if not top:
        return (
            "No feature family stands out; the bust risk is close to the usual level for this lead."
        )
    parts = [f"{FAMILY_PHRASES[b['family']]} ({b['pct']:.0f}%)" for b in top]
    return "Elevated bust risk is associated with " + " and ".join(parts) + "."
