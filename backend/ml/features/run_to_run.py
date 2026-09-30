"""Run-to-run 'jumpiness': how much the forecast for the same day changed since yesterday."""

from __future__ import annotations

import pandas as pd

from ml.features.base import Signal, SignalContext, register


@register
class RunToRun(Signal):
    name = "run_to_run"
    description = (
        "Change between today's forecast and yesterday's forecast for the same valid day "
        "and region. Flip-flopping guidance signals a poorly constrained, uncertain situation."
    )
    requires = ("fc", "init_date", "valid_date", "lead_day", "region_id", "variable")
    order = 35
    explanations = {
        "sig_jump_abs": "The forecast changed by {value:.0f} {unit} since yesterday's run: unstable guidance.",
        "sig_jump_rel": "The forecast swung by {value:.0%} since yesterday's run.",
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        prev = df[["region_id", "variable", "valid_date", "lead_day", "fc"]].copy()
        # yesterday's run verified on the same valid day with lead + 1
        prev["lead_day"] = prev["lead_day"] - 1
        prev = prev.rename(columns={"fc": "_fc_prev"})
        merged = df[["region_id", "variable", "valid_date", "lead_day", "fc"]].merge(
            prev, on=["region_id", "variable", "valid_date", "lead_day"], how="left"
        )
        merged.index = df.index
        jump = (merged["fc"] - merged["_fc_prev"]).abs()
        return pd.DataFrame(
            {
                "sig_jump_abs": jump,
                "sig_jump_rel": jump / (merged["fc"].abs() + merged["_fc_prev"].abs() + 1.0),
            },
            index=df.index,
        )
