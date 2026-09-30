"""Recent verified forecast error for the region (v2 #6).

Only verification that exists at issue time is used: for a forecast issued on day I, the
newest verified rain day is I - verification_lag_days (IMD's day closes at 03 UTC, a day
after the rain day; configs/model.yaml). Window = the 7 newest verified days.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register

WINDOW_DAYS = 7


def trailing_verified_mean(
    rows: pd.DataFrame, value: str, keys: list[str], window: int, lag: int
) -> pd.DataFrame:
    """Per key group and issue day I: mean of ``value`` over rain days [I-lag-window+1, I-lag]."""
    out = []
    for key, g in rows.groupby(keys, sort=False):
        s = g.set_index("valid_date")[value].sort_index()
        s = s[~s.index.duplicated()].asfreq("D")
        m = s.rolling(window, min_periods=max(2, window // 2)).mean().shift(lag)
        frame = m.rename("_v").reset_index().rename(columns={"valid_date": "init_date"})
        for k, v in zip(keys, key if isinstance(key, tuple) else (key,), strict=True):
            frame[k] = v
        out.append(frame)
    if not out:
        return pd.DataFrame(columns=["init_date", "_v", *keys])
    return pd.concat(out, ignore_index=True)


@register
class RecentError(Signal):
    name = "recent_error"
    description = (
        "Mean absolute error and bias of this region's forecasts that had verified by issue "
        "time (last 7 verified days). Persistent recent failures are associated with a regime "
        "the model currently handles poorly."
    )
    requires = ("fc", "obs", "valid_date", "init_date", "region_id", "variable", "lead_day")
    order = 45
    family = "context"
    explanations = {
        "sig_recent_mae_d1": "Recent verified Day-1 forecasts for {region} missed by {value:.0f} {unit} on average, which is associated with continuing errors.",
        "sig_recent_mae_lead": "Recent verified forecasts at this lead missed by {value:.0f} {unit} on average in {region}.",
        "sig_recent_bias_d1": {
            "high": "Recent forecasts for {region} have been too wet (bias {value:+.0f} {unit}).",
            "low": "Recent forecasts for {region} have been too dry (bias {value:+.0f} {unit}), which is associated with missed heavy rain.",
        },
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        lag = ctx.verification_lag_days
        base = df[["region_id", "variable", "lead_day", "valid_date", "fc", "obs"]].copy()
        base["valid_date"] = pd.to_datetime(base["valid_date"])
        base["abs_err"] = (base["fc"] - base["obs"]).abs()
        base["err"] = base["fc"] - base["obs"]
        keys = ["region_id", "variable"]
        d1 = base[base["lead_day"] == 1]
        tables = [
            (
                trailing_verified_mean(d1, "abs_err", keys, WINDOW_DAYS, lag),
                keys,
                "sig_recent_mae_d1",
            ),
            (trailing_verified_mean(d1, "err", keys, WINDOW_DAYS, lag), keys, "sig_recent_bias_d1"),
            (
                trailing_verified_mean(base, "abs_err", [*keys, "lead_day"], WINDOW_DAYS, lag),
                [*keys, "lead_day"],
                "sig_recent_mae_lead",
            ),
        ]
        left = df[["region_id", "variable", "lead_day", "init_date"]].copy()
        left["init_date"] = pd.to_datetime(left["init_date"])
        for tbl, on, name in tables:
            tbl = tbl.rename(columns={"_v": name})
            tbl["init_date"] = pd.to_datetime(tbl["init_date"])
            left = left.merge(tbl, on=[*on, "init_date"], how="left")
        left.index = df.index
        cols = ["sig_recent_mae_d1", "sig_recent_bias_d1", "sig_recent_mae_lead"]
        return left[cols].astype(float).replace([np.inf, -np.inf], np.nan)
