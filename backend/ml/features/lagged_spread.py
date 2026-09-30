"""Lagged-ensemble spread: how much the last three HRES runs disagree about the same day.

For a forecast issued on day I at lead d (valid day V), the "members" are the runs issued
on I (lead d), I-1 (lead d+1) and I-2 (lead d+2), all available at issue time. Their
standard deviation is a classic, download-free proxy for ensemble spread (time-lagged
ensemble). It is NOT the 50-member ECMWF ensemble spread; the UI and docs say so.
Needs lead d+1 / d+2 in the data: with Day 1-10 forecasts it covers Day 1-8 fully and
Day 9 with two members; Day 10 has no spread.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register

N_MEMBERS = 3


def lagged_members(df: pd.DataFrame, n: int = N_MEMBERS) -> np.ndarray:
    """Array (len(df), n): forecasts for the same region/valid day from runs I, I-1, ... I-n+1."""
    key = ["region_id", "variable", "valid_date"]
    base = df[[*key, "lead_day", "fc"]]
    out = np.full((len(df), n), np.nan)
    out[:, 0] = df["fc"].to_numpy(dtype=float)
    for k in range(1, n):
        older = base.copy()
        older["lead_day"] = older["lead_day"] - k  # run issued k days earlier has lead + k
        m = df[[*key, "lead_day"]].merge(older, on=[*key, "lead_day"], how="left")
        out[:, k] = m["fc"].to_numpy(dtype=float)
    return out


@register
class LaggedSpread(Signal):
    name = "lagged_spread"
    description = (
        "Spread of the last three HRES runs for the same valid day (time-lagged ensemble). "
        "A proxy for ensemble spread: large when successive runs disagree."
    )
    requires = ("fc", "init_date", "valid_date", "lead_day", "region_id", "variable")
    order = 32
    family = "spread"
    exclude_from_model = ("sig_spread_members",)
    explanations = {
        "sig_spread": {
            "high": "Large spread between the last three runs ({value:.0f} {unit}) is associated with low forecast reliability.",
            "low": "The last three runs agree closely (spread {value:.0f} {unit}), yet other factors point to a bust.",
        },
        "sig_spread_rel": "Run-to-run spread is {value:.0%} of the forecast amount.",
        "sig_lagged_departure": {
            "high": "The latest run is {value:+.0f} {unit} wetter than the average of recent runs.",
            "low": "The latest run is {value:+.0f} {unit} drier than the average of recent runs.",
        },
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        m = lagged_members(df)
        n = np.isfinite(m).sum(1)
        with np.errstate(all="ignore"):
            mean = np.nanmean(m, axis=1)
            sd = np.nanstd(m, axis=1)
        sd = np.where(n >= 2, sd, np.nan)
        return pd.DataFrame(
            {
                "sig_spread": sd,
                "sig_spread_rel": sd / (np.abs(mean) + 1.0),
                "sig_lagged_departure": np.where(n >= 2, m[:, 0] - mean, np.nan),
                "sig_spread_members": n.astype(float),
            },
            index=df.index,
        )
