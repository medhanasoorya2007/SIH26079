"""Jumpiness: run-to-run drift of the forecast for the same valid day (v2 #7).

Uses the runs issued on I, I-1 and I-2 for the same region and valid day (all known at
issue time). Large or flip-flopping changes mean the guidance is poorly constrained.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register
from ml.features.lagged_spread import lagged_members


@register
class Jumpiness(Signal):
    name = "jumpiness"
    description = (
        "Change between successive runs for the same valid day: last change, two-run drift and "
        "flip-flops (the forecast moved one way, then back)."
    )
    requires = ("fc", "init_date", "valid_date", "lead_day", "region_id", "variable")
    order = 35
    family = "drift"
    explanations = {
        "sig_jump_abs": "The forecast changed by {value:.0f} {unit} since yesterday's run; run-to-run drift of this size is associated with busts.",
        "sig_jump_rel": "The forecast swung by {value:.0%} since yesterday's run.",
        "sig_drift_2run": {
            "high": "The forecast has been trending wetter over the last two runs ({value:+.0f} {unit}).",
            "low": "The forecast has been trending drier over the last two runs ({value:+.0f} {unit}).",
        },
        "sig_flipflop": "The forecast flip-flopped between runs (up, then down or vice versa).",
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        m = lagged_members(df, 3)  # [run I, run I-1, run I-2]
        d1 = m[:, 0] - m[:, 1]
        d2 = m[:, 1] - m[:, 2]
        jump = np.abs(d1)
        flip = np.where(
            np.isfinite(d1) & np.isfinite(d2),
            ((d1 * d2) < 0) & (np.abs(d1) > 1) & (np.abs(d2) > 1),
            np.nan,
        )
        return pd.DataFrame(
            {
                "sig_jump_abs": jump,
                "sig_jump_rel": jump / (np.abs(m[:, 0]) + np.abs(m[:, 1]) + 1.0),
                "sig_drift_2run": m[:, 0] - m[:, 2],
                "sig_flipflop": flip.astype(float),
            },
            index=df.index,
        )
