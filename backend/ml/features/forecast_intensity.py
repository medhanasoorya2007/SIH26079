"""How extreme is the forecast itself? Heavy-rain forecasts carry the largest errors."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features.base import Signal, SignalContext, register

HEAVY_RAIN_MM = 64.5  # IMD 'heavy rainfall' 24-h threshold


def imd_rain_category(mm: np.ndarray | pd.Series) -> np.ndarray:
    """IMD warning class used for busts: 0 light/moderate, 1 heavy, 2 very heavy, 3 extremely heavy."""
    from ml.labels.bust import imd_category

    return imd_category(mm)


@register
class ForecastIntensity(Signal):
    name = "forecast_intensity"
    description = (
        "Forecast amount and how unusual it is for the region and month (ratio to the "
        "training-period climatology). Intense forecasts have large absolute errors."
    )
    requires = ("fc", "region_id", "valid_date", "variable")
    order = 20
    family = "context"
    explanations = {
        "sig_fc": {
            "high": "Forecast of {value:.0f} {unit} over {region}: forecasts in this range are associated with missed heavy-rain days.",
            "low": "Forecast rainfall is modest ({value:.0f} {unit}) in a setting associated with missed heavy rain.",
        },
        "sig_fc_clim_ratio": {
            "high": "Forecast is {value:.1f}x the normal for {region} this month; unusual amounts are associated with poor verification.",
            "low": "Forecast is well below normal ({value:.1f}x) for {region} this month.",
        },
        "sig_fc_category": "Forecast sits in IMD warning class {value:.0f} (1 = heavy, 2 = very heavy).",
    }

    def compute(self, df: pd.DataFrame, ctx: SignalContext) -> pd.DataFrame:
        month = pd.to_datetime(df["valid_date"]).dt.month
        key = [df["region_id"], df["variable"], month]
        fit = df.loc[ctx.fit_mask & df["obs"].notna()] if "obs" in df else df.iloc[:0]
        clim = fit.groupby(
            [fit["region_id"], fit["variable"], pd.to_datetime(fit["valid_date"]).dt.month]
        )["obs"].mean()
        idx = pd.MultiIndex.from_arrays(key)
        c = clim.reindex(idx).to_numpy()
        ratio = (df["fc"].to_numpy() + 1.0) / (c + 1.0)
        is_rain = (df["variable"] == "rain").to_numpy()
        return pd.DataFrame(
            {
                "sig_fc": df["fc"].astype(float),
                "sig_fc_clim_ratio": np.where(is_rain, ratio, np.nan),
                "sig_fc_category": np.where(is_rain, imd_rain_category(df["fc"]), np.nan),
            },
            index=df.index,
        )
