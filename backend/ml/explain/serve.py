"""Render explanations at serve time from the compact export (keeps the offline bundle small).

The export stores, per forecast, the top-K bust-raising features (index, value, TreeSHAP
contribution) and the family percentages; sentences, pathways and family breakdowns are
rebuilt here with the same templates used everywhere else.
"""

from __future__ import annotations

import math
from functools import lru_cache

from ml.explain.grouped_shap import FAMILY_LABELS, family_sentence
from ml.explain.pathways import pathway
from ml.explain.reasons import ANALOG_TEMPLATES, UNITS, _fmt
from ml.features.base import REGISTRY, discover


@lru_cache(maxsize=1)
def templates() -> dict:
    discover()
    t = dict(ANALOG_TEMPLATES)
    for cls in REGISTRY.values():
        t.update(cls.explanations)
    return t


def render_reasons(
    items: list[tuple[str, float, float]],
    medians: dict,
    region: str,
    variable: str,
    lead: int,
    n: int = 3,
) -> list[dict]:
    """items: [(feature, value, contribution)] sorted by contribution (desc)."""
    out, seen = [], set()
    for feat, value, contrib in items:
        if (
            contrib is None
            or not contrib > 0
            or value is None
            or (isinstance(value, float) and math.isnan(value))
        ):
            continue
        tpl = templates().get(feat)
        if tpl is None:
            continue
        if isinstance(tpl, dict):
            tpl = tpl["high"] if value >= medians.get(feat, 0.0) else tpl["low"]
        text = _fmt(tpl, float(value), {"variable": variable, "lead_day": lead}, region)
        if text in seen:
            continue
        seen.add(text)
        out.append(
            {
                "feature": feat,
                "text": text,
                "contribution": round(float(contrib), 4),
                "value": round(float(value), 4),
            }
        )
        if len(out) >= n:
            break
    return out


def breakdown_from_pct(pct: dict[str, float]) -> list[dict]:
    rows = [
        {
            "family": f,
            "label": FAMILY_LABELS.get(f, f),
            "pct": round(float(p), 1),
            "direction": "raises" if p > 0 else "neutral",
        }
        for f, p in pct.items()
        if p is not None and not (isinstance(p, float) and math.isnan(p))
    ]
    return sorted(rows, key=lambda r: -r["pct"])


__all__ = ["render_reasons", "breakdown_from_pct", "family_sentence", "pathway", "UNITS"]
