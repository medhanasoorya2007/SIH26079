"""Regime pathway chains filled with the families the model flagged (v2 #13)."""

from __future__ import annotations

from ml.config import load_config


def pathway(regime: str | None, breakdown: list[dict], region_name: str) -> list[dict] | None:
    """Ordered steps [{family, text}] + final step, or None if no family was flagged."""
    cfg = load_config("pathways")
    flagged = {
        b["family"]
        for b in breakdown
        if b["direction"] == "raises" and b["pct"] >= cfg["min_family_pct"]
    }
    template = cfg["pathways"].get(regime or "Normal") or cfg["pathways"]["Normal"]
    steps = [dict(s) for s in template if s["family"] in flagged]
    if not steps:
        return None
    return [*steps, {"family": "outcome", "text": cfg["final"].format(region=region_name)}]
