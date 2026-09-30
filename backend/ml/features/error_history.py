"""Recent error history: how wrong has the model been here over the past week?

Strictly causal: a row initialised on day I only sees forecasts whose valid day ended
before I (valid_date <= I - 1), i.e. errors a forecaster could know at issue time.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register

WINDOW_DAYS = 7


def _trailing_mean(series: pd.DataFrame, value: str, keys: list[str], window: int) -> pd.DataFrame:
    """Per key group: mean of `value` over valid days [d-window, d-1] (excludes day d)."""
    out = []
    for key, g in series.groupby(keys, sort=False):
        s = g.set_index("valid_date")[value].sort_index()
        s = s[~s.index.duplicated()].asfreq("D")
        # shift(1): value at d uses days up to d-1 only
        m = s.shift(1).rolling(window, min_periods=max(2, window // 2)).mean()
        frame = m.rename("_v").reset_index().rename(columns={"valid_date": "init_date"})
        for k, v in zip(keys, key if isinstance(key, tuple) else (key,), strict=True):
            frame[k] = v
        out.append(frame)
    return (
        pd.concat(out, ignore_index=True)
        if out
        else pd.DataFrame(columns=["init_date", "_v", *keys])
    )


@register
class ErrorHistory(Signal):
    name = "error_history"
    description = (
        "Mean absolute error and bias of this region's recent forecasts that have already "
        "verified (past 7 days). Persistent recent failures indicate a regime the model handles badly."
    )
    requires = ("fc", "obs", "valid_date", "init_date", "region_id", "variable", "lead_day")
    order = 45
    explanations = {
        "sig_recent_mae_d1": "Recent Day-1 forecasts for {region} were off by {value:.0f} {unit} on average over the past week.",
        "sig_recent_mae_lead": "Recent forecasts at this lead time were off by {value:.0f} {unit} on average in {region}.",
        "sig_recent_bias_d1": {
            "high": "The model has been over-forecasting {region} recently (bias {value:+.0f} {unit}).",
            "low": "The model has been under-forecasting {region} recently (bias {value:+.0f} {unit}).",
        },
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        base = df[["region_id", "variable", "lead_day", "valid_date", "fc", "obs"]].copy()
        base["valid_date"] = pd.to_datetime(base["valid_date"])
        base["abs_err"] = (base["fc"] - base["obs"]).abs()
        base["err"] = base["fc"] - base["obs"]
        keys = ["region_id", "variable"]
        d1 = base[base["lead_day"] == 1]
        mae_d1 = _trailing_mean(d1, "abs_err", keys, WINDOW_DAYS).rename(
            columns={"_v": "sig_recent_mae_d1"}
        )
        bias_d1 = _trailing_mean(d1, "err", keys, WINDOW_DAYS).rename(
            columns={"_v": "sig_recent_bias_d1"}
        )
        mae_ld = _trailing_mean(base, "abs_err", [*keys, "lead_day"], WINDOW_DAYS).rename(
            columns={"_v": "sig_recent_mae_lead"}
        )
        left = df[["region_id", "variable", "lead_day", "init_date"]].copy()
        left["init_date"] = pd.to_datetime(left["init_date"])
        for tbl, on in [(mae_d1, keys), (bias_d1, keys), (mae_ld, [*keys, "lead_day"])]:
            tbl["init_date"] = pd.to_datetime(tbl["init_date"])
            left = left.merge(tbl, on=[*on, "init_date"], how="left")
        left.index = df.index
        cols = ["sig_recent_mae_d1", "sig_recent_bias_d1", "sig_recent_mae_lead"]
        return left[cols].astype(float).replace([np.inf, -np.inf], np.nan)
